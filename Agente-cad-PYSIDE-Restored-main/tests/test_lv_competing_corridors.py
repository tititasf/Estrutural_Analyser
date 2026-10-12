import pytest
from src.core.lv_beam_scene import build_scene_runs

def fixture(vertical=False, pillars=True, parallel=False):
    def point(x,y):
        return (y,x) if vertical else (x,y)
    lines=[{'points':[point(0,y),point(1000,y)]} for y in (0,19)]
    labels=[{'text':'V1','pos':point(100,-20),'rotation':90 if vertical else 0},
            {'text':'V2','pos':point(1100,-20),'rotation':90 if vertical else 0}]
    if parallel:
        lines += [{'points':[point(0,y),point(1000,y)]} for y in (45,64)]
        labels[1]['pos']=point(800,70)
    supports={f'P{i}':{'name':f'P{i}','points':[point(x,-30),point(x+20,-30),point(x+20,80),point(x,80)]}
              for i,x in enumerate((300,700),1)} if pillars else {}
    return build_scene_runs([{'name':'V1'},{'name':'V2'}],labels,lines,supports)

@pytest.mark.parametrize('vertical',[False,True])
def test_offset_label_beyond_measured_endpoint_splits_at_interior_label_pillar(vertical):
    runs=fixture(vertical)
    assert (runs['V1'][0].start,runs['V1'][0].end)==(0,300)
    # The distant V2 text must not choose P2 and discard a legitimate span.
    assert (runs['V2'][0].start,runs['V2'][0].end)==(320,1000)

def test_offset_competitor_on_parallel_measured_band_cannot_trim_owner():
    runs=fixture(parallel=True)
    assert (runs['V1'][0].start,runs['V1'][0].end)==(0,1000)
    assert (runs['V2'][0].t_lo,runs['V2'][0].t_hi)==(45,64)

def test_offset_labels_without_solid_partition_do_not_invent_boundary():
    runs=fixture(pillars=False)
    assert (runs['V1'][0].start,runs['V1'][0].end)==(0,1000)
    assert (runs['V2'][0].start,runs['V2'][0].end)==(0,1000)

def test_repeated_name_does_not_become_competitor():
    labels=[{'text':'V1','pos':(100,-20),'rotation':0},
            {'text':'V1','pos':(800,-20),'rotation':0}]
    runs=build_scene_runs([{'name':'V1'}],labels,[{'points':[(0,y),(1000,y)]} for y in (0,19)],{})
    assert len(runs['V1'])==1
    assert (runs['V1'][0].start,runs['V1'][0].end)==(0,1000)
