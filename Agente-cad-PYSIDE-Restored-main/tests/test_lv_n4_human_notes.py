"""Regressões das notas humanas N2×N4 LV (ciclo 2026-08-24).

Regras universais, sem hardcode de viga:
- cotas de laje nos dois lados;
- sarrafo horizontal não cruza divisor Painéis;
- painel de 7 para na parede direita e a cota fica acima da laje;
- face CONT também emite 44/59 na parede curta.
"""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "gerar_lv_dxf_stog.py"


def _load():
    sys.path.insert(0, str(GEN.parent))
    spec = importlib.util.spec_from_file_location("lv_human_notes", GEN)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _panel(width, height):
    return {
        "width": width, "height1": height, "height2": 0.0,
        "grade_h1": 0.0, "grade_h2": 0.0,
        "panel_type": "Sarrafeado",
    }


def _dims(msp):
    return [e for e in msp if e.dxftype() == "DIMENSION"]


def test_repeated_unit_keeps_slab_cotas_both_sides():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(111.0, 109.0), _panel(63.0, 44.0), _panel(244.0, 44.0)],
        109.0, "UNIT.A#3",
        laje_sup=15.0, marco_laje_sup=True,
    )
    slab = [e for e in _dims(msp) if e.dxf.text == "15"]
    anchors = {round(e.dxf.defpoint2.x, 1) for e in slab}
    assert 0.0 in anchors
    assert max(anchors) >= 400.0


def test_n2_horizontal_sarrafo_stays_one_span():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(111.0, 109.0), _panel(63.0, 44.0), _panel(244.0, 44.0)],
        109.0, "UNIT.A#3",
        sarrafos_horizontais=[
            {"y_offset": 80.0, "x_left": 0.0, "x_right": 174.0},
        ],
        suppress_sarrafo_spans=True,
    )
    spans = []
    for ent in msp:
        if ent.dxftype() != "LINE" or ent.dxf.layer != "SARR_2.2x7":
            continue
        a, b = ent.dxf.start, ent.dxf.end
        if abs(a.y - 80.0) > 1.0:
            continue
        x1, x2 = sorted((a.x, b.x))
        spans.append((round(x1, 1), round(x2, 1)))
    assert spans == [(0.0, 174.0)]


def test_divider_at_tall_to_short_stops_at_shoulder():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(111.0, 109.0), _panel(63.0, 44.0), _panel(244.0, 44.0)],
        109.0, "UNIT.A#3",
        suppress_sarrafo_spans=True,
    )
    verts = set()
    for ent in msp:
        if ent.dxftype() != "LINE" or ent.dxf.layer != "Painéis":
            continue
        a, b = ent.dxf.start, ent.dxf.end
        if abs(a.x - b.x) > 0.2:
            continue
        verts.add((round(a.x, 1), round(min(a.y, b.y), 1),
                   round(max(a.y, b.y), 1)))
    assert (111.0, 0.0, 65.0) in verts
    assert (111.0, 0.0, 109.0) not in verts


def test_top_panel_stops_at_right_wall_and_cota_sits_above_slab():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0, [_panel(319.0, 102.0)], 102.0, "UNIT.B",
        laje_sup=15.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=420.0, painel_sup_x_offset=0.0,
    )
    boxes = []
    for ent in msp:
        if ent.dxftype() == "LWPOLYLINE" and ent.dxf.layer == "Painéis" and ent.closed:
            pts = list(ent.get_points("xy"))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            boxes.append((round(min(xs), 1), round(min(ys), 1),
                          round(max(xs), 1), round(max(ys), 1)))
    assert (0.0, 117.0, 319.0, 124.0) in boxes
    assert all(box[2] <= 319.1 for box in boxes if abs(box[1] - 117.0) < 0.2)
    sevens = [e for e in _dims(msp) if e.dxf.text == "7"]
    assert sevens
    assert all(abs(e.dxf.defpoint2.y - 117.0) < 0.6 for e in sevens)


def test_cont_face_emits_short_wall_44_and_59():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 44.0), _panel(63.0, 44.0), _panel(111.0, 109.0)],
        109.0, "CONT. V301.A",
        laje_sup=15.0, marco_laje_sup=True,
    )
    texts = {e.dxf.text for e in _dims(msp)}
    assert "44" in texts
    assert "59" in texts


