"""Paginate approved N3 pillar views without expanding the nine-cell index."""
import hashlib
import json
import textwrap

from ezdxf import bbox
from ezdxf.disassemble import make_primitive, recursive_decompose


def level_line(entity):
    return entity.dxf.layer.casefold() in ('nível', 'pedireito') and entity.dxftype() in ('LINE', 'LWPOLYLINE')


def physical(doc):
    return [e for e in doc.modelspace() if not level_line(e)]


def subset(doc, entities):
    from .n5_ini_frames import clone
    result = clone(doc)
    handles = {e.dxf.handle for e in entities}
    for e in list(result.modelspace()):
        if e.dxf.handle not in handles:
            result.modelspace().delete_entity(e)
    return result


def bounds(entities):
    # Native MLINEs need their real thickness in the fit test.
    from .ini_pillar_grades import bounds as native_bounds
    return native_bounds(entities)


def split_faces(doc):
    labels = sorted([e for e in doc.modelspace().query('TEXT')
                     if e.dxf.layer == 'NOMENCLATURA' and '.' in e.dxf.text],
                    key=lambda e: e.dxf.insert.x)
    anchors = {e.dxf.text.rsplit('.', 1)[-1]: e.dxf.insert.x for e in labels}
    if 'E' not in anchors:
        from .n5_ini_frames import CW
        if bounds(physical(doc)).size.x <= CW-30:
            return [doc]
        # A very wide rectangular pillar also needs separate projection cells.
        if 'C' not in anchors:
            return [doc]
        cut = anchors['C'] - 10
    else:
        cut = anchors['E'] - 10
    # The first face E begins after the D panel and its own dimension chain.
    parts = [[], []]
    for e in doc.modelspace():
        if level_line(e):
            for part in parts:
                part.append(e)
        else:
            box = bounds([e])
            if box.has_data:
                parts[int(box.center.x >= cut)].append(e)
    result = [subset(doc, part) for part in parts]
    for part in result:
        compact_faces(part)
    return result


def compact_faces(doc):
    """Remove surplus presentation gaps, retaining panel and dimension sizes."""
    labels = sorted([e for e in doc.modelspace().query('TEXT')
                     if e.dxf.layer == 'NOMENCLATURA' and '.' in e.dxf.text],
                    key=lambda e: e.dxf.insert.x)
    cuts = [e.dxf.insert.x - 10 for e in labels[1:]]
    for e in doc.modelspace():
        if level_line(e):
            continue
        box = bounds([e])
        if box.has_data:
            e.translate(-35 * sum(box.center.x > x for x in cuts), 0, 0)


def stretch_levels(doc, left, right, dx):
    for e in doc.modelspace():
        if not level_line(e):
            continue
        if e.dxftype() == 'LINE' and abs(e.dxf.start.y - e.dxf.end.y) < .001:
            y = e.dxf.start.y
            e.dxf.start = (left - dx, y, 0)
            e.dxf.end = (right - dx, y, 0)
        elif e.dxftype() == 'LWPOLYLINE':
            pts = e.get_points('xy')
            if len(pts) == 2 and abs(pts[0][1] - pts[1][1]) < .001:
                e.set_points([(left - dx, pts[0][1]), (right - dx, pts[0][1])])


def identity(doc):
    """Translation-independent fabrication + annotation identity of a face."""
    box = bounds(physical(doc))
    records = []
    for e in doc.modelspace():
        if level_line(e):
            continue
        kind = e.dxftype()
        base = [kind, e.dxf.layer, e.dxf.get('color', 256)]
        if kind == 'MLINE':
            style = doc.mline_styles.get(e.dxf.style_name)
            base += [e.dxf.scale_factor, e.dxf.justification, style.dxf.fill_color,
                     [(p.offset, p.color, p.linetype) for p in style.elements],
                     [(round(v.location.x-box.extmin.x, 4), round(v.location.y-box.extmin.y, 4)) for v in e.vertices]]
        else:
            points = []
            for child in recursive_decompose([e]):
                points += [(round(v.x-box.extmin.x, 4), round(v.y-box.extmin.y, 4))
                           for v in make_primitive(child).vertices()]
            base.append(sorted(points))
            if kind in ('TEXT', 'MTEXT'):
                base += [e.dxf.text if kind == 'TEXT' else e.text,
                         e.dxf.get('height' if kind == 'TEXT' else 'char_height', 0)]
            if kind == 'HATCH':
                base += [e.dxf.solid_fill, e.dxf.pattern_name,
                         e.dxf.get('pattern_scale', 1), e.dxf.get('pattern_angle', 0)]
        records.append(base)
    return hashlib.sha256(json.dumps(sorted(records, key=str)).encode()).hexdigest()


def grade_faces(doc):
    """Keep paired grades and their native gap/right dimension chains together."""
    labels = sorted([e for e in doc.modelspace().query('TEXT')
                     if e.dxf.layer == 'NOMENCLATURA' and '.' in e.dxf.text],
                    key=lambda e: e.dxf.insert.x)
    if not labels:
        raise ValueError('Grades INI sem identificação de face')
    cuts = [e.dxf.insert.x - 10 for e in labels[1:]]
    buckets = [[] for _ in labels]
    for e in physical(doc):
        if e in labels:
            continue
        box = bounds([e])
        if box.has_data:
            buckets[sum(box.center.x > x for x in cuts)].append(e)
    return [(label.dxf.text, subset(doc, entities)) for label, entities in zip(labels, buckets)]


