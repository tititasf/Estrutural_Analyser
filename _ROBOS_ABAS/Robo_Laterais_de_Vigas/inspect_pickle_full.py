import json
import os
import json

legacy_file = r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.json"
if os.path.exists(legacy_file):
    with open(legacy_file, 'r', encoding='utf-8') as f:

        data  = json.load(f)
    print(f"Total items: {len(data)}")
    
    # Check 5 items
    for i, (k, v) in enumerate(data.items()):
        if i >= 5: break
        print(f"\nViga: {k}")
        print(f"  numero: {v.get('numero')}")
        print(f"  altura_geral: {v.get('altura_geral')}")
        print(f"  nivel_viga: {v.get('nivel_viga')}")
        print(f"  paineis_alturas: {v.get('paineis_alturas')}")
        print(f"  paineis_alturas2: {v.get('paineis_alturas2')}")
        print(f"  paineis_grade_altura1: {v.get('paineis_grade_altura1')}")
        print(f"  paineis_grade_altura2: {v.get('paineis_grade_altura2')}")
        
else:
    print("File not found")
