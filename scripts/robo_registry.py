#!/usr/bin/env python3
"""Loader do registro plugavel de extratores N2 e robos N3/N4."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .classe_registry import load_registry, registered_classes
except ImportError:
    from classe_registry import load_registry, registered_classes

DEFAULT_REGISTRY_PATH = Path("D:/Agente-cad-PYSIDE/data/robo_registry.json")
DEFAULT_MODULES_DIR = Path(
    "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts"
)


def validate_robot_registry(
    registry: dict[str, Any],
    *,
    class_registry_path: str | Path | None = None,
) -> None:
    if registry.get("schema_version") != 1:
        raise ValueError("robo_registry.schema_version deve ser 1")
    entries = registry.get("classes")
    if not isinstance(entries, list) or not entries:
        raise ValueError("robo_registry deve declarar classes")

    known_classes = registered_classes(load_registry(class_registry_path))
    seen: set[str] = set()
    for entry in entries:
        class_id = str(entry.get("class_id") or "").strip().upper()
        if not class_id or class_id not in known_classes:
            raise ValueError(f"classe desconhecida no robo_registry: {class_id or '<vazia>'}")
        if class_id in seen:
            raise ValueError(f"classe duplicada no robo_registry: {class_id}")
        seen.add(class_id)
        for component in ("extractor", "robot"):
            descriptor = entry.get(component)
            if not isinstance(descriptor, dict):
                raise ValueError(f"{class_id}.{component} ausente")
            if not descriptor.get("module") or not descriptor.get("callable"):
                raise ValueError(f"{class_id}.{component} requer module e callable")
        scopes = entry["robot"].get("artifact_scope")
        if not isinstance(scopes, list) or not set(scopes) <= {"N3", "N4"}:
            raise ValueError(f"{class_id}.robot.artifact_scope invalido")


def load_robot_registry(
    path: str | Path | None = None,
    *,
    class_registry_path: str | Path | None = None,
) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_robot_registry(registry, class_registry_path=class_registry_path)
    return registry


def get_class_plugin(class_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    target = str(class_id or "").strip().upper()
    for entry in registry["classes"]:
        if str(entry["class_id"]).upper() == target:
            return entry
    raise KeyError(f"classe sem plugin: {target}")


def audit_module_contracts(
    registry: dict[str, Any],
    *,
    modules_dir: str | Path = DEFAULT_MODULES_DIR,
) -> list[dict[str, Any]]:
    modules_dir = Path(modules_dir)
    results = []
    for entry in registry["classes"]:
        for component in ("extractor", "robot"):
            descriptor = entry[component]
            module_path = modules_dir / f"{descriptor['module']}.py"
            callable_found = False
            if module_path.exists():
                source = module_path.read_text(encoding="utf-8", errors="replace")
                callable_found = (
                    f"def {descriptor['callable']}(" in source
                    or f"class {descriptor['callable']}(" in source
                )
            results.append(
                {
                    "class_id": entry["class_id"],
                    "component": component,
                    "module_path": str(module_path),
                    "module_found": module_path.exists(),
                    "callable": descriptor["callable"],
                    "callable_found": callable_found,
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--modules-dir", default=str(DEFAULT_MODULES_DIR))
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    registry = load_robot_registry(args.registry)
    result = audit_module_contracts(registry, modules_dir=args.modules_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.audit and not all(row["callable_found"] for row in result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
