import sqlite3
import json

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE elemento_id='V301' ORDER BY updated_at DESC LIMIT 1")
row = c.fetchone()
if row:
    er_ficha = json.loads(row[0])
    ficha_clean = { k: v for k, v in er_ficha.items() if not k.startswith('_') }
    ficha_clean['name'] = 'V301_n4er'
    with open('D:/Agente-cad-PYSIDE/sandbox_fv_arete/V301_n4er_fundo.json', 'w') as f:
        json.dump(ficha_clean, f)
