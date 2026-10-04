"""Reproduce the small raw-DXF physical evidence around L410."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    slab = next(x for x in state["slabs"] if x["name"] == "L410")
    n1_shape = Polygon(slab["points"])
    entities = list(ezdxf.readfile(str(args.dxf)).modelspace())
    texts = {e.dxf.handle: e for e in entities if e.dxftype() == "TEXT"}
    solids = []
    for entity in entities:
        if entity.dxftype() != "SOLID":
            continue
        pts = [(float(getattr(entity.dxf, f"vtx{i}").x),
                float(getattr(entity.dxf, f"vtx{i}").y)) for i in range(4)]
        poly = Polygon(pts).convex_hull
        if poly.is_valid and poly.area > 0:
            solids.append((entity, poly))
    records = []
    for handle in ("DAD", "CB5", "DC7", "E5D", "E5C"):
        entity = texts[handle]
        xy = (float(entity.dxf.insert.x), float(entity.dxf.insert.y))
        point = Point(xy)
        containing = [{"handle": solid.dxf.handle, "layer": solid.dxf.layer,
                       "area_cm2": round(poly.area, 2),
                       "bbox": tuple(round(v, 2) for v in poly.bounds)}
                      for solid, poly in solids if poly.covers(point)]
        records.append({"handle": handle, "text": str(entity.dxf.text), "xy": xy,
                        "n1_l410_polygon_contains": n1_shape.covers(point),
                        "containing_raw_solid": containing})
    output = {"schema": "jev_l410_physical_audit/1", "source_dxf": str(args.dxf),
              "sa_level": slab["nivel"], "n1_polygon_valid": n1_shape.is_valid,
              "n1_polygon_area_cm2": round(n1_shape.area, 2), "raw_texts": records,
              "caution": "Raw fill and text proximity establish distinct graphic regions, not final slab-level convention."}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
