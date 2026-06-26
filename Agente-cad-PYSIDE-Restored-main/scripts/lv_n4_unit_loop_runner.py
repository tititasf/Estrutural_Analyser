#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lv_n4_unit_loop_runner.py

Generate sandbox N4 DXF/PNG artifacts from a LV N2 loop run.

Input is the run directory produced by lv_n2_vision_loop_runner.py. This script
does not write to project_data.vision or to the obra final output folders.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from gerar_lv_dxf_stog import draw_lv_face, draw_section_detail, setup_doc
from lv_n2_vision_loop_runner import render_dxf_to_png, write_json


def _primitive_attribs(primitive: dict[str, Any]) -> dict[str, Any]:
    attribs: dict[str, Any] = {
        "layer": str(primitive.get("layer") or "0"),
    }
    color = int(primitive.get("color", 256) or 256)
    if color != 256:
        attribs["color"] = color
    linetype = str(primitive.get("linetype") or "BYLAYER")
    if linetype not in {"", "BYLAYER"}:
        attribs["linetype"] = linetype
    return attribs


def _draw_section_visual_primitives(msp: Any, view: dict[str, Any]) -> bool:
    raw = view.get("raw") or {}
    primitives = raw.get("visual_primitives") or []
    if not primitives:
        return False

    doc = msp.doc
    x_shift = 100.0

    def point(value: list[float]) -> tuple[float, float]:
        return x_shift + float(value[0]), float(value[1])

    for primitive in primitives:
        layer = str(primitive.get("layer") or "0")
        if layer not in doc.layers:
            doc.layers.add(layer)
        attribs = _primitive_attribs(primitive)
        kind = primitive.get("kind")
        try:
            if kind == "line":
                points = primitive.get("points") or []
                if len(points) == 2:
                    msp.add_line(
                        point(points[0]),
                        point(points[1]),
                        dxfattribs=attribs,
                    )
            elif kind == "polyline":
                points = primitive.get("points") or []
                if len(points) >= 2:
                    msp.add_lwpolyline(
                        [point(value) for value in points],
                        close=bool(primitive.get("closed")),
                        dxfattribs=attribs,
                    )
            elif kind == "text":
                insert = point(primitive.get("insert") or [0.0, 0.0])
                text = msp.add_text(
                    str(primitive.get("text") or ""),
                    dxfattribs={
                        **attribs,
                        "insert": insert,
                        "height": float(primitive.get("height", 7.0) or 7.0),
                        "rotation": float(primitive.get("rotation", 0.0) or 0.0),
                    },
                )
                halign = int(primitive.get("halign", 0) or 0)
                valign = int(primitive.get("valign", 0) or 0)
                if halign or valign:
                    text.dxf.halign = halign
                    text.dxf.valign = valign
                    text.dxf.align_point = point(
                        primitive.get("align_point")
                        or primitive.get("insert")
                        or [0.0, 0.0]
                    )
            elif kind == "hatch":
                paths = primitive.get("paths") or []
                if not paths:
                    continue
                hatch = msp.add_hatch(dxfattribs=attribs)
                if primitive.get("solid"):
                    color = int(primitive.get("color", 7) or 7)
                    hatch.set_solid_fill(color=color if 1 <= color <= 255 else 7)
                else:
                    hatch.set_pattern_fill(
                        str(primitive.get("pattern") or "ANSI31"),
                        scale=float(primitive.get("scale", 1.0) or 1.0),
                        angle=float(primitive.get("angle", 0.0) or 0.0),
                    )
                for path in paths:
                    if len(path) >= 3:
                        hatch.paths.add_polyline_path(
                            [point(value) for value in path],
                            is_closed=True,
                        )
        except Exception:
            continue
    return True


