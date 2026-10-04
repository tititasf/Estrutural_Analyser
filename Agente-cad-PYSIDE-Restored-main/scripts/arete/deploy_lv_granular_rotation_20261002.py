from pathlib import Path
import hashlib, shutil, sqlite3, subprocess, time
root=Path('/opt/cad-analyzer')
expected={'portal/app/lv_cut_map.py':'ad23bf8194b5d5406378bb4f873a8b90f89b2cb4b94f43841f32b066ac0449cf',
          'portal/app/lv_ficha.py':'a7a6d75796db139b9dace237cbde1cf5658b884087c5fc6d5e2014762129922b'}
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(), 'fila ocupada'
for rel,digest in expected.items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest, f'fonte mudou {rel}'
backup=Path('/root/lv_granular_rotation_20261002')/str(int(time.time()))
for rel in expected:
    source=Path('/tmp/lv-sections-stage')/rel
    compile(source.read_text(encoding='utf8'),rel,'exec')
    saved=backup/rel; saved.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,saved); shutil.copy2(source,root/rel)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
subprocess.run(['systemctl','is-active','cad-portal'],check=True)
print('PUBLISHED',backup)
