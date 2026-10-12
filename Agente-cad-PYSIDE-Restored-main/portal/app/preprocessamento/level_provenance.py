"""Explain each level support score by its evidence path; never changes values.

The percentage is evidence support (rubric), not a calibrated probability.
Independent confirmations are counted once per root origin: the same CAD mark
reaching FV, LV, LAJ and PIL remains a single source.
"""
from __future__ import annotations
import math

RUBRIC_REVISION = 'level_evidence_completeness_v1.2-independent-agreement'
SPATIAL_METHODS = ('spatial_', 'contact', 'lv_independent_evidence_fills_fv',
                   'standard_beam_top_principal_slab', 'no_slab')
CONSTRUCTED = ('spatial_fv_reference', 'lateral_spatial_level_ranges',
               'same_lateral_segment_level_continuity', 'same_beam_face_pillar_wall_continuity',
               'pillar_face_fv_contact', 'pillar_face_slab_contact', 'pillar_face_slab_region_contact')
QUANTITY = {'beam_bottom': 'fundo físico = referência superior − altura/100',
            'fundo': 'referência superior da viga (datum FV)',
            'slab_region_level': 'nível regional da laje',
            'slab_level': 'nível da laje', 'top': 'topo do pilar (contato mais alto por face)',
            'base': 'base do pilar', 'cut_beam_reference': 'referência superior pelo corte'}
WEAK = ('unknown', 'conflict', 'candidate')


def collect(tower):
    """Every persisted fact reachable by source_fact_ids, keyed by fact_id."""
    index = {}

    def add(fact):
        if isinstance(fact, dict) and fact.get('fact_id'):
            index.setdefault(fact['fact_id'], fact)
            for row in fact.get('level_ranges') or []:
                add(row)

    for item in tower.get('items', []):
        for fact in item.get('levels', []):
            add(fact)
        for contact in item.get('face_level_contacts') or []:
            add(contact)
        for seg in item.get('segments', []):
            add(seg.get('native_level_evidence'))
            for row in seg.get('level_ranges') or []:
                add(row)
    for fact in tower.get('floor_level_sources') or []:
        add(fact)
    for fact in tower.get('cut_level_facts') or []:
        add(fact)
    return index


def origin_kind(fact):
    handles = [e for e in fact.get('evidence_ids') or [] if str(e).startswith('cad:')]
    if fact.get('status') == 'human_review':
        return 'human_review'
    if fact.get('level_basis') == 'owner_convention':
        return 'owner_convention'
    if fact.get('method') == 'cad_level_inside_slab' and handles:
        return 'cad_direct_level'
    if fact.get('method') == 'named_section_marker_and_plan_region':
        # The adapter verifies the current source revision, named plan match,
        # level marker and geometry before publishing this root. A method name
        # or nearby CAD text alone does not establish a level reference.
        source = fact.get('section_source_id')
        marker = fact.get('marker_handle')
        revision = str(fact.get('section_revision') or '')
        if (fact.get('status') == 'sa_evidence' and source
                and source in (fact.get('evidence_ids') or [])
                and marker and 'cad:'+str(marker) in handles
                and len(revision) == 64 and all(c in '0123456789abcdef' for c in revision)
                and fact.get('projection') and fact.get('region_geometry')
                and fact.get('unit') == 'm' and fact.get('value') is not None):
            return 'cad_named_section_level'
        return 'sa_field_without_traced_root'
    if 'floor' in str(fact.get('method', '')) or fact.get('status') == 'floor_reference':
        return 'floor_convention'
    if fact.get('status') == 'estimated':
        return 'estimate'
    if fact.get('value') is None or fact.get('status') in WEAK:
        return 'missing_or_unresolved'
    return 'sa_field_without_traced_root'


