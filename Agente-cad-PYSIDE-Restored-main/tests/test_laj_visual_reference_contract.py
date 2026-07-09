from __future__ import annotations

from collections import Counter

from scripts import gerar_lj_dxf_stog as generator
from scripts.smart_panner import distribute_panels


def _l302_data() -> dict:
    return {
        "nome": "L302",
        "comprimento": 418.0,
        "largura": 183.0,
        "coordenadas": [[0, 0], [418, 0], [418, 183], [0, 183]],
        "linhas_verticais": [
            {"value": 244.0, "is_union": False},
            {"value": 2413.0, "is_union": False},
        ],
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
    assert counts == Counter({"DIMENSION": 5, "LINE": 3, "LWPOLYLINE": 1, "HATCH": 1, "TEXT": 1})
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


def test_draws_extracted_support_hatch_without_changing_panel_geometry():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = _l302_data() | {
        "apoios_hachurados": [
            {"x1": -19.0, "y1": -31.0, "x2": 0.0, "y2": -12.0},
            {"x1": -19.0, "y1": -19.0, "x2": 0.0, "y2": 0.0},
        ],
    }

    generator.draw_laje_planta(msp, data, distribute_panels)

    support_lines = list(msp.query('LINE[layer=="3"]'))
    assert len(support_lines) == 2
    assert [
        (tuple(line.dxf.start)[:2], tuple(line.dxf.end)[:2])
        for line in support_lines
    ] == [
        ((-19.0, -31.0), (0.0, -12.0)),
        ((-19.0, -19.0), (0.0, 0.0)),
    ]
    assert len(_panel_edges(msp)) == 7


def test_l320_label_keeps_clearance_from_vertical_dimension_text():
    polygon = [(0.0, 0.0), (418.0, 0.0), (418.0, 423.0), (0.0, 423.0)]
    v_positions = [122.0, 148.0, 270.0, 296.0]
    h_positions = [179.0]
    panel_x = 270.0
    panel_y = 179.0

    label_x, _ = generator._label_position_clear_of_dimensions(
        polygon, v_positions, h_positions, 0.0, 0.0, 418.0, 423.0,
        panel_x, panel_y,
    )

    vertical_text_x = panel_x - generator.DIM_VERTICAL_OFFSET_CM - 8.0
    assert abs(label_x - vertical_text_x) >= 70.0


def test_extracted_cotas_keep_canonical_dimensions_and_local_hlaz_is_solid_fill():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = {
        "nome": "LTEST",
        "comprimento": 3139.0,
        "largura": 201.0,
        "coordenadas": [
            [2413.0, 0.0], [2413.0, 49.0], [0.0, 49.0], [0.0, 201.0],
            [3139.0, 201.0], [3139.0, 0.0], [2413.0, 0.0],
        ],
        "linhas_verticais": [
            {"value": 244.0, "is_union": False},
            {"value": 2413.0, "is_union": False},
        ],
        "linhas_horizontais": [
            {
                "value": 89.5,
                "is_union": False,
                "segments": [{"x0": 2413.0, "x1": 3139.0}],
            },
            {
                "value": 109.5,
                "is_union": True,
                "segments": [{"x0": 0.0, "x1": 3139.0}],
            },
        ],
        "_hlaz": [{"x": 2413.0, "y": 89.5, "width": 726.0, "height": 20.0}],
        "cotas_paineis": [
            {"text": "91.5", "x": 2488.0, "y": 168.5, "rotation": 0.0, "height": 9.0},
            {"text": "60.5", "x": 779.0, "y": 85.4, "rotation": 0.0, "height": 9.0},
        ],
    }

    generator.draw_laje_planta(msp, data, lambda *_: {})

    dimensions = list(msp.query("DIMENSION"))
    measurements = sorted(round(dim.get_measurement(), 1) for dim in dimensions)
    assert 2413.0 in measurements
    assert 726.0 in measurements
    assert {20.0, 40.5, 49.0, 89.5, 91.5}.issubset(set(measurements))
    vertical_dims = [
        dim for dim in dimensions
        if round(dim.get_measurement(), 1) in {20.0, 89.5, 91.5}
    ]
    assert vertical_dims
    assert any(dim.dxf.defpoint.x > 2413.0 for dim in vertical_dims)
    assert any(dim.dxf.defpoint.x < 2413.0 for dim in vertical_dims)
    assert not list(msp.query('TEXT[layer=="PAINEIS"]'))
    assert not list(msp.query('LWPOLYLINE[layer=="Hachura"]'))
    hatches = list(msp.query('HATCH[layer=="Hachura"]'))
    assert len(hatches) == 1
    hlaz_vertices = list(hatches[0].paths[0].vertices)
    assert (min(v[0] for v in hlaz_vertices), max(v[0] for v in hlaz_vertices)) == (2413.0, 3139.0)
    assert (min(v[1] for v in hlaz_vertices), max(v[1] for v in hlaz_vertices)) == (89.5, 109.5)


def test_noisy_extracted_long_axis_is_replaced_by_preferred_panel_modules():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = {
        "nome": "L318",
        "comprimento": 3139.0,
        "largura": 201.0,
        "coordenadas": [
            [2413.0, 0.0], [2413.0, 49.0], [0.0, 49.0], [0.0, 201.0],
            [3139.0, 201.0], [3139.0, 0.0], [2413.0, 0.0],
        ],
        "linhas_verticais": [
            {"value": value, "is_union": False}
            for value in (58.0, 244.0, 320.5, 564.5, 769.0, 808.5, 1052.5)
        ],
        "linhas_horizontais": [
            {"value": 89.5, "is_union": False, "segments": [{"x0": 2413.0, "x1": 3139.0}]},
            {"value": 109.5, "is_union": True},
        ],
        "_hlaz": [{"x": 2413.0, "y": 89.5, "width": 726.0, "height": 20.0}],
    }

    generator.draw_laje_planta(msp, data, lambda comp, larg, *_: {
        "linhas_verticais": [{"value": x, "is_union": False} for x in range(244, 2929, 244)],
        "linhas_horizontais": [{"value": 122.0, "is_union": False}],
    })

    dimensions = list(msp.query("DIMENSION"))
    measurements = sorted(round(dim.get_measurement(), 1) for dim in dimensions)
    dims_by_value = {
        round(dim.get_measurement(), 1): dim
        for dim in dimensions
    }
    assert 58.0 not in measurements
    assert 76.5 not in measurements
    assert measurements.count(244.0) >= 10
    assert 211.0 not in measurements
    assert 217.0 in measurements
    assert 238.0 in measurements

    vertical_lines = sorted(set(
        round(entity.dxf.start.x, 1)
        for entity in msp.query('LINE')
        if entity.dxf.layer.upper() == 'PAINEIS'
        and abs(entity.dxf.start.x - entity.dxf.end.x) < 0.1
    ))
    assert 2413.0 in vertical_lines
    assert 2440.0 not in vertical_lines


def test_diagonal_cut_slab_adds_projection_dimensions_for_special_panels():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = {
        "nome": "L319",
        "comprimento": 405.5,
        "largura": 613.0,
        "coordenadas": [
            [405.5, 423.0], [182.5, 423.0], [182.5, 613.0],
            [0.0, 613.0], [0.0, 150.51], [158.85, 0.04],
            [405.5, 0.0], [405.5, 423.0],
        ],
        "linhas_verticais": [
            {"value": 122.0, "is_union": False},
            {"value": 142.0, "is_union": True},
            {"value": 264.0, "is_union": False},
            {"value": 284.4, "is_union": True},
        ],
        "linhas_horizontais": [
            {"value": 244.0, "is_union": False},
            {"value": 488.0, "is_union": False, "segments": [{"x0": 0.0, "x1": 182.5}]},
        ],
    }

    generator.draw_laje_planta(msp, data, lambda *_: {})

    measurements = sorted(round(dim.get_measurement(), 1) for dim in msp.query("DIMENSION"))
    assert len(measurements) == 17
    # Projeções do degrau superior: largura dos dois trechos até as linhas de painel.
    assert 40.5 in measurements
    assert 81.5 in measurements
    # Projeções verticais que permitem rastrear o recorte em L/chanfro.
    for value in (65.0, 93.5, 179.0, 209.1, 228.0):
        assert value in measurements
    # A cota alinhada/diagonal do chanfro não deve aparecer; o corte fica
    # rastreável pelas projeções ortogonais.
    assert 218.8 not in measurements


def test_shallow_diagonal_cut_slab_adds_orthogonal_cut_dimensions_without_diagonal():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = {
        "nome": "L326",
        "comprimento": 233.74,
        "largura": 71.0,
        "coordenadas": [
            [0.0, 71.0],
            [233.74, 71.0],
            [233.74, 66.0],
            [231.24, 66.0],
            [231.24, 0.0],
            [75.01, 0.0],
            [0.0, 71.0],
        ],
        "linhas_verticais": [
                {
                    "value": 116.8,
                    "is_union": False,
                    "exact": True,
                    "segments": [{"y0": 0.0, "y1": 71.0}],
                },
            ],
            "linhas_horizontais": [{"value": 35.6, "is_union": False, "exact": True}],
        "_stog_pose": {"x": 2914.33, "y": 1577.94},
    }

    generator.draw_laje_planta(msp, data, lambda *_: {})

    dimensions = list(msp.query("DIMENSION"))
    measurements = sorted(round(dim.get_measurement(), 1) for dim in dimensions)
    dims_by_value = {
        round(dim.get_measurement(), 1): dim
        for dim in dimensions
    }
    assert len(measurements) == 9
    for value in (5.0, 41.8, 79.4, 114.4, 116.8, 116.9):
        assert value in measurements
    assert measurements.count(116.8) == 1
    assert measurements.count(116.9) == 1
    # Não cotar micro-notch como se fosse parede de painel.
    assert 2.5 not in measurements
    # O chanfro deve ser rastreável por projeções ortogonais, nunca por cota
    # alinhada/diagonal direta.
    assert 103.3 not in measurements
    # As cotas de recorte devem ficar para dentro da area util: a base 41,8
    # acima da parede inferior e as verticais direitas a esquerda das paredes.
    assert dims_by_value[41.8].dxf.defpoint.y > dims_by_value[41.8].dxf.defpoint2.y
    assert dims_by_value[5.0].dxf.defpoint.x < dims_by_value[5.0].dxf.defpoint2.x
    assert dims_by_value[30.4].dxf.defpoint.x < dims_by_value[30.4].dxf.defpoint2.x


def test_shallow_side_notch_does_not_dimension_raw_lateral_total():
    doc = generator.setup_doc()
    msp = doc.modelspace()
    data = {
        "nome": "L327",
        "comprimento": 418.0,
        "largura": 71.0,
        "coordenadas": [
            [2.5, 0.0],
            [415.5, 0.0],
            [415.5, 52.0],
            [418.0, 52.0],
            [418.0, 71.0],
            [0.0, 71.0],
            [0.0, 52.0],
            [2.5, 52.0],
            [2.5, 0.0],
        ],
        "linhas_verticais": [
            {
                "value": 238.5,
                "is_union": False,
                "exact": True,
                "segments": [{"y0": 0.0, "y1": 70.9}],
            },
        ],
        "linhas_horizontais": [
            {
                "value": 35.4,
                "is_union": False,
                "exact": True,
                "segments": [{"x0": 2.5, "x1": 415.5}],
            }
        ],
    }

    generator.draw_laje_planta(msp, data, distribute_panels)

    measurements = sorted(round(dim.get_measurement(), 1) for dim in msp.query("DIMENSION"))
    assert 52.0 not in measurements
    assert measurements.count(17.0) == 3
    assert measurements.count(19.0) == 3
    assert 35.4 not in measurements
    assert 35.6 not in measurements
    for value in (35.0, 36.0, 177.0, 179.5, 236.0, 238.5):
        assert value in measurements
