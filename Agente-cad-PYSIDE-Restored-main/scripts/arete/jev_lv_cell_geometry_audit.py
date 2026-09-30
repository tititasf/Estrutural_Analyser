"""Audit N1 LV cells against their own FV geometry, without modifying N1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    by_kind: dict[str, dict[str, list[dict]]] = {}
    for kind, rows in state["segmentos"].items():
        for row in rows:
            by_kind.setdefault(row["beam_name"], {}).setdefault(kind, []).append(row)
    footprints = {}
    for name, kinds in by_kind.items():
        polygons = []
        for row in kinds.get("fundo", []):
            pts = row.get("points") or []
            if len(pts) >= 4:
                geom = Polygon(pts)
                if geom.is_valid and geom.area > 0:
                    polygons.append(geom)
        if polygons:
            footprints[name] = unary_union(polygons)
    results = []
    for name, kinds in sorted(by_kind.items()):
        if not name.startswith("V") or name.startswith("VF"):
            continue
        if name not in footprints:
            continue
        footprint = footprints[name]
        cells = []
        invalid_cells = []
        for kind in ("lateral_a_para", "lateral_b_para"):
            for row in kinds.get(kind, []):
                pts = row.get("points") or []
                if len(pts) != 2 or float(row.get("length") or 0.0) <= 0:
                    invalid_cells.append({"kind": kind, "segment_label": row.get("segment_label"),
                                          "length": row.get("length"), "point_count": len(pts)})
                    continue
                shape = LineString(pts)
                distance = float(shape.distance(footprint))
                outside_fraction = (float(shape.difference(footprint.buffer(30.0)).length / shape.length)
                                    if shape.length > 0 else 0.0)
                dx = max(p[0] for p in pts) - min(p[0] for p in pts)
                dy = max(p[1] for p in pts) - min(p[1] for p in pts)
                nearest_other = min(((other, float(shape.distance(other_footprint)))
                                     for other, other_footprint in footprints.items() if other != name),
                                    key=lambda pair: pair[1], default=(None, None))
                cells.append({"kind": kind, "segment_label": row.get("segment_label"),
                              "length": row.get("length"), "axis": "H" if dx > dy else "V",
                              "distance_to_own_fv_cm": round(distance, 3),
                              "nearest_other_fv": nearest_other[0],
                              "distance_to_nearest_other_fv_cm": round(nearest_other[1], 3) if nearest_other[1] is not None else None,
                              "outside_30cm_fraction": round(outside_fraction, 3),
                              "points": pts, "suspicious_remote": distance > 30.0 or outside_fraction > 0.5})
        results.append({"item": name, "fv_segment_count": len(kinds.get("fundo", [])),
                        "lv_cells_a_b_para": len(cells),
                        "remote_cells": sum(c["suspicious_remote"] for c in cells),
                        "invalid_cells": invalid_cells,
                        "cells": cells})
    output = {"schema": "jev_lv_cell_geometry_audit/1", "source": str(args.state),
              "method": "LV Para A/B line distance >30 cm OR >50% length outside own FV 30 cm buffer; diagnostic, not truth for side convention",
              "summary": {"regular_beams": len(results),
                          "beams_with_remote_cells": sum(x["remote_cells"] > 0 for x in results),
                          "remote_cells": sum(x["remote_cells"] for x in results),
                          "invalid_cells": sum(len(x["invalid_cells"]) for x in results)},
              "results": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": output["summary"],
                      "remote_items": [(x["item"], x["remote_cells"]) for x in results if x["remote_cells"]]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
