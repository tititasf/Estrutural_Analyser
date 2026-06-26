import pickle
import os

pkl_path = r'C:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src\core\pilares_salvos.pkl'

print("="*60)
print("INSPECIONANDO pilares_salvos.pkl (DICT)")
print("="*60)

with open(pkl_path, 'rb') as f:
    data = pickle.load(f)

print(f"\nTIPO: {type(data)}")
print(f"TOTAL DE CHAVES: {len(data)}")

# Mostrar primeiras 5 chaves
keys = list(data.keys())[:5]
print(f"\nPRIMEIRAS 5 CHAVES:")
for key in keys:
    print(f"  {key}")

# Mostrar estrutura de um valor
if keys:
    first_key = keys[0]
    first_value = data[first_key]
    print(f"\nESTRUTURA DO VALOR (chave='{first_key}'):")
    print(f"  Tipo: {type(first_value)}")
    
    if isinstance(first_value, dict):
        print(f"  Chaves: {list(first_value.keys())}")
    elif hasattr(first_value, '__dict__'):
        print(f"  Atributos: {list(vars(first_value).keys())}")
        # Mostrar alguns valores
        for attr in ['obra', 'pavimento', 'numero', 'nome']:
            if hasattr(first_value, attr):
                val = getattr(first_value, attr)
                print(f"    {attr}: {val}")

# Buscar OBRA-TESTE1
print(f"\n" + "="*60)
print("BUSCANDO OBRA-TESTE1, P-1")
print("="*60)

p1_pilares = []
for key, pilar in data.items():
    if hasattr(pilar, 'obra') and hasattr(pilar, 'pavimento'):
        if 'TESTE' in str(pilar.obra).upper() and str(pilar.pavimento) == 'P-1':
            p1_pilares.append(pilar)

print(f"\nPilares encontrados em P-1: {len(p1_pilares)}")

if p1_pilares:
    print(f"\nEXEMPLO DO PRIMEIRO PILAR:")
    p = p1_pilares[0]
    for attr in dir(p):
        if not attr.startswith('_'):
            try:
                val = getattr(p, attr)
                if not callable(val):
                    print(f"  {attr}: {val}")
            except:
                pass

print("\n" + "="*60)
print(f"CONCLUSÃO: Encontrados {len(p1_pilares)} pilares do P-1 no arquivo legado")
print("="*60)
