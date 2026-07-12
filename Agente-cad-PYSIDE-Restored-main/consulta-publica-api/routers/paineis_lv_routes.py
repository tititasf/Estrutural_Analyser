"""Endpoint GET /api/v1/ficha/{code}/paineis-lv (STORY-12)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.paineis_lv_service import obter_paineis_lv
from services.resolve_service import resolver_code

router = APIRouter(prefix="/api/v1", tags=["ficha"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/ficha/{code}/paineis-lv")
def obter_paineis_lv_route(
    code: str,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_ro_conn),
):
    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    settings = request.app.state.settings
    paineis = obter_paineis_lv(row, settings.dados_obras_root)
    if paineis is None:
        return _nao_encontrado()

    response.headers["Cache-Control"] = "public, max-age=3600"
    return paineis
