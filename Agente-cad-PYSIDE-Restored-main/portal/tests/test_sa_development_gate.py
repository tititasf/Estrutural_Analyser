from copy import deepcopy

import pytest

from portal.app.sa_development_gate import assess_cycle


def fixture_cycle():
    package = {'level_inventory': {'items': [
        {'item_id': 'p1', 'display_name': 'P1', 'item_class': 'pillar', 'level_fact_ids': ['f1']},
        {'item_id': 'b1', 'display_name': 'V1', 'item_class': 'beam'}],
        'beam_segments': [
            {'beam_item_id': 'b1', 'beam_name': 'V1', 'family': 'fundo', 'segment_id': 's1',
             'status': 'sa_evidence', 'level': 10},
            {'beam_item_id': 'b1', 'beam_name': 'V1', 'family': 'lateral_a_para', 'segment_id': 's2',
             'behavior': 'Para', 'status': 'inferred', 'level': 10}]},
        'levels': [{'item_id': 'p1', 'fact_id': 'f1', 'field': 'top', 'status': 'sa_evidence', 'value': 10},
                   {'item_id': 'b1', 'field': 'level', 'status': 'sa_evidence', 'value': 10}]}
    entry = dict(status='confere', divergencias=[], incertos=[], medidos=1,
                 snapshot_sha256='abc', medido_em='2026-10-10T12:00:00')
    qa = {'schema': 'cad.qa_gate_pavimento/v1', 'source': 'source.dxf', 'source_sha256': 'sourcehash',
          'classes': {'PIL': {'P1': deepcopy(entry)}, 'FV': {'V1': deepcopy(entry)},
                      'LV': {'V1|para': deepcopy(entry)}}}
    return package, qa


def test_complete_cycle_ready_but_visual_review_still_required_and_inputs_unchanged():
    package, qa = fixture_cycle()
    before = deepcopy((package, qa))
    result = assess_cycle(package, qa)
    assert result['ready_for_publication'] is True
    assert result['final_visual_approved'] is False and result['visual_review_required'] is True
    assert result['pending'] == [] and result['expected_qa_units'] == 3
    assert (package, qa) == before


@pytest.mark.parametrize('status', ['unknown', 'conflict', 'candidate', 'estimated'])
def test_unresolved_applicable_fact_blocks_even_when_numeric_and_qa_green(status):
    package, qa = fixture_cycle()
    package['levels'][0]['status'] = status
    result = assess_cycle(package, qa)
    assert not result['ready_for_publication']
    assert any(p['kind'] == 'level_pending' for p in result['pending_by_unit']['P1'])


def test_estimated_part_of_otherwise_resolved_range_blocks():
    package, qa = fixture_cycle()
    package['level_inventory']['beam_segments'][0]['level_ranges'] = [
        {'range_start': 0, 'range_end': 2, 'value': 10, 'status': 'sa_evidence'},
        {'range_start': 2, 'range_end': 3, 'value': 10, 'status': 'estimated'}]
    result = assess_cycle(package, qa)
    assert not result['ready_for_publication']
    assert any(p['field'].endswith('range:1') for p in result['pending_by_unit']['V1'])


@pytest.mark.parametrize('status', ['diverge', 'incerto', 'indisponivel'])
def test_qa_status_blocks_without_hiding_behind_empty_messages(status):
    package, qa = fixture_cycle()
    qa['classes']['PIL']['P1']['status'] = status
    assert not assess_cycle(package, qa)['ready_for_publication']


@pytest.mark.parametrize('change', ['zero', 'field', 'class', 'item', 'messages', 'source'])
def test_green_status_alone_cannot_prove_complete_qa(change):
    package, qa = fixture_cycle()
    if change == 'zero': qa['classes']['PIL']['P1']['medidos'] = 0
    if change == 'field': qa['classes']['PIL']['P1'].pop('snapshot_sha256')
    if change == 'class': qa['classes'].pop('LV')
    if change == 'item': qa['classes']['FV'].clear()
    if change == 'messages': qa['classes']['FV']['V1']['divergencias'] = ['parede deslocada']
    if change == 'source': qa.pop('source_sha256')
    assert not assess_cycle(package, qa)['ready_for_publication']


@pytest.mark.parametrize('package,qa', [({}, {}), (None, None), ({'level_inventory': {'items': []}}, {})])
def test_empty_inputs_never_pass(package, qa):
    assert not assess_cycle(package, qa)['ready_for_publication']


def test_not_applicable_is_not_pending_and_regression_still_blocks():
    package, qa = fixture_cycle()
    package['levels'][0] = dict(item_id='p1', fact_id='f1', field='top', status='not_applicable', value=None)
    qa['classes']['PIL']['P1'] = {'status': 'not_applicable'}
    assert assess_cycle(package, qa)['ready_for_publication']
    result = assess_cycle(package, qa, [{'unit': 'V1', 'reason': 'perda de área'}])
    assert not result['ready_for_publication']
    assert result['pending_by_unit']['V1'][0]['kind'] == 'regression'


def test_flat_preliminary_unknown_remains_visible_and_missing_fact_reference_blocks():
    package, qa = fixture_cycle()
    package['pre_sa_survey_levels'] = [{'item_id': 'p1', 'field': 'base', 'status': 'unknown', 'value': None}]
    package['level_inventory']['items'][0]['level_fact_ids'].append('missing')
    result = assess_cycle(package, qa)
    assert not result['ready_for_publication']
    assert any(p['field'] == 'missing' for p in result['pending_by_unit']['P1'])


def test_beam_without_segments_cannot_disappear_from_expected_qa():
    package, qa = fixture_cycle()
    package['level_inventory']['beam_segments'] = []
    package['level_inventory']['items'][1]['segments'] = []
    assert not assess_cycle(package, qa)['ready_for_publication']


