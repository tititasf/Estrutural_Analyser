import sqlite3
from pathlib import Path
c=sqlite3.connect('/opt/cad-analyzer/portal_data.db')
rows=c.execute("select id,status from portal_jobs where status in ('na_fila','executando')").fetchall()
print('active jobs:',rows)
if rows: raise SystemExit(2)
from portal.app.main import create_app
a=create_app()
print('app factory:', type(a).__name__)
from jinja2 import Environment
Environment().parse(Path('portal/app/templates/obra_detalhe.html').read_text())
print('template syntax: OK')
