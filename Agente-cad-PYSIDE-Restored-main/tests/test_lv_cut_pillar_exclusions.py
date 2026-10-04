import pytest
from src.core.lv_cut_inventory import pair_sections


@pytest.mark.parametrize('vertical',[False,True])
def test_support_is_removed_from_pairs_not_mistaken_for_bare_section(vertical):
    def pts(values):
        return [[y,x] for x,y in values] if vertical else values
    sides={s:{'segments':[dict(id=s,index=1,points=pts([[0,y],[300,y]]),
            width_cm=19,beam_height_cm=55,level=8.5)]} for s,y in [('A',0),('B',19)]}
    pillar=dict(name='P',points=pts([[130,-5],[170,-5],[170,25],[130,25]]))
    cuts,diag=pair_sections('V','passa',sides,pillars=[pillar])
    assert len(cuts)==1
    assert sorted(p['length_cm'] for p in cuts[0]['pairs'])==[130,130]
    assert diag['pillar_exclusions'][0]['length_cm']==40
    assert diag['coverage_gaps']==[]


def test_pair_entirely_on_pillar_is_not_published():
    sides={s:{'segments':[dict(id=s,index=1,points=[[0,y],[19,y]],
            width_cm=19,beam_height_cm=55,level=8.5)]} for s,y in [('A',0),('B',19)]}
    cuts,diag=pair_sections('V','passa',sides,pillars=[dict(name='P',points=[[-1,-1],[20,-1],[20,20],[-1,20]])])
    assert not cuts
    assert not diag['coverage_gaps']
