import sqlite3
import json

db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT classe, elemento_id, campos_json FROM reverse_eng_fichas WHERE elemento_id='V301' AND classe='FV' LIMIT 1")
    row = c.fetchone()
    if row:
        print(f"Classe: {row[0]}, Elemento: {row[1]}")
        data = json.loads(row[2])
        # flatten or un-nest
        while len(data.keys()) == 1 and isinstance(list(data.values())[0], dict):
            # some weird nesting happened? No, let's just print keys
            break
        print("Top level keys:", list(data.keys()))
        for k, v in data.items():
            if not isinstance(v, dict):
                print(f"{k}: {v}")
except Exception as e:
    print('Erro:', e)
