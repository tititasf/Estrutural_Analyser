import pickle
import os
import json

legacy_file = r"d:\Users\rvene\Desktop\GITHUB\Automacao_cad\Vigas\fundos_salvos.pkl"
if os.path.exists(legacy_file):
    with open(legacy_file, 'rb') as f:
        data = pickle.load(f)
    print(f"Total items: {len(data)}")
    for i, (k, v) in enumerate(data.items()):
        if i >= 1: break # Just first one
        print(f"Key: {k}")
        # Print all keys sorted
        all_keys = sorted(v.keys())
        print(f"Keys in value: {all_keys}")
        
        # Check specific height fields
        height_fields = [f for f in all_keys if 'alt' in f or 'h1' in f or 'h2' in f]
        print(f"Height related fields: {height_fields}")
        for f in height_fields:
            print(f"  {f}: {v[f]}")
else:
    print("File not found")
