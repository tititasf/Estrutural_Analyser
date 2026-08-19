from __future__ import annotations

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
    membro = repo.criar_membro(
        conn, login="ana", nome="Ana", senha_hash=auth.hash_senha("segredo123"),
        drive_folder_id="folder-ana",
    )
    obra_dir = settings.dados_obras_dir / "ObraPilarWeb"
    obra_dir.mkdir(parents=True)
    estado = {
        "pilares": [{
            "name": "P1", "classification": "Pilar",
            "points": [[0, 0], [66, 0], [66, 19], [0, 19], [0, 0]],
        }],
        "slabs": [], "cortes": [], "segmentos": {},
    }
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")
    robot_dir = obra_dir / "Fase-4_Sincronizacao" / "JSON_Pilares"
    robot_dir.mkdir(parents=True)
    (robot_dir / "P1.json").write_text(json.dumps({
        "nome": "P1", "comprimento": 66, "largura": 19, "altura": 280,
        "h1_A": 2, "h2_A": 244, "h3_A": 34, "larg1_A": 66, "grade_1": 88,
    }), encoding="utf-8")
    obra_id = repo.criar_obra(
        conn, membro_id=membro, nome="ObraPilarWeb", pasta_drive_id="folder-ana",
        arquivo_hash="pillar-web", estado="pronta", local_path=str(obra_dir),
    )
    conn.close()
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "ana", "senha": "segredo123"})
            yield client, obra_id, obra_dir


@pytest.mark.asyncio
async def test_get_put_pillar_n3_ficha_roundtrip(settings):
    async with _client(settings) as (client, obra_id, obra_dir):
        url = f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha?pavimento=TERREO"
        first = await client.get(url)
        assert first.status_code == 200
        ficha = first.json()["ficha"]
        assert ficha["faces"]["A"]["panels"][0]["height"] == 2
        ficha["faces"]["A"]["openings"]["right"] = [{
            "distance": 0, "width": 12, "depth": 25, "level": 120, "top_distance": 0,
        }]
        ficha["grades"]["horizontal_slats"] = [{
            "left_distance": 4, "right_distance": 6, "width": 5, "height": 7,
        }]
        saved = await client.put(url, json={"ficha": ficha})
        assert saved.status_code == 200
        body = saved.json()
        assert body["revision"] == 1
        assert body["robot_patch"]["abertura_A_1"]["lado"] == "direito"
        assert body["robot_patch"]["sarrafos_horizontais"][0]["right_distance"] == 6
        assert (obra_dir / "Fase-3_Interpretacao_Extracao" / "Pilares" /
                "portal_n3" / "TERREO" / "P1.json").is_file()
        again = await client.get(url)
        assert again.json()["ficha"]["source"]["human_override"] is True


@pytest.mark.asyncio
async def test_item_n1_pilar_expoe_somente_resumo_visual_canonico(settings):
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1?pavimento=TERREO"
        )
        assert response.status_code == 200
        resumo = response.json()["resumo_pilar_n1"]
        assert resumo == {
            "classificacao": "Pilar",
            "orientacao": "—",
            "nivel_chegada": 0.0,
            "nivel_saida": 280.0,
            "pe_direito": 280.0,
        }


@pytest.mark.asyncio
async def test_ficha_rejects_non_pillar_class(settings):
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.get(
            f"/obras/{obra_id}/n1/lajes/P1/pilar-n3-ficha?pavimento=TERREO"
        )
        assert response.status_code == 400
