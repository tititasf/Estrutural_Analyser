import pytest
from shapely.geometry import box, Polygon
from src.core.lv_beam_scene import LvScene
from src.core.beam_interpreters.fundo_viga_lateral_ref import _panel_overlap_priority


def item(index, polygon):
    return index, {'type': 'poly', 'points': list(polygon.exterior.coords)}, polygon


@pytest.mark.parametrize('angle', [45, 90])
def test_proven_nonparallel_component_cannot_change_local_priority(angle):
    beam = {'name': 'V900', 'fields': {'dimensao': '14/55'}}
    run = LvScene('V900', True, 0, 14, 0, 100)
    local = item(1, box(0, 0, 100, 14))
    other = LvScene('V900', True, 500, 514, 500, 550, angle=angle)
    remote = other.world_band()
    original = _panel_overlap_priority(beam, 1, local[1], [local], run=run)
    assert _panel_overlap_priority(beam, 1, local[1], [local, item(2, remote)],
                                   run=run, source_runs=[run, other]) == original


def test_disconnected_spans_in_same_measured_run_preserve_continuity_formula():
    beam = {'name': 'V900', 'fields': {'dimensao': '14/55'}}
    run = LvScene('V900', True, 0, 14, 0, 220)
    panels = [item(1, box(0, 0, 100, 14)), item(2, box(120, 0, 220, 14))]
    priority = _panel_overlap_priority(beam, 1, panels[0][1], panels, run=run)
    assert priority[3] == pytest.approx(.5)
    assert priority[4] == 200
    assert priority == _panel_overlap_priority(beam, 1, panels[0][1], panels)


def test_legacy_priority_without_measured_run_remains_unchanged():
    beam = {'name': 'V900', 'fields': {'dimensao': '14/55'}}
    panels = [item(i + 1, box(20 * i, 0, 20 * (i + 1), 14)) for i in range(3)]
    priority = _panel_overlap_priority(beam, 1, panels[0][1], panels)
    assert priority[3] == pytest.approx(1 / 3)
    assert priority[4] == 60


def test_source_run_preserves_existing_length_rubric():
    run = LvScene('V900', True, 0, 14, 0, 100, angle=45)
    polygon = Polygon([run.to_world(x, y) for x, y in [(0, 0), (100, 0), (100, 14), (0, 14)]])
    panel = item(1, polygon)
    beam = {'name': 'V900', 'fields': {'dimensao': '14/55'}}
    priority = _panel_overlap_priority(beam, 1, panel[1], [panel], run=run)
    assert priority[3] == 1
    assert priority == _panel_overlap_priority(beam, 1, panel[1], [panel])


def test_parallel_disconnected_runs_do_not_gain_false_continuity():
    beam = {'name': 'V900', 'fields': {'dimensao': '14/55'}}
    runs = [LvScene('V900', False, x, x+14, 0, 100) for x in (0, 500)]
    panels = [item(i+1, scene.world_band()) for i, scene in enumerate(runs)]
    baseline = _panel_overlap_priority(beam, 1, panels[0][1], panels)
    assert baseline[3] == .5
    assert _panel_overlap_priority(beam, 1, panels[0][1], panels,
                                   run=runs[0], source_runs=runs) == baseline


def test_unmatched_panel_is_not_excluded_without_source_proof():
    beam = {'name': 'V900', 'fields': {'dimensao': '14/55'}}
    run = LvScene('V900', True, 0, 14, 0, 100)
    panels = [item(1, run.world_band()), item(2, box(500, 500, 514, 600))]
    assert _panel_overlap_priority(beam, 1, panels[0][1], panels, run=run) == \
        _panel_overlap_priority(beam, 1, panels[0][1], panels)


def test_final_overlap_arbitration_preserves_remote_junction_when_diagonal_added(monkeypatch):
    from copy import deepcopy
    from shapely.ops import unary_union
    import src.core.lv_beam_scene as scene_module
    import src.core.beam_interpreters.fundo_viga_lateral_ref as fv
    horizontal = LvScene('A', True, 0, 14, 0, 220)
    diagonal = LvScene('A', True, 500, 514, 500, 600, angle=45)
    vertical = [LvScene('B', False, x, x+14, -86, 14) for x in (86, 206)]
    monkeypatch.setattr(scene_module, 'build_scene_runs',
                        lambda *args, **kwargs: {'A':[horizontal, diagonal], 'B':vertical})
    def beam(name, polygons):
        return {'name':name,'fv_is_h':name=='A','fields':{'dimensao':'14/55'},
                'links':{f'viga_fundo_seg_{index}_area_segs':{'contour':[item(index, poly)[1]]}
                         for index,poly in enumerate(polygons,1)}}
    baseline=[beam('A',[box(0,0,100,14),box(120,0,220,14)]),
              beam('B',[run.world_band() for run in vertical])]
    candidate=deepcopy(baseline)
    candidate[0]['links']['viga_fundo_seg_3_area_segs']={'contour':[item(3,diagonal.world_band())[1]]}
    for beams in (baseline,candidate):
        fv.resolve_automatic_overlaps_all(beams,texts=[],lines=[],pillar_report={})
    for old,new in zip(baseline,candidate):
        first=unary_union([p for _,_,p in fv._panels(old)])
        second=unary_union([p for _,_,p in fv._panels(new)])
        if old['name']=='A': second=second.difference(diagonal.world_band())
        assert first.symmetric_difference(second).area < 1e-6
