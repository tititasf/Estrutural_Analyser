"""Guarded deployment for frame upload and categorized profile UI."""
from pathlib import Path
import hashlib
import shutil
import sqlite3
import subprocess

root = Path('/opt/cad-analyzer')
stage = Path('/root/drawing_frame_stage')
expected = {
    'portal/app/routers/drawing_mode_config_routes.py': 'dcf1ca2a06e0d9498942c4fef282f6d55b6cbe2a6ef0031be8c067a6402d82d6',
    'portal/app/static/drawing_mode_config.js': 'c00c7f2bfb49388c92adcfe2b4304477f0e0db776ce2e41a4e2edc106d2c11b5',
    'portal/app/static/drawing_mode_config.css': '32b89f121738b6706f5dfe8feaf955b95d20cf030311981782ed84c6c8710d68',
    'portal/app/drawing_frame.py': None,
}
with sqlite3.connect(root / 'portal_data.db') as conn:
    jobs = conn.execute("select id,status from portal_jobs where status in ('na_fila','executando')").fetchall()
    if jobs:
        raise RuntimeError(f'Active jobs; no files changed: {jobs}')
for name, digest in expected.items():
    target = root / name
    if digest is None:
        assert not target.exists(), f'New file already exists: {name}'
    else:
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, f'Concurrent change: {name}'
    if name.endswith('.py'):
        compile((stage / target.name).read_text(encoding='utf8'), name, 'exec')
backup = Path('/root/backup_drawing_frame_20261001')
backup.mkdir(exist_ok=False)
for name in expected:
    target = root / name
    if target.exists():
        shutil.copy2(target, backup / target.name)
    shutil.copy2(stage / target.name, target)
    subprocess.run(['chown', 'cadapp:cadapp', str(target)], check=True)
subprocess.run(['systemctl', 'restart', 'cad-portal'], check=True)
subprocess.run(['systemctl', 'is-active', 'cad-portal'], check=True)
print('Frame settings deployed')
