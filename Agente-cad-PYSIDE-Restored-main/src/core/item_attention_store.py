from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
HUMAN_VALIDATION_ORIGINS = {"human", "human_ui", "manual", "operator", "ui", "ui_click", "user", "user_click"}
MACHINE_VALIDATION_ORIGINS = {"agent", "ai", "auto", "batch", "cli", "headless", "looper", "machine", "pipeline", "script", "synthetic"}


def _norm(value) -> str:
    return str(value or "").strip()


def _require_human_origin(origin: str | None) -> str:
    normalized = _norm(origin).lower()
    if normalized not in HUMAN_VALIDATION_ORIGINS or normalized in MACHINE_VALIDATION_ORIGINS:
        raise ValueError(
            f"validation_origin='{origin}' nao pode gravar validacao humana. "
            "Use apenas origem de clique/acao humana real."
        )
    return normalized


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
        if "note_origin" not in cols:
            conn.execute("ALTER TABLE item_attention_notes ADD COLUMN note_origin TEXT DEFAULT 'human_ui'")
        if "validation_origin" not in cols:
            conn.execute("ALTER TABLE item_attention_notes ADD COLUMN validation_origin TEXT DEFAULT ''")
        if "updated_by" not in cols:
            conn.execute("ALTER TABLE item_attention_notes ADD COLUMN updated_by TEXT DEFAULT ''")
        if "metadata_json" not in cols:
            conn.execute("ALTER TABLE item_attention_notes ADD COLUMN metadata_json TEXT DEFAULT '{}'")


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
            "SELECT attention, note, updated_at, COALESCE(human_validated, 0), "
            "COALESCE(note_origin, ''), COALESCE(validation_origin, ''), "
            "COALESCE(updated_by, ''), COALESCE(metadata_json, '{}') "
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
        "note_origin": row[4] or "",
        "validation_origin": row[5] or "",
        "updated_by": row[6] or "",
        "metadata_json": row[7] or "{}",
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
    note_origin: str = "human_ui",
    updated_by: str | None = None,
    metadata: dict | None = None,
) -> None:
    ensure_table(db_path)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    key = _key(obra, pavimento, classe, item_id, scope)
    note_origin = _norm(note_origin).lower() or "human_ui"
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO item_attention_notes
                (id, obra_name, pavimento, classe, item_id, scope, attention, note,
                 created_at, updated_at, note_origin, updated_by, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                attention=excluded.attention,
                note=excluded.note,
                updated_at=excluded.updated_at,
                note_origin=excluded.note_origin,
                updated_by=excluded.updated_by,
                metadata_json=excluded.metadata_json
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
                note_origin,
                _norm(updated_by),
                metadata_json,
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
    validation_origin: str = "human_ui",
    updated_by: str | None = None,
    metadata: dict | None = None,
) -> None:
    ensure_table(db_path)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    key = _key(obra, pavimento, classe, item_id, scope)
    validation_origin = _require_human_origin(validation_origin)
    if _norm(scope).upper() in {"N3", "N4"}:
        from src.core.artifact_governance import set_validation_protection

        set_validation_protection(
            obra,
            pavimento,
            classe,
            item_id,
            scope,
            bool(human_validated),
            db_path=db_path,
            validation_origin=validation_origin,
            updated_by=updated_by,
        )
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO item_attention_notes
                (id, obra_name, pavimento, classe, item_id, scope, human_validated,
                 created_at, updated_at, validation_origin, updated_by, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                human_validated=excluded.human_validated,
                updated_at=excluded.updated_at,
                validation_origin=excluded.validation_origin,
                updated_by=excluded.updated_by,
                metadata_json=excluded.metadata_json
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
                validation_origin,
                _norm(updated_by),
                metadata_json,
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
    validated = bool(data.get("human_validated"))
    if validated and _norm(scope).upper() in {"N3", "N4"}:
        from src.core.artifact_governance import (
            is_validation_policy_locked,
            set_validation_protection,
        )

        if not is_validation_policy_locked(
            obra, pavimento, classe, item_id, scope, db_path
        ):
            set_validation_protection(
                obra,
                pavimento,
                classe,
                item_id,
                scope,
                True,
                db_path=db_path,
                validation_origin=data.get("validation_origin") or "human_ui",
                updated_by=data.get("updated_by"),
            )
    return validated


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


def canonical_pavimento(pavimento: str) -> str:
    """Converte nomes de projeto/aliases para a chave usada pelas fichas N2."""
    raw = _norm(pavimento)
    normalized = unicodedata.normalize("NFKD", raw)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).upper()
    if "TERREO" in normalized or re.search(r"[-_ ]TER[-_ ]", normalized):
        return "TERREO"
    if "COB" in normalized:
        return "COBERTURA"
    matches = re.findall(r"(\d+)\s*_?PAV", normalized)
    if matches:
        return f"{matches[-1]}_PAV"
    matches = re.findall(r"[-_ ](\d{1,2})P(?:V)?(?:[-_ ]|$)", normalized)
    if matches:
        return f"{matches[-1]}_PAV"
    if "TIPO" in normalized or re.search(r"[-_ ]TIP[-_ ]", normalized):
        return "TIPO"
    return raw


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
    now = datetime.now(UTC).isoformat(timespec="seconds")
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
        pavimentos = [_norm(pavimento)]
        canonical = canonical_pavimento(pavimento)
        if canonical and canonical not in pavimentos:
            pavimentos.append(canonical)
        with sqlite3.connect(str(db_path)) as conn:
            row = None
            for candidate in pavimentos:
                key = _pp_key(obra, candidate, classe, item_id)
                row = conn.execute(
                    "SELECT tipo FROM lv_para_passa WHERE id=?", (key,)
                ).fetchone()
                if row:
                    break
        return (row[0] or "").strip().lower() if row else ""
    except Exception:
        return ""
