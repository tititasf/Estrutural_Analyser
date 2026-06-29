# -*- coding: utf-8 -*-
"""Motor Reverso FV — Extrai ficha N2 de recorte DXF STOG fundo de viga.

ALGORITMO (universal, por geometria — ZERO hardcode por viga/obra/pavimento).
Validado manualmente contra os 26 elementos FV do recorte "13_PAV" (V301..V332,
VF202, VF203, VF301) — ver scripts/arete/relatorios para o dump de validação.

  1. Cada poly (LWPOLYLINE/POLYLINE na layer 'Paineis') é um trecho físico real
     do fundo de viga. b_fv = altura (H) do poly (valor mais comum entre os
     polys do elemento).
  2. As polys do recorte cobrem o elemento-alvo E os vizinhos (contexto visual).
     Atribuição de cada poly ao elemento certo usa NOMENCLATURA (texto tipo
     'V123.C' / 'VF123.C', ou 'CONT. V123.C'):
       a. Agrupa-se os polys por "linha" (banda Y) próxima da nossa própria
          label.
       b. poly de referência = o poly que contém (ou está mais próximo de) o
          x da nossa label.
       c. Expande-se a partir dele para a esquerda/direita, poly a poly:
          - se o gap até o próximo poly é ~0 (toca, <2cm) ele É da mesma peça
            física (só um divisor modular) — inclui sempre, não há ambiguidade;
          - se o gap é real (>2cm), só inclui o próximo poly se o centro dele
            estiver mais próximo da NOSSA label do que de qualquer outra label
            de elemento na mesma linha (nearest-label). Caso contrário, para —
            esse poly pertence ao vizinho.
  3. Polys incluídos, na ordem, formam os SEGMENTOS do elemento. Um gap real
     (>2cm) ENTRE dois polys incluídos é um pilar cruzado (vira 1 'hole').
     Cada segmento (um ou mais polys que se tocam) entra em 'panels' com seu
     width TOTAL — o gerador (gerar_fv_dxf_stog.py) aplica compute_panels()
     em cada segmento individualmente para reproduzir a divisão modular real
     (validado: 254|418 em V306, 405.5|418|405.5 em VF301, 311 único em V330).
  4. b_fv final: poly height (mais confiável) — fallback cota vertical/TEXT.

Fallback: se não há geometria de paineis (recorte só com textos), usa-se a
extração antiga por COTA TEXT (_extract_fv_from_dxf_text_fallback).
"""

from pathlib import Path
import json
import re
import sqlite3

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

GAP_PILAR_MIN = 2.0      # cm — gap minimo entre polys para contar como pilar cruzado
Y_TOL_ROW = 60.0         # cm — tolerancia p/ agrupar polys/labels na mesma "linha"
B_FV_MIN, B_FV_MAX = 10.0, 40.0   # faixa plausivel de largura de viga (b_fv)

# Match V1.C, V1-V2.C, V1 / V2.C
_ELEM_CODE_RE = re.compile(r'([A-Z]+\d+[A-Z]?(?:[-/\s]+[A-Z]+\d+[A-Z]?)*)\.C')

def _get_visual_obstacles(project_id: str) -> list[dict]:
    """Retorna bounding boxes de objetos visuais (pilares NASCE ou cortes) que não interrompem a viga."""
    obstacles = []
    if not project_id:
        return obstacles
    try:
        conn = sqlite3.connect("D:/Agente-cad-PYSIDE/project_data.vision")
        rows = conn.execute("SELECT links_json FROM slabs WHERE project_id = ?", (project_id,)).fetchall()
        for r in rows:
            if not r[0]: continue
            links = json.loads(r[0])
            # 1. Pilares "NASCE"
            pillar_geom = links.get('laje_pilares_apoio', {}).get('pillar_geom', [])
            for link in pillar_geom:
                if not isinstance(link, dict): continue
                ficha = link.get('ficha', {})
                if ficha.get('hatch_description') == 'NASCE':
                    pts = link.get('points', [])
                    if pts:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        obstacles.append({'type': 'NASCE', 'bbox': (min(xs), min(ys), max(xs), max(ys))})
            # 2. Visão Corte
            cut_geom = links.get('laje_visao_corte', {}).get('cut_view_geom', [])
            for link in cut_geom:
                if not isinstance(link, dict): continue
                pts = link.get('points', [])
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    obstacles.append({'type': 'VISAO_CORTE', 'bbox': (min(xs), min(ys), max(xs), max(ys))})
        conn.close()
    except Exception as e:
        print(f"Erro ao carregar visual obstacles do SQLite: {e}")
    return obstacles


