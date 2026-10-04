"""Physical section transitions must follow actual full-width divider lines."""
import pytest
from src.core.lv_beam_scene import LvScene, _EdgeIndex, _sections


@pytest.mark.parametrize('horizontal', [True, False])
def test_measured_divider_beats_label_midpoint_and_fv_reference(horizontal):
    scene = LvScene('VX', horizontal, 10, 29, 0, 400)
    point = lambda axis, t: [axis,t] if horizontal else [t,axis]
    labels = [dict(pos=point(a,8), text=f'19/{h}', section=(19,h),
                   rotation=0 if horizontal else 90)
              for a,h in [(100,120),(220,120),(350,71)]]
    divider = (*point(290,10), *point(290,29))
    crossing = (*point(260,-10), *point(260,49))
    partial = (*point(270,10), *point(270,19))
    beam = dict(links={'viga_fundo_seg_1_area_segs': dict(contour=[dict(points=[
        point(0,10),point(250,10),point(250,29),point(0,29)])])})
    _sections(scene, beam, labels, [], _EdgeIndex([divider,crossing,partial]))
    assert [(s['start'],s['end'],s['depth']) for s in scene.sections] == [(0,290,120),(290,400,71)]
    assert scene.sections[0]['end_source'] == 'structural_transverse_divider'


def test_repeated_label_updates_midpoint_when_no_real_divider_exists():
    scene = LvScene('VX', True, 0, 19, 0, 400)
    labels = [dict(pos=[a,-2],text=f'19/{h}',section=(19,h),rotation=0)
              for a,h in [(100,120),(220,120),(350,71)]]
    _sections(scene, {}, labels, [], _EdgeIndex([]))
    assert scene.sections[0]['end'] == 285
    assert scene.sections[0]['end_source'] == 'midpoint_between_labels'
