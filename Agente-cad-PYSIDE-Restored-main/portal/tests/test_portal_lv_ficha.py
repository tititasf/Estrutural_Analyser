from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from portal.app import lv_ficha, lv_operations


def _estado() -> dict:
    return {
        "segmentos": {
            "lateral_a_para": [
                {"uid": "v328-a-s1", "beam_name": "V328", "segment_label": "1", "side": "A",
                 "behavior": "Para", "length": 260, "width": "19/60", "level": 852.16,
                 "status": "valid", "points": [[0, 0], [260, 0]]},
                {"uid": "v329-a-s1", "beam_name": "V329", "segment_label": "1", "side": "A",
                 "behavior": "Para", "length": 100, "width": "19/55", "points": []},
            ],
            "lateral_b_para": [
                {"uid": "v328-b-s1", "beam_name": "V328", "segment_label": "1", "side": "B",
                 "behavior": "Para", "length": 244, "width": "19/60", "level": 852.16,
                 "status": "valid", "points": [[0, 1], [244, 1]]},
            ],
            "lateral_a_passa": [],
            "lateral_b_passa": [],
        },
        "slabs": [{"name": "L301", "nivel": 852.16, "height": 12}],
        "cortes": [{"uid": "cut-v328-1", "beam_name": "V328", "own_laje": "L301",
                    "neigh_laje": None, "beam_h": 60, "conf_pct": 91, "status": "Válido", "pts": []}],
    }


def test_montar_ficha_lv_reune_lados_comportamento_cortes_e_camadas(tmp_path, monkeypatch):
    def fake_photos(_obra, _pavimento, classe, item):
        name = item.get("beam_name") or ""
        return {
            "n1": f'<svg viewBox="0 0 10 10"><text>{classe}-{name}</text></svg>',
            "n3": f'<svg viewBox="0 0 10 10"><text>N3-{classe}-{name}</text></svg>',
        }

    monkeypatch.setattr(lv_ficha.ficha_reader, "resolver_fotos_portal", fake_photos)
    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", _estado())

    assert result["schema"] == "cad.portal.lv_ficha/v1"
    assert result["beam"]["behavior_label"] == "Segmentos param nos pilares"
    assert result["beam"]["next"] == "V329"
    assert [item["id"] for item in result["sides"]["A"]["segments"]] == ["v328-a-s1"]
    assert [item["id"] for item in result["sides"]["B"]["segments"]] == ["v328-b-s1"]
    assert result["sides"]["A"]["segments"][0]["beam_height_cm"] == 60
    assert result["sides"]["A"]["segments"][0]["layers"]["c1"]["available"] is False
    assert result["sides"]["B"]["segments"][0]["layers"]["n3_panels"]["available"] is True
    assert result["cut_views"][0]["own_slab"] == "L301"
    assert result["cut_views"][0]["layers"]["n3_cut"]["available"] is True


def test_lateral_level_uses_explicit_sa_segment_and_lists_its_own_slabs(tmp_path):
    db = tmp_path / "beam.vision"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE beams (id TEXT, data_json TEXT)")
        conn.execute("INSERT INTO beams VALUES (?, ?)", (
            "beam-1", json.dumps({"viga_a_seg_1_nivel_viga": "855.25"}),
        ))
    state = _estado()
    state["db_path"] = str(db)
    state["segmentos"]["lateral_a_para"][0]["uid"] = "lateral_a_para|beam-1|1|1"
    state["segmentos"]["lateral_a_para"][0]["level"] = ""
    state["segmentos"]["lateral_a_para"][0]["points"] = [[0, 0], [100, 0]]
    state["slabs"] = [{"name": "L1", "nivel": "855.18", "points": [[0, 0], [100, 0], [100, 20], [0, 20]]}]

    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", state, include_svgs=False)
    segment = result["sides"]["A"]["segments"][0]
    assert segment["level"] == 855.25
    assert segment["level_source"] == "sa_beam_segment"
    assert segment["slabs"] == [{"name": "L1", "level": "855.18"}]


def test_lateral_level_marks_nearest_same_side_slab_as_inferred(tmp_path):
    state = _estado()
    state["segmentos"]["lateral_a_para"][0]["level"] = ""
    state["segmentos"]["lateral_a_para"][0]["points"] = [[0, 0], [100, 0]]
    state["slabs"] = [{"name": "L1", "nivel": "855.18",
                       "points": [[110, 0], [150, 0], [150, 20], [110, 20]]}]
    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", state, include_svgs=False)
    segment = result["sides"]["A"]["segments"][0]
    assert segment["level"] == 855.18
    assert segment["level_source"] == "sa_nearest_same_side_slab"
    assert segment["level_distance_cm"] is not None


