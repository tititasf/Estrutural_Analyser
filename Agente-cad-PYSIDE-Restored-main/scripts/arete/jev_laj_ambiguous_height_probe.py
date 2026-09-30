"""Targeted Jev counterfactual for an ambiguous slab-level association.

Uses only raw DXF text and a production SA polygon as a candidate region. It
never sends the SA level value to Jev or edits the SA. The target marker is
removed in one control while a competing inside-polygon marker remains.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--item", default="L410")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    import ezdxf
    from dotenv import load_dotenv
    from shapely.geometry import Point, Polygon
    from typesafe_sdk import Choice, TypeSafeClient

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    sa = json.loads(args.state.read_text(encoding="utf-8"))
    slab = next(row for row in sa["slabs"] if row["name"] == args.item)
    polygon = Polygon(slab["points"])
    texts = []
    for e in ezdxf.readfile(str(args.dxf)).modelspace():
        if e.dxftype() == "TEXT":
            texts.append({"handle": e.dxf.handle, "text": str(e.dxf.text).strip(),
                          "x": float(e.dxf.insert.x), "y": float(e.dxf.insert.y)})
    labels = [t for t in texts if t["text"] == args.item and polygon.covers(Point(t["x"], t["y"]))]
    if len(labels) != 1:
        raise ValueError("target label is not unique inside its SA polygon")
    label = labels[0]
    near = lambda t: math.hypot(t["x"]-label["x"], t["y"]-label["y"])
    heights = [t for t in texts if re.fullmatch(r"h\s*=\s*\d+", t["text"], re.I) and near(t) <= 270]
    target_height = min(heights, key=near)
    if near(target_height) > 40:
        raise ValueError("no locally associated h= text for target slab")
    levels = [t for t in texts if re.fullmatch(r"85\d[.,]\d{1,2}", t["text"]) and
              polygon.covers(Point(t["x"], t["y"])) and near(t) <= 270]
    levels.sort(key=near)
    if len(levels) != 2 or levels[0]["text"] == levels[1]["text"]:
        raise ValueError("this probe requires two inside-polygon level texts with distinct values")
    def candidate(t: dict, include_heights: bool) -> dict:
        adjacent = sorted((h for h in heights if math.hypot(t["x"]-h["x"], t["y"]-h["y"]) <= 60),
                          key=lambda h: math.hypot(t["x"]-h["x"], t["y"]-h["y"]))
        row = {"handle": t["handle"], "text": t["text"],
               "dx_from_target_label": round(t["x"]-label["x"], 2),
               "dy_from_target_label": round(t["y"]-label["y"], 2),
               "inside_sa_polygon": True}
        if include_heights:
            row["nearby_h_annotations"] = [{"handle": h["handle"], "text": h["text"],
                                               "distance": round(math.hypot(t["x"]-h["x"], t["y"]-h["y"]), 2)}
                                              for h in adjacent]
        return row
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for condition in ("minimal_full", "minimal_target_marker_removed",
                          "height_context_full", "height_context_target_marker_removed"):
            enriched = condition.startswith("height_context")
            active = levels[1:] if condition.endswith("removed") else levels
            matching_h = [t for t in active if any(h["text"] == target_height["text"] and
                          math.hypot(t["x"]-h["x"], t["y"]-h["y"]) <= 60 for h in heights)]
            options = {t["handle"]: f"DXF elevation {t['text']}" for t in active}
            options["INSUFFICIENT"] = "No supplied marker is sufficiently associated with the named slab."
            context = {"target_slab": args.item, "target_label_handle": label["handle"],
                       "candidate_elevations": [candidate(t, enriched) for t in active],
                       "polygon_bbox": [round(v, 2) for v in polygon.bounds]}
            if enriched:
                context["target_height_annotation"] = {"handle": target_height["handle"],
                                                       "text": target_height["text"],
                                                       "dx": round(target_height["x"]-label["x"], 2),
                                                       "dy": round(target_height["y"]-label["y"], 2)}
            instructions = ("Identify the original DXF elevation marker belonging to the named slab. "
                            "Nearby markers may belong to a neighboring region. If the supplied "
                            "evidence does not safely establish ownership, return INSUFFICIENT. "
                            "Do not invent a level.")
            question = Choice(instructions=instructions, criteria=options)
            started = time.perf_counter()
            response = client.system_one(state=context, questions={"source_level_marker": question})
            answer = response.choices["source_level_marker"]
            chosen = next((t for t in active if t["handle"] == answer.choice), None)
            results.append({"condition": condition, "choice": answer.choice,
                            "text": chosen["text"] if chosen else None,
                            "confidence": answer.confidence,
                            "input_tokens": response.usage.input_tokens if response.usage else None,
                            "latency_s": round(time.perf_counter()-started, 3),
                            "cad_nearest_available": active[0]["handle"] if active else None,
                            "cad_matching_h_gate": matching_h[0]["handle"] if len(matching_h) == 1 else None})
    payload = {"schema": "jev_laj_ambiguous_height_probe/1", "item": args.item,
               "source_dxf_sha256": hashlib.sha256(args.dxf.read_bytes()).hexdigest(),
               "target_label_handle": label["handle"], "target_height": target_height,
               "source_candidates": [candidate(t, True) for t in levels],
               "sa_level_withheld_from_jev": slab.get("nivel"),
               "results": results,
               "warning": "counterfactual outcome is not independent ground truth"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
