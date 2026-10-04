"""SA-time slab penalties yield to proven source slabs, never with a bonus."""
from shapely.geometry import box

from portal.app.preprocessamento.segment_levels import score, stale_slab_penalty_lift

SEG = dict(level_slabs=['L1'])
SHAPE = box(0, 0, 100, 20)


def record(warnings, value=852.19):
    r = dict(fact_id='B', value=value, status='inferred', method='slab_level', warnings=warnings)
    score(r)
    return r


def slab(value=852.19, status="sa_evidence"):
    return dict(fact_id='S', value=value, status=status, confidence_pct=85)


def test_proven_slab_lifts_stale_penalties():
    r = record(['source_slab_level_not_uniquely_observed', 'source_slab_requires_review'])
    assert r['confidence_pct'] == 25
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, []) == 75


def test_other_warnings_keep_inferred_base():
    r = record(['source_slab_requires_review', 'estimated_not_measured'])
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, []) == 55


def test_slab_at_other_value_keeps_penalty():
    r = record(['source_slab_requires_review'])
    assert stale_slab_penalty_lift(r, SEG, [slab(852.16)], SHAPE, []) is None


def test_incomplete_sources_keep_penalty():
    r = record(['source_slab_requires_review'])
    assert stale_slab_penalty_lift(r, dict(level_slabs=['L1', 'L2']), [slab()], SHAPE, []) is None


def test_touching_slab_with_other_level_keeps_penalty():
    r = record(['source_slab_requires_review'])
    touching = [('L9', box(0, 20, 100, 60), slab(852.12))]
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, touching) is None


def test_distant_or_weak_contradiction_ignored():
    r = record(['source_slab_requires_review'])
    far = ('L9', box(0, 40, 100, 60), slab(852.12))
    weak = ('L8', box(0, 20, 100, 60), slab(852.12, 'candidate'))
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, [far, weak]) == 75


def test_without_stale_warning_nothing_changes():
    assert stale_slab_penalty_lift(record([]), SEG, [slab()], SHAPE, []) is None


def test_lower_slab_touching_beam_at_datum_is_closed_step_not_contradiction():
    r = record(['source_slab_requires_review'])
    lower = [('L9', box(0, 20, 100, 60), slab(852.12))]
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, lower, datum=slab(852.19)) == 75


def test_lower_slab_contradicts_when_beam_is_not_at_datum():
    r = record(['source_slab_requires_review'])
    lower = [('L9', box(0, 20, 100, 60), slab(852.12))]
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, lower, datum=slab(852.25)) is None


def test_higher_slab_always_contradicts():
    r = record(['source_slab_requires_review'])
    higher = [('L9', box(0, 20, 100, 60), slab(852.25))]
    assert stale_slab_penalty_lift(r, SEG, [slab()], SHAPE, higher, datum=slab(852.19)) is None


def _region(geom, value, status='cad_level_inside_slab'):
    from shapely.geometry import mapping
    return dict(field='slab_region_level', region_geometry=mapping(geom), value=value,
                status=status, confidence_pct=95)


def test_multipart_slab_reads_the_region_the_segment_runs_along():
    from portal.app.preprocessamento.segment_levels import segment_region_source
    item = dict(levels=[_region(box(0, 20, 100, 60), 852.19), _region(box(100, 20, 200, 60), 852.16)])
    assert segment_region_source(item, box(0, 0, 100, 20), dict(value=852.19))['value'] == 852.19


def test_multipart_slab_abstains_when_segment_runs_along_both_regions():
    from portal.app.preprocessamento.segment_levels import segment_region_source
    item = dict(levels=[_region(box(0, 20, 100, 60), 852.19), _region(box(100, 20, 200, 60), 852.16)])
    assert segment_region_source(item, box(0, 0, 200, 20), dict(value=852.19)) is None


def test_multipart_region_at_other_value_is_not_a_source():
    from portal.app.preprocessamento.segment_levels import segment_region_source
    item = dict(levels=[_region(box(0, 20, 100, 60), 852.16)])
    assert segment_region_source(item, box(0, 0, 100, 20), dict(value=852.19)) is None
