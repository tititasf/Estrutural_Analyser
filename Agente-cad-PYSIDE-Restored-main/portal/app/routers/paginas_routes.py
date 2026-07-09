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

from .. import access, auth, certification
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["paginas"], include_in_schema=False)

# templates montados em setup_templates() a partir de create_app (injeta o env)
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _templates(request: Request):
    """Recupera o Jinja2Templates guardado em app.state (montado no create_app)."""
    return request.app.state.templates


def _render(request: Request, template_name: str, ctx: dict):
    """Chama TemplateResponse com a assinatura que ESTA versao do starlette exige.

    [FIX 2026-07-06] bug real, achado rodando (nao só lendo código): as 4 rotas de
    página chamavam `TemplateResponse(request, nome, ctx)` (convenção nova, request
    primeiro) — mas `starlette` 0.27.0 instalado tem a assinatura ANTIGA
    `TemplateResponse(name: str, context: dict, ...)`, sem `request` posicional.
    O resultado: TODA página HTML do portal (login, lista, detalhe) quebrava com
    `ValueError: context must include a "request" key` no primeiro acesso via
    navegador — nenhum teste anterior tinha feito um GET real numa página HTML
    (só nas rotas JSON), então isso nunca foi pego antes de agora. Centralizado
    aqui para as 4 chamadas nunca mais divergirem da assinatura real instalada.
    """
    ctx = {**ctx, "request": request}
    return _templates(request).TemplateResponse(template_name, ctx)


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


# [FIX 2026-07-06] etapa (1..5) derivada de `etapa_concluida` (migration 003),
# NAO mais so' de `estado` — achado real testando o modo rapido: toda etapa
# bem-sucedida (inclusive so' a triagem) marcava estado='pronta', fazendo
# `_etapa_atual` pular direto pra 4 (Validacao) mesmo sem recortes/SA terem
# rodado. `etapa_concluida` guarda precisamente qual foi a ULTIMA etapa do
# pipeline (triagem/recortes/sa) que terminou com sucesso.
_PROXIMA_ETAPA = {None: 1, "triagem": 2, "recortes": 3, "sa": 4}


def _etapa_atual(obra: dict, jobs: list[dict], n5_releases: list[dict]) -> int:
    """Deriva a etapa (1..5) da obra a partir de `etapa_concluida` + `estado`.

    A etapa retornada e' sempre "a proxima depois da ultima concluida" —
    vale tanto para o passo ainda nao iniciado (estado idle/processando)
    quanto para o passo que FALHOU (estado='erro': mostra o erro na propria
    etapa que quebrou, nao sempre na etapa 1).
    Se já houver release N5 registrado, avança para 5 (checado primeiro —
    mais autoritativo que qualquer coisa em `etapa_concluida`).
    """
    if n5_releases:
        return 5
    return _PROXIMA_ETAPA.get(obra.get("etapa_concluida"), 1)


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
    return _render(request, "login.html", {})


# --------------------------------------------------------------------------- #
# Lista de obras
# --------------------------------------------------------------------------- #

