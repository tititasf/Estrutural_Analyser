from copy import deepcopy
from types import SimpleNamespace

import pytest
from shapely.geometry import Point, Polygon

from portal.app.slab_step_overlay import missing_drawings, step_drawing
from portal.app.structural_cut_overlay import viewer_groups


def slab():
    return dict(name='LX', points=[[0,0],[200,0],[200,200],[0,200]], slab_steps=[
        dict(uid='region', points=[[0,0],[80,0],[80,120],[0,120]],
             height_cm=10, owner_height_cm=13, level_m=852.16,
             owner_level_m=852.19, sections=[])])


@pytest.mark.parametrize('rotate', [False, True])
def test_real_levels_and_local_internal_transition(rotate):
    state = dict(slabs=[slab()])
    if rotate:
        state['slabs'][0]['points'] = [[y,-x] for x,y in state['slabs'][0]['points']]
        state['slabs'][0]['slab_steps'][0]['points'] = [[y,-x] for x,y in state['slabs'][0]['slab_steps'][0]['points']]
    before = deepcopy(state)
    sections, blocked = missing_drawings(state)
    assert not blocked and len(sections) == 1
    drawing = sections[0]['drawing']
    assert Polygon(state['slabs'][0]['points']).contains(Point(drawing['anchor']))
    assert Polygon(drawing['points']).area == pytest.approx(25*(13+10))
    assert {p['text'] for p in drawing['primitives'] if p['kind']=='text'} >= {'13','10'}
    assert state == before


def test_original_precedence_and_missing_level_abstention():
    state = dict(slabs=[slab()])
    state['slabs'][0]['slab_steps'][0]['sections'] = [{'points':[]}]
    assert missing_drawings(state) == ([], [])
    state['slabs'][0]['slab_steps'][0]['sections'] = []
    del state['slabs'][0]['slab_steps'][0]['level_m']
    sections, blocked = missing_drawings(state)
    assert not sections and 'level_m ausente' in blocked[0]['reason']


def test_interpreted_group_draws_missing_step_and_preserves_inventory():
    state = dict(slabs=[slab()])
    inventory = dict(entries=[], physical_entries=[], slab_sections=[], blocked=[])
    before = deepcopy((state, inventory))
    group = viewer_groups(None, 'floor', state, SimpleNamespace(dxf_para_px=lambda *p:list(p)),
                          [], inventory=inventory)[-1]
    assert group['total'] == 1
    item = group['itens'][0]
    assert item['highlight_color'] == '#ffe033'
    assert item['section_kind'] == 'slab_step'
    assert item['step_uid'] == 'region' and item['section_drawing']['primitives']
    assert (state, inventory) == before


def test_unknown_region_geometry_is_not_drawn():
    s = slab()
    s['slab_steps'][0]['points'] = s['points']
    with pytest.raises(ValueError, match='transição interna'):
        step_drawing(s, s['slab_steps'][0])


@pytest.mark.parametrize('reverse', [False, True])
def test_same_soffit_top_step_is_drawn_above_not_below(reverse):
    s = slab()
    if reverse:
        s['slab_steps'][0]['points'].reverse()
    drawing = step_drawing(s, s['slab_steps'][0])
    points = drawing['points']
    # The selected vertical boundary produces a horizontal section. Check
    # physical elevation in CAD, not just polygon area or scalar metadata.
    assert points[0][1] == pytest.approx(points[3][1])
    assert points[7][1] > points[0][1]
    assert points[4][1] > points[3][1]
    assert points[7][1]-points[4][1] == pytest.approx(3)
