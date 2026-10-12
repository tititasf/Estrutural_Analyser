from copy import deepcopy
import json
from pathlib import Path
import pytest
import ezdxf
from portal.app.lv_n3_operations import load_ficha,save_ficha,effective_contracts
from portal.app.lv_n3_panels import resolve
from src.core.lv_n3_cut_contract import build_cut_contract
from scripts.arete.lv_n3_cut_draw import generate


def source(tmp_path):
    root=tmp_path/'Fase-6_Execucao_CAD'/'production_sa'/'13_PAV'/'20261004'/'n3'/'contracts_lv'/'LV-PARA'
    root.mkdir(parents=True)
    for side in ('A','B'):
        c=dict(beam_name='V301',behavior='Para',total_width=19,total_height=59,h_section=55,
            panels=[dict(width=w,height1=59,height2=59,structural_segment_index=i,
                        panel_type='Sarrafeado',grade_h1=0,grade_h2=0)
                    for w,i in [(244,1),(61.5,1),(100,2)]])
        (root/f'V301_{side}.json').write_text(json.dumps(c))
    return {p:p.read_bytes() for p in root.glob('*.json')}


def test_edits_are_variant_isolated_and_sa_immutable(tmp_path):
    originals=source(tmp_path)
    grade=load_ficha(tmp_path,'13_PAV','para','V301','gradeadas')
    slats=load_ficha(tmp_path,'13_PAV','para','V301','sarrafeadas')
    grade['sides']['A']['panels'][0]['grade_h1']=40
    grade['sides']['A']['panels'][0]['width']=240
    save_ficha(tmp_path,'13_PAV','para','V301',grade,'gradeadas')
    assert load_ficha(tmp_path,'13_PAV','para','V301','sarrafeadas')==slats
    assert effective_contracts(tmp_path,'13_PAV','para','V301','gradeadas')['A']['panels'][0]['grade_h1']==40
    assert all(p.read_bytes()==raw for p,raw in originals.items())
    with pytest.raises(ValueError,match='outra sessão'):
        save_ficha(tmp_path,'13_PAV','para','V301',grade,'gradeadas')


def test_selected_segment_is_not_whole_face_and_geometry_differs(tmp_path):
    source(tmp_path)
    results={kind:resolve(tmp_path,'13_PAV','para','V301','A',1,assembly=kind,render=False)
             for kind in ('gradeadas','sarrafeadas')}
    assert results['gradeadas']['path']!=results['sarrafeadas']['path']
    docs={kind:ezdxf.readfile(r['path']) for kind,r in results.items()}
    assert len(docs['gradeadas'].modelspace())!=len(docs['sarrafeadas'].modelspace())
    for r in results.values():
        contract=json.loads((Path(r['path']).parent/'contract.json').read_text())
        assert sum(p['width'] for p in contract['panels'])==305.5
        assert {p['structural_segment_index'] for p in contract['panels']}=={1}
    assert all(not d.audit().has_errors for d in docs.values())
    with pytest.raises(LookupError):resolve(tmp_path,'13_PAV','para','V301','A',9,render=False)


def test_cuts_have_independent_assembly_geometry(tmp_path):
    cut={'kind':'calculated','id':'x','beam':'V301','width_cm':19,'beam_height_cm':55,
         'profiles':{side:{'level':852.19,'slabs':[]} for side in ('A','B')},'pairs':[]}
    contract=build_cut_contract(cut);before=deepcopy(contract)
    docs={kind:generate(dict(contract,assembly_variant=kind),tmp_path/f'{kind}.dxf')
          for kind in ('gradeadas','sarrafeadas')}
    assert list(docs['gradeadas'].modelspace().query('INSERT'))
    assert not list(docs['sarrafeadas'].modelspace().query('INSERT'))
    assert all(list(d.modelspace().query('HATCH')) for d in docs.values())
    assert contract==before and all(not d.audit().has_errors for d in docs.values())


def test_profiles_pair_by_physical_overlap_not_segment_number():
    from src.core.vigas_drawing_config import prepare_lv_sources,apply_lv_config
    cell={'depth':55,'level':852.19,'slabs':[{'name':'L1','level':852.19,'height':'h=13'}]}
    a={'beam_name':'V301','side':'A','total_width':19,'structural_segments':[{'segment_index':1,'points':[[0,0],[100,0]],'lv_cell':cell}],'panels':[{'structural_segment_index':1,'height1':59,'height2':59}]}
    low={**cell,'level':852.12,'slabs':[{'name':'L2','level':852.12,'height':13}]}
    b={'beam_name':'V301','side':'B','total_width':19,'structural_segments':[{'segment_index':1,'points':[[300,19],[200,19]],'lv_cell':cell},{'segment_index':9,'points':[[100,19],[0,19]],'lv_cell':low}],'panels':[]}
    before=deepcopy({'A':a,'B':b})
    prepared=prepare_lv_sources(before)
    profile=prepared['A']['structural_segments'][0]['section_contract']['mounting']
    assert profile['A']['h1_cm']==44
    assert profile['B']['h1_cm']==37
    assert before=={'A':a,'B':b}
    assert apply_lv_config(prepared['A'])['panels'][0]['body_height_cm']==44


