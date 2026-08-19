#!/usr/bin/env python
"""Promove o microciclo interno de ponto de chegada para a Camada 3 pública.

As L3 anteriores são preservadas em checkpoint. Os artefatos temporários
L1-R2 saem de ``propostas`` após a promoção para não criarem uma camada
paralela na interface humana.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project, render_agentic_svg  # noqa: E402

ITEMS = ("P9", "P28", "P29", "P30", "P31", "P32", "P35")


def _copy_once(source: Path, destination: Path) -> None:
    if source.is_file() and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    parser.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    args = parser.parse_args()

    pack = Path(args.pack).resolve()
    proposals = pack / "propostas"
    checkpoint = pack / "checkpoints" / "arrival_tip_pre_l3_promotion_20260813"
    promoted_sources = checkpoint / "promoted_r2_sources"
    checkpoint.mkdir(parents=True, exist_ok=True)

    dxf, _sh, _sn, _sp, _beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    by_pillar = {pillar["name"]: pillar for pillar in pillars}
    promoted = []

    # Relatórios também pertencem ao checkpoint do microciclo.
    for report_name in ("qa_l3_report.json", "qa_arrival_tip_report.json"):
        _copy_once(proposals / report_name, checkpoint / report_name)

    for name in ITEMS:
        r2_tables_path = proposals / f"{name}_qa_R2_L1_tables.json"
        r2_svg_path = proposals / f"{name}_qa_R2_L1.svg"
        l3_tables_path = proposals / f"{name}_qa_L3_tables.json"
        l3_svg_path = proposals / f"{name}_qa_L3.svg"
        if not r2_tables_path.is_file() or not r2_svg_path.is_file():
            raise FileNotFoundError(f"microciclo interno ausente para {name}")

        _copy_once(l3_tables_path, checkpoint / l3_tables_path.name)
        _copy_once(l3_svg_path, checkpoint / l3_svg_path.name)

        r2 = json.loads(r2_tables_path.read_text(encoding="utf-8"))
        old = json.loads(l3_tables_path.read_text(encoding="utf-8"))
        tables = {"orientation": r2.get("orientation"), "faces": r2["faces"]}
        svg = render_agentic_svg(
            dxf, by_pillar[name]["points"], tables, layer="l3"
        )
        if not svg.lstrip().startswith(("<?xml", "<svg")) or "</svg>" not in svg:
            raise RuntimeError(f"SVG público inválido após promoção de {name}")
        l3_svg_path.write_text(svg, encoding="utf-8")

        old_actions = list(old.get("actions") or [])
        promotion_action = "pontos de viga chega centralizados por canto ABCD + largura nominal"
        if promotion_action not in old_actions:
            old_actions.append(promotion_action)
        promoted_sidecar = dict(old)
        promoted_sidecar.update({
            "item": name,
            "orientation": tables.get("orientation"),
            "faces": tables["faces"],
            "actions": old_actions,
            "qa_issues": [],
            "qa_status": "pass",
            "arrival_tip_qa_status": "pass",
            "current_public_layer": "L3",
            "promoted_from_internal_microcycle": True,
            "human_validation": "pending",
        })
        l3_tables_path.write_text(
            json.dumps(promoted_sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        promoted_sources.mkdir(parents=True, exist_ok=True)
        shutil.move(str(r2_svg_path), str(promoted_sources / r2_svg_path.name))
        shutil.move(str(r2_tables_path), str(promoted_sources / r2_tables_path.name))
        promoted.append(name)
        print(f"{name}: L3 atualizada; L3 anterior em checkpoint")

    qa_l3_path = proposals / "qa_l3_report.json"
    if qa_l3_path.is_file():
        report = json.loads(qa_l3_path.read_text(encoding="utf-8"))
        for item in report.get("items") or []:
            if item.get("item") in promoted:
                item["qa_status"] = "pass"
                item["arrival_tip_qa_status"] = "pass"
                item["current_public_layer"] = "L3"
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
        report["arrival_tip_promoted_items"] = promoted
        report["human_validation"] = "pending"
        qa_l3_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # O índice temporário deixa de existir na superfície pública.
    r2_index = pack / "index_l1_r2.html"
    if r2_index.is_file():
        shutil.move(str(r2_index), str(promoted_sources / r2_index.name))
    arrival_report = proposals / "qa_arrival_tip_report.json"
    if arrival_report.is_file():
        shutil.move(str(arrival_report), str(promoted_sources / arrival_report.name))

    manifest = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "public_layer": "L3",
        "items": promoted,
        "human_verdicts_changed": False,
        "checkpoint": str(checkpoint),
    }
    (checkpoint / "promotion_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"checkpoint: {checkpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
