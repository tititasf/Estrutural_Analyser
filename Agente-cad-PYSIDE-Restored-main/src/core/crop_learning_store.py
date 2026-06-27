"""Generic crop learning storage for reverse-engineering crops.

Human approval of a crop teaches where/how to crop. It must not validate
F5/N2 fields, N4 drawings, or promote an item into the global RAG of fichas.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_METHOD_VERSION = "crop_learning:v1"
VALID_STATUSES = {"validated", "revoked"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _operator() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"


def _json(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


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


def ensure_crop_learning_schema(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create crop learning tables in the project database."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crop_learning_events (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                status TEXT NOT NULL DEFAULT 'validated',
                obra_name TEXT NOT NULL,
                pavimento TEXT,
                classe TEXT NOT NULL,
                elemento_id TEXT NOT NULL,
                source_dxf TEXT,
                source_layer TEXT,
                source_color TEXT,
                recorte_path TEXT NOT NULL,
                recorte_hash TEXT,
                bbox_json TEXT,
                polygon_json TEXT,
                margin_profile_json TEXT,
                nearby_entities_json TEXT,
                method_version TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                revoked_by TEXT,
                revoked_at TEXT,
                revoked_reason TEXT,
                notes TEXT,
                metadata_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_crop_learning_active_class
                ON crop_learning_events(classe, status, created_at);
            CREATE INDEX IF NOT EXISTS idx_crop_learning_item
                ON crop_learning_events(obra_name, pavimento, classe, elemento_id);
            CREATE INDEX IF NOT EXISTS idx_crop_learning_recorte
                ON crop_learning_events(recorte_path, status);
            """
        )
        conn.commit()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _fetch_reverse_recorte(conn: sqlite3.Connection, recorte_path: str) -> dict[str, Any]:
    if not _table_exists(conn, "reverse_eng_recortes"):
        return {}
    cols = _columns(conn, "reverse_eng_recortes")
    wanted = [
        "obra_name",
        "pavimento",
        "classe",
        "elemento_id",
        "recorte_path",
        "bbox_json",
        "entity_count",
        "confidence",
        "status",
        "projeto_id",
    ]
    available = [col for col in wanted if col in cols]
    if not available:
        return {}
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        f"SELECT {','.join(available)} FROM reverse_eng_recortes "
        "WHERE recorte_path=? ORDER BY id DESC LIMIT 1",
        (recorte_path,),
    ).fetchone()
    return dict(row) if row else {}


def record_crop_learning_event(
    *,
    obra_name: str,
    classe: str,
    elemento_id: str,
    recorte_path: str | Path,
    pavimento: str | None = None,
    source_dxf: str | None = None,
    source_layer: str | None = None,
    source_color: str | None = None,
    bbox_json: str | dict[str, Any] | None = None,
    polygon_json: str | dict[str, Any] | None = None,
    margin_profile_json: str | dict[str, Any] | None = None,
    nearby_entities_json: str | dict[str, Any] | None = None,
    method_version: str | None = None,
    approved_by: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str:
    """Persist a human-approved crop example.

    This function intentionally does not update reverse_eng_fichas and does not
    index any ficha in global RAG.
    """
    if not obra_name or not classe or not elemento_id:
        raise ValueError("obra_name, classe and elemento_id are required")
    recorte = str(recorte_path)
    if not recorte:
        raise ValueError("recorte_path is required")

    ensure_crop_learning_schema(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        row = _fetch_reverse_recorte(conn, recorte)
        event_id = str(uuid.uuid4())
        now = _now()
        payload_metadata = {
            "source": "diagnostic_reverse_hub",
            "reverse_recorte_status": row.get("status"),
            "entity_count": row.get("entity_count"),
            "confidence": row.get("confidence"),
            "instrumentation_only": True,
        }
        if metadata:
            payload_metadata.update(metadata)
        conn.execute(
            """
            INSERT INTO crop_learning_events (
                id, created_at, updated_at, status,
                obra_name, pavimento, classe, elemento_id,
                source_dxf, source_layer, source_color,
                recorte_path, recorte_hash, bbox_json, polygon_json,
                margin_profile_json, nearby_entities_json, method_version,
                approved_by, approved_at, notes, metadata_json
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                now,
                now,
                "validated",
                obra_name,
                pavimento or row.get("pavimento") or row.get("projeto_id"),
                classe,
                elemento_id,
                source_dxf,
                source_layer,
                source_color,
                recorte,
                file_sha256(recorte),
                _json(bbox_json if bbox_json is not None else row.get("bbox_json")),
                _json(polygon_json),
                _json(margin_profile_json),
                _json(nearby_entities_json),
                method_version or DEFAULT_METHOD_VERSION,
                approved_by or _operator(),
                now,
                notes,
                _json(payload_metadata),
            ),
        )
        conn.commit()
        return event_id


def revoke_crop_learning_event(
    event_id: str,
    *,
    reason: str,
    revoked_by: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    """Tombstone a crop learning event without deleting history."""
    ensure_crop_learning_schema(db_path)
    now = _now()
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            """
            UPDATE crop_learning_events
            SET status='revoked',
                revoked_by=?,
                revoked_at=?,
                revoked_reason=?,
                updated_at=?
            WHERE id=? AND status='validated'
            """,
            (revoked_by or _operator(), now, reason, now, event_id),
        )
        conn.commit()
        return cur.rowcount > 0


def revoke_crop_learning_events_for_recorte(
    recorte_path: str | Path,
    *,
    reason: str,
    revoked_by: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Tombstone every active crop example derived from one crop file."""
    ensure_crop_learning_schema(db_path)
    now = _now()
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            """
            UPDATE crop_learning_events
            SET status='revoked',
                revoked_by=?,
                revoked_at=?,
                revoked_reason=?,
                updated_at=?
            WHERE recorte_path=? AND status='validated'
            """,
            (
                revoked_by or _operator(),
                now,
                reason,
                now,
                str(recorte_path),
            ),
        )
        conn.commit()
        return int(cur.rowcount)


def get_active_crop_examples(
    classe: str,
    *,
    limit: int = 20,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """Return active examples for a cropper to consult by class."""
    ensure_crop_learning_schema(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM crop_learning_events
            WHERE classe=? AND status='validated'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (classe, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]
