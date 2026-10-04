"""Publicação com fila vazia e proteção contra alterações concorrentes."""
from pathlib import Path
import hashlib
import shutil
import sqlite3
import subprocess
import time

root = Path('/opt/cad-analyzer')
db = sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro', uri=True)
jobs = db.execute("SELECT id,status FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall()
if jobs:
    print('WAIT', jobs); raise SystemExit(2)
files = [
    ('portal/app/lv_ficha.py', '/tmp/lv_dedupe_ficha.py', '150dd27e372e463eca0b6548194e199583a287a782b93a95c70c6989a73c07f6'),
    ('src/core/lv_n3_cut_contract.py', '/tmp/lv_dedupe_contract.py', '3c26509a6e969ea178c2d6fa2911ba0d40685dd8fc7165aa483e213f5cafe40e'),
    ('src/core/lv_cut_equivalence.py', '/tmp/lv_dedupe_equivalence.py', None),
]
for rel, staged, expected in files:
    path = root/rel
    assert not path.exists() if expected is None else hashlib.sha256(path.read_bytes()).hexdigest()==expected, rel
backup = Path('/root/lv_cut_dedupe_20261001')/str(int(time.time()))
backup.mkdir(parents=True)
for rel, staged, expected in files:
    path = root/rel
    if path.exists(): shutil.copy2(path, backup/path.name)
    shutil.copy2(staged, path)
    print('PUBLISHED', rel)
subprocess.run(['systemctl', 'restart', 'cad-portal'], check=True)
subprocess.run(['systemctl', 'is-active', 'cad-portal'], check=True)
print('BACKUP', backup)