def _infer_obra_root(recorte_path: str) -> Path | None:
    p = Path(recorte_path)
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx + 1])
    return None


def _lookup_fase4_fv(elem_id: str, obra_root: Path) -> dict | None:
    """Busca JSON_Vigas_Fundo/{elem_id}_fundo.json — usado só como METADADO
    auxiliar (nunca mais como fonte de verdade para panels/comprimento)."""
    base = elem_id.split('_')[0] if '_' in elem_id else elem_id
    p = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo" / f"{base}_fundo.json"
    if p.exists():
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    p2 = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo" / f"{elem_id}_fundo.json"
    if p2.exists():
        with open(p2, encoding='utf-8') as f:
            return json.load(f)
    return None


def _base_code(elemento_id: str) -> str:
    """'V330_A' -> 'V330'; 'V330' -> 'V330'."""
    return elemento_id.split('_')[0] if '_' in elemento_id else elemento_id

def _normalize_name(name: str) -> str:
    return re.sub(r'[-/\s]+', '-', name.strip())

def _elem_codes(text: str):
    matches = _ELEM_CODE_RE.findall(text.upper())
    res = []
    for m in matches:
        norm = _normalize_name(m)
        res.append(norm)
        # Se for um nome composto (ex: V1-V2), também adicionamos as partes soltas (V1, V2)
        if '-' in norm:
            res.extend(norm.split('-'))
    return res


def _poly_bboxes(msp):
    """Retorna lista de (x_min,x_max,y_min,y_max,vertices) de LWPOLYLINE/POLYLINE na layer Paineis."""
    out = []
    for e in msp:
        t = e.dxftype()
        try:
            layer = e.dxf.layer
        except Exception:
            continue
        if 'PAIN' not in layer.upper():
            continue
        try:
            if t == 'LWPOLYLINE':
                pts = list(e.get_points())
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                out.append((min(xs), max(xs), min(ys), max(ys), [(pt[0], pt[1]) for pt in pts]))
            elif t == 'POLYLINE':
                verts = [v.dxf.location for v in e.vertices]
                if not verts:
                    continue
                xs = [v.x for v in verts]
                ys = [v.y for v in verts]
                out.append((min(xs), max(xs), min(ys), max(ys), [(v.x, v.y) for v in verts]))
        except Exception:
            continue
            
    # Assembling loose lines into closed polygons
    lines = []
    for e in msp:
        if e.dxftype() == 'LINE':
            try:
                if 'PAIN' in e.dxf.layer.upper():
                    s = (round(e.dxf.start.x, 1), round(e.dxf.start.y, 1))
                    end = (round(e.dxf.end.x, 1), round(e.dxf.end.y, 1))
                    if s != end:
                        lines.append((s, end))
            except Exception:
                pass
                
    if lines:
        from collections import defaultdict
        adj = defaultdict(list)
        for s, e in lines:
            adj[s].append((e, frozenset((s, e))))
            adj[e].append((s, frozenset((s, e))))
            
        visited_edges = set()
        for start_node in adj:
            for next_node, edge in adj[start_node]:
                if edge in visited_edges:
                    continue
                path_pts = [start_node]
                curr, curr_edge = next_node, edge
                visited_in_path = {curr_edge}
                
                while True:
                    path_pts.append(curr)
                    if curr == start_node:
                        break # Fechou o loop!
                        
                    next_edges = [e for e in adj[curr] if e[1] not in visited_in_path]
                    if not next_edges:
                        break # Dead end
                    
                    nxt, nxt_edge = next_edges[0]
                    curr, curr_edge = nxt, nxt_edge
                    visited_in_path.add(curr_edge)
                    
                if path_pts[0] == path_pts[-1] and len(path_pts) > 3:
                    xs = [p[0] for p in path_pts]
                    ys = [p[1] for p in path_pts]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    # Filtra caixas muito pequenas (provavelmente cotas)
                    if max_x - min_x >= 10 and max_y - min_y >= 10:
                        out.append((min_x, max_x, min_y, max_y, path_pts))
                    visited_edges.update(visited_in_path)
                    
    return out


