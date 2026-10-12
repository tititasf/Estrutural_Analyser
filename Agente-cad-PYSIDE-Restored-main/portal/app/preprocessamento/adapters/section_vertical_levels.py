"""Bounded vertical datum in a named section; never an item-level assignment.

The elevation is at the triangle tip, not at the numeric text insertion.
Only a unique column of explicit markers can calibrate the section ordinate.
"""
import hashlib
import math
from pathlib import Path


def _tip(entity):
    if entity is None or entity.dxftype() not in {'POLYLINE', 'LWPOLYLINE'}:
        return None
    if tuple(entity.dxf.get('extrusion', (0, 0, 1))) != (0, 0, 1):
        return None
    if entity.dxftype() == 'POLYLINE':
        if not entity.is_2d_polyline:
            return None
        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        bulges = [v.dxf.get('bulge', 0) for v in entity.vertices]
    else:
        points = [(p[0], p[1]) for p in entity.get_points()]
        bulges = [p[4] for p in entity.get_points()]
    if any(bulges):
        return None
    closed = entity.is_closed or (len(points) == 4 and points[0] == points[-1])
    if len(points) == 4 and points[0] == points[-1]:
        points = points[:-1]
    if not closed or len(points) != 3:
        return None
    tip, a, b = sorted(points, key=lambda p: p[1])
    width, height = abs(b[0]-a[0]), a[1]-tip[1]
    if (height <= 0 or abs(a[1]-b[1]) > height*.02
            or not .5 <= width/height <= 2
            or abs((a[0]+b[0])/2-tip[0]) > width*.05):
        return None
    return {'position': list(tip), 'width': width}


def calibrate_vertical_levels(anchors):
    """No extrapolation, mixed columns, duplicate datums or inconsistent scale."""
    result = {'schema': 'cad.section.vertical-levels/v1', 'status': 'unresolved',
              'item_numeric_authority': 'none', 'independent_vote_count': 0,
              'anchors': anchors, 'reason': 'insufficient_explicit_markers'}
    if len(anchors) < 2:
        return result
    if any(not all(math.isfinite(v) for v in [a['value_m'], *a['position'], a['width']])
           or a['width'] <= 0 for a in anchors):
        result['reason'] = 'invalid_marker_geometry_or_value'
        return result
    anchors = sorted(anchors, key=lambda a: a['position'][1])
    result['anchors'] = anchors
    if len({a['marker_handle'] for a in anchors}) != len(anchors):
        result['reason'] = 'duplicate_marker_ownership'
        return result
    if any(abs(a['position'][0]-b['position'][0]) > min(a['width'], b['width'])*.1
           for a in anchors for b in anchors):
        result['reason'] = 'multiple_marker_columns'
        return result
    first, last = anchors[0], anchors[-1]
    dy = last['position'][1]-first['position'][1]
    dz = last['value_m']-first['value_m']
    if dy <= 0 or dz <= 0:
        result['reason'] = 'non_increasing_vertical_datum'
        return result
    scale = dz/dy
    for a, b in zip(anchors, anchors[1:]):
        interval = b['position'][1]-a['position'][1]
        rise = b['value_m']-a['value_m']
        if interval <= 0 or rise <= 0 or abs(rise/interval-scale) > scale*.005:
            result['reason'] = 'inconsistent_vertical_scale'
            return result
    result.update(status='calibrated_section_only', reason=None,
                  meters_per_drawing_unit=scale,
                  y_bounds=[first['position'][1], last['position'][1]],
                  level_bounds_m=[first['value_m'], last['value_m']],
                  authority='explicit_geometric_elevation_markers',
                  datum_id='source-local-section')
    return result


def level_at_y(profile, y):
    """Source-section ordinate only. Callers must prove item/face ownership."""
    if profile.get('status') != 'calibrated_section_only' or not math.isfinite(y):
        return None
    lower, upper = profile['y_bounds']
    if not lower <= y <= upper:
        return None
    return profile['level_bounds_m'][0]+(y-lower)*profile['meters_per_drawing_unit']


def enrich_section_vertical_levels(obra_dir, sources, auxiliary):
    import ezdxf
    from .level_convention import extract_level_convention

    root = Path(obra_dir).resolve()
    by_id = {s.source_id: s for s in sources}
    for entry in auxiliary:
        links = [link for link in entry.get('plan_callout_links', [])
                 if link.get('status') == 'unique_plan_callout_pair']
        if not links:
            continue
        diagnostic = {'schema': 'cad.section.vertical-levels/v1', 'status': 'unresolved',
                      'item_numeric_authority': 'none', 'independent_vote_count': 0}
        entry['section_vertical_levels'] = diagnostic
        # An aggregate crop with two named cuts cannot share one vertical datum.
        if len(links) != 1 or len(entry.get('section_title_links', [])) != 1:
            diagnostic['reason'] = 'ambiguous_section_extent'
            continue
        source = by_id.get(entry['source_id'])
        if source is None or source.revision != entry.get('source_revision'):
            diagnostic['reason'] = 'stale_source_revision'
            continue
        path = (root/source.relative_path).resolve()
        if (not path.is_relative_to(root) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != source.revision):
            diagnostic['reason'] = 'source_content_changed'
            continue
        doc = ezdxf.readfile(path)
        fresh = extract_level_convention(path)
        fresh_rows = {row['floor_text_handle']: row for row in fresh['direct_floor_levels']}
        anchors = []
        invalid = False
        for row in (entry.get('level_convention') or {}).get('direct_floor_levels', []):
            selected = row.get('selected') or {}
            if row.get('status') != 'direct' or selected.get('method') != 'elevation_triangle':
                continue
            current = (fresh_rows.get(row['floor_text_handle']) or {}).get('selected') or {}
            if any(selected.get(k) != current.get(k)
                   for k in ('marker_handle', 'text_handle', 'value', 'raw', 'position')):
                invalid = True
                break
            unit = selected.get('unit')
            inherited = row.get('unit_provenance') or {}
            if unit not in {'m', 'cm'} or (unit != current.get('unit') and (
                    inherited.get('status') != 'confirmed_same_original_entities'
                    or inherited.get('unit') != unit)):
                invalid = True
                break
            marker = _tip(doc.entitydb.get(selected['marker_handle']))
            if marker is None:
                invalid = True
                break
            anchors.append({**marker, 'value_m': selected['value']/(100 if unit == 'cm' else 1),
                            'floor_label': row['floor_label'],
                            'floor_text_handle': row['floor_text_handle'],
                            'text_handle': selected['text_handle'],
                            'marker_handle': selected['marker_handle']})
        if invalid:
            diagnostic['reason'] = 'unverified_marker_or_unit'
            continue
        profile = calibrate_vertical_levels(anchors)
        profile.update(source_id=source.source_id, source_revision=source.revision,
                       section_title_handle=links[0]['title_handle'],
                       plan_source_id=links[0]['plan_source_id'],
                       plan_revision=links[0]['plan_revision'])
        profile['datum_id'] = 'source-local-section:'+source.source_id
        entry['section_vertical_levels'] = profile
