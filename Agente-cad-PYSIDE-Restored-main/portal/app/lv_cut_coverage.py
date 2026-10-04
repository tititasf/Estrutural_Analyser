"""Place SA occurrences on soffit segments; N3 equivalence is unrelated."""
from copy import deepcopy
from math import dist

from shapely.geometry import LineString, Point, Polygon

from .lv_cut_map import pair_polygon, section_drawings
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError


def soffit_drawings(cuts, sides, fundos, pillars=()):
    if not fundos:
        drawings, blocked = section_drawings(cuts, sides, pillars)
        return drawings, blocked, []
    bottoms = [(s, Polygon(s['points'])) for s in fundos
               if len(s.get('points') or []) >= 3]
    b_segments = {s['id']: s for s in sides['B']['segments']}
    originals, candidates, blocked = [], [], []
    original_by_bottom = {}
    for index, cut in enumerate(cuts):
        if cut['kind'] == 'identified':
            rendered, failures = section_drawings([cut], sides, pillars)
            blocked.extend(dict(f, cut_index=index) for f in failures)
            for drawing in rendered:
                drawing['cut_index'] = index
                originals.append(drawing)
                center = Point(drawing['anchor'])
                matches = [(poly.centroid.distance(center), s['uid']) for s, poly in bottoms
                           if poly.buffer(.15).covers(center)]
                if matches:
                    uid = min(matches)[1]
                    original_by_bottom.setdefault(uid, []).append(index)
                    drawing['fundo_id'] = uid
            continue
        for pair in cut.get('pairs') or []:
            try:
                quad = pair_polygon(pair, b_segments[pair['b_id']])
                delta = [(quad[3][i]-quad[0][i])/2 for i in (0, 1)]
                line = LineString([[p[i]+delta[i] for i in (0, 1)]
                                   for p in (pair['start'], pair['end'])])
                candidates.append((index, pair, line, delta))
            except (ValueError, KeyError) as exc:
                blocked.append(dict(cut_index=index, reason=str(exc)))
    instances, source_indexes, coverage = [], [], []
    for segment, polygon in bottoms:
        uid = segment['uid']
        row = dict(fundo_id=uid, beam=segment.get('beam_name'),
                   segment=segment.get('segment_label'))
        if uid in original_by_bottom:
            original_indexes = original_by_bottom[uid]
            known = [build_cut_contract(cuts[i]) for i in original_indexes]
            dimensions = {(c['width_cm'], c['height_cm']) for c in known}
            changes = []
            for index, pair, line, delta in candidates:
                if polygon.intersection(line).length <= .5:
                    continue
                candidate = cuts[index]
                width, height = candidate.get('width_cm'), candidate.get('beam_height_cm')
                if width is not None and height is not None and not any(
                        abs(width-w) <= .5 and abs(height-h) <= .5 for w,h in dimensions):
                    changes.append(index)
            # A point occurrence cannot certify a whole soffit containing a
            # measured profile transition. Keep the original drawing visible;
            # expose subdivision instead of silently hiding the other profile.
            if changes or len(dimensions) > 1:
                coverage.append(dict(row, status='pending', cut_indexes=original_indexes,
                    profile_change_indexes=changes,
                    reason='fundo atravessa mudança de seção; original preservado, subdivisão necessária'))
            else:
                coverage.append(dict(row, status='original', cut_indexes=original_indexes))
            continue
        choices = []
        reasons = []
        for index, pair, line, delta in candidates:
            intersection = polygon.intersection(line)
            for part in getattr(intersection, 'geoms', [intersection]):
                if part.geom_type != 'LineString' or part.length <= .5:
                    continue
                try:
                    build_cut_contract(cuts[index])
                except CutContractError as exc:
                    reasons.append(str(exc))
                    continue
                choices.append((part.distance(polygon.centroid), -part.length,
                                index, pair, part, delta))
        if not choices:
            coverage.append(dict(row, status='pending', reason='; '.join(sorted(set(reasons))) or 'sem par A/B válido neste fundo'))
            continue
        _, _, index, pair, part, delta = min(choices, key=lambda c:c[:3])
        clipped = deepcopy(pair)
        pts = list(part.coords)
        # Preserve the A-face reading direction when clipping at the soffit.
        if dist(pts[0], line_start := [pair['start'][i]+delta[i] for i in (0,1)]) > dist(pts[-1], line_start):
            pts.reverse()
        clipped.update(start=[pts[0][i]-delta[i] for i in (0,1)],
                       end=[pts[-1][i]-delta[i] for i in (0,1)], length_cm=part.length)
        cut = deepcopy(cuts[index])
        cut['pairs'] = [clipped]
        instances.append(cut)
        source_indexes.append((index, uid))
        coverage.append(dict(row, status='interpreted', cut_index=index))
    drawings, failures = section_drawings(instances, sides, pillars)
    for drawing in drawings:
        index, uid = source_indexes[drawing['cut_index']]
        drawing.update(cut_index=index, fundo_id=uid)
        originals.append(drawing)
    for failure in failures:
        index, uid = source_indexes[failure['cut_index']]
        blocked.append(dict(failure, cut_index=index, fundo_id=uid))
        next(r for r in coverage if r['fundo_id'] == uid).update(status='pending', reason=failure['reason'])
    # Titles retain the same VC identity in repeated physical occurrences.
    for drawing in originals:
        cut = cuts[drawing['cut_index']]
        contract = build_cut_contract(cut)
        for primitive in drawing['primitives']:
            if primitive.get('role') == 'section_title':
                primitive['text'] = (f'{cut["beam"]} - VC{drawing["cut_index"]+1} - '
                                     f'({contract["width_cm"]:g}/{contract["height_cm"]:g})')
    return originals, blocked, coverage
