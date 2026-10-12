import copy

import ezdxf
import pytest

from portal.app.qa_cad_gate import measure


@pytest.mark.parametrize('case,expected', [('bilateral', 'measured'),
    ('missing_wall', 'uncertain'), ('foreign_name', 'uncertain'),
    ('missing_local_section', 'uncertain')])
@pytest.mark.parametrize('rotated', [False, True])
def test_long_face_identity_requires_bilateral_original_walls(tmp_path, case, expected, rotated):
    doc = ezdxf.new()
    ms = doc.modelspace()
    transform = (lambda p: (p[1], p[0])) if rotated else (lambda p: p)
    points = list(map(transform, [(0, 0), (60, 0), (60, 20), (0, 20)]))
    ms.add_lwpolyline(points, close=True)
    for x in (10, 24):
        ms.add_line(transform((x, -100)), transform((x, 0)))
        if case != 'missing_wall' or x != 24:
            ms.add_line(transform((x, 20)), transform((x, 120)))
    def text(value, pos):
        ms.add_text(value, dxfattribs={'insert': transform(pos), 'height': 2,
            'rotation': 0 if rotated else 90})
    text('V999', (12, -80))
    text('14/55', (12, -40))
    if case != 'missing_local_section':
        text('14/50', (12, 60))
    if case == 'foreign_name':
        text('V888', (12, 100))
    # A/B are the long physical faces in both orientations. Only the upper
    # original span lacks its name: its local height must not be transported.
    target_face = 'B'
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'vertical' if rotated else 'horizontal',
            'faces': {'A': {'chega': [dict(nome='V999', dim='14/55',
                dist_esq='36cm', dist_dir='10cm')]},
                target_face: {'chega': [dict(nome='V999', dim='14/50',
                dist_esq='10cm', dist_dir='36cm')]}}}}]}}
    path = tmp_path/'long_face.dxf'
    doc.saveas(path)
    contact = next(c for c in measure(path, snapshot)['contacts'] if c['face'] == target_face)
    assert contact['status'] == expected
    if expected == 'measured':
        assert contact['identity_path']['kind'] == 'original_bilateral_collinear_walls'
        assert contact['section'] == '14/50'
        assert contact['beam_handles'] and contact['wall_handles'] and contact['section_handles']


@pytest.mark.parametrize('case,expected', [('bilateral','measured'),('local_height_change','measured'),
    ('foreign_name','uncertain'),('offset','uncertain'),('missing_wall','uncertain'),
    ('missing_source_name','uncertain'),('missing_local_section','uncertain')])
