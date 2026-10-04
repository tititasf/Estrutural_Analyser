import json, sqlite3, os
from pathlib import Path
c=sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro',uri=True)
c.row_factory=sqlite3.Row
print('JOBS',json.dumps([dict(r) for r in c.execute('select * from portal_jobs order by rowid desc limit 3')],default=str))
print('TABLES',[r[0] for r in c.execute("select name from sqlite_master where type='table' and (name like '%job%' or name like '%etapa%')")])
for p in Path('/opt/cad-analyzer/portal/logs').glob('job_62433114*'):
 lines=p.read_text(errors='replace').splitlines()
 print('LOG',str(p),'\n'.join(lines[-4:])[:3000])
root=Path('/opt/cad-analyzer')
for p in root.glob('portal_runtime/drawing_*/NOVA/PL/*.json'):
 print(str(p),p.read_text()[:1200])

print('META', [dict(r) for r in c.execute('select * from portal_job_meta where job_id=?',('62433114-c762-4d8d-a9b8-b7e15714b286',))])

root=Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/production_sa/13_PAV')
for run in sorted(root.iterdir())[-2:]:
 print('RUN',run.name)
 for q in run.glob('*.json'):print(q.name,q.read_text()[:1200])
 print('N3',len(list(run.glob('n3/pil/**/*.dxf'))))
print('LOGHEAD',Path('/opt/cad-analyzer/portal/logs/job_62433114-c762-4d8d-a9b8-b7e15714b286.log').read_text(errors='replace')[:4500])
