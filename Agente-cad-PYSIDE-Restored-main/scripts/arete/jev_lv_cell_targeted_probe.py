"""Targeted Jev cross-check on LV cell attribution, with a no-geometry control."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    audit = json.loads(args.audit.read_text(encoding="utf-8-sig"))
    fv_by_name = {}
    for row in state["segmentos"]["fundo"]:
        fv_by_name.setdefault(row["beam_name"], []).append(row["points"])
    cells = {row["item"]: row["cells"] for row in audit["results"]}
    trials = [("V420", "lateral_b_para", "5", "full"),
              ("V419", "lateral_a_para", "2", "full"),
              ("V411", "lateral_a_para", "1", "full"),
              ("V420", "lateral_b_para", "5", "geometry_removed")]
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for beam, kind, segment, condition in trials:
            cell = next(c for c in cells[beam] if c["kind"] == kind and c["segment_label"] == segment)
            evidence = {"beam_name": beam, "lv_cell": kind + ":" + segment,
                        "source_condition": condition,
                        "lv_points": cell["points"] if condition == "full" else None,
                        "own_fv_polygons": fv_by_name[beam] if condition == "full" else None}
            question = Choice(
                instructions="Do these LV cell coordinates follow the named beam's OWN FV polygons? "
                             "Use only the coordinates supplied. A distant cell belongs to REMOTE, "
                             "even if its line crosses a polygon at one endpoint. "
                             "Choose INSUFFICIENT when coordinates are absent. Do not infer engineering correctness.",
                criteria={"MATCHES_OWN_FV": "Cell lies along its own named beam's FV footprint.",
                          "REMOTE_FROM_OWN_FV": "Most of the cell is clearly remote from all of its own beam's FV polygons.",
                          "INSUFFICIENT": "Supplied coordinates do not determine attribution."})
            reply = client.system_one(state=evidence, questions={"cell_attribution": question})
            answer = reply.choices["cell_attribution"]
            results.append({"beam": beam, "kind": kind, "segment": segment,
                            "condition": condition, "jev_choice": answer.choice,
                            "jev_confidence": answer.confidence,
                            "cad_distance_cm": cell["distance_to_own_fv_cm"],
                            "cad_outside_30cm_fraction": cell["outside_30cm_fraction"],
                            "input_tokens": reply.usage.input_tokens if reply.usage else None})
    payload = {"schema": "jev_lv_cell_targeted_probe/1", "results": results,
               "caution": "Jev is a second check; deterministic geometry and raw DXF decide attribution."}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
