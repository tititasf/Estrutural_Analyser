from copy import deepcopy
import pytest
from test_fv_inverted_crossings import scene
from src.core.lv_inverted_crossings import propose, reconcile_state, overlay_beam, _blocks


def lateral_scene(axis=0, sign=1):
    bottom, entries, lines = scene(axis,sign)
    for entry in entries:
        inverted = entry['beam']=='INVERTED'
        entry['section_contract']['mounting'] = {
            s: dict(panel_base_cm=15 if inverted else -4, panel_top_cm=120 if inverted else 40)
            for s in ('A','B')}
    row = dict(bottom,uid='lateral_a_passa|beam-id|1|1', side='A', points=bottom['points'][:2],
        lv_cell=dict(depth=55,dim='19/55',level='852.19',sobre_cota=0,slabs=[],
            pillar_openings=[],beam_openings=[]))
    return row,entries,lines


@pytest.mark.parametrize('axis,sign',[(0,1),(0,-1),(1,1),(1,-1)])
def test_disjoint_lateral_levels_and_two_actual_walls(axis,sign):
    row,entries,lines=lateral_scene(axis,sign)
    before=deepcopy((row,entries))
    assert propose(row,entries,lines)['length']==119
    assert (row,entries)==before


@pytest.mark.parametrize('failure',['missing_mount','overlap','missing_wall','manual'])
def test_unsafe_crossing_preserves_source(failure):
    row,entries,lines=lateral_scene()
    if failure=='missing_mount': entries[1]['section_contract'].pop('mounting')
    if failure=='overlap':
        entries[1]['section_contract']['base_level_m']=851.8
        entries[1]['section_contract']['mounting']['A']['panel_base_cm']=0
    if failure=='missing_wall': lines=lines[:1]
    if failure=='manual': row['geometry_validated']=True
    assert propose(row,entries,lines)==row


def test_only_independently_matching_slab_band_is_ignored():
    normal=dict(base_level_m=851.57,top_level_m=852.12,
        mounting={'B':dict(panel_base_cm=-4,panel_top_cm=55)},
        slabs={'A':[dict(height_cm=13,drop_cm=0)]})
    inverted=dict(base_level_m=851.99,top_level_m=852.70,
        mounting={s:dict(panel_base_cm=0,panel_top_cm=71) for s in ('A','B')},
        slabs={'A':[dict(height_cm=13,drop_cm=58)]})
    assert not _blocks(normal,inverted,'B')
    inverted['slabs']['A'][0]['drop_cm']=57
    assert _blocks(normal,inverted,'B')
    inverted['slabs']['A'][0]['drop_cm']=58
    normal['mounting']['B']['panel_top_cm']=56
    assert _blocks(normal,inverted,'B')


def test_union_keeps_opening_positions_and_n3_conversion_immutable():
    row,entries,lines=lateral_scene()
    row['lv_cell']['pillar_openings']=[dict(name='P1',pos_inicio=20,pos_fim=39,abertura=41)]
    other=deepcopy(row)
    other.update(uid='lateral_a_passa|beam-id|2|1', points=[[119,0],[200,0]])
    other['lv_cell']['pillar_openings']=[dict(name='P2',pos_inicio=10,pos_fim=29,abertura=41)]
    entries[0]['pairs'].append(dict(footprint=[[119,0],[200,0],[200,19],[119,19]]))
    state=dict(segmentos=dict(lateral_a_passa=[row,other]))
    before=deepcopy(state)
    result=reconcile_state(state,dict(physical_entries=entries),[(0,0,200,0),(0,19,200,19)])
    assert state==before
    merged=result['segmentos']['lateral_a_passa']
    assert len(merged)==1 and merged[0]['length']==200
    assert [o['pos_inicio'] for o in merged[0]['lv_cell']['pillar_openings']]==[20,129]
    assert reconcile_state(result,dict(physical_entries=entries),lines)==result
    record=dict(name='NORMAL',links={})
    projected=overlay_beam(record,result)
    assert record==dict(name='NORMAL',links={})
    assert projected['links']['viga_a_seg_1_comp_total_passa']['seg_side_a'][0]['len']==200
    assert projected['links']['viga_a_seg_2_comp_total_passa']['seg_side_a']==[]


def test_incompatible_opposite_arrivals_do_not_create_overlapping_panels():
    row,entries,lines=lateral_scene()
    other=deepcopy(row)
    other.update(uid='lateral_a_passa|beam-id|2|1',points=[[119,0],[200,0]])
    other['lv_cell']['depth']=71
    entries[0]['pairs'].append(dict(footprint=[[119,0],[200,0],[200,19],[119,19]]))
    state=dict(segmentos=dict(lateral_a_passa=[row,other]))
    assert reconcile_state(state,dict(physical_entries=entries),[(0,0,200,0),(0,19,200,19)])==state


@pytest.mark.parametrize('failure',[None,'explicit_level','step','different_datum','unknown_datum'])
def test_slab_scalar_disagreement_requires_continuous_paired_datum(failure):
    row,entries,lines=lateral_scene()
    row['level_source']='lv_cell_slabs'
    other=deepcopy(row)
    other.update(uid='lateral_a_passa|beam-id|2|1',points=[[119,0],[200,0]])
    other['lv_cell']['level']='852.12'
    pair=entries[0]['pairs'][0]
    pair.update(a_id=row['uid'],profiles={'B':{'level':852.12}})
    entries[0]['pairs'].append(dict(footprint=[[119,0],[200,0],[200,19],[119,19]],
        a_id=other['uid'],profiles={'B':{'level':852.12}}))
    if failure=='explicit_level': other['level_source']='original_dimension'
    if failure=='step': other['lv_cell']['support_start']={'type':'degrau_laje'}
    if failure=='different_datum': entries[0]['pairs'][1]['profiles']['B']['level']=852.19
    if failure=='unknown_datum': entries[0]['pairs'][1]['profiles']['B']['level']=None
    state=dict(segmentos=dict(lateral_a_passa=[row,other]))
    result=reconcile_state(state,dict(physical_entries=entries),[(0,0,200,0),(0,19,200,19)])
    if failure:
        assert result==state
    else:
        merged=result['segmentos']['lateral_a_passa']
        assert len(merged)==1 and merged[0]['length']==200
        assert [s['level'] for s in merged[0]['lv_cell']['source_level_sections']]==['852.19','852.12']
        assert reconcile_state(result,dict(physical_entries=entries),lines)==result


