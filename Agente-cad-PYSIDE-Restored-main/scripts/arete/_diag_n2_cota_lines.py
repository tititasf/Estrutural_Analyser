# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import ezdxf

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete._diag_right_wall_v301 import resolve_n2
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from arete.geometry_lv_units import pair_units, split_n4_view, unit_label
from gerar_lv_dxf_stog import _small_panel_start_x, select_canonical_face_units
from arete._diag_right_wall_v301 import N4_DIR


def main():
    n2 = resolve_n2("V301")
    entry = _entry_from_live_recorte("V301")
    fus = select_canonical_face_units(entry.get("face_units") or [], "V301")
    n4u = split_n4_view(N4_DIR / "LV_preview_V301_VIEW_A.dxf", "A")
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
        if unit_label(u2, u2.get("_idx", 0)) != "V301.A":
            continue
        panels = u2.get("panels") or []
        h = float(u2.get("h_body") or 0)
        full = sum(float(p.get("width", 0) or 0) for p in panels)
        be = float(_small_panel_start_x(0.0, h, panels))
        bb = u2.get("bbox") or {}
        ox, oy = float(bb["x_left"]), float(bb["y_bot"])
        doc = ezdxf.readfile(str(n2))
        print("be", be, "full", full)
        print("--- ALL vertical LINE L>8 in x be-5..full+80 ---")
        rows = []
        for e in doc.modelspace():
            if e.dxftype() != "LINE":
                continue
            s, t = e.dxf.start, e.dxf.end
            if abs(s.x - t.x) > 0.5:
                continue
            x = float(s.x) - ox
            yb = min(s.y, t.y) - oy
            yt = max(s.y, t.y) - oy
            L = yt - yb
            if L < 8:
                continue
            if not (be - 5 <= x <= full + 80):
                continue
            if yt < -10 or yb > h + 40:
                continue
            rows.append((x, yb, yt, L, e.dxf.layer))
        for x, yb, yt, L, layer in sorted(rows):
            print(f"  x={x:7.2f} y={yb:7.2f}->{yt:7.2f} L={L:6.1f} layer={layer!r}")
        print("--- entity types near right ---")
        from collections import Counter
        c = Counter()
        for e in doc.modelspace():
            c[e.dxftype()] += 1
        print(dict(c))


if __name__ == "__main__":
    main()
