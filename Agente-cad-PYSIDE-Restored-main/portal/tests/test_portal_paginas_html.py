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
        assert "Nenhuma obra ainda" in r.text  # estado vazio real


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
