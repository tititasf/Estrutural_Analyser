"""Cross-document Jev pilot: map special pillar labels to a raw CAD detail title."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path


def get_texts(path: Path) -> list[dict]:
    import ezdxf
    out = []
    for e in ezdxf.readfile(str(path)).modelspace():
        if e.dxftype() == "TEXT":
            out.append({"handle": e.dxf.handle, "text": str(e.dxf.text).strip(),
                        "layer": e.dxf.layer,
                        "x": round(float(e.dxf.insert.x), 3), "y": round(float(e.dxf.insert.y), 3)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overview-dxf", type=Path, required=True)
    ap.add_argument("--detail-dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--items", nargs="+", default=["P26", "P27"])
    args = ap.parse_args()
    from dotenv import load_dotenv
    from typesafe_sdk import TypeSafeClient, Choice
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TYPESAFE_API_KEY"):
        ap.error("TYPESAFE_API_KEY absent")
    overview, detail = get_texts(args.overview_dxf), get_texts(args.detail_dxf)
    anchors = []
    for item in args.items:
        names = [t for t in overview if t["text"] == item]
        if len(names) != 1:
            raise ValueError(f"ambiguous overview label for {item}: {len(names)}")
        name = names[0]
        notes = [t for t in overview if re.search(r"VER\s*DET", t["text"], re.IGNORECASE)
                 and math.hypot(t["x"] - name["x"], t["y"] - name["y"]) <= 60]
        anchors.append({"item": item, "label_handle": name["handle"],
                        "nearby_detail_notes": [{"handle": t["handle"], "text": t["text"]} for t in notes]})
    titles = [t for t in detail if "=" in t["text"] and any(item in t["text"] for item in args.items)]
    titles = [{"handle": t["handle"], "text": t["text"], "layer": t["layer"]} for t in titles]
    if not titles:
        raise ValueError("no candidate detail title found")
    choices = {t["handle"]: f"Detail title {t['text']}" for t in titles}
    choices["INSUFFICIENT"] = "No supplied title explicitly connects all target pillars to one detail."
    question = Choice(instructions="Which detail title explicitly maps all target pillar labels in the overview to one shared detail? Choose INSUFFICIENT if the supplied evidence does not state this mapping.", criteria=choices)
    rows = []
    with TypeSafeClient(model="jev-1.13.0") as client:
        for control in ("full", "title_removed"):
            state = {"overview_structural_dxf": anchors,
                     "separate_detail_dxf_titles": titles if control == "full" else [],
                     "evidence_condition": control}
            t0 = time.perf_counter()
            response = client.system_one(state=state, questions={"shared_detail": question})
            answer = response.choices["shared_detail"]
            accepted = any(t["handle"] == answer.choice and
                           set(args.items).issubset(set(re.findall(r"P\d+", t["text"]))) for t in state["separate_detail_dxf_titles"])
            rows.append({"control": control, "state": state, "jev_choice": answer.choice,
                         "jev_confidence": answer.confidence, "accepted_by_explicit_title_gate": accepted,
                         "input_tokens": response.usage.input_tokens if response.usage else None,
                         "latency_s": round(time.perf_counter() - t0, 3)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "jev_special_detail_link_pilot/1",
                                       "overview_dxf": str(args.overview_dxf), "detail_dxf": str(args.detail_dxf),
                                       "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"control": r["control"], "choice": r["jev_choice"],
                       "accepted": r["accepted_by_explicit_title_gate"]} for r in rows]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
