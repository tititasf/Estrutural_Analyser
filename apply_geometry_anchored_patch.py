import json,sys,shutil,time
from pathlib import Path
root=Path('/opt/cad-analyzer')
planned=[];conflicts=[]
for patch in json.loads(Path('/tmp/anchored.json').read_text()):
 p=root/patch['file'];raw=p.read_bytes();s=raw.decode('utf-8').replace('\r\n','\n');n=0
 for op in patch['operations']:
  if s.count(op['old'])==1:s=s.replace(op['old'],op['new']);n+=1
  elif s.count(op['new'])==1:pass
  else:conflicts.append((patch['file'],op['old'][:120]))
 planned.append((p,s,raw,n))
if conflicts:
 print('conflicts:',conflicts);raise SystemExit(1)
print('validated:',[(str(p.relative_to(root)),n) for p,s,raw,n in planned])
if '--apply' in sys.argv:
 backup=root/'backups'/('geometry-editor-'+time.strftime('%Y%m%d-%H%M%S'))
 for p,s,raw,n in planned:
  if not n:continue
  b=backup/p.relative_to(root);b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(raw)
  p.write_bytes(s.encode('utf-8'))
 print('backup:',backup)
