"""Source labels identify measured runs, never a remote namesake's geometry."""
from copy import deepcopy

import pytest
import src.core.lv_beam_scene as scene
import src.core.beam_interpreters.fundo_viga_lateral_ref as fv
from test_fv_diagonal_return_recovery import setup, labels_for


def recovered(beam):
    return [(link, poly) for _, link, poly in fv._panels(beam)
            if link.get('geometry_source', '').endswith('_special_diagonal')]


def test_local_label_allows_only_its_diagonal_despite_remote_namesake(monkeypatch):
    beam, angular = setup(monkeypatch)
    retained = fv._panels(beam)[0][2]
    report = fv.apply_lateral_reference_all([beam], labels_for(angular), [], {})
    assert len(recovered(beam)) == 1
    assert recovered(beam)[0][1].equals(angular.world_band())
    assert any(poly.equals(retained) for _, _, poly in fv._panels(beam))
    assert report['V900']['angular_local_identity'][0]['label_handles'] == ['NAME_DIAGONAL']
    assert 'angular_identity_pending' not in report['V900']


@pytest.mark.parametrize('label_kind', ['remote_only', 'wrong_rotation', 'outside_extent', 'too_far'])
def test_remote_or_invalid_local_label_never_authorizes_angular_run(monkeypatch, label_kind):
    beam, angular = setup(monkeypatch)
    labels = labels_for(angular)
    if label_kind == 'remote_only':
        labels = labels[1:]
    elif label_kind == 'wrong_rotation':
        labels[0]['rotation'] = 0
    elif label_kind == 'outside_extent':
        labels[0]['pos'] = list(angular.to_world(-50, 9.5))
    else:
        labels[0]['pos'] = list(angular.to_world(50, 1000))
    before = deepcopy(beam['links'])
    report = fv.apply_lateral_reference_all([beam], labels, [], {})
    assert not recovered(beam)
    assert beam['links'] == before
    assert report['V900']['angular_identity_pending']['run_indices'] == [0]


def test_missing_second_wall_blocks_even_locally_named_component(monkeypatch):
    beam, angular = setup(monkeypatch, coverage=.4)
    fv.apply_lateral_reference_all([beam], labels_for(angular), [], {})
    assert not recovered(beam)


def test_human_validated_panel_survives_component_recovery(monkeypatch):
    beam, angular = setup(monkeypatch)
    beam['links']['viga_fundo_seg_1_area_segs']['contour'][0]['validated'] = True
    before = deepcopy(beam['links'])
    fv.apply_lateral_reference_all([beam], labels_for(angular), [], {})
    assert beam['links'] == before


def test_existing_angular_panel_is_not_replaced_by_label_proof(monkeypatch):
    beam, angular = setup(monkeypatch)
    points = [list(angular.to_world(x, y)) for x, y in
              [(0, 0), (100, 0), (100, 14), (95, 19), (0, 19), (0, 0)]]
    beam['links']['viga_fundo_seg_2_area_segs'] = {
        'contour': [{'type': 'poly', 'closed': True, 'points': points,
                     'geometry_source': 'physical_chamfer'}]}
    before = deepcopy(beam['links'])
    fv.apply_lateral_reference_all([beam], labels_for(angular), [], {})
    assert not recovered(beam)
    assert beam['links'] == before


def test_named_diagonal_does_not_lend_identity_to_other_diagonal(monkeypatch):
    beam, angular = setup(monkeypatch)
    remote_cap = scene.LvScene('V900', False, 200, 219, 0, 30)
    remote_cap.face_coverage = {'A': [[0, 30]], 'B': [[0, 30]]}
    unlabelled = scene.LvScene('V900', True, 0, 19, 300, 400, angle=45)
    unlabelled.face_extent = {'A': (300, 400), 'B': (300, 400)}
    unlabelled.face_coverage = {'A': [[300, 400]], 'B': [[300, 400]]}
    monkeypatch.setattr(scene, 'build_scene_runs',
                        lambda *a, **k: {'V900': [angular, remote_cap, unlabelled]})
    report = fv.apply_lateral_reference_all([beam], labels_for(angular), [], {})
    assert len(recovered(beam)) == 1
    assert recovered(beam)[0][1].equals(angular.world_band())
    assert report['V900']['angular_identity_pending']['run_indices'] == [2]
