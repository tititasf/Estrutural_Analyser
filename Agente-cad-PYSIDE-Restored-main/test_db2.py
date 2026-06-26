import sys
sys.path.append('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main')

from src.core.database import _db_query

print('DB Query test...')
rows = _db_query("SELECT name FROM sqlite_master WHERE type='table';")
print('Tables:', [r[0] for r in rows] if rows else [])

if rows and any(r[0] == 'reverse_eng_fichas' for r in rows):
    rows_f = _db_query("SELECT obra_name, pavimento, classe, elemento_id, campos_json FROM reverse_eng_fichas LIMIT 5")
    print('Fichas:', rows_f)
