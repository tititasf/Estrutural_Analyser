from pathlib import Path
import difflib,json
root=Path(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main')
base=Path(r'D:\Agente-cad-PYSIDE\geometry-review')
patches=[]
for old in base.rglob('*'):
 if not old.is_file():continue
 rel=old.relative_to(base).as_posix();new=root/rel
 if not new.is_file():continue
 a=old.read_text(encoding='utf-8').splitlines(True);b=new.read_text(encoding='utf-8').splitlines(True)
 matcher=difflib.SequenceMatcher(None,a,b,autojunk=False)
 operations=[]
 for group in matcher.get_grouped_opcodes(2):
  i,j=group[0][1],group[-1][2];k,l=group[0][3],group[-1][4]
  if rel.endswith('obra_detalhe.html') and i<700:continue # concurrent N5 update, already deployed
  operations.append({'old':''.join(a[i:j]),'new':''.join(b[k:l])})
 if operations:patches.append({'file':rel,'operations':operations})
(base/'anchored.json').write_text(json.dumps(patches,ensure_ascii=False),encoding='utf-8')
print('files:',len(patches),'operations:',sum(len(p['operations']) for p in patches))
