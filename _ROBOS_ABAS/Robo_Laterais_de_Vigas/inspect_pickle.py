import pickle
import os

legacy_file = r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.pkl"
if os.path.exists(legacy_file):
    with open(legacy_file, 'rb') as f:
        data = pickle.load(f)
    print(f"Total keys: {len(data)}")
    first_key = list(data.keys())[0] if data else None
    print(f"First key: {first_key}")
    print(f"First value sample keys: {list(data[first_key].keys()) if first_key else 'N/A'}")
    if first_key:
        print(f"Sample data: {data[first_key]}")
else:
    print("File not found")
