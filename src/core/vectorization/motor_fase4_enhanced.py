"""
Motor Fase 4 Enhanced - With TransformationEngine Integration
======================================================
Versao aprimorada do MotorFase4 que integra o TransformationEngine
para predicao baseada em regras do banco de dados.

Features:
- Backward compatible com MotorFase4 original
- Suporte a A/B testing (transformation_engine vs legacy)
- Mantem contrato original da API
- Adiciona metricas de transformacao e observabilidade

Uso:
    motor = MotorFase4Enhanced(use_transformation_engine=True)
    result = motor.processar_pavimento(kb, 'P-1')

    # A/B comparison
    comparison = motor.compare_with_legacy(kb, obra='Obra_TREINO', pav='P-1', entities=[...])
"""

import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# Resolve src/ path para imports relativos
BASE_DIR = str(Path(__file__).parent.parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(1, BASE_DIR)

from motor_fase4 import MotorFase4
from core.robot_integration import RobotIntegration

logger = logging.getLogger(__name__)


class MotorFase4Enhanced(MotorFase4):
    """
    Enhanced version of MotorFase4 with TransformationEngine integration.

    Features:
    - Backward compatible with original MotorFase4
    - Supports A/B testing (transformation_engine vs legacy)
    - Maintains original API contract
    - Adds transformation metrics and observability
    """

    def __init__(
        self,
        pe_direito: float = 280.0,
        laje_espessura: float = 12.0,
        escala: float = 1.0,
        kb=None,
        use_transformation_engine: bool = True,
        db_path: Optional[str] = None,
    ):
        """
        Initialize enhanced motor.

        Args:
            pe_direito: Pe direito default (cm)
            laje_espessura: Espessura laje default (cm)
            escala: Escala DXF->cm
            kb: ObraKnowledge instance
            use_transformation_engine: If True, uses TransformationEngine
            db_path: Path to project_data.vision database
        """
        super().__init__(
            pe_direito=pe_direito,
            laje_espessura=laje_espessura,
            escala=escala,
            kb=kb,
        )
        self._use_transformation_engine = use_transformation_engine
        self._transformation_engine = None

        try:
            self._transformation_engine = RobotIntegration(
                db_path=Path(db_path) if db_path else None,
            )
            logger.info("MotorFase4Enhanced initialized with TransformationEngine")
        except Exception as e:
            logger.warning(f"Failed to initialize TransformationEngine: {e}")
            logger.warning("Falling back to legacy mode")
            self._use_transformation_engine = False

        self._metrics: Dict[str, Any] = {
            'legacy_calls': 0,
            'transformation_engine_calls': 0,
            'transformation_engine_time_ms': 0.0,
        }

    def processar_pavimento(
        self,
        obra_ou_kb,
        pavimento: str,
        entities_ou_pe_direito=None,
    ):
        """
        Process pavimento with automatic interface detection.

        Supports two interfaces:
        1. Legacy: processar_pavimento(kb: ObraKnowledge, pavimento: str, pe_direito: float)
        2. Enhanced: processar_pavimento(obra: str, pavimento: str, entities: dict)

        Auto-detects which interface based on first argument type.

        Returns:
            CalculationResult (legacy) or dict (enhanced)
        """
        if isinstance(obra_ou_kb, str):
            # Enhanced interface: obra=str, pavimento=str, entities=dict
            obra = obra_ou_kb
            entities = entities_ou_pe_direito

            if not isinstance(entities, dict):
                raise TypeError(
                    f"Enhanced mode expects entities dict, got {type(entities).__name__}"
                )

            if not self._use_transformation_engine:
                raise RuntimeError(
                    "Enhanced mode requires use_transformation_engine=True. "
                    "Use legacy interface with ObraKnowledge object instead."
                )

            return self._processar_com_transformation_engine(obra, pavimento, entities)

        else:
            # Legacy interface: kb=ObraKnowledge, pavimento=str, pe_direito=float
            self._metrics['legacy_calls'] += 1
            kb = obra_ou_kb
            pe_direito = entities_ou_pe_direito
            return super().processar_pavimento(kb, pavimento, pe_direito)

    def _processar_com_transformation_engine(
        self,
        obra: str,
        pavimento: str,
        entities: dict,
    ) -> dict:
        """
        Process using TransformationEngine.

        This is the new implementation that uses the transformation rules
        from the database for more flexible and maintainable transformations.
        """
        logger.info(f"Processing '{pavimento}' with TransformationEngine...")

        start_time = time.time()
        results = self._transformation_engine.process_pavimento(
            obra=obra,
            pavimento=pavimento,
            entities=entities.get('entities', []) if isinstance(entities, dict) else entities,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        self._metrics['transformation_engine_calls'] += 1
        self._metrics['transformation_engine_time_ms'] += elapsed_ms

        logger.info(
            f"TransformationEngine processed in {elapsed_ms:.2f}ms: "
            f"{results.get('stats', {}).get('total_transformed', '?')} entities"
        )

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Dict with transformation metrics
        """
        metrics = self._metrics.copy()
        if self._transformation_engine:
            engine_stats = self._transformation_engine.get_engine_stats()
            metrics['engine'] = engine_stats
        return metrics

    def compare_with_legacy(
        self,
        kb,
        obra: str,
        pavimento: str,
        entities,
        pe_direito: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compare TransformationEngine vs Legacy implementation.

        Useful for A/B testing and validation when you have both
        ObraKnowledge object (for legacy) and entities dict (for enhanced).

        Args:
            kb: ObraKnowledge instance (for legacy comparison)
            obra: Nome da obra
            pavimento: Nome do pavimento
            entities: Entity dict (for enhanced comparison)
            pe_direito: Pe direito (optional, for legacy)

        Returns:
            Dict with comparison results
        """
        logger.info("Running A/B comparison: TransformationEngine vs Legacy")

        # Legacy run
        t = time.time()
        legacy_result = super().processar_pavimento(kb, pavimento, pe_direito)
        legacy_time = (time.time() - t) * 1000

        # TransformationEngine run
        if not self._transformation_engine:
            return {
                'error': 'TransformationEngine not initialized',
                'legacy_result': legacy_result,
                'legacy_time_ms': legacy_time,
            }

        te_start = time.time()
        te_result = self._transformation_engine.process_pavimento(
            obra=obra,
            pavimento=pavimento,
            entities=entities if isinstance(entities, list) else entities.get('entities', []),
        )
        te_time = (time.time() - te_start) * 1000

        speedup = legacy_time / te_time if te_time > 0 else 0
        logger.info(
            f"A/B Comparison complete: Legacy={legacy_time:.2f}ms, "
            f"TE={te_time:.2f}ms, Speedup={speedup:.2f}x"
        )

        comparison = {
            'legacy_result': legacy_result,
            'te_result': te_result,
            'legacy_time_ms': round(legacy_time, 2),
            'te_time_ms': round(te_time, 2),
            'speedup': round(speedup, 2),
        }
        return {
            'comparison': comparison,
            'speedup': f"{speedup:.2f}x",
        }

    def enable_transformation_engine(self):
        """Enable TransformationEngine mode."""
        if self._transformation_engine:
            self._use_transformation_engine = True
            logger.info("TransformationEngine enabled")
        else:
            logger.warning("TransformationEngine not initialized, cannot enable")

    def disable_transformation_engine(self):
        """Disable TransformationEngine mode (fallback to legacy)."""
        self._use_transformation_engine = False
        logger.info("TransformationEngine disabled, using legacy mode")
