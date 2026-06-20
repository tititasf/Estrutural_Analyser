import sqlite3

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT obra_name, pavimento, classe, elemento_id, updated_at FROM reverse_eng_fichas WHERE elemento_id='V306'")
for row in c.fetchall():
    print(row)
