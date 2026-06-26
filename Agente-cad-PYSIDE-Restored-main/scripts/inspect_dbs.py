
import sqlite3
import os

dbs = [
    '_ROBOS_ABAS/Robo_Lajes/data/learning_map.db',
    '_ROBOS_ABAS/Robo_Lajes/test_ai.db',
    '_ROBOS_ABAS/Robo_Lajes/laje_src/data/learning_map.db',
    '_ROBOS_ABAS/Robo_Lajes/laje_src/learning_map.db'
]

for db in dbs:
    if os.path.exists(db):
        try:
            conn = sqlite3.connect(db)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print(f"DB: {db}")
            print(f"Tables: {tables}")
            for table in tables:
                col_info = conn.execute(f"PRAGMA table_info({table[0]})").fetchall()
                print(f"  Table {table[0]}: {[c[1] for c in col_info]}")
            conn.close()
        except Exception as e:
            print(f"Error reading {db}: {e}")
    else:
        print(f"File not found: {db}")
