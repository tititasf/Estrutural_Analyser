"""Slab level by layers (NIV-LAJE-CAMADAS-20261003).

Layer 0 (CAD mark inside the slab) and layer 1/3 (measured cut wings, see
segment_levels.resolve_missing_slab_cut_regions) run before this module.
Here a slab still without its own proof reads the slabs facing it across a
beam (spatial contact through the same FV section, never a distance radius):

* layer 2 - every independent neighbour origin agrees: continuity convention
  (no step cut drawn = no step), weakest vote x .95, capped at 85;
* layer 4 - neighbours disagree: the most frequent level among independent
  origins wins, weakest winner x .95 x (winning votes / all votes), capped
  at 75; a tie abstains.

Votes are frozen before any update and only come from facts with their own
root (CAD/human/measured, never an inferred slab), one vote per root origin,
so a slab never confirms itself through a neighbour (no cyclic confirmation).
A layered value differing from the stored SA value is reported, not applied.

Proven step line: a beam across which two slabs with their own (independent)
levels already differ does not carry the continuity convention anywhere along
it; votes through that beam are withheld (reported, never counted).
"""
from copy import deepcopy
from itertools import combinations

DECISION = 'NIV-LAJE-CAMADAS-20261003'
TOL = .0025
MIN_FACING_CM = 10
MIN_EDGE_FACING_CM = 5
MAX_CORRIDOR_CM = 100
OWN_ROOT = ('sa_evidence', 'human_review')


def _roots(fact, index, trail=()):
    sources = [s for s in fact.get('source_fact_ids') or [] if s != fact['fact_id']]
    if not sources or fact['fact_id'] in trail:
        return [fact]
    out = []
    for s in sources:
        if s in index:
            out += _roots(index[s], index, trail + (fact['fact_id'],))
    return out or [fact]


def _origin(fact, index):
    roots = _roots(fact, index)
    handles = sorted({e for r in roots for e in r.get('evidence_ids') or [] if str(e).startswith('cad:')})
    return ','.join(handles) if handles else ','.join(sorted(r['fact_id'] for r in roots))


def _across_beam(own, other, funds, exclude=()):
    """Contact piece when an FV occupies the corridor between two facing slabs.

    The corridor is the band between the two contours (their gap is the beam
    width); association needs a real beam section inside it, never distance
    alone. Directly touching slabs (no beam between) are not neighbours here,
    nor are slabs diagonal across a beam crossing (edges must really face).
    Returns (contact, beam_id) or None.
    """
    gap = own.distance(other)
    if gap < 1 or gap > MAX_CORRIDOR_CM:
        return None
    # Diagonal slabs at a beam crossing face each other over ~2 cm per edge
    # (corner geometry); a real beam between them gives a facing edge stretch.
    if min(other.boundary.intersection(own.buffer(gap+1)).length,
           own.boundary.intersection(other.buffer(gap+1)).length) < MIN_EDGE_FACING_CM:
        return None
    corridor = own.buffer(gap+1).intersection(other.buffer(gap+1)).difference(own).difference(other)
    for slab in exclude:
        corridor = corridor.difference(slab)
    best = None
    for beam, fund in funds:
        piece = fund.intersection(corridor)
        if piece.area <= 1:
            continue
        x0, y0, x1, y1 = piece.bounds
        if max(x1-x0, y1-y0) >= MIN_FACING_CM and (best is None or piece.area > best[0].area):
            best = (piece, beam)
    return (best[0].buffer(gap+2), best[1]) if best else None


def _open_gap(own, other, blockers):
    """The shortest gap between two regions stays in the beam corridor.

    A far step can sit inside MAX_CORRIDOR_CM and still reach the beam by
    buffering across the rest of its own slab. That is not "facing": the
    straight gap has to cross the sibling region. Touching pairs are left
    to _across_beam, which already rejects a gap under 1 cm.
    """
    from shapely.geometry import LineString
    from shapely.ops import nearest_points
    a, b = nearest_points(own, other)
    if a.distance(b) < 1:
        return True
    seg = LineString([(a.x, a.y), (b.x, b.y)])
    for block in blockers:
        if block is None or block.is_empty:
            continue
        crossed = seg.intersection(block)
        if not crossed.is_empty and getattr(crossed, 'length', 0) > 1:
            return False
    return True


def _partitions(context, geometry):
    """Stepped slab -> {region_id: shape}: principal plus each step contour.

    Same partition as segment_levels.add_slab_region_facts, including the
    regions that still have no level, so a contact can tell which part of the
    slab it really runs along.
    """
    from shapely.ops import unary_union
    out = {}
    for slab in context['state'].get('slabs', []):
        owner = geometry(slab.get('points'))
        steps = [(s['uid'], geometry(s.get('points'))) for s in slab.get('slab_steps') or [] if s.get('uid')]
        steps = [(uid, g) for uid, g in steps if g is not None and g.geom_type == 'Polygon']
        if owner is None or owner.geom_type != 'Polygon' or not steps:
            continue
        parts = dict(steps)
        principal = owner.difference(unary_union([g for _, g in steps]))
        if not principal.is_empty:
            parts['principal'] = principal
        out[slab['name']] = parts
    return out


