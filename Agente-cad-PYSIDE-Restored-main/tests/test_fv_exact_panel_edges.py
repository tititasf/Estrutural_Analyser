import ezdxf
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union
from scripts.gerar_fv_dxf_stog import draw_poly_as_lines, dedupe_panel_lines


def test_short_real_edges_keep_exact_closed_outline():
    points = [(0, 0), (99.038, 0), (99.038, .0005),
              (118, .0005), (118, .0175), (118.038, .0175),
              (118.038, -19), (0, -19)]
    doc = ezdxf.new(); m = doc.modelspace()
    draw_poly_as_lines(m, points, 'Painéis')
    before = [(tuple(e.dxf.start), tuple(e.dxf.end)) for e in m]
    # Duplicate in reverse direction and a truly null line must still disappear.
    m.add_line(points[1], points[0], dxfattribs={'layer': 'Painéis'})
    m.add_line(points[2], points[2], dxfattribs={'layer': 'Painéis'})
    dedupe_panel_lines(m, layer='Painéis')
    assert [(tuple(e.dxf.start), tuple(e.dxf.end)) for e in m] == before
    outlines = list(polygonize(unary_union([
        LineString([tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]) for e in m])))
    assert len(outlines) == 1
    assert outlines[0].symmetric_difference(Polygon(points)).area == 0


def test_nearby_distinct_edges_are_not_duplicates():
    doc = ezdxf.new(); m = doc.modelspace()
    m.add_line((0, 0), (100, 0), dxfattribs={'layer': 'Painéis'})
    m.add_line((0, .017), (100, .017), dxfattribs={'layer': 'Painéis'})
    dedupe_panel_lines(m, layer='Painéis')
    assert len(m) == 2
