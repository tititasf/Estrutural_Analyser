"""Conflitos consultivos e ciclos de proveniência; não promove consenso."""
from __future__ import annotations


def check_facts(facts):
    conflicts = []
    indexed = {fact["fact_id"]: fact for fact in facts}
    groups = {}
    for fact in facts:
        # Different physical segments legitimately have different elevations.
        groups.setdefault((fact["item_id"], fact["field"], fact.get('segment_id'),
                           tuple(map(tuple, fact.get('positions') or []))), []).append(fact)
    for key, group in groups.items():
        known = [f for f in group if f.get("value") is not None]
        alternatives = {(str(f["value"]), f.get("unit"), f.get("datum_id")) for f in known}
        if len(alternatives) > 1:
            conflicts.append({"kind": "divergent_values_or_reference", "item_id": key[0],
                              "field": key[1], "fact_ids": [f["fact_id"] for f in known]})
    visited, active = set(), set()

    def visit(key):
        if key in active:
            conflicts.append({"kind": "evidence_cycle", "fact_id": key})
            return
        if key in visited:
            return
        active.add(key)
        for dependency in indexed[key].get("derived_from", []):
            if dependency in indexed:
                visit(dependency)
            else:
                conflicts.append({"kind": "missing_evidence", "fact_id": key, "dependency": dependency})
        active.remove(key)
        visited.add(key)

    for key in indexed:
        visit(key)
    return conflicts
