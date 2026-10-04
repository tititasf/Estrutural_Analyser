from copy import deepcopy

import pytest

from src.core.fv_inverted_crossings import extend_normal_soffit, reconcile_state


def scene(axis=0, sign=1):
    def p(x,y):
        return [x,y] if axis==0 else [y,x]
    row=dict(uid='bottom1',beam_name='NORMAL',length=100,
             points=[p(0,0),p(100,0),p(100,19),p(0,19),p(0,0)])
    a,b=(100,119) if sign==1 else (-19,0)
    owner=dict(beam='NORMAL',section_contract=dict(base_level_m=851.64,top_level_m=852.19),
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


def test_opposite_ends_cannot_both_claim_a_crossing_gap():
    row,entries,lines=scene()
    other=deepcopy(row);other.update(uid='bottom2',points=[[119,0],[200,0],[200,19],[119,19]])
    entries[0]['pairs'].append(dict(footprint=other['points']))
    lines=[(0,0,200,0),(0,19,200,19)]
    state=dict(segmentos=dict(fundo=[row,other]))
    assert reconcile_state(state,dict(physical_entries=entries),lines)==state
