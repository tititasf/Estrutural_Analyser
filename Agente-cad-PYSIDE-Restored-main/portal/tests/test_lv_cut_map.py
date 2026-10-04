import pytest
from portal.app.lv_cut_map import pair_polygon, footprints
from portal.app.lv_cut_map import section_drawings


def test_long_straight_tail_is_compressed_with_true_dimensions_and_break():
    from math import dist
    pair=dict(start=[0,0],end=[300,0],length_cm=300,b_id='B',a_index=1,b_index=2)
    cut=dict(id='tail',beam='V',kind='calculated',width_cm=19,beam_height_cm=120,pairs=[pair],
        profiles={s:dict(level=852,slabs=[dict(name=s,level=852,height_cm=13)]) for s in ('A','B')})
    drawings,blocked=section_drawings([cut],dict(B=dict(segments=[dict(id='B',points=[[0,19],[300,19]])])))
    assert not blocked
    drawing=drawings[0]
    assert drawing['compressed_tail_cm']==70
    polygons=[p for p in drawing['primitives'] if p['kind']=='polygon']
    assert dist(polygons[0]['points'][1],polygons[0]['points'][2])==pytest.approx(50)
    assert all(dist(p['points'][1],p['points'][2])==pytest.approx(13) for p in polygons[1:])
    assert sorted(p['text'] for p in drawing['primitives'] if p['kind']=='text' and p['size']==5 and p.get('role')!='compression_label')==sorted(['13','107','13','107','19','120'])
    assert len([p for p in drawing['primitives'] if p['kind']=='line' and len(p['points'])==4])==2
    assert any(p.get('role')=='compression_label' and p['text']=='COMP. MAX' for p in drawing['primitives'])
    title=next(p for p in drawing['primitives'] if p.get('role')=='section_title')
    assert title['text']=='V - VC1 - (19/120)' and title['size']==8


@pytest.mark.parametrize('slab_height', [0, 13])
def test_short_pair_compresses_tail_in_place_outside_support(slab_height):
    pair=dict(start=[0,0],end=[19,0],length_cm=19,b_id='B',a_index=1,b_index=1)
    cut=dict(id='short',beam='V',kind='calculated',width_cm=19,beam_height_cm=55,pairs=[pair],
             profiles={s:dict(level=852,slabs=[dict(name=s, level=852, height_cm=slab_height)] if slab_height else []) for s in ('A','B')})
    pillar=dict(points=[[19,-10],[39,-10],[39,29],[19,29]])
    drawings,blocked=section_drawings([cut],dict(B=dict(segments=[dict(id='B',points=[[0,19],[19,19]])])),[pillar])
    assert not blocked and len(drawings)==1
    drawing=drawings[0]
    assert drawing['anchor']==[9.5,9.5]
    assert not drawing['displaced'] and drawing['detail_center']==drawing['anchor']
    assert drawing['strong_break'] and drawing['compression_ratio'] < .35
    from shapely.geometry import Polygon
    body=Polygon(drawing['primitives'][0]['points'])
    assert body.intersection(Polygon(pillar['points'])).area==0
    from math import dist
    polygons=[p for p in drawing['primitives'] if p['kind']=='polygon']
    assert dist(polygons[0]['points'][1], polygons[0]['points'][2]) == pytest.approx(17)
    assert all(dist(p['points'][1], p['points'][2]) == pytest.approx(slab_height) for p in polygons[1:])
    breaks=[p for p in drawing['primitives'] if p['kind']=='line' and len(p['points'])==4]
    assert len(breaks)==2 and any(p['color']=='#fff38c' for p in breaks)
    assert any(p.get('text')=='55' for p in drawing['primitives'])


def test_neighboring_sections_move_within_own_pairs_to_avoid_overlap():
    from shapely.geometry import Polygon
    cuts=[]
    for i,(start,end) in enumerate(((0,150),(100,250))):
        pair=dict(start=[start,0],end=[end,0],length_cm=end-start,b_id='B',a_index=1,b_index=1)
        cuts.append(dict(id=str(i),beam='V',kind='calculated',width_cm=19,beam_height_cm=120,pairs=[pair],
             profiles={s:dict(level=852,slabs=[dict(name=s,height_cm=13,level=852)]) for s in ('A','B')}))
    drawings,blocked=section_drawings(cuts,dict(B=dict(segments=[dict(id='B',points=[[0,19],[250,19]])])))
    assert not blocked and len(drawings)==2
    shapes=[Polygon(d['primitives'][0]['points']) for d in drawings]
    assert shapes[0].intersection(shapes[1]).area==0


@pytest.mark.parametrize('start,end,b,expected', [
    ([20,0],[40,0], [[100,19],[0,19]], [[20,0],[40,0],[40,19],[20,19]]),
    ([0,20],[0,40], [[-19,100],[-19,0]], [[0,20],[0,40],[-19,40],[-19,20]]),
])
def test_common_interval_only_and_reversed_b(start, end, b, expected):
    assert pair_polygon(dict(start=start,end=end),dict(points=b)) == expected


def test_distant_b_fails_instead_of_guessing():
    with pytest.raises(ValueError):
        pair_polygon(dict(start=[0,0],end=[20,0]),dict(points=[[40,19],[100,19]]))


