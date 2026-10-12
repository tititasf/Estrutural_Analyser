"""Replace legacy label-midpoint seams with measured full-width dividers."""
from copy import deepcopy
from math import dist


def reconcile_section_dividers(state, structural_lines, protected_uids=()):
    result = deepcopy(state)
    for key, rows in (result.get('segmentos') or {}).items():
        if not key.startswith('lateral_'):
            continue
        for i, left in enumerate(rows):
            for right in rows[i+1:]:
                if (left.get('beam_name') != right.get('beam_name') or
                        left.get('side') != right.get('side') or
                        any(r.get('uid') in protected_uids or r.get('validated') or
                            r.get('geometry_validated') for r in (left, right))):
                    continue
                lc, rc = left.get('lv_cell') or {}, right.get('lv_cell') or {}
                if lc.get('depth') == rc.get('depth'):
                    continue
                shared = [(a,b) for a in (0,1) for b in (0,1)
                          if dist(left['points'][a], right['points'][b]) < .05]
                if len(shared) != 1:
                    continue
                a,b = shared[0]
                supports = [c.get('support_start' if e == 0 else 'support_end') or {}
                            for c,e in ((lc,a),(rc,b))]
                if any(s.get('type') != 'secao' for s in supports):
                    continue
                points = left['points'] + right['points']
                axis = 0 if abs(left['points'][1][0]-left['points'][0][0]) > .1 else 1
                cross = 1-axis
                if any(abs(p[cross]-points[0][cross]) > .05 for p in points):
                    continue  # rotated/diagonal rows need their local frame
                seam = left['points'][a][axis]
                sections = [s for c in (lc,rc) for s in c.get('sections') or []]
                if not any(s.get('source') == 'midpoint_between_labels' and
                           min(abs(float(s[k])-seam) for k in ('start','end')) < .05
                           for s in sections):
                    continue
                lo, hi = min(p[axis] for p in points), max(p[axis] for p in points)
                width = float(str(lc.get('dim') or left.get('width') or '').split('/')[0])
                # A is the low wall, B the high wall, in the orthogonal SA frame.
                wall = points[0][cross]
                low_wall = wall if str(left.get('side')).upper() == 'A' else wall-width
                candidates = set()
                for line in structural_lines:
                    p,q = line[:2],line[2:]
                    if (abs(p[axis]-q[axis]) < .05 and
                            lo+.15 < p[axis] < hi-.15 and
                            abs(min(p[cross],q[cross])-low_wall) < .15 and
                            abs(max(p[cross],q[cross])-(low_wall+width)) < .15):
                        candidates.add(round((p[axis]+q[axis])/2,6))
                if len(candidates) != 1:
                    continue  # do not choose among ambiguous structural marks
                boundary = candidates.pop()
                if abs(boundary-seam) < .05:
                    continue
                # Openings cannot be silently truncated by a moving section seam.
                if any(c.get('pillar_openings') for c in (lc,rc)):
                    continue
                for row,cell,end in ((left,lc,a),(right,rc,b)):
                    old_start = row['points'][0][axis]
                    direction = 1 if row['points'][1][axis] > old_start else -1
                    for opening in cell.get('beam_openings') or []:
                        # Preserve physical coordinates when the start moves.
                        if end == 0:
                            delta = (old_start-boundary)*direction
                            opening['pos_inicio'] += delta
                            if 'pos_fim' in opening:
                                opening['pos_fim'] += delta
                    row['points'][end][axis] = boundary
                    row['length'] = dist(*row['points'])
                    for section in cell.get('sections') or []:
                        for field in ('start','end'):
                            if abs(float(section[field])-seam) < .05:
                                section[field] = boundary
                                section['source'] = 'structural_transverse_divider'
                    row.setdefault('section_boundary_corrections',[]).append(dict(
                        from_station_cm=seam,to_station_cm=boundary,
                        source='measured_full_width_structural_divider'))
    return result
