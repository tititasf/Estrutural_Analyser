from copy import deepcopy
import pytest
from src.core.pil_qa_short_arrivals import short_original_arrival


def walls(axis='y', anchor=100, direction=1):
    lo, hi = sorted((anchor, anchor+5*direction))
    return [dict(axis=axis, pos=p, lo=lo, hi=hi, handles=[h])
            for p, h in ((2.5, 'A'), (21.5, 'B'))]


def read(w, **overrides):
    args = dict(axis='y', face_coordinates=(0, 24), anchor=100,
                direction=1, closed_handles=set(), tolerance_cm=.05)
    args.update(overrides)
    return short_original_arrival(w, **args)


@pytest.mark.parametrize('axis', ['x', 'y'])
@pytest.mark.parametrize('direction', [-1, 1])
def test_short_source_geometry_without_identity_or_height(axis, direction):
    w = walls(axis, direction=direction)
    before = deepcopy(w)
    proof = read(w, axis=axis, direction=direction)
    assert proof['width_cm'] == 19
    assert proof['dist_esq_cm'] == proof['dist_dir_cm'] == 2.5
    assert proof['wall_handles'] == ['A', 'B']
    assert proof['status'] == 'geometry_only'
    assert not proof['identity_proved'] and not proof['section_proved']
    assert 'section' not in proof and 'beam' not in proof
    assert w == before


@pytest.mark.parametrize('case', ['one_wall', 'gap', 'closed', 'third_wall',
                                 'long', 'wrong_axis', 'behind', 'zero_width'])
def test_absence_or_ambiguity_abstains(case):
    w = walls()
    kw = {}
    if case == 'one_wall': w.pop()
    elif case == 'gap': w[1]['lo'] += .1
    elif case == 'closed': kw['closed_handles'] = {'A'}
    elif case == 'third_wall': w.append(dict(axis='y', pos=12, lo=100, hi=105, handles=['C']))
    elif case == 'long':
        for p in w: p['hi'] = 110
    elif case == 'wrong_axis': kw['axis'] = 'x'
    elif case == 'behind': kw['direction'] = -1
    elif case == 'zero_width': w[1]['pos'] = w[0]['pos']
    assert read(w, **kw) is None


def test_reversed_face_preserves_orientation_and_asymmetry():
    w = walls()
    w[0]['pos'], w[1]['pos'] = 1, 20
    proof = read(w, face_coordinates=(24, 0))
    assert proof['dist_esq_cm'] == 4
    assert proof['dist_dir_cm'] == 1
