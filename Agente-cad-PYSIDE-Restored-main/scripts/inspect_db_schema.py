import sqlite3
import json

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()

c.execute("SELECT DISTINCT project_id FROM beam_elements")
print("Projects in beam_elements:", c.fetchall())

c.execute("SELECT id, name, dxf_path FROM projects")
print("Projects in projects table:", c.fetchall())

# Search for "contour" or "points" in any campos_json across beam_elements
c.execute("SELECT viga_nome, classe, campos_json FROM beam_elements WHERE campos_json LIKE '%points%' OR campos_json LIKE '%contour%' LIMIT 5")
rows = c.fetchall()
print("Beams with points/contour:", len(rows))
for r in rows:
    print(r[0], r[1], r[2][:300])

c.execute("SELECT id, obra_name, pavimento, classe, elemento_id, campos_json FROM reverse_eng_fichas WHERE campos_json LIKE '%points%' OR campos_json LIKE '%contour%' LIMIT 5")
rows_re = c.fetchall()
print("Reverse eng fichas with points/contour:", len(rows_re))
for r in rows_re:
    print(r[1], r[2], r[3], r[4], r[5][:300] if r[5] else None)
