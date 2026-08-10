#!/usr/bin/env python3
"""Authority matrix canônica do QA Global — anti-drift skill/squad/código.

SoT operacional de *validation_mode* no runtime: CLASS_REGISTRY em
``qa_evidence_auditor.py``. Este módulo e o JSON da squad devem espelhar o
registry; o teste CI falha se divergirem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = (
    REPO_ROOT / "squads" / "qa-global-evidencias" / "data" / "authority_matrix.json"
)
AUDITOR_PATH = REPO_ROOT / "scripts" / "arete" / "qa_evidence_auditor.py"
SKILL_AUTHORITY = Path.home() / ".claude" / "skills" / "qa-global-evidencias" / "references" / "authority-and-provenance.md"
# Segunda superfície de skill: o comando que o dono invoca (/CAD:QAGlobalEvidencias-AIOS).
# Ficou fora do CI até 2026-07-30 e derivou — declarava FV/LV diagnostic_only por 14 dias
# depois da promoção das duas classes na matrix v1.3.0.
SKILL_COMMAND = REPO_ROOT / ".claude" / "commands" / "CAD" / "QAGlobalEvidencias-AIOS.md"
SQUAD_YAML = REPO_ROOT / "squads" / "qa-global-evidencias" / "squad.yaml"
PIL_PROFILE = REPO_ROOT / "squads" / "qa-global-evidencias" / "data" / "class_profiles" / "pil.json"
MASTERPLAN = REPO_ROOT / "docs" / "MASTERPLAN-AGENTE-QA-GLOBAL.md"


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "arete.qa_authority_matrix/v1":
        raise ValueError(f"schema de authority matrix inválido: {path}")
    return payload


def class_entry(classe: str, matrix: dict[str, Any] | None = None) -> dict[str, Any]:
    matrix = matrix or load_matrix()
    key = classe.upper()
    entry = (matrix.get("classes") or {}).get(key)
    if not entry:
        raise KeyError(f"classe ausente na authority matrix: {key}")
    return entry


def class_validation_mode(classe: str, matrix: dict[str, Any] | None = None) -> str:
    return str(class_entry(classe, matrix)["validation_mode"])


def apply_allowed(classe: str, matrix: dict[str, Any] | None = None) -> bool:
    return bool(class_entry(classe, matrix).get("apply_allowed"))


def parse_registry_modes(auditor_path: Path = AUDITOR_PATH) -> dict[str, str]:
    """Extrai validation_mode do CLASS_REGISTRY sem importar o auditor (evita Qt/DB)."""
    text = auditor_path.read_text(encoding="utf-8")
    block_match = re.search(
        r"CLASS_REGISTRY\s*=\s*\{(.*?)\n\}",
        text,
        flags=re.DOTALL,
    )
    if not block_match:
        raise ValueError("CLASS_REGISTRY não encontrado em qa_evidence_auditor.py")
    block = block_match.group(1)
    modes: dict[str, str] = {}
    for classe in ("LAJ", "PIL", "FV", "LV"):
        class_block = re.search(
            rf'"{classe}"\s*:\s*\{{(.*?)\n\s*\}}',
            block,
            flags=re.DOTALL,
        )
        if not class_block:
            raise ValueError(f"classe {classe} ausente no CLASS_REGISTRY")
        mode = re.search(r'"validation_mode"\s*:\s*"([^"]+)"', class_block.group(1))
        if not mode:
            raise ValueError(f"validation_mode ausente para {classe}")
        modes[classe] = mode.group(1)
    return modes


def _squad_evolution_modes(squad_path: Path = SQUAD_YAML) -> dict[str, str]:
    text = squad_path.read_text(encoding="utf-8")
    # evolution.current_authority block
    modes: dict[str, str] = {}
    for classe in ("LAJ", "PIL", "FV", "LV"):
        match = re.search(rf"(?m)^\s*{classe}:\s*(\S+)\s*$", text)
        if match:
            modes[classe] = match.group(1).strip()
    return modes


def _skill_modes(skill_path: Path = SKILL_AUTHORITY) -> dict[str, str]:
    if not skill_path.is_file():
        return {}
    text = skill_path.read_text(encoding="utf-8")
    modes: dict[str, str] = {}
    for classe in ("LAJ", "PIL", "FV", "LV"):
        match = re.search(
            rf"(?m)^\|\s*{classe}\s*\|\s*`([^`]+)`",
            text,
        )
        if match:
            modes[classe] = match.group(1).strip()
    return modes


def _check_skill_surface(
    nome: str, path: Path, expected: dict[str, str], findings: list[dict[str, str]]
) -> dict[str, str]:
    """Confere uma superfície de skill e ACUSA ausência/silêncio (fail-closed).

    Regra: um arquivo que sumiu, foi renomeado ou parou de declarar a classe não pode
    virar 'ALIGNED'. Antes de 2026-07-30 o CI era fail-open — devolvia {} em arquivo
    ausente e as checagens eram `if skill and skill.get(classe)`, então um caminho
    errado desligava a verificação em silêncio.
    """
    if not path.is_file():
        findings.append({
            "severity": "HIGH",
            "layer": f"{nome}:arquivo_ausente",
            "classe": "*",
            "expected": f"arquivo legível em {path}",
            "actual": "<ausente>",
        })
        return {}
    modes = _skill_modes(path)
    for classe, mode in expected.items():
        atual = modes.get(classe)
        if atual is None:
            findings.append({
                "severity": "HIGH",
                "layer": f"{nome}:classe_nao_declarada",
                "classe": classe,
                "expected": mode,
                "actual": "<nao declarada>",
            })
        elif atual != mode:
            findings.append({
                "severity": "HIGH",
                "layer": nome,
                "classe": classe,
                "expected": mode,
                "actual": atual,
            })
    return modes


def _masterplan_pil_mode(path: Path = MASTERPLAN) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    # Prefer explicit validation_ready on PIL row if present
    if re.search(r"(?m)^\|\s*PIL\s*\|[^|]*\|[^|]*\|\s*`?validation_ready`?", text):
        return "validation_ready"
    if re.search(r"(?m)^\|\s*PIL\s*\|[^|]*\|[^|]*\|\s*`?coverage_ready", text):
        return "coverage_ready"
    if re.search(r"(?m)^\|\s*PIL\s*\|[^|]*\|[^|]*\|\s*`?diagnostic_only`?", text):
        return "diagnostic_only"
    return None


def validate_alignment(
    *,
    matrix_path: Path = MATRIX_PATH,
    auditor_path: Path = AUDITOR_PATH,
    skill_path: Path = SKILL_AUTHORITY,
    skill_command_path: Path = SKILL_COMMAND,
    squad_path: Path = SQUAD_YAML,
    masterplan_path: Path = MASTERPLAN,
    pil_profile_path: Path = PIL_PROFILE,
) -> dict[str, Any]:
    matrix = load_matrix(matrix_path)
    expected = {
        classe: str(entry["validation_mode"])
        for classe, entry in (matrix.get("classes") or {}).items()
    }
    registry = parse_registry_modes(auditor_path)
    findings: list[dict[str, str]] = []
    # Toda superfície que o agente pode carregar em runtime é verificada, fail-closed.
    skill = _check_skill_surface("skill_authority", skill_path, expected, findings)
    skill_command = _check_skill_surface(
        "skill_command", skill_command_path, expected, findings
    )
    squad = _squad_evolution_modes(squad_path)

    for classe, mode in expected.items():
        if registry.get(classe) != mode:
            findings.append({
                "severity": "CRITICAL",
                "layer": "CLASS_REGISTRY",
                "classe": classe,
                "expected": mode,
                "actual": registry.get(classe, "<missing>"),
            })
        if squad and squad.get(classe) and squad.get(classe) != mode:
            findings.append({
                "severity": "HIGH",
                "layer": "squad_evolution",
                "classe": classe,
                "expected": mode,
                "actual": squad.get(classe, "<missing>"),
            })

    pil_master = _masterplan_pil_mode(masterplan_path)
    if pil_master and pil_master != expected.get("PIL"):
        findings.append({
            "severity": "HIGH",
            "layer": "masterplan",
            "classe": "PIL",
            "expected": expected.get("PIL", ""),
            "actual": pil_master,
        })

    if pil_profile_path.is_file():
        profile = json.loads(pil_profile_path.read_text(encoding="utf-8"))
        auth = str(profile.get("authority") or "")
        # Profile may say validation_ready with limits; must not say pure diagnostic_only as sole mode
        if expected.get("PIL") == "validation_ready":
            if "diagnostic_only" in auth and "validation_ready" not in auth and "coverage_ready" not in auth:
                findings.append({
                    "severity": "HIGH",
                    "layer": "pil_profile",
                    "classe": "PIL",
                    "expected": "validation_ready (or coverage_ready with apply limits)",
                    "actual": auth,
                })
            promo = ((profile.get("n3") or {}).get("promotion_gate") or {}).get("current")
            # n3 promotion_gate.current may lag; flag if pure diagnostic while N1 is ready
            if promo == "diagnostic_only" and "validation_ready" not in auth:
                findings.append({
                    "severity": "MEDIUM",
                    "layer": "pil_profile_promotion_gate",
                    "classe": "PIL",
                    "expected": "reflect N1 validation_ready limits",
                    "actual": str(promo),
                })

    critical = [row for row in findings if row["severity"] == "CRITICAL"]
    return {
        "schema": "arete.qa_authority_alignment/v1",
        "matrix_version": matrix.get("version"),
        "expected": expected,
        "registry": registry,
        "skill": skill,
        "skill_command": skill_command,
        "squad": squad,
        "findings": findings,
        "aligned": not findings,
        "passed": not critical and not any(row["severity"] == "HIGH" for row in findings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=MATRIX_PATH)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = validate_alignment(matrix_path=args.matrix)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    if args.json or args.out:
        print(rendered, end="")
    else:
        status = "ALIGNED" if result["passed"] else "DRIFT"
        print(f"authority_matrix: {status} (findings={len(result['findings'])})")
        for row in result["findings"]:
            print(
                f"  [{row['severity']}] {row['layer']}.{row['classe']}: "
                f"expected={row['expected']} actual={row['actual']}"
            )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
