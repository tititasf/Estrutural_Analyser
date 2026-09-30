import json
import sqlite3
from collections import Counter

con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
row = con.execute(
    "SELECT data_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()
data = json.loads(row[0])
geo = data.get("geometry") or {}
print("geometry keys", list(geo)[:30])
classified = geo.get("classified") or {}
print("classified keys", list(classified)[:20])
dt = geo.get("dimension_texts") or []
print("dimension_texts", len(dt))
for t in dt[:25]:
    print(" ", t.get("text"), "pos", t.get("pos"))

print("\nfields dim")
fields = data.get("fields") or {}
for k in sorted(fields):
    if k.endswith("_dim") and "fundo" in k:
        print(f"  {k}={fields[k]!r}")

print("\nseg_bottom count", len((data.get("links") or {}).get("viga_segs", {}).get("seg_bottom") or []))
# area segs
n_area = sum(1 for k in (data.get("links") or {}) if str(k).startswith("viga_fundo_seg_") and str(k).endswith("_area_segs"))
print("area_segs slots", n_area)

# ficha altura per contour
for i in range(1, 17):
    slots = (data.get("links") or {}).get(f"viga_fundo_seg_{i}_area_segs") or {}
    contour = (slots.get("contour") or [{}])[0]
    ficha = contour.get("ficha") or {} if isinstance(contour, dict) else {}
    pts = contour.get("points") if isinstance(contour, dict) else None
    bbox = None
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bbox = (min(xs), min(ys), max(xs), max(ys))
    print(f" seg{i}: dim_field={fields.get(f'viga_fundo_seg_{i}_dim')!r} altura_ficha={ficha.get('altura_total')!r} bbox={bbox}")
