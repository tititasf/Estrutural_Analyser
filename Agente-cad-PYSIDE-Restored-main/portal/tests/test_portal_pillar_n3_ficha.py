from __future__ import annotations

import contextlib
import json
from pathlib import Path

import httpx
import pytest

from portal.app.routers.n1_routes import _anexar_lajes_n3

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
async def test_niveis_sa_alimentam_distancia_ao_topo(settings):
    async with _client(settings) as (client, obra_id, obra_dir):
        variant = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / "para" / "P1.json"
        robot = json.loads(variant.read_text(encoding="utf-8"))
        robot["nivel_chegada_abs"] = 855.25
        robot["nivel_saida_abs"] = 852.45
        robot["nivel_laje_B"] = 855.22
        robot["_sa_mode_contract"]["faces"]["B"]["nivel_laje"] = 855.22
        robot["abertura_A_1"]["_nivel_origem"] = 852.45
        robot["abertura_A_2"] = {
            "lado": "esquerdo", "largura": 11, "altura": 40,
            "y_rel": 120, "_nivel_origem": None, "_viga": "V410", "_origem": "AC",
        }
        robot["abertura_A_1"]["_viga"] = "V410"
        robot["abertura_A_1"]["_origem"] = "AC"
        variant.write_text(json.dumps(robot), encoding="utf-8")
        url = (f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
               "?pavimento=TERREO&vista=abcd-para")
        ficha = (await client.get(url)).json()["ficha"]
        assert ficha["source"]["pillar_top_level"] == 855.25
        opening = ficha["faces"]["A"]["openings"]["right"][0]
        assert opening["element_level"] == 852.45
        assert opening["level_source"] == "sa"
        assert opening["top_distance"] == 280
        inferred = ficha["faces"]["A"]["openings"]["left"][0]
        assert inferred["level_source"] == "sa_related"
        assert inferred["element_level"] == 852.45
        assert inferred["top_distance"] == 280
        assert inferred["geometry_level_gap_cm"] == -162
        slab = ficha["faces"]["B"]["slabs"][0]
        assert slab["level"] == 855.22
        assert slab["top_distance"] == 3
        inferred["element_level"] = 853.67
        inferred["level_source"] = "n3_geometry"
        assert (await client.put(url, json={"ficha": ficha})).status_code == 200
        again = (await client.get(url)).json()["ficha"]
        assert again["faces"]["B"]["slabs"][0]["top_distance"] == 3
        assert again["faces"]["A"]["openings"]["right"][0]["element_level"] == 852.45
        assert again["faces"]["A"]["openings"]["left"][0]["element_level"] == 852.45
        again["faces"]["B"]["slabs"][0]["level"] = 855.30
        again["faces"]["A"]["openings"]["right"][0]["element_level"] = 855.30
        assert (await client.put(url, json={"ficha": again})).status_code == 200
        invalid_levels = (await client.get(url)).json()["ficha"]
        assert invalid_levels["faces"]["B"]["slabs"][0]["top_distance"] == -5
        assert invalid_levels["faces"]["A"]["openings"]["right"][0]["top_distance"] == -5


@pytest.mark.asyncio
async def test_grades_expoem_quadradinhos_e_alturas_do_desenho(settings):
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
            "?pavimento=TERREO&vista=grades-para"
        )
        assert response.status_code == 200
        detail = response.json()["grades_detail"]
        assert detail["visual_mode"] == "NOVA"
        grade_a = detail["faces"]["A"]["grades"][0]
        assert grade_a["width"] == 88
        assert grade_a["quadradinhos"] == [29, 29, 30]
        assert grade_a["alturas_montantes"] == [262.8] * 4
        assert grade_a["alturas_quadradinhos"] == [30, 80, 80, 42.8]
        assert grade_a["alturas_por_coluna"] == [[30, 80, 80, 42.8]] * 3
        assert detail["faces"]["B"]["grades"][0]["quadradinhos"] == [30, 29, 29]
        ini = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
            "?pavimento=TERREO&vista=grades-para&visual_mode=INI"
        )
        assert ini.status_code == 200
        assert ini.json()["grades_detail"]["faces"]["A"]["grades"][0]["alturas_quadradinhos"] == [60, 100, 82.8]


