"""CIMA L: seção N1 + globais SCR + DXF deixa de ser retângulo comum."""
from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from src.core.pillar_special_faces import secao_l_from_points
from src.core.cima_l_contract import (  # noqa: E402
    build_cima_l_contract,
    globais_pilar_especial_l,
    paineis_l_from_secao,
    secao_l_do_payload,
    split_panel_grades,
)
from pl_cima_especial import draw_cima_l  # noqa: E402

# Contorno N1 de P26 (13_PAV): ramo 165×19 + haste 19×218.
P26_POINTS = [
    [3936.3825, 2242.038],
    [4101.3825, 2242.038],
    [4101.3825, 2261.038],
    [3955.3825, 2261.038],
    [3955.3825, 2460.038],
    [3936.3825, 2460.038],
]


def test_secao_l_from_p26_points():
    secao = secao_l_from_points(P26_POINTS)
    assert secao is not None
    assert secao["externa_x"] == pytest.approx(165.0, abs=0.05)
    assert secao["externa_y"] == pytest.approx(218.0, abs=0.05)
    assert secao["interna_x"] == pytest.approx(19.0, abs=0.05)
    assert secao["interna_y"] == pytest.approx(199.0, abs=0.05)


def test_globais_l_match_n2_painel_labels():
    # N2 CIMA P26: "240 PAINEL" e "176 PAINEL".
    globais = globais_pilar_especial_l(218.0, 165.0, 19.0, 19.0)
    assert globais["pilar1_paia_tamanho"] == pytest.approx(240.0)
    assert globais["pilar1_gradea_tamanho"] == pytest.approx(240.0)
    assert globais["pilar2_paib_tamanho"] == pytest.approx(176.0)


def test_payload_without_n2_ficha_still_resolves_l():
    secao = secao_l_do_payload({"subtipo_pil": "L", "geometry_points": P26_POINTS})
    assert secao is not None
    assert secao["externa_x"] == pytest.approx(165.0, abs=0.05)


def test_nested_n1_base_still_is_cima_l():
    from src.core.cima_l_contract import is_cima_l
    wrapped = {
        "comprimento": 55.0,
        "largura": 19.0,
        "_sa_mode_contract": {
            "n1_base": {"subtipo_pil": "L", "geometry_points": P26_POINTS},
        },
    }
    assert is_cima_l(wrapped)
    secao = secao_l_do_payload(wrapped)
    assert secao is not None
    assert secao["externa_y"] == pytest.approx(218.0, abs=0.05)


def test_draw_cima_l_is_six_vertex_not_rectangle():
    from gerar_pl_dxf_stog import setup_doc

    doc = setup_doc()
    n = draw_cima_l(doc.modelspace(), 0, 0, "P26", {
        "subtipo_pil": "L",
        "geometry_points": P26_POINTS,
        "nome": "P26",
    })
    assert n > 8
    outlines = [
        e for e in doc.modelspace()
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "Painéis"
    ]
    assert outlines, "CIMA L precisa do contorno em Painéis"
    pts = list(outlines[0].get_points("xy"))
    if outlines[0].closed and pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    assert len(pts) == 6


def test_generate_pilar_zone_cima_uses_l_motor():
    from gerar_pl_dxf_stog import generate_pilar_zone, setup_doc

    doc = setup_doc()
    n = generate_pilar_zone(
        doc.modelspace(),
        {
            "nome": "P26",
            "comprimento": 50.0,  # Fase-4 errada: o motor L ignora isso
            "largura": 19.0,
            "subtipo_pil": "L",
            "geometry_points": P26_POINTS,
            "grade_1": 240.0,
        },
        "cima",
        visual_mode="NOVA",
    )
    assert n > 8
    painel = next(
        e for e in doc.modelspace()
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "Painéis"
    )
    pts = list(painel.get_points("xy"))
    if painel.closed and pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    assert len(pts) == 6
    labels = [
        e.dxf.text for e in doc.modelspace()
        if e.dxftype() == "TEXT" and "PAINEL" in (e.dxf.text or "")
    ]
    assert any("240" in t for t in labels)
    assert any("176" in t for t in labels)
    assert any("210" in t for t in labels)
    assert any("153" in t for t in labels)
    layers = {e.dxf.layer for e in doc.modelspace()}
    assert "Madeira" in layers
    assert "MEIO_PONT" in layers


def test_cima_l_contract_exposes_editable_grade_and_bolt_fields():
    contract = build_cima_l_contract({
        "subtipo_pil": "L",
        "geometry_points": P26_POINTS,
        "par_a_1": 45.0,
        "par_a_2": 45.0,
    })
    assert contract is not None
    haste = contract["arms"]["haste"]
    ramo = contract["arms"]["ramo"]
    assert haste["comprimento_interno"] == pytest.approx(218.0, abs=0.05)
    assert haste["grade_externa"] == pytest.approx(240.0, abs=0.05)
    assert ramo["comprimento_interno"] == pytest.approx(165.0, abs=0.05)
    assert ramo["grade_externa"] == pytest.approx(176.0, abs=0.05)
    assert haste["grade_widths"] == pytest.approx([120.0, 120.0], abs=0.05)
    haste_int = contract["arms"]["haste_int"]
    ramo_int = contract["arms"]["ramo_int"]
    assert haste_int["grade_externa"] == pytest.approx(210.0, abs=0.05)
    assert ramo_int["grade_externa"] == pytest.approx(153.0, abs=0.05)
    assert haste_int["grade_widths"][0] == pytest.approx(122.0, abs=0.05)
    assert ramo_int["grade_widths"] == pytest.approx([70.0, 70.0], abs=0.05)
    assert haste["quadradinhos"]
    assert abs(sum(haste["quadradinhos"][0]) - haste["grade_widths"][0]) < 1.0
    assert haste["quadradinhos"][0] == pytest.approx([30.0, 30.0, 30.0, 30.0], abs=0.05)


def test_cima_l_respects_manual_quadradinhos():
    preferred = [50.0, 70.0, 60.0, 60.0]
    contract = build_cima_l_contract({
        "subtipo_pil": "L",
        "geometry_points": P26_POINTS,
        "grade_haste_1_div_a": preferred,
    })
    row = contract["arms"]["haste"]["quadradinhos"][0]
    if len(contract["arms"]["haste"]["quadradinhos"]) == 1:
        assert row == pytest.approx(preferred, abs=1.5)


def test_paineis_and_grade_split_match_n2():
    secao = secao_l_from_points(P26_POINTS)
    paineis = paineis_l_from_secao(secao)
    assert paineis["haste_ext"] == pytest.approx(240.0)
    assert paineis["haste_int"] == pytest.approx(210.0)
    assert paineis["ramo_ext"] == pytest.approx(176.0)
    assert paineis["ramo_int"] == pytest.approx(153.0)
    assert split_panel_grades(240.0) == ([120.0, 120.0], [])
    widths_176, gaps_176 = split_panel_grades(176.0)
    assert widths_176 == [80.0, 80.0]
    assert gaps_176[0] == pytest.approx(16.0, abs=0.05)
    widths_210, gaps_210 = split_panel_grades(210.0)
    assert widths_210 == [122.0, 80.0]
    assert gaps_210[0] == pytest.approx(8.0, abs=0.05)
    widths_153, gaps_153 = split_panel_grades(153.0)
    assert widths_153 == [70.0, 70.0]
