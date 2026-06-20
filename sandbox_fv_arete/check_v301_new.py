import sqlite3
import json

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE elemento_id='V301' ORDER BY updated_at DESC LIMIT 1")
row = c.fetchone()
if row:
    data = json.loads(row[0])
    print('Panels:', len(data.get('panels', [])))
    print(json.dumps(data.get('panels', [])[:2], indent=2))
