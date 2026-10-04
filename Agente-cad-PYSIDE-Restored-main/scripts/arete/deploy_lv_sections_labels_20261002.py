from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root = Path('/opt/cad-analyzer')
rel = 'portal/app/static/lv_ficha.js'
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro', uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
assert hashlib.sha256((root/rel).read_bytes()).hexdigest() == 'e762cbac6b3838161ec1acdc9bab1771ebf2382406f40cd255d9ccf64d5992ab', 'fonte mudou'
backup = Path('/root/lv_sections_labels_20261002')/str(int(time.time()))/rel
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(root/rel, backup)
shutil.copy2(Path('/tmp/lv-sections-stage')/rel, root/rel)
print('PUBLISHED', backup)
