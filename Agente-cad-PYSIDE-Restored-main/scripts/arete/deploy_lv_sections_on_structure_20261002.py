from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root=Path('/opt/cad-analyzer')
expected={'portal/app/static/lv_ficha.js':'e8a93f41eca9efd12a9b2741bd4a110a57670831cee2cd51abd9edd0a3ab63c1',
          'portal/app/lv_cut_map.py':'f48ff3784b5df95b28b500d026724c807d9eff22fb4cb21d68153d92a23643a2'}
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
for rel,digest in expected.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest, f'fonte mudou {rel}'
backup=Path('/root/lv_sections_on_structure_20261002')/str(int(time.time()))
for rel in expected:
    source=Path('/tmp/lv-sections-stage')/rel
    if rel.endswith('.py'): compile(source.read_text(encoding='utf8'),rel,'exec')
    saved=backup/rel; saved.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,saved); shutil.copy2(source,root/rel)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
