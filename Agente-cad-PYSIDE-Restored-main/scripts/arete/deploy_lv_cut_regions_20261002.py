"""Guarded publication of this session's single source change."""
from pathlib import Path
import hashlib
import shutil
import sqlite3
import subprocess
import time

root=Path('/opt/cad-analyzer')
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
target=root/'src/core/lv_cut_inventory.py'
assert hashlib.sha256(target.read_bytes()).hexdigest()=='91a910e8a19d7369e1ac64a908d6d36f1bea9c153e55bbccdb3a689f77bb547e', 'fonte remota mudou'
source=Path('/tmp/lv_cut_inventory_region_20261002.py')
compile(source.read_text(encoding='utf8'),str(source),'exec')
backup=Path('/root/lv_cut_regions_20261002')/str(int(time.time()))
backup.mkdir(parents=True)
shutil.copy2(target,backup/target.name)
shutil.copy2(source,target)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',target,hashlib.sha256(target.read_bytes()).hexdigest(),'BACKUP',backup)
