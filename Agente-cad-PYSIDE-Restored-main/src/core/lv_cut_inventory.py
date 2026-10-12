"""Inventário derivado de cortes LV; não altera o schema nem os vínculos N1.

Pares são sobreposições longitudinais reais entre faces paralelas A/B.
Uma seção reúne todos os trechos equivalentes, preservando cada par de origem.
"""
from __future__ import annotations

from hashlib import sha256
import html
import json
import math
import re

# Normalized CAD faces and slab contours can differ by 0.10 cm.
# This is a contact tolerance, never a nearest-slab search.
SLAB_CONTACT_CM = .15
# Same containment allowance as slab_steps.recognize_slabs: this only
# reconciles a recognized inset with its normalized owner contour. It does
# not widen the subsequent slab/beam contact search.
SLAB_REGION_OWNER_CM = .5


def number(value):
    if isinstance(value, bool):
        return None
    match = re.fullmatch(r'\s*(?:h\s*=\s*)?([-+]?\d+(?:[.,]\d+)?)\s*(?:cm)?\s*', str(value or ''))
    if not match:
        return 0.0 if value == 0 else None
    result = float(match[1].replace(',', '.'))
    return result if math.isfinite(result) else None


def _key(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def geometry_key(points):
    """Mesmo polígono com ordem/origem de vértices diferentes continua um corte."""
    try:
        return tuple(sorted(set((round(float(p[0]), 3), round(float(p[1]), 3)) for p in points)))
    except (TypeError, ValueError, IndexError):
        return ()


def invalid_cut(raw):
    status = str(raw.get('status') or '').upper()
    return bool(raw.get('is_invalid')) or any(s in status for s in ('NÃO É', 'NAO E', 'ERRADA', 'SOLIDA', 'SÓLIDA', 'PILAR'))


def collect_explicit_cuts(state_cuts, slabs=(), preprocessing=()):
    """Union SA + vínculos ricos das lajes + pré-processamento, sem nearest-name."""
    groups = {}
    rejected = {geometry_key(r.get('pts') or r.get('points') or []) for r in state_cuts if invalid_cut(r)} - {()}
    rejected_ids = {str(r.get('uid')) for r in state_cuts if invalid_cut(r)}

    def add(raw, origin):
        if invalid_cut(raw):
            return
        points = raw.get('pts') or raw.get('points') or []
        geom = geometry_key(points)
        uid = str(raw.get('uid') or raw.get('item_id') or raw.get('id') or '')
        if geom in rejected or uid in rejected_ids:
            return
        identity = ('geometry', geom) if geom else ('uid', uid or _key(raw))
        existing = groups.get(identity)
        if existing is None:
            existing = dict(raw, uid=uid or 'cut-'+_key(identity), pts=points, origins=[], evidence_ids=[])
            groups[identity] = existing
        for key, value in raw.items():
            if key == 'ficha':
                existing['ficha'] = {**(raw.get('ficha') or {}), **(existing.get('ficha') or {})}
            elif existing.get(key) in (None, '', [], {}):
                existing[key] = value
        if origin not in existing['origins']:
            existing['origins'].append(origin)
        for evidence in [uid, *raw.get('source_entity_handles', [])]:
            if evidence and evidence not in existing['evidence_ids']:
                existing['evidence_ids'].append(evidence)

    for raw in state_cuts:
        add(raw, 'sa')  # assignments/status do snapshot prevalecem
    for slab in slabs:
        links = slab.get('links') or {}
        for field in ('laje_visao_corte', 'laje_nivel'):
            for raw in (links.get(field) or {}).get('cut_view_geom') or []:
                ficha = raw.get('ficha') or {}
                points = raw.get('points') or []
                if points:
                    x = (min(p[0] for p in points)+max(p[0] for p in points))/2
                    y = (min(p[1] for p in points)+max(p[1] for p in points))/2
                    uid = f"{slab.get('name')}_{round(x)}_{round(y)}"
                else:
                    uid = raw.get('id') or 'cut-'+_key(raw)
                own = slab.get('name')
                neighbor = ficha.get('side_b_laje_name') if own == ficha.get('side_a_laje_name') else ficha.get('side_a_laje_name')
                add({**raw, 'uid': uid, 'beam_name': ficha.get('beam_name'),
                     'own_laje': own, 'neigh_laje': neighbor,
                     'beam_h': ficha.get('beam_height'), 'beam_w': ficha.get('beam_bottom_dim'),
                     'conf_pct': (number(ficha.get('beam_name_confidence')) or 0)*100,
                     'status': 'Identificado no SA'}, 'sa_links')
    for raw in preprocessing:
        section = raw.get('section_geometry') or {}
        if isinstance(section, list):
            section = {'points': section}
        add({**raw, 'uid': raw.get('item_id'), 'pts': section.get('points') or raw.get('points') or [],
             'beam_name': raw.get('beam_name') or raw.get('beam_id'),
             'status': raw.get('status') or 'Pendente'}, 'preprocessamento')
    return list(groups.values())


def _edges(segment):
    points = segment.get('points') or []
    for a, b in zip(points, points[1:]):
        try:
            a, b = tuple(map(float, a[:2])), tuple(map(float, b[:2]))
            length = math.dist(a, b)
            if length > .5:
                yield a, b, length
        except (TypeError, ValueError, IndexError):
            continue


def _slab_regions(slab):
    """Physical regions, without spreading an inset's h/level over its owner."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    owner = Polygon(slab.get('points') or [])
    if not owner.is_valid or owner.is_empty or owner.area <= 0:
        return []
    steps = slab.get('slab_steps') or []
    if not steps:
        return [(owner, slab)]
    regions = []
    for step in steps:
        shape = Polygon(step.get('points') or [])
        if (shape.is_valid and not shape.is_empty and shape.area > 0
                and owner.buffer(SLAB_REGION_OWNER_CM).covers(shape)):
            # Keep the CAD evidence points untouched. Only the derived
            # contact geometry is clipped, so rounding cannot claim area
            # outside the owner or discard an otherwise proven region.
            clipped = shape.intersection(owner)
            if (clipped.is_valid and not clipped.is_empty and clipped.area > 0
                    and clipped.geom_type in ('Polygon', 'MultiPolygon')):
                regions.append((clipped, step))
    if not regions:
        return [(owner, slab)]
    heights = {number(s.get('owner_height_cm')) for _, s in regions}
    levels = {number(s.get('owner_level_m')) for _, s in regions}
    principal = {**slab, 'region_id': 'principal',
                 'height': next(iter(heights)) if len(heights) == 1 else None,
                 'nivel': next(iter(levels)) if len(levels) == 1 else None,
                 '_region_scoped': True}
    # The CAD inset may miss the owner's boundary by normalization rounding.
    # Reserve twice the contact tolerance from the principal: the
    # subsequent contact buffer must not bridge that rounding strip back.
    result = [(owner.difference(unary_union([p.buffer(2*SLAB_CONTACT_CM) for p, _ in regions])), principal)]
    result.extend((p, {**slab, 'region_id': s['uid'], 'height': number(s.get('height_cm')),
                       'nivel': number(s.get('level_m')), '_region_scoped': True})
                  for p, s in regions)
    return result


def prepare_slab_regions(slabs):
    """Immutable geometry reused within one current source snapshot."""
    result = []
    for slab in slabs:
        try:
            for polygon, region in _slab_regions(slab):
                if polygon.is_valid and not polygon.is_empty:
                    result.append((polygon, polygon.buffer(SLAB_CONTACT_CM), region))
        except (TypeError, ValueError, AttributeError):
            continue
    return result


def _slab_ranges(slabs, a, u, low, high, prepared=None):
    from shapely.geometry import LineString, Polygon
    line = LineString([(a[0]+u[0]*low, a[1]+u[1]*low), (a[0]+u[0]*high, a[1]+u[1]*high)])
    rows = []
    for polygon, buffered, region in prepare_slab_regions(slabs) if prepared is None else prepared:
        try:
                if polygon.distance(line) > .5:
                    continue
                contact = buffered.intersection(line)
                # Each connected contact keeps its own physical interval.
                for part in getattr(contact, 'geoms', [contact]):
                    if part.geom_type != 'LineString':
                        continue
                    coords = list(part.coords)
                    values = [(p[0]-a[0])*u[0]+(p[1]-a[1])*u[1] for p in coords]
                    if max(values)-min(values) > .5:
                        rows.append((max(low, min(values)), min(high, max(values)), region))
        except (TypeError, ValueError, AttributeError):
            continue
    return rows


def _profile(segment, slabs):
    rows = []
    for slab in slabs:
        fields = slab.get('fields') or {}
        scoped = slab.get('_region_scoped')
        rows.append({'name': slab.get('name'), 'height_cm': number(slab.get('height') or slab.get('laje_dim') or fields.get('laje_dim')),
                     'level': number(slab.get('nivel') or slab.get('level') or slab.get('laje_nivel') or fields.get('laje_nivel')),
                     'region_id': slab.get('region_id')})
        if scoped:
            # Missing regional evidence must not fall back to an unscoped scalar.
            rows[-1].update(height_cm=number(slab.get('height')), level=number(slab.get('nivel')))
    level = number(segment.get('level'))
    source = segment.get('level_source')
    # Cell-derived levels can predate the current regional slab evidence.
    # Resolve them from this physical contact; explicit beam data retain
    # precedence and must still be cross-checked against the slab.
    local_levels = [r['level'] for r in rows if r['level'] is not None]
    if (source == 'lv_cell_slabs' or 'estim' in str(source)) and local_levels and all(r['level'] is not None for r in rows):
        level, source = max(local_levels), 'paired_touching_slabs'
    return {'width_cm': number(segment.get('width_cm')), 'height_cm': number(segment.get('beam_height_cm')),
            'level': level, 'level_source': source, 'slabs': rows}


def _profile_key(profile, datum):
    # Nome não multiplica uma seção fisicamente igual. Lacuna de medida não é equivalência provada.
    relative = lambda level: round((level-datum)*100, 3) if level is not None and datum is not None else None
    slabs = sorted([(s['height_cm'], relative(s['level']), s['name'] if s['height_cm'] is None or s['level'] is None else '')
                   for s in profile['slabs']], key=repr)
    return [profile['width_cm'], profile['height_cm'], relative(profile['level']), slabs]


def _opening_ranges(segment, origin, direction, low, high):
    """Project opening arclengths in the segment's original reading direction."""
    rows = []
    for opening in segment.get('beam_openings') or []:
        position = number(opening.get('position_cm'))
        width = number(opening.get('width_cm'))
        if position is None or width is None or width <= 0:
            continue
        travelled = 0.
        for a, b, length in _edges(segment):
            parallel = abs(sum((b[i]-a[i])*direction[i] for i in (0,1))/length) >= .9999
            offset = abs((a[0]-origin[0])*(-direction[1])+(a[1]-origin[1])*direction[0])
            if not parallel or offset > .5:
                travelled += length
                continue
            left, right = max(position, travelled), min(position+width, travelled+length)
            if right > left:
                values = []
                for distance in (left-travelled, right-travelled):
                    point = [a[i]+(b[i]-a[i])*distance/length for i in (0,1)]
                    values.append(sum((point[i]-origin[i])*direction[i] for i in (0,1)))
                l, h = max(low,min(values)), min(high,max(values))
                if h > l:
                    rows.append((l,h,opening))
            travelled += length
    return rows


def _pillar_ranges(pillars, origin, direction, low, high):
    """Exclude measured support footprints at the beam centerline."""
    from shapely.geometry import Polygon, LineString
    line = LineString([[origin[i]+direction[i]*t for i in (0,1)] for t in (low,high)])
    rows = []
    for pillar in pillars:
        # Match the SA support policy: a column born above this floor does
        # not interrupt the beam or its physical section coverage.
        if (pillar.get('ignore_in_beams')
                or str(pillar.get('classification') or '').strip().upper() == 'NASCE'):
            continue
        points = pillar.get('points') or pillar.get('pts') or []
        if len(points) < 3:
            continue
        polygon = Polygon(points)
        if not polygon.is_valid:
            continue
        contact = polygon.intersection(line)
        for part in getattr(contact, 'geoms', [contact]):
            if part.geom_type == 'LineString' and part.length > .01:
                stations = [sum((p[i]-origin[i])*direction[i] for i in (0,1)) for p in part.coords]
                rows.append((max(low,min(stations)),min(high,max(stations)),pillar))
    return rows


def pair_sections(beam, behavior, sides, slabs=(), pillars=(), *, retain_opening_intervals=False, slab_regions=None):
    groups = {}
    slab_regions = prepare_slab_regions(slabs) if slab_regions is None else slab_regions
    diagnostics = {'pairs': 0, 'unpaired': [], 'conflicts': [], 'opening_exclusions': [], 'pillar_exclusions': []}
    paired = set()
    for A in sides.get('A', {}).get('segments', []):
        for B in sides.get('B', {}).get('segments', []):
            for a, end_a, length in _edges(A):
                u = ((end_a[0]-a[0])/length, (end_a[1]-a[1])/length)
                # Orientação canônica independe do sentido A/B.
                if u[0] < -1e-8 or (abs(u[0]) < 1e-8 and u[1] < 0):
                    a, end_a = end_a, a
                    u = (-u[0], -u[1])
                for b, end_b, len_b in _edges(B):
                    v = ((end_b[0]-b[0])/len_b, (end_b[1]-b[1])/len_b)
                    if abs(u[0]*v[0]+u[1]*v[1]) < .9999:
                        continue
                    offset = (b[0]-a[0])*(-u[1])+(b[1]-a[1])*u[0]
                    separation = abs(offset)
                    widths = [w for w in (number(A.get('width_cm')), number(B.get('width_cm'))) if w is not None]
                    if not widths or separation < .5 or separation > max(widths)+.5:
                        continue
                    t1 = (b[0]-a[0])*u[0]+(b[1]-a[1])*u[1]
                    t2 = (end_b[0]-a[0])*u[0]+(end_b[1]-a[1])*u[1]
                    lo, hi = max(0, min(t1,t2)), min(length,max(t1,t2))
                    if hi-lo <= .5:
                        continue
                    b_origin = (a[0]-u[1]*offset, a[1]+u[0]*offset)
                    ranges_a = _slab_ranges(slabs, a, u, lo, hi, slab_regions)
                    ranges_b = _slab_ranges(slabs, b_origin, u, lo, hi, slab_regions)
                    openings = [('A',l,h,o) for l,h,o in _opening_ranges(A,a,u,lo,hi)]
                    openings += [('B',l,h,o) for l,h,o in _opening_ranges(B,b_origin,u,lo,hi)]
                    center_origin = tuple((a[i]+b_origin[i])/2 for i in (0,1))
                    supports = _pillar_ranges(pillars,center_origin,u,lo,hi)
                    openings += [('pillar',l,h,{'name':p.get('name')}) for l,h,p in supports]
                    raw_boundaries = sorted({round(x, 3) for x in [lo,hi] + [x for l,h,s in ranges_a+ranges_b for x in (l,h)] + [x for side,l,h,o in openings for x in (l,h)]})
                    clusters = []
                    for boundary in raw_boundaries:
                        if clusters and boundary-clusters[-1][-1] <= .5:
                            clusters[-1].append(boundary)
                        else:
                            clusters.append([boundary])
                    boundaries = [sum(c)/len(c) for c in clusters]
                    boundaries[0], boundaries[-1] = lo, hi
                    for left, right in zip(boundaries, boundaries[1:]):
                        if right-left <= .5:
                            continue
                        middle = (left+right)/2
                        interference = [(side,o) for side,l,h,o in openings if l <= middle <= h]
                        if interference and (not retain_opening_intervals or any(s == 'pillar' for s,o in interference)):
                            bucket = 'pillar_exclusions' if any(s == 'pillar' for s,o in interference) else 'opening_exclusions'
                            diagnostics[bucket].append(dict(
                                a_id=A['id'],b_id=B['id'],length_cm=round(right-left,3),
                                start=[round(a[i]+u[i]*left,3) for i in (0,1)],
                                end=[round(a[i]+u[i]*right,3) for i in (0,1)],
                                openings=[dict(side=s, **o) for s,o in interference]))
                            paired.update((A['id'],B['id']))
                            continue
                        pa = _profile(A, [s for l,h,s in ranges_a if l <= middle <= h])
                        pb = _profile(B, [s for l,h,s in ranges_b if l <= middle <= h])
                        levels = [p['level'] for p in (pa,pb) if p['level'] is not None]
                        datum = max(levels) if levels else None
                        signature = [_profile_key(pa, datum), _profile_key(pb, datum)]
                        # Ausência de nível/dimensão não autoriza agrupar trechos desconhecidos.
                        if any(p[k] is None for p in (pa,pb) for k in ('width_cm','height_cm','level')):
                            signature.append([A['id'],B['id']])
                        key = _key(signature)
                        row = groups.setdefault(key, {'id': f'lv-cut-{beam}-{behavior}-{key}', 'beam':beam,
                            'kind':'calculated', 'origins':['pares_ab'], 'profiles':{'A':pa,'B':pb},
                            'beam_height_cm': pa['height_cm'] if pa['height_cm']==pb['height_cm'] else None,
                            'width_cm': pa['width_cm'] if pa['width_cm']==pb['width_cm'] else None,
                            'pairs':[], 'status':'Calculado A/B', 'attention':'', 'confidence_percent':None,
                            'own_slab':None, 'neighbor_slab':None})
                        row['pairs'].append({'a_id':A['id'],'b_id':B['id'],'a_index':A['index'],'b_index':B['index'],
                            'profiles': {'A':pa, 'B':pb},
                            'footprint': [[round(a[i]+u[i]*t,3) for i in (0,1)] for t in (left,right)] +
                                         [[round(b_origin[i]+u[i]*t,3) for i in (0,1)] for t in (right,left)],
                            'length_cm':round(right-left,3), 'start': [round(a[0]+u[0]*left,3),round(a[1]+u[1]*left,3)],
                            'end':[round(a[0]+u[0]*right,3),round(a[1]+u[1]*right,3)],
                            'dimension_span': [[a[i]+u[i]*lo for i in (0,1)], [a[i]+u[i]*hi for i in (0,1)]],
                            'a_slabs':[s['name'] for s in pa['slabs']], 'b_slabs':[s['name'] for s in pb['slabs']]})
                        if interference:
                            row['pairs'][-1]['beam_interferences'] = [dict(side=s, **o) for s,o in interference]
                        paired.update((A['id'], B['id']))
                        warnings=[]
                        if pa['width_cm']!=pb['width_cm'] or pa['height_cm']!=pb['height_cm']:
                            warnings.append('dimensões A/B divergentes')
                        if any(p[k] is None for p in (pa,pb) for k in ('width_cm','height_cm','level')):
                            warnings.append('medidas incompletas')
                        if any('estim' in str(p['level_source']) or 'nearest' in str(p['level_source']) for p in (pa,pb)):
                            warnings.append('nível estimado')
                        if any(abs(separation-w)>.5 for w in widths):
                            warnings.append('distância entre faces difere da largura')
                        row['attention'] = '; '.join(dict.fromkeys([w for w in row['attention'].split('; ') if w] + warnings))
                        if warnings: row['status']='Calculado · revisar'
                        diagnostics['pairs'] += 1
    for side in ('A','B'):
        diagnostics['unpaired'].extend({'side':side,'id':s['id'],'index':s['index']} for s in sides.get(side,{}).get('segments',[]) if s['id'] not in paired)
    # Cobertura mede trechos sem contraparte, inclusive em segmentos parcialmente pareados.
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    diagnostics['coverage_gaps'] = []
    for side in ('A','B'):
        for segment in sides.get(side,{}).get('segments',[]):
            intervals = []
            for a, b, length in _edges(segment):
                ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
                for row in groups.values():
                    for pair in row['pairs']:
                        if pair[side.lower()+'_id'] != segment['id']:
                            continue
                        vals = [(p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (pair['start'],pair['end'])]
                        lo, hi = max(0,min(vals)), min(length,max(vals))
                        if hi > lo:
                            intervals.append(LineString([(lo,0),(hi,0)]))
                for exclusion in diagnostics['opening_exclusions'] + diagnostics['pillar_exclusions']:
                    if exclusion[side.lower()+'_id'] == segment['id']:
                        vals = [(p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (exclusion['start'],exclusion['end'])]
                        lo,hi = max(0,min(vals)),min(length,max(vals))
                        if hi > lo:
                            intervals.append(LineString([(lo,0),(hi,0)]))
                covered = unary_union(intervals).length if intervals else 0
                gap = max(0,length-covered)
                if gap > .5:
                    diagnostics['coverage_gaps'].append({'side':side,'id':segment['id'],'index':segment['index'],'length_cm':round(gap,3)})
                overlap = sum(i.length for i in intervals)-covered
                if overlap > .5:
                    diagnostics['conflicts'].append({'side':side,'id':segment['id'],'index':segment['index'],'overlap_cm':round(overlap,3)})
                intervals = []
    return list(groups.values()), diagnostics


def section_svg(cut):
    """Esquema estrutural SA, sem inventar montagem STOG nem consultar N2/N3."""
    width, height = cut.get('width_cm'), cut.get('beam_height_cm')
    if not width or not height:
        return None
    profiles = cut['profiles']
    levels = [p['level'] for p in profiles.values() if p['level'] is not None]
    if len(levels)!=2:
        return None
    top=max(levels)
    scale=min(5.,260/height,150/width)
    x,y,w,h=360.,100.,width*scale,height*scale
    pieces=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 480"><rect width="900" height="480" fill="#07131f"/>',
        f'<text x="30" y="35" fill="#fff" font-size="20">{html.escape(cut["beam"])} · seção calculada A/B</text>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#173649" stroke="#4fc3a1" stroke-width="2"/>',
        f'<text x="{x+w/2}" y="{y+h+30}" fill="#fff" text-anchor="middle">{width:g} × {height:g} cm</text>']
    for side,px in [('A',x-145),('B',x+w)]:
        pieces.append(f'<text x="{px}" y="75" fill="#87c9ff">Lado {side} · nível {profiles[side]["level"]:g} m</text>')
        for slab in profiles[side]['slabs']:
            if slab['height_cm'] is None or slab['level'] is None: continue
            sy=y+(top-slab['level'])*100*scale
            sh=slab['height_cm']*scale
            pieces.append(f'<rect x="{px}" y="{sy}" width="145" height="{sh}" fill="#173649" stroke="#4fc3a1"/>')
            pieces.append(f'<text x="{px}" y="{sy-8}" fill="#fff">{html.escape(str(slab["name"]))} · h={slab["height_cm"]:g}</text>')
    pieces.append(f'<text x="30" y="435" fill="#ffcb80">{html.escape(cut.get("attention") or "Interpretação geométrica; confirmação humana pendente")}</text></svg>')
    return ''.join(pieces)
