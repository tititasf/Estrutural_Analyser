"""Read-only evidence fusion for the 14_PAV Jev/SA/visual research pilot.

Consumes frozen pilot reports. It never writes to N1. A candidate is only a
proposal: visual spot checks do not approve a complete pillar or class item.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fuse_pillar(row: dict, visual_review: dict[str, dict]) -> dict:
    target = row["item"]
    reference = row["reference_from_polygon_cad_units"]
    geom_handle = row["deterministic_geometry"]
    jev = row["jev"]
    json_handle = jev["json"].get("selected_handle")
    variants = {arm: jev.get(arm, {}).get("selected_handle") for arm in ("json", "svg", "svg-json")}
    output = {
        "class": "PIL", "item": target, "field": "dim", "n1_value": row["n1_dim_text"],
        "cad_polygon_sides": reference, "candidate_handles": variants,
        "geometry_compatible_handle": geom_handle,
        "source": "same original structural DXF, with distinct representations",
        "visual_review": visual_review.get(target),
    }
    if geom_handle is None:
        output["decision"] = "no_proposal_missing_compatible_cad_text"
        output["reason"] = "geometry gate found no compatible section text; Jev choice cannot override this absence"
        output["rejected_jev_handle"] = json_handle
        return output
    if json_handle != geom_handle:
        output["decision"] = "review_jev_vs_geometry_conflict"
        output["reason"] = "DXF-to-JSON Jev and geometric gate disagree"
        return output
    candidate = next((c for c in row["candidates"] if c["id"] == geom_handle), None)
    if candidate is None:
        output["decision"] = "review_missing_provenance"
        return output
    output["proposal"] = {"value": candidate["text"], "source_handle": geom_handle}
    divergent = [arm for arm in ("svg", "svg-json") if variants[arm] != geom_handle]
    output["representation_disagreements"] = divergent
    if divergent and target not in visual_review:
        output["decision"] = "proposal_needs_visual_review"
    elif target in visual_review:
        output["decision"] = "proposal_visual_spot_checked"
    else:
        output["decision"] = "proposal_needs_item_review"
    output["reason"] = "geometry and DXF-to-JSON Jev agree; no production approval implied"
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.report_dir
    pillars = read(root / "pil_33_all.json")
    negatives = read(root / "pil_negative_10.json")
    slabs = read(root / "laj_22.json")
    beams = read(root / "beam_37.json")
    special_detail = read(root / "hybrid_special_detail_2.json")
    special_geometry = read(root / "hybrid_special_geometry.json")
    duplicate_slab = read(root / "hybrid_l409_duplicate.json")
    slab_levels = read(root / "hybrid_laj_level_22.json")
    fv_scope = read(root / "hybrid_fv_scope_audit.json")
    levels_by_item = {row["item"]: row for row in slab_levels["results"]}
    qa_by_item: dict[tuple[str, str], dict] = {}
    for line in (root / "qa_baseline" / "decisoes.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = (row["classe"], row["item"])
        record = qa_by_item.setdefault(key, {"class": key[0], "item": key[1], "counts": Counter(),
                                              "unresolved_fields": set()})
        record["counts"][row["decision"]] += 1
        if row["decision"] in {"PENDENTE", "REVISAR_HUMANO"}:
            record["unresolved_fields"].add(row["field_id"])

    # These two observations are from full-layer structural-DXF PNGs inspected
    # visually in the pilot, with the semantic SVG also rendered to pixels.
    visual = {
        "P18": {"scope": "dimension text only", "observed": "19/79",
                "structural_dxf_png": "P18_source_dxf.png", "jev_svg_png": "P18_jev_semantic.png"},
        "P48": {"scope": "dimension text only", "observed": "50/19",
                "structural_dxf_png": "P48_source_dxf.png", "jev_svg_png": "P48_jev_semantic.png"},
    }
    pil = [fuse_pillar(row, visual) for row in pillars["items"]]
    if len({r["item"] for r in pil}) != len(pil):
        raise ValueError("multiple rectangular pillar rows with same item; identity must be resolved first")
    full_detail = next(r for r in special_detail["results"] if r["control"] == "full")
    missing_detail = next(r for r in special_detail["results"] if r["control"] == "title_removed")
    if not full_detail["accepted_by_explicit_title_gate"] or missing_detail["accepted_by_explicit_title_gate"]:
        raise ValueError("special-detail positive/negative evidence gate failed")
    for name in ("P26", "P27"):
        geometry_choice = next(r for r in special_geometry["results"]
                               if r["condition"] == "full" and r["item"] == name)
        geometry_negative = next(r for r in special_geometry["results"]
                                 if r["condition"] == "dimensions_removed" and r["item"] == name)
        if not geometry_choice["accepted_by_detail_dimension_gate"] or geometry_negative["choice"] != "INSUFFICIENT":
            raise ValueError(f"special geometry evidence gate failed for {name}")
        remaining = [r["row_id"] for r in special_geometry["n1_candidates"]
                     if r["name"] == name and r["row_id"] != geometry_choice["choice"]]
        pil.append({"class": "PIL", "item": name, "field": "special_detail_link",
                    "decision": "detail_geometry_candidate_needs_full_item_review",
                    "detail_title_handle": full_detail["jev_choice"], "detail_title": "P26=P27",
                    "matched_n1_geometry_row_id": geometry_choice["choice"],
                    "unresolved_same_name_n1_row_ids": remaining,
                    "detail_bbox_sides": [165.0, 218.0],
                    "visual_source_png": "hybrid_visual/P26_P27_detail_full.png",
                    "reason": "overview says VER DET.; Jev linked shared title and matched the 165x218 detail to one N1 polygon; other same-name geometry and full relations still need review"})
    pil.sort(key=lambda r: r["item"])

    negatives_out = []
    for row in negatives["items"]:
        outcome = fuse_pillar(row, {})
        if outcome["decision"] != "no_proposal_missing_compatible_cad_text":
            raise ValueError(f"negative case received proposal: {row['item']}")
        negatives_out.append(outcome)

    laj = []
    for row in slabs["results"]:
        result = {"class": "LAJ", "item": row["item"], "field": "laje_dim",
                  "n1_value": row.get("n1_text")}
        if row.get("skip"):
            if row["item"] == "L409":
                full = next(x for x in duplicate_slab["results"] if x["condition"] == "full")
                absent = next(x for x in duplicate_slab["results"] if x["condition"] == "polygon_removed")
                if not full["accepted_by_polygon_containment_gate"] or absent["choice"] != "INSUFFICIENT":
                    raise ValueError("L409 duplicate-label controls failed")
                result.update({"decision": "label_instance_resolved_full_slab_review_pending",
                               "matched_raw_label_handle": full["choice"],
                               "reason": "one of two L409 DXF labels lies within N1 polygon; other slab fields remain unapproved"})
            else:
                result.update({"decision": "review_duplicate_source_label", "reason": row["skip"]})
        else:
            svg = row["jev"]["svg-json"]
            direct = row["jev"]["json"]
            result.update({"candidate_svg_json": svg.get("text"), "candidate_json": direct.get("text"),
                           "nearest_source_handle": row["nearest_handle"],
                           "decision": "preserve_n1_with_format_disagreement" if direct.get("text") != svg.get("text")
                                       else "preserve_n1_consensus",
                           "reason": "text agreement is not a full slab or support approval"})
        laj.append(result)

    level_decisions = []
    for item, level in sorted(levels_by_item.items()):
        inside = sorted((candidate for candidate in level["candidates"]
                         if candidate["inside_n1_polygon"]), key=lambda candidate: candidate["distance"])
        choice = level["jev"]["full"]["choice"]
        rule = inside[0]["handle"] if inside else "INSUFFICIENT"
        if choice != rule:
            decision = "level_jev_geometry_disagreement_review"
        elif choice == "INSUFFICIENT":
            decision = "level_evidence_missing"
        else:
            decision = "level_candidate_needs_visual_review"
        selected = next((candidate for candidate in inside if candidate["handle"] == choice), None)
        level_decisions.append({"class": "LAJ", "item": item, "field": "laje_nivel",
                                "n1_value": None, "decision": decision,
                                "candidate": {"text": selected["text"], "source_handle": choice} if selected else None,
                                "cad_nearest_inside_handle": rule,
                                "inside_candidate_count": len(inside),
                                "reason": "Jev and nearest-within-N1-polygon rule agree; independent full-item evidence and human visual review still required" if selected else "no 855.xx source text within N1 polygon"})

    beam = []
    for row in beams["results"]:
        beam.append({"class": "FV_LV_SHARED_SOURCE", "item": row["item"], "field": "section_near_label",
                     "n1_value": row["n1_dim"], "jev_value": row.get("jev", {}).get("text"),
                     "decision": "preserve_n1_research_segment_topology",
                     "reason": row.get("skip") or "Jev abstained; nearby label cannot decide all segments or lateral contracts"})

    fv_scope_decisions = []
    for row in fv_scope["results"]:
        if not row["repeated_same_claim_across_segments"]:
            continue
        fv_scope_decisions.append({"class": "FV", "item": row["item"], "field": "abertura_especial_scope",
                                   "decision": "scope_review_required", "segment_count": row["segment_count"],
                                   "claimed_counts": [s["claimed_count"] for s in row["segments"]],
                                   "local_polygon_contact_counts": [len(s["n1_pillar_polygon_contacts_0_05"]) for s in row["segments"]],
                                   "reason": "same opening/interference count repeated on each segment; only per-segment source geometry and visual review can classify the scope"})

    decisions = pil + laj + level_decisions + beam + fv_scope_decisions
    qa_queue = []
    for record in qa_by_item.values():
        unresolved = sorted(record["unresolved_fields"])
        if not unresolved:
            continue
        family = "identity_geometry" if record["class"] == "PIL" else (
            "support_level_boundary" if record["class"] == "LAJ" else
            "segment_support_opening" if record["class"] == "FV" else "lateral_contract")
        qa_queue.append({"class": record["class"], "item": record["item"],
                         "family_to_investigate": family,
                         "unresolved_field_ids": unresolved,
                         "unresolved_field_count": len(unresolved),
                         "qa_decision_counts": dict(record["counts"]),
                         "next_evidence": "full-layer original-DXF PNG + CAD entities/handles for one field or segment; Jev Choice only after candidate validation"})
    qa_queue.sort(key=lambda r: (-r["unresolved_field_count"], r["class"], r["item"]))
    summary = {"pillar_unique": len(pil), "pillar_proposals": sum(r["decision"].startswith("proposal_") for r in pil),
               "pillar_visual_spot_checks": sum(r["decision"] == "proposal_visual_spot_checked" for r in pil),
               "negative_rejections": len(negatives_out), "slabs": len(laj), "beams": len(beam),
               "slab_level_candidates": sum(r["decision"] == "level_candidate_needs_visual_review" for r in level_decisions),
               "slab_level_missing_evidence": sum(r["decision"] == "level_evidence_missing" for r in level_decisions),
               "fv_scope_reviews": len(fv_scope_decisions),
               "decisions": dict(Counter(r["decision"] for r in decisions)),
               "qa_items_needing_evidence": len(qa_queue),
               "qa_queue_by_class": dict(Counter(r["class"] for r in qa_queue))}
    payload = {"schema": "jev_sa_vision_fusion_pilot/1", "project_id": pillars["project_id"],
               "dxf_sha256": pillars["dxf_sha256"],
               "authority": "research sidecar only; no full-item approval or DB writes",
               "summary": summary, "fields": decisions, "negative_controls": negatives_out,
               "qa_review_queue": qa_queue}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
