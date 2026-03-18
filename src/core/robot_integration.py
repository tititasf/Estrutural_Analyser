"""
Robot Integration - Sprint 5
=============================
Ponte entre TransformationEngine (Fase 3) e Robots (Fase 4).

Workflow:
    StructuralEntity (do ObraKnowledge/vetorizador)
        -> RobotIntegration.process_pavimento(obra, pavimento, entities)
        -> Para cada entity: TransformationEngine.transform()
        -> Agrupa resultados por robot (Bolt=pilares, Crane=vigas, Slab=lajes)
        -> Retorna dict pronto para os robos consumirem

Responsabilidades:
- Chamar TransformationEngine para cada robo
- Converter JSON da entidade para formato especifico de cada robo
- Agregar estatisticas de transformacao por pavimento
- Registrar erros e entidades skipped para revisao humana
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from core.transformation_engine import TransformationEngine

logger = logging.getLogger(__name__)


class RobotIntegration:
    """
    Integra TransformationEngine com os 5 robos.

    Responsabilidades:
    - Chamar TransformationEngine para cada robo
    - Converter JSON da entidade para o formato de cada robo
    - Agregar resultados por tipo (pillars, beams, slabs)
    - Registrar stats para dashboard

    Uso:
        integration = RobotIntegration(db_path=Path('project_data.vision'))
        result = integration.process_pavimento(
            obra='Obra_TREINO_21',
            pavimento='P-1',
            entities=[...],  # lista de dicts de StructuralEntity
        )
        for pilar in result['pillars']:
            print(pilar['fields'].get('Pilar_name'), pilar['confidence'])
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        enable_cache: bool = True,
        enable_logging: bool = True,
    ):
        self.engine = TransformationEngine(
            db_path=db_path,
            enable_cache=enable_cache,
            enable_logging=enable_logging,
        )
        logger.info("RobotIntegration initialized")

    def process_pavimento(
        self,
        obra: str,
        pavimento: str,
        entities: List[Dict[str, Any]],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Processa todas entities de um pavimento para todos os robos.

        Args:
            obra: Nome da obra
            pavimento: Nome do pavimento
            entities: Lista de dicts de StructuralEntity (do ObraKnowledge ou vetorizador)
            config: Configuracao opcional por robo

        Returns:
            Dict com:
                'pillars': lista de resultados para Bolt
                'beams': lista de resultados para Crane
                'slabs': lista de resultados para Slab
                'stats': estatisticas de transformacao
        """
        pillars = []
        beams = []
        slabs = []
        stats = {
            'total_entities': len(entities),
            'success': 0,
            'skipped': 0,
            'error': 0,
        }

        logger.info(
            f"Processing pavimento '{pavimento}': {len(entities)} entities "
            f"[{sum(1 for e in entities if e.get('entity_type') == 'Pilar')} pillar, "
            f"{sum(1 for e in entities if e.get('entity_type') == 'Viga')} beam, "
            f"{sum(1 for e in entities if e.get('entity_type') == 'Laje')} slab]"
        )

        for entity in entities:
            entity_type_raw = entity.get('entity_type', '')
            entity_type = self._map_entity_type(entity_type_raw)

            if entity_type is None:
                stats['skipped'] += 1
                continue

            result = self.engine.transform(
                entity_type=entity_type,
                entity_data=entity,
                target_robot='auto',
                obra=obra,
                pavimento=pavimento,
                config=config,
            )

            status = result.get('status', 'error')
            stats[status if status in stats else 'error'] += 1

            if status == 'success':
                enriched = {**result, 'raw_entity': entity}
                if entity_type == 'pillar':
                    pillars.append(enriched)
                elif entity_type == 'beam':
                    beams.append(enriched)
                elif entity_type == 'slab':
                    slabs.append(enriched)

        logger.info(
            f"Done: {stats['success']} ok, {stats['skipped']} skipped, "
            f"{stats['error']} errors"
        )

        return {
            'pillars': pillars,
            'beams': beams,
            'slabs': slabs,
            'stats': stats,
            'engine_stats': self.engine.get_stats(),
        }

    def _map_entity_type(self, raw_type: str) -> Optional[str]:
        """Mapeia entity_type do vetorizador para tipo do TransformationEngine."""
        mapping = {
            'Pilar': 'pillar',
            'Viga': 'beam',
            'Laje': 'slab',
            'pilar': 'pillar',
            'viga': 'beam',
            'laje': 'slab',
            'pillar': 'pillar',
            'beam': 'beam',
            'slab': 'slab',
        }
        return mapping.get(raw_type)

    def process_from_knowledge(
        self,
        knowledge,   # ObraKnowledge
        pavimento: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Conveniencia: processa pavimento diretamente de um ObraKnowledge.

        Args:
            knowledge: ObraKnowledge com entidades armazenadas
            pavimento: Nome do pavimento a processar
            config: Configuracao opcional

        Returns:
            Resultado de process_pavimento
        """
        pav_data = knowledge.get_pavimento(pavimento)

        # Combinar todos os tipos
        all_entities = (
            pav_data.pilares +
            pav_data.vigas +
            pav_data.lajes
        )

        profile = knowledge.get_profile()
        obra = profile.name if profile else knowledge.obra_id

        return self.process_pavimento(
            obra=obra,
            pavimento=pavimento,
            entities=all_entities,
            config=config,
        )
