"""
Spatial Analyzer
================
Analisa relacionamentos espaciais entre entidades estruturais
(pilares, vigas, lajes) dentro de cada pavimento.

Relationships detected:
- PILAR_SUPORTA_VIGA: pilar bbox overlaps or is near viga endpoint
- VIGA_BORDA_LAJE: viga bbox overlaps or is adjacent to laje bbox
- PILAR_NA_LAJE: pilar is inside/on-border of laje area
- VIGA_CRUZA_VIGA: two vigas overlap (intersection point)

Usage:
    from spatial_analyzer import SpatialAnalyzer
    analyzer = SpatialAnalyzer()
    rels = analyzer.analisar_pavimento(vigas, pilares, lajes)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class EntityRect:
    """Representacao espacial simplificada de uma entidade."""
    entity_id: str
    entity_type: str
    name: str
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    confidence: float = 1.0

    @property
    def cx(self) -> float:
        return (self.xmin + self.xmax) / 2

    @property
    def cy(self) -> float:
        return (self.ymin + self.ymax) / 2

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    @property
    def area(self) -> float:
        return self.width * self.height

    def overlaps(self, other: 'EntityRect', tol: float = 0.0) -> bool:
        """Verifica se as bboxes se sobrepoem (com tolerancia)."""
        return (
            self.xmin - tol <= other.xmax + tol and
            self.xmax + tol >= other.xmin - tol and
            self.ymin - tol <= other.ymax + tol and
            self.ymax + tol >= other.ymin - tol
        )

    def contains_point(self, x: float, y: float, tol: float = 0.0) -> bool:
        """Verifica se um ponto esta dentro da bbox."""
        return (
            self.xmin - tol <= x <= self.xmax + tol and
            self.ymin - tol <= y <= self.ymax + tol
        )

    def distance_to(self, other: 'EntityRect') -> float:
        """Distancia entre centros."""
        return math.sqrt((self.cx - other.cx) ** 2 + (self.cy - other.cy) ** 2)


@dataclass
class SpatialRelation:
    """Relacionamento espacial entre duas entidades."""
    relation_type: str              # PILAR_SUPORTA_VIGA, etc.
    entity_a_id: str
    entity_b_id: str
    entity_a_type: str
    entity_b_type: str
    entity_a_name: str
    entity_b_name: str
    distance: float = 0.0
    confidence: float = 1.0


class SpatialAnalyzer:
    """
    Analisa relacionamentos espaciais entre elementos estruturais.

    Parametros de proximidade:
        proximity_tol  — tolerancia para sobreposicao (mm no espaco DXF)
        near_distance  — distancia maxima para considerar "proximo" (para SUPORTA)
    """

    def __init__(
        self,
        proximity_tol: float = 50.0,
        near_distance: float = 500.0,
    ):
        self.proximity_tol = proximity_tol
        self.near_distance = near_distance

    def _to_rect(self, entity: Dict[str, Any]) -> Optional[EntityRect]:
        """Converte dict de entidade para EntityRect."""
        try:
            return EntityRect(
                entity_id=entity.get('entity_id', str(entity.get('id', ''))),
                entity_type=entity.get('entity_type', ''),
                name=entity.get('name', ''),
                xmin=float(entity.get('bbox_xmin', 0)),
                xmax=float(entity.get('bbox_xmax', 0)),
                ymin=float(entity.get('bbox_ymin', 0)),
                ymax=float(entity.get('bbox_ymax', 0)),
                confidence=float(entity.get('confidence', 1.0)),
            )
        except (TypeError, ValueError) as e:
            logger.debug(f"Could not create EntityRect: {e}")
            return None

    def analisar_pavimento(
        self,
        vigas: List[Dict],
        pilares: List[Dict],
        lajes: List[Dict],
    ) -> List[SpatialRelation]:
        """
        Analisa todos os relacionamentos espaciais de um pavimento.

        Args:
            vigas: Lista de dicts de StructuralEntity tipo Viga
            pilares: Lista de dicts de StructuralEntity tipo Pilar
            lajes: Lista de dicts de StructuralEntity tipo Laje

        Returns:
            Lista de SpatialRelation identificados
        """
        viga_rects = [r for r in (self._to_rect(e) for e in vigas) if r]
        pilar_rects = [r for r in (self._to_rect(e) for e in pilares) if r]
        laje_rects = [r for r in (self._to_rect(e) for e in lajes) if r]

        relations = []
        relations.extend(self._find_pilar_suporta_viga(pilar_rects, viga_rects))
        relations.extend(self._find_viga_borda_laje(viga_rects, laje_rects))
        relations.extend(self._find_pilar_na_laje(pilar_rects, laje_rects))
        relations.extend(self._find_viga_cruza_viga(viga_rects))

        logger.info(
            f"Spatial analysis: {len(relations)} relations "
            f"({len(pilar_rects)} pilares, {len(viga_rects)} vigas, {len(laje_rects)} lajes)"
        )
        return relations

    def _find_pilar_suporta_viga(
        self, pilares: List[EntityRect], vigas: List[EntityRect]
    ) -> List[SpatialRelation]:
        """Detecta: pilar proximo de endpoint de viga."""
        relations = []
        for pilar in pilares:
            for viga in vigas:
                dist = pilar.distance_to(viga)
                # Considera suporte se bbox sobreopoem ou estao proximos
                if pilar.overlaps(viga, tol=self.proximity_tol) or dist < self.near_distance:
                    conf = 1.0 if pilar.overlaps(viga) else max(0.3, 1.0 - dist / self.near_distance)
                    relations.append(SpatialRelation(
                        relation_type="PILAR_SUPORTA_VIGA",
                        entity_a_id=pilar.entity_id, entity_b_id=viga.entity_id,
                        entity_a_type="Pilar", entity_b_type="Viga",
                        entity_a_name=pilar.name, entity_b_name=viga.name,
                        distance=dist, confidence=round(conf, 3),
                    ))
        return relations

    def _find_viga_borda_laje(
        self, vigas: List[EntityRect], lajes: List[EntityRect]
    ) -> List[SpatialRelation]:
        """Detecta: viga na borda ou sobrepoem laje."""
        relations = []
        for viga in vigas:
            for laje in lajes:
                if viga.overlaps(laje, tol=self.proximity_tol):
                    dist = viga.distance_to(laje)
                    relations.append(SpatialRelation(
                        relation_type="VIGA_BORDA_LAJE",
                        entity_a_id=viga.entity_id, entity_b_id=laje.entity_id,
                        entity_a_type="Viga", entity_b_type="Laje",
                        entity_a_name=viga.name, entity_b_name=laje.name,
                        distance=dist, confidence=0.8,
                    ))
        return relations

    def _find_pilar_na_laje(
        self, pilares: List[EntityRect], lajes: List[EntityRect]
    ) -> List[SpatialRelation]:
        """Detecta: pilar dentro da area da laje."""
        relations = []
        for pilar in pilares:
            for laje in lajes:
                if laje.contains_point(pilar.cx, pilar.cy, tol=self.proximity_tol):
                    dist = pilar.distance_to(laje)
                    relations.append(SpatialRelation(
                        relation_type="PILAR_NA_LAJE",
                        entity_a_id=pilar.entity_id, entity_b_id=laje.entity_id,
                        entity_a_type="Pilar", entity_b_type="Laje",
                        entity_a_name=pilar.name, entity_b_name=laje.name,
                        distance=dist, confidence=0.9,
                    ))
        return relations

    def _find_viga_cruza_viga(
        self, vigas: List[EntityRect]
    ) -> List[SpatialRelation]:
        """Detecta: duas vigas que se cruzam."""
        relations = []
        for i, v1 in enumerate(vigas):
            for v2 in vigas[i + 1:]:
                if v1.overlaps(v2, tol=self.proximity_tol / 2):
                    dist = v1.distance_to(v2)
                    relations.append(SpatialRelation(
                        relation_type="VIGA_CRUZA_VIGA",
                        entity_a_id=v1.entity_id, entity_b_id=v2.entity_id,
                        entity_a_type="Viga", entity_b_type="Viga",
                        entity_a_name=v1.name, entity_b_name=v2.name,
                        distance=dist, confidence=0.7,
                    ))
        return relations

    def relations_to_dict(self, relations: List[SpatialRelation]) -> List[Dict]:
        """Serializa lista de relacoes para dict."""
        result = []
        for r in relations:
            result.append({
                'type': r.relation_type,
                'a_id': r.entity_a_id, 'b_id': r.entity_b_id,
                'a_name': r.entity_a_name, 'b_name': r.entity_b_name,
                'distance': r.distance, 'confidence': r.confidence,
            })
        return result


def analisar_obra_completa(
    knowledge,  # ObraKnowledge
    proximity_tol: float = 50.0,
    near_distance: float = 500.0,
) -> Dict[str, List[SpatialRelation]]:
    """
    Analisa todos os pavimentos de uma obra em sequencia.

    Args:
        knowledge: ObraKnowledge com entidades armazenadas
        proximity_tol: Tolerancia de sobreposicao (mm)
        near_distance: Distancia maxima para relacao SUPORTA (mm)

    Returns:
        Dict pavimento -> lista de SpatialRelation
    """
    analyzer = SpatialAnalyzer(proximity_tol=proximity_tol, near_distance=near_distance)
    stats = knowledge.get_statistics()
    pavimentos = stats.get('pavimentos', [])

    result = {}
    for pav_name in pavimentos:
        pav_data = knowledge.get_pavimento(pav_name)
        relations = analyzer.analisar_pavimento(
            vigas=pav_data.vigas,
            pilares=pav_data.pilares,
            lajes=pav_data.lajes,
        )
        result[pav_name] = relations
        logger.info(f"Pavimento '{pav_name}': {len(relations)} spatial relations")

    return result
