#!/usr/bin/env python3
"""Baseline visual N2 x N4 para visoes de corte de laterais de viga.

O runner e deliberadamente sandbox-only: le o banco e os recortes aprovados,
mas grava apenas em sandbox_lv_loop/section_visual_10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lv_n2_vision_loop_runner import (  # noqa: E402
    canonicalize_lv,
    extract_lv_ficha,
)
from lv_n4_unit_loop_runner import generate_section  # noqa: E402

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS_OBRAS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DEFAULT_ITEMS = [
    "V301", "V302", "V305", "V308", "V310",
    "V311", "V322", "V327", "V330", "V331",
]

# Campos necessarios para reproduzir a geometria e as decisoes do robo SCR.
SECTION_CONTRACT = {
    "identity": ["label", "side_context", "continuation"],
    "geometry": [
        "b_cm", "h_section", "h_A", "h_B", "h_body_A", "h_body_B",
        "laje_sup_A", "laje_inf_A", "laje_sup_B", "laje_inf_B",
        "level_beam", "level_opposite", "level_ceiling", "bottom",
        "topology", "body_width_cm", "extension_left_cm",
        "extension_right_cm", "concrete_profiles", "visual_primitives",
    ],
    "assembly": [
        "mode_h1_A", "mode_h1_B", "mode_h2_A", "mode_h2_B",
        "grade_h1_A", "grade_h1_B", "grade_h2_A", "grade_h2_B",
        "sarrafo_left", "sarrafo_right", "barrote", "anchor_bars",
        "concrete_hatch", "pontalete",
    ],
}

GENERATOR_CONSUMED = {
    "label", "b_cm", "h_section", "h_A", "h_B",
    "topology", "concrete_profiles", "visual_primitives",
}


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def official_recorte(obra: str, item: str) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, obra_name, projeto_id, elemento_id, recorte_path,
                   status, confidence, created_at
            FROM reverse_eng_recortes
            WHERE obra_name=? AND classe='LV' AND elemento_id=?
            ORDER BY
                CASE status
                    WHEN 'aprovado' THEN 0
                    WHEN 'auto_aprovado' THEN 1
                    ELSE 2
                END,
                id DESC
            LIMIT 1
            """,
            (obra, item),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError(f"Recorte oficial nao encontrado: {obra}/{item}")
    result = dict(row)
    path = Path(result["recorte_path"])
    if not path.exists():
        raise FileNotFoundError(path)
    result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _trim_content(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    bg = Image.new("RGB", rgb.size, "black")
    diff = ImageChops.difference(rgb, bg).convert("L")
    bbox = diff.point(lambda value: 255 if value > 20 else 0).getbbox()
    return rgb.crop(bbox) if bbox else rgb


def _normalized_mask(path: Path, size: tuple[int, int] = (512, 512)) -> Image.Image:
    src = _trim_content(Image.open(path))
    src.thumbnail((size[0] - 24, size[1] - 24), Image.Resampling.LANCZOS)
    canvas = Image.new("L", size, 0)
    gray = src.convert("L").point(lambda value: 255 if value > 28 else 0)
    x = (size[0] - gray.width) // 2
    y = (size[1] - gray.height) // 2
    canvas.paste(gray, (x, y))
    return canvas


def visual_metric(n2_png: Path, n4_png: Path) -> dict[str, Any]:
    a = _normalized_mask(n2_png)
    b = _normalized_mask(n4_png)
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
        "coarse_visual_score": round(100 * (0.65 * iou + 0.35 * density_ratio), 1),
        "note": "metrica preliminar; veredito final exige inspecao visual do agente",
    }


def section_field_report(view: dict[str, Any]) -> dict[str, Any]:
    raw = view.get("raw") or {}
    flattened = dict(raw)
    flattened.update(view)
    all_fields = [
        field for fields in SECTION_CONTRACT.values() for field in fields
    ]
    present = []
    missing = []
    for field in all_fields:
        value = flattened.get(field)
        if value not in (None, "", [], {}):
            present.append(field)
        else:
            missing.append(field)
    generator_present = sorted(GENERATOR_CONSUMED.intersection(present))
    return {
        "contract_fields": len(all_fields),
        "present_fields": present,
        "missing_fields": missing,
        "coverage_pct": round(100 * len(present) / max(len(all_fields), 1), 1),
        "generator_consumed_fields": generator_present,
        "generator_coverage_pct": round(
            100 * len(generator_present) / len(GENERATOR_CONSUMED), 1
        ),
    }


