#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lv_n2_vision_loop_runner.py

Headless LV N2 loop bootstrap.

This script does not call a vision API and does not write to project_data.vision.
It prepares the reproducible work package for the CLI agent with vision:
DXF, PNG render, extractor ficha, canonical ficha, schema, initial metrics,
and commands needed for the next visual reasoning pass.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
DB_DEFAULT = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS_OBRAS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
OUT_DEFAULT = REPO / "sandbox_lv_loop" / "runs"

sys.path.insert(0, str(SCRIPTS))


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()) or "NA"


def _pav_matches(db_pav: str | None, wanted: str | None) -> bool:
    if not wanted:
        return True
    a = (db_pav or "").upper().replace(" ", "_")
    b = wanted.upper().replace(" ", "_")
    return a == b or b in a or a in b


def find_recorte(
    db_path: Path,
    obra: str,
    pav: str,
    item: str,
) -> dict[str, Any]:
    """Find the best N2 LV recorte for obra/pav/item."""
    item = item.upper()
    candidates: list[dict[str, Any]] = []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT 'reverse_eng_fichas' AS source, id, obra_name, pavimento, classe,
                   elemento_id, recorte_path, confianca AS confidence, status
            FROM reverse_eng_fichas
            WHERE classe='LV' AND obra_name=? AND elemento_id=?
            ORDER BY id DESC
            """,
            (obra, item),
        ).fetchall()
        for row in rows:
            p = Path(row["recorte_path"] or "")
            if p.exists() and _pav_matches(row["pavimento"], pav):
                candidates.append(dict(row))

        rows = conn.execute(
            """
            SELECT 'reverse_eng_recortes' AS source, id, obra_name, NULL AS pavimento,
                   classe, elemento_id, recorte_path, confidence, status
            FROM reverse_eng_recortes
            WHERE classe='LV' AND obra_name=? AND elemento_id=?
            ORDER BY id DESC
            """,
            (obra, item),
        ).fetchall()
        for row in rows:
            p = Path(row["recorte_path"] or "")
            if p.exists():
                candidates.append(dict(row))
    finally:
        conn.close()

    if not candidates:
        obra_dir = DADOS_OBRAS / obra
        patterns = [
            f"**/LV_{item}_motor_*.dxf",
            f"**/LV_{item}_*.dxf",
        ]
        for pat in patterns:
            for p in obra_dir.glob(pat):
                candidates.append(
                    {
                        "source": "disk_glob",
                        "id": None,
                        "obra_name": obra,
                        "pavimento": pav,
                        "classe": "LV",
                        "elemento_id": item,
                        "recorte_path": str(p),
                        "confidence": None,
                        "status": "found",
                    }
                )

    if not candidates:
        raise FileNotFoundError(f"Recorte LV nao encontrado: obra={obra} pav={pav} item={item}")

    status_rank = {"aprovado": 0, "auto_aprovado": 1, "draft": 2, "manual": 3, "found": 4}

    def _rank(c: dict[str, Any]) -> tuple[int, float, int]:
        status = str(c.get("status") or "").lower()
        conf = c.get("confidence")
        try:
            conf_f = float(conf)
        except Exception:
            conf_f = -1.0
        rec_id = c.get("id") or 0
        return (status_rank.get(status, 9), -conf_f, -int(rec_id))

    return sorted(candidates, key=_rank)[0]


def render_dxf_to_png(dxf_path: Path, png_path: Path, max_px: int = 2600) -> Path:
    """Render DXF to PNG with a real-content crop."""
    try:
        import ezdxf
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.config import Configuration, HatchPolicy
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"Dependencias de render ausentes: {exc}") from exc

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    skip_layers = {"Folhas", "CARIMBO", "ESTRUTURACAO", "Forcador", "Perfil Metalico"}
    xs: list[float] = []
    ys: list[float] = []
    sentinel_x = -200.0

    for ent in msp:
        try:
            layer = getattr(ent.dxf, "layer", "")
            if layer in skip_layers:
                continue
            etype = ent.dxftype()
            if etype == "LINE":
                pts = [ent.dxf.start, ent.dxf.end]
                for pt in pts:
                    if float(pt.x) > sentinel_x:
                        xs.append(float(pt.x))
                        ys.append(float(pt.y))
            elif etype == "LWPOLYLINE":
                for x, y in ent.get_points("xy"):
                    if float(x) > sentinel_x:
                        xs.append(float(x))
                        ys.append(float(y))
            elif etype in {"TEXT", "MTEXT"} and hasattr(ent.dxf, "insert"):
                ins = ent.dxf.insert
                if float(ins.x) > sentinel_x:
                    xs.append(float(ins.x))
                    ys.append(float(ins.y))
        except Exception:
            continue

    if not xs or not ys:
        xs, ys = [0.0, 1000.0], [0.0, 500.0]

    w_dxf = max(xs) - min(xs)
    h_dxf = max(ys) - min(ys)
    ratio = w_dxf / max(h_dxf, 1.0)
    if ratio >= 1:
        fig_w = max_px / 100
        fig_h = max(max_px / max(ratio, 0.1) / 100, 4)
    else:
        fig_w = max(max_px * ratio / 100, 4)
        fig_h = max_px / 100

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("black")
    fig.patch.set_facecolor("black")
    ax.set_aspect("equal")
    ax.set_axis_off()

    ctx = RenderContext(doc)
    config = Configuration(show_defpoints=True, hatch_policy=HatchPolicy.NORMAL)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend, config=config).draw_layout(msp)

    pad_x = w_dxf * 0.02 + 5
    pad_y = h_dxf * 0.05 + 5
    ax.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
    ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y)

    png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(png_path), dpi=100, bbox_inches="tight", facecolor="black", edgecolor="none")
    plt.close(fig)
    return png_path


def generate_component_crops(png_path: Path, run_dir: Path, min_area: int = 3500) -> list[dict[str, Any]]:
    """Create coarse visual crops for each separated drawing group in the render."""
    try:
        from PIL import Image, ImageFilter
        import numpy as np
    except Exception as exc:  # pragma: no cover - environment dependent
        return [{"error": f"crop dependencies unavailable: {exc}"}]

    img = Image.open(png_path).convert("RGB")
    arr = np.asarray(img)
    mask = (arr[:, :, 0] > 35) | (arr[:, :, 1] > 35) | (arr[:, :, 2] > 35)
    mask_img = Image.fromarray((mask.astype("uint8") * 255), mode="L")
    mask_img = mask_img.filter(ImageFilter.MaxFilter(31))
    grown = np.asarray(mask_img) > 0
    h, w = grown.shape
    seen = np.zeros_like(grown, dtype=bool)
    crops: list[dict[str, Any]] = []

    for y0 in range(h):
        xs = np.where(grown[y0] & ~seen[y0])[0]
        for x0 in xs:
            if seen[y0, x0] or not grown[y0, x0]:
                continue
            stack = [(int(x0), int(y0))]
            seen[y0, x0] = True
            min_x = max_x = int(x0)
            min_y = max_y = int(y0)
            area = 0
            while stack:
                x, y = stack.pop()
                area += 1
                if x < min_x:
                    min_x = x
                elif x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                elif y > max_y:
                    max_y = y
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and grown[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((nx, ny))

            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            if area < min_area or bw < 80 or bh < 60:
                continue

            pad = 24
            left = max(0, min_x - pad)
            top = max(0, min_y - pad)
            right = min(w, max_x + pad + 1)
            bottom = min(h, max_y + pad + 1)
            crop_name = f"_crop_raw_{len(crops) + 1:02d}.png"
            img.crop((left, top, right, bottom)).save(run_dir / crop_name)
            crops.append(
                {
                    "file": crop_name,
                    "bbox_px": [left, top, right, bottom],
                    "width_px": right - left,
                    "height_px": bottom - top,
                    "component_area_px": area,
                }
            )

    crops.sort(key=lambda c: (c["bbox_px"][1], c["bbox_px"][0]))
    for idx, crop in enumerate(crops, 1):
        old_path = run_dir / crop["file"]
        new_name = f"crop_{idx:02d}.png"
        new_path = run_dir / new_name
        if old_path != new_path:
            old_path.replace(new_path)
        crop["file"] = new_name
        crop["idx"] = idx

    return crops


def render_dxf_region(dxf_path: Path, png_path: Path, bbox: dict[str, Any], pad: float = 80.0) -> Path:
    """Render a DXF region around a detected face unit."""
    import ezdxf
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, HatchPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    x_left = float(bbox.get("x_left", 0.0))
    x_right = float(bbox.get("x_right", 0.0))
    y_bot = float(bbox.get("y_bot", 0.0))
    y_top = float(bbox.get("y_top", 0.0))
    width = max(x_right - x_left, 1.0) + pad * 2
    height = max(y_top - y_bot, 1.0) + pad * 2
    ratio = width / max(height, 1.0)
    fig_w = 9.0 if ratio >= 1 else max(4.0, 9.0 * ratio)
    fig_h = max(4.0, fig_w / max(ratio, 0.1))

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("black")
    fig.patch.set_facecolor("black")
    ax.set_aspect("equal")
    ax.set_axis_off()

    ctx = RenderContext(doc)
    config = Configuration(show_defpoints=True, hatch_policy=HatchPolicy.NORMAL)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend, config=config).draw_layout(msp)
    ax.set_xlim(x_left - pad, x_right + pad)
    ax.set_ylim(y_bot - pad, y_top + pad)

    png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(png_path), dpi=120, bbox_inches="tight", facecolor="black", edgecolor="none")
    plt.close(fig)
    return png_path


def render_face_units(dxf_path: Path, run_dir: Path, canon: dict[str, Any]) -> list[dict[str, Any]]:
    renders: list[dict[str, Any]] = []
    for unit in canon.get("face_units", []):
        bbox = unit.get("bbox") or {}
        if not bbox:
            continue
        file_name = f"face_unit_{int(unit.get('idx', len(renders) + 1)):02d}_{_safe_part(unit.get('label') or 'face')}.png"
        render_dxf_region(dxf_path, run_dir / file_name, bbox)
        renders.append(
            {
                "idx": unit.get("idx"),
                "label": unit.get("label"),
                "side": unit.get("side"),
                "segments": len(unit.get("segments", [])),
                "file": file_name,
                "bbox": bbox,
            }
        )
    return renders


def extract_lv_ficha(dxf_path: Path, item: str, obra_root: Path) -> dict[str, Any]:
    from motor_reverso_lv import extrair_ficha_lateral_viga

    return extrair_ficha_lateral_viga(str(dxf_path), f"{item}_A", obra_root=str(obra_root))


def _norm_segment(seg: dict[str, Any], idx: int, face: str) -> dict[str, Any]:
    width = seg.get("largura_cm", seg.get("width", seg.get("largura", 0)))
    h1 = seg.get("height1", seg.get("h1", seg.get("h_A", 0)))
    return {
        "idx": idx,
        "face": face,
        "largura_cm": float(width or 0),
        "height1": float(h1 or 0),
        "height2": float(seg.get("height2", 0) or 0),
        "panel_type": seg.get("panel_type", seg.get("tipo", "Sarrafeado")),
        "grade_h1": float(seg.get("grade_h1", 0) or 0),
        "grade_h2": float(seg.get("grade_h2", 0) or 0),
        "laje_sup_local": float(seg.get("laje_sup_local", seg.get("slab_top", 0)) or 0),
        "laje_inf_local": float(seg.get("laje_inf_local", seg.get("slab_bottom", 0)) or 0),
        "slab_center": float(seg.get("slab_center", 0) or 0),
        "holes": seg.get("holes", []),
        "reuse": bool(seg.get("reuse") or seg.get("reuse_regions")),
        "reuse_regions": seg.get("reuse_regions", []),
        "is_first": bool(seg.get("is_first", idx == 1)),
        "is_last": bool(seg.get("is_last", False)),
        "codigos_forma": seg.get("codigos_forma", []),
        "raw": seg,
    }


def canonicalize_lv(ficha: dict[str, Any], item: str, recorte_path: Path) -> dict[str, Any]:
    segments_a = [
        _norm_segment(seg, idx + 1, "A")
        for idx, seg in enumerate(ficha.get("panels_A") or ficha.get("segments_A") or [])
    ]
    segments_b = [
        _norm_segment(seg, idx + 1, "B")
        for idx, seg in enumerate(ficha.get("panels_B") or ficha.get("segments_B") or [])
    ]

    views = ficha.get("section_views") or []
    norm_views = []
    for idx, sv in enumerate(views, 1):
        norm_views.append(
            {
                "idx": idx,
                "label": sv.get("label") or item,
                "h_A": float(sv.get("h_A", ficha.get("h_A", 0)) or 0),
                "h_B": float(sv.get("h_B", ficha.get("h_B", 0)) or 0),
                "b_cm": float(sv.get("b", ficha.get("b_geom", 0)) or 0),
                "h_section": float(sv.get("h_section", ficha.get("h_section", 0)) or 0),
                "laje_sup_A": float(sv.get("laje_sup_A", ficha.get("laje_sup_A", 0)) or 0),
                "laje_inf_A": float(sv.get("laje_inf_A", ficha.get("laje_inf_A", 0)) or 0),
                "laje_sup_B": float(sv.get("laje_sup_B", ficha.get("laje_sup_B", 0)) or 0),
                "laje_inf_B": float(sv.get("laje_inf_B", ficha.get("laje_inf_B", 0)) or 0),
                "raw": sv,
            }
        )

    face_units = []
    for idx, unit in enumerate(ficha.get("face_units") or [], 1):
        side = unit.get("side") or "?"
        panels = unit.get("panels") or []
        face_units.append(
            {
                "idx": idx,
                "label": unit.get("label") or "",
                "side": side,
                "bbox": unit.get("bbox") or {},
                "h_body": float(unit.get("h_body", 0) or 0),
                "h_total": float(unit.get("h_total", 0) or 0),
                "laje_sup": float(unit.get("laje_sup", 0) or 0),
                "laje_inf": float(unit.get("laje_inf", 0) or 0),
                "pontaletes_face": unit.get("pontaletes_face", 0),
                "grade_layer_style": unit.get("grade_layer_style", "native"),
                "segments": [
                    _norm_segment(seg, seg_idx + 1, side)
                    for seg_idx, seg in enumerate(panels)
                ],
                "raw": unit,
            }
        )

    return {
        "viga": item,
        "section_views": norm_views,
        "face_units": face_units,
        "segments_A": segments_a,
        "segments_B": segments_b,
        "metadata": {
            "source": "motor_reverso_lv",
            "recorte_path": str(recorte_path),
            "confidence": ficha.get("_confianca") or ficha.get("_er_meta", {}).get("confianca"),
            "h_A": ficha.get("h_A"),
            "h_B": ficha.get("h_B"),
            "b_geom": ficha.get("b_geom"),
            "tipo_viga": ficha.get("tipo_viga"),
            "continuation": ficha.get("continuation"),
            "text_left": ficha.get("text_left"),
            "text_right": ficha.get("text_right"),
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def initial_metrics(canon: dict[str, Any]) -> dict[str, Any]:
    n_vc = len(canon.get("section_views", []))
    n_a = len(canon.get("segments_A", []))
    n_b = len(canon.get("segments_B", []))
    conf = canon.get("metadata", {}).get("confidence")
    try:
        conf_f = float(conf)
    except Exception:
        conf_f = 0.0
    return {
        "stage": "pending_vision",
        "extractor_confidence": conf_f,
        "counts": {
            "section_views": n_vc,
            "face_units": len(canon.get("face_units", [])),
            "segments_A": n_a,
            "segments_B": n_b,
        },
        "ready_for_agent_vision": bool(n_vc and n_a and n_b),
        "score_formula": {
            "section_views": 25,
            "segments_A": 25,
            "segments_B": 25,
            "main_dimensions": 15,
            "details_provenance": 10,
        },
    }


def extractor_health(canon: dict[str, Any], crops: list[dict[str, Any]]) -> dict[str, Any]:
    section_heights = [
        sv.get("h_section")
        for sv in canon.get("section_views", [])
        if sv.get("h_section")
    ]
    unique_section_heights = sorted({float(v) for v in section_heights})
    n_a = len(canon.get("segments_A", []))
    n_b = len(canon.get("segments_B", []))
    face_units = canon.get("face_units", [])
    face_unit_summary = [
        {
            "idx": unit.get("idx"),
            "label": unit.get("label"),
            "side": unit.get("side"),
            "segments": len(unit.get("segments", [])),
            "h_total": unit.get("h_total"),
        }
        for unit in face_units
    ]
    warnings: list[str] = []
    if len(section_heights) != len(unique_section_heights):
        warnings.append("section_views contain repeated h_section values")
    if not face_units and n_a != n_b:
        warnings.append(f"segments_A/segments_B count mismatch: {n_a} vs {n_b}")
    if face_units and any(len(unit.get("segments", [])) == 0 for unit in face_units):
        warnings.append("one or more face_units have no segments")
    if not crops:
        warnings.append("no visual component crops generated")
    return {
        "section_heights": section_heights,
        "unique_section_heights": unique_section_heights,
        "segments_A": n_a,
        "segments_B": n_b,
        "face_units": face_unit_summary,
        "component_crops": len(crops),
        "warnings": warnings,
        "ready_for_stage_80": (
            not warnings
            and len(unique_section_heights) == len(section_heights)
            and bool(face_units)
        ),
    }


def make_schema() -> dict[str, Any]:
    return {
        "viga": "V301",
        "section_views": [
            {
                "idx": 1,
                "label": "V301",
                "h_A": "number_cm",
                "h_B": "number_cm",
                "b_cm": "number_cm",
                "h_section": "number_cm",
                "laje_sup_A": "number_cm",
                "laje_inf_A": "number_cm",
                "laje_sup_B": "number_cm",
                "laje_inf_B": "number_cm",
                "confidence": "0..1",
                "notes": "visual evidence",
            }
        ],
        "segments_A": [
            {
                "idx": 1,
                "largura_cm": "number_cm",
                "height1": "number_cm",
                "panel_type": "Sarrafeado|Grade|Misto|unknown",
                "laje_sup_local": "number_cm",
                "laje_inf_local": "number_cm",
                "details": {"sarrafos": "visible count/notes", "grades": "visible count/notes", "holes": []},
                "confidence": "0..1",
            }
        ],
        "face_units": [
            {
                "idx": 1,
                "label": "V301.A|CONT. V301.B",
                "side": "A|B",
                "h_total": "number_cm",
                "segments": "same segment schema",
                "confidence": "0..1",
            }
        ],
        "segments_B": "same as segments_A",
        "overall_similarity_stage": "40|60|80|90|95|100",
        "blocking_questions": [],
    }


def write_work_package(run_dir: Path, args: argparse.Namespace, rec: dict[str, Any]) -> None:
    package = {
        "objective": "LV N2 vision loop package for CLI agent",
        "obra": args.obra,
        "pav": args.pav,
        "item": args.item,
        "recorte": rec,
        "files": {
            "n2_png": "n2_recorte.png",
            "component_crops": "component_crops.json",
            "face_unit_renders": "face_unit_renders.json",
            "extractor_ficha": "extractor_ficha.json",
            "canonical_ficha": "canonical_ficha.json",
            "vision_schema": "vision_schema.json",
            "vision_ficha_target": "vision_ficha.json",
            "diff_target": "diff_extractor_vs_vision.json",
            "decision_log": "decision_log.md",
        },
        "commands": {
            "rerun": (
                f"python scripts/lv_n2_vision_loop_runner.py --obra {args.obra} "
                f"--pav {args.pav} --item {args.item}"
            ),
        },
        "instructions_for_agent": [
            "Open n2_recorte.png with vision.",
            "Open crop_*.png when the full render is too dense.",
            "Open face_unit_*.png to validate each detected lateral/continuation independently.",
            "Produce vision_ficha.json in the canonical schema.",
            "Compare vision_ficha.json against canonical_ficha.json.",
            "Classify stage 40/60/80/90/95/100.",
            "Write decision_log.md with cause and next action.",
        ],
    }
    write_json(run_dir / "work_package.json", package)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare LV N2 vision loop work package.")
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--item", default="V301")
    parser.add_argument("--db", default=str(DB_DEFAULT))
    parser.add_argument("--out-root", default=str(OUT_DEFAULT))
    parser.add_argument("--max-px", type=int, default=2600)
    args = parser.parse_args()

    item = args.item.upper()
    db_path = Path(args.db)
    out_root = Path(args.out_root)
    run_dir = out_root / _now_tag() / _safe_part(args.obra) / _safe_part(args.pav) / item
    run_dir.mkdir(parents=True, exist_ok=True)

    rec = find_recorte(db_path, args.obra, args.pav, item)
    recorte_path = Path(rec["recorte_path"])
    obra_root = DADOS_OBRAS / args.obra

    dxf_dst = run_dir / "n2_recorte.dxf"
    shutil.copy2(recorte_path, dxf_dst)

    png_path = render_dxf_to_png(dxf_dst, run_dir / "n2_recorte.png", max_px=args.max_px)
    component_crops = generate_component_crops(png_path, run_dir)
    ficha = extract_lv_ficha(dxf_dst, item, obra_root)
    canon = canonicalize_lv(ficha, item, dxf_dst)
    face_unit_renders = render_face_units(dxf_dst, run_dir, canon)
    metrics = initial_metrics(canon)
    metrics["extractor_health"] = extractor_health(canon, component_crops)

    write_json(run_dir / "recorte_record.json", rec)
    write_json(run_dir / "extractor_ficha.json", ficha)
    write_json(run_dir / "canonical_ficha.json", canon)
    write_json(run_dir / "component_crops.json", component_crops)
    write_json(run_dir / "face_unit_renders.json", face_unit_renders)
    write_json(run_dir / "vision_schema.json", make_schema())
    write_json(run_dir / "metrics.json", metrics)
    write_json(run_dir / "similarity_stage.json", {"stage": "pending_vision", "reason": "agent vision not run yet"})

    (run_dir / "vision_ficha.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "diff_extractor_vs_vision.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "human_questions.md").write_text("# Human Questions\n\nNone yet.\n", encoding="utf-8")
    (run_dir / "decision_log.md").write_text(
        "# Decision Log\n\n"
        "Status: pending agent vision.\n\n"
        f"Recorte: `{recorte_path}`\n\n"
        f"PNG: `{png_path}`\n\n"
        "Next: inspect image, produce vision_ficha.json, compare and classify stage.\n",
        encoding="utf-8",
    )
    write_work_package(run_dir, args, rec)

    print(f"RUN_DIR={run_dir}")
    print(f"PNG={png_path}")
    print(f"DXF={dxf_dst}")
    print(
        "COUNTS="
        f"VC:{len(canon['section_views'])} "
        f"A:{len(canon['segments_A'])} "
        f"B:{len(canon['segments_B'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
