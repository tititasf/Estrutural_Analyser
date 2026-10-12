"""Local beam sections proved by original dimensioned L/T glyphs.

No SA state is accepted. A section needs a continuous orthogonal stem, two
original dimension shafts with endpoint ticks and witnesses, and numeric texts.
Geometry binds the dimensions; the written height is the numeric authority.
"""
from __future__ import annotations

import math
import re
from shapely.geometry import LineString, Point, Polygon
from src.core.qa_original_polyline import original_polyline_xyb


def collect_dimensioned_sections(doc, tolerance_cm=.05):
    eps = tolerance_cm
    lines, texts, shapes, interrupted, markers, poly_witnesses = [], [], [], [], [], []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if tuple(entity.dxf.get('extrusion', (0, 0, 1))) != (0, 0, 1):
            continue
        if kind == 'LINE':
            a, b = tuple(entity.dxf.start)[:2], tuple(entity.dxf.end)[:2]
            if abs(entity.dxf.start.z) > eps or abs(entity.dxf.end.z) > eps:
                continue
            if math.dist(a, b) > eps:
                lines.append(dict(handle=entity.dxf.handle, a=a, b=b))
        elif kind in {'TEXT', 'MTEXT'}:
            text = (entity.dxf.text if kind == 'TEXT' else entity.plain_text()).strip()
            if not re.fullmatch(r'\d+(?:[.,]\d+)?', text):
                continue
            texts.append(dict(handle=entity.dxf.handle, value=float(text.replace(',', '.')),
                position=tuple(entity.dxf.insert)[:2],
                height=float(entity.dxf.height if kind == 'TEXT' else entity.dxf.char_height),
                rotation=float(entity.dxf.get('rotation', 0) if kind == 'TEXT' else entity.get_rotation())))
        elif kind in {'LWPOLYLINE', 'POLYLINE'}:
            elevation = entity.dxf.get('elevation', 0)
            z = elevation if isinstance(elevation, (int,float)) else elevation.z
            if abs(z) > eps:
                continue
            pts, closed = original_polyline_xyb(entity)
            if any(p[2] for p in pts):
                continue
            xy = [(float(p[0]), float(p[1])) for p in pts]
            edges = list(zip(xy, xy[1:]))
            if closed and xy and xy[0] != xy[-1]:
                edges.append((xy[-1], xy[0]))
            poly_witnesses.extend(dict(handle=entity.dxf.handle, a=a, b=b)
                for a,b in edges if math.dist(a,b)>eps and
                (abs(a[0]-b[0])<=eps or abs(a[1]-b[1])<=eps))
            if len(pts)>=6 and not closed and math.dist(xy[0],xy[-1])>eps:
                markers.append((entity.dxf.handle,xy))
            if len(pts)<6:continue
            if not closed and math.dist(xy[0], xy[-1]) > eps:
                continue
            shape = Polygon(xy)
            if not shape.is_valid or shape.interiors or shape.area <= eps:
                continue
            ring = list(shape.exterior.coords)
            if any(abs(a[0]-b[0]) > eps and abs(a[1]-b[1]) > eps for a,b in zip(ring,ring[1:])):
                interrupted.append((entity.dxf.handle,xy))
                continue
            shapes.append((entity.dxf.handle, shape, []))

    from src.core.pil_qa_broken_sections import traced_section_outline,broken_dimension_shafts
    for handle,xy in interrupted:
        recovered=traced_section_outline(xy,lines,eps)
        if recovered:
            shape,evidence=recovered
            shapes.append((handle,shape,evidence))
    shafts=lines+broken_dimension_shafts(lines,markers,eps)

    def dimensions(axis, limits, cross_limits):
        ai, ti = (0, 1) if axis == 'x' else (1, 0)
        proofs = []
        for shaft in shafts:
            a, b = shaft['a'], shaft['b']
            if abs(a[ti]-b[ti]) > eps:
                continue
            if any(abs(v-w) > eps for v,w in zip(sorted((a[ai],b[ai])), limits)):
                continue
            # Dimension must sit just outside the profile, not on its stem.
            distance = min(abs(a[ti]-v) for v in cross_limits)
            if cross_limits[0]-eps <= a[ti] <= cross_limits[1]+eps or distance > 60:
                continue
            local = [t for t in texts if t['value'] > 0 and
                abs(math.sin(math.radians(t['rotation']-(0 if axis == 'x' else 90)))) < 1e-6 and
                LineString((a,b)).distance(Point(t['position'])) <= max(eps, 3*t['height'])]
            values = {t['value'] for t in local}
            if len(values) != 1:
                continue
            evidence = shaft.get('evidence_handles',[shaft['handle']]) + [t['handle'] for t in local]
            for endpoint in (a,b):
                ticks = [line for line in lines if line['handle'] != shaft['handle'] and
                    abs(line['a'][0]-line['b'][0]) > eps and abs(line['a'][1]-line['b'][1]) > eps and
                    math.dist(tuple((v+w)/2 for v,w in zip(line['a'],line['b'])), endpoint) <= eps]
                # Duplicate CAD strokes at the same endpoint are one tick.
                tick_shapes = {tuple(sorted((tuple(round(v,3) for v in line['a']),
                    tuple(round(v,3) for v in line['b'])))) for line in ticks}
                witnesses = [line for line in lines+poly_witnesses if line['handle'] != shaft['handle'] and
                    abs(line['a'][ai]-endpoint[ai]) <= eps and abs(line['b'][ai]-endpoint[ai]) <= eps and
                    min(line['a'][ti],line['b'][ti])-eps <= endpoint[ti] <= max(line['a'][ti],line['b'][ti])+eps and
                    (min(abs(p[ti]-c) for p in (line['a'],line['b']) for c in cross_limits) <= 5+eps or
                     any(min(line['a'][ti],line['b'][ti])-eps <= c <=
                         max(line['a'][ti],line['b'][ti])+eps for c in cross_limits))]
                if len(tick_shapes) != 1 or not witnesses:
                    break
                evidence += [line['handle'] for line in ticks+witnesses]
            else:
                proofs.append(dict(value=next(iter(values)), handles=sorted(set(evidence))))
        if len({p['value'] for p in proofs}) != 1:
            return None
        return dict(value=proofs[0]['value'], handles=sorted({h for p in proofs for h in p['handles']}))

    result = []
    for handle, shape, outline_evidence in shapes:
        for axis in ('x','y'):
            ai, ti = (0,1) if axis == 'x' else (1,0)
            ring = list(shape.exterior.coords)
            coords = sorted({p[ai] for p in ring})
            transverse = sorted({p[ti] for p in ring})
            weight = {}
            bands = []
            for lo, hi in zip(coords,coords[1:]):
                midpoint = (lo+hi)/2
                line = ([(midpoint,transverse[0]-1),(midpoint,transverse[-1]+1)] if ai == 0 else
                        [(transverse[0]-1,midpoint),(transverse[-1]+1,midpoint)])
                hit = shape.intersection(LineString(line))
                if hit.geom_type != 'LineString':
                    break
                limits = (hit.bounds[ti],hit.bounds[ti+2])
                bands.append(limits)
                weight[limits] = weight.get(limits,0) + hi-lo
            else:
                if len(weight) < 2:
                    continue  # A rectangle alone is not a beam-section glyph.
                stem = max(weight, key=lambda iv: (weight[iv], -(iv[1]-iv[0])))
                if any(lo > stem[0]+eps or hi < stem[1]-eps for lo,hi in bands):
                    continue
                if stem[1]-stem[0] < 5 or coords[-1]-coords[0] <= stem[1]-stem[0]:
                    continue
                width = dimensions('y' if axis == 'x' else 'x', stem, (coords[0],coords[-1]))
                height = dimensions(axis, (coords[0],coords[-1]), (transverse[0],transverse[-1]))
                if not width or not height or abs(width['value']-(stem[1]-stem[0])) > eps:
                    continue
                result.append(dict(axis=axis, positions=stem, span=(coords[0],coords[-1]),
                    text=f"{width['value']:g}/{height['value']:g}",
                    handle=handle, evidence_handles=sorted({handle,*outline_evidence,*width['handles'],*height['handles']}),
                    evidence_kind='original_dimensioned_section', geometric_height_cm=coords[-1]-coords[0]))
    return result


def sections_in_span(records, *, axis, positions, span, tolerance_cm=.05):
    """Only a stem on both original walls and fully within the own source span."""
    eps = tolerance_cm
    return [r for r in records if r['axis'] == axis and
        all(abs(v-w) <= eps for v,w in zip(r['positions'], sorted(positions))) and
        span[0]-eps <= r['span'][0] and r['span'][1] <= span[1]+eps]
