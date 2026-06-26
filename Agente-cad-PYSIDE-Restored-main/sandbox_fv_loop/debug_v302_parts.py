import sqlite3, json
from pathlib import Path

DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
conn = sqlite3.connect(str(DB))

rows = conn.execute(
    "SELECT elemento_id, campos_json FROM reverse_eng_fichas "
    "WHERE classe='FV' AND obra_name='Obra_TREINO_1' AND pavimento LIKE '%13%'"
).fetchall()

print("FV N2 Fichas:")
for eid, cj_str in rows:
    cj = json.loads(cj_str or "{}")
    total_h = cj.get("total_height", 0)
    total_w = cj.get("total_width", 0)
    if "V302" in eid or "V302" in str(cj):
        print(f"{eid:12s} comp={str(total_h):<10s}  h={total_w}")

