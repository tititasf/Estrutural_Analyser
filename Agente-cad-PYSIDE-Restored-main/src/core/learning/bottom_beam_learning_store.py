# src/core/learning/bottom_beam_learning_store.py
from __future__ import annotations

from typing import Dict, Any, List
from .learning_store_base import LearningStoreBase, MIN_SAMPLES_FOR_ADJUSTMENT

class BottomBeamLearningStore(LearningStoreBase):
    """
    Learning Store especifico para Vigas de Fundo (bottom_beam).
    Campos suportados: nome, secao, comprimento_total, largura, painel_w, painel_h1, painel_h2, pilar, vigas_laterais_adjacentes
    Parametros ajustaveis: panel_detection_threshold, length_measurement_tolerance, vinculo_confidence_weight
    """

    def __init__(self, project_uuid: str, base_dir: str = ""):
        super().__init__(project_uuid=project_uuid, class_type="bottom_beam", base_dir=base_dir)

    def _recompute_parameters(self, field_name: str, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sobrescreve a logica base para recalcular os parametros ajustaveis 
        especificos de bottom_beam.
        """
        # Obter ajustes base (ex: confidence_boost, fallback_to_teacher)
        adjustments = super()._recompute_parameters(field_name, entries)
        
        field_entries = [e for e in entries if e.get("field_name") == field_name]
        if len(field_entries) < MIN_SAMPLES_FOR_ADJUSTMENT:
            return adjustments

        hits = [e for e in field_entries if e.get("was_correct", False)]
        hit_rate = len(hits) / len(field_entries) if field_entries else 0.0

        # Logica de recomputacao para painel (painel_w, painel_h1, painel_h2)
        if field_name in ["painel_w", "painel_h1", "painel_h2"]:
            if hit_rate < 0.70:
                adjustments["panel_detection_threshold"] = 0.85 # exige mais certeza
            elif hit_rate > 0.90:
                adjustments["panel_detection_threshold"] = 0.65 # relaxa

        # Logica de recomputacao para comprimento
        elif field_name == "comprimento_total":
            if hit_rate < 0.85:
                adjustments["length_measurement_tolerance"] = 0.05 # relaxa a tolerancia (ex: 5%)
            else:
                adjustments["length_measurement_tolerance"] = 0.01

        # Logica de recomputacao para vinculos
        elif field_name in ["pilar", "vigas_laterais_adjacentes"]:
            if hit_rate < 0.75:
                adjustments["vinculo_confidence_weight"] = 1.2 # dar mais peso
            else:
                adjustments["vinculo_confidence_weight"] = 1.0

        # Logica de recomputacao para contagem de segmentos (via Eng Reversa / Usuario)
        elif field_name == "segment_count":
            if hit_rate < 0.80:
                # O motor cru esta segmentando mal comparado as Fichas N2
                adjustments["segmentation_sensitivity"] = 1.5 # Deixa mais agucado
            else:
                adjustments["segmentation_sensitivity"] = 1.0

        return adjustments

    def get_learning_params(self) -> Dict[str, Any]:
        """
        Retorna os parametros aprendidos consolidados para uso no BeamTracer.
        """
        data = self._load_local()
        params = data.get("learned_parameters", [])
        
        # Valores defaults
        consolidated = {
            "panel_detection_threshold": 0.75,
            "length_measurement_tolerance": 0.02,
            "vinculo_confidence_weight": 1.0,
            "segmentation_sensitivity": 1.0,
            "confidence_boost": 0.0,
            "fallback_to_teacher": False
        }
        
        for p in params:
            param_name = p.get("parameter_name")
            if param_name:
                consolidated[param_name] = p.get("parameter_value")
        
        return consolidated
