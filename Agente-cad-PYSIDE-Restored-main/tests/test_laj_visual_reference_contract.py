from __future__ import annotations

from collections import Counter

from scripts import gerar_lj_dxf_stog as generator


def _l302_data() -> dict:
    return {
        "nome": "L302",
        "comprimento": 418.0,
        "largura": 183.0,
        "coordenadas": [[0, 0], [418, 0], [418, 183], [0, 183]],
        "linhas_verticais": [{"value": 244.0, "is_union": False}],
        "linhas_horizontais": [
            {"value": 102.0, "is_union": False},
            {"value": 122.0, "is_union": False},
        ],
    }


def _panel_edges(msp) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    edges = []
    for entity in msp:
        if entity.dxf.layer != "PAINEIS":
            continue
        if entity.dxftype() == "LINE":
            points = [entity.dxf.start, entity.dxf.end]
        elif entity.dxftype() == "LWPOLYLINE":
            points = list(entity.get_points("xy"))
            if entity.closed:
                points.append(points[0])
        else:
            continue
        for start, end in zip(points, points[1:]):
            a = (round(float(start[0]), 6), round(float(start[1]), 6))
            b = (round(float(end[0]), 6), round(float(end[1]), 6))
            edges.append(tuple(sorted((a, b))))
    return edges


def test_l302_uses_reference_layers_dimstyle_and_solid_union_hatch():
    doc = generator.setup_doc()
    msp = doc.modelspace()

    result = generator.draw_laje_planta(msp, _l302_data(), lambda *_: {})

    assert result[-1] == 6
    assert doc.layers.get("PAINEIS").dxf.color == 6
    assert doc.layers.get("COTA").dxf.color == 241
    assert doc.layers.get("NOMENCLATURA").dxf.color == 7
    style = doc.dimstyles.get("cotas")
    assert (style.dxf.dimtxt, style.dxf.dimasz) == (9.0, 2.0)
    assert (style.dxf.dimexo, style.dxf.dimexe, style.dxf.dimgap) == (2.0, 2.0, 2.0)
    assert (style.dxf.dimclrd, style.dxf.dimclre, style.dxf.dimclrt) == (4, 4, 240)
    assert style.dxf.dimblk.upper() == "_OBLIQUE"

    counts = Counter(entity.dxftype() for entity in msp)
    assert counts == Counter({"DIMENSION": 5, "LWPOLYLINE": 3, "HATCH": 1, "LINE": 1, "TEXT": 1})
    hatch = msp.query("HATCH").first
    assert hatch.dxf.layer == "Hachura"
    assert hatch.dxf.color == 8
    assert hatch.dxf.solid_fill == 1
    vertices = list(hatch.paths[0].vertices)
    assert (min(v[0] for v in vertices), max(v[0] for v in vertices)) == (0.0, 418.0)
    assert (min(v[1] for v in vertices), max(v[1] for v in vertices)) == (102.0, 122.0)


def test_l302_dimensions_match_reference_offsets_and_no_panel_edges_overlap():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    generator.draw_laje_planta(msp, _l302_data(), lambda *_: {})

    dimensions = list(msp.query("DIMENSION"))
    assert sorted(round(dim.get_measurement(), 1) for dim in dimensions) == [20.0, 61.0, 102.0, 174.0, 244.0]
    horizontal = [dim for dim in dimensions if round(dim.get_measurement(), 1) in (174.0, 244.0)]
    vertical = [dim for dim in dimensions if dim not in horizontal]
    assert all(abs(dim.dxf.defpoint.y - (102.0 - generator.DIM_HORIZONTAL_OFFSET_CM)) < 1e-6 for dim in horizontal)
    assert all(abs(dim.dxf.defpoint.x - (244.0 - generator.DIM_VERTICAL_OFFSET_CM)) < 1e-6 for dim in vertical)

    label = msp.query('TEXT[layer=="NOMENCLATURA"]').first
    assert label.dxf.text == "L302"
    assert tuple(label.dxf.insert)[:2] == (122.0, 51.0)
    assert not list(msp.query('LINE[layer=="3"]'))
    assert not list(msp.query('LINE[layer=="Pain\u00e9is"]'))
    edges = _panel_edges(msp)
    assert len(edges) == len(set(edges))


def test_shallow_slab_moves_label_away_from_dimension_texts():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = {
        "nome": "L330",
        "comprimento": 418.0,
        "largura": 71.0,
        "coordenadas": [[0, 0], [418, 0], [418, 71], [0, 71]],
        "linhas_verticais": [{"value": 200.0, "is_union": False}],
        "linhas_horizontais": [{"value": 35.5, "is_union": False}],
    }

    generator.draw_laje_planta(msp, data, lambda *_: {})

    label = msp.query('TEXT[layer=="NOMENCLATURA"]').first
    assert tuple(label.dxf.insert)[:2] == (309.0, 53.25)
    assert sorted(round(dim.get_measurement(), 1) for dim in msp.query("DIMENSION")) == [35.5, 35.5, 200.0, 218.0]
    assert not list(msp.query("HATCH"))
