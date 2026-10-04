import sqlite3,json
from pathlib import Path
c=sqlite3.connect(Path('/opt/cad-analyzer/portal_data.db').as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row
print(json.dumps([dict(r) for r in c.execute('select * from portal_jobs order by rowid desc limit 3')],default=str))
