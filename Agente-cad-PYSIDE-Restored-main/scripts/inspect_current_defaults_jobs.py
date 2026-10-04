import subprocess
code="""import sqlite3,json
c=sqlite3.connect('/opt/cad-analyzer/portal_data.db');c.row_factory=sqlite3.Row
rows=[dict(r) for r in c.execute("select * from portal_jobs where status in ('na_fila','executando')")]
print(json.dumps([{k:v for k,v in r.items() if k not in ('payload_json','result_json')} for r in rows],ensure_ascii=False,default=str))
"""
run=subprocess.run(['ssh','root@62.238.111.147','/opt/cad-analyzer/.venv/bin/python -'],input=code,text=True,capture_output=True,encoding='utf8')
print(run.stdout,run.stderr)
