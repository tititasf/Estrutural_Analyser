from pathlib import Path
import sys,json
import sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path('../DADOS-OBRAS/Obra_TREINO_1')
s=ler_estado_pavimento(p,'13_PAV')
print('STATE',s.keys())
db=sqlite3.connect(Path(s['db_path']).resolve().as_uri()+'?mode=ro',uri=True)
print('BEAMS SCHEMA',db.execute('PRAGMA table_info(beams)').fetchall())
for row in db.execute('SELECT data_json FROM beams'):
    b=json.loads(row[0])
    if b.get('name') in ('V301','V306'):
        print('BEAM DATA',b['name'],b.keys())
        print(json.dumps(b.get('lv_generation_contracts'),ensure_ascii=False,indent=2)[:10000])
for b in s.get('beams',[]):
    if b.get('name') not in ('V301','V306'):continue
    print('BEAM',b['name'],b.keys())
    print(json.dumps(b.get('lv_generation_contracts'),ensure_ascii=False,indent=2)[:14000])
