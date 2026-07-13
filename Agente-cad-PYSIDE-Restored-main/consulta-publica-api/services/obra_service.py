"""Índice de itens consultáveis de uma obra (STORY-07) e de 1 pavimento
específico dentro dela [2026-07-12] — "ficha do pavimento"/recorte limpo da
torre, cada pavimento tem seu próprio `code`, resolvendo direto pra lista
de itens DAQUELE pavimento sem precisar do código da obra inteira.

Pavimentos vêm de `ficha_reader.descobrir_pavimentos(obra_dir)` (fonte real
no disco) — não só dos valores distintos já publicados em `public_codes` —
para que um pavimento sem nenhum item publicado ainda apareça com
`itens: []` (AC3) em vez de ser omitido silenciosamente. Os itens de cada
pavimento vêm 100% de `public_codes` (já denormalizado pelo Publisher,
STORY-01) — nunca `item_id`/`pavimento` crus na resposta (AC1).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from portal.app import ficha_reader

from .code_lookup import code_da_obra, code_do_pavimento
from .ficha_service import pavimento_label


def _listar_itens_do_pavimento(conn: sqlite3.Connection, obra_id: str, pavimento: str) -> list[dict]:
    itens_rows = conn.execute(
        """
        SELECT code, titulo_publico, tipo_elemento FROM public_codes
        WHERE obra_id = ? AND pavimento = ? AND kind = 'item' AND revoked = 0
        ORDER BY titulo_publico
        """,
        (obra_id, pavimento),
    ).fetchall()
    return [
        {"code": item["code"], "titulo": item["titulo_publico"], "tipo": item["tipo_elemento"]}
        for item in itens_rows
    ]


def montar_indice_obra(conn: sqlite3.Connection, row) -> Optional[dict]:
    """Monta a resposta de `/obra/{code}` a partir de uma linha resolvida de
    `public_codes` com `kind='obra'`. Retorna None se `kind != 'obra'` —
    tratado como 404 genérico pelo router, mesmo padrão das outras stories."""
    if row["kind"] != "obra":
        return None

    obra_id = row["obra_id"]
    obra_dir = Path(row["obra_dir"])

    pavimentos_reais = ficha_reader.descobrir_pavimentos(obra_dir)

    resultado_pavimentos = []
    for pavimento in pavimentos_reais:
        resultado_pavimentos.append({
            "code": code_do_pavimento(conn, obra_id, pavimento),
            "pavimento_label": pavimento_label(pavimento),
            "itens": _listar_itens_do_pavimento(conn, obra_id, pavimento),
        })

    return {
        "obra_rotulo": row["obra_rotulo"],
        "pavimentos": resultado_pavimentos,
    }


def montar_ficha_pavimento(conn: sqlite3.Connection, row) -> Optional[dict]:
    """Monta a resposta de `/pavimento/{code}` — mesma forma de 1 entrada de
    `pavimentos[]` acima, mas resolvida direto pelo código PRÓPRIO do
    pavimento (kind='pavimento'), sem precisar do código da obra inteira."""
    if row["kind"] != "pavimento":
        return None

    obra_id = row["obra_id"]
    pavimento = row["pavimento"]

    return {
        "obra_rotulo": row["obra_rotulo"],
        "obra_code": code_da_obra(conn, obra_id),
        "pavimento_label": pavimento_label(pavimento),
        "itens": _listar_itens_do_pavimento(conn, obra_id, pavimento),
    }
