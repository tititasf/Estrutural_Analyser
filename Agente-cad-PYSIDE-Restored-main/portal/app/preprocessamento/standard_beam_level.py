"""Owner convention: common slab datum unless a beam exception is indicated.

This is scored support for a convention, never a measured beam altitude.
Unclassified fills and incomplete drawings cannot certify absence of exceptions.
"""
from copy import deepcopy

DECISION = 'NIV-PADRAO-EXCECAO-20261003'


def sources(slab_items, context, scalar_sources, geometry):
    result = []
    for slab in context['state'].get('slabs', []):
        item = slab_items.get(slab['name'])
        if not item:
            continue
        # The principal datum remains the beam reference across an inner slab
        # step. Do not use that inner region's scalar as the beam datum.
        principal = [f for f in item['levels'] if f.get('region_id') == 'principal'
                     and f.get('field') == 'slab_region_level']
        source = max(principal, key=lambda f: f.get('confidence_pct', 0)) if principal else scalar_sources.get(slab['name'])
        if source and (not slab.get('slab_steps') or principal):
            geom = geometry(slab.get('points'))
            if geom is not None:
                result.append((slab['name'], geom, source))
    return result


def common_datum_contacts(contacts, datum, coverage, geom):
    """Contacts at the storey's common datum when the others are lower slabs.

    A slab below the common level is a slab step closed by the top panel; by
    NIV-VIGA-LAJE-PAINEL it does not move the beam. A higher contact would
    require the beam itself to change, which only a cut/hatch proves.
    """
    if (datum is None or datum.get('value') is None or datum.get('status') in
            ('unknown', 'conflict', 'candidate', 'estimated')):
        return None, []
    at = [c for c in contacts if abs(c[2]['value']-datum['value']) <= .0025]
    others = [c for c in contacts if c not in at]
    if not at or any(c[2]['value'] > datum['value'] for c in others):
        return None, []
    if coverage(geom, [hit for _, hit, _ in at]) < .8:
        return None, []
    return at, others


def inner_step_values(slab_items):
    """Níveis de rebaixo que diferem da principal da mesma laje.

    O escalar da laje às vezes é a cota escrita dentro do rebaixo. Esse número
    não é medição da viga.
    """
    found = {}
    for name, item in (slab_items or {}).items():
        principal = [f.get('value') for f in item.get('levels') or []
                     if f.get('field') == 'slab_region_level' and f.get('region_id') == 'principal'
                     and f.get('value') is not None]
        if len({round(v, 4) for v in principal}) != 1:
            continue
        top = principal[0]
        values = [f['value'] for f in item.get('levels') or []
                  if f.get('field') == 'slab_region_level' and f.get('region_id') not in (None, 'principal')
                  and f.get('value') is not None and abs(f['value'] - top) > .0025
                  and f.get('status') not in ('unknown', 'conflict', 'candidate', 'estimated')]
        if values:
            found[name] = values
    return found


def level(geom, native, references, paints, cut_shapes, inherited, coverage, datum=None, steps_by_slab=None):
    if (geom is None or geom.geom_type != 'Polygon' or paints is None
            or native.get('status') in ('human_review', 'conflict')
            or 'cut' in native.get('method', '')):
        return None
    if any(geom.distance(cut) <= 1 for cut in cut_shapes):
        return None  # includes shortened/unresolved sections; never bypass them
    inner = geom.buffer(-.2)
    if any(inner.intersection(fill).area > 1 for fill in paints):
        return None
    contacts = []
    for name, region, source in references:
        hit = geom.intersection(region.buffer(1))
        if hit.is_empty or coverage(geom, [hit]) <= .01:
            continue
        if (source.get('value') is None or source.get('status') in
                ('unknown', 'conflict', 'candidate', 'estimated', 'floor_reference')):
            return None
        contacts.append((name, hit, source))
    if not contacts:
        return None
    values = [s['value'] for _, _, s in contacts]
    lower = []
    sources = [s for _, _, s in contacts]
    if max(values)-min(values) > .0025:
        contacts, lower = common_datum_contacts(contacts, datum, coverage, geom)
        if not contacts:
            return None
        # The datum only selects which contact is the common level; it is a
        # necessary input and therefore part of the limiting path.
        sources = [s for _, _, s in contacts] + [datum]
        values = [s['value'] for _, _, s in contacts]
    fraction = coverage(geom, [hit for _, hit, _ in contacts])
    if fraction < .8:
        return None
    value = values[0]
    # A convention cannot silently repair a different already-derived datum.
    # The exception is the slab scalar copied from the inner step: NIV-VIGA-LAJE-PAINEL
    # keeps the beam on the principal. A cut, an explicit beam field or a third
    # value stays put.
    if (native.get('value') is not None and native.get('status') not in ('estimated', 'unknown')
            and abs(native['value']-value) > .0025):
        contacted = {name for name, _, _ in contacts}
        step_values = [v for name in contacted for v in (steps_by_slab or {}).get(name, ())]
        copied_from_step = (native.get('method') == 'highest_touching_slab'
                            and any(abs(native['value'] - v) <= .0025 for v in step_values))
        copied_from_lower = any(abs(native['value'] - s['value']) <= .0025 for _, _, s in lower)
        if not copied_from_step and not copied_from_lower:
            return None
    result = inherited(native, sources,
                       'standard_beam_top_principal_slab', .95*fraction,
                       value=value, spatial_coverage=fraction,
                       source_slabs=sorted({name for name, _, _ in contacts}),
                       owner_decision=DECISION, level_basis='owner_convention')
    if lower:
        result['lower_contact_slabs'] = [dict(slab=name, value=s['value'], fact_id=s.get('fact_id'))
                                         for name, _, s in lower]
        result['warnings'] = result['warnings'] + ['lower_adjacent_slab_closed_by_top_panel']
    # Recognition of arbitrary hatch exceptions awaits examples and validation.
    result['confidence_pct'] = min(result['confidence_pct'], 85)
    result['confidence_components']['untrained_exception_reader_cap'] = 85
    result['confidence_components']['owner_convention_factor'] = .95
    result['warnings'] = sorted(set(result['warnings'] + ['standard_level_by_owner_convention',
                                                          'beam_hatch_exception_training_pending']))
    result['status'] = 'inferred'
    result['previous_level_evidence'] = deepcopy(native)
    return result
