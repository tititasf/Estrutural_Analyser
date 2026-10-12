"""Refresh derived pillar levels from the final slab evidence, after merging."""
from __future__ import annotations


def reconcile_pillar_slab_levels(pillars, slabs, source_of, format_level):
    sources = {s.get('name'): source_of(s, include_neighbor_context=False)
               for s in slabs if s.get('name')}
    changed = 0
    for pillar in pillars:
        if pillar.get('is_validated'):
            continue
        validated = set(pillar.get('validated_fields') or [])
        fields = pillar.setdefault('fields', {})
        adjacent = pillar.get('lajes_adjacentes') or pillar.get('lajes') or []
        # Reports cache rendered face tables before final slab reconciliation.
        # Rebuild that derived presentation from the final authoritative map.
        pillar.pop('_abcd_tables', None)
        for entry in pillar.get('lajes') or []:
            if not isinstance(entry, dict) or entry.get('validated'):
                continue
            src = sources.get(entry.get('laje'))
            if entry.get('laje') in sources:
                entry['nivel'] = (format_level(src['value'])
                                  if src and src.get('value') is not None else '')
        values = [sources[e['laje']]['value'] for e in adjacent
                  if isinstance(e, dict) and sources.get(e.get('laje'))
                  and sources[e['laje']].get('value') is not None]
        value = format_level(max(values)) if values else ''
        if 'level' not in validated and 'Nível (Via Laje)' not in validated:
            pillar['level'] = value
            if value:
                fields['Nível (Via Laje)'] = value
            else:
                fields.pop('Nível (Via Laje)', None)
            changed += 1
        for face in 'ABCDEF':
            for slot in (1, 2):
                prefix = f'p_s{face}_l{slot}'
                key = prefix + '_v'
                slots = (pillar.get('validated_link_classes') or {}).get(key) or []
                if key in validated or slots:
                    continue
                name = pillar.get(prefix + '_n') or fields.get(prefix + '_n')
                if name not in sources:
                    continue
                src = sources[name]
                level = format_level(src['value']) if src and src.get('value') is not None else ''
                pillar[key] = level
                if key in fields:
                    fields[key] = level
                # An automatic scalar cannot retain a contradictory old link.
                pillar.setdefault('links', {}).pop(key, None)
    return changed