def _section_body_edges(
    profiles: list[list[list[float]]],
    expected_width: float,
) -> tuple[float, float, float, float] | None:
    verticals: list[tuple[float, float, float]] = []
    for points in profiles:
        if len(points) < 2:
            continue
        loop = points + [points[0]]
        for p1, p2 in zip(loop, loop[1:]):
            if abs(float(p1[0]) - float(p2[0])) <= 0.5:
                y1, y2 = sorted((float(p1[1]), float(p2[1])))
                if y2 - y1 >= 25:
                    verticals.append((float(p1[0]), y1, y2))
    xs = sorted({round(x, 3) for x, _y1, _y2 in verticals})
    pairs = [
        (left, right) for pos, left in enumerate(xs)
        for right in xs[pos + 1:]
    ]
    if not pairs:
        return None
    left, right = min(
        pairs,
        key=lambda pair: abs((pair[1] - pair[0]) - expected_width),
    )
    relevant = [
        (y1, y2) for x, y1, y2 in verticals
        if abs(x - left) <= 0.5 or abs(x - right) <= 0.5
    ]
    return left, right, min(y1 for y1, _y2 in relevant), max(
        y2 for _y1, y2 in relevant
    )


def _draw_section_v2(msp: Any, view: dict[str, Any]) -> bool:
    raw = view.get("raw") or {}
    profiles = raw.get("concrete_profiles") or []
    if not profiles:
        return False

    x_shift = 100.0
    for points in profiles:
        shifted = [(x_shift + float(x), float(y)) for x, y in points]
        msp.add_lwpolyline(
            shifted,
            close=True,
            dxfattribs={"layer": "CONCRETO"},
        )
    for segment in raw.get("concrete_segments") or []:
        if len(segment) == 2:
            msp.add_line(
                (x_shift + float(segment[0][0]), float(segment[0][1])),
                (x_shift + float(segment[1][0]), float(segment[1][1])),
                dxfattribs={"layer": "CONCRETO"},
            )

    b = float(view.get("b_cm", 19) or 19)
    body = _section_body_edges(profiles, expected_width=2.0 * b)
    if body is None:
        return True
    left, right, bottom, top = body
    panel_t = 4.0
    wood_w = 14.0
    bottom_panel_h = 3.6

    def rect(x1: float, y1: float, x2: float, y2: float, layer: str) -> None:
        msp.add_lwpolyline(
            [
                (x_shift + x1, y1),
                (x_shift + x2, y1),
                (x_shift + x2, y2),
                (x_shift + x1, y2),
            ],
            close=True,
            dxfattribs={"layer": layer},
        )

    panel_layer = "PainÃ©is"
    rect(left - panel_t, bottom, left, top, panel_layer)
    rect(right, bottom, right + panel_t, top, panel_layer)
    rect(left, bottom - bottom_panel_h, right, bottom, panel_layer)

    rect(left - panel_t - wood_w, bottom, left - panel_t, top, "Madeira")
    rect(right + panel_t, bottom, right + panel_t + wood_w, top, "Madeira")
    rect(
        left - panel_t - wood_w,
        bottom - 4.4,
        left - panel_t,
        bottom,
        "Madeira",
    )
    rect(
        right + panel_t,
        bottom - 4.4,
        right + panel_t + wood_w,
        bottom,
        "Madeira",
    )

    text_h = 7.0
    msp.add_text(
        "a",
        dxfattribs={
            "insert": (x_shift + left - panel_t - wood_w / 2.0, (bottom + top) / 2.0),
            "height": text_h,
            "layer": "detalhes",
        },
    )
    msp.add_text(
        "b",
        dxfattribs={
            "insert": (x_shift + right + panel_t + 2.0, (bottom + top) / 2.0),
            "height": text_h,
            "layer": "detalhes",
        },
    )
    msp.add_text(
        "c",
        dxfattribs={
            "insert": (x_shift + (left + right) / 2.0 - 2.0, bottom - 1.0),
            "height": text_h,
            "layer": "detalhes",
        },
    )
    return True


