from __future__ import annotations

import json
import sqlite3

import ezdxf

from scripts import motor_reverso_laj as laj_motor
from scripts import gerar_lj_dxf_stog as laj_generator

_extract_laj_from_dxf = laj_motor._extract_laj_from_dxf


def _add_rect_lines(msp, layer: str, width: float, height: float) -> None:
    msp.add_line((0, 0), (width, 0), dxfattribs={"layer": layer})
    msp.add_line((width, 0), (width, height), dxfattribs={"layer": layer})
    msp.add_line((width, height), (0, height), dxfattribs={"layer": layer})
    msp.add_line((0, height), (0, 0), dxfattribs={"layer": layer})


def test_extracts_dimensions_from_geometry_and_cotas_with_arbitrary_layer(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    layer = "OBRA_X_MALHA_ABC"
    _add_rect_lines(msp, layer, 418.0, 179.7)
    msp.add_line((244, 0), (244, 179.7), dxfattribs={"layer": layer})
    for value, x in ((244, 120), (174, 330)):
        msp.add_text(str(value), dxfattribs={"layer": layer, "rotation": 0}).set_placement((x, 20))
    for value, y in ((102, 50), (20, 112), (61, 150)):
        msp.add_text(str(value), dxfattribs={"layer": layer, "rotation": 90}).set_placement((20, y))
    path = tmp_path / "arbitrary_layers.dxf"
    doc.saveas(path)

    ficha = _extract_laj_from_dxf(str(path))

    assert ficha["comprimento"] == 418.0
    assert ficha["largura"] == 183.0


def test_full_shallow_slab_is_not_classified_as_hlaz(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    layer = "GRADE_SEM_NOME_PADRAO"
    _add_rect_lines(msp, layer, 418.0, 71.0)
    msp.add_line((24, 5.5), (24, 51.9), dxfattribs={"layer": layer})
    msp.add_line((143, 0), (143, 35.5), dxfattribs={"layer": layer})
    msp.add_line((163, 35.5), (163, 71), dxfattribs={"layer": layer})
    msp.add_line((200, 0), (200, 71), dxfattribs={"layer": layer})
    msp.add_line((0, 15), (418, 15), dxfattribs={"layer": layer})
    msp.add_line((0, 35.5), (418, 35.5), dxfattribs={"layer": layer})
    msp.add_text("200", dxfattribs={"layer": layer}).set_placement((100, 20))
    msp.add_text("35.5", dxfattribs={"layer": "Painéis", "height": 9}).set_placement((210, 30))
    msp.add_lwpolyline(
        [(0, 0), (418, 0), (418, 71), (0, 71)],
        close=True,
        dxfattribs={"layer": "CONTORNO_CLIENTE_42"},
    )
    path = tmp_path / "shallow_slab.dxf"
    doc.saveas(path)

    ficha = _extract_laj_from_dxf(str(path))

    assert ficha["comprimento"] == 418.0
    assert ficha["largura"] == 71.0
    assert not ficha.get("_hlaz")
    assert ficha["cotas_paineis"] == [{
        "text": "35.5", "value": 35.5, "x": 210.0, "y": 30.0,
        "rotation": 0.0, "height": 9.0,
    }]
    assert ficha["_panel_vertical_segments"] == [{"value": 200.0, "y0": 0.0, "y1": 71.0}]
    assert ficha["linhas_verticais"] == [{
        "value": 200.0,
        "is_union": False,
        "exact": True,
        "segments": [{"y0": 0.0, "y1": 71.0}],
    }]
    assert ficha["linhas_horizontais"] == [{
        "value": 35.0, "is_union": False, "exact": True,
    }]


def test_reuse_panels_do_not_replace_full_slab_outline(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    layer = "Painéis"
    _add_rect_lines(msp, layer, 418.0, 311.0)
    msp.add_line((244, 0), (244, 311), dxfattribs={"layer": layer})
    for y in (122, 169, 189):
        msp.add_line((0, y), (418, y), dxfattribs={"layer": layer})
    msp.add_text("244", dxfattribs={"layer": layer}).set_placement((122, 20))
    for y0, y1 in ((0, 122), (189, 311)):
        msp.add_lwpolyline(
            [(0, y0), (418, y0), (418, y1), (0, y1)],
            close=True,
            dxfattribs={"layer": "REAPROVEITAMENTO"},
        )
    msp.add_lwpolyline(
        [(0, 122), (418, 122), (418, 169), (0, 169)],
        close=True,
        dxfattribs={"layer": "Hachura"},
    )
    path = tmp_path / "reuse_panels.dxf"
    doc.saveas(path)

    ficha = _extract_laj_from_dxf(str(path))

    assert ficha["comprimento"] == 418.0
    assert ficha["largura"] == 311.0
    assert ficha["area_cm2"] == 129998.0
    assert [line["value"] for line in ficha["linhas_horizontais"]] == [122.0, 169.0, 189.0]
    assert [line["is_union"] for line in ficha["linhas_horizontais"]] == [False, False, True]


def test_simple_rectangular_slab_replaces_sub_60_panel_cut(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    layer = "Painéis"
    _add_rect_lines(msp, layer, 418.0, 311.0)
    msp.add_line((244, 0), (244, 311), dxfattribs={"layer": layer})
    for y in (122, 169, 189):
        msp.add_line((0, y), (418, y), dxfattribs={"layer": layer})
    path = tmp_path / "simple_311.dxf"
    doc.saveas(path)

    ficha = _extract_laj_from_dxf(str(path))

    assert [line["value"] for line in ficha["linhas_horizontais"]] == [122.0, 142.0]
    assert [line["is_union"] for line in ficha["linhas_horizontais"]] == [False, True]


def test_extracts_support_hatch_lines_relative_to_slab(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    _add_rect_lines(msp, "Painéis", 418.0, 311.0)
    for offset in (0.0, 12.0, 24.0):
        msp.add_line(
            (-19.0, -31.0 + offset),
            (0.0, -12.0 + offset),
            dxfattribs={"layer": "3"},
        )
    # Setas de cota em outra layer não são hachura de apoio.
    msp.add_line((100.0, 20.0), (103.0, 23.0), dxfattribs={"layer": "Painéis"})
    path = tmp_path / "support_hatch.dxf"
    doc.saveas(path)

    ficha = _extract_laj_from_dxf(str(path))

    assert ficha["apoios_hachurados"] == [
        {"x1": -19.0, "y1": -31.0, "x2": 0.0, "y2": -12.0},
        {"x1": -19.0, "y1": -19.0, "x2": 0.0, "y2": 0.0},
        {"x1": -19.0, "y1": -7.0, "x2": 0.0, "y2": 12.0},
    ]


def test_filters_neighbor_support_hatch_outside_local_slab_window():
    local = [
        {"x1": -19.0, "y1": -31.0, "x2": 0.0, "y2": -12.0},
        {"x1": -19.0, "y1": -19.0, "x2": 0.0, "y2": 0.0},
        {"x1": -19.0, "y1": -7.0, "x2": 0.0, "y2": 12.0},
    ]
    neighbor = [
        {"x1": 650.0, "y1": 0.0, "x2": 669.0, "y2": 19.0},
        {"x1": 650.0, "y1": 12.0, "x2": 669.0, "y2": 31.0},
        {"x1": 650.0, "y1": 24.0, "x2": 669.0, "y2": 43.0},
    ]

    assert laj_motor._filter_support_hatch_lines(local + neighbor, 418.0, 311.0) == local


def test_diagonal_gate_ignores_reuse_marks_and_support_hatch():
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_line((0.0, 0.0), (50.0, 19.0), dxfattribs={"layer": "1"})
    for offset in (0.0, 12.0, 24.0):
        msp.add_line(
            (100.0, offset), (124.0, offset + 24.0),
            dxfattribs={"layer": "3"},
        )

    assert not laj_motor._has_diagonal_geometry(msp)

    # O gerador canônico grava o contorno estrutural na layer PAINEIS.
    msp.add_line((0.0, 0.0), (90.0, 85.0), dxfattribs={"layer": "PAINEIS"})
    assert laj_motor._has_diagonal_geometry(msp)


def test_vertical_dimensions_use_tallest_side_and_narrow_panels_get_hatch():
    polygon = [(0, 40), (100, 40), (100, 0), (180, 0), (180, 120), (0, 120)]

    guide = laj_generator._vertical_dimension_guide(polygon, 0, 180, [100, 120, 150])

    assert guide > 100

    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    count = laj_generator._add_narrow_panel_hatches(
        msp, polygon, 0, 0, 180, 120, [100, 120, 150], [40], {120.0}, set()
    )

    assert count == 2
    assert len(msp.query('HATCH[layer=="REAPROVEITAMENTO"]')) == 2

    doc_y = ezdxf.new("R2018")
    count_y = laj_generator._add_narrow_panel_hatches(
        doc_y.modelspace(), polygon, 0, 0, 180, 120, [50], [20], set(), {20.0}
    )

    assert count_y == 1


def test_panel_rectangles_reconstruct_stepped_outline_and_local_hlaz(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    for x0, y0, width, height in (
        (0.0, 49.0, 2413.0, 152.0),
        (2413.0, 0.0, 726.0, 89.5),
        (2413.0, 109.5, 726.0, 91.5),
    ):
        msp.add_lwpolyline(
            [(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height)],
            close=True,
            dxfattribs={"layer": "REAPROVEITAMENTO"},
        )
    msp.add_lwpolyline(
        [(2413.0, 89.5), (3139.0, 89.5), (3139.0, 109.5), (2413.0, 109.5)],
        close=True,
        dxfattribs={"layer": "Hachura"},
    )
    msp.add_line((0.0, 109.5), (3139.0, 109.5), dxfattribs={"layer": "Painéis"})
    msp.add_line((2413.0, 89.5), (3139.0, 89.5), dxfattribs={"layer": "Painéis"})
    for x in (0.0, 244.0, 2413.0, 3139.0):
        y0 = 49.0 if x < 2413.0 else 0.0
        msp.add_line((x, y0), (x, 201.0), dxfattribs={"layer": "Painéis"})
    outline = laj_motor._extract_panel_union_outline(
        msp, (0.0, 0.0, 3139.0, 201.0)
    )

    assert outline is not None
    box, coordinates = outline
    assert box == (0.0, 0.0, 3139.0, 201.0)
    assert coordinates == [
        [2413.0, 0.0], [2413.0, 49.0], [0.0, 49.0], [0.0, 201.0],
        [3139.0, 201.0], [3139.0, 0.0], [2413.0, 0.0],
    ]


def test_long_noisy_panel_axis_is_canonicalized_to_preferred_modules():
    noisy = [
        {"value": value, "is_union": False}
        for value in (58.0, 244.0, 320.5, 564.5, 769.0, 808.5, 1052.5)
    ]

    result = laj_motor._canonicalize_long_panel_axis(noisy, 3139.0, 201.0)
    positions = [line["value"] for line in result]

    assert positions[:4] == [244.0, 488.0, 732.0, 976.0]
    assert positions[-1] == 2928.0
    lengths = laj_motor._axis_panel_lengths(positions, 3139.0)
    assert lengths.count(244.0) == 12
    assert lengths[-1] == 211.0


def test_complex_sa_outline_replaces_rectangular_fallback(tmp_path, monkeypatch):
    obra = tmp_path / "Obra_TESTE"
    json_dir = obra / "Fase-4_Sincronizacao" / "JSON_Lajes"
    json_dir.mkdir(parents=True)
    (json_dir / "L900.json").write_text(
        json.dumps({
            "nome": "L900",
            "comprimento": 400.0,
            "largura": 500.0,
            "coordenadas": [[0, 0], [400, 0], [400, 500], [0, 500]],
            "_sa_meta": {},
        }),
        encoding="utf-8",
    )

    db = tmp_path / "project_data.vision"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE slabs (project_id TEXT, name TEXT, points_json TEXT, area REAL)")
    points = [[0, 0], [400, 0], [400, 300], [250, 300], [250, 500], [0, 500]]
    conn.execute(
        "INSERT INTO slabs VALUES (?, ?, ?, ?)",
        ("project-test", "L900", json.dumps(points), 170000.0),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(laj_motor, "PROJECT_DB_PATH", db)

    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    layer = "CLIENTE_SEM_PADRAO"
    _add_rect_lines(msp, layer, 400.0, 500.0)
    msp.add_line((0, 500), (100, 400), dxfattribs={"layer": "BORDA_DIAGONAL"})
    msp.add_text("200", dxfattribs={"layer": layer}).set_placement((100, 20))
    recorte = tmp_path / "L900.dxf"
    doc.saveas(recorte)

    ficha = laj_motor.extrair_ficha_laje(str(recorte), "L900", obra_root=obra)

    assert ficha["comprimento"] == 400.0
    assert ficha["largura"] == 500.0
    assert ficha["area_cm2"] == 170000.0
    assert len(ficha["coordenadas"]) == 7
