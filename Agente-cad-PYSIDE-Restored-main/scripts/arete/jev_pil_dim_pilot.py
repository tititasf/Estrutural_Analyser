"""Read-only pilot: N1 pillar dimension text versus deterministic and Jev choices.

The reference is the four-corner CAD polygon for simple rectangular pillars.
It is deliberately independent of N2 and of the N1 `dim` text value. Special
pillars are excluded from this narrow probe, and no result is applied to N1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import escape
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT.parent
DB = BASE / "project_data.vision"
PROJECT_ID = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"
DXF = BASE / "DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf"
PILLAR_SNAPSHOT: Path | None = None
DIM_RE = re.compile(r"^\s*(\d{1,3}(?:[.,]\d+)?)\s*[/xX×]\s*(\d{1,3}(?:[.,]\d+)?)\s*$")
DEFAULT_ITEMS = ("P1", "P2", "P10", "P15", "P19", "P20", "P21", "P22", "P30", "P35")


@dataclass(frozen=True)
class TextEntity:
    handle: str
    layer: str
    text: str
    x: float
    y: float


def dimension(text: str | None) -> tuple[float, float] | None:
    match = DIM_RE.fullmatch(str(text or ""))
    if not match:
        return None
    return tuple(sorted(float(s.replace(",", ".")) for s in match.groups()))


def pair_matches(a: tuple[float, float] | None, b: tuple[float, float], tol: float = 0.1) -> bool:
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def rectangular_reference(points: list) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Only accept a clear axis-aligned four-corner CAD polygon."""
    xy = [(float(p[0]), float(p[1])) for p in points]
    if len(xy) == 5 and math.dist(xy[0], xy[-1]) < 0.01:
        xy.pop()
    if len(xy) != 4:
        return None
    xs, ys = sorted({round(x, 3) for x, _ in xy}), sorted({round(y, 3) for _, y in xy})
    if len(xs) != 2 or len(ys) != 2:
        return None
    if {(round(x, 3), round(y, 3)) for x, y in xy} != {(x, y) for x in xs for y in ys}:
        return None
    sides = tuple(sorted((xs[1] - xs[0], ys[1] - ys[0])))
    # This experiment is deliberately about ordinary pillars only.
    if not (14 <= sides[0] <= 40 and sides[0] <= sides[1] <= 130):
        return None
    return ((sum(xs) / 2, sum(ys) / 2), sides)


def load_inputs() -> tuple[list[dict], list[TextEntity], float]:
    if PILLAR_SNAPSHOT:
        source = json.loads(PILLAR_SNAPSHOT.read_text(encoding="utf-8-sig"))
        if source["project_id"] != PROJECT_ID:
            raise ValueError("pillar snapshot project id mismatch")
        rows = [(row["name"], json.dumps(row["points"]), json.dumps(row["links"]), json.dumps(row["extra"]))
                for row in source["pillars"]]
    else:
        c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
        try:
            rows = list(c.execute(
                "SELECT name,points_json,links_json,extra_data_json FROM pillars WHERE project_id=? ORDER BY name",
                (PROJECT_ID,),
            ))
        finally:
            c.close()
    pillars = []
    for name, points, links, extra in rows:
        ref = rectangular_reference(json.loads(points or "[]"))
        if ref:
            center, sides = ref
            extra_obj = json.loads(extra or "{}")
            xy = [(float(p[0]), float(p[1])) for p in json.loads(points or "[]")]
            bbox = (min(x for x, _ in xy), min(y for _, y in xy),
                    max(x for x, _ in xy), max(y for _, y in xy))
            pillars.append({"name": name, "center": center, "reference": sides, "bbox": bbox,
                            "n1_dim": extra_obj.get("dim"), "links": json.loads(links or "{}")})
    start = time.perf_counter()
    doc = ezdxf.readfile(str(DXF))
    parse_seconds = time.perf_counter() - start
    texts = []
    for entity in doc.modelspace():
        if entity.dxftype() != "TEXT":
            continue
        try:
            x, y = entity.dxf.insert.x, entity.dxf.insert.y
            texts.append(TextEntity(entity.dxf.handle, entity.dxf.layer, str(entity.dxf.text), float(x), float(y)))
        except (AttributeError, ValueError, TypeError):
            continue
    return pillars, texts, parse_seconds


def candidates(pillar: dict, texts: list[TextEntity], radius: float = 190, limit: int = 12) -> list[dict]:
    cx, cy = pillar["center"]
    near = []
    for entity in texts:
        distance = math.hypot(entity.x - cx, entity.y - cy)
        if distance <= radius:
            near.append({"id": entity.handle, "text": entity.text, "layer": entity.layer,
                         "x": round(entity.x, 3), "y": round(entity.y, 3),
                         "distance_cad_units": round(distance, 3),
                         "is_dimension_syntax": dimension(entity.text) is not None})
    near.sort(key=lambda row: (row["distance_cad_units"], row["id"]))
    return near[:limit]


