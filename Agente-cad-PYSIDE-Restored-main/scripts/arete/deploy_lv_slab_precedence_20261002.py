from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root=Path('/opt/cad-analyzer')
files={'main.py':'ec64eea1b100bd6766773373c9deec35f84906eed062797ec8b0a483476664ef','portal/app/lv_cut_map.py':'dd8003f1d47100289d4135be5275ade0f64dadfd0a6a87602d3f98b1cd905ec8'}
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
for rel,expected in files.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected, 'fonte mudou: '+rel
    compile((Path('/tmp/lv-sections-stage')/rel).read_text(encoding='utf8'),rel,'exec')
backup=Path('/root/lv_slab_precedence_20261002')/str(int(time.time()))
for rel in files:
    dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,dest);shutil.copy2(Path('/tmp/lv-sections-stage')/rel,root/rel)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
