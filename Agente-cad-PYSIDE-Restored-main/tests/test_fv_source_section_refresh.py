import copy
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src.core.lv_beam_scene import LvScene, _EdgeIndex, _sections
from src.core.beam_interpreters.fundo_viga_lateral_ref import (
    _clip_automatic_bottoms_to_obstacles, _panels, _refresh_measured_panel_sections,
)


@pytest.mark.parametrize('divider', [False, True])
@pytest.mark.parametrize('offset', [0, 8000])
def test_offset_section_requires_unobstructed_local_source(divider, offset):
    o=offset
    run=LvScene('B', False, o, o+14, o, o+100)
    lines=[(o,o,o,o+100),(o+14,o,o+14,o+100)]
    if divider: lines.append((o+25,o,o+25,o+100))
    _sections(run, {}, [{'pos':[o+47,o+50], 'rotation':90,
                        'height':10, 'text':'14/63', 'section':(14,63)}], [], _EdgeIndex(lines))
    assert bool(run.sections) is not divider
    if run.sections: assert run.sections[0]['dim']=='14/63'


def beam(poly, **extra):
    return {'name':'B','fv_is_h':True,'fields':{'viga_fundo_seg_1_dim':'14/43'},
            'links':{'viga_fundo_seg_1_area_segs':{'contour':[
                dict(points=list(poly.exterior.coords), **extra)]}}}


@pytest.mark.parametrize('extra', [{}, {'manual':True}, {'geometry_source':'manual_svg'}, {'validated':True}])
def test_section_refresh_corrects_stale_automatic_dimensions_only(extra):
    b=beam(box(0,0,100,14), **extra); before=copy.deepcopy(b)
    run=LvScene('B',True,0,14,0,100)
    run.sections=[dict(start=0,end=100,dim='14/63',width=14,depth=63)]
    _refresh_measured_panel_sections([b], {'B':[run]})
    if extra: assert b==before
    else: assert b['fields']['viga_fundo_seg_1_dim']=='14/63'


def test_section_refresh_does_not_erase_depth_changes():
    b=beam(box(0,0,100,14)); before=copy.deepcopy(b)
    run=LvScene('B',True,0,14,0,100)
    run.sections=[dict(start=0,end=50,dim='14/63'),dict(start=50,end=100,dim='14/43')]
    _refresh_measured_panel_sections([b], {'B':[run]})
    assert b==before


@pytest.mark.parametrize('extra', [{}, {'manual':True}, {'validated':True}])
def test_cut_annotation_never_removes_bottom_area(extra):
    b=beam(box(0,0,100,14), **extra); before=copy.deepcopy(b)
    assert _clip_automatic_bottoms_to_obstacles(
        [b], [('C','corte_dxf',box(20,0,90,14))], 'cortes') == {}
    assert b==before


def test_crossclass_reconciliation_preserves_different_measured_sections():
    from src.core.pillar_face_beams import reconcile_beam_fundo_facts
    b=beam(box(0,0,100,14))
    b['links']['viga_fundo_seg_1_area_segs']['contour'][0]['fv_measured_section_dim']='14/63'
    b['fields']['viga_fundo_seg_2_dim']='wrong'
    b['links']['viga_fundo_seg_2_area_segs']={'contour':[{'fv_measured_section_dim':'14/43'}]}
    reconcile_beam_fundo_facts([b])
    assert b['fields']['viga_fundo_seg_1_dim']=='14/63'
    assert b['fields']['viga_fundo_seg_2_dim']=='14/43'


@pytest.mark.parametrize('horizontal', [False, True])
@pytest.mark.parametrize('offset', [0., 8000.])
@pytest.mark.parametrize('blocker', ['none','divider','depth','both_walls','unproven'])
def test_obscured_wall_requires_independent_glyph_and_opposite_wall(monkeypatch, horizontal, offset, blocker):
    from src.core import cad_object_recognition as cad
    from src.core.beam_interpreters.fundo_viga_lateral_ref import _bridge_cut_annotation_wall_gaps
    o=offset
    run=LvScene('B',horizontal,o,o+14,o,o+100)
    run.face_coverage={'A':[[o,o+40],[o+60,o+100]],'B':[[o,o+100]]}
    run.sections=[dict(start=o,end=o+100,dim='14/63')]
    if blocker=='depth': run.sections=[dict(start=o,end=o+50,dim='14/63'),dict(start=o+50,end=o+100,dim='14/43')]
    if blocker=='both_walls':run.face_coverage['B']=run.face_coverage['A'][:]
    poly=run.rect(o+30,o+70,o,o+14)
    records=[] if blocker=='unproven' else [{'points':list(poly.exterior.coords),'section_kind':'beam'}]
    monkeypatch.setattr(cad,'section_piece_keys',lambda *a:(set(),records))
    lines=[]
    if blocker=='divider':
        lines=[{'points': [run.point_local(o+50,'A'),run.point_local(o+50,'B')]}]
    _bridge_cut_annotation_wall_gaps({'B':[run]},lines,[])
    assert run.face_coverage['A']==([[o,o+100]] if blocker=='none' else [[o,o+40],[o+60,o+100]])


@pytest.mark.parametrize('horizontal',[True,False])
@pytest.mark.parametrize('guard',['none','divider','transition','manual','level','gap'])
def test_unsupported_short_section_seam_merges_without_erasing_source_facts(horizontal,guard):
    from src.core.beam_interpreters.fundo_viga_lateral_ref import _merge_unsupported_section_seams
    run=LvScene('B',horizontal,0,19,0,100)
    run.sections=[dict(start=0,end=50,dim='19/48'),dict(start=50,end=100,dim='19/50')]
    seam=50 if guard=='transition' else 10
    a=run.rect(0,seam,0,19);b=run.rect(seam+(1 if guard=='gap' else 0),100,0,19)
    item=beam(a);item['fv_is_h']=horizontal
    item['fields'].update(viga_fundo_seg_1_dim='19/48',viga_fundo_seg_2_dim='19/50')
    item['links']['viga_fundo_seg_2_area_segs']={'contour':[{'points':list(b.exterior.coords)}]}
    if guard=='manual':item['links']['viga_fundo_seg_1_area_segs']['contour'][0]['manual']=True
    if guard=='level':item['fields'].update(viga_fundo_seg_1_nivel='1.00',viga_fundo_seg_2_nivel='1.10')
    lines=[{'points':[run.point(seam,'A'),run.point(seam,'B')]}] if guard=='divider' else []
    _merge_unsupported_section_seams([item],{'B':[run]},lines,{})
    assert len(_panels(item))==(1 if guard=='none' else 2)
    if guard=='none':
        link=_panels(item)[0][1]
        assert link['fv_section_transition_unlocated']
        assert {z['dim'] for z in link['fv_source_section_references']}=={'19/48','19/50'}
        assert item['fields']['viga_fundo_seg_1_dim']=='19/50'
        assert _panels(item)[0][2].area==pytest.approx(1900)
        from src.core.pillar_face_beams import reconcile_beam_fundo_facts
        item['links']['viga_fundo_seg_2_area_segs']={'contour':[{'fv_measured_section_dim':'22/50'}]}
        item['fields']['viga_fundo_seg_2_dim']='22/50'
        reconcile_beam_fundo_facts([item])
        assert item['fields']['viga_fundo_seg_1_dim']=='19/50'
