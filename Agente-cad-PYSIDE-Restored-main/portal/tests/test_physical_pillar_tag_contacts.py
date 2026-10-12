import math

import pytest

from src.core.pillar_special_faces import (
    physical_face_contact,
    special_face_neighbors,
    special_l_face_segments,
)


@pytest.mark.parametrize('mirror', [1, -1])
@pytest.mark.parametrize('reverse', [False, True])
def test_corner_and_arrival_use_actual_edges_in_mirrored_l(mirror, reverse):
    points = [(mirror*x+130, y+260) for x,y in
              [(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)]]
    if reverse:
        points.reverse()
    edges = special_l_face_segments(points)
    neighbors = special_face_neighbors(edges)
    for fid, edge in edges.items():
        for other in neighbors[fid]:
            row = {'canto': fid+other, 'dim': '10/65'}
            start,end,corner = physical_face_contact(edges,fid,'passa',row)
            assert corner in (start,end)
            assert any(math.dist(corner,p)<.01 for p in
                       (edges[other]['p0'],edges[other]['p1']))
            a,b,tip = physical_face_contact(edges,fid,'chega',row)
            assert math.dist(a,b) == pytest.approx(10)
            assert math.dist(tip,corner) == pytest.approx(5)
            assert min(start[0],end[0]) <= tip[0] <= max(start[0],end[0])
            assert min(start[1],end[1]) <= tip[1] <= max(start[1],end[1])


def test_nonadjacent_or_missing_evidence_cannot_invent_a_contact():
    edges = special_l_face_segments([(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)])
    neighbors = special_face_neighbors(edges)
    other = next(fid for fid in edges if fid!='A' and fid not in neighbors['A'])
    with pytest.raises(ValueError,match='não adjacentes'):
        physical_face_contact(edges,'A','passa',{'canto':'A'+other})
    with pytest.raises(ValueError,match='largura'):
        physical_face_contact(edges,'A','chega',{'canto':'AA','dim':'—'})
    with pytest.raises(ValueError,match='intervalo'):
        physical_face_contact(edges,'A','lajes',{'dist_esq':'500','dist_dir':'0'})


def test_partial_slab_contact_is_independent_of_ring_winding():
    points = [(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)]
    result = []
    for ring in (points,list(reversed(points))):
        edges = special_l_face_segments(ring)
        result.append(physical_face_contact(edges,'A','lajes',{'dist_esq':'15,5','dist_dir':'20'}))
    assert result[0] == result[1]
    assert result[0] == ((0,15.5),(0,130),(0,72.75))


def test_verified_walls_reject_remote_links_and_measure_arrivals():
    from src.core.pillar_special_faces import reconcile_verified_special_contacts
    edges = special_l_face_segments([(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)])
    tables = {'faces': {'A': {'passa': [{'nome':'remote','canto':'AD'}]},
                        'D': {'chega': [{'nome':'arrival','dim':'999/65','canto':'DB'}]}}}
    beams = [{'name':'remote','dim':'19/65', '_verified_wall_runs': [[[200,200,300,219],'19/65']]},
             {'name':'arrival','dim':'20/65','_verified_wall_runs': [[[100,0,200,20],'20/65']]}]
    reconcile_verified_special_contacts(tables,edges,beams)
    assert tables['faces']['A']['passa'] == []
    row = tables['faces']['D']['chega'][0]
    assert row['dim'] == '20/65'
    assert row['canto'] == 'DD'
    assert physical_face_contact(edges,'D','chega',row) == ((100,0),(100,20),(100,10))
    assert len(tables['physical_contact_rejections']) == 1
    reconcile_verified_special_contacts(tables,edges,beams)
    assert len(tables['faces']['D']['chega']) == 1


def test_unverified_geometry_does_not_erase_existing_evidence():
    from src.core.pillar_special_faces import reconcile_verified_special_contacts
    edges = special_l_face_segments([(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)])
    row = {'nome':'unverified','canto':'AC'}
    tables = {'faces': {'A': {'passa':[row]}}}
    reconcile_verified_special_contacts(tables,edges,[{'name':'unverified'}])
    assert tables['faces']['A']['passa'] == [row]


def test_independently_wall_verified_section_can_reject_false_box_link():
    from src.core.pillar_special_faces import reconcile_verified_special_contacts
    edges = special_l_face_segments([(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)])
    tables = {'faces':{'A':{'chega':[{'nome':'remote','canto':'AA','dim':'14/50'}]}}}
    beam = {'name':'remote','dim':'14/50',
            '_verified_section_texts':[[[200,200,214,300],'14/50',[207,250]]]}
    reconcile_verified_special_contacts(tables,edges,[beam])
    assert not tables['faces']['A']['chega']
    assert len(tables['physical_contact_rejections']) == 1
    assert '_verified_wall_runs' not in beam


def test_reader_without_sources_preserves_canonical_six_face_contacts():
    import copy
    from src.core.pillar_special_faces import enrich_special_pillar_tables
    pillar = {'points':[(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)]}
    tables = {'geometry_type':'L_special_6_faces', 'faces':{f:{} for f in 'ABCDEF'}}
    tables['faces']['F']['chega'] = [{'nome':'arrival','canto':'FF','dim':'19/50',
                                     '_physical_contact_interval_cm':[0,19]}]
    before = copy.deepcopy(tables)
    assert enrich_special_pillar_tables(tables,pillar) == before


@pytest.mark.parametrize('reverse',[False,True])
def test_multiple_slabs_on_one_face_preserve_separate_measured_spans(reverse):
    from src.core.pillar_special_faces import enrich_special_pillar_tables
    points = [(0,0),(100,0),(100,20),(20,20),(20,150),(0,150)]
    if reverse:
        points.reverse()
    edges = special_l_face_segments(points)
    fid = next(f for f,e in edges.items() if e['p0'][0]==e['p1'][0]==0)
    tables = {'faces':{f:{'lajes':[]} for f in edges}}
    slabs = {'lower':[(-30,10),(0,10),(0,60),(-30,60)],
             'upper':[(-30,80),(0,80),(0,140),(-30,140)]}
    result = enrich_special_pillar_tables(tables,{'points':points},slab_points_map=slabs,
        slab_height_map={'lower':'10','upper':'12'},slab_nivel_map={'lower':'100','upper':'100.02'})
    rows = result['faces'][fid]['lajes']
    expected = [('lower',[10,60]),('upper',[80,140])] if reverse else [
        ('lower',[90,140]),('upper',[10,70])]
    assert [(r['nome'],r['_physical_contact_interval_cm']) for r in rows] == expected
    assert all(r['_physical_contact_origin'] == 'p0' for r in rows)
    assert [r['dim'] for r in rows] == ['10','12']
    assert [r['nivel'] for r in rows] == ['100','100.02']
    a,b,center = physical_face_contact(edges,fid,'lajes',rows[1])
    assert {a,b} == {(0,80),(0,140)}
    assert center == (0,110)


def test_concave_slab_bbox_cannot_prove_shared_face():
    from src.core.pillar_special_faces import slab_physical_contact_intervals
    edge = {'p0':(0,0),'p1':(100,0),'out':(0,1),'length':100}
    # The box spans the full face; the actual boundary has a central notch.
    slab = [(0,0),(20,0),(20,20),(80,20),(80,0),(100,0),(100,40),(0,40)]
    assert slab_physical_contact_intervals(edge,slab) == [[0,20],[80,100]]
