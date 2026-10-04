"""Small Jev ablation on ambiguous 14_PAV slab elevation candidates."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    by_item = {r["item"]: r for r in json.loads(args.source.read_text(encoding="utf-8"))["results"]}
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for item in ("L401", "L410"):
            row = by_item[item]
            for condition in ("full_reversed", "polygon_withheld"):
                candidates = list(reversed(row["candidates"]))
                if condition == "polygon_withheld":
                    candidates = [{key: value for key, value in candidate.items()
                                   if key != "inside_n1_polygon"} for candidate in candidates]
                state = {"target_slab": item, "label_handle": row["label_handle"],
                         "candidates": candidates,
                         "polygon_bbox_dxf": row["polygon_bbox"] if condition == "full_reversed" else None,
                         "condition": condition}
                options = {candidate["handle"]: candidate["text"] for candidate in candidates}
                options["INSUFFICIENT"] = "The supplied evidence does not assign a level to this slab."
                question = Choice(instructions="Select a raw elevation TEXT handle for the target slab only if geometric ownership is established. A nearest text by itself is not sufficient. If the polygon is missing or ownership is ambiguous, choose INSUFFICIENT.", criteria=options)
                start = time.perf_counter()
                response = client.system_one(state=state, questions={"level": question})
                answer = response.choices["level"]
                results.append({"item": item, "condition": condition, "choice": answer.choice,
                                "confidence": answer.confidence,
                                "input_tokens": response.usage.input_tokens if response.usage else None,
                                "latency_s": round(time.perf_counter()-start, 3)})
    payload = {"schema": "jev_laj_level_stability_pilot/1", "source": str(args.source), "results": results,
               "warning": "This probes output stability only; it is not a validated slab-level reference."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
