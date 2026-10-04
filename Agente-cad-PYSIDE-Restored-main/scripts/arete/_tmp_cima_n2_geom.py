"""Geometric read of N2 CIMA window: L contour, texts, small squares, dims."""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import ezdxf

ROOT = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main")
sys.path.insert(0, str(ROOT))
from src.core.n2_pilar_views import find_n2_pilar_recorte, zone_windows

OUT = ROOT / "scripts" / "arete" / "html_fichas" / "Obra_TREINO_1" / "13_PAV_20260912_161058_141102_pilares_2520" / "cima_l_preview"
DARK = "#1b2125"
DB = r"D:/Agente-cad-PYSIDE/project_data.vision"


def entity_pts(e):
    dt = e.dxftype()
    try:
        if dt == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        if dt == "LWPOLYLINE":
            return [(p[0], p[1]) for p in e.get_points("xy")]
        if dt == "POLYLINE":
            return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if dt in {"TEXT", "MTEXT", "INSERT"}:
            ins = e.dxf.insert
            return [(float(ins[0]), float(ins[1]))]
        if dt in {"CIRCLE", "ARC"}:
            c = e.dxf.center
            r = float(getattr(e.dxf, "radius", 0) or 0)
            return [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
        if dt == "HATCH":
            box = e.bbox()
            if box:
                return [(box.extmin.x, box.extmin.y), (box.extmax.x, box.extmax.y)]
        if dt == "DIMENSION":
            ins = e.dxf.insert
            return [(float(ins[0]), float(ins[1]))]
    except Exception:
        return []
    return []


def in_win(pt, w):
    return w[0] <= pt[0] <= w[1] and w[2] <= pt[1] <= w[3]


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def png(path, window, dest, size=1400):
    xmin, xmax, ymin, ymax = window
    dpi = 150
    doc = ezdxf.readfile(path)
    fig = plt.figure(figsize=(size / dpi, size / dpi), dpi=dpi, facecolor=DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.savefig(dest, format="png", dpi=dpi, facecolor=DARK, edgecolor="none")
    plt.close(fig)
    print("PNG", dest.name)


def analyze(item: str):
    recorte = find_n2_pilar_recorte("Obra_TREINO_1", "13_PAV", item, db_path=DB)
    wins = zone_windows(recorte, item)
    w = wins["cima"]
    print(f"\n======== {item} {recorte.name} cima={tuple(round(v,1) for v in w)}")
    doc = ezdxf.readfile(recorte)
    msp = doc.modelspace()

    texts = []
    polys = []
    hatches = []
    inserts = []
    dims = []
    for e in msp:
        pts = entity_pts(e)
        if not pts or not any(in_win(p, w) for p in pts):
            continue
        dt = e.dxftype()
        if dt in {"TEXT", "MTEXT"}:
            raw = e.plain_text() if dt == "MTEXT" else (e.dxf.text or "")
            raw = raw.replace("\\P", " ").strip()
            ins = e.dxf.insert
            h = float(getattr(e.dxf, "height", 0) or 0)
            rot = float(getattr(e.dxf, "rotation", 0) or 0)
            texts.append((float(ins[0]), float(ins[1]), h, rot, raw, e.dxf.layer))
        elif dt == "LWPOLYLINE":
            closed = bool(e.closed)
            layer = e.dxf.layer
            color = e.dxf.color
            bb = bbox(pts)
            ww, hh = bb[1] - bb[0], bb[3] - bb[2]
            polys.append((layer, color, closed, len(pts), ww, hh, bb, pts[:8]))
        elif dt == "HATCH":
            bb = bbox(pts)
            hatches.append((e.dxf.layer, e.dxf.color, bb[1]-bb[0], bb[3]-bb[2], bb))
        elif dt == "INSERT":
            ins = e.dxf.insert
            inserts.append((e.dxf.name, float(ins[0]), float(ins[1]), e.dxf.layer))
        elif dt == "DIMENSION":
            try:
                txt = e.dxf.text or ""
            except Exception:
                txt = ""
            ins = e.dxf.insert
            dims.append((float(ins[0]), float(ins[1]), txt, e.dxf.layer))

    print(f"texts={len(texts)} polys={len(polys)} hatches={len(hatches)} inserts={len(inserts)} dims={len(dims)}")

    print("--- TEXTS (sorted y desc, then x) ---")
    for t in sorted(texts, key=lambda r: (-r[1], r[0])):
        print(f"  {t[0]:7.1f},{t[1]:7.1f} h={t[2]:4.1f} rot={t[3]:5.1f} [{t[5]}] {t[4]!r}")

    print("--- INSERTS ---")
    names = {}
    for n, x, y, layer in inserts:
        names[n] = names.get(n, 0) + 1
    print("  counts", names)
    for n, x, y, layer in sorted(inserts, key=lambda r: (r[0], -r[2], r[1]))[:80]:
        print(f"  {n:12} {x:7.1f},{y:7.1f} [{layer}]")

    print("--- closed polys by size (w,h) ---")
    closed = [p for p in polys if p[2]]
    closed.sort(key=lambda p: -(p[4]*p[5]))
    for p in closed[:40]:
        print(f"  {p[0]:16} col={p[1]:3} n={p[3]:2} {p[4]:7.2f}x{p[5]:7.2f} bb=({p[6][0]:.1f},{p[6][2]:.1f})-({p[6][1]:.1f},{p[6][3]:.1f})")

    print("--- small squares 4-20cm (bolts/quad) ---")
    small = [p for p in closed if 3 <= p[4] <= 22 and 3 <= p[5] <= 22]
    print(f"  n={len(small)}")
    for p in sorted(small, key=lambda r: (r[6][0], r[6][2])):
        print(f"  {p[0]:16} col={p[1]:3} {p[4]:5.2f}x{p[5]:5.2f} at ({p[6][0]:.1f},{p[6][2]:.1f})")

    print("--- hatches ---")
    for h in sorted(hatches, key=lambda r: -(r[2]*r[3]))[:20]:
        print(f"  {h[0]:16} col={h[1]:3} {h[2]:7.2f}x{h[3]:7.2f} bb=({h[4][0]:.1f},{h[4][2]:.1f})")

    # L contour: 6-vertex closed poly whose bbox is ~165 x 218
    l_cands = [p for p in closed if p[3] in (6, 7) and 140 < p[4] < 200 and 190 < p[5] < 250]
    print("--- L candidates ---")
    for p in l_cands:
        print(f"  {p[0]} {p[4]:.2f}x{p[5]:.2f} n={p[3]} pts={p[7]}")

    # zoom around L or around all cima geometry that's not empty
    xs = [t[0] for t in texts] + [p[6][0] for p in closed] + [p[6][1] for p in closed]
    ys = [t[1] for t in texts] + [p[6][2] for p in closed] + [p[6][3] for p in closed]
    if l_cands:
        bb = l_cands[0][6]
        zoom = (bb[0] - 90, bb[1] + 90, bb[2] - 90, bb[3] + 90)
    else:
        zoom = (min(xs) - 20, max(xs) + 20, min(ys) - 20, max(ys) + 20)
    png(recorte, zoom, OUT / f"{item}_n2_cima_zoom.png", 1600)
    # even tighter on the L body
    if l_cands:
        bb = l_cands[0][6]
        png(recorte, (bb[0] - 40, bb[1] + 40, bb[2] - 40, bb[3] + 40), OUT / f"{item}_n2_cima_body.png", 1400)


if __name__ == "__main__":
    for item in ("P26", "P27"):
        analyze(item)
