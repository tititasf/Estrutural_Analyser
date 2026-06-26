"""Auditable learning store for N1 LAJ interpretation.

This store is intentionally separated from project_data.vision. It records
human and engine events for N1 slab interpretation without enabling any
calibrator automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_DATA_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_ENGREV_LAJ_N1_INTERPRETACAO_LEARNING_DB_PATH = Path(
    "D:/Agente-cad-PYSIDE/engrev_laj_n1_interpretacao_learning.vision"
)

EVENTS_TABLE = "engrev_laj_n1_interpretacao_events"
FEATURES_TABLE = "engrev_laj_n1_interpretacao_features"
CALIBRATORS_TABLE = "engrev_laj_n1_interpretacao_calibrator_versions"

EVENT_TYPES = {
    "baseline_generated",
    "context_generated",
    "engrev_assisted_generated",
    "cascade_generated",
    "human_laje_outline_validated",
    "human_laje_outline_rejected",
    "calibrator_suggested",
    "calibrator_applied",
    "regression_failed",
    "regression_passed",
}

DEFAULT_ENGINE_VERSION = "structural_analyzer:laj-n1-interpretação-v1"
DEFAULT_CALIBRATOR_VERSION = "disabled"


def file_sha256(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_engrev_laj_n1_interpretacao_learning_schema(
    db_path: str | Path = DEFAULT_ENGREV_LAJ_N1_INTERPRETACAO_LEARNING_DB_PATH,
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {EVENTS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                obra_name TEXT,
                pavimento TEXT,
                classe TEXT NOT NULL DEFAULT 'LAJ',
                elemento_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                analysis_mode TEXT NOT NULL,
                source_dxf_path TEXT,
                structural_clean_hash TEXT,
                n2_cut_hash TEXT,
                engine_version TEXT NOT NULL,
                calibrator_version TEXT NOT NULL,
                operator TEXT,
                notes TEXT,
                payload_json TEXT
            );

            CREATE TABLE IF NOT EXISTS {FEATURES_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                obra_name TEXT,
                pavimento TEXT,
                classe TEXT NOT NULL DEFAULT 'LAJ',
                elemento_id TEXT NOT NULL,
                label_json TEXT,
                bbox_n1_json TEXT,
                bbox_n2_json TEXT,
                laje_outline_segs_json TEXT,
                area_cm2 REAL,
                vertex_count INTEGER,
                candidate_line_count INTEGER,
                accepted_line_count INTEGER,
                rejected_line_count INTEGER,
                confidence_before REAL,
                confidence_after REAL,
                features_json TEXT,
                FOREIGN KEY(event_id) REFERENCES {EVENTS_TABLE}(id)
            );

            CREATE TABLE IF NOT EXISTS {CALIBRATORS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                version_name TEXT NOT NULL,
                training_set_hash TEXT NOT NULL,
                sample_count INTEGER NOT NULL,
                params_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate'
            );

            CREATE INDEX IF NOT EXISTS idx_laj_n1_events_item
                ON {EVENTS_TABLE}(obra_name, pavimento, classe, elemento_id, event_type);
            CREATE INDEX IF NOT EXISTS idx_laj_n1_events_mode
                ON {EVENTS_TABLE}(analysis_mode, created_at);
            CREATE INDEX IF NOT EXISTS idx_laj_n1_calibrators_status
                ON {CALIBRATORS_TABLE}(status, created_at);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _operator() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def record_engrev_laj_n1_interpretacao_event(
    *,
    event_type: str,
    elemento_id: str,
    analysis_mode: str = "baseline",
    obra_name: str | None = None,
    pavimento: str | None = None,
    source_dxf_path: str | Path | None = None,
    n2_cut_path: str | Path | None = None,
    engine_version: str = DEFAULT_ENGINE_VERSION,
    calibrator_version: str = DEFAULT_CALIBRATOR_VERSION,
    operator: str | None = None,
    notes: str | None = None,
    payload: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    learning_db_path: str | Path = DEFAULT_ENGREV_LAJ_N1_INTERPRETACAO_LEARNING_DB_PATH,
) -> int:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type invalido: {event_type}")
    if not elemento_id:
        raise ValueError("elemento_id e obrigatorio")
    if analysis_mode not in {"baseline", "context", "engrev_assisted", "cascade"}:
        raise ValueError(f"analysis_mode invalido: {analysis_mode}")

    ensure_engrev_laj_n1_interpretacao_learning_schema(learning_db_path)
    features = features or {}

    conn = sqlite3.connect(str(learning_db_path))
    try:
        cur = conn.execute(
            f"""INSERT INTO {EVENTS_TABLE}
                (created_at, obra_name, pavimento, classe, elemento_id, event_type,
                 analysis_mode, source_dxf_path, structural_clean_hash, n2_cut_hash,
                 engine_version, calibrator_version, operator, notes, payload_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now().isoformat(),
                obra_name,
                pavimento,
                "LAJ",
                elemento_id,
                event_type,
                analysis_mode,
                str(source_dxf_path) if source_dxf_path else None,
                file_sha256(source_dxf_path),
                file_sha256(n2_cut_path),
                engine_version,
                calibrator_version,
                operator or _operator(),
                notes,
                _json_dumps(payload),
            ),
        )
        event_id = int(cur.lastrowid)
        conn.execute(
            f"""INSERT INTO {FEATURES_TABLE}
                (event_id, obra_name, pavimento, classe, elemento_id,
                 label_json, bbox_n1_json, bbox_n2_json, laje_outline_segs_json,
                 area_cm2, vertex_count, candidate_line_count, accepted_line_count,
                 rejected_line_count, confidence_before, confidence_after, features_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id,
                obra_name,
                pavimento,
                "LAJ",
                elemento_id,
                _json_dumps(features.get("label")),
                _json_dumps(features.get("bbox_n1")),
                _json_dumps(features.get("bbox_n2")),
                _json_dumps(features.get("laje_outline_segs")),
                features.get("area_cm2"),
                features.get("vertex_count"),
                features.get("candidate_line_count"),
                features.get("accepted_line_count"),
                features.get("rejected_line_count"),
                features.get("confidence_before"),
                features.get("confidence_after"),
                _json_dumps(features),
            ),
        )
        conn.commit()
        return event_id
    finally:
        conn.close()


def record_human_laje_outline_validated(
    *,
    elemento_id: str,
    laje_outline_segs: Any,
    obra_name: str | None = None,
    pavimento: str | None = None,
    analysis_mode: str = "engrev_assisted",
    notes: str | None = None,
    learning_db_path: str | Path = DEFAULT_ENGREV_LAJ_N1_INTERPRETACAO_LEARNING_DB_PATH,
) -> int:
    return record_engrev_laj_n1_interpretacao_event(
        event_type="human_laje_outline_validated",
        elemento_id=elemento_id,
        analysis_mode=analysis_mode,
        obra_name=obra_name,
        pavimento=pavimento,
        notes=notes,
        features={"laje_outline_segs": laje_outline_segs},
        learning_db_path=learning_db_path,
    )
