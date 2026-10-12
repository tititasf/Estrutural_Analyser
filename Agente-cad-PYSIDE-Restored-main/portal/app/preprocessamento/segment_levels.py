"""Derived level convention: spatial correspondence, explicit evidence and scores.

Scores measure evidence completeness, not a calibrated probability. Raw SA geometry
and human fields are untouched. Transfers only read independent, frozen seeds.
"""
from copy import deepcopy
import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

TOL = .0025  # metres; never merge a centimetre step
CONTACT_CM = 1.0


def preserve_local_seed_over_estimated_fv(native, sources):
    """A weak agreeing FV is geometry, not a replacement for local slab proof.

    Explicit cuts/profile readings and disagreements retain normal precedence.
    No estimated FV enters the retained seed's level ancestry or support score.
    """
    if (native.get('status') not in ('inferred', 'sa_evidence')
            or native.get('method') != 'spatial_slab_region_reference'
            or (native.get('confidence_pct') or 0) < 50
            or not native.get('source_fact_ids') or native.get('value') is None
            or not sources):
        return False
    return all(
        source.get('status') in ('estimated', 'unknown')
        and (source.get('confidence_pct') or 0) < 50
        and source.get('value') is not None
        and abs(source['value'] - native['value']) <= TOL
        and 'cut' not in str(source.get('method') or '').lower()
        and not any(source.get(k) for k in ('cut_id', 'cut_ids', 'cut_profile_geometry',
                                           'cut_association', 'shortened_section_top_read'))
        for source in sources
    )


def numeric(value):
    try:
        value = float(str(value).replace(',', '.'))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def geometry(points):
    try:
        if len(points) > 3 and points[0] == points[-1]:
            shape = Polygon(points).buffer(0)
        else:
            shape = LineString(points)
        return shape if not shape.is_empty else None
    except (TypeError, ValueError):
        return None


def cut_break_shapes(context):
    """Two parallel red strokes denote a shortened section (not a scale)."""
    if not context.get('tower_path'):
        return []
    import ezdxf
    try:
        doc = ezdxf.readfile(context['tower_path'])
    except (OSError, ezdxf.DXFError):
        return []
    red = []
    for entity in doc.modelspace():
        color = entity.dxf.get('color', 256)
        if color == 256:
            color = doc.layers.get(entity.dxf.layer).dxf.color
        if color != 1:
            continue
        if entity.dxftype() == 'LINE':
            pts = [tuple(entity.dxf.start)[:2], tuple(entity.dxf.end)[:2]]
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = [tuple(p)[:2] for p in entity.get_points()]
        else:
            continue
        for a,b in zip(pts,pts[1:]):
            line = LineString([a,b])
            if 5 <= line.length <= 100:
                red.append(line)
    breaks = []
    for i,a in enumerate(red):
        av = (a.coords[-1][0]-a.coords[0][0],a.coords[-1][1]-a.coords[0][1])
        for b in red[i+1:]:
            if not 1 <= a.distance(b) <= 10:
                continue
            bv = (b.coords[-1][0]-b.coords[0][0],b.coords[-1][1]-b.coords[0][1])
            cosine = abs((av[0]*bv[0]+av[1]*bv[1])/(a.length*b.length))
            if cosine >= .98 and .8 <= a.length/b.length <= 1.25 and a.centroid.distance(b.centroid)<=15:
                breaks.append(unary_union([a,b]))
    return breaks


def break_spares_top(profile, breaks, own_top_cm):
    """A break line only invalidates the measurements that cross it.

    In an upright T section shortened through the stem, the slab wings and the
    beam top lie above the break: the top offset is read there, directly from
    the drawn outline (never from a depth chain through the break). Returns the
    reading, or None when the break reaches the wings, the section is not an
    upright T/L with a wing, or the drawn offsets do not contain the stated one.
    """
    from shapely.geometry import LineString
    if profile is None or profile.geom_type != 'Polygon' or own_top_cm is None:
        return None
    x0, y0, x1, y1 = profile.bounds

    def column(x):
        hit = profile.intersection(LineString([(x, y0-1), (x, y1+1)]))
        return None if hit.is_empty else hit.bounds

    feet = [p for p in profile.exterior.coords if p[1] <= y0+.5]
    stem_x = sum(p[0] for p in feet)/len(feet) if feet else None
    left, right = column(x0+.5), column(x1-.5)
    if stem_x is None or not x0+1 < stem_x < x1-1 or left is None or right is None:
        return None
    stem = column(stem_x)
    # Wings (T: two, edge-beam L: one) end well above the stem foot.
    wings = [c for c in (left, right) if stem is not None and c[1] > stem[1]+1]
    if not wings:
        return None
    wing_bottom = min(c[1] for c in wings)
    if any(b.bounds[3] >= wing_bottom for b in breaks):
        return None
    offsets = sorted({round(stem[3]-c[3], 1) for c in wings})
    if not any(abs(o-own_top_cm) <= .5 for o in offsets):
        return None
    return dict(drawn_top_offsets_cm=offsets, wing_bottom_above_break_cm=round(wing_bottom-max(b.bounds[3] for b in breaks), 1))


def cut_region_source(item, shape):
    """Own level of a multipart slab where its cut drawing sits.

    A multipart slab has no scalar level; the cut belongs to the region it
    touches. Only a single touched level is accepted, never a guess.
    """
    from shapely.geometry import shape as from_geojson
    if not item or shape is None:
        return None
    touched = [f for f in item['levels'] if f.get('field') == 'slab_region_level'
               and f.get('value') is not None and f.get('region_geometry')
               and f.get('status') not in ('conflict', 'candidate', 'estimated', 'unknown')
               and from_geojson(f['region_geometry']).distance(shape) <= CONTACT_CM]
    if len({round(f['value'], 4) for f in touched}) != 1:
        return None
    return max(touched, key=lambda f: f.get('confidence_pct') or 0)


# A region level produced by the neighbour vote, not by a measured step cut.
LAYERED_REGION_METHODS = ('slab_neighbor_continuity_without_step_cut',
                          'slab_neighbor_majority_vote')


def cut_owner_level(slab_name, shape, slab_sources, slab_items):
    """Scalar of the slab, unless the cut sits on a voted region of another level.

    The CAD mark inside a rebaixo becomes the slab scalar. A cut drawn on the
    principal reads that region's own vote (L413 at 855.25), not the rebaixo
    mark. A measured step that already had its level (L320) does not replace
    the scalar.
    """
    scalar = slab_sources.get(slab_name)
    regional = cut_region_source(slab_items.get(slab_name), shape)
    if (regional and regional.get('method') in LAYERED_REGION_METHODS
            and (scalar is None or abs(regional['value'] - scalar['value']) > TOL)):
        return regional
    return scalar or regional


def score(fact):
    """Versioned, reproducible rubric; a missing altitude has zero support."""
    status, method = fact.get('status'), fact.get('method', '')
    if fact.get('value') is None or status == 'not_applicable':
        base = 0
    elif status == 'human_review':
        base = 100
    elif status == 'conflict':
        base = 20
    elif method == 'cad_level_inside_slab':
        base = 95
    elif status == 'floor_reference':
        base = 25
    elif status in ('estimated', 'candidate'):
        base = 30
    elif status == 'inferred':
        base = 65 if 'paired' in method or 'cut' in method else 55
    else:
        base = 75
    penalties = {'multiple_plan_levels_require_part_review': 0,
                 'source_slab_level_not_uniquely_observed': 15,
                 'source_slab_requires_review': 15,
                 'unresolved_cut_level_alternative': 20,
                 'automatic_beam_field_without_cad_level_provenance': 30}
    components = {'origin_support': base}
    for warning in set(fact.get('warnings') or []):
        if penalties.get(warning):
            components[warning] = -penalties[warning]
    fact.update(confidence_pct=max(0, sum(components.values())),
                confidence_method='level_evidence_completeness_v1', confidence_components=components)


