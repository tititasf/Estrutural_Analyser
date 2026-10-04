"""Run on VPS with reviewed payload, hash guards and no active jobs."""
import hashlib,json,os,shutil,sqlite3,subprocess,tempfile
from datetime import datetime
from pathlib import Path
root=Path('/opt/cad-analyzer')
payload=json.loads(Path('/root/granular_modes_payload.json').read_text())
with sqlite3.connect(root/'portal_data.db') as c:
    jobs=c.execute("select id,status from portal_jobs where status in ('na_fila','executando')").fetchall()
if jobs:raise RuntimeError(f'Active jobs: {jobs}; deployment untouched')
for name,data in payload.items():
    path=root/name
    current=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    assert current==data['expected'],f'Concurrent source change: {name}; deployment untouched'
    if name.endswith('.py'):compile(data['source'],name,'exec')
backup=Path('/root')/('backup_granular_modes_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(exist_ok=False)
for name,data in payload.items():
    path=root/name
    if path.exists():
        saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,saved)
    fd,temporary=tempfile.mkstemp(dir=path.parent,prefix='.granular-')
    with os.fdopen(fd,'w',encoding='utf8',newline='') as f:f.write(data['source'])
    subprocess.run(['chown','cadapp:cadapp',temporary],check=True)
    os.chmod(temporary,0o644);os.replace(temporary,path)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print(json.dumps({'files':len(payload),'backup':str(backup),'status':'deployed'}))
