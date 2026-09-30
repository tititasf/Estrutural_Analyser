# -*- coding: utf-8 -*-
"""Probe Face B verts around 244 and leftover V7 through laje."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from lv_n4_face_unit_selection import select_n4_face_units
import gerar_lv_dxf_stog as lv


def verts(msp, layer="Painéis"):
    out = []
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if str(e.dxf.layer or "") != layer:
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.x - b.x) > 0.3:
            continue
        out.append(
            (
                round(a.x, 1),
                round(min(a.y, b.y), 1),
                round(max(a.y, b.y), 1),
                str(e.dxf.layer),
            )
        )
    return sorted(out)


def boxes(msp, layer="Painéis"):
    out = []
    for e in msp:
        if e.dxftype() != "LWPOLYLINE" or not e.closed:
            continue
        if str(e.dxf.layer or "") != layer:
            continue
        pts = list(e.get_points("xy"))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        out.append(
            (
                round(min(xs), 1),
                round(min(ys), 1),
                round(max(xs), 1),
                round(max(ys), 1),
            )
        )
    return sorted(out)


def sarr_h(msp):
    out = []
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if "SARR" not in str(e.dxf.layer or "").upper():
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.y - b.y) > 0.4:
            continue
        x1, x2 = sorted((a.x, b.x))
        out.append((round(x1, 1), round(x2, 1), round(a.y, 1)))
    return sorted(out, key=lambda t: (t[2], t[0]))


def dims(msp):
    out = []
    for e in msp:
        if e.dxftype() != "DIMENSION":
            continue
        txt = str(e.dxf.get("text", "") or "")
        p1 = e.dxf.defpoint
        p2 = e.dxf.defpoint2
        out.append(
            (
                txt,
                round(p1.x, 1),
                round(p1.y, 1),
                round(p2.x, 1),
                round(p2.y, 1),
            )
        )
    return out


def panel_summary(u):
    pans = u.get("panels") or []
    return [
        (
            round(float(p.get("width", 0) or 0), 1),
            round(float(p.get("height1", 0) or 0), 1),
        )
        for p in pans
    ]


e = _entry_from_live_recorte("V301")
fus = select_n4_face_units(lv, e.get("face_units") or [], "V301")
print("n_units", len(fus))
seen = set()
for i, u in enumerate(fus):
    lab = str(u.get("label") or "?")
    side = str(u.get("side") or "").upper()
    if side != "B":
        continue
    key = (lab, tuple(panel_summary(u)))
    if key in seen:
        continue
    seen.add(key)
    h = float(u.get("h_body") or u.get("h") or 0)
    print("\n====", i, lab, "h", h, "laje", u.get("laje_sup"),
          "sup", u.get("painel_sup_alt"), "wsup", u.get("painel_sup_width"),
          "xoff", u.get("painel_sup_x_offset"))
    print("panels", panel_summary(u))
    hs = u.get("sarrafos_horizontais") or []
    ys = sorted({round(float(s.get("y_offset", 0) or 0), 1) for s in hs})
    print("sarr_y", ys, "above_h", [y for y in ys if y > h + 1])
    print("sarr_v", u.get("sarrafos_verticais"))
    doc = lv.setup_doc()
    msp = doc.modelspace()
    kw = dict(
        laje_sup=float(u.get("laje_sup") or 0),
        marco_laje_sup=bool(u.get("marco_laje_sup") or (float(u.get("laje_sup") or 0) > 0)),
        painel_sup_alt=float(u.get("painel_sup_alt") or 0),
        painel_sup_width=float(u.get("painel_sup_width") or 0),
        painel_sup_x_offset=float(u.get("painel_sup_x_offset") or 0),
        sarrafos_horizontais=u.get("sarrafos_horizontais"),
        sarrafos_verticais=u.get("sarrafos_verticais"),
        suppress_sarrafo_spans=True,
    )
    lv.draw_lv_face(msp, 0.0, 0.0, u.get("panels") or [], h, lab, **kw)
    pv = verts(msp, "Painéis")
    print("Painéis V", pv)
    near244 = [v for v in pv if 230 <= v[0] <= 280]
    print("near244-280", near244)
    extra20 = [v for v in pv if 255 <= v[0] <= 275]
    print("extra20band", extra20)
    left = [v for v in pv if abs(v[0] - 0.0) < 0.4]
    print("leftV", left)
    print("boxes7", [b for b in boxes(msp) if b[1] >= h])
    print("sarrH y unique", sorted({t[2] for t in sarr_h(msp)}))
    print("cotaV", verts(msp, "COTA"))
    interesting = [d for d in dims(msp) if d[0] in ("7", "15", "14", "65", "44", "59", "244", "174", "75")]
    print("dims", interesting)
