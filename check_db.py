
import sqlite3
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/project_data.vision')
c = conn.cursor()
c.execute('SELECT name FROM sqlite_master WHERE type=''table''')
print(c.fetchall())