def _vote_fact(item, contact, region_shapes, parts=None):
    """The neighbour's own level where the beam touches it.

    For a stepped slab, the vote is the level of the region the contact runs
    along; a region without its own level casts no vote (a step region never
    speaks for the rest of the slab).
    """
    if parts:
        hits = {rid: shape.buffer(1).intersection(contact).area for rid, shape in parts.items()}
        rid = max(hits, key=hits.get) if hits else None
        if rid is None or hits[rid] <= 0:
            return None
        return next((f for f in item['levels'] if f.get('field') == 'slab_region_level'
                     and f.get('region_id') == rid and f.get('value') is not None
                     and f.get('status') in OWN_ROOT), None)
    regions = [f for f in item['levels'] if f.get('field') == 'slab_region_level'
               and f.get('value') is not None and f.get('status') in OWN_ROOT]
    if regions:
        best, area = None, 0
        for f in regions:
            shape = region_shapes.get(f['fact_id'])
            hit = shape.buffer(1).intersection(contact).area if shape is not None else 0
            if hit > area:
                best, area = f, hit
        if best is not None:
            return best
    own = [f for f in item['levels'] if f.get('field') == 'slab_level'
           and f.get('value') is not None and f.get('status') in OWN_ROOT]
    if len({f['value'] for f in own}) == 1:
        return max(own, key=lambda f: f.get('confidence_pct') or 0)
    return None


