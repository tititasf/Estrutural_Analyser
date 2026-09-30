"""Make full-layer source DXF SVG/PNG pairs for hybrid interpretation review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dxf", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--items", nargs="+", required=True)
    parser.add_argument("--radius", type=float, default=160.0)
    args = parser.parse_args()
    import ezdxf
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from portal.app.dxf_preview import renderizar_dxf_png, renderizar_dxf_svg_com_transform

    doc = ezdxf.readfile(str(args.dxf))
    labels: dict[str, list[dict]] = {name: [] for name in args.items}
    for entity in doc.modelspace():
        if entity.dxftype() != "TEXT":
            continue
        name = str(entity.dxf.text).strip()
        if name in labels:
            labels[name].append({"handle": entity.dxf.handle,
                                 "x": float(entity.dxf.insert.x),
                                 "y": float(entity.dxf.insert.y)})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name in args.items:
        points = labels[name]
        if not points:
            manifest.append({"item": name, "status": "no_raw_text_label"})
            continue
        xs, ys = [p["x"] for p in points], [p["y"] for p in points]
        x0, y0, x1, y1 = min(xs)-args.radius, min(ys)-args.radius, max(xs)+args.radius, max(ys)+args.radius
        bbox = (x0, y0, x1, y1)
        png = renderizar_dxf_png(args.dxf, bbox=bbox, largura_px=1000, altura_px=1000, margem_pct=0)
        svg = renderizar_dxf_svg_com_transform(args.dxf, bbox=bbox, largura_px=1000, altura_px=1000, margem_pct=0)
        png_name, svg_name = f"{name}_source_full.png", f"{name}_source_full.svg"
        (args.out_dir / png_name).write_bytes(png)
        (args.out_dir / svg_name).write_bytes(svg.svg)
        manifest.append({"item": name, "source_label_handles": [p["handle"] for p in points],
                         "requested_bbox_dxf": bbox, "actual_bbox_dxf": svg.bbox_dxf,
                         "png": png_name, "svg": svg_name, "status": "rendered_full_layer_source"})
    (args.out_dir / "manifest.json").write_text(json.dumps({"source_dxf": str(args.dxf), "items": manifest},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"requested": len(args.items), "rendered": sum(r["status"] == "rendered_full_layer_source" for r in manifest)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
