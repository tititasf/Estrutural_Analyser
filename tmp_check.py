import sqlite3, sys, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
conn = sqlite3.connect('project_data.vision')

# TEXT dados_json
rows = conn.execute("SELECT dados_json FROM dxf_entidades WHERE tipo='TEXT' LIMIT 3").fetchall()
for r in rows:
    d = json.loads(r[0] or '{}')
    print('TEXT dados_json:', d)

# DXF paths
projs = conn.execute("SELECT dxf_path FROM projects WHERE work_name='Obra_TREINO_1' AND dxf_path IS NOT NULL LIMIT 5").fetchall()
print()
for p in projs:
    path = p[0] or ''
    # normalize
    local = path.replace('C:\\Users\\Ryzen\\Desktop\\AIOS-DIANA\\Agente-cad-PYSIDE', 'D:')
    local = local.replace('\\', '/')
    print(f'  exists={os.path.exists(local)}  path=...{local[-60:]}')

# DXF exists check with local DADOS-OBRAS
dxf_dir = os.path.join('DADOS-OBRAS', 'Obra_TREINO_1', 'Fase-2_Triagem', 'Estruturais_Pavimentos_Limpos')
if os.path.exists(dxf_dir):
    files = os.listdir(dxf_dir)
    print(f'\nLocal DXFs found: {files[:5]}')
else:
    print(f'\nDXF dir not found: {dxf_dir}')

conn.close()
