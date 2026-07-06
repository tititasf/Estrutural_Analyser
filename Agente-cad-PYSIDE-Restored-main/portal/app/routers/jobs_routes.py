"""Rotas das etapas 2-6 do fluxo enxuto (DP-14) + GET /jobs/{id} (HANDOFF §1.2).

Cada POST de etapa e' uma transicao de estado da obra que enfileira um job e retorna
imediatamente (a UI faz polling em GET /jobs/{id}). O tipo de etapa e' guardado em
app_state.job_meta[job_id] porque o schema real de portal_jobs nao tem coluna 'tipo'.

  2 triagem   POST /obras/{id}/triagem
  3 recortes  POST /obras/{id}/recortes
  4 sa        POST /obras/{id}/sa       (body: {secao?: [...]})
  5 validacao POST /obras/{id}/validacao (body: {classe, n1_ok, n3_ok, item_id?}) — so DB/estado
  6 n5        POST /obras/{id}/n5        (body: {classe, pavimento})  -> depois GET .../n5/{classe}/download

[ASSUMPTION] validacao NAO tem tabela no schema congelado. Guardo o "usuario validou
sua parte" em app_state.validacoes[obra_id][classe] (memoria do processo) — suficiente
para o gating do N5 no MVP (DP-13). Persistir a validacao vira migration futura; nao
invento tabela no DB de outra sessao.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import auth, certification, n5_release, pipeline_runner
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["etapas"])


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if obra["membro_id"] != membro["id"]:
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _enfileirar(request: Request, conn: sqlite3.Connection, obra: dict, meta: dict) -> str:
    ev = pipeline_runner.engine_version(request.app.state.settings.repo_root)
    job_id = repo.enfileirar_job(conn, obra_id=obra["id"], engine_version=ev)
    request.app.state.job_meta[job_id] = meta
    repo.atualizar_estado_obra(conn, obra["id"], "processando")
    return job_id


class SAIn(BaseModel):
    secao: Optional[list[str]] = None
    pav: Optional[str] = None


class ValidacaoIn(BaseModel):
    classe: str
    n1_ok: bool
    n3_ok: bool
    item_id: Optional[str] = None


class N5In(BaseModel):
    classe: str
    pavimento: str = "GERAL"


# --------------------------------------------------------------------------- #
# Etapa 2 — Triagem
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/triagem")
def triagem(obra_id: str, request: Request, membro: dict = Depends(auth.exige_login),
            conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    job_id = _enfileirar(request, conn, obra, {"etapa": "triagem"})
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "triagem", "estado": "queued"}


# --------------------------------------------------------------------------- #
# Etapa 3 — Recortes
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/recortes")
def recortes(obra_id: str, request: Request, membro: dict = Depends(auth.exige_login),
             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    job_id = _enfileirar(request, conn, obra, {"etapa": "recortes"})
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "recortes", "estado": "queued"}


# --------------------------------------------------------------------------- #
# Etapa 4 — SA completo
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/sa")
def sa(obra_id: str, body: SAIn, request: Request, membro: dict = Depends(auth.exige_login),
       conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    meta = {"etapa": "sa", "secao": body.secao, "pav": body.pav}
    job_id = _enfileirar(request, conn, obra, meta)
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "sa",
            "estado": "queued", "secao": body.secao}


# --------------------------------------------------------------------------- #
# Etapa 5 — Validacao (so estado; nao recomputa)
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/validacao")
def validacao(obra_id: str, body: ValidacaoIn, request: Request,
              membro: dict = Depends(auth.exige_login),
              conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    validado = bool(body.n1_ok and body.n3_ok)
    store = request.app.state.validacoes.setdefault(obra_id, {})
    store[body.classe.upper()] = {
        "n1_ok": body.n1_ok, "n3_ok": body.n3_ok,
        "validado": validado, "por": membro["login"], "item_id": body.item_id,
    }
    return {"obra_id": obra_id, "classe": body.classe.upper(),
            "validado": validado, "libera_n5": validado}


# --------------------------------------------------------------------------- #
# Etapa 6 — N5 (gated por validacao + rotulo)
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/n5")
def n5(obra_id: str, body: N5In, request: Request, membro: dict = Depends(auth.exige_login),
       conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    classe = body.classe.upper()

    # gating DP-13/R9: exige validacao do usuario para a classe
    validado = (
        request.app.state.validacoes.get(obra_id, {}).get(classe, {}).get("validado", False)
    )
    if not validado:
        raise HTTPException(
            status_code=409,
            detail=f"validacao (etapa 5) da classe {classe} nao registrada — "
                   "libere N5 apenas apos validar N1+N3.",
        )
    ev = pipeline_runner.engine_version(settings.repo_root)
    try:
        info = n5_release.liberar_n5(
            conn, settings, obra=obra, classe=classe, pavimento=body.pavimento,
            membro_id=membro["id"], engine_version=ev, dry_run=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return info


@router.get("/obras/{obra_id}/n5/{classe}/download")
def n5_download(obra_id: str, classe: str, request: Request,
                membro: dict = Depends(auth.exige_login),
                conn: sqlite3.Connection = Depends(get_db_conn)):
    from fastapi.responses import FileResponse

    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    alvo = next((r for r in releases if r["classe"] == classe.upper() and r.get("dxf_path")), None)
    if alvo is None:
        raise HTTPException(status_code=404, detail="nenhum N5 liberado para esta classe")
    from pathlib import Path as _P
    if not _P(alvo["dxf_path"]).exists():
        raise HTTPException(status_code=410, detail="DXF do N5 nao esta mais disponivel")
    rotulo = certification.classificar_certificacao(settings.status_md_path, classe.upper())
    return FileResponse(
        alvo["dxf_path"], filename=_P(alvo["dxf_path"]).name,
        media_type="application/dxf", headers={"X-Certificacao": rotulo},
    )


# --------------------------------------------------------------------------- #
# GET /jobs/{id} — polling uniforme (HANDOFF §1.3)
# --------------------------------------------------------------------------- #

@router.get("/jobs/{job_id}")
def obter_job(job_id: str, request: Request, membro: dict = Depends(auth.exige_login),
              conn: sqlite3.Connection = Depends(get_db_conn)):
    row = conn.execute("SELECT * FROM portal_jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job nao encontrado")
    job = dict(row)
    obra = repo.obter_obra(conn, job["obra_id"])
    if obra is None or obra["membro_id"] != membro["id"]:
        raise HTTPException(status_code=403, detail="job de outro membro")
    meta = request.app.state.job_meta.get(job_id, {})
    # mapa status DB -> estado do contrato (HANDOFF §1.3)
    mapa = {"na_fila": "queued", "executando": "running",
            "concluido": "done", "falhou": "error", "cancelado": "error"}
    return {
        "job_id": job["id"], "obra_id": job["obra_id"],
        "tipo": meta.get("etapa"), "estado": mapa.get(job["status"], job["status"]),
        "engine_version": job.get("engine_version"),
        "criado_em": job.get("enfileirado_em"), "iniciado_em": job.get("iniciado_em"),
        "finalizado_em": job.get("finalizado_em"),
        "log_tail": _ler_log_tail(job.get("log_path")),
        "erro_msg": job.get("erro_msg"),
    }


def _ler_log_tail(log_path: Optional[str], linhas: int = 40) -> str:
    if not log_path:
        return ""
    from pathlib import Path as _P
    p = _P(log_path)
    if not p.exists():
        return ""
    try:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-linhas:])
    except OSError:
        return ""
