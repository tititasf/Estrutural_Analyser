import pytest
from src.core.lv_cut_inventory import pair_sections


@pytest.mark.parametrize('vertical',[False,True])
@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('side',['A','B'])
def test_opening_only_occupies_its_real_interval(vertical,reverse,side):
    def segment(s,y):
        pts=[[0,y],[300,y]]
        if vertical: pts=[[y,x] for x,y in pts]
        if reverse: pts.reverse()
        return dict(id=s,index=1,points=pts,width_cm=19,beam_height_cm=55,level=8.5)
    a,b=segment('A',0),segment('B',19)
    (a if side=='A' else b)['beam_openings']=[dict(name='W',position_cm=20,width_cm=40)]
    cuts,diag=pair_sections('V','passa',{'A':{'segments':[a]},'B':{'segments':[b]}})
    assert len(cuts)==1  # Real absence of slab remains a legitimate section.
    assert sum(p['length_cm'] for c in cuts for p in c['pairs'])==pytest.approx(260)
    assert sum(e['length_cm'] for e in diag['opening_exclusions'])==pytest.approx(40)
    excluded=diag['opening_exclusions'][0]
    axis=1 if vertical else 0
    assert sorted([excluded['start'][axis],excluded['end'][axis]])==([240,280] if reverse else [20,60])
    assert diag['coverage_gaps']==[]
    assert diag['conflicts']==[]


def test_opposite_sides_with_reversed_reading_and_coincident_openings_do_not_double_count():
    a=dict(id='A',index=1,points=[[0,0],[100,0]],width_cm=19,beam_height_cm=55,level=8.5,
           beam_openings=[dict(position_cm=20,width_cm=40)])
    b=dict(id='B',index=1,points=[[100,19],[0,19]],width_cm=19,beam_height_cm=55,level=8.5,
           beam_openings=[dict(position_cm=40,width_cm=40)])
    cuts,diag=pair_sections('V','passa',{'A':{'segments':[a]},'B':{'segments':[b]}})
    assert sum(e['length_cm'] for e in diag['opening_exclusions'])==40
    assert sum(p['length_cm'] for c in cuts for p in c['pairs'])==60
    assert len(diag['opening_exclusions'][0]['openings'])==2


def test_entire_pair_inside_opening_adds_no_common_cut():
    a=dict(id='A',index=1,points=[[0,0],[14,0]],width_cm=19,beam_height_cm=55,level=8.5,
           beam_openings=[dict(position_cm=0,width_cm=14)])
    b=dict(id='B',index=1,points=[[0,19],[14,19]],width_cm=19,beam_height_cm=55,level=8.5)
    cuts,diag=pair_sections('V','passa',{'A':{'segments':[a]},'B':{'segments':[b]}})
    assert cuts==[]
    assert diag['pairs']==0
    assert diag['coverage_gaps']==[]


@pytest.mark.parametrize('position,width,excluded',[(-.02,14,13.98),(-10,30,20),(-20,10,0)])
def test_opening_start_outside_segment_is_clipped_to_physical_contact(position,width,excluded):
    a=dict(id='A',index=1,points=[[0,0],[49,0]],width_cm=19,beam_height_cm=55,level=8.5)
    b=dict(id='B',index=1,points=[[49,19],[0,19]],width_cm=19,beam_height_cm=55,level=8.5,
           beam_openings=[dict(position_cm=position,width_cm=width)])
    cuts,diag=pair_sections('V','passa',{'A':{'segments':[a]},'B':{'segments':[b]}})
    assert sum(e['length_cm'] for e in diag['opening_exclusions'])==pytest.approx(excluded)
    assert sum(p['length_cm'] for c in cuts for p in c['pairs'])==pytest.approx(49-excluded)
    assert diag['coverage_gaps']==[]
