import ezdxf
import pytest
from src.core.slab_steps import collect_sa_steps, enrich_state, fill_region_levels, recognize_slabs


def test_region_singleflight_shares_concurrent_miss_and_retries_failure():
    from concurrent.futures import ThreadPoolExecutor
    from functools import lru_cache
    from threading import Event
    from src.core.slab_steps import _singleflight_regions
    entered, release = Event(), Event()
    calls = []
    @_singleflight_regions
    @lru_cache(maxsize=4)
    def compute(key):
        calls.append(key); entered.set()
        assert release.wait(3)
        if key == 'bad': raise ValueError('retry')
        return {'key': key}
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(compute, 'revision')
        assert entered.wait(3)
        second = pool.submit(compute, 'revision')
        release.set()
        assert first.result() == second.result()
    assert calls == ['revision']
    for _ in range(2):
        with pytest.raises(ValueError): compute('bad')
    assert calls == ['revision', 'bad', 'bad']


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


def test_enrich_state_refills_empty_regions_and_keeps_a_cad_level(tmp_path, monkeypatch):
    from src.core import slab_steps
    empty = dict(uid='slab-step:L1:1', level_m=None, owner_level_m=None,
                 height_cm=10, owner_height_cm=13)
    measured = dict(uid='slab-step:L2:1', level_m=855.22, owner_level_m=None,
                    height_cm=10, owner_height_cm=13)

    def fake_recognize(slabs, path):
        return {'L1': [empty], 'L2': [measured]}

    monkeypatch.setattr(slab_steps, 'recognize_slabs', fake_recognize)
    state = {'slabs': [
        {'name': 'L1', 'preprocess_region_levels': {
            'principal': {'value': 855.25}, 'slab-step:L1:1': {'value': 855.22}}},
        {'name': 'L2', 'preprocess_region_levels': {
            'principal': {'value': 855.25}, 'slab-step:L2:1': {'value': 855.10}}},
    ]}
    enrich_state(state, tmp_path / 'missing.dxf')
    filled = state['slabs'][0]['slab_steps'][0]
    kept = state['slabs'][1]['slab_steps'][0]
    assert filled['level_m'] == 855.22 and filled['owner_level_m'] == 855.25
    assert kept['level_m'] == 855.22 and kept['owner_level_m'] == 855.25


def test_height_only_region_keeps_the_slab_level_and_is_not_a_level_step():
    step = dict(uid='slab-step:L415:1', level_m=None, owner_level_m=855.25,
                height_cm=10, owner_height_cm=13, sections=[],
                evidence_checks={'direct_internal_level': False, 'direct_principal_level': True},
                status='unknown', bottom_m=None, owner_bottom_m=855.12, bottom_delta_m=None)
    fill_region_levels([step], {
        'principal': {'value': 855.25}, 'slab-step:L415:1': {'value': 855.25}})
    assert step['level_m'] == 855.25 and step['owner_level_m'] == 855.25
    assert step['status'] == 'unknown' and step['bottom_m'] is None
    assert step['color'] == '#ffe033'


def test_voted_level_different_from_the_owner_still_compares_bottoms():
    step = dict(uid='slab-step:L414:1', level_m=None, owner_level_m=855.25,
                height_cm=10, owner_height_cm=13, sections=[],
                evidence_checks={'direct_internal_level': False}, status='unknown')
    fill_region_levels([step], {
        'principal': {'value': 855.25}, 'slab-step:L414:1': {'value': 855.22}})
    assert step['level_m'] == 855.22 and step['status'] == 'same_bottom'


def test_region_without_changed_h_not_a_step(tmp_path):
    slab, path = drawing(tmp_path)
    doc = ezdxf.readfile(path)
    for e in doc.modelspace().query('TEXT'):
        if e.dxf.text == 'h=10':
            e.dxf.text = 'h=13'
    doc.saveas(path)
    assert recognize_slabs([slab], path) == {}


def test_region_cache_is_revision_scoped_and_returns_independent_results(tmp_path, monkeypatch):
    from copy import deepcopy
    from src.core import slab_steps
    path = tmp_path / 'cache.dxf'
    path.write_text('revision one')
    calls = []
    def recognize(slabs, source):
        calls.append(source)
        return {'L1': [dict(uid='slab-step:L1:1', level_m=None,
                           owner_level_m=None, height_cm=10, owner_height_cm=13)]}
    monkeypatch.setattr(slab_steps, 'recognize_slabs', recognize)
    slab_steps._cached_regions.cache_clear()
    initial = {'slabs': [{'name': 'L1', 'preprocess_region_levels': {
        'principal': {'value': 855.25}, 'slab-step:L1:1': {'value': 855.22}}}]}
    first = slab_steps.enrich_state(deepcopy(initial), path)
    first['slabs'][0]['slab_steps'][0]['level_m'] = 999
    second = slab_steps.enrich_state(deepcopy(initial), path)
    assert len(calls) == 1
    assert second['slabs'][0]['slab_steps'][0]['level_m'] == 855.22
    path.write_text('revision two, different size')
    slab_steps.enrich_state(deepcopy(initial), path)
    assert len(calls) == 2
    changed = deepcopy(initial)
    changed['slabs'][0]['name'] = 'L2'
    slab_steps.enrich_state(changed, path)
    assert len(calls) == 3


def _written_step_drawing(tmp_path, step_text='3'):
    # 14_PAV L406/96B + corte B1D: região sem h= próprio; corte com fundo
    # contínuo, 13 desenhado fora e 10 dentro, e o "3" escrito junto ao degrau.
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(100, 0), (300, 0), (300, 100), (100, 100)], close=True, dxfattribs={'color': 3})
    ms.add_lwpolyline([(66, 50), (130, 50), (130, 60), (100, 60), (100, 63), (66, 63)],
                      close=True, dxfattribs={'color': 8})
    ms.add_text('h=15', dxfattribs={'insert': (20, 150)})
    ms.add_text('100.25', dxfattribs={'insert': (20, 160)})
    if step_text:
        ms.add_text(step_text, dxfattribs={'insert': (115, 70)})
    path = tmp_path/'source.dxf'
    doc.saveas(path)
    return {'name': 'L406', 'points': [(0, 0), (400, 0), (400, 200), (0, 200)]}, path


def test_region_without_h_takes_height_and_level_from_written_step_cut(tmp_path):
    slab, path = _written_step_drawing(tmp_path)
    step = recognize_slabs([slab], path)['L406'][0]
    assert step['method'] == 'flat_bottom_section_written_step'
    assert step['height_cm'] == 12 and step['level_m'] == 100.22
    assert step['status'] == 'same_bottom' and step['bottom_m'] == step['owner_bottom_m'] == 100.1


def test_region_without_h_and_without_written_step_is_not_a_step(tmp_path):
    slab, path = _written_step_drawing(tmp_path, step_text='5')
    assert 'L406' not in recognize_slabs([slab], path)
