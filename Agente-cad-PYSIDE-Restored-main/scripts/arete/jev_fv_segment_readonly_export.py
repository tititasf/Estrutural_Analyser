"""Small read-only production FV evidence export for two ambiguous beams."""
import json
import sqlite3

db = sqlite3.connect("file:/opt/cad-analyzer/project_data.vision?mode=ro", uri=True)
project_id = "f28c3897-c8df-4bb9-a187-cb090f2c7ec7"
rows = db.execute("SELECT name,data_json FROM beams WHERE project_id=? AND name IN (?,?)",
                  (project_id, "V414", "VF402")).fetchall()
output = {}
for name, raw in rows:
    beam = json.loads(raw)
    links = beam.get("links") or {}
    segments = ((links.get("viga_segs") or {}).get("seg_bottom") or [])
    output[name] = {
        "opening_global": links.get("aberturas"),
        "segments": [{"index": i, "points": seg.get("points"),
                      "ficha": seg.get("ficha"),
                      "other_keys": sorted(k for k in seg if k not in ("points", "ficha"))}
                     for i, seg in enumerate(segments, 1)],
    }
db.close()
print(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
