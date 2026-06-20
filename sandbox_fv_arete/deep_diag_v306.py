import sqlite3, json
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' AND elemento_id='V306'")
row = c.fetchone()
data = json.loads(row[0])

# Top-level keys
print("=== TOP-LEVEL KEYS ===")
for k in data:
    v = data[k]
    if isinstance(v, (list, dict)):
        print(f"  {k}: {type(v).__name__} len={len(v)}")
    else:
        print(f"  {k}: {v!r}")

print()
print("=== panels (top-level) ===")
for p in data.get('panels', []):
    print(f"  {p}")

print()
print("=== segments_rich (top-level) ===")
for s in data.get('segments_rich', []):
    print(f"  total_width={s.get('total_width')}, n_panels={len(s.get('panels',[]))}")

print()
print("=== _fase4_ref keys ===")
ref = data.get('_fase4_ref', {})
for k in ref:
    v = ref[k]
    if isinstance(v, (list, dict)):
        print(f"  {k}: {type(v).__name__} len={len(v)}")
    else:
        print(f"  {k}: {v!r}")

print()
print("=== _fase4_ref.segments_rich ===")
for s in ref.get('segments_rich', []):
    print(f"  total_width={s.get('total_width')}, n_panels={len(s.get('panels',[]))}")

print()
print("=== _fase4_ref.label_left/right ===")
print(f"  label_left: {ref.get('label_left')}")
print(f"  label_right: {ref.get('label_right')}")

conn.close()
