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

import inspect
import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from .. import access, auth, certification, public_codes_lookup, viewer_pavimentos
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(tags=["paginas"], include_in_schema=False)

# templates montados em setup_templates() a partir de create_app (injeta o env)
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _templates(request: Request):
    """Recupera o Jinja2Templates guardado em app.state (montado no create_app)."""
    return request.app.state.templates


@lru_cache(maxsize=1)
def _request_e_posicional() -> bool:
    """A starlette instalada quer TemplateResponse(request, name, ctx)?

    Detecta em runtime em vez de fixar uma versao. Historico: em 2026-07-06 o
    codigo foi trocado para a forma posicional, revertido por engano para a forma
    antiga (starlette 0.27), e em 2026-07-30 o ambiente subiu para starlette 1.3.1
    — que REMOVEU a forma antiga, derrubando todas as telas HTML do portal com
    "TypeError: unhashable type: 'dict'" (o dict de contexto ia parar no lugar do
    nome do template e chegava como chave no LRUCache do jinja2).

    Fixar versao aqui ja falhou duas vezes nos dois sentidos. Perguntar a
    assinatura funciona nos dois mundos.
    """
    try:
        params = list(
            inspect.signature(Jinja2Templates.TemplateResponse).parameters
        )
    except (TypeError, ValueError):  # pragma: no cover - assinatura opaca
        return False
    # antiga: (self, name, context, ...) | nova: (self, request, name, context, ...)
    return len(params) > 1 and params[1] == "request"


def _render(request: Request, template_name: str, ctx: dict):
    # "request" segue no contexto nos dois casos: os templates usam url_for(),
    # que exige request no namespace do Jinja.
    ctx = {**ctx, "request": request}
    templates = _templates(request)
    if _request_e_posicional():
        return templates.TemplateResponse(request, template_name, ctx)
    return templates.TemplateResponse(template_name, ctx)


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
    eh_dono = access.eh_dono(membro)
    obras = (
        repo.listar_todas_obras(conn)
        if eh_dono
        else repo.listar_obras_por_membro(conn, membro["id"])
    )
    # Já vêm ORDER BY created_at DESC; agrupa por dono p/ sidebar + tabela
    # (dono vê blocos «Lista de Obras — {usuário}»; membro só o próprio).
    meu_nome = (membro.get("nome") or membro.get("login") or "").strip() or "—"
    grupos_map: dict[str, list] = {}
    ordem_donos: list[str] = []
    for o in obras:
        dono = (o.get("membro_nome") or o.get("membro_login") or meu_nome or "—").strip()
        if dono not in grupos_map:
            grupos_map[dono] = []
            ordem_donos.append(dono)
        grupos_map[dono].append(o)
    # dono logado primeiro; demais na ordem de primeira aparição (já por data)
    if meu_nome in grupos_map:
        ordem_donos = [meu_nome] + [d for d in ordem_donos if d != meu_nome]
    obras_por_membro = [{"dono": d, "obras": grupos_map[d]} for d in ordem_donos]

    drive = request.app.state.estado_global.get("drive", "ok")
    drive_folder_url = (
        f"https://drive.google.com/drive/folders/{membro['drive_folder_id']}"
        if membro.get("drive_folder_id") else None
    )
    settings = request.app.state.settings
    codigos_publicos = public_codes_lookup.buscar_codes_obras_batch(
        settings.public_consulta_db_path, [o["id"] for o in obras],
    )
    return _render(request, "obras_lista.html", {
        "membro": membro, "obras": obras, "obras_por_membro": obras_por_membro,
        "drive": drive, "drive_folder_url": drive_folder_url,
        "codigos_publicos": codigos_publicos, "nav_ativo": "obras",
        "eh_dono": eh_dono, "meu_nome": meu_nome,
    })


# --------------------------------------------------------------------------- #
# Viewer do estrutural limpo (P2)
# --------------------------------------------------------------------------- #

@router.get("/app/obras/{obra_id}/viewer/{pavimento}", response_class=HTMLResponse)
def pagina_viewer(
    obra_id: str, pavimento: str, request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Tela do estrutural limpo com destaque por classe.

    A página só monta o palco; os dados vêm por fetch de
    `/obras/{id}/viewer/{pav}` (viewer_routes), que já resolve fonte, transform e
    itens. Assim o contrato do viewer vive num lugar só.
    """
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)
    obra = repo.obter_obra(conn, obra_id)
    if obra is None or not access.pode_ver_obra(obra, membro):
        return RedirectResponse("/app/obras", status_code=303)

    # Pavimentos que TÊM torre limpa — é o que o seletor pode oferecer. Oferecer
    # um pavimento sem torre só produziria 409 depois do clique.
    settings = request.app.state.settings
    lp = obra.get("local_path")
    obra_dir = Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")
    pavimentos = viewer_pavimentos.listar_pavimentos_com_torre(obra_dir, obra)

    return _render(request, "viewer.html", {
        "membro": membro, "obra": obra, "pavimento": pavimento,
        "pavimentos": pavimentos, "nav_ativo": "obras",
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
    try:
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
        jobs = [dict(j) for j in repo.listar_jobs_por_obra(conn, obra_id)]
        for j in jobs:
            j["meta"] = request.app.state.job_meta.get(j["id"], {})
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
        pavimento_fichas = request.query_params.get("pavimento") or settings.pav_default
        base = _pipeline_runner.encontrar_dir_fichas(obra_dir, pavimento_fichas)
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
            "pavimento": pavimento_fichas,
            # Pavimentos com estrutural limpo — um link de viewer por pavimento.
            "pavimentos_viewer": viewer_pavimentos.listar_pavimentos_com_torre(
                obra_dir, obra
            ),
            "classe_ativa": None,
            "item_id": None,
            "nav_ativo": "obras",
        }

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # [2026-07-30] Removida a escrita de C:/Users/Thierry/Desktop/err_pagina.txt
        # (caminho de Desktop fixo num processo de servidor). Vai para o log, e o
        # corpo da resposta deixa de expor stack trace ao usuario.
        logging.getLogger("portal.paginas_routes").exception(
            "obra_detalhe falhou: obra=%s", obra_id
        )
        raise HTTPException(status_code=500, detail=f"falha ao montar a pagina: {exc}") from exc
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
