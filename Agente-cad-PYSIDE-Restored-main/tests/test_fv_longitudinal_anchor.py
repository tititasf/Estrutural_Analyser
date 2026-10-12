from copy import deepcopy
from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter as F


def test_bbox_vertices_on_opposite_faces_do_not_anchor_slanted_panel():
    points = [(0, 0), (410, 0), (790, 19), (420, 19), (0, 0)]
    faces = [[(0, 0), (790, 0)], [(0, 19), (790, 19)]]
    assert not F.contour_overlays_boundary_lines(points, faces, is_horizontal=True)
    # Axis swapping is the same physical problem.
    assert not F.contour_overlays_boundary_lines(
        [(y, x) for x, y in points],
        [[(y, x) for x, y in edge] for edge in faces], is_horizontal=False)


def test_split_longitudinal_face_and_short_chamfer_keep_anchor():
    faces = [[(0, 0), (400, 0)], [(400, 0), (800, 0)]]
    points = [(0, 0), (300, 0), (800, 0), (800, 19), (10, 19), (0, 9)]
    assert F.contour_overlays_boundary_lines(points, faces, is_horizontal=True)


def test_repair_rebuilds_unvalidated_slanted_panel_and_preserves_human_contour():
    points = [(0, 0), (410, 0), (790, 19), (420, 19), (0, 0)]
    beam = dict(name='sample', dim='19/55', is_h=True, fv_is_h=True, pos=(0, 0),
                geometry={'classified': {'merged_bottom_groups_coords': [[0, 790]],
                    'seg_bottom': [[(0, 0), (790, 0)], [(0, 19), (790, 19)]]}},
                links={'viga_fundo_seg_1_area_segs': {'contour': [
                    {'points': points, 'ficha': {'largura_total_fundo': '19'}}]}})
    human = deepcopy(beam)
    human['links']['viga_fundo_seg_1_area_segs']['contour'][0]['validated'] = True
    F.repair_area_links(beam)
    poly = beam['links']['viga_fundo_seg_1_area_segs']['contour'][0]['points']
    assert F._polygon_area(poly) == 790 * 19
    F.repair_area_links(human)
    assert human['links']['viga_fundo_seg_1_area_segs']['contour'][0]['points'] == points
