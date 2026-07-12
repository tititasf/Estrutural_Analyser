"""Endpoint GET /api/v1/ficha/{code} (STORY-05).

Só serve itens (`kind='item'`) — código de obra recebe o mesmo 404 genérico
(não vaza que o código é "do tipo errado", AC 3).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.ficha_service import montar_ficha
from services.resolve_service import resolver_code

router = APIRouter(prefix="/api/v1", tags=["ficha"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/ficha/{code}")
def obter_ficha(code: str, response: Response, conn: sqlite3.Connection = Depends(get_ro_conn)):
    response.headers["Cache-Control"] = "private, no-store"

    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    ficha = montar_ficha(row)
    if ficha is None:
        # Inclui kind='obra' (fora de escopo deste endpoint) E item cuja
        # fonte real sumiu desde a publicação — ambos tratados igual: 404
        # genérico, nunca um 400/422 que revelaria "o código existe mas...".
        return _nao_encontrado()

    return ficha
