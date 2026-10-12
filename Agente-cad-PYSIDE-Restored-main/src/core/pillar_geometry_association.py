"""Second pass grounded in source identity, dimensions and recurring conventions."""
from collections import Counter
import math
import re

from shapely.geometry import Point, Polygon


def circular_measurements(points):
    pts = list(points or [])
    if pts and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 24:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    radii = [math.hypot(p[0]-cx, p[1]-cy) for p in pts]
    radius = sum(radii) / len(radii)
    if radius <= 0 or max(radii)-min(radii) > max(1e-6, radius*1e-5):
        return None
    return dict(center=[cx, cy], radius=radius, diameter=2*radius,
                circumference=2*math.pi*radius, area=math.pi*radius**2)


def annotate_circular_state(state):
    """Derived measurements and contacts; do not invent ABCD faces on a circle.

    Contacts refer explicitly to published beam contours, so they can be
    revisited when the corresponding beam geometry is corrected.
    """
    for pillar in state.get('pilares', []):
        measured = circular_measurements(pillar.get('points'))
        if not measured:
            continue
        center = Point(measured['center'])
        contacts = []
        for beam in (state.get('segmentos') or {}).get('fundo', []):
            points = beam.get('points') or []
            if len(points) < 3:
                continue
            poly = Polygon(points)
            if not poly.is_valid or poly.area <= 0:
                continue
            from shapely.ops import nearest_points
            contact = nearest_points(center, poly)[1]
            distance = center.distance(contact)
            if distance > measured['radius'] + .1:
                continue
            angle = math.degrees(math.atan2(contact.y-center.y, contact.x-center.x)) % 360
            if math.isclose(angle, 360, abs_tol=1e-8) or math.isclose(angle, 0, abs_tol=1e-8):
                angle = 0.0
            contacts.append(dict(beam=beam.get('beam_name'), segment=beam.get('uid'),
                                 point=[contact.x, contact.y],
                                 angle_deg=angle,
                                 source='published_beam_soffit_contour',
                                 overlap=distance < measured['radius']-.1))
        pillar['circular_geometry'] = dict(**measured, beam_contacts=contacts,
                                          n3_n5_status='unsupported_circular_method')
        pillar['format'] = 'Circular'


