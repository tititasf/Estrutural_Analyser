import math
import ezdxf
import pytest

from src.core.qa_original_polyline import original_polyline_xyb
from src.core.pil_qa_identity_paths import collect_identity_scene, prove_identity_path
from src.core.pil_qa_original_faces import original_special_face_planes
from tests.test_pil_qa_identity_paths import scene


def legacy_contours(doc):
    for entity in list(doc.modelspace().query('LWPOLYLINE')):
        pts = list(entity.get_points('xyb'))
        legacy = doc.modelspace().add_polyline2d([p[:2] for p in pts], close=entity.closed)
        for vertex, point in zip(legacy.vertices, pts):
            vertex.dxf.bulge = point[2]
        doc.modelspace().delete_entity(entity)


@pytest.mark.parametrize('case', ['valid', 'missing_wall', 'missing_support_section',
                                  'wrong_support_section', 'competing_name'])
def test_identity_evidence_same_for_legacy_polyline(case, monkeypatch):
    import tests.test_pil_qa_identity_paths as fixtures
    before = scene(case)
    def legacy_scene(doc, tolerance_cm):
        legacy_contours(doc)
        inventory = collect_identity_scene(doc, tolerance_cm)
        assert len(inventory['supports']) == 2
        return inventory
    monkeypatch.setattr(fixtures, 'collect_identity_scene', legacy_scene)
    after = fixtures.scene(case)
    assert after['status'] == before['status']
    if before['status'] == 'measured':
        assert len(after['supports']) == len(before['supports'])


def test_legacy_curves_and_3d_not_straight_contour_proof():
    ms = ezdxf.new().modelspace()
    curved = ms.add_polyline2d([(0, 0), (20, 0), (20, 19), (0, 19)], close=True)
    curved.vertices[0].dxf.bulge = 1
    assert original_polyline_xyb(curved)[0][0][2] == 1
    assert original_special_face_planes(curved, tolerance_cm=.05) == {}
    spatial = ms.add_polyline3d([(0, 0, 0), (20, 0, 5), (20, 19, 0)], close=True)
    assert original_polyline_xyb(spatial) == ([], False)


def test_original_l_faces_same_for_both_polyline_formats():
    doc = ezdxf.new()
    contour = doc.modelspace().add_lwpolyline(
        [(0, 0), (40, 0), (40, 19), (19, 19), (19, 50), (0, 50)], close=True)
    before = original_special_face_planes(contour, tolerance_cm=.05)
    assert len(before) == 6
    legacy_contours(doc)
    after = original_special_face_planes(doc.modelspace().query('POLYLINE')[0], tolerance_cm=.05)
    assert after == before


@pytest.mark.parametrize('reverse', [False, True])
def test_original_u_uses_eight_physical_edges_not_enclosing_box(reverse):
    points = [(0, 0), (60, 0), (60, 80), (40, 80), (40, 20),
              (20, 20), (20, 80), (0, 80)]
    if reverse:
        points.reverse()
    doc = ezdxf.new()
    entity = doc.modelspace().add_polyline2d(points, close=True)
    faces = original_special_face_planes(entity, tolerance_cm=.05)
    assert set(faces) == set('ABCDEFGH')
    assert {tuple(faces['B'][key]) for key in ('p0', 'p1')} == {(20., 20.), (40., 20.)}
    assert sorted(math.dist(faces[f]['p0'], faces[f]['p1']) for f in faces) == [20, 20, 20, 60, 60, 60, 80, 80]
