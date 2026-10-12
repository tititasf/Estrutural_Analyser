"""Conservative composition of source runs across one solid short support.

Returns new scenes for evaluation; callers must rebuild context before producing
cells. This module does not publish links or change frozen cells.
"""
from copy import deepcopy
import math

from shapely.geometry import box

from .lv_beam_scene import LvScene, _merge


def _complete_sections(run, tolerance):
    """Every part of the source span needs a finite positive measured section."""
    covered = run.start
    try:
        sections = sorted(run.sections, key=lambda z: float(z['start']))
        for section in sections:
            start, end = float(section['start']), float(section['end'])
            width, depth = float(section['width']), float(section['depth'])
            if (not all(math.isfinite(v) for v in (start, end, width, depth))
                    or end <= start or min(width, depth) <= 0
                    or start > covered + tolerance):
                return False
            covered = max(covered, end)
    except (KeyError, TypeError, ValueError):
        return False
    return bool(sections) and covered >= run.end - tolerance


def compose_short_support_runs(runs, pillars, *, tolerance_cm=.15):
    """Join only equal measured bands/sections with concordant slab references.

The bridge must be a single rectangular original pillar. Both free beam walls
must have source coverage. Hollow, diagonal, detached and ambiguous supports
remain separate, as do missing or conflicting level references.
"""
    result = list(runs)
    for left in sorted(list(result), key=lambda r: r.start):
        if left not in result or left.angle:
            continue
        candidates = []
        for right in result:
            if right is left or right.angle or left.beam_name != right.beam_name:
                continue
            if left.is_horizontal != right.is_horizontal or right.start <= left.end:
                continue
            if max(abs(left.t_lo-right.t_lo), abs(left.t_hi-right.t_hi)) > tolerance_cm:
                continue
            if not all(r.provenance.get('band_source') in {
                    'dxf_edges_from_own_label', 'source_walls_unlabelled_support_span'}
                    for r in (left, right)):
                continue
            sections = [z for r in (left, right) for z in r.sections]
            dims = {(z.get('dim'), z.get('depth'), z.get('width')) for z in sections}
            if len(dims) != 1 or not sections or any(v is None or v == '' for v in next(iter(dims))):
                continue
            if any(not _complete_sections(r, tolerance_cm) for r in (left, right)):
                continue
            if any(r.line_coverage(side, r.start, r.end) < .99
                   or r.dimension_overlap(side, r.start, r.end) > .01
                   for r in (left, right) for side in ('A', 'B')):
                continue
            signatures = []
            for run in (left, right):
                refs = [s for side in ('A', 'B') for s in run.slabs[side]]
                try:
                    signature = {(float(str(s['level']).replace(',', '.')), float(s['height'])) for s in refs}
                except (KeyError, TypeError, ValueError):
                    signature = set()
                if any(not math.isfinite(v) for pair in signature for v in pair):
                    signature = set()
                signatures.append(signature)
            if not signatures[0] or signatures[0] != signatures[1] or len(signatures[0]) != 1:
                continue
            bridge = (box(left.end, left.t_lo, right.start, left.t_hi)
                      if left.is_horizontal else box(left.t_lo, left.end, left.t_hi, right.start))
            supports = []
            for name, classification, poly in pillars:
                if poly.geom_type != 'Polygon' or poly.interiors or not poly.is_valid:
                    continue
                rectangle = box(*poly.bounds)
                if poly.symmetric_difference(rectangle).area > .01:
                    continue
                lo, hi = left.axis_bounds(poly)
                x0, y0, x1, y1 = poly.bounds
                transverse = y1-y0 if left.is_horizontal else x1-x0
                if hi-lo >= .8*transverse:
                    continue
                if max(abs(lo-left.end), abs(hi-right.start)) > tolerance_cm:
                    continue
                if not poly.buffer(tolerance_cm).covers(bridge):
                    continue
                supports.append((name, classification, poly))
            if len(supports) != 1:
                continue
            candidates.append((right, supports[0]))
        if len(candidates) != 1:
            continue
        right, support = candidates[0]
        joined = LvScene(left.beam_name, left.is_horizontal, left.t_lo, left.t_hi,
                         left.start, right.end)
        joined.labels = deepcopy(left.labels+right.labels)
        joined.sections = deepcopy(left.sections+right.sections)
        joined.sections.append(dict(start=left.end, end=right.start,
                                    dim=left.sections[0]['dim'], depth=left.sections[0]['depth'],
                                    width=left.sections[0]['width'],
                                    end_source='original_solid_short_support'))
        joined.sections.sort(key=lambda z: z['start'])
        for side in ('A', 'B'):
            joined.face_coverage[side] = _merge(left.face_coverage[side]+right.face_coverage[side])
            joined.dimension_coverage[side] = _merge(left.dimension_coverage[side]+right.dimension_coverage[side])
        joined.provenance = dict(band_source='original_short_support_composition',
                                 support=support[0],
                                 source_runs=[deepcopy(r.provenance) | {'start': r.start, 'end': r.end}
                                              for r in (left, right)],
                                 context_rebuild_required=True)
        result.remove(left)
        result.remove(right)
        result.append(joined)
    return result
