"""Runner isolado da fundação do pré-processamento.

Publica inventário e leituras parciais de convenções/pilares. Os módulos ainda
não suportados são declarados para evitar falso sucesso ou consumo prematuro.
"""

from __future__ import annotations

import json
import os
import uuid
import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .adapters.pillar_convention import extract_pillar_convention
from .adapters.level_convention import extract_level_convention
from .adapters.pillars import inventory_pillars
from .adapters.inventory import inventory_labels
from .sources import SourceKind
from .sources import SourceRecord, resolve_crop_source


class RunnerError(RuntimeError):
    pass


def _revision(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    content = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def resolve_declared_sources(
    *,
    obra_dir: Path,
    obra_id: str,
    pavimento_id: str,
    declarations: Iterable[Mapping[str, Any]],
    selected_source_ids: set[str] | None = None,
) -> tuple[SourceRecord, ...]:
    resolved: list[SourceRecord] = []
    for declaration in declarations:
        source = resolve_crop_source(
            obra_dir=obra_dir,
            obra_id=obra_id,
            pavimento_id=pavimento_id,
            bruto_id=str(declaration.get("bruto_id") or ""),
            item_id=str(declaration.get("item_id") or ""),
        )
        if selected_source_ids and source.source_id not in selected_source_ids:
            continue
        resolved.append(source)
    if selected_source_ids:
        found = {source.source_id for source in resolved}
        missing = sorted(selected_source_ids - found)
        if missing:
            raise RunnerError(f"recorte_id não encontrado no manifesto: {', '.join(missing)}")
    return tuple(sorted(resolved, key=lambda source: source.source_id))


def build_inventory_result(
    *,
    obra_dir: Path,
    obra_id: str,
    pavimento_id: str,
    declarations: Iterable[Mapping[str, Any]],
    selected_source_ids: set[str] | None = None,
) -> dict[str, Any]:
    sources = resolve_declared_sources(
        obra_dir=obra_dir,
        obra_id=obra_id,
        pavimento_id=pavimento_id,
        declarations=declarations,
        selected_source_ids=selected_source_ids,
    )
    conventions: dict[str, Any] = {}
    convention_sources = [source for source in sources if source.kind is SourceKind.PILLAR_CONVENTION]
    for source in convention_sources:
        conventions[source.source_id] = extract_pillar_convention(
            obra_dir / Path(source.relative_path)
        )
    level_conventions = {
        source.source_id: extract_level_convention(obra_dir / Path(source.relative_path))
        for source in sources if source.kind is SourceKind.LEVEL_CONVENTION
    }
    pillars: dict[str, Any] = {}
    structural_labels: dict[str, Any] = {}
    for tower in (source for source in sources if source.kind is SourceKind.TOWER):
        # O service já restringe este lote a uma torre e suas dependências.
        # Convenção local única tem prioridade; sem ela, uma única convenção
        # do pavimento pode ser usada. Empates não escolhem por ordem.
        local = [
            source for source in convention_sources
            if source.bruto_id == tower.bruto_id
        ]
        candidates = local if local else convention_sources
        selected = candidates[0] if len(candidates) == 1 else None
        result = inventory_pillars(
            obra_dir / Path(tower.relative_path),
            source_id=tower.source_id,
            convention=conventions[selected.source_id] if selected else None,
        )
        if selected:
            result["convention_source_ids"] = [selected.source_id]
        else:
            result["convention_source_ids"] = [source.source_id for source in candidates]
            result["warnings"] = [
                "convencao_pilares_ambigua" if candidates else "convencao_pilares_ausente"
            ]
            result["status"] = "partial"
        pillars[tower.source_id] = result
        structural_labels[tower.source_id] = inventory_labels(
            obra_dir / Path(tower.relative_path), source_id=tower.source_id
        )
    convention_state = (
        "not_available" if not convention_sources
        else "complete" if all(value["status"] == "complete" for value in conventions.values())
        else "partial"
    )
    for source in sources:
        current_path = (obra_dir / Path(source.relative_path)).resolve()
        if obra_dir.resolve() not in current_path.parents:
            raise RunnerError(f"fonte saiu do escopo da obra: {source.source_id}")
        if _revision(current_path) != source.revision:
            raise RunnerError(f"fonte alterada durante pré-processamento: {source.source_id}")
    return {
        "schema_version": 1,
        "mode": "inventory_only",
        "status": "partial",
        "obra_id": obra_id,
        "pavimento_id": pavimento_id,
        "sources": [
            {**asdict(source), "kind": source.kind.value}
            for source in sources
        ],
        "pillar_conventions": conventions,
        "level_conventions": level_conventions,
        "pillars": pillars,
        "structural_labels": structural_labels,
        "modules": {
            "inventory": "complete",
            "pillar_convention": convention_state,
            "level_convention": (
                "not_available" if not level_conventions
                else "complete" if all(value["status"] == "complete" for value in level_conventions.values())
                else "partial"
            ),
            "pillars": (
                "not_available" if not pillars
                else "complete" if all(value["status"] == "complete" for value in pillars.values())
                else "partial"
            ),
            "slabs_beams": "partial" if structural_labels else "not_available",
            "cuts": "not_implemented",
            "levels": "not_implemented",
            "sa_consumption": "disabled",
        },
    }


def run_inventory(
    *,
    input_manifest: Path,
    output_dir: Path,
    obra_id: str,
    pavimento_id: str,
    selected_source_ids: set[str] | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    try:
        manifest = json.loads(input_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(f"manifesto de entrada inválido: {exc}") from exc
    if str(manifest.get("obra_id") or "") != obra_id:
        raise RunnerError("obra_id diverge do manifesto")
    if str(manifest.get("pavimento_id") or "") != pavimento_id:
        raise RunnerError("pavimento diverge do manifesto")
    obra_dir_raw = manifest.get("obra_dir")
    if not obra_dir_raw:
        raise RunnerError("obra_dir ausente no manifesto")
    result = build_inventory_result(
        obra_dir=Path(obra_dir_raw),
        obra_id=obra_id,
        pavimento_id=pavimento_id,
        declarations=manifest.get("sources") or (),
        selected_source_ids=selected_source_ids,
    )
    result["preview"] = bool(preview)
    unvalidated = [source["source_id"] for source in result["sources"] if not source["validated"]]
    result["unvalidated_source_ids"] = unvalidated
    result["provisional"] = bool(preview and unvalidated)
    if unvalidated and not preview:
        raise RunnerError("recortes pendentes de validação; use --preview para leitura provisória")
    if not preview:
        _write_atomic(output_dir / "inventory.json", result)
    return result
