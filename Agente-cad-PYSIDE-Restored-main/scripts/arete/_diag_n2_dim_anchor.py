# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import ezdxf

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete._diag_right_wall_v301 import N4_DIR, resolve_n2
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from arete.geometry_lv_units import pair_units, split_n4_view, unit_label
from gerar_lv_dxf_stog import _small_panel_start_x, select_canonical_face_units


def main():
    n2 = resolve_n2("V301")
    entry = _entry_from_live_recorte("V301")
    fus = select_canonical_face_units(entry.get("face_units") or [], "V301")
    n4a = N4_DIR / "LV_preview_V301_VIEW_A.dxf"
    n4u = split_n4_view(n4a, "A")
    n2s = []
    for i, u in enumerate(fus):
        if str(u.get("side")).upper() == "A":
            u = dict(u)
            u["_idx"] = i
            n2s.append(u)
    for pr in pair_units(n2s, n4u):
        if pr["status"] != "paired":
            continue
        u2 = pr["n2"]
        lab = unit_label(u2, u2.get("_idx", 0))
        if lab != "V301.A":
            continue
        panels = u2.get("panels") or []
        h = float(u2.get("h_body") or 0)
        full = sum(float(p.get("width", 0) or 0) for p in panels)
        be = float(_small_panel_start_x(0.0, h, panels))
        bb = u2.get("bbox") or {}
        ox, oy = float(bb["x_left"]), float(bb["y_bot"])
        print("body_end", be, "full", full)
        print("if dim@body: L1", be + 25, "L2", be + 50)
        print("if dim@full: L1", full + 25, "L2", full + 50)
        doc = ezdxf.readfile(str(n2))
        for e in doc.modelspace():
            if e.dxftype() != "DIMENSION":
                continue
            try:
                for ve in e.virtual_entities():
                    if ve.dxftype() != "LINE":
                        continue
                    s, t = ve.dxf.start, ve.dxf.end
                    if abs(s.x - t.x) > 0.8:
                        continue
                    x = float(s.x) - ox
                    yb = min(s.y, t.y) - oy
                    yt = max(s.y, t.y) - oy
                    L = yt - yb
                    if L < 40:
                        continue
                    if x < be - 10 or x > full + 80:
                        continue
                    if yb > 20:
                        continue
                    print(f"DIM V x={x:.1f} y={yb:.1f}->{yt:.1f} L={L:.1f}")
            except Exception:
                pass
        # all TEXT
        for e in doc.modelspace().query("TEXT"):
            tx = e.dxf.text or ""
            ins = e.dxf.insert
            xl, yl = float(ins.x) - ox, float(ins.y) - oy
            if xl < be - 30 or xl > full + 100:
                continue
            if -20 < yl < 150:
                print(f"TEXT x={xl:.1f} y={yl:.1f} '{tx}'")


if __name__ == "__main__":
    main()
