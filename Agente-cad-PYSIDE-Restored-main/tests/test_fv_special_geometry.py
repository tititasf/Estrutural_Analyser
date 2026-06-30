import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "gerar_fv_dxf_stog.py"
sys.path.insert(0, str(GENERATOR.parent))
SPEC = importlib.util.spec_from_file_location("fv_generator_geometry", GENERATOR)
fv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fv)
from fv_l_panel_geometry import (
    derive_quadrilateral_chanfros,
    detect_right_l_panel,
)


def _points(vertices):
    return [(item["x"], item["y"]) for item in vertices]


def test_chanfro_is_inclined_end_edge_not_square_notch():
    vertices = fv.build_chanfro_vertices(
        330, 24, te=0, fe=10, td=0, fd=8
    )

    assert _points(vertices) == [
        (10.0, 0.0),
        (322.0, 0.0),
        (330.0, 24.0),
        (0.0, 24.0),
    ]


def test_chanfro_is_derived_from_quadrilateral_vertices():
    chanfros = derive_quadrilateral_chanfros([
        {"x": 0.0, "y": 0.0},
        {"x": 7.6, "y": 19.0},
        {"x": 254.0, "y": 19.0},
        {"x": 254.0, "y": 0.0},
        {"x": 0.0, "y": 0.0},
    ])

    assert chanfros == {"te": 7.6, "fe": 0.0, "td": 0.0, "fd": 0.0}


def test_derived_top_chanfro_drives_sarrafos_and_dimension_above_panel():
    segments = [{
        "total_width": 254.0,
        "panels": [{
            "width": 254.0,
            "height": 19.0,
            "vertices": [
                {"x": 0.0, "y": 0.0},
                {"x": 7.6, "y": 19.0},
                {"x": 254.0, "y": 19.0},
                {"x": 254.0, "y": 0.0},
            ],
            "tiers": [[122.0, 132.0], [254.0]],
        }],
    }]
    doc = fv.setup_doc()
    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V306",
        label_left="", label_right="",
    )

    assert segments[0]["panels"][0]["chanfros"] == {
        "te": 7.6, "fe": 0.0, "td": 0.0, "fd": 0.0,
    }
    sarr_lines = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LINE" and entity.dxf.layer == fv.SARR_LAYER
    ]
    assert any(
        (round(float(line.dxf.start.x), 1), round(float(line.dxf.start.y), 1),
         round(float(line.dxf.end.x), 1), round(float(line.dxf.end.y), 1))
        == (7.0, 0.0, 14.6, 19.0)
        for line in sarr_lines
    )
    top_chanfro_dims = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "DIMENSION"
        and round(float(entity.get_measurement()), 1) == 7.6
    ]
    assert len(top_chanfro_dims) == 1
    assert float(top_chanfro_dims[0].dxf.defpoint.y) > 19.0

    nomenclature = next(
        entity for entity in doc.modelspace()
        if entity.dxftype() == "TEXT" and entity.dxf.text == "V306.C"
    )
    assert float(nomenclature.dxf.insert.x) == pytest.approx(22.6)

    panel_horizontal_lines = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LINE"
        and entity.dxf.layer == fv.LY_PAINEIS
        and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 1e-6
    ]
    assert panel_horizontal_lines == []


def test_l_panel_uses_length_perpendicular_and_width_transverse():
    entities = fv.build_panel_l_loose(
        main_comp=488,
        main_b=19,
        comp2=200,
        larg2=14,
        tipo="E/T",
        paineis_2=[200],
    )
    polygon = next(item for item in entities if item["type"] == "LWPOLYLINE")
    points = [(point["x"], point["y"]) for point in polygon["points"]]

    assert min(x for x, _ in points) == pytest.approx(-14.0)
    assert max(x for x, _ in points) == pytest.approx(0.0)
    assert min(y for _, y in points) == pytest.approx(0.0)
    assert max(y for _, y in points) == pytest.approx(200.0)