def segment_region_source(item, shape, record):
    """Multi-part slab: the level region the segment runs along, if unique.

    A touch confined to an endpoint is not contact.  The region must agree with
    the segment's own value; otherwise the provenance stays incomplete.
    """
    from shapely.geometry import shape as from_geojson
    if not item or shape is None or record.get('value') is None:
        return None
    touched = []
    for f in item.get('levels', []):
        if (f.get('field') != 'slab_region_level' or not f.get('region_geometry') or f.get('value') is None
                or f.get('status') in ('unknown', 'conflict', 'candidate', 'estimated')):
            continue
        hit = shape.intersection(from_geojson(f['region_geometry']).buffer(CONTACT_CM))
        size = hit.area if shape.geom_type == 'Polygon' else hit.length
        if size > (CONTACT_CM**2 if shape.geom_type == 'Polygon' else CONTACT_CM):
            touched.append(f)
    values = {round(f['value'], 4) for f in touched}
    if len(values) != 1 or abs(next(iter(values))-record['value']) > .0025:
        return None
    return max(touched, key=lambda f: f.get('confidence_pct') or 0)


STALE_SLAB_WARNINGS = {'source_slab_level_not_uniquely_observed', 'source_slab_requires_review'}


def stale_slab_penalty_lift(record, seg, sources, shape, contacts, datum=None):
    """Native score without the SA-time slab penalties, once the slabs are proven.

    The SA flags a beam whose source slab was not yet observed; the slab layers
    may prove it later.  The penalty yields only when every source slab is
    proven at the beam value and no proven slab touching the segment states
    another level.  A lower slab touching a beam at the storey datum is a step
    closed by the top panel (NIV-VIGA-LAJE-PAINEL), not a contradiction.
    No bonus: the weakest source still caps the result.
    """
    at_datum = (datum is not None and datum.get('value') is not None
                and datum.get('status') not in ('unknown', 'conflict', 'candidate', 'estimated')
                and record.get('value') is not None and abs(datum['value']-record['value']) <= .0025)
    if not (STALE_SLAB_WARNINGS & set(record.get('warnings') or [])) or record.get('value') is None:
        return None
    if len(sources) != len(seg.get('level_slabs') or []):
        return None
    if any(s.get('status') in ('estimated', 'candidate', 'conflict', 'unknown')
           or s.get('value') is None or abs(s['value']-record['value']) > .0025 for s in sources):
        return None
    if shape is not None:
        for _, region, source in contacts:
            if (source.get('value') is not None and source.get('status') not in ('unknown', 'conflict', 'candidate', 'estimated')
                    and abs(source['value']-record['value']) > .0025
                    and not (at_datum and source['value'] < record['value'])
                    and not shape.intersection(region.buffer(1.0)).is_empty):
                return None
    native = deepcopy(record)
    native['warnings'] = sorted(set(native.get('warnings') or []) - STALE_SLAB_WARNINGS)
    if native['status'] == 'inferred' and not native['warnings']:
        native['status'] = 'sa_evidence'
    score(native)
    return native['confidence_pct']


def confirmations(used, pool):
    """Agreeing alternatives, listed for audit; they never add score."""
    ids = {u['fact_id'] for u in used}
    return [{'fact_id': c['fact_id'], 'method': c.get('method'), 'value': c.get('value'),
             'confidence_pct': c.get('confidence_pct'), 'cut_id': c.get('cut_id')}
            for c in pool if c['fact_id'] not in ids]


def cut_matches_fund(profile, fund, depth, height_evidence=None):
    """Associate a section by geometry: stem inside the FV with its depth and width."""
    from shapely.geometry import shape as from_geojson
    if not profile or fund is None or fund.geom_type != 'Polygon' or numeric(depth) is None:
        return False
    x0, y0, x1, y1 = fund.bounds
    axis = 0 if x1-x0 >= y1-y0 else 1
    width = (y1-y0) if axis == 0 else (x1-x0)
    if max(x1-x0, y1-y0) <= width or width <= 0:
        return False
    stem = from_geojson(profile).intersection(fund)
    if stem.is_empty or stem.geom_type != 'Polygon':
        return False
    b = stem.bounds
    depth = numeric(depth)
    from .declared_cut_height import reconciled_depth
    declared = reconciled_depth(height_evidence, stem, fund, depth, width, axis)
    if declared is not None:
        depth = declared
    return (abs((b[axis+2]-b[axis])-depth) <= .25 and abs((b[3-axis]-b[1-axis])-width) <= .25
            and abs(stem.area-depth*width) <= depth*.5)


def inherited(fact, sources, method, factor, **extra):
    result = deepcopy(fact)
    result.update(method=method, **extra)
    result['evidence_ids'] = sorted(set(e for s in sources for e in s.get('evidence_ids', [])))
    result['warnings'] = sorted(set(w for s in sources for w in s.get('warnings', [])))
    result['confidence_pct'] = round(min(s['confidence_pct'] for s in sources) * factor, 1)
    result['confidence_method'] = 'level_evidence_completeness_v1'
    result['confidence_components'] = {'weakest_source': min(s['confidence_pct'] for s in sources),
                                        'spatial_transfer_factor': factor}
    result['source_fact_ids'] = sorted(set(s['fact_id'] for s in sources))
    result['status'] = ('unknown' if result['value'] is None else
                        'estimated' if any(s.get('status') == 'estimated' for s in sources) else
                        'sa_evidence' if result['confidence_pct'] >= 80 else 'inferred')
    if any(s.get('level_basis') == 'owner_convention' for s in sources):
        result['level_basis'] = 'owner_convention'
        result['owner_decision'] = 'NIV-PADRAO-EXCECAO-20261003'
        if result['status'] == 'sa_evidence':
            result['status'] = 'inferred'
    return result


def carries_slab_level(item):
    return any(f.get('field') == 'slab_level' and f.get('value') is not None
               and f.get('status') not in ('conflict', 'candidate')
               for f in item.get('levels') or [])


def index_slabs(items):
    """One item per slab name. A later empty homonym must not hide the level."""
    chosen = {}
    for item in items:
        if item.get('item_class') != 'slab':
            continue
        name = item['display_name']
        previous = chosen.get(name)
        carries = carries_slab_level(item)
        if previous is None or (carries and not carries_slab_level(previous)):
            chosen[name] = item
        elif carries == carries_slab_level(previous):
            chosen[name] = item
    return chosen


