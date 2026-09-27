"""Aba "Base Global" — grafo da base de conhecimento da empresa, só para o dono.

Lê `docs/CONHECIMENTO/grafo.json` (gerado por `scripts/kb/kb_grafo.py` e versionado
com o código, então chega à VPS no deploy). O portal só lê; nada é escrito.

Membro comum recebe 404 — a aba não existe para ele (nem no menu, nem por URL).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from .. import access
from ..dbdep import get_db_conn
from .paginas_routes import _membro_da_sessao, _render

router = APIRouter(tags=["base-global"], include_in_schema=False)

GRAFO_JSON = Path(__file__).resolve().parents[3] / "docs" / "CONHECIMENTO" / "grafo.json"


def _dono_ou_404(request: Request, conn: sqlite3.Connection):
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return None
    if not access.eh_dono(membro):
        raise HTTPException(status_code=404)
    return membro


@router.get("/app/base-global")
def pagina_base_global(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    membro = _dono_ou_404(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "base_global.html", {
        "membro": membro, "nav_ativo": "base_global", "tem_grafo": GRAFO_JSON.exists(),
    })


@router.get("/app/base-global/grafo.json")
def grafo_json(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    if _dono_ou_404(request, conn) is None:
        raise HTTPException(status_code=401)
    if not GRAFO_JSON.exists():
        raise HTTPException(status_code=404, detail="grafo.json ainda não gerado (scripts/kb/kb_grafo.py)")
    return FileResponse(GRAFO_JSON, media_type="application/json",
                        headers={"Cache-Control": "no-cache"})