def resolve(slab_items, items, context, geometry, inherited, tower):
    from shapely.geometry import shape as from_geojson, mapping
    slabs = {s['name']: s for s in context['state'].get('slabs', [])}
    polygons = {n: geometry(s.get('points')) for n, s in slabs.items()}
    polygons = {n: g for n, g in polygons.items() if g is not None and g.geom_type == 'Polygon'}
    partitions = _partitions(context, geometry)
    funds = [(i['item_id'], geometry(s.get('points'))) for i in items if i['item_class'] == 'beam'
             for s in i.get('segments') or [] if s.get('family') == 'fundo']
    funds = [(b, f) for b, f in funds if f is not None and f.geom_type == 'Polygon']
    frozen = {n: deepcopy(i) for n, i in slab_items.items()}
    index = {f['fact_id']: f for i in frozen.values() for f in i['levels'] if f.get('fact_id')}
    region_shapes = {f['fact_id']: from_geojson(f['region_geometry']) for f in index.values()
                     if f.get('region_geometry')}
    report = tower.setdefault('slab_level_layers', {'decision': DECISION, 'applied': [], 'not_applied': []})
    # Proven step lines: independent own levels already differ across the beam.
    step_lines = report.setdefault('proven_step_lines', {})
    for a, b in combinations(sorted(n for n in polygons if n in frozen), 2):
        hit = _across_beam(polygons[a], polygons[b], funds)
        if hit is None:
            continue
        fa, fb = (_vote_fact(frozen[n], hit[0], region_shapes, partitions.get(n)) for n in (a, b))
        if fa and fb and abs(fa['value']-fb['value']) > TOL and _origin(fa, index) != _origin(fb, index):
            step_lines.setdefault(hit[1], []).append(dict(pair=[a, b], values=[fa['value'], fb['value']]))

    def facing(name, region_id, other, poly):
        """(contact, beam, vote fact) per unit of `other` facing the target.

        A region target faces each region of a stepped neighbour (or the plain
        neighbour) directly across a beam; the corridor excludes both whole
        slabs, so a region never faces a slab through its own slab.
        """
        if not region_id:
            hit = _across_beam(polygons[name], poly, funds)
            if hit:
                yield hit[0], hit[1], _vote_fact(frozen[other], hit[0], region_shapes, partitions.get(other))
            return
        own = partitions[name][region_id]
        rest_own = polygons[name].difference(own)
        for rid, unit in (partitions.get(other) or {None: poly}).items():
            rest_other = poly.difference(unit) if rid is not None else None
            if not _open_gap(own, unit, (rest_own, rest_other)):
                continue
            hit = _across_beam(own, unit, funds, (polygons[name], poly))
            if hit is None:
                continue
            fact = (_vote_fact(frozen[other], hit[0], region_shapes) if rid is None else
                    next((f for f in frozen[other]['levels'] if f.get('field') == 'slab_region_level'
                          and f.get('region_id') == rid and f.get('value') is not None
                          and f.get('status') in OWN_ROOT), None))
            yield hit[0], hit[1], fact

    def vote(name, target_id, region_id=None):
        """Frozen neighbour votes across beams for one slab or one slab region."""
        votes, withheld = {}, []
        for other, poly in polygons.items():
            if other == name or other not in frozen:
                continue
            for contact, beam, fact in list(facing(name, region_id, other, poly)):
                if fact is None or target_id in {r['fact_id'] for r in _roots(fact, index)}:
                    continue
                if beam in step_lines:
                    withheld.append(dict(slab=other, value=fact['value'], beam=beam, reason='proven_step_line'))
                    continue
                votes.setdefault(_origin(fact, index), dict(slab=other, fact=fact))
        head = dict(slab=name, **({'region_id': region_id} if region_id else {}))
        if not votes:
            return None, ({**head, 'votes': [], 'withheld_votes': withheld, 'reason': 'only_step_line_votes'}
                          if withheld else None)
        groups = {}
        for key, v in votes.items():
            value = round(v['fact']['value'], 4)
            group = next((g for g in groups if abs(g-value) <= TOL), value)
            groups.setdefault(group, []).append((key, v))
        ranked = sorted(groups.items(), key=lambda g: len(g[1]), reverse=True)
        record = dict(**head, votes=[dict(slab=v['slab'], value=v['fact']['value'], origin=k,
                                          fact_id=v['fact']['fact_id']) for k, v in votes.items()],
                      withheld_votes=withheld)
        if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
            return None, {**record, 'reason': 'tie'}
        _, winners = ranked[0]
        unanimous = len(ranked) == 1
        return dict(record=record, sources=[v['fact'] for _, v in winners], unanimous=unanimous,
                    fraction=len(winners)/len(votes),
                    method='slab_neighbor_continuity_without_step_cut' if unanimous else 'slab_neighbor_majority_vote',
                    cap=85 if unanimous else 75), None

    def layered(fact, decision):
        result = inherited(fact, decision['sources'], decision['method'], .95*decision['fraction'],
                           value=decision['sources'][0]['value'], neighbor_votes=decision['record']['votes'],
                           vote_fraction=round(decision['fraction'], 3),
                           level_basis='owner_convention', owner_decision=DECISION)
        result['confidence_pct'] = min(result['confidence_pct'], decision['cap'])
        result['confidence_components'].update(layer_cap=decision['cap'], vote_fraction=round(decision['fraction'], 3))
        result['warnings'] = sorted(set(result['warnings'] + [
            'slab_level_by_neighbor_continuity' if decision['unanimous'] else 'neighbor_levels_disagree_majority_vote']))
        result['status'] = 'inferred'
        return result

    for name, item in slab_items.items():
        levels = [f for f in item['levels'] if f.get('field') == 'slab_level']
        if len(levels) != 1 or polygons.get(name) is None:
            continue
        target = levels[0]
        if target.get('status') not in ('inferred', 'estimated', 'unknown') or target.get('method') == 'cad_level_inside_slab':
            continue
        principal = next((f for f in item['levels'] if f.get('field') == 'slab_region_level'
                          and f.get('region_id') == 'principal'), None)
        # The scalar of a stepped slab is its principal region.
        stepped = 'principal' in (partitions.get(name) or {})
        decision, rejected = vote(name, target['fact_id'], 'principal' if stepped else None)
        if decision is None:
            if rejected:
                report['not_applied'].append(rejected)
            continue
        record, value = decision['record'], decision['sources'][0]['value']
        previous = target.get('value')
        if previous is not None and abs(previous-value) > TOL:
            report['not_applied'].append({**record, 'reason': 'differs_from_sa_value', 'sa_value': previous,
                                          'layer_value': value})
            continue
        for fact in [target] + ([principal] if principal and principal.get('value') is not None
                                and abs(principal['value']-value) <= TOL else []):
            result = layered(fact, decision)
            if result['confidence_pct'] <= (fact.get('confidence_pct') or 0):
                continue
            result['previous_level_evidence'] = deepcopy(fact)
            fact.update(result)
        if target.get('method') != decision['method']:
            report['not_applied'].append({**record, 'reason': 'not_stronger_than_existing'})
            continue
        report['applied'].append({**record, 'method': decision['method'], 'value': value,
                                  'fraction': round(decision['fraction'], 3),
                                  'confidence_pct': target.get('confidence_pct')})

    # Regions of a stepped slab still without a level: each region is voted by
    # the beams it faces, never by the slab scalar (which may belong to a step)
    # nor by a region on the other side of the slab.
    for name, parts in partitions.items():
        item = slab_items.get(name)
        if not item or name not in polygons:
            continue
        datum = next((f.get('datum_id') for f in item['levels'] if f.get('datum_id')), None)
        for rid, shape in parts.items():
            if shape.is_empty or any(f.get('field') == 'slab_region_level' and f.get('region_id') == rid
                                     and f.get('value') is not None for f in item['levels']):
                continue
            fact_id = item['item_id']+':region:'+rid
            decision, rejected = vote(name, fact_id, rid)
            if decision is None:
                if rejected:
                    report['not_applied'].append(rejected)
                continue
            base = dict(item_id=item['item_id'], fact_id=fact_id, field='slab_region_level', value=None,
                        unit='m', datum_id=datum, region_id=rid, region_geometry=mapping(shape),
                        status='unknown', confidence_pct=0, evidence_ids=[], warnings=[])
            fact = layered(base, decision)
            item['levels'].append(fact)
            report['applied'].append({**decision['record'], 'method': decision['method'],
                                      'value': fact['value'], 'fraction': round(decision['fraction'], 3),
                                      'confidence_pct': fact['confidence_pct']})
