import os
import sys
from pathlib import Path
import json

# Adicionar raiz ao PYTHONPATH
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from scripts.motor_reverso_fv import extrair_ficha_fundo_viga

def extract_n2_truth():
    target_dir = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes_reversos")
    
    # Encontrar a pasta do 13 PAV FV
    fv_dir = None
    for d in target_dir.iterdir():
        if "13" in d.name and "FV" in d.name and "motor" not in d.name:
            fv_dir = d
            break
            
    if not fv_dir:
        print("Pasta FV do 13_PAV nao encontrada!")
        return
        
    print(f"Lendo recortes N2 em: {fv_dir.name}\n")
    print(f"{'VIGA':<10} | {'SEGS':<5} | {'MEDIDAS DOS SEGMENTOS (cm)'}")
    print("-" * 60)
    
    dxf_files = list(fv_dir.glob("*.dxf"))
    
    total_segs = 0
    results = {}
    
    for dxf in dxf_files:
        # Pega o nome do elemento
        name_parts = dxf.stem.split('_')
        viga_name = ""
        for p in name_parts:
            if p.startswith('V') or p.startswith('VF'):
                viga_name = p
                break
        
        if not viga_name:
            viga_name = dxf.stem
            
        if viga_name in results:
            continue # Pular duplicatas
            
        try:
            ficha = extrair_ficha_fundo_viga(str(dxf), viga_name, "Obra_TREINO_1")
            # Em motor_reverso_fv a lista de segmentos pode vir em 'segments_rich' ou 'panels'
            # O main.py espera iterar em panels e somar width
            segs = ficha.get('segments_rich', ficha.get('panels', []))
            
            medidas = []
            for seg in segs:
                if 'panels' in seg:
                    medidas.append(sum([p.get('width', 0) for p in seg.get('panels', [])]))
                else:
                    medidas.append(seg.get('width', seg.get('comprimento', 0)))
            
            print(f"{viga_name:<10} | {len(segs):<5} | {medidas}")
            
            total_segs += len(segs)
            results[viga_name] = {
                "viga": viga_name,
                "segs": len(segs),
                "medidas": medidas
            }
            
        except Exception as e:
            print(f"{viga_name:<10} | ERRO  | Falha ao processar: {e}")
            
    print("-" * 60)
    print(f"Total de Vigas FV únicas: {len(results)}")
    print(f"Total de Segmentos contabilizados: {total_segs}")
    
    out_json = workspace_root / "scripts" / "n2_13pav_truth.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(list(results.values()), f, indent=2)

if __name__ == "__main__":
    extract_n2_truth()
