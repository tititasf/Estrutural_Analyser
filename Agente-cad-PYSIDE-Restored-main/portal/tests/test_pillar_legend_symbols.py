import math

import ezdxf
import pytest

from portal.app.preprocessamento.adapters.auxiliary import semantic_roles
from portal.app.preprocessamento.adapters.pillar_legend_symbols import associate_legend_symbols


def drawing(scale=1, angle=0, offset=(0, 0)):
    doc = ezdxf.new()
    model = doc.modelspace()
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def point(x, y):
        return (offset[0]+scale*(x*c-y*s), offset[1]+scale*(x*s+y*c))

    texts, handles = [], {}
    for name, x, y, height in [('CONVENÇÕES :', 0, 100, 20), ('NASCE', 70, 50, 12),
                                ('SEGUE', 230, 50, 12), ('MORRE', 390, 50, 12)]:
        entity = model.add_text(name, dxfattribs={'insert': point(x, y), 'height': height*scale, 'rotation': angle})
        texts.append({'text': name, 'handle': entity.dxf.handle, 'position': point(x, y), 'height': height*scale})
        if name.startswith('CONVEN'):
            continue
        corners = [point(x-60, y-5), point(x-10, y-5), point(x-10, y+15), point(x-60, y+15)]
        contour = model.add_lwpolyline(corners, close=True)
        handles[name] = contour.dxf.handle
        if name != 'SEGUE':
            model.add_line(point(x-60, y-5), point(x-40, y+15))
        if name == 'NASCE':
            model.add_line(point(x-60, y+15), point(x-40, y-5))
        if name == 'MORRE':
            model.add_line(point(x-50, y-5), point(x-30, y+15))
        if name == 'SEGUE':
            model.add_solid([corners[0], corners[1], corners[3], corners[2]])
        # Nearby dimension outside sample: must not alter its signature.
        model.add_line(point(x-65, y-5), point(x+10, y+20))
    return doc, texts, handles


@pytest.mark.parametrize('scale,angle,offset', [(.01, 0, (1000, -2000)), (1, 90, (0, 0)), (100, 37, (-900, 300))])
def test_bounded_symbols_keep_original_handles_and_ignore_neighbors(scale, angle, offset):
    doc, texts, handles = drawing(scale, angle, offset)
    result = associate_legend_symbols(doc, texts, semantic_roles(texts))
    assert result['status'] == 'bounded'
    assert result['classification_authority'] == 'none'
    entries = {e['label']: e for e in result['entries']}
    assert {label: e['contour_handle'] for label, e in entries.items()} == handles
    assert entries['NASCE']['signature']['signature'] == 'CROSS'
    assert entries['MORRE']['signature']['signature'] == 'DIAG'
    assert entries['SEGUE']['line_handles'] == []
    assert len(entries['SEGUE']['solid_handles']) == 1


def test_duplicate_contour_and_missing_contour_stay_unresolved():
    doc, texts, handles = drawing()
    contour = doc.entitydb[handles['NASCE']]
    doc.modelspace().add_entity(contour.copy())
    doc.modelspace().delete_entity(doc.entitydb[handles['MORRE']])
    result = associate_legend_symbols(doc, texts, semantic_roles(texts))
    assert result['status'] == 'partial'
    entries = {e['label']: e for e in result['entries']}
    assert entries['NASCE']['association_status'] == 'ambiguous'
    assert entries['MORRE']['association_status'] == 'unresolved'
    assert 'signature' not in entries['NASCE']


def test_self_crossing_contour_does_not_bind():
    doc, texts, handles = drawing()
    contour = doc.entitydb[handles['NASCE']]
    points = list(contour.get_points('xy'))
    contour.set_points([points[0], points[2], points[1], points[3]])
    result = associate_legend_symbols(doc, texts, semantic_roles(texts))
    assert result['entries'][0]['association_status'] == 'unresolved'


def test_repeated_endpoint_closes_contour_but_open_four_vertices_do_not():
    doc, texts, handles = drawing()
    contour = doc.entitydb[handles['NASCE']]
    points = list(contour.get_points('xy'))
    contour.closed = False
    contour.set_points([*points, points[0]])
    doc.entitydb[handles['MORRE']].closed = False
    result = associate_legend_symbols(doc, texts, semantic_roles(texts))
    entries = {e['label']: e for e in result['entries']}
    assert entries['NASCE']['association_status'] == 'bounded_unique_contour'
    assert entries['MORRE']['association_status'] == 'unresolved'
