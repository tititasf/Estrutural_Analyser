import sqlite3
import json

conn = sqlite3.connect('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/project_data.vision')
conn.row_factory = sqlite3.Row
c = conn.cursor()

for table in ['beams', 'pillars', 'slabs', 'works', 'projects']:
    try:
        c.execute(f"SELECT * FROM {table} WHERE name='V306'")
        for row in c.fetchall():
            print(f"Table {table}:", dict(row))
    except Exception as e:
        print(e)
