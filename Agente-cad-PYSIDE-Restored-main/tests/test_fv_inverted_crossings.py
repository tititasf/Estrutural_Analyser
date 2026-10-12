from copy import deepcopy

import pytest

from src.core.fv_inverted_crossings import extend_normal_soffit, reconcile_state


def scene(axis=0, sign=1):
    def p(x,y):
        return [x,y] if axis==0 else [y,x]
    row=dict(uid='bottom1',beam_name='NORMAL',length=100,
             points=[p(0,0),p(100,0),p(100,19),p(0,19),p(0,0)])
    a,b=(100,119) if sign==1 else (-19,0)
    owner=dict(beam='NORMAL',section_contract=dict(width_cm=19,height_cm=55,base_level_m=851.64,top_level_m=852.19),
               pairs=[dict(footprint=row['points'])])
    crossing=dict(beam='INVERTED',section_contract=dict(beam_type='inverted',
        base_level_m=852.06,top_level_m=853.26,section_semantics=dict(confirmed=True)),
        pairs=[dict(footprint=[p(a,-10),p(b,-10),p(b,30),p(a,30)],
                    start=p((a+b)/2,-10),end=p((a+b)/2,30))])
    lines=[(*p(-19,y),*p(119,y)) for y in (0,19)]
    return row,[owner,crossing],lines


@pytest.mark.parametrize('axis,sign',[(0,1),(0,-1),(1,1),(1,-1)])
def test_far_face_with_real_walls_and_disjoint_levels(axis,sign):
    row,entries,lines=scene(axis,sign)
    before=deepcopy((row,entries))
    result=extend_normal_soffit(row,entries,lines)
    assert result['length']==119
    assert result['normal_inverted_continuations'][0]['to_station_cm']==(119 if sign==1 else -19)
    assert (row,entries)==before


@pytest.mark.parametrize('change', ['missing_level','touching_level','pending','unconfirmed','normal','missing_wall'])
def test_ambiguous_or_colliding_crossing_keeps_source(change):
    row,entries,lines=scene()
    if change=='missing_level': entries[0]['section_contract'].pop('base_level_m')
    if change=='touching_level': entries[0]['section_contract']['base_level_m']=852.06
    if change=='pending': entries[1]['pending']=True
    if change=='unconfirmed': entries[1]['section_contract']['section_semantics']['confirmed']=False
    if change=='normal': entries[1]['section_contract']['beam_type']='normal'
    if change=='missing_wall': lines=lines[:1]
    assert extend_normal_soffit(row,entries,lines)==row


def test_conflicting_local_sections_do_not_supply_partial_permission():
    row,entries,lines=scene()
    conflict=deepcopy(entries[1]); conflict['pending']=True
    assert extend_normal_soffit(row,entries+[conflict],lines)==row


def test_support_arrival_is_allowed_but_passing_support_is_not():
    row,entries,lines=scene()
    support=dict(points=[[100,0],[119,0],[119,19],[100,19]])
    assert extend_normal_soffit(row,entries,lines,[support])['length']==119
    support['points'][1][0]=130; support['points'][2][0]=130
    assert extend_normal_soffit(row,entries,lines,[support])==row


def test_reconcile_preserves_identity_count_and_does_not_overlap_other_panel():
    row,entries,lines=scene()
    state=dict(segmentos=dict(fundo=[row]))
    inventory=dict(physical_entries=entries)
    result=reconcile_state(state,inventory,lines)
    assert len(result['segmentos']['fundo'])==1
    assert result['segmentos']['fundo'][0]['uid']==row['uid']
    assert reconcile_state(result,inventory,lines)==result
    other=deepcopy(row); other.update(uid='bottom2',points=[[105,0],[140,0],[140,19],[105,19]])
    state['segmentos']['fundo'].append(other)
    assert reconcile_state(state,inventory,lines)['segmentos']['fundo'][0]==row


def test_validated_geometry_is_not_replaced():
    row,entries,lines=scene(); row['geometry_validated']=True
    assert extend_normal_soffit(row,entries,lines)==row


def test_manual_sidecar_geometry_is_preserved():
    row,entries,lines=scene()
    state=dict(segmentos=dict(fundo=[row]))
    assert reconcile_state(state,dict(physical_entries=entries),lines,[row['uid']])==state


