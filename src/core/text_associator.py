"""
text_associator.py - Motor de Associacao de Textos DXF a Geometrias Estruturais

Associa textos DXF (ex: 'P1', 'V2', 'L3') as geometrias estruturais
(pilares, vigas, lajes) por proximidade espacial usando logica de 3 raios.

Raios de busca:
  - Raio 1 (Imediato):  Texto contido dentro do poligono  -> Score 1.0
  - Raio 2 (Adjacente):  Distancia <= 5 unidades          -> Score 0.8
  - Raio 3 (Contextual): Distancia <= context_radius       -> Score 0.5..0.0 (decaimento linear)
"""

from shapely.geometry import Polygon, Point
from typing import List, Dict, Optional, Tuple
import math


class TextAssociator:
    """
    Motor de Associacao Probabilistica (Logica de 3 Raios).
    Vincula textos (ex: 'P1', 'V2') as geometrias estruturais.

    Atributos:
        spatial_index: Instancia de SpatialIndex (opcional, reservado para otimizacao futura).
        texts: Lista de dicionarios com chaves 'text' (str) e 'pos' (Tuple[float, float]).
    """

    def __init__(self, spatial_index: Optional[object], texts: List[Dict]) -> None:
        """
        Inicializa o associador de textos.

        Args:
            spatial_index: Instancia de SpatialIndex (pode ser None; reservado
                           para otimizacao futura via indice espacial de textos).
            texts: Lista de textos DXF, cada um com formato:
                   {'text': str, 'pos': (x, y)}
        """
        self.spatial_index = spatial_index
        self.texts: List[Dict] = texts

    def find_associated_text(
        self,
        polygon: Polygon,
        context_radius: float = 100.0,
    ) -> Tuple[Optional[str], float]:
        """
        Encontra o melhor texto candidato para o poligono dado.

        Usa logica de 3 raios para calcular score de associacao:
          - 1.0: Texto contido dentro do poligono (Raio Imediato)
          - 0.8: Texto tocando/muito proximo, dist <= 5 unidades (Raio Adjacente)
          - 0.5..0.0: Texto proximo com decaimento linear (Raio Contextual)

        Args:
            polygon: Poligono Shapely representando a geometria estrutural.
            context_radius: Raio maximo de busca em unidades DXF (default: 100.0).

        Returns:
            Tupla (texto, score) do melhor candidato, ou (None, 0.0) se nenhum encontrado.
        """
        minx, miny, maxx, maxy = polygon.bounds
        search_bbox = (
            minx - context_radius,
            miny - context_radius,
            maxx + context_radius,
            maxy + context_radius,
        )

        candidates: List[Tuple[str, float, float]] = []

        for t in self.texts:
            tx, ty = t["pos"]

            # Filtro rapido por bounding box expandido
            if not (
                search_bbox[0] <= tx <= search_bbox[2]
                and search_bbox[1] <= ty <= search_bbox[3]
            ):
                continue

            p_text = Point(tx, ty)
            dist = polygon.distance(p_text)

            score = 0.0

            # Logica de 3 Raios
            if polygon.contains(p_text):
                score = 1.0  # Raio 1: Imediato
            elif dist <= 5.0:
                score = 0.8  # Raio 2: Adjacente (Touching/Very Close)
            elif dist <= context_radius:
                # Raio 3: Contextual (Decaimento linear)
                # Score varia de 0.5 (perto) ate 0.0 (limite)
                decay = 1.0 - (dist / context_radius)
                score = 0.5 * decay

            if score > 0:
                candidates.append((t["text"], score, dist))

        if not candidates:
            return None, 0.0

        # Ordenar pelo score decrescente, desempate por distancia crescente
        candidates.sort(key=lambda x: (-x[1], x[2]))

        return candidates[0][0], candidates[0][1]
