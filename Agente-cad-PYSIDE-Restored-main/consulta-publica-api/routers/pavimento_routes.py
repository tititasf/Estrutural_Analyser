"""Endpoint GET /api/v1/pavimento/{code} [2026-07-12].

"Ficha do pavimento"/recorte limpo da torre — cada pavimento tem seu
próprio código, resolvendo direto pra lista de itens DAQUELE pavimento sem
precisar do código da obra inteira. Só serve pavimentos (`kind='pavimento'`)
— código de obra/item recebe o mesmo 404 genérico (mesmo padrão de todas as
outras rotas — nunca vaza "código existe mas é do tipo errado").
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.obra_service import montar_ficha_pavimento
from services.resolve_service import resolver_code

router = APIRouter(prefix="/api/v1", tags=["pavimento"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/pavimento/{code}")
def obter_ficha_pavimento(code: str, response: Response, conn: sqlite3.Connection = Depends(get_ro_conn)):
    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    ficha = montar_ficha_pavimento(conn, row)
    if ficha is None:
        return _nao_encontrado()

    response.headers["Cache-Control"] = "private, max-age=60"
    return ficha
