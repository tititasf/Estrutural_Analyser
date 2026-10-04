"""Publish only reviewed portal files, refusing concurrent changes/jobs."""
from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root = Path('/opt/cad-analyzer')
hashes = {'portal/app/lv_ficha.py':'6260c93fa6a62180be9093aa92ad285703b7fad1b218d0a4ac7ff6e197c9d2b5',
          'portal/app/static/lv_ficha.js':'240254cac04dc515ce480f2d28b0e17d9f0d5f3123037830abbc23d79a94b73a'}
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
for rel, digest in hashes.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest() == digest, f'fonte mudou: {rel}'
assert not (root/'portal/app/lv_cut_map.py').exists(), 'módulo já existe'
backup = Path('/root/lv_cut_map_20261002')/str(int(time.time()))
for rel in [*hashes, 'portal/app/lv_cut_map.py']:
    source = Path('/tmp/lv-cut-map-stage')/rel
    if rel.endswith('.py'): compile(source.read_text(encoding='utf8'),rel,'exec')
    target = root/rel
    if target.exists():
        saved = backup/rel
        saved.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(target,saved)
    shutil.copy2(source,target)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
