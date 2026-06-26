import sqlite3
import os
import glob

db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute('SELECT id, dxf_path FROM projects')
rows = cur.fetchall()

updated = 0
for pid, dxf_path in rows:
    if dxf_path and not os.path.exists(dxf_path):
        dir_path = os.path.dirname(dxf_path)
        if os.path.exists(dir_path):
            dxf_files = glob.glob(os.path.join(dir_path, 'EL-(Torre-*.dxf'))
            if not dxf_files:
                # also check for torre_1.dxf.bak to maybe copy it
                if os.path.exists(dxf_path + ".bak"):
                    import shutil
                    shutil.copy(dxf_path + ".bak", dxf_path)
                    print(f"Copied .bak for {pid}")
                    updated += 1
            else:
                new_path = dxf_files[0]
                cur.execute('UPDATE projects SET dxf_path=? WHERE id=?', (new_path, pid))
                print(f"Updated {pid} to {new_path}")
                updated += 1

if updated > 0:
    conn.commit()
    print(f"Fixed {updated} projects.")
else:
    print("No projects needed fixing.")

conn.close()
