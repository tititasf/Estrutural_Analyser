"""Audit whether FV opening summaries carry beam-wide context into each segment.

Read-only research artifact. Polygon contact is a triage signal, not proof that
an opening exists or that a supporting pillar belongs to a panel.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--output", type=Path, help="omit to emit the complete JSON artifact on stdout")
    args = ap.parse_args()
    from shapely.geometry import Polygon

    conn = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        beams = conn.execute("SELECT name,data_json FROM beams WHERE project_id=? ORDER BY name", (args.project_id,)).fetchall()
        pillars = conn.execute("SELECT name,points_json FROM pillars WHERE project_id=?", (args.project_id,)).fetchall()
    finally:
        conn.close()
    pillar_shapes: dict[str, list] = {}
    for name, raw in pillars:
        points = json.loads(raw or "[]")
        if len(points) >= 3:
            shape = Polygon(points)
            if shape.is_valid and shape.area > 0:
                pillar_shapes.setdefault(name, []).append(shape)
    rows = []
    for name, raw in beams:
        beam = json.loads(raw)
        links = beam.get("links") or {}
        segments = ((links.get("viga_segs") or {}).get("seg_bottom") or [])
        if not segments:
            continue
        global_opening_names = sorted({p.get("name") or p.get("text") for p in
                                       ((links.get("aberturas") or {}).get("pilar") or []) if p.get("name") or p.get("text")})
        segment_rows = []
        for index, segment in enumerate(segments, 1):
            ficha = segment.get("ficha") or {}
            statement = str(ficha.get("abertura_especial") or "")
            match = re.fullmatch(r"(\d+) interferencia\(s\) por pilar", statement)
            points = segment.get("points") or []
            poly = Polygon(points) if len(points) >= 3 else None
            contacts = sorted(pname for pname, shapes in pillar_shapes.items()
                              if poly is not None and poly.is_valid and poly.area > 0
                              and any(poly.distance(shape) <= 0.05 for shape in shapes))
            segment_rows.append({"index": index, "statement": statement,
                                 "claimed_count": int(match.group(1)) if match else None,
                                 "n1_pillar_polygon_contacts_0_05": contacts})
        claims = [r["claimed_count"] for r in segment_rows if r["claimed_count"] is not None]
        if not claims:
            continue
        repeated = len(segment_rows) > 1 and len(claims) == len(segment_rows) and len(set(claims)) == 1
        rows.append({"item": name, "segment_count": len(segment_rows),
                     "global_links_aberturas_pilar_unique_names": global_opening_names,
                     "repeated_same_claim_across_segments": repeated,
                     "segments": segment_rows,
                     "decision": "scope_review_required" if repeated else "single_segment_or_nonuniform_claim",
                     "caution": "Counts and polygon contacts do not prove actual openings; inspect full-layer source and local FV evidence."})
    payload = {"schema": "jev_fv_scope_audit/1", "project_id": args.project_id,
               "authority": "read-only triage; no N1 or FV field modification",
               "summary": {"beams_with_claim": len(rows),
                           "multi_segment_same_claim": sum(r["repeated_same_claim_across_segments"] for r in rows)},
               "results": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload["summary"]))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
