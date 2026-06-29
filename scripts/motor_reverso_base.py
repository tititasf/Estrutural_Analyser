#!/usr/bin/env python3
"""Contrato base para novos motores reversos, sem impor lógica às classes atuais."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtractionContext:
    obra_name: str
    pavimento: str
    class_id: str
    item_id: str
    recorte_path: Path
    project_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionCandidate:
    fields: dict[str, Any]
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tier: str = "T0"
    validation_origin: str = "machine_extraction"

    def __post_init__(self) -> None:
        if self.tier != "T0":
            raise ValueError("motor reverso so pode produzir candidato T0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence deve estar entre 0 e 1")


class ReverseExtractorPlugin(ABC):
    """Nova classe implementa extração; promoção humana fica fora do plugin."""

    class_id: str
    schema_version = 1

    @abstractmethod
    def extract(self, context: ExtractionContext) -> ExtractionCandidate:
        raise NotImplementedError

    def validate_context(self, context: ExtractionContext) -> None:
        if context.class_id.upper() != self.class_id.upper():
            raise ValueError(
                f"plugin {self.class_id} nao aceita classe {context.class_id}"
            )
        if not context.recorte_path.exists():
            raise FileNotFoundError(context.recorte_path)
