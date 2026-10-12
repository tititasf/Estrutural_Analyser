"""FV iNi presentation measured from the registered FUNDOS INI original.

The certified generator remains responsible for fabrication geometry and cotas.
"""
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Matrix44
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union


def finish(doc):
    m = doc.modelspace()
    if getattr(doc, '_ini_fv_finished', False):
        return
    edges = []
    for e in m:
        if e.dxf.layer.casefold() not in ('painéis', 'paineis'):
            continue
        if e.dxftype() == 'LINE':
            edges.append(LineString([tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]))
        elif e.dxftype() == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in e.get_points()]
            if e.closed:
                pts.append(pts[0])
            edges.extend(LineString([a, b]) for a, b in zip(pts, pts[1:]))
    panels = sorted(polygonize(unary_union(edges)), key=lambda p: (-round(p.bounds[3], 3), p.bounds[0]))
    if not panels:
        raise ValueError('FV iNi requires closed panel geometry')
    outline = unary_union(panels)
    groups = list(outline.geoms) if hasattr(outline, 'geoms') else [outline]
    for name, color in [('Sarrafo de pressão', 1), ('NUMERACAO_FV_INI', 1), ('APOIOS_FV_INI', 4)]:
        if name not in doc.layers:
            doc.layers.new(name, dxfattribs={'color': color})
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.new('HIDDEN', dxfattribs={'description': 'Hidden', 'pattern': [9.525, 6.35, -3.175]})
    doc.layers.get('Sarrafo de pressão').dxf.linetype = 'HIDDEN'
    for e in list(m):
        layer = e.dxf.layer.casefold()
        if layer.startswith(('sarr_', 'sarrafo_', 'sarrafo de press')):
            m.delete_entity(e)
    # Native pressure battens: 30 cm at either edge, 20 cm in the middle.
    # Terminal edges are obtained from the formwork outline, including L returns.
    for group in groups:
        xy = list(group.exterior.coords)
        xmin, ymin, xmax, ymax = group.bounds
        terminals = []
        for a, b in zip(xy, xy[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = (dx * dx + dy * dy) ** .5
            if length < .1:
                continue
            vertical_end = abs(dx) < 1e-6 and (abs(a[0]-xmin)<1e-6 or abs(a[0]-xmax)<1e-6)
            top_return = abs(dy) < 1e-6 and abs(a[1]-ymax)<1e-6 and length < (xmax-xmin) / 2
            if not (vertical_end or top_return):
                continue
            # Reject long vertical sides of an L return; only its narrow end owns a batten.
            widths = [min(p.bounds[2]-p.bounds[0], p.bounds[3]-p.bounds[1]) for p in panels if p.intersects(group)]
            if length > max(widths) + .1:
                continue
            terminals.append((a, b, length))
        for a, b, length in terminals:
            tx, ty = (b[0]-a[0])/length, (b[1]-a[1])/length
            nx, ny = -ty, tx
            mid = ((a[0]+b[0])/2, (a[1]+b[1])/2)
            if not group.contains(Point(mid[0]+nx*.01, mid[1]+ny*.01)):
                nx, ny = -nx, -ny
            def pt(along, depth):
                return (a[0]+tx*along+nx*depth, a[1]+ty*along+ny*depth)
            band = min(7., length/2)
            for lo, hi, depth in [(0, band, 30), (length-band, length, 30), (band, length-band, 20)]:
                if hi-lo < .1:
                    continue
                m.add_lwpolyline([pt(lo, depth), pt(lo, 0), pt(hi, 0), pt(hi, depth)],
                                close=(lo == band), dxfattribs={'layer': 'Sarrafo de pressão', 'ltscale': 1})
    for i, panel in enumerate(panels, 1):
        c = panel.centroid
        if not panel.contains(c):
            c = panel.representative_point()
        m.add_circle((c.x, c.y), 7, dxfattribs={'layer': 'NUMERACAO_FV_INI', 'color': 1})
        m.add_text(str(i), dxfattribs={'height': 8, 'layer': 'NUMERACAO_FV_INI', 'color': 7}).set_placement(
            (c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)
    for e in m.query('DIMENSION'):
        if abs(e.dxf.get('angle', 0) % 180 - 90) < .01:
            a, b = e.dxf.defpoint2, e.dxf.defpoint3
            containing = min(groups, key=lambda p: p.distance(LineString([tuple(a)[:2], tuple(b)[:2]])))
            dx = containing.bounds[0]-18-e.dxf.defpoint.x
            e.transform(Matrix44.translate(dx, 0, 0))
            # Keep the measured endpoints on the actual formwork.
            e.dxf.defpoint2, e.dxf.defpoint3 = a, b
        override = e.override()
        override.update({'dimclrd': 4, 'dimclre': 4, 'dimclrt': 240})
        override.render()
    for e in m.query('TEXT'):
        if e.dxf.layer.casefold() not in ('5', 'divisao'):
            continue
        x, y, _ = e.dxf.insert
        group = min(groups, key=lambda p: p.distance(Point(x, y)))
        left, bottom, right, top = group.bounds
        edge = left if abs(x-left) < abs(x-right) else right
        e.dxf.layer = 'APOIOS_FV_INI'
        e.dxf.color = 4
        e.dxf.height = 8
        e.dxf.rotation = 90
        e.set_placement((edge-6 if edge == left else edge+6, bottom-17), align=TextEntityAlignment.MIDDLE_CENTER)
    for e in m:
        if e.dxf.layer.casefold() in ('painéis', 'paineis'):
            e.dxf.color = 7
            e.dxf.discard('true_color')
    for layer in doc.layers:
        if layer.dxf.name.casefold() in ('painéis', 'paineis'):
            layer.dxf.color = 7
    doc.header['$INSUNITS'] = 5
    doc._ini_fv_finished = True
