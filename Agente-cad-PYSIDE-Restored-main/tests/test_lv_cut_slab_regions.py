import pytest

from src.core.lv_cut_inventory import pair_sections
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError


def fixture(vertical=False, inner_level=8.47):
    def points(ps):
        return [[y, x] for x, y in ps] if vertical else ps
    sides = {s: {'segments': [dict(id=s, index=1,
        points=points([[0, y], [300, y]]), width_cm=19,
        beam_height_cm=55, level=8.5)]} for s, y in [('A', 0), ('B', 19)]}
    slab = dict(name='L', height=13, nivel=8.5,
        points=points([[0, -100], [300, -100], [300, 0], [0, 0]]),
        slab_steps=[dict(uid='inner', height_cm=10, level_m=inner_level,
            owner_height_cm=13, owner_level_m=8.5,
            points=points([[100, -50], [200, -50], [200, 0], [100, 0]]))])
    return sides, slab


@pytest.mark.parametrize('vertical', [False, True])
def test_section_uses_contact_region_and_retains_both_principal_intervals(vertical):
    sides, slab = fixture(vertical)
    cuts, diag = pair_sections('V', 'passa', sides, [slab])
    assert len(cuts) == 2
    assert diag['pairs'] == 3
    by_height = {c['profiles']['A']['slabs'][0]['height_cm']: c for c in cuts}
    assert len(by_height[13]['pairs']) == 2
    assert by_height[10]['profiles']['A']['slabs'][0]['level'] == 8.47
    contract = build_cut_contract(by_height[10])
    assert contract['slabs']['A'][0]['drop_cm'] == pytest.approx(3)
    assert sum(p['length_cm'] for c in cuts for p in c['pairs']) == pytest.approx(300)


def test_missing_regional_level_is_not_replaced_with_global_level():
    sides, slab = fixture(inner_level=None)
    cuts, _ = pair_sections('V', 'passa', sides, [slab])
    inner = next(c for c in cuts if c['profiles']['A']['slabs'][0]['height_cm'] == 10)
    assert inner['profiles']['A']['slabs'][0]['level'] is None
    with pytest.raises(CutContractError, match='nível ausente'):
        build_cut_contract(inner)


def test_inset_not_touching_face_does_not_add_section():
    sides, slab = fixture()
    slab['slab_steps'][0]['points'] = [[100,-50],[200,-50],[200,-10],[100,-10]]
    cuts, _ = pair_sections('V', 'passa', sides, [slab])
    assert len(cuts) == 1
    assert cuts[0]['profiles']['A']['slabs'][0]['height_cm'] == 13


def test_cad_rounding_at_face_does_not_create_two_slab_profiles():
    sides, slab = fixture()
    slab['slab_steps'][0]['points'] = [[100,-50],[200,-50],[200,-.038],[100,-.038]]
    cuts, _ = pair_sections('V', 'passa', sides, [slab])
    assert len(cuts) == 2
    for c in cuts:
        assert len(c['profiles']['A']['slabs']) == 1
        build_cut_contract(c)


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('gap,expected', [(.1, True), (.3, False)])
def test_normalized_opposite_slab_contact_is_not_lost_or_guessed(vertical, gap, expected):
    sides, slab = fixture(vertical)
    pts = [[0,19+gap],[300,19+gap],[300,100],[0,100]]
    opposite = dict(name='R',height=12,nivel=8.5,
                    points=[[y,x] for x,y in pts] if vertical else pts)
    cuts,_ = pair_sections('V','passa',sides,[slab,opposite])
    assert all(bool(c['profiles']['B']['slabs']) == expected for c in cuts)


def test_normalized_inset_keeps_one_physical_profile():
    sides,slab = fixture()
    slab['slab_steps'][0]['points'] = [[100,-50],[200,-50],[200,-.1],[100,-.1]]
    cuts,_ = pair_sections('V','passa',sides,[slab])
    assert len(cuts) == 2
    assert all(len(c['profiles']['A']['slabs']) == 1 for c in cuts)
