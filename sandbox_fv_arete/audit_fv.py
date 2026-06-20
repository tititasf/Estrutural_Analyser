"""
AUDITORIA COMPLETA: Rastrear todos os caminhos que tocam FV no sistema.
"""
import os, glob

print("=" * 80)
print("1. TODOS OS DXFs FV em Fase-6 (cache que a UI carrega)")
print("=" * 80)
fase6 = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD'
for root, dirs, files in os.walk(fase6):
    for f in files:
        if 'FV' in f.upper() or 'fv' in f.lower() or 'fundo' in f.lower():
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            mt = os.path.getmtime(fp)
            from datetime import datetime
            ts = datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  {ts}  {sz:>8} bytes  {fp}")

print()
print("=" * 80)
print("2. TODOS OS JSONs FV temporarios (n4er) na pasta JSON_Vigas_Fundo")
print("=" * 80)
json_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo'
for f in sorted(os.listdir(json_dir)):
    if 'n4er' in f:
        fp = os.path.join(json_dir, f)
        sz = os.path.getsize(fp)
        mt = os.path.getmtime(fp)
        ts = datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {ts}  {sz:>8} bytes  {f}")

print()
print("=" * 80)
print("3. REGISTROS no DB reverse_eng_fichas para FV")
print("=" * 80)
import sqlite3, json
conn = sqlite3.connect('D:/Agente-cad-PYSIDE/project_data.vision')
c = conn.cursor()
c.execute("SELECT elemento_id, pavimento, status, confianca, updated_at FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' ORDER BY elemento_id")
rows = c.fetchall()
print(f"  Total: {len(rows)} registros")
for r in rows[:10]:
    print(f"  {r[0]:15s} pav={r[1] or '-':20s} status={r[2]:12s} conf={r[3]:.2f} updated={r[4]}")
if len(rows) > 10:
    print(f"  ... e mais {len(rows)-10} registros")

# Check for duplicates
c.execute("SELECT elemento_id, COUNT(*) as cnt FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' GROUP BY elemento_id HAVING cnt > 1")
dupes = c.fetchall()
if dupes:
    print(f"\n  DUPLICATAS ENCONTRADAS:")
    for d in dupes:
        print(f"    {d[0]}: {d[1]} registros!")

print()
print("=" * 80)
print("4. V306 especifico - dados no DB")
print("=" * 80)
c.execute("SELECT id, elemento_id, pavimento, status, confianca, updated_at FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' AND elemento_id='V306'")
for r in c.fetchall():
    print(f"  id={r[0]} elem={r[1]} pav={r[2]} status={r[3]} conf={r[4]} updated={r[5]}")
    
c.execute("SELECT campos_json FROM reverse_eng_fichas WHERE obra_name='Obra_TREINO_1' AND classe='FV' AND elemento_id='V306'")
row = c.fetchone()
if row:
    data = json.loads(row[0])
    sr = data.get('segments_rich', [])
    p = data.get('panels', [])
    print(f"  segments_rich: {len(sr)} items")
    print(f"  panels: {len(p)} items")
    print(f"  label_left: {data.get('label_left')}")
    print(f"  label_right: {data.get('label_right')}")
    print(f"  holes active: {[h.get('active') for h in data.get('holes',[])]}")
    print(f"  _confianca: {data.get('_confianca')}")
    print(f"  _er_meta.source: {data.get('_er_meta',{}).get('source')}")
    
    # Check if _fase4_ref has the real data
    ref = data.get('_fase4_ref', {})
    if ref:
        print(f"  _fase4_ref.segments_rich: {len(ref.get('segments_rich', []))} items")
        print(f"  _fase4_ref.label_left: {ref.get('label_left')}")

conn.close()
