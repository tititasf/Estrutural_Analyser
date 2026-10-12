"""Scoped geometric slab references for independently collected beam seeds."""
from copy import deepcopy

from shapely.geometry import shape as from_geojson


def contact_sources(slab_items, context, scalar_sources, geometry):
    sources = []
    for slab in context['state'].get('slabs', []):
        item = slab_items.get(slab['name'])
        if not item:
            continue
        if slab.get('slab_steps'):
            for fact in item['levels']:
                if fact['field'] == 'slab_region_level' and fact.get('region_geometry'):
                    sources.append((slab['name'], from_geojson(fact['region_geometry']), fact))
        elif slab['name'] in scalar_sources:
            region = geometry(slab.get('points'))
            if region is not None:
                sources.append((slab['name'], region, scalar_sources[slab['name']]))
    return sources


def contact_level(segment_shape, native, sources, inherited, projected_coverage):
    """Contact is reference inference, not measurement of a beam top offset.

    Require at least 80% longitudinal support at the highest contacting level.
    Regional holes without altitude and contacts confined to an endpoint do
    not certify a whole segment. Never use estimated sources to bootstrap.
    """
    contacts = []
    for name, region, source in sources:
        if source.get('value') is None or source['status'] in ('unknown','conflict','candidate','estimated'):
            continue
        hit = segment_shape.intersection(region.buffer(1.0))
        if not hit.is_empty:
            contacts.append((name, hit, source))
    if not contacts:
        return None
    highest = max(source['value'] for _, _, source in contacts)
    chosen = [(name, hit, source) for name, hit, source in contacts if abs(source['value']-highest) <= .0025]
    coverage = projected_coverage(segment_shape, [hit for _, hit, _ in chosen])
    if coverage < .8:
        return None
    result = inherited(native, [source for _, _, source in chosen],
        'spatial_slab_region_reference', .9 * coverage, value=highest,
        source_slabs=sorted({name for name, _, _ in chosen}), spatial_coverage=coverage,
        region_ids=sorted({source.get('region_id','principal') for _, _, source in chosen}))
    result['status'] = 'inferred'
    result['warnings'] = sorted(set(result['warnings'] + ['slab_contact_reference_without_cut_offset']))
    return result


def _station_spans(piece, hit, minimum_cm):
    """Stations of one contact along the lateral. A point nick has no span."""
    from shapely.geometry import Point
    spans = []
    parts = list(hit.geoms) if hit.geom_type in ('MultiLineString', 'MultiPoint', 'GeometryCollection') else [hit]
    for part in parts:
        if part.is_empty or not hasattr(part, 'coords'):
            continue
        dists = [piece.project(Point(xy)) for xy in part.coords]
        if not dists:
            continue
        lo, hi = min(dists), max(dists)
        if hi - lo >= minimum_cm:
            spans.append((lo, hi))
    return spans


def _merge_spans(spans):
    merged = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1] + .1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged]


def apply_uncovered_range_contacts(shape, ranges, sources, inherited, projected_coverage, minimum_cm):
    """Certify the facing stretch of an uncovered lateral gap.

    contact_level still requires 80% of the whole shape. A gap that runs past
    the slab keeps the original estimate on the remainder. Call this only
    after lateral continuity and the pillar-wall pass: the new stretch must
    not paint the rest of the segment, and it must leave a row those passes
    already kept. Funds and FV-covered ranges stay put.
    The highest contacting level is the only one read, same as contact_level,
    and only when it already equals the cell altitude. An inferred cell held
    by the multi-part slab penalty is read the same way; any other inferred
    row stays as continuity left it.
    """
    from shapely.ops import substring
    if shape is None or getattr(shape, 'geom_type', None) != 'LineString' or shape.length <= 0:
        return ranges
    kept = []
    for row in ranges:
        start, end = row.get('range_start'), row.get('range_end')
        warnings = row.get('warnings') or []
        status = row.get('status')
        readable = status in ('estimated', 'unknown') or (
            status == 'inferred' and 'source_slab_level_not_uniquely_observed' in warnings)
        if (row.get('fv_segments') or not readable
                or start is None or end is None or end - start < minimum_cm):
            kept.append(row)
            continue
        start, end = float(start), float(end)
        piece = substring(shape, max(0., start), min(shape.length, end))
        if piece.is_empty or piece.length < minimum_cm:
            kept.append(row)
            continue
        contacts = []
        for name, region, source in sources:
            if source.get('value') is None or source['status'] in ('unknown', 'conflict', 'candidate', 'estimated'):
                continue
            hit = piece.intersection(region.buffer(1.0))
            if hit.is_empty:
                continue
            for lo, hi in _station_spans(piece, hit, minimum_cm):
                contacts.append((lo, hi, name, hit, source))
        if not contacts:
            kept.append(row)
            continue
        highest = max(source['value'] for _, _, _, _, source in contacts)
        # The cell already carries this altitude. A different contact, or an
        # empty row, stays untouched: this read does not invent a level.
        if row.get('value') is None or abs(row['value'] - highest) > .0025:
            kept.append(row)
            continue
        chosen = [item for item in contacts if abs(item[4]['value'] - highest) <= .0025]
        stretches = []
        for lo, hi in _merge_spans((item[0], item[1]) for item in chosen):
            if hi - lo < minimum_cm:
                continue
            sub = substring(piece, lo, hi)
            hits = [item[3] for item in chosen if not (item[1] < lo or item[0] > hi)]
            coverage = projected_coverage(sub, hits) if hits else 0.
            if coverage < .8:
                continue
            fact = inherited(row, [item[4] for item in chosen],
                'spatial_slab_region_reference', .9 * coverage, value=highest,
                source_slabs=sorted({item[2] for item in chosen}), spatial_coverage=coverage,
                region_ids=sorted({item[4].get('region_id', 'principal') for item in chosen}))
            fact['status'] = 'inferred'
            fact['warnings'] = sorted(set(fact['warnings'] + ['slab_contact_reference_without_cut_offset']))
            if (fact.get('confidence_pct') or 0) <= (row.get('confidence_pct') or 0):
                continue
            stretches.append((lo, hi, fact))
        if not stretches:
            kept.append(row)
            continue
        cursor = 0.
        for lo, hi, fact in stretches:
            if lo - cursor > .1:
                gap = deepcopy(row)
                gap.update(range_start=round(start + cursor, 2), range_end=round(start + lo, 2), range_unit='cm')
                kept.append(gap)
            fact.update(range_start=round(start + lo, 2), range_end=round(start + hi, 2),
                        range_unit='cm', fv_segments=[])
            kept.append(fact)
            cursor = hi
        if piece.length - cursor > .1:
            gap = deepcopy(row)
            gap.update(range_start=round(start + cursor, 2), range_end=round(end, 2), range_unit='cm')
            kept.append(gap)
    return kept
