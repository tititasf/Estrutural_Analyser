import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import sqlite3

conn = sqlite3.connect("D:/Agente-cad-PYSIDE/project_data.vision")
rows = conn.execute("SELECT viga_nome, campos_json FROM beam_elements WHERE classe='FV'").fetchall()
for r in rows:
    if r[0] in ['V321', 'V306']:
        print(f"{r[0]}: {r[1][:200]}...")
