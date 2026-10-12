"""Optional panel drilling, projected from the emitted CIMA bolt geometry.

Legacy supplies only the configurable vertical cadence. Panel boundaries and
horizontal stations come from the current drawing, never from legacy spacing.
The drawing algorithms themselves are not changed.
"""
from __future__ import annotations

from copy import deepcopy
import functools
import inspect
import math
import sys

APPID = 'PL_PANEL_DRILLING'


def defaults(mode=None):
    return {
        'enabled': str(mode).upper() == 'NOVA',
        'faces': {face: True for face in 'ABCDEFGH'},
        'diameter_cm': 1.6,
        'edge_clearance_cm': 0.8,
        'ab': {'first_cm': 30.0, 'top_clearance_cm': 25.0,
               'steps_cm': [50.0] + [55.0] * 8},
        'cdefgh': {'first_cm': 30.0, 'top_clearance_cm': 25.0,
                   'steps_cm': [50.0] + [55.0] * 8},
    }


def validate(value):
    base = defaults()
    if not isinstance(value, dict) or set(value) != set(base):
        raise ValueError('Campos de furação inválidos')
    if type(value['enabled']) is not bool:
        raise ValueError('Ativação de furação inválida')
    if not isinstance(value['faces'], dict) or set(value['faces']) != set(base['faces']) or any(type(v) is not bool for v in value['faces'].values()):
        raise ValueError('Faces de furação inválidas')
    def number(v, low, high):
        return type(v) in (int, float) and math.isfinite(v) and low <= v <= high
    if not number(value['diameter_cm'], .1, 10) or not number(value['edge_clearance_cm'], 0, 100):
        raise ValueError('Diâmetro / afastamento da furação inválido')
    for key in ('ab', 'cdefgh'):
        group = value[key]
        if not isinstance(group, dict) or set(group) != set(base[key]):
            raise ValueError('Distribuição vertical de furação inválida')
        if not number(group['first_cm'], 0, 1000) or not number(group['top_clearance_cm'], 0, 1000):
            raise ValueError('Distância da base / topo inválida')
        if not isinstance(group['steps_cm'], list) or len(group['steps_cm']) != 9 or any(not number(v, 1, 1000) for v in group['steps_cm']):
            raise ValueError('Informe nove intervalos de furação entre 1 e 1000 cm')


def rows(height, group):
    """Bottom-up cumulative legacy cadence; repeat the last step above row 10.

    Clip actual positions to the usable height. Top clearance is an independent
    safety setting; legacy's count formula is not a reliable top clearance.
    """
    result, y, i = [], float(group['first_cm']), 0
    stop = float(height) - float(group['top_clearance_cm'])
    while y <= stop + 1e-7:
        result.append(round(y, 6))
        y += group['steps_cm'][min(i, 8)]
        i += 1
    return result


class Recorder:
    """Observe coordinates while the existing generator draws them."""
    def __init__(self, layout, panels=False):
        self.layout, self.doc, self.panels = layout, layout.doc, panels
        self.faces, self.bolts = {}, {}

    def __iter__(self): return iter(self.layout)
    def __len__(self): return len(self.layout)

    def __getattr__(self, name):
        original = getattr(self.layout, name)
        if name not in {'add_line', 'add_lwpolyline'}:
            return original
        def create(*args, **kwargs):
            entity = original(*args, **kwargs)
            frame = sys._getframe(1)
            frames = []
            try:
                for _ in range(24):
                    if frame is None: break
                    frames.append(frame)
                    frame = frame.f_back
                if self.panels and entity.dxf.layer.casefold() in {'painéis', 'paineis'}:
                    source = next((f.f_locals for f in frames if f.f_code.co_name in {'draw_abcd', 'draw_efgh'}), None)
                    if source and source.get('fid') in tuple('ABCDEFGH'):
                        fid = source['fid']
                        face = self.faces.setdefault(fid, {'x': source['x_left'], 'width': source['larg_total'], 'bottom': source['y_bot'], 'entities': []})
                        face['entities'].append(entity)
                        face['openings'] = deepcopy(source.get('_aberturas', []))
                elif not self.panels and entity.dxf.layer.casefold() == 'hachura':
                    strip = next((f.f_locals for f in frames if f.f_code.co_name == '_draw_face_strip'), None)
                    rect = next((f.f_locals for f in frames if f.f_code.co_name == '_rect'), None)
                    bolt = next((f.f_locals for f in frames if f.f_code.co_name == '_bolt_pline'), None)
                    if strip and rect:
                        fid = {'haste_ext': 'A', 'haste_int': 'B', 'ramo_ext': 'E', 'ramo_int': 'F'}.get(strip.get('arm_id'))
                        if fid:
                            # The emitted bolt rectangle is one cm wide; read its axis.
                            self.bolts.setdefault(fid, set()).add(round(float(rect['u0']) + .5, 6))
                    elif bolt:
                        self.bolts.setdefault('_common', set()).add(round(float(bolt['bx']), 6))
            finally:
                frames.clear()
                del frame
            return entity
        return create


