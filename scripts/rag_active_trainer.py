#!/usr/bin/env python3
"""Indexa propostas MCP em stores isolados; nunca altera `estruturais.index`."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mcp import db_bridge  # noqa: E402

DB_PATH = ROOT / "project_data.vision"
VECTOR_ROOT = ROOT / "data" / "vectors" / "active_learning"
MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384


def normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (vectors / norms).astype(np.float32)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextlib.contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _eligible_rows(db_path: Path, approved: bool) -> list[dict[str, Any]]:
    status = "APPROVED" if approved else "PROPOSED"
    tier = "T1" if approved else "T0"
    db_bridge.ensure_event_sourcing_tables(db_path)
    with sqlite3.connect(str(db_path), timeout=15.0) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT log_id, obra_id, classe, item_id, fase_editada, ui_context,
                       timestamp, user_reason, source_agent, candidate_path,
                       status, tier
                FROM human_event_logs
                WHERE status=? AND tier=? AND candidate_path IS NOT NULL
                ORDER BY timestamp, log_id
                """,
                (status, tier),
            ).fetchall()
        ]


def _load_proposals(rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    texts: list[str] = []
    metadata: list[dict[str, Any]] = []
    for row in rows:
        path = Path(str(row.get("candidate_path") or ""))
        try:
            proposal = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if proposal.get("source_event_id") != row["log_id"]:
            continue
        text = str(proposal.get("explanation") or "").strip()
        if not text:
            continue
        texts.append(text)
        metadata.append(
            {
                "id": row["log_id"],
                "source_event_id": row["log_id"],
                "tipo": proposal.get("proposal_type"),
                "classe": row.get("classe"),
                "item_id": row.get("item_id"),
                "obra": row.get("obra_id"),
                "fase": row.get("fase_editada"),
                "text": text,
                "tier": row.get("tier"),
                "status": row.get("status"),
                "scope": proposal.get("scope"),
                "is_global_truth": bool(row.get("tier") in {"T1", "T2"}),
                "requires_human_approval": row.get("tier") == "T0",
                "timestamp": row.get("timestamp"),
            }
        )
    return texts, metadata


def _write_generation(
    *,
    store_name: str,
    vectors: np.ndarray,
    metadata: list[dict[str, Any]],
    vector_root: Path,
) -> dict[str, Any]:
    store_dir = vector_root / store_name
    store_dir.mkdir(parents=True, exist_ok=True)
    generation = uuid.uuid4().hex
    index_path = store_dir / f"{generation}.index"
    meta_path = store_dir / f"{generation}_meta.json"
    pointer_path = store_dir / "CURRENT.json"
    pointer_temp = store_dir / f"CURRENT.{generation}.tmp"

    index = faiss.IndexFlatIP(EMBED_DIM)
    if len(vectors):
        index.add(vectors)
    faiss.write_index(index, str(index_path))
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    check_index = faiss.read_index(str(index_path))
    check_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if check_index.ntotal != len(check_meta):
        raise RuntimeError("geração FAISS inconsistente")

    pointer = {
        "schema_version": 1,
        "store": store_name,
        "generation": generation,
        "index_file": index_path.name,
        "meta_file": meta_path.name,
        "count": check_index.ntotal,
        "dimension": check_index.d,
        "model": MODEL_NAME,
        "index_sha256": _sha256(index_path),
        "meta_sha256": _sha256(meta_path),
    }
    pointer_temp.write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(pointer_temp, pointer_path)
    return pointer


def build_store(
    *,
    approved: bool = False,
    db_path: str | Path = DB_PATH,
    vector_root: str | Path = VECTOR_ROOT,
    model: Any | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    vector_root = Path(vector_root)
    rows = _eligible_rows(db_path, approved)
    texts, metadata = _load_proposals(rows)
    store_name = "approved" if approved else "candidates"
    lock_path = vector_root / f"{store_name}.lock"

    if texts:
        model = model or SentenceTransformer(MODEL_NAME)
        vectors = normalize(
            np.asarray(model.encode(texts, show_progress_bar=False, batch_size=64))
        )
    else:
        vectors = np.empty((0, EMBED_DIM), dtype=np.float32)

    with _exclusive_lock(lock_path):
        pointer = _write_generation(
            store_name=store_name,
            vectors=vectors,
            metadata=metadata,
            vector_root=vector_root,
        )

    if approved:
        for position, row in enumerate(metadata):
            db_bridge.mark_event_as_processed(
                row["source_event_id"],
                f"active_learning:approved:{pointer['generation']}:{position}",
                db_path=db_path,
            )
    return {
        "status": "ok",
        "store": store_name,
        "count": len(metadata),
        "generation": pointer["generation"],
        "modified_structural_index": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--vector-root", default=str(VECTOR_ROOT))
    parser.add_argument(
        "--approved",
        action="store_true",
        help="Indexa somente propostas já aprovadas humanamente em store separado",
    )
    args = parser.parse_args()
    result = build_store(
        approved=args.approved,
        db_path=args.db,
        vector_root=args.vector_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
