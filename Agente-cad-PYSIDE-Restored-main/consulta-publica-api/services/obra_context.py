"""Configuração da obra, consultada em leitura no banco do portal interno."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

PORTAL_DB = Path(__file__).resolve().parents[2] / "portal_data.db"


def comportamento_obra(conn: sqlite3.Connection, obra_id: str) -> str:
    """Usa o cadastro atual; o payload público é fallback para instalações antigas."""
    if PORTAL_DB.is_file():
        try:
            with sqlite3.connect(f"file:{PORTAL_DB.as_posix()}?mode=ro", uri=True) as portal:
                row = portal.execute(
                    "SELECT comportamento FROM portal_obras WHERE id = ?", (obra_id,)
                ).fetchone()
                if row and row[0] in {"para", "passa", "misto"}:
                    return row[0]
        except sqlite3.Error:
            pass
    row = conn.execute(
        "SELECT payload_json FROM public_codes WHERE obra_id = ? AND kind = 'obra' AND revoked = 0",
        (obra_id,),
    ).fetchone()
    if row and row[0]:
        try:
            value = json.loads(row[0]).get("comportamento")
            if value in {"para", "passa", "misto"}:
                return value
        except (ValueError, TypeError):
            pass
    return "misto"


def classe_permitida(classe: str | None, modo: str) -> bool:
    if modo == "misto" or not classe:
        return True
    classe = classe.lower()
    if classe.startswith("pilares_n3_") or classe.startswith("lateral_a_") or classe.startswith("lateral_b_"):
        return classe.endswith("_" + modo)
    return True


def pavimentos_ordenados(obra_id: str) -> list[dict]:
    if not PORTAL_DB.is_file():
        return []
    try:
        with sqlite3.connect(f"file:{PORTAL_DB.as_posix()}?mode=ro", uri=True) as portal:
            rows = portal.execute(
                "SELECT pavimento,ordem,repete_de,repete_ate FROM portal_obra_pavimentos "
                "WHERE obra_id = ? ORDER BY ordem", (obra_id,),
            ).fetchall()
    except sqlite3.Error:
        return []
    return [{"pavimento": r[0], "ordem": r[1],
             "anterior": rows[i - 1][0] if i else None,
             "proximo": rows[i + 1][0] if i + 1 < len(rows) else None,
             "tipo": {"de": r[2], "ate": r[3]} if r[2] is not None else None}
            for i, r in enumerate(rows)]