def top_stations(namespace, pj, mode):
    """Use the very same CIMA function with a disposable DXF, before 2x scaling."""
    prepared = namespace['_prepare_pj_for_visual'](deepcopy(pj), mode)
    if str(mode).upper() == 'NOVA':
        from src.core.pillar_nova_design import special_payload
        payload = special_payload(prepared)
        if payload:
            from src.core.pillar_nova_special import Drawing, dot
            drawing = Drawing(payload)
            drawing.generate()
            # The elevation contract names the vertical arm A/B and the
            # horizontal arm E/F. Project actual rod intersections onto those
            # walls, including the sheet extension at each panel origin.
            from shapely.geometry import LineString
            result = {}
            for index, fid, offset in ((5, 'A', 11), (3, 'B', 0),
                                       (0, 'E', 0), (2, 'F', 0)):
                face = drawing.faces[index]
                p, u, length = face['p'], face['u'], face['length']
                wall = LineString([p, drawing.point(face, length, 0)])
                values = set()
                for rod in drawing.rod_axes:
                    hit = rod.intersection(wall)
                    if hit.geom_type == 'Point':
                        values.add(round(dot((hit.x-p[0], hit.y-p[1]), u)+offset, 6))
                result[fid] = sorted(values)
            return result
    comp, larg = namespace['_dimensoes_canonicas_pilar'](prepared)
    from src.core.cima_l_contract import secao_l_do_payload
    section = secao_l_do_payload(prepared)
    if section:
        comp, larg = float(section['externa_y']), float(section['externa_x'])
    doc = namespace['setup_doc']()
    record = Recorder(doc.modelspace())
    namespace['draw_cima'](record, 0, 0, comp, larg, float(prepared.get('grade_1', 0)), prepared.get('nome', '?'), prepared)
    stations = {fid: sorted(values) for fid, values in record.bolts.items() if fid != '_common'}
    if '_common' in record.bolts:
        # Elevation A/B use concrete + 11 cm at each edge, B mirrors A.
        a = sorted(round(x + comp / 2 + 11, 6) for x in record.bolts['_common'])
        stations['A'] = a
        stations['B'] = sorted(round(comp + 22 - x, 6) for x in a)
    return stations


