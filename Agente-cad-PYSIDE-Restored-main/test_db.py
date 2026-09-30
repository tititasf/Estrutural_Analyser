import sqlite3
import json

db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT obra_name, pavimento, classe, elemento_id, status FROM reverse_eng_fichas LIMIT 10")
    print("\nAmostra de Fichas:")
    for r in c.fetchall():
        print(r)
except Exception as e:
    print('Erro:', e)
