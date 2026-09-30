"""Revisões de dependências, sem invalidar ou escrever resultados estruturais."""
from __future__ import annotations

from pathlib import Path

from .sources import _sha256, resolve_crop_source


def changed_sources(obra_dir, sources):
    changed = []
    for source in sources:
        try:
            if source.get("kind") == "raw_level_reference":
                root = Path(obra_dir).resolve()
                current_path = (root / source["relative_path"]).resolve()
                if (root not in current_path.parents or not current_path.is_file()
                        or _sha256(current_path) != source["revision"]):
                    changed.append(source["source_id"])
                continue
            current = resolve_crop_source(
                obra_dir=obra_dir, obra_id=source["obra_id"],
                pavimento_id=source["pavimento_id"], bruto_id=source["bruto_id"],
                item_id=source["item_id"],
            )
            requires_validation = source.get("kind") != "level_convention"
            if current.revision != source["revision"] or (requires_validation and not current.validated):
                changed.append(source["source_id"])
        except (OSError, ValueError):
            changed.append(source["source_id"])
    return changed


def stale_modules(dependencies, changed):
    """Detalhes sem consumidor não invalida módulos de torre."""
    changed = set(changed)
    return sorted(name for name, ids in dependencies.items() if changed.intersection(ids))
