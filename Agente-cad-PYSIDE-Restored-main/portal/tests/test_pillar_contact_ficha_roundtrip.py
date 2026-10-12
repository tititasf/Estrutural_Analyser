"""Physical slab contacts must survive ficha round trips exactly once."""
from copy import deepcopy

from portal.app.routers.n1_routes import _anexar_lajes_n3
from src.core.pillar_n3_ficha import build_ficha, robot_patch
from src.core.pillar_slab_contacts import apply_contact_openings


def payload():
    contact = {'contact_id': 'L1:0', 'slab_name': 'L1', 'left_distance': 4,
               'right_distance': 26, 'width': 30, 'height': 14,
               'level': 103, 'top_distance': 0, 'pending': []}
    robot = {'altura': 300, 'comprimento': 60, 'largura': 20,
             'nivel_chegada_abs': 103, 'h1_A': 2,
             'abertura_A_1': {'lado': 'direito', 'largura': 10, 'altura': 40,
                              '_viga': 'V1', '_origem': 'AC', '_nivel_origem': 103},
             '_sa_mode_contract': {'faces': {'A': {}}}}
    return apply_contact_openings(robot, {'A': [contact]}), contact


def test_repeat_ficha_roundtrip_does_not_duplicate_contact_or_shift_beam_identity():
    robot, contact = payload()
    pillar = {'name': 'P1', 'points': [[0, 0], [60, 0], [60, 20], [0, 20]]}
    for _ in range(3):
        ficha = build_ficha(pillar, robot, pavimento='TIPO')
        _anexar_lajes_n3(ficha, robot)
        patch = robot_patch(ficha)
        openings = [v for k, v in patch.items() if k.startswith('abertura_A_') and isinstance(v, dict)]
        slabs = [v for v in openings if v.get('_origem') == 'slab_contact']
        beams = [v for v in openings if v.get('_viga') == 'V1']
        assert len(slabs) == len(beams) == 1
        assert slabs[0]['x_offset'] == contact['left_distance'] + 11
        assert slabs[0]['_nivel_origem'] == 103
        assert beams[0]['_origem'] == 'AC'
        robot.update(patch)


def test_current_physical_contacts_refresh_automatic_but_preserve_human_list():
    robot, contact = payload()
    pillar = {'name': 'P1', 'points': [[0, 0], [60, 0], [60, 20], [0, 20]]}
    tables = {'faces': {'A': {'lajes': [{'nome': 'L2', 'nivel': 102.95,
        'nivel_status': 'sa', '_contact_intervals': [{'left_distance_cm': 8,
        'right_distance_cm': 32, 'width_cm': 20, 'thickness_cm': 12}]}]}}}
    ficha = build_ficha(pillar, robot)
    _anexar_lajes_n3(ficha, robot, tables)
    assert ficha['faces']['A']['slabs'][0]['slab_name'] == 'L2'
    assert ficha['faces']['A']['slabs'][0]['level'] == 102.95
    saved = deepcopy(ficha)
    saved['faces']['A']['slabs'] = []
    human = build_ficha(pillar, robot, saved)
    _anexar_lajes_n3(human, robot, tables)
    assert human['faces']['A']['slabs'] == []
