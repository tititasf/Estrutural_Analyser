"""
BeamTracer - Motor de deteccao de vigas em projetos estruturais DXF.

Identifica vigas por padrao de nomenclatura (V1, V2, V10A, V1a) em textos DXF
e classifica a geometria associada (lados, fundo, apoios, dimensoes).
"""

import logging
import re
from typing import List, Dict, Tuple

from shapely.geometry import Point, LineString, Polygon
from .spatial_index import SpatialIndex

logger = logging.getLogger(__name__)


class BeamTracer:
    """
    Motor especializado em identificar vigas baseadas em nomes (V1, V2...)
    e tracar seu caminho geometrico entre apoios.
    """

    def __init__(self, spatial_index: SpatialIndex):
        self.spatial_index = spatial_index

    def detect_beams(self, texts: List[Dict], all_lines: List[Dict]) -> List[Dict]:
        """
        Identifica vigas a partir de textos que seguem o padrao V + Numero.

        Diferencia sufixos:
        - V1a (minusculo): Segmento de viga.
        - V1A (maiusculo): Outra viga.

        Se multiplos itens tiverem o mesmo nome (ex: V1), gera sufixos
        automaticos (V1a, V1b...).

        Args:
            texts: Lista de dicts com 'text' e 'pos' extraidos do DXF.
            all_lines: Lista de dicts representando linhas/polilinhas do DXF.

        Returns:
            Lista de dicts representando vigas detectadas com geometria classificada.
        """
        raw_beams = []

        for txt in texts:
            content = txt['text'].strip()
            # Padrao: V1, V2, V10A, V1a etc. (Case Sensitive)
            if (content.startswith('V') or content.startswith('v')) and \
               any(c.isdigit() for c in content):
                pos = txt['pos']
                geometry = self._find_beam_geometry(pos, all_lines)
                if geometry:
                    raw_beams.append({
                        'name': content,
                        'type': 'Viga',
                        'pos': pos,
                        'geometry': geometry,
                        'neighbors': []
                    })

        # Pos-processamento para gerar nomes de segmentos se houver duplicatas nominais
        final_beams = []

        # Agrupar por nome exato
        grouped_by_name: Dict[str, List[Dict]] = {}
        for b in raw_beams:
            name = b['name']
            if name not in grouped_by_name:
                grouped_by_name[name] = []
            grouped_by_name[name].append(b)

        for name, beam_list in grouped_by_name.items():
            if len(beam_list) > 1:
                # Mais de um com o mesmo nome -> adiciona sufixo minusculo (a, b, c...)
                for idx, b in enumerate(beam_list):
                    suffix = chr(97 + idx)  # 97 = 'a'
                    b['name'] = f"{name}{suffix}"
                    b['parent_name'] = name
                    final_beams.append(b)
            else:
                # Unico -> mantem nome original
                b = beam_list[0]
                # Extrair base name (ex: V1a -> V1)
                match = re.search(r'^(V\d+)([a-z])?$', b['name'])
                if match:
                    b['parent_name'] = match.group(1)
                else:
                    # V1A (maiusculo) - viga distinta
                    b['parent_name'] = b['name']
                final_beams.append(b)

        # Atribuir IDs finais
        for i, b in enumerate(final_beams):
            b['id'] = f"beam_{b['name']}_{i}"

        return final_beams

    def _find_beam_geometry(
        self,
        pos: Tuple[float, float],
        all_lines: List[Dict]
    ) -> Dict:
        """
        Encontra e CLASSIFICA geometrias (linhas e textos) vinculados a uma viga.
        Busca tambem dimensoes, candidatos a lajes e apoios.

        Args:
            pos: Coordenada (x, y) do texto da viga.
            all_lines: Todas as linhas do DXF para referencia.

        Returns:
            Dict com 'lines', 'texts', 'dimension_texts', 'support_candidates',
            'slab_candidates' e 'classified'.
        """
        # Area de busca ampliada para capturar textos de dimensao e apoios proximos
        search_area = (pos[0] - 400, pos[1] - 400, pos[0] + 400, pos[1] + 400)
        candidates = self.spatial_index.query_bbox(search_area)

        beam_geometry: Dict = {
            'lines': [],
            'texts': [],
            'dimension_texts': [],
            'support_candidates': [],
            'slab_candidates': [],
            'classified': {'seg_side_a': [], 'seg_side_b': [], 'seg_bottom': []}
        }

        raw_lines = []

        # 1. Coleta e Triagem Inicial
        for cand in candidates:
            if isinstance(cand, dict):
                # Linhas e Polilinhas
                if 'points' in cand:
                    # Filtra apenas o que esta mais perto (raio 250)
                    dist = self._point_dist(pos, cand['points'][0])
                    if dist < 250:
                        beam_geometry['lines'].append(cand['points'])
                        raw_lines.append(cand['points'])

                    # Candidatos a Apoio (Pilares sao polilinhas fechadas pequenas)
                    if 'layer' in cand and (
                        'PILAR' in cand['layer'].upper() or
                        'COL' in cand['layer'].upper()
                    ):
                        beam_geometry['support_candidates'].append(cand)

                # Textos
                elif 'text' in cand:
                    content = cand['text'].strip()
                    # Textos de Dimensao (ex: 20x60, 15/40)
                    if re.search(r'\d+[x\/\*]\d+', content):
                        beam_geometry['dimension_texts'].append(cand)
                    # Lajes (L1, L2...)
                    elif re.match(r'^[L|l]\d+', content):
                        beam_geometry['slab_candidates'].append(cand)
                    else:
                        beam_geometry['texts'].append(cand)

            elif isinstance(cand, list):
                beam_geometry['lines'].append(cand)
                raw_lines.append(cand)

        # 2. Classificacao Geometrica dos Segmentos
        if len(raw_lines) >= 2:
            classification = self._classify_lines(pos, raw_lines)
            beam_geometry['classified'] = classification

        return beam_geometry

    def _point_dist(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float]
    ) -> float:
        """Calcula distancia euclidiana entre dois pontos 2D."""
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def _classify_lines(
        self,
        center: Tuple[float, float],
        lines: List[List[Tuple[float, float]]]
    ) -> Dict:
        """
        Classifica linhas em Lado A, Lado B e Fundo baseado na posicao
        relativa ao centro da viga.

        Determina primeiro se a viga e predominantemente horizontal ou vertical,
        depois distribui as linhas entre seg_side_a, seg_side_b e seg_bottom.

        Args:
            center: Coordenada central (x, y) da viga.
            lines: Lista de polilinhas (listas de coordenadas).

        Returns:
            Dict com 'seg_side_a', 'seg_side_b', 'seg_bottom'.
        """
        classified: Dict[str, list] = {
            'seg_side_a': [],
            'seg_side_b': [],
            'seg_bottom': []
        }

        horizontal_weight = 0.0
        vertical_weight = 0.0

        valid_lines = []
        for line in lines:
            if len(line) < 2:
                continue
            p1, p2 = line[0], line[-1]
            dx = abs(p2[0] - p1[0])
            dy = abs(p2[1] - p1[1])
            length = (dx ** 2 + dy ** 2) ** 0.5

            if length < 10:
                continue  # Ignora linhas muito curtas (ruido)

            if dx > dy:
                horizontal_weight += length
            else:
                vertical_weight += length

            valid_lines.append({
                'line': line,
                'dx': dx,
                'dy': dy,
                'len': length,
                'center': ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            })

        is_horizontal = horizontal_weight > vertical_weight

        for item in valid_lines:
            line = item['line']
            lc = item['center']

            is_perpendicular = (
                (is_horizontal and item['dy'] > item['dx']) or
                (not is_horizontal and item['dx'] > item['dy'])
            )

            if is_perpendicular:
                classified['seg_bottom'].append(line)
                continue

            if is_horizontal:
                if lc[1] > center[1]:  # Acima
                    classified['seg_side_a'].append(line)
                else:  # Abaixo
                    classified['seg_side_b'].append(line)
            else:
                if lc[0] < center[0]:  # Esquerda
                    classified['seg_side_a'].append(line)
                else:  # Direita
                    classified['seg_side_b'].append(line)

        return classified
