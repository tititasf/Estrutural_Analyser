import logging
from typing import List, Dict, Tuple
from shapely.geometry import Point, LineString, Polygon
from .spatial_index import SpatialIndex

class BeamTracer:
    """
    Motor especializado em identificar vigas baseadas em nomes (V1, V2...)
    e traçar seu caminho geométrico entre apoios.
    """
    def __init__(self, spatial_index: SpatialIndex):
        self.spatial_index = spatial_index

    def detect_beams(self, texts: List[Dict], all_lines: List[Dict]) -> List[Dict]:
        """
        Identifica vigas a partir de textos que seguem o padrão V + Número.
        """
        beams = []
        for txt in texts:
            content = txt['text'].upper().strip()
            # Padrão: V1, V2, V10A, etc.
            if content.startswith('V') and any(c.isdigit() for c in content):
                pos = txt['pos']
                # Tentar encontrar a geometria da viga próxima ao texto
                geometry = self._find_beam_geometry(pos, all_lines)
                if geometry:
                    beams.append({
                        'name': content,
                        'type': 'Viga',
                        'pos': pos,
                        'geometry': geometry,
                        'neighbors': [],
                        'id': f"beam_{content}_{len(beams)}"
                    })
        return beams

    def _find_beam_geometry(self, pos: Tuple[float, float], all_lines: List[Dict]) -> Dict:
        """
        Encontra o conjunto de geometrias (linhas e textos) vinculados a uma viga.
        """
        search_area = (pos[0]-250, pos[1]-250, pos[0]+250, pos[1]+250)
        candidates = self.spatial_index.query_bbox(search_area)
        
        beam_geometry = {
            'lines': [],
            'texts': []
        }
        
        # Filtra candidatos para pegar o que parece ser a viga (nome/dim/geom)
        for cand in candidates:
            if isinstance(cand, dict):
                if 'points' in cand:
                    beam_geometry['lines'].append(cand['points'])
                elif 'text' in cand:
                    beam_geometry['texts'].append(cand)
            elif isinstance(cand, list): # Caso seja apenas lista de pontos
                beam_geometry['lines'].append(cand)
                
        return beam_geometry
