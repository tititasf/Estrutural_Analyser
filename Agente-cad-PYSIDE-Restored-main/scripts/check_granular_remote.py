"""Read-only source snapshot for guarded deployment amid concurrent agents."""
import json, subprocess, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'scripts/arete/relatorios/20261001_config_granular'
manifest=json.loads((OUT/'before_hashes.json').read_text())
extra=['portal/app/routers/drawing_mode_config_routes.py','portal/app/static/drawing_mode_config.css','src/core/n5_assembler.py','scripts/arete/lv_n3_cut_draw.py','src/ui/widgets/pre_validation_dialog.py']
files=list(manifest)+extra
remote_code='''import json, pathlib, hashlib, sqlite3
root=pathlib.Path('/opt/cad-analyzer')
c=sqlite3.connect(root/'portal_data.db')
print(json.dumps({'jobs':c.execute("select id,status from portal_jobs where status in ('na_fila','executando')").fetchall(),'files':{p:(root/p).read_text() for p in FILES},'hashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FILES}}))
'''.replace('FILES',repr(files))
result=subprocess.run(['ssh','-o','BatchMode=yes','root@62.238.111.147','/opt/cad-analyzer/.venv/bin/python -'],input=remote_code,text=True,capture_output=True,encoding='utf-8')
if result.returncode: raise RuntimeError(result.stderr)
data=json.loads(result.stdout)
dest=OUT/'remote_before';dest.mkdir(exist_ok=True)
for file,source in data['files'].items():
    path=dest/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8',newline='')
    remote_hash=hashlib.sha256(source.encode()).hexdigest()
    local_hash=hashlib.sha256((ROOT/file).read_bytes()).hexdigest()
    print(file, 'local_same' if remote_hash==local_hash else 'changed', 'remote_baseline' if remote_hash==manifest.get(file) else 'remote_modified')
(OUT/'remote_snapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACTIVE_JOBS',data['jobs'])
