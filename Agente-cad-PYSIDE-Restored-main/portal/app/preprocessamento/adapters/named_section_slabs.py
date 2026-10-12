"""Transfer a labelled storey's section wings to bounded plan regions.

The section ordinate, pillar identity, cut width and slab thickness must all
agree. A floor reference alone never supplies a slab level. CAD is read-only.
"""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re

from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import unary_union

METHOD = 'named_section_marker_and_plan_region'
TOL = .01


def wings(points, y, cut_width):
    """Closed T section: upper stem and two rectangular wings at the marker."""
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.area <= 0:
        return []
    x0, _, x1, ymax = polygon.bounds
    if ymax <= y+cut_width:
        return []
    stems = polygon.intersection(LineString([(x0-1, y+cut_width), (x1+1, y+cut_width)]))
    if stems.geom_type != 'LineString' or abs(stems.length-cut_width) > TOL:
        return []
    left, right = stems.bounds[0], stems.bounds[2]
    result = []
    for a, b, side in ((x0, left, -1), (right, x1, 1)):
        if b-a <= cut_width:
            return []
        middle = (a+b)/2
        section = polygon.intersection(LineString([(middle, polygon.bounds[1]-1), (middle, ymax+1)]))
        if section.geom_type != 'LineString' or abs(section.bounds[3]-y) > TOL:
            return []
        bottom = section.bounds[1]
        # The whole wing must be rectangular, not a slope or stepped schematic.
        from shapely.geometry import box
        expected = box(a, bottom, b, y)
        actual = polygon.intersection(box(a, polygon.bounds[1]-1, b, y))
        if expected.symmetric_difference(actual).area > TOL:
            return []
        result.append({'side': side, 'x_interval': [a, b], 'height': y-bottom,
                       'stem_interval': [left, right]})
    return result


def project_wing(link, candidate, wing, scale):
    """Section horizontal direction follows the paired arrows, never proximity."""
    start, end = link['bounded_axis']
    length = math.dist(start, end)
    if not math.isfinite(length) or not math.isfinite(scale) or length <= 0 or scale <= 0 or len(candidate['axis_intervals']) != 1:
        return None
    lo, hi = candidate['axis_intervals'][0]
    if abs((hi-lo)*length-(wing['stem_interval'][1]-wing['stem_interval'][0])*scale) > TOL:
        return None
    direction = [(end[k]-start[k])/length for k in (0, 1)]
    view = link['view_direction']
    right = [-view[1], view[0]]
    dot = sum(a*b for a, b in zip(direction, right))
    if abs(abs(dot)-1) > .005:
        return None
    center = (lo+hi)*length/2
    section_center = sum(wing['stem_interval'])/2
    intervals = sorted(center+(x-section_center)*scale*dot for x in wing['x_interval'])
    a, b = max(0., intervals[0]), min(length, intervals[1])
    if b-a <= TOL:
        return None
    return LineString([[start[k]+t*direction[k] for k in (0, 1)] for t in (a, b)])


