from copy import deepcopy
import pytest
from src.core.level_text_semantics import elevation_value
from src.core.analysis_helpers import process_slab_intelligent, apply_plan_level_provenance


@pytest.mark.parametrize('text,value', [('+2,80', 2.8), ('-3.00', -3), ('N=0.00', 0),
                                      ('NÍVEL 852.19', 852.19), ('EL: 12.5', 12.5)])
def test_explicit_elevation_without_reference(text, value):
    assert elevation_value({'text': text}) == value


@pytest.mark.parametrize('text', ['400.5', '371,5', 'h=12', 'P14', '19/170', '2-10 PAV'])
def test_no_altitude_from_unsigned_dimensions_or_other_annotations(text):
    assert elevation_value({'text': text}) is None


def test_dimension_overrides_sign_layer_and_floor_band():
    token = {'text': '+2.80', 'annotation_role': 'dimension'}
    assert elevation_value(token, trusted_layer=True, reference_level=2.8, floor_height=3) is None
    assert elevation_value({'text': '2.80'}, reference_level=2.8, floor_height=3) == 2.8
    assert elevation_value({'text': '400.5'}, reference_level=2.8, floor_height=3) is None


def slab():
    return {'name': 'L1', 'id_item': 1, 'pos': (10, 10),
            'points': [(0, 0), (100, 0), (100, 100), (0, 100)]}


def test_second_pass_does_not_reintroduce_length_or_old_candidates():
    s = slab()
    token = {'text': '371.5', 'pos': (50, 50)}
    s['_nivel_candidates'] = [('371.5', token)]
    s['laje_nivel'] = '371.5'
    process_slab_intelligent(s, [token])
    assert 'laje_nivel' not in s['fields'] and 'laje_nivel' not in s
    assert s['links']['laje_nivel']['label'] == []
    assert s['_nivel_provenance']['provenance'] == 'sem_evidencia_local'


def test_valid_unsigned_floor_level_and_explicit_level_preserve_geometry():
    for raw, args in [('+2.80', {}), ('852.19', {'reference_level': 852.19, 'floor_height': 3.21})]:
        s = slab()
        before = deepcopy(s['points'])
        process_slab_intelligent(s, [{'text': raw, 'pos': (50, 50)}], **args)
        assert s['fields']['laje_nivel'] == raw
        assert s['_nivel_provenance']['needs_human_review'] is False
        assert s['points'] == before


def test_containment_does_not_make_two_conflicting_levels_certain():
    s = slab()
    process_slab_intelligent(s, [{'text': '+2.80', 'pos': (30, 30)},
                                {'text': '+2.90', 'pos': (50, 50)}])
    assert s['_nivel_provenance']['needs_human_review'] is True
