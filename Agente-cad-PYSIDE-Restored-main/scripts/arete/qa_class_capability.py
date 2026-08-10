#!/usr/bin/env python3
"""Valida o mapa de capacidade do agente por classe (paridade PIL/LAJ/FV/LV).

Não avança domínio de obra: só confere que cada classe tem a mesma robustez
estrutural (arquivos, authority, golden/g2v runners, microciclos comuns).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MATRIX = (
    REPO / "squads" / "qa-global-evidencias" / "data" / "class_capability_matrix.json"
)
REQUIRED_KEYS = (
    "validation_mode", "adapter", "profile", "proveniencia", "quadro",
    "diagnostico_n1n2", "disclaimer_surface", "golden_n1", "g2v",
    "tests", "agent_microcycles",
)
COMMON_MICRO = {
    "discover", "review-n1", "probe-n1", "probe-profile",
    "parity", "smoke-n3", "review-artifact", "visual", "loop",
}


def load_matrix(path: Path = MATRIX) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path: Path = MATRIX) -> dict:
    matrix = load_matrix(path)
    findings: list[dict] = []
    classes = matrix.get("classes") or {}
    if set(classes) != {"PIL", "LAJ", "FV", "LV"}:
        findings.append({
            "severity": "HIGH",
            "message": f"classes incompletas: {sorted(classes)}",
        })

    from scripts.arete.qa_authority_matrix import parse_registry_modes
    registry = parse_registry_modes()

    for classe, entry in classes.items():
        for key in REQUIRED_KEYS:
            if key not in entry:
                findings.append({"severity": "HIGH", "classe": classe, "message": f"missing {key}"})
        mode = entry.get("validation_mode")
        if registry.get(classe) and registry.get(classe) != mode:
            findings.append({
                "severity": "CRITICAL",
                "classe": classe,
                "message": f"authority drift matrix={mode} registry={registry.get(classe)}",
            })
        paths = [
            entry.get("profile"),
            entry.get("proveniencia"),
            entry.get("quadro"),
            entry.get("diagnostico_n1n2"),
            entry.get("disclaimer_surface"),
            (entry.get("adapter") or {}).get("module"),
            (entry.get("golden_n1") or {}).get("runner"),
            (entry.get("g2v") or {}).get("runner"),
        ]
        if entry.get("coverage_adapter"):
            paths.append(entry["coverage_adapter"])
        for rel in paths:
            if not rel:
                continue
            if not (REPO / rel).is_file():
                findings.append({
                    "severity": "HIGH",
                    "classe": classe,
                    "message": f"missing file {rel}",
                })
        for rel in entry.get("tests") or []:
            if not (REPO / rel).is_file():
                findings.append({
                    "severity": "MEDIUM",
                    "classe": classe,
                    "message": f"missing test {rel}",
                })
        micros = set(entry.get("agent_microcycles") or [])
        missing_m = sorted(COMMON_MICRO - micros)
        if missing_m:
            findings.append({
                "severity": "HIGH",
                "classe": classe,
                "message": f"microciclos comuns ausentes: {missing_m}",
            })

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    high = [f for f in findings if f["severity"] == "HIGH"]
    return {
        "schema": "arete.qa_class_capability_validation/v1",
        "matrix_version": matrix.get("version"),
        "findings": findings,
        "passed": not critical and not high,
        "parity": {
            "classes": sorted(classes),
            "common_microcycles": sorted(COMMON_MICRO),
            "registry": registry,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(args.matrix)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PARITY_OK" if result["passed"] else "PARITY_GAP"
        print(f"class_capability: {status} findings={len(result['findings'])}")
        for row in result["findings"]:
            cls = row.get("classe", "-")
            print(f"  [{row['severity']}] {cls}: {row['message']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