def resolve_named_section_slabs(root, package, context):
    import ezdxf
    root = Path(root).resolve()
    reference = package['level_inventory']['reference']
    if reference.get('status') != 'direct_local_reference' or reference.get('unit') != 'm':
        return []
    floor = (reference.get('floor_selection') or {}).get('representative_floor')
    # Older packages use the explicit selected-floor field in the reference.
    floor = floor or reference.get('representative_floor')
    if floor is None:
        return []
    sources = {s['source_id']: s for s in package['sources']}
    tower = sources.get(package['scope']['recorte_id'])
    if not tower or hashlib.sha256(Path(context['tower_path']).read_bytes()).hexdigest() != tower['revision']:
        return []
    items = {(i['display_name'], i['item_id']): i for i in package['pillars']['items']}
    assignments = []
    for entry in package.get('auxiliary_evidence', []):
        profile = entry.get('section_vertical_levels') or {}
        if profile.get('status') != 'calibrated_section_only':
            continue
        links = [l for l in entry.get('plan_callout_links', []) if l.get('status') == 'unique_plan_callout_pair']
        if len(links) != 1 or links[0]['plan_source_id'] != tower['source_id'] or links[0]['plan_revision'] != tower['revision']:
            continue
        source = sources.get(entry['source_id'])
        if not source or source['revision'] != profile['source_revision']:
            continue
        path = (root/source['relative_path']).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != source['revision']:
            continue
        anchors = [a for a in profile['anchors'] if re.match(r'^\s*'+str(floor)+r'\D', a['floor_label'])
                   and abs(a['value_m']-reference['top']) <= .0025]
        if len(anchors) != 1:
            continue
        anchor = anchors[0]
        scale = profile['meters_per_drawing_unit']*100  # plan canonical coordinates are cm
        if not math.isfinite(scale) or scale <= 0:
            continue
        doc = ezdxf.readfile(path)
        from .section_vertical_levels import _tip, calibrate_vertical_levels
        verified = []
        for marker in profile['anchors']:
            convention = next((r for r in (entry.get('level_convention') or {}).get('direct_floor_levels', [])
                               if r.get('floor_text_handle') == marker['floor_text_handle']), {})
            unit = (convention.get('selected') or {}).get('unit')
            if unit not in ('m', 'cm'):
                break
            entity = doc.entitydb.get(marker['text_handle'])
            floor_entity = doc.entitydb.get(marker['floor_text_handle'])
            tip = _tip(doc.entitydb.get(marker['marker_handle']))
            try:
                if (not tip or tip['position'] != marker['position'] or tip['width'] != marker['width']
                        or entity.dxftype() != 'TEXT' or floor_entity.dxftype() != 'TEXT'
                        or floor_entity.dxf.text != marker['floor_label']
                        or abs(float(entity.dxf.text.replace(',', '.'))/(100 if unit == 'cm' else 1)-marker['value_m']) > 1e-8):
                    break
            except (AttributeError, ValueError):
                break
            verified.append(marker)
        fresh = calibrate_vertical_levels(verified)
        if (len(verified) != len(profile['anchors']) or fresh.get('status') != 'calibrated_section_only'
                or abs(fresh['meters_per_drawing_unit']-profile['meters_per_drawing_unit']) > 1e-10):
            continue
        link = links[0]
        candidates = link.get('pillar_axis_candidates', [])
        # Multiple pillars require a full horizontal registration, not a guess.
        if len(candidates) != 1:
            continue
        candidate = candidates[0]
        item = items.get((candidate['display_name'], candidate['item_id']))
        if not item:
            continue
        axis_width = math.dist(*link['bounded_axis'])*sum(b-a for a, b in candidate['axis_intervals'])
        labels = [t for t in entry['texts'] if t['text'] == candidate['display_name']
                  and anchor['position'][1] < t['position'][1] < anchor['position'][1]+axis_width*10/scale]
        pairs = []
        for label in labels:
            dimensions = [t for t in entry['texts'] if re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?-[A-Z]', t['text'])
                          and abs(t['position'][0]-label['position'][0]) < TOL
                          and 0 < label['position'][1]-t['position'][1] < label['height']*2]
            if len(dimensions) == 1:
                pairs.append((label, dimensions[0]))
        if len(pairs) != 1:
            continue
        label, dimension = pairs[0]
        if any(doc.entitydb.get(t['handle']) is None
               or doc.entitydb[t['handle']].dxftype() != 'TEXT'
               or doc.entitydb[t['handle']].dxf.text != t['text']
               or math.dist(list(doc.entitydb[t['handle']].dxf.insert)[:2], t['position'][:2]) > TOL
               for t in (label, dimension)):
            continue
        # Verify both dimensions against the actual plan footprint.
        shape = item.get('geometry') or {}
        if shape.get('type') != 'Polygon':
            continue
        plan = Polygon(shape['coordinates'][0])
        bounds = plan.bounds
        dims = sorted(float(v.replace(',', '.')) for v in dimension['text'].split('-')[0].split('/'))
        if any(abs(a-b) > TOL for a, b in zip(dims, sorted((bounds[2]-bounds[0], bounds[3]-bounds[1])))):
            continue
        sections = []
        for entity in doc.modelspace().query('POLYLINE LWPOLYLINE'):
            if entity.dxftype() == 'POLYLINE':
                if not entity.is_2d_polyline or any(v.dxf.get('bulge', 0) for v in entity.vertices):
                    continue
                points = [list(v.dxf.location)[:2] for v in entity.vertices]
            else:
                if any(p[4] for p in entity.get_points()):
                    continue
                points = [list(p)[:2] for p in entity.get_points()]
            if len(points) < 4 or not (entity.is_closed or points[0] == points[-1]):
                continue
            if tuple(entity.dxf.get('extrusion', (0, 0, 1))) != (0, 0, 1):
                continue
            found = wings(points, anchor['position'][1], axis_width/scale)
            if not found:
                continue
            # Label and its dimension must be alongside the upper stem.
            stem = found[0]['stem_interval']
            if min(abs(label['position'][0]-x) for x in stem) > label['height']*6:
                continue
            # Require a real leader from this label to this stem. Nearby text
            # or a matching dimension alone cannot identify the concrete body.
            leaders = []
            for leader in doc.modelspace().query('POLYLINE LWPOLYLINE'):
                if leader.is_closed:
                    continue
                if leader.dxftype() == 'POLYLINE':
                    if not leader.is_2d_polyline:
                        continue
                    vertices = [list(v.dxf.location)[:2] for v in leader.vertices]
                else:
                    vertices = [list(p)[:2] for p in leader.get_points()]
                if len(vertices) < 2:
                    continue
                near_label = math.dist(vertices[0], label['position'][:2]) < label['height']
                hits_stem = any(min(abs(p[0]-x) for x in stem) < TOL
                                and anchor['position'][1]+axis_width/scale < p[1] < Polygon(points).bounds[3]
                                for p in vertices[1:])
                if near_label and hits_stem:
                    leaders.append(leader.dxf.handle)
            if len(leaders) != 1:
                continue
            # Filled outlines alone cannot substitute for the structural edges.
            structural = [LineString([list(e.dxf.start)[:2], list(e.dxf.end)[:2]])
                          for e in doc.modelspace().query('LINE')
                          if not re.search(r'COTA|DIM|EIXO|AXIS', e.dxf.layer, re.I)]
            if any(not any(line.distance(LineString([(w['x_interval'][0], anchor['position'][1]),
                                                     (w['x_interval'][1], anchor['position'][1])])) < TOL
                               and line.intersection(LineString([(w['x_interval'][0], anchor['position'][1]),
                                                                (w['x_interval'][1], anchor['position'][1])])).length >=
                                   w['x_interval'][1]-w['x_interval'][0]-TOL
                           for line in structural) for w in found):
                continue
            sections.append((entity.dxf.handle, found, leaders[0]))
        if len(sections) != 1:
            continue
        handle, found, leader_handle = sections[0]
        for wing in found:
            trace = project_wing(link, candidate, wing, scale)
            if trace is None:
                continue
            for slab in context['state'].get('slabs', []):
                thickness = re.search(r'h\s*=\s*(\d+(?:[.,]\d+)?)', (slab.get('fields') or {}).get('laje_dim', ''))
                if not thickness or abs(float(thickness[1].replace(',', '.'))-wing['height']*scale) > TOL:
                    continue
                whole = Polygon(slab['points']).buffer(0)
                steps = [Polygon(s['points']).buffer(0) for s in slab.get('slab_steps', []) if s.get('points')]
                principal = whole.difference(unary_union(steps)) if steps else whole
                overlap = trace.intersection(principal).difference(principal.boundary)
                if overlap.length <= axis_width:
                    continue
                assignments.append({'name': slab['name'], 'value': anchor['value_m'], 'unit': 'm',
                    'method': METHOD, 'target_geometry': mapping(whole), 'region_geometry': mapping(principal),
                    'section_source_id': source['source_id'], 'section_revision': source['revision'],
                    'marker_handle': anchor['marker_handle'], 'section_geometry_handle': handle,
                    'evidence_ids': [source['source_id'], 'cad:'+anchor['marker_handle'], 'cad:'+anchor['text_handle'],
                                     'cad:'+handle, 'cad:'+label['handle'], 'cad:'+dimension['handle'], 'cad:'+leader_handle,
                                     *['cad:'+h for h in candidate['source_entity_handles']]],
                    'projection': mapping(trace), 'confidence_pct': 90,
                    'independent_origin': source['source_id']+':'+anchor['marker_handle']})
    return assignments


