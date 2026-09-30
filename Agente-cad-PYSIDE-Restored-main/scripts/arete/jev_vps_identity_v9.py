"""Read-only VPS identity probe; saves CAD into a new isolated experiment folder."""
from __future__ import annotations
import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REMOTE = r'''
import pathlib,hashlib,json,sqlite3,sys,base64
r=pathlib.Path('/opt/cad-analyzer')
def hashes(p):
 b=p.read_bytes()
 return {'raw':hashlib.sha256(b).hexdigest(),'lf':hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest()}
files={}
for sub in ('src','portal','scripts/arete'):
 for p in sorted((r/sub).rglob('*.py')):
  if '__pycache__' not in p.parts: files[str(p.relative_to(r))]=hashes(p)
db=r/'project_data.vision'
c=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
c.row_factory=sqlite3.Row
projects=[]
for row in c.execute("select * from projects where id in (?,?)",('dd238e47-1dc6-4f63-a760-4e7ce19a7386','f28c3897-c8df-4bb9-a187-cb090f2c7ec7')):
 d=dict(row); p=pathlib.Path(d.get('dxf_path') or '')
 projects.append({'id':d['id'],'name':d.get('name'),'path':str(p),'exists':p.is_file(),'source_sha256':hashes(p)['raw'] if p.is_file() else None})
beams=[]
for row in c.execute("select name,data_json from beams where project_id=? and name in ('V409','V420')",('f28c3897-c8df-4bb9-a187-cb090f2c7ec7',)):
 d=dict(row); d['data_json_sha256']=hashlib.sha256((d['data_json'] or '').encode()).hexdigest();beams.append(d)
c.close()
print(json.dumps({'root':str(r),'python':sys.version,'files':files,'projects':projects,'persisted_beams':beams}))
'''

def ssh(code: str) -> bytes:
    p = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',
        'root@62.238.111.147','cd /opt/cad-analyzer && .venv/bin/python -'],
        input=code.encode(),capture_output=True,timeout=150)
    if p.returncode:
        raise RuntimeError('Read-only SSH probe failed: '+p.stderr.decode(errors='replace')[:1200])
    return p.stdout

def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=REPO/'scripts/arete/relatorios'/('jev_vps_identity_v9_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    remote=json.loads(ssh(REMOTE))
    (out/'VPS-MANIFEST.json').write_text(json.dumps(remote,indent=2,ensure_ascii=False),encoding='utf8')
    same=[]; formatting=[]; changed=[]; missing=[]; local={}
    for rel,h in remote['files'].items():
        p=REPO/rel
        if not p.is_file(): missing.append(rel);continue
        b=p.read_bytes(); local[rel]={'raw':hashlib.sha256(b).hexdigest(),'lf':hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest()}
        if local[rel]['raw']==h['raw']: same.append(rel)
        elif local[rel]['lf']==h['lf']: formatting.append(rel)
        else: changed.append(rel)
    (out/'LOCAL-MANIFEST.json').write_text(json.dumps(local,indent=2),encoding='utf8')
    source=next(p for p in remote['projects'] if p['id']=='f28c3897-c8df-4bb9-a187-cb090f2c7ec7')
    if source['exists']:
        code='import pathlib,sys\nsys.stdout.buffer.write(pathlib.Path('+repr(source['path'])+').read_bytes())\n'
        b=ssh(code)
        if hashlib.sha256(b).hexdigest()!=source['source_sha256']: raise RuntimeError('Source changed during copy')
        (out/'source').mkdir();(out/'source/14_PAV_VPS.dxf').write_bytes(b)
    result={'captured_utc':stamp,'same_raw_count':len(same),'line_endings_only_count':len(formatting),
        'different_count':len(changed),'different':changed,'missing_local':missing,
        'projects':remote['projects'],'source_copied':source['exists'],
        'code_parity':not changed and not missing,'db_read_only':True,'remote_writes':False,
        'persisted_snapshot_is_current_run_proof':False}
    (out/'COMPARISON.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({'out':str(out),**result},indent=2,ensure_ascii=False))

if __name__=='__main__': main()
