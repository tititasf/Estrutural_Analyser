# -*- coding: utf-8 -*-
from pathlib import Path
import os

p = Path(__file__).resolve().parent.parent / "gerar_lv_dxf_stog.py"
t = p.read_text(encoding="utf-8")

old = """    _draw_panel_frame_n2(
        msp, x0, y0, h, panels,
        marco_laje_sup=marco_laje_sup,
        laje_sup=laje_sup,
    )
"""
new = """    _draw_panel_frame_n2(
        msp, x0, y0, h, panels,
        marco_laje_sup=marco_laje_sup,
        laje_sup=laje_sup,
    )
    # Hachura ANSI31 na faixa superior do degrau (N2 V301) — densifica visao.
    _draw_degrau_top_hatch(msp, x0, y0, h, panels)
"""
if old not in t:
    raise SystemExit("frame call not found")
t = t.replace(old, new, 1)
print("call ok")

fn = '''
def _draw_degrau_top_hatch(msp, x0, y0, h, panels):
    """ANSI31 na faixa ombro->topo do degrau (como N2 V301.A/B)."""
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    degrau_end = _degrau_zone_end_x(x0, h, panels)
    if y_shoulder is None or degrau_end <= x0 + 1.0:
        return
    y_top = y0 + h
    if y_top - y_shoulder < 2.0:
        return
    pts = [
        (x0, y_shoulder),
        (degrau_end, y_shoulder),
        (degrau_end, y_top),
        (x0, y_top),
    ]
    try:
        ht = msp.add_hatch(dxfattribs={"layer": "Hachura", "color": 8})
        ht.set_pattern_fill("ANSI31", scale=0.45)
        ht.paths.add_polyline_path(pts, is_closed=True)
    except Exception:
        pass


'''
if "def _draw_degrau_top_hatch" not in t:
    t = t.replace(
        "def _draw_degrau_step_verticals",
        fn + "def _draw_degrau_step_verticals",
        1,
    )
    print("fn ok")
else:
    print("fn exists")

tmp = p.with_suffix(".py.tmp_patch")
tmp.write_text(t, encoding="utf-8")
os.replace(str(tmp), str(p))
print("done")
