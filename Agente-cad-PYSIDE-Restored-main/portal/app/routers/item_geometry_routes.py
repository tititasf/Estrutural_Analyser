"""Ações compartilhadas do editor de itens estruturais."""
from __future__ import annotations
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from .. import auth, ficha_reader, item_geometry
from ..dbdep import get_db_conn
from ...db import repository as repo
from .n1_routes import _obra_do_membro, _obra_dir, _bloquear_modo_oposto

router = APIRouter(prefix="/obras", tags=["geometria"], dependencies=[Depends(_bloquear_modo_oposto)])

class GeometryPayload(BaseModel):
    points: list[list[float]]


def context(request, conn, membro, obra_id, pavimento):
    obra = _obra_do_membro(conn, obra_id, membro)
    directory = _obra_dir(request, obra)
    if not pavimento or pavimento not in ficha_reader.descobrir_pavimentos(directory):
        raise HTTPException(404, "pavimento SA não encontrado")
    return obra, directory


def execute(request, conn, membro, obra_id, pavimento, classe, item_id, **kwargs):
    _, directory = context(request, conn, membro, obra_id, pavimento)
    try:
        result = item_geometry.mutate(directory, pavimento, classe, item_id, **kwargs)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for item in result["affected"]:
        repo.set_campo_validado(conn, obra_id, pavimento, item["classe"], item["item_id"], "_item_", False)
    return {"status": "ok", **result}


@router.put("/{obra_id}/itens/{classe}/{item_id}/geometria")
def edit(obra_id: str, classe: str, item_id: str, payload: GeometryPayload,
         request: Request, pavimento: str, membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    if classe == "fundo":
        # Reusa transformação e atualização visual do editor existente da ficha FV.
        from .n1_routes import _fv_sa_visual_context, _refresh_fv_sa_visual
        obra, directory = context(request, conn, membro, obra_id, pavimento)
        state = ficha_reader.ler_estado_pavimento(directory, pavimento)
        row = next((r for r in item_geometry.collection(state, classe) if r.get("uid") == item_id), None)
        if not row:
            raise HTTPException(404, "segmento não encontrado")
        try:
            visual = _fv_sa_visual_context(request, obra, directory, pavimento, row["beam_name"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        result = execute(request, conn, membro, obra_id, pavimento, classe, item_id, points=payload.points)
        _refresh_fv_sa_visual(directory, pavimento, row["beam_name"], visual)
        return result
    return execute(request, conn, membro, obra_id, pavimento, classe, item_id, points=payload.points)


@router.delete("/{obra_id}/itens/{classe}/{item_id}")
def delete(obra_id: str, classe: str, item_id: str, request: Request, pavimento: str,
           inteiro: bool = False, membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    visual = None
    if classe == "fundo" and not inteiro:
        from .n1_routes import _fv_sa_visual_context, _refresh_fv_sa_visual
        obra, directory = context(request, conn, membro, obra_id, pavimento)
        state = ficha_reader.ler_estado_pavimento(directory, pavimento)
        row = next((r for r in item_geometry.collection(state, classe) if r.get("uid") == item_id), None)
        if not row:
            raise HTTPException(404, "segmento não encontrado")
        try:
            visual = _fv_sa_visual_context(request, obra, directory, pavimento, row["beam_name"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    result = execute(request, conn, membro, obra_id, pavimento, classe, item_id,
                     delete=True, whole_beam=inteiro)
    if visual:
        _refresh_fv_sa_visual(directory, pavimento, row["beam_name"], visual)
    return result


@router.post("/{obra_id}/itens/{classe}/{item_id}/interpretar-sa")
def interpret(obra_id: str, classe: str, item_id: str, request: Request, pavimento: str,
              membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    obra, directory = context(request, conn, membro, obra_id, pavimento)
    state = ficha_reader.ler_estado_pavimento(directory, pavimento)
    if not ficha_reader.obter_item_n1(state, classe, item_id):
        raise HTTPException(404, "item não encontrado")
    if classe not in {"pilares", "pilares_especiais"}:
        raise HTTPException(422, "interpretação granular disponível para pilares")
    from .jobs_routes import _enfileirar
    job_id = _enfileirar(request, conn, obra, {"etapa": "sa_item", "secao": "pilares",
                         "item": item_id, "pav": pavimento, "classe_ui": classe})
    return {"job_id": job_id, "item": item_id, "status": "na_fila"}
