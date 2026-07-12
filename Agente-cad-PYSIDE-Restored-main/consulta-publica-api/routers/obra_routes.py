"""Endpoint GET /api/v1/obra/{code} (STORY-07).

Só serve obras (`kind='obra'`) — código de item recebe o mesmo 404 genérico
(AC2), mesmo padrão das demais stories (nunca vaza "código existe mas é do
tipo errado").
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.obra_service import montar_indice_obra
from services.resolve_service import resolver_code

router = APIRouter(prefix="/api/v1", tags=["obra"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/obra/{code}")
def obter_indice_obra(code: str, response: Response, conn: sqlite3.Connection = Depends(get_ro_conn)):
    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    indice = montar_indice_obra(conn, row)
    if indice is None:
        return _nao_encontrado()

    response.headers["Cache-Control"] = "private, max-age=60"
    return indice