def section_visual_bbox(view: dict[str, Any]) -> dict[str, float]:
    raw = view.get("raw") or {}
    bbox = raw.get("bbox") or {}
    x_left = float(bbox.get("x_left", 0.0))
    x_right = float(bbox.get("x_right", 0.0))
    y_bot = float(bbox.get("y_bot", 0.0))
    y_top = float(bbox.get("y_top", 0.0))
    cx = (x_left + x_right) / 2.0
    cy = (y_bot + y_top) / 2.0
    primitives = raw.get("visual_primitives") or []
    primitive_points: list[tuple[float, float]] = []
    for primitive in primitives:
        if primitive.get("kind") in {"line", "polyline"}:
            primitive_points.extend(
                (float(point[0]), float(point[1]))
                for point in primitive.get("points") or []
            )
        elif primitive.get("kind") == "text":
            insert = primitive.get("insert") or [0.0, 0.0]
            primitive_points.append((float(insert[0]), float(insert[1])))
        elif primitive.get("kind") == "hatch":
            primitive_points.extend(
                (float(point[0]), float(point[1]))
                for path in primitive.get("paths") or []
                for point in path
            )
    if primitive_points:
        xs = [point[0] for point in primitive_points]
        ys = [point[1] for point in primitive_points]
        return {
            "x_left": cx + min(xs) - 6.0,
            "x_right": cx + max(xs) + 6.0,
            "y_bot": cy + min(ys) - 6.0,
            "y_top": cy + max(ys) + 6.0,
        }

    b = float(view.get("b_cm") or raw.get("b") or 0.0)
    heights = [
        float(view.get("h_section") or 0.0),
        float(view.get("h_A") or 0.0),
        float(view.get("h_B") or 0.0),
    ]

    # The semantic bbox is intentionally broad so dimension texts can be
    # associated. Visual review needs a tighter frame around the cut itself.
    half_width = max(72.0, b + 45.0)
    half_height = max(75.0, max(heights) / 2.0 + 45.0)
    return {
        "x_left": cx - half_width,
        "x_right": cx + half_width,
        "y_bot": cy - half_height,
        "y_top": cy + half_height,
    }


def section_core_bbox(
    view: dict[str, Any],
    origin_x: float,
    origin_y: float,
) -> dict[str, float]:
    raw = view.get("raw") or {}
    primitives = raw.get("visual_primitives") or []
    points: list[tuple[float, float]] = []
    for primitive in primitives:
        if primitive.get("layer") == "COTA":
            continue
        if primitive.get("kind") in {"line", "polyline"}:
            points.extend(
                (float(point[0]), float(point[1]))
                for point in primitive.get("points") or []
            )
        elif primitive.get("kind") == "text":
            insert = primitive.get("insert") or [0.0, 0.0]
            points.append((float(insert[0]), float(insert[1])))
        elif primitive.get("kind") == "hatch":
            points.extend(
                (float(point[0]), float(point[1]))
                for path in primitive.get("paths") or []
                for point in path
            )
    if not points:
        return section_visual_bbox(view)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "x_left": origin_x + min(xs) - 8.0,
        "x_right": origin_x + max(xs) + 8.0,
        "y_bot": origin_y + min(ys) - 8.0,
        "y_top": origin_y + max(ys) + 8.0,
    }


