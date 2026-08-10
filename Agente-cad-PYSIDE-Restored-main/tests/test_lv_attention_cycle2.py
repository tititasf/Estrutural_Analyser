"""Regressoes universais do segundo ciclo humano N2 x N4 de LV."""

from pathlib import Path
import importlib.util
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "gerar_lv_dxf_stog.py"
MOTOR = ROOT / "scripts" / "motor_reverso_lv.py"


def _load(path, name):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
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


def _verticals(msp, layer):
    result = set()
    for ent in msp:
        if ent.dxftype() != "LINE" or ent.dxf.layer != layer:
            continue
        a, b = ent.dxf.start, ent.dxf.end
        if abs(a.x - b.x) < 0.2:
            result.add((round(a.x, 1), round(min(a.y, b.y), 1),
                        round(max(a.y, b.y), 1)))
    return result


def test_leading_step_has_174_level_and_witnesses_touch_panel():
    lv = _load(GEN, "lv_cycle2_leading")
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 44.0), _panel(63.0, 44.0),
         _panel(111.0, 109.0)],
        109.0, "CONT. UNIT",
    )
    dims = [e for e in msp if e.dxftype() == "DIMENSION"
            and e.dxf.layer == "COTA"]
    assert "174" in {e.dxf.text for e in dims}
    d244 = next(e for e in dims if e.dxf.text == "244")
    assert round(d244.dxf.defpoint2.y, 1) == 65.0
    assert round(d244.dxf.defpoint3.y, 1) == 65.0
    assert (244.0, 65.0, 109.0) in _verticals(msp, "Painéis")
    assert (244.0, 0.0, 65.0) not in _verticals(msp, "Painéis")


def test_mirrored_step_divider_stays_inside_raised_panels():
    lv = _load(GEN, "lv_cycle2_trailing")
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(52.5, 109.0), _panel(22.5, 44.0),
         _panel(244.0, 44.0)],
        109.0, "UNIT",
    )
    verts = _verticals(msp, "Painéis")
    assert (75.0, 65.0, 109.0) in verts
    assert (75.0, 0.0, 65.0) not in verts
    dims = {e.dxf.text for e in msp if e.dxftype() == "DIMENSION"}
    assert {"52,5", "22,5", "75", "244"} <= dims


def test_motor_extracts_top_panel_above_slab_as_separate_ficha_field():
    motor = _load(MOTOR, "lv_cycle2_motor")
    db = Path(r"D:/Agente-cad-PYSIDE/project_data.vision")
    with sqlite3.connect(db) as conn:
        recorte = conn.execute(
            "SELECT recorte_path FROM reverse_eng_recortes "
            "WHERE UPPER(elemento_id)='V301' AND UPPER(classe)='LV' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    ficha = motor.extrair_ficha_lateral_viga(recorte, "V301_A")
    unit = next(u for u in ficha.get("face_units", [])
                if u.get("label") == "V301.B")
    assert float(unit.get("painel_sup_alt", 0)) == 7.0
    assert abs(float(unit.get("painel_sup_width", 0)) - 319.0) < 0.6
    assert 14.0 <= float(unit.get("laje_sup", 0)) <= 15.0
    mirrored = next(
        u for u in ficha.get("face_units", [])
        if float(u.get("painel_sup_width", 0) or 0) >= 400.0
        and len(u.get("panels", [])) >= 5
    )
    # Esta unidade TEM marco estreito real na ponta (21.2+19.0=40.2cm,
    # painel_sup_width=418): o offset nao e residuo de bbox, e a posicao
    # real do fechamento acima da laje. Confirmado direto no DXF do N2 —
    # o retangulo (LWPOLYLINE fechada, layer Paineis, y=h_body+laje_sup ate
    # +laje_sup+7) comeca em x_rel=43.1, nao em 0 (2026-07-23, ver
    # RELATORIO 20260723_18xxxx). offset=0.0 aqui desalinhava o painel do
    # N2 real (achado ao investigar "painel de 7 fora de posicao").
    assert abs(float(mirrored.get("painel_sup_x_offset", -1)) - 43.2) < 3.0


def test_generator_draws_top_panel_rectangle_when_ficha_provides_it():
    lv = _load(GEN, "lv_cycle2_top_panel")
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0, [_panel(319.0, 102.0)], 102.0, "UNIT.B",
        laje_sup=15.0, marco_laje_sup=True,
        painel_sup_alt=7.0, painel_sup_width=319.0,
        painel_sup_x_offset=0.0,
    )
    boxes = []
    for ent in msp:
        if (ent.dxftype() == "LWPOLYLINE"
                and ent.dxf.layer == "Painéis" and ent.closed):
            pts = list(ent.get_points("xy"))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            boxes.append((round(min(xs), 1), round(min(ys), 1),
                          round(max(xs), 1), round(max(ys), 1)))
    assert (0.0, 117.0, 319.0, 124.0) in boxes


def test_group_total_75_uses_outer_level_while_parts_stay_inner():
    lv = _load(GEN, "lv_cycle3_dim75")
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(52.5, 109.0), _panel(22.5, 44.0),
         _panel(244.0, 44.0)],
        109.0, "UNIT",
    )
    dims = {e.dxf.text: e for e in msp if e.dxftype() == "DIMENSION"}
    assert round(dims["75"].dxf.defpoint.y, 1) == -50.0
    assert round(dims["52,5"].dxf.defpoint.y, 1) == -25.0
    assert round(dims["22,5"].dxf.defpoint.y, 1) == -25.0


def test_slab_right_dimension_attaches_to_outer_contour_not_step_wall():
    lv = _load(GEN, "lv_cycle3_slab_anchor")
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0,
        [_panel(244.0, 44.0), _panel(63.0, 44.0),
         _panel(111.0, 109.0)],
        109.0, "UNIT", laje_sup=15.0, marco_laje_sup=True,
    )
    slab_dims = [
        e for e in msp if e.dxftype() == "DIMENSION" and e.dxf.text == "15"
    ]
    anchors = {round(e.dxf.defpoint2.x, 1) for e in slab_dims}
    assert anchors == {0.0, 418.0}


def test_live_v301_bbox_height_is_reconciled_from_material_panels():
    motor = _load(MOTOR, "lv_cycle3_body_height")
    db = Path(r"D:/Agente-cad-PYSIDE/project_data.vision")
    with sqlite3.connect(db) as conn:
        recorte = conn.execute(
            "SELECT recorte_path FROM reverse_eng_recortes "
            "WHERE UPPER(elemento_id)='V301' AND UPPER(classe)='LV' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    ficha = motor.extrair_ficha_lateral_viga(recorte, "V301_A")
    target = next(
        u for u in ficha.get("face_units", [])
        if str(u.get("side", "")).upper() == "B"
        and [round(float(p.get("width", 0)), 1) for p in u.get("panels", [])]
        == [111.0, 63.0, 244.0]
        and round(float((u.get("bbox") or {}).get("y_top", 0)), 1) == 7778.0
    )
    assert round(float(target.get("h_body", 0)), 1) == 110.3
    assert round(float(target.get("h_total", 0)), 1) == 124.3
    assert float(target.get("laje_inf", 0)) == 0.0


def test_dimension_chain_can_split_one_raw_174_panel_into_63_and_111():
    motor = _load(MOTOR, "lv_cycle3_split_174")
    raw = [_panel(174.0, 109.0), _panel(244.0, 44.0)]
    result = motor.reconcile_panel_segments_with_horizontal_dims(
        raw, [63.0, 111.0, 174.0, 244.0], 109.0, 0.0,
    )
    assert [float(p["width"]) for p in result] == [111.0, 63.0, 244.0]
