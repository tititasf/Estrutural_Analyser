from copy import deepcopy

import pytest

from portal.app.lv_cut_coverage import soffit_drawings
from portal.tests.test_structural_cut_overlay import data


def bottoms(vertical=False):
    result = []
    for index, (a,b) in enumerate(((0,100),(100,200)), 1):
        points = [[a,0],[b,0],[b,19],[a,19]]
        if vertical:
            points = [[-y,x] for x,y in points]
        result.append(dict(uid=f'f{index}',beam_name='V1',segment_label=str(index),points=points))
    return result


@pytest.mark.parametrize('vertical', [False,True])
def test_repeated_profile_drawn_in_every_soffit_not_only_longest_pair(vertical):
    source = data(vertical)
    pair = source['cut_views'][0]['pairs'][0]
    pair.update(end=[0,200] if vertical else [200,0], length_cm=200)
    source['sides']['B']['segments'][0]['points'] = [[-19,200],[-19,0]] if vertical else [[200,19],[0,19]]
    drawings, blocked, coverage = soffit_drawings(source['cut_views'],source['sides'],bottoms(vertical))
    assert not blocked
    assert len(drawings) == 2
    assert {d['fundo_id'] for d in drawings} == {'f1','f2'}
    assert all(r['status'] == 'interpreted' for r in coverage)
    assert [d['anchor'][1 if vertical else 0] for d in drawings] == [50,150]
    assert source['cut_views'][0]['pairs'][0]['length_cm'] == 200


def test_original_only_replaces_its_own_soffit_occurrence():
    source = data()
    pair = source['cut_views'][0]['pairs'][0]
    pair.update(end=[200,0],length_cm=200)
    source['sides']['B']['segments'][0]['points'] = [[200,19],[0,19]]
    # Horizontal section's width runs across the horizontal beam in plan.
    original = dict(id='original',beam='V1',kind='identified',source_cut=dict(
        pts=[[22.5,0],[22.5,19],[64.5,19],[64.5,39],[77.5,39],[77.5,0]],beam_w=19,beam_h=55,
        own_laje='L1',ficha=dict(direction='norte',side_a_laje_name='L1',
            own_slab_height=13,own_dist_top=0,own_dist_bottom=42,beam_lajes_side_b='0')))
    drawings, blocked, coverage = soffit_drawings([original,*source['cut_views']],source['sides'],bottoms())
    assert not blocked
    assert len(drawings) == 2
    assert [r['status'] for r in coverage] == ['original','interpreted']
    assert {d['fundo_id'] for d in drawings} == {'f1','f2'}


def test_unknown_slab_level_has_per_soffit_reason_instead_of_fabricated_section():
    source = data()
    source['cut_views'][0]['profiles']['B']['slabs'] = [dict(name='L1',height_cm=13,level=None)]
    drawings, blocked, coverage = soffit_drawings(source['cut_views'],source['sides'],bottoms()[:1])
    assert not drawings
    assert coverage[0]['status'] == 'pending'
    assert 'B.L1.level' in coverage[0]['reason']


def test_original_is_preserved_without_certifying_a_different_local_height():
    source = data()
    original = dict(id='original',beam='V1',kind='identified',source_cut=dict(
        pts=[[22.5,0],[22.5,19],[64.5,19],[64.5,39],[77.5,39],[77.5,0]],beam_w=19,beam_h=55,
        own_laje='L1',ficha=dict(direction='norte',side_a_laje_name='L1',
            own_slab_height=13,own_dist_top=0,own_dist_bottom=42,beam_lajes_side_b='0')))
    source['cut_views'][0]['beam_height_cm'] = 71
    drawings, blocked, coverage = soffit_drawings(
        [original,*source['cut_views']],source['sides'],bottoms()[:1])
    assert not blocked
    assert len(drawings) == 1 and drawings[0]['cut_index'] == 0
    assert coverage[0]['status'] == 'pending'
    assert coverage[0]['profile_change_indexes'] == [1]
    assert 'subdivisão' in coverage[0]['reason']


def test_shared_presentations_do_not_merge_different_soffits():
    from portal.app.structural_cut_overlay import deduplicate_sections
    source = data()
    first = dict(beam='V1',kind='calculated',behavior='passa',behaviors=['passa'],
                 fundo_id='f1',drawing=dict(anchor=[0,0],primitives=[]))
    other = deepcopy(first)
    other.update(behavior='para',behaviors=['para'])
    distinct = deepcopy(other)
    distinct['fundo_id'] = 'f2'
    assert len(deduplicate_sections([first,other,distinct])) == 2