def render_dxf_region_strict(
    dxf_path: Path,
    png_path: Path,
    bbox: dict[str, float],
) -> Path:
    import ezdxf
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, HatchPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    x_left = float(bbox["x_left"])
    x_right = float(bbox["x_right"])
    y_bot = float(bbox["y_bot"])
    y_top = float(bbox["y_top"])
    width = max(x_right - x_left, 1.0)
    height = max(y_top - y_bot, 1.0)
    ratio = width / height
    if ratio >= 1.0:
        fig_w = 9.0
        fig_h = max(0.8, fig_w / max(ratio, 0.1))
    else:
        fig_h = 9.0
        fig_w = max(0.8, fig_h * ratio)

    doc = ezdxf.readfile(str(dxf_path))
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("black")
    fig.patch.set_facecolor("black")
    ax.set_axis_off()
    Frontend(
        RenderContext(doc),
        MatplotlibBackend(ax),
        config=Configuration(
            show_defpoints=True,
            hatch_policy=HatchPolicy.NORMAL,
        ),
    ).draw_layout(doc.modelspace())
    fig.set_size_inches(fig_w, fig_h, forward=True)
    ax.set_aspect("auto")
    ax.set_xlim(x_left, x_right)
    ax.set_ylim(y_bot, y_top)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(
        str(png_path),
        dpi=120,
        facecolor="black",
        edgecolor="none",
    )
    plt.close(fig)
    return png_path


