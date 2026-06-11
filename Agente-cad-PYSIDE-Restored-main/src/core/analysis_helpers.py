"""
analysis_helpers.py — Funções puras extraídas do Structural Analyzer (main.py Fase 3).

Todas as funções aqui são standalone (sem Qt, sem self) para uso dentro de QThread workers
e qualquer outro contexto sem UI. São equivalentes diretos de:
  - MainWindow._extract_float
  - MainWindow._run_sanity_checks
  - MainWindow._process_beam_intelligent
  - MainWindow._process_slab_intelligent
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Primitivos
# ──────────────────────────────────────────────────────────────────────────────

def extract_float(text: Any) -> Optional[float]:
    """Extrai o primeiro número float de uma string. None se não encontrar."""
    if not text:
        return None
    try:
        m = re.search(r'[-+]?\d*[.,]\d+|\d+', str(text).replace(',', '.'))
        return float(m.group()) if m else None
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Sanity Checks — Pilar
# ──────────────────────────────────────────────────────────────────────────────

def run_sanity_checks(p: Dict) -> List[str]:
    """
    Camada de IA Sóbria: valida se a geometria e vínculos fazem sentido físico.
    Equivale a MainWindow._run_sanity_checks(self, p).
    """
    issues: List[str] = []

    # 1. Check de Dimensão Pilar vs Dimensão Viga
    p_dim_text = p.get('dim', '0')
    p_nums = [int(n) for n in re.findall(r'\d+', str(p_dim_text))]
    p_min = min(p_nums) if p_nums else 15

    for side, data in p.get('sides_data', {}).items():
        v_name = data.get('v_esq_n')
        v_dim_text = data.get('v_esq_d', '')
        if v_name and v_dim_text:
            v_nums = [int(n) for n in re.findall(r'\d+', str(v_dim_text))]
            if v_nums:
                v_width = min(v_nums)
                if v_width > p_min + 5:   # tolerância de 5 cm
                    issues.append(
                        f"L{side}: Viga {v_name} ({v_width}cm) é mais larga que o pilar ({p_min}cm)"
                    )

    # 2. Check de Nível Inconsistente
    all_v_lvls: List[float] = []
    for side, data in p.get('sides_data', {}).items():
        v_lv = extract_float(data.get('v_esq_v', ''))
        if v_lv is not None:
            all_v_lvls.append(v_lv)

    if all_v_lvls:
        max_diff = max(all_v_lvls) - min(all_v_lvls)
        if max_diff > 0.5:
            issues.append(f"Inconsistência de Níveis: Diferença de {max_diff:.2f}m entre vigas.")

    return issues


# ──────────────────────────────────────────────────────────────────────────────
# Interpretação de Viga
# ──────────────────────────────────────────────────────────────────────────────

def process_beam_intelligent(b: Dict) -> None:
    """
    Popula b['fields'] e b['links'] com a interpretação semântica completa da viga.
    Equivale a MainWindow._process_beam_intelligent(self, b). Modifica b in-place.
    """
    geo = b.get('geometry', {})
    classified = geo.get('classified', {})

    # --- ESTRUTURA BASE ---
    b.update({
        'type': 'Viga',
        'is_validated': False,
        'fields': {},
        'links': {
            'name': {'label': [{'text': b.get('name', ''), 'type': 'text',
                                 'pos': b.get('pos', (0, 0)), 'role': 'Identificador Viga'}]},
            'viga_segs': {'seg_bottom': []},
            'apoios': {'inicio': [], 'fim': []},
            'lajes': {'lado_a': [], 'lado_b': []},
            'cortes': [],
            'dimensoes': [],
            'aberturas': {'pilar': [], 'viga': []},
        },
    })

    # 1. Identidade
    b['fields']['numero'] = b.get('id_item')
    b['fields']['nome'] = b.get('name', '')

    # 2. Dimensão (Texto Global)
    dim_texts = geo.get('dimension_texts', [])
    main_dim_text = ''
    if dim_texts:
        main_dim_text = dim_texts[0]['text']
        b['fields']['dimensao'] = main_dim_text
        if not isinstance(b['links']['dimensoes'], list):
            b['links']['dimensoes'] = []
        b['links']['dimensoes'].append(dim_texts[0])

    # 3. Segmentos e Comprimentos
    if 'viga_a_seg_1_comp_total_passa' not in b['links']:
        b['links']['viga_a_seg_1_comp_total_passa'] = {'seg_side_a': []}
    if 'viga_b_seg_1_comp_total_passa' not in b['links']:
        b['links']['viga_b_seg_1_comp_total_passa'] = {'seg_side_b': []}

    def _process_segments(side_key: str, tag: str, target_field_key: str) -> float:
        lines = classified.get(side_key, [])
        total_len = 0.0
        for line in lines:
            p1, p2 = line[0], line[-1]
            length = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5
            total_len += length
            if target_field_key not in b['links']:
                b['links'][target_field_key] = {}
            slot_key = side_key
            if slot_key not in b['links'][target_field_key]:
                b['links'][target_field_key][slot_key] = []
            b['links'][target_field_key][slot_key].append(
                {'type': 'poly', 'points': line, 'len': length, 'tag': tag}
            )
        return total_len

    len_a = _process_segments('seg_side_a', 'Lado A', 'viga_a_seg_1_comp_total_passa')
    len_b = _process_segments('seg_side_b', 'Lado B', 'viga_b_seg_1_comp_total_passa')
    b['fields']['comprimento_total_a'] = round(len_a, 1)
    b['fields']['comprimento_total_b'] = round(len_b, 1)
    b['seg_a'] = len(classified.get('seg_side_a', []))
    b['seg_b'] = len(classified.get('seg_side_b', []))

    # 4. Visão de Corte
    has_corte = False
    for t in geo.get('texts', []):
        if re.match(r'^[A-Z]-[A-Z]$', t['text'].strip()):
            b['links']['cortes'].append(t)
            has_corte = True
    b['fields']['possui_corte'] = has_corte

    # 5. Dimensão por Segmento — vincular texto de dimensão ao segmento mais próximo
    if dim_texts:
        for side_key, field_key in [
            ('seg_side_a', 'viga_a_seg_1_comp_total_passa'),
            ('seg_side_b', 'viga_b_seg_1_comp_total_passa'),
        ]:
            if field_key not in b['links']:
                continue
            for seg in b['links'][field_key].get(side_key, []):
                pts = seg.get('points', [])
                if not pts:
                    continue
                p1, p2 = pts[0], pts[-1]
                mid_x, mid_y = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                closest_dim = None
                min_dist = float('inf')
                for dt in dim_texts:
                    dpos = dt.get('pos')
                    if not dpos:
                        continue
                    dist = ((mid_x - dpos[0]) ** 2 + (mid_y - dpos[1]) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        closest_dim = dt
                if closest_dim and min_dist < 100:
                    seg['dim_text'] = closest_dim['text']

    # 6. Apoios (Início / Fim)
    all_pts: list = []
    for seg_list in classified.values():
        for line in seg_list:
            all_pts.extend(line)

    if all_pts:
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        is_horiz = (max(xs) - min(xs)) > (max(ys) - min(ys))
    else:
        xs, ys = [], []
        is_horiz = True

    if all_pts and geo.get('support_candidates'):
        supports = geo.get('support_candidates', [])

        def _sort_key(s):
            if 'points' in s and s['points']:
                cx = sum(p[0] for p in s['points']) / len(s['points'])
                cy = sum(p[1] for p in s['points']) / len(s['points'])
                return cx if is_horiz else cy
            return s['pos'][0] if is_horiz else s['pos'][1]

        sorted_supports = sorted(supports, key=_sort_key)
        if sorted_supports:
            b['links']['apoios']['inicio'].append(sorted_supports[0])
            if len(sorted_supports) > 1:
                b['links']['apoios']['fim'].append(sorted_supports[-1])

    # 7. Alturas (H1, H2)
    h1 = 0
    if main_dim_text:
        nums = [int(n) for n in re.findall(r'\d+', main_dim_text)]
        if nums:
            h1 = max(nums)
    b['fields']['altura_h1'] = h1
    b['fields']['altura_h2'] = h1 if has_corte else None

    # 8. Lajes (Inf, Central, Superior)
    slab_cands = geo.get('slab_candidates', [])
    if slab_cands and all_pts:
        bx = sum(xs) / len(xs)
        by = sum(ys) / len(ys)
        for s in slab_cands:
            spos = s.get('pos')
            if not spos:
                continue
            target_side = 'lado_a'
            if is_horiz:
                if spos[1] < by:
                    target_side = 'lado_b'
            else:
                if spos[0] > bx:
                    target_side = 'lado_b'
            b['links']['lajes'][target_side].append(s)
        b['fields']['laje_superior_a'] = slab_cands[0]['text'] if len(slab_cands) > 0 else ''
        b['fields']['laje_superior_b'] = slab_cands[1]['text'] if len(slab_cands) > 1 else ''

    # 9. Níveis
    b['fields']['nivel_lado_a'] = 0
    b['fields']['nivel_lado_b'] = 0
    b['fields']['nivel_oposto_a'] = 0
    b['fields']['nivel_oposto_b'] = 0

    # 10/11. Aberturas (via pilares intermediários)
    supports = geo.get('support_candidates', [])
    if supports:
        for s in supports:
            is_start = s in b['links']['apoios']['inicio']
            is_end = s in b['links']['apoios']['fim']
            if not is_start and not is_end:
                b['links']['aberturas']['pilar'].append(s)

    # 12. Fundos
    len_bottom = _process_segments('seg_bottom', 'Fundo', 'viga_segs')
    b['fields']['comprimento_fundo'] = round(len_bottom, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Interpretação de Laje
# ──────────────────────────────────────────────────────────────────────────────

def process_slab_intelligent(
    s: Dict,
    dxf_texts: List[Dict],
    slab_learning_config: Optional[Dict] = None,
) -> None:
    """
    Popula s['fields'] e s['links'] com a interpretação semântica da laje.
    Equivale a MainWindow._process_slab_intelligent(self, s). Modifica s in-place.

    Args:
        s: dicionário da laje (saído do SlabTracer).
        dxf_texts: lista de textos do DXF carregado (dxf_data['texts']).
        slab_learning_config: configurações de aprendizado ativo (opcional).
    """
    learning = slab_learning_config or {}

    # --- ESTRUTURA BASE ---
    s.update({
        'type': 'Laje',
        'is_validated': False,
        'fields': {},
        'links': {
            'name': {
                'label': [{'text': s.get('name', ''), 'type': 'text',
                            'pos': s.get('pos', (0, 0)), 'role': 'Identificador Laje'}]
            },
            'laje_dim':          {'label': []},
            'laje_nivel':        {'label': [], 'cut_view_geom': [], 'cut_view_text': []},
            'laje_outline_segs': {'contour': [], 'acrescimo_borda': []},
            '_laje_complex':     {'label': [], 'dim': [], 'cut_view': []},
        },
    })

    # 1. Identidade
    s['fields']['nome'] = s.get('name', '')
    s['fields']['numero'] = s.get('id_item')

    # 2. Procurar Textos Próximos (Dimensão, Nível)
    pos = s.get('pos')
    if pos:
        cx, cy = pos
        search_radius   = learning.get('search_radius', 200.0)
        learned_dim_lvls = learning.get('dim_layers')
        learned_lvl_lvls = learning.get('level_layers')

        candidates: List[tuple] = []
        for t in dxf_texts:
            tx, ty = t.get('pos', (0, 0))
            dist = ((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5
            if dist <= search_radius:
                candidates.append((t, dist))
        candidates.sort(key=lambda x: x[1])
        sorted_texts = [x[0] for x in candidates]

        re_thick = re.compile(r'[HhDd][= :]?\d+', re.IGNORECASE)
        re_level = re.compile(r'[+-]?\d+\.\d+|[+-]?\d+', re.IGNORECASE)

        found_thick = False
        found_level = False

        for t in sorted_texts:
            txt_val = t['text'].strip()
            t_layer = t.get('layer')

            if txt_val == s.get('name', ''):
                continue

            # Espessura
            is_dim_cand = (
                (learned_dim_lvls and t_layer in learned_dim_lvls) or
                (not learned_dim_lvls)
            )
            if is_dim_cand and not found_thick and re_thick.search(txt_val):
                s['links']['laje_dim']['label'].append(t)
                s['fields']['laje_dim'] = txt_val
                found_thick = True
                continue

            # Nível
            is_lvl_cand = (
                (learned_lvl_lvls and t_layer in learned_lvl_lvls) or
                (not learned_lvl_lvls)
            )
            if not found_level and is_lvl_cand:
                if ('+' in txt_val or '-' in txt_val or '.' in txt_val) and re_level.search(txt_val):
                    s['links']['laje_nivel']['label'].append(t)
                    s['fields']['laje_nivel'] = txt_val
                    found_level = True

    # 3. Contorno (geometria já encontrada pelo SlabTracer)
    if s.get('points'):
        s['links']['laje_outline_segs']['contour'].append({
            'type': 'poly',
            'points': s['points'],
            'role': 'Contorno Automático',
        })

    # 4. Acréscimo de Borda
    for ext in s.get('extensions', []):
        s['links']['laje_outline_segs']['acrescimo_borda'].append(ext)


# ──────────────────────────────────────────────────────────────────────────────
# Correlação sides_data (Pilar ↔ Viga)
# ──────────────────────────────────────────────────────────────────────────────

def correlate_sides_data(pilares: List[Dict], vigas: List[Dict], search_radius: float = 1200.0) -> None:
    """
    Para cada pilar e cada um de seus lados, encontra a viga mais próxima
    cujo centroide está no semiespaço exterior ao lado e a preenche em sides_data.

    Modifica pilares in-place (sides_data[side] populado com v_esq_n, v_esq_d, v_esq_v).
    """
    # Pré-calcular centroide de cada viga
    viga_centroids: List[tuple] = []
    for v in vigas:
        geo = v.get('geometry', {})
        classified = geo.get('classified', {})
        all_pts: list = []
        for seg_list in classified.values():
            for line in seg_list:
                all_pts.extend(line)
        if all_pts:
            cx = sum(p[0] for p in all_pts) / len(all_pts)
            cy = sum(p[1] for p in all_pts) / len(all_pts)
        else:
            cx, cy = v.get('pos', (0, 0))
        viga_centroids.append((cx, cy))

    for p in pilares:
        pts = p.get('points', [])
        if not pts:
            continue
        px = sum(pt[0] for pt in pts) / len(pts)
        py = sum(pt[1] for pt in pts) / len(pts)

        # Bounding box para estimar lados
        xs = [pt[0] for pt in pts]
        ys = [pt[1] for pt in pts]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # Direções canônicas por lado (A=baixo, B=cima, C=esq, D=dir)
        side_dirs: Dict[str, tuple] = {
            'A': (0.0, -1.0),  # baixo
            'B': (0.0, +1.0),  # cima
            'C': (-1.0, 0.0),  # esquerda
            'D': (+1.0, 0.0),  # direita
        }

        sides_data = p.setdefault('sides_data', {})

        for side, (dx, dy) in side_dirs.items():
            side_data = sides_data.setdefault(side, {})
            if side_data.get('v_esq_n'):
                # Já tem dado — pular
                continue

            best_v: Optional[Dict] = None
            best_dist = float('inf')

            for v, (vcx, vcy) in zip(vigas, viga_centroids):
                # Vetor pilar→viga
                vx, vy = vcx - px, vcy - py
                dist = (vx ** 2 + vy ** 2) ** 0.5
                if dist > search_radius or dist == 0:
                    continue
                # Dot product com direção do lado — deve ser positivo (semiespaço correto)
                dot = vx * dx + vy * dy
                if dot < 0:
                    continue
                if dist < best_dist:
                    best_dist = dist
                    best_v = v

            if best_v:
                # Extrair dimensão do texto global da viga
                geo_v = best_v.get('geometry', {})
                dim_texts = geo_v.get('dimension_texts', [])
                v_dim = dim_texts[0]['text'] if dim_texts else best_v.get('fields', {}).get('dimensao', '')
                v_level_str = ''
                v_nivel = best_v.get('fields', {}).get('nivel_lado_a') or best_v.get('fields', {}).get('nivel_lado_b')
                if v_nivel:
                    v_level_str = str(v_nivel)
                side_data['v_esq_n'] = best_v.get('name', '')
                side_data['v_esq_d'] = v_dim
                side_data['v_esq_v'] = v_level_str


# ──────────────────────────────────────────────────────────────────────────────
# Detecção de Pilares (standalone — sem Qt)
# ──────────────────────────────────────────────────────────────────────────────

def detect_pilares_from_polylines(
    polylines: List[Dict],
    texts: List[Dict],
    min_area: float = 100.0,
    name_radius: float = 500.0,
    dim_radius: float = 400.0,
    scope: str = "",
) -> List[Dict]:
    """
    Detecta pilares a partir de polígonos fechados nas polylines do DXF.
    Para cada pilar, tenta associar nome ('P*') e dimensão ('NxM') por proximidade.

    Retorna lista de dicts com as chaves mínimas para save_pillar + process.
    """
    import uuid

    try:
        from shapely.geometry import Polygon
        use_shapely = True
    except ImportError:
        use_shapely = False

    re_dim = re.compile(r'^\d+[xX]\d+$')
    re_pname = re.compile(r'^P\w*', re.IGNORECASE)

    pilares: List[Dict] = []
    idx = 0

    for pl in polylines:
        pts = pl.get('points', [])
        # Deduplicar pontos consecutivos iguais
        uniq: list = []
        for pt in pts:
            if not uniq or pt != uniq[-1]:
                uniq.append(pt)
        if len(uniq) < 3:
            continue

        if use_shapely:
            try:
                shape = Polygon(uniq)
                if not shape.is_valid or shape.area < min_area:
                    continue
                area_val = float(shape.area)
                bounds = shape.bounds  # (minx, miny, maxx, maxy)
                cx = (bounds[0] + bounds[2]) / 2
                cy = (bounds[1] + bounds[3]) / 2
            except Exception:
                continue
        else:
            # Fallback — bounding-box centroid, area aproximada
            if len(uniq) < 4:
                continue
            xs = [p[0] for p in uniq]; ys = [p[1] for p in uniq]
            w = max(xs) - min(xs); h = max(ys) - min(ys)
            area_val = float(w * h)
            if area_val < min_area:
                continue
            cx = (max(xs) + min(xs)) / 2
            cy = (max(ys) + min(ys)) / 2

        # Encontrar nome ('P*') mais próximo
        name_val = f'P{idx + 1}'
        dim_val = ''
        best_name_dist = float('inf')
        best_dim_dist = float('inf')

        for t in texts:
            tx, ty = t.get('pos', (0, 0))
            dist = ((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5
            txt = t.get('text', '').strip()
            if dist <= name_radius and re_pname.match(txt) and dist < best_name_dist:
                best_name_dist = dist
                name_val = txt
            if dist <= dim_radius and re_dim.match(txt) and dist < best_dim_dist:
                best_dim_dist = dist
                dim_val = txt

        # Detectar tipo/orientação via PillarPerspectiveMapper (se disponível)
        sides_data: Dict = {}
        try:
            from src.core.perspective_mapper import PillarPerspectiveMapper
            shape_type, orientation = PillarPerspectiveMapper.identify_shape(uniq)
            sides_data = PillarPerspectiveMapper.map_sides(uniq, shape_type, orientation)
        except Exception:
            # Fallback — lados canônicos simples
            sides_data = {k: {} for k in ('A', 'B', 'C', 'D')}

        # ID determinístico: mesmo pilar na mesma obra/pav sempre gera o mesmo UUID
        _geo_key = f"{scope}|{round(cx, 1)}|{round(cy, 1)}|{round(area_val, 0)}"
        _stable_id = str(uuid.uuid5(uuid.NAMESPACE_OID, _geo_key))

        p = {
            'id':        _stable_id,
            'id_item':   idx + 1,
            'name':      name_val,
            'type':      'Pilar',
            'is_validated': False,
            'area_val':  area_val,
            'points':    uniq,
            'pos':       (cx, cy),
            'dim':       dim_val,
            'sides_data': sides_data,
            'links':     {},
            'confidence_map': {},
            'fields':    {'nome': name_val, 'numero': idx + 1, 'dim': dim_val},
            'issues':    [],
        }
        pilares.append(p)
        idx += 1

    return pilares
