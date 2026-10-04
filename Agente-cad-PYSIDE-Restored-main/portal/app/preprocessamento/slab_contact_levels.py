"""Scoped geometric slab references for independently collected beam seeds."""
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
