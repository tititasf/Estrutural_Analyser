from copy import deepcopy
import math
import pytest

from src.core.pillar_u_nova_contract import u_nova_payload
from src.core.pillar_nova_design import special_payload

U = [(0, 0), (220, 0), (220, 240), (190, 240),
     (190, 30), (30, 30), (30, 240), (0, 240)]


@pytest.mark.parametrize('start', range(8))
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('quarter', range(4))
def test_caps_and_profiles_follow_physical_walls_after_reordering(start, reverse, quarter):
    def pose(p):
        x, y = p
        for _ in range(quarter):
            x, y = -y, x
        return x + 123.5, y - 70.25
    ring = [pose(p) for p in U]
    ring = ring[start:] + ring[:start]
    if reverse:
        ring.reverse()
    source = {'geometry_points': ring, 'subtipo_pil': 'U'}
    before = deepcopy(source)
    result = special_payload(source)
    assert source == before
    names = result['face_names']
    assert set(names.values()) == set('ABCDEFGH')
    actual = result['geometry_points']
    assert sum(p[0]*actual[(i+1)%8][1] - actual[(i+1)%8][0]*p[1]
               for i, p in enumerate(actual)) > 0
    caps = [{actual[i], actual[(i+1)%8]} for i in result['panel_end_cap_faces']]
    assert {frozenset(edge) for edge in caps} == {
        frozenset([pose(U[2]), pose(U[3])]),
        frozenset([pose(U[6]), pose(U[7])]),
    }
    assert {names[str(i)] for i in result['metal_profile_faces']} == set('ABEFGH')
    assert result['inner_bolt_clearance_cm'] == 35


def test_other_shapes_do_not_become_u_and_l_contract_is_preserved():
    assert u_nova_payload({'geometry_points': [(0, 0), (10, 0), (10, 10), (0, 10)]}) is None
    assert u_nova_payload({'geometry_points': [(90, 0), (130, 0), (130, 200),
                         (240, 200), (240, 240), (0, 240), (0, 200), (90, 200)]}) is None
    payload = special_payload({'geometry_points': [(0, 0), (100, 0), (100, 30),
                                                   (30, 30), (30, 120), (0, 120)]})
    assert len(payload['geometry_points']) == 6
    assert payload['inner_bolt_clearance_cm'] == 20


def test_asymmetric_legs_keep_their_measured_lengths():
    ring = [(0, 0), (220.5, 0), (220.5, 260.25), (182.25, 260.25),
            (182.25, 35.5), (25.25, 35.5), (25.25, 210.75), (0, 210.75)]
    result = u_nova_payload({'geometry_points': ring})
    widths = {result['face_names'][str(i)]: math.dist(p, result['geometry_points'][(i+1)%8])
              for i, p in enumerate(result['geometry_points'])}
    assert widths == pytest.approx({'A': 220.5, 'B': 157, 'C': 25.25, 'D': 38.25,
                                   'E': 210.75, 'F': 175.25, 'G': 260.25, 'H': 224.75})


@pytest.mark.parametrize('width,required', [(40, False), (40.01, True)])
def test_grade_requirement_uses_physical_cap_width_not_panel_override(width, required):
    from src.core.cima_l_contract import n3_faces_l
    ring = [(0, 0), (220, 0), (220, 240), (220-width, 240),
            (220-width, 30), (width, 30), (width, 240), (0, 240)]
    source = {'geometry_points': ring, 'larg1_C': 70, 'larg1_D': 70}
    abcd = {r['id']: r for r in n3_faces_l(source)}
    grades = {r['id']: r for r in n3_faces_l(source, grades_only=True)}
    assert set(abcd) == set('ABCDEFGH')
    assert abcd['C']['panel'] == 70
    assert abcd['C']['inner'] == pytest.approx(width)
    assert ('C' in grades) is required
    assert ('D' in grades) is required
    assert set('ABEFGH') <= set(grades)


