import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "gerar_fv_dxf_stog.py"
SPEC = importlib.util.spec_from_file_location("fv_generator_geometry", GENERATOR)
fv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fv)


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