def test_a_real_pillar_in_crossing_still_stops_lateral():
    row,entries,lines=lateral_scene()
    assert propose(row,entries,lines,[dict(points=[[100,-1],[120,-1],[120,20],[100,20]])])==row


@pytest.mark.parametrize('axis,sign',[(0,1),(0,-1),(1,1),(1,-1)])
def test_arrival_at_far_pillar_face_crosses_disjoint_inverted_beam(axis,sign):
    row,entries,lines=lateral_scene(axis,sign)
    points=[[sign*x,y] if axis==0 else [y,sign*x]
            for x,y in ((100,-1),(119,-1),(119,20),(100,20))]
    assert propose(row,entries,lines,[dict(points=points)])['length']==119


def test_proven_continuation_removes_only_crossing_beam_opening():
    row,entries,lines=lateral_scene()
    incident=entries[1]['beam']
    row['lv_cell']['beam_openings']=[
        dict(name=incident,pos_inicio=100,pos_fim=119),
        dict(name=incident,pos_inicio=20,pos_fim=39),
        dict(name='OTHER',pos_inicio=100,pos_fim=119)]
    result=reconcile_state(dict(segmentos=dict(lateral_a_passa=[row])),
                           dict(physical_entries=entries),lines)
    openings=result['segmentos']['lateral_a_passa'][0]['lv_cell']['beam_openings']
    assert [(o['name'],o['pos_inicio']) for o in openings]==[(incident,20),('OTHER',100)]


def inverted_owner_scene(axis=0):
    p=lambda x,y: [x,y] if axis==0 else [y,x]
    contract=dict(beam_type='inverted',form_role='top_cap',width_cm=19,height_cm=120,
        base_level_m=852.06,top_level_m=853.26,section_semantics=dict(confirmed=True),
        mounting={s:dict(panel_base_cm=15,panel_top_cm=120,h1_cm=105) for s in ('A','B')})
    owner=dict(beam='UP',section_contract=contract,
        pairs=[dict(start=p(0,0),end=p(200,0))])
    lower=dict(beam='DOWN',section_contract=dict(beam_type='normal',base_level_m=851.64,
        mounting={s:dict(panel_base_cm=-4,panel_top_cm=55) for s in ('A','B')}),
        pairs=[dict(footprint=[p(90,0),p(110,0),p(110,19),p(90,19)])])
    rows=[]
    for index,(lo,hi) in enumerate(((0,100),(100,200)),1):
        rows.append(dict(uid=f'lateral_a_passa|up|{index}|1',beam_name='UP',side='A',
            points=[p(lo,0),p(hi,0)],length=100,
            lv_cell=dict(depth=120,dim='19/120',pillar_openings=[dict(name='P',pos_inicio=20,largura=10)],
                beam_openings=[dict(name='DOWN',pos_inicio=90 if index==1 else 0,largura=10)],
                support_start=dict(type='viga' if index==2 else 'extremidade',name='DOWN'),
                support_end=dict(type='viga' if index==1 else 'extremidade',name='DOWN'))))
    return dict(segmentos=dict(lateral_a_passa=rows)),dict(physical_entries=[owner,lower])


@pytest.mark.parametrize('axis',[0,1])
def test_inverted_owner_merges_lower_crossing_keeps_pillars_and_source(axis):
    state,inventory=inverted_owner_scene(axis)
    before=deepcopy(state)
    result=reconcile_state(state,inventory,[])
    rows=result['segmentos']['lateral_a_passa']
    assert len(rows)==1 and rows[0]['length']==200
    assert [o['pos_inicio'] for o in rows[0]['lv_cell']['pillar_openings']]==[20,120]
    assert rows[0]['lv_cell']['beam_openings']==[]
    assert state==before and reconcile_state(result,inventory,[])==result


def test_inverted_owner_merge_keeps_slabs_of_both_cells():
    # V330 2-A (13_PAV): L308 de um lado do cruzamento, L316 do outro.
    state,inventory=inverted_owner_scene()
    for row,name in zip(state['segmentos']['lateral_a_passa'],('L308','L316')):
        row['lv_cell']['slabs']=[dict(name=name,height=13)]
    rows=reconcile_state(state,inventory,[])['segmentos']['lateral_a_passa']
    assert len(rows)==1 and [s['name'] for s in rows[0]['lv_cell']['slabs']]==['L308','L316']


@pytest.mark.parametrize('reason',['step','height','collision','unknown','manual'])
def test_inverted_owner_keeps_real_or_unconfirmed_seam(reason):
    state,inventory=inverted_owner_scene()
    row=state['segmentos']['lateral_a_passa'][1]
    if reason=='step': row['lv_cell']['support_start']['type']='degrau_laje'
    if reason=='height': row['lv_cell']['depth']=71
    if reason=='collision': inventory['physical_entries'][1]['section_contract']['base_level_m']=852.2
    if reason=='unknown': inventory['physical_entries'][1]['section_contract'].pop('mounting')
    if reason=='manual': row['geometry_validated']=True
    assert reconcile_state(state,inventory,[])==state
