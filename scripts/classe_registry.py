#!/usr/bin/env python3
"""Registro declarativo de classes e dimensoes do Cerebro RAG."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_PATH = Path("D:/Agente-cad-PYSIDE/data/classe_registry.json")


def _normalized(value: Any) -> str:
    return str(value or "").strip().upper()


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schema_version") != 1:
        raise ValueError("classe_registry.schema_version deve ser 1")

    dimensions = registry.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != 8:
        raise ValueError("classe_registry deve declarar exatamente 8 dimensoes")
    dimension_ids = [item.get("id") for item in dimensions if isinstance(item, dict)]
    if sorted(dimension_ids) != list(range(1, 9)):
        raise ValueError("IDs das dimensoes devem ser unicos e cobrir 1..8")

    classes = registry.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValueError("classe_registry deve declarar ao menos uma classe")

    claimed_names: dict[str, str] = {}
    for item in classes:
        if not isinstance(item, dict):
            raise ValueError("cada classe deve ser um objeto")
        class_id = _normalized(item.get("id"))
        if not class_id:
            raise ValueError("classe sem id")
        for name in [class_id, *(item.get("aliases") or [])]:
            normalized = _normalized(name)
            owner = claimed_names.get(normalized)
            if owner and owner != class_id:
                raise ValueError(f"alias duplicado '{normalized}' em {owner} e {class_id}")
            claimed_names[normalized] = class_id


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_registry(registry)
    return registry


def alias_map(registry: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in registry["classes"]:
        class_id = _normalized(item["id"])
        result[class_id] = class_id
        for alias in item.get("aliases") or []:
            result[_normalized(alias)] = class_id
    return result


def canonicalize_class(value: Any, registry: dict[str, Any]) -> tuple[str, bool]:
    raw = _normalized(value) or "?"
    canonical = alias_map(registry).get(raw)
    if canonical:
        return canonical, True
    return raw, False


def registered_classes(registry: dict[str, Any], *, enabled_only: bool = True) -> set[str]:
    return {
        _normalized(item["id"])
        for item in registry["classes"]
        if not enabled_only or item.get("enabled", True)
    }
