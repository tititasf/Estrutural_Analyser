"""D-85/FV: straight angled arrivals, not arbitrary L/cross conversion."""
import copy
import math
import pytest
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from src.core.lv_beam_scene import LvScene
from src.core.beam_interpreters.fundo_viga_lateral_ref import _chamfer_arriving_junctions, _panels


def elbow(rotation=0):
    w=14/math.sqrt(2)
    diagonal=Polygon([(-100/math.sqrt(2),100/math.sqrt(2)),
                      (-86/math.sqrt(2),114/math.sqrt(2)),(w,w),(w,0),(0,0)])
    horizontal=box(w,0,110,w)
    runs={'VA':[LvScene('VA',True,0,14,-100,0,angle=-45)],
          'VB':[LvScene('VB',True,0,w,w,110)]}
    beams=[]
    for name,poly in (('VA',diagonal),('VB',horizontal)):
        for r in runs[name]:
            r.sections=[{'start':r.start,'end':r.end,'depth':55,'width':r.width}]
            r.angle+=rotation
        poly=affinity.rotate(poly,rotation,origin=(0,0))
        beams.append({'name':name,'fv_is_h':True,'fields':{'dimensao':'14/55'},
                      'links':{'viga_fundo_seg_1_area_segs':{'contour':[{
                          'points':list(poly.exterior.coords),'type':'poly','ficha':{}}]}}})
    return beams,runs


def union(beams):
    return unary_union([p for b in beams for _,_,p in _panels(b) if p is not None])


@pytest.mark.parametrize('rotation',[0,23,90,167])
def test_chamfer_rotation_invariant_preserves_outline_and_owners(rotation):
    beams,runs=elbow(rotation)
    original=union(beams)
    report={}
    _chamfer_arriving_junctions(beams,runs,[],report)
    assert set(report)=={'VA','VB'}
    assert union(beams).symmetric_difference(original).area<1e-7
    polys=[_panels(b)[0][2] for b in beams]
    assert polys[0].intersection(polys[1]).area<1e-7
    assert all(p.convex_hull.difference(p).area<1e-7 for p in polys)
    before=copy.deepcopy(beams)
    _chamfer_arriving_junctions(beams,runs,[],{})
    assert beams==before


@pytest.mark.parametrize('protection',['validated','solid','depth','same_beam','cross'])
def test_chamfer_does_not_replace_a_protected_bend_or_cross(protection):
    beams,runs=elbow()
    solids=[]
    if protection=='validated':
        _panels(beams[0])[0][1]['validated']=True
    elif protection=='solid':
        solids=[box(-5,-5,20,20)]
    elif protection=='depth':
        runs['VB'][0].sections[0]['depth']=66
    elif protection=='same_beam':
        runs['VA'].extend(runs.pop('VB'))
        runs['VA'][-1].beam_name='VA'
        beams[0]['links']['viga_fundo_seg_2_area_segs']=beams.pop()['links']['viga_fundo_seg_1_area_segs']
    else:
        for rr in runs.values():
            rr[0].start=-100
            rr[0].end=100
    before=copy.deepcopy(beams)
    _chamfer_arriving_junctions(beams,runs,solids,{})
    assert beams==before
