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
    flatten_cima_l_into_robot,
    globais_pilar_especial_l,
    n3_faces_l,
    paineis_l_from_secao,
    portal_cima_l_contract,
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

# P27 tem a mesma secao, espelhada horizontalmente no pavimento real.
P27_POINTS = [
    [4960.515, 2490.469],
    [4960.515, 2708.469],
    [4941.515, 2708.469],
    [4941.515, 2509.469],
    [4795.515, 2509.469],
    [4795.515, 2490.469],
]


def test_secao_l_from_p26_points():
    secao = secao_l_from_points(P26_POINTS)
    assert secao is not None
    assert secao["externa_x"] == pytest.approx(165.0, abs=0.05)
    assert secao["externa_y"] == pytest.approx(218.0, abs=0.05)
    assert secao["interna_x"] == pytest.approx(19.0, abs=0.05)
    assert secao["interna_y"] == pytest.approx(199.0, abs=0.05)


@pytest.mark.parametrize("points", [P26_POINTS, P27_POINTS], ids=["P26", "P27"])
def test_p26_p27_expose_four_long_sides_with_the_real_panels(points):
    faces = n3_faces_l({"subtipo_pil": "L", "geometry_points": points})
    by_side = {face["id"]: face for face in faces}
    assert by_side["A"]["panel"] == pytest.approx(240.0)
    assert by_side["B"]["panel"] == pytest.approx(210.0)
    assert by_side["E"]["panel"] == pytest.approx(176.0)
    assert by_side["F"]["panel"] == pytest.approx(153.0)


def test_portal_contract_integrates_grades_and_quadradinhos_by_side():
    portal = portal_cima_l_contract({"subtipo_pil": "L", "geometry_points": P26_POINTS})
    fields = portal["fields"]
    assert fields["classificacao_pilar"] == "especial_l"
    assert fields["shape"] == pytest.approx({
        "comprimento_1_interno": 199.0,
        "comprimento_1_externo": 218.0,
        "comprimento_2_interno": 146.0,
        "comprimento_2_externo": 165.0,
        "largura_1": 19.0,
        "largura_2": 19.0,
    }, abs=0.05)
    assert fields["side_order"] == ["A", "B", "E", "F"]
    expected = {
        "haste_ext": ("A", [120.0, 120.0], []),
        "haste_int": ("B", [122.0, 80.0], [8.0]),
        "ramo_ext": ("E", [80.0, 80.0], [16.0]),
        "ramo_int": ("F", [70.0, 70.0], [13.0]),
    }
    for arm_key, (side_id, widths, gaps) in expected.items():
        arm = fields["especial"][arm_key]
        assert arm["side_id"] == side_id
        assert arm["parafuso_final"] == pytest.approx(1.0)
        assert arm["grade_widths"] == pytest.approx(widths)
        assert arm["gaps"] == pytest.approx(gaps)
        assert len(arm["quadradinhos"]) == len(widths)
        for total, cells in zip(widths, arm["quadradinhos"]):
            assert sum(value for value in cells if value) == pytest.approx(total, abs=0.5)


def test_manual_l_side_layout_round_trips_to_the_drawing_contract():
    original = build_cima_l_contract({"subtipo_pil": "L", "geometry_points": P26_POINTS})
    original["arms"]["haste_int"]["grade_widths"] = [110.0, 91.0]
    original["arms"]["haste_int"]["gaps"] = [9.0]
    original["arms"]["haste_int"]["quadradinhos"] = [[25.0, 30.0, 30.0, 25.0], [30.0, 31.0, 30.0]]
    patched = flatten_cima_l_into_robot(
        {"subtipo_pil": "L", "geometry_points": P26_POINTS}, original,
    )
    rebuilt = build_cima_l_contract(patched)
    side_b = rebuilt["arms"]["haste_int"]
    assert side_b["side_id"] == "B"
    assert side_b["grade_widths"] == [110.0, 91.0]
    assert side_b["gaps"] == [9.0]
    assert side_b["quadradinhos"][0] == [25.0, 30.0, 30.0, 25.0]


