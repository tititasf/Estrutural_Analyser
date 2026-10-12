from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest
from src.core.n3_local_tasks import run_local_tasks


@pytest.mark.parametrize('mode', ['INI', 'NOVA', 'MOLDE_1'])
def test_process_generation_preserves_complete_dxf_and_reports_each_failure(tmp_path, mode):
    spec=importlib.util.spec_from_file_location('n3_parity',Path(__file__).resolve().parents[1]/'scripts/arete/relatorios/20261008_n3_performance/compare_dxf.py')
    parity=importlib.util.module_from_spec(spec);spec.loader.exec_module(parity)
    tasks=[]
    for assembly in ('gradeadas','sarrafeadas'):
        source=dict(beam_name='V9',side='A',assembly_variant=assembly,
                    panels=[dict(width=122,height1=75,height2=75,body_height_cm=60,structural_segment_index=1)])
        tasks.append((assembly,{'A':source},str(tmp_path/'serial'/f'{assembly}.dxf'),'A',mode,'Para'))
    tasks.append(('invalid',{'A':{}},str(tmp_path/'serial'/'invalid.dxf'),'A',mode,'Para'))
    original=deepcopy(tasks)
    serial=run_local_tasks(tasks,1)
    parallel_tasks=[(name,sides,path.replace('serial','parallel'),view,m,b) for name,sides,path,view,m,b in tasks]
    parallel=run_local_tasks(parallel_tasks,2)
    assert tasks==original
    assert [(r[0],r[1]) for r in serial]==[(r[0],r[1]) for r in parallel]==[('gradeadas',True),('sarrafeadas',True),('invalid',False)]
    assert parity.compare(tmp_path/'serial',tmp_path/'parallel')['equal']
    assert not (tmp_path/'parallel'/'invalid.dxf').exists()


def test_parallel_panel_inventory_preserves_variants_overrides_and_units(tmp_path):
    import json
    from src.core.n3_local_tasks import run_panel_tasks
    from portal.app.lv_n3_operations import load_ficha, save_ficha
    spec=importlib.util.spec_from_file_location('panel_parity',Path(__file__).resolve().parents[1]/'scripts/arete/relatorios/20261008_n3_performance/compare_dxf.py')
    parity=importlib.util.module_from_spec(spec);spec.loader.exec_module(parity)
    tasks=[]
    originals={}
    for rootname in ('serial','parallel'):
        obra=tmp_path/rootname
        source=obra/'Fase-6_Execucao_CAD/production_sa/P/20261008/n3/contracts_lv/LV-PARA'
        source.mkdir(parents=True)
        for side in 'AB':
            contract=dict(beam_name='V9',side=side,behavior='Para',total_width=19,total_height=59,h_section=55,
                panels=[dict(width=122,height1=59,height2=59,structural_segment_index=1,
                             panel_type='Sarrafeado',grade_h1=0,grade_h2=0)])
            path=source/f'V9_{side}.json';path.write_text(json.dumps(contract));originals[path]=path.read_bytes()
        draft=load_ficha(obra,'P','para','V9','gradeadas',mode='INI')
        draft['sides']['A']['panels'][0]['width']=120
        save_ficha(obra,'P','para','V9',draft,'gradeadas',mode='INI')
        tasks.append([(str(obra),'P','para','V9',side,'INI',assembly)
                      for side in 'AB' for assembly in ('gradeadas','sarrafeadas')]
                      +[(str(obra),'P','para','V999','A','INI','gradeadas')])
    serial=run_panel_tasks(tasks[0],1);parallel=run_panel_tasks(tasks[1],2)
    assert [r[0] for r in serial]==[r[0] for r in parallel]==[True,True,True,True,False]
    assert [r[2] for r in serial]==[r[2] for r in parallel]
    assert parity.compare(tmp_path/'serial',tmp_path/'parallel')['equal']
    assert all(path.read_bytes()==raw for path,raw in originals.items())
