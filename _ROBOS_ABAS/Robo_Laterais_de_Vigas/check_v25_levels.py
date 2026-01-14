import pickle

with open(r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.pkl", "rb") as f:
    data = pickle.load(f)
viga = data.get("25")
print(f"Nivel Viga: {viga.get('nivel_viga')}")
print(f"Nivel Oposto: {viga.get('nivel_oposto')}")
