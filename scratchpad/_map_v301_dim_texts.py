import json
import re
import sqlite3

con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
row = con.execute(
    "SELECT data_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()
data = json.loads(row[0])
fields = data.get("fields") or {}
geo = data.get("geometry") or {}
dt = geo.get("dimension_texts") or []
DIM = re.compile(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)")

segs = []
for i in range(1, 17):
    slots = (data.get("links") or {}).get(f"viga_fundo_seg_{i}_area_segs") or {}
    contour = (slots.get("contour") or [{}])[0]
    pts = contour.get("points") or []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    segs.append({
        "i": i,
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "cx": (min(xs)+max(xs))/2,
        "cy": (min(ys)+max(ys))/2,
        "ficha_h": (contour.get("ficha") or {}).get("altura_total"),
        "field": fields.get(f"viga_fundo_seg_{i}_dim"),
    })

by = 3000.5
print("=== W/H texts near V301 row y~3000 ===")
near = []
for t in dt:
    m = DIM.search(str(t.get("text") or ""))
    if not m or not t.get("pos"):
        continue
    x, y = float(t["pos"][0]), float(t["pos"][1])
    if abs(y - by) > 120:  # within 1.2m of beam axis
        continue
    a, b = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    w, h = min(a, b), max(a, b)
    near.append((x, y, t["text"], w, h))
near.sort()
for item in near:
    print(f"  x={item[0]:8.1f} y={item[1]:8.1f}  {item[2]!r:10}  h={item[4]:g}")

print("\n=== nearest text to each segment (axis projection, |dy|<80) ===")
for s in segs:
    cands = []
    for x, y, txt, w, h in near:
        if s["xmin"] - 30 <= x <= s["xmax"] + 30:
            dy = abs(y - s["cy"])
            dx = 0 if s["xmin"] <= x <= s["xmax"] else min(abs(x-s["xmin"]), abs(x-s["xmax"]))
            cands.append((dx + dy * 0.25, txt, w, h, x, y))
    cands.sort()
    best = cands[0] if cands else None
    print(
        f"seg{s['i']:2} x={s['xmin']:.0f}-{s['xmax']:.0f} "
        f"field={s['field']!r:8} ficha_h={s['ficha_h']!r:6} "
        f"best={best[1] if best else None} n={len(cands)}"
    )