def resolve(tower, context):
    """Resolve FV first; LV falls back into FV, then reads the resolved FV once."""
    items = tower['items']
    for item in items:
        for fact in item.get('levels', []):
            score(fact)
    slab_items = index_slabs(items)
    add_slab_region_facts(slab_items, context)
    from .level_provenance import collect
    resolve_missing_slab_cut_regions(slab_items, context, collect(tower))
    # Layers 2/4 only after the measured cut layer has had its chance.
    from .slab_level_layers import MIN_FACING_CM, resolve as resolve_slab_layers
    resolve_slab_layers(slab_items, items, context, geometry, inherited, tower)
    # One bounded reconciliation after continuity: measured wings can correct
    # an unmeasured neighbour convention. Frozen, traced roots forbid feedback
    # from the target through another class or a prior inferred slab.
    resolve_missing_slab_cut_regions(slab_items, context, collect(tower), allow_traced_inferred=True)
    slab_sources = {}
    for name, item in slab_items.items():
        facts = [f for f in item['levels'] if f['field'] == 'slab_level'
                 and f['value'] is not None and f['status'] not in ('conflict', 'candidate')]
        values = {f['value'] for f in facts}
        # A multi-part slab cannot certify its stored scalar for the whole polygon.
        if len(values) == 1:
            slab_sources[name] = max(facts, key=lambda f: f['confidence_pct'])

    from .slab_contact_levels import apply_uncovered_range_contacts, contact_sources, contact_level
    local_sources = contact_sources(slab_items, context, slab_sources, geometry)
    from .no_slab_levels import regions, floor_source, level as no_slab_level
    absence_regions = regions(context)
    # The storey datum also names the common beam level among disagreeing
    # slab contacts (lower slab = step closed by the top panel).
    datum_source = floor_source(tower, slab_sources)
    exit_source = datum_source if absence_regions else None
    if datum_source:
        datum_source['item_id'] = 'floor-exit-reference'
        tower['floor_level_sources'] = [datum_source]
    slab_regions = [geometry(s.get('points')) for s in context['state'].get('slabs', [])]
    slab_regions = [s for s in slab_regions if s is not None]

    cuts = []
    from .beam_cut_continuity import scoped_cut_profile, paint_regions, propagate
    paints = paint_regions(context.get('tower_path'))
    breaks = cut_break_shapes(context)
    from .standard_beam_level import sources as standard_sources, level as standard_level, inner_step_values
    principal_references = standard_sources(slab_items, context, slab_sources, geometry)
    step_values = inner_step_values(slab_items)
    all_cut_shapes = []
    seen_cuts = set()
    for slab in context['state'].get('slabs', []):
        for cut in (slab.get('cut_links') or {}).get('cut_view_geom', []):
            key = repr(cut.get('points'))
            # One drawing shared by the slabs on both sides: each linked slab
            # reads its own side (a multipart first owner must not hide the other).
            if (key, slab['name']) in seen_cuts:
                continue
            shape = geometry(cut.get('points'))
            if shape is None:
                continue
            if not any(k == key for k, _ in seen_cuts):
                all_cut_shapes.append(shape)
            seen_cuts.add((key, slab['name']))
            ficha = cut.get('ficha') or {}
            from .cut_level_scope import incompatible_own_height, own_wing_top
            if incompatible_own_height(cut, slab):
                tower.setdefault('rejected_cut_level_evidence', []).append({
                    'slab': slab['name'], 'cut_id': key,
                    'reason': 'cut_own_height_requires_separate_region_level'})
                continue
            distance = numeric(ficha.get('own_dist_top'))
            near = [b for b in breaks if shape.distance(b) <= CONTACT_CM]
            break_read = break_spares_top(shape, near, distance) if near else None
            if near and break_read is None:
                # The absolute beam-top offset cannot be inferred from a section
                # shortened by a break. Relative slab steps remain in raw SA.
                tower.setdefault('rejected_cut_level_evidence', []).append({
                    'slab':slab['name'], 'cut_id':key, 'reason':'shortened_section_break'})
                continue
            # The link owner supplies the own-side semantics; names on a diagram
            # are not sufficient to select a beam. Match the actual cut footprint.
            own = cut_owner_level(slab['name'], shape, slab_sources, slab_items)
            if own and distance is not None and 0 <= distance < 100:
                # The cut is its own hop in the chain: slab level -> CAD cut -> FV.
                cut_fact = inherited(own, [own], 'cut_slab_plus_top_offset_cm', .9,
                    value=round(own['value']+distance/100, 4), cut_id=key,
                    field='cut_beam_reference', cut_owner_slab=slab['name'], top_offset_cm=distance,
                    cut_profile_geometry=scoped_cut_profile(cut, slab),
                    cut_height_evidence=deepcopy(ficha.get('beam_height_evidence')))
                cut_fact.update(own_slab_value=own['value'],
                                own_wing_top_coordinate_cm=own_wing_top(shape, slab, own))
                if break_read:
                    # Only the top offset survives the break; never the section depth.
                    cut_fact.update(shortened_section_top_read=break_read, cut_profile_geometry=None)
                    cut_fact['warnings'] = sorted(set(cut_fact['warnings'] + ['shortened_section_top_offset_only']))
                facts = tower.setdefault('cut_level_facts', [])
                cut_fact['fact_id'] = own['fact_id'] + ':cut:' + str(len(facts))
                facts.append(cut_fact)
                cuts.append((shape, cut_fact))

    for item in items:
        if item['item_class'] != 'beam' or not item.get('segments'):
            continue
        records = {f['segment_id']: f for f in item['levels'] if f.get('segment_id') and f['field'] != 'beam_bottom'}
        shapes = {s['segment_id']: geometry(s.get('points')) for s in item['segments']}
        seeds = deepcopy(records)
        for uid, record in seeds.items():
            record['fact_id'] += ':independent_seed'
            seg = next(s for s in item['segments'] if s['segment_id'] == uid)
            if shapes[uid] is not None and record['status'] in ('estimated', 'unknown'):
                local = contact_level(shapes[uid], record, local_sources, inherited, projected_coverage)
                if local is None:
                    local = no_slab_level(shapes[uid], record, absence_regions, exit_source,
                                          slab_regions, inherited, projected_coverage)
                if local is not None:
                    local['evidence_ids'] = sorted(set(local['evidence_ids']+[context['evidence_id']]))
                    record.update(local)
                    record['fact_id'] = records[uid]['fact_id'] + ':independent_seed'
                    seg['native_level_evidence'] = deepcopy(record)
                    continue
            sources = [slab_sources.get(n) or segment_region_source(slab_items.get(n), shapes[uid], record)
                       for n in seg.get('level_slabs', [])]
            sources = [s for s in sources if s]
            # A lateral keeps a cited slab only when the altitudes agree.
            # The fund rule is unchanged: a lower contact can still be a step.
            usable = sources
            if seg.get('family') != 'fundo' and record.get('value') is not None:
                usable = [s for s in sources if s.get('value') is not None
                          and abs(s['value'] - record['value']) <= TOL]
            if usable and record['status'] not in ('estimated', 'human_review'):
                native = records[uid]['confidence_pct']
                lifted = stale_slab_penalty_lift(record, seg, usable, shapes[uid], local_sources, datum_source)
                if lifted is not None:
                    native = lifted
                    record['warnings'] = sorted(set(record['warnings']) - STALE_SLAB_WARNINGS
                                                | {'sa_slab_penalty_superseded_by_proven_source'})
                record['confidence_pct'] = min(native, min(s['confidence_pct'] for s in usable)*.95)
                record['evidence_ids'] = sorted(set(record['evidence_ids'] + [e for s in usable for e in s['evidence_ids']]))
                record['source_fact_ids'] = [s['fact_id'] for s in usable]
                record['confidence_components'] = {'native_support_cap': native,
                    'weakest_source': min(s['confidence_pct'] for s in usable), 'spatial_transfer_factor': .95}
                if lifted is not None:
                    record['confidence_components']['stale_sa_native_cap'] = records[uid]['confidence_pct']
            # No complete level provenance: keep its native score, capped.
            if seg.get('level_slabs') and len(usable) != len(seg['level_slabs']):
                record['confidence_pct'] = min(record['confidence_pct'], 35)
                record['confidence_components']['incomplete_source_cap'] = 35
            if not usable and record['status'] != 'human_review' and record['value'] is not None:
                record['confidence_pct'] = min(record['confidence_pct'], 30)
                record['confidence_components']['no_independent_source_cap'] = 30
                record['warnings'] = sorted(set(record['warnings']+['missing_independent_level_evidence']))
            seg['native_level_evidence'] = deepcopy(record)
        funds = [s for s in item['segments'] if s['family'] == 'fundo']
        sides = [s for s in item['segments'] if s['family'] != 'fundo']
        resolved_funds = {}
        for fund in funds:
            uid = fund['segment_id']
            current, shape = seeds[uid], shapes[uid]
            candidates = []
            if shape is not None and current['status'] != 'human_review':
                from .cut_level_scope import for_fund
                candidates = [for_fund(f, shape, fund.get('height_cm'))
                              for cg, f in cuts if cg.distance(shape) <= CONTACT_CM]
                candidates = [f for f in candidates if f is not None]
                # Persist each measured per-stem reading with its own identity;
                # the source slab chain remains the same independent origin.
                for f in candidates:
                    if f.get('top_offset_source') == 'matched_stem_and_scoped_own_wing':
                        f['fact_id'] += ':fund:' + uid
                        tower.setdefault('cut_level_facts', []).append(f)
            if candidates:
                values = {round(f['value'], 4) for f in candidates}
                if max(values)-min(values) <= TOL:
                    # Each cut whose stem matches this FV section is a sufficient
                    # path: score the strongest one. Unvalidated touching cuts
                    # keep the conservative weakest-of-all rule.
                    validated = [c for c in candidates if cut_matches_fund(
                        c.get('cut_profile_geometry'), shape, fund.get('height_cm'),
                        c.get('cut_height_evidence'))]
                    # Both sides of one drawing are readings of the same cut:
                    # the stronger agreeing side carries it (never a sum).
                    drawings = {}
                    for c in candidates:
                        if c['cut_id'] not in drawings or c['confidence_pct'] > drawings[c['cut_id']]['confidence_pct']:
                            drawings[c['cut_id']] = c
                    used = ([max(validated, key=lambda c: c['confidence_pct'])] if validated
                            else list(drawings.values()))
                    current = inherited(current, used, 'cut_geometry_on_fv', .95,
                                        value=used[0]['value'],
                                        cut_ids=sorted({c['cut_id'] for c in candidates}),
                                        cut_association=('stem_matches_fv_section' if validated
                                                         else 'contact_only'),
                                        cut_height_evidence=(deepcopy(used[0].get('cut_height_evidence'))
                                            if len(used) == 1 else None),
                                        cut_profile_geometry=(used[0].get('cut_profile_geometry')
                                            if len(used) == 1 else None))
                    current['independent_confirmations'] = confirmations(
                        used, validated or candidates)
                else:
                    current = deepcopy(current)
                    current.update(value=None, status='conflict', confidence_pct=0,
                                   alternatives=sorted(values), warnings=['contradictory_cuts_on_fv'])
            elif shape is not None and current['status'] != 'human_review' and current['confidence_pct'] < 50:
                support = []
                spans = []
                support_spans = []
                ceiling = None
                for side in sides:
                    ss, source = shapes[side['segment_id']], seeds[side['segment_id']]
                    if ss is None or ss.length <= 0 or source['value'] is None:
                        continue
                    overlap = ss.intersection(shape.buffer(CONTACT_CM))
                    if (overlap.length > CONTACT_CM
                            and source['status'] not in ('estimated', 'unknown', 'conflict', 'candidate')):
                        ceiling = source['value'] if ceiling is None else max(ceiling, source['value'])
                    if source['confidence_pct'] < 50:
                        continue
                    if overlap.length > CONTACT_CM:
                        support.append(source)
                        spans.append(overlap)
                        support_spans.append((source,overlap))
                # Para/Passa and opposite sides may duplicate the same interval.
                # Project their union along FV's long axis, never sum lengths.
                coverage = projected_coverage(shape, spans)
                # A lateral on the lower side only states its own slab; when the
                # opposite face reads higher, it does not bound the beam top.
                if support and coverage >= .8 and max(s['value'] for s in support) >= ceiling - TOL:
                    highest = max(s['value'] for s in support)
                    sources = [s for s in support if abs(s['value']-highest) <= TOL]
                    highest_coverage = projected_coverage(shape,[span for s,span in support_spans if abs(s['value']-highest)<=TOL])
                    if highest_coverage >= .8:
                        current = inherited(current, sources, 'lv_independent_evidence_fills_fv', .9*highest_coverage,
                                            value=highest, spatial_coverage=highest_coverage)
            # Resolve existing independent evidence before the default. A weak
            # convention source must not suppress stronger reciprocal LV proof.
            if not candidates:
                standard = standard_level(shape, current, principal_references, paints,
                                          all_cut_shapes, inherited, projected_coverage, datum_source,
                                          step_values)
                if standard and standard['confidence_pct'] > current['confidence_pct']:
                    current = standard
            resolved_funds[uid] = current
            current['fact_id'] = records[uid]['fact_id']
            records[uid].update(current)
            sync(fund, current)
        from .beam_junction_continuity import propagate_junctions
        all_funds = [s for beam in items if beam.get('item_class') == 'beam'
                     for s in beam.get('segments') or [] if s.get('family') == 'fundo']
        propagate_junctions(funds, all_funds, records, shapes, cuts,
                            context.get('tower_path'), paints, inherited, sync)
        propagate(funds, sides, records, shapes, paints, inherited, sync)
        estimate_same_beam_funds([item])
        resolved_funds = {uid: records[uid] for uid in resolved_funds}
        for side in sides:
            uid, shape = side['segment_id'], shapes[side['segment_id']]
            native = seeds[uid]
            ranges = []
            if shape is not None and shape.length > 0 and native['status'] != 'human_review':
                # Cut a lateral at every FV boundary. Different segmentation
                # counts and reversed B numbering have no bearing on matching.
                intervals = []
                for fund in funds:
                    fg = shapes[fund['segment_id']]
                    if fg is None:
                        continue
                    hit = shape.intersection(fg.buffer(.05))
                    for part in getattr(hit, 'geoms', [hit]):
                        if part.is_empty or part.length <= .05 or not hasattr(part, 'coords'):
                            continue
                        from shapely.geometry import Point
                        distances = [shape.project(Point(p))/shape.length for p in part.coords]
                        intervals.append((min(distances), max(distances), fund))
                boundaries = sorted({0., 1., *[v for a,b,_ in intervals for v in (a,b)]})
                for start, end in zip(boundaries, boundaries[1:]):
                    if (end-start)*shape.length <= .1:
                        continue
                    matched = [fund for a,b,fund in intervals if a <= (start+end)/2 <= b]
                    sources = [resolved_funds[f['segment_id']] for f in matched]
                    conflicting = any(f['status']=='conflict' for f in sources)
                    sources = [f for f in sources if f['value'] is not None and f['status'] != 'conflict']
                    if conflicting:
                        row = deepcopy(native)
                        row.update(value=None,status='conflict',confidence_pct=0,
                                   warnings=['source_fv_level_conflict'],fv_segments=[f['segment_label'] for f in matched])
                    elif sources and max(f['value'] for f in sources)-min(f['value'] for f in sources) <= TOL:
                        if preserve_local_seed_over_estimated_fv(native, sources):
                            row = deepcopy(native)
                            row['fv_segments'] = []
                            row['fv_geometry_segments'] = [f['segment_label'] for f in matched]
                        else:
                            row = inherited(native, sources, 'spatial_fv_reference', .95,
                                value=sources[0]['value'], fv_segments=[f['segment_label'] for f in matched])
                    elif sources:
                        row = deepcopy(native)
                        row.update(value=None,status='conflict',confidence_pct=0,
                                   warnings=['overlapping_fv_levels_conflict'])
                    else:
                        row = deepcopy(native)
                        row['fv_segments'] = []
                    row.update(range_start=round(start*shape.length, 2), range_end=round(end*shape.length, 2), range_unit='cm')
                    if ranges and ranges[-1].get('value') == row.get('value') and ranges[-1].get('fv_segments') == row.get('fv_segments') and ranges[-1].get('fv_geometry_segments') == row.get('fv_geometry_segments') and ranges[-1]['method']==row['method']:
                        ranges[-1]['range_end'] = row['range_end']
                    else:
                        ranges.append(row)
            if not ranges:
                ranges = [deepcopy(native)]
            for index, row in enumerate(ranges):
                row['fact_id'] = records[uid]['fact_id'] + ':range:' + str(index)
            continue_lateral_segment(ranges, native)
            side['level_ranges'] = ranges
            values = {r['value'] for r in ranges}
            record = records[uid]
            fact_id = record['fact_id']
            if len(values) == 1:
                record.update(inherited(native, ranges, 'lateral_spatial_level_ranges', 1,
                    value=ranges[0]['value']))
            else:
                record.update(value=None,status='segmented',confidence_pct=min(r['confidence_pct'] for r in ranges),
                              method='multiple_fv_levels_along_lateral', warnings=['see_spatial_level_ranges'],
                              confidence_components={'aggregation':'weakest_spatial_range',
                                  'range_scores':[r['confidence_pct'] for r in ranges]})
            record['level_ranges'] = ranges
            record['fact_id'] = fact_id
            sync(side, record)
        continue_pillar_wall_segments(sides, records, shapes)
        # After both continuity passes. The stretch must not paint the far gap,
        # and it must not take a row that the pillar-wall rule was going to keep.
        for side in sides:
            uid = side['segment_id']
            ranges = side.get('level_ranges') or []
            updated = apply_uncovered_range_contacts(
                shapes[uid], ranges, local_sources, inherited, projected_coverage, MIN_FACING_CM)
            if len(updated) == len(ranges) and all(new is old for new, old in zip(updated, ranges)):
                continue
            record = records[uid]
            base = record['fact_id']
            mapping = {}
            for index, row in enumerate(updated):
                previous = row.get('fact_id')
                row['fact_id'] = base + ':range:' + str(index)
                if previous:
                    mapping[previous] = row['fact_id']
            for row in updated:
                refs = row.get('continuity_source_ranges')
                if refs:
                    row['continuity_source_ranges'] = [mapping.get(ref, ref) for ref in refs]
            native = seeds[uid]
            fact_id = record['fact_id']
            values = {r['value'] for r in updated}
            if len(values) == 1:
                record.update(inherited(native, updated, 'lateral_spatial_level_ranges', 1,
                    value=updated[0]['value']))
            else:
                record.update(value=None,status='segmented',confidence_pct=min(r['confidence_pct'] for r in updated),
                              method='multiple_fv_levels_along_lateral', warnings=['see_spatial_level_ranges'],
                              confidence_components={'aggregation':'weakest_spatial_range',
                                  'range_scores':[r['confidence_pct'] for r in updated]})
            record['level_ranges'] = updated
            record['fact_id'] = fact_id
            side['level_ranges'] = updated
            sync(side, record)
        for fact in item['levels']:
            if fact['field'] == 'beam_bottom':
                source = records[fact['segment_id']]
                fact.update(inherited(fact, [source], 'fv_reference_minus_depth_cm', 1,
                    value=round(source['value']-fact['height_cm']/100,4) if source['value'] is not None else None))
                seg = next(s for s in funds if s['segment_id']==fact['segment_id'])
                seg['bottom_level'] = fact['value']
    resolve_pillars(items, context, slab_sources)
    from .level_provenance import annotate
    annotate(tower)
    return tower


