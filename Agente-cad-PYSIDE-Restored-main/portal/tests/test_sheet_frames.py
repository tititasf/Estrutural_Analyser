from copy import deepcopy
from shapely.geometry import Point, LineString
from portal.app.preprocessamento.adapters.sheet_frames import prove_sheet_frames


def fixture():
    outer=dict(handle='outer',points=[[0,0],[100,0],[100,100],[0,100],[0,0]])
    inner=dict(handle='inner',points=[[2,2],[98,2],[98,98],[2,98],[2,2]])
    contours=[outer,inner]
    primitives=[dict(handle=c['handle'],geometry=LineString(c['points'])) for c in contours]
    primitives += [dict(handle='plan-child',geometry=Point(20,20)),dict(handle='detail-child',geometry=Point(80,80))]
    detection=dict(torres=[dict(bbox=[10,10,40,40])],detalhes=[dict(bbox=[70,70,90,90])])
    return contours,primitives,detection


def test_nested_sheet_borders_preserve_original_children_and_require_separate_regions():
    args=fixture();before=deepcopy(args)
    records=prove_sheet_frames(*args)
    assert len(records)==2
    assert all(r['content_preserved'] and 'plan-child' in r['contained_entity_handles'] and 'detail-child' in r['contained_entity_handles'] for r in records)
    assert args==before
    args[2]['detalhes']=[]
    assert prove_sheet_frames(*args)==[]


def test_internal_geometry_or_text_does_not_make_a_real_pillar_a_sheet_frame():
    contours,primitives,detection=fixture()
    assert prove_sheet_frames(contours[:1],primitives,detection)==[]


def test_incident_border_or_nonrectangular_contour_cannot_certify_a_frame():
    for blocker in ('incident','shape'):
        contours,primitives,detection=fixture()
        if blocker=='incident':primitives.append(dict(handle='incident',geometry=LineString([[0,0],[20,20]])))
        else:contours[0]['points'][1]=[90,5]
        assert prove_sheet_frames(contours,primitives,detection)==[]


def test_missing_region_proof_preserves_source_and_returns_no_frame_roles(tmp_path):
    import ezdxf
    from portal.app.preprocessamento.adapters.sheet_frames import inventory_sheet_frames
    source = tmp_path/'no_regions.dxf'
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (20, 0))
    doc.saveas(source)
    before = source.read_bytes()
    result = inventory_sheet_frames(source, detection={'error': 'no recognized plan region'})
    assert result['status'] == 'region_detection_failed'
    assert result['records'] == []
    assert result['error'] == 'sheet_frame_region_detection_failed'
    assert result['production_files_modified'] is False
    assert source.read_bytes() == before
