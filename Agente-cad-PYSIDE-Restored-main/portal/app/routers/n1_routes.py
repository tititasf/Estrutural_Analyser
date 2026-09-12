"""Rotas do viewer nativo N1 (SA) — 2026-07-06 (ver plano witty-hopping-sunbeam).

O portal NUNCA reusa o HTML do headless como tela final — só LÊ os artefatos
reais já gerados (`estado_<pav>.json` + fichas HTML) via `ficha_reader`, e
monta a experiência nativa (lista + foto + campos) pedida pelo dono, na mesma
fronteira read-only do resto do portal.
"""

from __future__ import annotations

import math
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import access, auth, dxf_preview, ficha_reader, fv_ficha, fv_operations, laje_ficha, laje_operations, lv_ficha, lv_operations, pipeline_runner, public_codes_lookup, torre_crop
from ..dbdep import get_db_conn
from ...db import repository as repo
from src.core import pillar_n3_ficha
from src.core.cima_l_contract import is_cima_l, portal_cima_l_contract

router = APIRouter(prefix="/obras", tags=["n1"])


class ValidacaoCampoPayload(BaseModel):
    validado: bool


class LVPillarOpeningsPayload(BaseModel):
    pillar_openings: list[dict] = Field(default_factory=list)


class PilarN3FichaPayload(BaseModel):
    ficha: dict


class FvAdotarCamadaPayload(BaseModel):
    layer: str
    confirmado: bool = False


class FvEditarSegmentoPayload(BaseModel):
    points: list[list[float]]


class FvExcluirCamadaPayload(BaseModel):
    layer: str
    confirmado: bool = False


class FvN3DetailsPayload(BaseModel):
    panels: list[dict]
    chamfers: list[dict] = Field(default_factory=list)
    openings: list[dict] = Field(default_factory=list)


class FvRenamePayload(BaseModel):
    new_name: str
    confirmado: bool = False


class FvNotesPayload(BaseModel):
    notes: dict


class LajeFieldsPayload(BaseModel):
    name: str
    nivel: float | str | None = None
    height: float | str | None = None


class LajeN3Payload(BaseModel):
    linhas_verticais: list[dict] = Field(default_factory=list)
    linhas_horizontais: list[dict] = Field(default_factory=list)


class LajeNotesPayload(BaseModel):
    notes: dict


class ConfirmedPayload(BaseModel):
    confirmado: bool = False


class FvAnnotationPayload(BaseModel):
    layer: str
    segment: str = "todos"
    x: float
    y: float
    element: str = ""
    text: str


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _obra_dir(request: Request, obra: dict) -> Path:
    settings = request.app.state.settings
    lp = obra.get("local_path")
    return Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")


def _pavimento_da_obra(obra_dir: Path, pavimento: Optional[str]) -> Optional[str]:
    """Resolve o pavimento: usa o pedido se existir, senao o unico/primeiro real."""
    disponiveis = ficha_reader.descobrir_pavimentos(obra_dir)
    if not disponiveis:
        return None
    if pavimento and pavimento in disponiveis:
        return pavimento
    return disponiveis[0]


def _fv_sa_visual_context(request: Request, obra: dict, obra_dir: Path,
                          pavimento: str, beam: str) -> tuple[object, Path]:
    """Valida e prepara as dependencias do viewer antes de alterar o estado."""
    from .viewer_routes import encontrar_estrutural_limpo

    fonte = encontrar_estrutural_limpo(obra_dir, obra, pavimento)
    if fonte is None:
        raise ValueError("estrutural limpo indisponivel para atualizar o viewer SA")
    transform = dxf_preview.transform_preview_completo(
        Path(fonte["path"]), cache_dir=obra_dir / ".previews",
    )
    if transform is None:
        raise ValueError("estrutural limpo sem transform valida")
    html_root = request.app.state.settings.repo_root / "scripts" / "arete" / "html_fichas" / obra["nome"]
    html_path = fv_ficha.encontrar_ficha_fv(obra_dir, pavimento, beam, html_root)
    if html_path is None:
        raise ValueError("ficha HI-FI indisponivel para atualizar o viewer SA")
    return transform, html_path


def _refresh_fv_sa_visual(obra_dir: Path, pavimento: str, beam: str,
                          context: tuple[object, Path]) -> None:
    """Recria o viewer SA persistido usando o estrutural completo + estado atual."""
    transform, html_path = context
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento) or {}
    raw_segments = [
        row for row in (estado.get("segmentos", {}).get("fundo", []) or [])
        if str(row.get("beam_name") or "").upper() == beam.upper()
    ]
    fv_operations.write_sa_visual(html_path, beam, transform, raw_segments)