def continue_pillar_wall_segments(sides, records, shapes):
    """Follow the same beam face through a pillar and a shallower junction.

    A drawing opening can partition the lateral while its reference plane
    continues. Require an actual touching segment of the same face/behavior,
    equal depth and complete pillar-wall coverage. Slab steps never qualify.
    Read frozen supported facts so estimates cannot bootstrap each other.
    """
    frozen = deepcopy(records)
    for side in sides:
        uid = side['segment_id']
        target = records[uid]
        cell = (side.get('details') or {}).get('lv_cell') or {}
        shape = shapes[uid]
        if target['status'] not in ('estimated', 'unknown') or shape is None or shape.length <= 0:
            continue
        openings = cell.get('pillar_openings') or []
        if not any((numeric(p.get('comprimento')) or 0) >= shape.length-.1 for p in openings):
            continue
        junctions = [cell.get('support_start') or {}, cell.get('support_end') or {}]
        if not any(s.get('rule') == 'G7_incidente_menos_profunda_passa_por_baixo' for s in junctions):
            continue
        support = []
        for other in sides:
            other_uid = other['segment_id']
            source, other_shape = frozen[other_uid], shapes[other_uid]
            if other_uid == uid or other['family'] != side['family'] or other_shape is None:
                continue
            if source['value'] is None or source['status'] in ('estimated','unknown','candidate','conflict','segmented'):
                continue
            other_cell = (other.get('details') or {}).get('lv_cell') or {}
            if numeric(other_cell.get('depth')) != numeric(cell.get('depth')) or numeric(cell.get('depth')) is None:
                continue
            # Endpoints must touch; proximity to a parallel/opposite face is not evidence.
            a, b = list(shape.coords), list(other_shape.coords)
            ends = [('support_start', a[0]), ('support_end', a[-1])]
            other_ends = [('support_start', b[0]), ('support_end', b[-1])]
            connections = [(key, other_key) for key, p in ends
                           for other_key, q in other_ends if math.dist(p, q) <= .1]
            # A step at the far end of the supported segment does not affect
            # this junction. Never transfer across an actual step endpoint.
            if not any((cell.get(key) or {}).get('type') != 'degrau_laje'
                       and (other_cell.get(other_key) or {}).get('type') != 'degrau_laje'
                       for key, other_key in connections):
                continue
            support.append(source)
        if not support or max(s['value'] for s in support)-min(s['value'] for s in support)>TOL:
            continue
        ranges = side.get('level_ranges') or []
        if any(r.get('fv_segments') or r['status'] not in ('estimated','unknown') for r in ranges):
            continue
        for row in ranges:
            identity = row['fact_id']
            row.update(inherited(row,support,'same_beam_face_pillar_wall_continuity',.95,
                value=support[0]['value'],owner_decision='NIV-LV-CONTINUIDADE-20261002'))
            row['fact_id'] = identity
        identity = target['fact_id']
        target.update(inherited(target,ranges or support,'lateral_spatial_level_ranges',1,
            value=support[0]['value']))
        target['fact_id'] = identity
        target['level_ranges'] = ranges
        sync(side,target)


