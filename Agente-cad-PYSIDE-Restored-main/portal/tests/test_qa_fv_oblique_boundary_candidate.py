from shapely.geometry import Polygon
from portal.app.qa_fv_oblique_boundary_candidate import prove_oblique_boundary


def originals(points):
    return [(a,b,str(i)) for i,(a,b) in enumerate(zip(points,points[1:]))]


def test_physical_diagonal_tip_proves_only_contour():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(0,2),originals(points))
    assert result['status']=='measured'
    assert result['guards']==['identidade_contorno']
    assert all(not result[key] for key in ['caps_approved','section_approved','ownership_approved','inventory_approved'])


def test_internal_subdivision_faces_not_invented_as_walls():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(3,6),originals(points))
    assert result['status']=='measured'
    assert len(result['pieces'])==2
    assert all(a[0]!=b[0] for piece in result['pieces'] for a,b in [piece['points']])


def test_shared_generated_seam_is_not_physical_source_proof():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(0,10),originals(points)[:2])
    assert result['status']=='uncertain'
    assert any(not piece['proved'] for piece in result['pieces'])


def test_tiny_unsupported_edge_is_retained_and_blocks():
    points=[(0,0),(10,0),(10,2),(10.001,2),(10.001,3),(0,3),(0,0)]
    strokes=originals(points)
    result=prove_oblique_boundary(Polygon(points),(0,11),strokes[:2]+strokes[3:])
    assert result['status']=='uncertain'
    tiny=[p for p in result['pieces'] if p['length_cm']<.05]
    assert tiny and any(not p['proved'] for p in tiny)


def test_no_bbox_or_chord_for_bent_boundary():
    points=[(0,0),(4,1),(6,4),(10,5),(10,8),(0,8),(0,0)]
    strokes=originals(points)
    # A chord across the actual kink does not prove the original pieces.
    strokes=[((0,0),(10,5),'chord')]+strokes[3:]
    result=prove_oblique_boundary(Polygon(points),(0,10),strokes)
    assert result['status']=='uncertain'
    assert len(result['pieces'])==6


def test_original_handle_is_required():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(0,2),[(a,b,'') for a,b,h in originals(points)])
    assert result['status']=='uncertain'


def test_missing_original_wall_is_not_approved_by_small_cell():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(0,.0001),[])
    assert result['status']=='uncertain'
    assert result['pieces'] and all(not p['proved'] for p in result['pieces'])


def test_displaced_parallel_source_fails():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(0,2),[((a[0],a[1]+1),(b[0],b[1]+1),h) for a,b,h in originals(points)])
    assert result['status']=='uncertain'


def test_duplicate_originals_do_not_double_coverage():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(3,6),originals(points)*2)
    assert result['status']=='measured'
    assert all(p['covered_cm']<=p['length_cm']+1e-9 for p in result['pieces'])


def test_empty_or_invalid_polygon_fails_closed():
    assert prove_oblique_boundary(Polygon(),(0,2),[])['status']=='uncertain'
    assert prove_oblique_boundary(Polygon([(0,0),(1,1),(0,1),(1,0)]),(0,2),[])['status']=='uncertain'


def test_no_physical_boundary_in_slice_fails():
    points=[(0,0),(10,5),(10,10),(0,0)]
    assert prove_oblique_boundary(Polygon(points),(11,12),originals(points))['status']=='uncertain'


def test_nonfinite_original_coordinates_fail_closed():
    points=[(0,0),(10,5),(10,10),(0,0)]
    result=prove_oblique_boundary(Polygon(points),(0,2),[((0,0),(float('nan'),1),'bad')])
    assert result['status']=='uncertain'
    assert 'invalid original' in result['reason']