def test_grade_com_recorte_superior_mede_altura_por_quadradinho():
    from portal.app.routers.n1_routes import _grades_detail_contract

    robot = {
        "comprimento": 66, "largura": 19, "altura": 280,
        "h1_A": 2, "h2_A": 210, "h3_A": 68,
        "abertura_A_1": {
            "lado": "direito", "largura": 12, "altura": 25,
            "y_rel": 253,
        },
    }
    grade = _grades_detail_contract(robot, "NOVA")["faces"]["A"]["grades"][0]
    assert grade["alturas_montantes"][-1] < grade["alturas_montantes"][0]
    assert grade["alturas_por_coluna"][0][-1] > grade["alturas_por_coluna"][-1][-1]


@pytest.mark.asyncio
async def test_abertura_usa_nivel_da_viga_em_vez_do_y_rel_legado(settings):
    async with _client(settings) as (client, obra_id, obra_dir):
        state_path = obra_dir / "estado_TERREO.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["pilares"][0]["interpretacao_abcd"] = {"faces": {"A": {
            "passa": [{"nome": "V410", "canto": "AC", "nivel": "—", "dim": "19/55"}],
        }}}
        state["segmentos"]["fundo"] = [{
            "beam_name": "V410", "segment_label": "1", "level": 855.25,
            "level_source": "explicit_beam_or_side", "status": "valid",
        }]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        variant = obra_dir / "Fase-6_Execucao_CAD/n3_variants/para/P1.json"
        robot = json.loads(variant.read_text(encoding="utf-8"))
        robot["nivel_chegada_abs"] = 855.25
        robot["nivel_saida_abs"] = 852.45
        robot["abertura_A_1"].update({
            "_viga": "V410", "_origem": "AC", "_nivel_origem": 852.45, "y_rel": 0,
        })
        variant.write_text(json.dumps(robot), encoding="utf-8")
        response = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha?pavimento=TERREO&vista=abcd-para"
        )
        assert response.status_code == 200, response.text
        opening = response.json()["ficha"]["faces"]["A"]["openings"]["right"][0]
        assert opening["element_level"] == 855.25
        assert opening["top_distance"] == 0
        assert opening["level_source"] == "abcd_sa"
        assert opening["geometry_level_gap_cm"] == 253
        assert response.json()["robot_patch"]["abertura_A_1"]["y_rel"] == 253


@pytest.mark.asyncio
async def test_regeneracao_n3_preserva_vinculo_e_nivel_da_abertura(settings):
    async with _client(settings) as (client, obra_id, obra_dir):
        state_path = obra_dir / "estado_TERREO.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["pilares"][0]["interpretacao_abcd"] = {"faces": {"A": {
            "passa": [{"nome": "V410", "canto": "AC", "nivel": "855.25", "dim": "19/55"}],
        }}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        variant = obra_dir / "Fase-6_Execucao_CAD/n3_variants/para/P1.json"
        robot = json.loads(variant.read_text(encoding="utf-8"))
        robot.update({"nivel_chegada_abs": 855.25, "nivel_saida_abs": 852.45})
        robot["abertura_A_1"].update({"_viga": "V410", "_origem": "AC",
                                       "_nivel_origem": 852.45})
        variant.write_text(json.dumps(robot), encoding="utf-8")
        url = (f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
               "?pavimento=TERREO&vista=abcd-para")
        ficha = (await client.get(url)).json()["ficha"]
        opening = ficha["faces"]["A"]["openings"]["right"][0]
        assert (opening["beam_name"], opening["n3_slot"], opening["element_level"]) == ("V410", "AC", 855.25)
        opening["beam_dimension"] = "19/55"
        assert (await client.put(url, json={"ficha": ficha})).status_code == 200

        # Uma variante N3 antiga foi regenerada sem os campos de procedência.
        robot["abertura_A_1"] = {
            "lado": "direito", "largura": 12, "altura": 25,
            "y_rel": 253, "origem_portal": "right",
        }
        variant.write_text(json.dumps(robot), encoding="utf-8")
        response = await client.get(url)
        assert response.status_code == 200
        opening = response.json()["ficha"]["faces"]["A"]["openings"]["right"][0]
        assert opening["beam_name"] == "V410"
        assert opening["beam_dimension"] == "19/55"
        assert opening["n3_slot"] == "AC"
        assert opening["element_level"] == 855.25
        assert opening["top_distance"] == 0
        assert "geometry_level_gap_cm" not in opening
        patch = response.json()["robot_patch"]["abertura_A_1"]
        assert (patch["_viga"], patch["_origem"], patch["_nivel_origem"]) == ("V410", "AC", 855.25)


