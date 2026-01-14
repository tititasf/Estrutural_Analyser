import pickle

with open(r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.pkl", "rb") as f:
    data = pickle.load(f)
# Search for viga with numero 13.2
viga = None
for v in data.values():
    if v.get('numero') == '13.2' or v.get('numero') == 13.2:
        viga = v
        break

if viga:
    h_keys = [k for k in viga.keys() if 'alt' in k or 'h1' in k or 'h2' in k]
    print(f"Viga 13.2 Height keys: {h_keys}")
    for k in h_keys:
        print(f"  {k}: {viga[k]}")
else:
    print("Viga 13.2 not found")