@pytest.mark.parametrize('rotated', [False,True])
def test_identity_across_pillar_requires_two_original_collinear_corridors(tmp_path,case,expected,rotated):
    doc = ezdxf.new()
    ms = doc.modelspace()
    transform = (lambda p:(p[1],p[0])) if rotated else (lambda p:p)
    points = list(map(transform,[(0,0),(60,0),(60,19),(0,19)]))
    ms.add_lwpolyline(points,close=True)
    for y in (0,19):
        ms.add_lwpolyline([transform((-100,y)),transform((0,y))])
        if not (case=='missing_wall' and y==19):
            offset = 1 if case=='offset' else 0
            ms.add_lwpolyline([transform((60,y+offset)),transform((160,y+offset))])
    def text(value,pos):
        ms.add_text(value,dxfattribs={'insert':transform(pos),'height':2,'rotation':90 if rotated else 0})
    if case!='missing_source_name':
        text('V999',(-80,5))
    text('19/55',(-40,5))
    local_section = '19/50' if case=='local_height_change' else '19/55'
    if case!='missing_local_section':
        text(local_section,(100,5))
    if case=='foreign_name':
        text('V888',(130,5))
    def link(dim):
        return dict(nome='V999',dim=dim,dist_esq='0cm',dist_dir='0cm')
    snapshot = {'collections':{'pilares':[{'points':points,'interpretacao_abcd':{
        'orientation':'vertical' if rotated else 'horizontal','faces':{
            'D' if rotated else 'C':{'interior':[link('19/55')]},
            'C' if rotated else 'D':{'interior':[link(local_section)]}}}}]}}
    path = tmp_path/'bilateral.dxf'
    doc.saveas(path)
    contacts = measure(path,snapshot)['contacts']
    target = next(c for c in contacts if c['face']==('C' if rotated else 'D'))
    assert target['status']==expected
    if expected=='measured':
        assert target['identity_path']['kind']=='original_bilateral_collinear_walls'
        assert target['beam_handles'] and target['section_handles']
        assert target['section']==local_section
        assert not target['errors']


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('mutate', [False, True])
def test_six_face_original_contour_measures_edge_not_enclosing_box(tmp_path, reverse, mutate):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (165, 0), (165, 19), (19, 19), (19, 218), (0, 218)]
    if reverse:
        points.reverse()
    contour = ms.add_lwpolyline(points, close=True)
    for y in (199, 218):
        ms.add_lwpolyline([(-100, y), (0, y)])
    ms.add_text('V999', dxfattribs={'insert': (-70, 205), 'height': 2})
    ms.add_text('19/55', dxfattribs={'insert': (-30, 205), 'height': 2})
    path = tmp_path/'physical.dxf'
    doc.saveas(path)
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'vertical', 'faces': {'A': {'chega': [
            dict(nome='V999', dim='19/55', dist_esq='0cm', dist_dir='199cm')]}}}}]}}
    if mutate:
        snapshot['collections']['pilares'][0]['points'] = [(x+1, y) for x,y in points]
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == ('uncertain' if mutate else 'measured')
    if not mutate:
        assert contact['pillar_handle'] == contour.dxf.handle
        assert contact['physical_face']
        # Ring reversal reverses the canonical endpoint direction too.
        expected = (199, 0) if reverse else (0, 199)
        assert (contact['dist_esq_cm'], contact['dist_dir_cm']) == expected


@pytest.mark.parametrize('case,expected', [('capped_t', 'measured'),
    ('real_cross', 'uncertain'), ('missing_cap', 'uncertain'),
    ('missing_wall', 'uncertain'), ('competitor', 'uncertain'),
    ('closed_pillar', 'uncertain'), ('other_face_name', 'measured')])
@pytest.mark.parametrize('rotated', [False, True])
def test_identity_corridor_distinguishes_original_capped_t_from_barriers(tmp_path, case, expected, rotated):
    doc = ezdxf.new()
    ms = doc.modelspace()
    transform = (lambda p: (p[1], p[0])) if rotated else (lambda p: p)
    points = list(map(transform, [(0, 0), (60, 0), (60, 19), (0, 19)]))
    ms.add_lwpolyline(points, close=True)
    def line(a, b):
        ms.add_lwpolyline([transform(a), transform(b)])
    def text(value, pos, transverse=False):
        ms.add_text(value, dxfattribs={'insert': transform(pos), 'height': 2,
            'rotation': (0 if rotated else 90) if transverse else (90 if rotated else 0)})
    line((-100, 0), (0, 0))
    line((-100, 19), (-60, 19))
    if case != 'missing_cap':
        line((-60, 19), (-41, 19))
    line((-41, 19), (0, 19))
    start = -50 if case == 'real_cross' else 19
    line((-60, start), (-60, 100))
    line((-41, start), (-41, 100))
    if case == 'missing_wall':
        # The longitudinal bottom ends before the requested pillar.
        ms.delete_entity(list(ms.query('LWPOLYLINE'))[1])
        line((-100, 0), (-2, 0))
    text('V999', (-90, -3))
    text('19/55', (-20, -3))
    text('V888', (-55, 50), True)
    text('19/50', (-50, 70), True)
    if case == 'competitor':
        text('V777', (-30, -3))
    if case == 'other_face_name':
        text('V777', (90, -3))
    if case == 'closed_pillar':
        ms.add_lwpolyline(list(map(transform, [(-60, 0), (-41, 0), (-41, 19), (-60, 19)])), close=True)
        text('P9', (-50, 10))
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'vertical' if rotated else 'horizontal',
            'faces': {'D' if rotated else 'C': {'interior': [dict(nome='V999', dim='19/55',
                dist_esq='0cm', dist_dir='0cm')]}}}}]}}
    path = tmp_path/'junction.dxf'
    doc.saveas(path)
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == expected
    assert not contact['errors']
    if expected == 'measured':
        assert contact['beam_handles'] and contact['section_handles'] and contact['wall_handles']


