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


class HumanNotesIn(BaseModel):
    notes: dict[str, str]


class ValidateLayerIn(BaseModel):
    layer: str
    round_id: str
    candidate_sha256: str
    acknowledge_pending: bool = False


class RollbackLayerIn(BaseModel):
    expected_round_id: str


@router.post('/obras/{obra_id}/qa-camadas/{classe}/{item}/validar')
def validar_camada_qa(obra_id: str, classe: str, item: str, body: ValidateLayerIn,
    request: Request, pavimento: str, behavior: str='para',
    membro: dict=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    from .. import qa_interpretation
    obra_dir = _notes_context(request,conn,obra_id,membro,classe,item,pavimento,behavior)
    if body.layer not in {'L1','L2','L3'}:
        raise HTTPException(422,'camada inválida')
    try:
        result = qa_interpretation.promote(obra_dir,pavimento,classe,item,behavior,body.layer,
            body.round_id,body.candidate_sha256,membro['id'],acknowledge_pending=body.acknowledge_pending,
            previous_svg=_previous_sa_svg(request,obra_dir,pavimento,classe,item,behavior))
    except (ValueError, LookupError) as exc:
        raise HTTPException(409,str(exc)) from exc
    result['apontamento'] = _publish_adoption_notes(request,conn,obra_id,obra_dir,pavimento)
    return result


@router.post('/obras/{obra_id}/qa-camadas/{classe}/{item}/desfazer')
def desfazer_camada_qa(obra_id: str, classe: str, item: str, body: RollbackLayerIn,
    request: Request, pavimento: str, behavior: str='para',
    membro: dict=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    from .. import qa_interpretation
    obra_dir = _notes_context(request,conn,obra_id,membro,classe,item,pavimento,behavior)
    try:
        result = qa_interpretation.rollback(obra_dir,pavimento,classe,item,behavior,
            body.expected_round_id,membro['id'])
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    result['apontamento'] = _publish_adoption_notes(request,conn,obra_id,obra_dir,pavimento)
    return result


def _previous_sa_svg(request, obra_dir, pavimento, classe, item, behavior):
    """Viewer SA congelado na abertura da L1, só se o hash bater com o registrado."""
    from .. import qa_versions
    try:
        first = qa_versions.read(obra_dir,pavimento,classe,item,behavior).get('L1') or {}
        path = (request.app.state.settings.repo_root/'scripts/arete/relatorios/qa_portal'/
                first['round_id']/item/'source.svg')
        svg = path.read_text(encoding='utf-8')
        return svg if qa_versions.digest(svg) == first.get('source_sha256') else None
    except (KeyError, OSError, ValueError, SyntaxError):  # ParseError é SyntaxError
        return None


def _publish_adoption_notes(request, conn, obra_id, obra_dir, pavimento):
    # A adoção já está gravada; falha aqui só deixa o apontamento pendente para reprocesso.
    from .. import qa_adoption_notes
    return qa_adoption_notes.publish_pending(conn,obra_id=obra_id,obra_dir=obra_dir,
        pavimento=pavimento,base_url=str(request.base_url))


@router.get('/obras/{obra_id}/qa-camadas/{classe}/{item}/{layer}')
def obter_candidato_qa(obra_id: str, classe: str, item: str, layer: str,
    request: Request, pavimento: str, behavior: str='para',
    membro: dict=Depends(auth.exige_login), conn=Depends(get_db_conn)):
    from .. import qa_versions
    obra_dir = _notes_context(request,conn,obra_id,membro,classe,item,pavimento,behavior)
    record = qa_versions.read(obra_dir,pavimento,classe,item,behavior).get(layer)
    if not record:
        raise HTTPException(404,'camada não encontrada')
    details = _version_details(obra_dir,pavimento,classe,item,behavior,
        obra_id=obra_id,html_root=request.app.state.settings.repo_root/'scripts/arete/html_fichas'/_obra_do_membro(conn,obra_id,membro)['nome'])
    if (details['agent_reviews'].get(layer) or {}).get('stale'):
        record['stale'] = True
    return record


def _manual_notes_identity(obra_dir, pavimento, classe, item):
    """Aceita nomes livres somente quando pertencem a um item manual existente."""
    from .. import item_geometry
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', item) or item in {'.', '..'}:
        return False
    custom = item_geometry.load(obra_dir, pavimento)
    classes = {'PIL': ['pilares'], 'LAJ': ['lajes'], 'FV': ['fundo'],
               'LV': ['lateral_a_para', 'lateral_b_para', 'lateral_a_passa', 'lateral_b_passa']}
    for collection in classes.get(classe, []):
        deleted = custom.get('deleted', {}).get(collection, [])
        for key, row in custom.get('created', {}).get(collection, {}).items():
            if key not in deleted and 'beam:' + item not in deleted and (row.get('name') or row.get('beam_name')) == item:
                return True
    return False


def _notes_context(request, conn, obra_id, membro, classe, item, pavimento, behavior):
    from .n1_routes import _obra_dir
    from .. import ficha_reader
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    patterns = {'PIL': r'P\d+[A-Z]?', 'FV': r'(?:V|VF)\d+[A-Z]?',
                'LV': r'(?:V|VF)\d+[A-Z]?', 'LAJ': r'L\d+[A-Z]?'}
    if pavimento not in ficha_reader.descobrir_pavimentos(obra_dir):
        raise HTTPException(status_code=404, detail='pavimento não encontrado')
    if classe not in patterns or behavior not in {'para', 'passa'} or not (
            re.fullmatch(patterns[classe], item) or _manual_notes_identity(obra_dir, pavimento, classe, item)):
        raise HTTPException(status_code=422, detail='identidade de item inválida')
    return obra_dir


@router.get('/obras/{obra_id}/qa-notas/{classe}/{item}')
def obter_notas_qa(obra_id: str, classe: str, item: str, request: Request,
                   pavimento: str, behavior: str = 'para',
                   membro: dict = Depends(auth.exige_login), conn=Depends(get_db_conn)):
    from .. import qa_human_notes
    obra_dir = _notes_context(request, conn, obra_id, membro, classe, item, pavimento, behavior)
    return {'notes': qa_human_notes.load(obra_dir, pavimento, classe, item, behavior),
            'qa_available': True,
            **_version_details(obra_dir, pavimento, classe, item, behavior,
                html_root=request.app.state.settings.repo_root / 'scripts/arete/html_fichas' / _obra_do_membro(conn, obra_id, membro)['nome'], obra_id=obra_id)}


@router.put('/obras/{obra_id}/qa-notas/{classe}/{item}')
def salvar_notas_qa(obra_id: str, classe: str, item: str, body: HumanNotesIn, request: Request,
                   pavimento: str, behavior: str = 'para',
                   membro: dict = Depends(auth.exige_login), conn=Depends(get_db_conn)):
    from .. import qa_human_notes
    obra_dir = _notes_context(request, conn, obra_id, membro, classe, item, pavimento, behavior)
    return {'notes': qa_human_notes.save(obra_dir, pavimento, classe, item, body.notes, behavior)}


def _version_details(obra_dir, pavimento, classe, item, behavior, **source_kwargs):
    from .. import qa_versions, qa_interpretation, ficha_reader
    records, layers = qa_versions.availability(obra_dir, pavimento, classe, item, behavior)
    for layer, key in [('L2','c1'),('L3','c2')]:
        if (layers.get(key) or {}).get('available'):
            try:
                qa_versions.source(obra_dir, pavimento, classe, item, layer, behavior, **source_kwargs)
            except (ValueError, LookupError):
                layers[key]['available'] = False
                for record in records.values(): record['stale'] = True
    state = ficha_reader.ler_estado_pavimento(obra_dir,pavimento) or {}
    effective = qa_interpretation.effective_entry(obra_dir,pavimento,classe,item,behavior,state)
    latest = next((dict(layer=layer,round_id=record['round_id'],candidate_sha256=record.get('candidate_sha256'))
                   for layer,record in reversed(list(records.items())) if record.get('svg') and not record.get('stale')),None)
    manifest = qa_interpretation.load_manifest(obra_dir,pavimento)
    return {'agent_reviews': {key: {k:v for k,v in row.items() if k not in {'svg','interpretation','candidate_interpretation','base_sa_snapshot'}} for key,row in records.items()},
            'latest_agentic':latest, 'effective_sa':{k:v for k,v in effective.items() if k!='interpretation'} if effective else None,
            'history':[{k:v for k,v in event.items() if k!='previous'} for event in manifest['history']
                       if event['key']==qa_interpretation.key(classe,item,behavior)],
            'review_allowed': {'L1': True, 'L2': bool((layers.get('c1') or {}).get('available')),
                               'L3': bool((layers.get('c2') or {}).get('available'))}}


class QARoundIn(BaseModel):
    items: list[str]
    classe: str = "PIL"
    pavimento: str = "13_PAV"
    layer: str = "L1"
    behavior: str = "para"
    confirmacao: str = ""


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
    if classe not in {"PIL", "FV", "LV", "LAJ"}:
        raise HTTPException(status_code=422, detail="classe QA inválida")
    if layer not in {"L1", "L2", "L3"}:
        raise HTTPException(status_code=422, detail="layer deve ser L1, L2 ou L3")
    if body.confirmacao.strip().casefold() != "confirmo":
        raise HTTPException(
            status_code=409,
            detail="Revisão agentiva desativada para uso normal; disponível apenas para testes. Digite CONFIRMO para executar.",
        )
    if not items or len(items) > 100:
        raise HTTPException(status_code=422, detail="informe entre 1 e 100 itens por rodada")
    item_pattern = {"PIL":r"P\d+[A-Z]?", "LAJ":r"L\d+[A-Z]?"}.get(classe, r"(?:V|VF)\d+[A-Z]?")
    if any(not re.fullmatch(item_pattern, item) for item in items):
        raise HTTPException(status_code=422, detail=f"item invalido para a classe {classe}")

    from .. import qa_versions
    from .n1_routes import _obra_dir
    obra_dir = _notes_context(request, conn, obra_id, membro, classe, items[0], body.pavimento, body.behavior)
    for item in items:
        try:
            if layer != 'L1':
                qa_versions.source(obra_dir, body.pavimento, classe, item, layer, body.behavior, obra_id=obra_id,
                    html_root=request.app.state.settings.repo_root / 'scripts/arete/html_fichas' / _obra_do_membro(conn, obra_id, membro)['nome'])
        except (ValueError, LookupError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    round_id, job_id = repo.enfileirar_qa_round(
        conn,
        obra_id=obra_id,
        membro_id=membro["id"],
        classe=classe,
        pavimento=body.pavimento,
        layer=layer,
        items=items,
        behavior=body.behavior,
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
    job = conn.execute(
        "SELECT status, erro_msg FROM portal_jobs WHERE id=?",
        (detail["job_id"],),
    ).fetchone()
    detail["job_status"] = job["status"] if job else None
    detail["job_error"] = job["erro_msg"] if job else None
    return detail
