import sqlite3
import os
import sys

db_path = "project_data.vision"

if not os.path.exists(db_path):
    print(f"ERROR: {db_path} does not exist!")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. List Tables
    print("\n--- TABLES ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for t in tables:
        print(f"- {t[0]}")
        # Count rows
        try:
            c = conn.execute(f"SELECT COUNT(*) FROM {t[0]}")
            count = c.fetchone()[0]
            print(f"  Rows: {count}")
        except:
            print("  Rows: Error counting")

    # 2. Check Works
    print("\n--- WORKS ---")
    cursor.execute("SELECT * FROM works")
    works = cursor.fetchall()
    for w in works:
        print(w)

    # 3. Check Projects
    print("\n--- PROJECTS ---")
    try:
        # Try the exact query used in DatabaseManager.get_projects
        sql = """
            SELECT p.*,
                (SELECT COUNT(*) FROM pillars WHERE project_id = p.id) as pil_total,
                (SELECT COUNT(*) FROM pillars WHERE project_id = p.id AND is_validated=1) as pil_valid,
                (SELECT COUNT(*) FROM beams WHERE project_id = p.id) as beam_total,
                (SELECT COUNT(*) FROM beams WHERE project_id = p.id AND is_validated=1) as beam_valid,
                (SELECT COUNT(*) FROM slabs WHERE project_id = p.id) as slab_total,
                (SELECT COUNT(*) FROM slabs WHERE project_id = p.id AND is_validated=1) as slab_valid
            FROM projects p 
            ORDER BY updated_at DESC
            """
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        projects = [dict(r) for r in cursor.fetchall()]
        print(f"Projects found: {len(projects)}")
        for p in projects:
            print(f" - {p['name']} (Work: {p['work_name']})")
    except Exception as e:
        print(f"ERROR querying projects: {e}")

    conn.close()

except Exception as e:
    print(f"CRITICAL DB ERROR: {e}")
