import pytest
from src.core.lv_cut_inventory import pair_sections


def segment(name, low, high, side, vertical=False, height=55):
    points = [[low, side], [high, side]]
    if vertical:
        points = [[y, x] for x, y in points]
    return dict(id=name, index=name, points=points, width_cm=19,
                beam_height_cm=height, level=8.5)


@pytest.mark.parametrize('vertical', [False, True])
def test_disjoint_opposites_and_touching_endpoints_never_pair(vertical):
    a = segment('a', 0, 100, 0, vertical)
    bs = [segment('distant', 200, 300, 19, vertical),
          segment('touching', 100, 200, 19, vertical)]
    rows, diagnostics = pair_sections('V', 'passa', {'A': {'segments': [a]}, 'B': {'segments': bs}})
    assert rows == []
    assert diagnostics['pairs'] == 0


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('different', [False, True])
def test_long_a_pairs_three_overlapping_b_and_groups_only_identical_sections(vertical, different):
    a = segment('a', 0, 300, 0, vertical)
    bs = [segment(str(i), 100*i, 100*(i+1), 19, vertical,
                  height=55+i if different else 55) for i in range(3)]
    bs.append(segment('far', 400, 500, 19, vertical))
    rows, diagnostics = pair_sections('V', 'passa', {'A': {'segments': [a]}, 'B': {'segments': bs}})
    assert len(rows) == (3 if different else 1)
    assert diagnostics['pairs'] == 3
    pairs = [p for row in rows for p in row['pairs']]
    assert {p['b_id'] for p in pairs} == {'0', '1', '2'}
    assert all(p['length_cm'] == 100 for p in pairs)
