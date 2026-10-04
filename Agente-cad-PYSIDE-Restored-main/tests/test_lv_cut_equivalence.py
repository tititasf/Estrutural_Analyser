from copy import deepcopy
from src.core.lv_cut_equivalence import group_equivalent_cuts
from src.core.lv_n3_cut_contract import build_cut_contract


def cut(id='one'):
    return dict(id=id, beam='V999', kind='calculated', width_cm=19, beam_height_cm=55,
                origins=['pares_ab'], evidence_ids=[id], pairs=[{'a_id': id, 'b_id': id}],
                profiles={side: dict(level=8.5, slabs=[dict(name=name, height_cm=h, level=8.5)])
                          for side, name, h in [('A', 'L1', 12), ('B', 'L2', 10)]})


def test_names_duplicates_and_absolute_levels_do_not_multiply_section():
    a, b = cut(), cut('two')
    for p in b['profiles'].values():
        p['level'] += 3
        p['slabs'][0]['level'] += 3
        p['slabs'][0]['name'] += 'X'
        p['slabs'].append(deepcopy(p['slabs'][0]))
    before = deepcopy([a, b])
    rows = group_equivalent_cuts([a, b])
    assert len(rows) == 1
    assert len(rows[0]['pairs']) == 2
    assert rows[0]['evidence_ids'] == ['one', 'two']
    assert rows[0]['slab_aliases']['A'] == ['L1', 'L1X']
    assert len(rows[0]['section_members']) == 2
    assert build_cut_contract(rows[0])['slabs']['A'][0]['name'] == 'L1, L1X'
    assert [a, b] == before


def test_identified_and_calculated_equal_geometry_merge():
    a = cut()
    b = dict(id='identified', beam='V999', kind='identified', origins=['preprocessamento'],
             evidence_ids=['DXF123'], source_cut=dict(beam_w=19, beam_h=55, own_laje='L1',
             ficha=dict(direction='norte', side_a_laje_name='L1', side_b_laje_name='L2',
                        own_slab_height=12, neigh_slab_height=10, own_dist_top=0,
                        own_dist_bottom=43, neighbor_dist_top=0, neighbor_dist_bottom=45)))
    rows = group_equivalent_cuts([b, a])
    assert len(rows) == 1
    assert rows[0]['origins'] == ['preprocessamento', 'pares_ab']
    assert rows[0]['pairs'] == a['pairs']


def test_different_dimensions_drop_or_orientation_remain_separate():
    a = cut()
    variants = []
    b = cut('wide'); b['width_cm'] = 20; variants.append(b)
    b = cut('tall'); b['beam_height_cm'] = 56; variants.append(b)
    b = cut('drop'); b['profiles']['A']['slabs'][0]['level'] -= .01; variants.append(b)
    b = cut('mirror'); b['profiles']['A'], b['profiles']['B'] = b['profiles']['B'], b['profiles']['A']; variants.append(b)
    b = cut('other-beam'); b['beam'] = 'V998'; variants.append(b)
    assert len(group_equivalent_cuts([a, *variants])) == 6


def test_unknown_measures_never_merge():
    a, b = cut(), cut('two')
    for row in (a, b):
        row['profiles']['A']['slabs'][0]['height_cm'] = None
    assert len(group_equivalent_cuts([a, b])) == 2
