"""Jev QA gate for per-segment FV opening claims lacking local provenance."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    audit = json.loads(args.audit.read_text(encoding="utf-8-sig"))
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for beam in audit["results"]:
            if not beam["repeated_same_claim_across_segments"]:
                continue
            for segment in beam["segments"]:
                state = {"beam": beam["item"], "target_fv_segment": segment["index"],
                         "target_ficha_statement": segment["statement"],
                         "pillar_polygons_touching_target": segment["n1_pillar_polygon_contacts_0_05"],
                         "all_segment_claim_counts": [s["claimed_count"] for s in beam["segments"]],
                         "global_beam_opening_pillar_names": beam["global_links_aberturas_pilar_unique_names"],
                         "segment_local_opening_source_handles": [],
                         "note": "polygon contact alone does not prove a local opening"}
                q = Choice(instructions="Can the stated number of pillar interferences/openings be approved specifically for this FV segment from the supplied evidence? Beam-wide context, repeated text and mere polygon contact do not establish a local opening. Choose INSUFFICIENT_LOCAL_EVIDENCE when segment-specific opening geometry/provenance is absent. Do not decide whether the physical opening exists.",
                           criteria={"LOCAL_EVIDENCE_SUFFICIENT": "The exact count is supported by segment-specific source opening entities.",
                                     "INSUFFICIENT_LOCAL_EVIDENCE": "The supplied evidence cannot verify this segment's opening count."})
                started = time.perf_counter()
                response = client.system_one(state=state, questions={"local_fv_opening_evidence": q})
                answer = response.choices["local_fv_opening_evidence"]
                results.append({"item": beam["item"], "segment": segment["index"],
                                "choice": answer.choice, "confidence": answer.confidence,
                                "input_tokens": response.usage.input_tokens if response.usage else None,
                                "latency_s": round(time.perf_counter()-started, 3)})
    payload = {"schema": "jev_fv_scope_jev_probe/1", "project_id": audit["project_id"],
               "results": results,
               "warning": "abstention validates an evidence gate only; it does not validate FV geometry or absence of opening"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"segments": len(results),
                      "insufficient": sum(r["choice"] == "INSUFFICIENT_LOCAL_EVIDENCE" for r in results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
