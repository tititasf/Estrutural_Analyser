import sqlite3

db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get the project
pid = '4869be2b-f17c-410b-a9c8-98a887ec1c95'
cur.execute('SELECT id, name, work_name, pavement_name, dxf_path FROM projects WHERE id=?', (pid,))
row = cur.fetchone()

print(f"Project row: {row}")

if row:
    dxf_path = row[4]
    import os
    if dxf_path:
        print(f"DXF path exists? {os.path.exists(dxf_path)}")
    else:
        print("DXF path is None")
