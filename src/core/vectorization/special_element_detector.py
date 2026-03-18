"""
SpecialElementDetector -- Detecta elementos estruturais especiais.

Vai alem dos 3 tipos basicos (Pilar, Viga, Laje) para identificar:
- Pilar Cambotado  (pilar com curvatura/arco)
- Viga Cambotada   (viga com curvatura/arco)
- Misula           (consolo/bracket na juncao viga-pilar)
- Parede de Concreto (elemento linear espesso, aspect_ratio > 10)
- Reservatorio     (caixa d'agua embutida, retangulo grande proximo a borda)
- Tira de Reescoramento (reforco de forma, elemento linear fino)

Integracao com pipeline:
    Fase 2 (StructuralVectorizer) classifica os 3 tipos basicos.
    Este detector roda APOS a Fase 2 como pos-processador,
    reclassificando entidades que se encaixam nos tipos especiais.

Uso:
    detector = SpecialElementDetector()
    especiais = detector.processar_pavimento(entities)
    # especiais = {'entity_id_abc': 'pilar_cambotado', ...}
"""

import math
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

@dataclass
class SpecialDetectorConfig:
    """Thresholds para deteccao de elementos especiais."""

    # Cambotado: bulge minimo para considerar curvatura
    bulge_threshold: float = 0.01

    # Misula: area maxima relativa ao pilar medio (fator multiplicador)
    misula_max_area_factor: float = 0.3
    # Misula: distancia maxima da juncao viga-pilar (mm no DXF)
    misula_max_distance: float = 200.0
    # Misula: aspect_ratio maximo (quase quadrada/triangular)
    misula_max_aspect_ratio: float = 3.0

    # Parede: aspect_ratio minimo
    parede_min_aspect_ratio: float = 10.0
    # Parede: area minima (mm^2 no DXF)
    parede_min_area: float = 5000.0

    # Reservatorio: area minima (mm^2)
    reservatorio_min_area: float = 50000.0
    # Reservatorio: distancia maxima da borda do pavimento (mm)
    reservatorio_borda_max_dist: float = 2000.0

    # Tira de Reescoramento: largura maxima (mm)
    tira_max_largura: float = 30.0
    # Tira: comprimento minimo (mm)
    tira_min_comprimento: float = 300.0


# ---------------------------------------------------------------------------
# Tipos especiais
# ---------------------------------------------------------------------------

TIPOS_ESPECIAIS = (
    'pilar_cambotado',
    'viga_cambotada',
    'misula',
    'parede',
    'reservatorio',
    'tira_reescoramento',
)


# ---------------------------------------------------------------------------
# Detector principal
# ---------------------------------------------------------------------------