def test_opposite_ends_merge_without_overlapping_or_losing_the_gap():
    row,entries,lines=scene()
    other=deepcopy(row);other.update(uid='bottom2',points=[[119,0],[200,0],[200,19],[119,19]])
    entries[0]['pairs'].append(dict(footprint=other['points']))
    lines=[(0,0,200,0),(0,19,200,19)]
    state=dict(segmentos=dict(fundo=[row,other]))
    before=deepcopy(state)
    result=reconcile_state(state,dict(physical_entries=entries),lines)
    assert state==before
    merged=result['segmentos']['fundo']
    assert len(merged)==1
    assert merged[0]['length']==200
    assert merged[0]['merged_source_uids']==['bottom1','bottom2']
    assert reconcile_state(result,dict(physical_entries=entries),lines)==result


@pytest.mark.parametrize('failure',['pillar','manual','missing_wall','height_change','explicit_level_change'])
def test_merging_requires_unobstructed_matching_section(failure):
    row,entries,lines=scene()
    other=deepcopy(row);other.update(uid='bottom2',points=[[119,0],[200,0],[200,19],[119,19]])
    owner=deepcopy(entries[0]);owner['pairs']=[dict(footprint=other['points'])]
    entries.append(owner)
    lines=[(0,0,200,0),(0,19,200,19)]
    state=dict(segmentos=dict(fundo=[row,other]))
    protected=[]
    if failure=='pillar': state['pilares']=[dict(points=[[100,0],[119,0],[119,19],[100,19]])]
    if failure=='manual': protected=[row['uid']]
    if failure=='missing_wall': lines=lines[:1]
    if failure=='height_change': owner['section_contract']['height_cm']=71
    if failure=='explicit_level_change':
        row.update(level='852.12',level_source='explicit_beam_or_side')
        other.update(level='852.19',level_source='explicit_beam_or_side')
    result=reconcile_state(state,dict(physical_entries=entries),lines,protected)
    assert len(result['segmentos']['fundo'])==2


def test_neighbor_slab_levels_are_preserved_as_unresolved_not_invented():
    row,entries,lines=scene()
    row.update(level='852.12',level_source='highest_touching_slab')
    other=deepcopy(row);other.update(uid='bottom2',level='852.19',points=[[119,0],[200,0],[200,19],[119,19]])
    entries[0]['pairs'].append(dict(footprint=other['points']))
    result=reconcile_state(dict(segmentos=dict(fundo=[row,other])),dict(physical_entries=entries),[(0,0,200,0),(0,19,200,19)])
    merged=result['segmentos']['fundo'][0]
    assert merged['level']==''
    assert [r['level'] for r in merged['merged_source_segments']]==['852.12','852.19']


def _cut_contract(footprint, top, base, drop):
    return dict(beam='NORMAL', pairs=[dict(footprint=footprint)], section_contract=dict(
        width_cm=19, height_cm=55, top_level_m=top, base_level_m=base,
        vertical_datum_source='original_cut_datum', slabs=dict(A=[dict(drop_cm=drop)], B=[])))


@pytest.mark.parametrize('case',['proven','one_side_only','different_base'])
def test_union_level_is_decided_by_the_beam_cut_on_both_sides(case):
    # VF301 seg 8 (13_PAV): 7 + 48 sobre 852,12 e 0 + 55 sob 852,19 = mesmo fundo 851,64.
    row,entries,lines=scene()
    row.update(level='852.12',level_source='highest_touching_slab',level_slabs=['L308'])
    other=deepcopy(row);other.update(uid='bottom2',level='852.19',level_slabs=['L317'],
                                     points=[[119,0],[200,0],[200,19],[119,19]])
    entries[0]['pairs'].append(dict(footprint=other['points']))
    presented=[_cut_contract(row['points'],852.19,851.64,7)]
    if case!='one_side_only':
        presented.append(_cut_contract(other['points'],852.19,851.64 if case=='proven' else 851.57,0))
    inventory=dict(physical_entries=entries,entries=presented)
    merged=reconcile_state(dict(segmentos=dict(fundo=[row,other])),inventory,[(0,0,200,0),(0,19,200,19)])['segmentos']['fundo'][0]
    if case=='proven':
        assert (merged['level'],merged['level_source'],merged['level_slabs'])==('852.19','highest_touching_slab',['L317'])
        assert merged['level_proof']['base_level_m']==851.64
        assert 'attention' not in merged
    else:
        assert merged['level']=='' and merged['level_source']=='unresolved_local_slab_references'
