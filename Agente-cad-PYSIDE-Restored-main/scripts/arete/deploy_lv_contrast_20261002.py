"""Guarded publication of the current LV highlight contrast adjustment."""
from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root = Path('/opt/cad-analyzer')
target = root/'portal/app/static/lv_ficha.js'
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
assert hashlib.sha256(target.read_bytes()).hexdigest() == '90080a7a6727e5295e400a9ce4ea1076b1da95eebb20742303b438e96b119c77', 'fonte mudou'
backup = Path('/root/lv_contrast_20261002')/str(int(time.time()))
backup.mkdir(parents=True)
shutil.copy2(target,backup/'lv_ficha.js')
shutil.copy2('/tmp/lv-contrast-20261002.js',target)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
