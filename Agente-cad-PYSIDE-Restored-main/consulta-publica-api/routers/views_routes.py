"""Endpoint GET /api/v1/ficha/{code}/views — sub-vistas classe-específicas.

Serve os SVGs e metadados das sub-vistas que o portal mostra (cima/abcd/grades
para pilares; camadas SA/C1-3/N3 para FV/lajes/LV) de forma READ-ONLY.
Mesmo padrão de segurança do /ficha/{code}: 404 genérico, sem diferenciar
motivo, sem vazar tipo do item.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response, Request
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.resolve_service import resolver_code
from services.views_service import obter_views

router = APIRouter(prefix="/api/v1", tags=["views"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/ficha/{code}/views")
def obter_views_endpoint(
    code: str, response: Response, request: Request,
    conn: sqlite3.Connection = Depends(get_ro_conn),
):
    """Sub-vistas classe-específicas de um item publicado."""
    response.headers["Cache-Control"] = "private, no-store"

    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    settings = request.app.state.settings
    views = obter_views(row, settings.dados_obras_root)
    if views is None:
        return _nao_encontrado()

    return views
