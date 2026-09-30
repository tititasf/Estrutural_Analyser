"""Contrato v1 dos pacotes internos de pré-processamento.

O contrato preserva origem, escopo e incerteza. Ele não é o schema N1 e não
autoriza escrita nas tabelas estruturais. Modelos são dataclasses para que o CLI
possa validar pacotes sem iniciar FastAPI, Qt ou o motor SA.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


class ContractError(ValueError):
    """Pacote inválido ou ambíguo para publicação/consumo."""


class ContextStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    STALE = "stale"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


def _required_text(name: str, value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ContractError(f"{name} é obrigatório")
    return normalized


def _assert_finite(value: Any, path: str = "value") -> None:
    """Rejeita NaN/Inf em qualquer profundidade antes do JSON."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"{path} deve ser finito")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


def _enum_value(value: Enum | str) -> str:
    return value.value if isinstance(value, Enum) else str(value)


@dataclass(frozen=True)
class ScopeIdentity:
    obra_id: str
    pavimento_id: str
    recorte_id: str
    source_revision: str

    def __post_init__(self) -> None:
        for name in ("obra_id", "pavimento_id", "recorte_id"):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        revision = _required_text("source_revision", self.source_revision).lower()
        if not _SHA256_RE.fullmatch(revision):
            raise ContractError("source_revision deve ser SHA-256")
        object.__setattr__(self, "source_revision", revision.removeprefix("sha256:"))


@dataclass(frozen=True)
class GeometryReference:
    coordinate_system: str
    source_entity_handles: tuple[str, ...] = ()
    geometry: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "coordinate_system", _required_text("coordinate_system", self.coordinate_system)
        )
        object.__setattr__(
            self,
            "source_entity_handles",
            tuple(str(handle).strip() for handle in self.source_entity_handles if str(handle).strip()),
        )
        if self.geometry is not None:
            if not isinstance(self.geometry, Mapping):
                raise ContractError("geometry deve ser objeto JSON")
            _assert_finite(self.geometry, "geometry")


@dataclass(frozen=True)
class Confidence:
    value: float | None = None
    kind: str | None = None
    rule_version: str | None = None
    components: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.value is not None:
            numeric = float(self.value)
            if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
                raise ContractError("confidence.value deve estar entre 0 e 1")
            if self.kind not in {"heuristic", "calibrated"}:
                raise ContractError("confidence.kind deve ser heuristic ou calibrated")
            object.__setattr__(self, "value", numeric)
        elif self.kind is not None:
            raise ContractError("confidence.kind sem value é ambíguo")
        _assert_finite(self.components, "confidence.components")


@dataclass(frozen=True)
class Review:
    status: ReviewStatus = ReviewStatus.UNREVIEWED
    author_id: str | None = None
    reviewed_at: str | None = None
    source_revision: str | None = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "status", ReviewStatus(self.status))
        except ValueError as exc:
            raise ContractError("review.status inválido") from exc
        if self.status is not ReviewStatus.UNREVIEWED:
            _required_text("review.author_id", self.author_id)
            _required_text("review.reviewed_at", self.reviewed_at)
            revision = _required_text("review.source_revision", self.source_revision).lower()
            if not _SHA256_RE.fullmatch(revision):
                raise ContractError("review.source_revision deve ser SHA-256")


@dataclass(frozen=True)
class ContextFact:
    item_id: str
    display_name: str
    field: str
    value: Any
    geometry_ref: GeometryReference | None = None
    unit: str | None = None
    datum_id: str | None = None
    raw_text: str | None = None
    level_kind: str | None = None
    classification_raw: str | None = None
    classification_normalized: str | None = None
    physical_type: str | None = None
    evidence_ids: tuple[str, ...] = ()
    method: str | None = None
    derived_from: tuple[str, ...] = ()
    independence_group: str | None = None
    warnings: tuple[str, ...] = ()
    confidence: Confidence = field(default_factory=Confidence)
    review: Review = field(default_factory=Review)
    alternatives: tuple[Any, ...] = ()
    conflicts: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        for name in ("item_id", "display_name", "field"):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        _assert_finite(self.value)
        _assert_finite(self.alternatives, "alternatives")
        _assert_finite(self.conflicts, "conflicts")
        if not isinstance(self.confidence, Confidence):
            raise ContractError("confidence deve usar o contrato Confidence")
        if not isinstance(self.review, Review):
            raise ContractError("review deve usar o contrato Review")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ContextFact":
        data = dict(payload)
        geometry = data.get("geometry_ref")
        if geometry is not None:
            data["geometry_ref"] = GeometryReference(
                coordinate_system=geometry.get("coordinate_system"),
                source_entity_handles=tuple(geometry.get("source_entity_handles") or ()),
                geometry=geometry.get("geometry"),
            )
        confidence = data.get("confidence") or {}
        data["confidence"] = Confidence(**confidence)
        review = data.get("review") or {}
        data["review"] = Review(**review)
        for name in ("evidence_ids", "derived_from", "warnings", "alternatives", "conflicts"):
            data[name] = tuple(data.get(name) or ())
        return cls(**data)


@dataclass(frozen=True)
class ContextEnvelope:
    run_id: str
    scope: ScopeIdentity
    status: ContextStatus
    created_at: str
    items: tuple[ContextFact, ...] = ()
    dependency_revisions: tuple[str, ...] = ()
    engine_versions: Mapping[str, str] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _required_text("run_id", self.run_id))
        if self.schema_version != 1:
            raise ContractError("schema_version não suportada")
        if not isinstance(self.scope, ScopeIdentity):
            raise ContractError("scope completo é obrigatório")
        try:
            object.__setattr__(self, "status", ContextStatus(self.status))
        except ValueError as exc:
            raise ContractError("status inválido") from exc
        timestamp = _required_text("created_at", self.created_at)
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractError("created_at deve ser ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ContractError("created_at deve incluir timezone")
        for revision in self.dependency_revisions:
            if not _SHA256_RE.fullmatch(str(revision).lower()):
                raise ContractError("dependency_revisions deve conter SHA-256")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ContractError("item_id duplicado no mesmo envelope")

    @classmethod
    def empty(
        cls,
        *,
        run_id: str,
        scope: ScopeIdentity,
        status: ContextStatus = ContextStatus.COMPLETE,
    ) -> "ContextEnvelope":
        return cls(
            run_id=run_id,
            scope=scope,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = _enum_value(self.status)
        for item in payload["items"]:
            item["review"]["status"] = _enum_value(item["review"]["status"])
        _assert_finite(payload)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ContextEnvelope":
        data = dict(payload)
        scope = data.get("scope")
        if not isinstance(scope, Mapping):
            raise ContractError("scope completo é obrigatório")
        data["scope"] = ScopeIdentity(**scope)
        data["items"] = tuple(ContextFact.from_dict(item) for item in data.get("items") or ())
        data["dependency_revisions"] = tuple(data.get("dependency_revisions") or ())
        return cls(**data)
