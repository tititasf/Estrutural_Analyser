"""Striped CAD regions: evidence of a transition, never proof of its altitude.

Only real boundary segments close a region. Parallel repeated strokes confirm
the pattern but never participate in polygonization.
"""
import math
import hashlib
from collections import defaultdict
from shapely.strtree import STRtree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely import set_precision


def striped_regions(items, structural_lines):
    groups = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        pts = item.get('points') or ([item['start'], item['end']]
                                    if 'start' in item and 'end' in item else [])
        key = (item.get('layer'), item.get('linetype'), str(item.get('aci', item.get('color'))))
        for a, b in zip(pts, pts[1:]):
            line = set_precision(LineString([a[:2], b[:2]]), .001)
            if line.length > 1e-6:
                groups[key].append(line)
    regions = []
    for key, lines in groups.items():
        # Diagonal repeated strokes, distinct from axis-aligned delimiting lines.
        diagonals = defaultdict(list)
        delimiters = []
        for line in lines:
            a, b = line.coords[0], line.coords[-1]
            dx, dy = b[0]-a[0], b[1]-a[1]
            angle = math.atan2(dy, dx) % math.pi
            if min(abs(dx), abs(dy)) <= 1e-5:
                delimiters.append(line)
            else:
                diagonals[round(angle, 4)].append(line)
        if not delimiters:
            continue
        cells = list(polygonize(unary_union(list(structural_lines)+delimiters)))
        stroke_indexes = {angle: STRtree(strokes) for angle, strokes in diagonals.items()}
        for cell in cells:
            if not cell.is_valid or cell.interiors or cell.area <= 100:
                continue
            for angle, strokes in diagonals.items():
                # A drafter may continue hatch strokes across a support. Clip
                # the evidence to each independently closed structural cell.
                # Bounding boxes only exclude impossible intersections. Keep
                # source order and the exact original geometric predicates.
                hits = []
                for index in sorted(stroke_indexes[angle].query(cell)):
                    hit = strokes[index].intersection(cell)
                    if hit.geom_type == 'LineString' and hit.length > .01:
                        hits.append(hit)
                if len(hits) < 3:
                    continue
                offsets = sorted(set(round(-math.sin(angle)*s.centroid.x+
                                           math.cos(angle)*s.centroid.y, 3) for s in hits))
                gaps = [b-a for a,b in zip(offsets, offsets[1:]) if b-a > .01]
                if len(gaps) < 2:
                    continue
                pitch = sorted(gaps)[len(gaps)//2]
                if sum(abs(g-pitch) <= max(.02, pitch*.05) for g in gaps) < len(gaps)*.8:
                    continue
                # A separator must actually touch this cell, not another room.
                if not any(cell.boundary.intersection(d).length > .01 for d in delimiters):
                    continue
                uid = hashlib.sha256(cell.normalize().wkb).hexdigest()[:16]
                regions.append(dict(uid='striped-region:'+uid,
                    points=list(cell.exterior.coords), layer=key[0],
                    pattern='parallel_repeated_strokes', stroke_count=len(hits),
                    pitch=pitch, status='unknown', method='striped_closed_cad_region',
                    color='#ffe033', evidence_lines=[list(s.coords) for s in hits],
                    attention_reason='possible_level_or_thickness_transition'))
                break
    return list({r['uid']:r for r in regions}.values())


def scoped_thickness(face, seeds, regions):
    """Distinct thicknesses need disjoint, independently bounded CAD regions."""
    contained = [(t,h) for t,h in seeds if face.contains(Point(t['pos']))]
    local = []
    for region in regions:
        shape = Polygon(region['points'])
        if shape.area >= face.area*.85:
            continue
        if face.buffer(.001).covers(shape):
            local.append(region)
            continue
        # A proven pillar notch can trim the corner of an otherwise enclosed
        # striped region. The intersection follows those real support edges;
        # large/unrelated partial regions are never attached to this slab.
        clipped = shape.intersection(face)
        if (clipped.geom_type == 'Polygon' and clipped.is_valid and not clipped.interiors
                and clipped.area > 100 and clipped.area >= shape.area*.95):
            uid = hashlib.sha256(clipped.normalize().wkb).hexdigest()[:16]
            local.append(dict(region, points=list(clipped.exterior.coords),
                uid='striped-region:'+uid, support_trimmed=True))
    principal = [(t,h) for t,h in contained if not any(
        Polygon(r['points']).covers(Point(t['pos'])) for r in local)]
    values = {h for t,h in principal}
    if len(values) != 1:
        return None
    height = next(iter(values))
    accepted = []
    for region in local:
        shape=Polygon(region['points'])
        inner = [(t,h) for t,h in contained if shape.covers(Point(t['pos']))]
        heights={h for t,h in inner}
        if len(heights) > 1:
            return None
        accepted.append(dict(region, height_cm=next(iter(heights)) if heights else None,
            owner_height_cm=height, level_m=None, owner_level_m=None,
            bottom_m=None, owner_bottom_m=None, bottom_delta_m=None, sections=[],
            evidence_handles=[], evidence_checks=dict(striped_pattern=True,
                closed_cad_boundary=True, internal_height=bool(heights),
                principal_height=True, direct_internal_level=False,
                direct_principal_level=False),
            source_positions=[list(t['pos']) for t,h in inner]))
    return principal, accepted


def name_generated_slabs(slabs, floor=None):
    """Reading order: horizontal rows from top to bottom, left to right.

    A row groups nearby top edges relative to the smaller slab's height.
    Ordering and identity do not depend on CAD entity enumeration.
    """
    remaining = list(slabs)
    ordered=[]
    while remaining:
        anchor=max(remaining,key=lambda s:Polygon(s['points']).bounds[3])
        a=Polygon(anchor['points']).bounds
        top=a[3]
        row=[]
        for slab in remaining:
            b=Polygon(slab['points']).bounds
            tolerance=max(.01,min(a[3]-a[1],b[3]-b[1])*.15)
            if b[3]>=top-tolerance:
                row.append(slab)
        row.sort(key=lambda s:(Polygon(s['points']).bounds[0], -Polygon(s['points']).bounds[3]))
        ordered.extend(row)
        ids={id(s) for s in row}
        remaining=[s for s in remaining if id(s) not in ids]
    for i,slab in enumerate(ordered,1):
        slab['name']=f'L{i}'
    return ordered