def test_pre_conflict_and_failed_context_are_reported():
    package, qa = fixture_cycle()
    package['conflicts'] = [{'item_id': 'p1', 'kind': 'contorno'}]
    package['context_qa'] = {'status': 'failed', 'error': 'sem fonte'}
    result = assess_cycle(package, qa)
    assert not result['ready_for_publication']
    assert 'P1' in result['pending_by_unit'] and 'cycle' in result['pending_by_unit']



def test_segmented_level_without_measured_parts_does_not_pass():
    package, qa = fixture_cycle()
    package['levels'][0].update(status='segmented', value=None)
    assert not assess_cycle(package, qa)['ready_for_publication']


def test_source_revision_mismatch_blocks_stale_green_qa():
    package, qa = fixture_cycle()
    package['scope'] = {'recorte_id': 'source1'}
    package['sources'] = [{'source_id': 'source1', 'revision': 'newrevision'}]
    assert not assess_cycle(package, qa)['ready_for_publication']
    qa['source_sha256'] = 'newrevision'
    assert assess_cycle(package, qa)['ready_for_publication']



def test_current_flat_resolved_level_supersedes_unknown_survey_and_item_history():
    package, qa = fixture_cycle()
    historical = {'item_id': 'p1', 'field': 'top', 'status': 'unknown', 'value': None}
    package['pre_sa_survey_levels'] = [historical]
    package['level_inventory']['items'][0]['pre_sa_levels'] = [deepcopy(historical)]
    assert assess_cycle(package, qa)['ready_for_publication']
    package['levels'][0].update(status='unknown', value=None)
    assert not assess_cycle(package, qa)['ready_for_publication']


def test_embedded_current_level_supersedes_historical_unknown_when_flat_fact_absent():
    package, qa = fixture_cycle()
    current = package['levels'].pop(0)
    package['level_inventory']['items'][0]['levels'] = [current]
    package['pre_sa_survey_levels'] = [dict(current, status='unknown', value=None)]
    assert assess_cycle(package, qa)['ready_for_publication']
    current.update(status='estimated', value=10)
    assert not assess_cycle(package, qa)['ready_for_publication']


def test_current_unknown_is_not_rescued_by_resolved_historical_fact():
    package, qa = fixture_cycle()
    package['pre_sa_survey_levels'] = [deepcopy(package['levels'][0])]
    package['levels'][0].update(status='unknown', value=None)
    assert not assess_cycle(package, qa)['ready_for_publication']


def test_current_fv_superior_datum_supersedes_only_historical_top():
    package, qa = fixture_cycle()
    package['levels'][1].update(field='fundo', evidence_ids=['measured-fv'])
    package['pre_sa_survey_levels'] = [
        dict(item_id='b1', field='beam_top', status='unknown', value=None),
        dict(item_id='b1', field='beam_bottom', status='unknown', value=None)]
    result = assess_cycle(package, qa)
    assert any(n['kind'] == 'historical_level_superseded' for n in result['preserved_notes'])
    assert not any(p['field'] == 'beam_top' for p in result['pending'])
    assert any(p['field'] == 'beam_bottom' for p in result['pending'])
    package['level_inventory']['beam_segments'][0]['level'] = 11
    assert any(p['field'] == 'beam_top' for p in assess_cycle(package, qa)['pending'])


def region_cycle():
    package, qa = fixture_cycle()
    from shapely.geometry import Polygon, mapping
    step = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    principal = Polygon([(-1, -1), (2, -1), (2, 2), (-1, 2)], [list(step.exterior.coords)])
    for i, geometry in enumerate([step, principal]):
        package['levels'].append(dict(item_id='p1', fact_id=f'r{i}', field='slab_region_level',
            region_id=f'region{i}', datum_id='datum1', unit='m', value=10+i,
            status='sa_evidence', evidence_ids=['source'], region_geometry=mapping(geometry)))
    package['conflicts'] = [dict(item_id='p1', kind='divergent_values_or_reference',
                                 field='slab_region_level', fact_ids=['r0', 'r1'])]
    return package, qa


def test_measured_disjoint_regions_preserve_original_conflict_as_note():
    package, qa = region_cycle()
    before = deepcopy(package)
    result = assess_cycle(package, qa)
    assert result['ready_for_publication']
    assert result['preserved_notes'][0]['conflict'] == package['conflicts'][0]
    assert package == before
    qa['classes']['PIL']['P1']['divergencias'] = ['actual discrepancy']
    assert not assess_cycle(package, qa)['ready_for_publication']


@pytest.mark.parametrize('change', ['overlap', 'datum', 'geometry', 'unknown', 'evidence', 'same_region', 'missing_fact'])
def test_region_conflict_remains_pending_without_complete_partition_proof(change):
    package, qa = region_cycle()
    fact = package['levels'][-1]
    if change == 'overlap': fact['region_geometry'] = package['levels'][-2]['region_geometry']
    if change == 'datum': fact['datum_id'] = 'other'
    if change == 'geometry': fact.pop('region_geometry')
    if change == 'unknown': fact['status'] = 'unknown'
    if change == 'evidence': fact['evidence_ids'] = []
    if change == 'same_region': fact['region_id'] = 'region0'
    if change == 'missing_fact': package['levels'].pop()
    assert any(p['kind'] == 'pre_conflict' for p in assess_cycle(package, qa)['pending'])


def test_duplicate_region_fact_id_cannot_hide_unresolved_evidence():
    package, qa = region_cycle()
    unresolved = dict(package['levels'][-1], status='unknown', value=None)
    package['levels'].insert(0, unresolved)
    assert any(p['kind'] == 'pre_conflict' for p in assess_cycle(package, qa)['pending'])
