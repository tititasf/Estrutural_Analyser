from copy import deepcopy

import pytest
from scripts.arete.sa_development_diff import compare_states, numeric_value


def row(points, level='855.25', name='V406'):
    return dict(beam_name=name, points=points, level=level)


def state(rows):
    return dict(segmentos={'fundo': rows}, pilares=[], slabs=[])


RECT = [(0, 0), (20, 0), (20, 10), (0, 10)]


def test_partition_and_ring_order_do_not_invent_regression():
    before = state([row(RECT)])
    after = state([
        row([(0, 0), (10, 0), (10, 10), (0, 10)], '855,250'),
        row([(10, 10), (20, 10), (20, 0), (10, 0)], '855.25'),
    ])
    assert compare_states(before, after)['unchanged']


def test_real_corner_loss_is_reported_even_with_same_level():
    before = state([row(RECT)])
    after = state([row([(0, 0), (20, 0), (20, 10), (10, 10), (0, 5)])])
    diff = compare_states(before, after)
    assert diff['geometry_changes'][0]['removed_area_cm2'] == pytest.approx(25)
    assert not diff['numeric_changes']
    assert diff['pending_count'] == 1
    assert diff['reviewed'] is False


def test_shift_with_same_area_is_detected():
    diff = compare_states(state([row(RECT)]), state([row([(x+1, y) for x, y in RECT])]))
    change = diff['geometry_changes'][0]
    assert change['added_area_cm2'] == change['removed_area_cm2'] == 10


def test_level_change_on_only_half_of_segment_is_spatially_located():
    after = state([
        row([(0, 0), (10, 0), (10, 10), (0, 10)]),
        row([(10, 0), (20, 0), (20, 10), (10, 10)], '855.18'),
    ])
    diff = compare_states(state([row(RECT)]), after)
    assert not diff['geometry_changes']
    assert len(diff['numeric_changes']) == 2
    assert sum(c['removed_region_cm2'] for c in diff['numeric_changes']) == 100
    assert sum(c['added_region_cm2'] for c in diff['numeric_changes']) == 100


def test_added_geometry_is_not_misreported_as_changed_existing_level():
    after = state([row(RECT), row([(20, 0), (30, 0), (30, 10), (20, 10)])])
    diff = compare_states(state([row(RECT)]), after)
    assert diff['geometry_changes'][0]['added_area_cm2'] == 100
    assert not diff['numeric_changes']


def test_added_and_removed_items_are_pending():
    diff = compare_states(state([row(RECT, name='OLD')]), state([row(RECT, name='NEW')]))
    assert {c['change'] for c in diff['geometry_changes']} == {'added_item', 'removed_item'}


def test_pillar_and_slab_scalar_changes_are_detected_without_mutation():
    before = {'pilares': [dict(name='P34', points=RECT, nivel_str='855.25')],
              'slabs': [dict(name='L415', points=RECT, nivel='855.25', height='12')]}
    after = deepcopy(before)
    after['pilares'][0]['nivel_str'] = '855.18'
    after['slabs'][0]['height'] = '13'
    frozen = deepcopy(before)
    diff = compare_states(before, after)
    assert {c['field'] for c in diff['numeric_changes']} == {'nivel_str', 'height'}
    assert before == frozen


def test_invalid_geometry_fails_closed():
    broken = state([row([(0, 0), (1, 1), (0, 1), (1, 0)])])
    assert compare_states(broken, broken)['geometry_errors']
    assert not compare_states(broken, broken)['unchanged']


def test_homonymous_slab_levels_are_bound_to_physical_parcels_not_list_order():
    before = dict(slabs=[dict(name='L9', points=RECT, nivel='855.22', height='12'),
                        dict(name='L9', points=[(x+40,y) for x,y in RECT], nivel='855.25', height='15')])
    after = deepcopy(before)
    after['slabs'].reverse()
    assert compare_states(before, after)['unchanged']
    after['slabs'][0]['nivel'] = '855.22'
    diff = compare_states(before, after)
    assert not diff['geometry_changes']
    assert len(diff['numeric_changes']) == 2
    assert {c['field'] for c in diff['numeric_changes']} == {'nivel_on_physical_region'}
    assert sum(c['removed_region_cm2'] for c in diff['numeric_changes']) == 200
    after['slabs'][0]['height'] = '12'
    assert {c['field'] for c in compare_states(before, after)['numeric_changes']} == {'nivel_on_physical_region','height_on_physical_region'}


