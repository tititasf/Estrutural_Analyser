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
    n3_dir = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / "para"
    n3_dir.mkdir(parents=True)
    (n3_dir / "P1.json").write_text(json.dumps({
        "nome": "P1", "comprimento": 66, "largura": 19, "altura": 280,
        "h1_A": 2, "h2_A": 210, "h3_A": 68, "larg1_A": 66,
        "laje_B": 12, "posicao_laje_B": 1, "rebaixo_laje_B": 7,
        "vazio_laje_B": 14, "nivel_laje_B": 852.12,
        "abertura_A_1": {
            "lado": "direito", "largura": 12, "altura": 25,
            "y_rel": 120, "x_offset": 0,
        },
        "_sa_mode_contract": {"faces": {"B": {
            "fontes_n1": {"lajes": ["Laje: L301 · esp: 12cm"]},
            "espessura_laje": 12, "rebaixo_laje_cm": 7,
            "vazio_laje_cm": 14, "nivel_laje": 852.12,
        }}},
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
        cima_contract = first.json()["cima_contract"]
        assert ficha["faces"]["A"]["panels"][0]["height"] == 2
        assert cima_contract["rows"] == [
            ["comprimento interno", "66 cm"], ["largura interna", "19 cm"],
            ["comprimento +22", "66 + 22 = 88 cm"], ["parafusos", "offsets: — cm"],
            ["cotas parafusos", "88 cm"], ["layout grades", "1 grade(s): 88 cm; gaps —"],
            ["quadradinhos A", "G1: 22 | 22 | 22 | 22"],
            ["quadradinhos B", "G1: 22 | 22 | 22 | 22 (espelhado do A)"],
        ]
        assert cima_contract["fields"] == {
            "comprimento_interno": 66.0, "largura_interna": 19.0,
            "comprimento_externo": 88.0, "parafusos": [0.0] * 7,
            "grades": {"grade_1": 88.0, "distancia_1": 0.0, "grade_2": 0.0,
                       "distancia_2": 0.0, "grade_3": 0.0},
            "quadradinhos": [[22.0, 22.0, 22.0, 22.0, None]],
        }
        ficha["faces"]["A"]["openings"]["right"] = [{
            "distance": 0, "width": 12, "depth": 25, "level": 120, "top_distance": 0,
        }]
        ficha["grades"]["horizontal_slats"] = [{
            "left_distance": 4, "right_distance": 6, "width": 5, "height": 7,
        }]
        ficha["cima_contract"] = {"rows": [["comprimento interno", "70 cm"]]}
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
        assert again.json()["cima_contract"] == {"rows": [["comprimento interno", "70 cm"]]}


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
async def test_pillar_n3_ficha_expoe_dxf_da_aba_solicitada(settings, monkeypatch):
    from portal.app import ficha_reader

    monkeypatch.setattr(
        ficha_reader, "resolver_visualizacao_n3_pilar",
        lambda _obra, _item, vista: f'<svg data-vista="{vista}"/>',
    )
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
            "?pavimento=TERREO&vista=abcd-para"
        )
        assert response.status_code == 200
        assert response.json()["visualizacoes_n3"] == {
            "abcd-para": '<svg data-vista="abcd-para"/>'
        }
        ficha = response.json()["ficha"]
        assert [panel["height"] for panel in ficha["faces"]["A"]["panels"]] == [2.0, 210.0, 68.0]
        assert ficha["faces"]["A"]["openings"]["right"] == [{
            "distance": 0.0, "width": 12.0, "depth": 25.0,
            "level": 120.0, "top_distance": 0.0, "n3_kind": "opening",
        }]
        assert ficha["source"]["n3_variant"] == "para"
        assert ficha["faces"]["A"]["n3_width_extra"] == 22.0
        assert ficha["faces"]["B"]["n3_width_extra"] == 22.0
        assert ficha["faces"]["B"]["slab"] == {
            "evidence": "Laje: L301 · esp: 12cm", "thickness": 12.0,
            "position": 1, "recess": 7.0, "void": 14.0, "level": 852.12,
        }


@pytest.mark.asyncio
async def test_override_n3_nao_vaza_entre_para_e_passa(settings):
    async with _client(settings) as (client, obra_id, _obra_dir):
        para_url = (
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
            "?pavimento=TERREO&vista=abcd-para"
        )
        passa_url = (
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
            "?pavimento=TERREO&vista=abcd-passa"
        )
        para = (await client.get(para_url)).json()["ficha"]
        para["faces"]["A"]["panels"][0]["height"] = 9
        assert (await client.put(para_url, json={"ficha": para})).status_code == 200
        assert (await client.get(para_url)).json()["ficha"]["faces"]["A"]["panels"][0]["height"] == 9.0
        assert (await client.get(passa_url)).json()["ficha"]["faces"]["A"]["panels"][0]["height"] == 2.0


@pytest.mark.asyncio
async def test_ficha_rejects_non_pillar_class(settings):
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.get(
            f"/obras/{obra_id}/n1/lajes/P1/pilar-n3-ficha?pavimento=TERREO"
        )
        assert response.status_code == 400
