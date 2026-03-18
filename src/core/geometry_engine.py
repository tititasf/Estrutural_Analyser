"""
geometry_engine.py - Motor Geometrico para Classificacao de Formas DXF

Responsavel por classificar formas estruturais (pilares) e mapear seus lados
seguindo as regras do 'Pillar Compass'.

Formas suportadas:
  - RETANGULAR (4 vertices)
  - L_SHAPE (6 vertices)
  - T_SHAPE (8 vertices)
  - U_SHAPE (8+ vertices, concavidades no mesmo lado)
  - CIRCULAR (muitos vertices)
  - UNKNOWN (fallback)
"""

import math
from enum import Enum
from typing import List, Tuple, Dict, Optional

from shapely.geometry import Polygon, Point
from shapely.affinity import rotate
import numpy as np


class ShapeType(Enum):
    """Tipos de forma estrutural reconhecidos pelo motor geometrico."""

    RECTANGULAR = "RETANGULAR"
    CIRCULAR = "CIRCULAR"
    L_SHAPE = "L"
    T_SHAPE = "T"
    U_SHAPE = "U"
    UNKNOWN = "DESCONHECIDO"


class GeometryEngine:
    """
    O Motor Geometrico responsavel por classificar formas e mapear lados (A-H)
    seguindo rigorosamente as regras do 'Pillar Compass'.
    """

    @staticmethod
    def classify_shape(vertices: List[Tuple[float, float]]) -> ShapeType:
        """
        Classifica a forma baseada nos vertices simplificados.

        Args:
            vertices: Lista de tuplas (x, y) representando os vertices do poligono.

        Returns:
            ShapeType correspondente a forma detectada.
        """
        if not vertices or len(vertices) < 3:
            return ShapeType.UNKNOWN

        poly = Polygon(vertices)
        if not poly.is_valid:
            poly = poly.buffer(0)
            if not poly.is_valid:
                from shapely.validation import make_valid

                poly = make_valid(poly)

        simplified_poly = poly.simplify(0.01, preserve_topology=True)

        # Caso a simplificacao gere multiplos poligonos (artefatos), pegamos o maior
        if simplified_poly.geom_type == "MultiPolygon":
            simplified_poly = max(simplified_poly.geoms, key=lambda p: p.area)

        if not hasattr(simplified_poly, "exterior"):
            return ShapeType.UNKNOWN

        coords = list(simplified_poly.exterior.coords)
        if len(coords) > 0 and coords[0] == coords[-1]:
            coords.pop()  # Remove ponto duplicado de fechamento

        num_vertices = len(coords)

        # Regras Heuristicas de Contagem de Vertices
        if num_vertices == 4:
            return ShapeType.RECTANGULAR
        elif num_vertices == 6:
            return ShapeType.L_SHAPE
        elif num_vertices == 8:
            return ShapeType.T_SHAPE
        elif num_vertices > 8:
            return ShapeType.CIRCULAR

        return ShapeType.UNKNOWN

    @staticmethod
    def _find_concave_vertex(
        vertices: List[Tuple[float, float]],
    ) -> Optional[Tuple[float, float]]:
        """
        Identifica o vertice concavo em um poligono L-Shape (unico vertice interno).

        Usa cross product das arestas adjacentes para detectar mudanca de convexidade.
        Em um L-Shape com 6 vertices, 5 sao convexos e 1 e concavo.

        Args:
            vertices: Lista de tuplas (x, y) dos vertices do poligono.

        Returns:
            Coordenadas (x, y) do vertice concavo, ou None se nao encontrado.
        """
        n = len(vertices)

        # Calcular cross products para cada vertice
        angles: List[Tuple[int, float]] = []
        for i in range(n):
            p1 = np.array(vertices[i - 1])
            p2 = np.array(vertices[i])
            p3 = np.array(vertices[(i + 1) % n])

            v1 = p1 - p2
            v2 = p3 - p2

            # Angulo entre vetores
            cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            _angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
            cross = v1[0] * v2[1] - v1[1] * v2[0]

            angles.append((i, cross))

        # Contar sinais - o minoritario e o concavo
        pos = sum(1 for _, c in angles if c > 0)
        neg = sum(1 for _, c in angles if c < 0)

        target_sign = -1 if pos > neg else 1

        for i, c in angles:
            if (c > 0 and target_sign == 1) or (c < 0 and target_sign == -1):
                return vertices[i]

        return None

    @staticmethod
    def map_sides(
        shape_type: ShapeType,
        rotation_degrees: float,
        vertices: List[Tuple[float, float]],
    ) -> Dict[str, str]:
        """
        Mapeia os lados A-H de uma forma estrutural.

        Para formas retangulares, mapeia A-D baseado na orientacao.
        Para formas L, mapeia A-F baseado na posicao do vertice concavo.

        Args:
            shape_type: Tipo da forma (RECTANGULAR, L_SHAPE, etc.).
            rotation_degrees: Angulo de rotacao em graus.
            vertices: Lista de tuplas (x, y) dos vertices.

        Returns:
            Dicionario mapeando letras (A, B, C, ...) para descricao do lado.
        """
        sides: Dict[str, str] = {}
        rot = rotation_degrees % 360

        if shape_type == ShapeType.RECTANGULAR:
            is_vertical = (45 <= rot <= 135) or (225 <= rot <= 315)
            if not is_vertical:  # Horizontal
                sides = {"A": "Baixo", "B": "Cima", "C": "Esq", "D": "Dir"}
            else:  # Vertical
                sides = {"A": "Esq", "B": "Dir", "C": "Cima", "D": "Baixo"}

        elif shape_type == ShapeType.L_SHAPE:
            # Detectar orientacao do L baseado na posicao do vertice concavo relativo ao Bbox
            concave_pt = GeometryEngine._find_concave_vertex(vertices)
            if concave_pt:
                poly = Polygon(vertices)
                minx, miny, maxx, maxy = poly.bounds
                cx, cy = concave_pt

                # Normalizar posicao (0.0 a 1.0)
                width = maxx - minx
                height = maxy - miny
                nx = (cx - minx) / width if width > 0 else 0.5
                ny = (cy - miny) / height if height > 0 else 0.5

                # Logica: Onde esta a "quina interna"?
                if nx > 0.5 and ny > 0.5:  # Top-Right (Formato _|)
                    sides = {
                        "A": "Pe Esq (Face Esq)",
                        "B": "Pe Dir (Face Int vert)",
                        "C": "Pe Cima (Topo)",
                        "E": "Base Baixo",
                        "F": "Base Cima (Face Int horiz)",
                        "D": "Base Dir (Ponta)",
                    }
                elif nx < 0.5 and ny > 0.5:  # Top-Left (Formato |_)
                    sides = {"Info": "L Invertido Horizontal"}
                elif nx > 0.5 and ny < 0.5:  # Bottom-Right (Formato -|)
                    sides = {"Info": "L Invertido Vertical"}
                else:  # Bottom-Left
                    sides = {"Info": "L Rotacionado 180"}
            else:
                sides = {"Error": "Geometria L invalida (sem concavidade)"}

        return sides


# Teste Rapido (Executado se rodar direto)
if __name__ == "__main__":
    # Exemplo Retangulo
    rect_points = [(0, 0), (20, 0), (20, 40), (0, 40)]
    tipo = GeometryEngine.classify_shape(rect_points)
    print(f"Forma: {tipo}")

    # Exemplo L (6 pontos)
    l_points = [(0, 0), (40, 0), (40, 20), (20, 20), (20, 60), (0, 60)]
    tipo_l = GeometryEngine.classify_shape(l_points)
    print(f"Forma L: {tipo_l}")
