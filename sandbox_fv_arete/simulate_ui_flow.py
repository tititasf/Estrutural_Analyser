"""
Simular EXATAMENTE o fluxo da UI para N4 da V306.
"""
import sqlite3, json

# Step 1: _get_er_ficha_dict - busca no DB
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' AND elemento_id='V306'")
row = c.fetchone()
er_ficha = json.loads(row[0])
conn.close()

print("=== er_ficha do DB ===")
print(f"  segments_rich: {len(er_ficha.get('segments_rich', []))}")
print(f"  panels: {len(er_ficha.get('panels', []))}")  
print(f"  label_left: {er_ficha.get('label_left')}")
print(f"  label_right: {er_ficha.get('label_right')}")
print(f"  holes active: {[h.get('active') for h in er_ficha.get('holes',[])]}")

# Step 2: _start_n4_generation - cria ficha_clean
ficha_clean = {
    k: v for k, v in er_ficha.items()
    if not k.startswith('_')
}
ficha_clean.setdefault('name', 'V306')
ficha_clean.setdefault('floor', 'Pavimento')
ficha_clean.setdefault('panels', [])
ficha_clean.setdefault('holes', [])
ficha_clean.setdefault('pillar_left', {'active': False, 'width': 0.0, 'length': 0.0})
ficha_clean.setdefault('pillar_right', {'active': False, 'width': 0.0, 'length': 0.0})
ficha_clean.setdefault('sarrafo_left_id', 0)
ficha_clean.setdefault('sarrafo_right_id', 0)

print("\n=== ficha_clean (o que a UI salva no JSON temp) ===")
print(f"  segments_rich: {len(ficha_clean.get('segments_rich', []))}")
print(f"  panels: {len(ficha_clean.get('panels', []))}")
print(f"  label_left: {ficha_clean.get('label_left')}")
print(f"  label_right: {ficha_clean.get('label_right')}")
print(f"  holes active: {[h.get('active') for h in ficha_clean.get('holes',[])]}")

# Step 3: Salva JSON temporario
out_path = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo/V306_n4er_fundo.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(ficha_clean, f, ensure_ascii=False, indent=2)

# Step 4: Verifica o que foi salvo
with open(out_path, 'r', encoding='utf-8') as f:
    saved = json.load(f)
print(f"\n=== JSON salvo em disco ===")
print(f"  segments_rich: {len(saved.get('segments_rich', []))}")
print(f"  panels: {len(saved.get('panels', []))}")
print(f"  label_left: {saved.get('label_left')}")
print(f"  label_right: {saved.get('label_right')}")
print(f"  holes active: {[h.get('active') for h in saved.get('holes',[])]}")

# Step 5: Simula o gerar_fv_dxf_stog.py lendo o JSON
d = saved
seg_rich = d.get('segments_rich', d.get('panels', []))
print(f"\n=== O que gerar_fv_dxf_stog.py vai usar ===")
print(f"  panels_json (from segments_rich or panels): {len(seg_rich)} items")
for i, s in enumerate(seg_rich):
    if isinstance(s, dict) and 'total_width' in s:
        print(f"    seg[{i}]: total_width={s['total_width']}, n_panels={len(s.get('panels', []))}")
        for j, p in enumerate(s.get('panels', [])):
            verts = p.get('vertices')
            print(f"      panel[{j}]: width={p.get('width')}, has_verts={verts is not None}, n_verts={len(verts) if verts else 0}")
    else:
        print(f"    panel[{i}]: width={s.get('width', s)}")
