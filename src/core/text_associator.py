from shapely.geometry import Polygon, Point
from typing import List, Dict, Optional, Tuple
import math

class TextAssociator:
    """
    Motor de Associação Probabilística (Lógica de 3 Raios).
    Vincula textos (ex: 'P1', 'V2') às geometrias estruturais.
    """
    def __init__(self, spatial_index, texts: List[Dict]):
        self.spatial_index = spatial_index
        self.texts = texts # List[{'text': str, 'pos': (x, y)}]

    def find_associated_text(self, polygon: Polygon, context_radius: float = 100.0) -> Tuple[Optional[str], float]:
        """
        Encontra o melhor texto candidato para o polígono dado.
        Retorna (Texto, Score).
        Scores:
        - 1.0: Contido (Raio Curto)
        - 0.8: Tocando/Muito próximo (Raio Médio - < 5 units)
        - 0.5 -> 0.1: Próximo (Raio Longo - Decaimento linear)
        """
        minx, miny, maxx, maxy = polygon.bounds
        search_bbox = (minx - context_radius, miny - context_radius, 
                       maxx + context_radius, maxy + context_radius)
        
        # 1. Candidatos via Rtree (otimização)
        # O spatial_index guarda geometrias, mas precisamos de index espacial de TEXTOS para ser rápido.
        # Se o spatial_index atual for só de polígonos, precisamos de um para textos ou iterar se forem poucos.
        # Assumindo que passamos um index exclusivo de textos ou reconstruímos query manualmente por enquanto.
        # Vamos iterar localmente nos candidatos retornados pelo index se ele tiver textos, 
        # mas o spatial_index atual no projeto parece ser genérico.
        # Ajuste: Vamos assumir que recebemos candidatos filtrados ou iteramos brute-force se < 1000 textos (rápido o suficiente em Py puro).
        # Melhor: Usar o spatial_index se ele tiver textos. Caso contrário, filtrar por distancia manhattan simples aqui.
        
        candidates = []
        
        for t in self.texts:
            tx, ty = t['pos']
            # Filtro rápido BBox
            if not (search_bbox[0] <= tx <= search_bbox[2] and search_bbox[1] <= ty <= search_bbox[3]):
                continue
                
            p_text = Point(tx, ty)
            dist = polygon.distance(p_text)
            
            score = 0.0
            
            # Lógica de 3 Raios
            if polygon.contains(p_text):
                score = 1.0 # Raio 1: Imediato
            elif dist <= 5.0:
                score = 0.8 # Raio 2: Adjacente (Touching/Very Close)
            elif dist <= context_radius:
                # Raio 3: Contextual (Decaimento linear)
                # Score varia de 0.5 (perto) até 0.0 (limite)
                decay = 1.0 - (dist / context_radius)
                score = 0.5 * decay
            
            if score > 0:
                candidates.append((t['text'], score, dist))
        
        if not candidates:
            return None, 0.0
            
        # Ordenar pelo Score decrescente
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[0][0], candidates[0][1]
