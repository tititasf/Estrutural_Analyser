import os
import glob
from pathlib import Path
import json
import sqlite3
import traceback
import sys

sys.path.insert(0, "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts")
from motor_reverso_fv import extrair_ficha_fundo_viga

base_dir = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos"
db_path = "D:/Agente-cad-PYSIDE/project_data.vision"
json_out_dir = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo"

recortes = []
for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.startswith("FV_") and f.endswith(".dxf"):
            recortes.append(os.path.join(root, f))

import re
def extract_elem_id(filename):
    m = re.match(r'FV_(V\w+?)_motor_', filename)
    if m: return m.group(1)
    m = re.match(r'FV_(VF\w+?)_motor_', filename)
    if m: return m.group(1)
    # Check fallback like FV_V103.dxf ?
    m = re.match(r'FV_(V\w+?)\.dxf', filename)
    if m: return m.group(1)
    return None

conn = sqlite3.connect(db_path)
c = conn.cursor()

ok_count = 0
for rec in recortes:
    basename = os.path.basename(rec)
    elem_id = extract_elem_id(basename)
    if not elem_id:
        continue
        
    try:
        ficha = extrair_ficha_fundo_viga(
            rec, elem_id,
            obra_name="Obra_TREINO_1",
            obra_root="D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"
        )
        
        # update DB
        campos_json_str = json.dumps(ficha, ensure_ascii=False)
        c.execute("""
            UPDATE reverse_eng_fichas
            SET campos_json = ?, confianca = ?, status = 'extracted'
            WHERE obra_name = 'Obra_TREINO_1' AND classe = 'FV' AND elemento_id = ?
        """, (campos_json_str, ficha.get('_confianca', 0.9), elem_id))
        
        # update JSON
        out_json = os.path.join(json_out_dir, f"{elem_id}_fundo.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(ficha, f, ensure_ascii=False, indent=2)
            
        ok_count += 1
    except Exception as ex:
        print(f"Error on {elem_id}: {ex}")

conn.commit()
conn.close()

print(f"Processed {len(recortes)} recortes. Successfully updated {ok_count} elements in DB and JSON.")
