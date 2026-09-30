"""Apontamentos visuais comunitarios: persistencia, acesso e UI."""

from __future__ import annotations

import base64
import contextlib
import json
from pathlib import Path

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


def test_historico_isolado_por_membro_e_dono_ve_todos(settings):
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

    # [2026-09-28] Isolamento entre perfis: cada membro só vê os próprios.
    assert {p["texto"] for p in repo.listar_apontamentos_ui(conn, membro=ana)} == {"geral", "ana"}
    assert {p["texto"] for p in repo.listar_apontamentos_ui(conn, membro=bia)} == {"bia"}
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
        assert 'aria-labelledby="ui-feedback-dialog-title"' in page.text
        assert 'aria-describedby="ui-feedback-dialog-subtitle"' in page.text
        assert 'role="list"' in page.text
        assert 'aria-live="assertive"' in page.text

        # O recurso e' do portal inteiro, nao da obra: a listagem global tambem
        # mostra os acessos e inicializa o contexto com obra opcional nula.
        global_page = await client.get("/app/obras")
        assert global_page.status_code == 200
        assert "Fazer apontamento" in global_page.text
        assert "Ver apontamentos" in global_page.text
        assert "obraId: null" in global_page.text


def test_captura_achata_svg_cad_complexo_sem_reduzir_resolucao():
    runtime = (
        Path(__file__).parents[1] / "app" / "static" / "ui_feedback.js"
    ).read_text(encoding="utf-8")

    assert "function rasterizeSvg" in runtime
    assert "data-ui-feedback-capture-raster" in runtime
    assert "svg.getElementsByTagName('*').length > 80" in runtime
    assert "Math.min(Math.max(window.devicePixelRatio || 1, 1), 1.25)" in runtime
    assert "replaceChild(entry.original, entry.replacement)" in runtime
    assert "function pageState()" in runtime
    assert "visibleSvgViewBoxes" in runtime
    assert "function markTarget" in runtime
    assert "data:image/webp" in runtime
    assert "selectionSequence" in runtime
    assert "indexedDB.open('cad-portal-ui-feedback'" in runtime
    assert "Continuar apontamento" in runtime
    assert "ui-feedback-capture-stage" in runtime
    assert "ui-feedback-comments-pane" in runtime
    assert "data-ui-feedback-show-point" in runtime
    assert "page.activePoint=page.points.length-1" in runtime
    assert "Abrir estado registrado" in runtime
    assert "Abrir estado deste ponto" in runtime
    assert "RESTORE_PARAM = '_apontamento'" in runtime
    assert "window.DrillGrade.openSaClasse" in runtime
    assert "visibleSvgViewBoxes" in runtime
    assert "scrollContainers" in runtime
    assert "function renderSavedSession" in runtime
    assert "data-ui-feedback-view-session" in runtime
    assert "data-ui-feedback-view-page" in runtime
    assert "data-ui-feedback-view-point" in runtime
    assert "function setupImageZoom" in runtime
    assert "data-ui-feedback-zoom-reset" in runtime
    assert "viewport.addEventListener('wheel'" in runtime
    assert "viewport.addEventListener('pointermove'" in runtime
    assert "Math.min(6" in runtime
    template = (Path(__file__).parents[1] / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    assert "Adicionar mais pontuação" in template
    assert "Adicionar nova página" in template
    assert "ui-feedback-session-viewer" in template
    assert "← Todos os apontamentos" in template


@pytest.mark.asyncio
async def test_apontamento_ui_preserva_contexto_tecnico_v2(settings):
    async with _client(settings) as client:
        obra_id = _obra(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        contexto = {
            "version": 2,
            "target": {"tag": "div", "selector": "#n1-detalhe-painel"},
            "pageState": {
                "context": {"item": "L301", "layer": "n3"},
                "scroll": {"x": 0, "y": 540},
                "visibleSvgViewBoxes": [
                    {"selector": "#n1-detalhe-painel svg", "viewBox": {"x": 1, "y": 2, "width": 3, "height": 4}},
                ],
            },
            "capture": {"mime": "image/webp"},
        }
        created = await client.post(
            "/apontamentos-ui",
            json={**_payload(), "obra_id": obra_id, "elemento": contexto},
        )
        assert created.status_code == 200

        point = (await client.get("/apontamentos-ui")).json()["apontamentos"][0]
        assert point["elemento"] == contexto


@pytest.mark.asyncio
async def test_sessao_ui_agrupa_paginas_pontos_e_capturas_atomicamente(settings):
    async with _client(settings) as client:
        obra_id = _obra(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        imagem = b"\x89PNG\r\n\x1a\nfixture-session"
        captura = "data:image/png;base64," + base64.b64encode(imagem).decode("ascii")
        p1 = _payload(captura=captura)
        p2 = {**_payload(), "texto": "Segundo ponto na mesma pagina", "clique_x": 620}
        p3 = {**_payload(), "texto": "Ponto em outra pagina", "pagina_url": "https://portal.test/app/status"}
        response = await client.post("/apontamentos-ui/sessoes", json={
            "obra_id": obra_id,
            "titulo": "Revisao completa da laje",
            "paginas": [
                {"pagina_url": p1["pagina_url"], "pagina_titulo": "Laje", "pontos": [p1, p2]},
                {"pagina_url": p3["pagina_url"], "pagina_titulo": "Status", "pontos": [p3]},
            ],
        })
        assert response.status_code == 200
        assert response.json()["paginas"] == 2
        assert response.json()["pontos"] == 3

        listed = (await client.get("/apontamentos-ui/sessoes")).json()
        assert listed["total"] == 1
        session = listed["sessoes"][0]
        assert session["titulo"] == "Revisao completa da laje"
        assert [len(page["pontos"]) for page in session["paginas"]] == [2, 1]
        capture_id = session["paginas"][0]["pontos"][0]["id"]
        capture_response = await client.get(f"/apontamentos-ui/{capture_id}/captura")
        assert capture_response.content == imagem
