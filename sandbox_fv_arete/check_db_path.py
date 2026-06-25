import sqlite3
import json
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' AND elemento_id='V306'")
row = c.fetchone()
data = json.loads(row[0])
print(data.get('_er_meta', {}).get('dxf_path'))
