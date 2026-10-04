"""Publish reviewed display-only deltas with fresh compare-and-swap backups."""
from pathlib import Path
import subprocess, difflib, hashlib, json, base64, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
FILES = ['portal/app/static/decimal_display.js', 'portal/app/static/fv_ficha.js',
    'portal/app/static/lv_ficha.js', 'portal/app/static/laje_ficha.js',
    'portal/app/static/pillar_ficha.js', 'portal/app/dxf_preview.py',
    'src/core/n5_assembler.py', 'scripts/arete/headless_sa_analise.py',
    'portal/app/templates/obra_detalhe.html', 'portal/app/templates/base.html',
    'src/core/number_presentation.py', 'src/core/fv_dimension_presentation.py']
payload=[]
if len(sys.argv) > 1:
    requested = sys.argv[1:]
    assert all(path in FILES for path in requested), 'unsupported deployment target'
    FILES = requested
for rel in FILES:
    result=subprocess.run(['ssh','root@62.238.111.147','test ! -f /opt/cad-analyzer/'+rel+' || cat /opt/cad-analyzer/'+rel],capture_output=True,check=True)
    remote=result.stdout
    if rel in ('src/core/number_presentation.py', 'src/core/fv_dimension_presentation.py'):
        revised=(ROOT/rel).read_bytes()
        old_version=revised.replace(b'one-decimal-v4',b'one-decimal-v3').replace(b".removesuffix('.0')",b'').replace(b"'dimzin': 8",b"'dimzin': 0")
        reviewed_v4 = rel == 'src/core/number_presentation.py' and hashlib.sha256(remote).hexdigest() in {
            'f63c2aaf2cd552930fff3d78fcfda422d5f94706548ab6d714e04db31d1dbdf6',
            'd985239481413ec81db0f7933a37e72d8c775a5aa1eef72903357d1cdb7324af',
            '081f379f0133fb7f2c718df77f1043661f385205d0cc3673fa3215ac9e42986e',
            'fc04ec1d82aa97107507eae44b03c27347656e09b8254b6a3f675762328c36ca',
        }
        assert not remote or remote == revised or reviewed_v4 or remote.replace(b'\r\n',b'\n') == old_version.replace(b'\r\n',b'\n'), 'module changed remotely; inspect first'
    else:
        old=remote.decode().splitlines(keepends=True)
        local=(ROOT/rel).read_text(encoding='utf-8').splitlines(keepends=True)
        revised=[]
        for tag,a,b,c,d in difflib.SequenceMatcher(None,old,local,autojunk=False).get_opcodes():
            candidate=''.join(local[c:d])
            if tag=='equal': revised.extend(old[a:b]);continue
            relevant=any(word in candidate for word in ['PortalNumbers','prepareInput','data-measure-number',
                'number(value)', 'input:not([type=checkbox])', 'one-decimal3','one-decimal-v3','number_presentation','number presentation:',
                'lengthText(segment.', 'esc(segment.index)', 'esc(original.segment_index)',
                'minimumFractionDigits: 0', 'one-decimal4', 'one-decimal-v4', 'one-decimal-levels', 'data-level-number'])
            if rel.endswith('decimal_display.js'): relevant=True
            revised.extend(local[c:d] if relevant else old[a:b])
        revised=''.join(revised).encode()
    payload.append({'path':rel,'old_hash':hashlib.sha256(remote).hexdigest() if remote else None,
        'data':base64.b64encode(revised).decode()})
remote_script=r'''
import base64,hashlib,json,pathlib,shutil,sqlite3,sys,time,py_compile
root=pathlib.Path('/opt/cad-analyzer')
payload=json.loads(sys.stdin.read())
with sqlite3.connect((root/'portal_data.db').as_uri()+'?mode=ro',uri=True) as db:
    assert not db.execute("SELECT id FROM portal_jobs WHERE status IN ('executando','na_fila')").fetchall(),'fila ocupada'
for item in payload:
    path=root/item['path']
    actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    assert actual==item['old_hash'],'source changed: '+item['path']
backup=root/'deploy_backups'/('number_presentation_'+str(int(time.time())))
for item in payload:
    path=root/item['path'];saved=backup/item['path'];saved.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():shutil.copy2(path,saved)
    path.write_bytes(base64.b64decode(item['data']))
    if path.suffix=='.py':py_compile.compile(str(path),doraise=True)
print('PUBLISHED',str(backup),len(payload))
'''
# The remote code receives its payload on stdin; no shell interpolation of sources.
command='/opt/cad-analyzer/.venv/bin/python -c '+__import__('shlex').quote(remote_script)
result=subprocess.run(['ssh','root@62.238.111.147',command],input=json.dumps(payload).encode(),capture_output=True,check=True)
print(result.stdout.decode())