def test_abertura_sem_cota_usa_chegada_do_pilar_com_alerta():
    ficha = {"source": {}, "faces": {"A": {
        "panels": [{"row": 1, "height": 2, "width": 60}],
        "openings": {"left": [{"width": 11, "depth": 59}], "right": []},
    }}}
    robot = {"nivel_chegada_abs": 855.25, "nivel_saida_abs": 852.19,
             "_sa_mode_contract": {"faces": {"A": {}}},
             "abertura_A_1": {"lado": "esquerdo", "largura": 11,
                                "altura": 59, "y_rel": 245}}
    _anexar_lajes_n3(ficha, robot)
    opening = ficha["faces"]["A"]["openings"]["left"][0]
    assert opening["element_level"] == 855.25
    assert opening["top_distance"] == 0
    assert opening["level_source"] == "pillar_fallback"


def test_abertura_central_regenerada_mantem_lado_original():
    from src.core import pillar_n3_ficha

    ficha = pillar_n3_ficha.build_ficha(
        {"name": "P1", "points": [[0, 0], [60, 0], [60, 19], [0, 19]]},
        {"comprimento": 60, "largura": 19, "altura": 280,
         "h1_A": 2, "h2_A": 244, "h3_A": 34, "larg1_A": 60,
         "abertura_A_1": {"lado": "meio", "origem_portal": "right",
                          "largura": 20, "altura": 59, "x_offset": 18}},
    )
    assert not ficha["faces"]["A"]["openings"]["left"]
    assert ficha["faces"]["A"]["openings"]["right"][0]["width"] == 20


def test_face_curta_posiciona_abertura_pelo_pe_direito_e_nao_pela_malha():
    from src.core import pillar_n3_ficha

    ficha = pillar_n3_ficha.build_ficha(
        {"name": "P10", "points": [[0, 0], [82, 0], [82, 19], [0, 19]]},
        {"comprimento": 82, "largura": 19, "altura": 306,
         "h1_C": 2, "h2_C": 240, "larg1_C": 19},
    )
    ficha["faces"]["C"]["openings"]["right"].append({
        "distance": 0, "width": 19, "depth": 59, "level": 0,
        "element_level": 855.25, "top_distance": 0,
    })
    patch = pillar_n3_ficha.robot_patch(ficha)
    assert patch["paineis_intervals_C"] == [240]
    assert patch["abertura_C_1"]["y_rel"] == 245


def test_vazio_superior_atualizado_chega_ao_gerador_n3():
    from src.core import pillar_n3_ficha

    ficha = pillar_n3_ficha.build_ficha(
        {"name": "P10", "points": [[0, 0], [82, 0], [82, 19], [0, 19]]},
        {"comprimento": 82, "largura": 19, "altura": 306,
         "h1_C": 2, "h2_C": 240, "larg1_C": 19},
    )
    ficha["faces"]["C"]["top_void_cm"] = 59
    robot = {"_sa_mode_contract": {"faces": {"C": {
        "vazio_topo": {"valor_cm": 64, "fonte": "dentro_do_interior"},
    }}}}
    patched = pillar_n3_ficha.apply_ficha_to_robot(robot, ficha)
    assert patched["_sa_mode_contract"]["faces"]["C"]["vazio_topo"]["valor_cm"] == 59
    assert robot["_sa_mode_contract"]["faces"]["C"]["vazio_topo"]["valor_cm"] == 64


