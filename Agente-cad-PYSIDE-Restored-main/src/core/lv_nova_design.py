"""Approved NOVA drawing rules. All structural measures come from the caller's SA contract."""
from __future__ import annotations

import math
from hashlib import sha256
from pathlib import Path

import ezdxf
from ezdxf.addons import Importer
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import box, LineString
from shapely.ops import unary_union

DESIGN_VERSION = 'nova-lv-approved-20261005-v1'
ASSETS = Path(__file__).resolve().parents[2] / 'scripts/arete/assets/lv_nova'


def renderer_fingerprint():
    digest = sha256(Path(__file__).read_bytes())
    for path in sorted(ASSETS.glob('*_style.dxf')):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def panel_spans(length):
    """Preserve length; avoid a short remainder by splitting the preceding 244."""
    length = float(length)
    if not math.isfinite(length) or length <= 0:
        raise ValueError('length: positive finite measure required')
    spans, start = [], 0.
    while start < length - 1e-8:
        remaining = length - start
        width = remaining if remaining <= 244 + 1e-8 else 122 if remaining - 244 < 60 - 1e-8 else 244
        spans.append((start, min(length, start + width)))
        start += width
    return spans


def pontalete_count(start, end, openings):
    """Count useful width once, including overlaps between different openings."""
    intervals = sorted((max(start, a), min(end, b)) for a, b in openings if b > start and a < end)
    covered, last = 0., start
    for a, b in intervals:
        covered += max(0., b - max(a, last))
        last = max(last, b)
    return math.floor(max(0., end - start - covered) / 30 + .5 + 1e-10)


def _template(assembly, kind):
    if assembly not in ('gradeadas', 'sarrafeadas'):
        raise ValueError(f'Unknown LV assembly: {assembly}')
    ref = ezdxf.readfile(ASSETS / f'{assembly}_{kind}_style.dxf')
    doc = ezdxf.new('R2013')
    imp = Importer(ref, doc)
    for table in ('layers', 'styles', 'dimstyles', 'linetypes'):
        imp.import_table(table)
    if assembly == 'gradeadas' and kind == 'cut':
        imp.import_block('PRESILHA METÁLICA 1')
    imp.finalize()
    # Importer copies foreign layer handles without material/plot-style objects.
    # They can accidentally resolve to a new graphic entity after allocation.
    # Both approved styles use explicit CAD colors, not rendered materials.
    for layer in doc.layers:
        layer.dxf.discard('material_handle')
        layer.dxf.discard('plotstyle_handle')
    # Preserve real centimetres (e.g. 61.5), suppressing only trailing zeroes.
    for name in ('PAINEL', 'Cota Seção (2x)'):
        if name in doc.dimstyles:
            doc.dimstyles.get(name).dxf.dimdec = 1
            doc.dimstyles.get(name).dxf.dimzin = 8
            doc.dimstyles.get(name).dxf.dimrnd = .1
    return doc, ref


def _hatch(m, points, sample, scale=.5):
    hatch = m.add_hatch(dxfattribs={'layer': 'Hachura', 'color': 253})
    if sample.dxf.solid_fill:
        hatch.set_solid_fill(color=253)
    else:
        definition = [[line.angle, (0, 0), (line.offset.x * scale, line.offset.y * scale),
                       [v * scale for v in line.dash_length_items]] for line in sample.pattern.lines]
        hatch.set_pattern_fill(sample.dxf.pattern_name, definition=definition)
    hatch.paths.add_polyline_path(points, is_closed=True)
    return hatch


def _rect(m, x1, y1, x2, y2, layer, fill=None):
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    if fill is not None:
        _hatch(m, points, fill)
    return m.add_lwpolyline(points, close=True, dxfattribs={'layer': layer})


def _parts(geometry):
    return list(geometry.geoms) if hasattr(geometry, 'geoms') else [geometry]


def _text(m, value, x, y, height=4.8, centered=False):
    text = m.add_text(str(value), dxfattribs={'layer': 'Texto Seção', 'height': height,
                                           'insert': (x, y), 'style': 'Standard'})
    if centered:
        text.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    return text


