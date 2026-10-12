import pytest
from src.core.section_dimension_evidence import partial_height_dimension


def lines(a=7, b=60):
    return [dict(layer='9', start=(a, -25), end=(b, -25), handle='baseline'),
            dict(layer='9', start=(a, -35), end=(a, -5), handle='left'),
            dict(layer='9', start=(b, -35), end=(b, -5), handle='right')]


POINTS = [(0, 0), (60, 0), (60, 14), (17, 14), (17, 44),
          (7, 44), (7, 14), (0, 14)]


def test_chained_partial_dimension_is_not_total_section_height():
    evidence = partial_height_dimension(POINTS, 'Sul', dict(text='53', pos=(25, -22)), lines())
    assert evidence['section_span'] == 60
    assert evidence['span'] == 53
    assert evidence['extension_handles'] == ['left', 'right']


@pytest.mark.parametrize('value', ['60', '120'])
def test_whole_height_dimensions_including_scaled_are_retained(value):
    assert partial_height_dimension(POINTS, 'Sul', dict(text=value, pos=(25, -22)), lines(0, 60)) is None


def test_nearby_number_without_both_extensions_is_not_reclassified():
    assert partial_height_dimension(POINTS, 'Sul', dict(text='53', pos=(25, -22)), lines()[:2]) is None


def test_wrong_axis_dimension_is_not_height_evidence():
    assert partial_height_dimension(POINTS, 'Leste', dict(text='53', pos=(25, -22)), lines()) is None


def test_partial_dimension_rotated_with_section_is_rejected_as_total():
    rotate = lambda p: (p[1], p[0])
    rotated = [{**line, 'start': rotate(line['start']), 'end': rotate(line['end'])} for line in lines()]
    assert partial_height_dimension([rotate(p) for p in POINTS], 'Oeste',
                                    dict(text='53', pos=rotate((25, -22))), rotated)['span'] == 53


def test_ficha_keeps_full_height_and_clearance_when_label_is_traced_partial():
    from main import MainWindow
    window = MainWindow.__new__(MainWindow)
    window.dxf_data = {'lines': lines()}
    window._points_bbox_tuple = lambda pts: (0, 0, 60, 44)
    window._bbox_center_tuple = lambda bbox: (30, 22)
    window._slab_cut_direction = lambda *args: 'Sul'
    window._neighbor_by_direction = lambda *args, **_kw: None
    window._slab_height_value = lambda slab: '10' if slab else ''
    window._slab_dim_text = lambda slab: 'h=10' if slab else ''
    window._find_cut_view_cotas = lambda *args: {}
    window._nearest_dxf_text = lambda center, pattern, max_dist: (
        dict(text='53', pos=(25, -22)) if pattern.startswith('^\\d') else None)
    link = {'points': POINTS, 'ficha': {}}
    window._auto_fill_cut_view_ficha({'name': 'L1'}, link, [], {})
    assert float(link['ficha']['beam_height']) == 60
    assert float(link['ficha']['own_dist_bottom']) == 43
    assert 'beam_height_label' not in link['ficha']
    assert link['cut_dimension_debug']['partial_height_label']['span'] == 53