def test_face_curta_recalcula_so_malha_automatica_apos_dimensao_sa():
    from src.core import pillar_n3_ficha

    ficha = pillar_n3_ficha.build_ficha(
        {"name": "P10", "points": [[0, 0], [82, 0], [82, 19], [0, 19]]},
        {"comprimento": 82, "largura": 19, "altura": 306,
         "h1_C": 2, "h2_C": 240, "larg1_C": 19},
    )
    robot = {"paineis_intervals_C": [240], "nivel_chegada_abs": 855.25,
             "_sa_mode_contract": {"faces": {"C": {"vazio_topo": {
                 "valor_cm": 64, "fonte": "dentro_do_interior",
                 "evidencia": "Viga: V410 · dim: 19/60",
             }}}}}
    abcd = {"faces": {"C": {"interior": [{
        "nome": "V410", "dim": "19/55", "nivel": "855.25",
    }]}}}
    _anexar_lajes_n3(ficha, robot, abcd)
    assert ficha["faces"]["C"]["top_void_cm"] == 59
    assert [(p["row"], p["height"]) for p in ficha["faces"]["C"]["panels"]] == [
        (1, 2), (2, 244), (3, 1),
    ]


def test_viga_passa_coberta_pelo_vazio_superior_nao_alerta_desvio_falso():
    ficha = {"source": {}, "faces": {"A": {
        "panels": [{"row": 1, "height": 2, "width": 82},
                   {"row": 2, "height": 122, "width": 82},
                   {"row": 3, "height": 118, "width": 82}],
        "top_void_cm": 59,
        "openings": {"left": [{"width": 82, "depth": 59,
                                 "beam_name": "V410", "beam_behavior": "viga_passa"}],
                     "right": []},
    }}}
    robot = {"nivel_chegada_abs": 855.25, "nivel_saida_abs": 852.19,
             "_sa_mode_contract": {"faces": {"A": {}}},
             "abertura_A_1": {"lado": "esquerdo", "largura": 82, "altura": 59,
                                "y_rel": 0, "_viga": "V410"}}
    _anexar_lajes_n3(ficha, robot)
    opening = ficha["faces"]["A"]["openings"]["left"][0]
    assert opening["element_level"] == 855.25
    assert "geometry_level_gap_cm" not in opening


@pytest.mark.asyncio
async def test_faces_c_d_expoem_vazio_superior_e_slot_da_abertura(settings):
    async with _client(settings) as (client, obra_id, obra_dir):
        variant = obra_dir / "Fase-6_Execucao_CAD/n3_variants/para/P1.json"
        robot = json.loads(variant.read_text(encoding="utf-8"))
        robot["nivel_chegada_abs"] = 855.25
        robot["nivel_saida_abs"] = 852.45
        robot.update({
            "h1_C": 2, "h2_C": 214, "larg1_C": 19,
            "h1_D": 2, "h2_D": 214, "larg1_D": 19,
            "abertura_C_1": {
                "lado": "direito", "largura": 27, "altura": 70,
                "y_rel": 0, "_nivel_origem": 855.25,
                "_origem": "CC", "_viga": "V402",
            },
        })
        robot["_sa_mode_contract"]["faces"].update({
            "C": {
                "vazio_topo": {"valor_cm": 64, "evidencia": "Viga: V410 · dim: 19/60"},
                "aberturas_vigas_que_chegam": [{
                    "nome": "V402", "slot": "CC", "largura": 19,
                    "profundidade": 66, "largura_abertura": 27, "altura": 70,
                }],
                "fontes_n1": {},
            },
            "D": {"vazio_topo": {"valor_cm": 64, "evidencia": "Viga: V409 · dim: 19/60"}, "fontes_n1": {}},
        })
        variant.write_text(json.dumps(robot), encoding="utf-8")
        response = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha?pavimento=TERREO&vista=abcd-para"
        )
        assert response.status_code == 200, response.text
        faces = response.json()["ficha"]["faces"]
        assert faces["C"]["top_void_cm"] == faces["D"]["top_void_cm"] == 64
        assert faces["C"]["top_void_name"] == "V410"
        assert faces["D"]["top_void_name"] == "V409"
        assert faces["C"]["top_void_dimension"] == "19/60"
        assert faces["D"]["top_void_behavior"] == "viga_passa"
        assert [panel["height"] for panel in faces["C"]["panels"]] == [2, 214]
        opening = faces["C"]["openings"]["right"][0]
        assert opening["n3_slot"] == "CC"
        assert opening["beam_name"] == "V402"
        assert opening["beam_dimension"] == "19/66"
        assert opening["beam_behavior"] == "viga_interna"
        assert opening["n3_kind"] == "passing_beam"
        assert faces["D"]["openings"] == {"left": [], "right": []}


