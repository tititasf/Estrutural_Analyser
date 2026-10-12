"""Index canonical geometry without discarding the original label survey."""
from copy import deepcopy
import hashlib


def include_geometry(items, context):
    state = context['state']
    groups = {'slab': state.get('slabs', []), 'pillar': state.get('pilares', []),
              'beam': context.get('tables', {}).get('beams', [])}
    known = {(i['item_class'], i['display_name']) for i in items}
    canonical = set()
    for cls, rows in groups.items():
        for row in rows:
            name = row.get('name')
            if not name:
                continue
            key = (cls, name)
            canonical.add(key)
            if key in known:
                continue
            scope = ':'.join(str(context.get(k, '')) for k in ('root', 'floor', 'tower_path'))
            identity = scope + ':' + context['evidence_id'] + ':' + cls + ':' + name
            items.append({'item_id': 'canonical:' + hashlib.sha256(identity.encode()).hexdigest(),
                'item_class': cls, 'display_name': name, 'levels': [], 'segments': [],
                'identity_source': 'canonical_sa_geometry',
                'evidence_ids': [context['evidence_id']],
                'geometry': {'points': deepcopy(row.get('points') or [])}})
            known.add(key)
    for item in items:
        item['canonical_geometry_available'] = (item['item_class'], item['display_name']) in canonical


def coverage(items):
    names = {(i['item_class'], i['display_name']) for i in items
             if i.get('canonical_geometry_available')}
    return {plural: sum(cls == singular for cls, _ in names)
            for singular, plural in [('pillar', 'pillars'), ('slab', 'slabs'), ('beam', 'beams')]}
