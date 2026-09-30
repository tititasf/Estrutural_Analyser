import json
import sqlite3
from pathlib import Path

db = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
con = sqlite3.connect(str(db))
con.row_factory = sqlite3.Row
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("tables with beam/viga/slab:")
for t in tables:
    if any(x in t.lower() for x in ("beam", "viga", "slab", "laje", "project")):
        print(" ", t)

# try common
for t in ("beams", "slabs", "projects"):
    if t in tables:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"\n{t} cols:", cols[:40])
