import sqlite3
import json

db_path = "project_data.vision"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- PROJECTS ---")
cursor.execute("SELECT id, name FROM projects")
projects = cursor.fetchall()
for p in projects:
    pid = p['id']
    cursor.execute("SELECT COUNT(*) FROM pillars WHERE project_id=?", (pid,))
    count_p = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM beams WHERE project_id=?", (pid,))
    count_b = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM slabs WHERE project_id=?", (pid,))
    count_s = cursor.fetchone()[0]
    print(f"Project: {p['name']} (ID: {pid}) -> P:{count_p}, B:{count_b}, S:{count_s}")

conn.close()
