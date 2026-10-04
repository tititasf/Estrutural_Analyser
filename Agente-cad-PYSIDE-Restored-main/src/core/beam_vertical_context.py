"""Measured vertical semantics, independent of drawing scale and N1 schema.

An inverted symbol requires two distinct red parallel strokes spanning the web
and a flange reaching its base. Dimension ticks and duplicated entities cannot
establish inversion. Coordinates are transformed into the cut's local frame.
"""
from math import hypot, isfinite


def current_section_slabs(snapshot_slabs, analyzed_slabs):
    """Keep effective contours, but use the current SA's level evidence.

    A granular read-only export may retain database scalar values from a prior
    round. Those values must not overwrite newly analyzed regional evidence.
    Human validations have already been applied by the canonical SA runner.
    """
    from copy import deepcopy
    from .lv_cut_inventory import number
    lookup = {s.get('name'): s for s in analyzed_slabs}
    result = []
    for old in snapshot_slabs:
        source = lookup.get(old.get('name'))
        if source is None:
            result.append(deepcopy(old))
            continue
        row = deepcopy(source)
        row['points'] = deepcopy(old.get('points') or source.get('points') or [])
        fields = source.get('fields') or {}
        row['nivel'] = number(fields.get('laje_nivel') or source.get('laje_nivel'))
        row['height'] = number(fields.get('laje_dim') or source.get('height'))
        row['section_level_source'] = 'current_sa_round'
        result.append(row)
    return result


def inverted_cut_evidence(points, lines, direction, width_cm, height_cm):
    from shapely.geometry import Polygon, LineString
    if not points or not direction or not width_cm or not height_cm:
        return None
    ns = str(direction).casefold().startswith(('n', 's'))
    def local(p):
        return (float(p[1]), -float(p[0])) if ns else (float(p[0]), float(p[1]))
    vertices = [local(p) for p in points]
    poly = Polygon(vertices)
    if not poly.is_valid or poly.area <= 0:
        return None
    xmin, ymin, xmax, ymax = poly.bounds
    boundaries = sorted(set(p[0] for p in vertices))
    bands = []
    for a, b in zip(boundaries, boundaries[1:]):
        if b-a < .01:
            continue
        cross = poly.intersection(LineString([((a+b)/2, ymin-1), ((a+b)/2, ymax+1)]))
        if cross.is_empty:
            continue
        lo, hi = cross.bounds[1], cross.bounds[3]
        bands.append((hi-lo, a, b, lo, hi))
    if not bands:
        return None
    _, left, right, bottom, top = max(bands)
    if abs(right-left-float(width_cm)) > .5:
        return None
    flanges = {}
    for side, sign in (('left', -1), ('right', 1)):
        outside = [p[1] for p in vertices if p[0] < left-.1] if sign < 0 else [p[1] for p in vertices if p[0] > right+.1]
        if outside:
            low, high = min(outside), max(outside)
            if low < bottom-.5 or high > top+.5 or high-low <= .5:
                return None
            flanges[side] = dict(height_cm=round(high-low, 4), bottom_cm=round(low-bottom, 4))
    if not flanges or any(f['bottom_cm'] > .5 for f in flanges.values()):
        return None
    strokes = {}
    for row in lines:
        if row.get('aci') != 1 and row.get('color') not in (1, '#ff0000', (255, 0, 0), [255, 0, 0]):
            continue
        if not row.get('start') or not row.get('end'):
            continue
        a, b = sorted((local(row['start']), local(row['end'])))
        dx, dy = b[0]-a[0], b[1]-a[1]
        if dx <= 0 or a[0] > left or b[0] < right or not .03 <= abs(dy/dx) <= .7:
            continue
        if dx > 3*float(width_cm) or min(a[1], b[1]) < bottom or max(a[1], b[1]) > top:
            continue
        key = tuple(round(v, 3) for p in (a,b) for v in p)
        strokes.setdefault(key, (a,b,row.get('handle')))
    candidates = list(strokes.values())
    for i, (a,b,handle) in enumerate(candidates):
        slope = (b[1]-a[1])/(b[0]-a[0])
        for c,d,other in candidates[i+1:]:
            slope2 = (d[1]-c[1])/(d[0]-c[0])
            gap = abs((c[1]-slope*c[0])-(a[1]-slope*a[0]))/hypot(1,slope)
            if abs(slope-slope2) <= .02 and .5 <= gap <= .5*float(width_cm):
                return dict(schema='cad.sa.beam_vertical_context/v1', beam_type='inverted',
                            evidence='paired_red_strokes_and_lower_flange',
                            symbol_handles=[v for v in (handle,other) if v],
                            height_cm=float(height_cm), width_cm=float(width_cm),
                            measured_height_cm=top-bottom,
                            frame=dict(base_center=[-bottom,(left+right)/2] if ns else [(left+right)/2,bottom],
                                       ex=[0,1] if ns else [1,0], ey=[-1,0] if ns else [0,1]),
                            flanges=flanges, role='top_cap', confirmed=True)
    return None


