"""Rotas de obras: GET /obras, GET /obras/{id} (HANDOFF §1.1/§1.2 etapa 1)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import auth, certification
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["obras"])


@router.get("")
def listar_obras(
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Etapa 1 (Upload): lista as obras do membro detectadas pelo poller."""
    obras = repo.listar_obras_por_membro(conn, membro["id"])
    return {
        "membro": membro["login"],
        "drive": request.app.state.estado_global.get("drive", "ok"),
        "obras": obras,
    }


@router.get("/{obra_id}")
def obter_obra(
    obra_id: str,
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if obra["membro_id"] != membro["id"]:
        raise HTTPException(status_code=403, detail="obra de outro membro")
    settings = request.app.state.settings
    jobs = repo.listar_jobs_por_obra(conn, obra_id)
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    comentarios = repo.listar_comentarios_por_obra(conn, obra_id)
    # rotulos de certificacao por classe (R9) — exibidos junto da obra
    rotulos = {
        c: certification.classificar_certificacao(settings.status_md_path, c)
        for c in ("PL", "LV", "FV", "LJ")
    }
    return {
        "obra": obra,
        "jobs": jobs,
        "n5_releases": releases,
        "comentarios": comentarios,
        "rotulos_certificacao": rotulos,
    }
