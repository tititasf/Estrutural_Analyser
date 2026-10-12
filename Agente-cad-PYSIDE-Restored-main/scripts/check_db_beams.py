import sqlite3
import json

con = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = con.cursor()
pid = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'

for name in ['V302', 'V305']:
    cur.execute("SELECT data_json FROM beams WHERE project_id = ? AND name = ?", (pid, name))
    dj = cur.fetchone()[0]
    d = json.loads(dj)
    contract = d['lv_generation_contracts']['Passa']
    print(f"=== Beam {name} (Passa) ===")
    for side in ['A', 'B']:
        s = contract[side]
        print(f" Side {side}:")
        print(f"   total_width: {s.get('total_width')}, total_height: {s.get('total_height')}")
        print(f"   panels count: {len(s.get('panels', []))}")
        print(f"   structural_segments: {len(s.get('structural_segments', []))}")
        if s.get('panels'):
            print(f"   sample panel: {s['panels'][0]}")
        if s.get('structural_segments'):
            seg = s['structural_segments'][0]
            sec = seg.get('section_contract') or {}
            print(f"   sample section: beam={sec.get('beam')}, width={sec.get('width_cm')}, height={sec.get('height_cm')}")
