"""
Vectorization Pipeline — CAD-ANALYZER
======================================
Pipeline de vetorizacao de obras estruturais.

Modulos:
    dxf_ingestor       — Ingesta DXFs e PDFs em RawEntity normalizadas
    structural_vectorizer — Vetoriza RawEntity em FeatureVector numericos
    obra_knowledge     — Base de conhecimento persistente por obra (SQLite)
    spatial_analyzer   — Analisa relacionamentos espaciais entre elementos
    motor_fase4        — Motor de interpretacao Fase 4 (IA)
    motor_fase4_enhanced — Fase 4 com TransformationEngine integrado
"""

from .dxf_ingestor import (
    DXFIngestor,
    IngestorConfig,
    IngestedFile,
    DXFFamily,
    RawEntity,
    ingerir_obra,
    ingerir_dxf_unico,
)

from .structural_vectorizer import (
    StructuralVectorizer,
    VectorConfig,
    StructuralEntity,
    EntityType,
    FeatureVector,
    vetorizar_entidades,
)

from .obra_knowledge import (
    ObraKnowledge,
    ObraProfile,
    PavimentoData,
    criar_conhecimento_obra,
)

__all__ = [
    # dxf_ingestor
    "DXFIngestor", "IngestorConfig", "IngestedFile", "DXFFamily",
    "RawEntity", "ingerir_obra", "ingerir_dxf_unico",
    # structural_vectorizer
    "StructuralVectorizer", "VectorConfig", "StructuralEntity",
    "EntityType", "FeatureVector", "vetorizar_entidades",
    # obra_knowledge
    "ObraKnowledge", "ObraProfile", "PavimentoData", "criar_conhecimento_obra",
]

__version__ = "1.0.0"
