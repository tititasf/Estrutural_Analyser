"""Beam between slabs at different levels: common datum, lower slab closed by the panel."""
from shapely.geometry import Polygon

from portal.app.preprocessamento.segment_levels import inherited, projected_coverage
from portal.app.preprocessamento.standard_beam_level import level

FUND = Polygon([(0, 0), (300, 0), (300, 19), (0, 19)])
UPPER = Polygon([(0, 19), (300, 19), (300, 200), (0, 200)])     # slab on one side
LOWER = Polygon([(0, -200), (300, -200), (300, 0), (0, 0)])     # slab on the other side


def src(fid, value, pct=95, status='sa_evidence'):
    return dict(fact_id=fid, value=value, unit='m', status=status, confidence_pct=pct,
                confidence_components={}, warnings=[], evidence_ids=['cad:'+fid])


def native():
    return dict(fact_id='fv', value=852.19, unit='m', status='inferred', confidence_pct=30,
                method='highest_touching_slab', confidence_components={}, warnings=[])


DATUM = dict(src('floor', 852.19), field='floor_exit_reference')


def run(lower_value, datum=DATUM, lower_status='inferred'):
    refs = [('A', UPPER, src('a', 852.19)), ('B', LOWER, src('b', lower_value, 55, lower_status))]
    return level(FUND, native(), refs, [], [], inherited, projected_coverage, datum)


def test_lower_neighbor_slab_keeps_common_datum():
    r = run(852.12)
    assert r and r['value'] == 852.19
    assert set(r['source_fact_ids']) == {'a', 'floor'}          # lower slab is not a source
    assert r['lower_contact_slabs'][0]['slab'] == 'B'
    assert 'lower_adjacent_slab_closed_by_top_panel' in r['warnings']
    assert r['confidence_pct'] <= 85 and r['level_basis'] == 'owner_convention'


def test_higher_neighbor_or_missing_datum_abstains():
    assert run(852.25) is None                  # beam would have to change: needs cut/hatch
    assert run(852.12, datum=None) is None
    assert run(852.12, lower_status='unknown') is None
    assert run(852.12, datum=dict(DATUM, value=852.12)) is None   # other contact above the datum