def deterministic_choice(rows: list[dict], reference: tuple[float, float] | None = None) -> str | None:
    valid = [r for r in rows if r["layer"] == "3" and dimension(r["text"]) is not None]
    if reference is not None:
        valid = [r for r in valid if pair_matches(dimension(r["text"]), reference)]
    return min(valid, key=lambda r: r["distance_cad_units"])["id"] if valid else None


def svg_state(pillar: dict, rows: list[dict]) -> str:
    """Compact semantic SVG: original CAD positions/text, local origin for clarity."""
    cx, cy = pillar["center"]
    x0, y0, x1, y1 = pillar["bbox"]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-190 -190 380 380">',
             '<title>CAD neighborhood around an unlabeled pillar; source coordinates in CAD drawing units</title>',
             '<rect id="target-pillar" x="{:.3f}" y="{:.3f}" width="{:.3f}" height="{:.3f}" fill="none" stroke="black"/>'.format(
                 x0 - cx, cy - y1, x1 - x0, y1 - y0)]
    for row in rows:
        parts.append('<text id="{}" data-layer="{}" x="{:.3f}" y="{:.3f}">{}</text>'.format(
            escape(row["id"]), escape(row["layer"]), row["x"] - cx, cy - row["y"], escape(row["text"])))
    parts.append("</svg>")
    return "".join(parts)


def svg_to_json(svg: str) -> tuple[dict, list[dict]]:
    """Parse the actual SVG document, retaining its target and text coordinates."""
    root = ET.fromstring(svg)
    namespace = {"s": "http://www.w3.org/2000/svg"}
    rect = root.find("s:rect", namespace)
    if rect is None or rect.attrib.get("id") != "target-pillar":
        raise ValueError("semantic SVG has no target pillar")
    target = {k: float(rect.attrib[k]) for k in ("x", "y", "width", "height")}
    parsed = []
    for node in root.findall("s:text", namespace):
        text = "".join(node.itertext())
        x, y = float(node.attrib["x"]), float(node.attrib["y"])
        parsed.append({
            "id": node.attrib["id"], "layer": node.attrib["data-layer"],
            "text": text, "x_svg": x, "y_svg": y,
            "distance_svg_units": round(math.hypot(x, y), 3),
        })
    return {"source": "parsed semantic SVG generated from the original structural DXF",
            "viewBox": root.attrib.get("viewBox"), "target_rect": target,
            "texts_near_target": parsed}, parsed


def jev_choice(client, state: dict | str, rows: list[dict]) -> tuple[str | None, dict]:
    from typesafe_sdk import Choice

    # The option IDs are CAD handles. An explicit abstention keeps absence distinct.
    options = {r["id"]: f"CAD text '{r['text']}' on layer {r['layer']}" for r in rows}
    options["INSUFFICIENT"] = "No supplied text can be reliably associated with the pillar dimension."
    question = Choice(
        instructions=("Select the CAD text entity that states the cross-section dimensions "
                      "of the target pillar. Other texts may be beam dimensions, pillar names, "
                      "heights or notes. Prefer direct local evidence. Return INSUFFICIENT if "
                      "none is supported. Do not calculate or invent a dimension."),
        criteria=options,
    )
    started = time.perf_counter()
    response = client.system_one(state=state, questions={"dimension_text": question})
    answer = response.choices["dimension_text"]
    selected = str(answer.choice)
    result = {
        "model": response.model,
        "selected_handle": None if selected == "INSUFFICIENT" else selected,
        "confidence": answer.confidence,
        "probabilities": answer.probabilities,
        "latency_s": round(time.perf_counter() - started, 3),
        "input_tokens": response.usage.input_tokens if response.usage else None,
    }
    return result["selected_handle"], result


