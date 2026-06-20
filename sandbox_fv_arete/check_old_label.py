import sqlite3
import json

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' AND elemento_id='V306' ORDER BY updated_at ASC LIMIT 1")
row = c.fetchone()
data = json.loads(row[0])
print('old label_left:', data.get('label_left'))
