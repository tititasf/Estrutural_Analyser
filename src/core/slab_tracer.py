from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union
from typing import List, Tuple, Optional
import math

class SlabTracer:
    """
    Algoritmo 'Boundary Tracer' para Lajes.
    Usa 'Path Finding' (Polygonize) para encontrar polígonos fechados formados por vigas/paredes.
    """
    def __init__(self, spatial_index):
        self.spatial_index = spatial_index

    def trace_boundary(self, start_point: Tuple[float, float], search_radius: float = 1000.0) -> Optional[Polygon]:
        """
        Encontra o polígono fechado que contém o start_point.
        """
        # 1. Coletar linhas candidatas no raio ao redor do ponto
        cx, cy = start_point
        bounds = (cx - search_radius, cy - search_radius, cx + search_radius, cy + search_radius)
        
        candidates = self.spatial_index.query_bbox(bounds)
        lines = []
        
        for item in candidates:
            # Item pode ser polilinha, linha (tupla de pts) ou Polygon
            # Precisamos de LineStrings
            if isinstance(item, tuple) and len(item) == 2: # Linha ((x1,y1), (x2,y2))
                lines.append(LineString(item))
            elif isinstance(item, list): # Polyline
                if len(item) > 1:
                    lines.append(LineString(item))
            # Ignorar outros poligonos por enquanto ou explodi-los
        
        if not lines:
            return None

        # 2. Polygonize
        # Pode ser pesado se muitas linhas. Unary_union ajuda a limpar?
        # Polygonize requer linhas que se tocam perfeitamente ou cruzam.
        # DXF real pode ter gaps. (MVP: Assumir conexões decentes ou tolerância zero).
        
        try:
            # Tentar formar polígonos
            # Para robustez, noding (unary_union) é bom mas lento.
            # Vamos tentar direto primeiro.
            polygons = list(polygonize(lines))
            
            target_pt = Point(cx, cy)
            
            # Encontrar qual polígono contém o ponto
            for poly in polygons:
                if poly.contains(target_pt):
                    return poly
                    
        except Exception as e:
            # Falha na geometria
            return None
            
        return None