@router.get("/app/obras", response_class=HTMLResponse)
def pagina_obras(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)
    obras = (
        repo.listar_todas_obras(conn)
        if access.eh_dono(membro)
        else repo.listar_obras_por_membro(conn, membro["id"])
    )
    drive = request.app.state.estado_global.get("drive", "ok")
    drive_folder_url = (
        f"https://drive.google.com/drive/folders/{membro['drive_folder_id']}"
        if membro.get("drive_folder_id") else None
    )
    return _render(request, "obras_lista.html", {
        "membro": membro, "obras": obras, "drive": drive,
        "drive_folder_url": drive_folder_url, "nav_ativo": "obras",
    })


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
    if obra is None or not access.pode_ver_obra(obra, membro):
        return RedirectResponse("/app/obras", status_code=303)

    settings = request.app.state.settings
    # faixa fina de obras (2o nivel de navegacao) — mesma lista de /app/obras,
    # so' que compactada ao lado do painel de abas desta obra especifica.
    obras_do_membro = (
        repo.listar_todas_obras(conn)
        if access.eh_dono(membro)
        else repo.listar_obras_por_membro(conn, membro["id"])
    )
    jobs = repo.listar_jobs_por_obra(conn, obra_id)
    n5_releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    comentarios = repo.listar_comentarios_por_obra(conn, obra_id)
    documentos = repo.listar_documentos_por_obra(conn, obra_id)
    resumo_documentos = repo.contar_documentos_por_status(conn, obra_id)
    # [2026-07-06] "rápida" = upload legado de 1 arquivo (arquivo_nome preenchido,
    # sem linhas em portal_documentos) — pula triagem/recortes, vai direto pra SA.
    # "container" (novo modelo) tem documentos e nunca popula arquivo_nome.
    eh_obra_rapida = bool(obra.get("arquivo_nome")) and not documentos
    rotulos = {
        c: certification.classificar_certificacao(settings.status_md_path, c)
        for c in ("PL", "LV", "FV", "LJ")
    }
    # fichas HTML disponíveis (viewer) — [FIX 2026-07-06] ver
    # pipeline_runner.encontrar_dir_fichas: o SA real grava em
    # <obra_dir>/<pavimento>_<run_id>/, nao em "Fase-6_Execucao_CAD".
    from .. import pipeline_runner as _pipeline_runner

    fichas: list[dict] = []
    lp = obra.get("local_path")
    obra_dir = (Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra"))
    base = _pipeline_runner.encontrar_dir_fichas(obra_dir)
    if base is not None:
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
        "obras_do_membro": obras_do_membro,
        "jobs": jobs,
        "fichas": fichas,
        "comentarios": comentarios,
        "documentos": documentos,
        "resumo_documentos": resumo_documentos,
        "eh_obra_rapida": eh_obra_rapida,
        "n5_releases": n5_releases,
        "rotulos": rotulos,
        "etapa_atual": etapa_atual,
        # [FIX 2026-07-06] antes so' calculava com etapa_atual==3 (assumia que
        # "processando" so' acontecia na etapa SA) — agora triagem/recortes
        # tambem tem job proprio rodando em qualquer etapa (1/2/3).
        "job_ativo": _job_ativo(jobs),
        "validacao_concluida": validacao_concluida,
        "pavimento": settings.pav_default,
        "classe_ativa": None,
        "item_id": None,
        "nav_ativo": "obras",
    }
    return _render(request, "obra_detalhe.html", ctx)


# --------------------------------------------------------------------------- #
# /status — publica docs/STATUS.md no portal (P5, achado pendente no DevOps
# handoff: "rota /status nao existe no app" — 2026-07-06).
# --------------------------------------------------------------------------- #

@router.get("/app/status", response_class=HTMLResponse)
def pagina_status(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    """STATUS.md (gerado por scripts/arete/gerar_status.py) servido como HTML.

    So' LEITURA — o portal nunca escreve nesse arquivo. Visivel a qualquer membro
    logado (mesma info de certificacao ja exposta por classe nas obras; nada novo
    exposto). Sem STATUS.md ainda gerado -> mensagem clara, nao erro.
    """
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)

    settings = request.app.state.settings
    status_path = Path(settings.status_md_path)
    if not status_path.exists():
        html_corpo = (
            "<p><em>docs/STATUS.md ainda não foi gerado. Rode "
            "<code>python scripts/arete/gerar_status.py</code> no servidor.</em></p>"
        )
        gerado_em = None
    else:
        import markdown as _markdown

        texto = status_path.read_text(encoding="utf-8", errors="replace")
        html_corpo = _markdown.markdown(texto, extensions=["tables"])
        gerado_em = status_path.stat().st_mtime

    return _render(request, "status.html", {
        "membro": membro, "html_corpo": html_corpo, "gerado_em": gerado_em, "nav_ativo": "status",
    })


def setup_templates(app) -> None:
    """Monta o Jinja2Templates em app.state (chamado por create_app)."""
    from fastapi.templating import Jinja2Templates

    app.state.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
