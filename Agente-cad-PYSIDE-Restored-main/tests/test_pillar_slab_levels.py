from src.core.pillar_slab_levels import reconcile_pillar_slab_levels
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar


def source(slab, **kwargs):
    value = slab.get('confirmed_level')
    return {'value': value} if value is not None else None


def test_final_unknown_slab_clears_stale_pillar_level_and_face_slot():
    p = {'level': '3', 'fields': {'Nível (Via Laje)': '3'},
         'lajes_adjacentes': [{'laje': 'LA', 'side': 'A'}],
         'p_sA_l1_n': 'LA', 'p_sA_l1_v': '3',
         'links': {'p_sA_l1_v': {'label': [{'text': '3'}]}}}
    reconcile_pillar_slab_levels([p], [{'name': 'LA'}], source, str)
    assert p['level'] == p['p_sA_l1_v'] == ''
    assert 'Nível (Via Laje)' not in p['fields']
    assert 'p_sA_l1_v' not in p['links']


def test_zero_negative_levels_and_human_fields_are_preserved():
    p = {'level': 'old', 'lajes_adjacentes': [{'laje': 'LA'}, {'laje': 'LB'}],
         'p_sA_l1_n': 'LA', 'p_sA_l1_v': 'human',
         'validated_fields': ['p_sA_l1_v']}
    reconcile_pillar_slab_levels([p], [{'name': 'LA', 'confirmed_level': -3},
                                     {'name': 'LB', 'confirmed_level': 0}], source, str)
    assert p['level'] == '0'
    assert p['p_sA_l1_v'] == 'human'
    p['is_validated'] = True
    reconcile_pillar_slab_levels([p], [{'name': 'LA'}], source, str)
    assert p['level'] == '0'


def test_authoritative_unknown_map_does_not_restore_level_from_old_face_text():
    p = {'points': [[0, 0], [0, 20], [10, 20], [10, 0]],
         'lajes': [{'laje': 'LA', 'side': 'A', 'nivel': '6'}]}
    tables = build_abcd_tables_from_pillar(p, slab_nivel_map={'LA': ''},
        face_interp_lines={'B': {'lajes': ['Laje: LA · esp: 12 · N: 6']}})
    assert tables['faces']['A']['lajes'][0]['nivel'] == '—'
    assert tables['faces']['B']['lajes'][0]['nivel'] == '—'


def test_validated_face_link_preserves_human_level():
    p = {'p_sA_l1_n': 'LA', 'p_sA_l1_v': 'human',
         'validated_link_classes': {'p_sA_l1_v': ['label']},
         'links': {'p_sA_l1_v': {'label': [{'text': 'human'}]}}}
    reconcile_pillar_slab_levels([p], [{'name': 'LA'}], source, str)
    assert p['p_sA_l1_v'] == 'human'
    assert p['links']['p_sA_l1_v']['label'][0]['text'] == 'human'


def test_report_invalidates_cached_face_tables_and_refreshes_own_slab_entries():
    p = {'lajes': [{'laje': 'LA', 'nivel': '6'}, {'laje': 'LB', 'nivel': 'human',
                   'validated': True}], '_abcd_tables': {'stale': True}}
    reconcile_pillar_slab_levels([p], [{'name': 'LA'}, {'name': 'LB'}], source, str)
    assert '_abcd_tables' not in p
    assert p['lajes'][0]['nivel'] == ''
    assert p['lajes'][1]['nivel'] == 'human'