def profile_transition_source(reverse=False, gap=False):
    cell={'depth':55,'level':852.19,'slabs':[{'name':'L1','level':852.19,'height':13}]}
    higher={**cell,'level':852.24,'slabs':[{'name':'L2','level':852.24,'height':13}]}
    points=[[0,0],[100,0]] if not reverse else [[100,0],[0,0]]
    a=dict(beam_name='V301',side='A',total_width=19,total_length=100,
        structural_segments=[dict(segment_index=1,width=100,points=points,lv_cell=cell)],
        panels=[dict(width=100,height1=59,height2=59,structural_segment_index=1,
            holes=[dict(active=True,width=30,height=20,position=0,corner='TR')])])
    b=dict(beam_name='V301',side='B',total_width=19,panels=[],structural_segments=[
        dict(segment_index=4,width=40,points=[[0,19],[40,19]],lv_cell=cell),
        dict(segment_index=9,width=60,points=[[45 if gap else 40,19],[100,19]],lv_cell=higher)])
    return {'A':a,'B':b}


@pytest.mark.parametrize('reverse',[False,True])
def test_nova_partitions_measured_transition_without_changing_sa(reverse):
    from src.core.vigas_drawing_config import prepare_lv_sources,apply_lv_config
    from src.core.lv_nova_sa_adapter import ab_runs
    original=profile_transition_source(reverse)
    before=deepcopy(original)
    derived=prepare_lv_sources(original,mode='NOVA')['A']
    assert original==before
    assert sum(p['width'] for p in derived['panels'])==100
    assert [p['width'] for p in derived['panels']]==([60,40] if reverse else [40,60])
    assert sum(h['width'] for p in derived['panels'] for h in p['holes'])==30
    assert len({p['physical_segment_index'] for p in derived['panels']})==2
    runs=ab_runs(apply_lv_config(derived,{'comportamento_laterais_vigas':'gradeadas'}))
    assert len(runs)==1
    assert {s['body_cm'] for r in runs for s in r['segments']}=={39,44}
    assert sum(s['length'] for r in runs for s in r['segments'])==100


def test_nova_profile_partition_rejects_unmeasured_gap():
    from src.core.vigas_drawing_config import prepare_lv_sources
    with pytest.raises(ValueError,match='cobertura física única'):
        prepare_lv_sources(profile_transition_source(gap=True),mode='NOVA')


def test_other_modes_keep_profile_transition_pending():
    from src.core.vigas_drawing_config import prepare_lv_sources
    with pytest.raises(ValueError,match='perfis de montagem distintos'):
        prepare_lv_sources(profile_transition_source(),mode='INI')


def test_profile_partition_preserves_openings_crossing_boundary_and_trim():
    from src.core.vigas_drawing_config import prepare_lv_sources,apply_lv_config
    from src.core.lv_nova_sa_adapter import ab_runs
    original=profile_transition_source()
    a=original['A'];a['start_adjustment']=-10
    a['panels'][0]['width']=90
    a['panels'][0]['holes'][0]['width']=70
    a['structural_segments'][0]['lv_cell']['pillar_openings']=[
        {'pos_inicio':30,'pos_fim':50}]
    before=deepcopy(original)
    derived=prepare_lv_sources(original,mode='NOVA')['A']
    runs=ab_runs(apply_lv_config(derived))
    assert [s['length'] for r in runs for s in r['segments']]==[30,60]
    assert [s['column_openings'] for r in runs for s in r['segments']]==[[(20,30)],[(0,10)]]
    assert sum(b-a for r in runs for s in r['segments'] for a,b,_ in s['beam_openings'])==70
    assert original==before


def test_profile_partition_clears_only_resolved_headless_reason():
    from src.core.vigas_drawing_config import prepare_lv_sources
    source=profile_transition_source()
    marker='Segmento atravessa perfis de montagem distintos; subdividir no SA'
    source['A']['vertical_pending']=marker
    source['B']['vertical_pending']=marker
    prepared=prepare_lv_sources(source,mode='NOVA')
    assert prepared['A']['vertical_pending']==prepared['B']['vertical_pending']==''
    assert source['A']['vertical_pending']==marker
    source['A']['vertical_pending']='Regional slab level absent'
    assert prepare_lv_sources(source,mode='NOVA')['A']['vertical_pending']=='Regional slab level absent'


def test_missing_slab_level_resolves_only_from_complete_uniform_contact():
    from src.core.vigas_drawing_config import resolve_lv_contact_levels
    source = profile_transition_source()
    cell = source['A']['structural_segments'][0]['lv_cell']
    cell['slabs'][0]['level'] = ''
    cell['level_estimado'] = {'origem': 'outro_segmento'}
    before = deepcopy(source)
    slab = dict(name='L1', height=13, nivel=852.24,
                points=[[0,0],[100,0],[100,-50],[0,-50]])
    resolved = resolve_lv_contact_levels(source, [slab])
    actual = resolved['A']['structural_segments'][0]['lv_cell']
    assert actual['slabs'][0]['level'] == 852.24
    assert actual['level'] == 852.24
    assert source == before
    # Same name elsewhere, a partial contact and a conflicting level cannot fill.
    for points in ([[0,-50],[100,-50],[100,-100],[0,-100]],
                   [[0,0],[40,0],[40,-50],[0,-50]]):
        assert resolve_lv_contact_levels(source, [{**slab, 'points':points}]) == before
    assert resolve_lv_contact_levels(source, [slab,{**slab,'nivel':852.19}]) == before
    # A regional inset with no measured level must not inherit the owner value.
    unknown = {**slab, 'slab_steps':[dict(uid='step',points=slab['points'],
               height_cm=13, level_m=None, owner_height_cm=13, owner_level_m=852.24)]}
    assert resolve_lv_contact_levels(source, [unknown]) == before
