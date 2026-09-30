"""Rotas do viewer nativo N1 (SA) — 2026-07-06 (ver plano witty-hopping-sunbeam).

O portal NUNCA reusa o HTML do headless como tela final — só LÊ os artefatos
reais já gerados (`estado_<pav>.json` + fichas HTML) via `ficha_reader`, e
monta a experiência nativa (lista + foto + campos) pedida pelo dono, na mesma
fronteira read-only do resto do portal.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import access, auth, dxf_preview, ficha_reader, fv_ficha, fv_operations, laje_ficha, laje_operations, lv_ficha, lv_operations, lv_n3_operations, pipeline_runner, public_codes_lookup, torre_crop, pillar_level_view, pillar_abcd_review, pillar_tag_view
from ..dbdep import get_db_conn
from ..drawing_modes import normalize_visual_mode
from ...db import repository as repo
from src.core import pillar_n3_ficha
from src.core.cima_l_contract import is_cima_l, portal_cima_l_contract

def _bloquear_modo_oposto(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)) -> None:
    """Impede acesso direto às rotas N1/N3 do modo não escolhido pela obra."""
    params = request.path_params
    obra_id = params.get("obra_id")
    if not obra_id:
        return
    obra = repo.obter_obra(conn, obra_id)
    modo = str((obra or {}).get("comportamento") or "misto").lower()
    if modo == "misto":
        return
    classe = str(params.get("classe") or "").lower()
    behavior = str(params.get("behavior") or "").lower()
    vista = str(params.get("vista") or request.query_params.get("vista") or "").lower()
    oposto = "passa" if modo == "para" else "para"
    if (behavior == oposto or classe in {f"lateral_a_{oposto}", f"lateral_b_{oposto}",
                                     f"pilares_n3_{oposto}"} or
            (classe.startswith("pilares") and
             (vista.endswith("-" + oposto) or vista.endswith("_" + oposto)))):
        raise HTTPException(status_code=404, detail="vista indisponível para esta obra")
    if (modo == "passa" and classe.startswith("pilares") and
            "/pilar-n3-ficha" in request.url.path and not vista):
        raise HTTPException(status_code=404, detail="vista deve ser informada para esta obra")


router = APIRouter(prefix="/obras", tags=["n1"], dependencies=[Depends(_bloquear_modo_oposto)])


class ValidacaoCampoPayload(BaseModel):
    validado: bool


class LVPillarOpeningsPayload(BaseModel):
    pillar_openings: list[dict] = Field(default_factory=list)


class LVN3FichaPayload(BaseModel):
    source_hash: str
    revision: int
    sides: dict


class PilarN3FichaPayload(BaseModel):
    ficha: dict


class PilarSaReviewPayload(BaseModel):
    fields: dict


class PilarAbcdReviewPayload(BaseModel):
    edits: list[dict]


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


class DrawingModePayload(BaseModel):
    visual_mode: Literal["NOVA", "INI"] = "NOVA"


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
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    release_classes = {
        str(release.get("classe") or "").upper()
        for release in releases
        if str(release.get("pavimento") or "") == str(pav or "")
        and release.get("dxf_path") and Path(release["dxf_path"]).is_file()
    }
    n5_por_classe = {
        "pilares": "PL", "lajes": "LJ", "fundo": "FV",
        "lateral_a_para": "LV", "lateral_b_para": "LV",
        "lateral_a_passa": "LV", "lateral_b_passa": "LV",
    }
    classes = []
    for classe in ficha_reader.CLASSES_N1:
        modo = str(obra.get("comportamento") or "misto").lower()
        if modo != "misto" and classe in {f"lateral_a_{'passa' if modo == 'para' else 'para'}",
                                             f"lateral_b_{'passa' if modo == 'para' else 'para'}"}:
            continue
        if classe in {"pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
            continue
        itens = ficha_reader.listar_itens_n1(estado, classe) if estado else []
        classes.append({
            "classe": classe, "titulo": ficha_reader.TITULOS_CLASSE[classe],
            "total": len(itens),
            "n5_concluido": n5_por_classe.get(classe) in release_classes,
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
            "classification": campos.get("Classificação"),
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
    visual_mode: Optional[Literal["NOVA", "INI"]] = None,
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
            visual_mode=visual_mode,
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
    try:
        result["n3_ficha"] = lv_n3_operations.load_ficha(obra_dir, pav, behavior, beam)
    except FileNotFoundError:
        result["n3_ficha"] = None
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
    visual_mode: Literal["NOVA", "INI"] = "NOVA",
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
            obra_id=obra_id, side=side, segment_index=segment_index, cut_index=cut_index,
            visual_mode=visual_mode,
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


@router.put("/{obra_id}/lv/{behavior}/{beam}/n3-ficha")
def salvar_n3_ficha_lv_endpoint(
    obra_id: str, behavior: str, beam: str, body: LVN3FichaPayload,
    request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if not pav:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        ficha = lv_n3_operations.save_ficha(
            obra_dir, pav, behavior, beam,
            {"source_hash": body.source_hash, "revision": body.revision,
             "sides": body.sides},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "ficha": ficha}


@router.post("/{obra_id}/lv/{behavior}/{beam}/regenerar-n3/{view}")
def regenerar_n3_vista_lv_endpoint(
    obra_id: str, behavior: str, beam: str, view: str, request: Request,
    body: DrawingModePayload | None = None, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    if view not in {"corte", "paineis-a", "paineis-b"}:
        raise HTTPException(status_code=422, detail="vista N3 LV inválida")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if not pav:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        behavior, beam = lv_n3_operations._identity(behavior, beam)
        ficha = lv_n3_operations.load_ficha(obra_dir, pav, behavior, beam)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if ficha["stale"]:
        raise HTTPException(status_code=409, detail="contrato SA mudou; revise e salve a ficha N3 LV")
    meta = {
        "etapa": "n3_lv_view_item", "secao": "lv", "item": beam,
        "pav": pav, "behavior": behavior, "requested_view": view,
        "visual_mode": normalize_visual_mode(body.visual_mode if body else "NOVA"),
    }
    job_id, criado = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta,
        chaves=("etapa", "secao", "item", "pav", "behavior", "requested_view"),
        engine_version=pipeline_runner.engine_version(request.app.state.settings.repo_root),
    )
    request.app.state.job_meta[job_id] = meta
    return {"status": "queued" if criado else "already_active", "job_id": job_id,
            "created": criado, "view": view}


@router.get("/{obra_id}/lv/{behavior}/{beam}/regenerar-n3/{view}/status")
def status_regeneracao_n3_vista_lv_endpoint(
    obra_id: str, behavior: str, beam: str, view: str, request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    if view not in {"corte", "paineis-a", "paineis-b"}:
        raise HTTPException(status_code=422, detail="vista N3 LV inválida")
    obra = _obra_do_membro(conn, obra_id, membro)
    pav = _pavimento_da_obra(_obra_dir(request, obra), pavimento)
    if not pav:
        raise HTTPException(status_code=404, detail="pavimento não encontrado")
    try:
        behavior, beam = lv_n3_operations._identity(behavior, beam)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for job in repo.listar_jobs_por_obra(conn, obra_id):
        meta = request.app.state.job_meta.get(job["id"]) or repo.obter_job_meta(conn, job["id"])
        if all((meta.get(key) == value for key, value in (
            ("etapa", "n3_lv_view_item"), ("item", beam), ("pav", pav),
            ("behavior", behavior), ("requested_view", view),
        ))):
            return {"job_id": job["id"], "active": job["status"] in {"na_fila", "executando"}}
    return {"job_id": None, "active": False}


@router.get("/{obra_id}/lajes/{item_id}")
def obter_ficha_laje_endpoint(
    obra_id: str, item_id: str, request: Request, pavimento: Optional[str] = None,
    include_svgs: bool = False,
    visual_mode: Optional[Literal["NOVA", "INI"]] = None,
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
        result = laje_ficha.montar_ficha_laje(
            obra_dir, pav, item_id, estado, include_svgs=include_svgs,
            visual_mode=visual_mode,
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
    pavimento: Optional[str] = None,
    visual_mode: Optional[Literal["NOVA", "INI"]] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    if not pav or not estado:
        raise HTTPException(status_code=404, detail="estado do pavimento não encontrado")
    try:
        return laje_ficha.resolver_camada_laje(
            obra_dir, pav, item_id, estado, layer, visual_mode,
        )
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
        estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
        if not estado:
            raise LookupError("estado do pavimento não encontrado")
        ficha = laje_ficha.montar_ficha_laje(obra_dir, pav, item_id, estado)
        return {"status": "ok", **laje_operations.update_n3(
            obra_dir, pav, item_id, payload.model_dump(),
            comprimento=ficha["n3"].get("comprimento"),
            largura=ficha["n3"].get("largura"),
        )}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    obra_id: str, item_id: str, request: Request,
    payload: DrawingModePayload | None = None,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    if not pav or not estado or not ficha_reader.obter_item_n1(estado, "lajes", item_id):
        raise HTTPException(status_code=404, detail="laje não encontrada")
    settings = request.app.state.settings
    try:
        visual_mode = normalize_visual_mode(payload.visual_mode if payload else "NOVA")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    meta = {"etapa": "sa_item", "secao": "lajes", "item": item_id, "pav": pav,
            "visual_mode": visual_mode}
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
    payload: DrawingModePayload | None = None,
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
    try:
        visual_mode = normalize_visual_mode(payload.visual_mode if payload else "NOVA")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    meta = {"etapa": "sa_item", "secao": "fundos_viga", "item": beam, "pav": pav,
            "requested_segment": segment_index, "visual_mode": visual_mode}
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
    tag_sync = "original"
    if classe in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        resumo_pilar_n1 = _resumo_pilar_n1(
            estado, obra_dir, item_id.removesuffix("_Para").removesuffix("_Passa"), pav,
        )
        if item.get("interpretacao_abcd"):
            from src.core.pillar_abcd_tables import format_abcd_tables_portal_html
            from src.core.pillar_special_faces import format_tables_portal_dynamic

            item["interpretacao_abcd"] = pillar_level_view.enrich_pillar_abcd_levels(
                item["interpretacao_abcd"], estado,
                (resumo_pilar_n1 or {}).get("nivel_chegada"),
                pillar_level_view.load_preprocess_slab_levels(obra_dir, pav),
                pillar_name=item_id.removesuffix("_Para").removesuffix("_Passa"),
                beam_dim_texts=pillar_level_view.load_beam_dimension_texts(estado),
            )
            item["interpretacao_abcd"] = pillar_abcd_review.apply_review(
                item["interpretacao_abcd"], obra_dir, pav,
                item_id.removesuffix("_Para").removesuffix("_Passa"),
            )
            item["interpretacao_abcd_html"] = format_tables_portal_dynamic(
                format_abcd_tables_portal_html, item["interpretacao_abcd"],
            )
            try:
                updated_tag = pillar_tag_view.refreshed_tag_svg(
                    obra_dir, pav, item_id.removesuffix("_Para").removesuffix("_Passa"),
                    estado, item["interpretacao_abcd"],
                )
            except Exception:
                logging.getLogger(__name__).exception("Falha ao atualizar tag ABCD de %s/%s", pav, item_id)
                updated_tag = None
            if updated_tag:
                visualizacoes_n1["com_tag"] = updated_tag
                tag_sync = "atualizada"
            else:
                tag_sync = "original_nao_sincronizada"
    settings = request.app.state.settings
    code_publico = public_codes_lookup.buscar_code_item(
        settings.public_consulta_db_path, obra_id, pav, classe, item_id,
    )
    referencia = f"{obra.get('nome', '')} › {ficha_reader.pavimento_label(pav)} › {item['titulo']}"
    return {
        "obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": item_id,
        "titulo": item["titulo"], "campos": item["campos"], "atencao": item["atencao"],
        "campos_field_id": item.get("campos_field_id") or {},
        "campos_somente_leitura": item.get("campos_somente_leitura") or [],
        "campos_links": item.get("campos_links") or {},
        "referencias_corte": item.get("referencias_corte"),
        "interpretacao_abcd": item.get("interpretacao_abcd"),
        "interpretacao_abcd_html": item.get("interpretacao_abcd_html") or "",
        "foto_n1": fotos["n1"], "foto_n3": fotos["n3"],
        "foto_n1_origem": fotos["n1_origem"],
        "foto_n3_origem": fotos["n3_origem"],
        "camadas_qa": camadas_qa,
        "visualizacoes_n1": visualizacoes_n1,
        "tag_sync": tag_sync,
        "resumo_pilar_n1": resumo_pilar_n1,
        "code_publico": code_publico, "referencia": referencia,
    }


@router.put("/{obra_id}/n1/{classe}/{item_id}/sa-review")
def salvar_pilar_sa_review_endpoint(
    obra_id: str, classe: str, item_id: str, payload: PilarSaReviewPayload,
    request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    if classe not in {"pilares", "pilares_especiais"}:
        raise HTTPException(status_code=400, detail="Campos SA disponíveis somente para pilares")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    if not _pilar_raw(estado or {}, item_id):
        raise HTTPException(status_code=404, detail="Pilar não encontrado")
    from src.core import pillar_sa_review
    try:
        fields = pillar_sa_review.save(obra_dir, pav, item_id, payload.fields)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "fields": fields,
            "n3_n5_eligible": pillar_sa_review.eligible(pillar_sa_review.apply(_pilar_raw(estado, item_id), fields))}


@router.put("/{obra_id}/n1/{classe}/{item_id}/abcd-review")
def salvar_pilar_abcd_review_endpoint(
    obra_id: str, classe: str, item_id: str, payload: PilarAbcdReviewPayload,
    request: Request, pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login), conn: sqlite3.Connection = Depends(get_db_conn),
):
    if classe not in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        raise HTTPException(status_code=400, detail="revisão ABCD disponível somente para pilares")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    base_id = item_id.removesuffix("_Para").removesuffix("_Passa")
    pillar = _pilar_raw(estado or {}, base_id)
    if not pillar or not pillar.get("interpretacao_abcd"):
        raise HTTPException(status_code=404, detail="tabela ABCD do pilar não encontrada")
    try:
        revision = pillar_abcd_review.save_review(
            obra_dir, pav, base_id, pillar["interpretacao_abcd"], payload.edits,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "revision": revision}


def _pilar_raw(estado: dict, item_id: str) -> Optional[dict]:
    for pilar in estado.get("pilares", []):
        if str(pilar.get("name") or pilar.get("key") or "") == item_id:
            return pilar
    return None


def _exigir_pilar_n3(estado: dict, item_id: str) -> None:
    from src.core.pillar_sa_review import eligible
    pillar = _pilar_raw(estado, item_id)
    if pillar and not eligible(pillar):
        raise HTTPException(status_code=409, detail="Pilar NASCE no próximo pavimento: disponível somente no SA")


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


def _anexar_lajes_n3(ficha: dict, robot: dict, abcd: dict | None = None) -> None:
    """Anexa somente a laje realmente vinculada a cada face pelo contrato N3."""
    contract = robot.get("_sa_mode_contract") or {}
    faces_contract = contract.get("faces") if isinstance(contract, dict) else None
    altura_contract = contract.get("altura_pilar") if isinstance(contract, dict) else None
    pillar_top = robot.get("nivel_chegada_abs") or (
        altura_contract.get("nivel_chegada_abs") if isinstance(altura_contract, dict) else None
    )
    pillar_bottom = robot.get("nivel_saida_abs") or (
        altura_contract.get("nivel_saida_abs") if isinstance(altura_contract, dict) else None
    )
    if pillar_top is not None:
        ficha.setdefault("source", {})["pillar_top_level"] = float(pillar_top)
    if pillar_bottom is not None:
        ficha.setdefault("source", {})["pillar_bottom_level"] = float(pillar_bottom)
    beam_rows = []
    dimension_rows = []
    slab_rows = []
    for face_id, face_rows in ((abcd or {}).get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            for row in face_rows.get(role) or []:
                name = str(row.get("nome") or "").strip()
                dimension = str(row.get("dim") or "").strip()
                if name and re.fullmatch(r"\d+(?:[.,]\d+)?\s*/\s*\d+(?:[.,]\d+)?", dimension):
                    dimension_rows.append((face_id, name, str(row.get("canto") or ""),
                                           dimension.replace(" ", ""), row.get("dim_status")))
                try:
                    level = float(str(row.get("nivel") or "").strip().removesuffix("cm").strip().replace(",", "."))
                except ValueError:
                    continue
                beam_rows.append((face_id, str(row.get("nome") or ""),
                                  str(row.get("canto") or ""), level,
                                  str(row.get("nivel_status") or "")))
        for row in face_rows.get("lajes") or []:
            name = str(row.get("nome") or "").strip()
            dimension = str(row.get("dim") or "").strip()
            if name and re.fullmatch(r"\d+(?:[.,]\d+)?(?:\s*cm)?", dimension, re.I):
                slab_rows.append((face_id, name, float(dimension.lower().removesuffix("cm").replace(",", "."))))

    def current_dimension(face_id: str, name: str, corner: str = "") -> str:
        matching = [row for row in dimension_rows if row[1] == name]
        for scoped in (
            [row for row in matching if row[0] == face_id and row[2] == corner],
            [row for row in matching if row[0] == face_id], matching,
        ):
            values = {row[3] for row in scoped}
            if len(values) == 1:
                return next(iter(values))
            if scoped:
                break
        return ""

    def current_slab_thickness(face_id: str, name: str) -> float | None:
        scoped = [row[2] for row in slab_rows if row[0] == face_id and row[1] == name]
        if not scoped:
            scoped = [row[2] for row in slab_rows if row[1] == name]
        values = {round(value, 4) for value in scoped}
        return next(iter(values)) if len(values) == 1 else None

    def beam_level(face_id: str, name: str, corner: str):
        matching = [row for row in beam_rows if row[1] == name]
        for scoped in (
            [row for row in matching if row[0] == face_id and row[2] == corner],
            [row for row in matching if row[0] == face_id],
            matching,
        ):
            levels = {round(row[3], 4) for row in scoped}
            if len(levels) == 1:
                return next(iter(levels)), scoped[0][4]
            if scoped:
                break
        return None

    def evidence_identity(value: object, prefix: str) -> tuple[str, str]:
        evidence = str(value or "")
        name = re.search(rf"\b{prefix}\s*:\s*([A-Za-z][A-Za-z0-9_-]*)", evidence, re.I)
        dimension = re.search(r"\bdim\s*:\s*([\d.,]+\s*[/xX]\s*[\d.,]+)", evidence, re.I)
        if prefix == "Laje":
            dimension = re.search(r"\besp\s*:\s*([\d.,]+)\s*cm", evidence, re.I)
        return (name.group(1) if name else "", dimension.group(1).replace(" ", "") if dimension else "")

    def opening_identity(source: dict, raw: dict, face: str, face_width: float) -> tuple[str, str]:
        name, slot = str(raw.get("_viga") or raw.get("viga") or ""), str(raw.get("_origem") or "")
        width, depth = float(raw.get("largura") or 0), float(raw.get("altura") or 0)
        matches = []
        for behavior, key in (("viga_para", "aberturas_vigas_que_param"),
                              ("viga_chega", "aberturas_vigas_que_chegam"),
                              ("viga_passa", "aberturas_vigas_que_passam")):
            for item in source.get(key) or []:
                if str(item.get("nome") or "") != name:
                    continue
                if slot and str(item.get("slot") or "") != slot:
                    continue
                candidates = [item.get(k) for k in ("largura_abertura", "largura_nova", "largura_ini")]
                same_width = any(v is not None and abs(float(v) - width) < 0.2 for v in candidates)
                same_depth = item.get("altura") is not None and abs(float(item["altura"]) - depth) < 0.2
                score = (4 if same_width else 0) + (2 if same_depth else 0)
                matches.append((score, behavior, item))
        if not matches:
            return "", ""
        matches.sort(key=lambda entry: entry[0], reverse=True)
        best = matches[0]
        if len(matches) > 1 and matches[1][0] == best[0] and matches[1][1] != best[1]:
            return "", ""
        item = best[2]
        nominal = f"{float(item.get('largura') or 0):g}/{float(item.get('profundidade') or 0):g}"
        behavior = best[1]
        # Em face curta, viga da mesma largura da face ocupa o contato inteiro.
        # O alargamento de montagem do N3 (ex. 19 -> 27) não muda o vínculo SA.
        if (face in {"C", "D"} and behavior == "viga_chega" and face_width > 0
                and float(item.get("largura") or 0) >= face_width - 0.2):
            behavior = "viga_interna"
        return behavior, nominal
    for face, face_data in (ficha.get("faces") or {}).items():
        # O DXF N3 fecha A/B com as duas chapas laterais: comprimento interno
        # + 22 cm.  Isto e' geometria de exibicao N3, nao um novo campo N1.
        face_data["n3_width_extra"] = 22.0 if face in {"A", "B"} else 0.0
        if not isinstance(faces_contract, dict):
            continue
        source = faces_contract.get(face)
        if not isinstance(source, dict):
            source = {}
        top_void = source.get("vazio_topo") if isinstance(source, dict) else None
        if isinstance(top_void, dict):
            declared_top_void = max(0.0, float(top_void.get("valor_cm") or 0.0))
            face_data["top_void_cm"] = declared_top_void
            face_data["top_void_evidence"] = str(top_void.get("evidencia") or "")
            prefix = "Laje" if "laje" in str(top_void.get("fonte") or "").lower() else "Viga"
            name, dimension = evidence_identity(top_void.get("evidencia"), prefix)
            if prefix == "Viga":
                dimension = current_dimension(face, name) or dimension
                if dimension and declared_top_void > 0:
                    face_data["top_void_cm"] = float(dimension.split("/")[1].replace(",", ".")) + 4
            else:
                thickness = current_slab_thickness(face, name)
                if thickness is not None:
                    dimension = f"{thickness:g}"
                    if declared_top_void > 0:
                        face_data["top_void_cm"] = thickness + 2
            if dimension and dimension != evidence_identity(top_void.get("evidencia"), prefix)[1]:
                face_data["top_void_evidence"] = (
                    f"SA/N1 atual: {name} · dim: {dimension}. "
                    f"Evidência original N3: {top_void.get('evidencia') or ''}"
                )
            # Uma variante antiga ainda pode ter a malha calculada com a
            # dimensão anterior da viga. Só a atualizamos quando ela coincide
            # exatamente com a malha automática antiga; uma edição manual
            # diferente continua sendo autoridade.
            current_void = float(face_data["top_void_cm"])
            panels = face_data.get("panels") or []
            old_rows = sorted({int(p.get("row") or 0) for p in panels})
            old_heights = [max(float(p.get("height") or 0) for p in panels
                               if int(p.get("row") or 0) == row) for row in old_rows]
            raw_intervals = robot.get(f"paineis_intervals_{face}") or []
            if not isinstance(raw_intervals, (list, tuple)):
                raw_intervals = [raw_intervals]
            old_mesh = [float(value) for value in raw_intervals if value is not None]
            pillar_height = float((ficha.get("dimensions") or {}).get("height") or 0)
            if (face in {"C", "D"} and panels and len(old_heights) == len(old_mesh) + 1
                    and all(abs(a - b) < 0.01 for a, b in zip(old_heights[1:], old_mesh))
                    and abs(sum(old_heights) + declared_top_void - pillar_height) < 0.01
                    and abs(current_void - declared_top_void) > 0.01):
                from scripts.pl_abcd_visual_nova import paineis_intervals_for_face
                new_mesh = paineis_intervals_for_face(
                    face_id=face, height_cm=pillar_height,
                    h1_cm=old_heights[0], top_void_cm=current_void,
                )
                columns = [p for p in panels if int(p.get("row") or 0) == old_rows[0]]
                rebuilt = [p for p in panels if int(p.get("row") or 0) == old_rows[0]]
                for index, height in enumerate(new_mesh, start=2):
                    for template in columns:
                        panel = next((p for p in panels
                                      if int(p.get("row") or 0) == index
                                      and int(p.get("column") or 0) == int(template.get("column") or 0)), None)
                        panel = dict(panel or template)
                        panel.update(id=f"{face}{index}-{int(template.get('column') or 1)}",
                                     row=index, height=height)
                        rebuilt.append(panel)
                face_data["panels"] = rebuilt
            face_data["top_void_name"] = name
            face_data["top_void_dimension"] = dimension
            void_source = str(top_void.get("fonte") or "")
            face_data["top_void_behavior"] = (
                "laje" if prefix == "Laje" else
                "viga_interna" if "interior" in void_source else "viga_passa"
            )
        fontes = source.get("fontes_n1") if isinstance(source, dict) else None
        raw_by_side = {"left": [], "right": []}
        face_width = max((float(panel.get("width") or 0) for panel in face_data.get("panels") or []), default=0)
        for key, raw in sorted(robot.items()):
            if not str(key).startswith(f"abertura_{face}_") or not isinstance(raw, dict):
                continue
            lado = str(raw.get("origem_portal") or raw.get("lado") or raw.get("side") or "").lower()
            raw_by_side["right" if lado in {"direito", "right"} else "left"].append(raw)
        all_beam_openings = [value for key, value in robot.items()
                             if str(key).startswith("abertura_") and isinstance(value, dict)]
        for side, openings in (face_data.get("openings") or {}).items():
            for index, opening in enumerate(openings or []):
                raw = raw_by_side.get(side, [])[index] if index < len(raw_by_side.get(side, [])) else {}
                if raw.get("_origem"):
                    opening["n3_slot"] = str(raw["_origem"])
                slot = str(raw.get("_origem") or opening.get("n3_slot") or "")
                beam_name = str(raw.get("_viga") or raw.get("viga") or opening.get("beam_name") or "")
                behavior, nominal_dimension = opening_identity(source, raw, face, face_width)
                behavior = behavior or str(opening.get("beam_behavior") or "")
                nominal_dimension = nominal_dimension or str(opening.get("beam_dimension") or "")
                interpreted_dimension = current_dimension(face, beam_name, slot) if beam_name else ""
                if interpreted_dimension:
                    nominal_dimension = interpreted_dimension
                    beam_width, beam_height = (
                        float(part.replace(",", ".")) for part in interpreted_dimension.split("/")
                    )
                    interpreted_height = beam_height + 4
                    raw_height = float(raw.get("altura") or 0)
                    # A ficha humana pode ter ajustado a abertura; so sincronizar
                    # a geometria que ainda corresponde ao contrato gerado.
                    if abs(float(opening.get("depth") or 0) - raw_height) < 0.2:
                        opening["depth"] = interpreted_height
                    raw_width = float(raw.get("largura") or 0)
                    if abs(float(opening.get("width") or 0) - raw_width) < 0.2:
                        if behavior == "viga_chega":
                            opening["width"] = beam_width + (8 if len(slot) == 2 and slot[0] == slot[1] else 15)
                        elif behavior in {"viga_passa", "viga_interna"}:
                            opening["width"] = face_width + (22 if face in {"A", "B"} else 0)
                if beam_name:
                    opening["beam_name"] = beam_name
                if nominal_dimension:
                    opening["beam_dimension"] = nominal_dimension
                if behavior:
                    opening["beam_behavior"] = behavior
                opening["n3_kind"] = "passing_beam" if behavior in {"viga_passa", "viga_interna"} else "opening"
                if opening.get("element_level") is None or opening.get("level_source") in {
                    "n3_geometry", "abcd_sa", "abcd_manual", "abcd_inferred",
                    "pillar_fallback",
                }:
                    matched = beam_level(face, beam_name, slot) if beam_name else None
                    level = matched[0] if matched else raw.get("_nivel_origem")
                    if matched:
                        level_source = ("abcd_manual" if matched[1] == "human" else
                                        "abcd_sa" if matched[1] == "sa" else "abcd_inferred")
                    else:
                        level_source = "sa" if level is not None else None
                    if level is None and beam_name:
                        # y_rel e' posicao do recorte no N3, nao cota SA da viga.
                        # Recupera somente nivel inequivoco do mesmo vinculo/viga.
                        related = [item for item in all_beam_openings
                                   if str(item.get("_viga") or item.get("viga") or "") == beam_name
                                   and item.get("_nivel_origem") is not None]
                        same_slot = [item for item in related
                                     if item.get("_origem") == slot]
                        candidates = same_slot or related
                        levels = {round(float(item["_nivel_origem"]), 2) for item in candidates}
                        if len(levels) == 1:
                            level = levels.pop()
                            level_source = "sa_related"
                    if level is None and opening.get("element_level") is not None:
                        level = opening["element_level"]
                        level_source = str(opening.get("level_source") or "abcd_inferred")
                    if level is None and pillar_top is not None:
                        level = pillar_top
                        level_source = "pillar_fallback"
                    if level is not None:
                        opening["element_level"] = round(float(level), 4)
                        opening["level_source"] = level_source
                    else:
                        opening.pop("element_level", None)
                        opening.pop("level_source", None)
                        opening.pop("top_distance", None)
                if pillar_top is not None and opening.get("element_level") is not None:
                    opening["top_distance"] = round(
                        (float(pillar_top) - float(opening["element_level"])) * 100, 2
                    )
                opening.pop("geometry_level_gap_cm", None)
                if (pillar_top is not None and pillar_bottom is not None
                        and opening.get("element_level") is not None and raw.get("y_rel") is not None
                        and not raw.get("origem_portal")
                        and not (behavior in {"viga_passa", "viga_interna"}
                                 and float(face_data.get("top_void_cm") or 0) >= float(opening.get("depth") or 0) - 0.2
                                 and abs(float(opening.get("top_distance") or 0)) <= 0.2)):
                    # y_rel mede a base do recorte acima da cinta h1; a cota
                    # absoluta mede o topo. Comparar ambos diretamente gera
                    # falsos desvios iguais ao pé-direito inteiro.
                    face_height = float((ficha.get("dimensions") or {}).get("height") or 0)
                    h1 = min((float(panel.get("height") or 0) for panel in face_data.get("panels") or []
                              if int(panel.get("row") or 0) == 1), default=0.0)
                    expected_y_rel = (face_height - float(opening["top_distance"])
                                      - float(opening.get("depth") or 0) - h1)
                    gap = round(expected_y_rel - float(raw["y_rel"]), 2)
                    if abs(gap) > 1:
                        opening["geometry_level_gap_cm"] = gap
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
        slab_name, slab_dimension = evidence_identity(lajes[0], "Laje")
        interpreted_thickness = current_slab_thickness(face, slab_name)
        if interpreted_thickness is not None:
            old_void = void
            thickness = interpreted_thickness
            void = thickness + 2.0
            face_data["slab"]["thickness"] = thickness
            face_data["slab"]["void"] = void
            slab_dimension = f"{thickness:g}"
        else:
            old_void = void
        slab_level = face_data["slab"]["level"]
        slab_top_distance = round((float(pillar_top) - slab_level) * 100, 2) if pillar_top is not None and slab_level else face_data["slab"]["recess"]
        if "slabs" not in face_data:
            panels = face_data.get("panels") or []
            columns = {panel["column"]: max(
                (item["distance"] + item["width"] for item in panels
                 if item["column"] == panel["column"]), default=0,
            ) for panel in panels}
            total_width = sum(columns.values()) + face_data["n3_width_extra"]
            left = max((opening["distance"] + opening["width"]
                        for opening in face_data.get("openings", {}).get("left", [])), default=0)
            right = max((opening["distance"] + opening["width"]
                         for opening in face_data.get("openings", {}).get("right", [])), default=0)
            face_data["slabs"] = [{
                "left_distance": left, "right_distance": right,
                "level": slab_level or None, "top_distance": slab_top_distance,
                "width": max(0.0, total_width - left - right), "height": void,
            }]
        else:
            for index, slab in enumerate(face_data["slabs"]):
                if slab.get("level") is None and pillar_top is not None:
                    if index == 0 and slab_level and slab["top_distance"] == face_data["slab"]["recess"]:
                        slab["level"] = slab_level
                    else:
                        slab["level"] = round(float(pillar_top) - slab["top_distance"] / 100, 4)
                if pillar_top is not None and slab.get("level") is not None:
                    slab["top_distance"] = round((float(pillar_top) - slab["level"]) * 100, 2)
        for slab in face_data.get("slabs") or []:
            if interpreted_thickness is not None and abs(float(slab.get("height") or 0) - old_void) < 0.2:
                slab["height"] = void
            slab["slab_name"] = slab_name
            slab["slab_dimension"] = slab_dimension or f"{thickness:g}cm"
            slab["slab_behavior"] = "laje"
    if pillar_top is not None:
        for face_data in (ficha.get("faces") or {}).values():
            for slab in face_data.get("slabs") or []:
                if slab.get("level") is None:
                    slab["level"] = round(float(pillar_top) - slab["top_distance"] / 100, 4)
                slab["top_distance"] = round((float(pillar_top) - slab["level"]) * 100, 2)


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

    dimensions = ficha["dimensions"]
    length, width = number(dimensions["length"]), number(dimensions["width"])
    scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from gerar_pl_dxf_stog import cima_layout_contract

    layout = cima_layout_contract(robot, length)
    grades = layout["widths"]
    gaps = layout["gaps"]
    external = layout["total_width"]
    div_a = layout["divisions_a"]
    div_b = layout["divisions_b"]
    screw_spacings = [number(robot.get(f"par_{index}_{index + 1}")) for index in range(1, 8)]
    offsets, cursor = [], -1.0
    for spacing in screw_spacings:
        if spacing <= 0:
            break
        cursor += spacing
        if cursor >= external - 1.0:
            break
        offsets.append(cursor)
    spans = [end - start for start, end in zip([0.0, *offsets], [*offsets, external])]
    grade_fields = {
        "grade_1": grades[0] if grades else None,
        "distancia_1": gaps[0] if len(grades) > 1 else None,
        "grade_2": grades[1] if len(grades) > 1 else None,
        "distancia_2": gaps[1] if len(grades) > 2 else None,
        "grade_3": grades[2] if len(grades) > 2 else None,
    }
    padded_a = [(values + [None] * 5)[:5] for values in div_a]
    padded_b = [(values + [None] * 5)[:5] for values in div_b]
    return {"rows": [
        ["comprimento interno", f"{fmt(length)} cm"],
        ["largura interna", f"{fmt(width)} cm"],
        ["comprimento +22", f"{fmt(length)} + 22 = {fmt(external)} cm"],
        ["parafusos", f"offsets: {label(offsets)} cm"],
        ["cotas parafusos", f"{label(spans)} cm"],
        ["layout grades", f"{len(grades)} grade(s): {' + '.join(fmt(value) for value in grades)} cm; gaps {label(gaps)}"],
        ["quadradinhos A", " ; ".join(f"G{index + 1}: {label(values)}" for index, values in enumerate(div_a))],
        ["quadradinhos B", " ; ".join(f"G{index + 1}: {label(values)}" for index, values in enumerate(div_b))],
    ], "fields": {
        "classificacao_pilar": "retangular",
        "comprimento_interno": length,
        "largura_interna": width,
        "comprimento_externo": external,
        "parafuso_inicio": -1.0,
        "parafuso_final": 1.0,
        "parafusos": screw_spacings,
        "grade_count": len(grades),
        "grades": grade_fields,
        "quadradinhos_a": padded_a,
        "quadradinhos_b": padded_b,
        "quadradinhos": padded_a,
    }}


def _grades_detail_contract(robot: dict, visual_mode: str) -> dict:
    """Mede as grades pela mesma geometria usada no DXF N3, sem inventar sarrafos."""
    scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from gerar_pl_dxf_stog import (
        _grade_divisions, _grade_layout_from_inner, _grade_vertical_height,
        _grade_layout_for_panel_width, _integer_segments_with_avoidance,
    )
    from pl_grade_visual_config import positions_for_mode
    from src.core.cima_l_contract import n3_faces_l, split_panel_grades

    inner_width = float(robot.get("comprimento") or 0)
    thickness = float(robot.get("largura") or 0)
    height = float(robot.get("altura") or 0)
    faces = {}
    specs = []
    l_faces = n3_faces_l(robot)
    if l_faces:
        for face_data in l_faces:
            panel_width = float(face_data["panel"])
            if panel_width <= 0:
                continue
            widths, gaps = split_panel_grades(panel_width)
            grade_width = float(widths[0]) if widths else panel_width
            divisions = (_grade_divisions(robot, panel_width, len(widths), grade_width, gaps)
                         if face_data["id"] in {"A", "B"} else
                         [_integer_segments_with_avoidance(grade_width, []) for _ in widths])
            specs.append((face_data["id"], panel_width, widths, gaps, divisions))
    else:
        count, grade_width, gaps = _grade_layout_from_inner(inner_width)
        widths = [grade_width] * count
        divisions = _grade_divisions(robot, inner_width + 22, count, grade_width, gaps)
        specs.extend((face, inner_width + 22, widths, gaps, divisions) for face in ("A", "B"))
        if thickness >= 50:
            count, grade_width, gaps = _grade_layout_for_panel_width(thickness)
            widths = [grade_width] * count
            divisions = [_integer_segments_with_avoidance(grade_width, []) for _ in widths]
            specs.extend((face, thickness, widths, gaps, divisions) for face in ("C", "D"))
    for face, panel_width, widths, gaps, divisions in specs:
        grade_rows = []
        start = 0.0
        for index, width in enumerate(widths):
            width = float(width)
            cells = list(divisions[index])
            if face == "B":
                cells.reverse()  # draw_grades espelha o lado B.
            member_positions = [start + (3.5 if index == 0 else 1.75)]
            cursor = start
            for cell in cells[:-1]:
                cursor += float(cell)
                member_positions.append(cursor)
            member_positions.append(start + width - (3.5 if index == len(widths) - 1 else 1.75))
            member_heights = [
                _grade_vertical_height(robot, face, x, panel_width, height)
                for x in member_positions
            ]
            useful_height = min((value for value in member_heights if value > 0), default=0.0)
            row_heights = []
            cursor_y = 0.0
            for position in positions_for_mode(visual_mode):
                if position + 10 > useful_height + 0.1:
                    continue
                row_heights.append(round(max(0.0, position - cursor_y), 2))
                cursor_y = position + 10
            if useful_height > cursor_y:
                row_heights.append(round(useful_height - cursor_y, 2))
            cell_heights = []
            for left_member, right_member in zip(member_heights[:-1], member_heights[1:]):
                cell_top = min(left_member, right_member)
                column_heights = list(row_heights)
                if column_heights and cell_top > useful_height:
                    column_heights[-1] = round(column_heights[-1] + cell_top - useful_height, 2)
                cell_heights.append(column_heights)
            grade_rows.append({
                "width": width, "quadradinhos": [round(float(value), 2) for value in cells],
                "alturas_quadradinhos": row_heights,
                "alturas_por_coluna": cell_heights,
                "alturas_montantes": member_heights,
            })
            start += width + (float(gaps[index]) if index < len(gaps) else 0.0)
        faces[face] = {"width": float(panel_width), "grades": grade_rows,
                       "distancias": [float(value) for value in gaps]}
    return {"faces": faces, "visual_mode": visual_mode}


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
    from src.core.pillar_sa_review import load
    manual = load(obra_dir, pavimento, item_id)
    return {
        "classificacao": top_view.get("classification") or "—",
        "orientacao": top_view.get("orientation") or "—",
        "nivel_chegada": manual.get("nivel_chegada", niveis.get("nivel_chegada_abs", dimensions.get("nivel_chegada"))),
        "nivel_saida": manual.get("nivel_saida", niveis.get("nivel_saida_abs", dimensions.get("nivel_saida"))),
        "pe_direito": manual.get("pe_direito", niveis.get("pd_pavimento_cm", dimensions.get("height"))),
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
    visual_mode: Optional[Literal["NOVA", "INI"]] = None,
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
    _exigir_pilar_n3(estado, base_id)
    pilar = _pilar_raw(estado, base_id)
    if pilar is None:
        raise HTTPException(status_code=404, detail="pilar nao encontrado no N1")
    modo = _n3_modo(vista)
    from src.core.pillar_sa_review import load, apply_robot
    robot = apply_robot(_robot_pilar(obra_dir, base_id, modo), load(obra_dir, pav, base_id))
    saved_root = pillar_n3_ficha.load_ficha(obra_dir, pav, base_id)
    saved = _override_da_variante(saved_root, modo)
    ficha = pillar_n3_ficha.build_ficha(
        pilar, robot, saved, pavimento=pav,
    )
    abcd = None
    if pilar.get("interpretacao_abcd"):
        abcd = pillar_level_view.enrich_pillar_abcd_levels(
            pilar["interpretacao_abcd"], estado, robot.get("nivel_chegada_abs"),
            pillar_level_view.load_preprocess_slab_levels(obra_dir, pav),
            pillar_name=base_id,
            beam_dim_texts=pillar_level_view.load_beam_dimension_texts(estado),
        )
        abcd = pillar_abcd_review.apply_review(abcd, obra_dir, pav, base_id)
    _anexar_lajes_n3(ficha, robot, abcd)
    cima_canonica = pillar_n3_ficha.build_ficha(
        pilar, robot, None, pavimento=pav,
    )
    visualizacoes_n3 = {}
    resolved_visual_mode = ficha_reader.modo_visual_n3(
        obra_dir, pav, classe, {"beam_name": base_id}, vista or "cima", visual_mode,
    )
    if vista:
        svg = ficha_reader.resolver_visualizacao_n3_pilar(
            obra_dir, {"beam_name": base_id, "pavimento": pav}, vista,
            resolved_visual_mode,
        )
        visualizacoes_n3[vista] = svg
    saved_cima = saved.get("cima_contract") if isinstance(saved, dict) else None
    if is_cima_l(robot):
        # Reconstroi a apresentacao pelo contrato L atual, mas reaplica antes
        # qualquer override humano salvo. Isso permite evoluir a ficha (por
        # exemplo, nomes A/B/E/F) sem descartar as medidas editadas.
        robot_cima = {**robot, **pillar_n3_ficha.robot_patch(ficha)}
        cima_contract = portal_cima_l_contract(robot_cima)
    elif isinstance(saved_cima, dict) and isinstance(saved_cima.get("rows"), list):
        cima_contract = saved_cima
    else:
        cima_contract = _cima_contract(cima_canonica, robot)
    grades_detail = None
    if vista and vista.startswith("grades"):
        grade_ficha = {**ficha, "cima_contract": cima_contract}
        grade_robot = {**robot, **pillar_n3_ficha.robot_patch(grade_ficha)}
        grades_detail = _grades_detail_contract(grade_robot, resolved_visual_mode)
    return {"obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": base_id,
            "ficha": ficha, "visualizacoes_n3": visualizacoes_n3,
            "visual_mode": resolved_visual_mode,
            "available_visual_modes": ficha_reader.modos_visuais_n3_disponiveis(
                obra_dir, pav, classe, {"beam_name": base_id}, vista or "cima",
            ),
            "cima_contract": cima_contract,
            "grades_detail": grades_detail,
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
    _exigir_pilar_n3(estado, base_id)
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


@router.post("/{obra_id}/n1/{classe}/{item_id}/pilar-n3-{vista}/regenerar")
def regenerar_n3_cima_pilar_endpoint(
    obra_id: str, classe: str, item_id: str, vista: str, request: Request,
    payload: DrawingModePayload | None = None,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Enfileira a regeneração de uma vista N3 do pilar solicitado."""
    if classe not in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        raise HTTPException(status_code=400, detail="regeneracao N3 disponivel somente para pilares")
    if vista not in {"cima", "abcd-para", "abcd-passa", "grades-para", "grades-passa"}:
        raise HTTPException(status_code=422, detail="vista N3 invalida")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    base_id = item_id.removesuffix("_Para").removesuffix("_Passa")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    if not pav or not estado or _pilar_raw(estado, base_id) is None:
        raise HTTPException(status_code=404, detail="pilar nao encontrado")
    _exigir_pilar_n3(estado, base_id)
    settings = request.app.state.settings
    try:
        visual_mode = normalize_visual_mode(payload.visual_mode if payload else "NOVA")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    meta = {
        "etapa": "n3_cima_item" if vista == "cima" else "n3_pilar_vista_item",
        "secao": "pilares", "item": base_id,
        "pav": pav, "requested_view": vista, "visual_mode": visual_mode,
    }
    job_id, criado = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta,
        chaves=("etapa", "secao", "item", "pav", "requested_view") if vista != "cima" else ("etapa", "secao", "item", "pav"),
        engine_version=pipeline_runner.engine_version(settings.repo_root),
    )
    request.app.state.job_meta[job_id] = meta
    return {
        "status": "queued" if criado else "already_active",
        "job_id": job_id, "item": base_id, "created": criado,
    }


