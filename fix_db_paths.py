import sqlite3, shutil
from datetime import datetime

db = 'D:/Agente-cad-PYSIDE/project_data.vision'

bak = db + '.bak_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2(db, bak)
print(f'Backup: {bak}')

con = sqlite3.connect(db)
cur = con.cursor()

MAPS = [
    ('projects',          'dxf_path',
        'C:\\Users\\Ryzen\\Desktop\\AIOS-DIANA\\Agente-cad-PYSIDE\\',
        'D:\\Agente-cad-PYSIDE\\'),
    ('projects',          'dxf_path',
        'C:/Users/Ryzen/Desktop/Treinos-Projetos-Dxf/',
        'D:\\Agente-cad-PYSIDE\\DADOS-OBRAS\\OBRA-TESTE1\\Fase-2_Triagem\\Estruturais_Pavimentos_Limpos\\'),
    ('project_documents', 'file_path',
        'C:\\Users\\Ryzen\\Desktop\\GITHUB\\Agente-cad-PYSIDE\\',
        'D:\\Agente-cad-PYSIDE\\'),
    ('project_documents', 'file_path',
        'C:\\Users\\Ryzen\\Desktop\\AIOS-DIANA\\Agente-cad-PYSIDE\\',
        'D:\\Agente-cad-PYSIDE\\'),
    ('project_documents', 'source_dxf_path',
        'C:\\Users\\Ryzen\\Desktop\\GITHUB\\Agente-cad-PYSIDE\\',
        'D:\\Agente-cad-PYSIDE\\'),
]

for tbl, col, old, new in MAPS:
    cur.execute(
        f"UPDATE {tbl} SET {col} = REPLACE({col}, ?, ?) WHERE {col} LIKE '%Ryzen%'",
        (old, new)
    )
    print(f'  {tbl}.{col}: {cur.rowcount} linhas atualizadas')

con.commit()
print()
for tbl, col in [
    ('projects',          'dxf_path'),
    ('project_documents', 'file_path'),
    ('project_documents', 'source_dxf_path'),
]:
    cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {col} LIKE '%Ryzen%'")
    print(f'  Ryzen restantes em {tbl}.{col}: {cur.fetchone()[0]}')

print()
cur.execute("SELECT dxf_path FROM projects LIMIT 3")
for r in cur.fetchall():
    print(' ', r[0])

con.close()
print('\nDONE')
