"""Read-only raw-DXF beam-label/section association probe for FV/LV evidence.

The same beam records feed distinct FV and LV contracts. A nearby section text
does not establish the full beam dimension; N1 agreement is diagnostic only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import time
from pathlib import Path

from jev_pil_dim_pilot import DB, DXF, PROJECT_ID, ROOT

DIM = re.compile(r"^\d{1,3}(?:[.,]\d+)?\s*[/xX×]\s*\d{1,3}(?:[.,]\d+)?$")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--project-id", default=PROJECT_ID)
    ap.add_argument("--dxf", type=Path, default=DXF)
    args = ap.parse_args()
    project_id, dxf = args.project_id, args.dxf.resolve()
    if not dxf.exists():
        ap.error("DXF not found")
    import ezdxf
    from dotenv import load_dotenv
    from typesafe_sdk import TypeSafeClient, Choice
    load_dotenv(ROOT / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    try:
        beams = con.execute("SELECT name,data_json FROM beams WHERE project_id=? ORDER BY name", (project_id,)).fetchall()
    finally:
        con.close()
    doc = ezdxf.readfile(str(dxf))
    texts = []
    for entity in doc.modelspace():
        if entity.dxftype() == "TEXT":
            try:
                texts.append({"id": entity.dxf.handle, "text": str(entity.dxf.text).strip(),
                              "layer": entity.dxf.layer, "x": float(entity.dxf.insert.x),
                              "y": float(entity.dxf.insert.y)})
            except (AttributeError, ValueError, TypeError):
                pass
    rows = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for name, data in beams:
            labels = [t for t in texts if t["text"] == name]
            result = {"item": name, "raw_label_count": len(labels),
                      "n1_dim": json.loads(data or "{}").get("dim")}
            if len(labels) != 1:
                result["skip"] = "raw_label_not_unique"
                rows.append(result)
                continue
            label = labels[0]
            near = []
            for t in texts:
                if not DIM.fullmatch(t["text"]):
                    continue
                distance = math.hypot(t["x"]-label["x"], t["y"]-label["y"])
                if distance <= 240:
                    near.append({"id": t["id"], "text": t["text"], "layer": t["layer"],
                                 "dx": round(t["x"]-label["x"], 2),
                                 "dy": round(t["y"]-label["y"], 2),
                                 "distance": round(distance, 2)})
            near.sort(key=lambda x: (x["distance"], x["id"]))
            near = near[:8]
            result["candidates"] = near
            result["nearest_handle"] = near[0]["id"] if near else None
            if not near:
                result["skip"] = "no_section_text_near_label"
                rows.append(result)
                continue
            options = {x["id"]: f"{x['text']} at dx={x['dx']} dy={x['dy']}" for x in near}
            options["INSUFFICIENT"] = "None of the provided section texts can reliably be assigned to this beam label."
            state = {"source": "raw structural DXF TEXT to JSON", "beam_label": name,
                     "label_layer": label["layer"], "nearby_section_texts": near}
            question = Choice(
                instructions="Select the section dimension text that belongs to this beam label. Other texts may describe other beams, slab edges or pillar dimensions. Use explicit local evidence and abstain if ambiguous. Do not infer section from beam ID.",
                criteria=options,
            )
            t0 = time.perf_counter()
            try:
                response = client.system_one(state=state, questions={"beam_section_text": question})
                answer = response.choices["beam_section_text"]
                picked = next((x for x in near if x["id"] == answer.choice), None)
                result["jev"] = {"choice": answer.choice, "handle": picked["id"] if picked else None,
                                 "text": picked["text"] if picked else None,
                                 "confidence": answer.confidence,
                                 "input_tokens": response.usage.input_tokens if response.usage else None,
                                 "latency_s": round(time.perf_counter()-t0, 3)}
            except Exception as exc:
                result["jev"] = {"error_type": type(exc).__name__, "error": str(exc)[:160]}
            rows.append(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "jev_beam_section_pilot/1", "source": str(dxf),
                                       "warning": "beam section proximity is not full FV/LV interpretation; N1 agreement is not accuracy",
                                       "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    eligible = [r for r in rows if "text" in r.get("jev", {})]
    print(json.dumps({"beams": len(rows), "eligible": len(eligible),
                      "agreement_n1": sum(r["jev"]["text"] is not None and r["jev"]["text"] == r["n1_dim"] for r in eligible),
                      "agreement_nearest": sum(r["jev"]["handle"] is not None and r["jev"]["handle"] == r["nearest_handle"] for r in eligible),
                      "abstentions": sum(r["jev"]["handle"] is None for r in eligible),
                      "errors": sum("error_type" in r.get("jev", {}) for r in rows)}))
    print(args.output)


if __name__ == "__main__":
    main()