def _loose_paineis_entities(msp):
    """Retorna lista de dicionários p/ LINE e TEXT soltos na layer Paineis (ex: chanfros em L)."""
    out = []
    for e in msp:
        t = e.dxftype()
        try:
            if 'PAIN' not in e.dxf.layer.upper():
                continue
            if t == 'LINE':
                out.append({
                    'type': 'LINE',
                    'x': min(e.dxf.start.x, e.dxf.end.x),
                    'start': {'x': round(e.dxf.start.x, 1), 'y': round(e.dxf.start.y, 1)},
                    'end': {'x': round(e.dxf.end.x, 1), 'y': round(e.dxf.end.y, 1)}
                })
            elif t == 'TEXT':
                out.append({
                    'type': 'TEXT',
                    'x': e.dxf.insert.x,
                    'text': e.dxf.text,
                    'insert': {'x': round(e.dxf.insert.x, 1), 'y': round(e.dxf.insert.y, 1)}
                })
        except Exception:
            continue
    return out
def _cota_vertical_lines(msp):
    """Retorna lista de (dy, x, y_min, y_max) de LINEs verticais na layer COTA — usado p/ b_fv."""
    out = []
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        try:
            if e.dxf.layer.upper() != 'COTA':
                continue
            s, end = e.dxf.start, e.dxf.end
            dx = abs(end.x - s.x)
            dy = abs(end.y - s.y)
            if dx > 0.5 or dy < 1.0:
                continue
            x = (s.x + end.x) / 2.0
            out.append((round(dy, 1), round(x, 1), min(s.y, end.y), max(s.y, end.y)))
        except Exception:
            continue
    return out


def _cota_texts(msp):
    out = []
    for e in msp:
        if e.dxftype() != 'TEXT':
            continue
        try:
            if e.dxf.layer.upper() != 'COTA':
                continue
            v = float(e.dxf.text.strip())
            out.append((v, e.dxf.insert.x, e.dxf.insert.y))
        except Exception:
            continue
    return out


def _nomenclatura_labels(msp):
    """Todas as labels da layer NOMENCLATURA: (texto, x, y)."""
    out = []
    for e in msp:
        if e.dxftype() != 'TEXT':
            continue
        try:
            if e.dxf.layer.upper() != 'NOMENCLATURA':
                continue
            out.append((e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y))
        except Exception:
            continue
    return out


def _row_polys_for_label(polys, nom_x, nom_y, noms, target):
    """Aplica o algoritmo nearest-label + gap contíguo (ver docstring do módulo)
    para UMA label/linha específica. Retorna lista de bboxes de polys incluídos
    (ordenada em x), ou None se a linha não tiver polys."""
    row_polys = [p for p in polys if p[2] - Y_TOL_ROW <= nom_y <= p[3] + Y_TOL_ROW]
    if not row_polys:
        return None
    row_polys = sorted(row_polys, key=lambda p: p[0])

    # poly de referência: contem nom_x (com folga), senão o mais proximo
    ref_idx = None
    for i, p in enumerate(row_polys):
        if p[0] - 5 <= nom_x <= p[1] + 5:
            ref_idx = i
            break
    if ref_idx is None:
        ref_idx = min(range(len(row_polys)),
                      key=lambda i: min(abs(row_polys[i][0] - nom_x), abs(row_polys[i][1] - nom_x)))

    # labels de outros elementos na mesma linha (boundary) — exclui qualquer
    # label que também pertença ao elemento-alvo (ex.: 'CONT. V301.C' não é
    # boundary para a própria label 'V301.C' da mesma linha).
    boundary = []
    for (txt, x, y) in noms:
        if abs(y - nom_y) > Y_TOL_ROW:
            continue
        codes = _elem_codes(txt)
        if target in codes:
            continue
        for code in codes:
            boundary.append((code, x))

    def passes(cx):
        d_own = abs(cx - nom_x)
        if not boundary:
            return True
        d_other = min(abs(cx - bx) for (_, bx) in boundary)
        return d_other >= d_own

    included = [ref_idx]
    i = ref_idx + 1
    while i < len(row_polys):
        gap = row_polys[i][0] - row_polys[included[-1]][1]
        cx = (row_polys[i][0] + row_polys[i][1]) / 2.0
        if gap <= GAP_PILAR_MIN or passes(cx):
            included.append(i)
            i += 1
        else:
            break
    i = ref_idx - 1
    while i >= 0:
        gap = row_polys[included[0]][0] - row_polys[i][1]
        cx = (row_polys[i][0] + row_polys[i][1]) / 2.0
        if gap <= GAP_PILAR_MIN or passes(cx):
            included.insert(0, i)
            i -= 1
        else:
            break

    included.sort()
    return [row_polys[i] for i in included]


