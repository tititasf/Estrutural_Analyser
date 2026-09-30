import json
import sqlite3
con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
beam = json.loads(con.execute(
    "SELECT data_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()[0])
for i in range(1, 17):
    c = beam["links"][f"viga_fundo_seg_{i}_area_segs"]["contour"][0]
    print(i, "validated", c.get("validated"), "keys", [k for k in c if k in ("validated", "geometry_source", "tag")])
