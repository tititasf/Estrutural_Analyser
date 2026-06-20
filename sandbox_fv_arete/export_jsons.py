import sqlite3
import json
import os
from pathlib import Path

db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'
obra_name = 'Obra_TREINO_1'
json_dir = Path(f'D:/Agente-cad-PYSIDE/DADOS-OBRAS/{obra_name}/Fase-4_Sincronizacao/JSON_Vigas_Fundo')
json_dir.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT elemento_id, campos_json FROM reverse_eng_fichas WHERE obra_name=? AND classe='FV'", (obra_name,))

for row in c.fetchall():
    elem_id = row[0]
    campos_json = row[1]
    
    er_ficha = json.loads(campos_json)
    ficha_clean = {
        k: v for k, v in er_ficha.items()
        if not k.startswith('_')
    }
    
    # Adicionar base fields required by the script
    ficha_clean.setdefault('name', elem_id)
    ficha_clean.setdefault('floor', 'Pavimento')
    ficha_clean.setdefault('panels', [])
    ficha_clean.setdefault('holes', [])
    ficha_clean.setdefault('pillar_left', {'active': False, 'width': 0.0, 'length': 0.0})
    ficha_clean.setdefault('pillar_right', {'active': False, 'width': 0.0, 'length': 0.0})
    ficha_clean.setdefault('sarrafo_left_id', 0)
    ficha_clean.setdefault('sarrafo_right_id', 0)
    
    out_path = json_dir / f"{elem_id}_fundo.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(ficha_clean, f, indent=2)

print("Exportados JSONs da DB para o disco!")
conn.close()
