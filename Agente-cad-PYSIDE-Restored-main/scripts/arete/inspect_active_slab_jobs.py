import sqlite3,json
with sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 print(json.dumps([dict(r) for r in db.execute("select * from portal_jobs where status in ('executando','na_fila')")],default=str))