def make_contact_sheet(rows: list[dict[str, Any]], out_path: Path) -> None:
    cell_w, cell_h = 620, 390
    title_h = 34
    sheet = Image.new("RGB", (cell_w * 2, (cell_h + title_h) * len(rows)), "#111111")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for row_idx, row in enumerate(rows):
        top = row_idx * (cell_h + title_h)
        title = (
            f"{row['item']} corte {row['view_idx']} | "
            f"N2 campos {row['field_report']['coverage_pct']}% | "
            f"visual bruto {row['visual_metric']['coarse_visual_score']}%"
        )
        draw.text((8, top + 8), title, fill="white", font=font)
        for col, key in enumerate(("n2_png", "n4_png")):
            image = _trim_content(Image.open(row[key])).convert("RGB")
            fitted = ImageOps.contain(image, (cell_w - 20, cell_h - 20))
            x = col * cell_w + (cell_w - fitted.width) // 2
            y = top + title_h + (cell_h - fitted.height) // 2
            sheet.paste(fitted, (x, y))
        draw.text((8, top + title_h + 6), "N2", fill="#00d7ff", font=font)
        draw.text((cell_w + 8, top + title_h + 6), "N4", fill="#62ff62", font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--items", nargs="*", default=DEFAULT_ITEMS)
    parser.add_argument(
        "--out",
        default=str(REPO / "sandbox_lv_loop" / "section_visual_10"),
    )
    args = parser.parse_args()

    obra_root = DADOS_OBRAS / args.obra
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_rows: list[dict[str, Any]] = []
    beam_summary: list[dict[str, Any]] = []

    for item in args.items:
        rec = official_recorte(args.obra, item)
        recorte_path = Path(rec["recorte_path"])
        ficha = extract_lv_ficha(recorte_path, item, obra_root)
        canon = canonicalize_lv(ficha, item, recorte_path)
        item_dir = out_dir / item
        item_dir.mkdir(parents=True, exist_ok=True)
        write_json(item_dir / "recorte_record.json", rec)
        write_json(item_dir / "extractor_ficha.json", ficha)
        write_json(item_dir / "canonical_ficha.json", canon)

        item_rows = []
        for view in canon.get("section_views", []):
            idx = int(view.get("idx") or len(item_rows) + 1)
            context_bbox = section_visual_bbox(view)
            raw_bbox = (view.get("raw") or {}).get("bbox") or {}
            if not context_bbox or not raw_bbox:
                continue
            source_cx = (
                float(raw_bbox.get("x_left", 0.0))
                + float(raw_bbox.get("x_right", 0.0))
            ) / 2.0
            source_cy = (
                float(raw_bbox.get("y_bot", 0.0))
                + float(raw_bbox.get("y_top", 0.0))
            ) / 2.0
            n2_context_png = item_dir / f"n2_context_{idx:02d}.png"
            render_dxf_region_strict(
                recorte_path,
                n2_context_png,
                context_bbox,
            )
            n2_png = item_dir / f"n2_section_{idx:02d}.png"
            render_dxf_region_strict(
                recorte_path,
                n2_png,
                section_core_bbox(view, source_cx, source_cy),
            )
            n4_result = generate_section(item_dir, view)
            n4_auto_png = item_dir / n4_result["png"]
            n4_dxf = item_dir / n4_result["dxf"]
            roundtrip_ficha = extract_lv_ficha(n4_dxf, item, obra_root)
            write_json(
                item_dir / f"n4_roundtrip_ficha_{idx:02d}.json",
                roundtrip_ficha,
            )
            roundtrip_views = roundtrip_ficha.get("section_views") or []
            roundtrip_view = roundtrip_views[0] if roundtrip_views else {}
            roundtrip_ok = bool(roundtrip_views) and all(
                [
                    abs(
                        float(roundtrip_view.get("b", 0.0) or 0.0)
                        - float(view.get("b_cm", 0.0) or 0.0)
                    ) <= 0.2,
                    abs(
                        float(roundtrip_view.get("h_section", 0.0) or 0.0)
                        - float(view.get("h_section", 0.0) or 0.0)
                    ) <= 0.2,
                    str(roundtrip_view.get("topology") or "")
                    == str((view.get("raw") or {}).get("topology") or ""),
                ]
            )
            n4_png = item_dir / f"n4_core_{idx:02d}.png"
            render_dxf_region_strict(
                n4_dxf,
                n4_png,
                section_core_bbox(view, 100.0, 0.0),
            )
            row = {
                "item": item,
                "view_idx": idx,
                "view": view,
                "n2_png": str(n2_png),
                "n4_png": str(n4_png),
                "n2_context_png": str(n2_context_png),
                "n4_auto_png": str(n4_auto_png),
                "field_report": section_field_report(view),
                "visual_metric": visual_metric(n2_png, n4_png),
                "context_visual_metric": visual_metric(
                    n2_context_png,
                    n4_auto_png,
                ),
                "roundtrip": {
                    "passed": roundtrip_ok,
                    "section_count": len(roundtrip_views),
                    "b_cm": roundtrip_view.get("b"),
                    "h_section": roundtrip_view.get("h_section"),
                    "topology": roundtrip_view.get("topology"),
                },
            }
            item_rows.append(row)
            report_rows.append(row)

        beam_summary.append(
            {
                "item": item,
                "official_recorte": rec,
                "section_count": len(canon.get("section_views", [])),
                "rendered_pairs": len(item_rows),
                "avg_field_coverage_pct": round(
                    sum(r["field_report"]["coverage_pct"] for r in item_rows)
                    / max(len(item_rows), 1),
                    1,
                ),
                "avg_visual_score": round(
                    sum(r["visual_metric"]["coarse_visual_score"] for r in item_rows)
                    / max(len(item_rows), 1),
                    1,
                ),
                "roundtrip_passed": sum(
                    1 for row in item_rows if row["roundtrip"]["passed"]
                ),
                "roundtrip_total": len(item_rows),
            }
        )

    serializable_rows = []
    for row in report_rows:
        copy = dict(row)
        copy["n2_png"] = str(Path(copy["n2_png"]).relative_to(out_dir))
        copy["n4_png"] = str(Path(copy["n4_png"]).relative_to(out_dir))
        copy["n2_context_png"] = str(
            Path(copy["n2_context_png"]).relative_to(out_dir)
        )
        copy["n4_auto_png"] = str(
            Path(copy["n4_auto_png"]).relative_to(out_dir)
        )
        serializable_rows.append(copy)

    write_json(
        out_dir / "baseline.json",
        {
            "obra": args.obra,
            "items": args.items,
            "section_contract": SECTION_CONTRACT,
            "generator_consumed": sorted(GENERATOR_CONSUMED),
            "beams": beam_summary,
            "pairs": serializable_rows,
        },
    )
    make_contact_sheet(report_rows, out_dir / "contact_sheet_n2_n4.png")
    print(f"OUT={out_dir}")
    print(f"BEAMS={len(beam_summary)}")
    print(f"SECTION_PAIRS={len(report_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
