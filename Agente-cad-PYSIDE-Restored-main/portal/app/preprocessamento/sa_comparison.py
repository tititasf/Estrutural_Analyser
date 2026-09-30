"""Comparação consultiva com snapshot SA de origem exata.

Um snapshot sem identidade completa não é comparado por semelhança de nome.
"""
from __future__ import annotations

from .service import digest


def compare_tower(package, sa_snapshot, *, correspondence=None):
    scope = package['scope']
    origin = sa_snapshot.get('source') or {}
    if any(origin.get(key) != scope[key] for key in
           ('obra_id', 'pavimento_id', 'recorte_id', 'source_revision')):
        return {'status': 'unavailable', 'reason': 'source_identity_or_revision_mismatch',
                'tower': scope, 'comparisons': []}
    preprocess_items = (package.get('pillars') or {}).get('items') or []
    sa_items = sa_snapshot.get('items') or []
    by_id = {}
    for item in sa_items:
        by_id.setdefault(item.get('id'), []).append(item)
    correspondence = correspondence or {}
    comparisons = []
    for item in preprocess_items:
        link = correspondence.get(item['item_id'])
        candidates = by_id.get(link.get('sa_item_id')) or [] if isinstance(link, dict) else []
        if (len(candidates) != 1 or not isinstance(link, dict) or
                link.get('source_revision') != scope['source_revision'] or
                link.get('recorte_id') != scope['recorte_id'] or
                link.get('status') != 'confirmed'):
            comparisons.append({'pre_item_id': item['item_id'], 'status': 'unavailable_no_exact_link'})
            continue
        pre_value = item.get('classification_raw')
        sa_value = candidates[0].get('classification')
        comparisons.append({'pre_item_id': item['item_id'], 'sa_item_id': candidates[0].get('id'),
                            'field': 'classification', 'pre_value': pre_value, 'sa_value': sa_value,
                            'status': 'unknown' if pre_value is None or sa_value is None
                            else 'same' if pre_value == sa_value else 'divergent'})
    return {'status': 'consultative', 'tower': scope,
            'pre_package_hash': digest(package), 'comparisons': comparisons}