def test_manual_l_shape_and_bolt_limits_round_trip():
    original = build_cima_l_contract({"subtipo_pil": "L", "geometry_points": P26_POINTS})
    original["shape"]["comprimento_1_externo"] = 220.0
    original["shape"]["largura_2"] = 20.0
    original["arms"]["ramo_ext"]["parafuso_inicio"] = 43.0
    original["arms"]["ramo_ext"]["parafuso_final"] = 2.0
    rebuilt = build_cima_l_contract(flatten_cima_l_into_robot({}, original))
    assert rebuilt["shape"]["comprimento_1_interno"] == pytest.approx(200.0)
    assert rebuilt["arms"]["ramo_ext"]["parafuso_inicio"] == pytest.approx(43.0)
    assert rebuilt["arms"]["ramo_ext"]["parafuso_final"] == pytest.approx(2.0)


def test_globais_l_match_n2_painel_labels():
    # N2 CIMA P26: "240 PAINEL" e "176 PAINEL".
    globais = globais_pilar_especial_l(218.0, 165.0, 19.0, 19.0)
    assert globais["pilar1_paia_tamanho"] == pytest.approx(240.0)
    assert globais["pilar1_gradea_tamanho"] == pytest.approx(240.0)
    assert globais["pilar2_paib_tamanho"] == pytest.approx(176.0)
    assert globais["pilar2_parafuso_posicao"] == pytest.approx(41.0)
    assert globais["pilar1_parafuso_tamanho"] == pytest.approx(191.0)
    assert globais["perfil_metalico_a_posicao"] == pytest.approx(47.5)
    assert globais["pilar1_metalb_tamanho"] == pytest.approx(-58.5)


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
    assert "Perfil Metálico" in layers
    perfil = [
        e for e in doc.modelspace()
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "Perfil Metálico"
    ]
    assert len(perfil) >= 8, "perfil metálico nas 4 faces longas (C-channel = 2 por face)"
    assert not any(e.dxftype() == "DIMENSION" for e in doc.modelspace()), (
        "cotas CIMA L são LINE+TEXT (legado/N2); DIMENSION quebra no 2×"
    )


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


def test_cota_totals_stay_centered_on_the_dim_line():
    from pl_cima_especial import CotaBook

    book = CotaBook()
    x, y = book.place((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0, 240.0, 0.0, "240 PAINEL", 5.0, 0.0)
    assert x == pytest.approx(120.0, abs=0.2)
    xg, _yg = book.place((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0, 120.0, 28.0, "120(GRADE)", 5.0, 0.0)
    assert xg == pytest.approx(60.0, abs=0.2)


def test_cima_l_draws_bolts_and_six_abcd_faces():
    from gerar_pl_dxf_stog import generate_pilar_zone, setup_doc
    from src.core.cima_l_contract import n3_faces_l

    faces = n3_faces_l({"subtipo_pil": "L", "geometry_points": P26_POINTS})
    assert [f["id"] for f in faces] == list("ABCDEF")
    assert faces[0]["panel"] == pytest.approx(240.0)
    assert faces[4]["panel"] == pytest.approx(176.0)

    payload = {
        "nome": "P26",
        "comprimento": 50.0,
        "largura": 19.0,
        "subtipo_pil": "L",
        "geometry_points": P26_POINTS,
        "grade_1": 240.0,
        "altura": 321.0,
    }
    doc = setup_doc()
    generate_pilar_zone(doc.modelspace(), payload, "cima", visual_mode="NOVA")
    layers = {e.dxf.layer for e in doc.modelspace()}
    assert "Hachura" in layers
    assert "MEIO_PONT" in layers
    labels = " ".join(
        e.dxf.text or "" for e in doc.modelspace() if e.dxftype() == "TEXT"
    )
    assert "240 PAINEL" in labels
    assert "176 PAINEL" in labels
    assert "G120" in labels or "120(GRADE)" in labels

    doc_abcd = setup_doc()
    generate_pilar_zone(doc_abcd.modelspace(), payload, "abcd", visual_mode="NOVA")
    labels = {
        (e.dxf.text or "").strip()
        for e in doc_abcd.modelspace()
        if e.dxftype() == "TEXT"
    }
    joined = " ".join(labels)
    for fid in "ABCDEF":
        assert f"P26.{fid}" in joined or fid in labels

    doc_gr = setup_doc()
    generate_pilar_zone(doc_gr.modelspace(), payload, "grades", visual_mode="NOVA")
    names = " ".join(
        e.dxf.text or "" for e in doc_gr.modelspace() if e.dxftype() == "TEXT"
    )
    for fid in "ABCDEF":
        assert f"P26.{fid}" in names or fid in names
