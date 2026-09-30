import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main")
from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter as F

con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
beam = json.loads(con.execute(
    "SELECT data_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()[0])
print("is_h", beam.get("is_h"), "fv_is_h", beam.get("fv_is_h"), "pos", beam.get("pos"))
texts = F._iter_dimension_texts(beam)
print("wh texts", len(texts))
links = beam.get("links") or {}
is_h = bool(beam.get("fv_is_h", beam.get("is_h", True)))
print("using is_h", is_h)
for i in range(1, 5):
    c = (links.get(f"viga_fundo_seg_{i}_area_segs") or {}).get("contour") or [{}]
    span = F._segment_axis_span(c[0].get("points") or [], is_horizontal=is_h)
    print(f"seg{i} span", span, "npts", len(c[0].get("points") or []))

# force assign counting even if same
beam2 = json.loads(json.dumps(beam))
for i in range(1, 17):
    beam2.setdefault("fields", {})[f"viga_fundo_seg_{i}_dim"] = "CLEAR"
n = F.assign_segment_dimensions_from_texts(beam2)
print("assigned after clear", n)
for i in range(1, 17):
    print(i, beam2["fields"].get(f"viga_fundo_seg_{i}_dim"))
