import sqlite3

db_path = "project_data.vision"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- ORPHANED PILLARS ---")
cursor.execute("SELECT id, project_id, name FROM pillars WHERE project_id NOT IN (SELECT id FROM projects)")
orphans = cursor.fetchall()
for o in orphans:
    print(f"Pillar: {o['name']} (ID: {o['id']}) -> Missing Project: {o['project_id']}")

print("\n--- ORPHANED BEAMS ---")
cursor.execute("SELECT id, project_id, name FROM beams WHERE project_id NOT IN (SELECT id FROM projects)")
orphans = cursor.fetchall()
for o in orphans:
    print(f"Beam: {o['name']} (ID: {o['id']}) -> Missing Project: {o['project_id']}")

print("\n--- ORPHANED SLABS ---")
cursor.execute("SELECT id, project_id, name FROM slabs WHERE project_id NOT IN (SELECT id FROM projects)")
orphans = cursor.fetchall()
for o in orphans:
    print(f"Slab: {o['name']} (ID: {o['id']}) -> Missing Project: {o['project_id']}")

conn.close()