def origin_key(fact):
    """Same CAD handles = same origin, regardless of the class that consumed it."""
    handles = sorted(e for e in fact.get('evidence_ids') or [] if str(e).startswith('cad:'))
    kind = origin_kind(fact)
    if kind == 'cad_named_section_level':
        # Two wings of one section marker are one origin, even when their
        # plan polygons and downstream classes differ.
        return kind + ':' + fact['section_source_id'] + ':' + fact['section_revision'] + ':' + fact['marker_handle']
    if kind == 'cad_direct_level' and handles:
        return kind + ':' + ','.join(handles)
    return kind + ':' + fact['fact_id']


def origin_tokens(roots):
    """A compound CAD origin still shares each mark with a partial origin."""
    tokens = set()
    for root in roots:
        handles = {str(e) for e in root.get('evidence_ids') or [] if str(e).startswith('cad:')}
        tokens.update(handles or {origin_key(root)})
    return tokens


def walk(fact_id, index, trail=()):
    """Return (roots, cycles, missing) of the derivation graph below fact_id."""
    if fact_id in trail:
        return [], [list(trail) + [fact_id]], []
    fact = index.get(fact_id)
    if fact is None:
        return [], [], [fact_id]
    sources = list(dict.fromkeys([*(fact.get('source_fact_ids') or []),
                                 *(fact.get('derived_from') or [])]))
    if not sources:
        return [fact], [], []
    roots, cycles, missing = [], [], []
    for source in sources:
        r, c, m = walk(source, index, trail + (fact_id,))
        roots += r
        cycles += c
        missing += m
    return roots, cycles, missing


def path(fact, index, seen=None):
    """Weakest-source chain from a root to fact: the chain that bounds the score."""
    seen = set() if seen is None else seen
    seen.add(fact['fact_id'])
    sources = [index[s] for s in fact.get('source_fact_ids') or []
               if s in index and s not in seen]
    step = {'fact_id': fact['fact_id'], 'method': fact.get('method'),
            'value': fact.get('value'), 'unit': fact.get('unit'),
            'confidence_pct': fact.get('confidence_pct'),
            'factor': (fact.get('confidence_components') or {}).get('spatial_transfer_factor'),
            'coverage': fact.get('spatial_coverage'), 'region_id': fact.get('region_id'),
            'cut_id': fact.get('cut_id'), 'datum_id': fact.get('datum_id')}
    if not sources:
        return [step]
    weakest = min(sources, key=lambda s: s.get('confidence_pct') or 0)
    return path(weakest, index, seen) + [step]


