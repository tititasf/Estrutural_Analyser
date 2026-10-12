import copy
import pytest
from src.core.pillar_special_faces import (
    special_u_face_segments, eight_face_segments, special_face_neighbors,
    enrich_special_pillar_tables, physical_tag_artifact_matches,
    physical_tag_geometry_key, physical_face_contract_key,
)

U = [[0,0],[100,0],[100,120],[80,120],[80,20],[20,20],[20,100],[0,100]]

def canonical(edges):
    return {k: sorted([v['p0'],v['p1']]) for k,v in edges.items()}

@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('start',range(8))
def test_u_faces_do_not_depend_on_vertex_start_or_winding(start,reverse):
    ring = list(reversed(U)) if reverse else U
    ring = ring[start:]+ring[:start]
    assert canonical(special_u_face_segments(ring)) == canonical(special_u_face_segments(U))

@pytest.mark.parametrize('turns',range(4))
def test_u_face_identity_moves_with_the_section(turns):
    def rotate(p):
        x,y = p
        for _ in range(turns):
            x,y = -y,x
        return (x+321,y-47)
    original = special_u_face_segments(U)
    actual = special_u_face_segments([rotate(p) for p in U])
    assert canonical(actual) == {k:sorted([rotate(v['p0']),rotate(v['p1'])]) for k,v in original.items()}
    assert actual['A']['length'] == 100
    assert actual['B']['length'] == 60

def test_explicit_contract_rejects_duplicate_wall_and_invalid_polygon():
    edges = special_u_face_segments(U)
    assert eight_face_segments(U,edges)
    bad = copy.deepcopy(edges); bad['H'] = bad['G']
    assert not eight_face_segments(U,bad)
    assert not special_u_face_segments([[x+.3 if i==3 else x,y] for i,(x,y) in enumerate(U)])
    assert not special_u_face_segments([[0,0],[50,0],[50,30],[30,30],[30,60],[10,60],[10,30],[0,30]])

@pytest.mark.parametrize('reverse', [False, True])
def test_u_contacts_use_verified_intervals_not_bbox_rows(reverse):
    points = list(reversed(U)) if reverse else U
    pillar = {'points':points}
    tables = {'faces':{'A':{'chega':[{'nome':'WRONG'}]}}}
    beam = {'name':'V1','dim':'10/50','_verified_wall_runs':[((-40,30,0,40),'10/50')]}
    slab = [[20,20],[80,20],[80,80],[20,80]]
    result = enrich_special_pillar_tables(tables,pillar,beams=[beam],
             slab_points_map={'L1':slab}, slab_height_map={'L1':'12'},slab_nivel_map={'L1':'537.86'})
    assert result['face_ids'] == list('ABCDEFGH')
    contact = result['faces']['E']['chega'][0]
    assert contact['_physical_contact_origin'] == 'p0'
    assert contact['_physical_contact_interval_cm'] == ([30,40] if reverse else [60,70])
    edge = special_u_face_segments(points)['E']
    direction = 1 if edge['p1'][1] > edge['p0'][1] else -1
    assert sorted(edge['p0'][1] + direction*d
                  for d in contact['_physical_contact_interval_cm']) == [30,40]
    assert result['faces']['B']['lajes'][0]['nome'] == 'L1'
    assert result['legacy_bbox_faces']['A']['chega'][0]['nome'] == 'WRONG'
    assert len(special_face_neighbors(special_u_face_segments(U))) == 8

def test_artifact_requires_same_named_walls_as_current_contract():
    edges = special_u_face_segments(U)
    svg = (f'<svg data-pil-physical-version="1" data-pil-geometry="{physical_tag_geometry_key(U)}" '
           f'data-pil-faces="{physical_face_contract_key(edges)}"></svg>')
    assert physical_tag_artifact_matches(svg,U)
    changed = copy.deepcopy(edges); changed['E'],changed['F'] = changed['F'],changed['E']
    assert not physical_tag_artifact_matches(svg,U,{'face_geometry':changed})
