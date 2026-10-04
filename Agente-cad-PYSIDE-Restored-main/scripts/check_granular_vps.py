"""Run real PL generation on VPS with isolated inputs/settings/output."""
import os,sys,json
from pathlib import Path
root=Path('/opt/cad-analyzer'); out=Path('/root/granular_validation_20261001')
out.mkdir(exist_ok=True)
os.environ['ARETE_DRAWING_MODE_CONFIG']=str(out/'profiles.json')
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'scripts'))
from scripts import drawing_mode_config as cfg
from scripts.drawing_semantics import roles
from scripts.visual_modes import apply_visual_mode
from gerar_pl_dxf_stog import setup_doc,generate_pilar
payload=json.loads((out/'P1_source_copy.json').read_text())
results={}
for mode in cfg.MODES:
    cfg.save(mode,'PL',cfg.defaults(mode,'PL'),cfg.read_store()['revision'],'isolated-vps')
    def draw(label):
        doc=setup_doc();generate_pilar(doc.modelspace(),payload,0,visual_mode=mode)
        apply_visual_mode(doc,mode,'PL');doc.saveas(out/f'{mode}_{label}.dxf')
        assert not doc.audit().errors
        return doc
    before=draw('before')
    profile=cfg.effective(mode,'PL');profile['texts']['nome'].update(scale=1.7,color=1)
    cfg.save(mode,'PL',profile,cfg.read_store()['revision'],'isolated-vps')
    after=draw('after');changed=0
    assert len(before.modelspace())==len(after.modelspace())
    for a,b in zip(before.modelspace(),after.modelspace()):
        if roles(a) and roles(a)[1:]==('texts','nome'):
            attribute='char_height' if a.dxftype()=='MTEXT' else 'height'
            assert abs(getattr(b.dxf,attribute)-getattr(a.dxf,attribute)*1.7)<1e-6 and b.dxf.color==1
            changed+=1
        elif a.dxftype()=='TEXT':assert b.dxf.height==a.dxf.height
    assert changed
    results[mode]={'changed_names':changed,'audit_errors':0,'other_texts_preserved':True}
(out/'evidence.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