def _calc_sarrafos(p_width, p_height, is_l_drop=False):
    """Descreve os sarrafos construtivos de um painel FV."""
    w = max(0.0, float(p_width or 0.0))
    h = max(0.0, float(p_height or 0.0))
    if is_l_drop:
        vertical = f"1x {w:g}x7"
        horizontal = f"2x {max(0.0, h - 7.0):g}x7"
    else:
        vertical = f"1x {h:g}x7"
        horizontal = f"2x {max(0.0, w - 7.0):g}x7"
    return {
        'padrao': {'vertical': vertical, 'horizontal': horizontal},
        'aberturas': [],
        'chanfros': [],
    }


def _segments_and_holes_for_row(final_polys, msp_texts, nom_y, b_fv_hint=None, loose_entities=None, visual_obstacles=None):
    """Agrupa polys de UMA linha em segmentos (gap<=GAP_PILAR_MIN funde; gap
    maior = pilar cruzado real, vira 'hole'). Retorna (segments, holes_raw,
    b_fv_poly, segments_rich) onde holes_raw é lista de (width, position_relative_a_essa_linha, gap_text)."""
    visual_obstacles = visual_obstacles or []
    heights = [round(p[3] - p[2], 1) for p in final_polys]
    from collections import Counter
    b_fv_poly = Counter(heights).most_common(1)[0][0] if heights else b_fv_hint
    loose_entities = loose_entities or []
    
    row_max_y = max(p[3] for p in final_polys) if final_polys else nom_y
    row_base_y = row_max_y - (b_fv_poly or 19.0)

    segments = []
    holes_raw = []
    segments_rich = []
    
    current_segment_polys = [final_polys[0]]
    cur_width = round(final_polys[0][1] - final_polys[0][0], 1)
    pos_accum = 0.0
    
    def _finalize_segment_rich(polys, seg_width, next_seg_x=float('inf')):
        panels_rich = []
        seg_max_x = max(p[1] for p in polys)
        seg_min_y = min(p[2] for p in polys)
        
        for i, p in enumerate(polys):
            cy = (p[2] + p[3]) / 2.0
            p_width = round(p[1] - p[0], 1)
            p_height = round(p[3] - p[2], 1)
            p_texts = [
                t[0] for t in msp_texts
                if t[3] == '5'
                and p[0] - 5 <= t[1] <= p[1] + 5
                and abs(t[2] - cy) < Y_TOL_ROW
            ]
            p_dict = {
                'width': p_width,
                'height': p_height,
                'is_L_drop': False,
                'texts': list(set(p_texts)),
                'sarrafos': _calc_sarrafos(p_width, p_height),
            }
            if len(p) > 4 and len(p[4]) >= 4:
                p_dict['vertices'] = [{'x': round(v[0] - p[0], 1), 'y': round(v[1] - row_base_y, 1)} for v in p[4]]
            
            # Extract sub-dimensions (tiers)
            cota_texts = []
            for t in msp_texts:
                if t[3] in ('COTA', '0', 'PAINIS', 'PAINÉIS') and p[0]-5 <= t[1] <= p[1]+5 and (p[2] - 150) <= t[2] <= (p[2] + 20):
                    try:
                        val = float(t[0].replace(',', '.'))
                        # Ignore heights or small texts. We want dimension lengths!
                        if val >= 20 and abs(val - (b_fv_poly or 19.0)) > 2:
                            cota_texts.append({'val': val, 'x': t[1], 'y': t[2]})
                    except ValueError:
                        pass
            if cota_texts:
                tiers_dict = {}
                for ct in cota_texts:
                    matched = False
                    for ty in tiers_dict:
                        if abs(ct['y'] - ty) < 8.0:
                            tiers_dict[ty].append(ct)
                            matched = True
                            break
                    if not matched:
                        tiers_dict[ct['y']] = [ct]
                
                sorted_y = sorted(tiers_dict.keys(), reverse=True)
                tiers = []
                for ty in sorted_y:
                    items = sorted(tiers_dict[ty], key=lambda x: x['x'])
                    t_vals = [i['val'] for i in items]
                    # Só incluir tier se sum(vals) ≈ largura do painel (±2cm)
                    if abs(sum(t_vals) - p_dict['width']) < 2.0:
                        tiers.append(t_vals)
                if len(tiers) > 1:
                    # Remove exact duplicates if any
                    unique_tiers = []
                    for t in tiers:
                        if t not in unique_tiers:
                            unique_tiers.append(t)
                    p_dict['tiers'] = unique_tiers

            # O painel principal sempre precede uma eventual queda em L.
            panels_rich.append(p_dict)

            # Attach loose entities (L-corners) to the last panel in the segment
            if i == len(polys) - 1:
                adjacent_loose = []
                for le in loose_entities:
                    if le['type'] == 'TEXT':
                        continue  # Ignora textos soltos (normalmente cotas)
                    
                    if le['type'] == 'LINE':
                        sy, ey = le['start']['y'], le['end']['y']
                        min_y, max_y = min(sy, ey), max(sy, ey)
                        # Garante que a linha pertença verticalmente a este painel (tol. 10cm)
                        if max_y < p[2] - 10 or min_y > p[3] + 10:
                            continue
                            
                        # Limit to right side of polygon, but absolutely DO NOT exceed next_seg_x
                        max_capture_x = min(p[1] + 100, next_seg_x - 5)
                        is_near_right = p[1] - 15 <= le['x'] <= max_capture_x
                        is_near_left = p[0] - 50 <= le['x'] <= p[0] + 15
                        if is_near_right or is_near_left:
                            if abs(le['start']['x'] - le['end']['x']) > 50:
                                continue
                            # Normalize relative to the panel's bottom-left
                            norm_le = dict(le)
                            if le['type'] == 'LINE':
                                norm_le['start'] = {'x': round(le['start']['x'] - p[0], 1), 'y': round(le['start']['y'] - row_base_y, 1)}
                                norm_le['end'] = {'x': round(le['end']['x'] - p[0], 1), 'y': round(le['end']['y'] - row_base_y, 1)}
                            elif le['type'] == 'TEXT':
                                norm_le['insert'] = {'x': round(le['insert']['x'] - p[0], 1), 'y': round(le['insert']['y'] - row_base_y, 1)}
                            adjacent_loose.append(norm_le)
                if adjacent_loose and 'vertices' not in p_dict:
                    p_dict['loose'] = adjacent_loose
                    line_entities = [
                        le for le in adjacent_loose if le.get('type') == 'LINE'
                    ]
                    max_loose_x = max(
                        [le['start']['x'] for le in line_entities]
                        + [le['end']['x'] for le in line_entities]
                        + [0.0]
                    )
                    if max_loose_x > p_dict['width']:
                        extra = round(max_loose_x - p_dict['width'], 1)
                        seg_width = round(seg_width + extra, 1)
                        loose_y = (
                            [le['start']['y'] for le in line_entities]
                            + [le['end']['y'] for le in line_entities]
                        )
                        drop_h = abs(min(loose_y)) if loose_y and min(loose_y) < 0 else 0.0
                        l_height = round(p_height + drop_h, 1)
                        panels_rich.append({
                            'width': extra,
                            'height': l_height,
                            'is_L_drop': True,
                            'texts': [],
                            'sarrafos': _calc_sarrafos(
                                extra, l_height, is_l_drop=True
                            ),
                        })

        # Detectar texto multiplicador "NX" (ex: "4X", "6X") no layer Painéis
        import re as _re_mult
        seg_min_x = min(p[0] for p in polys)
        seg_max_x = max(p[1] for p in polys)
        _mult = None
        for _t in msp_texts:
            if 'PAIN' in _t[3].upper() and seg_min_x - 5 <= _t[1] <= seg_max_x + 5:
                _m = _re_mult.match(r'^(\d+)[Xx]$', _t[0].strip())
                if _m:
                    _mult = int(_m.group(1))
                    break
        seg_dict = {'total_width': seg_width, 'panels': panels_rich}
        if _mult and _mult > 1:
            seg_dict['_multiplier'] = _mult
            
        # Labels de apoio ficam na faixa de cotas abaixo do fundo. Restringir
        # essa busca evita promover textos internos do painel a labels de borda.
        def is_edge_label(t):
            return row_base_y - 100 <= t[2] <= row_base_y + 1

        left_x = seg_min_x - 10
        right_x = seg_max_x + 10
        left_cands = [
            t for t in msp_texts
            if t[3] == '5' and abs(t[1] - left_x) < 50 and is_edge_label(t)
        ]
        right_cands = [
            t for t in msp_texts
            if t[3] == '5' and abs(t[1] - right_x) < 50 and is_edge_label(t)
        ]
        if left_cands:
            seg_dict['texto_esq'] = min(left_cands, key=lambda t: abs(t[1] - left_x))[0]
        if right_cands:
            seg_dict['texto_dir'] = min(right_cands, key=lambda t: abs(t[1] - right_x))[0]
            
        return seg_dict, seg_width

    for i in range(len(final_polys) - 1):
        prev = final_polys[i]
        cur = final_polys[i+1]
        gap = round(cur[0] - prev[1], 1)
        if gap > GAP_PILAR_MIN:
            # Check if gap is just a visual obstacle
            is_visual = False
            if visual_obstacles:
                gap_cx = (prev[1] + cur[0]) / 2.0
                gap_cy = (prev[2] + prev[3] + cur[2] + cur[3]) / 4.0
                for obs in visual_obstacles:
                    x0, y0, x1, y1 = obs['bbox']
                    # Apply a tolerance of 20 cm around the center of the gap
                    if (x0 - 20) <= gap_cx <= (x1 + 20) and (y0 - 20) <= gap_cy <= (y1 + 20):
                        is_visual = True
                        break

            if is_visual:
                cur_width = round(cur_width + gap + (cur[1] - cur[0]), 1)
                # Create a dummy poly for the gap so total_width perfectly matches panels sum
                dummy_poly = (prev[1], cur[0], prev[2], prev[3])
                current_segment_polys.append(dummy_poly)
                current_segment_polys.append(cur)
                continue

            # Finalize rich segment before adding to list (it might adjust cur_width)
            rich_seg, cur_width = _finalize_segment_rich(current_segment_polys, cur_width, cur[0])
            
            segments.append(cur_width)
            pos_accum += cur_width
            
            # Find gap text (crossing pillar)
            gap_x = (prev[1] + cur[0]) / 2.0
            near_texts = [t for t in msp_texts if abs(t[1] - gap_x) < 50 and -200 < (t[2] - nom_y) < Y_TOL_ROW]
            pillar_texts = [t[0] for t in near_texts if t[3] in ('5', 'NOMENCLATURA', 'COTA') and re.match(r'^[A-Z]+\d+', t[0])]
            gap_text = pillar_texts[0] if pillar_texts else None
            
            holes_raw.append((gap, round(pos_accum, 1), gap_text))
            pos_accum += gap
            
            segments_rich.append(rich_seg)
            
            cur_width = round(cur[1] - cur[0], 1)
            current_segment_polys = [cur]
        else:
            cur_width = round(cur_width + (cur[1] - cur[0]), 1)
            current_segment_polys.append(cur)
            
    rich_seg, cur_width = _finalize_segment_rich(current_segment_polys, cur_width, float('inf'))
    segments.append(cur_width)
    segments_rich.append(rich_seg)
    
    return segments, holes_raw, b_fv_poly, segments_rich


