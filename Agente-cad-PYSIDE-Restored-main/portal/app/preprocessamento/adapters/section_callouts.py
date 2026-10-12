"""Trace named section callouts to plan arrows, without numerical authority.

Only a unique pair of aligned labels with nondegenerate triangular arrows is
accepted. Co-presence of a beam/pillar label never establishes an item link.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import hashlib
import math
from pathlib import Path
import re


def triangles(document):
    result = []
    for entity in document.modelspace().query('SOLID'):
        points = list(dict.fromkeys(tuple(entity.dxf.get('vtx' + str(i)))[:2] for i in range(4)))
        if len(points) != 3:
            continue
        a, b, c = points
        area2 = abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
        sides = sorted([(math.dist(points[i], points[j]), i, j)
                        for i, j in combinations(range(3), 2)], reverse=True)
        size, i, j = sides[0]
        if size <= 0 or area2 <= size*size*.01 or sides[1][0] >= size*.98:
            continue
        tip = points[3-i-j]
        base = [(points[i][k]+points[j][k])/2 for k in (0, 1)]
        direction = [tip[k]-base[k] for k in (0, 1)]
        length = math.hypot(*direction)
        result.append({'handle': entity.dxf.handle, 'tip': list(tip), 'base': base,
                       'direction': [v/length for v in direction], 'size': size})
    return result


def pair_callouts(labels, arrows):
    """Returns unique bounded axes, or explicit unresolved diagnostic records."""
    groups = defaultdict(list)
    for label in labels:
        if label.get('height', 0) <= 0:
            continue
        candidates = [a for a in arrows if math.dist(label['position'], a['tip']) <= 2*label['height']
                      and .5*label['height'] <= a['size'] <= 4*label['height']]
        if len(candidates) == 1:
            groups[label['label']].append({**label, 'arrow': candidates[0]})
    output = []
    for name, markers in groups.items():
        pairs = []
        for a, b in combinations(markers, 2):
            if a['arrow']['handle'] == b['arrow']['handle']:
                continue
            da, db = a['arrow']['direction'], b['arrow']['direction']
            # Same viewing direction and axis perpendicular to that direction.
            if sum(x*y for x, y in zip(da, db)) < .995:
                continue
            delta = [b['arrow']['base'][k]-a['arrow']['base'][k] for k in (0, 1)]
            tolerance = min(a['height'], b['height'])*.1
            if abs(sum(x*y for x, y in zip(da, delta))) > tolerance:
                continue
            if math.hypot(*delta) <= 4*max(a['height'], b['height']):
                continue
            pairs.append((a, b))
        if len(pairs) != 1:
            output.append({'label': name, 'status': 'ambiguous_pairs' if pairs else 'no_aligned_pair',
                           'candidate_pair_count': len(pairs), 'item_association_status': 'unresolved'})
            continue
        a, b = pairs[0]
        output.append({'label': name, 'status': 'unique_plan_callout_pair',
                       'label_handles': [a['handle'], b['handle']],
                       'arrow_handles': [a['arrow']['handle'], b['arrow']['handle']],
                       'bounded_axis': [a['arrow']['base'], b['arrow']['base']],
                       'view_direction': a['arrow']['direction'],
                       'authority': 'explicit_paired_labels_and_triangle_geometry',
                       'item_association_status': 'unresolved', 'numeric_authority': 'none'})
    return output


def enrich_plan_callouts(root, sources, raw_reference, auxiliary):
    if not raw_reference:
        return
    import ezdxf
    root = Path(root).resolve()
    raw = (root/raw_reference['relative_path']).resolve()
    if not raw.is_relative_to(root) or hashlib.sha256(raw.read_bytes()).hexdigest() != raw_reference['revision']:
        raise ValueError('section_callout_raw_revision_changed')
    raw_doc = ezdxf.readfile(raw)
    named = defaultdict(list)
    for entry in auxiliary:
        for link in entry.get('section_title_links', []):
            match = re.fullmatch(r'CORTE\s+([A-Z0-9]+)\s*[-–]\s*\1\s*:?\s*', link['title'], re.I)
            if match:
                named[match[1].upper()].append((entry, link))
    if not named:
        return
    raw_arrows = {a['handle']: a for a in triangles(raw_doc)}
    plan_matches = defaultdict(list)
    for source in sources:
        if source.kind.value != 'tower' or source.bruto_id != raw_reference['bruto_id']:
            continue
        path = (root/source.relative_path).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != source.revision:
            raise ValueError('section_callout_tower_revision_changed')
        # Use the actual plan crop, requiring each handle to exist in the raw.
        plan = ezdxf.readfile(path)
        labels = []
        for e in plan.modelspace().query('TEXT MTEXT'):
            label = (e.dxf.text if e.dxftype() == 'TEXT' else e.plain_mtext()).strip().upper()
            original = raw_doc.entitydb.get(e.dxf.handle)
            if label not in named or original is None or original.dxftype() != e.dxftype():
                continue
            original_label = (original.dxf.text if original.dxftype() == 'TEXT' else original.plain_mtext()).strip().upper()
            if original_label != label or math.dist(tuple(e.dxf.insert), tuple(original.dxf.insert)) > 1e-6:
                continue
            labels.append({'label': label, 'handle': e.dxf.handle,
                           'position': list(e.dxf.insert)[:2],
                           'height': float(e.dxf.height if e.dxftype() == 'TEXT' else e.dxf.char_height)})
        arrows = []
        for arrow in triangles(plan):
            if raw_arrows.get(arrow['handle']) == arrow:
                arrows.append(arrow)
        for pair in pair_callouts(labels, arrows):
            plan_matches[pair['label']].append({**pair,
                'plan_source_id': source.source_id, 'plan_revision': source.revision,
                'origin_source_id': raw_reference['source_id'], 'origin_revision': raw_reference['revision']})
    for name, matches in plan_matches.items():
        unique_count = sum(p['status'] == 'unique_plan_callout_pair' for p in matches)
        entries = named[name]
        for entry, title in entries:
            for pair in matches:
                status = ('ambiguous_section_titles' if len(entries) != 1 else
                          'ambiguous_plan_towers' if unique_count > 1 else pair['status'])
                entry.setdefault('plan_callout_links', []).append({**pair, 'status': status,
                    'title_handle': title['title_handle']})


def enrich_pillar_axis_candidates(auxiliary, inventory):
    """Trace finite plan axes through actual footprints, without projecting levels.

    Crossing a footprint proves a spatial candidate only. The section must still
    establish the item identity, storey and vertical region before any numeric use.
    Tangency, ambiguous names and another source cannot establish a candidate.
    """
    from shapely.geometry import LineString, Point, Polygon
    for entry in auxiliary:
        for link in entry.get('plan_callout_links', []):
            if (link.get('status') != 'unique_plan_callout_pair'
                    or link.get('plan_source_id') != inventory.get('source_id')):
                continue
            start, end = link['bounded_axis']
            dx, dy = end[0]-start[0], end[1]-start[1]
            length2 = dx*dx + dy*dy
            if length2 <= 0:
                continue
            axis = LineString([start, end])
            candidates = []
            for item in inventory.get('items', []):
                geometry = item.get('geometry') or {}
                handles = item.get('source_entity_handles') or []
                if item.get('status') != 'linked' or not handles:
                    continue
                if geometry.get('type') == 'Polygon':
                    polygon = Polygon(geometry['coordinates'][0])
                    if not polygon.is_valid or polygon.area <= 0:
                        continue
                    intersection = axis.intersection(polygon)
                    # Boundary-aligned axes and tangent points are not interior cuts.
                    interior = intersection.difference(polygon.boundary)
                    if interior.length <= 0:
                        continue
                    parts = list(interior.geoms) if hasattr(interior, 'geoms') else [interior]
                    intervals = []
                    for part in parts:
                        if part.geom_type != 'LineString' or part.length <= 0:
                            continue
                        bounds = [axis.project(Point(x, y)) / math.sqrt(length2) for x, y in part.coords]
                        intervals.append([max(0., min(bounds)), min(1., max(bounds))])
                    if not intervals:
                        continue
                elif geometry.get('type') == 'Circle':
                    cx, cy = geometry['center']
                    radius = geometry['radius']
                    if radius <= 0:
                        continue
                    fx, fy = start[0]-cx, start[1]-cy
                    b = 2*(fx*dx+fy*dy)
                    discriminant = b*b-4*length2*(fx*fx+fy*fy-radius*radius)
                    if discriminant <= 0:
                        continue
                    lower = max(0., (-b-math.sqrt(discriminant))/(2*length2))
                    upper = min(1., (-b+math.sqrt(discriminant))/(2*length2))
                    if upper <= lower:
                        continue
                    intervals = [[lower, upper]]
                else:
                    continue
                candidates.append({'item_id': item['item_id'], 'display_name': item['display_name'],
                    'source_entity_handles': handles, 'axis_intervals': sorted(intervals),
                    'status': 'plan_footprint_intersection_only',
                    'authority': 'bounded_axis_and_source_footprint',
                    'section_identity_status': 'unresolved', 'numeric_authority': 'none'})
            link['pillar_axis_candidates'] = sorted(candidates, key=lambda row: row['axis_intervals'][0][0])