def continue_lateral_segment(ranges, native):
    """A pillar/absence of FV does not split a canonical lateral segment.

    Freeze supported intervals first; extend their unique level within this
    segment only. Different levels/conflicts remain explicit for geometry QA.
    Estimated evidence never confirms itself or another range.
    """
    if any(r['status'] in ('conflict','segmented') for r in ranges):
        return
    supported = [deepcopy(r) for r in ranges if r.get('value') is not None
                 and r['status'] not in ('estimated','unknown','candidate')]
    if not supported:
        return
    different_levels = max(r['value'] for r in supported)-min(r['value'] for r in supported)>TOL
    frozen = deepcopy(ranges)
    value = supported[0]['value']
    if not different_levels and native.get('value') is not None and native['status'] not in ('estimated','unknown','candidate') and abs(native['value']-value)>TOL:
        return
    for index, row in enumerate(ranges):
        if row['status'] not in ('estimated','unknown') or row.get('fv_segments'):
            continue
        sources = supported
        if different_levels:
            # An unrelated span with another altitude must not veto a gap
            # bracketed by two agreeing independent intervals. Conversely,
            # never choose one side at an actual change of altitude.
            if not 0 < index < len(frozen)-1:
                continue
            sources = [frozen[index-1], frozen[index+1]]
            if any(s.get('value') is None or s['status'] in
                   ('estimated','unknown','candidate','conflict','segmented') for s in sources):
                continue
            if abs(sources[0]['value']-sources[1]['value']) > TOL:
                continue
            value = sources[0]['value']
            if native.get('value') is not None and native['status'] not in ('estimated','unknown','candidate') and abs(native['value']-value)>TOL:
                continue
        identity = row['fact_id']
        row.update(inherited(row,sources,'same_lateral_segment_level_continuity',.95,
            value=value, owner_decision='NIV-LV-CONTINUIDADE-20261002',
            continuity_source_ranges=[s['fact_id'] for s in sources]))
        row['status']='inferred'
        row['fact_id']=identity
        row['warnings']=sorted(set(row['warnings']+['level_continues_within_existing_lateral_segment']))


