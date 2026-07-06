"""Rotas de obras: GET /obras, GET /obras/{id} (HANDOFF §1.1/§1.2 etapa 1)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import access, auth, certification, drive_poller
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["obras"])


@router.get("")
def listar_obras(
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Etapa 1 (Upload): lista as obras do membro (ou de TODOS, se dono — 2026-07-06)."""
    obras = (
        repo.listar_todas_obras(conn)
        if access.eh_dono(membro)
        else repo.listar_obras_por_membro(conn, membro["id"])
    )
    return {
        "membro": membro["login"],
        "papel": membro["papel"],
        "drive": request.app.state.estado_global.get("drive", "ok"),
        "obras": obras,
    }


@router.post("/verificar-drive")
def verificar_drive_agora(
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Dispara 1 varredura do Drive AGORA (2026-07-06) — sem esperar o poller de fundo.

    Membro comum: so' varre a PROPRIA pasta. Dono: varre TODOS (ja' ve' tudo mesmo).
    Cliente novo por chamada (nao reusa app.state.drive_client) — mesma disciplina
    de thread-safety do poller de fundo (fix 2026-07-05, cross-thread sqlite/creds).
    """
    settings = request.app.state.settings
    cliente = drive_poller.montar_drive_client(settings)
    membros_alvo = None if access.eh_dono(membro) else [membro]
    try:
        novas = drive_poller.varrer_uma_vez(conn, cliente, settings, membros=membros_alvo)
    except Exception as exc:  # noqa: BLE001 - mesma degradacao R8 do poller de fundo
        raise HTTPException(status_code=502, detail=f"Drive indisponivel agora: {exc}") from exc
    return {"novas_obras": len(novas), "drive_modo": type(cliente).__name__}


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
    if not access.pode_ver_obra(obra, membro):
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
