"""Resolução de código opaco → registro `public_codes` (STORY-03).

Único ponto de lookup por `code` — reutilizado por `/resolve` (esta story),
`/ficha` (STORY-05), `/obra` (STORY-07), `/paineis-lv` (STORY-12). A query
SEMPRE executa contra o banco, mesmo para formato obviamente inválido —
isso é o que garante tempo constante (evita timing oracle, AC 4).
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from .obra_context import classe_permitida, comportamento_obra


def resolver_code(conn: sqlite3.Connection, code: str) -> Optional[sqlite3.Row]:
    """Retorna a linha de `public_codes` para `code` (trim, case-sensitive),
    ou None se não existir/estiver revogado — os 2 casos são INDISTINGUÍVEIS
    pelo chamador (AC 3): sempre a mesma query, sempre o mesmo tipo de
    retorno (None), nunca um branch por "formato válido" antes de consultar.
    """
    code = code.strip()
    row = conn.execute(
        "SELECT * FROM public_codes WHERE code = ? AND revoked = 0", (code,)
    ).fetchone()
    if row is not None and row["kind"] == "item" and not classe_permitida(
        row["classe"], comportamento_obra(conn, row["obra_id"])
    ):
        return None
    return row
