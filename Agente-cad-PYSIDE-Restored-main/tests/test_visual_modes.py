from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from visual_modes import (  # noqa: E402
    apply_visual_mode,
    normalize_visual_mode,
    _align_panel_centerline,
    _wall_flush_center_x,
)


def _snapshot(doc) -> tuple:
    entities = tuple(
        (e.dxftype(), e.dxf.get("layer", "0"), e.dxf.get("color", 256))
        for e in doc.modelspace()
    )
    layers = tuple(
        sorted((layer.dxf.name, layer.dxf.color) for layer in doc.layers)
    )
    return entities, layers


def test_nova_is_strict_noop():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_2.2x7", color=40)
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={
        "layer": "SARR_2.2x7",
        "color": 3,
    })
    before = _snapshot(doc)

    stats = apply_visual_mode(doc, "NOVA", "FV")

    assert stats.mlines_created == 0
    assert stats.remapped_entities == 0
    assert _snapshot(doc) == before


@pytest.mark.parametrize("value", ["ini", " INI ", "Ini"])
def test_normalizes_ini(value):
    assert normalize_visual_mode(value) == "INI"


def test_rejects_unknown_mode():
    with pytest.raises(ValueError):
        normalize_visual_mode("experimental")


def test_ini_pl_pressure_hidden_stays_line_opening_sarr_becomes_mline():
    """INI PL: pressão HIDDEN = LINE; SARR sólido de abertura = MLINE."""
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_2.2x7", color=40)
    doc.layers.add("Sarrafo de Pressão", color=42)
    try:
        doc.layers.get("Sarrafo de Pressão").dxf.linetype = "HIDDEN"
    except Exception:
        pass
    if "HIDDEN" not in doc.linetypes:
        doc.linetypes.add(
            "HIDDEN",
            pattern=[9.525, 6.35, -3.175],
            description="Hidden",
        )
    msp = doc.modelspace()
    # pressão (deve ficar LINE)
    msp.add_lwpolyline(
        [(7, 0), (7, 100)],
        dxfattribs={"layer": "Sarrafo de Pressão", "linetype": "HIDDEN"},
    )
    # abertura sólida (deve virar MLINE)
    msp.add_line(
        (20, 0),
        (20, 100),
        dxfattribs={"layer": "SARR_2.2x7"},
    )

    stats = apply_visual_mode(doc, "INI", "PL")

    mlines = list(msp.query("MLINE"))
    assert stats.mlines_created == 1
    assert len(mlines) == 1
    assert "SARR" in mlines[0].dxf.layer.upper() or "SARRAFO" in mlines[0].dxf.layer.upper()
    # pressão permanece como LINE/LWPOLY (não MLINE)
    press_left = [
        e
        for e in msp
        if e.dxftype() in ("LINE", "LWPOLYLINE")
        and "press" in str(e.dxf.layer).casefold()
    ]
    assert len(press_left) >= 1
    assert not any(
        e.dxftype() == "MLINE" and "press" in str(e.dxf.layer).casefold()
        for e in msp
    )


def test_ini_fundo_remaps_layers_and_creates_real_mline():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_2.2x7", color=40)
    doc.layers.add("NOMENCLATURA", color=7)
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={
        "layer": "SARR_2.2x7",
        "color": 3,
    })
    msp.add_text("V1", dxfattribs={"layer": "NOMENCLATURA"})

    stats = apply_visual_mode(doc, "INI", "FV")

    entities = list(msp)
    mlines = [e for e in entities if e.dxftype() == "MLINE"]
    assert stats.mlines_created == 1
    assert len(mlines) == 1
    assert mlines[0].dxf.layer == "SARRAFO_2_2X7"
    assert mlines[0].dxf.style_name == "SAR3"
    assert mlines[0].dxf.scale_factor == pytest.approx(7.0)
    assert not [
        e for e in entities
        if e.dxftype() == "LINE" and "SARR" in e.dxf.layer.upper()
    ]

    text = next(e for e in entities if e.dxftype() == "TEXT")
    assert text.dxf.layer == "0"
    assert text.dxf.color == 256
    assert doc.layers.get("SARRAFO_2_2X7").dxf.color == 30


