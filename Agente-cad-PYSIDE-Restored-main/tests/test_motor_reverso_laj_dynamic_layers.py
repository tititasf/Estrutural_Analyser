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
        "value": 35.5, "is_union": False, "exact": True,
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
