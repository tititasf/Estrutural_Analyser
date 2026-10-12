"""Ações compartilhadas do editor de itens estruturais."""
from __future__ import annotations
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .. import auth, ficha_reader, item_geometry, item_semantics
from ..dbdep import get_db_conn
from ...db import repository as repo
from .n1_routes import _obra_do_membro, _obra_dir, _bloquear_modo_oposto

router = APIRouter(prefix="/obras", tags=["geometria"], dependencies=[Depends(_bloquear_modo_oposto)])

class GeometryPayload(BaseModel):
    points: Optional[list[list[float]]] = None
    fields: Optional[dict] = None

class CreateGeometryPayload(GeometryPayload):
    name: str
    segment: Optional[int] = None

class DeleteReviewPayload(BaseModel):
    comentario: str = Field(default='', max_length=4000)


def context(request, conn, membro, obra_id, pavimento):
    obra = _obra_do_membro(conn, obra_id, membro)
    directory = _obra_dir(request, obra)
    if not pavimento or pavimento not in ficha_reader.descobrir_pavimentos(directory):
        raise HTTPException(404, "pavimento SA não encontrado")
    return obra, directory


def execute(request, conn, membro, obra_id, pavimento, classe, item_id, **kwargs):
    _, directory = context(request, conn, membro, obra_id, pavimento)
    try:
        if not kwargs.get("delete"):
            source = ficha_reader._fonte_estrutural_producao(directory, pavimento)
            kwargs["semantic_texts"] = item_semantics.source_texts(source)
            if classe.startswith("pilares"):
                kwargs["pillar_context"] = item_semantics.pillar_source(source)
                kwargs["semantic_beams"] = item_semantics.canonical_beams(
                    request.app.state.settings.sa_db_path, directory, pavimento)
        result = item_geometry.mutate(directory, pavimento, classe, item_id, **kwargs)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for item in result["affected"]:
        repo.set_campo_validado(conn, obra_id, pavimento, item["classe"], item["item_id"], "_item_", False)
    from ..structural_audit import record
    result['apontamento_id'] = record(conn, request, membro, obra_id, pavimento, result, directory)
    return {"status": "ok", **result}


@router.post("/{obra_id}/itens/{classe}/geometria")
def create(obra_id: str, classe: str, payload: CreateGeometryPayload,
           request: Request, pavimento: str, membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    return execute(request, conn, membro, obra_id, pavimento, classe, "",
                   points=payload.points, create={"name": payload.name, "segment": payload.segment})


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
    return execute(request, conn, membro, obra_id, pavimento, classe, item_id, points=payload.points, fields=payload.fields)


@router.get('/{obra_id}/cortes-interpretados')
def interpreted_items(obra_id: str, request: Request, pavimento: str,
                      membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    # Selection and drawing consume one inventory, including frozen preprocessing
    # evidence before a current production SA collection is available.
    from .viewer_routes import viewer_pavimento_endpoint
    viewer = viewer_pavimento_endpoint(obra_id, pavimento, request, membro, conn)
    items = next((g['itens'] for g in viewer['grupos'] if g['grupo'] == 'cortes_interpretados'), [])
    for item in items:
        title = item.get('rotulo') or item.get('beam_name') or item['item_id']
        if item.get('interpretation_scope') == 'measured_source_geometry':
            width, height = item.get('measured_width_cm'), item.get('measured_height_cm')
            if width is not None:
                title += f' · {width:g}/{height:g} cm'
            title += ' · medidas da fonte · sem referência de nível'
        item['titulo'] = title
    return dict(itens=items)


@router.post('/{obra_id}/itens/cortes_interpretados/{item_id}/validar')
def validate_interpreted(obra_id: str, item_id: str, request: Request, pavimento: str,
                        membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    return review_interpreted(obra_id, item_id, request, pavimento, membro, conn, 'validate')


@router.get('/{obra_id}/itens/cortes/{item_id}/dados-edicao')
def original_cut_fields(obra_id: str, item_id: str, request: Request, pavimento: str,
                        membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    _, directory = context(request, conn, membro, obra_id, pavimento)
    state = ficha_reader.ler_estado_pavimento(directory, pavimento)
    rows = item_geometry.original_cut_sources(state, directory, pavimento)
    row = next((r for r in rows if str(r.get('uid')) == item_id), None)
    if not row:
        row = next((r for r in item_geometry.collection(state, 'cortes') if str(r.get('uid')) == item_id), None)
    if not row:
        raise HTTPException(404, 'corte original não encontrado')
    return dict(fields={k: row.get(k) for k in ('beam_name', 'beam_h', 'beam_w', 'own_laje', 'neigh_laje', 'ficha')},
                points=row.get('pts') or row.get('points'), editable_fields=bool(row.get('ficha')))


def review_interpreted(obra_id, item_id, request, pavimento, membro, conn, action, comentario=''):
    _, directory = context(request, conn, membro, obra_id, pavimento)
    if item_id.startswith('interpreted:source-section:'):
        raise HTTPException(422, 'Este corte contém medidas da fonte; não possui referência de nível validável. A geometria original é preservada.')
    from ..structural_cut_overlay import collect_sections
    from ..structural_review import decide
    from ..structural_audit import record
    state = ficha_reader.ler_estado_pavimento(directory, pavimento)
    inventory = state.get('_current_beam_sections') or collect_sections(directory, pavimento, state)
    try:
        result = decide(directory, pavimento, inventory, item_id, action, membro['id'], comentario=comentario)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    result['apontamento_id'] = record(conn, request, membro, obra_id, pavimento, result, directory)
    return dict(status='ok', **result)


@router.delete("/{obra_id}/itens/{classe}/{item_id}")
def delete(obra_id: str, classe: str, item_id: str, request: Request, pavimento: str,
           inteiro: bool = False, payload: Optional[DeleteReviewPayload] = None,
           membro=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    if classe == 'cortes_interpretados':
        if inteiro:
            raise HTTPException(422, 'selecione apenas o corte interpretado')
        return review_interpreted(obra_id, item_id, request, pavimento, membro, conn, 'delete',
                                 comentario=payload.comentario if payload else '')
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
