"""Read-only comparison of slab height labels from raw DXF text.

Agreement with SA/N1 is diagnostic, not accuracy: the N1 label is not truth.
Every Jev call is restricted to one slab label and nearby h= candidates.
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

HEIGHT = re.compile(r"^h\s*=\s*\d+(?:[.,]\d+)?$", re.IGNORECASE)


def load():
    import ezdxf
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    try:
        slabs = con.execute("SELECT name,links_json FROM slabs WHERE project_id=? ORDER BY name", (PROJECT_ID,)).fetchall()
    finally:
        con.close()
    doc = ezdxf.readfile(str(DXF))
    texts = []
    for entity in doc.modelspace():
        if entity.dxftype() == "TEXT":
            try:
                texts.append({"id": entity.dxf.handle, "text": str(entity.dxf.text).strip(),
                              "layer": entity.dxf.layer,
                              "x": float(entity.dxf.insert.x), "y": float(entity.dxf.insert.y)})
            except (AttributeError, TypeError, ValueError):
                pass
    return slabs, texts


def case(name, links, texts):
    labels = [x for x in texts if x["text"] == name]
    if len(labels) != 1:
        return {"item": name, "skip": f"raw_label_count_{len(labels)}"}
    label = labels[0]
    heights = []
    for x in texts:
        if not HEIGHT.fullmatch(x["text"]):
            continue
        distance = math.hypot(x["x"] - label["x"], x["y"] - label["y"])
        if distance <= 160:
            heights.append({"id": x["id"], "text": x["text"], "layer": x["layer"],
                            "dx": round(x["x"] - label["x"], 2), "dy": round(x["y"] - label["y"], 2),
                            "distance": round(distance, 2)})
    heights.sort(key=lambda x: (x["distance"], x["id"]))
    heights = heights[:8]
    derived = json.loads(links or "{}")
    n1 = ((derived.get("laje_dim") or {}).get("label") or [{}])[0].get("text")
    return {"item": name, "raw_label": label, "height_candidates": heights,
            "nearest_handle": heights[0]["id"] if heights else None,
            "n1_text": n1}


def ask(client, row, use_svg=False):
    from typesafe_sdk import Choice
    candidates = row["height_candidates"]
    options = {x["id"]: f"{x['text']} at dx={x['dx']}, dy={x['dy']} from {row['item']}" for x in candidates}
    options["INSUFFICIENT"] = "No supplied h= text can be reliably assigned to this slab label."
    if use_svg:
        import xml.etree.ElementTree as ET
        from html import escape
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-160 -160 320 320">'
        svg += f'<text id="slab-label" x="0" y="0">{escape(row["item"])}</text>'
        for x in candidates:
            svg += f'<text id="{x["id"]}" data-layer="{escape(x["layer"])}" x="{x["dx"]}" y="{-x["dy"]}">{escape(x["text"])}</text>'
        svg += '</svg>'
        root = ET.fromstring(svg)
        state = {"source": "DXF text converted to semantic SVG and parsed back to JSON",
                 "svg_viewBox": root.attrib["viewBox"],
                 "text_nodes": [{"id": n.attrib["id"], "text": "".join(n.itertext()),
                                 "layer": n.attrib.get("data-layer"),
                                 "x": n.attrib["x"], "y": n.attrib["y"]} for n in root]}
    else:
        state = {"source": "raw structural DXF TEXT converted to JSON", "slab_label": row["item"],
                 "slab_label_layer": row["raw_label"]["layer"], "nearby_h_texts": candidates}
    question = Choice(
        instructions="Choose the h= text belonging to the target slab label. Use local spatial relation; other h= texts can belong to adjacent slabs. If ambiguous, choose INSUFFICIENT. Do not derive a number.",
        criteria=options,
    )
    t0 = time.perf_counter()
    result = client.system_one(state=state, questions={"slab_height_text": question})
    answer = result.choices["slab_height_text"]
    selected = next((x for x in candidates if x["id"] == answer.choice), None)
    return {"handle": selected["id"] if selected else None, "text": selected["text"] if selected else None,
            "choice": answer.choice, "confidence": answer.confidence,
            "latency_s": round(time.perf_counter()-t0, 3),
            "input_tokens": result.usage.input_tokens if result.usage else None}


def main():
    global PROJECT_ID, DXF
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--project-id", default=PROJECT_ID)
    ap.add_argument("--dxf", type=Path, default=DXF)
    ap.add_argument("--mode", choices=("json", "svg-json", "both"), default="both")
    args = ap.parse_args()
    PROJECT_ID, DXF = args.project_id, args.dxf.resolve()
    if not DXF.exists():
        ap.error("DXF not found")
    from dotenv import load_dotenv
    from typesafe_sdk import TypeSafeClient
    load_dotenv(ROOT / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    slabs, texts = load()
    rows = [case(name, links, texts) for name, links in slabs]
    with TypeSafeClient(model="jev-1.13.0") as client:
        for row in rows:
            if row.get("skip") or not row["height_candidates"]:
                continue
            row["jev"] = {}
            for arm in (("json", "svg-json") if args.mode == "both" else (args.mode,)):
                try:
                    row["jev"][arm] = ask(client, row, arm == "svg-json")
                except Exception as exc:
                    row["jev"][arm] = {"error_type": type(exc).__name__, "error": str(exc)[:160]}
            row.pop("raw_label")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "jev_laj_height_pilot/1", "source": str(DXF),
                                       "warning": "N1 agreement does not establish correctness",
                                       "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    for arm in (("json", "svg-json") if args.mode == "both" else (args.mode,)):
        eligible = [r for r in rows if "jev" in r and "text" in r["jev"].get(arm, {})]
        print(json.dumps({"arm": arm, "cases": len(eligible),
                          "agreement_n1": sum(r["jev"][arm]["text"] == r["n1_text"] for r in eligible),
                          "agreement_nearest": sum(r["jev"][arm]["handle"] == r["nearest_handle"] for r in eligible),
                          "abstentions": sum(r["jev"][arm]["handle"] is None for r in eligible),
                          "errors": sum("error_type" in r.get("jev", {}).get(arm, {}) for r in rows)}))
    print(args.output)


if __name__ == "__main__":
    main()
