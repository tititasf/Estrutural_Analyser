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
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import access, auth, certification, n5_release, pipeline_runner, viewer_pavimentos
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["etapas"])


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _enfileirar(request: Request, conn: sqlite3.Connection, obra: dict, meta: dict) -> str:
    ev = pipeline_runner.engine_version(request.app.state.settings.repo_root)
    job_id = repo.enfileirar_job(conn, obra_id=obra["id"], engine_version=ev)
    request.app.state.job_meta[job_id] = meta
    repo.atualizar_estado_obra(conn, obra["id"], "processando")
    return job_id


def _pavimentos_processaveis(request: Request, obra: dict) -> list[str]:
    """Pavimentos reais com torre limpa, na mesma ordem exibida no portal."""
    settings = request.app.state.settings
    local_path = obra.get("local_path")
    obra_dir = Path(local_path) if local_path else settings.dados_obras_dir / obra["nome"]
    return [
        item["pavimento"]
        for item in viewer_pavimentos.listar_pavimentos_com_torre(obra_dir, obra)
    ]


def _enfileirar_todos_pavimentos(
    request: Request,
    conn: sqlite3.Connection,
    obra: dict,
    *,
    etapa: str,
    secao: Optional[list[str]],
) -> tuple[str, list[dict]]:
    """Cria um lote visivel ao usuario; o JobWorker o executa serialmente."""
    pavimentos = _pavimentos_processaveis(request, obra)
    if not pavimentos:
        raise HTTPException(status_code=422, detail="nenhum pavimento com torre limpa encontrado")
    batch_id = uuid.uuid4().hex
    jobs = []
    for pavimento in pavimentos:
        meta = {
            "etapa": etapa,
            "secao": secao,
            "pav": pavimento,
            "escopo": "global",
            "batch_id": batch_id,
        }
        job_id = _enfileirar(request, conn, obra, meta)
        jobs.append({"job_id": job_id, "pav": pavimento, "meta": meta})
    return batch_id, jobs


class SAIn(BaseModel):
    secao: Optional[list[str]] = None
    pav: Optional[str] = None

class N3In(BaseModel):
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
# Conversão avulsa DWG->DXF (2026-07-08, a pedido do dono) — separada da
# Triagem: lista os .dwg da obra com status "possui DXF" (checado em disco,
# convenção <stem>.dxf na mesma pasta entrada/) e converte todos de uma vez
# só os que ainda não têm par, reusando o MESMO conversor da ingestão.
# --------------------------------------------------------------------------- #