def add_slab_region_facts(slab_items, context):
    """A CAD step bounds its own altitude; do not apply it to the entire slab."""
    from shapely.geometry import mapping
    for slab in context['state'].get('slabs', []):
        item = slab_items.get(slab['name'])
        steps = slab.get('slab_steps') or []
        owner = geometry(slab.get('points'))
        if not item or not steps or not isinstance(owner, Polygon):
            continue
        regions = [(step, geometry(step.get('points'))) for step in steps]
        regions = [(step, shape) for step, shape in regions if isinstance(shape, Polygon)]
        principal = owner.difference(unary_union([shape for _, shape in regions]))
        # Values the SA took from this layer's own vote are not evidence here:
        # the vote is recomputed, never read back as a measured step level.
        filled = lambda step: step.get('preprocess_filled') or []
        principal_values = {step['owner_level_m'] for step, _ in regions
                            if step.get('owner_level_m') is not None and 'owner_level_m' not in filled(step)}
        parts = [(step['uid'], shape, None if 'level_m' in filled(step) else step.get('level_m'), step,
                  not step.get('evidence_checks', {}).get('direct_internal_level', False))
                 for step, shape in regions]
        if len(principal_values) == 1:
            value = next(iter(principal_values))
            proof = next(step for step, _ in regions if step.get('owner_level_m') == value
                         and 'owner_level_m' not in filled(step))
            parts.append(('principal', principal, value, proof,
                          not proof.get('evidence_checks', {}).get('direct_principal_level', False)))
        for uid, shape, value, proof, inferred_level in parts:
            if shape.is_empty:
                continue
            fact = dict(item_id=item['item_id'], fact_id=item['item_id']+':region:'+uid,
                field='slab_region_level', value=value, unit='m',
                datum_id=(item['levels'][0].get('datum_id') if item['levels'] else None),
                region_id=uid, region_geometry=mapping(shape),
                region_height_cm=proof.get('owner_height_cm') if uid=='principal' else proof.get('height_cm'),
                method='unresolved_scoped_region' if value is None else
                    'slab_step_cut_scoped_level' if inferred_level else 'cad_level_inside_slab',
                status='unknown' if value is None else 'inferred' if inferred_level else 'sa_evidence',
                evidence_ids=[context['evidence_id'], *['cad:'+h for h in proof['evidence_handles']]],
                warnings=['level_transferred_through_flat_bottom_section'] if inferred_level else [])
            score(fact)
            item['levels'].append(fact)
        # A proved flat underside ties the altitude delta to a measured region.
        # Freeze direct facts before deriving: two inferred regions cannot
        # confirm each other, even when their stored numbers agree.
        direct_regions={f['region_id']:deepcopy(f) for f in item['levels']
            if f.get('field')=='slab_region_level'
            and f.get('method')=='cad_level_inside_slab'}
        for step,_ in regions:
            # The owner's same-bottom confirmation proves the flat underside as
            # a drawn section does; it never overrides a direct CAD altitude.
            owner_flat=(step.get('method')=='owner_confirmed_scoped_same_bottom'
                        and (step.get('owner_review') or {}).get('same_bottom') is True
                        and (step.get('owner_review') or {}).get('decision_id'))
            section_flat=(step.get('method')=='scoped_level_and_flat_bottom_section'
                          and step.get('sections'))
            if (step.get('review_conflict') or step.get('status')!='same_bottom'
                    or not (section_flat or owner_flat)):
                continue
            checks=step.get('evidence_checks') or {}
            if bool(checks.get('direct_internal_level'))==bool(checks.get('direct_principal_level')):
                continue
            source_id=step['uid'] if checks.get('direct_internal_level') else 'principal'
            target_id='principal' if source_id==step['uid'] else step['uid']
            source=direct_regions.get(source_id)
            target=next((f for f in item['levels'] if f.get('field')=='slab_region_level'
                         and f.get('region_id')==target_id),None)
            inner_h,principal_h=numeric(step.get('height_cm')),numeric(step.get('owner_height_cm'))
            if not source or not target or inner_h is None or principal_h is None:
                continue
            delta=(principal_h-inner_h) if target_id=='principal' else (inner_h-principal_h)
            if abs(source['value']+delta/100-target['value'])>TOL:
                continue
            proof_ids=target['evidence_ids']
            result=inherited(target,[source],'slab_step_cut_scoped_level',.9,
                delta_cm=delta,region_source_fact_id=source['fact_id'])
            result['evidence_ids']=sorted(set(result['evidence_ids']+proof_ids))
            result['warnings']=sorted(set(result['warnings']+['level_transferred_through_flat_bottom_section']))
            target.update(result)
        principal_fact = next((f for f in item['levels']
            if f.get('field')=='slab_region_level' and f.get('region_id')=='principal'), None)
        if principal_fact:
            # A contained CAD mark can belong to the inner step. The proved
            # principal region must not conflict with that distinct altitude.
            for f in item['levels']:
                if (f.get('field')=='slab_level' and f.get('status')=='conflict'
                        and f.get('method')=='scoped_slab_principal_region'
                        and numeric(f.get('value')) is not None
                        and abs(f['value']-principal_fact['value'])<=TOL):
                    f.update(inherited(f,[principal_fact],
                        'scoped_principal_region_level',1,
                        region_id='principal',region_geometry=principal_fact['region_geometry']))


def _cut_level_targets(slab_items, slabs):
    """Unknown regions use their own contour/h, never the whole owner slab."""
    import re
    from shapely.geometry import shape as from_geojson
    for name, item in slab_items.items():
        slab = slabs.get(name)
        if not slab:
            continue
        levels = [f for f in item['levels'] if f['field']=='slab_level']
        if len(levels)==1 and not slab.get('slab_steps'):
            match=re.search(r'h\s*=\s*(\d+(?:[.,]\d+)?)',str(slab.get('fields',{}).get('laje_dim','')),re.I)
            if match:
                yield name,item,slab,levels[0],float(match.group(1).replace(',','.')),geometry(slab['points'])
        for fact in item['levels']:
            if fact.get('field')!='slab_region_level' or fact.get('region_id')=='principal':
                continue
            height=numeric(fact.get('region_height_cm'))
            if height is None or height<=0 or not fact.get('region_geometry'):
                continue
            yield name,item,slab,fact,height,from_geojson(fact['region_geometry'])


