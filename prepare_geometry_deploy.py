from pathlib import Path
import difflib, json, tarfile
root=Path(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main')
base=Path(r'D:\Agente-cad-PYSIDE\geometry-review')
patch=''
changed=[]
for old in base.rglob('*'):
 if not old.is_file(): continue
 rel=old.relative_to(base).as_posix()
 new=root/rel
 if not new.is_file(): continue
 delta=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),new.read_text(encoding='utf-8').splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
 if delta: patch+=delta;changed.append(rel)
(base/'geometry.patch').write_text(patch,encoding='utf-8',newline='\n')
files=['portal/app/item_geometry.py','portal/app/routers/item_geometry_routes.py','portal/app/static/item_geometry.js']
with tarfile.open(base/'geometry-new.tar','w') as t:
 for f in files:t.add(root/f,arcname=f)
print(json.dumps({'patched':changed,'new':files},indent=2))