def test_ini_fundo_aligns_horizontal_and_vertical_sarrafos_inward():
    doc = ezdxf.new("R2018")
    doc.layers.add("Painéis", color=6)
    doc.layers.add("SARR_2.2x7", color=40)
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (100, 0), (100, 19), (0, 19)],
        close=True,
        dxfattribs={"layer": "Painéis"},
    )
    layer = {"layer": "SARR_2.2x7"}
    msp.add_line((7, 0), (7, 19), dxfattribs=layer)
    msp.add_line((93, 0), (93, 19), dxfattribs=layer)
    msp.add_line((7, 7), (93, 7), dxfattribs=layer)
    msp.add_line((7, 12), (93, 12), dxfattribs=layer)

    apply_visual_mode(doc, "INI", "FV")

    axes = []
    for entity in msp.query("MLINE"):
        locations = [vertex.location for vertex in entity.vertices]
        axes.append((
            round(float(locations[0].x), 1),
            round(float(locations[0].y), 1),
            round(float(locations[1].x), 1),
            round(float(locations[1].y), 1),
            round(float(entity.dxf.scale_factor), 1),
        ))
    assert set(axes) == {
        (3.5, 0.0, 3.5, 19.0, 7.0),
        (96.5, 0.0, 96.5, 19.0, 7.0),
        (7.0, 3.5, 93.0, 3.5, 7.0),
        (7.0, 15.5, 93.0, 15.5, 7.0),
    }


def test_ini_pilar_aligns_open_sarrafos_to_line_built_panel_edges():
    doc = ezdxf.new("R2018")
    doc.layers.add("Painéis", color=6)
    doc.layers.add("SARR_2.2x7", color=40)
    msp = doc.modelspace()
    panel = {"layer": "Painéis"}
    msp.add_line((0, 0), (100, 0), dxfattribs=panel)
    msp.add_line((100, 0), (100, 19), dxfattribs=panel)
    msp.add_line((100, 19), (0, 19), dxfattribs=panel)
    msp.add_line((0, 19), (0, 0), dxfattribs=panel)
    sarrafo = {"layer": "SARR_2.2x7"}
    msp.add_lwpolyline([(7, 0), (7, 19)], dxfattribs=sarrafo)
    msp.add_lwpolyline([(93, 0), (93, 19)], dxfattribs=sarrafo)
    msp.add_lwpolyline([(0, 9), (100, 9)], dxfattribs=sarrafo)
    msp.add_lwpolyline([(0, 12), (100, 12)], dxfattribs=sarrafo)

    apply_visual_mode(doc, "INI", "PL")

    axes = []
    for entity in msp.query("MLINE"):
        locations = [vertex.location for vertex in entity.vertices]
        axes.append((
            round(float(locations[0].x), 1),
            round(float(locations[0].y), 1),
            round(float(locations[1].x), 1),
            round(float(locations[1].y), 1),
            round(float(entity.dxf.scale_factor), 1),
        ))
    assert set(axes) == {
        (3.5, 0.0, 3.5, 19.0, 7.0),
        (96.5, 0.0, 96.5, 19.0, 7.0),
        (0.0, 5.5, 100.0, 5.5, 7.0),
        (0.0, 15.5, 100.0, 15.5, 7.0),
    }


def test_ini_can_add_alias_for_an_empty_source_layer():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARRAFO DE PRESSAO", color=251)

    apply_visual_mode(doc, "INI", "FV")

    assert "Sarrafo_de_pressao" in doc.layers
    assert doc.layers.get("Sarrafo_de_pressao").dxf.color == 1