def resolve_missing_slab_cut_regions(slab_items, context, fact_index=None, *, allow_traced_inferred=False):
    """Use the actual section wings and scoped regions, never nearby slab names.

    A shortened beam stem invalidates an absolute beam offset, but leaves the
    local difference between measured slab wings intact. Each wing must be one
    consistent drawn band at three stations; a thickness different from the
    declared h is a drawing error (h wins, NIV-LAJE-CAMADAS-20261003): it only
    re-proves an existing value, at a reduced factor.
    Existing inferred scalars may acquire a stronger independent proof of the
    same altitude; measured/human values and competing altitudes are untouched.
    """
    from shapely.geometry import shape as from_geojson
    from .level_provenance import walk, origin_kind
    # Include other classes when called from the full resolver: an apparently
    # independent slab can depend on the target through a beam/contact fact.
    fact_index = dict(fact_index or {})
    fact_index.update({f['fact_id']: f for item in slab_items.values()
                       for f in item['levels'] if f.get('fact_id')})
    slabs = {s['name']: s for s in context['state'].get('slabs', [])}
    def usable_seed(f):
        if f.get('status') in ('sa_evidence', 'human_review'):
            return True
        if not allow_traced_inferred or f.get('status') != 'inferred':
            return False
        roots, cycles, missing = walk(f['fact_id'], fact_index)
        return (not cycles and not missing and bool(roots) and all(
                r.get('status') in ('sa_evidence', 'human_review') and origin_kind(r) in
                ('cad_direct_level', 'cad_named_section_level', 'human_review') for r in roots))
    sources = []
    for name, item in slab_items.items():
        region_facts = [f for f in item['levels'] if f['field']=='slab_region_level']
        for f in region_facts:
            if (numeric(f.get('value')) is not None
                    and usable_seed(f)
                    and f.get('evidence_ids')):
                sources.append((name, deepcopy(f), from_geojson(f['region_geometry'])))
        if not slabs.get(name, {}).get('slab_steps'):
            valid = [f for f in item['levels'] if f['field']=='slab_level'
                     and f['value'] is not None and usable_seed(f)]
            if len({f['value'] for f in valid}) == 1:
                sources.append((name,deepcopy(max(valid,key=lambda f:f['confidence_pct'])),geometry(slabs[name]['points'])))
    def wing(section, region, height, up=(1,1)):
        """Top of a slab wing along the section's vertical axis.

        up=(axis, sign): (1,+1) for a horizontal drawing, (0,±1) for a section
        drawn rotated; the sign comes from the stem side, never assumed.
        """
        axis,sign=up
        hit=section.intersection(region)
        if hit.area < 1: return None
        x0,y0,x1,y1=hit.bounds
        tops=[]
        spans=[]
        for ratio in (.25,.5,.75):
            if axis==1:
                station=LineString([(x0+(x1-x0)*ratio,y0-1),(x0+(x1-x0)*ratio,y1+1)])
            else:
                station=LineString([(x0-1,y0+(y1-y0)*ratio),(x1+1,y0+(y1-y0)*ratio)])
            span=section.intersection(station).intersection(region)
            # NIV-LAJE-CAMADAS: declared h wins over a mis-drawn wing thickness;
            # the wing must still be one consistent drawn band (top line used).
            if span.geom_type!='LineString' or span.length<1: return None
            spans.append(span.length)
            b=span.bounds
            tops.append(b[axis+2] if sign>0 else -b[axis])
        if max(tops)-min(tops)>=.1 or max(spans)-min(spans)>.25: return None
        return sum(tops)/3, abs(sum(spans)/3-height)>.25
    def rotated_up(section, regions):
        """A rotated section points 'up' away from its stem (beam below wings)."""
        wings=unary_union([section.intersection(r) for r in regions if r is not None])
        stem=section.difference(wings)
        if wings.is_empty or stem.area < 1: return None
        delta=wings.centroid.x-stem.centroid.x
        if abs(delta) < 1: return None
        return (0, 1 if delta>0 else -1)
    for name,item,slab,target,height,owner in _cut_level_targets(slab_items,slabs):
        if target.get('status') not in ('unknown','inferred','estimated'): continue
        import re
        candidates=[]
        mismatched={}
        for cut in (slab.get('cut_links') or {}).get('cut_view_geom',[]):
            section=geometry(cut.get('original_pts') or cut.get('points'))
            if not isinstance(section,Polygon): continue
            x0,y0,x1,y1=section.bounds
            up=(1,1)
            if x1-x0<=y1-y0:
                # Vertical drawing: orientation from the stem side of the wings
                # actually crossed (own slab plus each scoped source region).
                # Geometry cannot tell an inverted beam from a rotated normal
                # one, so a rotated reading only re-proves an existing value.
                if numeric(target.get('value')) is None: continue
                up=rotated_up(section,[owner]+[r for _,_,r in sources])
                if up is None: continue
            target_wing=wing(section,owner,height,up)
            if target_wing is None: continue
            target_top,target_off=target_wing
            for source_name,source,region in sources:
                if source_name==name or region is None: continue
                # Seeding the traversal with the target also catches indirect
                # self-confirmation; existing cycles in a source are unusable.
                _, cycles, _ = walk(source['fact_id'], fact_index, (target['fact_id'],))
                if cycles: continue
                # A region supplies its h from the same scoped contour.
                source_slab=slabs[source_name]
                step=next((s for s in source_slab.get('slab_steps',[]) if s['uid']==source.get('region_id')),None)
                if step: source_height=step['height_cm']
                else:
                    m=re.search(r'h\s*=\s*(\d+(?:[.,]\d+)?)',str(source_slab.get('fields',{}).get('laje_dim','')),re.I)
                    if not m: continue
                    source_height=float(m.group(1).replace(',','.'))
                source_wing=wing(section,region,source_height,up)
                if source_wing is None: continue
                source_top,source_off=source_wing
                delta=target_top-source_top
                if abs(delta)>30: continue
                mismatched[id(source),len(candidates)]=target_off or source_off
                candidates.append((source,delta,source_name,repr(cut.get('original_pts') or cut.get('points')),
                                   'horizontal' if up==(1,1) else 'rotated'))
        values=[round(s['value']+delta/100,4) for s,delta,_,_,_ in candidates]
        if not values or max(values)-min(values)>TOL: continue
        previous_value=numeric(target.get('value'))
        correcting_convention = (allow_traced_inferred and target.get('method') in LAYERED_REGION_METHODS
                                 and previous_value is not None and abs(previous_value-values[0]) > TOL)
        if previous_value is not None and abs(previous_value-values[0])>TOL and not correcting_convention: continue
        from shapely.geometry import mapping
        # Every candidate passed both wing checks on its own: score the
        # strongest sufficient path; agreeing others are audit-only.
        # Prefer a wing drawn with its declared h; a mis-drawn wing (h wins,
        # NIV-LAJE-CAMADAS-20261003) stays valid at a reduced factor.
        ranked=[(not mismatched[id(c[0]),i],c[0]['confidence_pct'],i) for i,c in enumerate(candidates)]
        clean,_,pick=max(ranked)
        if not clean and (previous_value is None or correcting_convention): continue  # mis-drawn wing only re-proves
        best=candidates[pick]
        result=inherited(target,[best[0]],'scoped_cut_wing_relative_delta_cm',.9 if clean else .9*.95,
            independent_confirmations=confirmations([best[0]],[s for s,_,_,_,_ in candidates]),
            target_geometry=mapping(owner),
            value=values[0],unit='m',datum_id=candidates[0][0].get('datum_id'),cut_region_evidence=[dict(source_slab=n,source_fact_id=s['fact_id'],delta_cm=d,cut_id=k,section_drawing=o) for s,d,n,k,o in candidates])
        if not clean:
            result['warnings']=sorted(set(result['warnings']+['drawn_wing_thickness_differs_from_declared_h']))
            result['confidence_components']['drawn_wing_mismatch_factor']=.95
            result['owner_decision']='NIV-LAJE-CAMADAS-20261003'
        if previous_value is not None:
            if result['confidence_pct']<=target.get('confidence_pct',0) and not correcting_convention: continue
            result['previous_level_evidence']=deepcopy(target)
        if correcting_convention:
            result['warnings']=sorted(set(result['warnings']+['measured_wing_supersedes_neighbor_convention']))
        target.update(result)
        review=dict(status='inferred',reason=result['method'],value=result['value'],evidence=result['cut_region_evidence'])
        if target.get('field')=='slab_region_level':
            item.setdefault('region_level_reviews',{})[target['region_id']]=review
        else:
            item['level_review']=review