def inverted_levels(height_cm, slabs):
    """Solve a shared base from regional slabs; contradictions remain errors."""
    bases = [float(s['level'])-(float(s['height_cm'])+float(s.get('bottom_cm', 0)))/100 for s in slabs]
    if not bases:
        raise ValueError('viga invertida sem nível de laje confirmado')
    if not all(isfinite(v) for v in bases) or not isfinite(float(height_cm)) or float(height_cm) <= 0:
        raise ValueError('níveis ou altura inválidos para o corte invertido')
    if max(bases)-min(bases) > .005:
        raise ValueError('bases das lajes incompatíveis com o corte invertido')
    base = sum(bases)/len(bases)
    return dict(base_level_m=round(base, 6), top_level_m=round(base+float(height_cm)/100, 6))


def vertical_overlap(first, second):
    """None means unknown, zero means proven disjoint, otherwise cm contact."""
    if any(v.get(k) is None for v in (first, second) for k in ('base_level_m', 'top_level_m')):
        return None
    if any(not all(isfinite(float(v[k])) for k in ('base_level_m', 'top_level_m'))
           or v['top_level_m'] <= v['base_level_m'] for v in (first, second)):
        raise ValueError('intervalo vertical inválido')
    return max(0., min(first['top_level_m'], second['top_level_m'])-
               max(first['base_level_m'], second['base_level_m']))*100