def test_n3_recebe_dimensao_atual_do_sa_e_preserva_ajuste_humano():
    ficha = {"source": {"human_override": False}, "faces": {
        "B": {"panels": [{"width": 60}], "openings": {"left": [], "right": [
            {"width": 11, "depth": 64, "distance": 0},
            {"width": 11, "depth": 72, "distance": 0},
        ]}, "slabs": [{"height": 14, "level": 855.22, "top_distance": 3, "width": 30}]},
    }}
    robot = {
        "nivel_chegada_abs": 855.25, "nivel_saida_abs": 852.19,
        "abertura_B_1": {"lado": "direito", "largura": 11, "altura": 64,
                         "_viga": "V410", "_origem": "BC", "_nivel_origem": 855.25},
        "abertura_B_2": {"lado": "direito", "largura": 11, "altura": 64,
                         "_viga": "V410", "_origem": "BC", "_nivel_origem": 855.25},
        "_sa_mode_contract": {"faces": {"B": {
            "vazio_topo": {"valor_cm": 64, "evidencia": "Viga: V410 · dim: 19/60"},
            "aberturas_vigas_que_param": [{"nome": "V410", "slot": "BC", "largura": 19,
                                          "profundidade": 60, "largura_abertura": 11, "altura": 64}],
            "fontes_n1": {"lajes": ["Laje: L410 · esp: 12cm"]},
            "espessura_laje": 12, "vazio_laje_cm": 14, "nivel_laje": 855.22,
        }}},
    }
    abcd = {"faces": {"B": {
        "passa": [{"nome": "V410", "canto": "BC", "dim": "19/55",
                    "dim_status": "conflict", "nivel": "855.25"}],
        "lajes": [{"nome": "L410", "dim": "14", "nivel": "855.22"}],
    }}}
    _anexar_lajes_n3(ficha, robot, abcd)
    face = ficha["faces"]["B"]
    assert face["top_void_dimension"] == "19/55"
    assert face["top_void_cm"] == 59
    assert face["openings"]["right"][0]["beam_dimension"] == "19/55"
    assert face["openings"]["right"][0]["depth"] == 59
    assert face["openings"]["right"][1]["depth"] == 72
    assert face["slabs"][0]["slab_dimension"] == "14"
    assert face["slabs"][0]["height"] == 16

    # Na face curta, a viga interna corta exatamente a largura do painel,
    # mesmo quando o contrato antigo trazia a folga de uma chegada.
    short = {"faces": {"C": {"panels": [{"width": 19}],
                            "openings": {"left": [], "right": [{"width": 27, "depth": 70}]}}}}
    short_robot = {"abertura_C_1": {"lado": "direito", "largura": 27, "altura": 70,
                                    "_viga": "V402", "_origem": "CC"},
                   "_sa_mode_contract": {"faces": {"C": {"aberturas_vigas_que_chegam": [
                       {"nome": "V402", "slot": "CC", "largura": 19, "profundidade": 66,
                        "largura_abertura": 27, "altura": 70}]}}}}
    short_abcd = {"faces": {"C": {"interior": [
        {"nome": "V402", "canto": "CC", "dim": "19/55", "nivel": "855.25"}]}}}
    _anexar_lajes_n3(short, short_robot, short_abcd)
    assert short["faces"]["C"]["openings"]["right"][0]["width"] == 19
    assert short["faces"]["C"]["openings"]["right"][0]["depth"] == 59

    # Laje com recorte proprio nao transforma um vazio superior explicitamente
    # nulo em um corte de toda a largura da face.
    separate = {"faces": {"B": {"panels": [{"width": 60, "distance": 0, "column": 1}],
                               "openings": {"left": [], "right": []}}}}
    separate_robot = {"_sa_mode_contract": {"faces": {"B": {
        "vazio_topo": {"valor_cm": 0, "fonte": "laje_rebaixo_e_vazio_separados",
                       "evidencia": "Laje: L410 · esp: 14cm"},
        "fontes_n1": {"lajes": ["Laje: L410 · esp: 14cm"]},
        "espessura_laje": 14, "vazio_laje_cm": 16,
    }}}}
    _anexar_lajes_n3(separate, separate_robot, abcd)
    assert separate["faces"]["B"]["top_void_cm"] == 0
    assert separate["faces"]["B"]["slabs"][0]["height"] == 16


