"""Counterexamples distinguish tangent exterior branches from real barriers."""
import copy
import pytest
from src.core.pil_qa_t_junctions import capped_exterior_t


def scene():
    main = [dict(axis='x', pos=p, lo=0, hi=100) for p in (0, 19)]
    lateral = [dict(axis='y', pos=p, lo=19, hi=80) for p in (30, 44)]
    original = [dict(main[1], handle='main-wall')]
    return lateral, main, original, set()


@pytest.mark.parametrize('side', ['top', 'bottom'])
@pytest.mark.parametrize('cap', ['entire_wall', 'separate_cap'])
def test_original_main_wall_closes_t_without_redundant_cap(side, cap):
    lateral, main, original, closed = scene()
    if side == 'bottom':
        for w in lateral: w.update(lo=-80, hi=0)
        original[0]['pos'] = 0
    if cap == 'separate_cap': original[0].update(lo=30, hi=44)
    assert capped_exterior_t(*lateral, main, original, axis='x',
        positions=(0, 19), closed_handles=closed, tolerance_cm=.05)


@pytest.mark.parametrize('defect', ['crossing', 'one_endpoint', 'internal',
    'closed_cap', 'short_cap', 'absent_cap', 'main_gap', 'wrong_cap_axis',
    'wrong_branch_axis', 'zero_width', 'zero_extent'])
def test_barriers_are_not_skipped(defect):
    lateral, main, original, closed = scene()
    if defect == 'crossing':
        for w in lateral: w['lo'] = -20
    elif defect == 'one_endpoint': lateral[1]['lo'] = 18
    elif defect == 'internal':
        for w in lateral: w.update(lo=0, hi=19)
    elif defect == 'closed_cap': closed.add('main-wall')
    elif defect == 'short_cap': original[0]['lo'] = 31
    elif defect == 'absent_cap': original.clear()
    elif defect == 'main_gap': main[0]['hi'] = 43
    elif defect == 'wrong_cap_axis': original[0]['axis'] = 'y'
    elif defect == 'wrong_branch_axis': lateral[0]['axis'] = 'x'
    elif defect == 'zero_width': lateral[1]['pos'] = lateral[0]['pos']
    elif defect == 'zero_extent': lateral[0]['hi'] = 19
    assert not capped_exterior_t(*lateral, main, original, axis='x',
        positions=(0, 19), closed_handles=closed, tolerance_cm=.05)


def test_vertical_rotation_preserves_physical_t():
    lateral, main, original, closed = scene()
    for w in lateral+main+original: w['axis'] = 'y' if w['axis'] == 'x' else 'x'
    before = copy.deepcopy((lateral, main, original))
    assert capped_exterior_t(*lateral, main, original, axis='y',
        positions=(0, 19), closed_handles=closed, tolerance_cm=.05)
    assert (lateral, main, original) == before
