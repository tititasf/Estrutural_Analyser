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
from functools import lru_cache
import html
import json
import sqlite3
from statistics import median
import threading
import uuid
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import access, auth, certification, n5_release, pipeline_runner, viewer_pavimentos
from ..drawing_modes import normalize_visual_mode
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["etapas"])

_N5_PL_TILE_RENDER_LOCK = threading.Lock()


@lru_cache(maxsize=2048)
def _n5_pl_source_bbox_cached(
    source_path: str, mtime_ns: int,
) -> tuple[float, float, float, float] | None:
    """Extensão CAD da vista; ``mtime_ns`` invalida o cache ao regenerar."""
    del mtime_ns
    from .. import dxf_preview

    return dxf_preview.obter_bbox_dxf(Path(source_path))


def _n5_pl_source_size(source: str) -> tuple[float, float] | None:
    """Tamanho nativo em unidades CAD, sem normalizar uma vista pela outra."""
    try:
        path = Path(source).resolve()
        if not path.is_file():
            return None
        box = _n5_pl_source_bbox_cached(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return None
    if box is None:
        return None
    return max(float(box[2] - box[0]), 1.0), max(float(box[3] - box[1]), 1.0)


def _n5_manifest(dxf_path: Path) -> dict:
    manifest_path = dxf_path.with_suffix(".json")
    if not manifest_path.is_file():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _n5_release_mode(release: dict) -> str:
    path = Path(release.get("dxf_path") or "")
    manifest = _n5_manifest(path) if path else {}
    try:
        return normalize_visual_mode(manifest.get("visual_mode") or "NOVA")
    except ValueError:
        return "NOVA"


def _select_n5_release(
    releases: list[dict], classe: str, pavimento: str | None,
    visual_mode: str | None,
) -> dict | None:
    requested = normalize_visual_mode(visual_mode) if visual_mode else None
    return next((
        release for release in releases
        if release["classe"] == classe.upper()
        and (not pavimento or release.get("pavimento") == pavimento)
        and release.get("dxf_path")
        and (not requested or _n5_release_mode(release) == requested)
    ), None)


def _n5_group_path(dxf_path: Path, classe: str, pillar_group: str | None) -> Path:
    if not pillar_group:
        return dxf_path
    if classe.upper() != "PL" or pillar_group not in {"PARA", "PASSA"}:
        raise HTTPException(status_code=422, detail="grupo de pilares inválido")
    path = dxf_path.with_name(f"{dxf_path.stem}_{pillar_group}.dxf")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rode o N5 para gerar os conjuntos Para e Passa")
    return path


def _n5_pl_tiled_svg(
    obra_id: str, pavimento: str, dxf_path: Path, visual_mode: str = "NOVA",
    pillar_group: str | None = None,
) -> bytes:
    """Índice SVG leve com cinco vistas na mesma escala CAD por pilar.

    Cada preview é um SVG independente. Dar a todos um viewport fixo de
    720x480 fazia cada desenho sofrer um ``fit`` próprio: Grades 1x eram
    ampliadas e aparentavam a escala do Cima 2x. O mosaico agora usa o bbox
    nativo de cada fonte como largura/altura do ``<image>``. Assim o navegador
    só posiciona as vistas, reproduzindo o mesmo contrato do DXF N5.
    """
    manifest = _n5_manifest(dxf_path)
    items = [item for item in manifest.get("items", []) if item.get("status") == "ok"]
    fallback_size = (720.0, 480.0)
    label_w, gap_x, gap_y = 90.0, 24.0, 36.0
    rows: list[tuple[dict, list[tuple[float, float]], float, float]] = []
    width = 0.0
    height = 0.0
    for item in items:
        sources = str(item.get("source") or "").split(";")
        sizes = [
            _n5_pl_source_size(sources[index]) or fallback_size
            for index in range(3 if pillar_group else 5)
        ] if len(sources) == (3 if pillar_group else 5) else [fallback_size] * (3 if pillar_group else 5)
        row_height = max(size[1] for size in sizes)
        row_width = label_w + sum(size[0] for size in sizes) + (len(sizes) - 1) * gap_x
        rows.append((item, sizes, row_height, height))
        width = max(width, row_width)
        height += row_height + gap_y
    if rows:
        height -= gap_y
    width = max(width, label_w + fallback_size[0])
    height = max(height, fallback_size[1])
    version = int(dxf_path.stat().st_mtime_ns)
    chunks = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}">',
        '<rect width="100%" height="100%" fill="#050a10"/>',
        '<style>text{fill:#e8edf5;font:700 22px sans-serif}'
        '.tile{outline:1px solid #26384d}</style>',
    ]
    for item, sizes, row_height, y in rows:
        item_id = str(item.get("item_id") or "")
        chunks.append(f'<text x="12" y="{y + 32}">{html.escape(item_id)}</text>')
        x = label_w
        for view_index, (tile_w, tile_h) in enumerate(sizes):
            tile_y = y + (row_height - tile_h) / 2.0
            href = (
                f"/obras/{quote(obra_id, safe='')}/n5/PL/foto-tile/"
                f"{quote(item_id, safe='')}/{view_index}?"
                f"pavimento={quote(pavimento, safe='')}&amp;visual_mode={quote(visual_mode, safe='')}"
                f"&amp;v={version}"
                + (f"&amp;pillar_group={pillar_group}" if pillar_group else "")
            )
            chunks.append(
                f'<image class="tile" x="{x:g}" y="{tile_y:g}" '
                f'width="{tile_w:g}" height="{tile_h:g}" '
                f'href="{href}" preserveAspectRatio="xMidYMid meet"/>'
            )
            x += tile_w + gap_x
    chunks.append("</svg>")
    return "".join(chunks).encode("utf-8")


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
    visual_mode: str = "NOVA",
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
            "visual_mode": normalize_visual_mode(visual_mode),
        }
        job_id = _enfileirar(request, conn, obra, meta)
        jobs.append({"job_id": job_id, "pav": pavimento, "meta": meta})
    return batch_id, jobs