def test_ini_collapses_closed_rectangle_to_one_solid_centerline():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_2.2x7", color=40)
    doc.modelspace().add_lwpolyline(
        [(0, 0), (100, 0), (100, 2.2), (0, 2.2)],
        close=True,
        dxfattribs={"layer": "SARR_2.2x7"},
    )

    stats = apply_visual_mode(doc, "INI", "LV")

    mlines = list(doc.modelspace().query("MLINE"))
    assert len(mlines) == 1
    assert stats.rectangles_collapsed == 1
    assert not list(doc.modelspace().query("LWPOLYLINE"))
    assert mlines[0].dxf.scale_factor == pytest.approx(2.2)
    assert mlines[0].dxf.justification == 1
    locations = [vertex.location for vertex in mlines[0].vertices]
    assert locations[0].x == pytest.approx(0)
    assert locations[0].y == pytest.approx(1.1)
    assert locations[1].x == pytest.approx(100)
    assert locations[1].y == pytest.approx(1.1)

    style = doc.mline_styles.get("SAR3")
    assert style.dxf.flags & style.FILL
    assert style.dxf.fill_color == 256


def test_ini_collapses_four_line_rectangle_using_real_width():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_2.2x7", color=40)
    msp = doc.modelspace()
    layer = {"layer": "SARR_2.2x7"}
    msp.add_line((0, 0), (7, 0), dxfattribs=layer)
    msp.add_line((7, 0), (7, 120), dxfattribs=layer)
    msp.add_line((7, 120), (0, 120), dxfattribs=layer)
    msp.add_line((0, 120), (0, 0), dxfattribs=layer)

    stats = apply_visual_mode(doc, "INI", "PL")

    mlines = list(msp.query("MLINE"))
    assert len(mlines) == 1
    assert stats.rectangles_collapsed == 1
    assert not list(msp.query("LINE"))
    assert mlines[0].dxf.scale_factor == pytest.approx(7.0)
    locations = [vertex.location for vertex in mlines[0].vertices]
    assert locations[0].x == pytest.approx(3.5)
    assert locations[1].x == pytest.approx(3.5)


def test_ini_pilar_grades_preserves_mline_classes_widths_and_colors():
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    specs = (
        ("SARR_2.2x7", 2.2, 30),
        ("SARR_2.2x10", 10.0, 60),
        ("SARR_3.5x7", 3.5, 7),
    )
    for index, (layer_name, width, _color) in enumerate(specs):
        doc.layers.add(layer_name, color=40)
        y0 = index * 20.0
        layer = {"layer": layer_name}
        msp.add_line((0, y0), (100, y0), dxfattribs=layer)
        msp.add_line((100, y0), (100, y0 + width), dxfattribs=layer)
        msp.add_line(
            (100, y0 + width), (0, y0 + width), dxfattribs=layer
        )
        msp.add_line((0, y0 + width), (0, y0), dxfattribs=layer)

    apply_visual_mode(doc, "INI", "PL")

    mlines = list(msp.query("MLINE"))
    assert len(mlines) == 3
    actual = {
        entity.dxf.layer: (
            float(entity.dxf.scale_factor),
            int(entity.dxf.color),
            int(doc.layers.get(entity.dxf.layer).dxf.color),
        )
        for entity in mlines
    }
    assert actual == {
        "SARRAFO_2_2X7": (2.2, 256, 30),
        "SARR_2.2x10": (10.0, 256, 60),
        "SARR_3.5x7": (3.5, 256, 7),
    }


def test_ini_pilar_cima_classifies_grade_wood_without_touching_open_wood():
    doc = ezdxf.new("R2018")
    doc.layers.add("Madeira", color=30)
    msp = doc.modelspace()
    # Vista CIMA em escala 2x: secoes 7x7 e 3.5x7 viram 14x14 e 7x14.
    msp.add_lwpolyline(
        [(0, 0), (100, 0), (100, 14), (0, 14)],
        close=True,
        dxfattribs={"layer": "Madeira"},
    )
    msp.add_lwpolyline(
        [(20, 0), (27, 0), (27, 14), (20, 14)],
        close=True,
        dxfattribs={"layer": "Madeira"},
    )
    # Outra secao do pilar usa Madeira como eixo aberto e deve ser preservada.
    open_wood = msp.add_lwpolyline(
        [(0, 50), (100, 50)],
        dxfattribs={"layer": "Madeira"},
    )

    apply_visual_mode(doc, "INI", "PL")

    actual = {
        (entity.dxf.layer, float(entity.dxf.scale_factor))
        for entity in msp.query("MLINE")
    }
    assert actual == {("SARR_7x7", 14.0), ("SARR_3.5x7", 7.0)}
    assert open_wood.is_alive
    assert open_wood.dxf.layer == "Madeira"
    assert doc.layers.get("SARR_7x7").dxf.color == 100
    assert doc.layers.get("SARR_3.5x7").dxf.color == 7