def explain(fact, index):
    roots, cycles, missing = walk(fact['fact_id'], index)
    chain = path(fact, index)
    origins = sorted({origin_key(r) for r in roots})
    root = index.get(chain[0]['fact_id'], fact)
    confirmations, seen, disagreements = [], origin_tokens(roots), []
    for alt in fact.get('independent_confirmations') or []:
        # Agreement born of the same root (e.g. two cuts read from one slab
        # mark) is not an independent confirmation.
        alt_roots, alt_cycles, alt_missing = walk(alt.get('fact_id'), index)
        keys = {origin_key(r) for r in alt_roots}
        tokens = origin_tokens(alt_roots)
        candidate = index.get(alt.get('fact_id'))
        if candidate is None:
            continue
        try:
            values = float(fact.get('value')), float(candidate.get('value'))
            agrees = (all(math.isfinite(v) for v in values) and abs(values[0]-values[1]) <= .0025
                      and bool(fact.get('unit')) and fact.get('unit') == candidate.get('unit')
                      and fact.get('datum_id') == candidate.get('datum_id'))
        except (ValueError, TypeError):
            agrees = False
        if not agrees:
            disagreements.append({'fact_id': candidate['fact_id'], 'value': candidate.get('value'),
                                  'unit': candidate.get('unit'), 'datum_id': candidate.get('datum_id')})
            continue
        if tokens and not tokens.intersection(seen) and not alt_cycles and not alt_missing:
            seen.update(tokens)
            confirmations.append({**alt, 'origin_key': ','.join(sorted(keys))})
    components = fact.get('confidence_components') or {}
    limitations = sorted(set(fact.get('warnings') or []) |
                         {k for k in components if k.endswith('_cap')})
    if fact.get('status') in ('estimated', 'inferred'):
        limitations.append('status_' + fact['status'])
    sources = [index[s] for s in fact.get('source_fact_ids') or [] if s in index]
    support = fact.get('confidence_pct') or 0
    monotonic = all(support <= (s.get('confidence_pct') or 0) + .05 for s in sources)
    coverages = [s['coverage'] for s in chain if s.get('coverage') is not None]
    spatial_steps = [s for s in chain[1:] if any(t in str(s.get('method')) for t in SPATIAL_METHODS)]
    spatial = bool(spatial_steps)
    # Interval/contact matches are geometric by construction (range = FV overlap,
    # face edge intersecting the element); they carry no separate coverage.
    constructed = all(s.get('coverage') is not None or s.get('method') in CONSTRUCTED
                      for s in spatial_steps)
    units = {s['unit'] for s in chain if s.get('unit')}
    datums = {s['datum_id'] for s in chain if s.get('datum_id')}
    kinds = {origin_kind(r) for r in roots}
    gates = {
        'origem': ('fail' if not roots or fact.get('value') is None else
                   'limited' if kinds & {'estimate', 'missing_or_unresolved',
                                         'sa_field_without_traced_root'} else 'pass'),
        'sem_ciclo': 'fail' if cycles else 'pass',
        'fontes_presentes': 'fail' if missing else 'pass',
        'associacao_espacial': ('n/a' if not spatial else
                                'fail' if coverages and min(coverages) < .8 else
                                'pass' if constructed else 'not_measured'),
        'grandeza': 'pass' if len(units) <= 1 and len(datums) <= 1 else 'fail',
        'excecoes': ('pending_training' if 'owner_convention' in kinds
                     or fact.get('level_basis') == 'owner_convention' else
                     'not_certified' if 'slab_contact_reference_without_cut_offset' in limitations
                     else 'n/a'),
        'concordancia': ('conflict' if fact.get('status') == 'conflict' or disagreements else
                         'confirmed' if confirmations else 'single_path'),
        'sem_aumento_por_transferencia': 'pass' if monotonic else 'fail',
    }
    return {'rubric': RUBRIC_REVISION, 'meaning': 'suporte_de_evidencia_nao_probabilidade',
            'support_pct': support, 'quantity': QUANTITY.get(fact.get('field'), fact.get('field')),
            'primary_source': {**chain[0], 'origin_kind': origin_kind(root),
                               'evidence_ids': (root.get('evidence_ids') or [])[:8]},
            'calculation': chain, 'independent_origins': origins,
            'independent_origin_count': len(origins),
            'confirmations': confirmations, 'confirmation_conflicts': disagreements,
            'limitations': limitations, 'gates': gates}


def annotate(tower):
    index = collect(tower)
    summary = {'rubric': RUBRIC_REVISION, 'facts': len(index), 'cycles': 0, 'missing_sources': 0,
               'support_increase_violations': 0, 'limiting_origin_kinds': {}}
    for fact in index.values():
        if fact.get('status') == 'not_applicable':
            continue
        explanation = explain(fact, index)
        fact['support_explanation'] = explanation
        gates = explanation['gates']
        summary['cycles'] += gates['sem_ciclo'] == 'fail'
        summary['missing_sources'] += gates['fontes_presentes'] == 'fail'
        summary['support_increase_violations'] += gates['sem_aumento_por_transferencia'] == 'fail'
        if (fact.get('confidence_pct') or 0) < 60:
            kind = explanation['primary_source']['origin_kind']
            summary['limiting_origin_kinds'][kind] = summary['limiting_origin_kinds'].get(kind, 0) + 1
    tower['evidence_provenance'] = summary
    return summary