def panel_regions(entities):
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union
    lines = []
    for e in entities:
        points = ([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
                  if e.dxftype() == 'LINE' else [(p[0], p[1]) for p in e.get_points()])
        if e.dxftype() == 'LWPOLYLINE' and e.closed: points.append(points[0])
        lines.extend(LineString([a, b]) for a, b in zip(points, points[1:]) if a != b)
    return list(polygonize(unary_union(lines))) if lines else []


def add_drilling(layout, faces, stations, options):
    from shapely.geometry import Point
    doc, count = layout.doc, 0
    if APPID not in doc.appids: doc.appids.new(APPID)
    if 'DRAWING_ROLE' not in doc.appids: doc.appids.new('DRAWING_ROLE')
    if 'COTAS FURACAO' not in doc.layers:
        doc.layers.new('COTAS FURACAO', dxfattribs={'color': 16})
    radius = options['diameter_cm'] / 2
    margin = max(radius, options['edge_clearance_cm'])
    for fid, face in faces.items():
        if not options['faces'][fid]: continue
        regions = panel_regions(face['entities'])
        if not regions: continue  # no closed panel: do not invent drillable material
        from shapely.ops import unary_union
        material = unary_union(regions)
        from shapely.geometry import box
        for opening in face.get('openings', []):
            left, right = face['x'], face['x'] + face['width']
            if opening['lado'] == 'meio':
                left, right = opening['x_inn_l'], opening['x_inn_r']
            elif opening['lado'] == 'esquerdo':
                right = left + opening['larg']
            elif opening['lado'] == 'direito':
                left = right - opening['larg']
            else:
                continue
            material = material.difference(box(left, opening['y_bot'], right, opening['y_top']))
        if material.is_empty: continue
        height = material.bounds[3] - face['bottom']
        usable = material.buffer(-margin)
        group = options['ab' if fid in 'AB' else 'cdefgh']
        placed = {}
        for x_rel in stations.get(fid, []):
            for y_rel in rows(height, group):
                point = Point(face['x'] + x_rel, face['bottom'] + y_rel)
                if not usable.covers(point): continue
                entity = layout.add_circle((point.x, point.y), radius, dxfattribs={'layer': 'COTAS FURACAO', 'color': 2})
                entity.set_xdata(APPID, [(1000, fid), (1040, x_rel), (1040, y_rel)])
                entity.set_xdata('DRAWING_ROLE', [(1000, 'cd' if fid in 'CD' else 'abefgh'), (1000, 'geometry'), (1000, 'furacao')])
                # The uploaded index uses a 15 cm yellow crosshair. This is a
                # drawing symbol; the circle retains the configured bore diameter.
                for a, b in (((point.x - 7.5, point.y), (point.x + 7.5, point.y)),
                             ((point.x, point.y - 7.5), (point.x, point.y + 7.5))):
                    cross = layout.add_line(a, b, dxfattribs={'layer': 'COTAS FURACAO', 'color': 2})
                    cross.set_xdata('DRAWING_ROLE', [(1000, 'cd' if fid in 'CD' else 'abefgh'), (1000, 'geometry'), (1000, 'furacao')])
                placed.setdefault(point.x, []).append(point.y)
                count += 1
        if placed:
            _dimension_drilling(layout, fid, face, placed)
    return count


def _dimension_drilling(layout, fid, face, placed):
    """Dimension emitted holes, including real gaps caused by openings.

    A single vertical chain keeps multi-column panels readable; its column is
    the one with the most holes. Horizontal chains locate every drilled axis
    relative to both panel edges. No dimension is inferred from rejected holes.
    """
    attrs = {'layer': 'COTAS FURACAO'}
    overrides = {'dimclrd': 4, 'dimclre': 4, 'dimclrt': 10,
                 'dimtxt': 10, 'dimasz': 2, 'dimgap': 2.5, 'dimtad': 1,
                 'dimexo': 0, 'dimexe': 1, 'dimdec': 2, 'dimzin': 8}
    style = 'PAINEL-NOVA' if 'PAINEL-NOVA' in layout.doc.dimstyles else 'Standard'
    def dimension(p1, p2, base, angle):
        dim = layout.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle,
                                    dimstyle=style, override=overrides,
                                    dxfattribs=attrs)
        dim.dimension.set_xdata('DRAWING_ROLE', [
            (1000, 'cd' if fid in 'CD' else 'abefgh'),
            (1000, 'dimensions'), (1000, 'furacao')])
        dim.render()
    axis = max(placed, key=lambda x: (len(placed[x]), x))
    levels = [face['bottom']] + sorted(set(placed[axis]))
    # Reference index places the vertical chain just beside the drilling axis.
    for y0, y1 in zip(levels, levels[1:]):
        dimension((axis, y0), (axis, y1), (axis + 20, (y0 + y1) / 2), 90)
    xs = [face['x']] + sorted(placed) + [face['x'] + face['width']]
    bottom = face['bottom']
    # Keep the drilling chain inside the total-width dimension. Match the
    # actual total span rather than moving unrelated bottom dimensions.
    chain_y = bottom - 43
    for total in list(layout.query('DIMENSION')):
        if total.dxf.layer == 'COTAS FURACAO':
            continue
        a, b = total.dxf.defpoint2, total.dxf.defpoint3
        if (abs(a.y - bottom) < 1e-6 and abs(b.y - bottom) < 1e-6
                and abs(min(a.x, b.x) - face['x']) < 1e-6
                and abs(max(a.x, b.x) - face['x'] - face['width']) < 1e-6
                and total.dxf.defpoint.y < bottom):
            chain_y = total.dxf.defpoint.y
            total.dxf.defpoint = (total.dxf.defpoint.x, bottom - 70, 0)
            total.override().render()
    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 > 1e-7:
            dimension((x0, bottom), (x1, bottom),
                      ((x0 + x1) / 2, chain_y), 0)


def install(namespace, mode, options):
    """Scoped hooks for elevation drawing; restore entry points on exit."""
    from contextlib import contextmanager
    @contextmanager
    def scope():
        if not options['enabled']:
            yield
            return
        originals = {}
        for name in ('draw_abcd', 'draw_efgh'):
            if name not in namespace:
                continue
            function = namespace[name]
            if getattr(function, '_native_panel_drilling', False):
                continue
            signature = inspect.signature(function)
            @functools.wraps(function)
            def wrapped(*args, __f=function, __sig=signature, **kwargs):
                bound = __sig.bind(*args, **kwargs)
                record = Recorder(bound.arguments['msp'], panels=True)
                bound.arguments['msp'] = record
                result = __f(*bound.args, **bound.kwargs)
                if result < 0: return result
                stations = top_stations(namespace, bound.arguments['pj'], mode)
                return result + add_drilling(record.layout, record.faces, stations, options)
            originals[name] = function
            namespace[name] = wrapped
        try: yield
        finally: namespace.update(originals)
    return scope()
