"""Páginas server-rendered do portal (Jinja2) — front-end mínimo (HANDOFF-UX §1-6).

Este router serve APENAS HTML. As partes assíncronas (ações de etapa, polling de
job, autosave do ErrorMarker, download N5) são feitas por `fetch()` no cliente
contra as rotas JSON já existentes (auth_routes, obras_routes, jobs_routes,
comentarios_routes, fichas_routes) — não duplicamos contrato aqui.

Fronteira respeitada: o portal só LÊ artefatos e usa a camada de dados existente.
Nenhuma tabela nova, nenhum endpoint de negócio novo — só render.

Autenticação das páginas: reaproveita o cookie de sessão (auth.ler_cookie). Página
de login é pública; as demais redirecionam para /login sem sessão válida (em vez de
401, que é o comportamento das rotas JSON).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth, certification
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["paginas"], include_in_schema=False)

# templates montados em setup_templates() a partir de create_app (injeta o env)
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _templates(request: Request):
    """Recupera o Jinja2Templates guardado em app.state (montado no create_app)."""
    return request.app.state.templates


def _membro_da_sessao(request: Request, conn: sqlite3.Connection) -> Optional[dict]:
    settings = request.app.state.settings
    valor = request.cookies.get(settings.session_cookie_name, "")
    login = auth.ler_cookie(settings, valor)
    if login is None:
        return None
    membro = repo.obter_membro_por_login(conn, login)
    if membro is None or int(membro.get("ativo", 1)) != 1:
        return None
    return membro


def _etapa_atual(obra: dict, jobs: list[dict], n5_releases: list[dict]) -> int:
    """Deriva a etapa (1..5) do estado da obra (o enum do schema tem 4 valores).

    aguardando_ingestao -> 1 (aguardando triagem quando baixada)
    processando          -> 3 (SA em progresso)
    pronta               -> 4 (pronta para validação)
    erro                 -> 1 (mostra o erro no topo da lista)
    Se já houver release N5 registrado, avança para 5.
    """
    if n5_releases:
        return 5
    estado = obra.get("estado")
    if estado == "processando":
        return 3
    if estado == "pronta":
        return 4
    return 1


def _job_ativo(jobs: list[dict]) -> Optional[str]:
    for j in jobs:
        if j.get("status") in ("na_fila", "executando"):
            return j["id"]
    return None


# --------------------------------------------------------------------------- #
# Login (público)
# --------------------------------------------------------------------------- #

@router.get("/", response_class=HTMLResponse)
def raiz(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    if _membro_da_sessao(request, conn) is not None:
        return RedirectResponse("/app/obras", status_code=303)
    return RedirectResponse("/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def pagina_login(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    if _membro_da_sessao(request, conn) is not None:
        return RedirectResponse("/app/obras", status_code=303)
    return _templates(request).TemplateResponse(request, "login.html", {})


# --------------------------------------------------------------------------- #
# Lista de obras
# --------------------------------------------------------------------------- #

@router.get("/app/obras", response_class=HTMLResponse)
def pagina_obras(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)
    obras = repo.listar_obras_por_membro(conn, membro["id"])
    drive = request.app.state.estado_global.get("drive", "ok")
    return _templates(request).TemplateResponse(
        request, "obras_lista.html",
        {"membro": membro, "obras": obras, "drive": drive},
    )


# --------------------------------------------------------------------------- #
# Detalhe da obra (host das etapas 1-5)
# --------------------------------------------------------------------------- #

@router.get("/app/obras/{obra_id}", response_class=HTMLResponse)
def pagina_obra_detalhe(
    obra_id: str, request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Detalhe/progresso da obra. Namespace /app/* isola as páginas HTML das rotas
    JSON /obras/* (obras_routes), evitando colisão de path."""
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)

    obra = repo.obter_obra(conn, obra_id)
    if obra is None or obra["membro_id"] != membro["id"]:
        return RedirectResponse("/app/obras", status_code=303)

    settings = request.app.state.settings
    jobs = repo.listar_jobs_por_obra(conn, obra_id)
    n5_releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    comentarios = repo.listar_comentarios_por_obra(conn, obra_id)
    rotulos = {
        c: certification.classificar_certificacao(settings.status_md_path, c)
        for c in ("PL", "LV", "FV", "LJ")
    }
    # fichas HTML disponíveis (viewer)
    fichas: list[dict] = []
    lp = obra.get("local_path")
    base = (Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra"))
    base = base / "Fase-6_Execucao_CAD"
    if base.exists():
        for p in sorted(base.rglob("*.html")):
            fichas.append({
                "nome": p.name,
                "rel": str(p.relative_to(base)).replace("\\", "/"),
                "tamanho": p.stat().st_size,
            })

    etapa_param = request.query_params.get("etapa")
    etapa_derivada = _etapa_atual(obra, jobs, n5_releases)
    etapa_atual = etapa_derivada
    if etapa_param and etapa_param.isdigit():
        # o usuário pode revisar uma etapa <= à derivada (movimento com gate, §1)
        pedido = int(etapa_param)
        if 1 <= pedido <= etapa_derivada:
            etapa_atual = pedido

    validacao_concluida = any(
        v.get("validado")
        for v in request.app.state.validacoes.get(obra_id, {}).values()
    ) or bool(n5_releases)

    ctx = {
        "membro": membro,
        "obra": obra,
        "jobs": jobs,
        "fichas": fichas,
        "comentarios": comentarios,
        "n5_releases": n5_releases,
        "rotulos": rotulos,
        "etapa_atual": etapa_atual,
        "job_ativo": _job_ativo(jobs) if etapa_atual == 3 else None,
        "validacao_concluida": validacao_concluida,
        "pavimento": settings.pav_default,
        "classe_ativa": None,
        "item_id": None,
    }
    return _templates(request).TemplateResponse(request, "obra_detalhe.html", ctx)


def setup_templates(app) -> None:
    """Monta o Jinja2Templates em app.state (chamado por create_app)."""
    from fastapi.templating import Jinja2Templates

    app.state.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
