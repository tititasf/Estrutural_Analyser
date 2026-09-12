from __future__ import annotations

import json
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
        tmp_path, "13_PAV", "V328", "para", _estado(), "sa", side="B", segment_index=1,
    )
    assert result == {"layer": "sa", "available": True, "svg": "<svg>SA</svg>", "origin": "hifi"}
    assert calls == [("lateral_b_para", "v328-b-s1", "n1")]


def test_frontend_lv_tem_lados_cortes_n3_separado_e_abertura_para_pilar():
    repo = Path(__file__).resolve().parents[2]
    js = (repo / "portal" / "app" / "static" / "lv_ficha.js").read_text(encoding="utf-8")
    template = (repo / "portal" / "app" / "templates" / "obra_detalhe.html").read_text(encoding="utf-8")
    drill = (repo / "portal" / "app" / "static" / "drill_grade.js").read_text(encoding="utf-8")

    assert "<strong>Lado " in js and "data-lv-side" in js
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
