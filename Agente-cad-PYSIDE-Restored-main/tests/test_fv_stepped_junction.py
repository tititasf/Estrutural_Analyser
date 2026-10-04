"""Unequal collinear arms and an angled branch: measured single seam."""
import copy
import math
import pytest
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from src.core.lv_beam_scene import LvScene
from src.core.beam_interpreters.fundo_viga_lateral_ref import _stepped_collinear_junctions, _panels

def fixture(rotation=0):
    w, n = 19*math.sqrt(2), 14*math.sqrt(2)
    expected = [Polygon([(0,0),(w-19,19),(-70,70+w),(-70,70)]),
                Polygon([(0,0),(n,0),(70+n,-70),(70,-70)]),
                Polygon([(0,0),(w-19,19),(110,19),(110,0)])]
    stolen = Polygon([(0,0),(w-19,19),(w,0)])
    shapes = [expected[0].union(stolen), expected[1], expected[2].difference(stolen)]
    scenes = [LvScene('WIDE',True,-19,0,0,120,angle=135+rotation),
              LvScene('NARROW',True,-14,0,-120,0,angle=135+rotation),
              LvScene('BRANCH',True,0,19,0,110,angle=rotation)]
    beams, runs = [], {}
    for scene, shape in zip(scenes,shapes):
        scene.sections=[{'start':scene.start,'end':scene.end,'depth':55,'width':scene.width}]
        runs[scene.beam_name]=[scene]
        poly=affinity.rotate(shape,rotation,origin=(0,0))
        beams.append({'name':scene.beam_name,'fv_is_h':True,'fields':{'dimensao':f'{scene.width}/55'},
                      'links':{'viga_fundo_seg_1_area_segs':{'contour':[{'points':list(poly.exterior.coords),'type':'poly','ficha':{}}]}}})
    return beams,runs,[affinity.rotate(p,rotation,origin=(0,0)) for p in expected]

@pytest.mark.parametrize('rotation',[0,23,90,167])
@pytest.mark.parametrize('reverse',[False,True])
def test_single_seam_measured_walls_rotation_order_and_idempotence(rotation,reverse):
    beams,runs,expected=fixture(rotation)
    if reverse: beams.reverse()
    original=unary_union([_panels(b)[0][2] for b in beams])
    report={}
    _stepped_collinear_junctions(beams,runs,[],report)
    assert set(report)=={'WIDE','NARROW','BRANCH'}
    result={b['name']:_panels(b)[0][2] for b in beams}
    for name,p in zip(('WIDE','NARROW','BRANCH'),expected):
        assert result[name].symmetric_difference(p).area<1e-6
    assert unary_union(list(result.values())).symmetric_difference(original).area<1e-6
    before=copy.deepcopy(beams)
    _stepped_collinear_junctions(beams,runs,[],{})
    assert beams==before

@pytest.mark.parametrize('gap',[.005,.5])
def test_precision_contact_is_not_a_license_to_bridge_real_gaps(gap):
    beams,runs,_=fixture()
    # A witnessed DXF vertex on the shared edge is independently rounded.
    wide_link=_panels(beams[0])[0][1]
    coords=list(_panels(beams[0])[0][2].exterior.coords)
    coords.insert(4,(14*math.sqrt(2),0))
    wide_link['points']=[(x,y+gap if abs(y)<1e-8 else y) for x,y in coords]
    before=copy.deepcopy(beams)
    original=unary_union([_panels(b)[0][2] for b in beams])
    report={}
    _stepped_collinear_junctions(beams,runs,[],report)
    if gap>.05:
        assert beams==before
        assert not report
    else:
        assert set(report)=={'WIDE','NARROW','BRANCH'}
        result=unary_union([_panels(b)[0][2] for b in beams])
        assert original.difference(result).area<1e-6
        assert result.difference(original.buffer(.05)).area<1e-6

@pytest.mark.parametrize('protection',['validated','solid','depth','cross'])
def test_protected_geometry_is_untouched(protection):
    beams,runs,_=fixture()
    solids=[]
    if protection=='validated': _panels(beams[0])[0][1]['validated']=True
    elif protection=='solid': solids=[box(-2,-2,2,2)]
    elif protection=='depth': runs['NARROW'][0].sections[0]['depth']=66
    else: runs['BRANCH'][0].start=-110
    before=copy.deepcopy(beams)
    _stepped_collinear_junctions(beams,runs,solids,{})
    assert beams==before
