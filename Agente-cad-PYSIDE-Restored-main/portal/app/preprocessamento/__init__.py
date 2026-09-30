"""Pré-processamento interno e versionado por pavimento/torre.

Este pacote é deliberadamente independente do schema N1 do Structural Analyzer.
"""

from .contracts import (
    Confidence,
    ContextEnvelope,
    ContextFact,
    ContextStatus,
    ContractError,
    GeometryReference,
    Review,
    ReviewStatus,
    ScopeIdentity,
)
from .sources import (
    BindingScope,
    ConventionBinding,
    SourceKind,
    SourceRecord,
    SourceResolutionError,
    inventory_floor_sources,
    resolve_crop_source,
    select_convention_bindings,
)
from .store import PreprocessStore, StoreError, StoredPackage

__all__ = [
    "Confidence",
    "ContextEnvelope",
    "ContextFact",
    "ContextStatus",
    "ContractError",
    "GeometryReference",
    "Review",
    "ReviewStatus",
    "ScopeIdentity",
    "BindingScope",
    "ConventionBinding",
    "SourceKind",
    "SourceRecord",
    "SourceResolutionError",
    "inventory_floor_sources",
    "resolve_crop_source",
    "select_convention_bindings",
    "PreprocessStore",
    "StoreError",
    "StoredPackage",
]