def test_opening_splits_intersecting_horizontal_sarrafo():
    data = {
        "nome": "V303",
        "altura": "24",
        "paineis": ["244", "86"],
        "recuos": ["0", "10", "0", "8"],
        "aberturas": [
            ["0", "0", "0"],
            ["15", "8", "25"],
            ["0", "0", "0"],
            ["0", "0", "0"],
        ],
        "sarrafo_esq": True,
        "sarrafo_dir": True,
    }
    beam = fv.robot_dados_to_fv_dict(data, viga_nome="V303")
    doc = fv.setup_doc()
    fv.draw_viga(
        doc.modelspace(), 0, 0, beam["panels"], beam["b"], beam["nome"],
        label_left="", label_right="",
    )

    lower_lines = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LINE"
        and entity.dxf.layer == fv.SARR_LAYER
        and abs(entity.dxf.start.y - 7.0) < 1e-6
        and abs(entity.dxf.end.y - 7.0) < 1e-6
    ]
    spans = sorted(
        (round(line.dxf.start.x, 2), round(line.dxf.end.x, 2))
        for line in lower_lines
    )

    assert spans == [(14.08, 15.0), (40.0, 317.33)]


def test_pipeline_marker_is_removed_before_drawing_suffix():
    assert fv.normalize_viga_name("V301_n4er.C") == "V301"


def test_multi_segment_does_not_create_overall_dimension():
    segments = [
        {
            "total_width": 300.0,
            "panels": [{"width": 200.0}, {"width": 100.0}],
        },
        {
            "total_width": 250.0,
            "panels": [{"width": 150.0}, {"width": 100.0}],
        },
    ]
    holes = [{"active": True, "width": 20.0, "position": 300.0}]
    doc = fv.setup_doc()

    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V10",
        holes=holes, label_left="", label_right="",
    )

    measurements = [
        round(float(entity.get_measurement()), 2)
        for entity in doc.modelspace()
        if entity.dxftype() == "DIMENSION"
    ]
    assert 300.0 in measurements
    assert 250.0 in measurements
    assert 570.0 not in measurements


def test_dimension_tiers_are_spaced_25_cm_per_layer():
    segments = [{
        "total_width": 200.0,
        "panels": [{
            "width": 200.0,
            "tiers": [[100.0, 100.0], [80.0, 120.0]],
        }],
    }]
    doc = fv.setup_doc()

    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V11",
        label_left="", label_right="",
    )

    horizontal_tier_y = sorted({
        round(float(entity.dxf.defpoint.y), 2)
        for entity in doc.modelspace()
        if entity.dxftype() == "DIMENSION"
        and abs(entity.dxf.defpoint2.y - entity.dxf.defpoint3.y) < 1e-6
    })
    assert horizontal_tier_y == [-50.0, -25.0]


def test_single_polygon_uses_level_one_tier_as_panel_dividers():
    segments = [{
        "total_width": 286.0,
        "panels": [{
            "width": 286.0,
            "height": 19.0,
            "tiers": [[244.0, 42.0], [286.0]],
        }],
    }]
    doc = fv.setup_doc()

    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V305",
        label_left="", label_right="",
    )

    panel_dividers = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LINE"
        and entity.dxf.layer == fv.LY_PAINEIS
        and abs(float(entity.dxf.start.x) - 244.0) < 1e-6
        and abs(float(entity.dxf.end.x) - 244.0) < 1e-6
        and sorted((float(entity.dxf.start.y), float(entity.dxf.end.y)))
        == [0.0, 19.0]
    ]
    assert len(panel_dividers) == 1


def test_composite_name_suppresses_internal_panel_lines_and_end_labels():
    segments = [{
        "total_width": 394.0,
        "panels": [
            {"width": 244.0, "height": 19.0},
            {"width": 150.0, "height": 19.0},
        ],
    }]
    doc = fv.setup_doc()

    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V313-V315-V317",
        label_left="L Esq", label_right="L Dir",
    )

    assert fv.is_composite_viga_name("V313-V315-V317.C")
    assert not fv.is_composite_viga_name("V313.C")
    assert not any(
        entity.dxftype() == "LINE"
        and entity.dxf.layer == fv.LY_PAINEIS
        and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 1e-6
        for entity in doc.modelspace()
    )
    assert any(
        entity.dxftype() == "LINE"
        and entity.dxf.layer == fv.SARR_LAYER
        and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 1e-6
        for entity in doc.modelspace()
    )
    texts = {
        entity.dxf.text
        for entity in doc.modelspace()
        if entity.dxftype() == "TEXT"
    }
    assert "L Esq" not in texts
    assert "L Dir" not in texts
    assert "V313-V315-V317.C" in texts


def test_row_break_keeps_continuation_segments_15_cm_apart():
    segments = [
        {"total_width": 100.0, "panels": [{"width": 100.0}]},
        {
            "total_width": 80.0,
            "row_break": True,
            "panels": [{"width": 80.0}],
        },
    ]
    doc = fv.setup_doc()

    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V301",
        label_left="", label_right="",
    )

    panel_starts = sorted({
        round(min(point[0] for point in entity.get_points("xy")), 2)
        for entity in doc.modelspace()
        if entity.dxftype() == "LWPOLYLINE"
        and entity.dxf.layer == fv.LY_PAINEIS
    })
    assert panel_starts == [0.0, 115.0]


