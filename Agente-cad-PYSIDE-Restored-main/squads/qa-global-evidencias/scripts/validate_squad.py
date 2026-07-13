#!/usr/bin/env python3
"""Auditoria estrutural determinística da squad QA Global de Evidências."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


DIMENSIONS = {
    "manifest": 15,
    "structure": 10,
    "agent": 15,
    "tasks": 15,
    "workflow": 10,
    "checklists_templates": 10,
    "command": 5,
    "cross_references": 10,
    "documentation": 10,
}


def _listed_files(manifest: dict, group: str) -> list[str]:
    rows = manifest.get("components", {}).get(group, [])
    result: list[str] = []
    for row in rows:
        if isinstance(row, str):
            result.append(row)
        elif isinstance(row, dict) and row.get("file"):
            result.append(str(row["file"]))
    return result


def audit(root: Path, command_file: Path) -> dict:
    manifest_path = root / "squad.yaml"
    findings: list[dict] = []
    scores = {name: 0 for name in DIMENSIONS}

    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - fatal path
        return {
            "score": 0,
            "grade": "F",
            "scores": scores,
            "findings": [{"severity": "CRITICAL", "message": f"manifest inválido: {exc}"}],
        }

    required = {"name", "version", "description", "icon", "team", "slashPrefix", "components"}
    missing = sorted(required - set(manifest))
    if not missing and manifest.get("team") == "CAD":
        scores["manifest"] = 15
    else:
        findings.append({"severity": "CRITICAL", "message": f"manifest incompleto: {missing}"})

    groups = ("agents", "tasks", "workflows", "checklists", "templates", "contracts", "scripts")
    referenced = [(group, rel) for group in groups for rel in _listed_files(manifest, group)]
    missing_files = [f"{group}:{rel}" for group, rel in referenced if not (root / rel).is_file()]
    if not missing_files:
        scores["structure"] = 10
    else:
        findings.append({"severity": "CRITICAL", "message": f"phantom files: {missing_files}"})

    agent_files = _listed_files(manifest, "agents")
    agent_text = "\n".join((root / rel).read_text(encoding="utf-8") for rel in agent_files if (root / rel).is_file())
    agent_markers = ("## Persona", "## Expert DNA", "## Comandos", "## Roteamento", "## Self-critique")
    if all(marker in agent_text for marker in agent_markers):
        scores["agent"] = 15
    else:
        findings.append({"severity": "HIGH", "message": "agente sem persona/commands/routing/self-critique completos"})

    task_files = _listed_files(manifest, "tasks")
    bad_tasks: list[str] = []
    for rel in task_files:
        path = root / rel
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if not text.startswith("---\n") or "inputs:" not in text or "outputs:" not in text:
            bad_tasks.append(rel)
    if task_files and not bad_tasks:
        scores["tasks"] = 15
    else:
        findings.append({"severity": "HIGH", "message": f"tasks sem frontmatter/IO: {bad_tasks}"})

    workflow_files = _listed_files(manifest, "workflows")
    workflow_ok = False
    for rel in workflow_files:
        payload = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
        workflow_ok = bool(payload.get("phases") and payload.get("participants") and payload.get("veto_conditions"))
    if workflow_ok:
        scores["workflow"] = 10
    else:
        findings.append({"severity": "HIGH", "message": "workflow sem fases/participantes/vetos"})

    supporting = _listed_files(manifest, "checklists") + _listed_files(manifest, "templates")
    if supporting and all((root / rel).is_file() for rel in supporting):
        scores["checklists_templates"] = 10
    else:
        findings.append({"severity": "MEDIUM", "message": "checklists/templates incompletos"})

    command_text = command_file.read_text(encoding="utf-8") if command_file.is_file() else ""
    if "QAGlobalEvidencias-AIOS" in command_file.name and "agents/aegis.md" in command_text:
        scores["command"] = 5
    else:
        findings.append({"severity": "HIGH", "message": "command file ausente ou sem agente registrado"})

    operation_map = manifest.get("operation_map", [])
    referenced_tasks = {row.get("task") for row in operation_map if isinstance(row, dict) and row.get("task")}
    task_ids = {row.get("id") for row in manifest.get("components", {}).get("tasks", []) if isinstance(row, dict)}
    contracts_ok = bool(_listed_files(manifest, "contracts"))
    if referenced_tasks <= task_ids and contracts_ok:
        scores["cross_references"] = 10
    else:
        findings.append({"severity": "HIGH", "message": "operation map ou contratos têm referência quebrada"})

    if (root / "README.md").is_file() and (root / "CHANGELOG.md").is_file() and (root / "data/team-manifest.md").is_file():
        scores["documentation"] = 10
    else:
        findings.append({"severity": "MEDIUM", "message": "README/CHANGELOG/team manifest incompletos"})

    total = sum(scores.values())
    grade = "S" if total >= 95 else "A" if total >= 85 else "B" if total >= 75 else "C" if total >= 65 else "D" if total >= 50 else "F"
    return {
        "schema_version": 1,
        "squad": manifest.get("name"),
        "score": total,
        "grade": grade,
        "scores": scores,
        "findings": findings,
        "passed": total >= 75 and not any(row["severity"] == "CRITICAL" for row in findings),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--command-file", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.command_file.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
