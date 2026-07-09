"""GET real nas 4 páginas HTML server-rendered (login, lista, detalhe, status).

Achado 2026-07-06: as 4 rotas de página (`portal/app/routers/paginas_routes.py`)
chamavam `TemplateResponse(request, nome, ctx)` — convenção que a versão instalada
de `starlette` (0.27.0) NÃO aceita (assinatura real: `TemplateResponse(name, context)`,
sem `request` posicional). Toda página quebrava com `ValueError: context must
include a "request" key` no primeiro acesso via navegador. NENHUM teste anterior
tinha feito um GET real numa página HTML (só nas rotas JSON) — corrigido com um
helper `_render()` centralizado; este arquivo garante que as 4 páginas continuam
renderizando de verdade, não só que "não dá erro de import".
"""

from __future__ import annotations

import contextlib

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo


@contextlib.asynccontextmanager
async def _app_cliente(settings):
    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    c.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


@pytest.mark.asyncio
async def test_pagina_login_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        r = await client.get("/login")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "<form" in r.text  # formulário de login real, não stack trace


@pytest.mark.asyncio
async def test_pagina_obras_vazia_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/obras")
        assert r.status_code == 200
        assert "Minhas obras" in r.text
        assert "Nenhuma obra detectada ainda" in r.text  # estado vazio real (copy 2026-07-06)
        assert "Criar obra nova" in r.text  # cartão principal: obra-como-container (2026-07-06)


@pytest.mark.asyncio
async def test_pagina_obras_com_dados_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)  # ana já seedada por _app_cliente
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="EdificioAurora", pasta_drive_id="folder-ana",
            arquivo_hash="hash-pagina-1", estado="pronta",
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/obras")
        assert r.status_code == 200
        assert "EdificioAurora" in r.text
        assert f'/app/obras/{obra_id}' in r.text  # link real para o detalhe


@pytest.mark.asyncio
async def test_pagina_obra_detalhe_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="TorreCentral", pasta_drive_id="folder-ana",
            arquivo_hash="hash-pagina-2", estado="aguardando_ingestao",
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/app/obras/{obra_id}")
        assert r.status_code == 200
        assert "TorreCentral" in r.text


@pytest.mark.asyncio
async def test_paginas_sem_sessao_redirecionam_para_login(settings):
    async with _app_cliente(settings) as (_app, client):
        for path in ("/app/obras", "/app/status"):
            r = await client.get(path, follow_redirects=False)
            assert r.status_code == 303, f"{path} deveria redirecionar sem sessão"
            assert r.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# Regressão 2026-07-06 — `_etapa_atual` pulava Recortes/SA quando SÓ a triagem
# tinha rodado, porque TODO job bem-sucedido (mesmo triagem sozinha) marcava a
# obra "pronta" — achado testando de verdade o modo rápido (obra do usuário:
# "nao pula o recorte... o pavimento rapido deve ter essa fase tambem").
# --------------------------------------------------------------------------- #

def test_etapa_atual_usa_etapa_concluida_nao_so_estado():
    from portal.app.routers.paginas_routes import _etapa_atual

    # nada rodou ainda -> etapa 1 (Triagem)
    assert _etapa_atual({"estado": "aguardando_ingestao", "etapa_concluida": None}, [], []) == 1
    # so' a triagem terminou -> etapa 2 (Recortes) — NAO pula pra Validação
    assert _etapa_atual({"estado": "processando", "etapa_concluida": "triagem"}, [], []) == 2
    # recortes tambem terminou -> etapa 3 (SA) — ainda nao e' "pronta"
    assert _etapa_atual({"estado": "processando", "etapa_concluida": "recortes"}, [], []) == 3
    # SA terminou -> etapa 4 (Validação)
    assert _etapa_atual({"estado": "pronta", "etapa_concluida": "sa"}, [], []) == 4
    # erro tentando recortes (triagem ja tinha passado) -> continua mostrando
    # a etapa que falhou (2), nao reseta pra 1
    assert _etapa_atual({"estado": "erro", "etapa_concluida": "triagem"}, [], []) == 2
    # release N5 sempre manda pra etapa 5,
    # independente do que etapa_concluida diga
    assert _etapa_atual({"estado": "pronta", "etapa_concluida": "sa"}, [], [{"id": "r1"}]) == 5


@pytest.mark.asyncio
async def test_pagina_obra_detalhe_nao_pula_recortes_apos_so_triagem(settings):
    """Reproduz de verdade o bug: roda 1 job de triagem (via processar_um_job,
    o mesmo caminho do worker real) e confirma que a PÁGINA mostra "Recortes"
    como próxima etapa — não "Validação" (que exigiria SA já ter rodado)."""
    from portal.app import jobs as jobs_mod

    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="ObraSoTriagem", pasta_drive_id="folder-ana",
            arquivo_hash="hash-so-triagem", estado="aguardando_ingestao",
        )
        job_id = repo.enfileirar_job(c, obra_id=obra_id)
        job = repo.consumir_job(c)
        assert job["id"] == job_id

        class _AppStateFake:
            def __init__(self, settings_obj, conn_obj):
                self.settings = settings_obj
                self.db = conn_obj
                self.job_meta = {job_id: {"etapa": "triagem"}}

        import unittest.mock as mock
        with mock.patch.object(
            jobs_mod.pipeline_runner, "executar_etapa",
            return_value=type("R", (), {"ok": True, "log_tail": "", "artefatos": {}})(),
        ), mock.patch.object(jobs_mod, "wait_for_lock", return_value=(object(), None)), \
           mock.patch.object(jobs_mod, "release_lock", lambda *a, **k: None):
            jobs_mod.processar_um_job(_AppStateFake(settings, c), job)

        obra_depois = repo.obter_obra(c, obra_id)
        assert obra_depois["etapa_concluida"] == "triagem"
        assert obra_depois["estado"] != "pronta"  # NAO pode marcar pronta so' com triagem

        # [novo 2026-07-08, a pedido do dono] a triagem agora encadeia recortes
        # automaticamente (jobs.py, apos triagem terminar com sucesso) — sem
        # o usuario precisar clicar num botao separado. Confirma que o job de
        # recortes foi enfileirado de verdade pra essa obra.
        jobs_da_obra = repo.listar_jobs_por_obra(c, obra_id)
        assert any(j["id"] != job_id for j in jobs_da_obra), (
            "esperava um job de recortes encadeado apos a triagem"
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/app/obras/{obra_id}")
        assert r.status_code == 200
        # [FIX 2026-07-06] navegação nunca mais bloqueia — a etapa_concluida
        # real é o que importa (ja verificado acima), nao a presenca de um
        # botao especifico. [ATUALIZADO 2026-07-08] o botão "Rodar recortes"
        # isolado foi eliminado a pedido do dono — recortes agora roda
        # encadeado automaticamente logo após a Triagem (botão único "Triagem
        # + Recortes"); a seção "Recortes" continua sempre visível/informativa.
        # O job de recortes encadeado ainda está "na_fila" (o teste não roda o
        # JobWorker de verdade) — job_ativo fica true e os botões mostram
        # "Job em andamento…" em vez do texto normal, comportamento esperado.
        assert "Recortes" in r.text
        assert "Job em andamento" in r.text
        # recortes ainda nao rodaram -> aba SA avisa (nao bloqueia, so' informa)
        assert "recortes ainda não terminaram" in r.text
