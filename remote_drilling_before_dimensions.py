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


def defaults():
    return {
        'enabled': False,
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
        for x_rel in stations.get(fid, []):
            for y_rel in rows(height, group):
                point = Point(face['x'] + x_rel, face['bottom'] + y_rel)
                if not usable.covers(point): continue
                entity = layout.add_circle((point.x, point.y), radius, dxfattribs={'layer': 'COTAS FURACAO'})
                entity.set_xdata(APPID, [(1000, fid), (1040, x_rel), (1040, y_rel)])
                entity.set_xdata('DRAWING_ROLE', [(1000, 'cd' if fid in 'CD' else 'abefgh'), (1000, 'geometry'), (1000, 'furacao')])
                count += 1
    return count


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
            function = namespace[name]
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
