import math
from copy import deepcopy
import pytest
from src.core.dimension_geometry import mark_exploded_circle_dimensions
from src.core.lv_beam_scene import split_dimension_geometry, _line_segments


def fixture(scale=1, angle=0):
    def p(x, y):
        a = math.radians(angle)
        return (123 + scale * (x * math.cos(a) - y * math.sin(a)),
                -456 + scale * (x * math.sin(a) + y * math.cos(a)))
    return {'lines': [{'start': p(-15, 0), 'end': p(115, 0)},
                      {'start': p(0, -80), 'end': p(0, 15)},
                      {'start': p(100, -80), 'end': p(100, 15)}],
            'circles': [{'center': p(x, 0), 'radius': r * scale}
                        for x in (0, 100) for r in (1.4, 2.8)],
            'texts': [{'text': str(100 * scale), 'pos': p(40, 4),
                       'height': 11 * scale, 'rotation': angle}],
            'polylines': [{'points': [p(0, -80), p(100, -80), p(100, -61),
                                      p(0, -61), p(0, -80)]}]}


@pytest.mark.parametrize('scale,angle', [(1, 0), (.01, 90), (100, 180), (3, 37), (.00001, 37)])
def test_dimensions_scale_rotate_without_losing_entities(scale, angle):
    data = fixture(scale, angle)
    before = deepcopy(data)
    assert mark_exploded_circle_dimensions(data) == 3
    assert _line_segments(data['lines']) == []
    assert data['polylines'] == before['polylines']
    assert data['texts'][0]['annotation_role'] == 'dimension'
    assert data['texts'][0]['text'] == before['texts'][0]['text']
    for a, b in zip(data['lines'], before['lines']):
        assert a['start'] == b['start'] and a['end'] == b['end']


@pytest.mark.parametrize('missing', ['measurement', 'marker', 'witness', 'rotation'])
def test_insufficient_evidence_keeps_walls(missing):
    data = fixture()
    if missing == 'measurement':
        data['texts'][0]['text'] = '99'
    elif missing == 'marker':
        data['circles'] = data['circles'][:2]
    elif missing == 'witness':
        data['lines'].pop()
    else:
        data['texts'][0]['rotation'] = 90
    assert mark_exploded_circle_dimensions(data) == 0
    assert 'annotation_role' not in data['texts'][0]


def test_independent_wall_coincident_with_dimension_stays_structural():
    data = fixture()
    data['polylines'].append({'points': [(-1, 0), (1, 0)]})
    mark_exploded_circle_dimensions(data)
    structural, dimensions = split_dimension_geometry(data['lines'] + data['polylines'], data['texts'])
    assert (-1., 0., 1., 0.) in structural
    assert len(dimensions) == 3


def test_native_dimension_provenance_is_not_structural():
    line = {'start': (0, 0), 'end': (100, 0), 'annotation_role': 'dimension'}
    assert split_dimension_geometry([line]) == ([], [(0., 0., 100., 0.)])


def test_loader_marks_native_dimensions_without_removing_dxf_entities(tmp_path):
    import ezdxf
    from src.core.dxf_loader import DXFLoader
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0))
    msp.add_linear_dim(base=(0, 25), p1=(0, 0), p2=(100, 0)).render()
    path = tmp_path / 'native.dxf'
    doc.saveas(path)
    data = DXFLoader().load_dxf(str(path))
    dimensions = [l for l in data['lines'] if l.get('annotation_role') == 'dimension']
    assert dimensions
    assert len(_line_segments(data['lines'])) == 1
    assert len(list(ezdxf.readfile(path).modelspace().query('DIMENSION'))) == 1