@pytest.mark.parametrize('orientation,face,points,walls,pos,dist', [
    ('horizontal', 'B', [(0, 0), (60, 0), (60, 20), (0, 20)],
     [((10, 20), (10, 100)), ((24, 20), (24, 100))], (12, 40), (10, 36)),
    ('vertical', 'D', [(0, 0), (20, 0), (20, 60), (0, 60)],
     [((2, -100), (2, 0)), ((16, -100), (16, 0))], (4, -50), (4, 2)),
])
@pytest.mark.parametrize('role', ['chega', 'interior'])
def test_oriented_contact_and_swapped_distances(tmp_path, orientation, face, points, walls, pos, dist, role):
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline(points, close=True)
    for a, b in walls:
        ms.add_line(a, b)
    ms.add_text('V999', dxfattribs={'insert': pos, 'height': 2, 'rotation': 90})
    ms.add_text('14/55', dxfattribs={'insert': (pos[0], pos[1]+5), 'height': 2, 'rotation': 90})
    path = tmp_path/'original.dxf'
    doc.saveas(path)
    link = dict(nome='V999', dim='14/55', dist_esq=f'{dist[0]}cm', dist_dir=f'{dist[1]}cm')
    pillar = dict(points=points, interpretacao_abcd=dict(orientation=orientation, faces={face: {role: [link]}}))
    snapshot = {'collections': {'pilares': [pillar]}}
    before = copy.deepcopy(snapshot)
    contact = measure(path, snapshot)['contacts'][0]
    assert snapshot == before
    assert contact['status'] == 'measured'
    assert contact['role'] == role
    assert (contact['dist_esq_cm'], contact['dist_dir_cm']) == dist
    assert not contact['errors']
    link.update(dist_esq=f'{dist[1]}cm', dist_dir=f'{dist[0]}cm')
    swapped = measure(path, snapshot)['contacts'][0]
    assert 'distancias_cantos' in swapped['errors']


def test_passing_role_never_disappears_or_uses_arrival_approval(tmp_path):
    doc = ezdxf.new()
    path = tmp_path/'original.dxf'
    doc.saveas(path)
    snapshot = {'collections': {'pilares': [{'points': [[0, 0], [20, 0], [20, 60], [0, 60]],
        'interpretacao_abcd': {'faces': {'A': {'passa': [{'nome': 'V999', 'dim': '14/55'}]}}}}]}}
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['role'] == 'passa'
    assert contact['status'] == 'uncertain'
    assert 'canto' in contact['reason']
    assert 'não inventar posição' in contact['reason']


@pytest.mark.parametrize('foreign_name', [None, 'V888'])
def test_foreign_or_unidentified_section_cannot_certify_requested_beam(tmp_path, foreign_name):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (20, 0), (20, 60), (0, 60)]
    ms.add_lwpolyline(points, close=True)
    ms.add_line((20, 10), (120, 10))
    ms.add_line((20, 24), (120, 24))
    ms.add_text('14/55', dxfattribs={'insert': (40, 15), 'height': 2})
    if foreign_name:
        ms.add_text(foreign_name, dxfattribs={'insert': (60, 15), 'height': 2})
    path = tmp_path/'foreign.dxf'
    doc.saveas(path)
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'faces': {'B': {'chega': [dict(nome='V999', dim='14/55',
            dist_esq='10cm', dist_dir='36cm')]}}}}]}}
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == 'uncertain'
    assert 'section' not in contact
    assert 'vão próprio' in contact['reason']