def _panel_for_generator(seg: dict[str, Any]) -> dict[str, Any]:
    h1 = float(seg.get("height1", 0) or 0)
    slab_center = float(seg.get("slab_center", seg.get("laje_central_alt", 0)) or 0)
    central_alt = float(seg.get("laje_central_alt", slab_center) or slab_center)
    if h1 < 80.0:
        slab_center = 0.0
        central_alt = 0.0
    return {
        "width": float(seg.get("largura_cm", 0) or 0),
        "height1": h1,
        "height2": float(seg.get("height2", 0) or 0),
        "grade_h1": float(seg.get("grade_h1", 0) or 0),
        "grade_h2": float(seg.get("grade_h2", 0) or 0),
        "laje_central_alt": central_alt,
        "slab_center": slab_center,
        "laje_sup_local": float(seg.get("laje_sup_local", seg.get("slab_top", 0)) or 0),
        "laje_inf_local": float(seg.get("laje_inf_local", seg.get("slab_bottom", 0)) or 0),
        "slab_top": float(seg.get("slab_top", seg.get("laje_sup_local", 0)) or 0),
        "slab_bottom": float(seg.get("slab_bottom", seg.get("laje_inf_local", 0)) or 0),
        "reuse": bool(seg.get("reuse", False)),
        "reuse_regions": seg.get("reuse_regions", []),
        "panel_type": seg.get("panel_type", "Sarrafeado"),
        "codigos": seg.get("codigos_forma", []),
    }


def _image_stats(path: Path) -> dict[str, Any]:
    img = Image.open(path).convert("RGB")
    px = img.load()
    w, h = img.size
    nonblack = 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r > 25 or g > 25 or b > 25:
                nonblack += 1
    return {
        "width_px": w,
        "height_px": h,
        "nonblack_ratio": round(nonblack / max(w * h, 1), 5),
    }


def _basic_similarity(a_path: Path, b_path: Path) -> dict[str, Any]:
    if not a_path.exists() or not b_path.exists():
        return {"available": False}
    a = Image.open(a_path).convert("L").resize((512, 256))
    b = Image.open(b_path).convert("L").resize((512, 256))
    a_px = a.load()
    b_px = b.load()
    both = union = diff_sum = 0
    for y in range(256):
        for x in range(512):
            av = a_px[x, y] > 25
            bv = b_px[x, y] > 25
            if av and bv:
                both += 1
            if av or bv:
                union += 1
            diff_sum += abs(a_px[x, y] - b_px[x, y])
    return {
        "available": True,
        "mask_iou": round(both / max(union, 1), 4),
        "mean_abs_diff": round(diff_sum / (512 * 256), 2),
        "note": "coarse render metric only; final decision must use vision reasoning",
    }