def test_support_text_offsets_distinguish_ends_from_between_segments():
    segments = [
        {
            "total_width": 100.0,
            "texto_esq": "INICIO",
            "texto_dir": "APOIO",
            "panels": [{"width": 100.0}],
        },
        {
            "total_width": 80.0,
            "row_break": True,
            "texto_esq": "APOIO",
            "texto_dir": "FINAL",
            "panels": [{"width": 80.0}],
        },
    ]
    doc = fv.setup_doc()

    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V301",
        label_left="", label_right="",
    )

    labels = {
        entity.dxf.text: (
            round(float(entity.dxf.insert.x), 2),
            round(float(entity.dxf.insert.y), 2),
        )
        for entity in doc.modelspace()
        if entity.dxftype() == "TEXT"
        and entity.dxf.text in {"INICIO", "APOIO", "FINAL"}
    }
    assert labels == {
        "INICIO": (-10.0, -45.0),
        "APOIO": (95.0, -45.0),
        "FINAL": (205.0, -45.0),
    }


def test_multiplier_group_suppresses_internal_texts_and_keeps_next_segment_unique():
    segments = [
        {
            "total_width": 100.0,
            "texto_esq": "A",
            "texto_dir": "B",
            "panels": [{"width": 100.0}],
        },
        {
            "total_width": 40.0,
            "_multiplier": 3,
            "texto_esq": "B",
            "texto_dir": "C",
            "panels": [{"width": 40.0, "height": 19.0}],
        },
        {
            "total_width": 120.0,
            "row_break": True,
            "texto_esq": "C",
            "texto_dir": "D",
            "panels": [
                {"width": 60.0, "height": 0.0, "tiers": [[40.0, 20.0]]},
                {"width": 60.0, "height": 19.0, "tiers": [[40.0, 20.0]]},
            ],
        },
        {
            "total_width": 30.0,
            "texto_esq": "D",
            "texto_dir": "E",
            "panels": [{"width": 30.0}],
        },
    ]
    holes = [
        {"active": True, "width": 10.0, "position": 100.0, "text": "B"},
        # Position intentionally follows the duplicated source segment width.
        # The generator must still match by label after sanitizing the segment.
        {"active": True, "width": 20.0, "position": 270.0, "text": "D"},
    ]
    doc = fv.setup_doc()

    footprint = fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V302",
        holes=holes, label_left="", label_right="",
    )

    panel_starts = sorted({
        round(min(point[0] for point in entity.get_points("xy")), 2)
        for entity in doc.modelspace()
        if entity.dxftype() == "LWPOLYLINE"
        and entity.dxf.layer == fv.LY_PAINEIS
    })
    support_texts = [
        entity.dxf.text
        for entity in doc.modelspace()
        if entity.dxftype() == "TEXT"
        and entity.dxf.layer == "5"
        and entity.dxf.text in {"A", "B", "C", "D", "E"}
    ]

    assert footprint == pytest.approx(385.0)
    assert panel_starts == [0.0, 110.0, 165.0, 220.0, 275.0, 355.0]
    assert support_texts.count("C") == 1
    assert support_texts.count("D") == 1


def test_numpy_vertices_from_l_panel_do_not_break_truth_checks():
    np = pytest.importorskip("numpy")
    segments = [{
        "total_width": 120.0,
        "panels": [{
            "width": 120.0,
            "height": 29.0,
            "vertices": np.array([
                {"x": 0.0, "y": 0.0},
                {"x": 120.0, "y": 0.0},
                {"x": 120.0, "y": 29.0},
                {"x": 0.0, "y": 29.0},
            ], dtype=object),
            "texts": np.array([], dtype=object),
        }],
    }]
    doc = fv.setup_doc()

    footprint = fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V303",
        label_left="", label_right="",
    )

    assert footprint == pytest.approx(120.0)
    assert any(
        entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == fv.LY_PAINEIS
        for entity in doc.modelspace()
    )


