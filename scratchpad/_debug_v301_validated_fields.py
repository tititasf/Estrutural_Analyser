import json
import sqlite3
con = sqlite3.connect(r"D:\Agente-cad-PYSIDE\project_data.vision")
row = con.execute(
    "SELECT validated_fields_json, validated_link_classes_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()
print("validated_fields", row[0])
print("validated_link_classes", row[1])
beam = json.loads(con.execute(
    "SELECT data_json FROM beams WHERE id=?",
    ("dd238e47-1dc6-4f63-a760-4e7ce19a7386_b_1",),
).fetchone()[0])
print("validated_fields in data", (beam.get("validated_fields") or beam.get("fields", {}).get("validated")))
c = beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
print("contour1 sample keys", sorted(c.keys()))
print("validated value", c.get("validated"))
