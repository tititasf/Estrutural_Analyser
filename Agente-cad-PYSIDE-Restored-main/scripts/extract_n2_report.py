import json
import sys
from pathlib import Path

def extract_from_report(report_path):
    with open(report_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Dependendo de como o relatorio.json eh estruturado, vamos tentar buscar
    fundos = []
    
    # Se for uma lista de resultados
    items = data if isinstance(data, list) else data.get('resultados', data.get('items', []))
    if isinstance(data, dict):
        # Tentar buscar em todos os values se o root for um dict com chaves
        for v in data.values():
            if isinstance(v, list):
                items.extend(v)
            elif isinstance(v, dict) and 'panels' in v:
                items.append(v)
                
    for item in items:
        # Se for um item FV
        name = item.get('name', item.get('viga', ''))
        # Filtrar para fundo
        if 'FV' in name or name.startswith('V'):
            panels = item.get('panels', [])
            if panels:
                medidas = [p.get('total_width', 0) for p in panels]
                fundos.append({
                    "viga": name,
                    "segmentos": len(panels),
                    "medidas": medidas
                })
                print(f"✅ Viga: {name} | Segs: {len(panels)} | Medidas: {medidas}")
                
    return fundos

if __name__ == "__main__":
    p = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\relatorios\20260614_225555\relatorio.json")
    print("Iniciando extração do relatório...")
    res = extract_from_report(p)
    print(f"\nTotal extraído: {len(res)} vigas.")
