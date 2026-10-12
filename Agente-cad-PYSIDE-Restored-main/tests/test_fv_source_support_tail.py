import copy
import pytest
from shapely.geometry import box
from src.core.pillar_geometry_recovery import reconcile_pillar_source_geometry
from src.core.lv_beam_scene import build_scene_runs, LvScene

@pytest.mark.parametrize('offset',[0,3000])
@pytest.mark.parametrize('protected',[False,True])
def test_named_pillar_dimension_rejects_nearby_beam_rectangle(offset,protected):
    o=offset
    good=list(box(o+100,o,o+240,o+19).exterior.coords)
    wrong=list(box(o+119,o-71,o+134,o).exterior.coords)
    report={'P88':{'name':'P88','points':wrong,'is_validated':protected}}
    before=copy.deepcopy(report)
    texts=[{'text':'P88','pos':[o+140,o+40],'height':10},
           {'text':'19/140','pos':[o+140,o+25],'height':10}]
    source=[{'points':good,'layer':'PILAR-SEGUE'},{'points':wrong,'layer':'FACE-VIGA'}]
    repaired=reconcile_pillar_source_geometry(report,source,texts)
    if protected:assert report==before;assert not repaired
    else:assert report['P88']['points']==[list(p) for p in good];assert repaired

@pytest.mark.parametrize('leader',[True,False])
@pytest.mark.parametrize('offset',[0,3000])
def test_tail_needs_two_actual_walls_and_matching_section_leader(monkeypatch,leader,offset):
    import src.core.lv_beam_scene as scene
    o=offset
    main=LvScene('V88',True,o+1.5,o+20.5,o-100,o)
    main.face_coverage={'A':[[-100+o,o]],'B':[[-100+o,o]]}
    monkeypatch.setattr(scene,'build_band_scene',lambda *a,**kw:main)
    monkeypatch.setattr(scene,'_sections',lambda *a:None)
    texts=[{'text':'V88','pos':[o-50,o+30],'rotation':0},
           {'text':'22/50','pos':[o+50,o-20],'height':5,'rotation':0}]
    lines=[{'points':[(o+100,o),(o+110,o)]},
           {'points':[(o+100,o+22),(o+110,o+22)]}]
    if leader:lines.append({'points':[(o+50,o-20),(o+105,o),(o+102,o-3)]})
    pillars={'P88':{'name':'P88','classification':'SEGUE','points':list(box(o,o,o+100,o+22).exterior.coords)}}
    runs=build_scene_runs([{'name':'V88'}],texts,lines,pillars)
    tails=[r for r in runs['V88'] if r.provenance.get('band_source')=='source_walls_opposite_support_tail']
    assert len(tails)==int(leader)
    if tails:assert tails[0].width==22;assert tails[0].end-tails[0].start==10
