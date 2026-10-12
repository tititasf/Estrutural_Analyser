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


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('behavior', ['para', 'passa'])
@pytest.mark.parametrize('region', ['principal', 'inset'])
def test_slab_or_step_void_boundary_splits_only_contacting_face(vertical, behavior, region):
    scene = LvScene('V', not vertical, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    scene.slabs['A'] = [dict(name='L', region_id=region, start=25, end=200,
                             height='10', level='8.5')]
    cells = segment_cell(scene, 'A', behavior)
    assert len(cells) == 3
    assert sorted(s.length for s in cells) == [25, 100, 175]
    assert all(left.end == right.start for left, right in zip(cells, cells[1:]))
    assert sum(bool(s.slabs) for s in cells) == 1
    assert len(segment_cell(scene, 'B', behavior)) == 1
    boundaries = [s.support_end for s in cells[:-1]]
    assert all(s['rule'] == 'laje_ou_degrau_vazio_secciona_para_e_passa' for s in boundaries)


@pytest.mark.parametrize('gap', [0, -10, .3])
def test_continuous_neighbor_slabs_do_not_create_void_boundary(gap):
    scene = LvScene('V', True, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    scene.slabs['A'] = [dict(name=name, region_id='principal', start=a, end=b,
                             height='13', level='8.5')
                        for name,a,b in [('L1',0,150), ('L2',150+gap,300)]]
    assert len(segment_cell(scene, 'A', 'para')) == 1


def test_clipped_contact_does_not_split_passa_pillar_extension():
    scene = LvScene('V', True, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    scene.face_extent['A'] = (-30, 330)
    scene.slabs['A'] = [dict(name='L', region_id='principal', start=0, end=300,
                             height='13', level='8.5')]
    assert len(segment_cell(scene, 'A', 'passa')) == 1


def test_void_boundaries_keep_pillar_whole_and_short_free_strip():
    scene = LvScene('V', True, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    scene.pillars['A'] = [dict(name='P', start=100, end=200)]
    scene.slabs['A'] = [dict(name='L', region_id='principal', start=150, end=298.5,
                             height='13', level='8.5')]
    cells = segment_cell(scene, 'A', 'passa')
    assert len(cells) == 2
    assert [s.length for s in cells] == [298.5, 1.5]
    assert sum(s.length for s in cells) == 300
    assert len(cells[0].pillar_openings) == 1


def test_passa_along_pillar_wall_declares_the_touching_slab():
    """D-91: o trecho Passa que corre pela parede do pilar também tem laje."""
    from shapely.geometry import box
    scene = LvScene('V', True, 0, 19, 0, 300)
    scene.sections = [dict(start=0, end=300, dim='19/55', depth=55)]
    slabs = [dict(name='L1', height=13, nivel=8.5, fields={'laje_dim': '13', 'laje_nivel': '8.5'},
                  points=[[0, -100], [300, -100], [300, 0], [0, 0]]),
             dict(name='L2', height=12, nivel=8.5, fields={'laje_dim': '12', 'laje_nivel': '8.5'},
                  points=[[300, -100], [360, -100], [360, 0], [300, 0]])]
    _attach_context(scene, [('P1', 'RETANGULAR', box(300, 0, 360, 60))], [scene], _slab_polygons(slabs))
    passa = segment_cell(scene, 'A', 'passa')
    assert max(max(s.start, s.end) for s in passa) >= 359.5
    assert 'L2' in {sl['name'] for s in passa for sl in s.slabs}
    assert 'L2' not in {sl['name'] for s in segment_cell(scene, 'A', 'para') for sl in s.slabs}

