from copy import deepcopy
import json
from pathlib import Path

import pytest
from shapely.geometry import mapping, box

from portal.app.preprocessamento.adapters.named_section_slabs import (
    METHOD, attach_named_section_facts, project_wing, resolve_named_section_slabs, wings)
from portal.app.preprocessamento.sa_levels import consume_item_levels, item_level_input


def test_t_section_preserves_both_bands_and_rejects_wrong_width():
    ring = [(0, 10), (40, 10), (40, 40), (59, 40), (59, 10), (100, 10), (100, -2), (0, -2), (0, 10)]
    assert [w['height'] for w in wings(ring, 10, 19)] == [12, 12]
    assert wings(ring, 10, 22) == []
    assert wings(ring, 0, 19) == []


def test_projection_is_bounded_and_view_direction_changes_side():
    link = {'bounded_axis': [[0, 0], [0, 100]], 'view_direction': [-1, 0]}
    candidate = {'axis_intervals': [[.4, .59]]}
    wing = {'stem_interval': [40, 59], 'x_interval': [-100, 40]}
    assert list(project_wing(link, candidate, wing, 1).coords) == [(0, 59), (0, 100)]
    link['view_direction'] = [1, 0]
    assert list(project_wing(link, candidate, wing, 1).coords) == [(0, 0), (0, 40)]
    assert project_wing(link, candidate, wing, 2) is None
    candidate['axis_intervals'].append([.7, .9])
    assert project_wing(link, candidate, wing, 1) is None


def test_conflicting_seed_is_not_exported_or_applied():
    item = {'item_id': 'a', 'item_class': 'slab', 'display_name': 'L1',
            'levels': [{'field': 'slab_level', 'value': 1, 'method': 'other', 'status': 'sa_evidence', 'item_id': 'a', 'fact_id': 'old'}]}
    row = {'name': 'L1', 'value': 2, 'method': METHOD, 'marker_handle': 'm', 'unit': 'm',
           'evidence_ids': ['cad:m'], 'confidence_pct': 75, 'target_geometry': mapping(box(0, 0, 10, 10))}
    attach_named_section_facts([item], [row], {})
    assert item['levels'][-1]['status'] == 'conflict'
    assert item_level_input({'level_inventory': {'items': [item]}, 'levels': item['levels']}) == {}


def test_consumer_rejects_changed_contour_and_preserves_human():
    row = {'value': 537.86, 'unit': 'm', 'method': METHOD, 'evidence_ids': ['cad:m'],
           'target_geometry': mapping(box(0, 0, 10, 10))}
    slab = {'name': 'L1', 'points': [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]}
    assert consume_item_levels([slab], {'L1': row})[0]['value'] == 537.86
    assert slab['level_inference']['status'] == 'inferred'
    slab['points'][1] = [11, 0]
    assert consume_item_levels([slab], {'L1': row}) == []
    slab['points'][1] = [10, 0]
    slab['validated_fields'] = ['laje_nivel']
    assert consume_item_levels([slab], {'L1': row}) == []


def test_competing_named_cuts_do_not_confirm_each_other():
    item = {'item_id': 'a', 'item_class': 'slab', 'display_name': 'L1', 'levels': []}
    row = {'name': 'L1', 'value': 2, 'method': METHOD, 'marker_handle': 'm', 'unit': 'm',
           'evidence_ids': ['cad:m'], 'confidence_pct': 75,
           'target_geometry': mapping(box(0, 0, 10, 10)), 'region_geometry': mapping(box(0, 0, 8, 10))}
    other = {**row, 'marker_handle': 'n', 'value': 3}
    attach_named_section_facts([item], [row, other], {})
    assert all(f['status'] == 'conflict' for f in item['levels'])
    assert item_level_input({'level_inventory': {'items': [item]}, 'levels': item['levels']}) == {}


@pytest.mark.parametrize('scale', [float('nan'), float('inf')])
def test_nonfinite_projection_rejected(scale):
    assert project_wing({'bounded_axis': [[0, 0], [0, 100]], 'view_direction': [-1, 0]},
                        {'axis_intervals': [[.4, .59]]},
                        {'stem_interval': [40, 59], 'x_interval': [-100, 40]}, scale) is None


@pytest.fixture
def actual():
    directory = Path(__file__).resolve().parents[2]/'scripts/arete/relatorios/20261009_reprocessamento'
    package = directory/'pre_v44_full.json'
    if not package.is_file():
        pytest.skip('real immutable DXF regression fixture unavailable')
    p = json.loads(package.read_text(encoding='utf-8'))[0]
    c = json.loads((directory/'pre_v44_collection.json').read_text(encoding='utf-8'))
    root = directory/'named_section_fixture'
    source = next(s for s in p['sources'] if s['source_id'] == p['scope']['recorte_id'])
    c['tower_path'] = root/source['relative_path']
    return root, p, c


def test_real_section_selects_current_floor_and_principal_regions(actual):
    root, p, c = actual
    rows = resolve_named_section_slabs(root, p, c)
    assert {r['name'] for r in rows} == {'L13', 'L18'}
    assert {r['value'] for r in rows} == {537.86}
    assert {r['marker_handle'] for r in rows} == {'6F6F'}
    assert len({r['independent_origin'] for r in rows}) == 1
    assert all(r['target_geometry'] != r['region_geometry'] for r in rows)


def test_real_inferred_cut_deltas_reach_consumer_only_with_traced_roots():
    directory = Path(__file__).resolve().parents[2]/'scripts/arete/relatorios/20261009_reprocessamento'
    fixture = directory/'pre_v45_full.json'
    if not fixture.is_file():
        pytest.skip('real V45 package unavailable')
    p = json.loads(fixture.read_text(encoding='utf-8'))[0]
    rows = item_level_input(p)
    assert rows['L15']['value'] == 537.84 and rows['L16']['value'] == 537.81
    names = {i['item_id']:i['display_name'] for i in p['level_inventory']['items']}
    target = next(f for f in p['levels'] if names.get(f.get('item_id')) == 'L15'
                  and f.get('method') == 'scoped_cut_wing_relative_delta_cm')
    root = next(f for f in p['levels'] if f['fact_id'] in target['source_fact_ids'])
    root.pop('section_revision')
    assert 'value' not in item_level_input(p).get('L15', {})


@pytest.mark.parametrize('mutation', ['floor', 'revision', 'pillar_width', 'markers', 'multiple_pillars', 'thickness'])
def test_real_wrong_scope_or_geometry_never_becomes_a_seed(actual, mutation):
    root, p, c = actual
    entry = next(e for e in p['auxiliary_evidence'] if e.get('section_vertical_levels', {}).get('status') == 'calibrated_section_only')
    if mutation == 'floor':
        p['level_inventory']['reference']['floor_selection']['representative_floor'] = 3
    elif mutation == 'revision':
        entry['section_vertical_levels']['source_revision'] = 'stale'
    elif mutation == 'markers':
        entry['section_vertical_levels']['anchors'][-1]['value_m'] += .1
    elif mutation == 'multiple_pillars':
        entry['plan_callout_links'][0]['pillar_axis_candidates'] *= 2
    elif mutation == 'thickness':
        for slab in c['state']['slabs']:
            slab['fields']['laje_dim'] = 'h=15'
    else:
        for t in entry['texts']:
            if t['text'] == '19/140-S':
                t['text'] = '22/140-S'
    assert resolve_named_section_slabs(root, p, c) == []