def assemble(pages, index, sources, pillar_group):
    from . import n5_ini_frames as f
    current = None
    slot = 9

    def newcell(label):
        nonlocal current, slot
        if slot == 9:
            doc, _, _ = f.template_doc('PL')
            current = dict(doc=doc, kind='PL', entries=[])
            pages.append(current)
            slot = 0
        cell = f.cells()[slot]
        slot += 1
        entry = dict(label=label, page=len(pages), module=(len(pages)-1)*9+slot,
                     cell=list(cell), views=[])
        current['entries'].append(entry)
        index.append(entry)
        return current, cell, entry

    def place(doc, target, cell, zone, baseline=None, x=None):
        l, b, r, t = cell
        box = bounds(physical(doc))
        if box.size.x > r-l-30 or box.size.y > t-b-90:
            raise ValueError(f'{zone}: vista INI excede a célula em escala nativa: {box.size}')
        dx = (l+r)/2-box.center.x if x is None else x-box.extmin.x
        dy = t-45-box.extmax.y if zone == 'CIMA' else b+90-box.extmin.y if baseline is None else baseline
        bb = [box.extmin.x+dx, box.extmin.y+dy, box.extmax.x+dx, box.extmax.y+dy]
        if not (l <= bb[0] <= bb[2] <= r and b <= bb[1] <= bb[3] <= t):
            raise ValueError(f'{zone}: conteúdo atravessa a parede da moldura')
        stretch_levels(doc, l, r, dx)
        f.normalize_resources(doc)
        f.transfer(doc, target['doc'], dx, dy)
        return dict(view=zone, bounds=bb, scale=2 if zone=='CIMA' else 1, transfer_scale=1)

    unique = {}
    occurrences = 0
    for item, paths in sources:
        families = [('PARA', 3, 4), ('PASSA', 1, 2)] if pillar_group is None else [('PARA', 3, 4)] if pillar_group=='PARA' else [('PASSA', 1, 2)]
        for family, ab, grade in families:
            top, elevation = f.source(paths[0], 'PL'), f.source(paths[ab], 'PL')
            parts = split_faces(elevation)
            has_efgh = any(e.dxf.text.rsplit('.',1)[-1]=='E' for e in elevation.modelspace().query('TEXT') if e.dxf.layer=='NOMENCLATURA')
            zones = ('ABCD', 'EFGH') if has_efgh else ('AB', 'CD') if len(parts)>1 else ('ABCD',)
            views = [('CIMA', top)] + list(zip(zones, parts))
            fits = len(parts)==1 and max(bounds(physical(d)).size.x for _, d in views)<=f.CW-30 and sum(bounds(physical(d)).size.y for _, d in views)+160<=f.CH
            if fits:
                target, cell, entry = newcell(item+' / '+family+' / CIMA + ABCD')
                entry['views'] = [place(d, target, cell, zone) for zone, d in views]
            else:
                for zone, doc in views:
                    target, cell, entry = newcell(item+' / '+family+' / '+zone)
                    entry['views'].append(place(doc, target, cell, zone))
            # Absolute levels belong to identity too; do not combine floors.
            levels = sorted(e.dxf.text for e in elevation.modelspace().query('TEXT')
                            if 'nível' in e.dxf.layer.casefold())
            for name, doc in grade_faces(f.source(paths[grade], 'PL')):
                key = (identity(doc), tuple(levels))
                occurrences += 1
                if key not in unique:
                    unique[key] = dict(doc=doc, names=[], signature=key[0], levels=levels)
                unique[key]['names'].append(name+' / '+family)

    target = None
    cursor = 0
    datum = None
    for group in unique.values():
        doc = group['doc']
        box = bounds(physical(doc))
        # Heights and absolute levels must share a cell datum.
        key = (round(box.extmax.y, 4), tuple(group['levels']))
        if target is None or key != datum or cursor+box.size.x > f.CW-70:
            target, cell, entry = newcell('GRADES UNIFICADAS')
            cursor = 0
            datum = key
            l, b, r, t = cell
            for y in (b+100, b+100+box.extmax.y):
                target['doc'].modelspace().add_line((l,y),(r,y),dxfattribs={'layer':'PEDIREITO','color':2})
        l, b, r, t = cell
        x = l+35+cursor
        if cursor:
            target['doc'].modelspace().add_line((x-17,b+35),(x-17,b+100+box.extmax.y+75),dxfattribs={'layer':'INI_SEPARACAO_GRADES','color':8})
        names = list(dict.fromkeys(group['names']))
        lines = textwrap.wrap(', '.join(names), width=max(12,int(box.size.x/5)))
        if b+100+box.extmax.y+45+len(lines)*11 > t-20:
            raise ValueError('Nomes das grades excedem a célula INI')
        for n, line in enumerate(lines):
            target['doc'].modelspace().add_text(line,dxfattribs={'height':7,'color':7,'insert':(x,b+100+box.extmax.y+45-n*11)})
        view = place(doc,target,cell,'GRADES',baseline=b+100,x=x)
        view.update(names=names,signature=group['signature'])
        entry['views'].append(view)
        cursor += box.size.x+35
    return dict(unique_grade_faces=len(unique),grade_face_occurrences=occurrences,
                unified_grades=[dict(signature=g['signature'],names=list(dict.fromkeys(g['names']))) for g in unique.values()])
