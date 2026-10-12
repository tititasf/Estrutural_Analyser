import math
from collections import Counter
from pathlib import Path

import ezdxf
import pytest

from src.core.lv_nova_design import draw_cut, draw_ab, panel_spans, pontalete_count

EVIDENCE = Path(__file__).resolve().parents[1] / 'scripts/arete/relatorios/20261004_nova_lv_design_experimentos'
CASES = [
    (19, 55, [(13, 0)], [(12, 7)], False),
    (35, 75, [(20, 0)], [(15, 12)], False),
    (65, 130, [(20, 5)], [(25, 0)], False),
    (25, 90, [(14, 0), (12, 32)], [], False),
    (30, 60, [(15, 45)], [(12, 48)], True),
]


@pytest.mark.parametrize('length,expected', [(16, [16]), (244, [244]), (260, [122, 138]),
    (300, [122, 178]), (304, [244, 60]), (500, [244, 122, 134]), (640, [244, 244, 152])])
def test_panel_partition(length, expected):
    assert [b-a for a, b in panel_spans(length)] == expected


def test_partition_invariants():
    for step in range(1, 30001):
        length = step / 10
        widths = [b-a for a, b in panel_spans(length)]
        assert math.isclose(sum(widths), length, abs_tol=1e-7)
        assert max(widths) <= 244 + 1e-7
        assert len(widths) == 1 or min(widths) >= 60 - 1e-7


def test_openings_counted_once():
    assert pontalete_count(0, 244, []) == 8
    assert pontalete_count(0, 122, []) == 4
    assert pontalete_count(0, 145, []) == 5
    assert pontalete_count(0, 244, [(0, 40), (10, 30)]) == 7
    assert pontalete_count(0, 244, [(-10, 40), (200, 400)]) == 5


def signature(entity):
    typ = entity.dxftype()
    attrs = entity.dxf.all_existing_dxf_attribs()
    for key in ('handle', 'owner', 'geometry'):
        attrs.pop(key, None)
    # Imported records receive different handles; entity definitions are compared separately.
    if typ == 'DIMENSION':
        attrs.pop('dimstyle', None)
    def clean(v):
        if isinstance(v, float):
            return round(v, 5)
        if isinstance(v, (str, int)):
            return v
        try:
            return tuple(clean(x) for x in v)
        except TypeError:
            return str(v)
    data = tuple(sorted((k, clean(v)) for k, v in attrs.items()))
    extra = ()
    if typ == 'LWPOLYLINE':
        extra = tuple(clean(p) for p in entity.get_points())
    elif typ == 'HATCH':
        extra = tuple(tuple(clean(v) for v in p.vertices) for p in entity.paths)
        if not entity.dxf.solid_fill:
            extra += tuple((round(l.angle, 5), clean(l.offset), clean(l.dash_length_items)) for l in entity.pattern.lines)
    return typ, data, extra


@pytest.mark.parametrize('assembly', ['gradeadas', 'sarrafeadas'])
@pytest.mark.parametrize('index,case', list(enumerate(CASES, 1)))
def test_cut_matches_approved_entities(assembly, index, case, tmp_path):
    b, h, a, bb, inverted = case
    contract = dict(width_cm=b, height_cm=h, inverted=inverted, assembly_variant=assembly,
                    beam=f'VC{index:02}', slabs={s: [dict(height_cm=t, drop_cm=d) for t, d in values]
                                               for s, values in [('A', a), ('B', bb)]})
    actual = draw_cut(contract)
    actual.saveas(tmp_path / 'actual.dxf')
    actual = ezdxf.readfile(tmp_path / 'actual.dxf')
    folder = 'dual_v11' if assembly == 'gradeadas' else 'dual_v13'
    approved = ezdxf.readfile(EVIDENCE / folder / assembly / f'VC{index:02}.dxf')
    assert not actual.audit().errors
    expected = Counter(signature(e) for e in approved.modelspace())
    result = Counter(signature(e) for e in actual.modelspace())
    assert result == expected, {'missing': list((expected-result).items())[:4],
                               'extra': list((result-expected).items())[:4]}


AB_CASES = [
    [{'length':640}],
    [{'length':300, 'beam_opening':(0,55,18)}],
    [{'length':300, 'beam_opening':(245,300,18)}],
    [{'length':260, 'beam_opening':(205,260,18)}, {'length':260}],
    [{'length':360, 'column_opening':(205,265)}],
    [{'length':260}, {'length':260}],
]


@pytest.mark.parametrize('assembly', ['gradeadas', 'sarrafeadas'])
@pytest.mark.parametrize('index,segments', list(enumerate(AB_CASES,1)))
def test_ab_matches_approved_entities(assembly,index,segments,tmp_path):
    actual=draw_ab(dict(assembly_variant=assembly,body_cm=60,total_cm=75,
                        beam=f'AB{index:02}',side='A',segments=segments))
    actual.saveas(tmp_path/'actual.dxf')
    actual=ezdxf.readfile(tmp_path/'actual.dxf')
    approved=ezdxf.readfile(EVIDENCE/'dual_v20'/assembly/f'AB{index:02}.dxf')
    assert not actual.audit().errors
    # Oct 6 amendment changes labels, dimensions and unified void/panel
    # contours. The previously approved construction members stay exact.
    layers={'SARR_2.2x7','SARR_3.5x7'}
    result=Counter(signature(e) for e in actual.modelspace() if e.dxf.layer in layers)
    expected=Counter(signature(e) for e in approved.modelspace() if e.dxf.layer in layers)
    if assembly == 'gradeadas' and index == 4:
        # Requested amendment: remove exactly the left half post below the
        # right opening; every other approved entity remains identical.
        for e in approved.modelspace().query('LINE'):
            if e.dxf.layer == 'SARR_3.5x7' and min(e.dxf.start.x,e.dxf.end.x) >= 256.5 and max(e.dxf.start.x,e.dxf.end.x) <= 260 and max(e.dxf.start.y,e.dxf.end.y) <= 15.8:
                expected.subtract([signature(e)])
        expected += Counter()
    assert result==expected, {'missing':list((expected-result).items())[:4],
                             'extra':list((result-expected).items())[:4]}
