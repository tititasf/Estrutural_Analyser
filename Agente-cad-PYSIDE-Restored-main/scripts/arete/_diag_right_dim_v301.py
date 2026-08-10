# -*- coding: utf-8 -*-
"""Dim verticals after extreme-right wall — N2 vs N4 V301.A/B."""
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


def collect_v(path: Path, ox: float, oy: float, x_lo: float, x_hi: float):
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    seen = set()
    out = []
    texts = []
    for e in msp:
        lines = []
        if e.dxftype() == "LINE":
            lines = [(e.dxf.start, e.dxf.end, e.dxf.layer, "LINE")]
        elif e.dxftype() == "DIMENSION":
            try:
                for ve in e.virtual_entities():
                    if ve.dxftype() == "LINE":
                        lines.append((ve.dxf.start, ve.dxf.end, e.dxf.layer, "DIM"))
                    elif ve.dxftype() == "TEXT":
                        ins = ve.dxf.insert
                        texts.append(
                            (
                                float(ins.x) - ox,
                                float(ins.y) - oy,
                                (ve.dxf.text or "").strip(),
                            )
                        )
                    elif ve.dxftype() == "MTEXT":
                        ins = ve.dxf.insert
                        texts.append(
                            (
                                float(ins.x) - ox,
                                float(ins.y) - oy,
                                (ve.text or "").strip()[:24],
                            )
                        )
            except Exception:
                pass
        for s, t, layer, src in lines:
            x1, y1, x2, y2 = float(s.x), float(s.y), float(t.x), float(t.y)
            if abs(x1 - x2) > 0.8:
                continue
            x = 0.5 * (x1 + x2) - ox
            if not (x_lo <= x <= x_hi):
                continue
            yb, yt = min(y1, y2) - oy, max(y1, y2) - oy
            L = yt - yb
            if L < 15:
                continue
            key = (round(x, 1), round(yb, 1), round(yt, 1), layer, src)
            if key in seen:
                continue
            seen.add(key)
            out.append((round(x, 2), round(yb, 2), round(yt, 2), round(L, 2), layer, src))
    out.sort()
    texts = sorted({(round(x, 1), round(y, 1), t) for x, y, t in texts if x_lo - 30 <= x <= x_hi + 20})
    return out, texts


def main():
    item = "V301"
    n2 = resolve_n2(item)
    entry = _entry_from_live_recorte(item)
    fus = select_canonical_face_units(entry.get("face_units") or [], item)
    n4a = N4_DIR / f"LV_preview_{item}_VIEW_A.dxf"
    n4b = N4_DIR / f"LV_preview_{item}_VIEW_B.dxf"
    n4 = {"A": split_n4_view(n4a, "A"), "B": split_n4_view(n4b, "B")}
    n2s = {"A": [], "B": []}
    for i, u in enumerate(fus):
        s = str(u.get("side") or "?").upper()
        if s in n2s:
            u = dict(u)
            u["_idx"] = i
            n2s[s].append(u)

    for side, n4p in (("A", n4a), ("B", n4b)):
        for pr in pair_units(n2s[side], n4[side]):
            if pr["status"] != "paired":
                continue
            u2, u4 = pr["n2"], pr["n4"]
            lab = unit_label(u2, u2.get("_idx", 0))
            if lab not in ("V301.A", "V301.B"):
                continue
            panels = u2.get("panels") or []
            h = float(u2.get("h_body") or 0)
            full = sum(float(p.get("width", 0) or 0) for p in panels)
            be = float(_small_panel_start_x(0.0, h, panels) or full)
            bb = u2.get("bbox") or {}
            ox2, oy2 = float(bb["x_left"]), float(bb["y_bot"])
            ox4, oy4 = u4["origin"]
            mh = _marco_extension_cm(
                bool(u2.get("marco_laje_sup")), float(u2.get("laje_sup") or 0)
            )
            print("=" * 72, side, lab)
            print(f"  be={be:.1f} full={full:.1f} h={h:.1f} mh={mh:.1f}")
            print(f"  expected dim L1@ be+25={be+25:.1f} L2@ be+50={be+50:.1f}")
            print(f"  if anchored full: L1={full+25:.1f} L2={full+50:.1f}")
            # zone: body_end-2 .. full+70
            for tag, path, ox, oy in (("N4", n4p, ox4, oy4), ("N2", n2, ox2, oy2)):
                vs, texts = collect_v(path, ox, oy, be - 2, full + 70)
                print(f"  -- {tag} V --")
                for v in vs:
                    mark = ""
                    if abs(v[0] - full) < 1:
                        mark = " << FULL WALL"
                    elif abs(v[0] - (be + 25)) < 1:
                        mark = " << be+L1"
                    elif abs(v[0] - (be + 50)) < 1:
                        mark = " << be+L2"
                    elif abs(v[0] - (full + 25)) < 1:
                        mark = " << full+L1"
                    elif abs(v[0] - (full + 50)) < 1:
                        mark = " << full+L2"
                    elif v[0] > full + 1:
                        mark = " << AFTER FULL"
                    elif be + 1 < v[0] < full - 1:
                        mark = " << INSIDE MARCO"
                    print(f"    x={v[0]:7.2f} y={v[1]:7.2f}->{v[2]:7.2f} L={v[3]:6.1f} {v[4]}/{v[5]}{mark}")
                print(f"  -- {tag} texts in band --")
                for t in texts:
                    if be - 5 <= t[0] <= full + 65:
                        print(f"    x={t[0]:7.1f} y={t[1]:7.1f} '{t[2]}'")


if __name__ == "__main__":
    main()
