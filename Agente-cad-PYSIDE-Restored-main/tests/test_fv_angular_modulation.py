import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gerar_fv_dxf_stog as fv
from src.core.fv_generation_contract import _modulate_outline_panel


def test_modulated_fold_keeps_rails_and_all_detail_dimensions():
    panel = {'width': 255.7, 'height': 35.4, 'source': 'sa_outline',
             'vertices': [{'x': x, 'y': y} for x, y in [
                 (0,22.3),(21.1,0),(255.7,0),(248.2,19),(29.3,19),(13.8,35.4),(0,22.3)]],
             'sa_local_frame': {'origin': [0,0], 'axis': [1,0]}}
    parts = _modulate_outline_panel(panel)
    doc = fv.setup_doc()
    fv.draw_viga(doc.modelspace(), 0, 0, [{'total_width': 255.7, 'panels': parts}],
                 19, 'V987', label_left='', label_right='')
    measures = [round(e.get_measurement(), 1) for e in doc.modelspace().query('DIMENSION')]
    for expected in (133.7,122,21.1,15.5,16.4,35.4,22.3,13.1,19,7.5):
        assert expected in measures
    assert parts[0]['angled_l']['main_height'] == 19
    rails = list(doc.modelspace().query(f'LINE[layer=="{fv.SARR_LAYER}"]'))
    assert any(abs(e.dxf.start.x-e.dxf.end.x)>1 and abs(e.dxf.start.y-e.dxf.end.y)>1 for e in rails)
    assert sum(p['width'] for p in parts) == pytest.approx(255.7)


def test_stock_join_moves_inside_straight_body_not_to_fold_vertex():
    panel = {'width': 255.7, 'height': 40, 'source': 'sa_outline',
             'vertices': [{'x':x,'y':y} for x,y in [
                 (0,22),(190,0),(255.7,0),(255.7,19),(200,19),(10,40),(0,22)]],
             'sa_local_frame': {'origin':[0,0],'axis':[1,0]}}
    parts = _modulate_outline_panel(panel)
    assert 200 < parts[0]['width'] < 244
    assert all(0 < p['width'] <= 244 for p in parts)
    assert sum(p['width'] for p in parts) == pytest.approx(255.7)


def test_fold_that_does_not_fit_stock_requires_review_not_join_at_fold():
    panel = {'width': 300, 'height': 40, 'source': 'sa_outline',
             'vertices': [{'x':x,'y':y} for x,y in [
                 (0,22),(234,0),(300,0),(300,19),(244,19),(10,40),(0,22)]],
             'sa_local_frame': {'origin':[0,0],'axis':[1,0]}}
    with pytest.raises(ValueError,match='revisar'):
        _modulate_outline_panel(panel)
