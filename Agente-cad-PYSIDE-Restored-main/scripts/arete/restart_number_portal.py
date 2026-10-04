import subprocess, shlex
code = '''import sqlite3, subprocess
with sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro', uri=True) as db:
    active=db.execute("SELECT id,status FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall()
    print('Active jobs:',active)
    assert not active,'Cannot restart while jobs are active'
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
'''
subprocess.run(['ssh','root@62.238.111.147','/opt/cad-analyzer/.venv/bin/python -c '+shlex.quote(code)],check=True)