class SpecialElementDetector:
    """
    Detecta elementos estruturais especiais alem dos basicos
    (Pilar, Viga, Laje).

    Cada metodo detectar_* recebe uma entidade como Dict
    (serializada de StructuralEntity.to_dict() ou similar)
    e retorna True/False.

    O metodo classificar_elemento_especial orquestra todos os
    detectores e retorna o tipo especial ou None.
    """

    def __init__(self, config: Optional[SpecialDetectorConfig] = None) -> None:
        self.config = config or SpecialDetectorConfig()

    # ------------------------------------------------------------------
    # Deteccao de Cambotado (Pilar ou Viga com curvatura)
    # ------------------------------------------------------------------

    def detectar_cambotado(self, entity: Dict[str, Any]) -> bool:
        """
        Verifica se a entidade possui curvatura (arcos).

        No DXF, polilinhas com curvatura possuem valores de 'bulge'
        diferentes de zero nos vertices. A presenca de bulge indica
        que o segmento entre dois vertices e um arco, nao uma reta.

        Alem do bulge, verificamos:
        - Se a entidade tem vertices irregulares (nao-retangular)
        - Se o extra contém metadados de curvatura do ezdxf

        Args:
            entity: Dict com dados da entidade (vertices, extra, etc.)

        Returns:
            True se a entidade tem curvatura significativa.
        """
        # 1. Verificar bulge nos metadados extra
        extra = entity.get('extra', {})
        bulges = extra.get('bulges', [])
        if bulges:
            has_curve = any(
                abs(b) > self.config.bulge_threshold
                for b in bulges
                if isinstance(b, (int, float))
            )
            if has_curve:
                return True

        # 2. Verificar flag explicita de curvatura
        if extra.get('has_arcs', False):
            return True

        # 3. Heuristica: verificar irregularidade dos vertices
        #    Polilinhas retangulares tem 4 ou 5 vertices (fechada)
        #    e angulos retos. Se tem mais vertices E area significativa,
        #    pode ser cambotado.
        vertices = entity.get('vertices', [])
        if len(vertices) >= 6:
            # Verificar se os angulos nao sao todos retos
            angles = self._compute_vertex_angles(vertices)
            if angles:
                non_right = sum(
                    1 for a in angles
                    if abs(a - 90.0) > 15.0 and abs(a - 180.0) > 15.0
                )
                if non_right >= 2:
                    return True

        return False

    def _compute_vertex_angles(
        self, vertices: List[List[float]]
    ) -> List[float]:
        """
        Calcula os angulos internos (em graus) nos vertices da polilinha.

        Retorna lista de angulos para cada vertice intermediario.
        """
        if len(vertices) < 3:
            return []

        angles: List[float] = []
        n = len(vertices)
        for i in range(1, n - 1):
            p0 = vertices[i - 1]
            p1 = vertices[i]
            p2 = vertices[i + 1]

            dx1 = p0[0] - p1[0]
            dy1 = p0[1] - p1[1]
            dx2 = p2[0] - p1[0]
            dy2 = p2[1] - p1[1]

            len1 = math.sqrt(dx1 * dx1 + dy1 * dy1)
            len2 = math.sqrt(dx2 * dx2 + dy2 * dy2)

            if len1 < 1e-9 or len2 < 1e-9:
                angles.append(180.0)
                continue

            cos_angle = (dx1 * dx2 + dy1 * dy2) / (len1 * len2)
            # Clamp para [-1, 1] para evitar erro em acos
            cos_angle = max(-1.0, min(1.0, cos_angle))
            angle_deg = math.degrees(math.acos(cos_angle))
            angles.append(angle_deg)

        return angles

    # ------------------------------------------------------------------
    # Deteccao de Misula (consolo estrutural)
    # ------------------------------------------------------------------

    def detectar_misula(
        self,
        entity: Dict[str, Any],
        vizinhos: List[Dict[str, Any]],
    ) -> bool:
        """
        Detecta se a entidade e uma misula (consolo/bracket).

        Criterios:
        1. Forma triangular ou trapezoidal (3-5 vertices)
        2. Area pequena (menor que misula_max_area_factor * area media pilares)
        3. Proxima de uma juncao viga-pilar (vizinhos incluem pilar E viga)

        Args:
            entity: Dict da entidade candidata
            vizinhos: Lista de entidades proximas (dentro de misula_max_distance)

        Returns:
            True se classificada como misula.
        """
        vertices = entity.get('vertices', [])
        n_verts = len(vertices)

        # Misula tem forma simples: 3 a 5 vertices
        if n_verts < 3 or n_verts > 6:
            return False

        # Verificar aspect_ratio (misula nao e muito alongada)
        aspect = self._get_aspect_ratio(entity)
        if aspect > self.config.misula_max_aspect_ratio:
            return False

        # Verificar area: misula e pequena
        area = self._get_area(entity)
        if area <= 0:
            return False

        # Calcular area media dos pilares vizinhos
        pilar_areas = [
            self._get_area(v)
            for v in vizinhos
            if self._is_pilar(v) and self._get_area(v) > 0
        ]
        if pilar_areas:
            avg_pilar_area = sum(pilar_areas) / len(pilar_areas)
            if area > avg_pilar_area * self.config.misula_max_area_factor:
                return False
        else:
            # Sem pilares vizinhos: usar threshold absoluto
            if area > 2000.0:
                return False

        # Verificar proximidade de juncao viga-pilar
        has_pilar_neighbor = any(self._is_pilar(v) for v in vizinhos)
        has_viga_neighbor = any(self._is_viga(v) for v in vizinhos)

        return has_pilar_neighbor and has_viga_neighbor

    # ------------------------------------------------------------------
    # Deteccao de Parede de Concreto
    # ------------------------------------------------------------------

    def detectar_parede(self, entity: Dict[str, Any]) -> bool:
        """
        Detecta parede de concreto armado.

        Criterios:
        1. aspect_ratio muito alto (> 10) - elemento muito alongado
        2. Area acima do threshold
        3. Layer compativel (PAREDE, CONCRETO, ou numerico)

        Args:
            entity: Dict da entidade

        Returns:
            True se classificada como parede.
        """
        aspect = self._get_aspect_ratio(entity)
        area = self._get_area(entity)

        if aspect < self.config.parede_min_aspect_ratio:
            return False

        if area < self.config.parede_min_area:
            return False

        # Verificar layer (opcional, reforca a classificacao)
        layer = entity.get('layer', '').lower()
        parede_layers = ('parede', 'concreto', 'wall', 'muro')
        # Layer numerico (TQS) tambem e valido
        is_numeric_layer = layer.isdigit()
        is_parede_layer = any(k in layer for k in parede_layers)

        # Se layer e compativel, confianca alta. Se nao, ainda pode ser
        # parede se aspect + area batem.
        if is_parede_layer or is_numeric_layer:
            return True

        # Sem layer especifico: exigir aspect_ratio ainda mais alto
        return aspect > self.config.parede_min_aspect_ratio * 1.5

    # ------------------------------------------------------------------
    # Deteccao de Reservatorio
    # ------------------------------------------------------------------

    def detectar_reservatorio(
        self,
        entity: Dict[str, Any],
        bbox_pavimento: Tuple[float, float, float, float],
    ) -> bool:
        """
        Detecta reservatorio (caixa d'agua embutida).

        Criterios:
        1. Retangulo grande (area > threshold)
        2. Proximo do perimetro do pavimento
        3. Entidade fechada

        Args:
            entity: Dict da entidade
            bbox_pavimento: (xmin, ymin, xmax, ymax) do pavimento inteiro

        Returns:
            True se classificada como reservatorio.
        """
        area = self._get_area(entity)
        if area < self.config.reservatorio_min_area:
            return False

        # Verificar se e fechada
        vertices = entity.get('vertices', [])
        if len(vertices) < 4:
            return False

        features = entity.get('features', {})
        is_closed = features.get('is_closed', 0.0) if isinstance(features, dict) else 0.0
        if isinstance(features, list) and len(features) > 3:
            is_closed = features[3]
        if is_closed < 0.5:
            return False

        # Verificar proximidade da borda do pavimento
        pav_xmin, pav_ymin, pav_xmax, pav_ymax = bbox_pavimento
        ent_xmin = float(entity.get('bbox_xmin', 0))
        ent_ymin = float(entity.get('bbox_ymin', 0))
        ent_xmax = float(entity.get('bbox_xmax', 0))
        ent_ymax = float(entity.get('bbox_ymax', 0))

        # Distancia minima da entidade a qualquer borda do pavimento
        dist_left = abs(ent_xmin - pav_xmin)
        dist_right = abs(pav_xmax - ent_xmax)
        dist_bottom = abs(ent_ymin - pav_ymin)
        dist_top = abs(pav_ymax - ent_ymax)
        min_dist = min(dist_left, dist_right, dist_bottom, dist_top)

        return min_dist <= self.config.reservatorio_borda_max_dist

    # ------------------------------------------------------------------
    # Deteccao de Tira de Reescoramento
    # ------------------------------------------------------------------

    def detectar_tira_reescoramento(self, entity: Dict[str, Any]) -> bool:
        """
        Detecta tira de reescoramento (reforco fino e longo).

        Criterios:
        1. Elemento linear fino (largura <= tira_max_largura)
        2. Comprimento significativo (>= tira_min_comprimento)
        3. Nao e parede (area menor)

        Args:
            entity: Dict da entidade

        Returns:
            True se classificada como tira de reescoramento.
        """
        w = self._get_width(entity)
        h = self._get_height(entity)

        if w <= 0 or h <= 0:
            return False

        # Identificar qual dimensao e a "largura" (menor) e "comprimento" (maior)
        largura = min(w, h)
        comprimento = max(w, h)

        if largura > self.config.tira_max_largura:
            return False

        if comprimento < self.config.tira_min_comprimento:
            return False

        # Excluir se area for grande demais (seria parede)
        area = self._get_area(entity)
        if area > self.config.parede_min_area:
            return False

        return True

    # ------------------------------------------------------------------
    # Classificador unificado
    # ------------------------------------------------------------------

    def classificar_elemento_especial(
        self,
        entity: Dict[str, Any],
        vizinhos: List[Dict[str, Any]],
        bbox_pavimento: Optional[Tuple[float, float, float, float]] = None,
    ) -> Optional[str]:
        """
        Classifica uma entidade como tipo especial, se aplicavel.

        Ordem de prioridade de deteccao:
        1. Misula (mais especifica, depende de contexto)
        2. Pilar Cambotado / Viga Cambotada (depende de tipo base)
        3. Parede
        4. Reservatorio
        5. Tira de Reescoramento

        Args:
            entity: Dict da entidade
            vizinhos: Entidades proximas
            bbox_pavimento: Bbox do pavimento (para reservatorio)

        Returns:
            Tipo especial como string, ou None se nao especial.
        """
        entity_type = self._get_entity_type(entity).lower()

        # 1. Misula: forma pequena na juncao viga-pilar
        if self.detectar_misula(entity, vizinhos):
            return 'misula'

        # 2. Cambotado: pilar ou viga com curvatura
        if self.detectar_cambotado(entity):
            if entity_type in ('pilar', 'pillar'):
                return 'pilar_cambotado'
            elif entity_type in ('viga', 'beam'):
                return 'viga_cambotada'
            # Tipo nao-definido com curvatura: inferir pelo aspect_ratio
            aspect = self._get_aspect_ratio(entity)
            if aspect < 3.0:
                return 'pilar_cambotado'
            else:
                return 'viga_cambotada'

        # 3. Parede de concreto
        if self.detectar_parede(entity):
            return 'parede'

        # 4. Reservatorio
        if bbox_pavimento and self.detectar_reservatorio(entity, bbox_pavimento):
            return 'reservatorio'

        # 5. Tira de Reescoramento
        if self.detectar_tira_reescoramento(entity):
            return 'tira_reescoramento'

        return None

    # ------------------------------------------------------------------
    # Processamento de pavimento completo
    # ------------------------------------------------------------------

    def processar_pavimento(
        self,
        entities: List[Dict[str, Any]],
        bbox_pavimento: Optional[Tuple[float, float, float, float]] = None,
    ) -> Dict[str, str]:
        """
        Processa todas as entidades de um pavimento e classifica
        os elementos especiais.

        Se bbox_pavimento nao for fornecido, calcula automaticamente
        a partir das entidades.

        Args:
            entities: Lista de dicts de entidade (StructuralEntity serializada)

        Returns:
            Dict mapeando entity_id -> tipo_especial.
            Apenas entidades classificadas como especiais estao presentes.
        """
        if not entities:
            return {}

        # Calcular bbox do pavimento se nao fornecido
        if bbox_pavimento is None:
            bbox_pavimento = self._calcular_bbox_pavimento(entities)

        # Construir indice de vizinhos por proximidade
        # Para cada entidade, encontrar vizinhos num raio de misula_max_distance
        vizinhos_map = self._build_neighbor_map(entities)

        resultado: Dict[str, str] = {}
        contadores: Dict[str, int] = {t: 0 for t in TIPOS_ESPECIAIS}

        for entity in entities:
            entity_id = entity.get('entity_id', entity.get('id', ''))
            if not entity_id:
                continue

            vizinhos = vizinhos_map.get(entity_id, [])
            tipo = self.classificar_elemento_especial(
                entity, vizinhos, bbox_pavimento
            )

            if tipo:
                resultado[entity_id] = tipo
                contadores[tipo] = contadores.get(tipo, 0) + 1

        # Log resumo
        total_especiais = len(resultado)
        if total_especiais > 0:
            detalhes = ', '.join(
                f"{t}={c}" for t, c in contadores.items() if c > 0
            )
            logger.info(
                f"Special elements detected: {total_especiais} "
                f"out of {len(entities)} ({detalhes})"
            )
        else:
            logger.debug(
                f"No special elements in pavimento "
                f"({len(entities)} entities analyzed)"
            )

        return resultado

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_neighbor_map(
        self, entities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Constroi mapa de vizinhos por proximidade usando forca bruta.

        Para pavimentos pequenos (<500 entidades) isso e suficiente.
        Para pavimentos maiores, considere integrar com SpatialIndex/rtree.
        """
        radius = max(
            self.config.misula_max_distance,
            self.config.reservatorio_borda_max_dist,
        )

        neighbor_map: Dict[str, List[Dict[str, Any]]] = {}

        for i, ent_a in enumerate(entities):
            eid = ent_a.get('entity_id', ent_a.get('id', ''))
            if not eid:
                continue

            cx_a = self._get_center_x(ent_a)
            cy_a = self._get_center_y(ent_a)
            neighbors: List[Dict[str, Any]] = []

            for j, ent_b in enumerate(entities):
                if i == j:
                    continue
                cx_b = self._get_center_x(ent_b)
                cy_b = self._get_center_y(ent_b)
                dist = math.sqrt((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2)
                if dist <= radius:
                    neighbors.append(ent_b)

            neighbor_map[eid] = neighbors

        return neighbor_map

    def _calcular_bbox_pavimento(
        self, entities: List[Dict[str, Any]]
    ) -> Tuple[float, float, float, float]:
        """Calcula a bounding box envolvente de todas as entidades."""
        xmins = [float(e.get('bbox_xmin', 0)) for e in entities]
        xmaxs = [float(e.get('bbox_xmax', 0)) for e in entities]
        ymins = [float(e.get('bbox_ymin', 0)) for e in entities]
        ymaxs = [float(e.get('bbox_ymax', 0)) for e in entities]

        return (
            min(xmins) if xmins else 0.0,
            min(ymins) if ymins else 0.0,
            max(xmaxs) if xmaxs else 0.0,
            max(ymaxs) if ymaxs else 0.0,
        )

    @staticmethod
    def _get_aspect_ratio(entity: Dict[str, Any]) -> float:
        """Retorna aspect_ratio da entidade."""
        features = entity.get('features', {})
        if isinstance(features, dict):
            ar = features.get('aspect_ratio', 0.0)
            if ar:
                return float(ar)

        # Calcular do bbox
        w = abs(float(entity.get('bbox_xmax', 0)) - float(entity.get('bbox_xmin', 0)))
        h = abs(float(entity.get('bbox_ymax', 0)) - float(entity.get('bbox_ymin', 0)))
        if h > 0:
            return min(w / h, 100.0)
        return 1.0

    @staticmethod
    def _get_area(entity: Dict[str, Any]) -> float:
        """Retorna area da entidade (bbox)."""
        w = abs(float(entity.get('bbox_xmax', 0)) - float(entity.get('bbox_xmin', 0)))
        h = abs(float(entity.get('bbox_ymax', 0)) - float(entity.get('bbox_ymin', 0)))
        return w * h

    @staticmethod
    def _get_width(entity: Dict[str, Any]) -> float:
        return abs(float(entity.get('bbox_xmax', 0)) - float(entity.get('bbox_xmin', 0)))

    @staticmethod
    def _get_height(entity: Dict[str, Any]) -> float:
        return abs(float(entity.get('bbox_ymax', 0)) - float(entity.get('bbox_ymin', 0)))

    @staticmethod
    def _get_center_x(entity: Dict[str, Any]) -> float:
        return (float(entity.get('bbox_xmin', 0)) + float(entity.get('bbox_xmax', 0))) / 2

    @staticmethod
    def _get_center_y(entity: Dict[str, Any]) -> float:
        return (float(entity.get('bbox_ymin', 0)) + float(entity.get('bbox_ymax', 0))) / 2

    @staticmethod
    def _get_entity_type(entity: Dict[str, Any]) -> str:
        """Retorna tipo da entidade (campo entity_type ou entity_type_hint)."""
        return (
            entity.get('entity_type', '')
            or entity.get('entity_type_hint', '')
            or ''
        )

    @staticmethod
    def _is_pilar(entity: Dict[str, Any]) -> bool:
        t = SpecialElementDetector._get_entity_type(entity).lower()
        return t in ('pilar', 'pillar')

    @staticmethod
    def _is_viga(entity: Dict[str, Any]) -> bool:
        t = SpecialElementDetector._get_entity_type(entity).lower()
        return t in ('viga', 'beam')
