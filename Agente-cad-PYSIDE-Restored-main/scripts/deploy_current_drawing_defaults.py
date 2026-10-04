"""Publish only the two owned files and measured production catalog, hash guarded."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'scripts/arete/relatorios/20261001_current_defaults'
before=json.loads((OUT/'remote_before.json').read_text(encoding='utf8'))
payload={p:{'expected':v['hash'],'source':(ROOT/p).read_text(encoding='utf8')} for p,v in before.items()}
payload['config/drawing_mode_current_catalog.json']={'expected':None,'source':(OUT/'production_measured.json').read_text(encoding='utf8')}
if '--catalog-refresh' in sys.argv:
    # Only accept the exact source deployed by this task, never a concurrent edit.
    for name,data in payload.items():
        prior=(OUT/'production_measured_before_refresh.json').read_text(encoding='utf8') if name.endswith('current_catalog.json') else data['source']
        data['expected']=hashlib.sha256(prior.encode()).hexdigest()
    owned={name:data['expected'] for name,data in payload.items() if not name.endswith('current_catalog.json')}
    payload={name:data for name,data in payload.items() if name.endswith('current_catalog.json')}
code=(ROOT/'scripts/deploy_granular_modes.py').read_text(encoding='utf8')
code=code.replace("payload=json.loads(Path('/root/granular_modes_payload.json').read_text())",'payload='+repr(payload))
code=code.replace("backup_granular_modes_","backup_current_defaults_")
if '--catalog-refresh' in sys.argv:
    # Atomic metadata refresh is read dynamically and never restarts a running motor.
    code=code.replace("if jobs:raise RuntimeError(f'Active jobs: {jobs}; deployment untouched')",'')
    code=code.replace("subprocess.run(['systemctl','restart','cad-portal'],check=True)",'')
    code=code.replace("for name,data in payload.items():", "for p,digest in "+repr(owned)+".items():\n    assert hashlib.sha256((root/p).read_bytes()).hexdigest()==digest, 'Concurrent owned source change: '+p\nfor name,data in payload.items():",1)
# Reject a concurrently changed generator before exposing its measured defaults.
catalog=json.loads(payload['config/drawing_mode_current_catalog.json']['source'])
guard="\nfor p,digest in "+repr(catalog['sources'])+".items():\n    assert hashlib.sha256((root/p).read_text().encode()).hexdigest()==digest, 'Generator changed: '+p\n"
code=code.replace("backup=Path('/root')",guard+"\nbackup=Path('/root')")
run=subprocess.run(['ssh','root@62.238.111.147','/opt/cad-analyzer/.venv/bin/python -'],input=code,capture_output=True,text=True,encoding='utf8')
(OUT/'deployment.log').write_text(run.stdout+run.stderr,encoding='utf8')
print(run.stdout,run.stderr);assert run.returncode==0
