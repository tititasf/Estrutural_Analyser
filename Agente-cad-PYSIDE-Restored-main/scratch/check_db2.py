import sqlite3
import json

db_path = "src/core/dados_locais.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM beam_elements WHERE classe='FV'")
print(f"beam_elements FV count: {c.fetchone()[0]}")

c.execute("SELECT id, name, data_json FROM beams")
beams = c.fetchall()
print(f"Total beams in DB: {len(beams)}")

fv_links = 0
for b in beams:
    data = json.loads(b[2])
    if any(k.startswith('viga_fundo_seg_') for k in data.get('links', {}).keys()):
        fv_links += 1

print(f"Beams with FV links: {fv_links}")
conn.close()
