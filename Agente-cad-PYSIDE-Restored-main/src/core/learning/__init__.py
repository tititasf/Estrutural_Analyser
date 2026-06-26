# src/core/learning/__init__.py
"""
Learning Store para Motor de Analise Estrutural (Agente-CAD).

Modulo que transforma a deteccao estatica em sistema de aprendizado continuo.
Aprende com validacoes do usuario, campo por campo, e melhora a cada pavimento.

Exporta:
- LearningStoreBase: classe base para todas as classes estruturais
- LearningStoreCache: cache singleton thread-safe
- LearningStoreFactory: factory para instanciar por class_type
- compute_context_signature: assinatura geometrica normalizada
- run_baseline_detection: baseline sem learning
- FeedbackEntry, FieldPrediction, LearnedParameter: dataclasses
"""
from .feedback_models import FeedbackEntry, FieldPrediction, LearnedParameter
from .learning_store_base import LearningStoreBase, MIN_SAMPLES_FOR_ADJUSTMENT, MIN_SAMPLES_FOR_GLOBAL
from .learning_store_cache import LearningStoreCache
from .learning_store_factory import LearningStoreFactory
from .context_signature import compute_context_signature
from .baseline_runner import run_baseline_detection

__all__ = [
    "FeedbackEntry",
    "FieldPrediction",
    "LearnedParameter",
    "LearningStoreBase",
    "LearningStoreCache",
    "LearningStoreFactory",
    "compute_context_signature",
    "run_baseline_detection",
    "MIN_SAMPLES_FOR_ADJUSTMENT",
    "MIN_SAMPLES_FOR_GLOBAL",
]