@pytest.mark.asyncio
async def test_lajes_por_face_persistem_separadas_dos_paineis(settings):
    async with _client(settings) as (client, obra_id, _obra_dir):
        url = (f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
               "?pavimento=TERREO&vista=abcd-para")
        ficha = (await client.get(url)).json()["ficha"]
        assert ficha["faces"]["B"]["slabs"] == [{
            "left_distance": 0, "right_distance": 0, "top_distance": 7,
            "level": 852.12, "width": 41, "height": 14,
            "slab_name": "L301", "slab_dimension": "12", "slab_behavior": "laje",
        }]
        panels = ficha["faces"]["B"]["panels"]
        ficha["faces"]["B"]["slabs"] = [
            {"left_distance": 3, "right_distance": 4, "level": 852.12, "top_distance": 7,
             "width": 50, "height": 14},
            {"left_distance": 8, "right_distance": 9, "level": 851.84, "top_distance": 35,
             "width": 40, "height": 12},
        ]
        saved = await client.put(url, json={"ficha": ficha})
        assert saved.status_code == 200
        assert saved.json()["robot_patch"]["_portal_slabs_B"] == ficha["faces"]["B"]["slabs"]
        again = (await client.get(url)).json()["ficha"]
        assert len(again["faces"]["B"]["slabs"]) == len(ficha["faces"]["B"]["slabs"])
        for actual, expected in zip(again["faces"]["B"]["slabs"], ficha["faces"]["B"]["slabs"]):
            assert {key: actual[key] for key in expected} == expected
        assert again["faces"]["B"]["panels"] == panels
        again["faces"]["B"]["slabs"] = []
        assert (await client.put(url, json={"ficha": again})).status_code == 200
        assert (await client.get(url)).json()["ficha"]["faces"]["B"]["slabs"] == []


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
            ["quadradinhos A", "G1: 29 | 29 | 30"],
            ["quadradinhos B", "G1: 29 | 29 | 30"],
        ]
        assert cima_contract["fields"] == {
            "comprimento_interno": 66.0, "largura_interna": 19.0,
            "comprimento_externo": 88.0, "parafusos": [0.0] * 7,
            "classificacao_pilar": "retangular", "parafuso_inicio": -1.0,
            "parafuso_final": 1.0,
            "grade_count": 1,
            "grades": {"grade_1": 88.0, "distancia_1": None, "grade_2": None,
                       "distancia_2": None, "grade_3": None},
            "quadradinhos_a": [[29.0, 29.0, 30.0, None, None]],
            "quadradinhos_b": [[29.0, 29.0, 30.0, None, None]],
            "quadradinhos": [[29.0, 29.0, 30.0, None, None]],
        }
        ficha["faces"]["A"]["openings"]["right"] = [{
            "distance": 0, "width": 12, "depth": 25, "level": 120, "top_distance": 0,
        }]
        ficha["grades"]["horizontal_slats"] = [{
            "left_distance": 4, "right_distance": 6, "width": 5, "height": 7,
        }]
        ficha["cima_contract"] = cima_contract
        ficha["cima_contract"]["fields"]["quadradinhos_a"][0] = [20, 30, 38, None, None]
        ficha["cima_contract"]["fields"]["quadradinhos_b"][0] = [18, 32, 38, None, None]
        saved = await client.put(url, json={"ficha": ficha})
        assert saved.status_code == 200
        body = saved.json()
        assert body["revision"] == 1
        assert body["robot_patch"]["abertura_A_1"]["lado"] == "direito"
        assert body["robot_patch"]["sarrafos_horizontais"][0]["right_distance"] == 6
        assert body["robot_patch"]["_portal_cima_grade_layout"] == {
            "widths": [88.0], "gaps": [],
        }
        assert body["robot_patch"]["distancia_1"] == 0.0
        assert body["robot_patch"]["grade_1_div_a"] == [20.0, 30.0, 38.0]
        assert body["robot_patch"]["grade_1_div_b"] == [18.0, 32.0, 38.0]
        assert (obra_dir / "Fase-3_Interpretacao_Extracao" / "Pilares" /
                "portal_n3" / "TERREO" / "P1.json").is_file()
        again = await client.get(url)
        assert again.json()["ficha"]["source"]["human_override"] is True
        assert again.json()["cima_contract"]["fields"]["quadradinhos_a"][0][:3] == [20, 30, 38]
        assert again.json()["cima_contract"]["fields"]["quadradinhos_b"][0][:3] == [18, 32, 38]


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
        lambda _obra, _item, vista, mode: f'<svg data-vista="{vista}" data-mode="{mode}"/>',
    )
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.get(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-ficha"
            "?pavimento=TERREO&vista=abcd-para"
        )
        assert response.status_code == 200
        assert response.json()["visualizacoes_n3"] == {
            "abcd-para": '<svg data-vista="abcd-para" data-mode="NOVA"/>'
        }
        ficha = response.json()["ficha"]
        assert [panel["height"] for panel in ficha["faces"]["A"]["panels"]] == [2.0, 210.0, 68.0]
        assert ficha["faces"]["A"]["openings"]["right"] == [{
            "distance": 0.0, "width": 12.0, "depth": 25.0,
                "level": 120.0, "n3_kind": "opening",
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


@pytest.mark.asyncio
async def test_regeneracao_cima_enfileira_microciclo_do_pilar(settings, monkeypatch):
    captured = {}

    def enqueue(_conn, **kwargs):
        captured.update(kwargs)
        return "job-p1", True

    monkeypatch.setattr(repo, "enfileirar_job_unico_por_meta", enqueue)
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.post(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-cima/regenerar"
            "?pavimento=TERREO"
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job-p1"
        assert captured["meta"] == {
            "etapa": "n3_cima_item", "secao": "pilares", "item": "P1",
            "pav": "TERREO", "requested_view": "cima", "visual_mode": "NOVA",
        }
        assert captured["chaves"] == ("etapa", "secao", "item", "pav")


def test_frontend_cima_expoe_lados_salvar_e_regeneracao_granular():
    js = (
        Path(__file__).resolve().parents[1] / "app" / "static" / "pillar_ficha.js"
    ).read_text(encoding="utf-8")
    assert "quadradinhos_a" in js
    assert "quadradinhos_b" in js
    assert "Lado '+spec[0]" in js
    assert "Salvar edições manuais" in js
    assert "Solicitar regeneração N3 '+this.viewLabel()" in js
    assert "'/pilar-n3-' + encodeURIComponent(this.tab) + '/regenerar'" in js
    assert "board.appendChild(self.renderActions())" in js
    assert "wrap.appendChild(self.renderActions())" in js
    assert "Alterações não salvas" in js


@pytest.mark.asyncio
@pytest.mark.parametrize("vista,modo", [
    ("abcd-para", "para"), ("abcd-passa", "passa"),
    ("grades-para", "para"), ("grades-passa", "passa"),
])
async def test_regeneracao_n3_vista_enfileira_somente_variante_solicitada(
    settings, monkeypatch, vista, modo,
):
    captured = {}

    def enqueue(_conn, **kwargs):
        captured.update(kwargs)
        return "job-p1", True

    monkeypatch.setattr(repo, "enfileirar_job_unico_por_meta", enqueue)
    async with _client(settings) as (client, obra_id, _obra_dir):
        response = await client.post(
            f"/obras/{obra_id}/n1/pilares/P1/pilar-n3-{vista}/regenerar"
            "?pavimento=TERREO", json={"visual_mode": "NOVA"},
        )
        assert response.status_code == 200
        assert captured["meta"]["requested_view"] == vista
        assert captured["meta"]["etapa"] == "n3_pilar_vista_item"
        assert captured["chaves"] == (
            "etapa", "secao", "item", "pav", "requested_view",
        )
        assert modo in vista
