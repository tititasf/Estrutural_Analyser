"""Touching section symbols must not become a fictitious slab step."""
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union
from src.core.composite_cut_contours import composite_cut_contours


def rectangle(x, y, width, height):
    return dict(layer='section', points=[(x,y),(x+width,y),
                (x+width,y+height),(x,y+height),(x,y)])


@pytest.mark.parametrize('offset', [(0,0), (12345,-6789)])
def test_independent_dimensioned_bodies_keep_coverage_without_false_envelope(offset):
    x,y = offset
    pieces = [rectangle(x,y,50,14), rectangle(x-70,y+95,120,19),
              rectangle(x+5,y+14,12,81), rectangle(x,y-50,12,50)]
    texts = [dict(text='14/50',pos=(x+25,y+21)),
             dict(text='19/120',pos=(x+25,y+121))]
    old = composite_cut_contours(pieces)
    assert len(old) == 1
    result = composite_cut_contours(pieces,texts)
    assert len(result) == 2
    assert all(row['replaces_contour'] == old[0]['points'] for row in result)
    assert sorted(row['dimension_text']['text'] for row in result) == ['14/50','19/120']
    source = unary_union([Polygon(p['points']) for p in pieces])
    actual = unary_union([Polygon(p['points']) for p in result])
    assert source.symmetric_difference(actual).area < 1e-5
    for row in result:
        body = Polygon(row['body_points'])
        assert Polygon(row['points']).intersection(body).area == pytest.approx(body.area)
    lower = next(row for row in result if row['dimension_text']['text'] == '14/50')
    assert Polygon(lower['points']).bounds[2]-Polygon(lower['points']).bounds[0] == 50


def test_single_beam_remains_original_composite():
    pieces = [rectangle(0,0,50,14),rectangle(5,14,12,45)]
    original = composite_cut_contours(pieces)
    assert composite_cut_contours(pieces,[dict(text='14/50',pos=(25,-7))]) == original


def test_composite_preserves_only_contributing_original_handles():
    pieces = [rectangle(0,0,50,14), rectangle(5,14,12,45), rectangle(100,100,20,20)]
    for piece, handle in zip(pieces, ('flange', 'web', 'unrelated')):
        piece['source_entity_handles'] = [handle]
    result = composite_cut_contours(pieces)
    assert len(result) == 1
    assert result[0]['source_entity_handles'] == ['flange', 'web']
