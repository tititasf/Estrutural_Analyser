"""Corroborate estimated SA cells against a validated frozen PRE parcel.

This adapter changes provenance only when the current value already agrees.
Neither repeated names nor changing segment indices establish correspondence.
"""
from copy import deepcopy
import math

from shapely.geometry import LineString

from .level_provenance import collect, walk, origin_kind

METHOD = 'preprocessed_original_lateral_level'
STRONG = {'inferred', 'sa_evidence', 'human_review', 'observed'}


def strong_path(fact_id, index, seen=None):
    seen = set() if seen is None else seen
    if fact_id in seen:
        return False
    fact = index.get(fact_id) or {}
    if fact.get('status') not in STRONG or fact.get('unit') != 'm' or number(fact.get('value')) is None:
        return False
    return all(strong_path(source, index, seen | {fact_id}) for source in
               set((fact.get('source_fact_ids') or []) + (fact.get('derived_from') or [])))


def number(value):
    try:
        result = float(str(value).replace(',', '.'))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def parcel_input(package):
    """Call only after context scope, signature and source freshness checks."""
    inventory = package.get('level_inventory') or {}
    segments = inventory.get('beam_segments') or []
    facts = package.get('levels') or []
    index = collect({'items': [{'levels': facts, 'segments': segments}]})
    result = []
    for seg in segments:
        family = seg.get('family', '')
        proof = seg.get('original_label_parcel_proof') or {}
        if (not family.startswith('lateral_')
                or proof.get('section_source') != 'lateral_boundary_of_original_label_proved_fv'
                or not proof.get('source_entity_handles') or not proof.get('source_fv_segments')
                or (number(proof.get('spatial_coverage')) or 0) < .8):
            continue
        matches = [f for f in facts if f.get('segment_id') == seg.get('segment_id')
                   and f.get('item_id') == seg.get('beam_item_id') and f.get('field') == family]
        if len(matches) != 1:
            continue
        fact = matches[0]
        if fact.get('unit') != 'm' or fact.get('status') not in STRONG or number(fact.get('value')) is None:
            continue
        roots, cycles, missing = walk(fact['fact_id'], index)
        if (cycles or missing or not roots or not strong_path(fact['fact_id'], index)
                or any(r.get('status') not in STRONG
                or r.get('unit') != 'm' or number(r.get('value')) is None
                or origin_kind(r) not in ('cad_direct_level', 'cad_named_section_level', 'human_review')
                for r in roots)):
            continue
        try:
            geometry = LineString(seg['points'])
        except (KeyError, TypeError, ValueError):
            continue
        if geometry.is_empty or geometry.length <= 1 or not geometry.is_simple:
            continue
        ranges = seg.get('level_ranges') or []
        intervals = []
        for row in ranges:
            if (row.get('status') not in STRONG or row.get('unit') != 'm'
                    or row.get('range_unit') != 'cm' or number(row.get('value')) is None
                    or abs(number(row['value']) - number(fact['value'])) > .0025):
                break
            start, end = number(row.get('range_start')), number(row.get('range_end'))
            if start is None or end is None or end <= start:
                break
            intervals.append((start, end))
        else:
            intervals.sort()
            covered = 0.
            for start, end in intervals:
                if start > covered + .05:
                    break
                covered = max(covered, end)
            if intervals and covered >= geometry.length - .05:
                result.append(dict(family=family, beam_name=seg.get('beam_name'),
                    points=deepcopy(seg['points']), value=number(fact['value']), unit='m',
                    status=fact['status'], fact_id=fact['fact_id'],
                    evidence_ids=deepcopy(fact.get('evidence_ids') or []),
                    source_fact_ids=deepcopy(fact.get('source_fact_ids') or []),
                    root_fact_ids=sorted({r['fact_id'] for r in roots}),
                    warnings=deepcopy(seg.get('warnings') or []),
                    confidence_pct=fact.get('confidence_pct'),
                    source_revision=package['scope']['source_revision'],
                    parcel_proof=deepcopy(proof)))
    return result


def corroborate_cells(beams, parcels, *, source_revision):
    """Write proof onto actual link cells, preserving every geometric field."""
    from src.core.preficha_segments import collect_preficha_segments
    receipt = dict(consumed=[], blocked=[])
    # A prior run's cached annotation cannot establish consumption this run.
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        beam_links = beam.get('links') or {}
        if not isinstance(beam_links, dict):
            continue
        for slots in beam_links.values():
            if not isinstance(slots, dict):
                continue
            for links in slots.values():
                if isinstance(links, list):
                    for link in links:
                        if isinstance(link, dict) and isinstance(link.get('lv_cell'), dict):
                            link['lv_cell'].pop('preprocess_level_provenance', None)
    if not parcels:
        return receipt
    for family, entries in collect_preficha_segments(beams).items():
        for entry in entries:
            if entry.get('level_source') != 'lv_cell_estimado':
                continue
            cell = entry['_link_ref'].get('lv_cell')
            if not isinstance(cell, dict) or not cell.get('level_estimado'):
                continue
            try:
                current = LineString(entry['points'])
            except (KeyError, TypeError, ValueError):
                continue
            matches = []
            for parcel in parcels:
                if (parcel['family'] != family or parcel['beam_name'] != entry['beam_name']
                        or parcel['source_revision'] != source_revision):
                    continue
                frozen = LineString(parcel['points'])
                if (current.hausdorff_distance(frozen) <= .05
                        and abs(current.length-frozen.length) <= .05):
                    matches.append(parcel)
            if not matches:
                continue
            if len(matches) != 1:
                receipt['blocked'].append(dict(uid=entry['uid'], reason='ambiguous_original_level_parcel'))
                continue
            proof = matches[0]
            value = number(cell.get('level'))
            if value is None or abs(value-proof['value']) > .0025:
                receipt['blocked'].append(dict(uid=entry['uid'], reason='original_level_parcel_conflict'))
                continue
            cell['preprocess_level_provenance'] = deepcopy(proof)
            receipt['consumed'].append(dict(uid=entry['uid'], value=value, method=METHOD,
                status=proof['status'], fact_id=proof['fact_id'],
                source_revision=source_revision, root_fact_ids=proof['root_fact_ids']))
    return receipt
