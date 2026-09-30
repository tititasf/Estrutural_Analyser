"""Pilot for a shared detail resolving ambiguous special-pillar N1 rows.

CAD code calculates polygon envelopes; Jev only selects among row IDs.
The detail dimensions are source TEXT handles, not N1-derived values.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--detail-dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    import ezdxf
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")

    doc = ezdxf.readfile(str(args.detail_dxf))
    wanted = {"165", "218"}
    source_dims = []
    for e in doc.modelspace():
        if e.dxftype() == "TEXT" and str(e.dxf.text).strip() in wanted:
            x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
            if 5700 <= x <= 6700 and 2700 <= y <= 3900:
                source_dims.append({"text": str(e.dxf.text).strip(), "handle": e.dxf.handle})
    if {d["text"] for d in source_dims} != wanted:
        raise ValueError("detail 165x218 texts were not uniquely localized")
    conn = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        n1_rows = conn.execute("SELECT id,name,points_json FROM pillars WHERE project_id=? AND name IN ('P26','P27') ORDER BY name,id",
                               (args.project_id,)).fetchall()
    finally:
        conn.close()
    candidates = []
    for id, name, serialized in n1_rows:
        points = json.loads(serialized or "[]")
        xy = [(float(p[0]), float(p[1])) for p in points]
        if not xy:
            continue
        width = round(max(x for x, _ in xy) - min(x for x, _ in xy), 3)
        height = round(max(y for _, y in xy) - min(y for _, y in xy), 3)
        candidates.append({"row_id": id, "name": name, "bbox_sides": sorted([width, height]),
                           "polygon_vertices": len(xy)-int(xy[0] == xy[-1])})
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for condition in ("full", "dimensions_removed"):
            for name in ("P26", "P27"):
                options = {r["row_id"]: f"N1 {name} polygon with bbox sides {r['bbox_sides']}" for r in candidates if r["name"] == name}
                options["INSUFFICIENT"] = "The supplied detail cannot identify one row."
                state = {"target": name,
                         "shared_detail_title": {"handle": "67A", "text": "P26=P27"},
                         "detail_external_dimensions": source_dims if condition == "full" else [],
                         "persisted_n1_geometry_candidates": [r for r in candidates if r["name"] == name],
                         "condition": condition}
                q = Choice(instructions="Which N1 polygon row corresponds to the shared detail external dimensions? Treat the detail dimensions as required evidence. Select INSUFFICIENT if those dimensions are absent or no candidate matches both external sides. Do not infer from the title alone.", criteria=options)
                t0 = time.perf_counter()
                response = client.system_one(state=state, questions={"matching_polygon_row": q})
                answer = response.choices["matching_polygon_row"]
                gate = next((r for r in candidates if r["row_id"] == answer.choice and
                             r["name"] == name and r["bbox_sides"] == [165.0, 218.0]), None)
                accepted = bool(source_dims and condition == "full" and gate)
                results.append({"condition": condition, "item": name, "choice": answer.choice,
                                "accepted_by_detail_dimension_gate": accepted,
                                "confidence": answer.confidence,
                                "input_tokens": response.usage.input_tokens if response.usage else None,
                                "latency_s": round(time.perf_counter()-t0, 3)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "jev_special_geometry_pilot/1", "detail_source_dimensions": source_dims,
                                       "n1_candidates": candidates, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"condition": r["condition"], "item": r["item"], "choice": r["choice"],
                       "accepted": r["accepted_by_detail_dimension_gate"]} for r in results]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