def attach_named_section_facts(items, assignments, reference):
    """Conflict-aware seed facts; never silently overwrite another source."""
    for row in assignments:
        matches = [i for i in items if i['item_class'] == 'slab' and i['display_name'] == row['name']]
        if len(matches) != 1:
            continue
        item = matches[0]
        competing = [f for f in item['levels'] if f.get('field') in ('slab_level', 'slab_level_candidate')
                     and f.get('value') is not None and abs(f['value']-row['value']) > .0025]
        competing += [r for r in assignments if r['name'] == row['name'] and abs(r['value']-row['value']) > .0025]
        item['levels'].append({**deepcopy(row), 'item_id': item['item_id'],
            'fact_id': item['item_id']+':named-section:'+row['marker_handle'],
            'field': 'slab_level', 'status': 'conflict' if competing else 'sa_evidence',
            'datum_id': reference.get('datum_id'), 'warnings': ['conflicting_level_evidence'] if competing else [],
            'source_fact_ids': []})
        if row.get('region_geometry'):
            fact = deepcopy(item['levels'][-1])
            fact.update(field='slab_region_level', region_id='principal',
                        fact_id=fact['fact_id']+':principal')
            regional = [f for f in item['levels'] if f.get('field') == 'slab_region_level'
                        and f.get('region_id') == 'principal' and f.get('value') is not None]
            if any(abs(f['value']-row['value']) > .0025 for f in regional):
                fact.update(status='conflict', warnings=['conflicting_level_evidence'])
            item['levels'].append(fact)
