import pickle
import os

pkl_path = r'C:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src\core\pilares_salvos.pkl'

print("="*60)
print("INSPECIONANDO pilares_salvos.pkl")
print("="*60)

if not os.path.exists(pkl_path):
    print("ARQUIVO NÃO ENCONTRADO!")
    exit(1)

with open(pkl_path, 'rb') as f:
    data = pickle.load(f)

print(f"\nTIPO: {type(data)}")
print(f"TOTAL: {len(data) if hasattr(data, '__len__') else 'N/A'}")

if isinstance(data, list) and len(data) > 0:
    print(f"\nPRIMEIRO ITEM:")
    first = data[0]
    print(f"  Tipo: {type(first)}")
    
    if isinstance(first, dict):
        print(f"  Chaves: {list(first.keys())}")
        for key in ['obra', 'pavimento', 'numero', 'nome']:
            if key in first:
                print(f"  {key}: {first[key]}")
    elif hasattr(first, '__dict__'):
        print(f"  Atributos: {list(vars(first).keys())}")
        for attr in ['obra', 'pavimento', 'numero', 'nome']:
            if hasattr(first, attr):
                print(f"  {attr}: {getattr(first, attr)}")
    else:
        print(f"  Valor: {first}")
    
    # Buscar OBRA-TESTE1
    print(f"\n" + "="*60)
    print("BUSCANDO OBRA-TESTE1, P-1")
    print("="*60)
    
    count_teste1 = 0
    count_p1 = 0
    
    for item in data:
        if isinstance(item, dict):
            obra = str(item.get('obra', ''))
            pav = str(item.get('pavimento', ''))
        elif hasattr(item, 'obra'):
            obra = str(item.obra) if item.obra else ''
            pav = str(item.pavimento) if hasattr(item, 'pavimento') and item.pavimento else ''
        else:
            continue
        
        if 'TESTE' in obra.upper():
            count_teste1 += 1
            if pav == 'P-1':
                count_p1 += 1
    
    print(f"\nPilares OBRA-TESTE1: {count_teste1}")
    print(f"Pilares P-1: {count_p1}")

print("\n" + "="*60)
