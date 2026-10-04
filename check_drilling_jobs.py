import sqlite3
c=sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro',uri=True)
print(c.execute('select status,count(*) from portal_jobs group by status').fetchall())
