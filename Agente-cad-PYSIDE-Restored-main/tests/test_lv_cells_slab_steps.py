import pytest
from src.core.lv_beam_scene import LvScene, _attach_context, _slab_polygons
from src.core.beam_interpreters.lateral_viga_cells import segment_cell


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('behavior', ['para', 'passa'])
def test_contact_step_splits_cells_with_touching_endpoints(vertical, behavior):
    def pts(values):
        return [[y, x] for x, y in values] if vertical else values
    scene = LvScene('V', not vertical, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    slab = dict(name='L', height=13, nivel=8.5,
        fields={'laje_dim': '13', 'laje_nivel': '8.5'},
        points=pts([[0,-100],[300,-100],[300,0],[0,0]]),
        slab_steps=[dict(uid='inset', height_cm=10, level_m=8.47,
            owner_height_cm=13, owner_level_m=8.5,
            points=pts([[100,-50],[200,-50],[200,0],[100,0]]))])
    _attach_context(scene, [], [scene], _slab_polygons([slab]))
    cells = segment_cell(scene, 'A', behavior)
    assert len(cells) == 3
    assert sum(abs(s.end-s.start) for s in cells) == pytest.approx(300)
    assert all(left.end == right.start for left, right in zip(cells,cells[1:]))
    assert [s.slabs[0]['height'] for s in cells] == ['13.0', '10.0', '13.0']
    assert cells[1].slabs[0]['level'] == '8.47'
    assert [s.level for s in cells] == ['8.5', '8.5', '8.5']
    assert cells[1].support_start['type'] == 'degrau_laje'
    assert len(segment_cell(scene, 'B', behavior)) == 1


def test_internal_step_without_face_contact_keeps_one_segment():
    scene = LvScene('V', True, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    slab = dict(name='L', height=13, nivel=8.5,
        points=[[0,-100],[300,-100],[300,0],[0,0]],
        slab_steps=[dict(uid='inset',height_cm=10,level_m=8.47,
            owner_height_cm=13,owner_level_m=8.5,
            points=[[100,-50],[200,-50],[200,-10],[100,-10]])])
    _attach_context(scene, [], [scene], _slab_polygons([slab]))
    assert len(segment_cell(scene,'A','passa')) == 1


def test_step_reference_does_not_cross_a_beam_section_change():
    scene = LvScene('V', True, 0, 19, 0, 300)
    scene.sections = [dict(start=0,end=100,dim='19/55',depth=55),
                      dict(start=100,end=300,dim='19/60',depth=60)]
    scene.slabs['A'] = [dict(name='L',region_id='principal',start=0,end=100,
                            level='8.5',height='13'),
                        dict(name='L',region_id='inset',start=100,end=300,
                            level='8.47',height='10')]
    cells = segment_cell(scene,'A','para')
    inset = next(s for s in cells if s.slabs and s.slabs[0]['region_id']=='inset')
    assert inset.level == ''
    assert inset.slabs[0]['level']=='8.47'
