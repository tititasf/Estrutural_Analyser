from copy import deepcopy
from src.core.pil_qa_wall_pairs import independent_open_wall_candidates


def wall(lo, hi, closed, pos=10, axis='x', handle='original'):
    return dict(lo=lo, hi=hi, closed_contour=closed, pos=pos, axis=axis, handles=[handle])


def test_full_open_original_coverage_removes_only_redundant_closed_edges():
    rows = [wall(0, 400, False, handle='beam'), wall(200, 400, True, handle='slab'),
            wall(200, 400, True, handle='duplicate'), wall(0, 400, False, pos=29)]
    before = deepcopy(rows)
    result = independent_open_wall_candidates(rows, .05)
    assert [r['handles'][0] for r in result] == ['beam', 'original']
    assert rows == before


def test_partial_edges_and_separate_strokes_do_not_bridge_a_gap():
    rows = [wall(0, 40, False), wall(60, 100, False), wall(0, 100, True)]
    assert independent_open_wall_candidates(rows, .05) == rows


def test_nearby_or_perpendicular_walls_do_not_prove_coverage():
    rows = [wall(0, 400, False, pos=10.1), wall(0, 400, False, axis='y'),
            wall(200, 400, True)]
    assert independent_open_wall_candidates(rows, .05) == rows


def test_closed_contours_alone_never_remove_each_other():
    rows = [wall(0, 400, True), wall(200, 400, True)]
    assert independent_open_wall_candidates(rows, .05) == rows


def test_real_original_reader_keeps_independent_pair_despite_closed_overlay(tmp_path):
    import ezdxf
    from portal.app import qa_cad_gate as gate
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (20, 0), (20, 80), (0, 80)]
    ms.add_lwpolyline(points, close=True)
    lower = ms.add_line((20, 10), (120, 10))
    upper = ms.add_line((20, 29), (120, 29))
    overlay = ms.add_lwpolyline([(20, 29), (80, 29), (80, 150), (20, 150)], close=True)
    ms.add_text('V304', dxfattribs={'insert': (60, 20), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (65, 22), 'height': 3})
    path = tmp_path/'source.dxf'
    doc.saveas(path)
    snapshot = {'collections': {'pilares': [{'points': points, 'interpretacao_abcd': {
        'faces': {'B': {'chega': [{'nome': 'V304', 'dim': '19/55',
                                 'dist_esq': 10, 'dist_dir': 51}]}}}}]}}
    contact = gate.measure(path, snapshot)['contacts'][0]
    assert contact['status'] == 'measured'
    assert not contact['errors']
    assert set(contact['wall_handles']) == {lower.dxf.handle, upper.dxf.handle}
    assert overlay.dxf.handle not in contact['wall_handles']
    # A foreign original label is evidence for review, not approval of an alias.
    row = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['B']['chega'][0]
    row['nome'] = 'V999'
    disputed = gate.measure(path, snapshot)['contacts'][0]
    assert disputed['status'] == 'uncertain'
    assert disputed['identity_path_review']['names'] == ['V304']
    assert set(disputed['geometry_only']['wall_handles']) == {lower.dxf.handle, upper.dxf.handle}
    assert disputed['geometry_only']['section'] == '19/55'
