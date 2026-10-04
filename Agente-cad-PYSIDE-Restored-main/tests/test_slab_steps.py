import ezdxf
import pytest
from src.core.slab_steps import collect_sa_steps, recognize_slabs


def drawing(tmp_path, *, region_level=100.16, principal_level=100.19, section=True):
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True,
                     dxfattribs={'color': 3})
    for text, pos in [('h=10', (60, 50)), ('h=13', (150, 150))]:
        ms.add_text(text, dxfattribs={'insert': pos})
    for value, pos in [(region_level, (60, 60)), (principal_level, (150, 160))]:
        if value is not None:
            ms.add_text(str(value), dxfattribs={'insert': pos})
    if section:
        # 10cm below region boundary; 13cm above; right edge continuous.
        ms.add_lwpolyline([(40, 60), (50, 60), (50, 140), (37, 140),
                          (37, 100), (40, 100)], close=True, dxfattribs={'color': 8})
    path = tmp_path/'source.dxf'
    doc.saveas(path)
    slab = {'name': 'LX99', 'points': [(0, 0), (200, 0), (200, 200), (0, 200)],
            'fields': {'laje_nivel': '100.16'}}
    return slab, path


def test_equal_bottom_preserves_one_slab_and_lists_real_section(tmp_path):
    slab, path = drawing(tmp_path)
    step = recognize_slabs([slab], path)['LX99'][0]
    assert step['status'] == 'same_bottom'
    assert step['bottom_m'] == step['owner_bottom_m'] == 100.06
    assert step['color'] == '#ffe033'
    assert len(step['sections']) == 1


def test_different_bottom_red_even_with_section(tmp_path):
    slab, path = drawing(tmp_path, region_level=100.12)
    step = recognize_slabs([slab], path)['LX99'][0]
    assert step['status'] == 'different_bottom'
    assert step['bottom_delta_m'] == -.04
    assert step['color'] == '#ff4545'


def test_missing_level_only_transports_through_proved_flat_bottom(tmp_path):
    slab, path = drawing(tmp_path, region_level=None)
    step = recognize_slabs([slab], path)['LX99'][0]
    assert step['level_m'] == 100.16
    assert step['method'] == 'scoped_level_and_flat_bottom_section'
    slab, path = drawing(tmp_path, region_level=None, section=False)
    step = recognize_slabs([slab], path)['LX99'][0]
    assert step['status'] == 'unknown'
    assert step['level_m'] is None


def test_principal_level_not_inset_and_human_preserved(tmp_path):
    slab, path = drawing(tmp_path)
    geometry = list(slab['points'])
    collect_sa_steps([slab], path)
    assert slab['fields']['laje_nivel'] == '100.19'
    assert slab['points'] == geometry
    slab['fields']['laje_nivel'] = '100.25'
    slab['validated_fields'] = ['laje_nivel']
    collect_sa_steps([slab], path)
    assert slab['fields']['laje_nivel'] == '100.25'


def test_beam_t_section_not_a_slab_step_section(tmp_path):
    slab, path = drawing(tmp_path, section=False)
    doc = ezdxf.readfile(path)
    doc.modelspace().add_lwpolyline([(20, 130), (80, 130), (80, 120), (60, 120),
        (60, 60), (40, 60), (40, 120), (20, 120)], close=True, dxfattribs={'color': 8})
    doc.saveas(path)
    assert recognize_slabs([slab], path)['LX99'][0]['sections'] == []


def test_region_without_changed_h_not_a_step(tmp_path):
    slab, path = drawing(tmp_path)
    doc = ezdxf.readfile(path)
    for e in doc.modelspace().query('TEXT'):
        if e.dxf.text == 'h=10':
            e.dxf.text = 'h=13'
    doc.saveas(path)
    assert recognize_slabs([slab], path) == {}
