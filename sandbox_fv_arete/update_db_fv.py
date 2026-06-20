import os
import json
import sqlite3
import glob

db_path = "D:/Agente-cad-PYSIDE/project_data.vision"
json_dir = "D:/Agente-cad-PYSIDE/sandbox_fv_arete"
json_out_dir = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo"

conn = sqlite3.connect(db_path)
c = conn.cursor()

json_files = glob.glob(os.path.join(json_dir, "*_ficha_n2.json"))

for jf in json_files:
    elem_id = os.path.basename(jf).replace("_ficha_n2.json", "")
    with open(jf, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 1. Update DB
    campos_json_str = json.dumps(data, ensure_ascii=False)
    c.execute("""
        UPDATE reverse_eng_fichas
        SET campos_json = ?, confianca = ?, status = 'extracted'
        WHERE obra_name = 'Obra_TREINO_1' AND classe = 'FV' AND elemento_id = ?
    """, (campos_json_str, data.get('_confianca', 0.9), elem_id))
    
    # 2. Update Fase-4 JSON
    out_json = os.path.join(json_out_dir, f"{elem_id}_fundo.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

conn.commit()
conn.close()

print(f"Updated {len(json_files)} FV elements in DB and Fase-4 JSON directory.")