class SAIn(BaseModel):
    secao: Optional[list[str]] = None
    pav: Optional[str] = None
    classe_ui: Optional[str] = None

class N3In(BaseModel):
    secao: Optional[list[str]] = None
    pav: Optional[str] = None
    classe_ui: Optional[str] = None
    visual_mode: Literal["NOVA", "INI"] = "NOVA"


class ValidacaoIn(BaseModel):
    classe: str
    n1_ok: bool
    n3_ok: bool
    item_id: Optional[str] = None


class N5In(BaseModel):
    classe: str
    pavimento: str = "GERAL"
    visual_mode: Literal["NOVA", "INI"] = "NOVA"


class N5ValidacaoIn(BaseModel):
    pavimento: str = "GERAL"
    visual_mode: Literal["NOVA", "INI"] = "NOVA"


class MotoresIn(BaseModel):
    pav: Optional[str] = None
    secao: Optional[list[str]] = None
    classe_ui: Optional[str] = None
    visual_mode: Literal["NOVA", "INI"] = "NOVA"


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
    documentos = repo.listar_documentos_por_obra(conn, obra_id)
    dwgs = pipeline_runner.listar_dwgs_com_status(
        request.app.state.settings, obra, documentos,
    )
    dwgs_pendentes = [item for item in dwgs if not item["tem_dxf"]]
    documentos_pendentes = [
        item for item in documentos if item.get("status") in ("pendente", "erro")
    ]
    job_id = _enfileirar(request, conn, obra, {"etapa": "triagem"})
    return {
        "job_id": job_id, "obra_id": obra_id, "etapa": "triagem", "estado": "queued",
        "preflight": {
            "dwgs_encontrados": len(dwgs),
            "dwgs_a_converter": len(dwgs_pendentes),
            "documentos_a_processar": len(documentos_pendentes),
            "conversao_automatica": True,
        },
    }


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
    meta = {"etapa": "sa", "secao": body.secao, "pav": body.pav,
            "classe_ui": body.classe_ui}
    job_id = _enfileirar(request, conn, obra, meta)
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "sa",
            "estado": "queued", "secao": body.secao, "meta": meta}


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
    try:
        visual_mode = normalize_visual_mode(body.visual_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    meta = {"etapa": "n3", "secao": body.secao, "pav": body.pav,
            "classe_ui": body.classe_ui,
            "visual_mode": visual_mode}
    job_id = _enfileirar(request, conn, obra, meta)
    return {"job_id": job_id, "obra_id": obra_id, "etapa": "n3",
            "estado": "queued", "secao": body.secao, "visual_mode": visual_mode,
            "meta": meta}


@router.post("/obras/{obra_id}/n3-todos")
def n3_todos(obra_id: str, body: N3In, request: Request,
             membro: dict = Depends(auth.exige_login),
             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    batch_id, jobs = _enfileirar_todos_pavimentos(
        request, conn, obra, etapa="n3", secao=body.secao,
        visual_mode=body.visual_mode,
    )
    return {"batch_id": batch_id, "obra_id": obra_id, "etapa": "n3",
            "estado": "queued", "total": len(jobs), "jobs": jobs,
            "visual_mode": body.visual_mode}


@router.post("/obras/{obra_id}/motores")
def todos_motores(obra_id: str, body: MotoresIn, request: Request,
                   membro: dict = Depends(auth.exige_login),
                   conn: sqlite3.Connection = Depends(get_db_conn)):
    """SA -> N3 da mesma rodada -> N5 das classes previamente validadas."""
    obra = _obra_do_membro(conn, obra_id, membro)
    try:
        visual_mode = normalize_visual_mode(body.visual_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    meta = {
        "etapa": "motores", "secao": body.secao, "pav": body.pav,
        "classe_ui": body.classe_ui,
        "cascade_n5": True, "membro_id": membro["id"],
        "visual_mode": visual_mode,
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

@router.get("/obras/{obra_id}/n5/modos")
def n5_modes(obra_id: str, request: Request, classe: Literal["PL", "LV", "FV", "LJ"] = "PL",
             pavimento: str = "GERAL", membro: dict = Depends(auth.exige_login),
             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    from src.core.n5_assembler import n3_mode_readiness
    obra_dir = pipeline_runner._obra_dir(settings, obra)
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    modes = {}
    for mode in ("NOVA", "INI"):
        ready = n3_mode_readiness(obra_dir, classe, pavimento, mode, settings.sa_db_path)
        release = _select_n5_release(releases, classe, pavimento, mode)
        exists = bool(release and release.get("dxf_path") and Path(release["dxf_path"]).is_file())
        if exists and classe == "PL":
            try:
                for group in ("PARA", "PASSA"):
                    _n5_group_path(Path(release["dxf_path"]), classe, group)
            except HTTPException:
                exists = False
        modes[mode] = {"n3": ready["ready"], "n5": exists, "total": ready["total"], "missing": ready["missing"]}
    return {"modes": modes}


@router.post("/obras/{obra_id}/n5")
def n5(obra_id: str, body: N5In, request: Request, membro: dict = Depends(auth.exige_login),
       conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    classe = body.classe.upper()
    try:
        visual_mode = normalize_visual_mode(body.visual_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if classe == "ALL":
        releases = []
        blocked = []
        ev = pipeline_runner.engine_version(settings.repo_root)
        for class_code in ("PL", "LV", "FV", "LJ"):
            if not repo.obter_validacao_classe(conn, obra_id, class_code)["validado"]:
                blocked.append(class_code)
                continue
            try:
                releases.append(n5_release.liberar_n5(
                    conn, settings, obra=obra, classe=class_code,
                    pavimento=body.pavimento, membro_id=membro["id"],
                    engine_version=ev, dry_run=False,
                    visual_mode="NOVA" if class_code == "LV" else visual_mode,
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
    # O dono pode gerar um rascunho para inspeção antes do fechamento da
    # validação N1+N3. O artefato nasce com aprovação N5 pendente; demais
    # papéis continuam protegidos pelo gate original.
    if not validado and not access.eh_dono(membro):
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
            visual_mode="NOVA" if classe == "LV" else visual_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    info["validacao_previa"] = validado
    info["aprovacao_n5"] = "pendente"
    return info


@router.post("/obras/{obra_id}/n5/{classe}/validacao")
def validar_n5(
    obra_id: str,
    classe: str,
    body: N5ValidacaoIn,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Aprova o release mais recente da classe+pavimento que ainda existe."""
    _obra_do_membro(conn, obra_id, membro)
    classe = classe.upper()
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    alvo = _select_n5_release(releases, classe, body.pavimento, body.visual_mode)
    if alvo is None:
        raise HTTPException(status_code=404, detail="N5 gerado não encontrado")
    validacao = repo.aprovar_n5_release(
        conn,
        release_id=alvo["id"],
        obra_id=obra_id,
        classe=classe,
        pavimento=body.pavimento,
        aprovado_por=membro["id"],
    )
    return {"ok": True, "aprovado": True, "release_id": alvo["id"], **validacao}


@router.get("/obras/{obra_id}/n5/{classe}/download")
def n5_download(obra_id: str, classe: str, request: Request,
                pavimento: Optional[str] = None,
                visual_mode: Optional[Literal["NOVA", "INI"]] = None,
            pillar_group: Optional[Literal["PARA", "PASSA"]] = None,
                membro: dict = Depends(auth.exige_login),
                conn: sqlite3.Connection = Depends(get_db_conn)):
    from fastapi.responses import FileResponse

    obra = _obra_do_membro(conn, obra_id, membro)
    settings = request.app.state.settings
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    alvo = _select_n5_release(releases, classe, pavimento, visual_mode)
    if alvo is None:
        raise HTTPException(status_code=404, detail="nenhum N5 liberado para esta classe")
    from pathlib import Path as _P
    path = _n5_group_path(_P(alvo["dxf_path"]), classe, pillar_group)
    if not path.exists():
        raise HTTPException(status_code=410, detail="DXF do N5 nao esta mais disponivel")
    rotulo = certification.classificar_certificacao(settings.status_md_path, classe.upper())
    return FileResponse(
        path, filename=path.name,
        media_type="application/dxf", headers={"X-Certificacao": rotulo},
    )


@router.get("/obras/{obra_id}/n5/download")
def n5_download_all(obra_id: str, request: Request, pavimento: Optional[str] = None,
                    visual_mode: Optional[Literal["NOVA", "INI"]] = None,
                    membro: dict = Depends(auth.exige_login),
                    conn: sqlite3.Connection = Depends(get_db_conn)):
    """ZIP real: quatro classes de um pavimento ou todos os pavimentos completos."""
    from tempfile import NamedTemporaryFile
    from zipfile import ZIP_DEFLATED, ZipFile
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask

    obra = _obra_do_membro(conn, obra_id, membro)
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    latest: dict[tuple[str, str], dict] = {}
    for release in releases:
        mode = _n5_release_mode(release)
        requested = normalize_visual_mode(visual_mode) if visual_mode else None
        if requested and release["classe"] != "LV" and mode != requested:
            continue
        key = (str(release.get("pavimento") or "GERAL"), release["classe"])
        path = Path(release.get("dxf_path") or "")
        if key not in latest and path.is_file():
            latest[key] = release

    classes = ("PL", "LV", "FV", "LJ")
    if pavimento:
        pavimentos = [pavimento]
    else:
        settings = request.app.state.settings
        lp = obra.get("local_path")
        obra_dir = Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")
        pavimentos = [
            item["pavimento"]
            for item in viewer_pavimentos.listar_pavimentos_com_torre(obra_dir, obra)
        ]
        if not pavimentos:
            pavimentos = sorted({key[0] for key in latest})
    if not pavimentos:
        raise HTTPException(status_code=404, detail="nenhum pavimento com N5")

    faltantes = [
        f"{pav}/{classe}" for pav in pavimentos for classe in classes
        if (pav, classe) not in latest
    ]
    if faltantes:
        raise HTTPException(
            status_code=409,
            detail="ZIP completo aguarda: " + ", ".join(faltantes),
        )

    tmp = NamedTemporaryFile(prefix="cad-n5-", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        with ZipFile(tmp_path, "w", compression=ZIP_DEFLATED) as archive:
            for pav in pavimentos:
                for classe in classes:
                    src = Path(latest[(pav, classe)]["dxf_path"])
                    parts = [_n5_group_path(src, classe, group) for group in ("PARA", "PASSA")] if classe == "PL" else [src]
                    for part in parts:
                        archive.write(part, arcname=f"{pav}/{part.name}")
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    nome = f"N5_{pavimento}.zip" if pavimento else "N5_todos_pavimentos.zip"
    return FileResponse(
        tmp_path,
        filename=nome,
        media_type="application/zip",
        background=BackgroundTask(tmp_path.unlink, missing_ok=True),
    )

@router.get("/obras/{obra_id}/n5/{classe}/foto")
def n5_foto(obra_id: str, classe: str, request: Request,
            pavimento: Optional[str] = None,
            visual_mode: Optional[Literal["NOVA", "INI"]] = None,
            pillar_group: Optional[Literal["PARA", "PASSA"]] = None,
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
    alvo = _select_n5_release(releases, classe, pavimento, visual_mode)
    if alvo is None:
        raise HTTPException(status_code=404, detail="nenhum N5 liberado para esta classe")
    dxf_path = _n5_group_path(_P(alvo["dxf_path"]), classe, pillar_group)
    if not dxf_path.exists():
        raise HTTPException(status_code=410, detail="DXF do N5 nao esta mais disponivel")

    settings = request.app.state.settings
    lp = obra.get("local_path")
    obra_dir = _P(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")
    cache_dir = obra_dir / ".previews"
    try:
        if classe.upper() == "PL":
            svg = _n5_pl_tiled_svg(
                obra_id, pavimento or alvo.get("pavimento") or "GERAL", dxf_path,
                _n5_release_mode(alvo), pillar_group,
            )
        else:
            svg = dxf_preview.renderizar_dxf_svg_cacheado(dxf_path, cache_dir)
    except Exception as exc:  # noqa: BLE001 - DXF pode ter geometria que o renderer nao suporta
        raise HTTPException(status_code=502, detail=f"falha ao renderizar: {exc}") from exc
    return _Response(content=svg, media_type="image/svg+xml")


@router.get("/obras/{obra_id}/n5/PL/foto-tile/{item_id}/{view_index}")
def n5_pl_foto_tile(
    obra_id: str,
    item_id: str,
    view_index: int,
    request: Request,
    pavimento: Optional[str] = None,
    visual_mode: Optional[Literal["NOVA", "INI"]] = None,
    pillar_group: Optional[Literal["PARA", "PASSA"]] = None,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Uma das cinco vistas N3 exatas usadas na linha do pilar no N5."""
    from fastapi.responses import Response as _Response
    from .. import dxf_preview

    if view_index not in range(3 if pillar_group else 5):
        raise HTTPException(status_code=404, detail="vista N5 de pilar invalida")
    obra = _obra_do_membro(conn, obra_id, membro)
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    alvo = _select_n5_release(releases, "PL", pavimento, visual_mode)
    if alvo is None:
        raise HTTPException(status_code=404, detail="N5 PL nao liberado")
    dxf_path = _n5_group_path(Path(alvo["dxf_path"]), "PL", pillar_group)
    manifest = _n5_manifest(dxf_path)
    item = next(
        (entry for entry in manifest.get("items", [])
         if str(entry.get("item_id")) == item_id and entry.get("status") == "ok"),
        None,
    )
    sources = str((item or {}).get("source") or "").split(";")
    if len(sources) != (3 if pillar_group else 5):
        raise HTTPException(status_code=404, detail="conjunto N3 do pilar incompleto")
    source = Path(sources[view_index]).resolve()
    settings = request.app.state.settings
    local_path = obra.get("local_path")
    obra_dir = (Path(local_path) if local_path
                else settings.dados_obras_dir / obra.get("nome", "obra")).resolve()
    if not source.is_file() or not source.is_relative_to(obra_dir):
        raise HTTPException(status_code=410, detail="vista N3 nao esta mais disponivel")
    try:
        bbox = _n5_pl_source_bbox_cached(str(source), source.stat().st_mtime_ns)
        if bbox is None:
            raise ValueError("vista N3 sem extensão CAD")
        cad_w = max(float(bbox[2] - bbox[0]), 1.0)
        cad_h = max(float(bbox[3] - bbox[1]), 1.0)
        alvo = 1200
        if cad_w >= cad_h:
            largura_px = alvo
            altura_px = max(int(round(alvo * cad_h / cad_w)), 1)
        else:
            altura_px = alvo
            largura_px = max(int(round(alvo * cad_w / cad_h)), 1)
        # Matplotlib nao e thread-safe. O lock mantem a memoria limitada; os
        # acessos seguintes usam cache e atravessam esta secao rapidamente.
        with _N5_PL_TILE_RENDER_LOCK:
            svg = dxf_preview.renderizar_dxf_svg_cacheado(
                source,
                obra_dir / ".previews" / "n5_pl_tiles",
                bbox=bbox,
                largura_px=largura_px,
                altura_px=altura_px,
                margem_pct=0.03,
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"falha ao renderizar vista: {exc}") from exc
    return _Response(content=svg, media_type="image/svg+xml")


# --------------------------------------------------------------------------- #
# GET /obras/{id}/jobs — lista todos os jobs de uma obra (polling UI)
# --------------------------------------------------------------------------- #

def _posicoes_fila(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Posição na fila única do portal, na mesma ordem consumida pelo worker.

    Os jobs de outras obras entram apenas na contagem; suas identidades nunca
    são expostas ao usuário que consulta esta obra.
    """
    running = conn.execute(
        "SELECT id FROM portal_jobs WHERE status='executando' ORDER BY iniciado_em, rowid"
    ).fetchall()
    queued = conn.execute(
        """SELECT id FROM portal_jobs WHERE status='na_fila'
           ORDER BY prioridade DESC, enfileirado_em, rowid"""
    ).fetchall()
    ahead_running = len(running)
    total = ahead_running + len(queued)
    return {
        row["id"]: {"posicao": ahead_running + index + 1,
                    "a_frente": ahead_running + index, "total_ativos": total}
        for index, row in enumerate(queued)
    }


@router.get("/obras/{obra_id}/jobs")
def listar_jobs_obra(obra_id: str, request: Request,
                     membro: dict = Depends(auth.exige_login),
                     conn: sqlite3.Connection = Depends(get_db_conn)):
    """Lista todos os jobs de uma obra para polling do frontend."""
    obra = _obra_do_membro(conn, obra_id, membro)
    rows = repo.listar_jobs_por_obra(conn, obra_id)
    fila = _posicoes_fila(conn)
    jobs = []
    eta_cache: dict[str, tuple[int, str]] = {}
    for r in rows:
        meta = request.app.state.job_meta.get(r["id"]) or repo.obter_job_meta(conn, r["id"])
        etapa = str((meta or {}).get("etapa") or "sa")
        if etapa not in eta_cache:
            eta_cache[etapa] = _duracao_estimada(conn, obra_id, etapa)
        esperado_s, fonte_eta = eta_cache[etapa]
        jobs.append({
            "id": r["id"],
            "status": _status_publico(r),
            "meta": meta,
            "enfileirado_em": r.get("enfileirado_em"),
            "iniciado_em": r.get("iniciado_em"),
            "finalizado_em": r.get("finalizado_em"),
            "erro_msg": r.get("erro_msg"),
            "progresso": _progresso_estimado(
                r, meta, esperado_s=esperado_s, fonte_estimativa=fonte_eta,
            ),
            "fila": fila.get(r["id"]),
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
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        # SQLite datetime() devolve texto sem offset; os timestamps do portal
        # são UTC por contrato, não horário local do host.
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        return instante.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _duracao_estimada(
    conn: sqlite3.Connection, obra_id: str, etapa: str,
) -> tuple[int, str]:
    """Mediana das últimas execuções equivalentes; fallback conservador."""
    rows = conn.execute(
        """SELECT j.iniciado_em, j.finalizado_em, m.meta_json
           FROM portal_jobs j
           LEFT JOIN portal_job_meta m ON m.job_id = j.id
           WHERE j.obra_id = ? AND j.status = 'concluido'
             AND j.iniciado_em IS NOT NULL AND j.finalizado_em IS NOT NULL
           ORDER BY j.rowid DESC LIMIT 40""",
        (obra_id,),
    ).fetchall()
    duracoes: list[int] = []
    for row in rows:
        try:
            meta = json.loads(row["meta_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if str(meta.get("etapa") or "sa") != etapa:
            continue
        inicio = _instante(row["iniciado_em"])
        fim = _instante(row["finalizado_em"])
        if inicio and fim:
            duracao = int((fim - inicio).total_seconds())
            if 0 < duracao <= 24 * 3600:
                duracoes.append(duracao)
        if len(duracoes) >= 10:
            break
    if duracoes:
        # Um piso curto evita uma barra saltando de 0 a 95% em um único poll,
        # sem fingir precisão para jobs que historicamente duram poucos segundos.
        return max(5, int(round(median(duracoes)))), "historico_da_obra"
    return _ETA_PADRAO_S.get(etapa, 300), "padrao_da_etapa"


def _progresso_estimado(
    job: dict,
    meta: dict,
    *,
    esperado_s: Optional[int] = None,
    fonte_estimativa: str = "padrao_da_etapa",
) -> dict:
    """Telemetria temporal limitada a 95% até o worker confirmar o resultado."""
    status = str(job.get("status") or "")
    etapa = str((meta or {}).get("etapa") or "sa")
    inicio = _instante(job.get("iniciado_em"))
    fim = _instante(job.get("finalizado_em"))
    agora = fim or datetime.now(timezone.utc)
    decorrido = max(0, int((agora - inicio).total_seconds())) if inicio else 0
    esperado = esperado_s or _ETA_PADRAO_S.get(etapa, 300)

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
        "duracao_estimada_s": esperado,
        "fonte_estimativa": fonte_estimativa,
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
    esperado_s, fonte_eta = _duracao_estimada(conn, job["obra_id"], str(meta.get("etapa") or "sa"))
    fila = _posicoes_fila(conn)
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
        "progresso": _progresso_estimado(
            job, meta, esperado_s=esperado_s, fonte_estimativa=fonte_eta,
        ),
        "fila": fila.get(job_id),
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
