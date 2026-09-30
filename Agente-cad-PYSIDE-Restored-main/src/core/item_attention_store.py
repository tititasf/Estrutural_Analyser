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
        cols = {row[1] for row in conn.execute("PRAGMA table_info(item_attention_notes)").fetchall()}
        if "human_validated" not in cols:
            conn.execute("ALTER TABLE item_attention_notes ADD COLUMN human_validated INTEGER DEFAULT 0")


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
            "SELECT attention, note, updated_at, COALESCE(human_validated, 0) "
            "FROM item_attention_notes WHERE id=?",
            (key,),
        )
        row = cur.fetchone()
    if not row:
        return {"attention": False, "note": "", "updated_at": ""}
    return {
        "attention": bool(row[0]),
        "note": row[1] or "",
        "updated_at": row[2] or "",
        "human_validated": bool(row[3]),
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


def save_human_validation(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    human_validated: bool = False,
    db_path: Path | str = DB_PATH,
) -> None:
    ensure_table(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    key = _key(obra, pavimento, classe, item_id, scope)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO item_attention_notes
                (id, obra_name, pavimento, classe, item_id, scope, human_validated, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                human_validated=excluded.human_validated,
                updated_at=excluded.updated_at
            """,
            (
                key,
                _norm(obra),
                _norm(pavimento),
                _norm(classe).upper(),
                _norm(item_id),
                _norm(scope).upper(),
                1 if human_validated else 0,
                now,
                now,
            ),
        )


def is_human_validated(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    db_path: Path | str = DB_PATH,
) -> bool:
    data = load_attention(obra, pavimento, classe, item_id, scope, db_path)
    return bool(data.get("human_validated"))


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


# ── Para/Passa classification ──────────────────────────────────────────────

def _ensure_para_passa_table(db_path: Path | str = DB_PATH) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lv_para_passa (
                id TEXT PRIMARY KEY,
                obra TEXT,
                pavimento TEXT,
                classe TEXT,
                item_id TEXT,
                tipo TEXT DEFAULT '',
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lv_para_passa_lookup "
            "ON lv_para_passa(obra, pavimento, classe, item_id)"
        )


def _pp_key(obra: str, pavimento: str, classe: str, item_id: str) -> str:
    return "|".join([_norm(obra), _norm(pavimento), _norm(classe).upper(), _norm(item_id)])


def save_para_passa(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    tipo: str,
    db_path: Path | str = DB_PATH,
) -> None:
    """tipo: 'para', 'passa' ou '' (limpa)."""
    _ensure_para_passa_table(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds")
    key = _pp_key(obra, pavimento, classe, item_id)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO lv_para_passa (id, obra, pavimento, classe, item_id, tipo, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET tipo=excluded.tipo, updated_at=excluded.updated_at
            """,
            (key, _norm(obra), _norm(pavimento), _norm(classe).upper(), _norm(item_id),
             _norm(tipo).lower(), now),
        )


def load_para_passa(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    db_path: Path | str = DB_PATH,
) -> str:
    """Retorna 'para', 'passa' ou ''."""
    try:
        _ensure_para_passa_table(db_path)
        key = _pp_key(obra, pavimento, classe, item_id)
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT tipo FROM lv_para_passa WHERE id=?", (key,)
            ).fetchone()
        return (row[0] or "").strip().lower() if row else ""
    except Exception:
        return ""
