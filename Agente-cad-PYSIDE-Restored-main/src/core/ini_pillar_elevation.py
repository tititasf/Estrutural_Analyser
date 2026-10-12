"""Approved iNi panel drilling, levels and panel annotations."""
import math
from ezdxf import bbox
from ezdxf.addons import Importer
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from scripts.pl_panel_drilling import defaults,rows,APPID
from .ini_pillar_top import symbols,hole_stations
from .n5_ini_frames import normalize_resources

def add_drilling(d,payload,namespace):
    drilling=defaults("INI")
    for key in ("ab","cdefgh"):drilling[key]["steps_cm"]=[50,55,55,60,55,55,55,55,55]
    m = d.modelspace()
    if 'INI-FURACAO' not in d.layers:
        d.layers.new('INI-FURACAO', dxfattribs={'color': 3})
    if APPID not in d.appids:
        d.appids.new(APPID)
    from shapely.geometry import box, Polygon, Point
    from shapely.ops import unary_union
    stations=hole_stations(payload,namespace)
    names = sorted([e for e in m.query('TEXT') if e.dxf.layer == 'NOMENCLATURA' and '.' in e.dxf.text], key=lambda e: e.dxf.insert.x)
    voids = []
    for e in m.query('HATCH'):
        for path in e.paths:
            if hasattr(path, 'vertices'):
                voids.append(Polygon([(v[0], v[1]) for v in path.vertices]))
    levels = bbox.extents([e for e in m if e.dxf.layer.casefold() in ('nível', 'pedireito')])
    yb = levels.extmin.y
    for i, name in enumerate(names):
        fid = name.dxf.text.split('.')[-1]
        right = names[i + 1].dxf.insert.x if i + 1 < len(names) else float('inf')
        edges = []
        for edge in m:
            if edge.dxf.layer.casefold() not in ('painéis', 'paineis', 'hachura-chapa'):
                continue
            b = bbox.extents([edge])
            if b.has_data and b.extmin.x >= name.dxf.insert.x - 1e-06 and (b.extmax.x < right):
                edges.append(edge)
        b = bbox.extents(edges)
        if not b.has_data:
            continue
        xl, xr, yt = (b.extmin.x, b.extmax.x, b.extmax.y)
        material = box(xl, yb + float(payload.get(f'h1_{fid}', 2)), xr, yt).difference(unary_union(voids))
        placed = {}
        for relative_x in stations.get(fid, []):
            for relative_y in rows(yt - yb, drilling['ab' if fid in 'AB' else 'cdefgh']):
                x, y = (xl + relative_x, yb + relative_y)
                if not material.buffer(-0.8).covers(Point(x, y)):
                    continue
                c = m.add_circle((x, y), 5.660389519995078, dxfattribs={'layer': 'INI-FURACAO', 'color': 3})
                c.set_xdata(APPID, [(1000, fid), (1040, relative_x), (1040, relative_y)])
                for a, z in [((x - 5.66038952, y), (x + 5.66038952, y)), ((x, y - 5.66038952), (x, y + 5.66038952))]:
                    m.add_line(a, z, dxfattribs={'layer': 'INI-FURACAO', 'color': 3})
                placed.setdefault(x, []).append(y)
        if not placed:
            continue
    
        def dimension(a, b, base, angle):
            v = m.add_linear_dim(base=base, p1=a, p2=b, angle=angle, dxfattribs={'layer': 'COTAS FURACAO'}, override={'dimclrd': 4, 'dimclre': 4, 'dimclrt': 240, 'dimtxt': 10, 'dimasz': 3, 'dimblk': '_Oblique', 'dimexo': 0, 'dimexe': 3, 'dimgap': 3, 'dimtad': 1, 'dimdec': 1, 'dimzin': 8})
            v.render()
        axis = min(placed)
        ys = [yb + float(payload.get(f'h1_{fid}', 2))] + sorted(placed[axis])
        for a, z in zip(ys, ys[1:]):
            dimension((axis, a), (axis, z), (axis - 13, (a + z) / 2), 90)
        xs = [xl] + sorted(placed) + [xr]
        for a, z in zip(xs, xs[1:]):
            dimension((a, yb + 80), (z, yb + 80), ((a + z) / 2, yb + 80), 0)
    for e in m:
        if e.dxftype() == 'CIRCLE' and e.has_xdata('PL_PANEL_DRILLING'):
            e.dxf.radius = 5.660389519995078
            e.dxf.layer = 'INI-FURACAO'
            e.dxf.color = 3
        elif e.dxftype() == 'LINE' and e.dxf.layer == 'COTAS FURACAO':
            center = (e.dxf.start + e.dxf.end) / 2
            direction = (e.dxf.end - e.dxf.start).normalize(5.660389519995078)
            e.dxf.start = center - direction
            e.dxf.end = center + direction
            e.dxf.layer = 'INI-FURACAO'
            e.dxf.color = 3
        elif e.dxftype() == 'HATCH':
            e.dxf.layer = 'CONCRETO'
            e.set_pattern_fill('AR-CONC', scale=0.1, angle=0, color=251)
            e.dxf.associative = 0
            e.dxf.discard('pixel_size')
            for path in e.paths:
                path.source_boundary_objects = []
                path.path_type_flags &= ~4

