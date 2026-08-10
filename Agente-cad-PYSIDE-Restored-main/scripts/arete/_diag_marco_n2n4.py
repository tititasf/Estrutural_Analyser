# -*- coding: utf-8 -*-
"""Marco zone exact V/H/HATCH for V301.A N2 vs N4."""
from __future__ import annotations

import sys
from pathlib import Path

import ezdxf

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

from arete._diag_right_wall_v301 import N4_DIR, resolve_n2  # noqa: E402
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
from arete.geometry_lv_units import pair_units, split_n4_view, unit_label  # noqa: E402
from gerar_lv_dxf_stog import (  # noqa: E402
    _marco_extension_cm,
    _small_panel_start_x,
    select_canonical_face_units,
)


def dump(path, ox, oy, x0, x1, y0, y1, tag):
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    print(f"\n=== {tag} zone x=[{x0:.1f},{x1:.1f}] y=[{y0:.1f},{y1:.1f}] ===")
    vs, hs, hats = [], [], []
    for e in msp:
        if e.dxftype() == "LINE":
            s, t = e.dxf.start, e.dxf.end
            x1_, y1_ = float(s.x), float(s.y)
            x2_, y2_ = float(t.x), float(t.y)
            layer = e.dxf.layer
            if abs(x1_ - x2_) < 0.5:
                x = 0.5 * (x1_ + x2_) - ox
                yb, yt = min(y1_, y2_) - oy, max(y1_, y2_) - oy
                if x0 - 1 <= x <= x1 + 1 and yt >= y0 - 2 and yb <= y1 + 2:
                    if yt - yb >= 3:
                        vs.append((round(x, 2), round(yb, 2), round(yt, 2), round(yt - yb, 2), layer))
            elif abs(y1_ - y2_) < 0.5:
                y = 0.5 * (y1_ + y2_) - oy
                xl, xr = min(x1_, x2_) - ox, max(x1_, x2_) - ox
                if y0 - 2 <= y <= y1 + 2 and xr >= x0 - 1 and xl <= x1 + 1:
                    if xr - xl >= 3:
                        hs.append((round(y, 2), round(xl, 2), round(xr, 2), round(xr - xl, 2), layer))
        elif e.dxftype() == "HATCH":
            try:
                for p in e.paths:
                    xs, ys = [], []
                    if hasattr(p, "vertices"):
                        for v in p.vertices:
                            xs.append(float(v[0]) - ox)
                            ys.append(float(v[1]) - oy)
                    if xs and max(xs) >= x0 - 5 and min(xs) <= x1 + 5:
                        hats.append(
                            (
                                e.dxf.layer,
                                round(min(xs), 1),
                                round(max(xs), 1),
                                round(min(ys), 1),
                                round(max(ys), 1),
                                e.dxf.pattern_name if e.dxf.pattern_name else "?",
                            )
                        )
            except Exception as ex:
                hats.append(("err", str(ex)[:40], 0, 0, 0, 0))
        elif e.dxftype() == "DIMENSION":
            try:
                for ve in e.virtual_entities():
                    if ve.dxftype() != "LINE":
                        continue
                    s, t = ve.dxf.start, ve.dxf.end
                    x1_, y1_ = float(s.x), float(s.y)
                    x2_, y2_ = float(t.x), float(t.y)
                    if abs(x1_ - x2_) < 0.5:
                        x = 0.5 * (x1_ + x2_) - ox
                        yb, yt = min(y1_, y2_) - oy, max(y1_, y2_) - oy
                        if x0 - 1 <= x <= x1 + 30 and yt - yb >= 10:
                            vs.append(
                                (
                                    round(x, 2),
                                    round(yb, 2),
                                    round(yt, 2),
                                    round(yt - yb, 2),
                                    f"DIM/{e.dxf.layer}",
                                )
                            )
            except Exception:
                pass
    print("V:")
    for v in sorted(set(vs)):
        mark = ""
        if 420 < v[0] < 430:
            mark = " << ~first-marco"
        if 443 < v[0] < 450:
            mark = " << ~full"
        if 465 < v[0] < 500:
            mark = " << dim zone"
        if 403 < v[0] < 408:
            mark = " << body_end"
        print(f"  {v}{mark}")
    print("H:")
    for h in sorted(set(hs)):
        print(f"  {h}")
    print("HATCH:")
    for h in hats:
        print(f"  {h}")


def main():
    item = "V301"
    n2 = resolve_n2(item)
    entry = _entry_from_live_recorte(item)
    fus = select_canonical_face_units(entry.get("face_units") or [], item)
    n4a = N4_DIR / "LV_preview_V301_VIEW_A.dxf"
    n4 = {"A": split_n4_view(n4a, "A"), "B": []}
    n2s = {"A": [], "B": []}
    for i, u in enumerate(fus):
        s = str(u.get("side") or "?").upper()
        if s in n2s:
            u = dict(u)
            u["_idx"] = i
            n2s[s].append(u)
    for pr in pair_units(n2s["A"], n4["A"]):
        if pr["status"] != "paired":
            continue
        u2, u4 = pr["n2"], pr["n4"]
        lab = unit_label(u2, u2.get("_idx", 0))
        if lab != "V301.A":
            continue
        panels = u2.get("panels") or []
        h = float(u2.get("h_body") or 0)
        full = sum(float(p.get("width", 0) or 0) for p in panels)
        be = float(_small_panel_start_x(0.0, h, panels) or full)
        mh = _marco_extension_cm(bool(u2.get("marco_laje_sup")), float(u2.get("laje_sup") or 0))
        bb = u2.get("bbox") or {}
        ox2, oy2 = float(bb["x_left"]), float(bb["y_bot"])
        ox4, oy4 = u4["origin"]
        print("V301.A be", be, "full", full, "mh", mh)
        # zone: body_end-5 to full+60, y -5 to h+mh+5
        dump(n4a, ox4, oy4, be - 5, full + 60, -5, h + mh + 5, "N4")
        dump(n2, ox2, oy2, be - 5, full + 60, -5, h + mh + 5, "N2")


if __name__ == "__main__":
    main()
