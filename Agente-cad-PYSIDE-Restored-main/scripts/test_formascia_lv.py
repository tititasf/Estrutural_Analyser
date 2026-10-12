import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

import json
import sqlite3
import ezdxf
from copy import deepcopy
from src.core.vigas_drawing_config import LV_ASSEMBLIES, apply_lv_config, prepare_lv_sources
from scripts.arete.lv_n3_cut_draw import generate_local_panels, generate_local_sections

con = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
cur = con.cursor()
pid = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'

out_dir = ROOT / 'scripts/arete/relatorios/20261006_formascia_lv_teste'
out_dir.mkdir(parents=True, exist_ok=True)

beams_to_test = ['V302', 'V305']
generated_files = []

for beam_name in beams_to_test:
    cur.execute("SELECT data_json FROM beams WHERE project_id = ? AND name = ?", (pid, beam_name))
    dj = cur.fetchone()[0]
    data = json.loads(dj)
    contracts = data['lv_generation_contracts']['Passa']
    prepared_sides = prepare_lv_sources(contracts, mode='MOLDE_1')
    
    for assembly in ('gradeadas', 'sarrafeadas'):
        variant_sides = {side: apply_lv_config(prepared_sides.get(side) or {}, {'comportamento_laterais_vigas': assembly})
                         for side in ('A', 'B')}
        
        # 1. Panels Face A & Face B
        for side in ('A', 'B'):
            dxf_path = out_dir / f"LV_{beam_name}_Passa_VIEW_{side}_{assembly}.dxf"
            res = generate_local_panels(variant_sides, dxf_path, side, mode='MOLDE_1', behavior='Passa')
            doc = ezdxf.readfile(dxf_path)
            audit = doc.audit()
            print(f"[OK] {dxf_path.name} | Entities: {len(list(doc.modelspace()))} | Audit errors: {len(audit.errors)}")
            generated_files.append(dxf_path)
        
        # 2. Corte
        # To generate cut, we construct basic section contract from beam dimensions if missing in raw DB
        corte_sides = deepcopy(variant_sides)
        for s in ('A', 'B'):
            for seg in corte_sides[s].get('structural_segments', []):
                if not seg.get('section_contract'):
                    seg['section_contract'] = {
                        'beam': beam_name,
                        'beam_type': 'normal',
                        'form_role': 'beam',
                        'width_cm': float(corte_sides[s].get('total_width', 19.0)),
                        'height_cm': float(corte_sides[s].get('total_height', 60.0)),
                        'slabs': {'A': [], 'B': []},
                        'mounting': {'A': {'panel_top_cm': float(corte_sides[s].get('total_height', 60.0)), 'panel_base_cm': 0.0, 'h1_cm': float(corte_sides[s].get('total_height', 60.0)), 'lower_slab': False},
                                     'B': {'panel_top_cm': float(corte_sides[s].get('total_height', 60.0)), 'panel_base_cm': 0.0, 'h1_cm': float(corte_sides[s].get('total_height', 60.0)), 'lower_slab': False}},
                        'rules': {'face_allowance_cm': 0.0, 'panel_cm': 2.0, 'wood_cm': 7.0, 'cap_cm': 0.0},
                    }
        corte_path = out_dir / f"LV_{beam_name}_Passa_CORTE_{assembly}.dxf"
        try:
            res_corte = generate_local_sections(corte_sides, corte_path, mode='MOLDE_1', behavior='Passa')
            doc_corte = ezdxf.readfile(corte_path)
            audit_corte = doc_corte.audit()
            print(f"[OK] {corte_path.name} | Entities: {len(list(doc_corte.modelspace()))} | Audit errors: {len(audit_corte.errors)}")
            generated_files.append(corte_path)
        except Exception as exc:
            print(f"[FAIL] {corte_path.name}: {exc}")

print(f"\nTotal files generated: {len(generated_files)}")
