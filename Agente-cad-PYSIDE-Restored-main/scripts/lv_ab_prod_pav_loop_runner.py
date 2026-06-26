#!/usr/bin/env python3
"""Baseline visual N2 x N4 para laterais A/B de vigas LV.

Usa a saida do runner de visao-corte (`lv_section_prod_pav_loop_runner.py`):
canonical_ficha.json + LV_preview_*.dxf por item. Renderiza cada face_unit do
N2 e o slot correspondente no N4 real para detectar gaps de reproducao A/B.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
DADOS_OBRAS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
sys.path.insert(0, str(SCRIPTS))

from lv_n2_vision_loop_runner import canonicalize_lv, extract_lv_ficha  # noqa: E402
from lv_n4_unit_loop_runner import generate_face_unit  # noqa: E402
from lv_section_visual_loop_runner import render_dxf_region_strict, visual_metric  # noqa: E402

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def trim_content(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    bg = Image.new("RGB", rgb.size, "black")
    diff = ImageChops.difference(rgb, bg).convert("L")
    bbox = diff.point(lambda value: 255 if value > 20 else 0).getbbox()
    return rgb.crop(bbox) if bbox else rgb


def _body_mask(path: Path, size: tuple[int, int] = (512, 256)) -> Image.Image:
    image = trim_content(Image.open(path)).convert("RGB")
    image.thumbnail((size[0] - 24, size[1] - 24), Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    src = Image.new("L", image.size, 0)
    px = image.load()
    out = src.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = px[x, y]
            if max(r, g, b) <= 24:
                continue
            is_cyan_dim = g > 90 and b > 90 and r < 80
            is_red_dim = r > 120 and g < 80 and b < 90
            if is_cyan_dim or is_red_dim:
                continue
            out[x, y] = 255
    x0 = (size[0] - image.width) // 2
    y0 = (size[1] - image.height) // 2
    mask.paste(src, (x0, y0))
    return mask


def body_visual_metric(n2_png: Path, n4_png: Path) -> dict[str, Any]:
    a = _body_mask(n2_png)
    b = _body_mask(n4_png)
    pa = list(a.get_flattened_data())
    pb = list(b.get_flattened_data())
    intersection = sum(1 for av, bv in zip(pa, pb) if av and bv)
    union = sum(1 for av, bv in zip(pa, pb) if av or bv)
    a_count = sum(1 for value in pa if value)
    b_count = sum(1 for value in pb if value)
    density_ratio = min(a_count, b_count) / max(a_count, b_count, 1)
    iou = intersection / max(union, 1)
    return {
        "mask_iou": round(iou, 4),
        "density_ratio": round(density_ratio, 4),
        "body_visual_score": round(100 * (0.55 * iou + 0.45 * density_ratio), 1),
        "note": "filtra cores de cota/anotacao para comparar corpo estrutural",
    }


def visual_bbox_for_unit(unit: dict[str, Any]) -> dict[str, Any]:
    bbox = dict(unit.get("bbox") or {})
    raw = unit.get("raw") or {}
    if not bbox:
        return bbox
    try:
        width = float(bbox.get("x_right", 0.0)) - float(bbox.get("x_left", 0.0))
        height = float(bbox.get("y_top", 0.0)) - float(bbox.get("y_bot", 0.0))
    except Exception:
        width = height = 0.0
    if not str(unit.get("label") or ""):
        if width <= 130.0:
            bbox["x_left"] = float(bbox.get("x_left", 0.0)) - 18.0
            bbox["x_right"] = float(bbox.get("x_right", 0.0)) + 75.0
            bbox["y_bot"] = float(bbox.get("y_bot", 0.0)) - 45.0
            bbox["y_top"] = float(bbox.get("y_top", 0.0)) + 50.0
        return bbox
    try:
        if width > 260.0:
            return bbox
    except Exception:
        return bbox
    try:
        lx = float(raw.get("label_x"))
        ly = float(raw.get("label_y"))
    except Exception:
        return bbox
    bbox["x_left"] = min(float(bbox.get("x_left", lx)), lx - 30.0)
    bbox["x_right"] = max(float(bbox.get("x_right", lx)), lx + 90.0)
    bbox["y_bot"] = min(float(bbox.get("y_bot", ly)), ly - 20.0)
    bbox["y_top"] = max(float(bbox.get("y_top", ly)), ly + 25.0)
    return bbox


def make_contact_sheets(rows: list[dict[str, Any]], out_dir: Path, page_size: int = 18) -> None:
    font = ImageFont.load_default()
    cell_w, cell_h = 650, 270
    title_h = 30
    for page_idx, start in enumerate(range(0, len(rows), page_size), 1):
        page_rows = rows[start:start + page_size]
        sheet = Image.new("RGB", (cell_w * 2, (cell_h + title_h) * len(page_rows)), "#111111")
        draw = ImageDraw.Draw(sheet)
        for row_idx, row in enumerate(page_rows):
            top = row_idx * (cell_h + title_h)
            title = (
                f"{row['item']} {row['side']} unit {row['unit_idx']} "
                f"seg={row['segments']} score={row['visual_metric']['coarse_visual_score']}% "
                f"body={row['body_visual_metric']['body_visual_score']}%"
            )
            draw.text((8, top + 8), title, fill="white", font=font)
            for col, key in enumerate(("n2_png", "n4_png")):
                image = trim_content(Image.open(row[key]))
                fitted = ImageOps.contain(image, (cell_w - 20, cell_h - 20))
                x = col * cell_w + (cell_w - fitted.width) // 2
                y = top + title_h + (cell_h - fitted.height) // 2
                sheet.paste(fitted, (x, y))
            draw.text((8, top + title_h + 5), "N2", fill="#00d7ff", font=font)
            draw.text((cell_w + 8, top + title_h + 5), "N4", fill="#62ff62", font=font)
        sheet.save(out_dir / f"contact_sheet_ab_p{page_idx:02d}.png")


def run(
    source_dir: Path,
    out_dir: Path,
    max_units: int | None = None,
    refresh_extraction: bool = True,
    only_items: set[str] | None = None,
) -> dict[str, Any]:
    report_path = source_dir / "prod_pav_section_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    for item in report.get("items") or []:
        if only_items and item not in only_items:
            continue
        item_dir = source_dir / item
        canon_path = item_dir / "canonical_ficha.json"
        extractor_path = item_dir / "extractor_ficha.json"
        if not canon_path.exists() or not extractor_path.exists():
            summary.append({"item": item, "ok": False, "reason": "missing_artifacts"})
            continue
        cached = json.loads(canon_path.read_text(encoding="utf-8"))
        cached_ficha = json.loads(extractor_path.read_text(encoding="utf-8"))
        recorte_path = Path(
            cached.get("metadata", {}).get("recorte_path")
            or cached_ficha.get("_er_meta", {}).get("dxf_path", "")
        )
        if refresh_extraction and recorte_path.exists():
            obra_root = DADOS_OBRAS / "Obra_TREINO_1"
            ficha = extract_lv_ficha(recorte_path, item, obra_root)
            canon = canonicalize_lv(ficha, item, recorte_path)
            write_json(out_dir / item / "live_canonical_ficha.json", canon)
        else:
            canon = cached
        units = [u for u in canon.get("face_units") or [] if u.get("bbox") and u.get("segments")]
        item_rows = []
        for unit in units:
            if max_units is not None and len(rows) >= max_units:
                break
            idx = int(unit.get("idx") or len(item_rows) + 1)
            side = str(unit.get("side") or "?")
            n2_png = out_dir / item / f"n2_ab_unit_{idx:02d}_{side}.png"
            render_dxf_region_strict(recorte_path, n2_png, visual_bbox_for_unit(unit))
            unit_for_n4 = dict(unit)
            n4_result = generate_face_unit(out_dir / item / "n4_units", unit_for_n4)
            n4_png = out_dir / item / "n4_units" / n4_result["png"]
            row = {
                "item": item,
                "unit_idx": idx,
                "label": unit.get("label"),
                "side": side,
                "segments": len(unit.get("segments") or []),
                "n2_png": str(n2_png),
                "n4_png": str(n4_png),
                "visual_metric": visual_metric(n2_png, n4_png),
                "body_visual_metric": body_visual_metric(n2_png, n4_png),
                "fields": {
                    "h_body": unit.get("h_body"),
                    "h_total": unit.get("h_total"),
                    "laje_sup": unit.get("laje_sup"),
                    "laje_inf": unit.get("laje_inf"),
                    "panel_types": sorted({s.get("panel_type") for s in unit.get("segments") or []}),
                },
            }
            rows.append(row)
            item_rows.append(row)
        summary.append({
            "item": item,
            "ok": True,
            "face_units": len(units),
            "units_A": sum(1 for u in units if u.get("side") == "A"),
            "units_B": sum(1 for u in units if u.get("side") == "B"),
            "segments": sum(len(u.get("segments") or []) for u in units),
            "rendered": len(item_rows),
        })

    scores = [r["visual_metric"]["coarse_visual_score"] for r in rows]
    body_scores = [r["body_visual_metric"]["body_visual_score"] for r in rows]
    result = {
        "source_dir": str(source_dir),
        "summary": summary,
        "rows": rows,
        "totals": {
            "items": len(summary),
            "units_rendered": len(rows),
            "avg_coarse_visual": round(sum(scores) / max(len(scores), 1), 1),
            "min_coarse_visual": min(scores) if scores else 0,
            "avg_body_visual": round(sum(body_scores) / max(len(body_scores), 1), 1),
            "min_body_visual": min(body_scores) if body_scores else 0,
            "missing_A": [s["item"] for s in summary if s.get("ok") and s.get("units_A") == 0],
            "missing_B": [s["item"] for s in summary if s.get("ok") and s.get("units_B") == 0],
        },
    }
    write_json(out_dir / "ab_prod_visual_report.json", result)
    make_contact_sheets(rows, out_dir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default=str(REPO / "sandbox_lv_loop" / "prod_pav13_sections_arete_gap1800"))
    parser.add_argument("--out", default=str(REPO / "sandbox_lv_loop" / "prod_pav13_ab_baseline"))
    parser.add_argument("--max-units", type=int, default=None)
    parser.add_argument("--items", nargs="*", default=None)
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    result = run(
        Path(args.source_dir),
        Path(args.out),
        args.max_units,
        refresh_extraction=not args.use_cache,
        only_items={item.upper() for item in args.items} if args.items else None,
    )
    print(json.dumps(result["totals"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