def test_machine_noise_is_not_a_physical_change():
    diff = compare_states(state([row(RECT)]), state([row([(x+1e-12, y) for x, y in RECT])]))
    assert diff['unchanged']


def test_units_are_not_guessed_or_converted():
    assert numeric_value('855,250') == numeric_value('855.25')
    assert numeric_value('855.25cm') != numeric_value('855.25m')


def linear_state(rows):
    return dict(segmentos={'lateral_a_para': rows}, pilares=[], slabs=[])


def test_lateral_lines_are_valid_and_partition_invariant():
    before = linear_state([row([(0, 0), (20, 0)])])
    after = linear_state([row([(10, 0), (0, 0)]), row([(10, 0), (20, 0)])])
    diff = compare_states(before, after)
    assert diff['unchanged']
    assert not diff['geometry_errors']


def test_lateral_length_loss_is_detected_without_area():
    diff = compare_states(linear_state([row([(0, 0), (20, 0)])]),
                          linear_state([row([(0, 0), (15, 0)])]))
    change = diff['geometry_changes'][0]
    assert change['removed_area_cm2'] == 0
    assert change['removed_length_cm'] == pytest.approx(5)
    assert not diff['numeric_changes']


def test_parallel_line_translation_with_same_length_is_detected():
    diff = compare_states(linear_state([row([(0, 0), (20, 0)])]),
                          linear_state([row([(0, 1), (20, 1)])]))
    change = diff['geometry_changes'][0]
    assert change['hausdorff_cm'] == 1
    assert change['removed_length_cm'] == change['added_length_cm'] == 20


def test_lateral_partial_level_change_is_detected_by_length():
    before = linear_state([row([(0, 0), (20, 0)])])
    after = linear_state([row([(0, 0), (10, 0)]), row([(10, 0), (20, 0)], '855.18')])
    diff = compare_states(before, after)
    assert not diff['geometry_changes']
    assert len(diff['numeric_changes']) == 2
    assert sum(c['removed_span_cm'] for c in diff['numeric_changes']) == pytest.approx(10)
    assert sum(c['added_span_cm'] for c in diff['numeric_changes']) == pytest.approx(10)


def test_lateral_machine_noise_does_not_invent_translation_or_level_change():
    before = linear_state([row([(0, 0), (20, 0)])])
    after = linear_state([row([(0, 1e-12), (20, 1e-12)])])
    assert compare_states(before, after)['unchanged']


def test_zero_length_lateral_is_invalid():
    invalid = linear_state([row([(0, 0), (0, 0)])])
    assert compare_states(invalid, invalid)['geometry_errors']


def pillar_state(rows):
    return {'pilares':[dict(name='P',points=RECT,nivel_str='855.25',
        interpretacao_abcd={'faces':{'C':{'passa':rows}}})]}


def test_removed_contact_blocks_even_when_geometry_level_and_remaining_measurements_match():
    before=pillar_state([{'nome':'V1'},{'nome':'V2'}])
    after=pillar_state([{'nome':'V2'}])
    diff=compare_states(before,after)
    assert not diff['geometry_changes'] and not diff['numeric_changes']
    assert diff['contact_changes'][0]['removed_contacts']==[('C','passa','V1')]
    assert diff['pending_count']==1 and not diff['unchanged']


def test_contact_row_order_duplicates_and_none_placeholder_do_not_change_inventory():
    before=pillar_state([{'nome':'V1'},{'nome':'V2'}])
    after=pillar_state([{'nome':'V2'},{'nome':'V1'},{'nome':'V1'},{'nome':'nenhuma'}])
    assert compare_states(before,after)['unchanged']


def test_face_or_role_change_preserves_both_removed_and_added_contact():
    before=pillar_state([{'nome':'V1'}])
    after=deepcopy(before)
    after['pilares'][0]['interpretacao_abcd']['faces']={'D':{'interior':[{'nome':'V1'}]}}
    change=compare_states(before,after)['contact_changes'][0]
    assert change['removed_contacts']==[('C','passa','V1')]
    assert change['added_contacts']==[('D','interior','V1')]
    assert change['original_source_review_required']
