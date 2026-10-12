"""Bind explicit legend labels to bounded symbols, without classifying pillars.

Lengths are relative to text height. The label's rotation defines its local
frame. A symbol needs a unique closed rectangular contour; nearby unrelated
lines cannot participate in its signature. Original handles remain evidence.
"""
from __future__ import annotations

import math

from .pillar_convention import geometry_signature


def associate_legend_symbols(document, texts, roles):
    from ezdxf.math import Vec2

    model = document.modelspace()
    lookup = {str(e.dxf.handle): e for e in model}
    contours = []
    for entity in model.query('LWPOLYLINE POLYLINE'):
        if entity.dxftype() == 'LWPOLYLINE':
            points = [(float(x), float(y)) for x, y, *_ in entity.get_points()]
            if any(abs(p[4]) > 1e-12 for p in entity.get_points()):
                continue
        else:
            if not entity.is_2d_polyline or any(abs(v.dxf.bulge) > 1e-12 for v in entity.vertices):
                continue
            points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
        if len(points) == 5 and math.dist(points[0], points[-1]) < 1e-9:
            points.pop()
        elif not entity.is_closed:
            continue
        if len(points) != 4:
            continue
        contours.append((str(entity.dxf.handle), points))

    entries = []
    for role in roles:
        if role.get('role') != 'pillar_legend_candidate':
            continue
        labels = [t for t in texts if t['handle'] in role['label_handles']]
        for label in labels:
            source = lookup.get(label['handle'])
            if source is None or source.dxftype() != 'TEXT':
                continue  # MTEXT alignment needs its own bounded contract.
            height = float(label.get('height') or 0)
            if height <= 0 or abs(source.dxf.extrusion.z - 1) > 1e-9:
                continue
            angle = math.radians(float(source.dxf.rotation))
            c, s = math.cos(angle), math.sin(angle)
            ox, oy = label['position']

            def local(point):
                dx, dy = point[0] - ox, point[1] - oy
                return ((dx*c + dy*s)/height, (-dx*s + dy*c)/height)

            candidates = []
            for handle, points in contours:
                projected = [local(p) for p in points]
                x0, x1 = min(p[0] for p in projected), max(p[0] for p in projected)
                y0, y1 = min(p[1] for p in projected), max(p[1] for p in projected)
                # A sample sits just before the explicit word on its baseline.
                if not (-8 <= x0 < x1 <= 0 and 0 <= -x1 <= 2 and
                        -2 <= y0 <= 1 and 0 <= y1 <= 3 and x1-x0 >= 1 and y1-y0 >= .5):
                    continue
                tolerance = 1e-5
                corners = {(round(x0, 5), round(y0, 5)), (round(x0, 5), round(y1, 5)),
                           (round(x1, 5), round(y0, 5)), (round(x1, 5), round(y1, 5))}
                if {(round(x, 5), round(y, 5)) for x, y in projected} != corners:
                    continue
                if any(abs(projected[i][0]-projected[(i+1)%4][0]) > tolerance and
                       abs(projected[i][1]-projected[(i+1)%4][1]) > tolerance for i in range(4)):
                    continue
                candidates.append((handle, (x0, y0, x1, y1), tolerance))
            entry = {'label': label['text'], 'label_handle': label['handle'],
                     'title_handle': role['title_handle'], 'classification_authority': 'none',
                     'association_status': 'ambiguous' if len(candidates) > 1 else 'unresolved'}
            if len(candidates) != 1:
                entry['candidate_contour_handles'] = [candidate[0] for candidate in candidates]
                entries.append(entry)
                continue
            handle, (x0, y0, x1, y1), tolerance = candidates[0]

            def inside(point):
                x, y = local(point)
                return x0-tolerance <= x <= x1+tolerance and y0-tolerance <= y <= y1+tolerance

            lines, solids = [], []
            for entity in model.query('LINE SOLID'):
                if entity.dxftype() == 'LINE':
                    start, end = entity.dxf.start, entity.dxf.end
                    if inside(start) and inside(end) and math.dist(local(start), local(end)) > 1e-8:
                        lines.append({'handle': str(entity.dxf.handle), 'start': local(start), 'end': local(end)})
                else:
                    points = [entity.dxf.get('vtx'+str(i)) for i in (0, 1, 3, 2)]
                    if any(p is None or not inside(p) for p in points):
                        continue
                    area = abs(sum(Vec2(local(points[i])).det(Vec2(local(points[(i+1)%4]))) for i in range(4)))/2
                    if area > 1e-8:
                        solids.append({'handle': str(entity.dxf.handle), 'normalized_area': area})
            entry.update(association_status='bounded_unique_contour', contour_handle=handle,
                         line_handles=[line['handle'] for line in lines],
                         solid_handles=[solid['handle'] for solid in solids],
                         line_count=len(lines), signature=geometry_signature(lines),
                         symbol_bounds_in_text_frame=[x0, y0, x1, y1],
                         policy='explicit_label_only; no_global_pattern_meaning; no_item_classification')
            entries.append(entry)
    # One contour cannot be a sample for two labels, even across headings.
    for entry in entries:
        handle = entry.get('contour_handle')
        if handle and sum(other.get('contour_handle') == handle for other in entries) > 1:
            entry['association_status'] = 'ambiguous_shared_contour'
    return {'schema': 'cad.pillar.legend.symbols/v1', 'entries': entries,
            'status': 'bounded' if entries and all(e['association_status'] == 'bounded_unique_contour' for e in entries) else 'partial',
            'classification_authority': 'none'}
