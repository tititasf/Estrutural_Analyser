from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from typing import List, Tuple, Dict, Any
import math

class BeamWalker:
    """
    Algoritmo 'Beam Walker': Percorre o eixo de uma viga detectando conflitos (Pilares/Vigas/Paredes).
    """
    def __init__(self, spatial_index):
        self.spatial_index = spatial_index

    def walk(self, start_pt: Tuple[float, float], end_pt: Tuple[float, float], beam_width: float = 15.0) -> Dict[str, Any]:
        """
        Executa o raycasting do start_pt ao end_pt.
        Retorna lista de segmentos (Vão Livre vs Conflito).
        """
        axis_line = LineString([start_pt, end_pt])
        total_length = axis_line.length
        
        # 1. Identificar candidatos a colisão usando Rtree (Bounding Box do eixo)
        minx, miny, maxx, maxy = axis_line.bounds
        candidates = self.spatial_index.query_bbox((minx, miny, maxx, maxy))
        
        intersections = []
        
        for item in candidates:
            geom = None
            type_label = "Desconhecido"
            element_name = None
            
            # Reconhecer entidades indexadas como dicts (do main.py)
            if isinstance(item, dict):
                content = str(item.get('text', '')).upper()
                if 'points' in item: # Polilinha/Pilar
                    geom = Polygon(item['points'])
                    type_label = "Pilar"
                    element_name = item.get('name', 'Pilar')
                elif 'start' in item: # Linha
                    geom = LineString([item['start'], item['end']])
                    type_label = "Suporte"
                    element_name = item.get('name', 'Viga/Parede')
                elif content: # Texto
                    p = item['pos']
                    geom = Point(p).buffer(10) # Area de influência do texto
                    type_label = "Texto"
                    element_name = content
            
            if geom and geom.intersects(axis_line):
                intersection = geom.intersection(axis_line)
                if not intersection.is_empty:
                    if intersection.geom_type == 'LineString':
                        parts = [intersection]
                    elif intersection.geom_type == 'Polygon':
                        parts = [intersection.exterior]
                    elif intersection.geom_type in ('MultiLineString', 'MultiPolygon'):
                        parts = [] # Simplificar
                    else: continue
                        
                    for part in parts:
                        proj_start = axis_line.project(Point(part.coords[0]))
                        proj_end = axis_line.project(Point(part.coords[-1]))
                        d_start, d_end = sorted((proj_start, proj_end))
                        
                        intersections.append({
                            'type': type_label,
                            'name': element_name,
                            'start': d_start,
                            'end': d_end,
                            'length': d_end - d_start
                        })

        # 2. Ordenar e Fundir interseções que se sobrepõem (Clean up)
        intersections.sort(key=lambda x: x['start'])
        
        # Merge simples
        merged_conflicts = []
        if intersections:
            current = intersections[0]
            for next_conflict in intersections[1:]:
                if next_conflict['start'] < current['end']: # Sobreposição
                    current['end'] = max(current['end'], next_conflict['end'])
                    current['length'] = current['end'] - current['start']
                    # Tipo misto? Manter o primeiro
                else:
                    merged_conflicts.append(current)
                    current = next_conflict
            merged_conflicts.append(current)
            
        # 3. Gerar Segmentos (Vão Livre vs Conflito)
        segments = []
        cursor = 0.0
        
        for conflict in merged_conflicts:
            if conflict['start'] > cursor:
                segments.append({
                    'type': 'Vão Livre',
                    'length': conflict['start'] - cursor,
                    'start_dist': cursor,
                    'end_dist': conflict['start']
                })
            
            segments.append({
                'type': conflict['type'],
                'element_name': conflict.get('name', 'Apoio'),
                'length': conflict['length'],
                'start_dist': conflict['start'],
                'end_dist': conflict['end']
            })
            cursor = conflict['end']
            
        # Vão livre final
        if cursor < total_length:
             segments.append({
                    'type': 'Vão Livre',
                    'length': total_length - cursor,
                    'start_dist': cursor,
                    'end_dist': total_length
                })

        return {
            'start_node': merged_conflicts[0].get('name', 'Início') if merged_conflicts else 'Livre',
            'end_node': merged_conflicts[-1].get('name', 'Fim') if merged_conflicts else 'Livre',
            'total_length': total_length,
            'segments': segments,
            'conflicts_count': len(merged_conflicts)
        }