def draw_cut(contract):
    """Return editable DXF, matching approved sections for arbitrary local profiles."""
    assembly = contract.get('assembly_variant', 'sarrafeadas')
    doc, ref = _template(assembly, 'cut')
    m = doc.modelspace()
    b, h = float(contract['width_cm']), float(contract['height_cm'])
    if not all(math.isfinite(v) and v > 0 for v in (b, h)):
        raise ValueError('width_cm/height_cm: positive finite measures required')
    inv = bool(contract.get('inverted') or
               (contract.get('beam_type') == 'inverted' and contract.get('form_role') == 'top_cap'))
    slabs = {s: sorted([(float(v['height_cm']), float(v['drop_cm']))
                        for v in contract['slabs'][s]], key=lambda v: v[1]) for s in 'AB'}
    solid = next(e for e in ref.modelspace().query('HATCH') if e.dxf.solid_fill)
    wood = next(e for e in ref.modelspace().query('HATCH') if e.dxf.pattern_name == 'ANSI31')
    style = 'Cota Seção (2x)'
    ds = doc.dimstyles.get(style)
    ds.dxf.dimlfac = 1
    for key in ('dimtxt', 'dimasz', 'dimexo', 'dimexe', 'dimgap'):
        if ds.dxf.hasattr(key):
            setattr(ds.dxf, key, getattr(ds.dxf, key) * .5)

    def measure(p1, p2, base, angle=0):
        dimension = m.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle=style,
                                    override={'dimexo': 0, 'dimexe': 1.5}, dxfattribs={'layer': 'COTA'})
        dimension.render()

    concrete, side_parts, heights = [box(0, 0, b, h)], {}, []
    for side, edge, sign in [('A', 0, -1), ('B', b, 1)]:
        base, intervals = (0 if inv else -4), []
        for index, (thickness, drop) in enumerate(slabs[side]):
            # A confirmed inverted web can meet a neighboring slab whose
            # underside is below its base. Keep that measured slab interval;
            # its upper surface still has to touch the web, as in the SA gate.
            outside = drop >= h if inv else drop + thickness > h + .5
            if thickness <= 0 or drop < 0 or outside:
                raise ValueError(f'{side}: slab outside beam profile')
            top, bottom = h - drop, h - drop - thickness
            intervals.append((bottom - 2, top))
            sx1, sx2 = sorted((edge, edge + sign * 30))
            concrete.append(box(sx1, bottom, sx2, top))
            _rect(m, sx1, bottom - 2, sx2, bottom, 'Painéis', solid)
            q, lane = edge + sign * 30, edge + sign * 55
            measure((q, bottom), (q, top), (lane, bottom), 90)
            measure((q, bottom - 2), (q, bottom), (lane, bottom - 2), 90)
            if drop and not inv:
                previous = h if index == 0 else h - slabs[side][index - 1][1] - slabs[side][index - 1][0] - 2
                if previous > top:
                    measure((edge, top), (edge, previous), (lane, top), 90)
        exposed = box(min(edge, edge + sign * 2), base, max(edge, edge + sign * 2), h)
        for low, high in intervals:
            exposed = exposed.difference(box(edge - 3, low, edge + 3, high))
        side_parts[side] = [p for p in _parts(exposed) if p.geom_type == 'Polygon' and p.area]
        top = h if inv else min((h - dr - th - 2 for th, dr in slabs[side]), default=h)
        heights.append(h - max((h - dr for th, dr in slabs[side]), default=0) if inv else top - base)
        for part in side_parts[side]:
            x1, y1, x2, y2 = part.bounds
            _rect(m, x1, y1, x2, y2, 'Painéis', solid)
            if y2 - y1 <= 7:
                continue
            if assembly == 'sarrafeadas':
                wx1, wx2 = sorted((edge + sign * 2, edge + sign * 4.2))
                count = max(2, math.ceil((y2 - y1 - 7) / 30) + 1)
                for i in range(count):
                    yy = y1 + (y2 - y1 - 7) * i / (count - 1)
                    _rect(m, wx1, yy, wx2, yy + 7, 'Madeira', wood)
            else:
                gx1, gx2 = sorted((edge + sign * 2, edge + sign * 9))
                _rect(m, gx1, y1, gx2, y2, 'Madeira')
                _rect(m, gx1, y2 - 2.2, gx2, y2, 'Madeira', wood)
                fx1, fx2 = sorted((edge + sign * 9, edge + sign * 19))
                _rect(m, fx1, y1, fx2, y1 + 2.2, 'Madeira', wood)
        if assembly == 'sarrafeadas':
            x1, x2 = sorted((edge + sign * 4.2, edge + sign * 11.2))
            post_top = h - 2.2 if inv else top - 2.2
            _rect(m, x1, base if inv else base - 38.24, x2,
                  post_top, 'SARR_3.5x7')
            _rect(m, x1, post_top, x2, post_top + 2.2, 'Madeira', wood)
        witness, lane = edge + sign * 2, edge + sign * 55
        if not inv:
            measure((witness, base), (witness, top), (lane, base), 90)
        elif intervals:
            measure((witness, max(high for low, high in intervals)), (witness, h), (lane, h), 90)

    for part in _parts(unary_union(concrete)):
        m.add_lwpolyline(list(part.exterior.coords)[:-1], close=True, dxfattribs={'layer': 'CONCRETO'})
    axes = []
    if inv:
        _rect(m, 0, h, b, h + 2, 'Painéis', solid)
        _text(m, 'c', b / 2, h + 3.5)
    else:
        _rect(m, 0, -1.8, b, 0, 'Painéis', solid)
        _rect(m, 0, -4, 7, -1.8, 'Madeira', wood)
        _rect(m, b - 7, -4, b, -1.8, 'Madeira', wood)
        if assembly == 'sarrafeadas':
            _rect(m, -11.2, -19.03, b + 11.2, -4, 'SARR_3.5x7')
        else:
            _rect(m, -35.7, -14, b + 35.7, -4, 'barrote')
            for x, sign in [(-23.4338, 1), (b + 23.4338, -1)]:
                m.add_blockref('PRESILHA METÁLICA 1', (x, -7.9833), dxfattribs={
                    'layer': 'presilha', 'xscale': sign / 3, 'yscale': 1 / 3, 'zscale': 1 / 3})
            _rect(m, -31.226, -6.2665, b + 33.426, -4.6667, 'SCO-___-LAJ').dxf.color = 1
            offset = 24.985
            while offset < min(heights) - 7:
                yy = -4 + offset
                axes.append(yy)
                m.add_line((-24, yy), (b + 24, yy), dxfattribs={'layer': 'Tensor7'})
                for edge, sign in [(0, -1), (b, 1)]:
                    for dy in (-3, 3):
                        m.add_line((edge + sign * 9, yy + dy), (edge + sign * 24, yy + dy))
                    m.add_line((edge + sign * 24, yy - 3), (edge + sign * 24, yy + 3))
                    m.add_line((edge + sign * 25, yy - 1.5), (edge + sign * 25, yy + 1.5))
                    for dy in (-1.5, 1.5):
                        m.add_line((edge + sign * 24, yy + dy), (edge + sign * 25, yy + dy))
                offset += 40
        _text(m, 'c', 5, .5)

    for side, edge, sign in [('A', 0, -1), ('B', b, 1)]:
        regions = side_parts[side]
        if not regions:
            continue
        if assembly == 'sarrafeadas':
            region = max(regions, key=lambda p: p.bounds[3] - p.bounds[1])
            y = (region.bounds[1] + region.bounds[3]) / 2
            x = edge + sign * 7.7
        else:
            free = []
            for region in regions:
                lo, hi = region.bounds[1] + 7, region.bounds[3] - 7
                if hi <= lo:
                    continue
                space = box(0, lo, 1, hi)
                for yy in axes:
                    space = space.difference(box(-1, yy - 6, 2, yy + 6))
                free.extend(p for p in _parts(space) if p.geom_type == 'Polygon' and p.area)
            if free:
                region = max(free, key=lambda p: p.area)
                y = (region.bounds[1] + region.bounds[3]) / 2
            else:
                region = max(regions, key=lambda p: p.area)
                y = (region.bounds[1] + region.bounds[3]) / 2
            x = edge + sign * 5.5
        _text(m, side.lower(), x, y, centered=True)

    measure((0, 0 if inv else -4), (b, 0 if inv else -4), (0, -32))
    for value, x, y, rotation in [(b, b / 2, 6, 0), (h, b - 5.5, h / 2, 90)]:
        text = m.add_text(f'{value:g}', dxfattribs={'height': 3.5, 'color': 1, 'rotation': rotation})
        text.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
        w, hh = (3, 4.5) if rotation else (4.5, 3)
        m.add_lwpolyline([(x - w, y - hh), (x + w, y - hh), (x + w, y + hh), (x - w, y + hh)],
                         close=True, dxfattribs={'color': 5})
    title_y = h + max(32, h * .15)
    for y in range(math.ceil(h + 1), math.ceil(title_y - 8), 4):
        m.add_line((b / 2, y), (b / 2, min(y + 2, title_y - 8)), dxfattribs={'color': 8})
    _text(m, contract.get('beam') or contract.get('id') or 'Corte', b / 2, title_y, 6.5, True)
    _text(m, f'({b:g}x{h:g})', b / 2, title_y - 7, 4, True)
    return doc