def test_ini_lateral_faces_use_scr_planar_width_and_distinct_classes():
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    specs = (
        ("SARR_2.2x7", "SARRAFO_2_2X7", 7.0, 30),
        ("SARR_2.2x10", "SARR_2.2x10", 10.0, 60),
        ("SARR_2.2x5", "SARRAFO_2_2x5", 5.0, 91),
        ("SARR_2.2x3.5", "SARR_2.2x3.5", 3.5, 71),
        ("SARR_3.5x7", "SARR_3.5x7", 7.0, 7),
        ("MEIOPONTALETE", "MEIOPONTALETE", 14.0, 160),
    )
    for index, (source, _target, _width, _color) in enumerate(specs):
        doc.layers.add(source, color=40)
        msp.add_line(
            (0, index * 20.0),
            (100, index * 20.0),
            dxfattribs={"layer": source},
        )

    apply_visual_mode(doc, "INI", "LV")

    actual = {
        entity.dxf.layer: (
            float(entity.dxf.scale_factor),
            int(doc.layers.get(entity.dxf.layer).dxf.color),
        )
        for entity in msp.query("MLINE")
    }
    assert actual == {
        target: (width, color)
        for _source, target, width, color in specs
    }


def test_ini_lateral_corte_prefers_drawn_section_width():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARRAFO_2_2X7", color=40)
    msp = doc.modelspace()
    layer = {"layer": "SARRAFO_2_2X7"}
    msp.add_line((0, 0), (20, 0), dxfattribs=layer)
    msp.add_line((20, 0), (20, 4.4), dxfattribs=layer)
    msp.add_line((20, 4.4), (0, 4.4), dxfattribs=layer)
    msp.add_line((0, 4.4), (0, 0), dxfattribs=layer)

    apply_visual_mode(doc, "INI", "LV")

    mlines = list(msp.query("MLINE"))
    assert len(mlines) == 1
    assert mlines[0].dxf.layer == "SARRAFO_2_2X7"
    assert mlines[0].dxf.scale_factor == pytest.approx(4.4)


def test_ini_lateral_corte_keeps_horizontal_axis_for_near_square_section():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARRAFO_2_2X7", color=40)
    msp = doc.modelspace()
    layer = {"layer": "SARRAFO_2_2X7"}
    msp.add_line((10, 20), (14, 20), dxfattribs=layer)
    msp.add_line((14, 20), (14, 24.4), dxfattribs=layer)
    msp.add_line((14, 24.4), (10, 24.4), dxfattribs=layer)
    msp.add_line((10, 24.4), (10, 20), dxfattribs=layer)

    apply_visual_mode(doc, "INI", "LV")

    mline = next(iter(msp.query("MLINE")))
    locations = [vertex.location for vertex in mline.vertices]
    assert mline.dxf.scale_factor == pytest.approx(4.4)
    assert locations[0].x == pytest.approx(10)
    assert locations[0].y == pytest.approx(22.2)
    assert locations[1].x == pytest.approx(14)
    assert locations[1].y == pytest.approx(22.2)


def test_ini_lateral_does_not_convert_layer_presence_sentinel():
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_3.5x7", color=81)
    sentinel = doc.modelspace().add_line(
        (-9000, 0),
        (-8990, 0),
        dxfattribs={"layer": "SARR_3.5x7"},
    )

    apply_visual_mode(doc, "INI", "LV")

    assert not list(doc.modelspace().query("MLINE"))
    assert sentinel.is_alive
    assert sentinel.dxf.layer == "SARR_3.5x7"


