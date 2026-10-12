from copy import deepcopy

import pytest

from portal.app.routers.viewer_routes import _ajustes_pontas_lateral, _geometria_dos_itens


@pytest.mark.parametrize('classe', ['lateral_a_para', 'lateral_b_para', 'lateral_a_passa', 'lateral_b_passa'])
@pytest.mark.parametrize('values', [(-11, 0), (-4, 11), (4, -11), (0, 0)])
def test_adjustments_preserve_sign_and_independent_ends(classe, values):
    item = {'lv_cell': dict(zip(('adjustment_start', 'adjustment_end'), values))}
    original = deepcopy(item)
    result = _ajustes_pontas_lateral(item, classe)
    assert (result['esquerda'], result['direita']) == values
    assert item == original


@pytest.mark.parametrize('raw', [None, '', 'bad', True, float('nan'), float('inf')])
def test_missing_or_invalid_is_unknown_not_zero(raw):
    result = _ajustes_pontas_lateral({'lv_cell': {'adjustment_start': raw, 'adjustment_end': 0}}, 'lateral_b_passa')
    assert result['esquerda'] is None
    assert result['direita'] == 0


def test_reversed_b_geometry_retains_local_endpoint_order():
    points = [[90, 12], [10, 12]]
    state = {'segmentos': {'lateral_b_para': [{
        'uid': 'B1', 'beam_name': 'V1', 'side': 'B', 'segment_label': '1',
        'points': points, 'lv_cell': {'adjustment_start': -11, 'adjustment_end': 4},
    }]}}
    original = deepcopy(state)
    class Transform:
        largura_px = altura_px = 100
        def dxf_para_px(self, x, y):
            return (x, 100-y)
    item, = _geometria_dos_itens(state, 'lateral_b_para', Transform())
    assert item['pontos_px'] == [(90, 88), (10, 88)]
    assert item['ajustes_pontas']['esquerda'] == -11
    assert item['ajustes_pontas']['direita'] == 4
    assert state == original
    assert _ajustes_pontas_lateral({}, 'fundo') is None