@router.get("/{obra_id}/n1/{classe}/{item_id}/pilar-n3-{vista}/regenerar/status")
def status_regeneracao_n3_cima_pilar_endpoint(
    obra_id: str, classe: str, item_id: str, vista: str, request: Request,
    pavimento: Optional[str] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Restaura o monitor do último microciclo do pilar após recarregar."""
    if classe not in {"pilares", "pilares_especiais", "pilares_n3_para", "pilares_n3_passa"}:
        raise HTTPException(status_code=400, detail="regeneracao N3 disponivel somente para pilares")
    if vista not in {"cima", "abcd-para", "abcd-passa", "grades-para", "grades-passa"}:
        raise HTTPException(status_code=422, detail="vista N3 invalida")
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="pavimento nao encontrado")
    alvo = item_id.removesuffix("_Para").removesuffix("_Passa").strip().upper()
    for job in repo.listar_jobs_por_obra(conn, obra_id):
        meta = request.app.state.job_meta.get(job["id"]) or repo.obter_job_meta(conn, job["id"])
        if (
            meta.get("etapa") in {"n3_cima_item", "n3_pilar_vista_item", "sa_item"}
            and meta.get("secao") == "pilares"
            and str(meta.get("item") or "").strip().upper() == alvo
            and meta.get("pav") == pav
            and (meta.get("requested_view") == vista or (vista == "cima" and meta.get("etapa") == "sa_item"))
        ):
            return {
                "job_id": job["id"],
                "active": job["status"] in {"na_fila", "executando"} or (
                    job["status"] == "cancelado" and job.get("erro_msg") == repo.PAUSA_OPERADOR
                ),
            }
    return {"job_id": None, "active": False}


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