def test_right_l_outline_is_split_into_horizontal_and_rotated_panels():
    geometry = detect_right_l_panel([
        {"x": 0.0, "y": 19.0},
        {"x": 193.0, "y": 19.0},
        {"x": 193.0, "y": -30.0},
        {"x": 174.0, "y": -30.0},
        {"x": 174.0, "y": 0.0},
        {"x": 0.0, "y": 0.0},
        {"x": 0.0, "y": 19.0},
    ], 19.0)

    assert geometry == {
        "main_width": 174.0,
        "leaf_width": 19.0,
        "leaf_height": 49.0,
        "drop_depth": 30.0,
        "side": "right",
    }


def test_legacy_right_l_draws_separate_panel_sarrafos_and_dimensions():
    segments = [{
        "total_width": 437.0,
        "panels": [
            {"width": 244.0, "height": 19.0},
            {
                "width": 193.0,
                "height": 49.0,
                "vertices": [
                    {"x": 0.0, "y": 19.0},
                    {"x": 193.0, "y": 19.0},
                    {"x": 193.0, "y": -30.0},
                    {"x": 174.0, "y": -30.0},
                    {"x": 174.0, "y": 0.0},
                    {"x": 0.0, "y": 0.0},
                ],
            },
        ],
    }]
    fv._split_legacy_right_l_panels(segments, 19.0)
    assert [panel["width"] for panel in segments[0]["panels"]] == [244.0, 174.0, 19.0]

    doc = fv.setup_doc()
    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V303",
        label_left="", label_right="",
    )

    panel_boxes = sorted(
        tuple(round(value, 1) for value in (
            min(point[0] for point in entity.get_points("xy")),
            max(point[0] for point in entity.get_points("xy")),
            min(point[1] for point in entity.get_points("xy")),
            max(point[1] for point in entity.get_points("xy")),
        ))
        for entity in doc.modelspace()
        if entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == fv.LY_PAINEIS
    )
    assert panel_boxes == [
        (0.0, 244.0, 0.0, 19.0),
        (244.0, 418.0, 0.0, 19.0),
        (418.0, 437.0, -30.0, 19.0),
    ]

    contaminating_panel_lines = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LINE"
        and entity.dxf.layer == fv.LY_PAINEIS
        and abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) < 1e-6
        and min(float(entity.dxf.start.x), float(entity.dxf.end.x)) >= 244.0
    ]
    assert contaminating_panel_lines == []

    sarr_lines = [
        (
            round(float(entity.dxf.start.x), 1),
            round(float(entity.dxf.start.y), 1),
            round(float(entity.dxf.end.x), 1),
            round(float(entity.dxf.end.y), 1),
        )
        for entity in doc.modelspace()
        if entity.dxftype() == "LINE" and entity.dxf.layer == fv.SARR_LAYER
    ]
    assert (425.0, 0.0, 425.0, -23.0) in sarr_lines
    assert (430.0, 0.0, 430.0, -23.0) in sarr_lines
    assert (418.0, 0.0, 437.0, 0.0) in sarr_lines
    assert (418.0, -23.0, 437.0, -23.0) in sarr_lines
    assert not any(
        x1 == x2 == 430.0 and min(y1, y2) >= 0.0 and max(y1, y2) == 19.0
        for x1, y1, x2, y2 in sarr_lines
    )
    assert any(
        y1 == y2 and max(x1, x2) == 437.0 and y1 > 0.0
        for x1, y1, x2, y2 in sarr_lines
    )

    measurements = sorted(
        round(float(entity.get_measurement()), 1)
        for entity in doc.modelspace()
        if entity.dxftype() == "DIMENSION"
    )
    for expected in (19.0, 49.0, 174.0, 244.0, 437.0):
        assert expected in measurements


def test_multiplier_repeats_the_independent_l_panel_once_per_copy():
    segments = [{
        "total_width": 437.0,
        "_multiplier": 2,
        "panels": [
            {"width": 244.0, "height": 19.0},
            {"width": 174.0, "height": 19.0},
            {
                "width": 19.0,
                "height": 49.0,
                "is_L_drop": True,
                "l_side": "right",
            },
        ],
    }]
    doc = fv.setup_doc()
    fv.draw_viga(
        doc.modelspace(), 0, 0, segments, 19.0, "V303",
        label_left="", label_right="",
    )

    l_panels = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LWPOLYLINE"
        and entity.dxf.layer == fv.LY_PAINEIS
        and round(max(point[0] for point in entity.get_points("xy"))
                  - min(point[0] for point in entity.get_points("xy")), 1) == 19.0
        and round(max(point[1] for point in entity.get_points("xy"))
                  - min(point[1] for point in entity.get_points("xy")), 1) == 49.0
    ]
    assert len(l_panels) == 2