def _extract_fv_from_geometry(msp, elemento_id: str, visual_obstacles: list[dict] = None) -> dict | None:
    """Extração geométrica universal (ver docstring do módulo). Retorna None se
    não houver geometria suficiente (paineis/labels) — caller deve usar fallback.

    Suporta vigas desenhadas em MÚLTIPLAS LINHAS da folha STOG (NOMENCLATURA
    'V123.C' seguida de uma ou mais 'CONT. V123.C' — convenção STOG quando o
    elemento é longo demais para uma linha). Cada linha é resolvida pelo MESMO
    algoritmo nearest-label + gap contíguo (já validado para o caso de 1
    linha), depois as linhas são concatenadas em ordem (Y decrescente = topo
    da folha primeiro = início real do elemento) somando seus segmentos. A
    junção ENTRE linhas é tratada como contígua (gap=0) por padrão — não há
    coordenada X comparável entre linhas distintas da folha para detectar um
    pilar real nessa junção; só pilares DENTRO de uma mesma linha (gap em X
    real entre polys) entram como 'hole'.
    """
    polys = _poly_bboxes(msp)
    if not polys:
        return None

    target = _base_code(elemento_id).upper()
    target = _normalize_name(target)
    noms = _nomenclatura_labels(msp)

    own = [n for n in noms if target in _elem_codes(n[0])]
    if not own:
        return None

    # Múltiplas linhas (V123.C + CONT. V123.C ...): ordena por Y decrescente
    # (topo da folha = início do elemento, convenção STOG observada).
    own_rows = sorted(set((round(y, 1), round(x, 1)) for (_, x, y) in own),
                       key=lambda xy: -xy[0])

    all_segments = []
    all_holes_abs = []   # (width, position_absoluta, text)
    all_segments_rich = []
    b_fv_candidates = []
    n_polys_total = 0
    pos_offset = 0.0
    all_final_polys = []

    # Extract all texts once for fast searching
    msp_texts = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            try:
                msp_texts.append((e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y, e.dxf.layer.upper()))
            except Exception:
                pass

    # Extract all loose line/text entities from the panel layer
    loose_entities = _loose_paineis_entities(msp)

    for idx, (nom_y, nom_x) in enumerate(own_rows):
        final_polys = _row_polys_for_label(polys, nom_x, nom_y, noms, target)
        if not final_polys:
            continue
        all_final_polys.extend(final_polys)
        segs, holes_raw, b_fv_poly, segs_rich = _segments_and_holes_for_row(final_polys, msp_texts, nom_y, loose_entities=loose_entities, visual_obstacles=visual_obstacles)
        if b_fv_poly:
            b_fv_candidates.append(b_fv_poly)
        n_polys_total += len(final_polys)

        for (w, pos, txt) in holes_raw:
            all_holes_abs.append((w, round(pos_offset + pos, 1), txt))
        row_width = round(sum(segs), 1)

        # Junção com a linha anterior: contígua (funde no último segmento) —
        # Não fundir os segmentos entre fileiras! Em fundos em L (ex: V303), a
        # quebra de fileira representa o chanfro/esquina em L, e fundir os dois
        # braços do L destrói a medida real de cada braço (ex: soma 418+244 = 662).
        # Como não há pilar_gap detectado entre fileiras, eles ficarão contíguos
        # mas serão cotados separadamente, o que é o correto.
        if idx > 0 and segs_rich:
            segs_rich[0]['row_break'] = True
        all_segments.extend(segs)
        all_segments_rich.extend(segs_rich)

        pos_offset += row_width + sum(w for w, pos, txt in holes_raw)

    if not all_segments:
        return None

    from collections import Counter
    b_fv = Counter(b_fv_candidates).most_common(1)[0][0] if b_fv_candidates else None

    if all_final_polys:
        x_min = min(p[0] for p in all_final_polys)
        x_max = max(p[1] for p in all_final_polys)
        cy = sum(p[2]+p[3] for p in all_final_polys) / (2 * len(all_final_polys))
        Y_TOL_LABEL = 100.0
        # Textos plausíveis para as pontas (ignora a própria nomenclatura Vxxx.C)
        valid_texts = [t for t in msp_texts if abs(t[2] - cy) < Y_TOL_LABEL and t[3] in ('5', 'NOMENCLATURA') and (not target or target not in t[0])]
        
        # Filtra por proximidade do x_min e x_max (tolerância de 50cm para dentro ou para fora)
        X_TOL_END = 50.0
        left_texts = [t for t in valid_texts if abs(t[1] - x_min) < X_TOL_END]
        right_texts = [t for t in valid_texts if abs(t[1] - x_max) < X_TOL_END]
        
        label_left = min(left_texts, key=lambda t: abs(t[1] - x_min))[0] if left_texts else "L Esq"
        label_right = min(right_texts, key=lambda t: abs(t[1] - x_max))[0] if right_texts else "L Dir"
    else:
        label_left = "L Esq"
        label_right = "L Dir"
    
    if b_fv is None:
        vert_lines = _cota_vertical_lines(msp)
        vert_in_range = [v for v in vert_lines if B_FV_MIN <= v[0] <= B_FV_MAX]
        if vert_in_range:
            b_fv = min(v[0] for v in vert_in_range)
        else:
            texts = _cota_texts(msp)
            cand = [v for (v, tx, ty) in texts if B_FV_MIN <= v <= B_FV_MAX]
            b_fv = min(cand) if cand else 19.0

    panels = [{'width': w, 'height1': b_fv, 'height2': b_fv,
               'grade_h1': str(w), 'grade_h2': str(w)} for w in all_segments]

    holes = [{'active': True, 'width': w, 'height': b_fv or 0.0, 'position': pos, 'text': txt}
              for (w, pos, txt) in all_holes_abs]
    while len(holes) < 4:
        holes.append({'active': False, 'width': 0.0, 'height': 0.0, 'position': 0.0, 'text': None})

    comprimento = round(sum(all_segments), 1)

    return {
        'total_width': b_fv,
        'total_height': comprimento,
        'panels': panels,
        'segments_rich': all_segments_rich,
        'holes': holes,
        'pillar_left': {'active': False, 'width': 0.0, 'length': 0.0},
        'pillar_right': {'active': False, 'width': 0.0, 'length': 0.0},
        'label_left': label_left,
        'label_right': label_right,
        'sarrafo_left_id': 0,
        'sarrafo_right_id': 0,
        '_confianca_extracao': 0.9,
        '_n_pilar_gaps': len([h for h in holes if h.get('active')]),
        '_n_polys_atribuidos': n_polys_total,
        '_n_linhas_folha': len(own_rows),
    }


