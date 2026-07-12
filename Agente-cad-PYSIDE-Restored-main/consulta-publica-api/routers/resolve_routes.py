"""Endpoint GET /api/v1/resolve/{code} (STORY-03).

Resolução LEVE de tipo (`kind`) — o corpo completo de "obra→índice" é a
STORY-07 e "item→ficha" é a STORY-05. 404 genérico e de tempo constante para
código inexistente/malformado/revogado/fora de escopo — os 4 casos são
tratados de forma IDÊNTICA (mesma query, mesmo branch, mesma resposta).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.resolve_service import resolver_code

router = APIRouter(prefix="/api/v1", tags=["resolve"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


@router.get("/resolve/{code}")
def resolve(code: str, response: Response, conn: sqlite3.Connection = Depends(get_ro_conn)):
    response.headers["Cache-Control"] = "private, no-store"

    # A query SEMPRE executa, independente do formato de `code` — nenhum
    # early-return por regex/comprimento antes do lookup (AC 4, timing oracle).
    row = resolver_code(conn, code)

    if row is None:
        # Corpo/status EXATAMENTE iguais pros 4 casos negativos (inexistente,
        # malformado, revogado, fora de escopo) — indistinguíveis (AC 3).
        return JSONResponse(
            status_code=404,
            content=_ERRO_GENERICO,
            headers={"Cache-Control": "private, no-store"},
        )

    return {"kind": row["kind"], "code": row["code"]}
