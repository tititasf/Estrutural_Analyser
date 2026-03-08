# -*- coding: utf-8 -*-
"""
Fases do Pipeline CAD-ANALYZER
"""

from phases.fase1_ingestao import Fase1Ingestao, IngestaoResultado
from phases.fase2_triagem import Fase2Triagem, TriagemResultado
from phases.fase3_interpretacao import (
    Fase3Interpretacao,
    InterpretacaoResultado,
    FichaFase3Pilar,
    FichaFase3Viga,
    FichaFase3Laje,
    carregar_fichas_obra
)
from phases.fase3_revisor import Fase3Revisor, RevisaoResultado, Sugestao, TrainingEvent

__all__ = [
    # Fase 1
    "Fase1Ingestao",
    "IngestaoResultado",
    # Fase 2
    "Fase2Triagem",
    "TriagemResultado",
    # Fase 3
    "Fase3Interpretacao",
    "InterpretacaoResultado",
    "FichaFase3Pilar",
    "FichaFase3Viga",
    "FichaFase3Laje",
    "carregar_fichas_obra",
    # Revisor
    "Fase3Revisor",
    "RevisaoResultado",
    "Sugestao",
    "TrainingEvent",
]
