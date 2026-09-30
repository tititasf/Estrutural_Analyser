"""Endpoints autenticados da fila QA agêntica multi-item."""

from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import access, auth, pipeline_runner
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["qa-agentico"])


class QARoundIn(BaseModel):
    items: list[str]
    classe: str = "PIL"
    pavimento: str = "13_PAV"
    layer: str = "L1"


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


@router.post("/obras/{obra_id}/qa-agentico")
def criar_qa_round(
    obra_id: str,
    body: QARoundIn,
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    classe = body.classe.upper().strip()
    layer = body.layer.upper().strip()
    items = list(dict.fromkeys(item.upper().strip() for item in body.items if item.strip()))
    if classe != "PIL":
        raise HTTPException(status_code=422, detail="primeiro E2E QA suporta somente PIL")
    if layer not in {"L1", "L2", "L3"}:
        raise HTTPException(status_code=422, detail="layer deve ser L1, L2 ou L3")
    if not items or len(items) > 10:
        raise HTTPException(status_code=422, detail="informe entre 1 e 10 itens por rodada")
    if any(not re.fullmatch(r"P\d+", item) for item in items):
        raise HTTPException(status_code=422, detail="itens PIL devem usar o formato P<n>")

    round_id, job_id = repo.enfileirar_qa_round(
        conn,
        obra_id=obra_id,
        membro_id=membro["id"],
        classe=classe,
        pavimento=body.pavimento,
        layer=layer,
        items=items,
        engine_version=pipeline_runner.engine_version(request.app.state.settings.repo_root),
    )
    meta = {"etapa": "qa_agentico", "round_id": round_id}
    request.app.state.job_meta[job_id] = meta
    return {
        "round_id": round_id,
        "job_id": job_id,
        "obra_id": obra_id,
        "status": "queued",
        "classe": classe,
        "pavimento": body.pavimento,
        "layer": layer,
        "items": items,
    }


@router.get("/qa-rounds/{round_id}")
def obter_qa_round(
    round_id: str,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    detail = repo.detalhe_qa_round(conn, round_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="rodada QA nao encontrada")
    obra = _obra_do_membro(conn, detail["obra_id"], membro)
    _ = obra
    return detail
