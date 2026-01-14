import pickle
import sys

try:
    with open(r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.pkl", "rb") as f:
        data = pickle.load(f)
    viga = data.get("25")
    if viga:
        print(f"Alturas: {viga.get('paineis_alturas')}")
        print(f"Alturas2: {viga.get('paineis_alturas2')}")
        print(f"Grade H1: {viga.get('paineis_grade_altura1')}")
        print(f"Grade H2: {viga.get('paineis_grade_altura2')}")
    else:
        print("Viga 25 not found")
except Exception as e:
    print(f"Error: {e}")
