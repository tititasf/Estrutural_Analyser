# src/core/learning/feedback_models.py
"""
Dataclasses para o Learning Store.
Um unico schema para todas as 4 classes estruturais, com class_type como discriminador.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FieldPrediction:
    """Resultado de uma deteccao para um campo especifico."""
    field_name: str           # ex: "comprimento", "h1_face_A", "nome"
    predicted_value: Any      # valor que o motor detectou
    confidence: float         # 0.0 - 1.0
    origin: str               # "teacher_global" | "motor_geom" | "teacher_dynamic" | "learning_store"
    method: str               # "n2_teacher_axes" | "polygonize" | "beam_trace" | etc.


@dataclass
class FeedbackEntry:
    """Uma validacao do usuario para um campo."""
    class_type: str           # "slab" | "bottom_beam" | "lateral_beam" | "pillar"
    element_id: str           # ex: "L301", "P01", "V03"
    field_name: str           # ex: "comprimento", "nome"
    predicted_value: Any      # o que o motor disse
    actual_value: Any         # o que o usuario corrigiu/confirmou
    was_correct: bool         # True se predicted == actual
    confidence_at_prediction: float  # confidence que o motor tinha
    context_signature: dict   # assinatura geometrica do elemento
    timestamp: str            # ISO 8601
    pavimento: str            # ex: "13"
    project_uuid: str         # UUID do projeto

    def to_dict(self) -> dict:
        return {
            "class_type": self.class_type,
            "element_id": self.element_id,
            "field_name": self.field_name,
            "predicted_value": self.predicted_value,
            "actual_value": self.actual_value,
            "was_correct": self.was_correct,
            "confidence_at_prediction": self.confidence_at_prediction,
            "context_signature": self.context_signature,
            "timestamp": self.timestamp,
            "pavimento": self.pavimento,
            "project_uuid": self.project_uuid,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FeedbackEntry":
        return cls(
            class_type=d["class_type"],
            element_id=d["element_id"],
            field_name=d["field_name"],
            predicted_value=d.get("predicted_value"),
            actual_value=d.get("actual_value"),
            was_correct=d.get("was_correct", False),
            confidence_at_prediction=d.get("confidence_at_prediction", 0.0),
            context_signature=d.get("context_signature", {}),
            timestamp=d.get("timestamp", datetime.now().isoformat()),
            pavimento=d.get("pavimento", ""),
            project_uuid=d.get("project_uuid", ""),
        )

    def idempotency_key(self) -> str:
        """Chave unica para idempotencia: element_id + field_name + timestamp."""
        return f"{self.element_id}|{self.field_name}|{self.timestamp}"


@dataclass
class LearnedParameter:
    """Parametro ajustado pelo learning store para um campo+contexto."""
    class_type: str
    field_name: str
    context_key: str          # hash da assinatura geometrica
    parameter_name: str       # ex: "search_margin", "confidence_weight", "area_filter"
    parameter_value: float
    sample_count: int         # quantas validacoes alimentaram este parametro
    hit_rate: float           # % de acertos
    last_updated: str         # ISO 8601

    def to_dict(self) -> dict:
        return {
            "class_type": self.class_type,
            "field_name": self.field_name,
            "context_key": self.context_key,
            "parameter_name": self.parameter_name,
            "parameter_value": self.parameter_value,
            "sample_count": self.sample_count,
            "hit_rate": self.hit_rate,
            "last_updated": self.last_updated,
        }
