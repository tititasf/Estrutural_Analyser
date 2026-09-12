"""Apontamentos visuais comunitarios: persistencia, acesso e UI."""

from __future__ import annotations

import base64
import contextlib
import json

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo


@contextlib.asynccontextmanager
async def _client(settings):
    conn = connection.init_db(settings.db_path)
    repo.criar_membro(
        conn, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    conn.close()
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def _obra(settings) -> str:
    conn = connection.init_db(settings.db_path)
    membro = repo.obter_membro_por_login(conn, "ana")
    obra_id = repo.criar_obra(
        conn, membro_id=membro["id"], nome="Obra Feedback",
        pasta_drive_id="folder-ana", estado="pronta",
    )
    conn.close()
    return obra_id


def _payload(*, captura: str | None = None) -> dict:
    return {
        "texto": "Este botao deveria explicar o resultado.",
        "pagina_url": "https://portal.test/app/obras/obra?pavimento=13_PAV",
        "pagina_titulo": "Obra Feedback",
        "seletor_elemento": "#btn-processar",
        "elemento_tag": "button",
        "elemento_role": "button",
        "elemento_texto": "Processar",
        "elemento": {"tag": "button", "attributes": {"id": "btn-processar"}},
        "clique_x": 410.5,
        "clique_y": 220.25,
        "pagina_x": 410.5,
        "pagina_y": 1320.25,
        "viewport_largura": 1280,
        "viewport_altura": 720,
        "captura_data_url": captura,
    }


def _insert_point(conn, *, obra_id, membro_id, texto):
    return repo.inserir_apontamento_ui(
        conn, obra_id=obra_id, membro_id=membro_id, texto=texto,
        pagina_url="https://portal.test/app/obras", pagina_titulo="Portal",
        seletor_elemento="#alvo", elemento_tag="button", elemento_role="button",
        elemento_texto="Alvo", elemento_json=json.dumps({"tag": "button"}),
        clique_x=10, clique_y=20, pagina_x=10, pagina_y=20,
        viewport_largura=1280, viewport_altura=720,
        captura_mime=None, captura_blob=None,
    )


def test_historico_global_e_identificado_mantem_visibilidade_das_obras(settings):
    conn = connection.init_db(settings.db_path)
    ana_id = repo.criar_membro(conn, login="ana-db", nome="Ana", senha_hash="h")
    bia_id = repo.criar_membro(conn, login="bia-db", nome="Bia", senha_hash="h")
    dono_id = repo.criar_membro(conn, login="dono-db", nome="Dono", senha_hash="h", papel="dono")
    obra_ana = repo.criar_obra(conn, membro_id=ana_id, nome="Obra Ana", pasta_drive_id="a")
    obra_bia = repo.criar_obra(conn, membro_id=bia_id, nome="Obra Bia", pasta_drive_id="b")
    _insert_point(conn, obra_id=None, membro_id=ana_id, texto="geral")
    _insert_point(conn, obra_id=obra_ana, membro_id=ana_id, texto="ana")
    ponto_bia = _insert_point(conn, obra_id=obra_bia, membro_id=bia_id, texto="bia")
    ana = repo.obter_membro_por_login(conn, "ana-db")
    bia = repo.obter_membro_por_login(conn, "bia-db")
    dono = repo.obter_membro_por_login(conn, "dono-db")

    assert {p["texto"] for p in repo.listar_apontamentos_ui(conn, membro=ana)} == {"geral", "ana"}
    assert {p["texto"] for p in repo.listar_apontamentos_ui(conn, membro=bia)} == {"geral", "bia"}
    assert len(repo.listar_apontamentos_ui(conn, membro=dono)) == 3
    assert {p["texto"] for p in repo.listar_apontamentos_ui(conn, membro=ana, somente_meus=True)} == {"geral", "ana"}
    assert repo.pode_ver_apontamento_ui(conn, repo.obter_apontamento_ui(conn, ponto_bia), ana) is False
    assert repo.pode_ver_apontamento_ui(conn, repo.obter_apontamento_ui(conn, ponto_bia), dono) is True
    conn.close()


@pytest.mark.asyncio
async def test_apontamento_ui_persiste_autor_contexto_e_captura(settings):
    async with _client(settings) as client:
        obra_id = _obra(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        imagem = b"\x89PNG\r\n\x1a\nfixture"
        captura = "data:image/png;base64," + base64.b64encode(imagem).decode("ascii")

        created = await client.post(
            "/apontamentos-ui", json={**_payload(captura=captura), "obra_id": obra_id},
        )
        assert created.status_code == 200
        apontamento_id = created.json()["apontamento_id"]

        listed = await client.get("/apontamentos-ui")
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 1
        point = body["apontamentos"][0]
        assert point["autor_login"] == "ana"
        assert point["tem_captura"] is True
        assert point["elemento"]["attributes"]["id"] == "btn-processar"
        assert "captura_blob" not in point

        response = await client.get(
            f"/apontamentos-ui/{apontamento_id}/captura",
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == imagem


@pytest.mark.asyncio
async def test_apontamento_ui_exige_login_e_valida_captura(settings):
    async with _client(settings) as client:
        obra_id = _obra(settings)
        assert (await client.get("/apontamentos-ui")).status_code == 401
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        invalid = await client.post(
            "/apontamentos-ui",
            json={**_payload(captura="data:text/plain;base64,SGVsbG8="), "obra_id": obra_id},
        )
        assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_pagina_da_obra_expoe_botoes_e_runtime_de_apontamento(settings):
    async with _client(settings) as client:
        obra_id = _obra(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        page = await client.get(f"/app/obras/{obra_id}")
        assert page.status_code == 200
        assert "Fazer apontamento" in page.text
        assert "Ver apontamentos" in page.text
        assert "/static/html2canvas.min.js?v=1.4.1" in page.text
        assert "/static/ui_feedback.js?v=" in page.text
        assert "ui-feedback-dialog" in page.text

        # O recurso e' do portal inteiro, nao da obra: a listagem global tambem
        # mostra os acessos e inicializa o contexto com obra opcional nula.
        global_page = await client.get("/app/obras")
        assert global_page.status_code == 200
        assert "Fazer apontamento" in global_page.text
        assert "Ver apontamentos" in global_page.text
        assert "obraId: null" in global_page.text
