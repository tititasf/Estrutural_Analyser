import json,sqlite3
from pathlib import Path
c=sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
print('JOB',dict(c.execute('select * from portal_jobs where id=?',('62433114-c762-4d8d-a9b8-b7e15714b286',)).fetchone()))
r=Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/production_sa/13_PAV')
run=sorted(r.iterdir())[-1];print('RUN',run)
p=run/'production_manifest.json';j=json.loads(p.read_text());print('N3_SUMMARY',{k:v for k,v in j.get('n3',{}).items() if k.startswith('pl') or k.startswith('pil') or k=='visual_mode'})
print('PLKEYS',j.get('n3',{}).keys());print('ROOTFILES',[p.name for p in run.iterdir()]);print('CACHELATEST',sorted([(p.stat().st_mtime,p.name) for p in Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n3_modes/NOVA/pilares/para').glob('*.dxf')])[-2:])