def main() -> int:
    global PROJECT_ID, DXF, PILLAR_SNAPSHOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default=PROJECT_ID)
    parser.add_argument("--dxf", type=Path, default=DXF)
    parser.add_argument("--pillar-snapshot-json", type=Path, help="read-only export from the matching N1 database")
    parser.add_argument("--items", nargs="*", default=list(DEFAULT_ITEMS))
    parser.add_argument("--all-eligible", action="store_true")
    parser.add_argument("--drop-reference-text", action="store_true",
                        help="Negative probe: remove every candidate matching the CAD polygon dimension.")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--mode", choices=("offline", "json", "svg", "svg-json", "both", "all"), default="offline")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    PROJECT_ID, DXF, PILLAR_SNAPSHOT = args.project_id, args.dxf.resolve(), args.pillar_snapshot_json
    if not DXF.exists():
        parser.error("DXF not found")
    if args.max_items < 1 or args.max_items > 500:
        parser.error("--max-items must be between 1 and 500")
    pillars, texts, parse_seconds = load_inputs()
    available = {p["name"]: p for p in pillars}
    requested = list(available) if args.all_eligible else args.items
    selected = [available[n] for n in requested if n in available][:args.max_items]
    if not selected:
        parser.error("none of the requested items is a simple rectangular pillar")
    if args.mode != "offline":
        from dotenv import load_dotenv
        from typesafe_sdk import TypeSafeClient
        load_dotenv(ROOT / ".env")
        if not os.getenv("TYPESAFE_API_KEY"):
            parser.error("TYPESAFE_API_KEY is absent; no API call was made")
        client = TypeSafeClient(model="jev-1.13.0")
    else:
        client = None
    outputs = []
    try:
        for pillar in selected:
            rows = candidates(pillar, texts)
            reference = pillar["reference"]
            if args.drop_reference_text:
                rows = [r for r in rows if not pair_matches(dimension(r["text"]), reference)]
            by_id = {r["id"]: r for r in rows}
            record = {
                "item": pillar["name"], "reference_from_polygon_cad_units": reference,
                "reference_text_removed": args.drop_reference_text,
                "n1_dim_text": pillar["n1_dim"], "n1_correct": pair_matches(dimension(pillar["n1_dim"]), reference),
                "candidates": rows, "candidate_has_reference": any(pair_matches(dimension(r["text"]), reference) for r in rows),
                "deterministic_nearest": deterministic_choice(rows),
                "deterministic_geometry": deterministic_choice(rows, reference),
                "jev": {},
            }
            arms = ("json", "svg", "svg-json") if args.mode == "all" else (
                ("json", "svg") if args.mode == "both" else (args.mode,) if args.mode != "offline" else ())
            for arm in arms:
                arm_rows = rows
                if arm == "json":
                    state = {"target": "unlabeled axis-aligned rectangular pillar",
                             "target_center_cad_units": [round(v, 3) for v in pillar["center"]],
                             "polygon_side_lengths_cad_units": reference,
                             "texts_near_target": rows}
                elif arm == "svg-json":
                    state, parsed_rows = svg_to_json(svg_state(pillar, rows))
                    if {r["id"] for r in parsed_rows} != set(by_id):
                        raise ValueError("SVG-to-JSON entity set differs from DXF candidates")
                    arm_rows = parsed_rows
                else:
                    state = svg_state(pillar, rows)
                try:
                    choice, result = jev_choice(client, state, arm_rows)
                    result["selected_text"] = by_id[choice]["text"] if choice in by_id else None
                    result["correct"] = pair_matches(dimension(result["selected_text"]), reference)
                    record["jev"][arm] = result
                except Exception as exc:
                    record["jev"][arm] = {"error_type": type(exc).__name__, "error": str(exc)[:240]}
            outputs.append(record)
    finally:
        if client is not None:
            client.close()
    result = {
        "purpose": "PIL N1 versus local CAD geometry and Jev; N2 unused",
        "project_id": PROJECT_ID,
        "dxf_sha256": hashlib.sha256(DXF.read_bytes()).hexdigest(),
        "dxf_insunits_header": ezdxf.readfile(str(DXF)).header.get("$INSUNITS"),
        "dxf_parse_seconds": round(parse_seconds, 3),
        "msp_text_count": len(texts), "simple_rectangular_pillars": len(pillars),
        "tested": len(outputs), "mode": args.mode, "items": outputs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"tested": len(outputs), "n1_correct": sum(r["n1_correct"] for r in outputs),
               "nearest_correct": sum(pair_matches(dimension(next((c["text"] for c in r["candidates"] if c["id"] == r["deterministic_nearest"]), None)), r["reference_from_polygon_cad_units"]) for r in outputs),
               "geometry_correct": sum(r["deterministic_geometry"] is not None for r in outputs),
               "jev_json_correct": sum(r["jev"].get("json", {}).get("correct", False) for r in outputs),
               "jev_svg_correct": sum(r["jev"].get("svg", {}).get("correct", False) for r in outputs),
               "jev_svg_json_correct": sum(r["jev"].get("svg-json", {}).get("correct", False) for r in outputs),
               "api_errors": sum("error_type" in arm for r in outputs for arm in r["jev"].values())}
    print(json.dumps(summary, ensure_ascii=False))
    print(args.output)
    return 0 if summary["api_errors"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
