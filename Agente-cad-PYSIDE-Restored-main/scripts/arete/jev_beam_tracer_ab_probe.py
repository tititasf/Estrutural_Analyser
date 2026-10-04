"""Compare current local vs copied VPS BeamTracer on the same frozen DXF, in memory."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dxf", type=Path, required=True)
    ap.add_argument("--vps-beam-tracer", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.core.beam_tracer import BeamTracer as LocalBeamTracer
    from src.core.dxf_loader import DXFLoader, RenderMode
    from src.core.spatial_index import SpatialIndex

    source = DXFLoader.load_dxf(str(args.dxf), mode=RenderMode.TRUE_GEOMETRY)
    lines, polys, texts = [source.get(k, []) for k in ("lines", "polylines", "texts")]
    index = SpatialIndex()
    for poly in polys:
        pts = poly.get("points") or []
        if pts:
            index.insert(poly, (min(p[0] for p in pts), min(p[1] for p in pts),
                                max(p[0] for p in pts), max(p[1] for p in pts)))
    for line in lines:
        start, end = line["start"], line["end"]
        index.insert(line, (min(start[0], end[0]), min(start[1], end[1]),
                            max(start[0], end[0]), max(start[1], end[1])))
    for item in texts:
        x, y = item["pos"]
        index.insert(item, (x-5, y-5, x+5, y+5))
    geometry = [item if "points" in item else {"points": [item["start"], item["end"]]}
                for item in lines + polys]
    spec = importlib.util.spec_from_file_location("src.core._vps_beam_tracer_probe", args.vps_beam_tracer)
    if spec is None or spec.loader is None:
        raise RuntimeError("VPS BeamTracer source cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    result = {}
    for name, cls in (("vps_beam_tracer", module.BeamTracer), ("local_beam_tracer", LocalBeamTracer)):
        found = cls(index).detect_beams(texts, geometry, visual_obstacles=[])
        result[name] = {}
        for beam in found:
            if beam.get("name") not in ("V411", "V419", "V420"):
                continue
            classified = (beam.get("geometry") or {}).get("classified") or {}
            by_class = {}
            for key in ("seg_bottom", "lv_seg_side_a", "lv_seg_side_b"):
                rows = classified.get(key) or []
                compact = []
                for row in rows:
                    pts = row.get("points") if isinstance(row, dict) else row
                    if not pts:
                        continue
                    compact.append({"bbox": [round(min(p[0] for p in pts), 2),
                                             round(min(p[1] for p in pts), 2),
                                             round(max(p[0] for p in pts), 2),
                                             round(max(p[1] for p in pts), 2)]})
                by_class[key] = compact
            result[name][beam["name"]] = {"is_h": beam.get("is_h"),
                                           "lv_is_h": beam.get("lv_is_h"),
                                           "classified": by_class}
    args.output.write_text(json.dumps({"schema": "jev_beam_tracer_ab_probe/1", "source_dxf": str(args.dxf),
                                       "same_spatial_index": True,
                                       "same_local_FundoVigaInterpreter": True,
                                       "visual_obstacles": [], "results": result},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: {n: {"is_h": b["is_h"], "lv_is_h": b["lv_is_h"],
                              "classes": {c: len(v) for c, v in b["classified"].items()}}
                          for n, b in beams.items()} for k, beams in result.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
