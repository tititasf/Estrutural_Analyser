from copy import deepcopy

from shapely.geometry import Polygon, box, mapping

from portal.app.preprocessamento.cut_level_scope import incompatible_own_height, own_wing_top, for_fund


def test_step_height_cannot_borrow_principal_altitude():
    assert incompatible_own_height({'ficha': {'own_slab_height': 10}}, {'fields': {'laje_dim': 'h=12'}})
    assert not incompatible_own_height({'ficha': {'own_slab_height': 12}}, {'fields': {'laje_dim': 'h=12'}})
    assert not incompatible_own_height({'ficha': {}}, {'fields': {'laje_dim': 'h=12'}})


def test_two_stems_read_their_own_top_and_actual_owner_wing():
    # Left stem 19x50, right stem 19x120; wings separated by a 5cm step.
    section = Polygon([(164,0),(145,0),(145,33),(64,33),(64,0),(45,0),
                       (45,38),(0,38),(0,50),(64,50),(64,45),(145,45),
                       (145,120),(164,120),(164,0)])
    left = {'points': list(box(-5, -20, 45, 130).exterior.coords), 'fields': {'laje_dim': 'h=12'}}
    right = {'points': list(box(64,-20,145,130).exterior.coords), 'fields': {'laje_dim': 'h=12'}}
    assert own_wing_top(section, left, {}) == 50
    assert own_wing_top(section, right, {}) == 45
    fact = dict(value=100.75, own_slab_value=100, own_wing_top_coordinate_cm=50,
                cut_profile_geometry=mapping(section), fact_id='f')
    before = deepcopy(fact)
    assert for_fund(fact, box(45,-50,64,150),50)['value'] == 100
    assert for_fund(fact, box(145,-50,164,150),120)['value'] == 100.7
    assert fact == before
    # An unrelated plan footprint cannot gain a measurement from this section.
    assert for_fund(fact, box(200,-50,219,150),120) == fact
    right['fields']['laje_dim'] = 'h=10'
    assert own_wing_top(section, right, {}) is None


def test_ambiguous_owner_band_and_missing_profile_preserve_conservative_reading():
    section=box(0,0,100,12)
    assert own_wing_top(section, {'points': list(box(200,0,250,12).exterior.coords)}, {}) is None
    fact={'value':100}
    assert for_fund(fact, box(0,0,19,100),50) == fact
