#!/usr/bin/env python3
"""Loop de producao N2 x N4 para visoes-corte LV de um pavimento.

Este runner valida o caminho real da interface:
recorte LV -> motor_reverso_lv -> gerar_lv_n4_fichas.py -> gerar_lv_dxf_stog.py
-> reextracao do N4.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lv_n2_vision_loop_runner import canonicalize_lv, extract_lv_ficha  # noqa: E402
from lv_section_visual_loop_runner import (  # noqa: E402
    render_dxf_region_strict,
    section_core_bbox,
    visual_metric,
)

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS_OBRAS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
N4_SCRIPT = SCRIPTS / "arete" / "gerar_lv_n4_fichas.py"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def list_lv_recortes(obra: str, pav_label: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, obra_name, projeto_id, elemento_id, recorte_path,
                   status, confidence, created_at
            FROM reverse_eng_recortes
            WHERE obra_name=? AND classe='LV' AND recorte_path LIKE ?
            ORDER BY CAST(SUBSTR(elemento_id, 2) AS INTEGER), elemento_id, id DESC
            """,
            (obra, f"%{pav_label}%"),
        ).fetchall()
    finally:
        conn.close()

    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        rec = dict(row)
        path = Path(rec["recorte_path"])
        if path.exists():
            latest.setdefault(rec["elemento_id"], rec)
    return list(latest.values())


def n4_slot_center_y(section_index: int, h_section: float) -> float:
    y_section = -150.0
    for _ in range(section_index - 1):
        y_section -= max(float(h_section) + 90.0, 180.0)
    return y_section + float(h_section) / 2.0


def make_contact_sheets(rows: list[dict[str, Any]], out_dir: Path, page_size: int = 16) -> None:
    font = ImageFont.load_default()
    cell_w, cell_h = 620, 390
    title_h = 34

    def trim_content(image: Image.Image) -> Image.Image:
        rgb = image.convert("RGB")
        bg = Image.new("RGB", rgb.size, "black")
        diff = ImageChops.difference(rgb, bg).convert("L")
        bbox = diff.point(lambda value: 255 if value > 20 else 0).getbbox()
        return rgb.crop(bbox) if bbox else rgb

    for page_idx, start in enumerate(range(0, len(rows), page_size), 1):
        page_rows = rows[start:start + page_size]
        sheet = Image.new(
            "RGB",
            (cell_w * 2, (cell_h + title_h) * len(page_rows)),
            "#111111",
        )
        draw = ImageDraw.Draw(sheet)
        for row_idx, row in enumerate(page_rows):
            top = row_idx * (cell_h + title_h)
            title = (
                f"{row['item']} corte {row['view_idx']} | "
                f"score {row['visual_metric']['coarse_visual_score']}% | "
                f"roundtrip {'ok' if row['roundtrip']['passed'] else 'fail'}"
            )
            draw.text((8, top + 8), title, fill="white", font=font)
            for col, key in enumerate(("n2_png", "n4_png")):
                image = trim_content(Image.open(row[key]))
                fitted = ImageOps.contain(image, (cell_w - 20, cell_h - 20))
                x = col * cell_w + (cell_w - fitted.width) // 2
                y = top + title_h + (cell_h - fitted.height) // 2
                sheet.paste(fitted, (x, y))
            draw.text((8, top + title_h + 6), "N2", fill="#00d7ff", font=font)
            draw.text((cell_w + 8, top + title_h + 6), "N4", fill="#62ff62", font=font)
        sheet.save(out_dir / f"contact_sheet_prod_sections_p{page_idx:02d}.png")


