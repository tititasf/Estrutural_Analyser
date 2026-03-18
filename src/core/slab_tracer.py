"""
SlabTracer - Motor de deteccao e tracado de contorno de lajes em DXF.

Detecta lajes por padrao de nomenclatura (L1, LAJE 03, L-2) e traca
seus contornos usando polygonize sobre as linhas estruturais do DXF.
Detecta tambem extensoes de borda (acrescimos) em arestas externas.
"""

import math
import re
import logging
from typing import List, Tuple, Optional, Dict

from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union

logger = logging.getLogger(__name__)


class SlabTracer:
    """
    Algoritmo 'Boundary Tracer' para Lajes.
    Usa 'Path Finding' (Polygonize) para encontrar poligonos fechados
    formados por vigas/paredes.
    """

    def __init__(self, spatial_index):
        """
        Args:
            spatial_index: Instancia de SpatialIndex com geometrias do DXF indexadas.
        """
        self.spatial_index = spatial_index
        self.global_boundary = None

    def _init_global_boundary(self):
        """
        Calcula o 'Envelope' global do desenho para validar o que e 'Exterior'.

        Prioridade:
        1. Layers explicitos ('MARCO', 'CONTORNO', 'LIMITE').
        2. Se nao achar, Convex Hull de toda a estrutura (Vigas/Paredes).
        """
        marco_geoms = []
        structure_geoms = []

        # Iterar todos os itens do indice
        all_items = (
            list(self.spatial_index.items.values())
            if hasattr(self.spatial_index, 'items')
            else []
        )

        invalid_layers = [
            'COTA', 'DIM', 'TEXT', 'EIXO', 'HATCH', 'MP_', 'OBS', 'TITULO'
        ]

        for item in all_items:
            geom = None
            layer = ""

            if isinstance(item, dict):
                layer = item.get('layer', '').upper()
                if 'points' in item:
                    geom = LineString(item['points'])
                elif 'start' in item:
                    geom = LineString([item['start'], item['end']])
            elif isinstance(item, list) and len(item) > 1:
                geom = LineString(item)

            if not geom:
                continue

            # Checar se e Marco
            if any(k in layer for k in ['MARCO', 'CONTORNO', 'LIMITE', 'FRAME']):
                marco_geoms.append(geom)

            # Checar se e Estrutura (para fallback)
            is_invalid = any(k in layer for k in invalid_layers)
            if not is_invalid:
                structure_geoms.append(geom)

        if marco_geoms:
            # Marco explicito encontrado
            print(
                f"[INFO] Detectado Marco Global com "
                f"{len(marco_geoms)} segmentos."
            )
            try:
                self.global_boundary = unary_union(marco_geoms)
            except Exception:
                self.global_boundary = unary_union(marco_geoms).convex_hull

        elif structure_geoms:
            # Fallback: Convex Hull de tudo
            print(
                f"[INFO] Marco nao detectado. Usando Convex Hull da "
                f"estrutura ({len(structure_geoms)} segmentos)."
            )
            try:
                # Extrair todos os pontos e fazer convex hull (rapido)
                all_points = []
                for g in structure_geoms:
                    all_points.extend(g.coords)

                if all_points:
                    from shapely.geometry import MultiPoint
                    self.global_boundary = MultiPoint(all_points).convex_hull
            except Exception as e:
                print(f"[ERROR] Falha ao calcular Convex Hull: {e}")
                self.global_boundary = None

        if self.global_boundary:
            # Converter para apenas Exterior Ring se for Poligono
            if isinstance(self.global_boundary, Polygon):
                self.global_boundary = self.global_boundary.exterior
            elif isinstance(self.global_boundary, MultiLineString):
                pass  # Manter como esta

    def trace_boundary(
        self,
        start_point: Tuple[float, float],
        search_radius: float = 1000.0,
        valid_layers: List[str] = None
    ) -> Optional[Polygon]:
        """
        Encontra o poligono fechado que contem o start_point.

        Coleta linhas candidatas no raio de busca, aplica polygonize
        (com noding via unary_union) e retorna o poligono que contem
        o ponto alvo.

        Args:
            start_point: Coordenada (x, y) central do texto da laje.
            search_radius: Raio de busca em unidades DXF (default 1000.0).
            valid_layers: Lista de layers permitidos (filtragem opcional).

        Returns:
            Polygon shapely se encontrado, ou None.
        """
        cx, cy = start_point
        bounds = (
            cx - search_radius,
            cy - search_radius,
            cx + search_radius,
            cy + search_radius
        )

        candidates = self.spatial_index.query_bbox(bounds)
        lines = []

        for item in candidates:
            geom = None
            layer = None

            if isinstance(item, dict):
                layer = item.get('layer')
                if 'points' in item:  # Polyline
                    pts = item['points']
                    if len(pts) > 1:
                        geom = LineString(pts)
                elif 'start' in item:  # Line
                    geom = LineString([item['start'], item['end']])

            elif isinstance(item, tuple) and len(item) == 2:
                geom = LineString(item)
            elif isinstance(item, list) and len(item) > 1:
                geom = LineString(item)

            if geom:
                # Filtragem por Layer
                if valid_layers:
                    if layer and layer not in valid_layers:
                        continue
                lines.append(geom)

        if not lines:
            return None

        try:
            # Noding: unary_union corrige intersecoes nao-nodadas
            noded_lines = unary_union(lines)

            # Polygonize retorna gerador de poligonos
            polygons = list(polygonize(noded_lines))

            target_pt = Point(cx, cy)

            # Encontrar qual poligono contem o ponto
            for poly in polygons:
                if poly.contains(target_pt):
                    return poly

        except Exception as e:
            print(f"[DEBUG] Trace Error: {e}")
            return None

        return None

    def detect_extensions(
        self,
        main_poly: Polygon,
        search_radius: float = 50.0
    ) -> List[Dict]:
        """
        Detecta e GERA 'acrescimos' (strips de 10 unidades) em bordas externas.

        Estrategia: Generative Edge Extrusion (V4).
        1. Para cada aresta da laje, testa se aponta para o 'vazio' (Ray Cast).
        2. Se for vazio, extruda aresta em 10 unidades e cria poligono.

        Args:
            main_poly: Poligono principal da laje.
            search_radius: Raio de busca para deteccao de bloqueios.

        Returns:
            Lista de dicts com 'type', 'points', 'role', 'width_est', 'side'.
        """
        if not main_poly or not self.spatial_index:
            return []

        generated_extensions = []

        coords = list(main_poly.exterior.coords)
        if len(coords) < 2:
            return []

        # Remove ponto duplicado final (LinearRing)
        if coords[0] == coords[-1]:
            coords = coords[:-1]

        num_pts = len(coords)
        if num_pts < 3:
            return []

        # Parametros
        BLOCK_DIST_THRESHOLD = 1000.0  # 10m em unidades DXF
        EXTENSION_WIDTH = 10.0

        # 1. Fase de Classificacao
        edge_status = []  # True=Livre, False=Bloqueado

        for i in range(num_pts):
            p1 = coords[i]
            p2 = coords[(i + 1) % num_pts]

            edge = LineString([p1, p2])
            if edge.length < 1.0:
                edge_status.append(False)
                continue

            # Ray Cast: determinar normal da aresta
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = (dx * dx + dy * dy) ** 0.5
            nx, ny = -dy / length, dx / length

            # Garantir que Normal aponta para fora
            mid = edge.interpolate(0.5, normalized=True)
            check_pt = (mid.x + nx * 0.1, mid.y + ny * 0.1)
            if main_poly.contains(Point(check_pt)):
                nx, ny = -nx, -ny

            # Fan Scan (3 direcoes)
            angles = [0, -10, 10]
            is_blocked = False

            for ang in angles:
                rad = math.radians(ang)
                rnx = nx * math.cos(rad) - ny * math.sin(rad)
                rny = nx * math.sin(rad) + ny * math.cos(rad)

                r_start = (mid.x + rnx * 1.0, mid.y + rny * 1.0)
                r_end = (
                    r_start[0] + rnx * 5000.0,
                    r_start[1] + rny * 5000.0
                )
                ray_geom = LineString([r_start, r_end])

                hits = self.spatial_index.query_bbox(ray_geom.bounds)

                for h in hits:
                    h_geom = None
                    if isinstance(h, dict):
                        if 'points' in h:
                            h_geom = LineString(h['points'])
                        elif 'start' in h:
                            h_geom = LineString([h['start'], h['end']])
                    elif isinstance(h, list) and len(h) > 1:
                        h_geom = LineString(h)

                    if not h_geom:
                        continue
                    if not ray_geom.intersects(h_geom):
                        continue

                    if Point(r_start).distance(h_geom) < BLOCK_DIST_THRESHOLD:
                        is_blocked = True
                        break

                if is_blocked:
                    break

            edge_status.append(not is_blocked)

        # 2. Fase de Encadeamento
        chains = []
        if not edge_status:
            return []

        if all(edge_status):
            # Caso especial: todas as arestas livres (ilha)
            chains.append(list(range(num_pts)) + [0])
        else:
            # Encontrar inicio em aresta bloqueada
            start_idx = 0
            if edge_status[0]:
                for k in range(num_pts):
                    if not edge_status[k]:
                        start_idx = (k + 1) % num_pts
                        break

            current_chain = []
            for k in range(num_pts):
                idx = (start_idx + k) % num_pts
                if edge_status[idx]:
                    if not current_chain:
                        current_chain.append(idx)
                    current_chain.append((idx + 1) % num_pts)
                else:
                    if current_chain:
                        chains.append(current_chain)
                        current_chain = []

            if current_chain:
                chains.append(current_chain)

        # 3. Fase de Geracao (Offset)
        for chain_indices in chains:
            pts = [coords[i] for i in chain_indices]
            if len(pts) < 2:
                continue

            line = LineString(pts)

            try:
                # Offset negativo = lado direito (exterior para CCW)
                offset_dist = -EXTENSION_WIDTH
                offset_line = line.offset_curve(offset_dist, join_style=2)

                # Validar se offset esta realmente fora
                test_pt = offset_line.interpolate(0.5, normalized=True)
                if (main_poly.contains(test_pt) or
                        main_poly.distance(test_pt) < 1.0):
                    offset_dist = EXTENSION_WIDTH
                    offset_line = line.offset_curve(offset_dist, join_style=2)

                # Se MultiLineString, pular (geometria complexa)
                if hasattr(offset_line, 'geoms'):
                    continue

                off_coords = list(offset_line.coords)

                # Construir anel: Pts + Offset invertido + fechar
                final_loop = pts + off_coords[::-1] + [pts[0]]
                ext_poly = Polygon(final_loop)

                # Corrigir auto-intersecoes
                if not ext_poly.is_valid:
                    ext_poly = ext_poly.buffer(0)

                generated_extensions.append({
                    'type': 'poly',
                    'points': list(ext_poly.exterior.coords),
                    'role': 'Acrescimo_borda',
                    'width_est': EXTENSION_WIDTH,
                    'side': 'Composite'
                })

            except Exception as e:
                print(f"[ERROR] Failed to generate offset for chain: {e}")
                continue

        return generated_extensions

    def detect_slabs_from_texts(
        self,
        texts: List[Dict],
        search_radius: float = 2000.0,
        valid_layers: List[str] = None
    ) -> List[Dict]:
        """
        Varre textos buscando padroes de laje (Lx, Laje X) e tenta tracar limites.

        Para cada texto que casa com o padrao, tenta tracar o contorno via
        trace_boundary e detectar extensoes de borda.

        Args:
            texts: Lista de dicts com 'text' e 'pos' extraidos do DXF.
            search_radius: Raio de busca para polygonize (default 2000.0).
            valid_layers: Lista de layers permitidos (filtragem opcional).

        Returns:
            Lista de dicts com: name, pos, points, area, extensions,
            is_detected, type, neighbors.
        """
        slabs = []

        slab_pattern = re.compile(
            r'^(L|LAJE)\s*[-_]?\s*\d+[a-zA-Z]*$',
            re.IGNORECASE
        )

        # Debug
        sample_texts = [t.get('text') for t in texts[:5]]
        print(
            f"[DEBUG] SlabTracer checking {len(texts)} texts. "
            f"Patterns found?"
        )

        for t in texts:
            txt = t.get('text', '').strip()
            if not slab_pattern.match(txt):
                continue

            pos = t.get('pos')
            if not pos:
                continue

            # Tentar tracar contorno
            poly = self.trace_boundary(
                pos,
                search_radius,
                valid_layers=valid_layers
            )

            found_poly = bool(poly)
            points = []
            area = 0.0
            extensions = []

            if poly:
                points = list(poly.exterior.coords)
                area = poly.area

                # Detectar Acrescimos
                try:
                    extensions = self.detect_extensions(poly)
                except Exception as e:
                    print(f"Erro detectando extensoes Laje {txt}: {e}")

            else:
                # Fallback: Quadrado de 50x50 em volta do texto
                cx, cy = pos
                points = [
                    (cx - 25, cy - 25), (cx + 25, cy - 25),
                    (cx + 25, cy + 25), (cx - 25, cy + 25),
                    (cx - 25, cy - 25)
                ]

            slabs.append({
                'id': f"temp_{len(slabs)}",
                'name': txt.upper(),
                'pos': pos,
                'points': points,
                'area': area,
                'neighbors': [],
                'is_detected': found_poly,
                'is_validated': False,
                'type': 'Laje',
                'extensions': extensions
            })

        return slabs
