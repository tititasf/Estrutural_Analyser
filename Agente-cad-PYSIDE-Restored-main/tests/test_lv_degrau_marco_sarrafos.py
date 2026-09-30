"""Degrau: verticais do ombro, marco da laje e sarrafos verticais do N2."""

from pathlib import Path
import importlib.util
import sys

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lv_dxf_stog.py"
sys.path.insert(0, str(_SCRIPT.parent))
_SPEC = importlib.util.spec_from_file_location("gerar_lv_dxf_stog_test", _SCRIPT)
lv = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_stdout = sys.stdout
try:
    _SPEC.loader.exec_module(lv)
finally:
    sys.stdout = _stdout


def _verticals(msp, layer, x_max=500.0):
    out = []
    for ent in msp:
        if ent.dxftype() != "LINE" or ent.dxf.layer != layer:
            continue
        x1, y1 = ent.dxf.start.x, ent.dxf.start.y
        x2, y2 = ent.dxf.end.x, ent.dxf.end.y
        if abs(x1 - x2) > 0.5 or max(x1, x2) > x_max:
            continue
        out.append((round(x1, 1), round(min(y1, y2), 1), round(max(y1, y2), 1)))
    return sorted(set(out))


def test_degrau_draws_step_shoulder_verticals():
    doc = lv.setup_doc()
    msp = doc.modelspace()
    def _panel(width, height1, **extra):
        base = {
            "width": width, "height1": height1, "height2": 0.0,
            "grade_h1": 0.0, "grade_h2": 0.0, "panel_type": "Sarrafeado",
        }
        base.update(extra)
        return base

    panels = [
        _panel(244.0, 44.0, reuse=True,
               reuse_regions=[{"y_offset": 65.0, "x_offset": 0.0, "width": 244.0, "height": 44.0}]),
        _panel(28.7, 44.0),
        _panel(21.8, 44.0),
        _panel(111.0, 109.0),
    ]
    lv.draw_lv_face(
        msp, 0.0, -259.0, panels, 109.0, "V301.A",
        laje_sup=15.0, laje_inf=0.0,
        sarrafos_verticais=[
            {"side": "left", "x_offset": 6.9, "y_bot": 66.0, "y_top": 109.0},
            {"side": "internal", "x_offset": 301.5, "y_bot": 0.0, "y_top": 65.0},
            {"side": "internal", "x_offset": 398.5, "y_bot": 0.0, "y_top": 109.0},
        ],
        sarrafo_vertical_esquerdo=True,
        marco_laje_sup=True,
    )
    verts = _verticals(msp, "Painéis")
    # N2 degrau: esquerda e 1º divisor só na faixa alta; 272.7/294.5 só baixos.
    assert (0.0, -194.0, -150.0) in verts
    assert (0.0, -259.0, -194.0) not in verts
    assert (244.0, -194.0, -150.0) in verts
    assert (244.0, -259.0, -194.0) not in verts
    assert (272.7, -259.0, -194.0) in verts
    assert (294.5, -259.0, -194.0) in verts
    assert (405.5, -259.0, -150.0) in verts
    sarr = _verticals(msp, "SARR_2.2x7")
    assert (6.9, -193.0, -150.0) in sarr
    assert (301.5, -259.0, -194.0) in sarr
    assert (398.5, -259.0, -150.0) in sarr
    assert len(sarr) == 3


def test_merge_extremity_sarrafos_only_when_requested():
    width = 244.0 + 28.7 + 21.8 + 111.0
    specs = [
        {'side': 'left', 'x_offset': 6.9, 'y_bot': 66.0, 'y_top': 109.0},
        {'side': 'internal', 'x_offset': 301.5, 'y_bot': 0.0, 'y_top': 65.0},
    ]
    without = lv.merge_sarrafos_verticais_extremidades(
        specs, width, 109.0, draw_left=False, draw_right=False,
    )
    right_x = round(width - 7.0, 1)
    assert len(without) == 2
    assert not any(abs(item['x_offset'] - right_x) < 0.2 for item in without)

    with_right = lv.merge_sarrafos_verticais_extremidades(
        specs, width, 109.0, draw_left=False, draw_right=True,
    )
    assert any(
        item['side'] == 'right' and abs(item['x_offset'] - right_x) < 0.2
        for item in with_right
    )


def test_motor_detects_sarrafos_and_marco_for_v301():
    motor = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location(
            "motor_reverso_lv_test",
            Path(__file__).resolve().parents[1] / "scripts" / "motor_reverso_lv.py",
        )
    )
    # lightweight: reuse gerar test import style
    motor_path = Path(__file__).resolve().parents[1] / "scripts" / "motor_reverso_lv.py"
    spec = importlib.util.spec_from_file_location("motor_reverso_lv_test", motor_path)
    motor = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    _stdout = sys.stdout
    try:
        spec.loader.exec_module(motor)
    finally:
        sys.stdout = _stdout

    import sqlite3
    db = Path(r"D:/Agente-cad-PYSIDE/project_data.vision")
    with sqlite3.connect(db) as conn:
        recorte = conn.execute(
            """
            SELECT recorte_path FROM reverse_eng_recortes
             WHERE UPPER(elemento_id)='V301' AND UPPER(classe)='LV'
             ORDER BY id DESC LIMIT 1
            """
        ).fetchone()[0]
    ficha = motor.extrair_ficha_lateral_viga(recorte, "V301_A")
    unit = next(
        u for u in lv.select_canonical_face_units(ficha.get("face_units") or [])
        if u.get("label") == "V301.A"
    )
    assert float(unit.get("laje_sup", 0) or 0) >= 7.0
    assert unit.get("marco_laje_sup") is True
    assert unit.get("sarrafo_vertical_esquerdo") is True
    assert unit.get("sarrafo_vertical_direito") is False
    assert len(unit.get("sarrafos_verticais") or []) >= 2
    panel_w = sum(float(p.get("width", 0) or 0) for p in unit.get("panels") or [])
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_sarr_lv_vertical_pairs(
        msp, 0.0, 0.0, float(unit.get("h_body", 109) or 109),
        [float(p.get("width", 0) or 0) for p in unit.get("panels") or []],
        draw_left=bool(unit.get("sarrafo_vertical_esquerdo")),
        draw_right=bool(unit.get("sarrafo_vertical_direito")),
        sarrafos_verticais=unit.get("sarrafos_verticais"),
    )
    right_x = round(panel_w - 7.0, 1)
    assert (right_x, 0.0, float(unit.get("h_body", 109) or 109)) not in _verticals(
        msp, "SARR_2.2x7", x_max=panel_w + 5
    )
    horiz = unit.get("sarrafos_horizontais") or []
    assert len(horiz) >= 8
    ys = {round(float(h.get("y_offset", 0)), 1) for h in horiz}
    assert 73.0 in ys or 72.0 in ys or 8.0 in ys