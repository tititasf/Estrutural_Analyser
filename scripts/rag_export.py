#!/usr/bin/env python3
"""Exporta uma fotografia auditavel do RAG sem modificar as fontes."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DEFAULT_FAISS_DIR = Path("D:/Agente-cad-PYSIDE/data/vectors/faiss")
DEFAULT_ARTIFACT_ROOT = Path("D:/Agente-cad-PYSIDE/data/artifact_memory")
DEFAULT_ACTIVE_LEARNING_ROOT = Path("D:/Agente-cad-PYSIDE/data/vectors/active_learning")
DEFAULT_CANDIDATES_ROOT = Path("D:/Agente-cad-PYSIDE/data/active_learning_candidates")
EXPORT_TABLES = (
    "semantic_rag_kb",
    "crop_learning_events",
    "rag_artifact_validations",
    "training_events",
    "item_attention_notes",
    "human_event_logs",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def export_rag_bundle(
    output_dir: str | Path,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    obras_root: str | Path = DEFAULT_OBRAS_ROOT,
    faiss_dir: str | Path = DEFAULT_FAISS_DIR,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    active_learning_root: str | Path = DEFAULT_ACTIVE_LEARNING_ROOT,
    candidates_root: str | Path = DEFAULT_CANDIDATES_ROOT,
    include_binary: bool = False,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    db_path = Path(db_path)
    obras_root = Path(obras_root)
    faiss_dir = Path(faiss_dir)
    artifact_root = Path(artifact_root)
    active_learning_root = Path(active_learning_root)
    candidates_root = Path(candidates_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            for table in EXPORT_TABLES:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                rows = [dict(row) for row in conn.execute(f"SELECT * FROM {table}")] if exists else []
                _write_json(output_dir / "tables" / f"{table}.json", rows)

    for source in sorted(obras_root.glob("*/obra_rag/manifest.json")):
        destination = output_dir / "obra_snapshots" / source.parents[1].name / "manifest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    for source in sorted(artifact_root.rglob("*.json")) if artifact_root.exists() else []:
        destination = output_dir / "artifact_manifests" / source.relative_to(artifact_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if include_binary and artifact_root.exists():
        for source in sorted(artifact_root.rglob("*.png")):
            destination = output_dir / "artifact_images" / source.relative_to(artifact_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    if candidates_root.exists():
        for source in sorted(candidates_root.rglob("*.json")):
            destination = output_dir / "active_learning_candidates" / source.relative_to(candidates_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    if active_learning_root.exists():
        patterns = ("*.json", "*.index") if include_binary else ("*.json",)
        for pattern in patterns:
            for source in sorted(active_learning_root.rglob(pattern)):
                destination = output_dir / "active_learning_stores" / source.relative_to(active_learning_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

    for name in ("rag_tombstones.json", "REGISTRY.json"):
        source = faiss_dir / name
        if source.exists():
            destination = output_dir / "faiss_control" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    registry = db_path.parent / "data" / "classe_registry.json"
    if registry.exists():
        destination = output_dir / "registries" / registry.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(registry, destination)

    files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.json":
            files.append(
                {
                    "path": path.relative_to(output_dir).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    manifest = {
        "schema_version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "read_only_source_export": True,
        "is_global_truth": False,
        "include_binary": bool(include_binary),
        "source_db": str(db_path),
        "files": files,
    }
    _write_json(output_dir / "MANIFEST.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--obras-root", default=str(DEFAULT_OBRAS_ROOT))
    parser.add_argument("--faiss-dir", default=str(DEFAULT_FAISS_DIR))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--active-learning-root", default=str(DEFAULT_ACTIVE_LEARNING_ROOT))
    parser.add_argument("--candidates-root", default=str(DEFAULT_CANDIDATES_ROOT))
    parser.add_argument("--include-binary", action="store_true")
    args = parser.parse_args()
    manifest = export_rag_bundle(
        args.output_dir,
        db_path=args.db_path,
        obras_root=args.obras_root,
        faiss_dir=args.faiss_dir,
        artifact_root=args.artifact_root,
        active_learning_root=args.active_learning_root,
        candidates_root=args.candidates_root,
        include_binary=args.include_binary,
    )
    print(json.dumps({"status": "ok", "files": len(manifest["files"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
