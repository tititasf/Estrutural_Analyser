import pytest
from shapely.geometry import box
from portal.app.preprocessamento.standard_beam_level import level, sources
from portal.app.preprocessamento.segment_levels import inherited, projected_coverage, geometry


def fixture(score=95):
    source = dict(fact_id='slab:principal', value=101, status='sa_evidence',
                  confidence_pct=score, evidence_ids=['cad:level'], warnings=[])
    native = dict(fact_id='fund:1', value=101, status='inferred', method='highest_touching_slab',
                  confidence_pct=30, evidence_ids=[], warnings=['missing_independent_level_evidence'])
    geom = box(0, 0, 100, 14)
    refs = [('L', box(0, 14, 100, 100), source)]
    return geom, native, refs


def test_real_spatial_source_convention_caps_support_and_retains_origin():
    geom, native, refs = fixture()
    result = level(geom, native, refs, [], [], inherited, projected_coverage)
    assert result['value'] == 101 and result['confidence_pct'] == 85
    assert result['level_basis'] == 'owner_convention'
    assert result['source_fact_ids'] == ['slab:principal']
    assert 'missing_independent_level_evidence' not in result['warnings']
    assert result['previous_level_evidence']['confidence_pct'] == 30
    side = inherited(native, [result], 'spatial_fv_reference', .95)
    assert side['confidence_pct'] == 80.8
    assert side['level_basis'] == 'owner_convention' and side['status'] == 'inferred'


def test_weak_source_is_not_promoted_to_strong():
    geom, native, refs = fixture(40)
    result = level(geom, native, refs, [], [], inherited, projected_coverage)
    assert result['confidence_pct'] == 38


@pytest.mark.parametrize('case', ['missing_dxf', 'fill', 'cut', 'human', 'conflict', 'different_datum', 'partial', 'different_slabs', 'estimated_source'])
def test_unresolved_exceptions_and_incomplete_support_block_convention(case):
    geom, native, refs = fixture()
    paints, cuts = [], []
    if case == 'missing_dxf': paints = None
    if case == 'fill': paints = [box(0, 0, 100, 14)]
    if case == 'cut': cuts = [box(40, 0, 60, 14)]
    if case == 'human': native['status'] = 'human_review'
    if case == 'conflict': native['status'] = 'conflict'
    if case == 'different_datum': native['value'] = 102
    if case == 'partial': refs[0] = ('L', box(0, 14, 50, 100), refs[0][2])
    if case == 'different_slabs': refs.append(('L2', box(0, -50, 100, 0), dict(refs[0][2], value=102)))
    if case == 'estimated_source': refs[0][2]['status'] = 'estimated'
    assert level(geom, native, refs, paints, cuts, inherited, projected_coverage) is None


def test_slab_scalar_copied_from_the_inner_step_yields_to_the_principal():
    geom, native, refs = fixture(85)
    native.update(value=100.97, status='sa_evidence', confidence_pct=75, method='highest_touching_slab')
    result = level(geom, native, refs, [], [], inherited, projected_coverage,
                   steps_by_slab={'L': [100.97]})
    assert result is not None
    assert result['value'] == 101
    assert result['confidence_pct'] > 75
    assert result['previous_level_evidence']['value'] == 100.97


def test_explicit_beam_value_at_the_step_number_is_not_replaced():
    geom, native, refs = fixture(85)
    native.update(value=100.97, status='sa_evidence', confidence_pct=75, method='explicit_beam_or_side')
    assert level(geom, native, refs, [], [], inherited, projected_coverage,
                 steps_by_slab={'L': [100.97]}) is None


def test_third_value_is_not_treated_as_the_inner_step():
    geom, native, refs = fixture(85)
    native.update(value=100.5, status='sa_evidence', confidence_pct=75, method='highest_touching_slab')
    assert level(geom, native, refs, [], [], inherited, projected_coverage,
                 steps_by_slab={'L': [100.97]}) is None


def test_inner_slab_datum_is_not_selected_as_beam_reference():
    context = {'state': {'slabs': [dict(name='L', points=[[0,0],[100,0],[100,100],[0,100],[0,0]], slab_steps=[{}])]}}
    principal = dict(field='slab_region_level', region_id='principal', value=101, confidence_pct=65)
    inner = dict(field='slab_region_level', region_id='inner', value=100.97, confidence_pct=95)
    refs = sources({'L': {'levels': [inner, principal]}}, context, {}, geometry)
    assert refs[0][2] is principal
