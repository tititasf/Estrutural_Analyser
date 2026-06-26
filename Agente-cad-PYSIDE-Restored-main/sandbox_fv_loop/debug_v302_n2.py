import sys, json, sqlite3
from pathlib import Path

DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
conn = sqlite3.connect(str(DB))

row = conn.execute(
    "SELECT campos_json FROM reverse_eng_fichas "
    "WHERE classe='FV' AND obra_name='Obra_TREINO_1' AND pavimento LIKE '%13%' AND elemento_id='V302'"
).fetchone()

if row:
    data = json.loads(row[0])
    print(json.dumps(data, indent=2))
else:
    print("V302 not found")
