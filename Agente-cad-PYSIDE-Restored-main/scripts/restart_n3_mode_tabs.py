import sqlite3
import subprocess

with sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro', uri=True) as conn:
    statuses = conn.execute('SELECT status, count(*) FROM portal_jobs GROUP BY status').fetchall()
    print(statuses, flush=True)
    assert all(status in ('concluido', 'falhou', 'cancelado') for status, count in statuses), 'Jobs ativos: restart impedido'
subprocess.run(['systemctl', 'restart', 'cad-portal'], check=True)
subprocess.run(['systemctl', 'is-active', 'cad-portal'], check=True)
