# -*- coding: utf-8 -*-
"""
Motor de Busca Contextual (Refatorado).
Responsável por encontrar entidades (Textos, Linhas) próximos a um item (Pilar/Viga/Laje)
usando Geometria, Regex e Memória Vetorial.
"""

import re
import math
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class ContextEngine:
    """
    Motor de Busca Contextual (Refatorado).
    Responsável por encontrar entidades (Textos, Linhas) próximos a um item (Pilar/Viga/Laje)
    usando Geometria, Regex e Memória Vetorial.
    """

    def __init__(self, dxf_data: Dict, spatial_index: Any, memory: Any) -> None:
        self.dxf_data = dxf_data
        self.spatial_index = spatial_index
        self.memory = memory

    def perform_search(
        self,
        item_context: Dict,
        search_config: Dict,
        side: str,
    ) -> Dict:
        """
        Executa a busca por um slot específico (ex: 'dim', 'level') ao redor do item.
        integrando Inteligência Geométrica e Memória (Active Learning).
        """
        # --- Extract search parameters from config ---
        field_id = search_config.get('field_id', 'unknown')
        slot_id = search_config.get('slot_id', field_id)
        prompt = search_config.get('prompt', '')
        base_radius = search_config.get('radius', 800.0)
        points = item_context.get('points', [])
        center_p = item_context.get('pos', (0, 0))

        # Calculate search center from points
        if points:
            search_center = (
                sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points),
            )
        else:
            search_center = center_p

        pilar_type = item_context.get('type', 'UNKNOWN')

        # --- DNA and Memory Integration ---
        current_dna = None
        training_ctx = None
        role = field_id.split('_')[0] if '_' in field_id else field_id

        try:
            current_dna = self._generate_dna(item_context)
            training_ctx = self.memory.retrieve_relevant_context(
                role=role,
                item_type=pilar_type,
                dna_vector=current_dna,
            )
        except Exception:
            training_ctx = None

        # --- Memory-based prediction ---
        confidence = 0.5
        used_memory = False
        debug_info = ''

        if training_ctx and training_ctx.get('samples', 0) > 0:
            # Check for N/A prediction from context
            if training_ctx.get('predicted_status') == 'na':
                return {
                    'found_ent': None,
                    'links': None,
                    'confidence': 1.0,
                    'used_training': True,
                    'debug': f"IA: Predição N/A por Contexto (n={training_ctx.get('samples', 0)})",
                    'status': 'na',
                }

            # Apply learned pattern offsets
            offset_x = training_ctx.get('avg_rel_pos', (0, 0))[0] if training_ctx.get('avg_rel_pos') else 0
            offset_y = training_ctx.get('avg_rel_pos', (0, 0))[1] if training_ctx.get('avg_rel_pos') else 0
            sim = training_ctx.get('similarity', 0.5)
            search_center = (search_center[0] + offset_x, search_center[1] + offset_y)
            search_radius = base_radius * (1 + sim)
            confidence = sim
            used_memory = True
            debug_info = (
                f"IA: Padrão aprendido (Conf: {sim * 100:.0f}%, "
                f"n={training_ctx.get('samples', 0)})"
            )
            blocklist = search_config.get('blocklist', [])
        else:
            search_radius = base_radius
            blocklist = search_config.get('blocklist', [])

        found_ent = None
        new_links = None

        # --- Void-X line search (for 'void_x' slots) ---
        if slot_id == 'void_x':
            v_lines = self._find_vazio_x_lines(points, search_radius, side=side)
            if v_lines:
                for vl in v_lines:
                    found_ent = {
                        'type': 'line',
                        'points': [vl.get('start'), vl.get('end')],
                        'text': 'Vazio (X)',
                        'role': slot_id,
                    }
                    break
                # Check for "SEM LAJE" text nearby
                is_na_pattern = False
                return {
                    'found_ent': found_ent,
                    'links': new_links,
                    'confidence': min(confidence, 0.2),
                    'used_training': used_memory,
                    'debug': debug_info,
                    'status': 'valid',
                }

        # --- Determine search type from prompt / field_id ---
        # Extract prefix or pattern from prompt
        side_code = side
        prefix_match = None
        regex_match = None

        # Check if prompt specifies a letter prefix like 'P', 'L', 'V'
        pattern = re.search(r'''[\"\']([ PLV])[\"\']''', prompt, re.I)
        if pattern:
            prefix_match = pattern.group(1)

        # Check if prompt specifies a regex pattern
        regex_match = re.search(r'regex\s*[:=]\s*(.+)', prompt)

        # --- Execute search based on field type ---
        try:
            if regex_match:
                # Regex-based search (e.g., dimensions like '30x60')
                found_ent = self._find_nearest_text_pattern(
                    points, regex_match.group(1).strip(), search_radius,
                    side, ref_origin=search_center, blocklist=blocklist,
                )
            elif prefix_match:
                # Prefix-based search (e.g., 'P' for pilar names, 'V' for vigas)
                found_ent = self._find_nearest_text_prefix(
                    points, prefix_match, search_radius,
                    side, ref_origin=search_center, blocklist=blocklist,
                )
            else:
                # Determine prefix from field_id
                prefix = None
                if 'name' in field_id:
                    if '_v_' in field_id:
                        prefix = 'V'
                    elif '_l1_n' in field_id:
                        prefix = 'L'
                    else:
                        prefix = 'P'
                elif 'viga' in field_id:
                    prefix = 'V'
                elif '_l1_' in field_id:
                    prefix = 'L'

                if prefix:
                    found_ent = self._find_nearest_text_prefix(
                        points, prefix, search_radius,
                        side, ref_origin=search_center, blocklist=blocklist,
                    )
                else:
                    # Fallback: try without offset
                    found_ent = self._find_nearest_text_prefix(
                        points, 'P', search_radius * 1.5,
                        side, ref_origin=search_center, blocklist=blocklist,
                    )
                    if found_ent:
                        debug_info += ' (Recuperado via Fallback sem offset)'

        except Exception as e:
            found_ent = None

        # --- Check N/A patterns ---
        patterns_na = search_config.get('patterns_na', [])
        if found_ent and patterns_na:
            try:
                is_na_pattern = any(
                    re.search(p, str(found_ent.get('text', '')), re.I)
                    for p in patterns_na
                )
                if is_na_pattern:
                    debug_info += ' (N/A via Pattern Match)'
                    return {
                        'found_ent': found_ent,
                        'links': new_links,
                        'confidence': 1.0,
                        'used_training': used_memory,
                        'debug': debug_info,
                        'status': 'na',
                    }
            except Exception as e:
                debug_info += f' (Erro regex NA: {e})'

        # --- Build result ---
        if found_ent:
            new_links = {
                'text': found_ent.get('text', ''),
                'type': found_ent.get('type', ''),
                'pos': found_ent.get('pos', (0.0, 0.0)),
                'role': slot_id,
            }
            confidence = min(confidence, 1.0)
        else:
            confidence = 0.0

        debug_info += f" C:{confidence:.2f} | R:{search_radius:.2f}"

        return {
            'found_ent': found_ent,
            'links': new_links,
            'confidence': confidence,
            'used_training': used_memory,
            'debug': debug_info,
            'status': 'valid' if found_ent else 'na',
        }

    def find_nearest_text(
        self, points: List, prefix: str, radius: Optional[float] = None
    ) -> Optional[Dict]:
        """Versão pública para busca rápida de textos próximos (ex: 'P', 'V')."""
        return self._find_nearest_text_prefix(points, prefix, radius or 800.0)

    def _find_nearest_text_prefix(
        self,
        points: List,
        prefix: str,
        radius: float = 800.0,
        side: Optional[str] = None,
        ref_origin: Optional[Tuple] = None,
        blocklist: Optional[List] = None,
    ) -> Optional[Dict]:
        """
        Busca o texto mais próximo que começa com ``prefix`` dentro de ``radius``
        dos ``points`` fornecidos, respeitando o filtro de lado (side).
        """
        if not points:
            return None

        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)

        texts = self.dxf_data.get('texts', [])
        best_dist = radius
        best_ent = None

        for txt in texts:
            pos = txt.get('pos')
            content = txt.get('text', '')
            if not pos or not content:
                continue

            tx, ty = pos[0], pos[1]

            # Apply side filter if specified
            if side and not self._check_side_filter((tx, ty), (cx, cy), side):
                continue

            # Check prefix match
            content_upper = str(content).upper().strip()
            if not content_upper.startswith(prefix.upper()):
                continue

            # Skip if only the prefix letter with no digits following
            if len(content_upper) <= len(prefix):
                continue
            if not content_upper[len(prefix):].strip()[0:1].isdigit():
                continue

            # Check blocklist
            if blocklist and txt in blocklist:
                continue

            dist = math.hypot(tx - cx, ty - cy)
            if dist < best_dist:
                best_dist = dist
                best_ent = txt

        return best_ent

    def _find_nearest_text_pattern(
        self,
        points: List,
        pattern: str,
        radius: float = 800.0,
        side: Optional[str] = None,
        ref_origin: Optional[Tuple] = None,
        blocklist: Optional[List] = None,
    ) -> Optional[Dict]:
        """
        Busca o texto mais próximo que casa com ``pattern`` (regex) dentro de ``radius``
        dos ``points`` fornecidos, respeitando o filtro de lado (side).
        """
        if not points:
            return None

        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)

        texts = self.dxf_data.get('texts', [])
        best_dist = radius
        best_ent = None

        for txt in texts:
            pos = txt.get('pos')
            content = txt.get('text', '')
            if not pos or not content:
                continue

            tx, ty = pos[0], pos[1]

            # Apply side filter
            if side and not self._check_side_filter((tx, ty), (cx, cy), side):
                continue

            # Check regex match
            content_clean = str(content).upper().strip()
            if not re.search(pattern, content_clean):
                continue

            # Check blocklist
            if blocklist and txt in blocklist:
                continue

            dist = math.hypot(tx - cx, ty - cy)
            if dist < best_dist:
                best_dist = dist
                best_ent = txt

        return best_ent

    def _find_vazio_x_lines(
        self,
        points: List,
        radius: float,
        side: Optional[str] = None,
    ) -> List[Dict]:
        """
        Encontra linhas 'vazias' (sem texto associado) na direção ``side``,
        usadas para detectar ausência de laje (Vazio X).
        """
        if not points:
            return []

        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)

        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        nearby = self.spatial_index.query_bbox(bbox)

        found = []
        for item in nearby:
            start = item.get('start')
            end = item.get('end')
            if not start or not end:
                continue

            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2

            if side and not self._check_side_filter((mid_x, mid_y), (cx, cy), side):
                continue

            found.append(item)

        return found

    def _check_side_filter(
        self,
        target_pos: Tuple[float, float],
        center_pos: Tuple[float, float],
        side: str,
    ) -> bool:
        """
        Gabarito Ouro: Retorna True se target_pos estiver no setor 'side' com
        tolerância a vazamentos diagonais, assumindo sistema padrão A(Norte), B(Leste), C(Sul), D(Oeste).
        """
        tx, ty = target_pos
        cx, cy = center_pos
        dx = tx - cx
        dy = ty - cy

        # Tolerance for diagonal leakage
        tol = 1e-05

        if side == 'A':
            # Norte: target must be above center (dy > 0) and predominantly vertical
            return dy > 0 and abs(dx) <= abs(dy) + tol
        elif side == 'C':
            # Sul: target must be below center (dy < 0)
            return dy < 0 and abs(dx) <= abs(dy) + tol
        elif side == 'B':
            # Leste: target must be to the right (dx > 0)
            return dx > 0 and abs(dy) <= abs(dx) + tol
        elif side == 'D':
            # Oeste: target must be to the left (dx < 0)
            return dx < 0 and abs(dy) <= abs(dx) + tol
        elif side == 'Superior':
            return dy > 0
        elif side == 'Inferior':
            return dy < 0
        else:
            return True

    def find_neighbors(
        self,
        item_context: Dict,
        radius: float = 1000.0,
    ) -> List[Dict]:
        """
        Encontra itens estruturais vizinhos (Pilar, Viga, Laje) usando o Spatial Index.
        """
        points = item_context.get('points', [])
        if not points:
            return []

        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)

        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        candidates = self.spatial_index.query_bbox(bbox)

        item_id = item_context.get('id')
        neighbors = []

        for item in candidates:
            # Skip self
            if item.get('id') == item_id:
                continue

            item_type = item.get('type', '')
            if item_type not in ('pillar', 'beam', 'slab', 'polyline'):
                continue

            # Calculate distance
            pts = item.get('points', [])
            if not pts:
                # Try start/end for lines/beams
                start = item.get('start')
                end = item.get('end')
                if start and end:
                    pts = [start, end]
                else:
                    continue

            tx = sum(p[0] for p in pts) / len(pts)
            ty = sum(p[1] for p in pts) / len(pts)
            dist = math.hypot(tx - cx, ty - cy)

            if dist > 0:
                neighbors.append({
                    'type': item_type,
                    'name': item.get('name', 'UNKNOWN'),
                    'distance': dist,
                    'pos': (tx, ty),
                })

        # Sort by distance and return closest 5
        neighbors.sort(key=lambda x: x['distance'])
        return neighbors[:5]

    def _generate_dna(self, item_context: Dict) -> List[float]:
        """Gera vetor DNA para o item (Area, Vizinhos, Complexidade, Perimetro)."""
        area = item_context.get('area_val', 1.0)
        points = item_context.get('points', [])

        # Calculate perimeter from points
        perim = 0.0
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            perim += math.hypot(p2[0] - p1[0], p2[1] - p1[1])

        # Complexity: ratio of area to perimeter squared (compactness)
        complexity = (area / (perim ** 2 + 1e-05)) ** 0.5 if perim > 0 else 0.5

        # Neighbors
        neighbors = self.find_neighbors(item_context)
        num_neighbors = float(len(neighbors))
        avg_dist = (
            sum(n['distance'] for n in neighbors) / len(neighbors)
            if neighbors
            else 1000.0
        )

        return [area, num_neighbors, complexity, perim]

    def extract_float(self, text: str) -> Optional[float]:
        """Extrai o primeiro número de ponto flutuante encontrado no texto."""
        clean_text = text.replace(' ', '').replace(',', '.')
        match = re.search(r'[+-]?\d+\.?\d*', clean_text)
        if match:
            return float(match.group())
        return None
