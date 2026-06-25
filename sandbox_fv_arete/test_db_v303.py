import sqlite3, json
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT name, row_index, total_width, segments_rich FROM beams_fv WHERE name='V303'")
rows = c.fetchall()
print(json.dumps([json.loads(r[3]) for r in rows], indent=2))
