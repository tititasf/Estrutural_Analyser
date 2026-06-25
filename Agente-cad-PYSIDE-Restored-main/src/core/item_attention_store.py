from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")


def _norm(value) -> str:
    return str(value or "").strip()


def _key(obra: str, pavimento: str, classe: str, item_id: str, scope: str) -> str:
    return "|".join([
        _norm(obra),
        _norm(pavimento),
        _norm(classe).upper(),
        _norm(item_id),
        _norm(scope).upper(),
    ])


def ensure_table(db_path: Path | str = DB_PATH) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS item_attention_notes (
                id TEXT PRIMARY KEY,
                obra_name TEXT,
                pavimento TEXT,
                classe TEXT,
                item_id TEXT,
                scope TEXT,
                attention INTEGER DEFAULT 0,
                note TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_item_attention_lookup "
            "ON item_attention_notes(obra_name, pavimento, classe, item_id, scope)"
        )


def load_attention(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    db_path: Path | str = DB_PATH,
) -> dict:
    ensure_table(db_path)
    key = _key(obra, pavimento, classe, item_id, scope)
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT attention, note, updated_at FROM item_attention_notes WHERE id=?",
            (key,),
        )
        row = cur.fetchone()
    if not row:
        return {"attention": False, "note": "", "updated_at": ""}
    return {
        "attention": bool(row[0]),
        "note": row[1] or "",
        "updated_at": row[2] or "",
    }


def save_attention(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    attention: bool = False,
    note: str = "",
    db_path: Path | str = DB_PATH,
) -> None:
    ensure_table(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    key = _key(obra, pavimento, classe, item_id, scope)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO item_attention_notes
                (id, obra_name, pavimento, classe, item_id, scope, attention, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                attention=excluded.attention,
                note=excluded.note,
                updated_at=excluded.updated_at
            """,
            (
                key,
                _norm(obra),
                _norm(pavimento),
                _norm(classe).upper(),
                _norm(item_id),
                _norm(scope).upper(),
                1 if attention else 0,
                note or "",
                now,
                now,
            ),
        )


def has_attention(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    db_path: Path | str = DB_PATH,
    note_counts: bool = True,
) -> bool:
    data = load_attention(obra, pavimento, classe, item_id, scope, db_path)
    return bool(data.get("attention") or (note_counts and str(data.get("note") or "").strip()))
