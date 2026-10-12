from copy import deepcopy
import pytest
import src.core.lv_beam_scene as scene
import src.core.beam_interpreters.fundo_viga_lateral_ref as fv
from shapely.geometry import Polygon


def setup(monkeypatch, coverage=1.0):
    angular=scene.LvScene('V900',True,0,19,0,100,angle=45)
    angular.face_extent={'A':(0,100),'B':(0,100)}
    angular.face_coverage={'A':[[0,100]],'B':[[0,100*coverage]]}
    cap=scene.LvScene('V900',False,200,219,0,30)
    cap.face_coverage={'A':[[0,30]],'B':[[0,30]]}
    monkeypatch.setattr(scene,'build_scene_runs',lambda *args,**kwargs:{'V900':[angular,cap]})
    pts=[[200,0],[219,0],[219,30],[200,30],[200,0]]
    beam={'name':'V900','fv_is_h':False,'pos':[200,0],'fields':{'dimensao':'19/55'},'links':{'viga_fundo_seg_1_area_segs':{'contour':[{'type':'poly','closed':True,'points':pts}]}}}
    return beam,angular


def test_orthogonal_return_does_not_block_witnessed_diagonal(monkeypatch):
    beam,angular=setup(monkeypatch)
    fv.apply_lateral_reference_all([beam],[],[],{})
    panels=fv._panels(beam)
    assert len(panels)==2
    assert any(link.get('geometry_source','').endswith('_special_diagonal') and poly.area==pytest.approx(1900) for _,link,poly in panels)
    assert any(poly.bounds==(200,0,219,30) for _,_,poly in panels)


def test_human_return_preserves_entire_beam(monkeypatch):
    beam,_=setup(monkeypatch)
    beam['links']['viga_fundo_seg_1_area_segs']['contour'][0]['validated']=True
    before=deepcopy(beam['links'])
    fv.apply_lateral_reference_all([beam],[],[],{})
    assert beam['links']==before


def test_diagonal_without_two_real_walls_remains_missing(monkeypatch):
    beam,_=setup(monkeypatch,coverage=.4)
    fv.apply_lateral_reference_all([beam],[],[],{})
    assert not any(link.get('geometry_source','').endswith('_special_diagonal') for _,link,_ in fv._panels(beam))


def test_existing_chamfered_diagonal_is_preserved(monkeypatch):
    beam,angular=setup(monkeypatch)
    pts=[angular.to_world(x,y) for x,y in [(0,0),(100,0),(100,14),(95,19),(0,19),(0,0)]]
    beam['links']['viga_fundo_seg_2_area_segs']={'contour':[{'type':'poly','closed':True,'points':[list(p) for p in pts],'geometry_source':'physical_chamfer'}]}
    expected=Polygon(pts)
    fv.apply_lateral_reference_all([beam],[],[],{})
    rich=[poly for _,link,poly in fv._panels(beam) if link.get('geometry_source')=='physical_chamfer']
    assert len(rich)==1 and rich[0].equals_exact(expected,1e-8)
    assert not any(link.get('geometry_source','').endswith('_special_diagonal') for _,link,_ in fv._panels(beam))


def labels_for(angular):
    return [{'text':'V900','handle':'NAME_DIAGONAL','pos':list(angular.to_world(50,9.5)),'rotation':45},
            {'text':'V900','handle':'NAME_RETURN','pos':[209.5,15],'rotation':90}]


def test_disconnected_named_mixed_occurrences_recover_only_locally_named_diagonal(monkeypatch):
    # Source evidence now distinguishes two disconnected namesakes: a
    # remote orthogonal label cannot veto a locally labelled measured run.
    # The remote-only counterproof lives in test_fv_angular_component_identity.
    beam,angular=setup(monkeypatch)
    report=fv.apply_lateral_reference_all([beam],labels_for(angular),[],{})
    assert len(fv._panels(beam))==2
    assert 'angular_identity_pending' not in report['V900']
    assert report['V900']['angular_local_identity'][0]['label_handles']==['NAME_DIAGONAL']
    assert any(link.get('geometry_source','').endswith('_special_diagonal') for _,link,_ in fv._panels(beam))


def test_single_named_occurrence_recovers_with_unnamed_return(monkeypatch):
    beam,angular=setup(monkeypatch)
    report=fv.apply_lateral_reference_all([beam],labels_for(angular)[:1],[],{})
    assert 'angular_identity_pending' not in report['V900']
    assert any(link.get('geometry_source','').endswith('_special_diagonal') for _,link,_ in fv._panels(beam))


def test_multiple_labels_in_same_angular_component_do_not_defer(monkeypatch):
    beam,angular=setup(monkeypatch)
    labels=[{'text':'V900','pos':list(angular.to_world(x,9.5)),'rotation':45} for x in (25,75)]
    report=fv.apply_lateral_reference_all([beam],labels,[],{})
    assert 'angular_identity_pending' not in report['V900']
    assert any(link.get('geometry_source','').endswith('_special_diagonal') for _,link,_ in fv._panels(beam))


def test_disconnected_collinear_named_occurrences_do_not_defer(monkeypatch):
    beam,angular=setup(monkeypatch)
    second=scene.LvScene('V900',True,0,19,200,300,angle=45)
    second.face_coverage={'A':[[200,300]],'B':[[200,300]]}
    monkeypatch.setattr(scene,'build_scene_runs',lambda *a,**k:{'V900':[angular,second]})
    labels=[{'text':'V900','pos':list(angular.to_world(x,9.5)),'rotation':45} for x in (50,250)]
    report=fv.apply_lateral_reference_all([beam],labels,[],{})
    assert 'angular_identity_pending' not in report['V900']


def test_section_texts_are_not_named_identity(monkeypatch):
    beam,angular=setup(monkeypatch)
    labels=labels_for(angular)
    labels[1]['text']='19/55'
    report=fv.apply_lateral_reference_all([beam],labels,[],{})
    assert 'angular_identity_pending' not in report['V900']
    assert any(link.get('geometry_source','').endswith('_special_diagonal') for _,link,_ in fv._panels(beam))
