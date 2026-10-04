"""Publish only the numeric policy source/chunks; preserve all VPS-owned knowledge."""
from pathlib import Path
import base64
import hashlib
import json
import shlex
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REL = 'docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md'
remote = subprocess.run(['ssh', 'root@62.238.111.147', 'cat /opt/cad-analyzer/'+REL],
                        capture_output=True, check=True).stdout
local = (ROOT/REL).read_bytes()
assert local.replace(b'\r\n', b'\n').startswith(remote.replace(b'\r\n', b'\n')), 'remote source diverged; review first'
with sqlite3.connect(f'file:{(ROOT.parent/"KB-GLOBAL/kb_global.sqlite").as_posix()}?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute('SELECT * FROM chunks WHERE path LIKE ?', ('%/'+REL,))]
    assert rows and len({r['path'] for r in rows}) == 1
    meta = dict(db.execute('SELECT k,v FROM meta'))
    vectors = []
    for row in rows:
        row.pop('rowid')
        vector = db.execute('SELECT vec FROM vetores WHERE sha=? AND embedder=?',
                            (row['sha'], meta['embedder'])).fetchone()
        assert vector is not None
        vectors.append({'sha': row['sha'], 'vec': base64.b64encode(vector[0]).decode()})
payload = {'source': base64.b64encode(local).decode(), 'old_hash': hashlib.sha256(remote).hexdigest(),
           'rows': rows, 'vectors': vectors, 'meta': meta, 'rel': REL}
code = r'''
from pathlib import Path
import sqlite3,sys,json,hashlib,base64,time,shutil
p=json.load(sys.stdin);root=Path('/opt/cad-analyzer');source=root/p['rel']
assert hashlib.sha256(source.read_bytes()).hexdigest()==p['old_hash'],'source changed during review'
db=sqlite3.connect(root/'KB-GLOBAL/kb_global.sqlite',timeout=30)
db.row_factory=sqlite3.Row
meta=dict(db.execute('SELECT k,v FROM meta'))
assert all(meta[k]==p['meta'][k] for k in ('embedder','dim','esquema')),'incompatible vector/schema'
path=p['rows'][0]['path']
existing=list(db.execute('SELECT DISTINCT path FROM chunks WHERE path LIKE ?',('%/'+p['rel'],)))
assert len(existing)<=1 and (not existing or existing[0][0]==path),'source path mismatch'
backup=root/'deploy_backups'/('numeric_knowledge_'+str(int(time.time())))
backup.mkdir(parents=True)
shutil.copy2(source,backup/'APRESENTACAO-NUMERICA.md')
with sqlite3.connect(backup/'kb_global.sqlite') as saved:db.backup(saved)
def untouched():
    return [tuple(r) for r in db.execute('SELECT * FROM chunks WHERE path != ? ORDER BY id',(path,))]
before=untouched()
with db:
    db.execute('DELETE FROM chunks WHERE path=?',(path,))
    for row in p['rows']:
        fields=list(row)
        db.execute('INSERT INTO chunks ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',list(row.values()))
    for v in p['vectors']:
        raw=base64.b64decode(v['vec'])
        assert len(raw)==int(meta['dim'])*4
        old=db.execute('SELECT vec FROM vetores WHERE sha=? AND embedder=?',(v['sha'],meta['embedder'])).fetchone()
        assert old is None or old[0]==raw,'vector conflict'
        db.execute('INSERT OR IGNORE INTO vetores VALUES(?,?,?)',(v['sha'],meta['embedder'],raw))
    db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    count=db.execute('SELECT count(*) FROM chunks').fetchone()[0]
    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('n_chunks',str(count)))
    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('numeric_policy_updated_at',str(int(time.time()))))
    assert untouched()==before,'unrelated knowledge changed'
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
source.write_bytes(base64.b64decode(p['source']))
print(json.dumps({'backup':str(backup),'updated_chunks':len(p['rows']),'preserved_chunks':len(before),'integrity':'ok'}))
db.close()
'''
result = subprocess.run(['ssh','root@62.238.111.147','/opt/cad-analyzer/.venv/bin/python -c '+shlex.quote(code)],
                        input=json.dumps(payload).encode(), capture_output=True)
print(result.stdout.decode())
if result.returncode:
    raise RuntimeError(result.stderr.decode())
