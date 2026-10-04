import sqlite3
import subprocess
import urllib.request
with sqlite3.connect('/opt/cad-analyzer/portal_data.db') as connection:
    jobs = connection.execute("select id,status from portal_jobs where status in ('na_fila','executando')").fetchall()
    if jobs:
        raise RuntimeError(f'Active jobs: {jobs}')
subprocess.run(['systemctl', 'restart', 'cad-portal'], check=True)
subprocess.run(['systemctl', 'is-active', 'cad-portal'], check=True)
