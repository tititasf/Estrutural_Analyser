"""
SlabLearningStore - Learning Store especifico para lajes.
Herda de LearningStoreBase e adiciona campos e parametros especificos.

Campos mapeados:
    nome, comprimento, largura, area, coordenadas,
    pontaletes_total, obstaculos, modo_selecionado, vinculo_pilar

Parametros ajustaveis:
    search_margin, max_area_filter, confidence_weight_axes,
    n2_crop_clamp_expand, teacher_axis_preference
"""
from __future__ import annotations

from .learning_store_base import LearningStoreBase
from .feedback_models import FeedbackEntry


# Campos validos para lajes
SLAB_FIELDS = [
    "nome",
    "comprimento",
    "largura",
    "area",
    "coordenadas",
    "pontaletes_total",
    "obstaculos",
    "modo_selecionado",
    "vinculo_pilar",
    # Campos de migration (legacy)
    "outline_validation",
    "recorte_validation",
    "dimension_detection",
]

# Parametros que podem ser ajustados pelo learning
SLAB_ADJUSTABLE_PARAMS = [
    "search_margin",
    "max_area_filter",
    "confidence_weight_axes",
    "n2_crop_clamp_expand",
    "teacher_axis_preference",
]


class SlabLearningStore(LearningStoreBase):
    """Learning Store para lajes (slab)."""

    def __init__(self, project_uuid: str, base_dir: str = ""):
        super().__init__(project_uuid, "slab", base_dir)

    def get_valid_fields(self) -> list:
        """Retorna lista de campos validos para lajes."""
        return SLAB_FIELDS.copy()

    def get_adjustable_params(self) -> list:
        """Retorna lista de parametros ajustaveis."""
        return SLAB_ADJUSTABLE_PARAMS.copy()

    def get_slab_stats(self, field_name: str = None) -> dict:
        """Retorna estatisticas detalhadas para lajes.
        Se field_name=None, retorna stats de todos os campos.
        """
        if field_name:
            return self.get_field_stats(field_name)

        all_stats = {}
        for field in SLAB_FIELDS:
            all_stats[field] = self.get_field_stats(field)
        return all_stats

    def get_slab_hit_rate(self, field_name: str = None) -> float:
        """Hit rate para um campo especifico ou geral de lajes."""
        return self.get_hit_rate(field_name)

    def get_slab_adjusted_parameters(self, field_name: str = None) -> dict:
        """Parametros ajustados pelo learning para lajes.
        Se field_name=None, retorna todos agrupados por campo.
        """
        return self.get_adjusted_parameters(field_name)

    def record_slab_feedback(
        self,
        element_id: str,
        field_name: str,
        predicted_value,
        actual_value,
        was_correct: bool,
        confidence_at_prediction: float,
        context_signature: dict,
        pavimento: str,
        project_uuid: str = None,
    ) -> None:
        """Convenience method para gravar feedback de laje.
        Cria FeedbackEntry e chama record_feedback.
        """
        from datetime import datetime

        if field_name not in SLAB_FIELDS:
            raise ValueError(
                f"Campo invalido para laje: {field_name}. Validos: {SLAB_FIELDS}"
            )

        entry = FeedbackEntry(
            class_type="slab",
            element_id=element_id,
            field_name=field_name,
            predicted_value=predicted_value,
            actual_value=actual_value,
            was_correct=was_correct,
            confidence_at_prediction=confidence_at_prediction,
            context_signature=context_signature,
            timestamp=datetime.now().isoformat(),
            pavimento=pavimento,
            project_uuid=project_uuid or self.project_uuid,
        )
        self.record_feedback(entry)
