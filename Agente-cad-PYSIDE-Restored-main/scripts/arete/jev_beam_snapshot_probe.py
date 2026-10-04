"""Read-only, compact FV/LV N1 contract profile for one SA project."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--project-id", required=True)
    args = ap.parse_args()
    db = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT name,data_json FROM beams WHERE project_id=? ORDER BY name", (args.project_id,)).fetchall()
    finally:
        db.close()
    result = []
    def segment_count(value: object) -> int:
        if isinstance(value, (list, tuple)):
            return len(value)
        if isinstance(value, int):
            return max(value, 0)
        return 0
    for name, raw in rows:
        d = json.loads(raw or "{}")
        links = d.get("links") or {}
        contracts = d.get("lv_generation_contracts") or {}
        result.append({"item": name,
                       "n1_is_h": d.get("is_h"), "n1_lv_is_h": d.get("lv_is_h"),
                       "n1_position": d.get("pos"),
                       "n1_dimension": d.get("dim") or (d.get("fields") or {}).get("dimensao"),
                       "fv_segments": len(((links.get("viga_segs") or {}).get("seg_bottom") or [])),
                       "lv_segments_a": segment_count(d.get("seg_a")),
                       "lv_segments_b": segment_count(d.get("seg_b")),
                       "lv_exists_a1": d.get("viga_a_seg_1_exists"),
                       "lv_exists_b1": d.get("viga_b_seg_1_exists"),
                       "lv_contract_cells_with_panels": [f"{behavior}_{side}" for behavior in ("Para", "Passa")
                                                         for side in ("A", "B")
                                                         if ((contracts.get(behavior) or {}).get(side) or {}).get("panels")],
                       "lv_contract_present": bool(contracts),
                       "fv_local_support_links": sum(bool(links.get(f"viga_fundo_seg_{i}_local_{end}"))
                                                     for i in range(1, len(((links.get("viga_segs") or {}).get("seg_bottom") or []))+1)
                                                     for end in ("ini", "fim"))})
    print(json.dumps({"schema": "jev_beam_snapshot_probe/1", "project_id": args.project_id,
                      "results": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
