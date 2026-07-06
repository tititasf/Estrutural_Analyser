"""Rotas de fichas HTML: serve os HTML N1-N4 ja gerados pelo pipeline (HANDOFF §1.1).

O portal SO LE estes artefatos (regra de fronteira §3) — nunca escreve neles. As
fichas ficam em <obra_dir>/Fase-6_Execucao_CAD/. O portal lista e serve o HTML como
estatico, com protecao de path traversal (nunca sai do diretorio da obra).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .. import access, auth
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["fichas"])


def _obra_dir(request: Request, obra: dict) -> Path:
    settings = request.app.state.settings
    lp = obra.get("local_path")
    return Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")


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
    base = _obra_dir(request, obra) / "Fase-6_Execucao_CAD"
    fichas = []
    if base.exists():
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
    base = (_obra_dir(request, obra) / "Fase-6_Execucao_CAD").resolve()
    alvo = (base / rel_path).resolve()
    # guarda: alvo tem que estar DENTRO de base (nunca sobe com ../)
    if base not in alvo.parents and alvo != base:
        raise HTTPException(status_code=403, detail="path fora da obra")
    if not alvo.exists() or not alvo.is_file():
        raise HTTPException(status_code=404, detail="ficha nao encontrada")
    if alvo.suffix.lower() not in (".html", ".htm", ".svg", ".css", ".js", ".png", ".json"):
        raise HTTPException(status_code=415, detail="tipo de arquivo nao servivel")
    return FileResponse(str(alvo))
