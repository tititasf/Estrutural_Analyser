from pathlib import Path
import hashlib
import sqlite3
import sys
root=Path('/opt/cad-analyzer')
db=sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True)
jobs=db.execute("SELECT id,status FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall()
print('active_jobs',jobs)
if jobs: sys.exit(2)
for path in ('portal/app/lv_ficha.py','portal/app/static/lv_ficha.js','portal/app/pipeline_runner.py'):
    print(path,hashlib.sha256((root/path).read_bytes()).hexdigest())
