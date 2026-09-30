"""Read-only dynamic Jev/SA/CAD/vision routing from frozen VPS pilot evidence.

This is a shadow-mode routing prototype. It never promotes a model choice to N1.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = args.report_dir
    pil = read(root / "pil_31_jev.json")
    pil_negative = read(root / "pil_negative_10_jev.json")
    laj = read(root / "laj_level_crosscheck.json")
    lv = read(root / "lv_orientation_audit_vps.json")
    lv_jev = read(root / "lv_orientation_jev_probe.json")
    lv_cells = read(root / "lv_cell_geometry_audit_vps.json")
    fv = read(root / "fv_scope_audit_vps.json")
    fv_jev = read(root / "fv_scope_jev_probe.json")
    if not all(row["deterministic_geometry"] == row["jev"]["json"]["selected_handle"]
               and row["n1_correct"] for row in pil["items"]):
        raise ValueError("PIL consensus precondition changed")
    if any(row["jev"]["json"]["selected_handle"] is None for row in pil_negative["items"]):
        raise ValueError("PIL negative behavior changed; re-evaluate gate")

    queue = []
    for row in laj["results"]:
        if row["decision"] == "direct_marker_vs_sa_conflict":
            queue.append({"class": "LAJ", "item": row["item"], "field": "laje_nivel",
                          "route": "JEV_SECOND_OPINION_THEN_VISUAL",
                          "evidence": "two direct DXF elevation handles + nearby h= texts + full-layer PNG",
                          "sa_value": row["sa_state_level"],
                          "cad_direct_value": row["cad_nearest_inside"]["text"],
                          "jev_value": row["jev_choice"]["text"] if row["jev_choice"] else None,
                          "approval": "human review of physical region/step required"})
        elif row["decision"] in {"sa_level_without_contained_marker", "no_direct_marker_and_sa_empty"}:
            queue.append({"class": "LAJ", "item": row["item"], "field": "laje_nivel",
                          "route": "EXPAND_SOURCE_BEFORE_JEV",
                          "evidence": "cut view, named neighboring slab and original level convention",
                          "sa_value": row["sa_state_level"],
                          "approval": "no level inference from proximity alone"})
    lv_jev_by_item = {row["item"]: row for row in lv_jev["results"] if row["condition"] == "full"}
    lv_cell_by_item = {row["item"]: row for row in lv_cells["results"]}
    queued_lv = set()
    for row in lv["results"]:
        if not row["item"].startswith("V") or row["item"].startswith("VF") or not row["label_vs_lv_disagree"]:
            continue
        query = lv_jev_by_item.get(row["item"])
        cell_audit = lv_cell_by_item.get(row["item"], {})
        remote_cells = cell_audit.get("remote_cells", 0)
        queue.append({"class": "LV", "item": row["item"], "field": "lv_is_h",
                      "route": "CELL_GEOMETRY_REVIEW" if remote_cells else "CAD_LABEL_AND_VISUAL_REVIEW",
                      "evidence": "raw DXF label rotation, full-layer beam axis, four local LV cells",
                      "raw_label_axis": row["raw_label_axis"], "n1_lv_axis": row["n1_lv_axis"],
                      "jev_axis": query["choice"] if query else None,
                      "remote_lv_para_cells": remote_cells,
                      "approval": "do not replace panels or supports from orientation flag alone"})
        queued_lv.add(row["item"])
    for row in lv_cells["results"]:
        if row["remote_cells"] and row["item"] not in queued_lv:
            queue.append({"class": "LV", "item": row["item"], "field": "lv_segment_attribution",
                          "route": "CELL_GEOMETRY_REVIEW", "remote_lv_para_cells": row["remote_cells"],
                          "evidence": "LV Para A/B segment coordinates versus own FV footprints",
                          "approval": "inspect four contracts and raw source before correcting attribution"})
    fv_jev_by_item = {}
    for row in fv_jev["results"]:
        fv_jev_by_item.setdefault(row["item"], []).append(row)
    for row in fv["results"]:
        if not row["repeated_same_claim_across_segments"]:
            continue
        probes = fv_jev_by_item.get(row["item"], [])
        queue.append({"class": "FV", "item": row["item"], "field": "abertura_especial_scope",
                      "route": "SEGMENT_SOURCE_EXPANSION",
                      "segment_count": row["segment_count"],
                      "jev_local_evidence_insufficient": sum(x["choice"] == "INSUFFICIENT_LOCAL_EVIDENCE" for x in probes),
                      "evidence": "opening contour/source handle and local endpoint evidence for each segment",
                      "approval": "no per-segment opening count from repeated beam-wide text"})
    payload = {"schema": "jev_sa_dynamic_router/1", "mode": "shadow_read_only",
               "project_id": lv["project_id"],
               "policy": "SA remains baseline; CAD/visual gates constrain Jev; no automatic N1 write",
               "summary": {"pil_simple_no_query": len(pil["items"]),
                           "queued": len(queue),
                           "by_route": dict(Counter(row["route"] for row in queue)),
                           "by_class": dict(Counter(row["class"] for row in queue))},
               "queue": queue}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