def test_coplanar_step_sarrafos_are_not_gapped_at_52_5():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 38.0), _panel(22.5, 38.0), _panel(52.5, 102.0)],
        102.0, "V301.B",
        sarrafos_horizontais=[
            {"y_offset": 20.0, "x_left": 0.0, "x_right": 266.5},
        ],
        suppress_sarrafo_spans=True,
        laje_sup=15.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=319.0,
    )
    holes = []
    for ent in msp:
        if ent.dxftype() != "LINE" or ent.dxf.layer != "SARR_2.2x7":
            continue
        a, b = ent.dxf.start, ent.dxf.end
        if abs(a.y - 20.0) > 1.0:
            continue
        x1, x2 = sorted((a.x, b.x))
        if 244.0 < x1 < 266.5 or 244.0 < x2 < 266.5:
            if x2 - x1 < 20.0:
                holes.append((round(x1, 1), round(x2, 1)))
    assert holes == []


def test_short_wall_total_includes_top_panel_as_59():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 38.0), _panel(63.0, 38.0), _panel(111.0, 102.0)],
        102.0, "CONT. V301.B",
        laje_sup=14.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=418.0,
    )
    texts = {e.dxf.text for e in _dims(msp)}
    assert "59" in texts
    assert "52" not in texts


def test_top_panel_stops_at_body_end_not_marco():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 38.0), _panel(22.5, 38.0), _panel(52.5, 102.0),
         _panel(21.7, 102.0), _panel(26.2, 102.0)],
        102.0, "V301.B",
        laje_sup=15.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=400.0, painel_sup_x_offset=0.0,
    )
    rights = []
    for ent in msp:
        if ent.dxftype() == "LWPOLYLINE" and ent.dxf.layer == "Painéis" and ent.closed:
            pts = list(ent.get_points("xy"))
            ys = [p[1] for p in pts]
            if min(ys) >= 116.0:
                rights.append(max(p[0] for p in pts))
    assert rights
    assert max(rights) <= 319.2


def test_paineis_stack_above_cotas_and_below_sarrafos():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(111.0, 109.0), _panel(63.0, 44.0), _panel(244.0, 44.0)],
        109.0, "UNIT.A#3",
        laje_sup=15.0, marco_laje_sup=True,
        sarrafos_horizontais=[
            {"y_offset": 80.0, "x_left": 0.0, "x_right": 174.0},
        ],
        suppress_sarrafo_spans=True,
    )
    order = {h: s for h, s in msp.get_redraw_order()}

    def sort_key(entity):
        return order.get(entity.dxf.handle, entity.dxf.handle)

    def layer_of(entity):
        return str(entity.dxf.get("layer", "") or "")

    cota_keys = [sort_key(e) for e in msp if "COTA" in layer_of(e).upper()]
    painel_keys = [
        sort_key(e) for e in msp
        if layer_of(e) == "Painéis" or layer_of(e).upper().replace("É", "E") == "PAINEIS"
    ]
    sarr_keys = [sort_key(e) for e in msp if "SARR" in layer_of(e).upper()]
    assert cota_keys and painel_keys and sarr_keys
    assert max(cota_keys) < min(painel_keys)
    assert max(painel_keys) < min(sarr_keys)


def _closed_boxes(msp, layer="Painéis"):
    boxes = []
    for ent in msp:
        if ent.dxftype() != "LWPOLYLINE" or not ent.closed:
            continue
        if str(ent.dxf.layer or "") != layer:
            continue
        pts = list(ent.get_points("xy"))
        xs = [pt[0] for pt in pts]
        ys = [pt[1] for pt in pts]
        boxes.append((round(min(xs), 1), round(min(ys), 1),
                      round(max(xs), 1), round(max(ys), 1)))
    return boxes


def _verts(msp, layer="Painéis"):
    out = set()
    for ent in msp:
        if ent.dxftype() != "LINE" or str(ent.dxf.layer or "") != layer:
            continue
        a, b = ent.dxf.start, ent.dxf.end
        if abs(a.x - b.x) > 0.2:
            continue
        out.add((round(a.x, 1), round(min(a.y, b.y), 1),
                 round(max(a.y, b.y), 1)))
    return out


