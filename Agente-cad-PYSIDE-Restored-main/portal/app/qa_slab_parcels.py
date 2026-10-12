"""Aggregate slab measurements without losing homonymous physical units."""
from collections import defaultdict


def annotate_slab_parcels(report, slabs):
    from src.core.slab_parcel_identity import parcel_identity, source_label_handle
    contacts = report.setdefault('contacts', [])
    parcels, groups = [], defaultdict(list)
    for i, slab in enumerate(slabs):
        path = f'/collections/lajes/{i}'
        identity = parcel_identity(slab)
        own = [c for c in contacts if c.get('unit_path') == path]
        for contact in own:
            contact['parcel_id'] = identity
            contact['source_label_handle'] = source_label_handle(slab)
        divergent = any(c.get('errors') for c in own)
        uncertain = not own or any(c.get('status') != 'measured' for c in own)
        status = 'diverge' if divergent else 'incerto' if uncertain else 'confere'
        record = dict(item=str(slab.get('name') or ''),parcel_id=identity,
                      unit_path=path,source_label_handle=source_label_handle(slab),
                      source_handles=sorted({h for c in own for h in c.get('handles', [])}),
                      status=status,blocks_promotion=status != 'confere')
        parcels.append(record)
        groups[record['item']].append(record)
    aggregates = {}
    for name, rows in groups.items():
        statuses = {r['status'] for r in rows}
        status = 'diverge' if 'diverge' in statuses else 'incerto' if 'incerto' in statuses else 'confere'
        aggregates[name] = dict(status=status,parcel_count=len(rows),
            parcel_ids=sorted(r['parcel_id'] for r in rows),blocks_promotion=status != 'confere')
        # Existing consumers inspect contacts, not additive aggregate fields.
        # A good last parcel must not certify an uncertain homonymous parcel.
        if len(rows) > 1 and status != 'confere':
            contacts.append(dict(item=name,aspect='parcelas homônimas',
                status='uncertain',errors={},guards=report.get('guards') or [],
                blocks_promotion=True,reason='uma ou mais parcelas físicas permanecem incertas ou divergentes',
                parcel_ids=aggregates[name]['parcel_ids']))
    report['parcels'] = parcels
    report['items'] = aggregates
    return report
