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
    assert mlines[0].dxf.layer == "SARRAFO_2_2x5"
    assert mlines[0].dxf.style_name == "SAR3"
    assert not [
        e for e in entities
        if e.dxftype() == "LINE" and "SARR" in e.dxf.layer.upper()
    ]

    text = next(e for e in entities if e.dxftype() == "TEXT")
    assert text.dxf.layer == "0"
    assert text.dxf.color == 256
    assert doc.layers.get("SARRAFO_2_2x5").dxf.color == 91


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