def native_annotations(d):
    m=d.modelspace()
    old_level_texts=sorted([e for e in m.query('TEXT') if e.dxf.layer=='Texto Nível' and e.dxf.text.replace(',','').replace('.','').isdigit()],key=lambda e:e.dxf.insert.y)
    level_labels=[e.dxf.text for e in old_level_texts]
    floor_labels=[e.dxf.text for e in m.query('TEXT') if e.dxf.layer=='Texto Nível' and e not in old_level_texts]
    removed={}
    for e in list(m):
        reason=None
        if e.dxf.layer in ('FORMASCIA-FOLGA','S1','Texto Nível'):reason=e.dxf.layer
        elif e.dxftype()=='MLINE' and e.dxf.style_name=='SAR15':reason='C/D sarrafos'
        if reason:
            removed[reason]=removed.get(reason,0)+1;m.delete_entity(e)
    # Copy the actual original arrow, including its ANSI31 hatch and yellow edges.
    imp=Importer(symbols(),d);imp.import_block('NIVEL');imp.import_table('styles',entries=['R8']);imp.finalize()
    arrow=d.blocks['NIVEL']
    bar=next(e for e in arrow.query('LINE') if abs(e.dxf.start.y-e.dxf.end.y)<1e-5)
    stem=next(e for e in arrow.query('LINE') if abs(e.dxf.start.x-e.dxf.end.x)<1e-5)
    ox,oy=stem.dxf.start.x,bar.dxf.start.y
    for e in arrow:
        e.translate(-ox,-oy,0);e.dxf.color=2
    level_edges=[e for e in m if e.dxf.layer.casefold()=='pedireito']
    levels=sorted({round(v[1],6) for e in level_edges for v in e.get_points()})
    minx=min(v[0] for e in level_edges for v in e.get_points())
    arrowx=minx+12
    for y,label in zip(levels,level_labels):
        m.add_blockref('NIVEL',(arrowx,y),dxfattribs={'layer':'pedireito','color':2})
        m.add_text(label,dxfattribs={'layer':'pedireito','color':4,'height':8,'style':'R8','insert':(arrowx+16,y+2.2)})
    for i,label in enumerate(floor_labels):
        m.add_text(label,dxfattribs={'layer':'pedireito','color':4,'height':8,'style':'R8','insert':(arrowx+16,levels[0]+15+12*i)})
    # Derive face B extents from its actual emitted panel geometry.
    names=sorted([e for e in m.query('TEXT') if e.dxf.layer=='NOMENCLATURA' and '.' in e.dxf.text],key=lambda e:e.dxf.insert.x)
    ib=next((i for i,e in enumerate(names) if e.dxf.text.endswith('.B')),None)
    if ib is None:return
    lo=names[ib].dxf.insert.x;hi=names[ib+1].dxf.insert.x
    edges=[e for e in m if e.dxf.layer=='hachura-chapa' and (b:=bbox.extents([e])).has_data and b.extmin.x>=lo-1e-6 and b.extmax.x<hi]
    b=bbox.extents(edges);xl,xr,yt=b.extmin.x,b.extmax.x,b.extmax.y
    aligned=[]
    for dim in m.query('DIMENSION'):
        if dim.dxf.layer=='COTAS FURACAO':continue
        a,z=dim.dxf.defpoint2,dim.dxf.defpoint3
        ov=dim.override()
        if abs(dim.dxf.angle-90)<1e-6 and abs(a.x-xr)<1e-6 and abs(z.x-xr)<1e-6 and dim.dxf.defpoint.x>=xr+30:
            before=tuple(dim.dxf.defpoint)
            column=xr+40
            dim.dxf.defpoint=(column,dim.dxf.defpoint.y,0)
            ov.set_location((column-8,(a.y+z.y)/2),leader=False,relative=False)
            if abs(z.y-a.y)<20:ov.update({'dimtxt':4})
            ov.render();aligned.append({'before':before,'after':tuple(dim.dxf.defpoint),'value_cm':abs(z.y-a.y)})
        elif abs(dim.dxf.angle)<1e-6 and abs(a.y-yt)<1e-6 and abs(z.y-yt)<1e-6 and xl-1e-6<=a.x<=xr and xl-1e-6<=z.x<=xr:
            ov.set_location(((a.x+z.x)/2,yt+27),leader=False,relative=False);ov.render()

