from pathlib import Path
import hashlib,json,sqlite3,subprocess,datetime,shutil,py_compile

root=Path('/opt/cad-analyzer')
stage=Path('/tmp/panel_drilling_deploy')
manifest=json.loads((stage/'manifest.json').read_text())
db=sqlite3.connect('file:/opt/cad-analyzer/portal_data.db?mode=ro',uri=True)
active=db.execute("select id,status from portal_jobs where status not in ('cancelado','concluido','falhou')").fetchall()
assert not active,active
for item in manifest:
    target=root/item['path']
    actual=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    assert actual==item['old_hash'],(item['path'],actual,'concurrent change')
backup=Path('/root')/('backup_panel_drilling_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir()
for item in manifest:
    target=root/item['path'];source=stage/item['staged']
    if target.exists():shutil.copy2(target,backup/target.name)
    shutil.copy2(source,target)
    subprocess.run(['chown','cadapp:cadapp',str(target)],check=True)
    if target.suffix=='.py':py_compile.compile(str(target),doraise=True)
subprocess.run(['systemctl','restart','cad-portal'],check=True)
print(json.dumps({'backup':str(backup),'deployed':[i['path'] for i in manifest]}))
