import sqlite3

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reverse_eng_fichas'")
print(c.fetchone()[0])
