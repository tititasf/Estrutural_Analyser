import sqlite3

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = conn.cursor()
cur.execute("DELETE FROM reverse_eng_fichas WHERE classe='FV'")
conn.commit()
print("FV DB cleared:", cur.rowcount)
conn.close()
