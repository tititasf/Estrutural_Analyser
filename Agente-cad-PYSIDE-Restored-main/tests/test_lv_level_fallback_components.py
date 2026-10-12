"""D-61 keeps estimates within a measured run, including displaced homonyms."""
import copy

import pytest
from shapely.geometry import box

from src.core.lv_beam_scene import LvScene
from src.core.beam_interpreters.lateral_viga_cells import (
    apply_cells_to_beam, estimate_missing_cell_levels, _cell_entries,
)


def scene(start=0., end=100., offset=0., horizontal=True, angle=0.):
    s = LvScene('V1', horizontal, offset, offset + 14., start, end, angle=angle)
    s.sections = [dict(start=start, end=end, dim='14/55', depth=55.)]
    return s


def slab(s, side, level):
    s.slabs[side] = [dict(start=s.start, end=s.end, name='L1', level=str(level), height='10')]


def entries(beam, side, behavior='Para'):
    return [e for e in _cell_entries(beam) if e['side'] == side and e['behavior'] == behavior]


@pytest.mark.parametrize('horizontal,angle', [(True, 0.), (False, 0.), (True, -43.)])
def test_local_opposite_face_precedes_same_side_remote_homonym(horizontal, angle):
    local = scene(horizontal=horizontal, angle=angle)
    remote = scene(start=2200., end=2500., offset=1000.)
    slab(local, 'B', 123.25)
    slab(remote, 'A', 123.18)
    beam = {'name': 'V1'}
    apply_cells_to_beam(beam, [local, remote])
    target, remote_a = entries(beam, 'A')
    original = copy.deepcopy(remote_a)
    estimate_missing_cell_levels(beam, [])
    cell = target['lv_cell']
    assert cell['level'] == '123.25'
    assert cell['level_estimado']['origem'] == 'outro_segmento'
    assert cell['level_estimado']['source_physical_run'] == entries(beam, 'B')[0]['lv_cell']['physical_run']
    assert remote_a == original


def test_missing_local_source_never_uses_remote_component_or_cascaded_estimate():
    local, remote = scene(), scene(2200., 2500.)
    slab(remote, 'A', 123.18)
    beam = {'name': 'V1'}
    apply_cells_to_beam(beam, [local, remote])
    estimate_missing_cell_levels(beam, [])
    assert entries(beam, 'A')[0]['lv_cell']['level'] == ''
    assert entries(beam, 'B')[0]['lv_cell']['level'] == ''
    # A local estimate may not bootstrap its other modality or face.
    target = entries(beam, 'A')[0]['lv_cell']
    target['level'], target['level_estimado'] = '123.4', {'origem': 'laje_mais_proxima'}
    estimate_missing_cell_levels(beam, [])
    assert entries(beam, 'B')[0]['lv_cell']['level'] == ''


def test_legacy_without_run_proof_retains_slab_fallback_as_estimated():
    s = scene(); slab(s, 'B', 123.25)
    beam = {'name': 'V1'}; apply_cells_to_beam(beam, s)
    for e in _cell_entries(beam):
        e['lv_cell'].pop('physical_run')
    estimate_missing_cell_levels(beam, [({'name': 'L2', 'nivel': '123.1'}, box(0, 30, 100, 50))])
    cell = entries(beam, 'A')[0]['lv_cell']
    assert cell['level'] == '123.1'
    assert cell['level_estimado']['origem'] == 'laje_mais_proxima'


def test_incompatible_section_blocks_opposite_face_fallback():
    s = scene(); slab(s, 'B', 123.25)
    beam = {'name': 'V1'}; apply_cells_to_beam(beam, s)
    for e in entries(beam, 'B') + entries(beam, 'B', 'Passa'):
        e['lv_cell']['dim'], e['lv_cell']['depth'] = '14/70', 70.
    estimate_missing_cell_levels(beam, [])
    assert entries(beam, 'A')[0]['lv_cell']['level'] == ''


def test_touching_bend_is_not_assumed_to_share_datum():
    first = scene()
    bend = scene(start=14., end=100., offset=100., horizontal=False)
    slab(bend, 'A', 123.25)
    beam = {'name': 'V1'}; apply_cells_to_beam(beam, [first, bend])
    estimate_missing_cell_levels(beam, [])
    assert entries(beam, 'A')[0]['lv_cell']['level'] == ''


def test_human_frozen_target_is_not_rewritten():
    s = scene(); slab(s, 'B', 123.25)
    beam = {'name': 'V1'}; apply_cells_to_beam(beam, s)
    beam['validated_fields'] = ['viga_a_seg_1_comprimento_total']
    estimate_missing_cell_levels(beam, [])
    assert entries(beam, 'A')[0]['lv_cell']['level'] == ''