def test_wall_flush_center_aligns_opening_sarr():
    """Eixo a 7cm da parede + thickness 7 → centro 3.5 (MLINE flush na parede)."""
    boxes = [(80.0, -158.0, 157.0, -100.0)]
    assert _wall_flush_center_x(150.0, 7.0, boxes, 2.5) == pytest.approx(153.5)
    # trecho no vao (fora do box) tambem alinha
    verts = [(150.0, -224.0), (150.0, -158.0)]
    aligned = _align_panel_centerline(verts, 7.0, boxes, edge_extra=2.5)
    assert aligned[0][0] == pytest.approx(153.5)
    assert aligned[1][0] == pytest.approx(153.5)
    # braco L horizontal parede→eixo (+ Y flush sob a abertura)
    h = [(157.0, -224.0), (150.0, -224.0)]
    ah = _align_panel_centerline(h, 7.0, boxes, edge_extra=2.5)
    assert ah[0][0] == pytest.approx(157.0)
    assert ah[1][0] == pytest.approx(153.5)
    assert ah[0][1] == pytest.approx(-227.5)
    assert ah[1][1] == pytest.approx(-227.5)
    # polilinha L continua: X flush parede + Y desce th/2 (face sup. no fundo abertura)
    L = [(157.0, -224.0), (150.0, -224.0), (150.0, -231.0), (161.0, -231.0)]
    aL = _align_panel_centerline(L, 7.0, boxes, edge_extra=2.5)
    assert aL[0][0] == pytest.approx(157.0)
    assert aL[1][0] == pytest.approx(153.5)
    assert aL[2][0] == pytest.approx(153.5)
    assert aL[3][0] == pytest.approx(161.0)
    # y original -224 → -227.5 (centro do MLINE 7cm; face superior em -224)
    assert aL[0][1] == pytest.approx(-227.5)
    assert aL[1][1] == pytest.approx(-227.5)
    assert aL[2][1] == pytest.approx(-234.5)
    assert aL[3][1] == pytest.approx(-234.5)


def test_ini_opening_l_mline_flushes_to_wall():
    """INI: fuste seccionado no vao e no solido ficam no mesmo X (flush parede)."""
    doc = ezdxf.new("R2018")
    doc.layers.add("SARR_2.2x7", color=40)
    doc.layers.add("Painéis", color=7)
    msp = doc.modelspace()
    # painel solido a esquerda da parede 157
    msp.add_line((80, -158), (157, -158), dxfattribs={"layer": "Painéis"})
    msp.add_line((80, -100), (157, -100), dxfattribs={"layer": "Painéis"})
    msp.add_line((80, -158), (80, -100), dxfattribs={"layer": "Painéis"})
    msp.add_line((157, -158), (157, -100), dxfattribs={"layer": "Painéis"})
    # parede de abertura continua no vao
    msp.add_line((157, -224), (157, -158), dxfattribs={"layer": "Painéis"})
    layer = {"layer": "SARR_2.2x7"}
    # fuste seccionado: vao + solido
    msp.add_line((150, -224), (150, -158), dxfattribs=layer)
    msp.add_line((150, -158), (150, -100), dxfattribs=layer)
    # L
    msp.add_lwpolyline(
        [(157, -224), (150, -224), (150, -231), (161, -231)],
        close=False,
        dxfattribs=layer,
    )
    apply_visual_mode(doc, "INI", "PL")
    xs = []
    l_ys = []
    for e in msp.query("MLINE"):
        verts = list(e.vertices)
        pts = [(float(v.location.x), float(v.location.y)) for v in verts]
        for x, y in pts:
            xs.append(round(x, 2))
        # L tem 3+ vertices
        if len(pts) >= 3:
            l_ys = [y for _, y in pts]
    # eixos do fuste/L (exceto pressao 161 e parede 157) em ~153.5
    sarr_xs = [x for x in xs if 148 <= x <= 156]
    assert sarr_xs, xs
    assert all(abs(x - 153.5) < 0.2 for x in sarr_xs), sarr_xs
    # L desceu th/2: topo do H em -224 (face) → centro -227.5
    assert l_ys, "L MLINE multi-vertex esperado"
    assert max(l_ys) == pytest.approx(-227.5, abs=0.2)
