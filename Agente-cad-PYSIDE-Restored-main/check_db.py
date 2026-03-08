import sqlite3
import os

db_path = "project_data.vision"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- PROJECTS ---")
    cursor.execute("SELECT id, name, work_name FROM projects")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- WORKS ---")
    cursor.execute("SELECT name FROM works")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()
else:
    print(f"Database not found at {db_path}")
