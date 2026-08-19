"""Rotas de fichas HTML: serve os HTML N1-N4 ja gerados pelo pipeline (HANDOFF §1.1).

O portal SO LE estes artefatos (regra de fronteira §3) — nunca escreve neles.

[FIX 2026-07-06] achado rodando o SA de verdade pela 1a vez contra uma obra
nova do portal: as fichas ficam em <obra_dir>/<pavimento>_<run_id>/ (timestamp
por rodada), NAO em <obra_dir>/Fase-6_Execucao_CAD/ (esse path fixo era
suposicao — nenhuma obra do portal tinha chegado ate' aqui pra revelar isso
antes). Resolvido via pipeline_runner.encontrar_dir_fichas (pega a rodada mais
recente, identificada pelo arete_manifest.json). O portal lista e serve o HTML
como estatico, com protecao de path traversal (nunca sai do diretorio da obra).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .. import access, auth, pipeline_runner
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["fichas"])


def _dir_fichas(request: Request, obra: dict) -> Optional[Path]:
    settings = request.app.state.settings
    lp = obra.get("local_path")
    obra_dir = Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")
    pavimento = request.query_params.get("pavimento")
    return pipeline_runner.encontrar_dir_fichas(obra_dir, pavimento)


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


@router.get("/{obra_id}/fichas")
def listar_fichas(obra_id: str, request: Request, membro: dict = Depends(auth.exige_login),
                  conn: sqlite3.Connection = Depends(get_db_conn)):
    """Lista os HTML de ficha disponiveis para a obra (viewer basico)."""
    obra = _obra_do_membro(conn, obra_id, membro)
    base = _dir_fichas(request, obra)
    fichas = []
    if base is not None:
        for p in sorted(base.rglob("*.html")):
            fichas.append({
                "nome": p.name,
                "rel": str(p.relative_to(base)).replace("\\", "/"),
                "tamanho": p.stat().st_size,
            })
    return {"obra_id": obra_id, "total": len(fichas), "fichas": fichas}


@router.get("/{obra_id}/fichas/{rel_path:path}")
def servir_ficha(obra_id: str, rel_path: str, request: Request,
                 membro: dict = Depends(auth.exige_login),
                 conn: sqlite3.Connection = Depends(get_db_conn)):
    """Serve um HTML de ficha especifico (com guarda contra path traversal)."""
    obra = _obra_do_membro(conn, obra_id, membro)
    base_dir = _dir_fichas(request, obra)
    if base_dir is None:
        raise HTTPException(status_code=404, detail="nenhuma ficha gerada ainda para esta obra")
    base = base_dir.resolve()
    alvo = (base / rel_path).resolve()
    # guarda: alvo tem que estar DENTRO de base (nunca sobe com ../)
    if base not in alvo.parents and alvo != base:
        raise HTTPException(status_code=403, detail="path fora da obra")
    if not alvo.exists() or not alvo.is_file():
        raise HTTPException(status_code=404, detail="ficha nao encontrada")
    if alvo.suffix.lower() not in (".html", ".htm", ".svg", ".css", ".js", ".png", ".json"):
        raise HTTPException(status_code=415, detail="tipo de arquivo nao servivel")
    return FileResponse(str(alvo))