def test_all_saved_golden_inputs_preserve_the_legacy_special_contract():
    """Exercise every saved PIL input, without relabeling an absent U as PASS."""
    import json
    from pathlib import Path
    from src.core.cima_l_contract import n3_faces_l, secao_l_do_payload, paineis_l_from_secao
    root = Path(__file__).resolve().parents[1]
    inputs = list((root/'GOLDEN').rglob('PIL/*/ficha.json'))
    assert len(inputs) > 0
    for path in inputs:
        pj = json.loads(path.read_text(encoding='utf-8'))
        before = deepcopy(pj)
        # All saved inputs currently lack physical U contours. This proves
        # branch preservation, not a regenerated golden G1/G2 approval.
        assert u_nova_payload(pj) is None, str(path)
        section = secao_l_do_payload(pj)
        if section:
            dims = paineis_l_from_secao(section)
            expected = [
                ('A', dims['haste_ext'], dims['haste']),
                ('B', dims['haste_int'], dims['haste']-dims['espessura']),
                ('C', dims['espessura'], dims['espessura']),
                ('D', dims['espessura'], dims['espessura']),
                ('E', dims['ramo_ext'], dims['ramo']),
                ('F', dims['ramo_int'], dims['ramo']-dims['espessura']),
            ]
        else:
            expected = []
        for grades_only in (False, True):
            assert [(f['id'], f['panel'], f['inner']) for f in
                    n3_faces_l(pj, grades_only=grades_only)] == expected, str(path)
        assert pj == before


@pytest.mark.parametrize('mode', ['NOVA', 'INI'])
@pytest.mark.parametrize('cap_width', [30, 40, 41])
def test_actual_task_covers_eight_faces_and_only_required_grades(tmp_path, mode, cap_width):
    import json
    import ezdxf
    from src.core.pillar_n3_ficha import build_ficha, robot_patch
    from src.core.pillar_n3_tasks import draw_pillar_task
    ring = [(0, 0), (220, 0), (220, 240), (220-cap_width, 240),
            (220-cap_width, 30), (cap_width, 30), (cap_width, 240), (0, 240)]
    pillar = {'name': 'PU', 'points': ring, 'subtipo_pil': 'U'}
    payload = {'nome': 'PU', 'geometry_points': ring, 'subtipo_pil': 'U',
               'comprimento': 220, 'largura': cap_width, 'altura': 280,
               'grade_1': 120, 'grade_2': 100}
    payload.update(robot_patch(build_ficha(pillar, payload)))
    before = deepcopy(payload)
    (tmp_path/'PU.json').write_text(json.dumps(payload))
    _, paths, error, _ = draw_pillar_task(('PU_PASSA', payload, tmp_path, mode, []))
    assert not error, error
    assert payload == before
    for zone, path in paths.items():
        doc = ezdxf.readfile(path)
        texts = {e.dxf.text for e in doc.modelspace().query('TEXT')}
        if zone == 'cima':
            assert set('ABCDEFGH') <= texts
        else:
            expected = 'ABEFGH' if zone == 'grades' and cap_width <= 40 else 'ABCDEFGH'
            assert {text for text in texts if text.startswith('PU.')} == {'PU.'+f for f in expected}
        assert not doc.audit().errors


def test_task_refuses_publication_when_a_real_generated_face_is_missing(tmp_path, monkeypatch):
    import json
    from src.core.pillar_n3_ficha import build_ficha, robot_patch
    from src.core.pillar_n3_tasks import draw_pillar_task
    import gerar_pl_dxf_stog as generator
    from scripts.drawing_semantics import instrument
    instrument(vars(generator), 'PL')
    original = generator.generate_pilar_zone
    def omit_one_face(msp, pj, zone, **kwargs):
        result = original(msp, pj, zone, **kwargs)
        if zone == 'abcd':
            for e in list(msp.query('TEXT')):
                if e.dxf.text == 'PU.H':
                    msp.delete_entity(e)
        return result
    monkeypatch.setattr(generator, 'generate_pilar_zone', omit_one_face)
    payload = {'nome': 'PU', 'geometry_points': U, 'subtipo_pil': 'U',
               'comprimento': 220, 'largura': 30, 'altura': 280,
               'grade_1': 120, 'grade_2': 100}
    payload.update(robot_patch(build_ficha({'name': 'PU', 'points': U}, payload)))
    (tmp_path/'PU.json').write_text(json.dumps(payload))
    destination = tmp_path/'published'
    _, paths, error, _ = draw_pillar_task(('PU_PASSA', payload, tmp_path, 'NOVA', [destination]))
    assert 'missing required faces' in error and 'PU.H' in error
    assert paths == {}
    assert not destination.exists()
