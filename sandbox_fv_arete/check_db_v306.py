import sqlite3
import json
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT obra_name, classe, elemento_id, status FROM reverse_eng_fichas WHERE elemento_id LIKE '%306%'")
for row in c.fetchall():
    print(row)
