import sqlite3

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT updated_at FROM reverse_eng_fichas WHERE elemento_id='V306' ORDER BY updated_at DESC LIMIT 1")
print(c.fetchone()[0])
