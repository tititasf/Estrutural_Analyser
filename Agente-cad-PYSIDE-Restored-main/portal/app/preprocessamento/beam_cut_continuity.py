"""Keep slab datums separate from a geometrically anchored beam datum."""
from copy import deepcopy
import re

from shapely.geometry import box, LineString, shape


def fund_section(segment, fields, peers, source=None):
    section = _axis_fund_section(segment, fields, peers)
    if section is not None or not source:
        return section
    from .oriented_beam_section import source_section
    try:
        return source_section(segment.get('points'), segment.get('beam_name'), source)
    except (OSError, ValueError, TypeError):
        return None


def _axis_fund_section(segment, fields, peers):
    """Read a dimension only when its width and spatial segment agree."""
    from .segment_levels import geometry
    geom = geometry(segment.get('points'))
    if geom is None or geom.geom_type != 'Polygon':
        return None
    b = geom.bounds
    axis = 0 if b[2]-b[0] >= b[3]-b[1] else 1
    # A short end parcel can be shorter than the beam's transverse width.
    # Own lateral edges supply its longitudinal direction; bbox size cannot.
    supported_axes = set()
    for family, side in peers:
        if not family.startswith('lateral'):
            continue
        if (segment.get('beam_name') and side.get('beam_name')
                and segment['beam_name'] != side['beam_name']):
            continue
        line = geometry(side.get('points'))
        if line is None or line.geom_type != 'LineString' or line.length <= 0:
            continue
        lb = line.bounds
        direction = 0 if lb[2]-lb[0] >= lb[3]-lb[1] else 1
        if lb[3-direction]-lb[1-direction] > .1:
            continue
        span = b[direction+2]-b[direction]
        if span > .1 and line.intersection(geom.boundary.buffer(.1)).length >= .8*span:
            supported_axes.add(direction)
    if len(supported_axes) > 1:
        return None  # Ambiguous branches do not certify a dimension.
    if supported_axes:
        axis = next(iter(supported_axes))
    width = b[3-axis]-b[1-axis]
    length = b[axis+2]-b[axis]
    def section_dim(value):
        match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*', str(value or ''))
        if not match:
            return None
        w, depth = [float(v.replace(',', '.')) for v in match.groups()]
        return depth if abs(w-width) <= .25 and depth > 0 else None
    slot = 'viga_fundo_seg_'+str(segment.get('segment_label'))+'_dim'
    own = section_dim(fields.get(slot))
    if own is not None:
        return dict(height_cm=own, section_source=slot)
    candidates = set()
    sources = []
    for family, side in peers:
        if not family.startswith('lateral'):
            continue
        line = geometry(side.get('points'))
        if line is None or line.intersection(geom.buffer(.1)).length < .8*length:
            continue
        for section in ((side.get('details') or {}).get('lv_cell') or {}).get('sections') or []:
            depth = section_dim(section.get('dim'))
            try:
                start, end = sorted([float(section['start']), float(section['end'])])
            except (KeyError, TypeError, ValueError):
                continue
            overlap = max(0, min(end,b[axis+2])-max(start,b[axis]))
            if depth is not None and overlap >= .8*length:
                candidates.add(depth)
                sources.append(side.get('uid'))
    if len(candidates) == 1:
        return dict(height_cm=candidates.pop(), section_source='spatial_lateral_section',
                    section_segment_ids=sorted({s for s in sources if s}))
    return None


def paint_regions(path):
    """Conservative blocker: a fill inside a fund requires separate review."""
    if not path:
        return None
    import ezdxf
    from ezdxf import bbox
    try:
        doc = ezdxf.readfile(path)
        result = []
        for entity in doc.modelspace().query('HATCH SOLID TRACE'):
            bounds = bbox.extents([entity])
            if bounds.has_data:
                result.append(box(bounds.extmin.x, bounds.extmin.y,
                                  bounds.extmax.x, bounds.extmax.y))
        return result
    except (OSError, ezdxf.DXFError):
        return None


def scoped_cut_profile(cut, slab):
    """The actual slab h must agree with the interpreted section wing."""
    ficha = cut.get('ficha') or {}
    match = re.search(r'h\s*=\s*(\d+(?:[.,]\d+)?)',
                      str(slab.get('fields', {}).get('laje_dim', '')), re.I)
    try:
        height = float(match.group(1).replace(',', '.')) if match else None
        wing = float(ficha.get('own_slab_height'))
    except (TypeError, ValueError):
        return None
    if height is None or abs(height-wing) > .25:
        return None
    points = cut.get('original_pts') or cut.get('points')
    from .segment_levels import geometry
    profile = geometry(points)
    if profile is None or profile.geom_type != 'Polygon':
        return None
    from shapely.geometry import mapping
    return mapping(profile)


