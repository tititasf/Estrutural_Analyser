import sys
from pathlib import Path
ROOT = Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

import json
import sqlite3
from src.core.vigas_drawing_config import apply_lv_config, prepare_lv_sources
from src.core.lv_nova_sa_adapter import ab_runs

con = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = con.cursor()
pid = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'

cur.execute("SELECT data_json FROM beams WHERE project_id = ? AND name = 'V302'", (pid,))
dj = cur.fetchone()[0]
data = json.loads(dj)
contracts = data['lv_generation_contracts']['Passa']
prepared_sides = prepare_lv_sources(contracts, mode='NOVA')

for assembly in ('sarrafeadas', 'gradeadas'):
    source = apply_lv_config(prepared_sides['A'], {'comportamento_laterais_vigas': assembly})
    source = dict(source, side='A')
    runs = ab_runs(source)
    print(f"=== Assembly {assembly} runs count: {len(runs)} ===")
    for r in runs:
        print(f"  beam: {r['beam']}, side: {r['side']}, total_cm: {r['total_cm']}, body_cm: {r['body_cm']}")
        print(f"  segments count: {len(r['segments'])}")
        for s in r['segments']:
            print(f"    seg length: {s['length']}, total_cm: {s['total_cm']}, beam_openings: {s['beam_openings']}, column_openings: {s['column_openings']}")
