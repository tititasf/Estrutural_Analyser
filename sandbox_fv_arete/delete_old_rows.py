import sqlite3

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("DELETE FROM reverse_eng_fichas WHERE updated_at < '2026-06-17'")
conn.commit()
print('Deleted old rows!')
