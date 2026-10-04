from pathlib import Path
import hashlib
import shutil
import sqlite3
import subprocess
import time

root = Path('/opt/cad-analyzer')
db = sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro', uri=True)
assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
files = [
    ('portal/app/lv_n3_cuts.py', '/tmp/dynamic_lv_cuts.py', '628672437c1e8d1a3aeaa1fe6f10d1931a676a6a52dd3dd4ced013f6c08f740e'),
    ('portal/app/pipeline_runner.py', '/tmp/dynamic_lv_pipeline.py', '0fc475e8ce1387009c1e61efde4a4060a06745b9d6c6d6a412213ae0fb1fd3b1'),
]
for rel, source, expected in files:
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest() == expected, rel
backup = Path('/root/lv_cut_dynamic_20261001')/str(int(time.time()))
backup.mkdir(parents=True)
for rel, source, expected in files:
    shutil.copy2(root/rel, backup/Path(rel).name)
    shutil.copy2(source, root/rel)
    print('PUBLISHED', rel)
subprocess.run(['systemctl','restart','cad-portal'], check=True)
subprocess.run(['systemctl','is-active','cad-portal'], check=True)
print('BACKUP', backup)
