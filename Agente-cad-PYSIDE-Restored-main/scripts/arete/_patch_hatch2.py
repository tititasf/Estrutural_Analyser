# -*- coding: utf-8 -*-
from pathlib import Path
import os
import re

p = Path(__file__).resolve().parent.parent / "gerar_lv_dxf_stog.py"
t = p.read_text(encoding="utf-8")

m = re.search(r"def _draw_degrau_top_hatch\(msp, x0, y0, h, panels\):", t)
if not m:
    raise SystemExit("fn not found")
start = m.start()
m2 = re.search(r"\ndef _draw_degrau_step_verticals\(", t[start:])
if not m2:
    raise SystemExit("end not found")
end = start + m2.start()

new = '''def _draw_degrau_top_hatch(msp, x0, y0, h, panels):
    """ANSI31: faixa ombro->topo do degrau + faixa topo do corpo (N2)."""
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    degrau_end = _degrau_zone_end_x(x0, h, panels)
    y_top = y0 + h
    small_x = _small_panel_start_x(x0, h, panels)
    body_end = float(small_x) if small_x is not None else float(
        x0 + sum(float(p.get("width", 0) or 0) for p in (panels or []))
    )

    def _hatch(pts):
        try:
            ht = msp.add_hatch(dxfattribs={"layer": "Hachura", "color": 8})
            ht.set_pattern_fill("ANSI31", scale=0.4)
            ht.paths.add_polyline_path(pts, is_closed=True)
        except Exception:
            pass

    if y_shoulder is not None and degrau_end > x0 + 1.0 and y_top - y_shoulder >= 2.0:
        _hatch([
            (x0, y_shoulder), (degrau_end, y_shoulder),
            (degrau_end, y_top), (x0, y_top),
        ])
    # faixa topo pos-degrau (densifica B / corpo cheio)
    if degrau_end is not None and body_end > degrau_end + 5.0:
        y1 = y_top - min(18.0, h * 0.25)
        if y1 < y_top - 1.0:
            _hatch([
                (degrau_end, y1), (body_end, y1),
                (body_end, y_top), (degrau_end, y_top),
            ])


'''
t = t[:start] + new + t[end:]
tmp = p.with_suffix(".py.tmp_patch")
tmp.write_text(t, encoding="utf-8")
os.replace(str(tmp), str(p))
print("ok")