def generate_face_unit(out_dir: Path, unit: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = int(unit.get("idx") or 0)
    visual_label = str(unit.get("label") or "")
    file_label = visual_label or f"face_{idx}_{unit.get('side') or 'X'}"
    side = str(unit.get("side") or "?")
    panels = [_panel_for_generator(seg) for seg in unit.get("segments", [])]
    h_body = float(unit.get("h_body", 0) or unit.get("h_total", 0) or 0)
    laje_sup = float(unit.get("laje_sup", 0) or 0)
    laje_inf = float(unit.get("laje_inf", 0) or 0)
    reverse_grade = str(unit.get("grade_layer_style") or "native") == "paineis"

    doc = setup_doc()
    msp = doc.modelspace()
    draw_lv_face(
        msp,
        0,
        0,
        panels,
        h_body,
        visual_label,
        holes=[],
        pillar_left={"active": False, "width": 0.0, "length": 0.0},
        pillar_right={"active": False, "width": 0.0, "length": 0.0},
        laje_sup=laje_sup,
        laje_inf=laje_inf,
        pontaletes_face=unit.get("pontaletes_face", 0),
        fallback_panel_ids=False,
        nom_height=8.0,
        reverse_grade_style=reverse_grade,
        suppress_sarrafo_spans=reverse_grade,
    )

    stem = f"n4_face_unit_{idx:02d}_{file_label.replace(' ', '_').replace('.', '_')}"
    dxf_path = out_dir / f"{stem}.dxf"
    png_path = out_dir / f"{stem}.png"
    doc.saveas(dxf_path)
    render_dxf_to_png(dxf_path, png_path, max_px=1600)
    return {
        "idx": idx,
        "label": visual_label,
        "side": side,
        "segments": len(panels),
        "dxf": dxf_path.name,
        "png": png_path.name,
        "png_stats": _image_stats(png_path),
    }


def generate_section(out_dir: Path, view: dict[str, Any]) -> dict[str, Any]:
    idx = int(view.get("idx") or 0)
    b = float(view.get("b_cm", 19) or 19)
    h = float(view.get("h_section", 0) or 0)
    h_a = float(view.get("h_A", h) or h)
    h_b = float(view.get("h_B", h) or h)
    raw_label = str(view.get("label") or f"section_{idx}")
    label = raw_label.replace("CONT.", "").strip().split()[0]
    label = label.replace(".A", "").replace(".B", "") or f"section_{idx}"

    doc = setup_doc()
    msp = doc.modelspace()
    used_primitives = _draw_section_visual_primitives(msp, view)
    used_v2 = False
    if not used_primitives:
        used_v2 = _draw_section_v2(msp, view)
    if not used_primitives and not used_v2:
        draw_section_detail(
            msp,
            100,
            0,
            b,
            h,
            viga_nome=label,
            b_alma=b,
            h_A=h_a,
            h_B=h_b,
        )

    stem = f"n4_section_{idx:02d}_{label.replace(' ', '_').replace('.', '_')}"
    dxf_path = out_dir / f"{stem}.dxf"
    png_path = out_dir / f"{stem}.png"
    doc.saveas(dxf_path)
    render_dxf_to_png(dxf_path, png_path, max_px=1000)
    return {
        "idx": idx,
        "label": label,
        "b_cm": b,
        "h_section": h,
        "generator": (
            "section_v3_visual_primitives"
            if used_primitives
            else "section_v2_geometry"
            if used_v2
            else "legacy_fixed_template"
        ),
        "dxf": dxf_path.name,
        "png": png_path.name,
        "png_stats": _image_stats(png_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sandbox N4 unit artifacts from LV N2 run.")
    parser.add_argument("--run-dir", required=True, help="Path to LV N2 loop run directory.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    canon_path = run_dir / "canonical_ficha.json"
    if not canon_path.exists():
        raise FileNotFoundError(canon_path)

    canon = json.loads(canon_path.read_text(encoding="utf-8"))
    out_dir = run_dir / "n4_validation"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    face_results = [generate_face_unit(out_dir, unit) for unit in canon.get("face_units", [])]
    section_results = [generate_section(out_dir, view) for view in canon.get("section_views", [])]

    n2_face_manifest = {}
    face_manifest_path = run_dir / "face_unit_renders.json"
    if face_manifest_path.exists():
        for item in json.loads(face_manifest_path.read_text(encoding="utf-8")):
            n2_face_manifest[int(item.get("idx") or 0)] = item.get("file")

    for item in face_results:
        n2_png = run_dir / str(n2_face_manifest.get(int(item["idx"]), ""))
        item["coarse_n2_n4_similarity"] = _basic_similarity(n2_png, out_dir / item["png"])

    manifest = {
        "source_run": str(run_dir),
        "viga": canon.get("viga"),
        "status": "generated_n4_unit_artifacts",
        "face_units": face_results,
        "sections": section_results,
        "decision": {
            "stage": "n4_artifacts_ready",
            "next": [
                "Run agent vision on each N4 PNG and matching N2 face_unit PNG.",
                "Compare section N4 PNG against N2 section evidence.",
                "Only then promote from 80 to 90+.",
            ],
        },
    }
    write_json(out_dir / "n4_validation_manifest.json", manifest)

    print(f"N4_VALIDATION_DIR={out_dir}")
    print(f"FACE_UNITS={len(face_results)}")
    print(f"SECTIONS={len(section_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
