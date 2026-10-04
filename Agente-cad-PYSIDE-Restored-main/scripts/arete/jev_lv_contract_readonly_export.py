"""Small read-only beam contract export; safe to pipe to VPS python3 stdin."""
import json
import sqlite3

db = sqlite3.connect("file:/opt/cad-analyzer/project_data.vision?mode=ro", uri=True)
project_id = "f28c3897-c8df-4bb9-a187-cb090f2c7ec7"
names = ("V411", "V420", "V419")
rows = db.execute("SELECT name,data_json FROM beams WHERE project_id=? AND name IN (?,?,?)",
                  (project_id, *names)).fetchall()
output = {}
for name, raw in rows:
    data = json.loads(raw)
    contracts = data.get("lv_generation_contracts") or {}
    output[name] = {
        "is_h": data.get("is_h"), "lv_is_h": data.get("lv_is_h"),
        "cells": {
            behavior + "_" + side: {
                "segments": [{"index": item.get("segment_index"),
                              "width": item.get("width"),
                              "points": item.get("points"),
                              "source_key": item.get("source_key")}
                             for item in ((cell or {}).get("structural_segments") or [])],
                "panel_count": len((cell or {}).get("panels") or []),
                "generation_ready": (cell or {}).get("generation_ready"),
            }
            for behavior, sides in contracts.items()
            for side, cell in sides.items()
        },
    }
db.close()
print(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