def test_lv_openings_use_segment_links_and_related_beam_sa_levels(tmp_path):
    db = tmp_path / "beam.vision"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE beams (id TEXT, project_id TEXT, name TEXT, data_json TEXT)")
        links = {
            "viga_a_seg_1_comprimento_total": {"seg_side_a": [{"lv_cell": {
                "beam_openings": [{"name": "V777", "dim": "19/55"}],
            }}]},
            "viga_b_seg_1_abert_viga_1": {
                "arr_label": [{"text": "V778"}], "arr_dim": [{"text": "20/60"}],
            },
        }
        conn.executemany("INSERT INTO beams VALUES (?, ?, ?, ?)", [
            ("beam-1", "project-1", "V328", json.dumps({"project_id": "project-1", "links": links})),
            ("beam-2", "project-1", "V777", json.dumps({"viga_a_seg_1_nivel_viga": "855.25"})),
            ("beam-3", "project-1", "V778", json.dumps({"viga_b_seg_1_nivel_viga": "855.18"})),
        ])
    state = _estado()
    state["db_path"] = str(db)
    state["segmentos"]["lateral_a_para"][0]["uid"] = "lateral_a_para|beam-1|1|1"
    state["segmentos"]["lateral_b_para"][0]["uid"] = "lateral_b_para|beam-1|1|1"
    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", state, include_svgs=False)
    segment = result["sides"]["A"]["segments"][0]
    assert segment["beam_openings_status"] == "verified"
    assert segment["beam_openings"] == [
        {"name": "V777", "dimension": "19/55", "level": 855.25,
         "level_source": "sa_related_beam"},
    ]
    other = result["sides"]["B"]["segments"][0]
    assert other["beam_openings_status"] == "verified"
    assert other["beam_openings"] == [
        {"name": "V778", "dimension": "20/60", "level": 855.18,
         "level_source": "sa_related_beam"},
    ]


def test_lv_openings_preserve_published_sa_cell_without_db_links(tmp_path):
    state = _estado()
    state["segmentos"]["lateral_a_para"][0]["lv_cell"] = {
        "beam_openings": [{"name": "V777", "dim": "19/55", "level": "855,25"}],
    }
    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", state, include_svgs=False)
    segment = result["sides"]["A"]["segments"][0]
    assert segment["beam_openings_status"] == "verified"
    assert segment["beam_openings"] == [
        {"name": "V777", "dimension": "19/55", "level": 855.25,
         "level_source": "sa_opening"},
    ]


@pytest.mark.parametrize("position,location", [(0, "esquerda"), (241, "direita"), (100, "interna")])
def test_opening_position_is_preserved_per_published_segment(tmp_path, position, location):
    state = _estado()
    state["segmentos"]["lateral_a_para"][0]["lv_cell"] = {
        "beam_openings": [{"name": "V777", "dim": "19/50", "level": "852.16",
                           "pos_inicio": position, "largura": 19,
                           "abertura_largura": 27, "abertura_altura": 54, "sobra": 10}],
    }
    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", state, include_svgs=False)
    segment = result["sides"]["A"]["segments"][0]
    opening = segment["beam_openings"][0]
    assert opening["location"] == location
    assert opening["distance_left_cm"] + opening["width_cm"] + opening["distance_right_cm"] == 260
    assert segment["pillar_passages"] == []


def test_aberturas_para_pilar_persistem_por_lado_e_segmento(tmp_path):
    saved = lv_operations.save_pillar_openings(
        tmp_path, "13_PAV", "para", "V328", "A", 1,
        [{"pillar": "p27", "position_cm": 12.5, "width_cm": 19, "height_cm": 60}],
    )
    assert saved == [{"pillar": "P27", "position_cm": 12.5, "width_cm": 19.0, "height_cm": 60.0}]
    result = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", _estado())
    assert result["sides"]["A"]["segments"][0]["pillar_openings"] == saved
    assert result["sides"]["B"]["segments"][0]["pillar_openings"] == []


def test_abertura_invalida_falha_fechado(tmp_path):
    with pytest.raises(ValueError, match="largura"):
        lv_operations.save_pillar_openings(
            tmp_path, "13_PAV", "para", "V328", "A", 1,
            [{"pillar": "P27", "position_cm": 0, "width_cm": 0, "height_cm": 60}],
        )


def test_ficha_compacta_nao_materializa_svg_e_reduz_payload(tmp_path, monkeypatch):
    huge_svg = '<svg viewBox="0 0 10 10">' + ('<path d="M0 0H10"/>' * 5000) + '</svg>'
    calls = []

    def fake_photos(_obra, _pavimento, classe, _item):
        calls.append(classe)
        return {"n1": huge_svg, "n3": huge_svg, "n1_origem": "hifi", "n3_origem": "hifi"}

    monkeypatch.setattr(lv_ficha.ficha_reader, "resolver_fotos_portal", fake_photos)
    compact = lv_ficha.montar_ficha_lv(
        tmp_path, "13_PAV", "V328", "para", _estado(), include_svgs=False,
    )
    assert calls == []
    assert compact["sides"]["A"]["segments"][0]["layers"]["sa"]["lazy"] is True

    full = lv_ficha.montar_ficha_lv(tmp_path, "13_PAV", "V328", "para", _estado())
    assert calls
    assert len(json.dumps(compact)) < len(json.dumps(full)) * 0.05