def validate_item(item: str, recorte_path: Path, obra_root: Path, out_dir: Path) -> dict[str, Any]:
    item_dir = out_dir / item
    item_dir.mkdir(parents=True, exist_ok=True)

    ficha = extract_lv_ficha(recorte_path, item, obra_root)
    canon = canonicalize_lv(ficha, item, recorte_path)
    write_json(item_dir / "extractor_ficha.json", ficha)
    write_json(item_dir / "canonical_ficha.json", canon)

    n4_cmd = [
        sys.executable,
        str(N4_SCRIPT),
        item,
        "--out",
        str(item_dir),
        "--entry-json",
        str(item_dir / "extractor_ficha.json"),
    ]
    n4_run = subprocess.run(
        n4_cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    n4_dxf = item_dir / f"LV_preview_{item}_A.dxf"
    if n4_run.returncode != 0 or not n4_dxf.exists():
        return {
            "item": item,
            "ok": False,
            "reason": "n4_generation_failed",
            "log": (n4_run.stdout + n4_run.stderr)[-1000:],
            "rows": [],
        }

    n4_ficha = extract_lv_ficha(n4_dxf, item, obra_root)
    n4_canon = canonicalize_lv(n4_ficha, item, n4_dxf)
    write_json(item_dir / "n4_roundtrip_ficha.json", n4_ficha)

    rows: list[dict[str, Any]] = []
    n2_views = canon.get("section_views") or []
    n4_views = n4_canon.get("section_views") or []
    for idx, n2_view in enumerate(n2_views, 1):
        raw_bbox = (n2_view.get("raw") or {}).get("bbox") or {}
        source_cx = (
            float(raw_bbox.get("x_left", 0.0))
            + float(raw_bbox.get("x_right", 0.0))
        ) / 2.0
        source_cy = (
            float(raw_bbox.get("y_bot", 0.0))
            + float(raw_bbox.get("y_top", 0.0))
        ) / 2.0

        n2_png = item_dir / f"n2_section_{idx:02d}.png"
        render_dxf_region_strict(
            recorte_path,
            n2_png,
            section_core_bbox(n2_view, source_cx, source_cy),
        )

        h_sec = float(n2_view.get("h_section") or 0.0)
        n4_png = item_dir / f"n4_section_{idx:02d}.png"
        render_dxf_region_strict(
            n4_dxf,
            n4_png,
            section_core_bbox(n2_view, 95.0, n4_slot_center_y(idx, h_sec)),
        )

        n4_view = n4_views[idx - 1] if idx <= len(n4_views) else {}
        roundtrip_passed = bool(n4_view) and all(
            [
                abs(
                    float(n4_view.get("b_cm", 0.0) or 0.0)
                    - float(n2_view.get("b_cm", 0.0) or 0.0)
                ) <= 0.5,
                abs(
                    float(n4_view.get("h_section", 0.0) or 0.0)
                    - float(n2_view.get("h_section", 0.0) or 0.0)
                ) <= 0.5,
            ]
        )
        rows.append(
            {
                "item": item,
                "view_idx": idx,
                "n2_png": str(n2_png),
                "n4_png": str(n4_png),
                "visual_metric": visual_metric(n2_png, n4_png),
                "roundtrip": {
                    "passed": roundtrip_passed,
                    "n4_section_count": len(n4_views),
                    "b_cm": n4_view.get("b_cm"),
                    "h_section": n4_view.get("h_section"),
                    "primitives": len(
                        ((n4_view.get("raw") or {}).get("visual_primitives") or [])
                    ) if n4_view else 0,
                },
            }
        )

    scores = [r["visual_metric"]["coarse_visual_score"] for r in rows]
    return {
        "item": item,
        "ok": True,
        "recorte_path": str(recorte_path),
        "n2_sections": len(n2_views),
        "n4_sections": len(n4_views),
        "roundtrip_passed": sum(1 for r in rows if r["roundtrip"]["passed"]),
        "roundtrip_total": len(rows),
        "avg_coarse_visual": round(sum(scores) / max(len(scores), 1), 1),
        "min_coarse_visual": min(scores) if scores else 0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav-label", default="13° PAV")
    parser.add_argument("--out", default=str(REPO / "sandbox_lv_loop" / "prod_pav13_sections"))
    parser.add_argument("--items", nargs="*", default=None)
    args = parser.parse_args()

    obra_root = DADOS_OBRAS / args.obra
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    recortes = list_lv_recortes(args.obra, args.pav_label)
    if args.items:
        requested = set(args.items)
        recortes = [rec for rec in recortes if rec["elemento_id"] in requested]
    if not recortes:
        raise SystemExit(f"Nenhum recorte LV encontrado para {args.obra}/{args.pav_label}")

    summaries: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for rec in recortes:
        item = rec["elemento_id"]
        print(f"[{item}] extraindo N2 e gerando N4 real...", flush=True)
        result = validate_item(item, Path(rec["recorte_path"]), obra_root, out_dir)
        item_rows = result.pop("rows", [])
        summaries.append(result)
        all_rows.extend(item_rows)
        print(
            f"[{item}] sections={result.get('n2_sections')} "
            f"roundtrip={result.get('roundtrip_passed')}/{result.get('roundtrip_total')} "
            f"visual={result.get('avg_coarse_visual')}%",
            flush=True,
        )

    write_json(out_dir / "prod_pav_section_report.json", {
        "obra": args.obra,
        "pav_label": args.pav_label,
        "items": [rec["elemento_id"] for rec in recortes],
        "summary": summaries,
        "rows": all_rows,
    })
    make_contact_sheets(all_rows, out_dir)

    total_rows = len(all_rows)
    roundtrip_ok = sum(1 for row in all_rows if row["roundtrip"]["passed"])
    scores = [row["visual_metric"]["coarse_visual_score"] for row in all_rows]
    print(json.dumps({
        "items": len(recortes),
        "section_pairs": total_rows,
        "roundtrip": f"{roundtrip_ok}/{total_rows}",
        "avg_coarse_visual": round(sum(scores) / max(len(scores), 1), 1),
        "min_coarse_visual": min(scores) if scores else 0,
        "out": str(out_dir),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
