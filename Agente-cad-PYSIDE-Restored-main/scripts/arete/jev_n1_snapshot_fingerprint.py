"""Read-only N1 table fingerprint for comparing local and VPS SA snapshots."""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    result = {"schema": "jev_n1_snapshot_fingerprint/1", "project_id": args.project_id, "tables": {}}
    try:
        for table in ("pillars", "beams", "slabs"):
            columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            selected = [c for c in ("name", "data_json", "points_json", "links_json", "extra_data_json") if c in columns]
            rows = conn.execute(f"SELECT {','.join(selected)} FROM {table} WHERE project_id=?", (args.project_id,)).fetchall()
            entries = [dict(zip(selected, row)) for row in rows]
            names = [str(row.get("name") or "") for row in entries]
            dims: list[str] = []
            levels: list[str] = []
            segment_counts: list[int] = []
            for row in entries:
                data = json.loads(row.get("data_json") or "{}")
                links = json.loads(row.get("links_json") or "{}")
                extra = json.loads(row.get("extra_data_json") or "{}")
                fields = data.get("fields") or {}
                dim = fields.get("dimensao") or fields.get("dim") or data.get("dim") or extra.get("dim")
                if dim:
                    dims.append(str(dim))
                level = fields.get("laje_nivel") or data.get("laje_nivel")
                if level:
                    levels.append(str(level))
                if table == "beams":
                    segments = (data.get("links") or links).get("viga_segs") or {}
                    segment_counts.append(len(segments.get("seg_bottom") or []))
            result["tables"][table] = {"rows": len(rows), "unique_names": len(set(names)),
                                         "names": sorted(set(names)), "filled_dimensions": len(dims),
                                         "filled_slab_levels": len(levels),
                                         "bottom_segment_counts": dict(Counter(segment_counts)) if table == "beams" else None}
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
