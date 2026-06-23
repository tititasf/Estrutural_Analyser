"""Dump N2 reference data for key beams."""
import sys, json, sqlite3
from pathlib import Path

DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
conn = sqlite3.connect(str(DB))

rows = conn.execute(
    "SELECT elemento_id, campos_json FROM reverse_eng_fichas "
    "WHERE classe='FV' AND obra_name='Obra_TREINO_1' AND pavimento LIKE '%13%'"
).fetchall()

for eid, cj_raw in sorted(rows, key=lambda x: x[0]):
    try:
        cj = json.loads(cj_raw)
    except:
        cj = {}
    panels = cj.get("panels", [])
    total_h = cj.get("total_height", 0)
    total_w = cj.get("total_width", 0)
    print(f"{eid:12s}  panels={len(panels):<3d}  comp(total_height)={str(total_h):<10s}  h(total_width)={total_w}")
    for i, p in enumerate(panels):
        print(f"              panel[{i}]: h={p.get('panel_height','?')} w={p.get('panel_width','?')}")

conn.close()
