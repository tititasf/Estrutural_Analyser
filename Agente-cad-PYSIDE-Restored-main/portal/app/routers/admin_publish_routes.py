"""Publicação de obras para a App de Consulta Pública (STORY-01).

Zona interna e autenticada — nunca exposta na zona pública. Publica uma cópia
mínima e denormalizada da obra em `public_consulta.db` (schema em
`consulta-publica-api/publisher/schema.sql`), mintando código opaco por item.
A API pública (fora do escopo desta story) só lê esse arquivo, em mode=ro.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import auth
from ..dbdep import get_db_conn
from ...db import repository as repo

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_CONSULTA_PUBLICA_DIR = _REPO_ROOT / "consulta-publica-api"
if str(_CONSULTA_PUBLICA_DIR) not in sys.path:
    sys.path.insert(0, str(_CONSULTA_PUBLICA_DIR))

from publisher.publish import publicar, revogar  # noqa: E402

router = APIRouter(prefix="/admin", tags=["admin-publish"])


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    return obra


def _obra_dir(request: Request, obra: dict) -> Path:
    settings = request.app.state.settings
    lp = obra.get("local_path")
    return Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")


class PublicarIn(BaseModel):
    obra_rotulo: str | None = None


@router.post("/publicar/{obra_id}")
def publicar_obra_endpoint(
    obra_id: str, body: PublicarIn, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Publica (ou republica) uma obra na App de Consulta Pública. Zona
    interna/autenticada apenas — nunca chamado pela API pública."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    if not obra_dir.exists():
        raise HTTPException(status_code=404, detail="pasta da obra nao encontrada em disco")
    settings = request.app.state.settings
    resumo = publicar(
        obra, obra_dir,
        db_path=settings.public_consulta_db_path,
        obra_rotulo=body.obra_rotulo,
    )
    return {"obra_id": obra_id, **resumo}


class RevogarIn(BaseModel):
    code: str | None = None


@router.post("/revogar/{obra_id}")
def revogar_obra_endpoint(
    obra_id: str, body: RevogarIn, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Revoga a obra inteira, ou (se `code` informado) só 1 item publicado."""
    _obra_do_membro(conn, obra_id, membro)
    db_path = request.app.state.settings.public_consulta_db_path
    if body.code:
        afetadas = revogar(code=body.code, db_path=db_path)
    else:
        afetadas = revogar(obra_id=obra_id, db_path=db_path)
    return {"obra_id": obra_id, "linhas_afetadas": afetadas}