def _extract_fv_from_dxf_text_fallback(dxf_path: str) -> dict:
    """Fallback antigo: extração só por COTA TEXT, usado quando não há geometria
    de paineis/nomenclatura suficiente no recorte."""
    result = {'panels': [], 'holes': [], '_confianca_extracao': 0.4}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        cota_nums = []
        for e in msp:
            if e.dxftype() != 'TEXT':
                continue
            if e.dxf.layer.upper() != 'COTA':
                continue
            try:
                cota_nums.append(float(e.dxf.text.strip()))
            except Exception:
                pass
        panel_widths = sorted([v for v in cota_nums if 30 <= v <= 1500], reverse=True)
        w_candidates = [v for v in cota_nums if B_FV_MIN <= v <= B_FV_MAX]
        total_w = min(w_candidates) if w_candidates else 19.0
        result['total_width'] = total_w
        result['total_height'] = sum(panel_widths) if panel_widths else 0.0
        for w in (panel_widths[:8] if panel_widths else []):
            result['panels'].append({'width': w, 'height1': total_w, 'height2': total_w,
                                     'grade_h1': str(w), 'grade_h2': str(w)})
        result['holes'] = [{'active': False, 'width': 0.0, 'height': 0.0, 'position': 0.0}] * 4
        result['pillar_left'] = {'active': False, 'width': 0.0, 'length': 0.0}
        result['pillar_right'] = {'active': False, 'width': 0.0, 'length': 0.0}
        result['label_left'] = "L Esq"
        result['label_right'] = "L Dir"
        result['sarrafo_left_id'] = 0
        result['sarrafo_right_id'] = 0
        result['_confianca_extracao'] = 0.5 if panel_widths else 0.3
    except Exception as ex:
        result['_extracao_erro'] = str(ex)
        result['_confianca_extracao'] = 0.3
    return result


