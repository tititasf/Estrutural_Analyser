import math

import pytest
from shapely.geometry import Polygon

from src.core.fv_generation_contract import build_fv_generation_contract, compute_panel_modules
from shapely.ops import unary_union


OUTLINE = [(0, 22.3), (21.1, 0), (255.7, 0), (248.2, 19),
           (29.3, 19), (13.8, 35.4), (0, 22.3)]


@pytest.mark.parametrize('angle', [0, 43.4, 90, 137, 225])
@pytest.mark.parametrize('reverse', [False, True])
def test_angled_fold_modulates_on_straight_and_preserves_exact_sa_polygon(angle, reverse):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    points = [(1000+x*c-y*s, 2000+x*s+y*c) for x, y in OUTLINE]
    if reverse:
        points.reverse()
    contract = build_fv_generation_contract('V987', {
        'dim_text': '19/55', 'segmentos_fundo': [
            {'length': 255.7, 'geometry': points, 'dim_width': 19}]})
    panels = contract['segments_rich'][0]['panels']
    assert len(panels) == 2
    assert panels[0]['width'] == pytest.approx(133.7)
    assert panels[1]['width'] == pytest.approx(122)
    restored_parts = []
    for panel in panels:
        assert 0 < panel['width'] <= 244
        frame = panel['sa_local_frame']
        ux, uy = frame['axis']
        ox, oy = frame['origin']
        restored_parts.append(Polygon([
            (ox+p['x']*ux-p['y']*uy, oy+p['x']*uy+p['y']*ux)
            for p in panel['vertices']]))
    assert unary_union(restored_parts).symmetric_difference(Polygon(points)).area < 1e-7
    assert restored_parts[0].intersection(restored_parts[1]).area < 1e-8
    # The manufacturing seam crosses only the parallel straight walls.
    assert restored_parts[0].boundary.intersection(restored_parts[1].boundary).length == pytest.approx(19)


@pytest.mark.parametrize('length', [1, 244, 244.001, 255.7, 488, 488.01, 500, 900])
def test_stock_modulation_retains_every_positive_remainder(length):
    widths = compute_panel_modules(length)
    assert sum(widths) == pytest.approx(length)
    assert all(0 < width <= 244 for width in widths)


def test_rectangular_sa_retains_robot_modulation():
    contract = build_fv_generation_contract('V987', {'segmentos_fundo': [
        {'length': 500, 'dim_width': 19,
         'geometry': [(0, 0), (500, 0), (500, 19), (0, 19), (0, 0)]}]})
    assert 'panels' not in contract['segments_rich'][0]


@pytest.mark.parametrize('points', [
    [(0, 0), (500, 0), (500, 19), (10, 19), (0, 9)],
    [(0, 0), (100, 0), (100, 19), (19, 19), (19, 80), (0, 80)],
])
def test_chamfer_and_right_angle_do_not_become_single_angled_panel(points):
    result = build_fv_generation_contract('V987', {'segmentos_fundo': [
        {'length': 500, 'dim_width': 19, 'geometry': points}]})
    assert result['segments_rich'][0].get('source_geometry') != 'sa_outline'


def test_explicit_panels_remain_authoritative():
    source = {'length': 255.7, 'dim_width': 19, 'geometry': OUTLINE,
              'panels': [{'width': 123, 'height': 19}]}
    result = build_fv_generation_contract('V987', {'segmentos_fundo': [source]})
    assert result['segments_rich'][0]['panels'] == source['panels']


@pytest.mark.parametrize('angle', [0, 43.4, 90, 225])
def test_angular_cap_uses_shared_solid_pillar_not_neighbor_label(angle):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    transform = lambda ps: [(1000+x*c-y*s, 2000+x*s+y*c) for x, y in ps]
    # The left cap is the last slanted edge, not the long bottom wall.
    pillar = {'name': 'P987', 'classification': 'SEGUE',
              'points': transform([(0,22.3), (13.8,35.4), (0,50), (-13.8,36.9)])}
    result = build_fv_generation_contract('V987', {'segmentos_fundo': [{
        'length':255.7, 'dim_width':19, 'geometry':transform(OUTLINE),
        'apoio_inicial':'V999', 'apoio_final':'V998'}]}, pillars=[pillar])
    # Stable local axis may exchange physical left/right after a half rotation.
    segment = result['segments_rich'][0]
    assert 'P987' in (segment['texto_esq'], segment['texto_dir'])
    assert 'P987' in (result['label_left'], result['label_right'])
    assert segment['support_source'] == 'sa_shared_solid_pillar_cap'


@pytest.mark.parametrize('classification,points', [
    ('NASCE', [(0,22.3), (13.8,35.4), (0,50), (-13.8,36.9)]),
    ('SEGUE', [(0,22.3), (-19,22.3), (-19,40), (0,40)]),  # point only
    ('SEGUE', [(-1,23.3), (12.8,36.4), (-1,51), (-14.8,37.9)]),  # nearby
])
def test_no_support_inference_from_non_solid_point_or_proximity(classification, points):
    result = build_fv_generation_contract('V987', {'segmentos_fundo': [{
        'length':255.7, 'geometry':OUTLINE, 'apoio_inicial':'V999'}]},
        pillars=[{'name':'P987','classification':classification,'points':points}])
    assert result['label_left'] == 'V999'
    assert 'support_source' not in result['segments_rich'][0]


def test_ambiguous_cap_keeps_sa_support():
    pillars = [{'name':name, 'classification':'SEGUE',
                'points':[(0,22.3), (13.8,35.4), (0,50), (-13.8,36.9)]}
               for name in ('P987','P988')]
    result = build_fv_generation_contract('V987', {'segmentos_fundo': [{
        'length':255.7,'geometry':OUTLINE,'apoio_inicial':'V999'}]}, pillars=pillars)
    assert result['label_left'] == 'V999'
