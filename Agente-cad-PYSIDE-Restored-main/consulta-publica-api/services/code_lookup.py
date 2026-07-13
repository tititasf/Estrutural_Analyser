"""Lookups isolados de `code` em `public_codes`, sem depender de nenhum outro
serviço [2026-07-12] — extraído de `obra_service.py` pra `ficha_service.py`
também poder resolver o código do pavimento de um item (link recíproco
item -> pavimento -> obra) sem criar import circular entre os dois módulos
(`obra_service` já importa `pavimento_label` de `ficha_service`).
"""

from __future__ import annotations

import sqlite3
from typing import Optional


def code_da_obra(conn: sqlite3.Connection, obra_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id = ? AND kind = 'obra' AND revoked = 0",
        (obra_id,),
    ).fetchone()
    return row["code"] if row else None


def code_do_pavimento(conn: sqlite3.Connection, obra_id: str, pavimento: str) -> Optional[str]:
    row = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id = ? AND pavimento = ? AND kind = 'pavimento' AND revoked = 0",
        (obra_id, pavimento),
    ).fetchone()
    return row["code"] if row else None