def propagate(funds, sides, records, shapes, paints, inherit, sync):
    """A straight canonical lateral scopes continuous equal-section funds.

    Slab-contact guesses cannot veto a measured beam-cut datum. Conflicting
    cuts, human levels, depth/width changes and unreviewed fills do veto it.
    Frozen anchors prevent inferred levels from certifying themselves.
    """
    if paints is None:
        return
    frozen = deepcopy(records)
    for side in sorted(sides, key=lambda s: shapes[s['segment_id']].length
                       if shapes.get(s['segment_id']) is not None else 0, reverse=True):
        line = shapes.get(side['segment_id'])
        if line is None or line.geom_type != 'LineString' or line.length <= 0:
            continue
        straight = LineString([line.coords[0], line.coords[-1]])
        if abs(straight.length-line.length) > .1:
            continue
        horizontal = abs(line.coords[-1][0]-line.coords[0][0]) > abs(line.coords[-1][1]-line.coords[0][1])
        axis = 0 if horizontal else 1
        group = []
        for fund in funds:
            geom = shapes.get(fund['segment_id'])
            if geom is None or geom.geom_type != 'Polygon':
                continue
            hit = line.intersection(geom.buffer(.1))
            bounds = geom.bounds
            length = bounds[axis+2]-bounds[axis]
            if hit.length >= .8*length and length > 1:
                group.append(fund)
        if len(group) < 2:
            continue
        widths = [shapes[f['segment_id']].bounds[3-axis]-shapes[f['segment_id']].bounds[1-axis] for f in group]
        sections = ((side.get('details') or {}).get('lv_cell') or {}).get('sections') or []
        section_depths = {s.get('depth') for s in sections}
        section_widths = set()
        for section in sections:
            match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*', str(section.get('dim', '')))
            if match:
                section_widths.add(float(match.group(1).replace(',', '.')))
        fallback = next(iter(section_depths)) if len(section_depths) == 1 and None not in section_depths else None
        if (fallback is not None and (len(section_widths) != 1
                or abs(next(iter(section_widths))-widths[0]) > .25)):
            continue
        depths = [f.get('height_cm') or fallback for f in group]
        if any(d is None for d in depths) or max(depths)-min(depths) > .25 or max(widths)-min(widths) > .25:
            continue
        if any(p.intersection(shapes[f['segment_id']].buffer(-.25)).area > 2
               for f in group for p in paints):
            continue
        sources = [frozen[f['segment_id']] for f in group]
        if any(s.get('status') == 'conflict' for s in sources):
            continue
        cuts = [s for s in sources if s.get('method') == 'cut_geometry_on_fv']
        if not cuts or any(s.get('value') is None for s in cuts):
            continue
        if max(s['value'] for s in cuts)-min(s['value'] for s in cuts) > .0025:
            continue
        anchors = []
        for fund in group:
            source = frozen[fund['segment_id']]
            profile = source.get('cut_profile_geometry')
            if source.get('method') != 'cut_geometry_on_fv' or not profile:
                continue
            # Numeric height has authority only with a traced physical binding;
            # the same validator preserves footprint, width and stem shape.
            from .segment_levels import cut_matches_fund
            depth = depths[group.index(fund)]
            if cut_matches_fund(profile, shapes[fund['segment_id']], depth,
                                source.get('cut_height_evidence')):
                anchors.append(source)
        if not anchors:
            continue
        value = anchors[0]['value']
        if any(s.get('status') == 'human_review' and abs(s['value']-value) > .0025 for s in sources):
            continue
        # Use the strongest independent cut; weaker agreeing observations are
        # corroboration, not artificial confidence amplification.
        anchor = max(anchors, key=lambda s: s['confidence_pct'])
        height_authority = anchor.get('cut_height_evidence')
        anchor_fund = next(f for f in group if frozen[f['segment_id']] is anchor)
        anchor_stem = shape(anchor['cut_profile_geometry']).intersection(
            shapes[anchor_fund['segment_id']])
        measured_depth = anchor_stem.bounds[axis+2]-anchor_stem.bounds[axis]
        for fund in group:
            uid = fund['segment_id']
            current = records[uid]
            if current.get('status') == 'human_review' or current.get('method') == 'cut_geometry_on_fv':
                continue
            result = inherit(current, [anchor], 'cut_anchored_constant_beam_section', .95,
                value=value, continuity_segment_id=side['segment_id'],
                measured_width_cm=widths[0], measured_depth_cm=measured_depth,
                declared_height_cm=depths[0],
                section_height_authority=deepcopy(height_authority),
                previous_level_evidence=deepcopy(frozen[uid]),
                agreeing_cut_fact_ids=[s['fact_id'] for s in anchors])
            current.update(result)
            sync(fund, current)