@router.get("/{obra_id}/n1/classes")
def listar_classes_n1(obra_id: str, request: Request, pavimento: Optional[str] = None,
                       membro: dict = Depends(auth.exige_login),
                       conn: sqlite3.Connection = Depends(get_db_conn)):
    """Pavimentos disponiveis + classes com contagem (pra montar as sub-abas)."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    disponiveis = ficha_reader.descobrir_pavimentos(obra_dir)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    classes = []
    for classe in ficha_reader.CLASSES_N1:
        if classe in {"pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
            continue
        itens = ficha_reader.listar_itens_n1(estado, classe) if estado else []
        classes.append({
            "classe": classe, "titulo": ficha_reader.TITULOS_CLASSE[classe],
            "total": len(itens),
        })
    return {
        "obra_id": obra_id, "pavimentos": disponiveis, "pavimento_atual": pav,
        "classes": classes,
    }


@router.get("/{obra_id}/n1/{classe}")
def listar_itens_n1_endpoint(obra_id: str, classe: str, request: Request,
                              pavimento: Optional[str] = None,
                              membro: dict = Depends(auth.exige_login),
                              conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        return {"obra_id": obra_id, "classe": classe, "pavimento": None, "itens": []}
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    itens = ficha_reader.listar_itens_n1(estado, classe) if estado else []
    qa_class = "PIL" if classe in {"pilares", "pilares_especiais"} else ("FV" if classe == "fundo" else None)
    qa_reviews = repo.listar_qa_resumos(conn, obra_id, pav, qa_class) if qa_class else {}
    human_validated = {
        row["item_id"] for row in repo.listar_campos_validados_por_obra(conn, obra_id)
        if row["pavimento"] == pav and row["classe"] == classe.upper()
        and row["field_id"] == "_item_"
    }
    # beam_name + Segmento: painel "Criar item" (fundo/laterais) monta o
    # combobox de SEG por viga — sem isto o front só via o título.
    def _item_lista(i: dict) -> dict:
        campos = i.get("campos") or {}
        out = {
            "item_id": i["item_id"],
            "titulo": i["titulo"],
            "validado": i["item_id"] in human_validated,
            "beam_name": i.get("beam_name") or campos.get("Nome") or campos.get("Viga"),
            "segmento": campos.get("Segmento") or campos.get("segmento"),
        }
        qa_key = out["beam_name"] if classe == "fundo" else i["item_id"]
        out["qa_reviews"] = qa_reviews.get(str(qa_key or "").upper(), {})
        if classe == "cortes":
            # [2026-07-13, Fase 3.5] motor de cruzamento corte->laje (main.py)
            if i.get("own_laje") is not None:
                out["own_laje"] = i["own_laje"]
            if i.get("neigh_laje") is not None:
                out["neigh_laje"] = i["neigh_laje"]
        return out

    return {
        "obra_id": obra_id, "classe": classe, "pavimento": pav,
        "itens": [_item_lista(i) for i in itens],
    }


@router.get("/{obra_id}/fv/{beam}")
def obter_ficha_fv_endpoint(
    obra_id: str,
    beam: str,
    request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Ficha HI-FI nativa agrupada por viga de fundo.

    A rota e' somente leitura. O estado SA decide quais segmentos existem; o
    pack HTML persistido enriquece a ficha com SVG contextual e detalhes N3.
    """
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    if not estado:
        raise HTTPException(status_code=404, detail="estado do pavimento nao encontrado")
    html_root = (
        request.app.state.settings.repo_root
        / "scripts" / "arete" / "html_fichas" / obra["nome"]
    )
    try:
        result = fv_ficha.montar_ficha_fv(
            obra_dir, pav, beam, estado, html_fichas_root=html_root,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result["obra"]["id"] = obra_id
    result["obra"]["name"] = obra.get("nome")
    result["qa_reviews"] = repo.listar_qa_resumos(conn, obra_id, pav, "FV").get(beam.upper(), {})
    validated_ids = {
        row["item_id"] for row in repo.listar_campos_validados_por_obra(conn, obra_id)
        if row["pavimento"] == pav and row["classe"] == "FUNDO" and row["field_id"] == "_item_"
    }
    for segment in result["segments"]:
        segment["human_validated"] = segment.get("id") in validated_ids
    result["human_validated"] = bool(result["segments"]) and all(
        segment["human_validated"] for segment in result["segments"]
    )
    return result


@router.get("/{obra_id}/lv/{behavior}/{beam}")
def obter_ficha_lv_endpoint(
    obra_id: str,
    behavior: str,
    beam: str,
    request: Request,
    pavimento: Optional[str] = None,
    include_svgs: bool = True,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Ficha agrupada das laterais A/B de uma viga, sem executar motores."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    if not estado:
        raise HTTPException(status_code=404, detail="estado do pavimento não encontrado")
    try:
        result = lv_ficha.montar_ficha_lv(
            obra_dir, pav, beam, behavior, estado, include_svgs=include_svgs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    validated = {
        (row["classe"].lower(), row["item_id"])
        for row in repo.listar_campos_validados_por_obra(conn, obra_id)
        if row["pavimento"] == pav and row["field_id"] == "_item_"
    }
    for side in ("A", "B"):
        side_data = result["sides"][side]
        for segment in side_data["segments"]:
            segment["human_validated"] = (side_data["class"], segment["id"]) in validated
    return result


@router.get("/{obra_id}/lv/{behavior}/{beam}/camada/{layer}")
def obter_camada_lv_endpoint(
    obra_id: str,
    behavior: str,
    beam: str,
    layer: str,
    request: Request,
    pavimento: Optional[str] = None,
    side: str = "A",
    segment_index: int = 1,
    cut_index: int = 0,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    if not estado:
        raise HTTPException(status_code=404, detail="estado do pavimento não encontrado")
    try:
        return lv_ficha.resolver_camada_lv(
            obra_dir, pav, beam, behavior, estado, layer,
            side=side, segment_index=segment_index, cut_index=cut_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{obra_id}/lv/{behavior}/{beam}/segmentos/{side}/{index}/aberturas-pilar")
def salvar_aberturas_pilar_lv_endpoint(
    obra_id: str,
    behavior: str,
    beam: str,
    side: str,
    index: int,
    body: LVPillarOpeningsPayload,
    request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        saved = lv_operations.save_pillar_openings(
            obra_dir, pav, behavior.lower(), beam.upper(), side, index, body.pillar_openings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "pillar_openings": saved}


@router.get("/{obra_id}/lajes/{item_id}")
def obter_ficha_laje_endpoint(
    obra_id: str, item_id: str, request: Request, pavimento: Optional[str] = None,
    include_svgs: bool = False, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    if not estado:
        raise HTTPException(status_code=404, detail="estado do pavimento não encontrado")
    try:
        result = laje_ficha.montar_ficha_laje(
            obra_dir, pav, item_id, estado, include_svgs=include_svgs,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result["human_validated"] = any(
        row["pavimento"] == pav and row["classe"] == "LAJES"
        and row["item_id"].upper() == item_id.upper() and row["field_id"] == "_item_"
        for row in repo.listar_campos_validados_por_obra(conn, obra_id)
    )
    return result


@router.get("/{obra_id}/lajes/{item_id}/camada/{layer}")
def obter_camada_laje_endpoint(
    obra_id: str, item_id: str, layer: str, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    if not pav or not estado:
        raise HTTPException(status_code=404, detail="estado do pavimento não encontrado")
    try:
        return laje_ficha.resolver_camada_laje(obra_dir, pav, item_id, estado, layer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{obra_id}/lajes/{item_id}/campos")
def editar_campos_laje_endpoint(
    obra_id: str, item_id: str, payload: LajeFieldsPayload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        result = laje_operations.update_fields(obra_dir, pav, item_id, payload.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    repo.set_campo_validado(conn, obra_id, pav, "lajes", item_id, "_item_", False)
    return {"status": "ok", **result}


@router.put("/{obra_id}/lajes/{item_id}/n3")
def editar_n3_laje_endpoint(
    obra_id: str, item_id: str, payload: LajeN3Payload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        return {"status": "ok", **laje_operations.update_n3(obra_dir, pav, item_id, payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/{obra_id}/lajes/{item_id}/notas")
def salvar_notas_laje_endpoint(
    obra_id: str, item_id: str, payload: LajeNotesPayload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    return {"status": "ok", "notes": laje_operations.save_notes(obra_dir, pav, item_id, payload.notes)}


@router.post("/{obra_id}/lajes/{item_id}/regenerar-n3")
def regenerar_n3_laje_endpoint(
    obra_id: str, item_id: str, request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    if not pav or not estado or not ficha_reader.obter_item_n1(estado, "lajes", item_id):
        raise HTTPException(status_code=404, detail="laje não encontrada")
    settings = request.app.state.settings
    meta = {"etapa": "sa_item", "secao": "lajes", "item": item_id, "pav": pav}
    job_id, criado = repo.enfileirar_job_unico_por_meta(
        conn,
        obra_id=obra_id,
        meta=meta,
        chaves=("etapa", "secao", "item", "pav"),
        engine_version=pipeline_runner.engine_version(settings.repo_root),
    )
    request.app.state.job_meta[job_id] = meta
    return {
        "status": "queued" if criado else "already_active",
        "job_id": job_id,
        "item": item_id,
        "created": criado,
    }


@router.get("/{obra_id}/lajes/{item_id}/regenerar-n3/status")
def status_regeneracao_n3_laje_endpoint(
    obra_id: str, item_id: str, request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Descobre o último job deste item para restaurar o monitor após reload."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    alvo = str(item_id).strip().upper()
    for job in repo.listar_jobs_por_obra(conn, obra_id):
        meta = request.app.state.job_meta.get(job["id"]) or repo.obter_job_meta(conn, job["id"])
        if (
            meta.get("etapa") == "sa_item"
            and meta.get("secao") == "lajes"
            and str(meta.get("item") or "").strip().upper() == alvo
            and meta.get("pav") == pav
        ):
            return {
                "job_id": job["id"],
                "active": job["status"] in {"na_fila", "executando"} or (
                    job["status"] == "cancelado" and job.get("erro_msg") == repo.PAUSA_OPERADOR
                ),
            }
    return {"job_id": None, "active": False}


@router.delete("/{obra_id}/lajes/{item_id}")
def excluir_laje_endpoint(
    obra_id: str, item_id: str, payload: ConfirmedPayload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    if not payload.confirmado:
        raise HTTPException(status_code=400, detail="confirmação obrigatória")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        return {"status": "ok", **laje_operations.delete_slab(obra_dir, pav, item_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{obra_id}/fv/{beam}/segmentos/{segment_index}/n3")
def salvar_n3_segmento_fv_endpoint(
    obra_id: str, beam: str, segment_index: int, payload: FvN3DetailsPayload,
    request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    try:
        result = fv_operations.update_n3_override(
            obra_dir, pav, beam, segment_index, payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "pavimento": pav, **result}


@router.post("/{obra_id}/fv/{beam}/segmentos/{segment_index}/regenerar-n3")
def regenerar_n3_segmento_fv_endpoint(
    obra_id: str, beam: str, segment_index: int, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) or {}
    exists = any(
        str(item.get("beam_name") or "").upper() == beam.upper()
        and int(str((item.get("campos") or {}).get("Segmento") or 0)) == segment_index
        for item in ficha_reader.listar_itens_n1(estado, "fundo")
    )
    if not exists:
        raise HTTPException(status_code=404, detail="segmento nao encontrado")
    settings = request.app.state.settings
    job_id = repo.enfileirar_job(
        conn, obra_id=obra_id,
        engine_version=pipeline_runner.engine_version(settings.repo_root),
    )
    meta = {"etapa": "sa_item", "secao": "fundos_viga", "item": beam, "pav": pav,
            "requested_segment": segment_index}
    request.app.state.job_meta[job_id] = meta
    repo.salvar_job_meta(conn, job_id, meta)
    return {"status": "queued", "job_id": job_id, "beam": beam, "segment": segment_index}


@router.post("/{obra_id}/fv/{beam}/renomear")
def renomear_fv_endpoint(
    obra_id: str, beam: str, payload: FvRenamePayload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    if not payload.confirmado:
        raise HTTPException(status_code=409, detail="confirmacao obrigatoria para renomear")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    html_root = request.app.state.settings.repo_root / "scripts" / "arete" / "html_fichas" / obra["nome"]
    html_path = fv_ficha.encontrar_ficha_fv(obra_dir, pav, beam, html_root)
    try:
        result = fv_operations.rename_beam(obra_dir, pav, beam, payload.new_name)
        if html_path and not result.get("unchanged"):
            fv_operations.rename_ficha_artifacts(html_path, beam, result["new_name"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fv_ficha._parse_hifi_html.cache_clear()
    return {"status": "ok", "pavimento": pav, **result}


@router.put("/{obra_id}/fv/{beam}/notas")
def salvar_notas_fv_endpoint(
    obra_id: str, beam: str, payload: FvNotesPayload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    return {"status": "ok", "notes": fv_operations.save_notes(obra_dir, pav, beam, payload.notes)}


@router.post("/{obra_id}/fv/{beam}/apontamentos")
def criar_apontamento_fv_endpoint(
    obra_id: str, beam: str, payload: FvAnnotationPayload, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    try:
        item = fv_operations.add_annotation(obra_dir, pav, beam, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "annotation": item}


@router.delete("/{obra_id}/fv/{beam}/apontamentos/{annotation_id}")
def excluir_apontamento_fv_endpoint(
    obra_id: str, beam: str, annotation_id: str, request: Request,
    pavimento: Optional[str] = None, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    try:
        fv_operations.delete_annotation(obra_dir, pav, beam, annotation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{obra_id}/fv/{beam}/adotar-camada")
def adotar_camada_fv_endpoint(
    obra_id: str, beam: str, payload: FvAdotarCamadaPayload, request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Promove uma proposta C1/C2/C3 estruturada ao SA e remove as propostas.

    A confirmacao explicita faz parte do contrato HTTP para impedir que um
    clique ou cliente antigo sobrescreva o estado canônico silenciosamente.
    """
    if not payload.confirmado:
        raise HTTPException(status_code=409, detail="confirmacao obrigatoria para sobrescrever o SA")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) or {}
    previous_ids = [
        item["item_id"] for item in ficha_reader.listar_itens_n1(estado, "fundo")
        if str(item.get("beam_name") or "").upper() == beam.upper()
    ]
    html_root = request.app.state.settings.repo_root / "scripts" / "arete" / "html_fichas" / obra["nome"]
    html_path = fv_ficha.encontrar_ficha_fv(obra_dir, pav, beam, html_root)
    if html_path is None:
        raise HTTPException(status_code=404, detail="ficha HI-FI da viga nao encontrada")
    try:
        visual_context = _fv_sa_visual_context(request, obra, obra_dir, pav, beam)
        result = fv_operations.adopt_agent_layer(obra_dir, pav, beam, html_path, payload.layer)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        _refresh_fv_sa_visual(obra_dir, pav, beam, visual_context)
        adopted_segments = result.pop("adopted_segments")
        fv_operations.finalize_agent_adoption(
            html_path, beam, payload.layer.lower(), adopted_segments,
        )
    except Exception as exc:
        fv_operations.restore_state_backup(
            Path(result["backup"]), obra_dir / f"estado_{pav}.json",
        )
        raise HTTPException(
            status_code=500,
            detail=f"adocao cancelada e SA restaurado: viewer nao atualizado ({exc})",
        ) from exc
    for item_id in previous_ids:
        repo.set_campo_validado(conn, obra_id, pav, "fundo", item_id, "_item_", False)
    fv_ficha._parse_hifi_html.cache_clear()
    return {"status": "ok", "pavimento": pav, **result}


@router.post("/{obra_id}/fv/{beam}/excluir-camada")
def excluir_camada_fv_endpoint(
    obra_id: str, beam: str, payload: FvExcluirCamadaPayload, request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Remove somente a camada agentica escolhida; SA e demais camadas permanecem."""
    if not payload.confirmado:
        raise HTTPException(status_code=409, detail="confirmacao obrigatoria para excluir a camada")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    html_root = request.app.state.settings.repo_root / "scripts" / "arete" / "html_fichas" / obra["nome"]
    html_path = fv_ficha.encontrar_ficha_fv(obra_dir, pav, beam, html_root)
    if html_path is None:
        raise HTTPException(status_code=404, detail="ficha HI-FI da viga nao encontrada")
    try:
        result = fv_operations.delete_agent_layer(html_path, beam, payload.layer)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fv_ficha._parse_hifi_html.cache_clear()
    return {"status": "ok", "pavimento": pav, **result}


@router.put("/{obra_id}/fv/{beam}/segmentos/{segment_index}")
def editar_segmento_fv_endpoint(
    obra_id: str, beam: str, segment_index: int, payload: FvEditarSegmentoPayload,
    request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    try:
        visual_context = _fv_sa_visual_context(request, obra, obra_dir, pav, beam)
        result = fv_operations.update_segment(obra_dir, pav, beam, segment_index, payload.points)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        _refresh_fv_sa_visual(obra_dir, pav, beam, visual_context)
    except Exception as exc:
        fv_operations.restore_state_backup(
            Path(result["backup"]), obra_dir / f"estado_{pav}.json",
        )
        raise HTTPException(
            status_code=500,
            detail=f"edicao cancelada e SA restaurado: viewer nao atualizado ({exc})",
        ) from exc
    if result.get("item_id"):
        repo.set_campo_validado(conn, obra_id, pav, "fundo", result["item_id"], "_item_", False)
    return {"status": "ok", "pavimento": pav, **result}


@router.delete("/{obra_id}/fv/{beam}/segmentos/{segment_index}")
def excluir_segmento_fv_endpoint(
    obra_id: str, beam: str, segment_index: int, request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) or {}
    previous_ids = [
        item["item_id"] for item in ficha_reader.listar_itens_n1(estado, "fundo")
        if str(item.get("beam_name") or "").upper() == beam.upper()
    ]
    try:
        visual_context = _fv_sa_visual_context(request, obra, obra_dir, pav, beam)
        result = fv_operations.delete_segment(obra_dir, pav, beam, segment_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        _refresh_fv_sa_visual(obra_dir, pav, beam, visual_context)
    except Exception as exc:
        fv_operations.restore_state_backup(
            Path(result["backup"]), obra_dir / f"estado_{pav}.json",
        )
        raise HTTPException(
            status_code=500,
            detail=f"exclusao cancelada e SA restaurado: viewer nao atualizado ({exc})",
        ) from exc
    # A exclusao renumera segmentos; limpa os selos antigos para nao associar
    # uma validacao humana ao novo numero errado.
    for item_id in previous_ids:
        repo.set_campo_validado(conn, obra_id, pav, "fundo", item_id, "_item_", False)
    return {"status": "ok", "pavimento": pav, **result}


@router.get("/{obra_id}/n1/{classe}/{item_id}")
def obter_item_n1_endpoint(obra_id: str, classe: str, item_id: str, request: Request,
                            pavimento: Optional[str] = None,
                            membro: dict = Depends(auth.exige_login),
                            conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado (nenhum estado_<pav>.json)")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    item = ficha_reader.obter_item_n1(estado, classe, item_id) if estado else None
    if item is None:
        raise HTTPException(status_code=404, detail="item nao encontrado nesta classe/pavimento")
    # A ficha persistida contem o SVG contextual completo. O artefato direto
    # da rodada de producao e' fallback para obras/itens ainda sem pack HTML.
    fotos = ficha_reader.resolver_fotos_portal(
        obra_dir, pav, classe, item,
    )
    html_fichas_root = request.app.state.settings.repo_root / "scripts" / "arete" / "html_fichas" / obra["nome"]
    camadas_qa = ficha_reader.resolver_camadas_qa_pilar(
        obra_dir, pav, classe, item, html_fichas_root,
    )
    visualizacoes_n1 = ficha_reader.resolver_visualizacoes_n1_pilar(
        obra_dir, pav, classe, item,
        foto_n1_fallback=fotos["n1"], html_fichas_root=html_fichas_root,
    )
    resumo_pilar_n1 = None
    if classe in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        resumo_pilar_n1 = _resumo_pilar_n1(
            estado, obra_dir, item_id.removesuffix("_Para").removesuffix("_Passa"), pav,
        )
    settings = request.app.state.settings
    code_publico = public_codes_lookup.buscar_code_item(
        settings.public_consulta_db_path, obra_id, pav, classe, item_id,
    )
    referencia = f"{obra.get('nome', '')} › {ficha_reader.pavimento_label(pav)} › {item['titulo']}"
    return {
        "obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": item_id,
        "titulo": item["titulo"], "campos": item["campos"], "atencao": item["atencao"],
        "campos_field_id": item.get("campos_field_id") or {},
        "interpretacao_abcd": item.get("interpretacao_abcd"),
        "interpretacao_abcd_html": item.get("interpretacao_abcd_html") or "",
        "foto_n1": fotos["n1"], "foto_n3": fotos["n3"],
        "foto_n1_origem": fotos["n1_origem"],
        "foto_n3_origem": fotos["n3_origem"],
        "camadas_qa": camadas_qa,
        "visualizacoes_n1": visualizacoes_n1,
        "resumo_pilar_n1": resumo_pilar_n1,
        "code_publico": code_publico, "referencia": referencia,
    }


def _pilar_raw(estado: dict, item_id: str) -> Optional[dict]:
    for pilar in estado.get("pilares", []):
        if str(pilar.get("name") or pilar.get("key") or "") == item_id:
            return pilar
    return None


def _n3_modo(vista: Optional[str]) -> str:
    """Converte a aba do portal na variante que realmente desenha o N3."""
    return "passa" if str(vista or "").lower().endswith("-passa") else "para"


def _ler_json_objeto(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _robot_pilar(obra_dir: Path, item_id: str, modo: Optional[str] = None) -> dict:
    """Retorna o payload N3 que alimenta o DXF da aba solicitada.

    A Fase 4 fornece a base comum, mas as divisões e aberturas de cada face
    pertencem à variante N3 ``para``/``passa`` da Fase 6. Antes, os campos web
    liam somente a Fase 4, enquanto o viewer já lia a Fase 6.
    """
    path = obra_dir / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
    base = _ler_json_objeto(path)
    if modo not in {"para", "passa"}:
        return base
    candidatos = [
        obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / modo / f"{item_id}.json",
        *sorted(
            obra_dir.glob(f"*_*/pilares/n3_variants/{modo}/{item_id}.json"),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        ),
    ]
    for candidato in candidatos:
        variante = _ler_json_objeto(candidato)
        if variante:
            resultado = deepcopy(base)
            resultado.update(variante)
            resultado["_portal_n3_variant"] = modo
            return resultado
    return base


def _override_da_variante(saved: dict | None, modo: str) -> dict | None:
    """Lê só a edição humana da variante aberta, sem vazar Para em Passa."""
    variants = saved.get("variants") if isinstance(saved, dict) else None
    value = variants.get(modo) if isinstance(variants, dict) else None
    return value if isinstance(value, dict) and value.get("schema") == pillar_n3_ficha.SCHEMA else None


def _anexar_lajes_n3(ficha: dict, robot: dict) -> None:
    """Anexa somente a laje realmente vinculada a cada face pelo contrato N3."""
    contract = robot.get("_sa_mode_contract") or {}
    faces_contract = contract.get("faces") if isinstance(contract, dict) else None
    for face, face_data in (ficha.get("faces") or {}).items():
        # O DXF N3 fecha A/B com as duas chapas laterais: comprimento interno
        # + 22 cm.  Isto e' geometria de exibicao N3, nao um novo campo N1.
        face_data["n3_width_extra"] = 22.0 if face in {"A", "B"} else 0.0
        if not isinstance(faces_contract, dict):
            continue
        source = faces_contract.get(face)
        fontes = source.get("fontes_n1") if isinstance(source, dict) else None
        # Mantém no portal a semântica do N3: uma viga que passa não é uma
        # abertura comum. A malha web já tem os valores métricos; aqui só
        # reanexamos a categoria após um override humano ter removido metadados.
        passing_evidence = fontes.get("passa") if isinstance(fontes, dict) else []
        raw_by_side = {"left": [], "right": []}
        for key, raw in sorted(robot.items()):
            if not str(key).startswith(f"abertura_{face}_") or not isinstance(raw, dict):
                continue
            lado = str(raw.get("lado") or raw.get("side") or "").lower()
            raw_by_side["right" if lado in {"direito", "right"} else "left"].append(raw)
        for side, openings in (face_data.get("openings") or {}).items():
            for index, opening in enumerate(openings or []):
                raw = raw_by_side.get(side, [])[index] if index < len(raw_by_side.get(side, [])) else {}
                beam_name = str(raw.get("_viga") or raw.get("viga") or "")
                opening["n3_kind"] = (
                    "passing_beam"
                    if beam_name and any(beam_name in str(item) for item in (passing_evidence or []))
                    else "opening"
                )
        lajes = fontes.get("lajes") if isinstance(fontes, dict) else None
        if not isinstance(lajes, list) or not lajes:
            continue
        thickness = float(source.get("espessura_laje") or robot.get(f"laje_{face}") or 0)
        if thickness <= 0:
            continue
        void = float(source.get("vazio_laje_cm") or robot.get(f"vazio_laje_{face}") or 0)
        # No desenho N3 o vazio representado pela laje inclui a folga fixa de
        # 2 cm.  Contratos antigos podem ainda nao trazer esse campo.
        if void <= 0:
            void = thickness + 2.0
        face_data["slab"] = {
            "evidence": str(lajes[0]), "thickness": thickness,
            "position": max(1, int(float(robot.get(f"posicao_laje_{face}") or 1))),
            "recess": float(source.get("rebaixo_laje_cm") or robot.get(f"rebaixo_laje_{face}") or 0),
            "void": void,
            "level": float(source.get("nivel_laje") or robot.get(f"nivel_laje_{face}") or 0),
        }


def _salvar_override_da_variante(
    obra_dir: Path, pavimento: str, pilar: str, modo: str, ficha: dict,
) -> dict:
    """Persiste uma edição por variante, guardando a ficha web legado intacta."""
    anterior = pillar_n3_ficha.load_ficha(obra_dir, pavimento, pilar) or {}
    variants = deepcopy(anterior.get("variants") or {}) if isinstance(anterior.get("variants"), dict) else {}
    corrente = deepcopy(ficha)
    corrente.pop("variants", None)
    corrente.pop("legacy_pre_variant", None)
    variants[modo] = corrente
    envelope = deepcopy(corrente)
    envelope["variants"] = variants
    # A ficha antiga tinha uma única malha Fase 4. Ela continua recuperável,
    # mas não pode mais substituir a variante que o DXF efetivamente mostra.
    if anterior and "variants" not in anterior:
        envelope["legacy_pre_variant"] = anterior
    salvo = pillar_n3_ficha.save_ficha(obra_dir, pavimento, pilar, envelope)
    resposta = deepcopy(salvo.get("variants", {}).get(modo) or corrente)
    resposta["revision"] = salvo["revision"]
    resposta["source"] = deepcopy(salvo["source"])
    return resposta


def _cima_contract(ficha: dict, robot: dict) -> dict:
    """Campos de Cima no mesmo contrato métrico que desenha o DXF N3."""
    def number(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def fmt(value: float) -> str:
        return str(int(value)) if abs(value - round(value)) < 1e-6 else f"{value:.1f}"

    def label(values: list[float]) -> str:
        return " | ".join(fmt(value) for value in values) if values else "—"

    def balanced(total: float, count: int = 4) -> list[float]:
        whole, remainder = divmod(int(math.floor(total)), count)
        result = [float(whole)] * count
        for index in range(count - remainder, count):
            result[index] += 1.0
        result[-1] += total - math.floor(total)
        return result

    def divisions(total: float, offsets: list[float], preferred: object) -> list[float]:
        candidate = [number(value) for value in preferred] if isinstance(preferred, list) else []
        if len(candidate) == 4 and abs(sum(candidate) - total) <= 0.5:
            return candidate
        ideal = total / 4.0
        best: tuple[tuple[float, ...], list[float]] | None = None
        low, high = max(1, int(math.floor(ideal - 20))), int(math.ceil(ideal + 20))
        for first in range(low, high + 1):
            for second in range(low, high + 1):
                for third in range(low, high + 1):
                    fourth = int(math.floor(total)) - first - second - third
                    if fourth < low or fourth > high:
                        continue
                    values = [float(first), float(second), float(third), float(fourth)]
                    values[-1] += total - math.floor(total)
                    boundaries = [sum(values[:index]) for index in range(1, 4)]
                    conflicts = sum(abs(boundary - offset) <= 3 for boundary in boundaries for offset in offsets)
                    score = (float(conflicts), sum((value - ideal) ** 2 for value in values), *values)
                    if best is None or score < best[0]:
                        best = (score, values)
        return best[1] if best else balanced(total)

    dimensions = ficha["dimensions"]
    length, width = number(dimensions["length"]), number(dimensions["width"])
    grades = [number(robot.get(f"grade_{index}")) for index in range(1, 4)]
    grades = [value for value in grades if value > 0] or [length + 22.0]
    gaps = [number(robot.get(f"distancia_{index}")) for index in range(1, len(grades))]
    gaps = [value for value in gaps if value > 0]
    external = sum(grades) + sum(gaps)
    offsets, cursor = [], -1.0
    for index in range(1, 9):
        spacing = number(robot.get(f"par_{index}_{index + 1}"))
        if spacing <= 0:
            break
        cursor += spacing
        if cursor >= external - 1.0:
            break
        offsets.append(cursor)
    spans = [end - start for start, end in zip([0.0, *offsets], [*offsets, external])]
    cursor = 0.0
    div_a = []
    for index, grade in enumerate(grades, start=1):
        local_offsets = [offset - cursor for offset in offsets if cursor - 3 <= offset <= cursor + grade + 3]
        div_a.append(divisions(grade, local_offsets, robot.get(f"grade_{index}_div_a")))
        if index <= len(gaps):
            cursor += grade + gaps[index - 1]
    div_b = [list(reversed(values)) for values in reversed(div_a)]
    screw_spacings = [number(robot.get(f"par_{index}_{index + 1}")) for index in range(1, 8)]
    return {"rows": [
        ["comprimento interno", f"{fmt(length)} cm"],
        ["largura interna", f"{fmt(width)} cm"],
        ["comprimento +22", f"{fmt(length)} + 22 = {fmt(external)} cm"],
        ["parafusos", f"offsets: {label(offsets)} cm"],
        ["cotas parafusos", f"{label(spans)} cm"],
        ["layout grades", f"{len(grades)} grade(s): {' + '.join(fmt(value) for value in grades)} cm; gaps {label(gaps)}"],
        ["quadradinhos A", " ; ".join(f"G{index + 1}: {label(values)}" for index, values in enumerate(div_a))],
        ["quadradinhos B", " ; ".join(f"G{index + 1}: {label(values)}" for index, values in enumerate(div_b)) + " (espelhado do A)"],
    ], "fields": {
        "comprimento_interno": length,
        "largura_interna": width,
        "comprimento_externo": external,
        "parafusos": screw_spacings,
        "grades": {
            "grade_1": number(robot.get("grade_1")),
            "distancia_1": number(robot.get("distancia_1")),
            "grade_2": number(robot.get("grade_2")),
            "distancia_2": number(robot.get("distancia_2")),
            "grade_3": number(robot.get("grade_3")),
        },
        "quadradinhos": [(values + [None] * 5)[:5] for values in div_a[:3]],
    }}


def _resumo_pilar_n1(
    estado: dict, obra_dir: Path, item_id: str, pavimento: str,
) -> Optional[dict]:
    """Resumo visual canônico da ficha N1 do pilar.

    A tela não deve voltar a exibir o dump genérico de lados/lajes. Classificação
    e orientação vêm do snapshot SA; níveis e pé-direito usam a mesma conversão
    automática consumida pelo N3, sem aplicar eventual override humano do N3.
    """
    pilar = _pilar_raw(estado, item_id)
    if pilar is None:
        return None
    ficha = pillar_n3_ficha.build_ficha(
        pilar, _robot_pilar(obra_dir, item_id), None, pavimento=pavimento,
    )
    dimensions = ficha["dimensions"]
    top_view = ficha["top_view"]
    niveis = _niveis_absolutos_pilar(obra_dir, pavimento, item_id)
    return {
        "classificacao": top_view.get("classification") or "—",
        "orientacao": top_view.get("orientation") or "—",
        "nivel_chegada": niveis.get("nivel_chegada_abs", dimensions.get("nivel_chegada")),
        "nivel_saida": niveis.get("nivel_saida_abs", dimensions.get("nivel_saida")),
        "pe_direito": niveis.get("pd_pavimento_cm", dimensions.get("height")),
    }


def _niveis_absolutos_pilar(obra_dir: Path, pavimento: str, item_id: str) -> dict:
    """Localiza o payload N3 de produção que preserva os níveis absolutos do SA."""
    candidatos = [
        obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / modo / f"{item_id}.json"
        for modo in ("para", "passa")
    ]
    candidatos.extend(sorted(
        obra_dir.glob(f"{pavimento}_*/pilares/n3_variants/para/{item_id}.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ))
    for path in candidatos:
        try:
            import json
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("nivel_chegada_abs") is None or payload.get("nivel_saida_abs") is None:
            continue
        return {
            "nivel_chegada_abs": payload["nivel_chegada_abs"],
            "nivel_saida_abs": payload["nivel_saida_abs"],
            "pd_pavimento_cm": payload.get("pd_pavimento_cm") or payload.get("altura"),
        }
    return {}


@router.get("/{obra_id}/n1/{classe}/{item_id}/pilar-n3-ficha")
def obter_pilar_n3_ficha_endpoint(
    obra_id: str, classe: str, item_id: str, request: Request,
    pavimento: Optional[str] = None, vista: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Ficha editavel N3 derivada do N1, comum a pilares normais/especiais."""
    if classe not in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        raise HTTPException(status_code=400, detail="ficha N3 disponivel somente para pilares")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) or {}
    base_id = item_id.removesuffix("_Para").removesuffix("_Passa")
    pilar = _pilar_raw(estado, base_id)
    if pilar is None:
        raise HTTPException(status_code=404, detail="pilar nao encontrado no N1")
    modo = _n3_modo(vista)
    robot = _robot_pilar(obra_dir, base_id, modo)
    saved_root = pillar_n3_ficha.load_ficha(obra_dir, pav, base_id)
    saved = _override_da_variante(saved_root, modo)
    ficha = pillar_n3_ficha.build_ficha(
        pilar, robot, saved, pavimento=pav,
    )
    _anexar_lajes_n3(ficha, robot)
    cima_canonica = pillar_n3_ficha.build_ficha(
        pilar, robot, None, pavimento=pav,
    )
    visualizacoes_n3 = {}
    if vista:
        svg = ficha_reader.resolver_visualizacao_n3_pilar(
            obra_dir, {"beam_name": base_id}, vista,
        )
        visualizacoes_n3[vista] = svg
    saved_cima = saved.get("cima_contract") if isinstance(saved, dict) else None
    if isinstance(saved_cima, dict) and isinstance(saved_cima.get("rows"), list):
        cima_contract = saved_cima
    elif is_cima_l(robot):
        cima_contract = portal_cima_l_contract(robot)
    else:
        cima_contract = _cima_contract(cima_canonica, robot)
    return {"obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": base_id,
            "ficha": ficha, "visualizacoes_n3": visualizacoes_n3,
            "cima_contract": cima_contract,
            "robot_patch": pillar_n3_ficha.robot_patch(ficha)}


@router.put("/{obra_id}/n1/{classe}/{item_id}/pilar-n3-ficha")
def salvar_pilar_n3_ficha_endpoint(
    obra_id: str, classe: str, item_id: str, payload: PilarN3FichaPayload,
    request: Request, pavimento: Optional[str] = None, vista: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Salva override humano sem alterar estado SA nem project_data.vision."""
    if classe not in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        raise HTTPException(status_code=400, detail="ficha N3 disponivel somente para pilares")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado")
    base_id = item_id.removesuffix("_Para").removesuffix("_Passa")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) or {}
    if _pilar_raw(estado, base_id) is None:
        raise HTTPException(status_code=404, detail="pilar nao encontrado no N1")
    try:
        ficha = _salvar_override_da_variante(
            obra_dir, pav, base_id, _n3_modo(vista), payload.ficha,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "pavimento": pav, "item_id": base_id,
            "revision": ficha["revision"], "ficha": ficha,
            "robot_patch": pillar_n3_ficha.robot_patch(ficha)}


@router.post("/{obra_id}/n1/{classe}/{item_id}/campo/{field_id}/validar")
def validar_campo_endpoint(obra_id: str, classe: str, item_id: str, field_id: str,
                            payload: ValidacaoCampoPayload, request: Request,
                            pavimento: Optional[str] = None,
                            membro: dict = Depends(auth.exige_login),
                            conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-13, harmonização de validação — selo rosa] Valida/desvalida 1
    campo específico de 1 item — granularidade real de campo (diferente da
    validação de classe inteira em `jobs_routes.py`). Gera a origem
    `humano_portal` no app desktop via sync (`docs/CONVENCAO-SELOS-VALIDACAO.md`).
    """
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado (nenhum estado_<pav>.json)")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    item = ficha_reader.obter_item_n1(estado, classe, item_id) if estado else None
    titulo = item.get("titulo") if item else None
    repo.set_campo_validado(
        conn, obra_id, pav, classe, item_id, field_id, payload.validado,
        validado_por=membro.get("login"), titulo=titulo,
    )
    return {"status": "ok", "pavimento": pav, "classe": classe, "item_id": item_id,
            "field_id": field_id, "validado": payload.validado}


@router.get("/{obra_id}/n1/{classe}/{item_id}/campos-validados")
def listar_campos_validados_endpoint(obra_id: str, classe: str, item_id: str, request: Request,
                                      pavimento: Optional[str] = None,
                                      membro: dict = Depends(auth.exige_login),
                                      conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        return {"obra_id": obra_id, "classe": classe, "item_id": item_id, "pavimento": None, "campos": []}
    campos = repo.listar_campos_validados(conn, obra_id, pav, classe, item_id)
    return {"obra_id": obra_id, "classe": classe, "item_id": item_id, "pavimento": pav, "campos": campos}


@router.get("/{obra_id}/campos-validados")
def listar_campos_validados_por_obra_endpoint(obra_id: str,
                                               membro: dict = Depends(auth.exige_login),
                                               conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-13] Todos os campos validados dessa obra (todos pavimentos/
    classes/itens) — a app desktop usa isso pra espelhar em lote, mesmo
    padrão de `GET /{obra_id}/sa` (1 GET, não 1 por item)."""
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return {"obra_id": obra_id, "campos": repo.listar_campos_validados_por_obra(conn, obra_id)}


@router.get("/{obra_id}/obra-code")
def obter_code_obra_endpoint(obra_id: str, request: Request,
                              membro: dict = Depends(auth.exige_login),
                              conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-12] Código público (App de Consulta) da obra inteira —
    mostrado no cabeçalho de `obra_detalhe.html` assim que a obra é aberta/
    criada."""
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    code_publico = public_codes_lookup.buscar_code_obra(settings.public_consulta_db_path, obra_id)
    return {"obra_id": obra_id, "code_publico": code_publico, "referencia": obra.get("nome", "")}


@router.get("/{obra_id}/pavimento-code")
def obter_code_pavimento_endpoint(obra_id: str, pavimento: str, request: Request,
                                   membro: dict = Depends(auth.exige_login),
                                   conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-12] Código público (App de Consulta) de 1 pavimento — usado
    pelo painel de recortes (`obra_detalhe.html`, "ficha do pavimento"/
    recorte limpo da torre) pra mostrar/imprimir o código sem duplicar a
    lógica de lookup no JS."""
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    code_publico = public_codes_lookup.buscar_code_pavimento(
        settings.public_consulta_db_path, obra_id, pavimento,
    )
    referencia = f"{obra.get('nome', '')} › {ficha_reader.pavimento_label(pavimento)}"
    return {"obra_id": obra_id, "pavimento": pavimento, "code_publico": code_publico, "referencia": referencia}


@router.get("/{obra_id}/recorte-code")
def obter_code_recorte_endpoint(obra_id: str, pavimento: str, recorte_tipo: str, bruto_id: str,
                                 request: Request,
                                 membro: dict = Depends(auth.exige_login),
                                 conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-13] Código público de 1 recorte (Torre 1/Detalhes/etc) já
    mintado ao validar (`recortes_routes.py::validar_recorte_endpoint`) —
    usado pra reabrir o painel de recorte depois e mostrar o código sem
    precisar validar de novo."""
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    code_publico = public_codes_lookup.buscar_code_recorte(
        settings.public_consulta_db_path, obra_id, pavimento, recorte_tipo, bruto_id,
    )
    titulo = torre_crop._TITULOS_RECORTE.get(recorte_tipo, recorte_tipo)
    referencia = f"{obra.get('nome', '')} › {ficha_reader.pavimento_label(pavimento)} › {titulo}"
    return {
        "obra_id": obra_id, "pavimento": pavimento, "recorte_tipo": recorte_tipo,
        "bruto_id": bruto_id, "code_publico": code_publico, "referencia": referencia,
    }


@router.get("/{obra_id}/stats-globais")
def stats_globais(obra_id: str, request: Request,
                  membro: dict = Depends(auth.exige_login),
                  conn: sqlite3.Connection = Depends(get_db_conn)):
    """Estatisticas globais de N1 e N3 em toda a obra."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pavimentos = ficha_reader.descobrir_pavimentos(obra_dir)
    
    n1_total = 0
    n1_val = 0
    n3_total = 0
    n3_val = 0
    
    validacoes = request.app.state.validacoes.get(obra_id, {})
    campos_validados = {
        (str(row["pavimento"]), str(row["classe"]).upper(), str(row["item_id"]))
        for row in repo.listar_campos_validados_por_obra(conn, obra_id)
        if row.get("field_id") == "_item_"
    }
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    releases_por_pav: dict[str, dict[str, dict]] = {}
    for release in releases:
        pav = str(release.get("pavimento") or "")
        classe = str(release.get("classe") or "").upper()
        if pav and classe:
            # A consulta vem do mais recente para o mais antigo: preserva o
            # primeiro release de cada classe/pavimento.
            releases_por_pav.setdefault(pav, {}).setdefault(classe, release)
    status_pavimentos: dict[str, dict] = {}
    
    for pav in pavimentos:
        estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
        if not estado: continue
        pav_n1_total = 0
        pav_n1_val = 0
        classes_necessarias: set[str] = set()
        
        for classe in ficha_reader.CLASSES_N1:
            # Pilares N3 (Para/Passa) sao so' reprojecao N3 dos mesmos pilares
            # de "pilares"/"pilares_especiais" — contar aqui duplicaria os
            # pilares no total de N1.
            if classe in ficha_reader._PILARES_N3_VARIANTE:
                continue
            itens_n1 = ficha_reader.listar_itens_n1(estado, classe)
            n1_total += len(itens_n1)
            pav_n1_total += len(itens_n1)
            if itens_n1:
                if classe in ("pilares", "pilares_especiais"):
                    classes_necessarias.add("PL")
                elif classe == "lajes":
                    classes_necessarias.add("LJ")
                elif classe == "fundo":
                    classes_necessarias.add("FV")
                elif classe.startswith("lateral_"):
                    classes_necessarias.add("LV")
            for it in itens_n1:
                item_id = it["item_id"]
                val = validacoes.get(classe, {}).get(item_id, {})
                if val.get("n1_ok"):
                    n1_val += 1
                if (str(pav), str(classe).upper(), str(item_id)) in campos_validados:
                    pav_n1_val += 1
                    
        # [FIX] `ficha_reader.CLASSES_N3`/`listar_itens_n3` nao existem — N3 e'
        # "robo gerado a partir do N1" (mesmo conjunto de classes/itens do N1,
        # so' que com validacao propria `n3_ok`), nao uma fonte de dados
        # separada. Reaproveita CLASSES_N1/listar_itens_n1, igual o resto do
        # app ja' faz (mesmo endpoint /n1/classes serve as duas abas).
        for classe in ficha_reader.CLASSES_N1:
            # Pilares tem N3 proprio (2 variantes Para/Passa, ficha diferente
            # da N1) — a reprojecao generica ("mesmos itens do N1") nao vale
            # pra eles, senao conta cada pilar 2x (pilares/especiais) + 2x
            # (variantes) no total de N3.
            if classe in ("pilares", "pilares_especiais"):
                continue
            itens_n3 = ficha_reader.listar_itens_n1(estado, classe)
            n3_total += len(itens_n3)
            for it in itens_n3:
                item_id = it["item_id"]
                val = validacoes.get(classe, {}).get(item_id, {})
                if val.get("n3_ok"):
                    n3_val += 1

        pav_releases = releases_por_pav.get(str(pav), {})
        classes_liberadas = classes_necessarias.intersection(pav_releases)
        classes_com_arquivo = {
            classe for classe in classes_liberadas
            if pav_releases[classe].get("dxf_path")
            and Path(pav_releases[classe]["dxf_path"]).is_file()
        }
        status_pavimentos[str(pav)] = {
            "n1_total": pav_n1_total,
            "n1_validados": pav_n1_val,
            "classes_necessarias": sorted(classes_necessarias),
            "classes_liberadas": sorted(classes_liberadas),
            "fase3_concluida": pav_n1_total > 0 and pav_n1_val == pav_n1_total,
            "fase4_concluida": bool(classes_necessarias) and classes_liberadas == classes_necessarias,
            "fase5_concluida": bool(classes_necessarias) and classes_com_arquivo == classes_necessarias,
        }
                    
    return {
        "n1": {"total": n1_total, "validados": n1_val},
        "n3": {"total": n3_total, "validados": n3_val},
        "pavimentos": status_pavimentos,
    }
