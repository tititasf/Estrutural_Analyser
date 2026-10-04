from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root=Path('/opt/cad-analyzer')
files={'portal/app/lv_cut_map.py':'40eb93c82ed5a036d20feb8248afefa30dc72366583d1c77da85cc99fac8131e','portal/app/lv_ficha.py':'5579520e71ed1d0206b44a872dcb9e8e7dab23e096d323b07528769c1f7540dd'}
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
for rel,expected in files.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected, 'fonte mudou: '+rel
    compile((Path('/tmp/lv-sections-stage')/rel).read_text(encoding='utf8'),rel,'exec')
backup=Path('/root/lv_original_dimensions_20261002')/str(int(time.time()))
for rel in files:
    dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,dest);shutil.copy2(Path('/tmp/lv-sections-stage')/rel,root/rel)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
