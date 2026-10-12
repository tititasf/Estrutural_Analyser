import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

import json
import sqlite3
from src.core.vigas_drawing_config import LV_ASSEMBLIES, apply_lv_config, prepare_lv_sources
from scripts.arete.lv_n3_cut_draw import generate_local_sections

con = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = con.cursor()
pid = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'

out_dir = ROOT / 'scripts/arete/relatorios/teste_lv_nova_baseline'

for beam_name in ['V302', 'V305']:
    cur.execute("SELECT data_json FROM beams WHERE project_id = ? AND name = ?", (pid, beam_name))
    dj = cur.fetchone()[0]
    data = json.loads(dj)
    contracts = data['lv_generation_contracts']['Passa']
    prepared_sides = prepare_lv_sources(contracts, mode='NOVA')
    
    for assembly in LV_ASSEMBLIES:
        variant_sides = {side: apply_lv_config(prepared_sides.get(side) or {}, {'comportamento_laterais_vigas': assembly})
                         for side in ('A', 'B')}
        dxf_path = out_dir / f"{beam_name}_Passa_CORTE_{assembly}.dxf"
        try:
            res = generate_local_sections(variant_sides, dxf_path, mode='NOVA', behavior='Passa')
            print(f"Generated {dxf_path.name}: {res is not None}")
        except Exception as e:
            print(f"Failed {dxf_path.name}: {e}")
