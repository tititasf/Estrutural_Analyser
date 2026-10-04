"""Compare production SA slab state against direct DXF elevation evidence.

Jev and the CAD nearest-inside rule are kept separate so an agreement between
them is not counted as independent proof. This tool never edits N1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--jev-probe", type=Path, required=True)
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    probe = json.loads(args.jev_probe.read_text(encoding="utf-8"))
    sa = {row["name"]: str(row.get("nivel") or "") for row in state["slabs"]}
    decisions = []
    for row in probe["results"]:
        item = row["item"]
        inside = sorted((candidate for candidate in row["candidates"]
                         if candidate["inside_n1_polygon"]), key=lambda candidate: candidate["distance"])
        rule = inside[0] if inside else None
        jev_choice = row["jev"]["full"].get("choice")
        jev = next((candidate for candidate in row["candidates"] if candidate["handle"] == jev_choice), None)
        if rule and sa[item] and rule["text"] != sa[item]:
            decision = "direct_marker_vs_sa_conflict"
        elif rule and sa[item]:
            decision = "direct_marker_agrees_sa"
        elif rule:
            decision = "direct_marker_for_empty_sa"
        elif sa[item]:
            decision = "sa_level_without_contained_marker"
        else:
            decision = "no_direct_marker_and_sa_empty"
        decisions.append({"item": item, "sa_state_level": sa[item] or None,
                          "cad_nearest_inside": {"handle": rule["handle"], "text": rule["text"]} if rule else None,
                          "jev_choice": {"handle": jev["handle"], "text": jev["text"]} if jev else None,
                          "inside_candidates": [{"handle": c["handle"], "text": c["text"], "distance": c["distance"]}
                                                for c in inside], "decision": decision,
                          "jev_rule_same_handle": jev_choice == (rule["handle"] if rule else "INSUFFICIENT")})
    if set(sa) != {row["item"] for row in decisions}:
        raise ValueError("SA and Jev probe slab universes differ")
    payload = {"schema": "jev_prod_laj_level_crosscheck/1",
               "sa_state_sha256": hashlib.sha256(args.state.read_bytes()).hexdigest(),
               "source_dxf_sha256": hashlib.sha256(args.dxf.read_bytes()).hexdigest(),
               "authority": "read-only QA; SA state is baseline, not ground truth",
               "summary": dict(Counter(row["decision"] for row in decisions)),
               "jev_rule_same_handle": sum(row["jev_rule_same_handle"] for row in decisions),
               "results": decisions}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
