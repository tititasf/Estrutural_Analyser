"""Real generators, copied inputs, isolated settings and governance DB."""
import os,sys,json,subprocess
from datetime import datetime
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import ezdxf
from scripts import drawing_mode_config as cfg
from scripts.drawing_semantics import roles
from scripts.visual_modes import apply_visual_mode
from gerar_pl_dxf_stog import setup_doc,generate_pilar

def main():
    out=ROOT/'scripts/arete/relatorios/20261001_config_granular'/('real_'+datetime.now().strftime('%H%M%S'))
    out.mkdir(parents=True,exist_ok=True)
    os.environ['ARETE_DRAWING_MODE_CONFIG']=str(out/'profiles.json')
    os.environ['DRAWING_TEST_DB']=str(out/'governance.sqlite')
    os.environ['CAD_MOTOR_HEADLESS']='0'
    source=ROOT/'scripts/arete/relatorios/20261001_drawing_mode_config'
    cfg.catalog()
    result={}
    for mode in cfg.MODES:
        for cls in cfg.CLASSES:
            def generate(label):
                folder=out/(mode+'_'+cls+'_'+label);folder.mkdir(exist_ok=True)
                if cls=='PL':
                    doc=setup_doc()
                    payload=json.loads((source/'P1_source_copy.json').read_text(encoding='utf8'))
                    generate_pilar(doc.modelspace(),payload,0,visual_mode=mode)
                    apply_visual_mode(doc,mode,'PL')
                    doc.saveas(folder/'P1.dxf')
                else:
                    inputs=source/'cli_output_v2/inputs'
                    robot=cls.split('_')[0].lower()
                    args=[sys.executable,str(ROOT/'scripts/check_drawing_mode_cli_real.py'),'--child','gerar_'+robot+'_dxf_stog.py','--obra',str(out/'isolated_obra'),'--item','L301' if cls=='LJ' else 'V301','--visual-mode',mode]
                    args += ['--json-dir',str(inputs),'--out-dir',str(folder)] if cls=='LJ' else ['--input-dir',str(inputs/cls.split('_')[1] if cls.startswith('LV_') else inputs),'--output-dir',str(folder)]
                    if cls.startswith('LV_'):args += ['--behavior',cls.split('_')[1].title(),'--view','A']
                    run=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf8'})
                    (folder/'run.log').write_text(run.stdout+run.stderr,encoding='utf8')
                    assert run.returncode==0,run.stderr
                    doc=ezdxf.readfile(next(folder.glob('*.dxf')))
                assert not doc.audit().errors
                return doc
            before=generate('default')
            value=cfg.effective(mode,cls)
            value['texts']['nome'].update(scale=1.7,color=1)
            cfg.save(mode,cls,value,cfg.read_store()['revision'],'real-test')
            after=generate('custom')
            expected=actual=0
            assert len(before.modelspace())==len(after.modelspace())
            for a,b in zip(before.modelspace(),after.modelspace()):
                role=roles(a)
                if role and role[1:] == ('texts','nome'):
                    expected+=1
                    attr='char_height' if a.dxftype()=='MTEXT' else 'height'
                    assert abs(getattr(b.dxf,attr)-getattr(a.dxf,attr)*1.7)<1e-6
                    assert b.dxf.color==1
                    actual+=1
                elif a.dxftype()=='TEXT':assert b.dxf.height==a.dxf.height,(cls,a.dxf.text,role)
            assert actual>0,(mode,cls,'no name texts classified')
            counter=Counter('/'.join(roles(e) or ('UNCLASSIFIED',)) for e in before.modelspace())
            result[mode+'/'+cls]={'entities':len(before.modelspace()),'changed_name_texts':actual,'other_texts_preserved':True,'audit_errors':0,'roles':dict(counter)}
            print(mode,cls,actual,'name texts selectively changed',flush=True)
            cfg.save(mode,cls,cfg.defaults(mode,cls),cfg.read_store()['revision'],'restore-test')
    (out/'evidence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
if __name__=='__main__':main()
