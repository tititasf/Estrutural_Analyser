import json
import sqlite3
import sys

sys.path.insert(0, r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main")
from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter as F

con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
beam = json.loads(con.execute(
    "SELECT data_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()[0])
texts = F._iter_dimension_texts(beam)
print("n texts", len(texts), "sample", texts[:3])
is_h = True
axis, trans_axis = 0, 1
PAD_T, PAD_E = F._DIM_TRANSVERSE_PAD, F._DIM_AXIS_END_PAD
print("pads", PAD_T, PAD_E)

c = (beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"])
span = F._segment_axis_span(c, is_horizontal=is_h)
span_min, span_max, axis_pos = span
print("span", span)
hits = 0
for t in texts:
    along = t["pos"][axis]
    trans = abs(t["pos"][trans_axis] - axis_pos)
    if trans > PAD_T:
        continue
    if along < span_min - PAD_E or along > span_max + PAD_E:
        continue
    hits += 1
    print(" HIT", t["text"], "pos", t["pos"], "trans", round(trans, 1), "along", round(along, 1))
print("hits", hits)
# how many texts have trans<50 to this axis
n_near = sum(1 for t in texts if abs(t["pos"][1] - axis_pos) <= PAD_T)
print("texts with trans<=50", n_near)
# y range of texts
ys = [t["pos"][1] for t in texts]
print("text y min/max", min(ys), max(ys))
