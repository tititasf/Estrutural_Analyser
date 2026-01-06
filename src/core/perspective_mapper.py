from shapely.geometry import Polygon
import numpy as np

class PillarPerspectiveMapper:
    """
    Traduz a geometria bruta em faces A, B, C, D, E, F, G, H 
    seguindo as regras de perspectiva do usuário.
    """
    @staticmethod
    def identify_shape(points):
        poly = Polygon(points)
        area = poly.area
        bbox = poly.bounds # (minx, miny, maxx, maxy)
        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        
        # Heurística de complexidade por número de vértices e convexidade
        num_v = len(set(points))
        if num_v <= 5: # Retangular (com fechamento)
            return "Retangular", "Horizontal" if bw > bh else "Vertical"
        
        # Para L, T, U, usamos a área relativa ao bbox (Convex Hull)
        # Pilares complexos têm 'buracos' na bounding box
        hull_area = poly.convex_hull.area
        ratio = area / hull_area
        
        if ratio > 0.85: return "Retangular", "Vertical"
        
        # Identificação por análise de 'braços' (simplificado para MVP)
        if num_v >= 10: return "Em U", "Normal"
        if num_v >= 8: return "Em T", "Normal"
        return "Em L", "Normal"

    @staticmethod
    def map_sides(points, shape_type, orientation):
        """
        Mapeia os segmentos geométricos para as faces nominais A, B, C, D...
        """
        sides = {}
        if shape_type == "Retangular":
            if orientation == "Horizontal":
                # A: Abaixo, B: Acima, C: Esquerda, D: Direita
                keys = ['A', 'B', 'C', 'D']
            else:
                # A: Esquerda, B: Direita, C: Acima, D: Abaixo
                keys = ['A', 'B', 'C', 'D']
        elif shape_type == "Em L":
            # L: pé esquerda=A, direita=B, acima=C. deitado baixo=E, cima=F, direita=D
            keys = ['A', 'B', 'C', 'D', 'E', 'F']
        elif shape_type == "Em T":
            # T: horizontal A topo, C esq, D dir. pé esq=E, dir=F, baixo=H. baixo_esq=B, baixo_dir=G
            keys = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        elif shape_type == "Em U":
            # U: baixo=A, interior=B, ponta_esq esq=E dir=F topo=C. ponta_dir esq=H dir=G topo=D
            keys = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        else:
            keys = ['Topo', 'Base']
            
        for k in keys: 
            sides[k] = {} # Usar dicionário para armazenar dados do lado
        return sides