def test_resolver_camada_lv_materializa_somente_segmento_visivel(tmp_path, monkeypatch):
    calls = []

    def fake_photo(_obra, _pavimento, classe, item, nivel):
        calls.append((classe, item["item_id"], nivel))
        return {"svg": "<svg>SA</svg>", "origem": "hifi"}

    monkeypatch.setattr(lv_ficha.ficha_reader, "resolver_foto_portal", fake_photo)
    result = lv_ficha.resolver_camada_lv(
        tmp_path, "13_PAV", "V328", "para", _estado(), "sa",
        obra_id="obra-teste", side="B", segment_index=1,
    )
    assert result == {"layer": "sa", "available": True, "svg": "<svg>SA</svg>", "origin": "hifi"}
    assert calls == [("lateral_b_para", "v328-b-s1", "n1")]


def test_resolver_camada_lv_prefere_vista_regenerada_no_modo_escolhido(tmp_path, monkeypatch):
    target = (tmp_path / "Fase-6_Execucao_CAD" / "n3_modes" / "INI" / "lv" /
              "para" / "LV_preview_V328_Para_CORTE.dxf")
    target.parent.mkdir(parents=True)
    target.write_text("dxf regenerado", encoding="utf-8")
    seen = []

    def fake_render(path, _cache, **_kwargs):
        seen.append(path)
        return b"<svg>INI</svg>"

    monkeypatch.setattr(lv_ficha.dxf_preview, "renderizar_dxf_svg_cacheado", fake_render)
    result = lv_ficha.resolver_camada_lv(
        tmp_path, "13_PAV", "V328", "para", _estado(), "n3_cut",
        obra_id="obra-teste", cut_index=-1, visual_mode="INI",
    )
    assert result["svg"] == "<svg>INI</svg>"
    assert result["origin"] == "n3_lv_override"
    assert seen == [target]


def test_frontend_lv_tem_lados_cortes_n3_separado_e_abertura_para_pilar():
    repo = Path(__file__).resolve().parents[2]
    js = (repo / "portal" / "app" / "static" / "lv_ficha.js").read_text(encoding="utf-8")
    template = (repo / "portal" / "app" / "templates" / "obra_detalhe.html").read_text(encoding="utf-8")
    drill = (repo / "portal" / "app" / "static" / "drill_grade.js").read_text(encoding="utf-8")

    assert "<span>Lado " in js and "data-lv-side" in js
    assert "Interpretação das visões de corte" in js
    assert "N3 Visão Corte" in js
    assert "N3 Painéis Segmentos" in js
    assert "Adicionar Abertura para Pilar" in js
    assert "Comportamento:" in js
    assert "Desvalidar Segmento" in js
    assert "LvFicha.mount" in template
    assert "/static/lv_ficha.js" in template
    assert "grupoLateral" in drill
    assert "include_svgs=false" in js
    assert "/camada/" in js


def test_torre_context_publica_frame_px_do_transform() -> None:
    """Destaques vêm em px do transform; o cliente precisa do frame para
    converter às unidades do SVG da foto (pt), senão o destaque desloca."""
    payload = lv_ficha._torre_context_payload(
        "obra-x",
        {"bruto_id": "b", "item_id": "torre_1"},
        [{"pontos_px": [[100.0, 50.0], [200.0, 50.0]], "rotulo": "V1 SEG 1"}],
        (1200.0, 544.0),
    )
    assert payload["frame_px"] == [1200.0, 544.0]
    assert payload["highlights"][0]["points"] == [[100.0, 50.0], [200.0, 50.0]]
    assert payload["viewbox"][0] == pytest.approx(100.0 - 140.0)


def test_sa_corte_usa_foto_do_corte_e_todos_preserva_ids(tmp_path, monkeypatch):
    state = _estado()
    state['cortes'].append(dict(state['cortes'][0], uid='cut-v328-2'))
    calls = []

    def photo(_obra, _pav, classe, item, nivel):
        calls.append((classe, nivel))
        return {'svg': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"><defs><path id="wall" d="M0 0H20"/></defs><use href="#wall"/></svg>', 'origem': 'sa'}

    monkeypatch.setattr(lv_ficha.ficha_reader, 'resolver_foto_portal', photo)
    single = lv_ficha.resolver_camada_lv(tmp_path, '13_PAV', 'V328', 'para', state, 'sa_cut', obra_id='obra')
    assert single['available'] and single['origin'] == 'sa'
    all_cuts = lv_ficha.resolver_camada_lv(tmp_path, '13_PAV', 'V328', 'para', state, 'sa_cut', obra_id='obra', cut_index=-1)
    assert all_cuts['available']
    assert 'vc0_wall' in all_cuts['svg'] and 'vc1_wall' in all_cuts['svg']
    assert all_cuts['svg'].count('href="#vc') == 2
    assert calls == [('cortes', 'n1')] * 3