def lateral_wall_contact(owner, incident, side):
    """Intersect concrete contact with the actual executive wall on this side.

    Coordinates are centimetres above the wall's mounting base, not above
    the slab and not above a common depth shared by both sides. Unknown levels
    remain pending; separated beams return no opening.
    """
    if vertical_overlap(owner, incident) is None:
        raise ValueError('cruzamento sem intervalos verticais confirmados')
    mount = (owner.get('mounting') or {}).get(side) or {}
    try:
        panel_base = float(mount['panel_base_cm'])
        panel_top = float(mount['panel_top_cm'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('cruzamento sem montagem local da lateral') from exc
    if not all(isfinite(v) for v in (panel_base, panel_top)) or panel_top <= panel_base:
        raise ValueError('montagem vertical inválida da lateral')
    origin = float(owner['base_level_m'])
    concrete_top = (float(owner['top_level_m'])-origin)*100
    incident_base = (float(incident['base_level_m'])-origin)*100
    incident_top = (float(incident['top_level_m'])-origin)*100
    low = max(0., panel_base, incident_base)
    high = min(concrete_top, panel_top, incident_top)
    if high-low <= 1e-6:
        return None
    return {'bottom_cm': round(low-panel_base, 6),
            'top_cm': round(high-panel_base, 6),
            'height_cm': round(high-low, 6),
            'panel_height_cm': round(panel_top-panel_base, 6),
            'contact_base_level_m': round(origin+low/100, 6),
            'contact_top_level_m': round(origin+high/100, 6)}


def end_joint_footprint(pair, corridor, width):
    """Extend contact geometry into a measured beam end joint, never an interior gap.

    Lateral walls stop at support faces; the measured concrete corridor includes
    the terminal joint. This changes contact geometry only, not wall lengths or
    the adjacent section's confirmed altitude.
    """
    from math import hypot
    from copy import deepcopy
    if len(corridor or []) != 4 or len(pair.get('footprint') or []) != 4 or not width:
        return None
    start, end = pair['start'], pair['end']
    dx, dy = end[0]-start[0], end[1]-start[1]
    length = hypot(dx, dy)
    if length <= .01:
        return None
    horizontal = abs(dy) < .01
    vertical = abs(dx) < .01
    if not (horizontal or vertical):
        return None
    axis = 0 if horizontal else 1
    other = 1-axis
    if any(not corridor[other]-.5 <= p[other] <= corridor[other+2]+.5 for p in pair['footprint']):
        return None
    low, high = corridor[axis], corridor[axis+2]
    points = deepcopy(pair['footprint'])
    changed = False
    for index, endpoint in enumerate((start, end)):
        station = endpoint[axis]
        is_low_end = (index == 0) == (start[axis] < end[axis])
        boundary = low if is_low_end else high
        distance = abs(station-boundary)
        if .5 < distance <= float(width)+.5:
            # Both vertices of this end face move together.
            for vertex in (index, 3-index):
                points[vertex][axis] = boundary
            changed = True
    return points if changed else None


def incident_vertical_contract(point, name, entries):
    """Resolve a crossing against its physical footprint and local altitude."""
    from copy import deepcopy
    from shapely.geometry import Point, Polygon
    candidates = []
    for entry in entries:
        if str(entry.get('beam') or '').upper() != str(name).upper():
            continue
        matching = any(len(pair.get('footprint') or []) >= 3 and
                       Polygon(pair.get('joint_footprint') or pair['footprint']).buffer(.5).covers(Point(point))
                       for pair in entry.get('pairs') or [])
        if not matching:
            continue
        contract = entry.get('section_contract') or {}
        if entry.get('pending') or vertical_overlap(contract, contract) is None:
            raise ValueError(f'{name}: cruzamento local sem intervalo vertical confirmado')
        candidates.append(contract)
    signatures = {(c['base_level_m'], c['top_level_m']) for c in candidates}
    if len(signatures) != 1:
        reason = 'perfis verticais conflitantes' if signatures else 'sem seção na estação do cruzamento'
        raise ValueError(f'{name}: {reason}')
    return deepcopy(candidates[0])


def inverted_slab_level_source(cut, own_slab, source_slab, source):
    """Transport a regional altitude across measured inverted flanges.

    A remote slab name assigned to the broken web cannot establish a datum.
    Both owners must contain the actual flange probes, and a thinner regional
    flange requires an evidenced regional altitude rather than a principal one.
    """
    from shapely.geometry import Point, Polygon
    semantics = cut.get('section_semantics') or {}
    frame = semantics.get('frame') or {}
    try:
        center, ex, ey = frame['base_center'], frame['ex'], frame['ey']
        width = float(semantics['width_cm'])
        flanges = semantics['flanges']
        def contact(slab):
            polygon = Polygon(slab.get('points') or [])
            if not polygon.is_valid or polygon.is_empty:
                return None
            matches = []
            for side, sign in (('left', -1), ('right', 1)):
                flange = flanges.get(side)
                if not flange:
                    continue
                x = sign*(width/2+1)
                y = flange['bottom_cm']+flange['height_cm']/2
                probe = Point(*(center[i]+ex[i]*x+ey[i]*y for i in (0,1)))
                if polygon.buffer(.5).covers(probe):
                    matches.append((side, flange, probe))
            return matches[0] if len(matches) == 1 else None
        own, other = contact(own_slab), contact(source_slab)
        if not own or not other or own[0] == other[0]:
            return None
        altitude = float(source['value'])
        fields = source_slab.get('fields') or {}
        from .lv_cut_inventory import number
        thickness = number(source_slab.get('height') or fields.get('laje_dim'))
        for region in source_slab.get('slab_steps') or []:
            if Polygon(region['points']).buffer(.5).covers(other[2]):
                if region.get('status') != 'same_bottom' or region.get('level_m') is None:
                    return None
                thickness = number(region.get('height_cm'))
                altitude = float(region['level_m'])
                break
        if thickness is None or abs(thickness-other[1]['height_cm']) > .5:
            return None
        delta = (own[1]['bottom_cm']+own[1]['height_cm']-
                 other[1]['bottom_cm']-other[1]['height_cm'])
        if not isfinite(altitude) or abs(delta) >= 100:
            return None
        return {**source, 'value':round(altitude+delta/100, 2),
                'source_level':altitude, 'delta_cm':delta,
                'kind':'inverted_regional_flange',
                'source_slab':source_slab.get('name')}
    except (KeyError, TypeError, ValueError):
        return None


def inverted_profile_levels(height_cm, profiles, semantics=None):
    """Use the local slab reference, keeping neighboring slabs at their levels.

    An estimated opposite-face level is not an independent beam datum. Only
    slabs agreeing with a contact-derived profile level can anchor the base.
    A borrowed face level promoted after geometric contact remains a secondary
    reference. Two conflicting direct cell anchors still require review.
    """
    anchors = []
    references = []
    # A measured original at the same structural height identifies which
    # regional slab reaches the web base. A different height is a new local
    # profile and must use its own contact reference instead.
    semantics = semantics or {}
    reference = semantics.get('local_slab_reference')
    if reference:
        side = reference['side']
        matches = [s for s in profiles.get(side, {}).get('slabs') or []
                   if s.get('name') == reference['slab']
                   and s.get('region_id') == reference.get('region_id')]
        if len(matches) != 1:
            raise ValueError('referência local da viga invertida não corresponde à laje do segmento')
        result = inverted_levels(height_cm, matches)
        result['level_references'] = [dict(reference)]
        return result
    original_height = semantics.get('reference_height_cm', semantics.get('height_cm'))
    if (semantics.get('confirmed') and original_height is not None
            and abs(float(original_height)-float(height_cm)) <= .5):
        for side, profile in profiles.items():
            flange = (semantics.get('flanges') or {}).get('left' if side == 'A' else 'right')
            if not flange or abs(float(flange.get('bottom_cm', -1))) > .5:
                continue
            for slab in profile.get('slabs') or []:
                if (slab.get('level') is not None and slab.get('height_cm') is not None
                        and abs(float(slab['height_cm'])-float(flange['height_cm'])) <= .5):
                    anchors.append(slab)
                    references.append(dict(side=side,slab=slab.get('name'),
                        region_id=slab.get('region_id'),source='measured_original_base_flange'))
        if anchors:
            result = inverted_levels(height_cm, anchors)
            result['level_references'] = references
            return result
    direct = any(p.get('level_source') == 'lv_cell_slabs' for p in profiles.values())
    accepted = {'lv_cell_slabs'} if direct else {'paired_touching_slabs'}
    for side, profile in profiles.items():
        if profile.get('level_source') not in accepted:
            continue
        level = profile.get('level')
        if level is None:
            continue
        for slab in profile.get('slabs') or []:
            if slab.get('level') is not None and abs(float(slab['level'])-float(level)) <= .005:
                anchors.append(slab)
                references.append(dict(side=side,slab=slab.get('name'),
                    region_id=slab.get('region_id'),source=profile['level_source']))
    if not anchors:
        anchors = [s for p in profiles.values() for s in p.get('slabs') or []]
    result = inverted_levels(height_cm, anchors)
    result['level_references'] = references
    return result


def attach_local_inverted_references(cuts, dimension_labels, slabs):
    """Resolve changed heights against their physical dimension annotation.

    Require the matching width/height, a station inside the segment, and a
    unique adjacent slab containing the annotation. Never choose a lower level
    merely to resolve conflicting direct references.
    """
    import re
    from shapely.geometry import Point, Polygon, LineString
    lookup = {s.get('name'): s for s in slabs}
    for cut in cuts:
        semantics = cut.get('section_semantics') or {}
        height = cut.get('beam_height_cm')
        original = semantics.get('reference_height_cm')
        if not semantics.get('confirmed') or original is None or height is None or abs(original-height) <= .5:
            continue
        candidates = []
        for label in dimension_labels:
            match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*', str(label.get('text') or ''))
            if not match or not label.get('pos'):
                continue
            width, depth = (float(v.replace(',', '.')) for v in match.groups())
            if abs(width-cut['width_cm']) > .5 or abs(depth-height) > .5:
                continue
            point = Point(label['pos'][:2])
            for pair in cut.get('pairs') or []:
                span = pair.get('dimension_span') or [pair['start'], pair['end']]
                line = LineString(span)
                # No endpoint clamping: a nearby label outside this physical
                # interval belongs to another section, even on the same beam.
                start, end = span
                station = sum((point.coords[0][i]-start[i])*(end[i]-start[i]) for i in (0,1))/line.length
                if not 0 <= station <= line.length or line.distance(point) > width+5:
                    continue
                owners = []
                for side, profile in (cut.get('profiles') or {}).items():
                    for slab in profile.get('slabs') or []:
                        source = lookup.get(slab.get('name')) or {}
                        region = next((r for r in source.get('slab_steps') or []
                                       if (r.get('region_id') or r.get('uid')) == slab.get('region_id')), None) if slab.get('region_id') else None
                        points = (region or source).get('points') or []
                        if len(points) >= 3 and Polygon(points).covers(point):
                            owners.append(dict(side=side, slab=slab['name'], region_id=slab.get('region_id'),
                                source='local_dimension_in_slab', dimension=label['text'], position=list(point.coords[0])))
                if len(owners) == 1:
                    candidates.extend(owners)
        keys = {(r['side'], r['slab'], r['region_id']) for r in candidates}
        if len(keys) == 1:
            semantics['local_slab_reference'] = candidates[0]
    return cuts


def clear_top_cap_interferences(cuts, reference_cuts=()):
    """Retain only crossing intervals proven below an inverted top cap.

    Wall openings remain in the lateral inventory. This complementary context
    is solely for FV caps, whose plane may be above all incident beam levels.
    Unknown altitude or a touching/crossing cap never establishes clearance.
    """
    from copy import deepcopy
    from math import dist
    from .lv_n3_cut_contract import build_cut_contract
    result = []
    for cut in cuts:
        try:
            contract = build_cut_contract(cut)
        except ValueError:
            # An incident beam occupies the slab contact area. The cap plane
            # may continue from a directly adjacent interval of the exact same
            # A/B faces and declared height, without inventing a slab there.
            candidates = []
            for ref in reference_cuts:
                if ref.get('width_cm') != cut.get('width_cm') or ref.get('beam_height_cm') != cut.get('beam_height_cm'):
                    continue
                if (ref.get('section_semantics') or {}).get('source_section_id') != (cut.get('section_semantics') or {}).get('source_section_id'):
                    continue
                adjacent = any(p['a_id'] == q['a_id'] and p['b_id'] == q['b_id']
                    and min(dist(a,b) for a in (p['start'],p['end']) for b in (q['start'],q['end'])) <= .5
                    for p in cut.get('pairs') or [] for q in ref.get('pairs') or [])
                if adjacent:
                    try:
                        candidates.append(build_cut_contract(ref))
                    except ValueError:
                        pass
            signatures = {(c.get('beam_type'), c.get('base_level_m'), c.get('top_level_m')) for c in candidates}
            if len(signatures) != 1:
                continue
            contract = deepcopy(candidates[0])
            contract['level_continuity_source'] = 'adjacent_same_ab_faces_and_height'
        if contract.get('beam_type') != 'inverted' or contract.get('form_role') != 'top_cap':
            continue
        kept = []
        for pair in cut.get('pairs') or []:
            crossings = pair.get('beam_interferences') or []
            if not crossings:
                continue
            clear = True
            for opening in crossings:
                levels = ([opening['level']] if opening.get('level') is not None
                          else opening.get('level_candidates_m') or [])
                try:
                    values = [float(v) for v in levels]
                    clear &= bool(values) and all(isfinite(v) for v in values) and max(values) < contract['top_level_m']-.005
                except (ValueError, TypeError):
                    clear = False
            if clear:
                kept.append(deepcopy(pair))
        if kept:
            row = deepcopy(cut)
            row['pairs'] = kept
            row['coverage_role'] = 'top_cap_above_incident_beams'
            row['cap_contract'] = deepcopy(contract)
            result.append(row)
    return result


def apply_inverted_sections(calculated, originals):
    """Propagate only measured beam evidence; retain each local section height.

    An original lacking validated semantics is a boundary, not permission to
    carry inversion through it. Conflicting slab bases remain a blocked cut.
    """
    from copy import deepcopy
    result = []
    for cut in calculated:
        related = [r for r in originals if r.get('beam') == cut.get('beam')]
        for pair_index, pair in enumerate(cut.get('pairs') or []):
            start, end = pair['start'], pair['end']
            length = hypot(end[0]-start[0], end[1]-start[1])
            if length <= .01:
                raise ValueError('intervalo de corte sem comprimento físico')
            axis = [(end[i]-start[i])/length for i in (0,1)]
            # Stations must not depend on the A/B segment reading direction.
            if axis[0] < -1e-8 or (abs(axis[0]) < 1e-8 and axis[1] < 0):
                start, end = end, start
                axis = [-v for v in axis]
            stations = []
            for original in related:
                raw = original.get('source_cut') or {}
                points = raw.get('pts') or raw.get('points') or []
                if not points:
                    continue
                center = [(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in (0,1)]
                station = sum((center[i]-start[i])*axis[i] for i in (0,1))
                stations.append((station, raw.get('section_semantics') or {}, original.get('id')))
            boundaries = sorted({0., length, *(s[0] for s in stations if .01 < s[0] < length-.01)})
            for interval_index, (low, high) in enumerate(zip(boundaries,boundaries[1:])):
                row = deepcopy(cut)
                # Shape grouping is only a presentation optimization. Each
                # station keeps its own slab identities and absolute levels.
                if pair.get('profiles'):
                    row['profiles'] = deepcopy(pair['profiles'])
                row.pop('section_semantics', None)
                physical = deepcopy(pair)
                physical.update(start=[start[i]+axis[i]*low for i in (0,1)],
                                end=[start[i]+axis[i]*high for i in (0,1)], length_cm=high-low)
                if pair.get('footprint'):
                    delta = [pair['footprint'][3][i]-pair['footprint'][0][i] for i in (0,1)]
                    physical['footprint'] = [physical['start'], physical['end'],
                        [physical['end'][i]+delta[i] for i in (0,1)],
                        [physical['start'][i]+delta[i] for i in (0,1)]]
                row['pairs'] = [physical]
                row['id'] = f"{cut['id']}-physical-{pair_index}-{interval_index}"
                # Each original is a boundary, including an undecoded one.
                before = [s for s in stations if s[0] <= (low+high)/2]
                selected = max(before,key=lambda s:s[0]) if before else min(stations,key=lambda s:s[0]) if stations else None
                semantics = selected[1] if selected else {}
                if semantics.get('confirmed') and semantics.get('beam_type') == 'inverted':
                    row['section_semantics'] = deepcopy(semantics)
                    row['section_semantics']['reference_height_cm'] = semantics['height_cm']
                    row['section_semantics']['height_cm'] = row['beam_height_cm']
                    row['section_semantics']['propagation'] = 'same_beam_until_next_original'
                    row['section_semantics']['source_section_id'] = selected[2]
                result.append(row)
        if not cut.get('pairs'):
            result.append(deepcopy(cut))
    return result


def enrich_originals(originals, lines):
    """Rebuild derived semantics on read, without modifying stored N1 fields."""
    from copy import deepcopy
    from .lv_cut_inventory import number
    result = deepcopy(originals)
    for raw in result:
        ficha = raw.get('ficha') or {}
        evidence = inverted_cut_evidence(raw.get('pts') or raw.get('points'), lines,
            ficha.get('direction'), number(raw.get('beam_w') or ficha.get('beam_bottom_dim')),
            number(raw.get('beam_h') or ficha.get('beam_height')))
        if not evidence:
            measured = raw.get('section_semantics') or {}
            if (measured.get('confirmed') is True and measured.get('beam_type') == 'inverted'
                    and measured.get('evidence') == 'paired_red_strokes_and_lower_flange'
                    and measured.get('flanges') and measured.get('frame')):
                evidence = measured
        if not evidence:
            continue
        raw['section_semantics'] = evidence
        own_a = str(ficha.get('direction') or '').casefold().startswith(('n', 'l', 'e'))
        for prefix,side,key in [('own','left' if own_a else 'right','own_slab_height'),
                                ('neighbor','right' if own_a else 'left','neigh_slab_height')]:
            slab = evidence['flanges'].get(side)
            if slab:
                ficha[key] = slab['height_cm']
                ficha[prefix+'_dist_top'] = evidence['height_cm']-slab['height_cm']-slab['bottom_cm']
                ficha[prefix+'_dist_bottom'] = slab['bottom_cm']
                ficha['own_position' if prefix=='own' else 'neighbor_position'] = 'fundo'
        raw['ficha'] = ficha
    return result


def covering_vertical_contract(points, entries, *, axis=None):
    """Require complete physical coverage before converting a span to a cap.

    A representative section alone cannot classify a long FV spanning several
    profiles. Unknown levels, conflicting heights and uncovered stations fail
    closed; they never imply a normal beam or permission to invent a level.
    """
    from copy import deepcopy
    from math import dist
    if len(points or []) < 2:
        raise ValueError('fundo sem geometria para conferir contexto vertical')
    edges = list(zip(points,points[1:]))
    if len(points)>2:
        edges.append((points[-1],points[0]))
    start,end = max(edges,key=lambda edge:dist(*edge))
    size = dist(start,end)
    if size <= .01:
        raise ValueError('fundo sem extensão para conferir contexto vertical')
    if axis is None:
        axis = [(end[i]-start[i])/size for i in (0,1)]
    else:
        norm = hypot(*axis)
        if norm <= .01:
            raise ValueError('eixo do fundo sem direção válida')
        axis = [v/norm for v in axis]
    project = lambda p: sum((p[i]-start[i])*axis[i] for i in (0,1))
    transverse = lambda p: (p[0]-start[0])*(-axis[1])+(p[1]-start[1])*axis[0]
    low,high = min(map(project,points)),max(map(project,points))
    across_low,across_high = min(map(transverse,points)),max(map(transverse,points))
    ranges, contracts = [], []
    for entry in entries:
        contract = entry.get('section_contract') or {}
        semantics = contract.get('section_semantics') or entry.get('section_semantics') or {}
        if contract.get('beam_type') != 'inverted' and semantics.get('beam_type') != 'inverted':
            continue
        matching = []
        for pair in entry.get('pairs') or []:
            a,b=pair['start'],pair['end']
            length=dist(a,b)
            if length <= .01 or abs(sum((b[i]-a[i])*axis[i] for i in (0,1))/length) < .9999:
                continue
            # An interval on a distant parallel occurrence of the same named
            # beam does not cover this bottom. Allow its lateral face offset.
            # Published stations lie on face A. A lateral B line is one full
            # beam width away; a soffit polygon already spans both faces.
            margin = float(contract.get('width_cm') or 0)/(1 if len(points)==2 else 2)+.5
            if any(not across_low-margin <= transverse(p) <= across_high+margin for p in (a,b)):
                continue
            l,h=sorted((project(a),project(b)))
            l,h=max(l,low),min(h,high)
            if h-l > .01:
                matching.append((l,h))
        if matching:
            if entry.get('pending'):
                raise ValueError('contexto do fundo invertido pendente: '+entry['pending'])
            if contract.get('form_role') != 'top_cap' or not (contract.get('section_semantics') or {}).get('confirmed'):
                raise ValueError('tipo invertido sem evidência confirmada')
            if vertical_overlap(contract,contract) is None:
                raise ValueError('tampa invertida sem níveis absolutos confirmados')
            ranges.extend(matching)
            contracts.append(contract)
    if not ranges:
        raise ValueError('fundo invertido sem intervalo vertical confirmado')
    cursor=low
    for l,h in sorted(ranges):
        if l-cursor > .5:
            raise ValueError('contexto vertical não cobre todo o segmento de fundo')
        cursor=max(cursor,h)
    if high-cursor > .5:
        raise ValueError('contexto vertical não cobre todo o segmento de fundo')
    signatures={(c['width_cm'],c['height_cm'],c['base_level_m'],c['top_level_m']) for c in contracts}
    if len(signatures)!=1:
        raise ValueError('segmento de fundo atravessa mudança de perfil vertical; subdivisão necessária')
    return deepcopy(contracts[0])


def partition_inverted_lateral(points, entries, side):
    """Cover a physical lateral line with confirmed, local mounting profiles.

    Retain every station, including repeated sections; a gap or conflicting
    slab mounting is pending rather than permission to use a common depth.
    """
    from math import dist
    if len(points or []) != 2:
        raise ValueError('lateral invertida exige um segmento reto de dois pontos')
    start, end = points
    length = dist(start, end)
    if length <= .01:
        raise ValueError('lateral invertida sem extensão')
    axis = [(end[i]-start[i])/length for i in (0, 1)]
    project = lambda p: sum((p[i]-start[i])*axis[i] for i in (0, 1))
    stations = {0., length}
    for entry in entries:
        for pair in entry.get('pairs') or []:
            stations.update(max(0., min(length, project(p))) for p in (pair['start'], pair['end']))
    pieces = []
    bounds = sorted(stations)
    for lo, hi in zip(bounds, bounds[1:]):
        if hi-lo <= .01:
            continue
        segment = [[start[i]+t*axis[i] for i in (0, 1)] for t in (lo, hi)]
        # First validate the entire union so a conflicting pending interval
        # cannot disappear when selecting the profiles that cover this piece.
        try:
            covering_vertical_contract(segment, entries, axis=axis)
        except ValueError as exc:
            pieces.append({'points': segment, 'width': hi-lo,
                           'pending': str(exc),
                           'vertical_partition': {'start_cm': lo, 'end_cm': hi}})
            continue
        candidates = []
        for entry in entries:
            try:
                candidates.append(covering_vertical_contract(segment, [entry], axis=axis))
            except ValueError:
                continue
        signatures = {
            (c['base_level_m'], c['top_level_m'],
             (c.get('mounting', {}).get(side) or {}).get('panel_base_cm'),
             (c.get('mounting', {}).get(side) or {}).get('panel_top_cm'))
            for c in candidates
        }
        if len(signatures) != 1 or None in next(iter(signatures), (None,)):
            pieces.append({'points': segment, 'width': hi-lo,
                           'pending': 'lateral invertida sem montagem local única e confirmada',
                           'vertical_partition': {'start_cm': lo, 'end_cm': hi}})
            continue
        contract = candidates[0]
        mount = contract['mounting'][side]
        if float(mount['h1_cm']) <= 0:
            pieces.append({'points': segment, 'width': hi-lo,
                           'pending': 'lateral invertida sem altura executiva positiva',
                           'vertical_partition': {'start_cm': lo, 'end_cm': hi}})
            continue
        pieces.append({'points': segment, 'width': hi-lo,
                       'section_contract': contract, 'face_height': mount['h1_cm'],
                       'vertical_partition': {'start_cm': lo, 'end_cm': hi}})
    return pieces


def split_inverted_lateral(points, entries, side):
    """Strict generation interface: no partial lateral when any interval is pending."""
    pieces = partition_inverted_lateral(points, entries, side)
    failures = list(dict.fromkeys(p['pending'] for p in pieces if p.get('pending')))
    if failures:
        raise ValueError('; '.join(failures))
    return pieces


def exclude_inverted_cap_junctions(source, entries, *, pillars=None):
    """Assembly spans stop at measured incident-beam faces, even above them.

    This is a cap modulation rule, independent of vertical collision in LV.
    Only owner intervals explicitly carrying a named beam interference are
    removed. Geometry and the removal ledger remain available for review.
    """
    from copy import deepcopy
    from shapely.geometry import Polygon, LineString
    from shapely.ops import unary_union
    from math import dist
    polygon = Polygon(source.get('geometry') or [])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('tampa invertida sem polígono válido')
    start, end = max(zip(list(polygon.exterior.coords), list(polygon.exterior.coords)[1:]),
                     key=lambda edge: dist(*edge))
    size = dist(start, end)
    axis = [(end[i]-start[i])/size for i in (0, 1)]
    station = lambda p: sum((p[i]-start[i])*axis[i] for i in (0, 1))
    across = lambda p: (p[0]-start[0])*(-axis[1])+(p[1]-start[1])*axis[0]
    across_low, across_high = min(map(across, polygon.exterior.coords)), max(map(across, polygon.exterior.coords))
    # Resolve exterior supports from a shared solid face, never a nearby name.
    # The same 0.15 cm contact tolerance accommodates normalized SA contours.
    source = deepcopy(source)
    for key, position in (('apoio_inicial', 0.), ('apoio_final', size)):
        face = LineString([(start[0]+axis[0]*position-axis[1]*a,
                            start[1]+axis[1]*position+axis[0]*a)
                           for a in (across_low, across_high)])
        candidates = set()
        for pillar in pillars or []:
            classification = str(pillar.get('classification') or '').upper().replace('_', ' ')
            if classification not in ('SEGUE', 'MORRE', 'MORRE AQUI'):
                continue
            solid = Polygon(pillar.get('points') or [])
            label = str(pillar.get('name') or pillar.get('key') or '').strip()
            if not label or not solid.is_valid or solid.is_empty:
                continue
            if polygon.intersection(solid).area > .15*face.length:
                continue
            if face.difference(solid.boundary.buffer(.15)).length <= 1e-5:
                candidates.add(label)
        if len(candidates) == 1:
            source[key] = candidates.pop()
        elif len(candidates) > 1:
            raise ValueError('extremidade da tampa com mais de um pilar de apoio')
    removed = []
    for entry in entries:
        for pair in entry.get('pairs') or []:
            names = sorted({str(o.get('name')) for o in pair.get('beam_interferences') or [] if o.get('name')})
            footprint = pair.get('footprint') or []
            if not names or len(footprint) < 3:
                continue
            mask = Polygon(footprint)
            if not mask.is_valid:
                raise ValueError('encontro de tampa com contorno inválido')
            # Current A/B contours have submillimetric normalization offsets.
            # Snap only a proven full-width rectangular encounter, using the
            # same physical contact tolerance as the slab/cut inventory.
            coords = list(mask.exterior.coords)
            lo, hi = min(map(station, coords)), max(map(station, coords))
            al, ah = min(map(across, coords)), max(map(across, coords))
            if (abs(mask.area-(hi-lo)*(ah-al)) <= .05
                    and al <= across_low+.15 and ah >= across_high-.15):
                widths = {float(o['width_cm']) for o in pair.get('beam_interferences') or []
                          if o.get('width_cm') is not None}
                if len(widths) == 1:
                    width = widths.pop()
                    if abs(hi-lo-width) <= .15:
                        if abs(hi-size) <= .15:
                            lo, hi = size-width, size
                        elif abs(lo) <= .15:
                            lo, hi = 0., width
                world = lambda t, a: [start[0]+axis[0]*t-axis[1]*a,
                                      start[1]+axis[1]*t+axis[0]*a]
                mask = Polygon([world(lo,across_low),world(hi,across_low),
                                world(hi,across_high),world(lo,across_high)])
            intersection = polygon.intersection(mask)
            if intersection.area > .01:
                removed.append((intersection, names))
    if not removed:
        return [deepcopy(source)]
    excluded = unary_union([p for p, _ in removed])
    remainder = polygon.difference(excluded)
    parts = list(remainder.geoms) if remainder.geom_type == 'MultiPolygon' else [remainder]
    if not parts or any(p.geom_type != 'Polygon' or p.is_empty for p in parts):
        raise ValueError('encontros não deixam vão de tampa executável')
    parts.sort(key=lambda p: min(station(q) for q in p.exterior.coords))
    if source.get('panels') or (source.get('ficha') or {}).get('panels'):
        raise ValueError('tampa pré-modulada atravessa encontro; revisar modulação')
    ledger = [{'names': names, 'geometry': [list(p) for p in shape.exterior.coords],
               'area_cm2': shape.area} for shape, names in removed]
    result = []
    for part in parts:
        coords = list(part.exterior.coords)
        low, high = min(map(station, coords)), max(map(station, coords))
        # A partial-width cut cannot become a rectangular cap silently.
        width = max(map(across, coords))-min(map(across, coords))
        if abs(part.area-(high-low)*width) > .05:
            raise ValueError('encontro parcial exige geometria especial da tampa')
        row = deepcopy(source)
        row.update(geometry=[list(p) for p in coords], length=high-low,
                   _longitudinal_frame=dict(origin=list(start), axis=list(axis)),
                   cap_assembly_rule='between_incident_beam_faces',
                   cap_assembly_span=dict(length_cm=high-low, geometry=[list(p) for p in coords]),
                   cap_junction_exclusions=deepcopy(ledger))
        for key, position, original in (('apoio_inicial', low, 0.), ('apoio_final', high, size)):
            if abs(position-original) <= .15:
                continue
            touching = {name for shape, names in removed
                        if min(abs(station(p)-position) for p in shape.exterior.coords) <= .15
                        for name in names}
            if len(touching) != 1:
                raise ValueError('limite da tampa sem encontro único identificado')
            row[key] = touching.pop()
        result.append(row)
    if abs(sum(Polygon(r['geometry']).area for r in result)+excluded.area-polygon.area) > 1e-5:
        raise ValueError('inventário de tampas e encontros não conserva a área original')
    return result


def split_inverted_soffit(source, entries):
    """Partition a measured FV at physical vertical-profile boundaries.

    Every piece must have complete, consistent coverage. Never drop a gap,
    copy a premodulated leaf across a transition, or change the input polygon.
    """
    from copy import deepcopy
    from math import dist
    from shapely.geometry import Polygon, box
    from shapely.affinity import affine_transform
    points = source.get('geometry') or []
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('fundo invertido sem polígono válido')
    edges = list(zip(points,points[1:]+points[:1]))
    start,end = max(edges,key=lambda e:dist(*e))
    size=dist(start,end)
    if size <= .01:
        raise ValueError('fundo invertido sem extensão')
    ux,uy=((end[i]-start[i])/size for i in (0,1))
    frame = source.get('_longitudinal_frame') or {}
    if frame:
        start = frame['origin']
        ux, uy = frame['axis']
    vx,vy=-uy,ux
    local=affine_transform(polygon,[ux,uy,vx,vy,
        -start[0]*ux-start[1]*uy,-start[0]*vx-start[1]*vy])
    low,across_low,high,across_high=local.bounds
    stations={low,high}
    for entry in entries:
        for pair in entry.get('pairs') or []:
            a,b=pair['start'],pair['end']
            length=dist(a,b)
            if length <= .01 or abs(((b[0]-a[0])*ux+(b[1]-a[1])*uy)/length) < .9999:
                continue
            margin=float((entry.get('section_contract') or {}).get('width_cm') or 0)/2+.5
            if any(not across_low-margin <= (p[0]-start[0])*vx+(p[1]-start[1])*vy <= across_high+margin for p in (a,b)):
                continue
            stations.update(max(low,min(high,(p[0]-start[0])*ux+(p[1]-start[1])*uy)) for p in (a,b))
    regions=[]
    for a,b in zip(sorted(stations),sorted(stations)[1:]):
        if b-a <= 1e-7:
            continue
        part=local.intersection(box(a,across_low-1,b,across_high+1))
        if part.geom_type != 'Polygon' or part.area <= 0:
            raise ValueError('subdivisão de fundo invertido exige revisão da geometria')
        world=affine_transform(part,[ux,vx,uy,vy,*start])
        try:
            contract=covering_vertical_contract(list(world.exterior.coords),entries, axis=(ux,uy))
        except ValueError as exc:
            raise ValueError(f'{exc}; trecho {a:g}–{b:g} cm, contorno {tuple(round(v,3) for v in world.bounds)}') from exc
        signature=tuple(contract[k] for k in ('width_cm','height_cm','base_level_m','top_level_m'))
        if regions and regions[-1][2]==signature:
            regions[-1]=(regions[-1][0],b,signature,contract)
        else:
            regions.append((a,b,signature,contract))
    if len(regions)>1 and (source.get('panels') or (source.get('ficha') or {}).get('panels')):
        raise ValueError('fundo com painéis pré-modulados atravessa mudança de perfil; revisar modulação')
    result=[]
    for index,(a,b,signature,contract) in enumerate(regions):
        part=local.intersection(box(a,across_low-1,b,across_high+1))
        world=affine_transform(part,[ux,vx,uy,vy,*start])
        row=deepcopy(source)
        row.update(geometry=[list(p) for p in world.exterior.coords],length=b-a,
                   dim_width=contract['width_cm'],dim_height=contract['height_cm'],
                   dim_text=f"{contract['width_cm']:g}/{contract['height_cm']:g}",
                   _vertical_contract=contract,
                   vertical_partition=dict(index=index,start_cm=a,end_cm=b,
                       source_length_cm=high-low,source_uid=source.get('uid')))
        if index: row['apoio_inicial']=''
        if index<len(regions)-1: row['apoio_final']=''
        result.append(row)
    if abs(sum(Polygon(r['geometry']).area for r in result)-polygon.area)>1e-5:
        raise ValueError('subdivisão vertical não preserva a área do fundo')
    return result
