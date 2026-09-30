"""Testes HTTP das rotas de validação de campo (2026-07-13 — selo rosa).

Diferente de `test_portal_n1_routes.py`, não depende de nenhuma obra real
processada nesta máquina: cria um `estado_<pav>.json` mínimo (vazio) só pra
`ficha_reader.descobrir_pavimentos` resolver o pavimento — os endpoints de
validação de campo não leem conteúdo nenhum desse arquivo.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

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


def _obra_com_pavimento_falso(settings, tmp_path: Path, pavimento: str = "Terreo") -> str:
    obra_dir = tmp_path / "ObraCampo"
    obra_dir.mkdir(parents=True, exist_ok=True)
    (obra_dir / f"estado_{pavimento}.json").write_text("{}", encoding="utf-8")
    c = connection.init_db(settings.db_path)
    ana = repo.obter_membro_por_login(c, "ana")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraCampo", pasta_drive_id="folder-ana",
        arquivo_hash="hash-campo", estado="pronta", local_path=str(obra_dir),
    )
    c.close()
    return obra_id


@pytest.mark.asyncio
async def test_validar_campo_grava_e_retorna_ok(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_pavimento_falso(settings, tmp_path)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post(
            f"/obras/{obra_id}/n1/pilares/P1/campo/nivel/validar",
            json={"validado": True},
        )
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "status": "ok", "pavimento": "Terreo", "classe": "pilares",
            "item_id": "P1", "field_id": "nivel", "validado": True,
        }


@pytest.mark.asyncio
async def test_listar_campos_validados_de_um_item(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_pavimento_falso(settings, tmp_path)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        await client.post(f"/obras/{obra_id}/n1/pilares/P1/campo/nivel/validar", json={"validado": True})
        await client.post(f"/obras/{obra_id}/n1/pilares/P1/campo/classificacao/validar", json={"validado": True})
        r = await client.get(f"/obras/{obra_id}/n1/pilares/P1/campos-validados")
        assert r.status_code == 200
        body = r.json()
        assert body["pavimento"] == "Terreo"
        assert {c["field_id"] for c in body["campos"]} == {"nivel", "classificacao"}
        assert all(c["validado_por"] == "ana" for c in body["campos"])


@pytest.mark.asyncio
async def test_desvalidar_campo_remove_da_lista(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_pavimento_falso(settings, tmp_path)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        await client.post(f"/obras/{obra_id}/n1/pilares/P1/campo/nivel/validar", json={"validado": True})
        r = await client.post(f"/obras/{obra_id}/n1/pilares/P1/campo/nivel/validar", json={"validado": False})
        assert r.status_code == 200
        assert r.json()["validado"] is False
        campos = (await client.get(f"/obras/{obra_id}/n1/pilares/P1/campos-validados")).json()["campos"]
        assert campos == []


@pytest.mark.asyncio
async def test_listar_campos_validados_por_obra_agrega_tudo(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_pavimento_falso(settings, tmp_path)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        await client.post(f"/obras/{obra_id}/n1/pilares/P1/campo/nivel/validar", json={"validado": True})
        await client.post(f"/obras/{obra_id}/n1/lajes/L2/campo/laje_dim/validar", json={"validado": True})
        r = await client.get(f"/obras/{obra_id}/campos-validados")
        assert r.status_code == 200
        campos = r.json()["campos"]
        assert len(campos) == 2
        chaves = {(c["classe"], c["item_id"], c["field_id"]) for c in campos}
        assert ("PILARES", "P1", "nivel") in chaves
        assert ("LAJES", "L2", "laje_dim") in chaves


@pytest.mark.asyncio
async def test_validar_campo_sem_pavimento_da_404(settings, tmp_path):
    """Obra sem nenhum estado_<pav>.json (SA nunca rodou) -> 404 honesto,
    igual o resto das rotas N1 já faz pra outros endpoints de item."""
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="ObraSemSA", pasta_drive_id="folder-ana",
            arquivo_hash="hash-sem-sa", estado="aguardando_ingestao",
        )
        c.close()
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post(f"/obras/{obra_id}/n1/pilares/P1/campo/nivel/validar", json={"validado": True})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_validar_campo_de_obra_de_outro_membro_e_recusado_403(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        bruno = repo.criar_membro(c, login="bruno", nome="Bruno",
                                  senha_hash=auth.hash_senha("x"), drive_folder_id="folder-bruno")
        obra_bruno = repo.criar_obra(c, membro_id=bruno, nome="ObraBruno",
                                     pasta_drive_id="folder-bruno", arquivo_hash="h-bruno")
        c.close()
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post(f"/obras/{obra_bruno}/n1/pilares/P1/campo/nivel/validar", json={"validado": True})
        assert r.status_code == 403
