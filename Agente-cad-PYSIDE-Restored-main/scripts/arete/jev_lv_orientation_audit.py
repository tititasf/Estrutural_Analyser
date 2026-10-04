"""Read-only audit of LV orientation against raw DXF beam-label rotation."""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path


def axis_from_rotation(degrees: float) -> str | None:
    angle = degrees % 180.0
    if min(angle, 180.0-angle) <= 5.0:
        return "H"
    if abs(angle-90.0) <= 5.0:
        return "V"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    import ezdxf

    db = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        beams = db.execute("SELECT name,data_json FROM beams WHERE project_id=? ORDER BY name", (args.project_id,)).fetchall()
    finally:
        db.close()
    labels: dict[str, list[dict]] = {}
    for e in ezdxf.readfile(str(args.dxf)).modelspace():
        if e.dxftype() != "TEXT":
            continue
        text = str(e.dxf.text).strip()
        if re.fullmatch(r"VF?\d+[A-Z]?", text):
            labels.setdefault(text, []).append({"handle": e.dxf.handle,
                                                 "x": float(e.dxf.insert.x), "y": float(e.dxf.insert.y),
                                                 "rotation": float(e.dxf.get("rotation", 0))})
    rows = []
    for name, raw in beams:
        beam = json.loads(raw)
        pos = beam.get("pos") or []
        candidates = labels.get(name) or []
        closest = min(candidates, key=lambda x: math.hypot(x["x"]-pos[0], x["y"]-pos[1])) if len(pos) >= 2 and candidates else None
        label_axis = axis_from_rotation(closest["rotation"]) if closest else None
        links = beam.get("links") or {}
        votes = Counter()
        for key, slots in links.items():
            if not re.fullmatch(r"viga_[ab]_seg_\d+_comp_total_passa", str(key)) or not isinstance(slots, dict):
                continue
            for segment_list in slots.values():
                if not isinstance(segment_list, list):
                    continue
                for segment in segment_list:
                    points = segment.get("points") if isinstance(segment, dict) else None
                    if not points or len(points) < 2:
                        continue
                    dx, dy = abs(points[-1][0]-points[0][0]), abs(points[-1][1]-points[0][1])
                    if dx > dy*2:
                        votes["H"] += 1
                    elif dy > dx*2:
                        votes["V"] += 1
                    else:
                        votes["other"] += 1
        n1_axis = "H" if beam.get("lv_is_h") is True else "V" if beam.get("lv_is_h") is False else None
        rows.append({"item": name, "label": closest, "raw_label_axis": label_axis,
                     "n1_beam_axis": "H" if beam.get("is_h") is True else "V" if beam.get("is_h") is False else None,
                     "n1_lv_axis": n1_axis, "lv_geometry_axis_votes": dict(votes),
                     "label_vs_lv_disagree": label_axis is not None and n1_axis is not None and label_axis != n1_axis})
    payload = {"schema": "jev_lv_orientation_audit/1", "project_id": args.project_id,
               "source_dxf": str(args.dxf),
               "summary": {"beams": len(rows), "label_vs_lv_disagree": sum(x["label_vs_lv_disagree"] for x in rows)},
               "results": rows,
               "warning": "label rotation is evidence, not complete proof of side-panel geometry"}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload["summary"]))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
