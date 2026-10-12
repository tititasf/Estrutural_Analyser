import pytest
from shapely.geometry import box
from src.core.lv_beam_scene import LvScene, _EdgeIndex, _recover_unlabelled_support_spans


@pytest.mark.parametrize('horizontal',[True,False])
@pytest.mark.parametrize('offset',[0,8000])
@pytest.mark.parametrize('guard',['none','section','wall','name','protected','ambiguous','support'])
def test_unlabelled_span_needs_unique_adjacent_section_and_source_walls(horizontal,offset,guard):
    o=offset
    xy=lambda a,t:(o+a,o+t) if horizontal else (o+t,o+a)
    run=LvScene('V88',horizontal,o,o+19,o,o+100)
    run.sections=[dict(start=o,end=o+100,dim='19/50')]
    lines=[(*xy(119,0),*xy(300,0))]
    if guard!='wall':lines.append((*xy(119,19),*xy(300,19)))
    support=run.rect(o+100,o+119,o,o+(9 if guard=='support' else 19))
    pillars=[('P88','SEGUE',support),('P89','SEGUE',run.rect(o+300,o+319,o,o+19))]
    text=dict(text='19/65' if guard=='section' else '19/50',section=(19,65 if guard=='section' else 50),
              pos=xy(180,26.5),rotation=0 if horizontal else 90,height=10)
    runs={'V88':[run]};beams={'V88':dict(name='V88',is_validated=guard=='protected')}
    labels=[dict(text='V99',pos=xy(180,26.5),rotation=text['rotation'])] if guard=='name' else []
    if guard=='ambiguous':
        other=LvScene('V99',horizontal,o,o+19,o+319,o+400)
        other.sections=[dict(start=o+319,end=o+400,dim='19/50')]
        runs['V99']=[other];beams['V99']={'name':'V99'}
    _recover_unlabelled_support_spans(runs,beams,_EdgeIndex(lines),[text],[],labels,pillars)
    assert len(runs['V88'])==(2 if guard=='none' else 1)
    if guard=='none':
        added=runs['V88'][1]
        assert added.start==pytest.approx(o+119)
        assert added.end==pytest.approx(o+300)
        assert added.sections[0]['dim']=='19/50'


@pytest.mark.parametrize('horizontal',[True,False])
@pytest.mark.parametrize('offset',[0,8000])
@pytest.mark.parametrize('guard',['none','depth','common_wall','support','missing_wall','name','protected','detached'])
def test_width_transition_clips_source_extent_at_opposite_solid_face(horizontal,offset,guard):
    o=offset
    xy=lambda a,t:(o+a,o+t) if horizontal else (o+t,o+a)
    run=LvScene('V88',horizontal,o,o+14,o,o+100)
    run.sections=[dict(start=o,end=o+100,dim='14/55')]
    lower=5 if guard=='common_wall' else 0
    # The wider source pair includes a piece of the known narrow run: this
    # reproduces support-edge coverage preceding the actual new span.
    first=130 if guard=='detached' else 80
    lines=[(*xy(first,lower),*xy(350,lower))]
    if guard!='missing_wall':lines.append((*xy(first,19+lower),*xy(350,19+lower)))
    support=run.rect(o+100,o+119,o,o+(14 if guard=='support' else 19+lower))
    pillars=[('P88','SEGUE',support)]
    text=dict(text='19/60' if guard=='depth' else '19/55',section=(19,60 if guard=='depth' else 55),
              pos=xy(180,26.5+lower),rotation=0 if horizontal else 90,height=10)
    label=dict(text='V99' if guard=='name' else 'V88',pos=xy(125,-20+lower),rotation=text['rotation'])
    runs={'V88':[run]};beams={'V88':dict(name='V88',is_validated=guard=='protected')}
    _recover_unlabelled_support_spans(runs,beams,_EdgeIndex(lines),[text],[],[label],pillars)
    assert len(runs['V88'])==(2 if guard=='none' else 1)
    if guard=='none':
        added=runs['V88'][1]
        assert (added.start,added.end)==pytest.approx((o+119,o+350))
        assert added.width==pytest.approx(19)
        assert added.sections[0]['dim']=='19/55'
        assert added.provenance['support']=='P88'
        assert added.world_band().intersection(run.world_band()).area==0


@pytest.mark.parametrize('candidate_start',[80,110])
def test_same_width_recovery_does_not_expand_old_extent_or_overlap_policy(candidate_start):
    run=LvScene('V88',True,0,19,0,100)
    run.sections=[dict(start=0,end=100,dim='19/55')]
    lines=[(candidate_start,0,350,0),(candidate_start,19,350,19)]
    text=dict(text='19/55',section=(19,55),pos=(180,26.5),rotation=0,height=10)
    runs={'V88':[run]}
    _recover_unlabelled_support_spans(runs,{'V88':{'name':'V88'}},_EdgeIndex(lines),[text],[],[],
                                    [('P88','SEGUE',box(100,0,119,19))])
    assert len(runs['V88'])==1