def estimate_same_beam_funds(items):
    """D-61: an unsupported segment may estimate from independently sourced peers."""
    for item in items:
        if item['item_class'] != 'beam':
            continue
        records = {f['segment_id']: f for f in item['levels']
                   if f.get('segment_id') and f['field'] == 'fundo'}
        seeds = [deepcopy(records[s['segment_id']]) for s in item.get('segments', [])
                 if s['family'] == 'fundo' and s['segment_id'] in records
                 and records[s['segment_id']].get('source_fact_ids')
                 and records[s['segment_id']]['value'] is not None
                 and records[s['segment_id']]['status'] not in ('estimated', 'conflict', 'unknown')]
        if not seeds or max(s['value'] for s in seeds)-min(s['value'] for s in seeds) > TOL:
            continue
        for seg in item.get('segments', []):
            record = records.get(seg['segment_id'])
            if seg['family'] != 'fundo' or not record or record['status'] != 'estimated':
                continue
            sources = [s for s in seeds if s['fact_id'] != record['fact_id']]
            if not sources:
                continue
            result = inherited(record, sources, 'estimated_from_same_beam_sourced_segment', .8,
                               value=sources[0]['value'])
            result['status'] = 'estimated'
            result['warnings'] = sorted(set(result['warnings']+['estimated_not_measured']))
            record.update(result)
            sync(seg, record)
            for bottom in item['levels']:
                if bottom['field'] == 'beam_bottom' and bottom.get('segment_id') == seg['segment_id']:
                    bottom.update(inherited(bottom, [record], 'fv_reference_minus_depth_cm', 1,
                        value=round(record['value']-bottom['height_cm']/100,4)))
                    bottom['status'] = 'estimated'
                    seg['bottom_level'] = bottom['value']


def sync(segment, fact):
    segment.update(level=fact['value'], level_source=fact['method'], status=fact['status'],
                   confidence_pct=fact['confidence_pct'], confidence_components=fact['confidence_components'],
                   warnings=fact['warnings'], evidence_ids=fact['evidence_ids'])


def projected_coverage(fund, spans):
    if fund is None or fund.is_empty or not spans:
        return 0.
    # Stations belong to the target's longitudinal axis, not the drawing's
    # world X/Y axes. World-axis bounds include the width of an oblique beam
    # and can reject an otherwise sufficient physical contact.
    from math import hypot
    from shapely.affinity import affine_transform
    rectangle = fund.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords) if rectangle.geom_type == 'Polygon' else list(rectangle.coords)
    edges = [(hypot(b[0]-a[0], b[1]-a[1]), a, b) for a,b in zip(coords, coords[1:])]
    if not edges:
        return 0.
    length, a, b = max(edges, key=lambda edge: edge[0])
    if length <= 0:
        return 0.
    ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
    # A local origin avoids cancellation in drawings with large coordinates.
    matrix = [ux, uy, -uy, ux, -ux*a[0]-uy*a[1], uy*a[0]-ux*a[1]]
    target = affine_transform(fund, matrix)
    lo,hi = target.bounds[0], target.bounds[2]
    if hi <= lo:
        return 0.
    intervals = []
    def collect(shape):
        if shape is None or shape.is_empty:
            return
        if hasattr(shape, 'geoms'):
            for part in shape.geoms:
                collect(part)
            return
        bounds = affine_transform(shape, matrix).bounds
        start, end = max(lo,bounds[0]), min(hi,bounds[2])
        if end > start:
            intervals.append((start,end))
    for span in spans:
        collect(span)
    # Union connected spans individually: disconnected contacts do not fill
    # the gap between them, and duplicate Para/Passa evidence is not summed.
    covered = 0.
    end = lo
    for start, stop in sorted(intervals):
        if stop > end:
            covered += stop-max(start,end)
            end = stop
    return min(1., covered/(hi-lo))


def resolve_pillars(items, context, slab_sources):
    from shapely.geometry import shape as from_geojson
    pillars = {p['name']:p for p in context['state'].get('pilares', [])}
    beams = {i['display_name']:i for i in items if i['item_class']=='beam'}
    slabs = {s['name']:s for s in context['state'].get('slabs', [])}
    regional_sources = [(i['display_name'], f, from_geojson(f['region_geometry']))
        for i in items if i['item_class']=='slab' for f in i['levels']
        if f['field']=='slab_region_level' and f.get('value') is not None]
    regional_names = {s['name'] for s in context['state'].get('slabs', []) if s.get('slab_steps')}
    for item in items:
        if item['item_class'] != 'pillar' or item['display_name'] not in pillars:
            continue
        if 'canonical_owner_item_id' in item and item['canonical_owner_item_id'] != item['item_id']:
            continue
        top = next((f for f in item['levels'] if f['field']=='top'), None)
        if not top or top['status'] in ('human_review','not_applicable'):
            continue
        p = pillars[item['display_name']]
        shape = geometry(p.get('points'))
        if shape is None:
            continue
        x1,y1,x2,y2 = shape.bounds
        edges = {'left':[(x1,y1),(x1,y2)],'right':[(x2,y1),(x2,y2)],
                 'up':[(x1,y2),(x2,y2)],'down':[(x1,y1),(x2,y1)]}
        mapping = {'A':'left','B':'right','C':'up','D':'down'} if y2-y1 > x2-x1 else {'A':'down','B':'up','C':'left','D':'right'}
        contacts = []
        for face, key in mapping.items():
            edge = LineString(edges[key])
            for name, source in slab_sources.items():
                if name in regional_names:
                    continue
                sg = geometry(slabs[name].get('points'))
                if sg is not None and edge.intersection(sg.buffer(CONTACT_CM)).length > CONTACT_CM:
                    contacts.append(inherited(top,[source],'pillar_face_slab_contact',.95,
                        value=source['value'],face=face,linked_item=name))
            for name, source, region in regional_sources:
                if edge.intersection(region.buffer(CONTACT_CM)).length > CONTACT_CM:
                    contacts.append(inherited(top,[source],'pillar_face_slab_region_contact',.95,
                        value=source['value'],face=face,linked_item=name,region_id=source['region_id']))
            for name, beam in beams.items():
                for seg in beam.get('segments', []):
                    if seg['family'] != 'fundo' or seg['level'] is None or seg['status']=='conflict':
                        continue
                    sg = geometry(seg.get('points'))
                    if sg is not None and edge.intersection(sg.buffer(CONTACT_CM)).length > CONTACT_CM:
                        source = next(f for f in beam['levels'] if f.get('segment_id')==seg['segment_id'] and f['field']=='fundo')
                        contact_sources, factor = [source], .95
                        if seg['confidence_pct'] < 50:
                            # Weak evidence is still evidence when its independent
                            # slab sources are complete and agree with the FV.
                            # Never promote a floor fallback or a multipart scalar.
                            names = seg.get('level_slabs') or []
                            support = [slab_sources[n] for n in names if n in slab_sources]
                            traced_estimate = (source['status']=='estimated' and
                                source['method']=='estimated_from_same_beam_sourced_segment' and
                                bool(source.get('source_fact_ids')))
                            if not traced_estimate and (not names or len(support) != len(names) or any(
                                    abs(s['value']-seg['level']) > TOL for s in support)):
                                continue
                            contact_sources, factor = [source]+support, .9*.95
                        contact = inherited(top,contact_sources,'pillar_face_fv_contact',factor,
                            value=source['value'],face=face,linked_item=name,segment_label=seg['segment_label'])
                        if seg['confidence_pct'] < 50:
                            contact['warnings'] = sorted(set(contact['warnings'] +
                                ['weak_contact_level_requires_review']))
                        if source['status']=='estimated':
                            contact['status'] = 'estimated'
                        contacts.append(contact)
        for index, contact in enumerate(contacts):
            contact['fact_id'] = top['fact_id'] + ':contact:' + str(index)
        item['face_level_contacts'] = contacts
        if contacts:
            highest = max(c['value'] for c in contacts)
            winners = [c for c in contacts if abs(c['value']-highest)<=TOL]
            source = max(winners,key=lambda c:c['confidence_pct'])
            top.update(inherited(top,[source],'highest_touching_face_level',1,value=highest,
                faces=sorted({c['face'] for c in winners}), linked_item=source['linked_item']))
            if source['status']=='estimated':
                top['status'] = 'estimated'
        else:
            top.update(value=None,status='unknown',confidence_pct=0,method='no_resolved_face_contact',
                       warnings=['pillar_top_requires_contact_level'],confidence_components={'resolved_contacts':0})
