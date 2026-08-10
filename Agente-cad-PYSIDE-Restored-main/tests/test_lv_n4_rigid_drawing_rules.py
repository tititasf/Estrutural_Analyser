from pathlib import Path
import importlib.util
import sys


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lv_dxf_stog.py"
sys.path.insert(0, str(_SCRIPT.parent))
_SPEC = importlib.util.spec_from_file_location("gerar_lv_rigid_rules", _SCRIPT)
lv = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(lv)


def _step_panels(with_hole=False):
    second = {
        "width": 161.5,
        "height1": 109.0,
        "height2": 0.0,
        "grade_h1": 0.0,
        "grade_h2": 0.0,
        "panel_type": "Sarrafeado",
    }
    if with_hole:
        second["holes"] = [
            {"active": True, "corner": "BL", "width": 50.5, "height": 65}
        ]
    return [
        {
            "width": 244.0,
            "height1": 44.0,
            "height2": 0.0,
            "grade_h1": 0.0,
            "grade_h2": 0.0,
            "panel_type": "Sarrafeado",
        },
        second,
    ]


def test_internal_65_dimension_stays_on_cota_without_low_panel_divider():
    doc = lv.setup_doc()
    msp = doc.modelspace()
    lv.draw_lv_face(
        msp, 0.0, 0.0, _step_panels(), 109.0, "SEGMENTO 1A",
        laje_sup=0.0, laje_inf=0.0,
    )

    dimension_texts = {
        str(entity.dxf.text)
        for entity in msp.query("DIMENSION[layer=='COTA']")
    }
    assert "65" in dimension_texts

    low_vertical_at_step = []
    for entity in msp.query("LINE[layer=='Painéis']"):
        start, end = entity.dxf.start, entity.dxf.end
        if abs(start.x - 244.0) > 0.01 or abs(end.x - 244.0) > 0.01:
            continue
        if min(start.y, end.y) < 64.9:
            low_vertical_at_step.append(entity)
    assert low_vertical_at_step == []


def test_n4_face_has_no_panel_hatch_and_hatches_only_explicit_void():
    doc = lv.setup_doc()
    msp = doc.modelspace()
    panels = _step_panels(with_hole=True)
    holes = []
    offset = 0.0
    for panel in panels:
        for raw in panel.get("holes", []):
            hole = dict(raw)
            hole["panel_offset"] = offset
            hole["panel_width"] = panel["width"]
            holes.append(hole)
        offset += panel["width"]

    lv.draw_lv_face(
        msp, 0.0, 0.0, panels, 109.0, "SEGMENTO 1A",
        holes=holes, laje_sup=0.0, laje_inf=0.0,
    )

    hatches = list(msp.query("HATCH"))
    assert len(hatches) == 1
    assert hatches[0].dxf.layer == "Hachura"

