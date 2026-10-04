import os,json,hashlib,tempfile,shutil
from pathlib import Path
r=Path('/opt/cad-analyzer');target=r/'config/drawing_mode_current_catalog.json';source=Path('/tmp/nova_current_measure_20261003/measured.json')
assert hashlib.sha256(target.read_bytes()).hexdigest()=='c3cde6cbd8f096c5805fc86d58a55bc3b61609639a6c548c58da7f2518f87d02'
catalog=json.loads(source.read_text())
assert len(catalog['modes'])==5
assert all(hashlib.sha256((r/name).read_text().encode()).hexdigest()==sha for name,sha in catalog['sources'].items())
profile=r/'portal_runtime/drawing_mode_settings.json';before=hashlib.sha256(profile.read_bytes()).hexdigest()
backup=Path('/root/nova_catalog_before_20261003_2048.json');assert not backup.exists();shutil.copy2(target,backup)
fd,tmp=tempfile.mkstemp(dir=target.parent,prefix='.catalog-')
with os.fdopen(fd,'w') as out:json.dump(catalog,out,ensure_ascii=False,indent=2)
os.chown(tmp,target.stat().st_uid,target.stat().st_gid);os.chmod(tmp,0o644);os.replace(tmp,target)
assert before==hashlib.sha256(profile.read_bytes()).hexdigest()
from scripts.drawing_mode_config import current_catalog
assert current_catalog()['verified']
print('Current catalog verified, 25 mode/class pairs. Saved manual profiles unchanged.')
