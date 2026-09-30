"""Fila do inventário pré-SA por pavimento; sem acionar motores estruturais."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import access, auth
from ..dbdep import get_db_conn
from ..preprocessamento.sources import SourceKind, SourceResolutionError, inventory_floor_sources, raw_level_references
from ..preprocessamento.service import ENGINE_VERSION
from ...db import repository as repo


router = APIRouter(prefix="/obras", tags=["preprocessamento"])
_FLOOR = re.compile(r"^[A-Za-z0-9_.-]+$")
_KINDS = {SourceKind.TOWER, SourceKind.DETAILS, SourceKind.PILLAR_CONVENTION, SourceKind.LEVEL_CONVENTION}


class PreprocessRequest(BaseModel):
    pavimento: str


def _obra(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra não encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _sources_for_floor(request: Request, conn: sqlite3.Connection, obra: dict, pavimento: str):
    if not _FLOOR.fullmatch(pavimento) or ".." in pavimento:
        raise HTTPException(status_code=422, detail="pavimento inválido")
    settings = request.app.state.settings
    obra_dir = Path(obra["local_path"]) if obra.get("local_path") else settings.dados_obras_dir / obra["nome"]
    try:
        sources = tuple(source for source in inventory_floor_sources(
            obra_dir=obra_dir, obra_id=obra["id"], pavimento_id=pavimento,
            documents=repo.listar_documentos_por_obra(conn, obra["id"]),
        ) if source.kind in _KINDS)
    except (OSError, SourceResolutionError) as exc:
        raise HTTPException(status_code=409, detail=f"recortes indisponíveis: {exc}") from exc
    return sources


@router.post("/{obra_id}/preprocessamento/jobs", status_code=202)
def start_preprocess(
    obra_id: str, payload: PreprocessRequest, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra(conn, obra_id, membro)
    if not getattr(request.app.state.settings, "preprocess_enabled", False):
        raise HTTPException(status_code=409, detail="pré-processamento desabilitado")
    sources = _sources_for_floor(request, conn, obra, payload.pavimento)
    if not any(source.kind is SourceKind.TOWER for source in sources):
        raise HTTPException(status_code=409, detail="nenhuma torre recortada neste pavimento")
    pending = [source.item_id for source in sources
               if not source.validated and source.kind is not SourceKind.LEVEL_CONVENTION]
    if pending:
        raise HTTPException(status_code=409, detail="valide os recortes antes: " + ", ".join(pending))
    frozen = {source.source_id: source.revision for source in sources}
    frozen.update({source["source_id"]: source["revision"]
                   for source in raw_level_references(
                       Path(obra["local_path"]) if obra.get("local_path") else
                       request.app.state.settings.dados_obras_dir / obra["nome"], sources)})
    digest = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
    meta = {
        "etapa": "preprocessamento", "pav": payload.pavimento,
        "scope_hash": digest, "engine_version": ENGINE_VERSION,
        "sources": [{"bruto_id": source.bruto_id, "item_id": source.item_id} for source in sources],
        "frozen_sources": frozen,
    }
    job_id, created = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta,
        chaves=("etapa", "pav", "scope_hash", "engine_version"), engine_version=ENGINE_VERSION,
    )
    request.app.state.job_meta[job_id] = meta if created else repo.obter_job_meta(conn, job_id)
    return {"job_id": job_id, "created": created, "status": "queued" if created else "already_active",
            "tower_count": sum(source.kind is SourceKind.TOWER for source in sources),
            "source_count": len(sources)}


@router.get("/{obra_id}/preprocessamento")
def get_preprocess(
    obra_id: str, pavimento: str, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = _obra(conn, obra_id, membro)
    if not _FLOOR.fullmatch(pavimento) or ".." in pavimento:
        raise HTTPException(status_code=422, detail="pavimento inválido")
    for job in repo.listar_jobs_por_obra(conn, obra_id):
        meta = request.app.state.job_meta.get(job["id"]) or repo.obter_job_meta(conn, job["id"])
        if meta.get("etapa") == "preprocessamento" and meta.get("pav") == pavimento:
            result = meta.get("result")
            if result:
                from ..preprocessamento.service import read_floor
                from ..preprocessamento.freshness import changed_sources
                settings = request.app.state.settings
                root = Path(obra['local_path']) if obra.get('local_path') else settings.dados_obras_dir / obra['nome']
                try:
                    floor = read_floor(root, pavimento)
                    if floor and changed_sources(root, floor['sources']):
                        result = {**result, 'status': 'stale'}
                except (OSError, ValueError, RuntimeError):
                    result = {**result, 'status': 'unavailable'}
            return {"job_id": job["id"], "status": job["status"],
                    "result": result, "progress": meta.get("progress"),
                    "enabled": getattr(request.app.state.settings, 'preprocess_enabled', False),
                    "error": job.get("erro_msg")}
    return {"job_id": None, "status": "not_started", "result": None, "error": None,
            "enabled": getattr(request.app.state.settings, 'preprocess_enabled', False)}


@router.get("/{obra_id}/preprocessamento/niveis")
def get_level_inventory(
    obra_id: str, pavimento: str, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Listagem consultiva por torre; nenhum dado é escrito no SA."""
    obra = _obra(conn, obra_id, membro)
    if not _FLOOR.fullmatch(pavimento) or ".." in pavimento:
        raise HTTPException(status_code=422, detail="pavimento inválido")
    from ..preprocessamento.service import read_floor, read_tower
    from ..preprocessamento.freshness import changed_sources

    settings = request.app.state.settings
    root = Path(obra["local_path"]) if obra.get("local_path") else settings.dados_obras_dir / obra["nome"]
    try:
        floor = read_floor(root, pavimento)
        if floor is None:
            return {"status": "not_started", "pavimento": pavimento, "towers": []}
        stale = changed_sources(root, floor["sources"])
        towers = []
        for source_id, reference in floor["towers"].items():
            if reference["status"] == "failed":
                towers.append({"source_id": source_id, "status": "failed", "items": []})
                continue
            package = read_tower(root, floor, source_id)
            inventory = package.get("level_inventory") or {}
            facts: dict[str, list[dict]] = {}
            for fact in package.get("levels", []):
                facts.setdefault(fact["item_id"], []).append(fact)
            segments: dict[str, list[dict]] = {}
            for segment in inventory.get("beam_segments", []):
                segments.setdefault(segment["beam_item_id"], []).append(segment)
            towers.append({
                "source_id": source_id, "status": package["status"],
                "reference": inventory.get("reference"),
                "coverage": inventory.get("coverage"),
                "segment_coverage": inventory.get("segment_coverage"),
                "sa_evidence": inventory.get('sa_evidence'),
                "items": [{**item, "levels": facts.get(item["item_id"], []),
                           "segments": segments.get(item["item_id"], [])}
                          for item in inventory.get("items", [])],
            })
        return {"status": "stale" if stale else floor["status"],
                "pavimento": pavimento, "run_id": floor["run_id"],
                "changed_source_ids": stale, "towers": towers}
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=f"listagem indisponível: {exc}") from exc
