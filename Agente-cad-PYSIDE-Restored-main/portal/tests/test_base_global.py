"""Aba Base Global (2026-09-26): só o dono vê — menu, página e o JSON do grafo."""

from __future__ import annotations

import pytest

from portal.app.routers import base_global_routes
from portal.tests.test_portal_admin_visibility import _app_cliente, _login


@pytest.mark.asyncio
async def test_dono_ve_aba_pagina_e_grafo(settings):
    async with _app_cliente(settings) as (_app, client):
        await _login(client, "chefe", "segredosuper")
        r = await client.get("/app/obras")
        assert r.status_code == 200 and "/app/base-global" in r.text
        r = await client.get("/app/base-global")
        assert r.status_code == 200 and "bg-grafo" in r.text
        if base_global_routes.GRAFO_JSON.exists():
            r = await client.get("/app/base-global/grafo.json")
            assert r.status_code == 200
            g = r.json()
            assert {"nos", "arestas", "lacunas", "cobertura"} <= set(g)


@pytest.mark.asyncio
async def test_membro_comum_nao_ve_nada(settings):
    async with _app_cliente(settings) as (_app, client):
        await _login(client, "ana", "segredo123")
        r = await client.get("/app/obras")
        assert r.status_code == 200 and "/app/base-global" not in r.text
        assert (await client.get("/app/base-global")).status_code == 404
        assert (await client.get("/app/base-global/grafo.json")).status_code == 404


@pytest.mark.asyncio
async def test_sem_sessao_vai_para_login(settings):
    async with _app_cliente(settings) as (_app, client):
        r = await client.get("/app/base-global")
        assert r.status_code == 303 and r.headers["location"] == "/login"
        assert (await client.get("/app/base-global/grafo.json")).status_code == 401
