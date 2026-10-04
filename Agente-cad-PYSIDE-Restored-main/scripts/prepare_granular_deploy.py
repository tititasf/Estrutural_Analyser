"""Stage only this task's changes, preserving independent agent edits."""
import difflib,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'scripts/arete/relatorios/20261001_config_granular'
snapshot=json.loads((OUT/'remote_snapshot.json').read_text(encoding='utf8'))
full={'scripts/drawing_mode_config.py','scripts/visual_modes.py','portal/app/drawing_modes.py','portal/app/static/drawing_mode.js','portal/app/static/drawing_mode_config.js','portal/app/static/drawing_mode_config.css','portal/app/drawing_frame.py','portal/app/routers/drawing_mode_config_routes.py','scripts/pl_grade_visual_config.py','portal/app/lv_n3_cuts.py'}
payload={}; report=[]
for file,remote in snapshot['files'].items():
    local=(ROOT/file).read_text(encoding='utf8')
    if local==remote: continue
    if file in full: result=local
    elif file=='scripts/arete/lv_n3_cut_draw.py':
        result=remote
        replacements={
            "def generate(contract, path, mode='NOVA'):":"def generate(contract, path, mode='NOVA', behavior='PARA'):",
            '    doc=m.setup_doc(); space=doc.modelspace()':"    from scripts.drawing_semantics import LayoutProxy\n    doc=m.setup_doc(); space=LayoutProxy(doc.modelspace(),'LV')",
            "if hatch and mode=='NOVA':":"if hatch and mode!='INI':",
            '    doc.saveas(path)':"    from scripts.drawing_mode_config import apply_config\n    apply_config(doc,mode,'LV',behavior)\n    doc.saveas(path)",
        }
        for old,new in replacements.items():
            assert result.count(old)==1,(file,old)
            result=result.replace(old,new)
    else:
        before=remote.splitlines(True);after=local.splitlines(True);result=[]
        for tag,i,j,k,l in difflib.SequenceMatcher(None,before,after,autojunk=False).get_opcodes():
            old=''.join(before[i:j]);new=''.join(after[k:l])
            approved=tag=='equal' or 'MOLDE_' in new
            if file=='scripts/arete/lv_n3_cut_draw.py':
                approved=tag=='equal' or any(s in new for s in ["behavior='PARA'","LayoutProxy", "hatch and mode!='INI'",'apply_config(doc,mode'])
            if file=='src/core/n5_assembler.py': approved=tag=='equal' or 'visual_mode != "NOVA"' in new
            if approved: result.extend(after[k:l])
            else:
                result.extend(before[i:j]);report.append({'file':file,'preserved_remote':old[:180],'excluded_other_agent':new[:180]})
        result=''.join(result)
    if result==remote: continue
    if file.endswith('.py'):compile(result,file,'exec')
    payload[file]={'expected':snapshot['hashes'][file],'source':result}
payload['scripts/drawing_semantics.py']={'expected':None,'source':(ROOT/'scripts/drawing_semantics.py').read_text(encoding='utf8')}
(OUT/'deploy_payload.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
(OUT/'deployment_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('Staged files',len(payload),'independent hunks preserved',len(report))
print('\n'.join(payload))
