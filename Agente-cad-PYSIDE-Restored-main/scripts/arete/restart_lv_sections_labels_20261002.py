import sqlite3, subprocess
with sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro', uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
subprocess.run(['systemctl','restart','cad-portal'], check=True)
subprocess.run(['systemctl','is-active','cad-portal'], check=True)