def draw_ab(contract, *, timber_sink=None):
    """Draw contiguous local segments. Opening coordinates are local to each segment."""
    assembly = contract['assembly_variant']
    doc, ref = _template(assembly, 'ab')
    m = doc.modelspace()
    body, height = float(contract['body_cm']), float(contract['total_cm'])
    from shapely.geometry import box as raw_box
    active_y = 0.
    def box(x1, y1, x2, y2, offset=None):
        dy = active_y if offset is None else offset
        return raw_box(x1, y1+dy, x2, y2+dy)
    segments, start, voids = [], 0., []
    for source in contract['segments']:
        active_y = float(source.get('y_offset_cm', 0))
        body = float(source.get('body_cm', contract['body_cm']))
        height = float(source.get('total_cm', contract['total_cm']))
        length = float(source['length'])
        if length <= 0 or body <= 0 or height < body:
            raise ValueError('Invalid AB local dimensions')
        end = start + length
        beam_openings = source.get('beam_openings', [source['beam_opening']] if source.get('beam_opening') else [])
        columns = source.get('column_openings', [source['column_opening']] if source.get('column_opening') else [])
        beam_openings = [(max(0., a), min(length, b), max(0., min(body, y)))
                         for a, b, y in beam_openings if b > 0 and a < length and b > a]
        columns = [(max(0., a), min(length, b)) for a, b in columns if b > 0 and a < length and b > a]
        segments.append((start, end, source, beam_openings, columns))
        voids.extend(box(start+a, y, start+b, height) for a, b, y in beam_openings)
        if height > body:
            voids.append(box(start, body, end, height))
        start = end
    total = start
    if all(float(s[2].get('y_offset_cm',0)) == active_y and
           float(s[2].get('body_cm',contract['body_cm'])) == body and
           float(s[2].get('total_cm',contract['total_cm'])) == height for s in segments):
        voids = [box(sx+a,y,sx+b,height) for sx,end,source,holes,columns in segments for a,b,y in holes]
        if height > body:
            voids.insert(0,box(0,body,total,height))
    void_geometry = unary_union(voids).simplify(1e-7, preserve_topology=True)
    band = next(e for e in ref.modelspace().query('HATCH') if e.dxf.pattern_name == 'AR-CONC')
    for part in _parts(void_geometry):
        if part.geom_type == 'Polygon' and part.area:
            hatch = _hatch(m, list(part.exterior.coords)[:-1], band, 1)
            hatch.dxf.layer, hatch.dxf.color = 'COTA', 256
    doc.layers.get('SARR_2.2x7').dxf.color = 40
    doc.layers.get('SARR_3.5x7').dxf.color = 81

    def line(a, b, layer, mask=None, world=False):
        if not world:
            a, b = (a[0], a[1]+active_y), (b[0], b[1]+active_y)
        geometry = LineString([a, b])
        if mask is not None:
            geometry = geometry.intersection(mask)
        for part in _parts(geometry):
            if part.geom_type == 'LineString' and part.length > 1e-6:
                m.add_line(part.coords[0], part.coords[-1], dxfattribs={'layer': layer})

    def measure(p1, p2, base, angle=0):
        p1, p2, base = [(p[0],p[1]+active_y) for p in (p1,p2,base)]
        d = m.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle,
                             dimstyle='PAINEL', dxfattribs={'layer': 'COTA'})
        d.render()

    dimension_floor = min(float(s[2].get('y_offset_cm',0)) for s in segments)
    orange, green, materials, jambs, continuations = [], [], [], [], []
    for index, (sx, end, source, openings, columns) in enumerate(segments, 1):
        active_y = float(source.get('y_offset_cm', 0))
        body = float(source.get('body_cm', contract['body_cm']))
        height = float(source.get('total_cm', contract['total_cm']))
        material = box(sx, 0, end, height)
        for a, b, y in openings:
            material = material.difference(box(sx+a, y, sx+b, height+1))
        local = material.intersection(box(sx, 0, end, body))
        materials.append(local)
        mask, greenmask = local, local
        for a, b in columns:
            mask = mask.difference(box(sx+a, -1, sx+b, body-7))
            greenmask = greenmask.difference(box(sx+a, -1, sx+b, body+1))
        spans = [(sx+a, sx+b) for a, b in panel_spans(end-sx)]
        for x, stop in spans:
            panel = box(x, 0, stop, body).intersection(local)
            for part in _parts(panel):
                if part.geom_type != 'Polygon' or not part.area:
                    continue
                coords = list(part.exterior.coords)
                for a, b in zip(coords, coords[1:]):
                    if abs(a[0]-b[0]) < 1e-6 and sx < a[0] < end:
                        line(a, b, 'Painéis', local, world=True)
                    else:
                        line(a, b, 'Painéis', world=True)
            line((x, body), (stop, body), 'Painéis', material)
            measure((x, 0), (stop, 0), (x, dimension_floor-26.54-active_y))
        for a, b, y in openings:
            a, b = sx+a, sx+b
            measure((a, y), (b, y), (a, height+24))
            q = a+25 if abs(a-sx) < 1e-6 else b-25
            measure((q, y), (q, height), (q, y), 90)
        for a, b in columns:
            a, b = sx+a, sx+b
            anchors = [a]+[q for x, q in spans[:-1] if a < q < b]+[b]
            for x, stop in zip(anchors, anchors[1:]):
                measure((x, body/2), (stop, body/2), (x, body/2))
        if index == 1:
            label = (f'Cont. {contract["beam"]}.{contract.get("side", "A")}'
                     if contract.get('continuation') else f'{contract["beam"]}.{contract.get("side", "A")}')
            _text(m, label, sx+5, height+5+active_y, 13)
        rails = [(body-2.2, body)]
        if assembly == 'sarrafeadas':
            n = max(2, math.ceil((body-7)/30)+1)
            rails = [(0, 7), (body-7, body)] + [((body-7)*i/(n-1), (body-7)*i/(n-1)+7) for i in range(1, n-1)]
        for low, high in rails:
            if min(end, total-7) > max(sx, 7):
                orange.append(box(max(sx, 7), low, min(end, total-7), high).intersection(mask))
        for a, b in columns:
            a, b = sx+a, sx+b
            orange.append(box(a, body-7, b, body).intersection(local))
            if assembly == 'gradeadas':
                green.extend([box(a-3.5, 0, a, body-2.2).intersection(local),
                              box(b, 0, b+3.5, body-2.2).intersection(local)])
        if sx == 0:
            orange.append(box(0, 0, min(7, total), body).intersection(local))
        if end == total:
            orange.append(box(max(0, total-7), 0, total, body).intersection(local))
        if assembly == 'gradeadas':
            if sx == 0:
                green.append(box(15, 0, 18.5, body-2.2).intersection(greenmask))
            if end == total:
                green.append(box(total-18.5, 0, total-15, body-2.2).intersection(greenmask))
            for x, stop in spans[:-1]:
                green.extend([box(stop-3.5, 0, stop, body-2.2).intersection(greenmask),
                              box(stop, 0, stop+3.5, body-2.2).intersection(greenmask)])
            if end < total:
                next_body = float(segments[index][2].get('body_cm', contract['body_cm']))
                if not any(abs(b-(end-sx)) < 1e-6 for a,b,y in openings):
                    green.append(box(end-3.5, 0, end, body-2.2).intersection(greenmask))
                next_y = float(segments[index][2].get('y_offset_cm',0))
                next_mask = box(end,0,segments[index][1],next_body,offset=next_y)
                for a,b,y in segments[index][3]:
                    next_mask = next_mask.difference(box(end+a,y,end+b,next_body+1,offset=next_y))
                post = box(end, 0, end+3.5, next_body-2.2,offset=next_y)
                green.append(post.intersection(next_mask) if segments[index][3] else post)
        elif index > 1:
            previous = segments[index-2]
            if any(abs(b-(previous[1]-previous[0])) < 1e-6 for a, b, y in previous[3]):
                continuations.append((sx, active_y, body+active_y))
        for a, b, y in openings:
            a, b = sx+a, sx+b
            left = abs(a-sx) < 1e-6
            if assembly == 'gradeadas':
                j1, j2 = (b, b+3.5) if left else (a-3.5, a)
                green.append(box(j1, 0, j2, body-2.2).intersection(local))
                orange.append(box(a, y-2.2, b, y))
                endpoint = a if left else b
                outer = abs(endpoint) < 1e-6 or abs(endpoint-total) < 1e-6
                width = 7 if outer else 3.5
                e1, e2 = (endpoint, endpoint+width) if left else (endpoint-width, endpoint)
                if outer or left or abs(endpoint-end) > 1e-6:
                    (orange if outer else green).append(box(e1, 0, e2, y-2.2))
            else:
                j1, j2 = (b, b+7) if left else (a-7, a)
                orange.extend([box(j1, y-7, j2, body).intersection(mask), box(a, y-7, b, y)])
                jambs.append((j1, j2, y+active_y, body+active_y))
        if assembly == 'gradeadas':
            intervals = [(sx+a, sx+b) for a, b, y in openings]+[(sx+a, sx+b) for a, b in columns]
            for x, stop in spans:
                free = box(x, 4, stop, body-5)
                for a, b, y in openings:
                    free = free.difference(box(sx+a, y, sx+b, body+1))
                for a, b in columns:
                    free = free.difference(box(sx+a, 0, sx+b, body+1))
                regions = [p for p in _parts(free) if p.geom_type == 'Polygon' and p.area]
                if not regions:
                    continue
                count = pontalete_count(x, stop, intervals)
                # A fully removed panel must not receive a floating annotation.
                if unary_union([box(max(x,a), 0, min(stop,b), 1) for a,b in intervals if b>x and a<stop]).area >= stop-x-1e-6:
                    continue
                label = f'{count} pontalete' if count == 1 else f'{count} pontaletes'
                region = max(regions, key=lambda p: p.bounds[2]-p.bounds[0])
                p = region.representative_point()
                size = min(5, max(1.2, (region.bounds[2]-region.bounds[0]-2)/(len(label)*.75)))
                _text(m, label, p.x, p.y, size, True)

    active_y = 0.
    measure((0,float(segments[0][2].get('y_offset_cm',0))),
            (total,float(segments[-1][2].get('y_offset_cm',0))),
            (0,dimension_floor-70))
    # A connected slab/opening has one pink boundary; the shared panel
    # interface retains the panel layer and is not duplicated in pink.
    interface = unary_union(materials).boundary
    for part in ([] if void_geometry.is_empty else _parts(void_geometry.boundary.difference(interface))):
        if part.geom_type == 'LineString':
            coords=list(part.simplify(1e-7).coords)
            for a,b in zip(coords,coords[1:]):
                line(a,b,'COTA',world=True)
    body_heights = {float(s[2].get('body_cm',contract['body_cm']))+float(s[2].get('y_offset_cm',0)) for s in segments}
    base_heights = {float(s[2].get('y_offset_cm',0)) for s in segments}
    seen = set()
    def outline(geometry, layer):
        for part in _parts(geometry):
            if part.geom_type != 'Polygon' or not part.area:
                continue
            for ring in [part.exterior]+list(part.interiors):
                coords = list(ring.coords)
                for a, b in zip(coords, coords[1:]):
                    if layer == 'SARR_2.2x7':
                        if any(abs(a[1]-y) < 1e-6 and abs(b[1]-y) < 1e-6 for y in (*base_heights, *body_heights)):
                            continue
                        if any(abs(a[0]-x) < 1e-6 and abs(b[0]-x) < 1e-6 for x in (0, total, 7, total-7)):
                            continue
                    key = layer, tuple(sorted((tuple(round(v,6) for v in a), tuple(round(v,6) for v in b))))
                    if key not in seen:
                        line(a, b, layer)
                        seen.add(key)
    if timber_sink is not None:
        timber_sink.extend((piece, False) for piece in orange)
        timber_sink.extend((piece, True) for piece in green)
    outline(unary_union(orange), 'SARR_2.2x7')
    for x, edge_source in ((7,segments[0][2]), (total-7,segments[-1][2])):
        edge_body = float(edge_source.get('body_cm',contract['body_cm']))
        edge_y = float(edge_source.get('y_offset_cm',0))
        line((x, edge_y), (x, edge_body+edge_y), 'SARR_2.2x7', unary_union(materials))
    for j1, j2, y, jamb_body in jambs:
        for e in list(m.query('LINE')):
            if e.dxf.layer != 'SARR_2.2x7':
                continue
            a, b = e.dxf.start, e.dxf.end
            if abs(a.x-b.x) < 1e-6 and any(abs(a.x-x) < 1e-6 for x in (j1,j2)) and min(a.y,b.y) >= y-7-1e-6:
                m.delete_entity(e)
        for x in (j1, j2):
            line((x, y-7), (x, jamb_body), 'SARR_2.2x7')
        if not any(e.dxf.layer=='SARR_2.2x7' and abs(e.dxf.start.y-(y-7))<1e-6 and abs(e.dxf.end.y-(y-7))<1e-6 and abs(min(e.dxf.start.x,e.dxf.end.x)-j1)<1e-6 and abs(max(e.dxf.start.x,e.dxf.end.x)-j2)<1e-6 for e in m.query('LINE')):
            line((j1,y-7),(j2,y-7),'SARR_2.2x7')
    for geometry in green:
        outline(geometry, 'SARR_3.5x7')
    for sx, end, source, openings, columns in segments:
        segment_y = float(source.get('y_offset_cm',0))
        for a, b, y in openings:
            y += segment_y
            for e in m.query('LINE'):
                if e.dxf.layer != 'SARR_3.5x7':
                    continue
                p, q = e.dxf.start, e.dxf.end
                if min(p.x,q.x) < sx+a-1e-6 or max(p.x,q.x) > sx+b+1e-6:
                    continue
                if max(p.y,q.y) > y+1e-6 or max(p.y,q.y) <= y-2.2+1e-6:
                    continue
                e.dxf.start=(p.x,min(p.y,y-2.2),p.z)
                e.dxf.end=(q.x,min(q.y,y-2.2),q.z)
    for start, base_y, body in continuations:
        for e in list(m.query('LINE')):
            if e.dxf.layer != 'SARR_2.2x7' or abs(e.dxf.start.y-e.dxf.end.y)>1e-6:
                continue
            left, right = sorted((e.dxf.start.x,e.dxf.end.x))
            y = e.dxf.start.y
            if right <= start+1e-6 or left >= start+7-1e-6:
                continue
            m.delete_entity(e)
            if left < start-1e-6:
                line((left,y),(start,y),'SARR_2.2x7')
            if right > start+7+1e-6:
                line((start+7,y),(right,y),'SARR_2.2x7')
        for x in (start,start+7):
            line((x,base_y),(x,body),'SARR_2.2x7')
    body = float(segments[-1][2].get('body_cm',contract['body_cm']))
    height = float(segments[-1][2].get('total_cm',contract['total_cm']))
    active_y = float(segments[-1][2].get('y_offset_cm',0))
    measure((total,0),(total,body),(total+29.35,0),90)
    measure((total,body),(total,height),(total+29.35,body),90)
    measure((total,0),(total,height),(total+55.34,0),90)
    # Merge adjoining straight panel/void walls without changing any other
    # construction members or dimension graphics.
    groups = {}
    for e in list(m.query('LINE')):
        if e.dxf.layer not in ('Painéis','COTA'):
            continue
        a,b=e.dxf.start,e.dxf.end
        if abs(a.y-b.y)<1e-7:
            key=(e.dxf.layer,'h',round(a.y,6)); interval=sorted((a.x,b.x))
        elif abs(a.x-b.x)<1e-7:
            key=(e.dxf.layer,'v',round(a.x,6)); interval=sorted((a.y,b.y))
        else:
            continue
        groups.setdefault(key,[]).append((interval,e))
    for (layer,axis,fixed),items in groups.items():
        intervals=[]
        for (lo,hi),e in sorted(items,key=lambda v:v[0]):
            m.delete_entity(e)
            if intervals and lo<=intervals[-1][1]+1e-6:
                intervals[-1][1]=max(intervals[-1][1],hi)
            else:
                intervals.append([lo,hi])
        for lo,hi in intervals:
            a,b=((lo,fixed),(hi,fixed)) if axis=='h' else ((fixed,lo),(fixed,hi))
            m.add_line(a,b,dxfattribs={'layer':layer})
    return doc
