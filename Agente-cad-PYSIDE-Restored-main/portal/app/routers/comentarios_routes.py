"""Rotas de comentarios T0 (equipe:*) — server-side, substituem localStorage (HANDOFF §1.1/§4).

Todo comentario grava marcado_por = 'equipe:<login>' (proveniencia real T0, §3). O
portal so grava no namespace 'equipe' (o repository forca isso); a curadoria/decisao
continua exclusiva do dono, pela cabine PySide6 — nunca por este processo.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import access, auth
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["comentarios"])


class ComentarioIn(BaseModel):
    texto: str
    tipo: str = "observacao"  # 'erro' | 'observacao'
    classe: Optional[str] = None
    pavimento: Optional[str] = None
    item_id: Optional[str] = None


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


@router.post("/{obra_id}/comentarios")
def criar_comentario(obra_id: str, body: ComentarioIn, request: Request,
                     membro: dict = Depends(auth.exige_login),
                     conn: sqlite3.Connection = Depends(get_db_conn)):
    if body.tipo not in ("erro", "observacao"):
        raise HTTPException(status_code=422, detail="tipo deve ser 'erro' ou 'observacao'")
    obra = _obra_do_membro(conn, obra_id, membro)
    coment_id = repo.inserir_comentario(
        conn, obra_id=obra["id"], membro_id=membro["id"], texto=body.texto,
        tipo=body.tipo, classe=body.classe, pavimento=body.pavimento, item_id=body.item_id,
    )
    return {"comentario_id": coment_id, "marcado_por": f"equipe:{membro['login']}",
            "tipo": body.tipo}


@router.get("/{obra_id}/comentarios")
def listar_comentarios(obra_id: str, request: Request,
                       membro: dict = Depends(auth.exige_login),
                       conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    coments = repo.listar_comentarios_por_obra(conn, obra["id"])
    return {"obra_id": obra_id, "total": len(coments), "comentarios": coments}