@router.get("/obras/{obra_id}/documentos/dwgs")
def listar_dwgs(obra_id: str, request: Request, membro: dict = Depends(auth.exige_login),
                conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    documentos = repo.listar_documentos_por_obra(conn, obra_id)
    dwgs = pipeline_runner.listar_dwgs_com_status(request.app.state.settings, obra, documentos)
    return {"obra_id": obra_id, "dwgs": dwgs}


@router.post("/obras/{obra_id}/documentos/converter-dwg")
def converter_dwg(obra_id: str, request: Request, membro: dict = Depends(auth.exige_login),
                   conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    job_id = _enfileirar(request, conn, obra, {"etapa": "converter_dwg"})
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "converter_dwg", "estado": "queued"}


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


@router.post("/obras/{obra_id}/sa-todos")
def sa_todos(obra_id: str, body: SAIn, request: Request,
             membro: dict = Depends(auth.exige_login),
             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    batch_id, jobs = _enfileirar_todos_pavimentos(
        request, conn, obra, etapa="sa", secao=body.secao,
    )
    return {"batch_id": batch_id, "obra_id": obra_id, "etapa": "sa",
            "estado": "queued", "total": len(jobs), "jobs": jobs}


@router.post("/obras/{obra_id}/n3")
def n3(obra_id: str, body: N3In, request: Request, membro: dict = Depends(auth.exige_login),
       conn: sqlite3.Connection = Depends(get_db_conn)):
    import sqlite3 # just to be safe
    obra = _obra_do_membro(conn, obra_id, membro)
    meta = {"etapa": "n3", "secao": body.secao, "pav": body.pav}
    job_id = _enfileirar(request, conn, obra, meta)
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "n3",
            "estado": "queued", "secao": body.secao}


@router.post("/obras/{obra_id}/n3-todos")
def n3_todos(obra_id: str, body: N3In, request: Request,
             membro: dict = Depends(auth.exige_login),
             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    batch_id, jobs = _enfileirar_todos_pavimentos(
        request, conn, obra, etapa="n3", secao=body.secao,
    )
    return {"batch_id": batch_id, "obra_id": obra_id, "etapa": "n3",
            "estado": "queued", "total": len(jobs), "jobs": jobs}

# --------------------------------------------------------------------------- #
# Etapa 5 — Validacao (so estado; nao recomputa)
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/validacao")
def validacao(obra_id: str, body: ValidacaoIn, request: Request,
              membro: dict = Depends(auth.exige_login),
              conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-10, Masterplan OBRAS DRIVE Fase 3] Persistida em
    `portal_validacoes` (era só memória do processo — perdia tudo a cada
    restart). Merge protetivo: nunca rebaixa n1_ok/n3_ok já True (harmonia
    com a validação que a app desktop também vai poder empurrar aqui)."""
    obra = _obra_do_membro(conn, obra_id, membro)
    resultado = repo.set_validacao_classe(
        conn, obra_id, body.classe, body.n1_ok, body.n3_ok, body.item_id, membro["login"]
    )
    return {"obra_id": obra_id, "classe": resultado["classe"],
            "validado": resultado["validado"], "libera_n5": resultado["validado"]}


@router.get("/obras/{obra_id}/validacao")
def listar_validacoes_endpoint(obra_id: str, membro: dict = Depends(auth.exige_login),
                                conn: sqlite3.Connection = Depends(get_db_conn)):
    """{classe: {n1_ok, n3_ok, validado}} de todas as classes já tocadas —
    a app desktop usa isso pra espelhar em lote (1 GET, não 1 por classe)."""
    _obra_do_membro(conn, obra_id, membro)
    return {"obra_id": obra_id, "validacoes": repo.listar_validacoes_por_obra(conn, obra_id)}


@router.get("/obras/{obra_id}/validacao/{classe}")
def obter_validacao_endpoint(obra_id: str, classe: str, membro: dict = Depends(auth.exige_login),
                              conn: sqlite3.Connection = Depends(get_db_conn)):
    _obra_do_membro(conn, obra_id, membro)
    return repo.obter_validacao_classe(conn, obra_id, classe)


# --------------------------------------------------------------------------- #
# Etapa 6 — N5 (gated por validacao + rotulo)
# --------------------------------------------------------------------------- #

@router.post("/obras/{obra_id}/n5")
def n5(obra_id: str, body: N5In, request: Request, membro: dict = Depends(auth.exige_login),
       conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    classe = body.classe.upper()

    # gating DP-13/R9: exige validacao do usuario para a classe (agora
    # persistida em portal_validacoes — sobrevive a restart do servidor)
    validado = repo.obter_validacao_classe(conn, obra_id, classe)["validado"]
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


@router.get("/obras/{obra_id}/n5/download")
def n5_download_all(obra_id: str, request: Request, membro: dict = Depends(auth.exige_login),
                    conn: sqlite3.Connection = Depends(get_db_conn)):
    # Mocking global zip download
    from fastapi.responses import Response
    import sqlite3
    _ = _obra_do_membro(conn, obra_id, membro) # valida
    return Response(content=b"Mock ZIP content for all N5", media_type="application/zip", headers={"Content-Disposition": "attachment; filename=n5_all.zip"})

@router.get("/obras/{obra_id}/n5/{classe}/foto")
def n5_foto(obra_id: str, classe: str, request: Request,
            membro: dict = Depends(auth.exige_login),
            conn: sqlite3.Connection = Depends(get_db_conn)):
    """Foto (SVG) do DXF final do N5 mais recente dessa classe — [2026-07-06]
    N5 so' tinha download de DXF, sem preview visual nenhum; aqui usa o mesmo
    `dxf_preview` (ezdxf.addons.drawing) ja usado pelo viewer de Recortes.

    [2026-07-30] O docstring dizia PNG desde a migracao para SVG. Portal web
    entrega SVG por politica canonica (`docs/QA-VISAO-EVIDENCIA-CANONICA.md`:
    agente le PNG; persist/app/portal web = SVG)."""
    from fastapi.responses import Response as _Response
    from pathlib import Path as _P

    from .. import dxf_preview

    obra = _obra_do_membro(conn, obra_id, membro)
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    alvo = next((r for r in releases if r["classe"] == classe.upper() and r.get("dxf_path")), None)
    if alvo is None:
        raise HTTPException(status_code=404, detail="nenhum N5 liberado para esta classe")
    dxf_path = _P(alvo["dxf_path"])
    if not dxf_path.exists():
        raise HTTPException(status_code=410, detail="DXF do N5 nao esta mais disponivel")

    settings = request.app.state.settings
    lp = obra.get("local_path")
    obra_dir = _P(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")
    cache_dir = obra_dir / ".previews"
    try:
        svg = dxf_preview.renderizar_dxf_svg_cacheado(dxf_path, cache_dir)
    except Exception as exc:  # noqa: BLE001 - DXF pode ter geometria que o renderer nao suporta
        raise HTTPException(status_code=502, detail=f"falha ao renderizar: {exc}") from exc
    return _Response(content=svg, media_type="image/svg+xml")


# --------------------------------------------------------------------------- #
# GET /obras/{id}/jobs — lista todos os jobs de uma obra (polling UI)
# --------------------------------------------------------------------------- #

@router.get("/obras/{obra_id}/jobs")
def listar_jobs_obra(obra_id: str, request: Request,
                     membro: dict = Depends(auth.exige_login),
                     conn: sqlite3.Connection = Depends(get_db_conn)):
    """Lista todos os jobs de uma obra para polling do frontend."""
    obra = _obra_do_membro(conn, obra_id, membro)
    rows = repo.listar_jobs_por_obra(conn, obra_id)
    mapa = {"na_fila": "na_fila", "executando": "executando",
            "concluido": "concluido", "falhou": "erro", "cancelado": "erro"}
    jobs = []
    for r in rows:
        meta = request.app.state.job_meta.get(r["id"], {})
        jobs.append({
            "id": r["id"],
            "status": mapa.get(r["status"], r["status"]),
            "meta": meta,
            "enfileirado_em": r.get("enfileirado_em"),
            "iniciado_em": r.get("iniciado_em"),
            "finalizado_em": r.get("finalizado_em"),
            "erro_msg": r.get("erro_msg"),
        })
    return {"jobs": jobs}


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
    if obra is None or not access.pode_ver_obra(obra, membro):
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
