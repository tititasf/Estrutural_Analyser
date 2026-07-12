"""Endpoint GET /api/v1/ficha/{code}/svg/{nivel} (STORY-06).

SVG puro (`image/svg+xml`), nunca envolto em JSON — desacoplado do payload
da ficha (STORY-05) para permitir cache agressivo por content-hash. Nível
fora de `{n1, n3}` ou SVG ausente recebem o mesmo 404 genérico da STORY-03.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from dbdep import get_ro_conn
from services.resolve_service import resolver_code
from services.svg_service import etag_de, obter_svg

router = APIRouter(prefix="/api/v1", tags=["ficha"])

_ERRO_GENERICO = {"erro": "nao_encontrado"}


def _nao_encontrado() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=_ERRO_GENERICO,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/ficha/{code}/svg/{nivel}")
def obter_svg_route(
    code: str,
    nivel: str,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_ro_conn),
):
    row = resolver_code(conn, code)
    if row is None:
        return _nao_encontrado()

    settings = request.app.state.settings
    svg = obter_svg(row, nivel, settings.dados_obras_root)
    if svg is None:
        return _nao_encontrado()

    etag = f'"{etag_de(svg)}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        })

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )
