"""Storage auditavel para aprendizagem de recortes LAJ da engenharia reversa.

Esta camada registra eventos e features de recorte de lajes sem alterar o motor atual.
O calibrador/aprendizado ativo fica desligado ate regressao explicita.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


EVENT_TYPES = {
    "motor_generated",
    "human_saved",
    "human_approved",
    "calibrator_suggested",
    "calibrator_applied",
    "regression_failed",
    "regression_passed",
}

DEFAULT_MOTOR_VERSION = "recorte_motor:instrumented-v1"
DEFAULT_CALIBRATOR_VERSION = "disabled"
DEFAULT_PROJECT_DATA_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_ENGREV_LAJ_RECORTE_LEARNING_DB_PATH = Path(
    "D:/Agente-cad-PYSIDE/engrev_laj_recorte_learning.vision"
)

ENGREV_LAJ_RECORTE_EVENTS_TABLE = "engrev_laj_recorte_learning_events"
ENGREV_LAJ_RECORTE_FEATURES_TABLE = "engrev_laj_recorte_learning_features"
ENGREV_LAJ_RECORTE_CALIBRATORS_TABLE = "engrev_laj_recorte_calibrator_versions"


def file_sha256(path: str | Path | None) -> str | None:
    """Retorna hash SHA-256 do arquivo, ou None se o arquivo nao existir."""
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


def infer_pavimento_from_path(path: str | Path | None) -> str | None:
    """Infere pavimento a partir dos nomes de pastas conhecidos dos recortes."""
    if not path:
        return None
    parts = [str(part) for part in Path(path).parts]
    for part in reversed(parts):
        norm = part.upper()
        norm_ascii = (
            norm.replace("°", "")
            .replace("º", "")
            .replace("É", "E")
            .replace("Ê", "E")
        )
        if "COBERTURA" in norm_ascii:
            return "COBERTURA"
        if "TIPO" in norm_ascii:
            return "TIP"
        if "TERREO" in norm_ascii or norm_ascii.strip() == "TER":
            return "TER"
        if "PAV" in norm_ascii:
            import re

            m = re.search(r"(\d+)\s*PAV", norm_ascii)
            if m:
                return f"{int(m.group(1))}_PAV"
            return part
    return None


def ensure_engrev_laj_recorte_learning_schema(
    db_path: str | Path = DEFAULT_ENGREV_LAJ_RECORTE_LEARNING_DB_PATH,
) -> None:
    """Cria as tabelas especificas de aprendizagem dos recortes LAJ ER."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS engrev_laj_recorte_learning_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                obra_name TEXT NOT NULL,
                pavimento TEXT,
                classe TEXT NOT NULL,
                elemento_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source_recorte_path TEXT,
                approved_recorte_path TEXT,
                motor_version TEXT,
                calibrator_version TEXT,
                operator TEXT,
                notes TEXT,
                source_hash TEXT,
                approved_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS engrev_laj_recorte_learning_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                obra_name TEXT NOT NULL,
                pavimento TEXT,
                classe TEXT NOT NULL,
                elemento_id TEXT NOT NULL,
                bbox_motor_json TEXT,
                bbox_aprovado_json TEXT,
                delta_left REAL,
                delta_right REAL,
                delta_bottom REAL,
                delta_top REAL,
                entity_count_motor INTEGER,
                entity_count_aprovado INTEGER,
                own_label_count INTEGER,
                neighbor_label_count INTEGER,
                dimension_text_count INTEGER,
                panel_line_count INTEGER,
                contour_closure_score REAL,
                neighbor_capture_score REAL,
                confidence_before REAL,
                confidence_after REAL,
                features_json TEXT,
                FOREIGN KEY(event_id) REFERENCES engrev_laj_recorte_learning_events(id)
            );

            CREATE TABLE IF NOT EXISTS engrev_laj_recorte_calibrator_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                classe TEXT NOT NULL,
                version_name TEXT NOT NULL,
                training_set_hash TEXT NOT NULL,
                sample_count INTEGER NOT NULL,
                params_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate'
            );

            CREATE INDEX IF NOT EXISTS idx_engrev_laj_recorte_learning_events_item
                ON engrev_laj_recorte_learning_events(obra_name, pavimento, classe, elemento_id, event_type);
            CREATE INDEX IF NOT EXISTS idx_engrev_laj_recorte_learning_events_hash
                ON engrev_laj_recorte_learning_events(source_hash, approved_hash);
            CREATE INDEX IF NOT EXISTS idx_engrev_laj_recorte_calibrator_versions_status
                ON engrev_laj_recorte_calibrator_versions(classe, status, created_at);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_for_path(project_db_path: str | Path, path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    project_db = Path(project_db_path)
    if not project_db.exists():
        return {}
    conn = sqlite3.connect(str(project_db))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT obra_name, elemento_id, classe, recorte_path, bbox_json,
                      entity_count, status, confidence
               FROM reverse_eng_recortes
               WHERE recorte_path=?
               ORDER BY id DESC
               LIMIT 1""",
            (str(path),),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _event_operator() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"


def _feature_payload(row: dict[str, Any], event_type: str, extra: dict[str, Any] | None) -> str:
    payload = {
        "status": row.get("status"),
        "recorte_path": row.get("recorte_path"),
        "instrumentation_only": True,
        "learning_enabled": os.environ.get("RECORTE_LEARNING_ENABLED", "false").lower() == "true",
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def record_engrev_laj_recorte_learning_event(
    project_db_path: str | Path = DEFAULT_PROJECT_DATA_DB_PATH,
    *,
    event_type: str,
    obra_name: str,
    classe: str,
    elemento_id: str,
    pavimento: str | None = None,
    source_recorte_path: str | Path | None = None,
    approved_recorte_path: str | Path | None = None,
    motor_version: str | None = None,
    calibrator_version: str | None = None,
    operator: str | None = None,
    notes: str | None = None,
    features_extra: dict[str, Any] | None = None,
    learning_db_path: str | Path = DEFAULT_ENGREV_LAJ_RECORTE_LEARNING_DB_PATH,
) -> int:
    """Registra evento e snapshot simples de features.

    A funcao nao treina nem altera motor; apenas versiona evidencia.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type invalido: {event_type}")
    if not obra_name or not classe or not elemento_id:
        raise ValueError("obra_name, classe e elemento_id sao obrigatorios")

    ensure_engrev_laj_recorte_learning_schema(learning_db_path)
    source_path = str(source_recorte_path) if source_recorte_path else None
    approved_path = str(approved_recorte_path) if approved_recorte_path else None
    primary_path = approved_path or source_path
    pavimento = pavimento or infer_pavimento_from_path(primary_path)

    conn = sqlite3.connect(str(learning_db_path))
    try:
        row = _row_for_path(project_db_path, primary_path)
        now = datetime.now().isoformat()
        source_hash = file_sha256(source_path)
        approved_hash = file_sha256(approved_path)
        cur = conn.execute(
            """INSERT INTO engrev_laj_recorte_learning_events
               (created_at, obra_name, pavimento, classe, elemento_id, event_type,
                source_recorte_path, approved_recorte_path, motor_version,
                calibrator_version, operator, notes, source_hash, approved_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                now,
                obra_name,
                pavimento,
                classe,
                elemento_id,
                event_type,
                source_path,
                approved_path,
                motor_version or DEFAULT_MOTOR_VERSION,
                calibrator_version or DEFAULT_CALIBRATOR_VERSION,
                operator or _event_operator(),
                notes,
                source_hash,
                approved_hash,
            ),
        )
        event_id = int(cur.lastrowid)

        is_motor = event_type == "motor_generated"
        entity_count = row.get("entity_count")
        confidence = row.get("confidence")
        conn.execute(
            """INSERT INTO engrev_laj_recorte_learning_features
               (event_id, obra_name, pavimento, classe, elemento_id,
                bbox_motor_json, bbox_aprovado_json,
                entity_count_motor, entity_count_aprovado,
                confidence_before, confidence_after, features_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id,
                obra_name,
                pavimento,
                classe,
                elemento_id,
                row.get("bbox_json") if is_motor else None,
                row.get("bbox_json") if not is_motor else None,
                entity_count if is_motor else None,
                entity_count if not is_motor else None,
                confidence if is_motor else None,
                confidence if not is_motor else None,
                _feature_payload(row, event_type, features_extra),
            ),
        )
        conn.commit()
        return event_id
    finally:
        conn.close()
