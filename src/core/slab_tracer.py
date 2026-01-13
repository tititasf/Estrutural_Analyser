from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union
from typing import List, Tuple, Optional, Dict
import math

class SlabTracer:
    """
    Algoritmo 'Boundary Tracer' para Lajes.
    Usa 'Path Finding' (Polygonize) para encontrar polígonos fechados formados por vigas/paredes.
    """
    def __init__(self, spatial_index):
        self.spatial_index = spatial_index

    def trace_boundary(self, start_point: Tuple[float, float], search_radius: float = 1000.0, valid_layers: List[str] = None) -> Optional[Polygon]:
        """
        Encontra o polígono fechado que contém o start_point.
        valid_layers: Lista de layers permitidos/preferenciais.
        """
        # 1. Coletar linhas candidatas no raio ao redor do ponto
        cx, cy = start_point
        bounds = (cx - search_radius, cy - search_radius, cx + search_radius, cy + search_radius)
        
        candidates = self.spatial_index.query_bbox(bounds)
        lines = []
        
        for item in candidates:
            # Item: geometria original ou dict que a envelopa?
            # O SpatialIndex guarda o objeto original passado no insert.
            # No DXFLoader modificado, lines/polylines são dicts com 'layer'.
            
            geom = None
            layer = None
            
            if isinstance(item, dict):
                # Se for dict vindo do DXFLoader novo
                layer = item.get('layer')
                if 'points' in item: # Polyline
                    pts = item['points']
                    if len(pts) > 1: geom = LineString(pts)
                elif 'start' in item: # Line
                    geom = LineString([item['start'], item['end']])
            
            # Retrocompatibilidade com tupla crua (caso algo mais insira assim)
            elif isinstance(item, tuple) and len(item) == 2: 
                geom = LineString(item)
            elif isinstance(item, list) and len(item) > 1:
                geom = LineString(item)
                
            if geom:
                # Filtragem por Layer (Inteligência)
                if valid_layers:
                    # Se tiver filtro e a linha tiver layer, testamos.
                    # Se linha não tiver layer (tupla antiga), aceitamos ou rejeitamos? Aceitamos por segurança.
                    # Mas se tiver layer e não estiver na lista, rejeita.
                    if layer and layer not in valid_layers:
                        continue
                
                lines.append(geom)
        
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

    def detect_slabs_from_texts(self, texts: List[Dict], search_radius: float = 2000.0, valid_layers: List[str] = None) -> List[Dict]:
        """
        Varre textos buscando padrões de laje (Lx, Laje X) e tenta traçar limites.
        """
        slabs = []
        import re
        # Padrão: Começa com L seguido de numero, ou LAJE...
        # Ex: "L1", "L-2", "LAJE 03"
        slab_pattern = re.compile(r'^(L|LAJE)\s*[-_]?\s*\d+[a-zA-Z]*$', re.IGNORECASE)
        
        # DEBUG
        sample_texts = [t.get('text') for t in texts[:5]]
        print(f"[DEBUG] SlabTracer checking {len(texts)} texts. Samples: {sample_texts}")
        
        for t in texts:
            txt = t.get('text', '').strip()
            if slab_pattern.match(txt):
                pos = t.get('pos')
                if not pos: continue
                
                # Tentar traçar contorno
                poly = self.trace_boundary(pos, search_radius, valid_layers=valid_layers)
                
                # Se falhar tracing, cria um polígono dummy pequeno ou apenas marca o ponto
                # Para MVP, se não achar contorno, criamos um placeholder
                found_poly = bool(poly)
                points = []
                area = 0.0
                
                if poly:
                    points = list(poly.exterior.coords)
                    area = poly.area
                else:
                    # Fallback: Quadrado de 50x50 em volta do texto
                    cx, cy = pos
                    points = [
                        (cx-25, cy-25), (cx+25, cy-25),
                        (cx+25, cy+25), (cx-25, cy+25),
                        (cx-25, cy-25)
                    ]
                
                slabs.append({
                    'id': f"temp_{len(slabs)}", # Temp ID
                    'name': txt.upper(), # L1
                    'pos': pos,
                    'points': points,
                    'area': area,
                    'neighbors': [],
                    'is_detected': found_poly,
                    'type': 'Laje' # Essential for DetailCard identification
                })
        
        return slabs
