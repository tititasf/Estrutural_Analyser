"""Read-only LAJ level association from DXF TEXT + N1 polygon + Jev.

The source of level text is raw structural DXF; N1 level value is never sent to
Jev. The polygon only defines a local spatial candidate region, not truth.
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


LEVEL = re.compile(r"^85\d[.,]\d{1,2}$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path)
    ap.add_argument("--project-id")
    ap.add_argument("--state-json", type=Path, help="read-only production SA state instead of SQLite")
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--negative-items", nargs="*", default=["L401", "L409", "L410", "L415", "L419"])
    args = ap.parse_args()
    import ezdxf
    from shapely.geometry import Point, Polygon
    from dotenv import load_dotenv
    from typesafe_sdk import Choice, TypeSafeClient
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    if args.state_json:
        state = json.loads(args.state_json.read_text(encoding="utf-8"))
        slabs = [(row["name"], json.dumps(row.get("points") or []),
                  json.dumps({"laje_nivel": {"label": [row["nivel"]] if row.get("nivel") else []}}))
                 for row in state["slabs"]]
    else:
        if not args.db or not args.project_id:
            ap.error("provide --state-json or both --db and --project-id")
        conn = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
        try:
            slabs = conn.execute("SELECT name,points_json,links_json FROM slabs WHERE project_id=? ORDER BY name",(args.project_id,)).fetchall()
        finally:
            conn.close()
    labels, levels = [], []
    for e in ezdxf.readfile(str(args.dxf)).modelspace():
        if e.dxftype() != "TEXT":
            continue
        row = {"handle": e.dxf.handle, "text": str(e.dxf.text).strip(),
               "x": float(e.dxf.insert.x), "y": float(e.dxf.insert.y), "layer": e.dxf.layer}
        if re.fullmatch(r"L\d+",row["text"]):
            labels.append(row)
        elif LEVEL.fullmatch(row["text"]):
            levels.append(row)
    results=[]
    with TypeSafeClient(model="jev-1.13.0") as client:
        for name,polygon_raw,links_raw in slabs:
            polygon=Polygon(json.loads(polygon_raw or "[]"))
            raw_labels=[r for r in labels if r["text"]==name]
            inside_labels=[r for r in raw_labels if polygon.covers(Point(r["x"],r["y"]))]
            row={"item":name,"n1_level_present":bool((json.loads(links_raw or "{}").get("laje_nivel") or {}).get("label")),
                 "raw_label_count":len(raw_labels),"labels_inside_polygon":len(inside_labels)}
            if len(inside_labels)!=1:
                row["skip"]="label_instance_unresolved"
                results.append(row)
                continue
            label=inside_labels[0]
            candidates=[]
            for r in levels:
                distance=math.hypot(r["x"]-label["x"],r["y"]-label["y"])
                if distance<=460:
                    candidates.append({"handle":r["handle"],"text":r["text"],"layer":r["layer"],
                                       "dx":round(r["x"]-label["x"],2),"dy":round(r["y"]-label["y"],2),
                                       "distance":round(distance,2),
                                       "inside_n1_polygon":bool(polygon.covers(Point(r["x"],r["y"])))})
            candidates.sort(key=lambda r:(not r["inside_n1_polygon"],r["distance"],r["handle"]))
            candidates=candidates[:8]
            row.update({"label_handle":label["handle"],"polygon_bbox":[round(v,2) for v in polygon.bounds],
                        "candidates":candidates,
                        "inside_candidates":[r["handle"] for r in candidates if r["inside_n1_polygon"]]})
            controls=("full","local_levels_removed") if name in args.negative_items else ("full",)
            row["jev"]={}
            for condition in controls:
                active=[r for r in candidates if condition=="full" or not r["inside_n1_polygon"]]
                options={r["handle"]:f"{r['text']} at dx={r['dx']} dy={r['dy']}" for r in active}
                options["INSUFFICIENT"]="No supplied elevation marker can be assigned safely to this slab label."
                state={"target_slab":name,"label_handle":label["handle"],
                       "n1_polygon_bbox_relative_to_label":[round(v-label["x"],2) if i%2==0 else round(v-label["y"],2) for i,v in enumerate(polygon.bounds)],
                       "candidate_level_texts":active,"evidence_condition":condition}
                q=Choice(instructions="Choose the DXF elevation text (855.xx) associated with the named slab. Use position relative to its label and polygon. A nearby marker of a neighboring slab is not sufficient. If local evidence is absent or conflicting, return INSUFFICIENT. Do not derive a new level.", criteria=options)
                t0=time.perf_counter()
                try:
                    response=client.system_one(state=state,questions={"slab_level_text":q})
                    answer=response.choices["slab_level_text"]
                    chosen=next((r for r in active if r["handle"]==answer.choice),None)
                    row["jev"][condition]={"choice":answer.choice,"text":chosen["text"] if chosen else None,
                                            "inside_n1_polygon":chosen["inside_n1_polygon"] if chosen else None,
                                            "confidence":answer.confidence,
                                            "input_tokens":response.usage.input_tokens if response.usage else None,
                                            "latency_s":round(time.perf_counter()-t0,3)}
                except Exception as exc:
                    row["jev"][condition]={"error_type":type(exc).__name__,"error":str(exc)[:160]}
            results.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"schema":"jev_laj_level_hybrid_pilot/1","source_dxf":str(args.dxf),
                                       "warning":"polygon and proximity do not certify slab level; visual review required",
                                       "results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    done=[r for r in results if "jev" in r]
    print(json.dumps({"slabs":len(results),"tested":len(done),
                      "full_selected":sum(r["jev"]["full"].get("text") is not None for r in done),
                      "full_abstained":sum(r["jev"]["full"].get("choice")=="INSUFFICIENT" for r in done),
                      "selected_inside":sum(r["jev"]["full"].get("inside_n1_polygon") is True for r in done),
                      "negative_abstained":sum(r["jev"].get("local_levels_removed",{}).get("choice")=="INSUFFICIENT" for r in done),
                      "negative_count":sum("local_levels_removed" in r["jev"] for r in done)}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
