"""Export only the pillar columns needed for a read-only Jev/SA comparison."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT name,points_json,links_json,extra_data_json FROM pillars WHERE project_id=? ORDER BY name",
                            (args.project_id,)).fetchall()
    finally:
        conn.close()
    result = {"schema": "jev_pil_readonly_export/1", "project_id": args.project_id,
              "pillars": [{"name": name, "points": json.loads(points or "[]"),
                           "links": json.loads(links or "{}"), "extra": json.loads(extra or "{}")}
                          for name, points, links, extra in rows]}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
