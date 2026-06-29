#!/usr/bin/env python3
"""Health check read-only do ecossistema RAG do CAD-Analyzer."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DEFAULT_FAISS_DIR = Path("D:/Agente-cad-PYSIDE/data/vectors/faiss")
DEFAULT_ARTIFACT_ROOT = Path("D:/Agente-cad-PYSIDE/data/artifact_memory")
DEFAULT_ACTIVE_LEARNING_ROOT = Path("D:/Agente-cad-PYSIDE/data/vectors/active_learning")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_health(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    obras_root: str | Path = DEFAULT_OBRAS_ROOT,
    faiss_dir: str | Path = DEFAULT_FAISS_DIR,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    active_learning_root: str | Path = DEFAULT_ACTIVE_LEARNING_ROOT,
) -> dict[str, Any]:
    db_path = Path(db_path)
    obras_root = Path(obras_root)
    faiss_dir = Path(faiss_dir)
    artifact_root = Path(artifact_root)
    active_learning_root = Path(active_learning_root)
    report: dict[str, Any] = {
        "status": "ok",
        "read_only": True,
        "db_path": str(db_path),
        "tables": {},
        "artifacts": Counter(),
        "faiss": Counter(),
        "snapshots": Counter(),
        "active_learning": Counter(),
        "issues": [],
    }

    if not db_path.exists():
        report["issues"].append({"severity": "error", "code": "db_missing", "detail": str(db_path)})
    else:
        with sqlite3.connect(db_path) as conn:
            for table in (
                "semantic_rag_kb",
                "reverse_eng_fichas",
                "fase3_fichas",
                "crop_learning_events",
                "rag_artifact_validations",
                "training_events",
                "item_attention_notes",
                "human_event_logs",
            ):
                report["tables"][table] = (
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    if _table_exists(conn, table)
                    else 0
                )

            if report["tables"]["semantic_rag_kb"] == 0:
                report["issues"].append(
                    {"severity": "warning", "code": "semantic_bridge_empty", "detail": "semantic_rag_kb=0"}
                )
            if _table_exists(conn, "human_event_logs") and "status" in _columns(conn, "human_event_logs"):
                for status, count in conn.execute(
                    "SELECT status, COUNT(*) FROM human_event_logs GROUP BY status"
                ):
                    report["active_learning"][str(status or "unknown")] += count

            if _table_exists(conn, "rag_artifact_validations"):
                cols = _columns(conn, "rag_artifact_validations")
                if "status" in cols:
                    for status, count in conn.execute(
                        "SELECT status, COUNT(*) FROM rag_artifact_validations GROUP BY status"
                    ):
                        report["artifacts"][str(status or "unknown")] = count
                if {"status", "render_status"} <= cols:
                    for render_status, count in conn.execute(
                        """
                        SELECT render_status, COUNT(*)
                        FROM rag_artifact_validations
                        WHERE status='validated'
                        GROUP BY render_status
                        """
                    ):
                        report["artifacts"][f"render_{render_status or 'missing'}"] = count
                if {"status", "render_status", "thumbnail_path"} <= cols:
                    paths = conn.execute(
                        """
                        SELECT thumbnail_path FROM rag_artifact_validations
                        WHERE status='validated' AND render_status='ready'
                        """
                    ).fetchall()
                    missing = sum(1 for (path,) in paths if not path or not Path(path).exists())
                    report["artifacts"]["missing_thumbnail"] = missing
                    if missing:
                        report["issues"].append(
                            {
                                "severity": "warning",
                                "code": "artifact_thumbnail_missing",
                                "detail": f"{missing} renders validados sem PNG acessivel",
                            }
                        )

    for meta_path in sorted(faiss_dir.glob("*_meta.json")):
        if meta_path.name == "REGISTRY.json":
            continue
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            rows = payload if isinstance(payload, list) else list(payload.values())
            report["faiss"]["stores"] += 1
            report["faiss"]["metadata_rows"] += len(rows)
            for row in rows:
                if isinstance(row, dict):
                    report["faiss"][str(row.get("tier") or "T0")] += 1
        except (OSError, ValueError, TypeError) as exc:
            report["issues"].append(
                {"severity": "warning", "code": "faiss_meta_invalid", "detail": f"{meta_path}: {exc}"}
            )

    tombstones_path = faiss_dir / "rag_tombstones.json"
    if tombstones_path.exists():
        try:
            tombstones = json.loads(tombstones_path.read_text(encoding="utf-8"))
            report["faiss"]["tombstones"] = len(tombstones) if isinstance(tombstones, dict) else 0
        except (OSError, json.JSONDecodeError):
            report["issues"].append(
                {"severity": "warning", "code": "tombstones_invalid", "detail": str(tombstones_path)}
            )

    for store in ("candidates", "approved"):
        store_dir = active_learning_root / store
        pointer_path = store_dir / "CURRENT.json"
        if not pointer_path.exists():
            continue
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            index_path = store_dir / pointer["index_file"]
            meta_path = store_dir / pointer["meta_file"]
            if _sha256(index_path) != pointer["index_sha256"]:
                raise ValueError("index hash mismatch")
            if _sha256(meta_path) != pointer["meta_sha256"]:
                raise ValueError("metadata hash mismatch")
            rows = json.loads(meta_path.read_text(encoding="utf-8"))
            if len(rows) != int(pointer["count"]):
                raise ValueError("pointer count mismatch")
            if store == "candidates" and any(row.get("tier") != "T0" for row in rows):
                raise ValueError("candidate store contains non-T0 row")
            if store == "approved" and any(row.get("tier") not in {"T1", "T2"} for row in rows):
                raise ValueError("approved store contains non-approved tier")
            report["active_learning"][f"{store}_vectors"] = len(rows)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            report["issues"].append(
                {"severity": "error", "code": "active_learning_store_invalid", "detail": f"{store}: {exc}"}
            )

    for manifest_path in obras_root.glob("*/obra_rag/manifest.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("scope") != "obra_local" or payload.get("promotion_policy") != "never_auto_global":
                raise ValueError("politica local ausente")
            report["snapshots"]["valid"] += 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            report["snapshots"]["invalid"] += 1
            report["issues"].append(
                {"severity": "warning", "code": "obra_snapshot_invalid", "detail": f"{manifest_path}: {exc}"}
            )

    report["artifacts"]["manifest_files"] = len(list(artifact_root.rglob("*.json"))) if artifact_root.exists() else 0
    report["artifacts"] = dict(report["artifacts"])
    report["faiss"] = dict(report["faiss"])
    report["snapshots"] = dict(report["snapshots"])
    report["active_learning"] = dict(report["active_learning"])
    if any(issue["severity"] == "error" for issue in report["issues"]):
        report["status"] = "error"
    elif report["issues"]:
        report["status"] = "warning"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--obras-root", default=str(DEFAULT_OBRAS_ROOT))
    parser.add_argument("--faiss-dir", default=str(DEFAULT_FAISS_DIR))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--active-learning-root", default=str(DEFAULT_ACTIVE_LEARNING_ROOT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = collect_health(
        db_path=args.db_path,
        obras_root=args.obras_root,
        faiss_dir=args.faiss_dir,
        artifact_root=args.artifact_root,
        active_learning_root=args.active_learning_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
