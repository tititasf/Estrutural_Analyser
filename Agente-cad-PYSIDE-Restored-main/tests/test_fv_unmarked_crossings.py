import copy
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src.core.lv_beam_scene import LvScene
from src.core.beam_interpreters.fundo_viga_lateral_ref import (
    _optimize_unmarked_junctions, _panels, _confirmed_cut_obstacles,
    _clip_automatic_bottoms_to_obstacles,
)

def beam(name, horizontal, polys):
    return {'name':name, 'fv_is_h':horizontal, 'fields':{}, 'links':{
        f'viga_fundo_seg_{i}_area_segs':{'contour':[{'points':list(p.exterior.coords)}]}
        for i,p in enumerate(polys,1)}}

def fixture(offset=0):
    o=offset
    bs=[beam('V11', True, [box(o,o,o+40,o+14),box(o+40,o,o+54,o+14),box(o+54,o,o+100,o+14)]),
        beam('V22',False,[box(o+40,o+14,o+54,o+100)])]
    rs={'V11':[LvScene('V11',True,o,o+14,o,o+100)],
        'V22':[LvScene('V22',False,o+40,o+54,o,o+100)]}
    for rr in rs.values():
        for r in rr:r.sections=[{'start':r.start,'end':r.end,'width':14,'depth':50}]
    return bs,rs

def union(bs):
    return unary_union([p for b in bs for _,_,p in _panels(b)])


@pytest.mark.parametrize('reverse', [False, True])
def test_equal_count_prefers_fewer_short_panels_without_erasing_material(reverse):
    bs = [beam('V11', True, [box(0,0,70,14)]),
          beam('V22', False, [box(56,14,70,64)])]
    rs = {'V11': [LvScene('V11',True,0,14,0,70)],
          'V22': [LvScene('V22',False,56,70,0,64)]}
    for rr in rs.values():
        for r in rr:
            r.sections = [{'start':r.start,'end':r.end,'width':14,'depth':55}]
    if reverse:
        bs.reverse()
    original = union(bs)
    report = {}
    _optimize_unmarked_junctions(bs,rs,[],[],report)
    assert report
    assert sum(len(_panels(b)) for b in bs) == 2
    assert union(bs).symmetric_difference(original).area < 1e-6
    assert all(entry['dono'] == 'V22' for entries in report.values() for entry in entries)
    assert _panels(bs[0])[0][2].intersection(_panels(bs[1])[0][2]).area < 1e-6
    saved = copy.deepcopy(bs)
    _optimize_unmarked_junctions(bs,rs,[],[],{})
    assert bs == saved

@pytest.mark.parametrize('offset',[0,12345])
@pytest.mark.parametrize('reverse',[False,True])
def test_repartition_preserves_area_without_overlap_and_is_idempotent(offset,reverse):
    bs,rs=fixture(offset)
    if reverse:bs.reverse();rs=dict(reversed(list(rs.items())))
    original=union(bs);report={}
    _optimize_unmarked_junctions(bs,rs,[],[],report)
    assert report
    assert sum(len(_panels(b)) for b in bs)==2
    assert union(bs).symmetric_difference(original).area<1e-6
    assert _panels(bs[0])[0][2].intersection(_panels(bs[1])[0][2]).area<1e-6
    saved=copy.deepcopy(bs)
    _optimize_unmarked_junctions(bs,rs,[],[],{})
    assert bs==saved

@pytest.mark.parametrize('veto',['divider','obstacle','depth','local_depth','manual','validated'])
def test_physical_and_human_constraints_veto_reassignment(veto):
    bs,rs=fixture();lines=[];obstacles=[]
    if veto=='divider':lines=[{'points':[(40,14),(54,14)]}]
    if veto=='obstacle':obstacles=[box(45,3,46,4)]
    if veto=='depth':rs['V22'][0].sections[0]['depth']=65
    if veto=='local_depth':rs['V11'][0].sections.append({'start':70,'end':100,'width':14,'depth':65})
    if veto in ('manual','validated'):
        link=_panels(bs[0])[0][1]
        link.update({'geometry_source':'manual_svg'} if veto=='manual' else {'validated':True})
    saved=copy.deepcopy(bs)
    _optimize_unmarked_junctions(bs,rs,lines,obstacles,{})
    assert bs==saved

def test_cut_requires_current_structural_witness_not_stale_or_dimension(monkeypatch):
    import src.core.lv_cut_inventory as cuts
    shape=box(40,0,60,14)
    monkeypatch.setattr(cuts,'collect_explicit_cuts',lambda *a:[{'uid':'C1','pts':list(shape.exterior.coords)}])
    lines=[{'points':list(shape.exterior.coords)}]
    assert len(_confirmed_cut_obstacles([],lines))==1
    assert _confirmed_cut_obstacles([], [{'points':[(1,1),(2,2)]}])==[]
    assert _confirmed_cut_obstacles([], [dict(lines[0],annotation_role='dimension')])==[]
    bs=[beam('V11',True,[box(0,0,100,14)])]
    before=union(bs)
    _clip_automatic_bottoms_to_obstacles(bs,[('C1','corte_dxf',shape)],'cortes')
    assert union(bs).symmetric_difference(before).area<1e-6
    saved=copy.deepcopy(bs)
    assert _clip_automatic_bottoms_to_obstacles(bs,[('C1','corte_dxf',shape)],'cortes')=={}
    assert bs==saved