@pytest.mark.parametrize('named_support', [False, True])
def test_annotation_crossing_is_not_support_but_named_closed_pillar_is(tmp_path, named_support):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (20, 0), (20, 60), (0, 60)]
    ms.add_lwpolyline(points, close=True)
    ms.add_line((20, 10), (120, 10))
    ms.add_line((20, 24), (120, 24))
    # A detached exploded section stroke crosses the beam band.
    ms.add_line((50, 0), (50, 30))
    if named_support:
        ms.add_lwpolyline([(50, 0), (60, 0), (60, 40), (50, 40)], close=True)
        ms.add_text('P2', dxfattribs={'insert': (55, 30), 'height': 2})
    # Own section is before the crossing, name is behind it.
    ms.add_text('14/55', dxfattribs={'insert': (35, 15), 'height': 2})
    ms.add_mtext('V999', dxfattribs={'insert': (90, 15), 'char_height': 2})
    path = tmp_path/'supports.dxf'
    doc.saveas(path)
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'faces': {'B': {'chega': [dict(nome='V999', dim='14/55',
            dist_esq='10cm', dist_dir='36cm')]}}}}]}}
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == ('uncertain' if named_support else 'measured')


def test_pillar_dimension_crossing_beam_corridor_is_not_beam_section(tmp_path):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (20, 0), (20, 60), (0, 60)]
    ms.add_lwpolyline(points, close=True)
    ms.add_line((20, 10), (120, 10))
    ms.add_line((20, 29), (120, 29))
    ms.add_text('V999', dxfattribs={'insert': (40, 15), 'height': 2})
    # A pillar annotation lies in the corridor but is oriented across the beam.
    ms.add_text('P2', dxfattribs={'insert': (60, 16), 'height': 2, 'rotation': 90})
    ms.add_text('19/50', dxfattribs={'insert': (60, 12), 'height': 2, 'rotation': 90})
    path = tmp_path/'pillar_dim.dxf'
    doc.saveas(path)
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'faces': {'B': {'chega': [dict(nome='V999', dim='19/55',
            dist_esq='10cm', dist_dir='31cm')]}}}}]}}
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == 'uncertain'
    assert not contact['errors']
    assert 'section' not in contact


def test_variable_beam_sections_are_compared_only_in_proved_local_span(tmp_path):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (19, 0), (19, 60), (0, 60)]
    ms.add_lwpolyline(points, close=True)
    for x in (0, 19):
        ms.add_line((x, -100), (x, 0))
        ms.add_line((x, 60), (x, 160))
    for y, dim in [(-50, '19/50'), (100, '19/55')]:
        ms.add_text('V999', dxfattribs={'insert': (5, y), 'height': 2, 'rotation': 90})
        ms.add_text(dim, dxfattribs={'insert': (5, y+5), 'height': 2, 'rotation': 90})
    path = tmp_path/'variable.dxf'
    doc.saveas(path)
    def link(dim):
        return dict(nome='V999', dim=dim, dist_esq='0cm', dist_dir='0cm')
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'vertical', 'faces': {
            'C': {'interior': [link('19/55')]}, 'D': {'interior': [link('19/50')]}}}}]}}
    contacts = measure(path, snapshot)['contacts']
    assert all(c['status'] == 'measured' and not c['errors'] for c in contacts)
    snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces']['D']['interior'][0]['dim'] = '19/55'
    contacts = measure(path, snapshot)['contacts']
    assert not next(c for c in contacts if c['face'] == 'C')['errors']
    assert 'dimensoes' in next(c for c in contacts if c['face'] == 'D')['errors']


@pytest.mark.parametrize('gap', [0, 1])
def test_original_touching_wall_pieces_preserve_handles_without_bridging_gap(tmp_path, gap):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (19, 0), (19, 60), (0, 60)]
    ms.add_lwpolyline(points, close=True)
    walls = []
    for x in (0, 19):
        walls.append(ms.add_lwpolyline([(x, -100), (x, -50)]).dxf.handle)
        walls.append(ms.add_lwpolyline([(x, -50+gap), (x, 0)]).dxf.handle)
    ms.add_text('V999', dxfattribs={'insert': (5, -80), 'height': 2, 'rotation': 90})
    ms.add_text('19/55', dxfattribs={'insert': (5, -20), 'height': 2, 'rotation': 90})
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'vertical', 'faces': {'D': {'interior': [
            dict(nome='V999', dim='19/55', dist_esq='0cm', dist_dir='0cm')]}}}}]}}
    path = tmp_path/'pieces.dxf'
    doc.saveas(path)
    contact = measure(path, snapshot)['contacts'][0]
    assert contact['status'] == ('uncertain' if gap else 'measured')
    if not gap:
        assert set(contact['wall_handles']) == set(walls)


