"""Resolução de fontes por obra/pavimento/bruto/recorte.

Somente arquivos encontrados pelo cadastro documental e por ``torre_crop`` são
aceitos. Query strings e nomes recebidos do cliente nunca viram paths diretamente.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

from .. import recortes_reader, torre_crop


_SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


class SourceResolutionError(ValueError):
    """Fonte ausente, fora da obra ou com identidade inválida."""


class SourceKind(str, Enum):
    TOWER = "tower"
    DETAILS = "details"
    PILLAR_CONVENTION = "pillar_convention"
    LEVEL_CONVENTION = "level_convention"
    OTHER = "other"


class BindingScope(str, Enum):
    WORK = "work"
    FLOOR = "floor"
    TOWER = "tower"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    obra_id: str
    pavimento_id: str
    bruto_id: str
    item_id: str
    kind: SourceKind
    revision: str
    relative_path: str
    validated: bool


@dataclass(frozen=True)
class ConventionBinding:
    source: SourceRecord
    convention_type: str
    scope: BindingScope
    obra_id: str
    pavimento_id: str | None = None
    tower_recorte_id: str | None = None

    def __post_init__(self) -> None:
        if self.convention_type not in {"pillars", "levels", "cuts"}:
            raise SourceResolutionError("convention_type inválido")
        if self.source.obra_id != self.obra_id:
            raise SourceResolutionError("binding e fonte pertencem a obras diferentes")
        if self.scope in {BindingScope.FLOOR, BindingScope.TOWER} and not self.pavimento_id:
            raise SourceResolutionError("binding de pavimento/torre exige pavimento_id")
        if self.scope is BindingScope.TOWER and not self.tower_recorte_id:
            raise SourceResolutionError("binding de torre exige tower_recorte_id")


def _safe_part(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or not _SAFE_PART.fullmatch(normalized) or ".." in normalized:
        raise SourceResolutionError(f"{name} inválido")
    return normalized


def _inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise SourceResolutionError("fonte fora do diretório da obra")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_id(*, obra_id: str, pavimento_id: str, bruto_id: str, item_id: str) -> str:
    identity = "\0".join((obra_id, pavimento_id, bruto_id, item_id)).encode("utf-8")
    return f"pre-src-v1:{hashlib.sha256(identity).hexdigest()}"


def _kind(item_id: str) -> SourceKind:
    if re.fullmatch(r"torre_\d+", item_id):
        return SourceKind.TOWER
    for prefix, kind in (("convencao_pilares", SourceKind.PILLAR_CONVENTION),
                         ("convencao_niveis", SourceKind.LEVEL_CONVENTION)):
        if item_id == prefix or item_id.startswith(prefix + "_"):
            return kind
    return {
        "detalhes": SourceKind.DETAILS,
        "convencao_pilares": SourceKind.PILLAR_CONVENTION,
        "convencao_niveis": SourceKind.LEVEL_CONVENTION,
    }.get(item_id, SourceKind.OTHER)


def resolve_crop_source(
    *,
    obra_dir: Path,
    obra_id: str,
    pavimento_id: str,
    bruto_id: str,
    item_id: str,
) -> SourceRecord:
    """Resolve um recorte somente a partir do inventário real no disco."""
    obra_id = _safe_part("obra_id", obra_id)
    pavimento_id = _safe_part("pavimento_id", pavimento_id)
    bruto_id = _safe_part("bruto_id", bruto_id)
    item_id = _safe_part("item_id", item_id)
    root = obra_dir.resolve()
    item = torre_crop.obter_recorte_bruto(root, bruto_id, item_id)
    if item is None:
        raise SourceResolutionError("recorte não encontrado no inventário da obra")
    path = _inside(root, Path(item["path"]))
    if not path.is_file() or path.suffix.lower() != ".dxf":
        raise SourceResolutionError("fonte DXF ausente ou inválida")
    return SourceRecord(
        source_id=_source_id(
            obra_id=obra_id,
            pavimento_id=pavimento_id,
            bruto_id=bruto_id,
            item_id=item_id,
        ),
        obra_id=obra_id,
        pavimento_id=pavimento_id,
        bruto_id=bruto_id,
        item_id=item_id,
        kind=_kind(item_id),
        revision=_sha256(path),
        relative_path=path.relative_to(root).as_posix(),
        validated=bool(item.get("validado")),
    )


def inventory_floor_sources(
    *,
    obra_dir: Path,
    obra_id: str,
    pavimento_id: str,
    documents: Sequence[dict],
) -> tuple[SourceRecord, ...]:
    """Inventaria recortes atuais dos brutos cadastrados para um pavimento.

    O cadastro define o pavimento; o diretório de recortes define as versões
    atualmente publicadas. Históricos de ``recortes_reversos`` não participam.
    """
    selected_stems: set[str] = set()
    for document in documents:
        floor = document.get("pavimento_confirmado") or document.get("pavimento_sugerido")
        if str(floor or "").strip() != pavimento_id:
            continue
        filename = str(document.get("arquivo_nome") or "").strip()
        if filename:
            selected_stems.add(recortes_reader.stem_bruto_canonico(Path(filename).stem).lower())

    sources: list[SourceRecord] = []
    for bruto in recortes_reader.listar_brutos_recorte(obra_dir):
        canonical = str(bruto.get("bruto_base") or "").lower()
        if canonical not in selected_stems:
            continue
        bruto_id = str(bruto["bruto_id"])
        for item in torre_crop.listar_recortes_bruto(obra_dir, bruto_id):
            sources.append(
                resolve_crop_source(
                    obra_dir=obra_dir,
                    obra_id=obra_id,
                    pavimento_id=pavimento_id,
                    bruto_id=bruto_id,
                    item_id=str(item["item_id"]),
                )
            )
    return tuple(sorted(sources, key=lambda item: (item.bruto_id, item.item_id)))


def raw_level_references(obra_dir: Path, sources: Sequence[SourceRecord]) -> tuple[dict, ...]:
    """Versões dos DXFs brutos correspondentes às torres, sem exigir recorte.

    O stem do bruto já veio do inventário autorizado da obra. Somente o DXF
    exato desse stem é aceito; DWG sem conversão não é interpretado aqui.
    """
    root = obra_dir.resolve()
    found = []
    for tower in (source for source in sources if source.kind is SourceKind.TOWER):
        path = _inside(root, root / "entrada" / f"{tower.bruto_id}.dxf")
        if not path.is_file():
            continue
        identity = "\0".join((tower.obra_id, tower.pavimento_id, tower.bruto_id)).encode()
        found.append({
            "source_id": "pre-raw-level-v1:" + hashlib.sha256(identity).hexdigest(),
            "obra_id": tower.obra_id, "pavimento_id": tower.pavimento_id,
            "bruto_id": tower.bruto_id, "item_id": "__raw_level_reference__",
            "kind": "raw_level_reference", "revision": _sha256(path),
            "relative_path": path.relative_to(root).as_posix(), "validated": True,
        })
    return tuple({ref["source_id"]: ref for ref in found}.values())


def select_convention_bindings(
    bindings: Iterable[ConventionBinding],
    *,
    obra_id: str,
    pavimento_id: str,
    tower_recorte_id: str,
    convention_type: str,
) -> tuple[ConventionBinding, ...]:
    """Retorna *todas* as fontes da maior abrangência aplicável.

    Empates são preservados como conflito potencial; ordem de arquivo nunca
    escolhe silenciosamente uma convenção.
    """
    rank = {BindingScope.WORK: 1, BindingScope.FLOOR: 2, BindingScope.TOWER: 3}
    applicable: list[ConventionBinding] = []
    for binding in bindings:
        if binding.obra_id != obra_id or binding.convention_type != convention_type:
            continue
        if binding.scope is BindingScope.FLOOR and binding.pavimento_id != pavimento_id:
            continue
        if binding.scope is BindingScope.TOWER and (
            binding.pavimento_id != pavimento_id
            or binding.tower_recorte_id != tower_recorte_id
        ):
            continue
        applicable.append(binding)
    if not applicable:
        return ()
    highest = max(rank[item.scope] for item in applicable)
    return tuple(
        sorted(
            (item for item in applicable if rank[item.scope] == highest),
            key=lambda item: item.source.source_id,
        )
    )