def test_grouped_section_keeps_disjoint_footprints():
    pairs = [dict(start=[x,0],end=[x+20,0],b_id='B',a_index=1,b_index=2) for x in (0,60)]
    result = footprints([dict(pairs=pairs),dict(pairs=[])],dict(B=dict(segments=[dict(id='B',points=[[100,19],[0,19]])])))
    assert len(result) == 2
    assert result[0]['color'] == result[1]['color']
    assert result[0]['points'][1][0] == 20
    assert result[1]['points'][0][0] == 60


@pytest.mark.parametrize('vertical', [False, True])
def test_section_dimensions_rotation_and_one_per_group(vertical):
    pair=dict(start=[0,0],end=[100,0],length_cm=100,b_id='B',a_index=1,b_index=2)
    b=[[100,19],[0,19]]
    if vertical:
        pair.update(start=[0,0],end=[0,100]); b=[[-19,100],[-19,0]]
    cut=dict(id='test',beam='V1',kind='calculated',width_cm=19,beam_height_cm=55,
             profiles={s:dict(level=852,slabs=[]) for s in ('A','B')},pairs=[pair,pair])
    drawings,blocked=section_drawings([cut],dict(B=dict(segments=[dict(id='B',points=b)])))
    assert not blocked and len(drawings)==1
    pts=drawings[0]['primitives'][0]['points']
    from math import dist
    assert dist(pts[0],pts[1])==pytest.approx(19)
    assert dist(pts[1],pts[2])==pytest.approx(50)
    assert drawings[0]['anchor']==([50,9.5] if not vertical else [-9.5,50])
    if vertical:
        assert pts[0][1]==pytest.approx(pts[1][1])
    else:
        assert pts[0][0]==pytest.approx(pts[1][0])
    # Width must follow the A->B normal, with A at the left section edge.
    delta = [b[-1][i]-pair['start'][i] for i in (0,1)]
    edge = [pts[1][i]-pts[0][i] for i in (0,1)]
    assert sum(delta[i]*edge[i] for i in (0,1)) > 0


def test_wall_dimensions_close_each_side_with_recessed_slab():
    pair=dict(start=[0,0],end=[100,0],length_cm=100,b_id='B',a_index=1,b_index=2)
    cut=dict(id='test',beam='V1',kind='calculated',width_cm=19,beam_height_cm=55,
             profiles={'A':dict(level=852.19,slabs=[dict(name='L1',level=852.19,height_cm=13)]),
                       'B':dict(level=852.12,slabs=[dict(name='L2',level=852.12,height_cm=12)])},pairs=[pair])
    drawings,blocked=section_drawings([cut],dict(B=dict(segments=[dict(id='B',points=[[100,19],[0,19]])])))
    assert not blocked
    labels=[p for p in drawings[0]['primitives'] if p['kind']=='text']
    measures=[float(p['text']) for p in labels if p['size']==5 and p.get('role')!='compression_label']
    # A: 13+42. B: 7+12+36. Width 19 and total height 55 stay visible.
    assert sorted(measures)==sorted([13,42,7,12,36,19,55])
    assert not any('h=' in p['text'] for p in labels)


@pytest.mark.parametrize('rotate', [False, True])
@pytest.mark.parametrize('annotated', [False, True])
def test_original_polygon_preserved_and_title_outside_without_pairs(rotate, annotated):
    # The original lies far from any inferred pair. Its actual shape is authoritative.
    pts=[[7,79],[17,79],[17,49],[55,49],[55,30],[12,30],[12,0],[0,0],[0,49],[7,49],[7,79]]
    pts=[[1000+(y if rotate else x),2000+(-x if rotate else y)] for x,y in pts]
    raw=dict(points=pts,beam_w=19,beam_h=55,own_laje='L2',neigh_laje='L1',
             ficha=dict(direction='Sul',own_slab_height=10,own_dist_top=7,own_dist_bottom=38,
                        neigh_slab_height=12,neighbor_dist_top=0,neighbor_dist_bottom=43))
    cut=dict(id='original',beam='V1',kind='identified',source_cut=raw,pairs=[])
    if annotated:
        raw['ficha'].update(side_a_laje_height='h=12',side_b_laje_height='h=12')
    drawings,blocked=section_drawings([cut],dict(B=dict(segments=[])))
    assert not blocked and len(drawings)==1
    assert (drawings[0]['primitives'][0]['points']==pts) is (not annotated)
    assert raw['points'] == pts  # The original DXF evidence stays untouched.
    labels=[p for p in drawings[0]['primitives'] if p['kind']=='text']
    assert sorted(float(p['text']) for p in labels if p['size']==5)==sorted([12,43,7,12,36,19,55] if annotated else [12,43,7,10,38,19,55])
    if annotated:
        from math import dist
        polygons = [p for p in drawings[0]['primitives'] if p['kind']=='polygon']
        assert len(polygons) == 3
        assert dist(polygons[2]['points'][1],polygons[2]['points'][2]) == pytest.approx(12)
    title=next(p for p in labels if 'VC1' in p['text'])
    assert title['points'][0] not in pts