@pytest.mark.parametrize('horizontal', [False, True])
@pytest.mark.parametrize('wrong_corner', [False, True])
def test_passing_corner_requires_proved_source_walls_and_external_continuity(tmp_path, horizontal, wrong_corner):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (19, 0), (19, 60), (0, 60)]
    beamwalls = [((0, -100), (0, 0)), ((19, -100), (19, 0))]
    if horizontal:
        points = [(y, x) for x, y in points]
        beamwalls = [((a[1], a[0]), (b[1], b[0])) for a,b in beamwalls]
    ms.add_lwpolyline(points, close=True)
    for a, b in beamwalls:
        ms.add_line(a, b)
    pos = (-60, 5) if horizontal else (5, -60)
    ms.add_text('V999', dxfattribs={'insert': pos, 'height': 2, 'rotation': 0 if horizontal else 90})
    ms.add_text('19/55', dxfattribs={'insert': (pos[0]+5, pos[1]+5), 'height': 2,
                                   'rotation': 0 if horizontal else 90})
    short_face = 'C' if horizontal else 'D'
    corner = 'AD' if horizontal else 'AC'
    if not wrong_corner:
        corner = 'AC' if horizontal else 'AD'
    link = dict(nome='V999', dim='19/55', dist_esq='0cm', dist_dir='0cm')
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'horizontal' if horizontal else 'vertical',
            'faces': {short_face: {'interior': [link]}, 'A': {'passa': [dict(link, canto=corner)]}}}}]}}
    path = tmp_path/'corner.dxf'
    doc.saveas(path)
    contacts = measure(path, snapshot)['contacts']
    passing = next(c for c in contacts if c['role'] == 'passa')
    assert passing['status'] == ('uncertain' if wrong_corner else 'measured')
    if not wrong_corner:
        assert passing['aspect'] == 'passa_corner'
        assert passing['source_contact_face'] == short_face
        assert passing['wall_handles']
        assert passing['section_handles']
        assert passing['beam_handles']


@pytest.mark.parametrize('horizontal', [False, True])
@pytest.mark.parametrize('wrong_corner', [False, True])
def test_short_face_passing_uses_independent_long_face_proof(tmp_path, horizontal, wrong_corner):
    doc = ezdxf.new()
    ms = doc.modelspace()
    points = [(0, 0), (19, 0), (19, 60), (0, 60)]
    beamwalls = [((-100, 0), (0, 0)), ((-100, 19), (0, 19))]
    if horizontal:
        points = [(y, x) for x, y in points]
        beamwalls = [((a[1], a[0]), (b[1], b[0])) for a,b in beamwalls]
    ms.add_lwpolyline(points, close=True)
    for a, b in beamwalls:
        ms.add_line(a, b)
    pos = (5, -60) if horizontal else (-60, 5)
    ms.add_text('V999', dxfattribs={'insert': pos, 'height': 2, 'rotation': 90 if horizontal else 0})
    ms.add_text('19/55', dxfattribs={'insert': (pos[0]+5, pos[1]+5), 'height': 2,
                                   'rotation': 90 if horizontal else 0})
    short_face = 'C' if horizontal else 'D'
    link = dict(nome='V999', dim='19/55', dist_esq='0cm' if horizontal else '41cm',
                dist_dir='41cm' if horizontal else '0cm')
    snapshot = {'collections': {'pilares': [{'points': points,
        'interpretacao_abcd': {'orientation': 'horizontal' if horizontal else 'vertical',
            'faces': {'A': {'chega': [link]}, short_face: {'passa': [dict(link,
                canto=short_face+('B' if wrong_corner else 'A'))]}}}}]}}
    path = tmp_path/'short_corner.dxf'
    doc.saveas(path)
    passing = next(c for c in measure(path, snapshot)['contacts'] if c['role'] == 'passa')
    assert passing['status'] == ('uncertain' if wrong_corner else 'measured')
    if not wrong_corner:
        assert passing['source_contact_face'] == 'A'
        assert passing['wall_handles'] and passing['beam_handles'] and passing['section_handles']

