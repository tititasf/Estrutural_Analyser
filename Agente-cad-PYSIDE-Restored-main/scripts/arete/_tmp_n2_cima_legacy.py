"""N2 CIMA P27: perfil/madeira/parafuso vs concreto, in cm (drawing is 2x)."""
from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main")
sys.path.insert(0, str(ROOT))
from src.core.n2_pilar_views import find_n2_pilar_recorte, zone_windows
import ezdxf

DB = r"D:/Agente-cad-PYSIDE/project_data.vision"


def pts(e):
    dt = e.dxftype()
    try:
        if dt == "LWPOLYLINE":
            return [(p[0], p[1]) for p in e.get_points("xy")]
        if dt == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        if dt in {"TEXT", "MTEXT"}:
            ins = e.dxf.insert
            return [(float(ins[0]), float(ins[1]))]
    except Exception:
        return []
    return []


def bb(ps):
    xs = [p[0] for p in ps]
    ys = [p[1] for p in ps]
    return min(xs), max(xs), min(ys), max(ys)


def main():
    recorte = find_n2_pilar_recorte("Obra_TREINO_1", "13_PAV", "P27", db_path=DB)
    w = zone_windows(recorte, "P27")["cima"]
    doc = ezdxf.readfile(recorte)
    layers = defaultdict(list)
    texts = []
    for e in doc.modelspace():
        p = pts(e)
        if not p or not any(w[0] <= x <= w[1] and w[2] <= y <= w[3] for x, y in p):
            continue
        dt = e.dxftype()
        if dt in {"TEXT", "MTEXT"}:
            raw = e.plain_text() if dt == "MTEXT" else (e.dxf.text or "")
            ins = e.dxf.insert
            texts.append((float(ins[0]), float(ins[1]), raw.replace("\\P", " ").strip(), e.dxf.layer))
        elif dt == "LWPOLYLINE":
            box = bb(p)
            layers[e.dxf.layer].append((box[1]-box[0], box[3]-box[2], box, e.dxf.color, bool(e.closed)))
    print("=== LAYERS closed polys (w x h cm = /2) ===")
    for layer, items in sorted(layers.items()):
        items = sorted(items, key=lambda t: -(t[0]*t[1]))
        print(f"\n[{layer}] n={len(items)}")
        for ww, hh, box, col, closed in items[:12]:
            print(f"  {ww/2:7.2f}x{hh/2:7.2f} cm  col={col} closed={closed} bb=({box[0]/2:.1f},{box[2]/2:.1f})")
    print("\n=== TEXTS with 65/47.5/41/18.5/PAR ===")
    for x, y, raw, layer in texts:
        u = raw.upper()
        if any(s in u for s in ("65", "47", "41", "18", "METAL", "PAR", "PERFIL")):
            print(f"  {x/2:.1f},{y/2:.1f} [{layer}] {raw!r}")


if __name__ == "__main__":
    main()
