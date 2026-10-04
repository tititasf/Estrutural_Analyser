"""Verify real emitted DXFs: unchanged save and selective absolute editing."""
import json,os,sys
from pathlib import Path
ROOT=Path(os.environ.get('CAD_CURRENT_ROOT',str(Path(__file__).resolve().parents[1])))
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import ezdxf
from scripts import drawing_mode_config as cfg
from scripts.drawing_semantics import roles

def main():
    source=Path(sys.argv[1]);os.environ['ARETE_DRAWING_MODE_CONFIG']=str(source/'validation_profiles.json')
    results={}
    for mode in cfg.MODES:
        for cls in cfg.CLASSES:
            value=cfg.defaults(mode,cls);cfg.save(mode,cls,value,cfg.read_store()['revision'],'isolated-actual-defaults')
            assert cfg.overrides(mode,cls)=={}
            changed=0;paths=list((source/(mode+'_'+cls)).glob('*.dxf'))
            assert paths
            for path in paths:
                doc=ezdxf.readfile(path)
                layouts=[doc.modelspace()]+list(doc.blocks)
                before=[[e.dxf.all_existing_dxf_attribs() for e in layout] for layout in layouts]
                cfg.apply_config(doc,mode,cls)
                assert before==[[e.dxf.all_existing_dxf_attribs() for e in layout] for layout in layouts]
                edited=cfg.defaults(mode,cls);edited['texts']['nome']['height']=23.75
                cfg.save(mode,cls,edited,cfg.read_store()['revision'],'isolated-absolute-edit')
                originals=[e.dxf.all_existing_dxf_attribs() for e in doc.modelspace()]
                cfg.apply_config(doc,mode,cls)
                for original,entity in zip(originals,doc.modelspace()):
                    role=roles(entity)
                    if role and role[1:]==('texts','nome'):
                        attr='char_height' if entity.dxftype()=='MTEXT' else 'height'
                        assert getattr(entity.dxf,attr)==23.75
                        changed+=1
                    else: assert original==entity.dxf.all_existing_dxf_attribs()
                assert not doc.audit().errors
                cfg.save(mode,cls,value,cfg.read_store()['revision'],'reset-isolated')
            assert changed
            results[mode+'/'+cls]={'DXFs':len(paths),'unchanged_default_save':True,'absolute_height':23.75,'changed_name_entities':changed,'other_entities_unchanged':True,'audit_errors':0}
    (source/'validation.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print('Verified',len(results),'mode/class pairs;',sum(r['DXFs'] for r in results.values()),'real DXFs')

if __name__=='__main__': main()
