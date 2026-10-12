from copy import deepcopy

import pytest

from portal.app.preprocessamento.segment_levels import preserve_local_seed_over_estimated_fv
from portal.app.preprocessamento.sa_levels import merge_sa_levels
from portal.tests.test_segment_level_correspondence import fixture, beam


def seed():
    return dict(value=100, status='inferred', confidence_pct=76.5,
                method='spatial_slab_region_reference', source_fact_ids=['local-slab'])


def weak():
    return dict(value=100, status='estimated', confidence_pct=30, method='estimated_beam_level')


def test_independent_local_seed_survives_agreeing_estimated_fv():
    native, fv = seed(), weak()
    before = deepcopy((native, fv))
    assert preserve_local_seed_over_estimated_fv(native, [fv])
    assert (native, fv) == before


@pytest.mark.parametrize('change', [
    {'value': 100.07}, {'status': 'inferred', 'confidence_pct': 70},
    {'status': 'human_review'}, {'method': 'cut_geometry_on_fv'},
    {'cut_ids': ['cut-original']}, {'cut_profile_geometry': {'stem': []}},
])
def test_disagreement_strong_source_and_explicit_cut_keep_existing_precedence(change):
    fv = weak(); fv.update(change)
    assert not preserve_local_seed_over_estimated_fv(seed(), [fv])


@pytest.mark.parametrize('change', [
    {'status': 'estimated'}, {'confidence_pct': 30}, {'source_fact_ids': []},
    {'method': 'cut_geometry_on_fv'},
])
def test_unproven_native_is_not_promoted(change):
    native = seed(); native.update(change)
    assert not preserve_local_seed_over_estimated_fv(native, [weak()])


def test_partial_lv_cannot_fill_fv_but_fv_cannot_erase_local_lv_proof(monkeypatch):
    from portal.app.preprocessamento import standard_beam_level
    monkeypatch.setattr(standard_beam_level, 'level', lambda *args, **kwargs: None)
    tower, c, fund, side = fixture()
    c['state']['slabs'] = [c['state']['slabs'][0]]
    c['marks'] = [c['marks'][0]]
    fv = fund(1, 0, 150, 100, None)
    fv['level_source'] = 'estimated_beam_level'
    lv = side(1, 0, 50, 100, None)
    lv['level_source'] = 'lv_cell_estimado'
    c['state']['segmentos'] = {'fundo': [fv], 'lateral_b_para': [lv]}
    segments = beam(merge_sa_levels(tower, c))['segments']
    fund_row = next(s for s in segments if s['family'] == 'fundo')
    lateral = next(s for s in segments if s['family'] == 'lateral_b_para')
    row = lateral['level_ranges'][0]
    assert fund_row['status'] == 'estimated' and fund_row['confidence_pct'] <= 30
    assert row['status'] == 'inferred' and row['confidence_pct'] >= 50
    assert row['method'] == 'spatial_slab_region_reference'
    assert row['source_fact_ids'] == lateral['native_level_evidence']['source_fact_ids']
    assert row['fv_segments'] == [] and list(map(str, row['fv_geometry_segments'])) == ['1']
    assert not any('fundo' in uid for uid in row['source_fact_ids'])