def reassociate(data, names, initial, predicate, max_distance=200):
    """Return unique source candidates; recurrence is a prior, never a veto.

    Dimensions are read next to each P label, independently of the initial
    geometry. Section/beam layers are source evidence, not previous SA guesses.
    A minority shape remains eligible when supported by its own dimension.
    """
    from src.core.cad_object_recognition import section_layer, section_piece_keys
    from src.core.pillar_special_faces import physical_ring
    raw_section_keys, _ = section_piece_keys(data.get('polylines', []), data.get('texts', []))
    def key(points):
        return tuple(sorted(set((round(p[0], 6), round(p[1], 6)) for p in points)))
    section_keys = {key(points) for points in raw_section_keys}
    candidates = []
    for item in data.get('polylines', []):
        pts = item.get('points') or []
        if len(pts) < 3:
            continue
        try:
            poly = Polygon(pts)
            if not poly.is_valid or not predicate(poly, pts):
                continue
        except (ValueError, TypeError):
            continue
        layer = str(item.get('layer') or '').upper()
        if section_layer(layer) or key(pts) in section_keys or re.search(r'VIGA|BEAM', layer):
            continue
        ring = physical_ring(pts)
        rect = poly.minimum_rotated_rectangle
        lengths = sorted(math.dist(a,b) for a,b in zip(list(rect.exterior.coords), list(rect.exterior.coords)[1:]))
        candidates.append(dict(points=pts, poly=poly, layer=layer, dims=[lengths[0], lengths[-1]],
                               source_id=id(item), special=len(ring)>4))
    for item in data.get('circles', []):
        radius = float(item.get('radius') or 0)
        layer = str(item.get('layer') or '').upper()
        if not re.search(r'PILAR|COLUMN|PILLAR', layer) or not 80 <= math.pi*radius**2 <= 60000:
            continue
        cx, cy = item['center'][:2]
        count = max(32, math.ceil(math.pi / math.acos(max(-1, 1-.05/radius))))
        pts = [(cx+radius*math.cos(2*math.pi*i/count), cy+radius*math.sin(2*math.pi*i/count)) for i in range(count)]
        pts.append(pts[0])
        candidates.append(dict(points=pts, poly=Polygon(pts), layer=layer, dims=[2*radius]*2,
                               source_id=id(item), special=True))
    dimensions = {}
    for name, positions in names.items():
        labels = [t for t in data.get('texts', []) if str(t.get('text') or '').strip().upper()==name]
        choices = []
        for t in data.get('texts', []):
            match = re.fullmatch(r'(?:Ø|⌀|%%[cC])?\s*(\d+(?:[.,]\d+)?)\s*(?:[/xX]\s*(\d+(?:[.,]\d+)?)(?:-[MS])?)?', str(t.get('text') or '').strip())
            if not match or not t.get('pos'):
                continue
            # Single numbers are admissible only with the diameter symbol.
            if not match[2] and not re.match(r'^(Ø|⌀|%%[cC])', str(t['text']).strip()):
                continue
            distance = min((math.dist(t['pos'][:2], p[:2]) for p in positions), default=math.inf)
            height = max([float(t.get('height') or 0)]+[float(label.get('height') or 0) for label in labels])
            if distance <= max(20, 3*height):
                vals = sorted(float(v.replace(',', '.')) for v in (match[1], match[2] or match[1]))
                choices.append((distance, vals))
        if choices:
            dimensions[name] = [choice[1] for choice in sorted(choices)]
    def agrees(candidate, dims):
        return bool(dims) and any(all(abs(a-b) <= max(.5, .025*b)
                                    for a,b in zip(candidate['dims'], alternative)) for alternative in dims)
    # Dominance comes from independently dimensioned, nearby source candidates.
    votes = Counter()
    for name, positions in names.items():
        matches = [c for c in candidates if agrees(c, dimensions.get(name)) and
                   min((c['poly'].distance(Point(p)) for p in positions), default=math.inf) <= max_distance]
        if len(matches)==1:
            votes[matches[0]['layer']] += 1
    dominant = votes.most_common(1)[0][0] if votes and votes.most_common(1)[0][1]>=3 else None
    options = {}
    for name, positions in names.items():
        scores = []
        for index, candidate in enumerate(candidates):
            distance = min((candidate['poly'].distance(Point(p)) for p in positions), default=math.inf)
            if distance > max_distance:
                continue
            matched = agrees(candidate, dimensions.get(name))
            # A dimension contradicting the candidate outweighs recurrence.
            mismatch = bool(dimensions.get(name)) and not matched and not candidate['special']
            score = distance + (300 if mismatch else 0) - (150 if matched else 0)
            if dominant and candidate['layer']==dominant:
                score -= 30
            if key(candidate['points'])==key(initial.get(name) or []):
                score -= 5
            scores.append((score, index, matched, distance))
        options[name] = sorted(scores)
    result, used = {}, set()
    # Resolve strongest margins first; never assign one source twice.
    order = sorted(options, key=lambda name: (-(options[name][1][0]-options[name][0][0]) if len(options[name])>1 else -math.inf))
    for name in order:
        available = [s for s in options[name] if s[1] not in used]
        if not available:
            continue
        best = available[0]
        if len(available)>1 and available[1][0]-best[0]<1:
            continue  # unresolved is safer than an arbitrary ownership
        candidate = candidates[best[1]]
        used.add(best[1])
        result[name] = dict(points=candidate['points'], source_id=candidate['source_id'],
                            evidence=dict(source_layer=candidate['layer'], dimension=dimensions.get(name),
                                          dimension_match=best[2], distance=best[3], dominant_layer=dominant,
                                          votes=dict(votes)))
    return result
