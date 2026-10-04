from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root=Path('/opt/cad-analyzer')
rel='portal/app/lv_cut_map.py'
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
assert hashlib.sha256((root/rel).read_bytes()).hexdigest()=='705f469c449954783a0c1fbcb71b7fce8f84f5b357f9c98f872a65a14add31a4', 'fonte mudou'
source=Path('/tmp/lv-sections-stage')/rel
compile(source.read_text(encoding='utf8'),rel,'exec')
backup=Path('/root/lv_wall_dimensions_20261002')/str(int(time.time()))/rel
backup.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(root/rel,backup); shutil.copy2(source,root/rel)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
