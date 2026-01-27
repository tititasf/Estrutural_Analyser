import json

with open(r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.json", 'r', encoding='utf-8') as f:


    data  = json.load(f)
viga = data.get("25")
h_keys = [k for k in viga.keys() if 'alt' in k or 'h1' in k or 'h2' in k]
print(f"Height related keys: {h_keys}")
for k in h_keys:
    print(f"  {k}: {viga[k]}")
