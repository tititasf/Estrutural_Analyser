from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root=Path('/opt/cad-analyzer')
expected={'portal/app/static/lv_ficha.js':'89a73177c649f2c70f24c05148fbeef16f7ddb8f0469f844c12075b82d9e8237',
          'portal/app/lv_ficha.py':'ed74b2fde8dcc39bd77ed941de18a861268429bf338bc587c3c6774661dc073a'}
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
for rel,digest in expected.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest, f'fonte mudou {rel}'
backup=Path('/root/lv_cut_tabs_20261002')/str(int(time.time()))
for rel in expected:
    source=Path('/tmp/lv-sections-stage')/rel
    if rel.endswith('.py'): compile(source.read_text(encoding='utf8'),rel,'exec')
    saved=backup/rel; saved.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,saved); shutil.copy2(source,root/rel)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
