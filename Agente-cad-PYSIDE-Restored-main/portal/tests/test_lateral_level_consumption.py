from copy import deepcopy
import pytest

from portal.app.preprocessamento.lateral_level_consumption import (
    parcel_input, corroborate_cells, METHOD,
)
from src.core.preficha_segments import collect_preficha_segments


def fixture():
    root = dict(fact_id='CAD', field='slab_level', value=100., unit='m',
                status='sa_evidence', method='cad_level_inside_slab', evidence_ids=['cad:level'])
    part = dict(fact_id='part', field='lateral_a_para', value=100., unit='m',
                status='inferred', method='lateral_spatial_level_ranges', source_fact_ids=['CAD'],
                item_id='original-label', segment_id='pre-index-1')
    interval = dict(part, fact_id='range', range_start=0., range_end=100., range_unit='cm')
    segment = dict(family='lateral_a_para', beam_item_id='original-label', beam_name='V1',
        segment_id='pre-index-1', points=[[0., 0.], [100., 0.]], level_ranges=[interval],
        warnings=['status_inferred'], original_label_parcel_proof=dict(
            section_source='lateral_boundary_of_original_label_proved_fv',
            source_entity_handles=['name', 'wall1', 'wall2'], source_fv_segments=['FV'], spatial_coverage=1.))
    package = dict(scope=dict(source_revision='a'*64), levels=[root, part],
                   level_inventory=dict(beam_segments=[segment]))
    cell = dict(level='100', level_estimado=dict(origem='same_name'), depth=55,
                adjustment_start=-11, adjustment_end=11)
    link = dict(points=[[100., 0.], [0., 0.]], len=100., lv_cell=cell)
    beam = dict(name='V1', id='new-run', links={
        'viga_a_seg_9_comprimento_total': {'seg_side_a': [link]}})
    return package, beam, cell


def test_actual_collector_consumes_reversed_geometry_without_matching_indices():
    package, beam, cell = fixture()
    original = deepcopy(cell)
    result = corroborate_cells([beam], parcel_input(package), source_revision='a'*64)
    assert len(result['consumed']) == 1 and not result['blocked']
    row = collect_preficha_segments([beam])['lateral_a_para'][0]
    assert row['level_source'] == METHOD and row['level'] == '100'
    assert result['consumed'][0]['status'] == 'inferred'
    assert cell == {**original, 'preprocess_level_provenance': cell['preprocess_level_provenance']}
    cell['level'] = '101'
    assert collect_preficha_segments([beam])['lateral_a_para'][0]['level_source'] == 'lv_cell_estimado'


@pytest.mark.parametrize('cause', ['missing', 'cycle', 'weak', 'partial', 'conflict', 'unit', 'no_wall_proof'])
def test_rejects_unproved_or_incomplete_original_paths(cause):
    package, _, _ = fixture()
    root, fact = package['levels']
    seg = package['level_inventory']['beam_segments'][0]
    if cause == 'missing': fact['source_fact_ids'] = ['absent']
    elif cause == 'cycle': root['source_fact_ids'] = [fact['fact_id']]
    elif cause == 'weak': root['status'] = 'estimated'
    elif cause == 'partial': seg['level_ranges'][0]['range_end'] = 90
    elif cause == 'conflict': seg['level_ranges'][0]['value'] = 101
    elif cause == 'unit': fact['unit'] = 'cm'
    elif cause == 'no_wall_proof': seg['original_label_parcel_proof']['source_entity_handles'] = []
    assert parcel_input(package) == []


def test_rejects_displacement_stale_revision_ambiguity_and_value_conflict():
    package, beam, cell = fixture()
    parcels = parcel_input(package)
    assert not corroborate_cells([beam], parcels, source_revision='b'*64)['consumed']
    moved = deepcopy(beam)
    moved['links']['viga_a_seg_9_comprimento_total']['seg_side_a'][0]['points'] = [[0,1],[100,1]]
    assert not corroborate_cells([moved], parcels, source_revision='a'*64)['consumed']
    assert corroborate_cells([beam], parcels*2, source_revision='a'*64)['blocked']
    cell['level'] = '101'
    assert corroborate_cells([beam], parcels, source_revision='a'*64)['blocked']
    assert 'preprocess_level_provenance' not in cell


def test_preserves_non_estimated_manual_cell_and_removes_old_annotation():
    package, beam, cell = fixture()
    cell.pop('level_estimado')
    cell['preprocess_level_provenance'] = dict(stale=True)
    assert not corroborate_cells([beam], parcel_input(package), source_revision='a'*64)['consumed']
    assert cell['level'] == '100' and 'preprocess_level_provenance' not in cell


def test_independent_root_does_not_hide_weak_intermediate_transfer():
    package, _, _ = fixture()
    middle = dict(package['levels'][0], fact_id='weak-transfer',
                  status='estimated', source_fact_ids=['CAD'])
    package['levels'].append(middle)
    package['levels'][1]['source_fact_ids'] = ['weak-transfer']
    assert parcel_input(package) == []


def test_mixed_sa_link_slots_preserve_non_lateral_lists():
    package, beam, cell = fixture()
    other_links = [{'points': [[0, 1], [100, 1]]}]
    beam['links']['support_inventory'] = other_links
    beam['links']['empty_metadata'] = None
    before = deepcopy(other_links)
    result = corroborate_cells([beam], parcel_input(package), source_revision='a'*64)
    assert len(result['consumed']) == 1 and not result['blocked']
    assert other_links == before
    assert cell['preprocess_level_provenance']['unit'] == 'm'


@pytest.mark.parametrize('other', [None, [], [{'points': []}], 'metadata', 7])
def test_empty_parcels_still_clear_only_valid_cell_annotations(other):
    _, beam, cell = fixture()
    beam['links']['non_lateral'] = other
    beam['links']['viga_a_seg_9_comprimento_total']['other_slot'] = [None, 7, {'lv_cell': None}]
    cell['preprocess_level_provenance'] = {'stale': True}
    before = deepcopy(other)
    assert corroborate_cells([None, {'links': []}, beam], [], source_revision='a'*64) == {
        'consumed': [], 'blocked': []}
    assert beam['links']['non_lateral'] == before
    assert 'preprocess_level_provenance' not in cell
