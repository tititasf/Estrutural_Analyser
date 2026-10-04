"""Jev second-opinion on LV orientation disagreements, using raw DXF only."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--matched-controls", nargs="*", default=["V401", "V403", "V409"])
    args = ap.parse_args()
    import ezdxf
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    audit = json.loads(args.audit.read_text(encoding="utf-8-sig"))
    targets = [row for row in audit["results"] if row["item"].startswith("V") and not row["item"].startswith("VF")
               and row["label_vs_lv_disagree"]]
    controls = [row for row in audit["results"] if row["item"] in args.matched_controls]
    lines = [e for e in ezdxf.readfile(str(args.dxf)).modelspace() if e.dxftype() == "LINE"]
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for row in targets + controls:
            label = row["label"]
            if not label:
                continue
            nearby = []
            for e in lines:
                mx = (float(e.dxf.start.x)+float(e.dxf.end.x))/2
                my = (float(e.dxf.start.y)+float(e.dxf.end.y))/2
                dist = math.hypot(mx-label["x"], my-label["y"])
                if dist > 100:
                    continue
                dx = float(e.dxf.end.x-e.dxf.start.x)
                dy = float(e.dxf.end.y-e.dxf.start.y)
                length = math.hypot(dx, dy)
                if length < 12:
                    continue
                nearby.append({"handle": e.dxf.handle, "layer": e.dxf.layer,
                               "midpoint_dx": round(mx-label["x"], 1),
                               "midpoint_dy": round(my-label["y"], 1),
                               "line_dx": round(dx, 1), "line_dy": round(dy, 1),
                               "length": round(length, 1), "distance": round(dist, 1)})
            nearby.sort(key=lambda x: (x["distance"], -x["length"]))
            nearby = nearby[:16]
            conditions = ["full", "label_only", "linework_only"]
            if row["item"] in ("V402", "V411", "V420"):
                conditions.append("evidence_removed")
            for condition in conditions:
                state = {"beam_name": row["item"],
                         "raw_label": {"handle": label["handle"], "rotation_deg": label["rotation"]} if condition in ("full", "label_only") else None,
                         "nearby_dxf_lines": nearby if condition in ("full", "linework_only") else [],
                         "evidence_condition": condition}
                instruction = ("Determine the main axis of the named beam in the raw structural DXF: H horizontal or V vertical. "
                               "If only label rotation is supplied, interpret its orientation. If only linework is supplied, "
                               "it may contain crossing beams; abstain when it cannot be uniquely attributed. "
                               "When both are supplied, reconcile them. If evidence is missing or conflicting, choose INSUFFICIENT. "
                               "Do not use any SA orientation flag.")
                q = Choice(instructions=instruction,
                           criteria={"H": "The named beam runs horizontally in the original drawing.",
                                     "V": "The named beam runs vertically in the original drawing.",
                                     "INSUFFICIENT": "Source evidence does not determine one beam axis."})
                started = time.perf_counter()
                response = client.system_one(state=state, questions={"beam_axis": q})
                answer = response.choices["beam_axis"]
                results.append({"item": row["item"], "condition": condition,
                                "choice": answer.choice, "confidence": answer.confidence,
                                "raw_label_axis": row["raw_label_axis"],
                                "n1_beam_axis": row["n1_beam_axis"], "n1_lv_axis": row["n1_lv_axis"],
                                "raw_line_candidates": len(nearby),
                                "input_tokens": response.usage.input_tokens if response.usage else None,
                                "latency_s": round(time.perf_counter()-started, 3)})
    payload = {"schema": "jev_lv_orientation_jev_probe/1", "project_id": audit["project_id"],
               "target_rule": "regular-V raw-label-vs-N1-LV disagreements plus matched controls",
               "results": results,
               "warning": "axis agreement is a triage signal, not validation of four LV panels or support links"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"full_calls": sum(x["condition"] == "full" for x in results),
                      "full_agree_raw_label": sum(x["condition"] == "full" and x["choice"] == x["raw_label_axis"] for x in results),
                      "full_disagree_n1_lv": sum(x["condition"] == "full" and x["choice"] != x["n1_lv_axis"] for x in results),
                      "negative_abstain": sum(x["condition"] == "evidence_removed" and x["choice"] == "INSUFFICIENT" for x in results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
