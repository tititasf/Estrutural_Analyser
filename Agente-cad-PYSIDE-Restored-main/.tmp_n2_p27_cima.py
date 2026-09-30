"""Measure N2 P27 CIMA: grades, bolts, dims, texts."""
from collections import Counter
from pathlib import Path
import ezdxf

path = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes_reversos"
    r"\ALIMONTI - PARAISO - 13° PAV.- PL - R00\PIL_P27_motor_178111335539.dxf"
)
doc = ezdxf.readfile(path)
msp = doc.modelspace()
print("layers", Counter(e.dxftype() + ":" + (e.dxf.layer or "") for e in msp))

texts = []
for e in msp:
    if e.dxftype() not in {"TEXT", "MTEXT"}:
        continue
    raw = e.plain_text() if e.dxftype() == "MTEXT" else (e.dxf.text or "")
    raw = raw.replace("\\P", " | ").strip()
    if not raw:
        continue
    ins = e.dxf.insert
    h = float(getattr(e.dxf, "height", 0) or getattr(e.dxf, "char_height", 0) or 0)
    texts.append((ins.x, ins.y, h, raw[:80], e.dxf.layer))

# CIMA cluster ~4800-5600 from earlier
print("\n=== TEXTS x=4800-5600 (CIMA) sorted ===")
cima = [t for t in texts if 4800 <= t[0] <= 5600]
for t in sorted(cima, key=lambda r: (round(r[1], 0), r[0])):
    print(f"  {t[0]:8.1f} {t[1]:8.1f} h={t[2]:5.1f} [{t[4]}] {t[3]}")

print("\n=== TEXTS x=6400-7600 (ABCD) sample heights ===")
abcd = [t for t in texts if 6400 <= t[0] <= 7600]
heights = Counter(round(t[2], 1) for t in abcd)
print("abcd text heights", heights)

print("\n=== LINES in CIMA bbox ===")
# collect line endpoints in cima x
segs = []
for e in msp:
    dt = e.dxftype()
    layer = e.dxf.layer
    if dt == "LINE":
        x0, y0 = e.dxf.start.x, e.dxf.start.y
        x1, y1 = e.dxf.end.x, e.dxf.end.y
        if 4800 <= min(x0, x1) and max(x0, x1) <= 5600:
            segs.append((layer, x0, y0, x1, y1, ((x1-x0)**2+(y1-y0)**2)**0.5))
    elif dt == "LWPOLYLINE":
        pts = list(e.get_points("xy"))
        xs = [p[0] for p in pts]
        if xs and 4800 <= min(xs) and max(xs) <= 5600:
            ys = [p[1] for p in pts]
            segs.append((layer + "/PL", min(xs), min(ys), max(xs), max(ys), max(xs)-min(xs)))

print("cima segs", len(segs))
by_layer = {}
for s in segs:
    by_layer.setdefault(s[0], []).append(s)
for layer, items in sorted(by_layer.items()):
    lens = sorted({round(it[5], 1) for it in items})[:12]
    print(f"  {layer}: n={len(items)} lens={lens}")

print("\n=== Hatch in CIMA ===")
for e in msp:
    if e.dxftype() != "HATCH":
        continue
    box = None
    try:
        box = e.bbox()
    except Exception:
        pass
    if box and 4800 <= box.extmin.x and box.extmax.x <= 5600:
        print(" hatch", e.dxf.layer, "pattern", getattr(e, "pattern_name", None),
              f"x={box.extmin.x:.1f}..{box.extmax.x:.1f} y={box.extmin.y:.1f}..{box.extmax.y:.1f}")