def refine(d, pj):
    m = d.modelspace()
    records = []
    for e in list(m.query('TEXT')):
        if 'sar' in e.dxf.text.casefold():
            m.delete_entity(e)
    level_lines = [e for e in m.query('LWPOLYLINE') if e.dxf.layer.casefold() == 'pedireito']
    ys = sorted({v[1] for e in level_lines for v in e.get_points()})
    yb, yt = (ys[0], ys[-1])
    block = d.blocks['NIVEL']
    triangle = next(iter(block.query('LWPOLYLINE')))
    tip = min((v[1] for v in triangle.get_points()))
    for e in m.query('INSERT'):
        if e.dxf.name == 'NIVEL':
            e.dxf.insert = (e.dxf.insert.x, e.dxf.insert.y - tip, e.dxf.insert.z)
    for e in list(m.query('TEXT')):
        if e.dxf.layer.casefold() != 'pedireito':
            continue
        try:
            value = float(e.dxf.text.replace(',', '.'))
        except ValueError:
            m.delete_entity(e)
            continue
        e.dxf.text = f'{value:.2f}'.replace('.', ',')
        e.dxf.insert = (e.dxf.insert.x, e.dxf.insert.y - tip, e.dxf.insert.z)
    voids = []
    for h in m.query('HATCH'):
        if h.dxf.layer != 'CONCRETO':
            continue
        for path in h.paths:
            if hasattr(path, 'vertices'):
                voids.append(Polygon([(v[0], v[1]) for v in path.vertices]))
    obstacles = unary_union(voids)
    circles = list(m.query('CIRCLE'))
    removed = []
    for e in circles:
        if not e.has_xdata('PL_PANEL_DRILLING'):
            continue
        point = Point(e.dxf.center.x, e.dxf.center.y)
        dv = point.distance(obstacles) if not obstacles.is_empty else float('inf')
        dt = yt - point.y
        if min(dv, dt) < 15 - 1e-07:
            center = e.dxf.center
            for line in list(m.query('LINE')):
                if line.dxf.layer == 'INI-FURACAO' and ((line.dxf.start + line.dxf.end) / 2 - center).magnitude < 1e-06:
                    m.delete_entity(line)
            removed.append({'center': tuple(center), 'void_distance_cm': dv, 'top_distance_cm': dt})
            m.delete_entity(e)
    for e in list(m.query('DIMENSION')):
        if e.dxf.layer == 'COTAS FURACAO':
            m.delete_entity(e)
    names = sorted([e for e in m.query('TEXT') if e.dxf.layer == 'NOMENCLATURA' and '.' in e.dxf.text], key=lambda e: e.dxf.insert.x)
    if 'INI-SAR-QUANTIDADE' not in d.layers:
        d.layers.new('INI-SAR-QUANTIDADE', dxfattribs={'color': 4})

    def dim(a, z, base, angle):
        v = m.add_linear_dim(base=base, p1=a, p2=z, angle=angle, dxfattribs={'layer': 'COTAS FURACAO'}, override={'dimclrd': 4, 'dimclre': 4, 'dimclrt': 240, 'dimtxt': 10, 'dimasz': 3, 'dimblk': '_Oblique', 'dimexo': 0, 'dimexe': 3, 'dimgap': 3, 'dimtad': 1, 'dimdec': 1, 'dimzin': 8})
        v.render()
    for i, name in enumerate(names):
        fid = name.dxf.text.split('.')[-1]
        lo = name.dxf.insert.x
        hi = names[i + 1].dxf.insert.x if i + 1 < len(names) else float('inf')
        edges = [e for e in m if e.dxf.layer == 'hachura-chapa' and (b := bbox.extents([e])).has_data and (b.extmin.x >= lo - 1e-06) and (b.extmax.x < hi)]
        b = bbox.extents(edges)
        if not b.has_data:
            continue
        xl, xr = (b.extmin.x, b.extmax.x)
        width = xr - xl
        placed = {}
        for e in m.query('CIRCLE'):
            if e.has_xdata('PL_PANEL_DRILLING') and xl - 1e-06 <= e.dxf.center.x <= xr + 1e-06:
                placed.setdefault(e.dxf.center.x, []).append(e.dxf.center.y)
        if placed:
            axis = min(placed)
            chain = [yb + float(pj.get(f'h1_{fid}', 2))] + sorted(placed[axis])
            for a, z in zip(chain, chain[1:]):
                dim((axis, a), (axis, z), (axis - 13, (a + z) / 2), 90)
            chain = [xl] + sorted(placed) + [xr]
            for a, z in zip(chain, chain[1:]):
                dim((a, yb + 80), (z, yb + 80), ((a + z) / 2, yb + 80), 0)
        qualifying = fid in 'ABEFGH' and width > 244 + 1e-06 or (fid in 'CD' and width >= 30 - 1e-06)
        if not qualifying:
            continue
        level = yb + float(pj.get(f'h1_{fid}', 2))
        boundaries = [level]
        limit = 122 if fid in 'ABEFGH' else 244
        for height in pj.get(f'paineis_intervals_{fid}', []):
            remaining = float(height)
            while remaining > 1e-06:
                step = min(limit, remaining)
                level = min(level + step, b.extmax.y)
                boundaries.append(level)
                remaining -= step
        if boundaries[-1] < b.extmax.y - 1e-06:
            boundaries.append(b.extmax.y)
        cap = float(pj.get(f'rebaixo_laje_{fid}', 0) or 0)
        slab = float(pj.get(f'vazio_laje_{fid}', 0) or 0)
        if cap > 0 and slab > 0:
            boundaries.append(b.extmax.y - cap)
        boundaries = sorted(set(boundaries))
        circles = [e for e in m.query('CIRCLE') if e.dxf.layer == 'NUMERACAO_PAINEIS' and xl <= e.dxf.center.x <= xr]
        used = set()
        for circle in circles:
            center = circle.dxf.center.y
            lower = max((y for y in boundaries if y < center), default=boundaries[0])
            upper = min((y for y in boundaries if y > center), default=boundaries[-1])
            key = (round(lower, 6), round(upper, 6))
            if key in used:
                continue
            used.add(key)
            height = upper - lower
            count = int(math.floor(height / 30 + 0.5))
            if count < 1:
                continue
            dims = [e for e in m.query('DIMENSION') if e.dxf.layer != 'COTAS FURACAO' and abs(e.dxf.angle - 90) < 1e-06 and (abs(e.dxf.defpoint2.x - xr) < 1e-06) and (abs(e.dxf.defpoint3.x - xr) < 1e-06) and (min(e.dxf.defpoint2.y, e.dxf.defpoint3.y) >= lower - 1e-06) and (max(e.dxf.defpoint2.y, e.dxf.defpoint3.y) <= upper + 1e-06)]
            column = max((e.dxf.defpoint.x for e in dims), default=xr + 40)
            m.add_text(f'{count} sar.', dxfattribs={'layer': 'INI-SAR-QUANTIDADE', 'color': 4, 'height': 5, 'rotation': 90, 'style': 'R8', 'insert': (column + 7, (lower + upper) / 2 - 8)})
            records.append({'face': fid, 'width_cm': width, 'panel_height_cm': height, 'count': count})
    normalize_resources(d)
    audit = d.audit()
    retained = []
    for e in m.query('CIRCLE'):
        if e.has_xdata('PL_PANEL_DRILLING'):
            point = Point(e.dxf.center.x, e.dxf.center.y)
            retained.append(min(yt - point.y, point.distance(obstacles) if not obstacles.is_empty else float('inf')))
    assert all((distance >= 15 - 1e-07 for distance in retained))
    tip_gaps = [min((abs(e.dxf.insert.y + tip - y) for y in ys)) for e in m.query('INSERT') if e.dxf.name == 'NIVEL']
    assert all((gap < 1e-06 for gap in tip_gaps))
    return {'removed_drillings': removed, 'retained_holes': len(retained), 'minimum_remaining_clearance_cm': min(retained, default=None), 'level_tip_gaps': tip_gaps, 'rounding_examples': {str(height): int(math.floor(height / 30 + 0.5)) for height in (122, 110, 100)}, 'sar_counts': records, 'errors': len(audit.errors), 'fixes': len(audit.fixes), 'engine_modified': False, 'deployed': False}
