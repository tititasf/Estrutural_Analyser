"""Download code to an isolated directory; never replace the working repository."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from scripts.arete.jev_vps_identity_v9 import ssh

def main():
    out=Path(sys.argv[1]).resolve()
    manifest=json.loads((out/'VPS-MANIFEST.json').read_text(encoding='utf8'))
    code=r'''
import io,zipfile,pathlib,sys
r=pathlib.Path('/opt/cad-analyzer');buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
 for sub in ('src','portal','scripts'):
  for p in (r/sub).rglob('*.py'):
   if '__pycache__' not in p.parts: z.write(p,str(p.relative_to(r)))
 for p in r.glob('*.py'): z.write(p,p.name)
 for sub in ('config','configs'):
  if (r/sub).is_dir():
   for p in (r/sub).rglob('*'):
    if p.is_file() and p.suffix in ('.json','.yaml','.yml','.toml'): z.write(p,str(p.relative_to(r)))
sys.stdout.buffer.write(buf.getvalue())
'''
    data=ssh(code); dest=out/'vps_runtime';dest.mkdir(exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            target=(dest/name).resolve()
            if not target.is_relative_to(dest): raise ValueError('Unsafe archive path')
        z.extractall(dest)
    failures=[]
    for rel,h in manifest['files'].items():
        p=dest/rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=h['raw']: failures.append(rel)
    result={'zip_sha256':hashlib.sha256(data).hexdigest(),'archive_bytes':len(data),
            'manifest_files_verified':len(manifest['files']),'changed_during_capture':failures,
            'runtime':str(dest),'snapshot_consistent':not failures,'remote_writes':False}
    (out/'SNAPSHOT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))
    if failures: raise SystemExit(2)

if __name__=='__main__':main()
