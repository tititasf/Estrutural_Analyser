"""Resolve two raw L409 labels against one N1 slab polygon, without trusting N1 text position."""
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
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    import ezdxf
    from shapely.geometry import Point, Polygon
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    conn = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id,points_json FROM slabs WHERE project_id=? AND name='L409'", (args.project_id,)).fetchall()
    finally:
        conn.close()
    if len(rows) != 1:
        raise ValueError("expected one N1 L409 polygon")
    polygon = Polygon(json.loads(rows[0][1]))
    if not polygon.is_valid:
        raise ValueError("invalid N1 slab polygon")
    raw = []
    for e in ezdxf.readfile(str(args.dxf)).modelspace():
        if e.dxftype() == "TEXT" and str(e.dxf.text).strip() == "L409":
            x,y = float(e.dxf.insert.x), float(e.dxf.insert.y)
            raw.append({"handle": e.dxf.handle, "text": "L409", "x": round(x,3), "y": round(y,3),
                        "inside_n1_polygon": bool(polygon.covers(Point(x,y)))})
    if len(raw) != 2:
        raise ValueError(f"expected two raw L409 labels, got {len(raw)}")
    bounds = [round(v,3) for v in polygon.bounds]
    choices = {r["handle"]: f"Raw DXF L409 text at ({r['x']}, {r['y']})" for r in raw}
    choices["INSUFFICIENT"] = "The supplied evidence does not identify one text instance."
    results = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for condition in ("full", "polygon_removed"):
            state = {"target": "one persisted L409 polygon", "n1_polygon_bbox": bounds if condition == "full" else None,
                     "raw_dxf_label_candidates": [{k:v for k,v in row.items() if k!='inside_n1_polygon'} for row in raw],
                     "condition": condition}
            q = Choice(instructions="Choose the raw DXF L409 label instance that lies in the supplied N1 polygon bounding box. If the box is absent, choose INSUFFICIENT. Never choose from label text alone because both labels read L409.", criteria=choices)
            t0 = time.perf_counter()
            response = client.system_one(state=state, questions={"matching_label": q})
            answer = response.choices["matching_label"]
            accepted = condition == "full" and any(row["handle"] == answer.choice and row["inside_n1_polygon"] for row in raw)
            results.append({"condition": condition, "choice": answer.choice,
                            "accepted_by_polygon_containment_gate": accepted,
                            "confidence": answer.confidence,
                            "input_tokens": response.usage.input_tokens if response.usage else None,
                            "latency_s": round(time.perf_counter()-t0,3)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "jev_duplicate_slab_label_pilot/1", "n1_polygon_bbox": bounds,
                                       "raw_labels": raw, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
