"""Measure current N3 output, never import legacy settings or production profiles.

Writes an auditable catalog from real generators and copied contracts. Mixed
values remain mixed: saving the catalog defaults must not flatten a drawing.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import runpy
import functools
from collections import defaultdict

ROOT = Path(os.environ.get('CAD_CURRENT_ROOT',str(Path(__file__).resolve().parents[1])))
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import ezdxf
from scripts import drawing_mode_config as cfg
from scripts.drawing_semantics import roles

SOURCES = ['scripts/gerar_' + c + '_dxf_stog.py' for c in ('pl','lv','fv','lj')] + [
    'scripts/visual_modes.py', 'scripts/arete/lv_n3_cut_draw.py', 'scripts/drawing_semantics.py',
    'scripts/pl_abcd_visual_nova.py', 'scripts/pl_cima_especial.py',
    'scripts/pl_grade_visual_config.py', 'src/core/pillar_special_faces.py']
SOURCES += [str(p.relative_to(ROOT)).replace('\\','/') for pattern in
            ('ini*.py','lv_*design.py','lv_*sa_adapter.py','lv_*grades.py','pillar_*design.py','pillar_nova_special.py')
            for p in (ROOT/'src/core').glob(pattern)]
SOURCES += ['scripts/drawing_mode_config.py','scripts/build_current_drawing_defaults.py']

def fingerprint():
    return {p: hashlib.sha256((ROOT/p).read_text(encoding='utf8').encode()).hexdigest() for p in SOURCES}

def measure(doc, result):
    assert not doc.audit().errors
    for layer in doc.layers:
        values=result.setdefault('layers',{}).setdefault(layer.dxf.name,defaultdict(set))
        values['color'].add(layer.dxf.color)
        values['linetype'].add(layer.dxf.linetype)
    for entity in doc.modelspace():
        layer_values=result['layers'].setdefault(entity.dxf.layer,defaultdict(set))
        if entity.dxftype()=='HATCH': layer_values['hatch_pattern'].add('SOLID' if entity.dxf.solid_fill else entity.dxf.pattern_name)
        elif entity.dxftype() not in {'TEXT','MTEXT','DIMENSION','INSERT'}:
            lt=entity.dxf.get('linetype','BYLAYER')
            layer_values['entity_linetype'].add(doc.layers.get(entity.dxf.layer).dxf.linetype if lt=='BYLAYER' and entity.dxf.layer in doc.layers else lt)
        role = roles(entity)
        if not role or role[1] not in {'texts','hatches','dimensions'}:
            continue
        view, family, name = role
        values = result.setdefault(family, {}).setdefault(name, defaultdict(set))
        kind = entity.dxftype()
        values['views'].add(view)
        values['entity_types'].add(kind)
        values['color'].add(entity.dxf.get('color',256))
        color=entity.dxf.get('color',256)
        values['resolved_color'].add((doc.layers.get(entity.dxf.layer).dxf.color if entity.dxf.layer in doc.layers else 'layer ausente') if color==256 else color)
        if kind in {'TEXT','MTEXT'}:
            values['height' if family=='texts' else 'text_height'].add(round(entity.dxf.get('char_height' if kind=='MTEXT' else 'height'),6))
            # Plain dimensions use a text style, native dimensions a DIMSTYLE.
            values['style'].add(entity.dxf.get('style','Standard'))
            if family=='texts': values['rotation'].add(round(entity.dxf.get('rotation',0),6))
            if family=='dimensions' and kind=='TEXT':
                label=entity.dxf.text.strip()
                try:
                    float(label)
                    values['precision'].add(len(label.partition('.')[2]))
                except ValueError:
                    pass
            if family=='dimensions' and entity.has_xdata('DRAWING_DIM_DETAIL'):
                detail=entity.get_xdata('DRAWING_DIM_DETAIL')
                if len(detail)>1: values['gap'].add(round(detail[1].value,6))
        elif kind=='HATCH':
            values['pattern'].add('SOLID' if entity.dxf.solid_fill else entity.dxf.pattern_name)
            if not entity.dxf.solid_fill:
                values['pattern_scale'].add(round(entity.dxf.pattern_scale,6))
                values['angle'].add(round(entity.dxf.pattern_angle,6))
        elif kind=='DIMENSION':
            dim=entity.override()
            style=doc.dimstyles.get(entity.dxf.dimstyle)
            values['style'].add(entity.dxf.dimstyle)
            for field,key in [('dimension_text_color','dimclrt'),('dimension_line_color','dimclrd'),('dimension_extension_color','dimclre')]:
                color=dim.get(key,getattr(style.dxf,key))
                if color is not None: values[field].add(color)
            for field,key in [('text_height','dimtxt'),('arrow_size','dimasz'),('gap','dimgap'),('precision','dimdec')]:
                value=dim.get(key,getattr(style.dxf,key))
                if value is not None: values[field].add(round(value,6))
        elif kind=='LINE' and entity.has_xdata('DRAWING_DIM_DETAIL'):
            if entity.get_xdata('DRAWING_DIM_DETAIL')[0].value=='tick':
                values['arrow_size'].add(round((entity.dxf.end-entity.dxf.start).magnitude,6))

def main():
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['ARETE_DRAWING_MODE_CONFIG']=str(out/'empty_profiles.json')
    os.environ['DRAWING_TEST_DB']=str(out/'governance.sqlite')
    os.environ['CAD_MOTOR_HEADLESS']='0'
    source=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'scripts/arete/relatorios/20261001_drawing_mode_config'
    from gerar_pl_dxf_stog import setup_doc,generate_pilar
    from scripts.visual_modes import apply_visual_mode
    hashes=fingerprint()
    catalog={'schema_version':1,'sources':hashes,'contracts': ['P1','V301 A/B Para/Passa','L301','LV corte: contrato do teste de qualidade (lajes com desnível)'], 'modes':{}}
    for mode in cfg.MODES:
        catalog['modes'][mode]={}
        for cls in cfg.CLASSES:
            folder=out/(mode+'_'+cls);folder.mkdir(exist_ok=True)
            result={}
            if cls=='PL':
                doc=setup_doc();payload=json.loads((source/'P1_source_copy.json').read_text(encoding='utf8'))
                generate_pilar(doc.modelspace(),payload,0,visual_mode=mode)
                apply_visual_mode(doc,mode,'PL');doc.saveas(folder/'P1.dxf');measure(doc,result)
            else:
                robot=cls.split('_')[0].lower();inputs=source/'cli_output_v2/inputs'
                args=[sys.executable,str(Path(__file__).resolve()),'--child','gerar_'+robot+'_dxf_stog.py','--obra',str(out/'isolated_obra'),'--item','L301' if cls=='LJ' else 'V301','--visual-mode',mode]
                args+=['--json-dir',str(inputs),'--out-dir',str(folder)] if cls=='LJ' else ['--input-dir',str(inputs/cls.split('_')[1] if cls.startswith('LV_') else inputs),'--output-dir',str(folder)]
                if cls.startswith('LV_'): args+=['--behavior',cls.split('_')[1].title()]
                run=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf8'})
                (folder/'run.log').write_text(run.stdout+run.stderr,encoding='utf8')
                assert run.returncode==0,run.stderr
                for path in folder.glob('*.dxf'): measure(ezdxf.readfile(path),result)
                if cls.startswith('LV_'):
                    from src.core.lv_n3_cut_contract import build_cut_contract
                    from scripts.arete.lv_n3_cut_draw import generate as generate_cut
                    fixture={'kind':'calculated','id':'catalog-cut','beam':'V1','width_cm':19,'beam_height_cm':55,
                        'profiles':{'A':{'level':852.12,'slabs':[{'name':'L1','height_cm':10,'level':852.12}]},
                                    'B':{'level':852.19,'slabs':[{'name':'L2','height_cm':12,'level':852.19}]}},'pairs':[]}
                    measure(generate_cut(build_cut_contract(fixture),folder/'cut.dxf',mode,cls.split('_')[1]),result)
            catalog['modes'][mode][cls]={family:{name:{key:sorted(vals,key=str) for key,vals in values.items()} for name,values in group.items()} for family,group in result.items()}
            print(mode,cls,'measured',flush=True)
    assert hashes==fingerprint(),'Generators changed during measurement; rerun'
    (out/'measured.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')
    if len(sys.argv)<4 or sys.argv[3]!='--measure-only':
        (ROOT/'config/drawing_mode_current_catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')

def refresh_measurements(out,publish=False):
    out=Path(out)
    catalog=json.loads((out/'measured.json').read_text(encoding='utf8'))
    assert catalog['sources']==fingerprint(),'Generators changed; regenerate drawings'
    for mode in cfg.MODES:
        for cls in cfg.CLASSES:
            result={}
            for path in (out/(mode+'_'+cls)).glob('*.dxf'): measure(ezdxf.readfile(path),result)
            catalog['modes'][mode][cls]={family:{name:{key:sorted(vals,key=str) for key,vals in values.items()} for name,values in group.items()} for family,group in result.items()}
    (out/'measured.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')
    if publish:(ROOT/'config/drawing_mode_current_catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')


def measure_approved(out, source, publish=False):
    """Measure the approved SA adapters, both LV assemblies and all N3 views."""
    from copy import deepcopy
    from scripts.arete.lv_n3_cut_draw import generate, generate_local_panels
    from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone
    from scripts.visual_modes import apply_visual_mode
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['ARETE_DRAWING_MODE_CONFIG']=str(out/'empty_profiles.json')
    os.environ['DRAWING_TEST_DB']=str(out/'governance.sqlite')
    os.environ['CAD_MOTOR_HEADLESS']='0'
    hashes=fingerprint()
    reports=ROOT/'scripts/arete/relatorios'
    inventory=json.loads((reports/'20261007_ini_lv_comparacao/current_inventory.json').read_text(encoding='utf8'))
    payload=json.loads((reports/'20261007_ini_abcd_design/payload_P1_portal.json').read_text(encoding='utf-8-sig'))
    special=json.loads((reports/'20261007_ini_parafusos_especiais/baseline.json').read_text(encoding='utf8'))['payloads']['para/P26.json']
    catalog=dict(schema_version=2,sources=hashes,contracts=['PL P1/P26 SA; CIMA/ABCD/EFGH/GRADES','LV V316 SA; A/B/corte; gradeadas/sarrafeadas; PARA/PASSA style calibration','FV V301 SA','LJ L301 SA'],measurement='approved_sa_adapters',modes={})
    for mode in ('INI','NOVA','MOLDE_1'):
        catalog['modes'][mode]={}
        for cls in cfg.CLASSES:
            folder=out/(mode+'_'+cls);folder.mkdir(exist_ok=True);result={}
            if cls=='PL':
                for pj in (payload,special):
                    for zone in ('cima','abcd','efgh','grades'):
                        doc=setup_doc()
                        if generate_pilar_zone(doc.modelspace(),deepcopy(pj),zone,visual_mode=mode)<0:continue
                        apply_visual_mode(doc,mode,'PL');doc.saveas(folder/f"{pj['nome']}_{zone}.dxf");measure(doc,result)
            elif cls.startswith('LV_'):
                behavior=cls.split('_')[1]
                for assembly in ('sarrafeadas','gradeadas'):
                    sides={r['kind']:deepcopy(r['contract']) for r in inventory if r['assembly']==assembly}
                    for side in 'AB':
                        target=folder/f'{assembly}_{side}.dxf'
                        generate_local_panels(sides,target,side,mode=mode,behavior=behavior)
                        # Measure native granular units, including loose grades.
                        for path in target.with_suffix('.units').glob('*.dxf'):
                            measure(ezdxf.readfile(path),result)
                    measure(generate(sides['CORTE'],folder/f'{assembly}_CORTE.dxf',mode=mode,behavior=behavior),result)
            else:
                robot=cls.lower();inputs=Path(source)/'cli_output_v2/inputs'
                args=[sys.executable,str(Path(__file__).resolve()),'--child',f'gerar_{robot}_dxf_stog.py','--obra',str(out/'isolated_obra'),'--item','L301' if cls=='LJ' else 'V301','--visual-mode',mode]
                args+=['--json-dir',str(inputs),'--out-dir',str(folder)] if cls=='LJ' else ['--input-dir',str(inputs),'--output-dir',str(folder)]
                run=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf8'})
                (folder/'run.log').write_text(run.stdout+run.stderr,encoding='utf8')
                if run.returncode:raise RuntimeError(run.stderr)
                for path in folder.glob('*.dxf'):measure(ezdxf.readfile(path),result)
            catalog['modes'][mode][cls]={family:{name:{key:sorted(vals,key=str) for key,vals in values.items()} for name,values in group.items()} for family,group in result.items()}
            print(mode,cls,'approved adapters measured',flush=True)
    assert hashes==fingerprint(),'Renderer changed during measurement'
    (out/'measured.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')
    if publish:(ROOT/'config/drawing_mode_current_catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf8')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':
        from src.core import artifact_governance as governance
        governance.guarded_saveas=functools.partial(governance.guarded_saveas,db_path=os.environ['DRAWING_TEST_DB'])
        generator=sys.argv[2];sys.argv=[generator]+sys.argv[3:]
        runpy.run_path(str(ROOT/'scripts'/generator),run_name='__main__')
    elif len(sys.argv)>1 and sys.argv[1]=='--approved-adapters': measure_approved(sys.argv[2],sys.argv[3], '--publish' in sys.argv)
    elif len(sys.argv)>1 and sys.argv[1]=='--refresh-measurements': refresh_measurements(sys.argv[2], '--publish' in sys.argv)
    else: main()
