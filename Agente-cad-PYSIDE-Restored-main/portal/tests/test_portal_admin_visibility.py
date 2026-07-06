"""Visibilidade do papel 'dono' (2026-07-06) — vê obras de TODOS os membros.

O schema (portal_membros.papel CHECK IN ('membro','dono')) já previa isso, mas
nenhum endpoint usava — cada rota checava `obra["membro_id"] != membro["id"]`
direto, o que bloquearia até o dono de ver obras de outros. Ver portal/app/access.py
(regra centralizada) e os 5 routers que passaram a usá-la.

Usa httpx.ASGITransport pelo mesmo motivo do test_portal_http_flow.py — o
fastapi.testclient.TestClient está quebrado nesta máquina (starlette 0.27 + httpx
0.28.1).
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
    """Semeia 'ana' (membro comum) e 'chefe' (papel='dono') ANTES do lifespan."""
    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    repo.criar_membro(
        c, login="chefe", nome="O Dono", papel="dono",
        senha_hash=auth.hash_senha("segredosuper"),
    )
    c.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


def _obra_da_ana(settings, arquivo_hash: str = "hash-admin-1") -> str:
    c = connection.init_db(settings.db_path)
    try:
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="ObraDaAna", pasta_drive_id="folder-ana",
            arquivo_hash=arquivo_hash, estado="aguardando_ingestao",
        )
        return obra_id
    finally:
        c.close()


async def _login(client: httpx.AsyncClient, login: str, senha: str) -> None:
    r = await client.post("/login", json={"login": login, "senha": senha})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_dono_ve_obra_de_outro_membro_na_listagem(settings):
    """GET /obras do dono inclui a obra da ana, com membro_login/membro_nome."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)

        await _login(client, "chefe", "segredosuper")
        r = await client.get("/obras")
        assert r.status_code == 200
        body = r.json()
        assert body["papel"] == "dono"
        achada = next((o for o in body["obras"] if o["id"] == obra_id), None)
        assert achada is not None, "dono deveria ver a obra da ana na listagem"
        assert achada["membro_login"] == "ana"
        assert achada["membro_nome"] == "Ana Silva"


@pytest.mark.asyncio
async def test_dono_abre_detalhe_de_obra_de_outro_membro(settings):
    """GET /obras/{id} do dono NÃO recebe 403 numa obra que não é dele."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)

        await _login(client, "chefe", "segredosuper")
        r = await client.get(f"/obras/{obra_id}")
        assert r.status_code == 200, r.text
        assert r.json()["obra"]["id"] == obra_id


@pytest.mark.asyncio
async def test_membro_comum_continua_isolado_das_obras_de_outros(settings):
    """Regressão: 'ana' (papel='membro') NÃO ganha acesso a obra alheia."""
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        chefe = repo.obter_membro_por_login(c, "chefe")
        obra_do_chefe = repo.criar_obra(
            c, membro_id=chefe["id"], nome="ObraDoChefe", pasta_drive_id="folder-chefe",
            arquivo_hash="hash-admin-2", estado="aguardando_ingestao",
        )
        c.close()

        await _login(client, "ana", "segredo123")

        # não aparece na listagem da ana
        r = await client.get("/obras")
        assert r.status_code == 200
        assert all(o["id"] != obra_do_chefe for o in r.json()["obras"])

        # e o acesso direto continua barrado
        r = await client.get(f"/obras/{obra_do_chefe}")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_dono_pode_disparar_etapa_em_obra_de_outro_membro(settings):
    """Dono também pode agir (não só ver) sobre obra alheia — governança única (masterplan §)."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)

        await _login(client, "chefe", "segredosuper")
        r = await client.post(f"/obras/{obra_id}/triagem")
        assert r.status_code == 200, r.text
        assert r.json()["job_id"]
