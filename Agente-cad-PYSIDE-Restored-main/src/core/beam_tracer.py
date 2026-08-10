import logging
import re
from typing import List, Dict, Tuple
from shapely.geometry import Point, LineString, Polygon
from .spatial_index import SpatialIndex
from .beam_interpreters import FundoVigaInterpreter

class BeamTracer:
    """
    Motor especializado em identificar vigas baseadas em nomes (V1, V2...)
    e traçar seu caminho geométrico entre apoios.
    """
    def __init__(self, spatial_index: SpatialIndex, learning_params_bottom: dict = None):
        self.spatial_index = spatial_index
        # [BOTTOM]
        self.learning_params_bottom = learning_params_bottom or {}
        self.fundo_interpreter = FundoVigaInterpreter()

    @staticmethod
    def _entity_points(entity) -> List[Tuple[float, float]]:
        """Normaliza POLYLINE (`points`) e LINE DXF nativa (`start/end`).

        O índice espacial guarda a entidade original do loader. Linhas DXF não
        possuem `points`; ignorá-las truncava a topologia antes dos
        interpretadores FV/LV/PIL.
        """
        if not isinstance(entity, dict):
            return []
        raw_points = entity.get('points')
        if not raw_points and entity.get('start') is not None and entity.get('end') is not None:
            raw_points = [entity.get('start'), entity.get('end')]
        points = []
        for point in raw_points or []:
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError, IndexError):
                continue
        return points

    @staticmethod
    def _label_owns_points(
        pts,
        pos: Tuple[float, float],
        is_h: bool,
        orientations: Dict[int, bool],
        beam_labels: List[Dict],
        my_name: str,
    ) -> bool:
        """Resolve a propriedade geométrica entre rótulos paralelos.

        Usa a distância bidimensional ao rótulo, com transversal e longitudinal
        como desempates. A versão anterior comparava só o eixo longitudinal e
        deixava uma viga absorver o fundo da paralela vizinha; priorizar apenas
        o transversal, por outro lado, fundiria vigas colineares consecutivas.
        """
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)

        def _score(label_pos) -> tuple[float, float, float]:
            if is_h:
                transverse = abs(cy - label_pos[1])
                longitudinal = abs(cx - label_pos[0])
            else:
                transverse = abs(cx - label_pos[0])
                longitudinal = abs(cy - label_pos[1])
            return (
                (transverse ** 2 + longitudinal ** 2) ** 0.5,
                transverse,
                longitudinal,
            )

        my_score = _score(pos)
        my_key = (my_score, str(my_name).upper())
        # Um rótulo de outra viga só pode disputar uma geometria quando está
        # no mesmo corredor transversal. Sem este filtro, um nome globalmente
        # mais perto, porém centenas de unidades acima/ao lado do eixo, rouba
        # continuações colineares legítimas. A margem mantém a competição entre
        # vigas paralelas próximas e, para rótulos colineares, deixa o eixo
        # longitudinal decidir qual trecho consecutivo pertence a cada uma.
        transverse_competition_margin = 60.0
        for other in beam_labels:
            other_name = str(other.get('text') or '').strip()
            if other_name == my_name:
                continue
            if orientations.get(id(other), True) != is_h:
                continue
            op = other.get('pos')
            if not op:
                continue
            if abs(op[0] - pos[0]) < 5 and abs(op[1] - pos[1]) < 5:
                continue
            other_score = _score(op)
            if other_score[1] > my_score[1] + transverse_competition_margin:
                continue
            other_key = (other_score, other_name.upper())
            if other_key < my_key:
                return False
        return True

    def detect_beams(self, texts: List[Dict], lines: List[Dict], visual_obstacles: List[Dict] = None) -> List[Dict]:
        beam_labels = []
        for t in texts:
            content = t['text'].strip()
            # Padrões comuns de vigas (V101, VF20, CONT1)
            if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
                beam_labels.append(t)
                
        # PASS 1: Determinar orientações com a Magical Formula
        orientations = {}
        legacy_orientations_by_name = {}
        for b_text in beam_labels:
            content = b_text['text'].strip()
            pos = b_text['pos']
            legacy_orientations_by_name[content] = self._determine_orientation(pos)
            is_h = self._determine_orientation(
                pos, label_rotation=b_text.get('rotation')
            )
            # A orientação pertence à ocorrência. Uma viga contínua pode
            # possuir trechos horizontais e verticais com o mesmo nome.
            orientations[id(b_text)] = is_h
        legacy_orientations = {
            id(label): legacy_orientations_by_name[label['text'].strip()]
            for label in beam_labels
        }
            
        # PASS 2: Capturar geometria usando _owns com conn_tol=400 e trans_tol=30
        pre_beams = []
        for b_text in beam_labels:
            content = b_text['text'].strip()
            pos = b_text['pos']
            is_h = orientations[id(b_text)]
            # FV possui uma evidência adicional que não pertence à leitura de
            # laterais: divisores transversais nativos que fecham exatamente as
            # duas bordas do fundo.  Eles abrem painéis reais (por exemplo,
            # mudanças de profundidade), mas não podem virar fallback de LV.
            raw_lines = self._capture_fundo_geometry(
                pos, is_h, orientations, beam_labels, content,
            )
            lv_is_h = legacy_orientations[id(b_text)]
            lv_raw_lines = (
                self._capture_geometry(
                    pos, lv_is_h, legacy_orientations, beam_labels, content,
                )
                if lv_is_h == is_h
                else self._capture_geometry(
                    pos,
                    lv_is_h,
                    legacy_orientations,
                    beam_labels,
                    content,
                )
            )
            pre_beams.append({
                'name': content,
                'pos': pos,
                'is_h': is_h,
                'raw_lines': raw_lines,
                'lv_is_h': lv_is_h,
                'lv_raw_lines': lv_raw_lines,
                'visual_obstacles': visual_obstacles,
            })
            
        # PASS 3: Build final_beams structure
        final_beams = []
        grouped_by_base = {}
        for pb in pre_beams:
            name = pb['name']
            pos = pb['pos']
            is_h = pb['is_h']
            
            clean_name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name).strip()
            # Sufixo alfabético colado ao número faz parte do identificador
            # estrutural (V309 e V309A são vigas distintas). Sufixos após
            # ponto/hífen seguem sendo convenções de face/seção (V301.C).
            m = re.match(r'^([A-Za-z]+\d+[A-Za-z]*)', clean_name)
            if m:
                base_name = m.group(1)
            else:
                base_name = clean_name
                
            visual_obstacles = pb.get('visual_obstacles')
            geometry = self._process_beam_geometry(
                pos,
                pb['raw_lines'],
                pb['is_h'],
                visual_obstacles,
                lv_raw_lines=pb['lv_raw_lines'],
                lv_is_h=pb['lv_is_h'],
            )
            
            if base_name not in grouped_by_base:
                grouped_by_base[base_name] = []
            grouped_by_base[base_name].append({
                'name': name,
                'pos': pos,
                'geometry': geometry,
                'is_h': is_h,
                'lv_is_h': pb['lv_is_h'],
            })
            
        for base_name, beam_list in grouped_by_base.items():
            master_beam = {
                'name': base_name,
                'pos': beam_list[0]['pos'],
                'texts': [],
                'dimension_texts': [],
                'geometry': {
                    'texts': [],
                    'dimension_texts': [],
                    'support_candidates': [],
                    'slab_candidates': [],
                    'classified': {
                        'seg_side_a': [],
                        'seg_side_b': [],
                        'seg_bottom': [],
                        'lv_seg_side_a': [],
                        'lv_seg_side_b': [],
                        'fv_physical_divider_positions': [],
                    }
                }
            }
            master_beam['geometry']['lv_dimension_text'] = next(
                (
                    b['geometry'].get('lv_dimension_text')
                    for b in beam_list
                    if b['geometry'].get('lv_dimension_text')
                ),
                None,
            )
            
            seen_centers = set()
            seen_sup = set()
            seen_slab = set()
            for b in beam_list:
                g = b.get('geometry') or {}
                master_beam['texts'].extend(g.get('texts') or [])
                master_beam['dimension_texts'].extend(g.get('dimension_texts') or [])
                # Espelha no geometry para _process_beam_intelligent / populate
                master_beam['geometry']['texts'].extend(g.get('texts') or [])
                master_beam['geometry']['dimension_texts'].extend(
                    g.get('dimension_texts') or []
                )
                for s in g.get('support_candidates') or []:
                    key = (
                        str(s.get('text') or s.get('name') or ''),
                        round(float((s.get('pos') or (0, 0))[0]), 1),
                        round(float((s.get('pos') or (0, 0))[1]), 1),
                    )
                    if key not in seen_sup:
                        seen_sup.add(key)
                        master_beam['geometry']['support_candidates'].append(s)
                for s in g.get('slab_candidates') or []:
                    key = (
                        str(s.get('text') or s.get('name') or ''),
                        round(float((s.get('pos') or (0, 0))[0]), 1),
                        round(float((s.get('pos') or (0, 0))[1]), 1),
                    )
                    if key not in seen_slab:
                        seen_slab.add(key)
                        master_beam['geometry']['slab_candidates'].append(s)
                
                for seg in b['geometry']['classified']['seg_bottom']:
                    if seg:
                        cx = round((seg[0][0] + seg[1][0])/2, 2)
                        cy = round((seg[0][1] + seg[1][1])/2, 2)
                        if (cx, cy) not in seen_centers:
                            seen_centers.add((cx, cy))
                            master_beam['geometry']['classified']['seg_bottom'].append(seg)
                for divider_position in b['geometry']['classified'].get(
                    'fv_physical_divider_positions', []
                ):
                    if divider_position not in master_beam['geometry']['classified'][
                        'fv_physical_divider_positions'
                    ]:
                        master_beam['geometry']['classified'][
                            'fv_physical_divider_positions'
                        ].append(divider_position)
                            
                # Collect side segments
                master_beam['geometry']['classified']['seg_side_a'].extend(b['geometry']['classified'].get('seg_side_a', []))
                master_beam['geometry']['classified']['seg_side_b'].extend(b['geometry']['classified'].get('seg_side_b', []))
                master_beam['geometry']['classified']['lv_seg_side_a'].extend(
                    b['geometry']['classified'].get('lv_seg_side_a', [])
                )
                master_beam['geometry']['classified']['lv_seg_side_b'].extend(
                    b['geometry']['classified'].get('lv_seg_side_b', [])
                )
                
            # O campo legado is_h permanece no contrato LV/PIL. FV usa a
            # orientação por ocorrência sem alterar os demais consumidores.
            master_beam['is_h'] = bool(beam_list[0]['lv_is_h'])
            master_beam['lv_is_h'] = bool(beam_list[0]['lv_is_h'])
            master_beam['fv_is_h'] = bool(beam_list[0]['is_h'])
            lv_dimension_text = master_beam['geometry'].get(
                'lv_dimension_text'
            )
            if (
                master_beam['fv_is_h'] != master_beam['lv_is_h']
                and isinstance(lv_dimension_text, dict)
                and lv_dimension_text.get('text')
            ):
                master_beam['lv_dimension_override'] = str(
                    lv_dimension_text['text']
                )
            
            # FV tem consolidacao propria. Enquanto o tipo de encontro ainda
            # nao estiver classificado, usa o modo conservador compativel.
            occurrence_coords = []
            bottom_runs = []
            for b in beam_list:
                classified = b['geometry']['classified']
                coords = self.fundo_interpreter.consolidate_occurrences([
                    classified.get('merged_bottom_groups_coords', [])
                ])
                if classified.get('bottom_mode') == 'panel':
                    coords = self.fundo_interpreter.discard_attached_narrow_caps(
                        coords,
                        protected_boundaries=classified.get(
                            'fv_physical_divider_positions', []
                        ),
                    )
                    coords = self.fundo_interpreter.merge_unlabeled_short_gaps(
                        coords,
                        is_horizontal=bool(b['is_h']),
                        transverse_center=(b['pos'][1] if b['is_h'] else b['pos'][0]),
                        texts=b['geometry'].get('texts', []),
                        current_name=b.get('name', base_name),
                    )
                occurrence_coords.append(coords)
                mode = classified.get('bottom_mode', 'fallback')
                if mode == 'divisor':
                    run_coords = [
                        (coords[index][1], coords[index + 1][0])
                        for index in range(len(coords) - 1)
                        if coords[index + 1][0] - coords[index][1] > 10.0
                    ]
                    lengths = self.fundo_interpreter.lengths(run_coords)
                else:
                    run_coords = coords
                    lengths = self.fundo_interpreter.lengths(run_coords)
                if lengths:
                    bottom_runs.append({
                        'is_h': bool(b['is_h']),
                        'pos': b['pos'],
                        'mode': mode,
                        'coords': run_coords,
                        'lengths': lengths,
                    })

            master_beam['geometry']['classified']['bottom_runs'] = bottom_runs

            merged_coords = self.fundo_interpreter.consolidate_occurrences(
                occurrence_coords
            )
            master_beam['geometry']['classified']['merged_bottom_groups_coords'] = merged_coords

            # Divisores representam apoios; painéis/fallback representam os
            # intervalos livres propriamente ditos.
            source_coords = sorted(
                coord
                for coords in occurrence_coords
                for coord in coords
            )
            if (
                source_coords
                and source_coords[0][1] - source_coords[0][0] < 30
            ):
                spans = []
                for i in range(len(merged_coords) - 1):
                    span = merged_coords[i + 1][0] - merged_coords[i][1]
                    if span > 10.0:
                        spans.append(span)
                master_beam['geometry']['classified']['merged_bottom_lengths'] = spans
            else:
                master_beam['geometry']['classified']['merged_bottom_lengths'] = (
                    self.fundo_interpreter.lengths(merged_coords)
                )

            lv_occurrence_coords = [
                b['geometry']['classified'].get(
                    'lv_merged_bottom_groups_coords', []
                )
                for b in beam_list
            ]
            lv_source_coords = sorted(
                coord
                for coords in lv_occurrence_coords
                for coord in coords
            )
            lv_coords = self.fundo_interpreter.consolidate_occurrences(
                lv_occurrence_coords
            )
            if (
                lv_source_coords
                and lv_source_coords[0][1] - lv_source_coords[0][0] < 30
            ):
                lv_lengths = [
                    lv_coords[index + 1][0] - lv_coords[index][1]
                    for index in range(len(lv_coords) - 1)
                    if lv_coords[index + 1][0] - lv_coords[index][1] > 10.0
                ]
            else:
                lv_lengths = self.fundo_interpreter.lengths(lv_coords)
            master_beam['geometry']['classified'].update({
                'lv_merged_bottom_groups_coords': lv_coords,
                'lv_merged_bottom_lengths': lv_lengths,
            })

            final_beams.append(master_beam)
            
        return final_beams

    @staticmethod
    def _orientation_from_label(rotation) -> bool | None:
        """Usa texto ortogonal; rótulos diagonais ficam para a geometria."""
        try:
            angle = float(rotation) % 180.0
        except (TypeError, ValueError):
            return None
        horizontal_distance = min(angle, 180.0 - angle)
        vertical_distance = abs(angle - 90.0)
        if min(horizontal_distance, vertical_distance) > 10.0:
            return None
        return horizontal_distance <= vertical_distance

    def _determine_orientation(
        self,
        pos: Tuple[float, float],
        label_rotation=None,
    ) -> bool:
        label_orientation = self._orientation_from_label(label_rotation)
        if label_orientation is not None:
            return label_orientation
        cands = self.spatial_index.query_bbox((pos[0]-400, pos[1]-400, pos[0]+400, pos[1]+400))
        
        best_h_len = 0
        best_v_len = 0
        
        for cand in cands:
            if isinstance(cand, dict) and 'points' in cand:
                for i in range(len(cand['points'])-1):
                    p1, p2 = cand['points'][i], cand['points'][i+1]
                    dx = abs(p2[0]-p1[0])
                    dy = abs(p2[1]-p1[1])
                    l = max(dx, dy)
                    if l < 10: continue
                    
                    if dx > dy:
                        cy = (p1[1] + p2[1]) / 2
                        if abs(cy - pos[1]) <= 60:
                            best_h_len = max(best_h_len, l)
                    else:
                        cx = (p1[0] + p2[0]) / 2
                        if abs(cx - pos[0]) <= 60:
                            best_v_len = max(best_v_len, l)
                            
        return best_h_len >= best_v_len

    def _capture_geometry(self, pos: Tuple[float, float], is_h: bool, orientations: Dict[int, bool], beam_labels: List[Dict], my_name: str) -> List[List[Tuple[float, float]]]:
        contain_long = 4000
        contain_trans = 30
        if is_h:
            cbox = (pos[0]-contain_long, pos[1]-contain_trans, pos[0]+contain_long, pos[1]+contain_trans)
        else:
            cbox = (pos[0]-contain_trans, pos[1]-contain_long, pos[0]+contain_trans, pos[1]+contain_long)

        def _in_box(pts):
            for p in pts:
                if cbox[0] <= p[0] <= cbox[2] and cbox[1] <= p[1] <= cbox[3]:
                    return True
            return False

        def _owns(pts):
            return self._label_owns_points(
                pts, pos, is_h, orientations, beam_labels, my_name
            )

        sementes = []
        seed_cands = self.spatial_index.query_bbox(
            (pos[0]-60, pos[1]-60, pos[0]+60, pos[1]+60)
        )
        for cand in seed_cands:
            if (
                isinstance(cand, dict)
                and 'points' in cand
                and _in_box(cand['points'])
            ):
                sementes.append(cand)

        visited = set()
        q = []
        res_lines = []

        for seed in sementes:
            if id(seed) not in visited:
                visited.add(id(seed))
                q.append(seed)
                res_lines.append(seed['points'])

        while q and len(res_lines) < 5000:
            current = q.pop(0)
            for point in current['points']:
                if not (
                    cbox[0] <= point[0] <= cbox[2]
                    and cbox[1] <= point[1] <= cbox[3]
                ):
                    continue
                neighbors = self.spatial_index.query_bbox((
                    point[0]-400,
                    point[1]-400,
                    point[0]+400,
                    point[1]+400,
                ))
                for candidate in neighbors:
                    if isinstance(candidate, dict) and 'points' in candidate:
                        if (
                            id(candidate) not in visited
                            and _in_box(candidate['points'])
                            and _owns(candidate['points'])
                        ):
                            visited.add(id(candidate))
                            q.append(candidate)
                            res_lines.append(candidate['points'])

        return res_lines

    def _capture_fundo_geometry(
        self,
        pos: Tuple[float, float],
        is_h: bool,
        orientations: Dict[int, bool],
        beam_labels: List[Dict],
        my_name: str,
    ) -> List[List[Tuple[float, float]]]:
        """Captura FV sem emprestar semântica para laterais.

        A geometria de fundo pode conter uma LINE nativa curta, perpendicular
        ao eixo, no meio de duas bordas paralelas.  O region-growing comum não
        alcança esse divisor porque ele toca o *interior* das bordas, não seus
        endpoints.  Aceitá-lo livremente absorveria cotas e hachuras; por isso
        a regra é estrita: a LINE deve atravessar, de ponta a ponta, duas
        bordas axiais já capturadas da mesma faixa do FV e pertencer ao rótulo.

        A captura com LINE nativa também preserva continuações axiais reais
        que terminam em um apoio.  Esta lista é exclusiva de FV; LV recebe sua
        própria captura em :meth:`detect_beams`.
        """
        captured = self._capture_geometry_with_native_lines_experimental(
            pos, is_h, orientations, beam_labels, my_name,
        )
        if not captured:
            return captured

        axis = 0 if is_h else 1
        transverse = 1 - axis
        edge_tolerance = 5.0
        min_width = 10.0
        max_width = 80.0

        # Bordas axiais já comprovadas pela classificação FV da captura
        # topológica. Não basta uma linha paralela no corredor: cotas e
        # detalhes de vigas vizinhas também podem ser paralelos.  Usar somente
        # seg_bottom fixa a evidência na faixa de fundo já reconhecida, sem
        # usar N2/N4, cotas ou texto como fonte de uma fronteira nova.
        baseline_classified = self._classify_lines(
            pos, captured, is_h, label_pos=pos,
        )
        axial_edges = []
        for points in baseline_classified.get('seg_bottom') or []:
            if len(points) < 2:
                continue
            axis_values = [point[axis] for point in points]
            transverse_values = [point[transverse] for point in points]
            axis_span = max(axis_values) - min(axis_values)
            transverse_span = max(transverse_values) - min(transverse_values)
            if axis_span < 30.0 or transverse_span > edge_tolerance:
                continue
            axial_edges.append([
                min(axis_values),
                max(axis_values),
                sum(transverse_values) / len(transverse_values),
                set(),
            ])

        if len(axial_edges) < 2:
            return captured

        axis_values = [
            point[axis]
            for line in (baseline_classified.get('seg_bottom') or [])
            for point in line
        ]
        transverse_values = [
            point[transverse]
            for line in (baseline_classified.get('seg_bottom') or [])
            for point in line
        ]
        search_box = (
            min(axis_values) - 5.0,
            min(transverse_values) - 5.0,
            max(axis_values) + 5.0,
            max(transverse_values) + 5.0,
        )
        # SpatialIndex sempre usa x/y; reconstrói a caixa nessa ordem para
        # vigas verticais sem inverter os eixos semânticos acima.
        if is_h:
            bbox = search_box
        else:
            bbox = (
                search_box[1], search_box[0], search_box[3], search_box[2],
            )

        # A coincidência geométrica não basta: uma cota pode atravessar uma
        # faixa do fundo.  Cada borda traz os layers das entidades axiais que
        # a provaram; o divisor nativo só é aceito se tiver o mesmo layer nas
        # duas bordas que fecha.  Assim a regra funciona com qualquer layer
        # estrutural, sem enumerar nomes, e rejeita linhas de dimensão.
        for edge in axial_edges:
            edge_axis_min, edge_axis_max, edge_transverse, edge_layers = edge
            if is_h:
                edge_bbox = (
                    edge_axis_min - edge_tolerance,
                    edge_transverse - edge_tolerance,
                    edge_axis_max + edge_tolerance,
                    edge_transverse + edge_tolerance,
                )
            else:
                edge_bbox = (
                    edge_transverse - edge_tolerance,
                    edge_axis_min - edge_tolerance,
                    edge_transverse + edge_tolerance,
                    edge_axis_max + edge_tolerance,
                )
            for source in self.spatial_index.query_bbox(edge_bbox):
                if not isinstance(source, dict):
                    continue
                source_points = self._entity_points(source)
                if len(source_points) < 2:
                    continue
                source_axis = [point[axis] for point in source_points]
                source_transverse = [point[transverse] for point in source_points]
                source_axis_span = max(source_axis) - min(source_axis)
                source_transverse_span = max(source_transverse) - min(source_transverse)
                overlaps_edge = min(edge_axis_max, max(source_axis)) - max(
                    edge_axis_min, min(source_axis)
                )
                min_structural_overlap = max(
                    30.0,
                    min(100.0, (edge_axis_max - edge_axis_min) * 0.5),
                )
                if (
                    source_axis_span >= 30.0
                    and source_transverse_span <= edge_tolerance
                    and overlaps_edge >= min_structural_overlap
                    and abs(
                        (sum(source_transverse) / len(source_transverse))
                        - edge_transverse
                    ) <= edge_tolerance
                ):
                    edge_layers.add(str(source.get('layer') or ''))

        def _is_native_line(candidate: Dict) -> bool:
            return (
                isinstance(candidate, dict)
                and not candidate.get('points')
                and candidate.get('start') is not None
                and candidate.get('end') is not None
            )

        def _bridges_existing_fv_strip(
            points: List[Tuple[float, float]],
            native_layer: str,
        ) -> bool:
            if len(points) != 2:
                return False
            candidate_axis = [point[axis] for point in points]
            candidate_transverse = [point[transverse] for point in points]
            axis_span = max(candidate_axis) - min(candidate_axis)
            width = max(candidate_transverse) - min(candidate_transverse)
            if axis_span > edge_tolerance or not (min_width <= width <= max_width):
                return False

            axis_position = sum(candidate_axis) / 2.0
            low, high = min(candidate_transverse), max(candidate_transverse)
            low_matches = [
                edge for edge in axial_edges
                if edge[0] - edge_tolerance <= axis_position <= edge[1] + edge_tolerance
                and abs(edge[2] - low) <= edge_tolerance
            ]
            high_matches = [
                edge for edge in axial_edges
                if edge[0] - edge_tolerance <= axis_position <= edge[1] + edge_tolerance
                and abs(edge[2] - high) <= edge_tolerance
            ]
            return any(
                native_layer in (low_edge[3] & high_edge[3])
                for low_edge in low_matches
                for high_edge in high_matches
            )

        def _already_captured(points: List[Tuple[float, float]]) -> bool:
            for existing in captured:
                if len(existing) != len(points):
                    continue
                if all(
                    self._point_dist(first, second) <= 0.05
                    for first, second in zip(existing, points)
                ):
                    return True
            return False

        for candidate in self.spatial_index.query_bbox(bbox):
            if not _is_native_line(candidate):
                continue
            points = self._entity_points(candidate)
            if (
                _bridges_existing_fv_strip(
                    points, str(candidate.get('layer') or ''),
                )
                and self._label_owns_points(
                    points, pos, is_h, orientations, beam_labels, my_name,
                )
                and not _already_captured(points)
            ):
                captured.append(points)

        return captured

    def _capture_geometry_with_native_lines_experimental(self, pos: Tuple[float, float], is_h: bool, orientations: Dict[int, bool], beam_labels: List[Dict], my_name: str) -> List[List[Tuple[float, float]]]:
        contain_long = 4000
        contain_trans = 30
        connection_tolerance = 80.0
        if is_h:
            cbox = (pos[0]-contain_long, pos[1]-contain_trans, pos[0]+contain_long, pos[1]+contain_trans)
        else:
            cbox = (pos[0]-contain_trans, pos[1]-contain_long, pos[0]+contain_trans, pos[1]+contain_long)
            
        def _in_box(pts):
            for p in pts:
                if cbox[0] <= p[0] <= cbox[2] and cbox[1] <= p[1] <= cbox[3]:
                    return True
            return False

        def _owns(pts):
            return self._label_owns_points(
                pts, pos, is_h, orientations, beam_labels, my_name
            )

        seed_cands = self.spatial_index.query_bbox((pos[0]-60, pos[1]-60, pos[0]+60, pos[1]+60))
        layer_scores = {}
        for cand in seed_cands:
            # As POLYLINEs já eram a fonte confiável do tracer. Elas definem
            # quais layers de LINE nativa pertencem à geometria estrutural,
            # evitando absorver cotas/hachuras de outros layers.
            if not isinstance(cand, dict) or not cand.get('points'):
                continue
            cand_points = self._entity_points(cand)
            if len(cand_points) < 2 or not _in_box(cand_points):
                continue
            xs = [point[0] for point in cand_points]
            ys = [point[1] for point in cand_points]
            axis_extent = (
                max(xs) - min(xs)
                if is_h
                else max(ys) - min(ys)
            )
            transverse_extent = (
                max(ys) - min(ys)
                if is_h
                else max(xs) - min(xs)
            )
            if axis_extent < 10 or transverse_extent > 80:
                continue
            layer = str(cand.get('layer') or '')
            layer_scores[layer] = layer_scores.get(layer, 0.0) + axis_extent

        if not layer_scores:
            # Suporte a desenhos compostos somente por LINE: escolhe o layer
            # axial dominante junto ao rótulo, sem liberar todos os layers.
            for cand in seed_cands:
                if not isinstance(cand, dict) or cand.get('points'):
                    continue
                cand_points = self._entity_points(cand)
                if len(cand_points) < 2 or not _in_box(cand_points):
                    continue
                xs = [point[0] for point in cand_points]
                ys = [point[1] for point in cand_points]
                axis_extent = (
                    max(xs) - min(xs)
                    if is_h
                    else max(ys) - min(ys)
                )
                transverse_extent = (
                    max(ys) - min(ys)
                    if is_h
                    else max(xs) - min(xs)
                )
                if axis_extent < 10 or transverse_extent > 80:
                    continue
                layer = str(cand.get('layer') or '')
                layer_scores[layer] = layer_scores.get(layer, 0.0) + axis_extent

        structural_native_layers = set()
        if layer_scores:
            best_layer_score = max(layer_scores.values())
            structural_native_layers = {
                layer
                for layer, score in layer_scores.items()
                if score >= best_layer_score * 0.75
            }

        def _is_native_line(cand):
            return (
                isinstance(cand, dict)
                and not cand.get('points')
                and cand.get('start') is not None
                and cand.get('end') is not None
            )

        def _capture_points(cand):
            if _is_native_line(cand):
                if (
                    structural_native_layers
                    and str(cand.get('layer') or '') not in structural_native_layers
                ):
                    return []
                native_points = self._entity_points(cand)
                if len(native_points) < 2:
                    return []
                xs = [point[0] for point in native_points]
                ys = [point[1] for point in native_points]
                dx = max(xs) - min(xs)
                dy = max(ys) - min(ys)
                if max(dx, dy) <= 30.0:
                    # Traços curtos repetidos são tipicamente hachura, marcas
                    # ou símbolos; não podem formar uma ponte topológica.
                    return []
                # LINEs estritamente perpendiculares incluem divisores de
                # modulação e cotas. Mudança de profundidade será classificada
                # pela topologia B/H, não por toda linha transversal encontrada.
                if (is_h and dy > dx * 3.0) or (
                    not is_h and dx > dy * 3.0
                ):
                    return []
                return native_points
            return self._entity_points(cand)

        def _is_compact_support(points):
            if len(points) < 4 or self._point_dist(points[0], points[-1]) >= 5.0:
                return False
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            narrow = min(dx, dy)
            long = max(dx, dy)
            return (
                narrow >= 10.0
                and long < 250.0
                and long / max(narrow, 1e-9) < 7.0
            )

        def _endpoint_connected(points, existing_lines, tolerance=40.0):
            if len(points) < 2:
                return False
            endpoints = (points[0], points[-1])
            for existing in existing_lines:
                if len(existing) < 2:
                    continue
                # Uma LINE nativa não pode usar um apoio compacto como ponte
                # para capturar o vão estrutural do outro lado.
                if _is_compact_support(existing):
                    continue
                existing_endpoints = (existing[0], existing[-1])
                if any(
                    self._point_dist(first, second) <= tolerance
                    for first in endpoints
                    for second in existing_endpoints
                ):
                    return True
            return False

        def _adds_axis_coverage(points, existing_lines, tolerance=5.0):
            if len(points) < 2:
                return False
            axis = 0 if is_h else 1
            transverse = 1 - axis
            cand_min = min(point[axis] for point in points)
            cand_max = max(point[axis] for point in points)
            cand_transverse = sum(point[transverse] for point in points) / len(points)
            for existing in existing_lines:
                if len(existing) < 2:
                    continue
                existing_transverse = (
                    sum(point[transverse] for point in existing) / len(existing)
                )
                if abs(existing_transverse - cand_transverse) > 5.0:
                    continue
                existing_min = min(point[axis] for point in existing)
                existing_max = max(point[axis] for point in existing)
                if (
                    cand_min >= existing_min - tolerance
                    and cand_max <= existing_max + tolerance
                ):
                    return False
            return True

        def _is_traversable(points):
            if len(points) < 2:
                return False
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            # Elementos perpendiculares podem ser evidência/divisor do fundo,
            # mas não são caminho para saltar à viga vizinha.
            return not (
                (is_h and dy > dx * 3.0)
                or (not is_h and dx > dy * 3.0)
            )

        polyline_seed_lines = [
            self._entity_points(cand)
            for cand in seed_cands
            if isinstance(cand, dict) and cand.get('points')
        ]
        polyline_seed_lines = [
            points for points in polyline_seed_lines if len(points) >= 2
        ]

        sementes = []
        for cand in seed_cands:
            cand_points = _capture_points(cand)
            if not cand_points or not _in_box(cand_points):
                continue
            if (
                _is_native_line(cand)
                and polyline_seed_lines
                and (
                    not _endpoint_connected(cand_points, polyline_seed_lines)
                    or not _adds_axis_coverage(cand_points, polyline_seed_lines)
                )
            ):
                continue
            if cand_points:
                sementes.append((cand, cand_points))
                
        visited = set()
        q = []
        res_lines = []
        
        for s, points in sementes:
            if id(s) not in visited:
                visited.add(id(s))
                if _is_traversable(points):
                    q.append(s)
                res_lines.append(points)
                
        while q and len(res_lines) < 5000:
            curr = q.pop(0)
            for pt in _capture_points(curr):
                if not (cbox[0] <= pt[0] <= cbox[2] and cbox[1] <= pt[1] <= cbox[3]):
                    continue
                vizinhos = self.spatial_index.query_bbox((
                    pt[0] - connection_tolerance,
                    pt[1] - connection_tolerance,
                    pt[0] + connection_tolerance,
                    pt[1] + connection_tolerance,
                ))
                for cand in vizinhos:
                    cand_points = _capture_points(cand)
                    if cand_points:
                        if (
                            _is_native_line(cand)
                            and (
                                not _endpoint_connected(cand_points, res_lines)
                                or not _adds_axis_coverage(cand_points, res_lines)
                            )
                        ):
                            continue
                        if id(cand) not in visited and _in_box(cand_points) and _owns(cand_points):
                            visited.add(id(cand))
                            if _is_traversable(cand_points):
                                q.append(cand)
                            res_lines.append(cand_points)
                            
        return res_lines

    def _process_beam_geometry(
        self,
        pos: Tuple[float, float],
        raw_lines: List[Dict],
        is_h: bool,
        visual_obstacles: List[Dict] = None,
        lv_raw_lines: List[Dict] | None = None,
        lv_is_h: bool | None = None,
    ) -> Dict:
        beam_geometry = {
            'lines': raw_lines,
            'texts': [],
            'dimension_texts': [],
            'support_candidates': [],
            'slab_candidates': [],
            'classified': {'seg_side_a': [], 'seg_side_b': [], 'seg_bottom': []}
        }
        
        if not raw_lines: return beam_geometry
            
        all_x = [p[0] for l in raw_lines for p in l]
        all_y = [p[1] for l in raw_lines for p in l]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        # Caixa generosa: cotas, nível e rótulos P/L/h= ficam próximos da viga
        # (400 cobre lajes laterais e seções H/B invertidas tipo 100/19).
        search_box = (min_x - 400, min_y - 400, max_x + 400, max_y + 400)
        cands = self.spatial_index.query_bbox(search_box)
        seen_support = set()
        seen_slab = set()
        for c in cands:
            if not isinstance(c, dict):
                continue
            # Geometria de apoio (polylines com type pilar/pilar-like ou tags)
            etype = str(c.get('type') or c.get('entity_type') or '').upper()
            layer = str(c.get('layer') or '').upper()
            pts = c.get('points')
            if pts and len(pts) >= 2 and not c.get('text'):
                # Candidato geométrico próximo (pilar contorno) — só se layer/tipo sugerir
                if any(tok in layer for tok in ('PIL', 'PILA', 'COL', 'ESTR')) or 'PIL' in etype:
                    key = ('geom', round(pts[0][0], 1), round(pts[0][1], 1), len(pts))
                    if key not in seen_support:
                        seen_support.add(key)
                        beam_geometry['support_candidates'].append(dict(c, role='geometry'))
                continue
            if 'text' not in c:
                continue
            txt = str(c.get('text') or '').strip()
            if not txt:
                continue
            # Dimensão numérica pura ou seção B/H
            if re.fullmatch(r'\d+(?:[.,]\d+)?', txt):
                beam_geometry['dimension_texts'].append(c)
            elif re.fullmatch(r'\d+(?:[.,]\d+)?\s*[/xX]\s*\d+(?:[.,]\d+)?', txt):
                beam_geometry['dimension_texts'].append(c)
            else:
                beam_geometry['texts'].append(c)
            # Apoios: Pxx, VFxx, Vxx (textos de pilar/viga de apoio)
            if re.match(r'^(?:P|VF|V)\d+[A-Za-z]?$', txt, re.I):
                key = ('t', txt.upper(), round(float((c.get('pos') or (0, 0))[0]), 1),
                       round(float((c.get('pos') or (0, 0))[1]), 1))
                if key not in seen_support:
                    seen_support.add(key)
                    beam_geometry['support_candidates'].append(dict(c, name=txt, text=txt))
            # Lajes: Lxx
            if re.match(r'^L\d+[A-Za-z]?$', txt, re.I):
                key = ('l', txt.upper(), round(float((c.get('pos') or (0, 0))[0]), 1),
                       round(float((c.get('pos') or (0, 0))[1]), 1))
                if key not in seen_slab:
                    seen_slab.add(key)
                    beam_geometry['slab_candidates'].append(dict(c, name=txt, text=txt))
                        
        # Pilar NASCE é semântica exclusiva do fundo: ele atravessa a área FV,
        # mas não pode alterar a leitura de laterais da mesma viga.
        beam_geometry['classified'] = self._classify_lines(
            pos, raw_lines, is_h, label_pos=pos, visual_obstacles=visual_obstacles,
        )
        lv_visual_obstacles = [
            obstacle for obstacle in (visual_obstacles or [])
            if str((obstacle or {}).get('type') or '').upper() != 'PILAR_NASCENTE'
        ]
        lv_classified = self._classify_lines(
            pos,
            lv_raw_lines if lv_raw_lines is not None else raw_lines,
            is_h if lv_is_h is None else lv_is_h,
            label_pos=pos,
            visual_obstacles=lv_visual_obstacles,
        )
        # A nuvem bruta inclui cruzamentos e cotas vizinhas alcançados pelo
        # region-growing. Para vincular a seção B/H, use primeiro o fundo já
        # classificado da própria viga; só recorra à nuvem quando não houver
        # eixo/fundo utilizável.
        dimension_geometry = (
            lv_classified.get('seg_bottom')
            or (lv_raw_lines if lv_raw_lines is not None else raw_lines)
        )
        beam_geometry['lv_dimension_text'] = self._nearest_beam_dimension(
            pos,
            dimension_geometry,
            is_h if lv_is_h is None else lv_is_h,
        )
        beam_geometry['classified'].update({
            'lv_seg_side_a': lv_classified.get('seg_side_a', []),
            'lv_seg_side_b': lv_classified.get('seg_side_b', []),
            'lv_merged_bottom_groups_coords': lv_classified.get(
                'merged_bottom_groups_coords', []
            ),
            'lv_bottom_mode': lv_classified.get('bottom_mode', 'fallback'),
        })
        beam_geometry['classified']['merged_bottom_lengths'] = []
        return beam_geometry

    def _nearest_beam_dimension(
        self,
        pos: Tuple[float, float],
        raw_lines: List[Dict],
        is_h: bool,
    ) -> Dict | None:
        """Dimensão B/H alinhada ao contrato LV, sem reutilizar a ficha FV."""
        if not raw_lines:
            return None
        all_x = [point[0] for line in raw_lines for point in line]
        all_y = [point[1] for line in raw_lines for point in line]
        search_box = (
            min(all_x) - 160,
            min(all_y) - 160,
            max(all_x) + 160,
            max(all_y) + 160,
        )
        preferred = []  # B/H com B <= H (contrato LV clássico)
        fallback = []   # H/B (ex. 100/19 de viga larga / parede)

        def _geometry_score(point) -> tuple[float, float, float]:
            """Prioriza a seção que pertence ao trecho geométrico capturado.

            Distância ao rótulo da viga é apenas desempate. Em plantas com
            trechos colineares consecutivos (por exemplo, uma viga termina e
            outra começa no mesmo eixo), o rótulo pode ficar junto da emenda e
            mais perto da seção do trecho vizinho. O vínculo correto é:
            coordenada longitudinal dentro do bbox do trecho, depois distância
            transversal ao seu eixo, só então proximidade ao nome.
            """
            px, py = float(point[0]), float(point[1])
            if is_h:
                longitudinal = px
                lo, hi = min(all_x), max(all_x)
                transverse = py
                transverse_center = (min(all_y) + max(all_y)) / 2.0
            else:
                longitudinal = py
                lo, hi = min(all_y), max(all_y)
                transverse = px
                transverse_center = (min(all_x) + max(all_x)) / 2.0
            if longitudinal < lo:
                longitudinal_gap = lo - longitudinal
            elif longitudinal > hi:
                longitudinal_gap = longitudinal - hi
            else:
                longitudinal_gap = 0.0
            transverse_gap = abs(transverse - transverse_center)
            label_distance = (
                (px - float(pos[0])) ** 2 + (py - float(pos[1])) ** 2
            ) ** 0.5
            return (longitudinal_gap, transverse_gap, label_distance)

        for candidate in self.spatial_index.query_bbox(search_box):
            if not isinstance(candidate, dict) or 'text' not in candidate:
                continue
            text = str(candidate.get('text') or '').strip()
            if not re.fullmatch(r'\d+(?:[.,]\d+)?\s*[/xX]\s*\d+(?:[.,]\d+)?', text):
                continue
            dimensions = [
                float(value.replace(',', '.'))
                for value in re.findall(r'\d+(?:[.,]\d+)?', text)
            ]
            if len(dimensions) < 2:
                continue
            text_orientation = self._orientation_from_label(
                candidate.get('rotation')
            )
            if text_orientation is not None and text_orientation != is_h:
                continue
            point = candidate.get('pos') or pos
            score = _geometry_score(point)
            label_distance_sq = score[2] ** 2
            # Preferir B/H; aceitar H/B só se bem perto do rótulo da viga
            # (vigas largas tipo 100/19; cotas de pilar 120/19 ficam mais longe).
            if dimensions[0] <= dimensions[1]:
                preferred.append((score, candidate))
            elif label_distance_sq <= (120.0 ** 2):
                fallback.append((score, candidate))
        pool = preferred or fallback
        return min(pool, key=lambda item: item[0])[1] if pool else None

    def _group_bottom_lengths_and_coords(self, segs: List[List[Tuple[float, float]]], is_h: bool) -> Tuple[List[float], List[Tuple[float, float]]]:
        # Merge collinear segments and return their lengths and coords
        if not segs: return [], []
        
        spans = []
        for s in segs:
            if len(s) < 2: continue
            if is_h:
                spans.append((min(p[0] for p in s), max(p[0] for p in s)))
            else:
                spans.append((min(p[1] for p in s), max(p[1] for p in s)))
                
        # Merge overlapping spans, but preserve distinct adjacent panels
        spans.sort(key=lambda x: x[0])
        merged = []
        cur_min, cur_max = spans[0]
        for start, end in spans[1:]:
            is_narrow_1 = (cur_max - cur_min) < 30
            is_narrow_2 = (end - start) < 30
            
            if start <= cur_max - 5:
                # Signficant overlap (same panel captured multiple times)
                cur_max = max(cur_max, end)
            elif is_narrow_1 and is_narrow_2 and (start - cur_max) <= 30:
                # Close divisores (pillars/obstacles) -> merge
                cur_max = max(cur_max, end)
            else:
                merged.append((cur_min, cur_max))
                cur_min, cur_max = start, end
        merged.append((cur_min, cur_max))
        
        final_merged = [(start, end) for start, end in merged if end - start > 10]
        lengths = [end - start for start, end in final_merged]
        return lengths, final_merged

    def _point_dist(self, p1, p2):
        import math
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def _classify_lines(self, center: Tuple[float, float], lines: List[List[Tuple[float, float]]], is_horizontal: bool, label_pos=None, visual_obstacles=None) -> Dict:
        """
        Classifica linhas em Lado A, Lado B e Fundo baseado na posicao relativa ao centro.
        Assumes horizontal or vertical beams mostly.
        """
        classified = {
            'seg_side_a': [],
            'seg_side_b': [],
            'seg_bottom': [],
            # Exclusivo FV: divisores nativos que fecham as duas bordas
            # locais. Não alimentam a leitura de LV.
            'fv_physical_divider_positions': [],
        }
        valid_lines = []
        horizontal_weight = 0
        vertical_weight = 0
        sum_hx, sum_hlen = 0.0, 0.0
        sum_vy, sum_vlen = 0.0, 0.0
        
        for line in lines:
            if len(line) < 2: continue
            
            xs = [p[0] for p in line]
            ys = [p[1] for p in line]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            dx = max_x - min_x
            dy = max_y - min_y
            length = max(dx, dy)
            
            if length < 10: continue # Ignora linhas muito curtas (ruido)
            
            cx, cy = (min_x+max_x)/2.0, (min_y+max_y)/2.0
            if dx > dy: 
                horizontal_weight += length
                sum_vy += cy * length
                sum_vlen += length
            else: 
                vertical_weight += length
                sum_hx += cx * length
                sum_hlen += length
                
            valid_lines.append({'line': line, 'dx': dx, 'dy': dy, 'len': length, 'center': (cx, cy)})

        # Define a orientação primária e o centro geométrico com base nos polígonos fechados primeiro
        bottom_cands = [item for item in valid_lines if len(item['line']) >= 4 and abs(item['line'][0][0] - item['line'][-1][0]) < 1.0 and abs(item['line'][0][1] - item['line'][-1][1]) < 1.0]
        if bottom_cands:
            geo_center_x = sum(c['center'][0] * c['len'] for c in bottom_cands) / sum(c['len'] for c in bottom_cands)
            geo_center_y = sum(c['center'][1] * c['len'] for c in bottom_cands) / sum(c['len'] for c in bottom_cands)
            geo_center = (geo_center_x, geo_center_y)
        else:
            geo_center_x = sum_hx / sum_hlen if sum_hlen > 0 else 0
            geo_center_y = sum_vy / sum_vlen if sum_vlen > 0 else 0
            geo_center = (geo_center_x, geo_center_y)
        
        bottom_candidates = []
        for item in valid_lines:
            line = item['line']
            lc = item['center']
            dx, dy = item['dx'], item['dy']
            length = item['len']
            
            is_perpendicular = (is_horizontal and dy > dx) or \
                               (not is_horizontal and dx > dy)
                               
            is_closed = len(line) >= 4 and self._point_dist(line[0], line[-1]) < 5.0
            
            is_pillar = False
            # Se for polígono fechado, o eixo menor deve ser a largura da viga (ex: 10 a 60cm).
            # Se for muito largo, não é um fundo de viga individual.
            if is_closed:
                width = min(dx, dy)
                length = max(dx, dy)
                if width > 80:
                    is_closed = False # Falso positivo, pode ser uma laje
                elif width >= 10 and length / width < 7.0 and length < 250:
                    # É muito provavelmente um PILAR (ex: 20x40, 30x90).
                    # Vigas (quando desenhadas fechadas) tendem a ser muito mais alongadas.
                    is_pillar = True
                    
            if is_pillar:
                continue
            
            # Condições para ser fundo:
            # 1. É uma linha solta perpendicular (divisória) de tamanho razoável
            # 2. É um polígono fechado PARALELO à viga, E está próximo ao CENTRO GEOMÉTRICO do desenho
            # 3. [NEW] É uma linha aberta PARALELA ao eixo da viga, com comprimento > 30,
            #    e que passa perto do label (eixo transversal ±40u). Esses são os fundos
            #    reais no CAD quando o DXF não usa polígonos fechados.
            is_valid_bottom = False

            if not is_closed and is_perpendicular and length <= 80:
                is_valid_bottom = True
            elif is_closed and not is_perpendicular:
                # Checagem de distância ao centro geométrico do bloco para achar a chapa do meio (Fundo)
                if is_horizontal:
                    dist_to_center = abs(lc[1] - geo_center[1])
                    if dist_to_center < 30.0: # Fundo fica no meio, laterais ficam afastadas
                        is_valid_bottom = True
                else:
                    dist_to_center = abs(lc[0] - geo_center[0])
                    if dist_to_center < 30.0:
                        is_valid_bottom = True
            elif not is_closed and not is_perpendicular and length > 30:
                # Critério 3: linha aberta paralela ao eixo, perto do label.
                # INDEPENDENTE DA ORIENTAÇÃO DA VIGA — usa a orientação da PRÓPRIA linha.
                # Tolerância apertada (25u) para não capturar vigas vizinhas.
                # A largura transversal deve ser < 5u (linha realmente reta, não diagonal).
                label_ref = label_pos or center
                if is_horizontal:
                    if dx > dy and dy < 5:  # horizontal panel
                        if abs(lc[1] - label_ref[1]) < 25.0:
                            is_valid_bottom = True
                    elif dy > dx and dx < 5:  # vertical height step
                        if abs(lc[1] - label_ref[1]) < 25.0:
                            is_valid_bottom = True
                else:
                    if dy > dx and dx < 5:  # vertical panel
                        if abs(lc[0] - label_ref[0]) < 25.0:
                            is_valid_bottom = True
                    elif dx > dy and dy < 5:  # horizontal height step
                        if abs(lc[0] - label_ref[0]) < 25.0:
                            is_valid_bottom = True
            
            if is_valid_bottom:
                bottom_candidates.append(item)
                continue
                
            if is_horizontal:
                if lc[1] > center[1]: # Acima
                    classified['seg_side_a'].append(line)
                else: # Abaixo
                    classified['seg_side_b'].append(line)
            else:
                if lc[0] < center[0]: # Esquerda
                    classified['seg_side_a'].append(line)
                else: # Direita
                    classified['seg_side_b'].append(line)
                    
        # Filtro de desduplicação e prioridade para polígonos sobre linhas soltas
        # Pega apenas os items que realmente formam o fundo
        raw_bottoms = []
        for cand in bottom_candidates:
            raw_bottoms.append(cand)
            classified['seg_bottom'].append(cand['line'])
            
        # Merge Logic: dois modos dependendo do tipo de candidato
        #   PAINEL: polígono horizontal largo (dx grande) — calcular largura do painel
        #   DIVISOR: linha perpendicular estreita (pilares/caps) — calcular span ENTRE divisores
        def _merge_axis(items, axis_min_fn, axis_max_fn):
            """Agrupa items por proximidade e retorna lista de (group_min, group_max)."""
            items = sorted(items, key=lambda it: axis_min_fn(it))
            groups = []
            cur_min = axis_min_fn(items[0])
            cur_max = axis_max_fn(items[0])
            for it in items[1:]:
                it_min = axis_min_fn(it)
                it_max = axis_max_fn(it)
                gap = it_min - cur_max
                if gap <= 30:   # mesmo pilar/grupo — une (30u absorve variações de pilar duplo)
                    cur_max = max(cur_max, it_max)
                else:
                    groups.append((cur_min, cur_max))
                    cur_min, cur_max = it_min, it_max
            groups.append((cur_min, cur_max))
            return groups

        def _spans_from_groups(groups, min_span=10.0):
            """Retorna spans (distâncias entre grupos consecutivos)."""
            spans = []
            for i in range(len(groups) - 1):
                span = groups[i + 1][0] - groups[i][1]   # borda interna → borda interna
                if span > min_span:
                    spans.append(span)
            return spans

        def _widths_from_groups(groups, min_width=10.0):
            """Retorna larguras internas de cada grupo (modo painel)."""
            return [g[1] - g[0] for g in groups if g[1] - g[0] > min_width]

        def _is_solid_pillar(obstacle):
            """Somente pilar existente neste pavimento interrompe um FV."""
            return str((obstacle or {}).get('type') or '').upper() == 'PILAR_SOLIDO'

        def _is_nascent_gap(start, end):
            """Verifica se uma lacuna axial pertence a um pilar que NASCE."""
            gap_min, gap_max = min(start, end), max(start, end)
            for obstacle in visual_obstacles or []:
                if str((obstacle or {}).get('type') or '').upper() != 'PILAR_NASCENTE':
                    continue
                try:
                    minx, miny, maxx, maxy = obstacle['bbox']
                except (KeyError, TypeError, ValueError):
                    continue
                axis_min, axis_max = (minx, maxx) if is_horizontal else (miny, maxy)
                trans_min, trans_max = (miny, maxy) if is_horizontal else (minx, maxx)
                if (
                    trans_min - 20.0 <= geo_center[1 if is_horizontal else 0] <= trans_max + 20.0
                    and gap_min >= axis_min - 5.0
                    and gap_max <= axis_max + 5.0
                ):
                    return True
            return False

        def _bridge_nascent_pillars(panels):
            """Une painéis separados somente por um pilar NASCE."""
            if len(panels) < 2:
                return panels
            bridged = []
            current_min, current_max = panels[0]
            for next_min, next_max in panels[1:]:
                if next_min > current_max and _is_nascent_gap(current_max, next_min):
                    current_max = max(current_max, next_max)
                    continue
                bridged.append((current_min, current_max))
                current_min, current_max = next_min, next_max
            bridged.append((current_min, current_max))
            return bridged

        # --- APPLY VISUAL OBSTACLES ---
        def _apply_obstacles_to_panels(panels, obs_list):
            if not obs_list: return panels
            new_panels = []
            for p_min, p_max in panels:
                cuts = []
                for obs in obs_list:
                    if not _is_solid_pillar(obs):
                        continue
                    minx, miny, maxx, maxy = obs['bbox']
                    if is_horizontal:
                        if miny - 20 <= geo_center[1] <= maxy + 20:
                            cuts.append((minx, maxx))
                    else:
                        if minx - 20 <= geo_center[0] <= maxx + 20:
                            cuts.append((miny, maxy))
                if not cuts:
                    new_panels.append((p_min, p_max))
                else:
                    cuts.sort()
                    curr = p_min
                    for c_min, c_max in cuts:
                        if c_max <= curr: continue
                        if c_min >= p_max: break
                        if c_min > curr + 5:
                            new_panels.append((curr, c_min))
                        curr = max(curr, c_max)
                    if curr < p_max - 5:
                        new_panels.append((curr, p_max))
            return new_panels

        if raw_bottoms:
            if is_horizontal:
                ax_min = lambda it: min(p[0] for p in it['line'])
                ax_max = lambda it: max(p[0] for p in it['line'])
            else:
                ax_min = lambda it: min(p[1] for p in it['line'])
                ax_max = lambda it: max(p[1] for p in it['line'])

            # Detectar modo: se maioria dos candidatos são estreitos → divisores (pilares)
            avg_breadth = sum(ax_max(it) - ax_min(it) for it in raw_bottoms) / len(raw_bottoms)
            groups = _merge_axis(raw_bottoms, ax_min, ax_max)

            if avg_breadth < 30 and len(groups) >= 2:
                # MODO DIVISOR: spans entre grupos de pilares
                # Adicionar obstáculos como divisores extras antes de gerar spans
                if visual_obstacles:
                    for obs in visual_obstacles:
                        if not _is_solid_pillar(obs):
                            continue
                        minx, miny, maxx, maxy = obs['bbox']
                        if is_horizontal:
                            if miny - 20 <= geo_center[1] <= maxy + 20:
                                groups.append((minx, maxx))
                        else:
                            if minx - 20 <= geo_center[0] <= maxx + 20:
                                groups.append((miny, maxy))
                    # Reordena e recria os spans
                    groups.sort()
                    # Faz um re-merge básico nos grupos para combinar obstáculos sobrepostos a pilares
                    merged_groups = []
                    c_min, c_max = groups[0]
                    for g_min, g_max in groups[1:]:
                        if g_min - c_max <= 10:
                            c_max = max(c_max, g_max)
                        else:
                            merged_groups.append((c_min, c_max))
                            c_min, c_max = g_min, g_max
                    merged_groups.append((c_min, c_max))
                    groups = merged_groups

                classified['merged_bottom_lengths'] = _spans_from_groups(groups)
                classified['merged_bottom_groups_coords'] = groups
                classified['bottom_mode'] = 'divisor'
            else:
                # MODO PAINEL: largura de cada grupo
                # O painel contém divisores internos (linhas perpendiculares curtas) que representam degraus de altura (Caso 2).
                # Eles DEVEM quebrar os painéis contínuos!
                
                painel_items = [it for it in raw_bottoms if ax_max(it) - ax_min(it) > 30]
                divisor_items = [it for it in raw_bottoms if ax_max(it) - ax_min(it) <= 30]
                
                if not painel_items:
                    painel_items = raw_bottoms
                
                # Paineis separados por um apoio curto continuam sendo
                # segmentos distintos. O merge antigo (gap <= 30) atravessava
                # esses apoios e colapsava vigas continuas como V301.
                base_panels = self.fundo_interpreter.panel_groups(
                    painel_items,
                    ax_min,
                    ax_max,
                    split_support_gaps=True,
                )
                base_panels = _bridge_nascent_pillars(base_panels)
                # O extremo de uma linha axial pode cair na borda externa de
                # uma chapa curta de encontro. FV deve encostar na face
                # estrutural interna quando ela existe no próprio DXF; sem
                # essa prova, inclusive diante de um pilar sólido, o intervalo
                # original permanece. A regra e os dados são exclusivos da
                # interpretação de fundo e não alimentam LV.
                transverse_center = sum(
                    item['center'][1 if is_horizontal else 0]
                    for item in painel_items
                ) / len(painel_items)
                base_panels = self.fundo_interpreter.resolve_attached_support_faces(
                    base_panels,
                    [item['line'] for item in valid_lines],
                    is_horizontal=is_horizontal,
                    transverse_center=transverse_center,
                )
                
                div_pos = []
                for d in divisor_items:
                    pos = (ax_min(d) + ax_max(d)) / 2.0
                    if not _is_nascent_gap(pos - 0.05, pos + 0.05):
                        div_pos.append(pos)
                div_pos.sort()
                classified['fv_physical_divider_positions'] = list(div_pos)
                
                split_panels = []
                for p_min, p_max in base_panels:
                    curr_min = p_min
                    for d_p in div_pos:
                        if curr_min + 5 < d_p < p_max - 5:
                            split_panels.append((curr_min, d_p))
                            curr_min = d_p
                    if curr_min < p_max:
                        split_panels.append((curr_min, p_max))

                # Um divisor real (apoio/mudança de altura) às vezes cai a
                # poucos cm de uma extremidade e produz um fragmento residual
                # do tamanho da largura da própria viga, não um segmento
                # estrutural — achado real V310/V331 (2026-07-20): quina
                # chanfrada, a borda mais longa de um lado do fundo gera uma
                # lasca de ~19cm colada ao painel principal quando o divisor
                # bate exatamente onde a borda mais curta começa. N2 não conta
                # essa lasca como segmento próprio nem soma seu comprimento ao
                # painel vizinho. O limiar (30cm) fica bem abaixo do menor
                # painel real confirmado no 13_PAV (41.5cm, V301) e bem acima
                # da lasca observada (19cm nos dois casos reais), então só
                # afeta esse padrão específico de fragmento residual.
                _notch_fragment_max_length = 30.0
                cleaned_panels = []
                for idx, (p_min, p_max) in enumerate(split_panels):
                    length = p_max - p_min
                    if length > _notch_fragment_max_length:
                        cleaned_panels.append((p_min, p_max))
                        continue
                    touches_larger_neighbor = False
                    if idx > 0:
                        prev_min, prev_max = split_panels[idx - 1]
                        if (
                            abs(prev_max - p_min) <= 0.5
                            and (prev_max - prev_min) > _notch_fragment_max_length
                        ):
                            touches_larger_neighbor = True
                    if idx < len(split_panels) - 1:
                        next_min, next_max = split_panels[idx + 1]
                        if (
                            abs(next_min - p_max) <= 0.5
                            and (next_max - next_min) > _notch_fragment_max_length
                        ):
                            touches_larger_neighbor = True
                    if not touches_larger_neighbor:
                        cleaned_panels.append((p_min, p_max))
                split_panels = cleaned_panels

                final_groups = _apply_obstacles_to_panels(split_panels, visual_obstacles)
                classified['merged_bottom_lengths'] = _widths_from_groups(final_groups)
                classified['merged_bottom_groups_coords'] = final_groups
                classified['bottom_mode'] = 'panel'
        else:
            # Se não houver raw_bottoms (viga vazia/sem linhas), a viga toda é o fundo.
            all_side_pts = []
            for seg in classified.get('seg_side_a', []) + classified.get('seg_side_b', []):
                all_side_pts.extend(seg)
                
            if all_side_pts:
                if is_horizontal:
                    p_min = min(p[0] for p in all_side_pts)
                    p_max = max(p[0] for p in all_side_pts)
                else:
                    p_min = min(p[1] for p in all_side_pts)
                    p_max = max(p[1] for p in all_side_pts)
            else:
                # Fallback extremo caso não tenha linhas laterais também
                axis_center = center[0] if is_horizontal else center[1]
                p_min, p_max = axis_center - 50, axis_center + 50
            base_panel = [(p_min, p_max)]
            final_groups = _apply_obstacles_to_panels(base_panel, visual_obstacles)
            classified['merged_bottom_lengths'] = _widths_from_groups(final_groups)
            classified['merged_bottom_groups_coords'] = final_groups
            classified['bottom_mode'] = 'fallback'
            
        return classified
