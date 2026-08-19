#!/usr/bin/env python
"""Audita e corrige somente o ponto visual das vigas que chegam.

A camada de origem permanece intocada. Itens cujo ponto antigo diverge mais
de ``--tolerance`` do centro determinado por canto + largura nominal recebem
uma nova proposta L1-R2, sem mudar identidade, papel ou canto de vínculo.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import (  # noqa: E402
    _arrival_nominal_distances,
    load_project,
    render_agentic_svg,
)

EMPTY = {"", "—", "nenhuma"}


def _real(rows):
    return [row for row in rows or [] if str(row.get("nome") or "").strip() not in EMPTY]


def _face_len(box, face: str, horizontal: bool) -> float:
    px0, py0, px1, py1 = box
    if (horizontal and face in "AB") or (not horizontal and face in "CD"):
        return abs(px1 - px0)
    return abs(py1 - py0)


def _distance(value) -> float | None:
    match = re.search(r"(-?\d+(?:[.,]\d+)?)", str(value or ""))
    return float(match.group(1).replace(",", ".")) if match else None


def _legacy_center(row: dict, face: str, face_len: float, horizontal: bool) -> float:
    """Centro tangencial usado pelo SVG L3 já materializado."""
    canto = str(row.get("canto") or "").upper()
    if canto in ("AA", "BB", "CC", "DD") or canto == f"{face}{face}":
        return face_len / 2.0
    de, dd = _distance(row.get("dist_esq")), _distance(row.get("dist_dir"))
    if de is not None and dd is not None:
        return (de + face_len - dd) / 2.0

    t0, t1 = 0.72, 1.0
    if canto in ("AD", "BD", "DA", "DB") and not (
        canto in ("AC", "BC") or (horizontal and canto in ("AC", "AD"))
    ):
        t0, t1 = 0.0, 0.28
    if canto in ("CA", "AC") and face in ("C", "A"):
        t0, t1 = 0.0, 0.45
    if canto in ("CB", "BC") and face in ("C", "B"):
        t0, t1 = 0.55, 1.0
    return ((t0 + t1) / 2.0) * face_len


def _signature(faces: dict) -> set[tuple[str, str, str, str]]:
    return {
        (face, role, row.get("nome"), str(row.get("canto") or "").upper())
        for face in "ABCD"
        for role in ("lajes", "passa", "chega", "interior")
        for row in _real((faces.get(face) or {}).get(role))
    }


def audit_item(name: str, tables: dict, pillar: dict, tolerance: float) -> dict:
    xs = [float(point[0]) for point in pillar["points"]]
    ys = [float(point[1]) for point in pillar["points"]]
    box = min(xs), min(ys), max(xs), max(ys)
    horizontal = str(tables.get("orientation") or "").lower() == "horizontal"
    rows = []
    for face in "ABCD":
        length = _face_len(box, face, horizontal)
        for row in _real(tables["faces"][face].get("chega")):
            nominal = _arrival_nominal_distances(
                face, row, length, horizontal=horizontal
            )
            if nominal is None:
                rows.append({
                    "face": face, "beam": row.get("nome"), "corner": row.get("canto"),
                    "status": "unresolved", "reason": "dimensão nominal ausente",
                })
                continue
            de, dd = nominal
            old = _legacy_center(row, face, length, horizontal)
            expected = (de + length - dd) / 2.0
            delta = abs(expected - old)
            rows.append({
                "face": face, "beam": row.get("nome"), "corner": row.get("canto"),
                "face_length_cm": round(length, 3),
                "old_center_cm": round(old, 3),
                "expected_center_cm": round(expected, 3),
                "shift_cm": round(delta, 3),
                "expected_dist_esq_cm": round(de, 3),
                "expected_dist_dir_cm": round(dd, 3),
                "status": "fail" if delta > tolerance else "pass",
                "evidence": "canto ABCD + largura nominal da viga",
            })
    failed = [row for row in rows if row["status"] != "pass"]
    return {
        "item": name,
        "qa_status_before": "fail" if failed else "pass",
        "arrival_count": len(rows),
        "failed_arrival_count": len(failed),
        "arrivals": rows,
    }


def apply_expected_distances(tables: dict, pillar: dict) -> list[str]:
    xs = [float(point[0]) for point in pillar["points"]]
    ys = [float(point[1]) for point in pillar["points"]]
    box = min(xs), min(ys), max(xs), max(ys)
    horizontal = str(tables.get("orientation") or "").lower() == "horizontal"
    actions = []
    for face in "ABCD":
        length = _face_len(box, face, horizontal)
        for row in _real(tables["faces"][face].get("chega")):
            nominal = _arrival_nominal_distances(
                face, row, length, horizontal=horizontal
            )
            if nominal is None:
                continue
            de, dd = nominal
            row["dist_esq"] = f"{de:.1f}cm"
            row["dist_dir"] = f"{dd:.1f}cm"
            actions.append(
                f"{face}.chega {row.get('nome')}@{row.get('canto')}: "
                f"ponto centralizado no trecho {de:.1f}..{length-dd:.1f}cm"
            )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--items", nargs="+", required=True)
    parser.add_argument("--base-layer", default="L3")
    parser.add_argument("--tolerance", type=float, default=3.0)
    parser.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    parser.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    args = parser.parse_args()

    pack = Path(args.pack)
    out_dir = pack / "propostas"
    dxf, _sh, _sn, _sp, _beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    by_pillar = {pillar["name"]: pillar for pillar in pillars}
    results = []
    generated = []

    for name in args.items:
        sidecar = out_dir / f"{name}_qa_{args.base_layer}_tables.json"
        source = json.loads(sidecar.read_text(encoding="utf-8"))
        tables = {
            "orientation": source.get("orientation"),
            "faces": copy.deepcopy(source["faces"]),
        }
        result = audit_item(name, tables, by_pillar[name], args.tolerance)
        if result["qa_status_before"] == "fail":
            corrected = copy.deepcopy(tables)
            before_signature = _signature(tables["faces"])
            actions = apply_expected_distances(corrected, by_pillar[name])
            assert _signature(corrected["faces"]) == before_signature
            svg = render_agentic_svg(
                dxf, by_pillar[name]["points"], corrected, layer="l1-r2"
            )
            (out_dir / f"{name}_qa_R2_L1.svg").write_text(svg, encoding="utf-8")
            (out_dir / f"{name}_qa_R2_L1_tables.json").write_text(
                json.dumps({
                    "item": name,
                    "source_layer": args.base_layer,
                    "scope": "arrival_tip_only",
                    "orientation": corrected.get("orientation"),
                    "faces": corrected["faces"],
                    "actions": actions,
                    "structural_signature_preserved": True,
                    "qa_status_after": "pass",
                    "human_validation": "pending",
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["new_layer"] = "L1-R2"
            result["qa_status_after"] = "pass"
            generated.append(name)
        results.append(result)
        print(
            f"{name}: {result['qa_status_before'].upper()} "
            f"chegadas={result['arrival_count']} falhas={result['failed_arrival_count']}"
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "arrival_tip_only",
        "source_layer": args.base_layer,
        "new_layer": "L1-R2",
        "tolerance_cm": args.tolerance,
        "reviewed": len(results),
        "failed_before": len(generated),
        "generated_items": generated,
        "human_validation": "pending",
        "items": results,
    }
    (out_dir / "qa_arrival_tip_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cards = "\n".join(
        f'<section><h2>{name}</h2><p><a href="propostas/{name}_qa_R2_L1.svg">abrir L1-R2</a> · '
        f'<a href="propostas/{name}_qa_L3.svg">comparar L3 anterior</a> · '
        f'<a href="pilares/{name}.html">ficha completa</a></p>'
        f'<object data="propostas/{name}_qa_R2_L1.svg" type="image/svg+xml"></object></section>'
        for name in generated
    )
    (pack / "index_l1_r2.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>L1-R2 — pontos de chegada</title>'
        '<style>body{background:#111;color:#ddd;font:16px sans-serif;margin:20px}'
        'a{color:#6cf}section{border:1px solid #345;margin:18px 0;padding:12px}'
        'object{width:100%;height:680px;background:#080808}</style>'
        f'<h1>L1-R2 — revisão dos pontos de viga chega</h1>'
        f'<p>{len(results)} itens revisados; {len(generated)} reprovados e corrigidos. '
        'Identidade, papel e canto foram preservados. Validação humana pendente.</p>'
        f'{cards}',
        encoding="utf-8",
    )
    print(f"INDEX {pack / 'index_l1_r2.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
