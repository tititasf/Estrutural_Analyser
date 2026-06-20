import json
import os

with open("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo/V303_fundo.json", "r", encoding="utf-8") as f:
    v303 = json.load(f)

print("V303 panels:")
for i, s in enumerate(v303.get('panels', [])):
    print(f"Segment {i} width: {s.get('total_width')}")
    for p in s.get('panels', []):
        print(f"  Panel width: {p.get('width')}")
