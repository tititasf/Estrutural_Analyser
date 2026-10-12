import json
import sqlite3

con = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = con.cursor()
pid = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'
cur.execute("SELECT name, data_json FROM beams WHERE project_id = ?", (pid,))

beams_with_sections = []
for name, dj in cur.fetchall():
    d = json.loads(dj) if dj else {}
    contracts = d.get('lv_generation_contracts', {}).get('Passa', {})
    for side in ('A', 'B'):
        segs = contracts.get(side, {}).get('structural_segments', [])
        for seg in segs:
            if seg.get('section_contract') or seg.get('section_contracts'):
                beams_with_sections.append(name)
                break
        if name in beams_with_sections:
            break

print("Beams with section_contracts in Passa:", sorted(list(set(beams_with_sections))))
