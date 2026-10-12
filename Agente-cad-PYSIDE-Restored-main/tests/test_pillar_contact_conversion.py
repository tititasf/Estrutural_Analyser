from src.core.pillar_slab_contacts import contact_slabs
from src.core.pillar_n3_ficha import build_ficha, robot_patch, validate_ficha, apply_ficha_to_robot
from src.core.pillar_slab_contacts import apply_contact_openings
from copy import deepcopy
import pytest


def contact(start, end, level=None, regions=None):
    return dict(slab_name='L', left_distance_cm=start, right_distance_cm=100-end,
                width_cm=end-start, thickness_cm=10, level_m=level,
                principal_level=0, region_ids=regions or [], conflict=False)


def test_region_unknown_cannot_inherit_parent_level_and_explicit_zero_is_valid():
    slabs=contact_slabs([contact(0,40), contact(60,100,regions=['step'])],0)
    assert slabs[0]['level']==0 and slabs[0]['pending']==[]
    assert slabs[1]['level'] is None and 'missing_contact_level' in slabs[1]['pending']


def test_multiple_contacts_use_independent_generator_openings_without_scalar_void():
    ficha=build_ficha({'name':'P','points':[[0,0],[100,0],[100,20],[0,20]]},
                       {'comprimento':100,'largura':20,'altura':280})
    ficha['faces']['B']['slabs']=contact_slabs([contact(0,40,9.8),contact(60,100,9.6)],10)
    ficha['faces']['B']['n3_width_extra']=22
    patch=robot_patch(ficha)
    assert patch['vazio_laje_B']==0
    openings=[patch[f'abertura_B_{i}'] for i in (1,2)]
    assert [o['x_offset'] for o in openings]==[11,71]
    assert [o['largura'] for o in openings]==[40,40]
    assert abs(openings[0]['y_rel']-openings[1]['y_rel']-20)<1e-6
    assert [o['_nivel_origem'] for o in openings]==[9.8,9.6]


def test_unknown_contact_survives_save_and_is_not_drawn_as_zero_level():
    ficha=build_ficha({'name':'P','points':[[0,0],[100,0],[100,20],[0,20]]},
                       {'comprimento':100,'largura':20,'altura':280})
    ficha['faces']['B']['slabs']=contact_slabs([contact(0,40,regions=['step'])],10)
    clean=validate_ficha(ficha)
    assert clean['faces']['B']['slabs'][0]['pending']==['missing_contact_level']
    patch=robot_patch(clean)
    assert patch['vazio_laje_B']==0 and patch.get('abertura_B_1') is None


def test_segmented_contacts_clear_stale_scalar_sources_without_mutating_original():
    robot={'comprimento':100,'largura':20,'altura':280,
           'abertura_B':{'largura':100,'altura':12},
           'abertura_B_3':{'largura':100,'altura':12},
           '_sa_mode_contract':{'faces':{'B':{'fontes_n1':{
               'lajes':['Laje: L · nivel: 9.80 · esp: 10 cm']}}}}}
    ficha=build_ficha({'name':'P','points':[[0,0],[100,0],[100,20],[0,20]]},robot)
    ficha['faces']['B']['slabs']=contact_slabs([contact(0,40,9.8),contact(60,100,9.6)],10)
    result=apply_ficha_to_robot(robot,ficha)
    assert result['abertura_B'] is None and result['abertura_B_4'] is None
    assert result['abertura_B_3']['_origem']=='slab_contact'
    assert result['_sa_mode_contract']['faces']['B']['fontes_n1']['lajes']==[]
    assert robot['_sa_mode_contract']['faces']['B']['fontes_n1']['lajes']


def test_single_partial_contact_is_not_expanded_to_whole_face():
    ficha=build_ficha({'name':'P','points':[[0,0],[100,0],[100,20],[0,20]]},
                      {'comprimento':100,'largura':20,'altura':280})
    ficha['faces']['B']['slabs']=[{'left_distance':20,'right_distance':40,
                                 'width':40,'height':12,'top_distance':20,'level':9.8}]
    result=robot_patch(ficha)
    assert result['vazio_laje_B']==0
    assert result['abertura_B_1']['largura']==40
    assert result['abertura_B_1']['x_offset']==20


@pytest.mark.parametrize('mode', ['para', 'passa'])
@pytest.mark.parametrize('visual', ['INI', 'NOVA', 'MOLDE1'])
def test_batch_conversion_preserves_mesh_beams_and_each_slab_contact(mode, visual):
    robot = {'altura': 292, 'comprimento': 100, 'largura': 20, 'h1_B': 2,
             'modo': mode, 'modo_visual': visual, 'paineis_intervals_B': [122, 122, 32],
             'grade_1': 60, 'abertura_B_1': {'largura': 19, 'altura': 54, '_origem': 'BC'},
             '_sa_mode_contract': {'faces': {'B': {'fontes_n1': {
                 'lajes': ['scalar old contact']}}}}}
    original = deepcopy(robot)
    slabs = contact_slabs([contact(0, 40, 9.8), contact(60, 100, 9.6)], 10)
    converted = apply_contact_openings(robot, {'B': slabs})
    assert converted['abertura_B_1'] == original['abertura_B_1']
    assert [converted[f'abertura_B_{i}']['x_offset'] for i in (2, 3)] == [11, 71]
    assert converted['paineis_intervals_B'] == robot['paineis_intervals_B']
    assert converted['grade_1'] == 60
    assert robot == original
    assert apply_contact_openings(converted, {'B': slabs}) == converted
    assert converted['_sa_mode_contract']['faces']['B']['fontes_n1']['lajes'] == []


def test_batch_missing_or_outside_level_is_retained_pending_without_fake_opening():
    robot = {'altura': 292, 'h1_B': 2, '_sa_mode_contract': {'faces': {'B': {}}}}
    slabs = contact_slabs([contact(0, 40, regions=['step']), contact(60, 100, 0)], 10)
    result = apply_contact_openings(robot, {'B': slabs})
    assert result['abertura_B_1'] is None
    assert 'missing_contact_level' in result['_portal_slabs_B'][0]['pending']
    assert 'contact_outside_pillar_height' in result['_portal_slabs_B'][1]['pending']


def test_explicit_empty_physical_intersection_clears_stale_scalar_cut():
    robot = {'altura': 292, 'vazio_laje_B': 20,
             '_sa_mode_contract': {'faces': {'B': {'fontes_n1': {'lajes': ['old']}}}}}
    result = apply_contact_openings(robot, {'B': []})
    assert result['vazio_laje_B'] == 0
    assert result['_sa_mode_contract']['faces']['B']['fontes_n1']['lajes'] == []
    assert result['_portal_slabs_B'] == []
    assert apply_contact_openings(robot, {}) == robot