def _extract_fv_from_dxf(dxf_path: str, elemento_id: str = "V1", project_id: str = None) -> dict:
    """Extrai campos FV do DXF recorte: 1) geometria (paineis+nomenclatura), 2) fallback texto."""
    try:
        import ezdxf
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        visual_obstacles = _get_visual_obstacles(project_id)

        # 1) Tenta Extração Universal por Geometria
        geom_res = _extract_fv_from_geometry(msp, elemento_id, visual_obstacles)
        if geom_res is not None:
            return geom_res
    except Exception as ex:
        return {'panels': [], 'holes': [], '_confianca_extracao': 0.3, '_extracao_erro': str(ex)}
    return _extract_fv_from_dxf_text_fallback(dxf_path)


def extrair_ficha_fundo_viga(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
    project_id: str = None,
) -> dict:
    """Extrai a ficha N2 SEMPRE a partir da geometria do recorte aprovado.

    IMPORTANTE: Fase-4 (Structural Analyzer) NÃO é mais usada como fonte de
    panels/comprimento — está sistematicamente errada para FV (ex.: V330 SA diz
    comp=19cm, recorte real mostra 311cm). Fase-4 é mantida apenas como
    metadado auxiliar em '_fase4_ref' para referência/depuração, nunca
    sobrescrevendo os campos extraídos do DXF.
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name

    dxf_data = _extract_fv_from_dxf(recorte_path, elemento_id, project_id=project_id)
    dxf_conf = dxf_data.pop('_confianca_extracao', 0.4)
    dxf_data.pop('_extracao_erro', None)
    n_pilar_gaps = dxf_data.pop('_n_pilar_gaps', 0)
    n_polys = dxf_data.pop('_n_polys_atribuidos', 0)

    base_id = _base_code(elemento_id)
    elem_num = re.sub(r'[^\d]', '', base_id)
    result = {
        'number': elem_num, 'name': elemento_id, 'floor': 'Pavimento',
        **dxf_data,
    }
    result['_er_meta'] = {
        'source': 'dxf_geometry', 'dxf_path': str(recorte_path),
        'confianca': dxf_conf, 'n_pilar_gaps': n_pilar_gaps, 'n_polys_atribuidos': n_polys,
    }
    result['_confianca'] = dxf_conf

    # Fase-4 mantida só como referência auxiliar (nunca fonte de verdade)
    fase4 = _lookup_fase4_fv(elemento_id, obra_root_path) if obra_root_path else None
    if fase4:
        result['_fase4_ref'] = {k: v for k, v in fase4.items() if k != '_sa_meta'}

    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "V1"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_fundo_viga(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
