"""Bind repeated beam labels to source-proved fund and lateral parcels."""
from collections import defaultdict
from pathlib import Path


def parcel_receivers(items, segments, source, *, measure=None):
    """No same-name transfer: require the original label in wall/section proof.

    This proves parcel identity only. Level provenance and full contour QA
    remain the responsibility of their existing independent consumers.
    """
    if not source or not Path(source).is_file():
        return {}, {}
    if measure is None:
        from .oriented_beam_section import source_section
        measure = source_section
    groups = defaultdict(list)
    for item in items:
        if item.get('item_class') == 'beam':
            groups[item['display_name']].append(item)
    receivers, proofs = {}, {}
    for name, labels in groups.items():
        if len(labels) < 2:
            continue
        for family, segment in segments.get(name, []):
            if family != 'fundo':
                continue
            proof = measure(segment.get('points'), name, source)
            if not proof or proof.get('section_source') != 'original_aligned_name_section_wall_pair':
                continue
            if len(proof.get('source_name_candidates', [])) > 1:
                continue
            handles = set(proof.get('source_entity_handles') or [])
            owners = [label for label in labels
                      if handles.intersection(label.get('source_entity_handles') or [])]
            if len(owners) == 1 and segment.get('uid'):
                receivers[segment['uid']] = owners[0]['item_id']
                proofs[segment['uid']] = proof
        # A lateral has no closed section of its own. Bind it through the
        # original-label-proved FV it actually runs along, never by name or
        # segment numbering. Do not transfer levels here.
        from .segment_levels import geometry
        from shapely.ops import unary_union
        funds = [(segment, geometry(segment.get('points')))
                 for family, segment in segments.get(name, [])
                 if family == 'fundo' and segment.get('uid') in receivers]
        for family, segment in segments.get(name, []):
            if family == 'fundo' or not segment.get('uid'):
                continue
            line = geometry(segment.get('points'))
            if line is None or line.geom_type != 'LineString' or line.length <= 1:
                continue
            contacts = defaultdict(list)
            supporting = defaultdict(list)
            for fund, contour in funds:
                if contour is None or contour.geom_type != 'Polygon':
                    continue
                # Physical boundary contact excludes interior/crossing lines.
                hit = line.intersection(contour.boundary.buffer(.05))
                if hit.length <= 1:
                    continue
                owner = receivers[fund['uid']]
                contacts[owner].append(hit)
                supporting[owner].append(fund['uid'])
            if len(contacts) != 1:
                continue
            owner, hits = next(iter(contacts.items()))
            coverage = unary_union(hits).length / line.length
            if coverage < .8:
                continue
            receivers[segment['uid']] = owner
            proofs[segment['uid']] = dict(
                section_source='lateral_boundary_of_original_label_proved_fv',
                source_fv_segments=supporting[owner],
                spatial_coverage=coverage,
                source_entity_handles=sorted({h for uid in supporting[owner]
                    for h in proofs[uid].get('source_entity_handles', [])}))
    return receivers, proofs
