import os
import sys
import json
from pathlib import Path

# Adicionar raiz ao PYTHONPATH
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from scripts.motor_reverso_fv import extrair_ficha_fundo_viga

def extract_n2_data_for_pav(pavimento="13_PAV"):
    print(f"=== EXTRAINDO GABARITO N2 ({pavimento}) ===")
    
    # Buscar possiveis locais dos recortes N2 (DXF) do pavimento
    # Tentar buscar em projects_repo
    base_repo = workspace_root / "projects_repo"
    
    fv_n2_list = []
    
    # Procurar por pastas de FV do pavimento
    # Geralmente os recortes N2 ficam em pastas com o nome do item ou na subpasta de Fase-6
    dxf_files = list(workspace_root.rglob(f"*FV*{pavimento}*.dxf")) + list(workspace_root.rglob(f"*{pavimento}*FV*.dxf"))
    
    if not dxf_files:
        # Tentar buscar arquivos com V301..V332 para ver se achamos algo
        print("Buscando por DXFs de vigas fundo conhecidas (V301 a V332)...")
        for i in range(301, 333):
            dxf_files.extend(list(workspace_root.rglob(f"*V{i}*.dxf")))
    
    # Remover duplicatas
    dxf_files = list(set(dxf_files))
    
    print(f"Encontrados {len(dxf_files)} DXFs potenciais de vigas.")
    
    for dxf in dxf_files:
        try:
            # Tenta inferir o nome da viga pelo nome do arquivo
            name_parts = dxf.stem.split('_')
            viga_name = name_parts[-1] if len(name_parts) > 1 else dxf.stem
            
            # Alguns testes podem ser lajes ou pilares, tenta ignorar
            if 'PIL' in dxf.name or 'LAJ' in dxf.name:
                continue
                
            ficha = extrair_ficha_fundo_viga(str(dxf), viga_name)
            
            panels = ficha.get('panels', [])
            if not panels:
                continue
                
            # Extrair contornos/medidas
            medidas = [p.get('total_width', 0) for p in panels]
            
            fv_n2_list.append({
                "viga": viga_name,
                "segmentos_n2": len(panels),
                "medidas_n2": medidas,
                "dxf": str(dxf)
            })
            
            print(f"N2 -> Viga: {viga_name} | Segs: {len(panels)} | Medidas: {medidas}")
            
        except Exception as e:
            pass
            
    return fv_n2_list

if __name__ == "__main__":
    n2_data = extract_n2_data_for_pav("13_PAV")
    print(f"\nTotal extraído com sucesso: {len(n2_data)} vigas fundo (N2).")
