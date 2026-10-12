"""Resolve measured section constraints without circular confidence inflation."""
from collections import defaultdict, deque
from math import isfinite


def resolve_cut_level_graph(seeds, edges, *, tolerance_m=.0025):
    """Edges state ``target = source + delta_m``; seeds are independent facts.

    An inconsistent cycle or disagreeing independent anchors rejects the whole
    connected component. An unanchored cycle never produces an altitude.
    Each accepted result keeps one acyclic path and its original root confidence.
    Caller owns evidence validation, scope and field persistence.
    """
    graph = defaultdict(list)
    for edge in edges:
        source, target = edge['source'], edge['target']
        delta = float(edge['delta_m'])
        if source == target or not isfinite(delta):
            continue
        graph[source].append((target, delta, edge))
        graph[target].append((source, -delta, edge))
    for name in seeds:
        graph[name]
    resolved, rejected, visited = {}, {}, set()
    for first in sorted(graph):
        if first in visited:
            continue
        offsets, queue, inconsistent = {first: 0.0}, deque([first]), False
        while queue:
            source = queue.popleft()
            for target, delta, _edge in graph[source]:
                proposed = offsets[source] + delta
                if target in offsets:
                    inconsistent |= abs(offsets[target]-proposed) > tolerance_m
                else:
                    offsets[target] = proposed
                    queue.append(target)
        visited.update(offsets)
        roots = [n for n in offsets if n in seeds and isfinite(float(seeds[n]['value']))]
        reason = 'inconsistent_cut_cycle' if inconsistent else ''
        datums = [float(seeds[n]['value'])-offsets[n] for n in roots]
        if datums and max(datums)-min(datums) > tolerance_m:
            reason = 'conflicting_independent_roots'
        if reason or not roots:
            for name in offsets:
                if name not in seeds:
                    rejected[name] = reason or 'no_independent_root'
            continue
        root = max(sorted(roots), key=lambda n: float(seeds[n].get('confidence', .55)))
        paths, queue = {root: ([root], [])}, deque([root])
        while queue:
            source = queue.popleft()
            names, evidence = paths[source]
            for target, _delta, edge in graph[source]:
                if target in paths:
                    continue
                paths[target] = (names+[target], evidence+[edge])
                queue.append(target)
        for name in offsets:
            if name in seeds:
                continue
            path, evidence = paths[name]
            resolved[name] = {
                'value': float(seeds[root]['value']) + offsets[name]-offsets[root],
                'root_slab': root, 'root_source': dict(seeds[root]),
                'confidence': min(.80, float(seeds[root].get('confidence', .55))),
                'path': path, 'edges': evidence,
                'independent_roots': sorted(roots),
            }
    return resolved, rejected


def infer_measured_cut_network(runner, slabs):
    """Apply only unknown levels, rooted in current independently bound evidence.

    Cut links and pre-SA facts have already passed the canonical scope/geometry
    consumers. Persisted contextual inferences alone cannot become new roots.
    Regional/inverted sections keep their dedicated interpretation path.
    """
    from .slab_level_inference import (paired_cut_delta_cm, principal_cut_wings_match,
                                       gate_cut_delta_level)
    from .lv_cut_inventory import geometry_key
    seeds, edges = {}, []
    by_name = {s.get('name'): s for s in slabs if s.get('name')}
    for name, slab in by_name.items():
        source = runner._slab_level_source(slab, include_neighbor_context=False)
        pre = slab.get('preprocess_level_evidence') or {}
        provenance = slab.get('_nivel_provenance') or {}
        pre_matches = (pre.get('evidence_ids') and pre.get('unit') == 'm'
                       and pre.get('value') is not None and source
                       and abs(float(pre['value'])-source['value']) <= .0025)
        if source and (source.get('human') or pre_matches or
                provenance.get('provenance') == 'contida' and not provenance.get('needs_human_review')):
            confidence = (slab.get('level_inference') or {}).get('confidence_pct')
            seeds[name] = {**source, 'slab': name,
                'confidence': 1.0 if source.get('human') else
                    float(confidence)/100 if confidence is not None else .65,
                'evidence_ids': pre.get('evidence_ids', []),
                'preprocess_method': pre.get('method')}
        for cut in runner._slab_cut_links(slab):
            if (cut.get('section_semantics') or {}).get('beam_type') == 'inverted':
                continue
            ficha = cut.get('ficha') or {}
            sides = [ficha.get('side_a_laje_name'), ficha.get('side_b_laje_name')]
            other_name = next((n for n in sides if n != name and n in by_name), None)
            if other_name is None:
                continue
            other = by_name[other_name]
            delta = paired_cut_delta_cm(cut, name, other_name)
            if delta is None or not principal_cut_wings_match(cut, slab, other):
                continue
            signature = geometry_key(cut.get('points'))
            if not signature or not any(signature == geometry_key(c.get('points'))
                                        for c in runner._slab_cut_links(other)):
                continue
            edges.append({'source': other_name, 'target': name, 'delta_m': delta/100,
                          'points': cut.get('points'), 'beam': ficha.get('beam_name')})
    resolved, rejected = resolve_cut_level_graph(seeds, edges)
    applied = 0
    for name, row in resolved.items():
        slab = by_name[name]
        if runner._slab_level_source(slab, include_neighbor_context=False):
            continue
        root = row['root_source']
        delta_cm = (row['value']-root['value'])*100
        gate = gate_cut_delta_level(row['value'], delta_cm, reference_level_m=root['value'])
        if not gate['accepted']:
            rejected[name] = 'rooted_cut_level_gate_failed'
            continue
        runner._apply_inferred_slab_level(slab, row['value'], 'cut_view_rooted_graph', [row])
        slab['level_inference'].update(confidence=row['confidence'], gates=gate['gates'],
                                       root_slab=row['root_slab'], path=row['path'])
        applied += 1
    runner._sa_cut_level_graph_qa = {'roots': sorted(seeds), 'edges': len(edges),
                                   'applied': applied, 'rejected': rejected}
    return applied
