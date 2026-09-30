"""Endpoint GET /api/v1/ficha/{code}/materiais — Materiais e Construção.

Painéis e sarrafos MEDIDOS no DXF N3 desenhado (ver
`services/materiais_service.py`). Mesmo padrão de segurança do
/ficha/{code}: 404 genérico, sem diferenciar motivo.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response, Request
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.resolve_service import resolver_code
from services.materiais_service import obter_materiais
from services.reaproveitamento_service import obter_reaproveitamento

router = APIRouter(prefix="/api/v1", tags=["materiais"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/ficha/{code}/materiais")
def obter_materiais_endpoint(
    code: str, response: Response, request: Request,
    conn: sqlite3.Connection = Depends(get_ro_conn),
):
    """Painéis e sarrafos medidos no N3 desenhado."""
    response.headers["Cache-Control"] = "private, no-store"

    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    settings = request.app.state.settings
    materiais = obter_materiais(row, settings.dados_obras_root)
    if materiais is None:
        return _nao_encontrado()

    return materiais


@router.get("/ficha/{code}/reaproveitamento")
def obter_reaproveitamento_endpoint(
    code: str, response: Response, request: Request,
    conn: sqlite3.Connection = Depends(get_ro_conn),
):
    """Reaproveitamento do pavimento anterior (etapas D-70) para o item."""
    response.headers["Cache-Control"] = "private, no-store"

    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    settings = request.app.state.settings
    reap = obter_reaproveitamento(conn, row, settings.dados_obras_root)
    if reap is None:
        return _nao_encontrado()
    if reap.get("calculando"):  # cenário sendo medido em segundo plano
        return JSONResponse(status_code=202, content=reap, headers={"Cache-Control": "private, no-store"})

    return reap
