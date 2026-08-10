"""Reprodução N2 LV: painéis sem hatch sólido branco."""

from pathlib import Path
import importlib.util
import sys

import ezdxf


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lv_dxf_stog.py"
_MOTOR = Path(__file__).resolve().parents[1] / "scripts" / "motor_reverso_lv.py"
sys.path.insert(0, str(_SCRIPT.parent))
_SPEC = importlib.util.spec_from_file_location("gerar_lv_hatch", _SCRIPT)
lv = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(lv)
_MSPEC = importlib.util.spec_from_file_location("motor_lv_hatch", _MOTOR)
motor = importlib.util.module_from_spec(_MSPEC)
assert _MSPEC and _MSPEC.loader
_MSPEC.loader.exec_module(motor)


def _hatch_counts(msp):
    solid = patterned = 0
    for ent in msp:
        if ent.dxftype() != "HATCH":
            continue
        if getattr(ent.dxf, "solid_fill", 0):
            solid += 1
        else:
            patterned += 1
    return solid, patterned


def test_draw_section_skips_solid_hachura_but_keeps_pattern():
    section = {
        "visual_primitives": [
            {
                "kind": "hatch",
                "layer": "Hachura",
                "solid": True,
                "pattern": "SOLID",
                "paths": [[(0, 0), (40, 0), (40, 4), (0, 4)]],
            },
            {
                "kind": "hatch",
                "layer": "Hachura",
                "solid": False,
                "pattern": "ANSI31",
                "scale": 0.5,
                "paths": [[(0, 10), (40, 10), (40, 20), (0, 20)]],
            },
        ],
    }
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    assert lv.draw_section_visual_primitives(msp, section, 100.0, 50.0)
    solid, patterned = _hatch_counts(msp)
    assert solid == 0
    assert patterned == 1


def test_motor_does_not_extract_solid_hachura_primitives():
    assert motor._skip_n2_panel_solid_hatch("Hachura", True)
    assert motor._skip_n2_panel_solid_hatch("Painéis", True)
    assert not motor._skip_n2_panel_solid_hatch("Hachura", False)
    assert not motor._skip_n2_panel_solid_hatch("COTA", True)