def test_top_panel_splits_at_244_into_244_and_75():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 38.0), _panel(22.5, 38.0), _panel(52.5, 102.0)],
        102.0, "V301.B",
        laje_sup=15.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=319.0, painel_sup_x_offset=0.0,
    )
    boxes = _closed_boxes(msp)
    assert (0.0, 117.0, 244.0, 124.0) in boxes
    assert (244.0, 117.0, 319.0, 124.0) in boxes
    verts = _verts(msp)
    assert (244.0, 117.0, 124.0) in verts
    assert (244.0, 102.0, 124.0) not in verts
    assert (244.0, 102.0, 117.0) not in verts


def test_cont_face_emits_174_aligned_with_244():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 40.0), _panel(63.0, 40.0), _panel(111.0, 104.0)],
        104.0, "CONT. V301.B",
        laje_sup=14.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=418.0,
    )
    dims = {e.dxf.text: e for e in msp if e.dxftype() == "DIMENSION"}
    assert "174" in dims
    assert "244" in dims
    assert abs(dims["174"].dxf.defpoint.y - dims["244"].dxf.defpoint.y) < 1.0


def test_mirrored_left_wall_is_not_duplicated():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(21.2, 103.0), _panel(19.0, 103.0), _panel(117.5, 103.0),
         _panel(21.8, 38.0), _panel(34.7, 38.0), _panel(244.0, 38.0)],
        103.0, "UNIT.B#10",
        laje_sup=14.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=418.0, painel_sup_x_offset=43.2,
        suppress_sarrafo_spans=True,
    )
    left = [v for v in _verts(msp) if abs(v[0] - 0.0) < 0.2]
    assert left == []
    body_left = [v for v in _verts(msp) if abs(v[0] - 40.2) < 0.4]
    assert body_left


def test_leading_marco_cotas_sit_on_body_wall():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(21.2, 103.0), _panel(19.0, 103.0), _panel(117.5, 103.0),
         _panel(21.8, 38.0), _panel(34.7, 38.0), _panel(244.0, 38.0)],
        103.0, "UNIT.B#10",
        laje_sup=14.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=418.0, painel_sup_x_offset=43.2,
        suppress_sarrafo_spans=True,
    )
    left_15 = [
        round(e.dxf.defpoint2.x, 1)
        for e in _dims(msp)
        if e.dxf.text in ("14", "15") and e.dxf.defpoint2.x < 80.0
    ]
    left_7 = [
        round(e.dxf.defpoint2.x, 1)
        for e in _dims(msp)
        if e.dxf.text == "7" and e.dxf.defpoint2.x < 80.0
    ]
    assert left_15
    assert left_7
    assert all(x >= 39.0 for x in left_15)
    assert all(x >= 39.0 for x in left_7)


def test_wide_bay_vertical_does_not_cross_slab():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 40.0), _panel(63.0, 40.0), _panel(111.0, 104.0)],
        104.0, "CONT. V301.B",
        laje_sup=14.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=418.0,
        suppress_sarrafo_spans=True,
    )
    laje_bot, laje_top = 104.0, 118.0
    through = [
        v for v in _verts(msp)
        if abs(v[0] - 244.0) < 0.4
        and v[1] < laje_top - 0.5
        and v[2] > laje_bot + 0.5
    ]
    assert through == []
    assert (244.0, 118.0, 125.0) in _verts(msp)


def test_sarrafo_above_body_is_dropped():
    lv = _load()
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0, [_panel(244.0, 102.0)], 102.0, "UNIT.B#7",
        sarrafos_horizontais=[
            {"y_offset": 40.0, "x_left": 0.0, "x_right": 200.0},
            {"y_offset": 120.0, "x_left": 0.0, "x_right": 200.0},
        ],
        suppress_sarrafo_spans=True,
    )
    ys = []
    for ent in msp:
        if ent.dxftype() != "LINE" or "SARR" not in str(ent.dxf.layer or "").upper():
            continue
        ys.append(round(ent.dxf.start.y, 1))
    assert 40.0 in ys
    assert 120.0 not in ys
