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

from datetime import datetime, timezone
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


def _status_publico(job: dict) -> str:
    if job.get("status") == "cancelado" and job.get("erro_msg") == repo.PAUSA_OPERADOR:
        return "pausado"
    mapa = {"na_fila": "na_fila", "executando": "executando",
            "concluido": "concluido", "falhou": "erro", "cancelado": "cancelado"}
    return mapa.get(str(job.get("status")), str(job.get("status")))


def _job_controlavel(
    job_id: str, request: Request, membro: dict, conn: sqlite3.Connection,
) -> tuple[dict, dict]:
    row = conn.execute("SELECT * FROM portal_jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job nao encontrado")
    job = dict(row)
    obra = repo.obter_obra(conn, job["obra_id"])
    if obra is None or not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="job de outro membro")
    meta = request.app.state.job_meta.get(job_id) or repo.obter_job_meta(conn, job_id)
    return job, meta


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
    repo.salvar_job_meta(conn, job_id, meta)
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


class MotoresIn(BaseModel):
    pav: Optional[str] = None
    secao: Optional[list[str]] = None


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


@router.post("/obras/{obra_id}/motores")
def todos_motores(obra_id: str, body: MotoresIn, request: Request,
                   membro: dict = Depends(auth.exige_login),
                   conn: sqlite3.Connection = Depends(get_db_conn)):
    """SA -> N3 da mesma rodada -> N5 das classes previamente validadas."""
    obra = _obra_do_membro(conn, obra_id, membro)
    meta = {
        "etapa": "motores", "secao": body.secao, "pav": body.pav,
        "cascade_n5": True, "membro_id": membro["id"],
    }
    job_id = _enfileirar(request, conn, obra, meta)
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "motores",
            "estado": "queued", "meta": meta}

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

    if classe == "ALL":
        releases = []
        blocked = []
        ev = pipeline_runner.engine_version(settings.repo_root)
        for class_code in ("PL", "LV", "FV", "LAJ"):
            if not repo.obter_validacao_classe(conn, obra_id, class_code)["validado"]:
                blocked.append(class_code)
                continue
            try:
                releases.append(n5_release.liberar_n5(
                    conn, settings, obra=obra, classe=class_code,
                    pavimento=body.pavimento, membro_id=membro["id"],
                    engine_version=ev, dry_run=False,
                ))
            except ValueError as exc:
                blocked.append(f"{class_code}: {exc}")
        if not releases:
            raise HTTPException(
                status_code=409,
                detail="nenhuma classe possui validação N1+N3; N5 não foi gerado",
            )
        return {"ok": True, "pavimento": body.pavimento,
                "releases": releases, "bloqueadas": blocked}

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
    jobs = []
    for r in rows:
        meta = request.app.state.job_meta.get(r["id"]) or repo.obter_job_meta(conn, r["id"])
        jobs.append({
            "id": r["id"],
            "status": _status_publico(r),
            "meta": meta,
            "enfileirado_em": r.get("enfileirado_em"),
            "iniciado_em": r.get("iniciado_em"),
            "finalizado_em": r.get("finalizado_em"),
            "erro_msg": r.get("erro_msg"),
            "progresso": _progresso_estimado(r, meta),
        })
    return {"jobs": jobs}


@router.post("/jobs/{job_id}/pausar")
def pausar_job_endpoint(
    job_id: str, request: Request, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    job, meta = _job_controlavel(job_id, request, membro, conn)
    if job["status"] == "executando" and meta.get("etapa") != "qa_agentico":
        raise HTTPException(status_code=409, detail="este motor nao pode ser pausado no meio da execucao")
    if repo.pausar_job(conn, job_id) is None:
        raise HTTPException(status_code=409, detail="job nao esta ativo para pausar")
    return {"job_id": job_id, "estado": "pausado", "mensagem": "Job pausado pelo operador."}


@router.post("/jobs/{job_id}/continuar")
def continuar_job_endpoint(
    job_id: str, request: Request, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    _job_controlavel(job_id, request, membro, conn)
    if repo.continuar_job(conn, job_id) is None:
        raise HTTPException(status_code=409, detail="job nao esta pausado pelo operador")
    return {"job_id": job_id, "estado": "na_fila", "mensagem": "Job devolvido a fila."}


@router.post("/jobs/{job_id}/cancelar")
def cancelar_job_endpoint(
    job_id: str, request: Request, membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    job, meta = _job_controlavel(job_id, request, membro, conn)
    if job["status"] == "executando" and meta.get("etapa") != "qa_agentico":
        raise HTTPException(status_code=409, detail="este motor nao pode ser cancelado com seguranca no meio da execucao")
    if repo.cancelar_job_operador(conn, job_id) is None:
        raise HTTPException(status_code=409, detail="job ja foi finalizado")
    return {"job_id": job_id, "estado": "cancelado", "mensagem": "Job cancelado pelo operador."}


_ETA_PADRAO_S = {
    "sa": 600,
    "sa_item": 180,
    "n3": 360,
    "n5": 180,
    "triagem": 180,
    "recortes": 240,
    "converter_dwg": 180,
}


def _instante(valor: Optional[str]) -> Optional[datetime]:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _progresso_estimado(job: dict, meta: dict) -> dict:
    """Telemetria temporal limitada a 95% até o worker confirmar o resultado."""
    status = str(job.get("status") or "")
    etapa = str((meta or {}).get("etapa") or "sa")
    inicio = _instante(job.get("iniciado_em"))
    fim = _instante(job.get("finalizado_em"))
    agora = fim or datetime.now(timezone.utc)
    decorrido = max(0, int((agora - inicio).total_seconds())) if inicio else 0
    esperado = _ETA_PADRAO_S.get(etapa, 300)

    if status == "cancelado" and job.get("erro_msg") == repo.PAUSA_OPERADOR:
        percentual, restante, rotulo = None, None, "Pausado pelo operador"
    elif status == "na_fila":
        percentual, restante, rotulo = 0, None, "Aguardando na fila"
    elif status == "executando":
        percentual = min(95, max(2, round((decorrido / esperado) * 100)))
        restante = max(0, esperado - decorrido)
        rotulo = "Processando no motor"
    elif status == "concluido":
        percentual, restante, rotulo = 100, 0, "Concluído"
    else:
        percentual, restante, rotulo = None, None, "Falhou" if status == "falhou" else status

    return {
        "percentual_estimado": percentual,
        "decorrido_s": decorrido,
        "restante_estimado_s": restante,
        "rotulo": rotulo,
        "estimativa": status == "executando",
    }


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
    meta = request.app.state.job_meta.get(job_id) or repo.obter_job_meta(conn, job_id)
    # mapa status DB -> estado do contrato (HANDOFF §1.3)
    mapa = {"na_fila": "queued", "executando": "running",
            "concluido": "done", "falhou": "error", "cancelado": "cancelled"}
    estado = "paused" if _status_publico(job) == "pausado" else mapa.get(job["status"], job["status"])
    return {
        "job_id": job["id"], "obra_id": job["obra_id"],
        "tipo": meta.get("etapa"), "estado": estado,
        "engine_version": job.get("engine_version"),
        "criado_em": job.get("enfileirado_em"), "iniciado_em": job.get("iniciado_em"),
        "finalizado_em": job.get("finalizado_em"),
        "log_tail": _ler_log_tail(job.get("log_path")),
        "erro_msg": job.get("erro_msg"),
        "progresso": _progresso_estimado(job, meta),
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
