# -*- coding: utf-8 -*-
"""Motor Reverso LV — Extrai ficha N2 de recorte DXF STOG lateral viga.

Schema de saída (2 partes):
  VISÃO CORTE  → h_A/B, b_geom, h_section, laje_sup/inf por face, tipo_viga
  LATERAL A/B  → panels_A/B: lista de segmentos completos, cada um com:
                   largura_cm, panel_type (Sarrafeado|Grade|Misto),
                   height1 (h_body), grade_h1, laje_sup_local, laje_inf_local,
                   laje_central_alt, holes, is_first, is_last, codigos_forma

Estratégia de detecção de faces:
  1. Usa face labels ("V13.A", "V13.B") da camada "Texto Seção" / "5"
     para ancorar cada face — robusto contra múltiplas vigas por sheet.
  2. Encontra par de H-lines da camada Painéis (h_body 8-130 cm) abaixo
     de cada label e alinhado horizontalmente com o label.
     Confirmação por COTA TEXT para descartar pares espúrios de LWPOLYLINE.
  3. Extrai V-lines dentro do range xy da face → segmentos com largura.
  4. Classifica cada segmento: Grade (pares SARR_3.5x7 internos) vs Sarrafeado.
  5. Extrai grade_h de cada segmento Grade (span Y dos SARR_3.5x7).
  6. Detecta aberturas (LWPOLYLINE DASHED nos cantos) por segmento.
  7. Associa COTA TEXT próximos → h_total, laje_sup, laje_inf por face.
  8. Propaga laje_sup_local / laje_inf_local para cada segmento.
"""

from __future__ import annotations
from pathlib import Path
from collections import defaultdict, Counter
import json, re, unicodedata

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

# ── Tolerâncias geométricas ──────────────────────────────────────────────────
_EPS_LINE    = 0.5    # tolerância horizontal/vertical (cm)
_EPS_Y       = 1.0    # agrupar H-lines pelo mesmo y
_MIN_FACE_W  = 80     # largura mínima de H-line para ser borda de face (não VC)
_H_BODY_MIN  = 8      # h_body mínimo válido (cm)
_H_BODY_MAX  = 200    # h_body máximo válido (cm) — beams can reach 130–200cm in practice
_MIN_OVERLAP = 40     # sobreposição x mínima entre H-lines do mesmo par (cm)
_LABEL_Y_GAP = 120    # máximo de distância y abaixo do label para encontrar face (cm)
_LABEL_X_GAP = 80     # máximo de distância x entre label e face (cm)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

# Segmentos laterais curtos (por exemplo, retornos de 60 cm) tambem sao
# unidades validas. A atribuicao A/B continua restrita ao contexto dos labels.
_MIN_FACE_W = 40


def _layer_key(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', str(value))
    return normalized.encode('ascii', 'ignore').decode('ascii').upper()


def _infer_obra_root(recorte_path: str) -> Path | None:
    p = Path(recorte_path)
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx + 1])
    return None


def _lookup_fase4_lv(elem_id: str, obra_root: Path) -> dict | None:
    """Busca JSON_Vigas_Laterais/{elem_id}_A.json. Retorna dict ou None."""
    base = re.sub(r'_[AB]$', '', elem_id)
    for name in (elem_id, f"{base}_A", f"{base}_B", base):
        p = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / f"{name}.json"
        if p.exists():
            with open(p, encoding='utf-8') as f:
                return json.load(f)
    return None


def _collect_seg_line(layer: str, x1: float, y1: float, x2: float, y2: float,
                      paineis_h: list, paineis_v: list,
                      sarr_v: list, madeira_v: list,
                      sarr3_v: list | None = None) -> None:
    """Classifica um segmento de linha nas listas corretas.
    sarr3_v: recebe especificamente SARR_3.5x7 V-lines (grade pernas).
    """
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    if layer == 'Painéis':
        if dy < _EPS_LINE and dx > 5:
            paineis_h.append((min(y1, y2), min(x1, x2), max(x1, x2)))
        elif dx < _EPS_LINE and dy > 5:
            paineis_v.append((min(x1, x2), min(y1, y2), max(y1, y2)))
    elif layer in ('SARR_2.2x7', 'SARR_EDITAR', 'SARR_3.5x7'):
        if dx < _EPS_LINE and dy > 5:
            sarr_v.append((min(x1, x2), min(y1, y2), max(y1, y2)))
            if layer == 'SARR_3.5x7' and sarr3_v is not None:
                sarr3_v.append((min(x1, x2), min(y1, y2), max(y1, y2)))
    elif layer == 'Madeira':
        if dx < _EPS_LINE and dy > 5:
            madeira_v.append((min(x1, x2), min(y1, y2), max(y1, y2)))


# ──────────────────────────────────────────────────────────────────────────────
# Extração geométrica principal
# ──────────────────────────────────────────────────────────────────────────────

def _extract_lv_geom_from_dxf(dxf_path: str, elem_id: str = '') -> dict:
    """
    Extrai campos geométricos completos do recorte DXF N2 de uma lateral de viga.
    Usa face labels ("V13.A", "V13.B") para localizar cada face robustamente
    mesmo quando múltiplas vigas compartilham o mesmo sheet.

    Retorna dict com:
      h_A, h_B, b_geom, h_section,
      laje_sup_A, laje_inf_A, laje_sup_B, laje_inf_B,
      panels_A, panels_B, pillar_left, pillar_right, holes,
      _confianca_extracao
    """
    result: dict = {
        # Visão Corte
        'h_A': 0.0, 'h_B': 0.0,
        'b_geom': 19.0, 'h_section': 55.0,
        'laje_sup_A': 0.0, 'laje_inf_A': 0.0,
        'laje_sup_B': 0.0, 'laje_inf_B': 0.0,
        'tipo_viga': 'sarrafeada',
        # Múltiplas seções transversais (visões de corte por par A/B)
        'section_views': [],  # [{h_A, h_B, b, laje_sup_A, laje_inf_A, ...}]
        'face_units': [],     # [{label, side, h_total, panels, bbox}] por bloco visual
        # Lateral A/B (segmentos completos)
        'panels_A': [], 'panels_B': [],
        'pillar_left':  {'active': False, 'width': 0.0, 'length': 0.0},
        'pillar_right': {'active': False, 'width': 0.0, 'length': 0.0},
        'holes': [],
        # Campos de identificação e referência
        'continuation': '',    # 'Proxima Parte' se CONT. prefix no label
        'text_left':    '',    # pilar/referência à esquerda (P19, etc.)
        'text_right':   '',    # pilar/referência à direita
        '_confianca_extracao': 0.35,
    }

    # Prefixo do elemento para filtrar labels no sheet (ex: "V13", "VF203")
    elem_prefix = re.sub(r'_[AB]$', '', elem_id).upper()

    try:
        import ezdxf

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        paineis_h:    list = []   # (y, x_left, x_right)
        paineis_v:    list = []   # (x, y_bot, y_top)
        sarr_v:       list = []   # (x, y_bot, y_top)  todos sarrafos verticais
        sarr3_v:      list = []   # (x, y_bot, y_top)  SARR_3.5x7 V-lines (grade pernas)
        sarr_lines:   list = []   # (layer, xl, yb, xr, yt) linhas SARR reais
        madeira_v:    list = []   # (x, y_bot, y_top)
        holes_lwpoly: list = []   # (xl, yl, xr, yr) LWPOLYLINE DASHED = aberturas
        reap_boxes:   list = []   # (xl, yl, xr, yr) HATCH REAPROVEITAMENTO
        laje_boxes:   list = []   # (xl, yl, xr, yr) HATCH Hachura de laje/faixas
        cota_txts:    list = []   # (x, y, val)
        panel_num_txts: list = [] # (x, y, val) numeros desenhados na layer Paineis
        secao_txts:   list = []   # (x, y, val)  camada "Cota Seção (2x)"
        face_labels:  list = []   # (x, y, txt, side)  camada "Texto Seção" / "5"
        other_labels: list = []   # (x, y, txt)  pilar/viga refs da camada "5"
        pontalete_txts: list = [] # (x, y, count, txt, layer, color, height) textos "N 1/2pont"

        concrete_profiles: list = []
        concrete_lines: list = []

        for e in msp:
            layer = e.dxf.layer
            layer_key = _layer_key(layer)
            etype = e.dxftype()

            if etype == 'LINE':
                try:
                    p1, p2 = e.dxf.start, e.dxf.end
                    x1, y1 = float(p1[0]), float(p1[1])
                    x2, y2 = float(p2[0]), float(p2[1])
                    _collect_seg_line(layer, x1, y1, x2, y2,
                                      paineis_h, paineis_v, sarr_v, madeira_v, sarr3_v)
                    if layer in ('SARR_2.2x7', 'SARR_EDITAR', 'SARR_3.5x7'):
                        sarr_lines.append((
                            layer,
                            min(x1, x2), min(y1, y2),
                            max(x1, x2), max(y1, y2),
                        ))
                    if layer == 'CONCRETO':
                        concrete_lines.append(((x1, y1), (x2, y2)))
                except Exception:
                    pass

            elif etype == 'LWPOLYLINE':
                try:
                    pts = list(e.get_points('xy'))
                    n = len(pts)
                    if n == 2:
                        (x1, y1), (x2, y2) = pts[0], pts[1]
                        _collect_seg_line(layer, x1, y1, x2, y2,
                                          paineis_h, paineis_v, sarr_v, madeira_v, sarr3_v)
                    elif n >= 3:
                        closed = bool(e.closed)
                        limit = n if closed else n - 1
                        for i in range(limit):
                            x1, y1 = pts[i]
                            x2, y2 = pts[(i + 1) % n]
                            _collect_seg_line(layer, x1, y1, x2, y2,
                                              paineis_h, paineis_v, sarr_v, madeira_v, sarr3_v)
                        # LWPOLYLINE DASHED em Painéis = abertura/slot
                        if layer == 'Painéis' and n >= 3:
                            lt = str(e.dxf.get('linetype', '') or '').upper()
                            if 'DASHED' in lt or 'HIDDEN' in lt:
                                xs_p = [p[0] for p in pts]
                                ys_p = [p[1] for p in pts]
                                holes_lwpoly.append((
                                    min(xs_p), min(ys_p),
                                    max(xs_p), max(ys_p)
                                ))
                        if layer == 'CONCRETO':
                            concrete_profiles.append([
                                (float(x), float(y)) for x, y in pts
                            ])
                except Exception:
                    pass

            elif etype == 'POLYLINE':
                try:
                    pts = [
                        (float(v.dxf.location[0]), float(v.dxf.location[1]))
                        for v in e.vertices
                    ]
                    if layer == 'CONCRETO' and len(pts) >= 3:
                        concrete_profiles.append(pts)
                except Exception:
                    pass

            elif etype == 'TEXT':
                try:
                    txt = e.dxf.text.strip()
                    ix, iy = float(e.dxf.insert[0]), float(e.dxf.insert[1])
                    if layer == 'COTA':
                        val = float(txt)
                        cota_txts.append((ix, iy, val))
                    elif layer_key.startswith('PAINE'):
                        try:
                            panel_num_txts.append((ix, iy, float(txt)))
                        except Exception:
                            pass
                    elif layer_key.startswith('COTA SECAO'):
                        val = float(txt)
                        secao_txts.append((ix, iy, val))
                    elif layer in ('Texto Seção', '5', 'texto', 'NOMENCLATURA'):
                        tu = txt.strip().upper()
                        mpont = re.search(r'(\d+)\s*(?:1/2)?\s*PONT', tu)
                        if mpont:
                            pontalete_txts.append((
                                ix, iy, int(mpont.group(1)), txt.strip(),
                                layer,
                                int(e.dxf.get('color', 256) or 256),
                                float(e.dxf.get('height', 8.0) or 8.0),
                            ))
                        if re.search(r'\.[AB]$', tu):
                            side = 'A' if tu.endswith('.A') else 'B'
                            face_labels.append((ix, iy, txt.strip(), side))
                        elif re.match(r'^P\d', tu) or re.match(r'^VF?\d', tu):
                            # Pilar/viga labels (P19, VF203, etc.) — texto de referência
                            other_labels.append((ix, iy, txt.strip()))
                except Exception:
                    pass

            elif etype == 'HATCH':
                try:
                    layer_u = str(layer).upper()
                    if layer_u in ('REAPROVEITAMENTO', 'HACHURA'):
                        xs_h = []
                        ys_h = []
                        for path in e.paths:
                            verts = getattr(path, 'vertices', None)
                            if verts:
                                for v in verts:
                                    xs_h.append(float(v[0]))
                                    ys_h.append(float(v[1]))
                        if xs_h and ys_h:
                            box = (min(xs_h), min(ys_h), max(xs_h), max(ys_h))
                            if layer_u == 'REAPROVEITAMENTO':
                                reap_boxes.append(box)
                            elif layer_u == 'HACHURA':
                                laje_boxes.append(box)
                except Exception:
                    pass

        # ── 1. Catalogar H-lines largas (candidatos a bordas de faces) ──────────
        # Filtrar H-lines com largura > _MIN_FACE_W (excluir detalhes VC e pequenos)
        wide_h = [(y, xl, xr) for (y, xl, xr) in paineis_h if xr - xl > _MIN_FACE_W]

        # Agrupar por y (tolerância _EPS_Y) e criar representante por y-cluster
        y_groups: dict = defaultdict(list)
        for y, xl, xr in wide_h:
            y_key = round(y / _EPS_Y) * _EPS_Y
            y_groups[y_key].append((xl, xr))

        ys: list = []  # (y_repr, xl, xr, width)
        for y_k, spans in y_groups.items():
            spans_sorted = sorted(spans)
            merged: list = []
            cur_l, cur_r = spans_sorted[0]
            for xl, xr in spans_sorted[1:]:
                if xl <= cur_r + 5:
                    cur_r = max(cur_r, xr)
                else:
                    merged.append((cur_l, cur_r))
                    cur_l, cur_r = xl, xr
            merged.append((cur_l, cur_r))
            for xl_min, xr_max in merged:
                ys.append((y_k, xl_min, xr_max, xr_max - xl_min))
        ys.sort(key=lambda t: t[0], reverse=True)  # y decrescente

        # ── 2. Busca direta de face por label + confirmação por COTA ─────────
        #
        # Estratégia robusta: para cada face label, busca diretamente o par de
        # H-lines (y_top, y_bot) que satisfaz:
        #   • y_top ≤ label_y + 5  (face está abaixo/no nível do label)
        #   • label_x dentro do range x da face
        #   • h_body = y_top − y_bot ∈ [20, _H_BODY_MAX]
        #   • h_body aparece em COTA TEXT próximo ao lado direito da face
        #     (confirmação COTA descarta pares espúrios de LWPOLYLINE)
        # Se não houver confirmação COTA, usa o par com maior h_body dentro do range.

        def _find_pair_for_label(lx: float, ly: float) -> dict | None:
            """Par de H-lines para um face label.

            Estratégia 3-buckets para funcionar SEM layer COTA no DXF:

            1. cota_confirmed: COTA text confirma h_body (tol 0.6) → prioridade máxima.
            2. partial_floor : H-line parcial (ratio < 0.90) → borda de degrau interna.
                               Usa "minimum cover": iterando do menor para o maior h_body,
                               aceita apenas H-lines que cobrem x-zonas ainda descobertas
                               da face. O h_body mais profundo do cover é o correto.
                               Isso evita H-lines espúrias na mesma x-zona que dariam
                               h_body maior (ex.: 142 vs 109 para a mesma zona direita).
            3. full_floor    : H-line full-width (ratio ≥ 0.90) → fundo uniforme ou topo CONT.
                               Prefere o MENOR h_body para evitar cruzar para fileira CONT.

            Prioridade de retorno: cota_confirmed > partial_floor > full_floor.
            """
            tops = [
                (y, xl, xr) for y, xl, xr, w in ys
                if (ly - _LABEL_Y_GAP <= y <= ly + 5)
                and (xl - _LABEL_X_GAP <= lx <= xr + _LABEL_X_GAP)
            ]
            tops.sort(key=lambda t: abs(ly - t[0]))

            best_confirmed:  dict | None = None
            best_full_floor: dict | None = None
            cover_pair:      dict | None = None

            for y_top, xl_t, xr_t in tops:
                top_w = max(xr_t - xl_t, 1.0)

                # --- Minimum-cover para partial_floor ----------------------------
                # Ordena y_bot descendente (menor h_body primeiro) e constrói uma
                # cobertura incremental do range [xl_t, xr_t].  Para cada x-zona,
                # aceita apenas o primeiro candidato (o mais raso), descartando
                # H-lines espúrias mais profundas na mesma zona.
                covered_intervals: list = []   # [(xl, xr)] já cobertos
                cover_depth: float = 0.0       # profundidade máxima do cover

                for y_bot, xl_b, xr_b, w_b in sorted(
                        ys, key=lambda t: t[0], reverse=True):  # menor h primeiro
                    if y_bot >= y_top:
                        continue
                    h_body = y_top - y_bot
                    if not (20 < h_body < _H_BODY_MAX):
                        continue
                    x_ov = min(xr_t, xr_b) - max(xl_t, xl_b)
                    if x_ov < _MIN_OVERLAP:
                        continue
                    ratio = x_ov / top_w

                    x_right = max(xr_t, xr_b)
                    pair = {
                        'y_bot':   y_bot,   'y_top':   y_top,
                        'h_body':  round(h_body, 1),
                        'x_left':  min(xl_t, xl_b),
                        'x_right': x_right,
                        'total_w': round(x_right - min(xl_t, xl_b), 1),
                    }
                    allow_left_cota = lx < xl_t - 15.0
                    cota_near = [
                        v for cx, cy, v in cota_txts
                        if (
                            (x_right - 10 <= cx <= x_right + 160)
                            or (
                                allow_left_cota
                                and abs(cx - lx) <= 35.0
                                and cx <= xl_t + 10.0
                            )
                        )
                        and (y_bot - 40 <= cy <= y_top + 40)
                    ]
                    if any(abs(float(v) - h_body) <= 0.6 for v in cota_near):
                        if best_confirmed is None:
                            best_confirmed = pair
                        continue  # confirmado por COTA: não participa do cover

                    if ratio < 0.90:
                        # Candidato partial_floor: calcula nova cobertura
                        xl_c = max(xl_b, xl_t)
                        xr_c = min(xr_b, xr_t)
                        already_covered = sum(
                            max(0.0, min(xr_c, ci_xr) - max(xl_c, ci_xl))
                            for ci_xl, ci_xr in covered_intervals
                        )
                        new_cov = (xr_c - xl_c) - already_covered
                        if new_cov > 5.0:  # cobre ≥5cm de zona nova
                            covered_intervals.append((xl_c, xr_c))
                            if h_body > cover_depth:
                                cover_depth = h_body
                                cover_pair = pair
                    else:
                        # H-line full-width: fundo uniforme OU topo de CONT
                        if (best_full_floor is None
                                or h_body < best_full_floor['h_body']):
                            best_full_floor = pair

                if best_confirmed is not None:
                    break
                if cover_pair is not None:
                    break  # primeiro y_top válido vence (tops ordenados por prox. ao label)

            best_partial_floor = cover_pair
            return best_confirmed or best_partial_floor or best_full_floor

        # Pares fallback (sem label) — algoritmo guloso padrão
        all_pairs: list = []
        used: set = set()
        for i in range(len(ys)):
            if i in used:
                continue
            yi, xli, xri, wi = ys[i]
            for j in range(i + 1, len(ys)):
                if j in used:
                    continue
                yj, xlj, xrj, wj = ys[j]
                h_body = yi - yj
                if not (_H_BODY_MIN < h_body < _H_BODY_MAX):
                    continue
                x_ov = min(xri, xrj) - max(xli, xlj)
                if x_ov < _MIN_OVERLAP:
                    continue
                all_pairs.append({
                    'y_bot':   yj,   'y_top':  yi,
                    'h_body':  round(h_body, 1),
                    'x_left':  min(xli, xlj),
                    'x_right': max(xri, xrj),
                    'total_w': round(max(xri, xrj) - min(xli, xlj), 1),
                })
                used.add(i)
                used.add(j)
                break

        def _geometric_pair_candidates() -> list:
            """Pares de bordas horizontais que podem formar um segmento."""
            candidates = []
            seen = set()
            for i, (y_top, xl_t, xr_t, _wt) in enumerate(ys):
                for y_bot, xl_b, xr_b, _wb in ys[i + 1:]:
                    h_body = y_top - y_bot
                    if not (20 < h_body < _H_BODY_MAX):
                        continue
                    overlap = min(xr_t, xr_b) - max(xl_t, xl_b)
                    min_width = min(xr_t - xl_t, xr_b - xl_b)
                    if overlap < 20 or min_width <= 0:
                        continue
                    if overlap / min_width < 0.60:
                        continue
                    pair = {
                        'y_bot': y_bot,
                        'y_top': y_top,
                        'h_body': round(h_body, 1),
                        'x_left': min(xl_t, xl_b),
                        'x_right': max(xr_t, xr_b),
                        'total_w': round(
                            max(xr_t, xr_b) - min(xl_t, xl_b), 1),
                    }
                    key = (
                        round(pair['x_left'], 1),
                        round(pair['x_right'], 1),
                        round(pair['y_bot'], 1),
                        round(pair['y_top'], 1),
                    )
                    if key not in seen:
                        seen.add(key)
                        candidates.append(pair)
            return candidates

        geometric_pairs = _geometric_pair_candidates()

        def _row_pairs_for_anchor(anchor: dict) -> list:
            """Expande um label para desenhos independentes da mesma fileira."""
            row_y_tol = 8.0
            anchor_h = float(anchor.get('h_body', 0))
            anchor_left = float(anchor.get('x_left', 0))
            anchor_right = float(anchor.get('x_right', 0))
            row_candidates = [anchor]
            for pair in geometric_pairs:
                same_base = abs(pair['y_bot'] - anchor['y_bot']) <= row_y_tol
                same_top = abs(pair['y_top'] - anchor['y_top']) <= row_y_tol
                if not (same_base or same_top):
                    continue
                if abs(pair['h_body'] - anchor_h) > 25:
                    continue
                if anchor_h > 0 and pair['h_body'] < anchor_h * 0.55:
                    continue
                overlap_anchor = (
                    min(pair['x_right'], anchor_right)
                    - max(pair['x_left'], anchor_left)
                )
                if overlap_anchor > 0.60 * min(
                        pair['total_w'], anchor_right - anchor_left):
                    continue
                row_candidates.append(pair)

            # Candidatos repetidos podem usar bordas internas diferentes.
            # Agrupar por faixa X e manter a altura mais proxima do anchor.
            row_candidates.sort(key=lambda p: (
                p['x_left'], abs(p['h_body'] - anchor_h)))
            selected = []
            for pair in row_candidates:
                duplicate_idx = None
                for idx, current in enumerate(selected):
                    overlap = (
                        min(pair['x_right'], current['x_right'])
                        - max(pair['x_left'], current['x_left'])
                    )
                    min_w = min(pair['total_w'], current['total_w'])
                    if min_w > 0 and overlap / min_w > 0.70:
                        duplicate_idx = idx
                        break
                if duplicate_idx is None:
                    selected.append(pair)
                elif (
                    abs(pair['h_body'] - anchor_h)
                    < abs(selected[duplicate_idx]['h_body'] - anchor_h)
                ):
                    selected[duplicate_idx] = pair
            selected.sort(key=lambda p: p['x_left'])
            return selected

        def _infer_anchor_from_row(lx: float, ly: float) -> dict | None:
            """Infere segmento sem par completo usando uma borda e a fileira."""
            best = None
            best_score = None
            for pair in geometric_pairs:
                if not (ly - _LABEL_Y_GAP <= pair['y_top'] <= ly + 5):
                    continue
                for edge_y, edge_xl, edge_xr, _w in ys:
                    shares_row = (
                        abs(edge_y - pair['y_bot']) <= _EPS_Y
                        or abs(edge_y - pair['y_top']) <= _EPS_Y
                    )
                    if not shares_row:
                        continue
                    x_dist = (
                        edge_xl - lx if lx < edge_xl
                        else lx - edge_xr if lx > edge_xr
                        else 0.0
                    )
                    if x_dist > _LABEL_X_GAP:
                        continue
                    # Nao substituir pelo proprio par: este fallback existe
                    # para uma faixa X orfa na mesma base/topo.
                    overlap = (
                        min(edge_xr, pair['x_right'])
                        - max(edge_xl, pair['x_left'])
                    )
                    if overlap > 0.60 * min(
                            edge_xr - edge_xl, pair['total_w']):
                        continue
                    score = abs(ly - pair['y_top']) + x_dist
                    if best_score is None or score < best_score:
                        best_score = score
                        best = {
                            'y_bot': pair['y_bot'],
                            'y_top': pair['y_top'],
                            'h_body': pair['h_body'],
                            'x_left': edge_xl,
                            'x_right': edge_xr,
                            'total_w': round(edge_xr - edge_xl, 1),
                        }
            return best

        # Filtrar labels do elemento atual (elem_prefix = "V13", etc.)
        my_labels = [(lx, ly, txt, side) for lx, ly, txt, side in face_labels
                     if txt.upper().startswith(elem_prefix + '.')]

        face_A: dict | None = None
        face_B: dict | None = None

        found_by_label = False
        if my_labels:
            print(f"DEBUG {elem_prefix}: my_labels = {my_labels}")
            for lx, ly, txt, side in my_labels:
                pair = _find_pair_for_label(lx, ly)
                print(f"DEBUG {elem_prefix}: label {txt} at ({lx}, {ly}) -> pair = {pair}")
                if side == 'A' and pair:
                    face_A = pair
                    found_by_label = True
                elif side == 'B' and pair:
                    face_B = pair
                    found_by_label = True

        print(f"DEBUG {elem_prefix}: face_A = {face_A}")
        print(f"DEBUG {elem_prefix}: face_B = {face_B}")

        # Fallback: sem labels — usar pares com mesmo x_left (mesma coluna de desenho)
        if face_A is None and face_B is None and all_pairs:
            # Agrupar pares por x_left (±20 cm)
            x_groups: dict = defaultdict(list)
            for pair in all_pairs:
                xk = round(pair['x_left'] / 20) * 20
                x_groups[xk].append(pair)
            # Coluna com mais pares (faces)
            best_col = max(x_groups.values(), key=len)
            best_col.sort(key=lambda p: p['y_top'], reverse=True)
            if len(best_col) >= 2:
                face_A = best_col[0]
                face_B = best_col[1]
            elif len(best_col) == 1:
                face_A = best_col[0]
                face_B = best_col[0]

        if face_A is None and face_B is None:
            result['_confianca_extracao'] = 0.3
            if not secao_txts:
                return result

        # Garantir que A é a face mais alta — só no fallback (sem labels).
        # Quando labels identificaram as faces explicitamente, respeitar a identidade.
        if not found_by_label and face_A and face_B and face_A['y_top'] < face_B['y_top']:
            face_A, face_B = face_B, face_A

        # ── 2b. Continuação e labels de pilar ─────────────────────────────────
        # continuation: True se algum face_label tem prefixo "CONT." + contém elem_prefix
        is_continuation = any(
            'CONT.' in txt.strip().upper() and elem_prefix in txt.strip().upper()
            for _, _, txt, _ in face_labels
        )
        result['continuation'] = 'Proxima Parte' if is_continuation else ''

        # text_left / text_right: pilar mais próximo da borda esquerda/direita da face
        if face_A and other_labels:
            x_left  = face_A['x_left']
            x_right = face_A['x_right']
            y_range = (face_A['y_bot'] - 30, face_A['y_top'] + 30)
            nearby  = [(x, y, t) for x, y, t in other_labels
                       if y_range[0] <= y <= y_range[1]]
            if nearby:
                left_cands  = sorted([(abs(x - x_left), t) for x, y, t in nearby])
                right_cands = sorted([(abs(x - x_right), t) for x, y, t in nearby])
                result['text_left']  = left_cands[0][1]  if left_cands  else ''
                result['text_right'] = right_cands[0][1] if right_cands else ''

        # ── 3. Segmentos completos por face ───────────────────────────────────
        # Constantes para classificação
        _GRADE_PAIR_SEP_MAX = 10.0   # separação máx entre duas pernas de um par (cm)
        _GRADE_FACE_MARGIN  = 30.0   # margem das bordas externas da face a ignorar
        _GRADE_SEG_MARGIN   = 15.0   # extensão lateral para buscar pernas num segmento

        def _face_is_grade(x_left: float, x_right: float,
                            y_bot: float, y_top: float) -> bool:
            """True se a face tem pares SARR_3.5x7 (grade pernas) dentro do range.

            As pernas de grade no STOG humano ficam nas BORDAS dos segmentos
            (junto às V-lines do Painéis), não no interior. Por isso classifica-se
            a FACE inteira como Grade/Sarrafeado.

            Nota: y_top é o topo das H-lines (h_body), mas pernas SARR_3.5x7 em
            vigas grade podem se estender até h_total (acima do y_top das H-lines).
            Usamos y_top + 150 como limite superior generoso.
            """
            inner_l = x_left + _GRADE_FACE_MARGIN
            inner_r = x_right - _GRADE_FACE_MARGIN
            # Range Y generoso: pernas podem ir além do y_top das H-lines (h_body)
            y_lo = y_bot - 20
            y_hi = y_top + 150
            xs_inner = sorted(
                x for x, yb, yt in sarr3_v
                if inner_l <= x <= inner_r
                and y_lo <= yb and yt <= y_hi
            )
            for i in range(len(xs_inner) - 1):
                if xs_inner[i + 1] - xs_inner[i] <= _GRADE_PAIR_SEP_MAX:
                    return True
            return False

        def _extract_grade_h(xl: float, xr: float,
                              y_bot: float, y_top: float) -> float:
            """Grade height para este segmento: span Y das pernas SARR_3.5x7 próximas."""
            # Margem X: 15cm (pernas ficam nas bordas dos segmentos)
            # Margem Y: 150cm acima do y_top para cobrir a altura total da forma
            spans = [(yb, yt) for x, yb, yt in sarr3_v
                     if xl - _GRADE_SEG_MARGIN <= x <= xr + _GRADE_SEG_MARGIN
                     and y_bot - 20 <= yb and yt <= y_top + 150]
            if not spans:
                return 0.0
            return round(max(yt for _, yt in spans) - min(yb for yb, _ in spans), 1)

        def _detect_holes_seg(xl: float, xr: float,
                               y_bot: float, y_top: float) -> list:
            """Aberturas LWPOLYLINE DASHED nos cantos do segmento."""
            result_h = []
            for hxl, hyl, hxr, hyr in holes_lwpoly:
                hw, hh = hxr - hxl, hyr - hyl
                if hw <= 0 or hh <= 0:
                    continue
                cx = (hxl + hxr) / 2
                if not (xl - 5 <= cx <= xr + 5):
                    continue
                cy = (hyl + hyr) / 2
                if not (y_bot - 5 <= cy <= y_top + 5):
                    continue
                near_l  = (hxl - xl) < 12
                near_r  = (xr - hxr) < 12
                near_top = (y_top - hyr) < 12
                near_bot = (hyl - y_bot) < 12
                corner = None
                if near_l and near_top:   corner = 'TL'
                elif near_r and near_top: corner = 'TR'
                elif near_l and near_bot: corner = 'BL'
                elif near_r and near_bot: corner = 'BR'
                if corner:
                    pos = (y_top - hyr) if 'T' in corner else (hyl - y_bot)
                    result_h.append({
                        'active':   True,
                        'corner':   corner,
                        'width':    round(hw, 1),
                        'height':   round(hh, 1),
                        'position': round(max(pos, 0), 1),
                    })
            return result_h

        def _seg_actual_height(xl: float, xr: float,
                               y_bot: float, y_top: float,
                               h_body: float) -> float:
            """Detecta H-line interna que limita a altura REAL deste segmento.

            Em vigas com degrau (ex.: V301.A P1=44cm vs P2=109cm) existe
            uma H-line de Painéis em y_top-h1 que abrange o painel baixo mas
            não o painel alto. Retorna h1 real se encontrada, senão h_body.
            Condição: h_line interna deve abranger >= 55% do X do segmento
            e estar pelo menos 5 cm acima de y_bot e abaixo de y_top.
            """
            seg_w = xr - xl
            if seg_w < 1.0:
                return h_body
            inner_hs = [
                y for y, xl_h, xr_h in paineis_h
                if y_bot + 5.0 < y < y_top - 5.0
                and (min(xr_h, xr) - max(xl_h, xl)) > seg_w * 0.55
            ]
            if not inner_hs:
                return h_body
            # H-line mais alta (mais próxima do topo) delimita o fundo do painel baixo
            y_inner = float(max(inner_hs))
            h_computed = round(float(y_top) - y_inner, 1)
            if 5.0 < h_computed < h_body - 5.0:
                return h_computed
            return h_body

        def _reuse_regions_seg(xl: float, xr: float,
                               y_bot: float, y_top: float) -> list:
            """Retorna faixas de reaproveitamento recortadas no corpo do segmento."""
            seg_area = max((xr - xl) * (y_top - y_bot), 1.0)
            regions = []
            for hxl, hyl, hxr, hyr in reap_boxes:
                ix1, ix2 = max(xl, hxl), min(xr, hxr)
                iy1, iy2 = max(y_bot, hyl), min(y_top, hyr)
                ox = ix2 - ix1
                oy = iy2 - iy1
                if ox <= 0.5 or oy <= 0.5:
                    continue
                overlap_ratio = (ox * oy) / seg_area
                width_ratio = ox / max(xr - xl, 1.0)
                if overlap_ratio < 0.05 and width_ratio < 0.60:
                    continue
                regions.append({
                    'x_offset': round(ix1 - xl, 1),
                    'y_offset': round(iy1 - y_bot, 1),
                    'width': round(ox, 1),
                    'height': round(oy, 1),
                })
            return regions

        def _panel_segments(fg: dict) -> list:
            """Extrai lista de segmentos completos da face com classificação."""
            y_bot, y_top = fg['y_bot'], fg['y_top']
            x_left, x_right = fg['x_left'], fg['x_right']
            h_body = fg['h_body']

            # Classificação da face inteira (grade pernas ficam nas bordas de segmento)
            face_grade = _face_is_grade(x_left, x_right, y_bot, y_top)
            ptype_face = 'Grade' if face_grade else 'Sarrafeado'

            xs = [
                x for x, yb, yt in paineis_v
                if (x_left - 2 <= x <= x_right + 2)
                and not (yt < y_bot - 2 or yb > y_top + 2)
            ]
            xs.sort()
            deduped: list = []
            for x in xs:
                if not deduped or abs(x - deduped[-1]) > 1.0:
                    deduped.append(x)

            if len(deduped) < 2:
                gh = _extract_grade_h(x_left, x_right, y_bot, y_top) if face_grade else 0.0
                h_seg = _seg_actual_height(x_left, x_right, y_bot, y_top, h_body)
                return [_make_seg(x_left, x_right, y_bot, y_top,
                                  h_seg, ptype_face, gh,
                                  is_first=True, is_last=True)]

            segs: list = []
            n = len(deduped)
            # Recalcular is_last corretamente com filtragem de w > 5
            valid_ks = [k for k in range(n - 1)
                        if round(deduped[k + 1] - deduped[k], 1) > 5]
            for idx, k in enumerate(valid_ks):
                xl, xr = deduped[k], deduped[k + 1]
                gh = _extract_grade_h(xl, xr, y_bot, y_top) if face_grade else 0.0
                h_seg = _seg_actual_height(xl, xr, y_bot, y_top, h_body)
                segs.append(_make_seg(xl, xr, y_bot, y_top,
                                      h_seg, ptype_face, gh,
                                      is_first=(idx == 0),
                                      is_last=(idx == len(valid_ks) - 1)))
            return segs

        def _make_seg(xl: float, xr: float, y_bot: float, y_top: float,
                      h_body: float,
                      ptype: str, gh: float,
                      is_first: bool, is_last: bool) -> dict:
            """Constrói o dict canônico de um segmento (campos do gerador)."""
            w = round(xr - xl, 1)
            holes = _detect_holes_seg(xl, xr, y_bot, y_top)
            reuse_regions = _reuse_regions_seg(xl, xr, y_bot, y_top)
            return {
                'largura_cm':     w,
                'width':          w,          # backward compat com gerador
                'panel_type':     ptype,
                'height1':        h_body if ptype == 'Sarrafeado' else 0.0,
                'height2':        0.0,
                'grade_h1':       gh,
                'grade_h2':       0.0,
                'laje_central_alt': 0.0,
                'laje_sup_local': 0.0,        # preenchido por _per_seg_slab
                'laje_inf_local': 0.0,
                'slab_top':       0.0,        # alias robot-schema
                'slab_bottom':    0.0,
                'slab_center':    0.0,
                'is_first':       is_first,
                'is_last':        is_last,
                'holes':          holes,
                'reuse':          bool(reuse_regions),
                'reuse_regions':  reuse_regions,
                'codigos_forma':  [],
                '_xl':            xl,         # guardado para per-seg slab lookup
                '_xr':            xr,
            }

        panels_A = _panel_segments(face_A) if face_A else []
        panels_B = _panel_segments(face_B) if face_B else []

        def _extract_section_views_local() -> list:
            """Detecta e interpreta cada visao de corte por cluster espacial."""
            if not secao_txts:
                return []

            small_points = sorted(
                [p for p in secao_txts if 5 <= p[2] <= 30],
                key=lambda p: (-p[1], p[0]),
            )
            large_points = [p for p in secao_txts if p[2] > 30]
            clusters = []
            used_large = set()
            for small_point in small_points:
                sx, sy, _sv = small_point
                candidates = [
                    (idx, point) for idx, point in enumerate(large_points)
                    if idx not in used_large
                    and abs(point[0] - sx) <= 90
                    and 0 < point[1] - sy <= 230
                ]
                if not candidates:
                    continue
                best_idx, best_large = min(
                    candidates,
                    key=lambda item: (
                        abs(item[1][0] - sx)
                        + abs(item[1][1] - sy)
                    ),
                )
                used_large.add(best_idx)
                clusters.append([small_point, best_large])

            cluster_centers = [
                (
                    sum(p[0] for p in cluster) / len(cluster),
                    sum(p[1] for p in cluster) / len(cluster),
                )
                for cluster in clusters
            ]
            views = []
            for cluster_idx, cluster in enumerate(clusters):
                values = [float(p[2]) for p in cluster if p[2] > 0]
                small = [v for v in values if 5 <= v <= 30]
                large = [v for v in values if v > 30]
                if not small or not large:
                    continue

                b = min(small)
                h_section = max(large)
                cx = sum(p[0] for p in cluster) / len(cluster)
                cy = sum(p[1] for p in cluster) / len(cluster)
                nearby = [
                    (x, y, float(v)) for x, y, v in cota_txts
                    if abs(x - cx) <= 155 and abs(y - cy) <= 175
                    and min(
                        range(len(cluster_centers)),
                        key=lambda idx: (
                            (x - cluster_centers[idx][0]) ** 2
                            + (y - cluster_centers[idx][1]) ** 2
                        ),
                    ) == cluster_idx
                ]
                total_candidates = [
                    v for _x, _y, v in nearby
                    if h_section < v <= h_section + 20
                ]
                h_total = (
                    Counter(round(v, 1) for v in total_candidates)
                    .most_common(1)[0][0]
                    if total_candidates else h_section + 4.0
                )

                def _side_data(side: str) -> tuple[float, float]:
                    vals = [
                        (x, y, v) for x, y, v in nearby
                        if (x < cx - 25 if side == 'A' else x > cx + 25)
                    ]
                    slab_candidates = [
                        v for _x, y, v in vals
                        if y >= cy and 8 <= v <= 25
                    ]
                    slab = max(slab_candidates) if slab_candidates else 0.0
                    expected_body = h_total - slab if slab else h_section
                    body_candidates = [
                        v for _x, y, v in vals
                        if 25 < v < h_total
                        and abs(y - cy) <= 80
                        and abs(v - h_section) > 1
                    ]
                    body = (
                        min(body_candidates,
                            key=lambda v: abs(v - expected_body))
                        if body_candidates else 0.0
                    )
                    return float(body), float(slab)

                def _concrete_geometry() -> dict:
                    candidates = []
                    max_distance = max(150.0, h_section * 1.8)
                    for points in concrete_profiles:
                        xs = [point[0] for point in points]
                        ys = [point[1] for point in points]
                        pcx = (min(xs) + max(xs)) / 2.0
                        pcy = (min(ys) + max(ys)) / 2.0
                        distance = ((pcx - cx) ** 2 + (pcy - cy) ** 2) ** 0.5
                        if distance <= max_distance:
                            candidates.append((distance, points))
                    if not candidates:
                        return {}

                    candidates.sort(key=lambda item: item[0])
                    nearest = candidates[0][0]
                    selected = [
                        points for distance, points in candidates
                        if distance <= nearest + 65.0
                    ]
                    all_points = [point for points in selected for point in points]

                    def _visual_primitives() -> list:
                        allowed_layers = {
                            'CONCRETO', 'Painéis', 'Madeira', 'Hachura',
                            'SARR_3.5x7', 'COTA', 'Cota Seção (2x)',
                            'detalhes',
                        }
                        core_x_min = min(point[0] for point in all_points)
                        core_x_max = max(point[0] for point in all_points)
                        core_y_min = min(point[1] for point in all_points)
                        core_y_max = max(point[1] for point in all_points)

                        def _inside_bounds(
                            x_min: float,
                            y_min: float,
                            x_max: float,
                            y_max: float,
                            layer: str,
                        ) -> bool:
                            margin_x = 85.0 if layer in {
                                'COTA', 'Cota Seção (2x)'
                            } else 38.0
                            margin_y = 70.0 if layer in {
                                'COTA', 'Cota Seção (2x)'
                            } else 38.0
                            return not (
                                x_max < core_x_min - margin_x
                                or x_min > core_x_max + margin_x
                                or y_max < core_y_min - margin_y
                                or y_min > core_y_max + margin_y
                            )

                        def _rel(point) -> list:
                            return [
                                round(float(point[0]) - cx, 3),
                                round(float(point[1]) - cy, 3),
                            ]

                        primitives = []
                        for entity in msp:
                            layer = str(entity.dxf.layer)
                            if layer not in allowed_layers:
                                continue
                            etype = entity.dxftype()
                            primitive = None
                            try:
                                if etype == 'LINE':
                                    points = [
                                        entity.dxf.start,
                                        entity.dxf.end,
                                    ]
                                    xs = [float(point[0]) for point in points]
                                    ys = [float(point[1]) for point in points]
                                    if _inside_bounds(
                                        min(xs), min(ys), max(xs), max(ys),
                                        layer,
                                    ):
                                        primitive = {
                                            'kind': 'line',
                                            'layer': layer,
                                            'points': [_rel(point) for point in points],
                                        }
                                elif etype in ('LWPOLYLINE', 'POLYLINE'):
                                    if etype == 'LWPOLYLINE':
                                        points = list(entity.get_points('xy'))
                                        closed = bool(entity.closed)
                                    else:
                                        points = [
                                            (
                                                float(vertex.dxf.location[0]),
                                                float(vertex.dxf.location[1]),
                                            )
                                            for vertex in entity.vertices
                                        ]
                                        closed = bool(entity.is_closed)
                                    if len(points) >= 2:
                                        xs = [float(point[0]) for point in points]
                                        ys = [float(point[1]) for point in points]
                                        if _inside_bounds(
                                            min(xs), min(ys), max(xs), max(ys),
                                            layer,
                                        ):
                                            primitive = {
                                                'kind': 'polyline',
                                                'layer': layer,
                                                'closed': closed,
                                                'points': [
                                                    _rel(point) for point in points
                                                ],
                                            }
                                elif etype == 'TEXT':
                                    insert = entity.dxf.insert
                                    x = float(insert[0])
                                    y = float(insert[1])
                                    if _inside_bounds(x, y, x, y, layer):
                                        primitive = {
                                            'kind': 'text',
                                            'layer': layer,
                                            'text': str(entity.dxf.text),
                                            'insert': _rel(insert),
                                            'align_point': _rel(
                                                entity.dxf.get(
                                                    'align_point', insert
                                                ) or insert
                                            ),
                                            'height': round(float(
                                                entity.dxf.get(
                                                    'height', 7.0
                                                ) or 7.0
                                            ), 3),
                                            'rotation': round(float(
                                                entity.dxf.get(
                                                    'rotation', 0.0
                                                ) or 0.0
                                            ), 3),
                                            'halign': int(entity.dxf.get(
                                                'halign', 0
                                            ) or 0),
                                            'valign': int(entity.dxf.get(
                                                'valign', 0
                                            ) or 0),
                                        }
                                elif etype == 'HATCH':
                                    paths = []
                                    for path in entity.paths:
                                        vertices = getattr(
                                            path, 'vertices', None
                                        )
                                        if not vertices:
                                            continue
                                        points = [
                                            (float(v[0]), float(v[1]))
                                            for v in vertices
                                        ]
                                        if len(points) >= 3:
                                            paths.append(points)
                                    if paths:
                                        xs = [
                                            point[0] for path in paths
                                            for point in path
                                        ]
                                        ys = [
                                            point[1] for path in paths
                                            for point in path
                                        ]
                                        if _inside_bounds(
                                            min(xs), min(ys), max(xs), max(ys),
                                            layer,
                                        ):
                                            primitive = {
                                                'kind': 'hatch',
                                                'layer': layer,
                                                'paths': [
                                                    [
                                                        _rel(point)
                                                        for point in path
                                                    ]
                                                    for path in paths
                                                ],
                                                'pattern': str(
                                                    entity.dxf.get(
                                                        'pattern_name',
                                                        'ANSI31',
                                                    ) or 'ANSI31'
                                                ),
                                                'scale': round(float(
                                                    entity.dxf.get(
                                                        'pattern_scale', 1.0
                                                    ) or 1.0
                                                ), 4),
                                                'angle': round(float(
                                                    entity.dxf.get(
                                                        'pattern_angle', 0.0
                                                    ) or 0.0
                                                ), 4),
                                                'solid': bool(
                                                    entity.dxf.get(
                                                        'solid_fill', 0
                                                    )
                                                ),
                                            }
                            except Exception:
                                primitive = None
                            if primitive is not None:
                                primitive['color'] = int(entity.dxf.get(
                                    'color', 256
                                ) or 256)
                                primitive['linetype'] = str(entity.dxf.get(
                                    'linetype', 'BYLAYER'
                                ) or 'BYLAYER')
                                primitives.append(primitive)
                        return primitives

                    verticals = []
                    for points in selected:
                        loop = points + [points[0]]
                        for p1, p2 in zip(loop, loop[1:]):
                            if abs(p1[0] - p2[0]) <= 0.5:
                                length = abs(p1[1] - p2[1])
                                if length >= max(25.0, h_section):
                                    verticals.append((p1[0], length))

                    body_left = body_right = None
                    expected_span = max(2.0 * b, 1.0)
                    unique_x = sorted({round(x, 3) for x, _length in verticals})
                    pairs = [
                        (left, right) for pos, left in enumerate(unique_x)
                        for right in unique_x[pos + 1:]
                    ]
                    if pairs:
                        body_left, body_right = min(
                            pairs,
                            key=lambda pair: (
                                abs((pair[1] - pair[0]) - expected_span)
                                + abs(((pair[0] + pair[1]) / 2.0) - cx) * 0.2
                            ),
                        )

                    min_x = min(point[0] for point in all_points)
                    max_x = max(point[0] for point in all_points)
                    extension_left = (
                        max(0.0, (body_left - min_x) / 2.0)
                        if body_left is not None else 0.0
                    )
                    extension_right = (
                        max(0.0, (max_x - body_right) / 2.0)
                        if body_right is not None else 0.0
                    )
                    has_left = extension_left >= 3.0
                    has_right = extension_right >= 3.0
                    topology = (
                        'bilateral' if has_left and has_right
                        else 'extension_left' if has_left
                        else 'extension_right' if has_right
                        else 'u_straight'
                    )

                    nearby_lines = []
                    for p1, p2 in concrete_lines:
                        mx = (p1[0] + p2[0]) / 2.0
                        my = (p1[1] + p2[1]) / 2.0
                        if abs(mx - cx) <= 90 and abs(my - cy) <= max_distance:
                            nearby_lines.append([
                                [round(p1[0] - cx, 2), round(p1[1] - cy, 2)],
                                [round(p2[0] - cx, 2), round(p2[1] - cy, 2)],
                            ])
                    if any(
                        abs(line[0][1] - line[1][1]) <= 0.5
                        and abs(line[1][0] - line[0][0]) > expected_span * 1.8
                        for line in nearby_lines
                    ):
                        topology = f'{topology}_wide_bottom'

                    return {
                        'topology': topology,
                        'extension_left_cm': round(extension_left, 1),
                        'extension_right_cm': round(extension_right, 1),
                        'body_width_cm': round(
                            (body_right - body_left) / 2.0, 1
                        ) if body_left is not None else float(b),
                        'profiles': [
                            [
                                [round(x - cx, 2), round(y - cy, 2)]
                                for x, y in points
                            ]
                            for points in selected
                        ],
                        'segments': nearby_lines,
                        'visual_primitives': _visual_primitives(),
                        'source': 'concrete_layer_geometry',
                    }

                body_a, slab_a = _side_data('A')
                body_b, slab_b = _side_data('B')
                concrete_geometry = _concrete_geometry()
                views.append({
                    'label': '',
                    'b': float(b),
                    'h_section': float(h_section),
                    'h_A': float(h_total),
                    'h_B': float(h_total),
                    'h_body_A': body_a,
                    'h_body_B': body_b,
                    'laje_sup_A': slab_a,
                    'laje_inf_A': 0.0,
                    'laje_sup_B': slab_b,
                    'laje_inf_B': 0.0,
                    'topology': concrete_geometry.get('topology', 'unknown'),
                    'extension_left_cm': concrete_geometry.get(
                        'extension_left_cm', 0.0),
                    'extension_right_cm': concrete_geometry.get(
                        'extension_right_cm', 0.0),
                    'body_width_cm': concrete_geometry.get(
                        'body_width_cm', float(b)),
                    'concrete_profiles': concrete_geometry.get('profiles', []),
                    'concrete_segments': concrete_geometry.get('segments', []),
                    'visual_primitives': concrete_geometry.get(
                        'visual_primitives', []),
                    'profile_source': concrete_geometry.get('source', ''),
                    'bbox': {
                        'x_left': round(cx - 155, 1),
                        'x_right': round(cx + 155, 1),
                        'y_bot': round(cy - 175, 1),
                        'y_top': round(cy + 175, 1),
                    },
                    'source': 'section_text_cluster',
                })
            views.sort(key=lambda v: (
                -(v.get('bbox') or {}).get('y_top', 0),
                (v.get('bbox') or {}).get('x_left', 0),
            ))
            for idx, view in enumerate(views, 1):
                view['label'] = f'Corte {idx}'
            return views

        local_section_views = _extract_section_views_local()

        # ── 4. b e h_section de "Cota Seção (2x)" próximos à face ativa ─────
        # Filtrar textos dentro do range x das faces (± 250 cm)
        fa_xl = face_A['x_left']  if face_A else 0
        fa_xr = face_A['x_right'] if face_A else 9999
        secao_near = [v for cx, cy, v in secao_txts
                      if (fa_xl - 50 <= cx <= fa_xr + 250) and v > 0]
        secao_all = [v for _cx, _cy, v in secao_txts if v > 0]
        if len({round(v, 1) for v in secao_near}) < 2 and secao_all:
            # Recortes LV podem ter continuação deslocada para outra coluna do
            # mesmo DXF. Nesses casos a segunda "Cota Seção (2x)" fica fora do
            # range da face primária, mas ainda pertence à única viga do recorte.
            secao_near = secao_all
        if secao_near:
            vals_s = sorted(set(secao_near))
            small = [v for v in vals_s if 5 <= v <= 30]
            large = [v for v in vals_s if v > 30]
            if small:
                result['b_geom'] = float(min(small))
            if large:
                # Guardar TODOS os valores de h distintos — cada um pode ser
                # uma configuração de seção diferente (multiple section_views)
                result['h_section'] = float(min(large))
                result['h_section_all'] = [float(v) for v in large]
        if local_section_views:
            result['b_geom'] = float(local_section_views[0]['b'])
            result['h_section'] = float(
                local_section_views[0]['h_section'])
            result['h_section_all'] = [
                float(v['h_section']) for v in local_section_views
            ]

        # ── 5. Alturas (h_total, laje_sup, laje_inf) de COTA TEXT ────────────
        # Excluir TODAS as larguras de painel (não só as >100) e o valor de b.
        all_panel_ws = {round(p['width']) for p in panels_A + panels_B}
        b_round = round(result['b_geom'])

        def _has_laje_box(xl: float, xr: float, y_bot: float, y_top: float,
                          where: str) -> bool:
            """Confirma se ha hachura/faixa de laje perto do topo ou base."""
            if not laje_boxes:
                return False
            if where == 'top':
                y1, y2 = y_top - 2.0, y_top + 90.0
            else:
                y1, y2 = y_bot - 90.0, y_bot + 2.0
            for hxl, hyl, hxr, hyr in laje_boxes:
                ox = min(xr, hxr) - max(xl, hxl)
                oy = min(y2, hyr) - max(y1, hyl)
                if ox <= 2.0 or oy <= 1.0:
                    continue
                if ox / max(xr - xl, 1.0) >= 0.20:
                    return True
            return False

        def _face_heights(fg: dict) -> tuple[float, float, float]:
            """Extrai h_total, laje_sup, laje_inf de COTA TEXT.

            Passo 1 (clássico STOG): COTA à DIREITA da face (x >= x_right-10).
            Passo 2 (fallback per-face): COTA dentro da face, perto de y_top/y_bot.
            """
            y_bot, y_top = fg['y_bot'], fg['y_top']
            x_left, x_right = fg['x_left'], fg['x_right']
            h_body = fg['h_body']
            exclude = all_panel_ws | {b_round}

            # ── Passo 1: margem direita (STOG clássico: DIM_H_RIGHT) ──────────
            nearby_r = [
                v for cx, cy, v in cota_txts
                if (x_right - 10 <= cx <= x_right + 160)
                and (y_bot - 100 <= cy <= y_top + 70)
                and v > 0
            ]
            h_cands_r = sorted(
                {round(v, 1) for v in nearby_r
                 if 2 < v < 200 and round(v) not in exclude},
                reverse=True,
            )
            h_total_opts = [v for v in h_cands_r if v >= h_body - 1]
            if h_total_opts:
                h_total = float(h_total_opts[0])
                laje_total = round(h_total - h_body, 1)
                if laje_total > 0:
                    lo = sorted([v for v in h_cands_r if 2 < v <= min(35, laje_total+3)],
                                reverse=True)
                    if not (
                        _has_laje_box(x_left, x_right, y_bot, y_top, 'top')
                        or _has_laje_box(x_left, x_right, y_bot, y_top, 'bottom')
                    ):
                        return h_body, 0.0, 0.0
                    if not lo and laje_total > 35:
                        # Diferencas grandes geralmente sao outra cota vertical
                        # do desenho, nao espessura de laje. Sem cota local
                        # plausivel, manter apenas o corpo da face.
                        return h_body, 0.0, 0.0
                    laje_sup = float(lo[0]) if lo else laje_total
                    laje_inf = max(0.0, round(laje_total - laje_sup, 1))
                    if laje_sup > 35 or laje_inf > 35:
                        return h_body, 0.0, 0.0
                    return h_total, laje_sup, laje_inf

            # ── Passo 2: COTA espalhada dentro da face (laje por segmento) ────
            # COTAs de laje aparecem no range Y da face inteira (não só perto de y_top).
            # Janela conservadora: excluir valores que podem ser larguras de segmento.
            # x_left - 80: alguns COTAs de laje ficam ligeiramente à esquerda da face.
            sup_nearby = [
                v for cx, cy, v in cota_txts
                if (x_left - 20 <= cx <= x_right + 80)
                and (y_bot - 20 <= cy <= y_top + 80)
                and 2 < v <= 35 and round(v) not in exclude
            ]
            inf_nearby = [
                v for cx, cy, v in cota_txts
                if (x_left - 20 <= cx <= x_right + 80)
                and (y_bot - 80 <= cy <= y_bot + 40)
                and 2 < v <= 35 and round(v) not in exclude
            ]
            # Usa o valor MAIS FREQUENTE (mode) — aparece 1x por segmento no face X range
            # evita capturar COTA da seção transversal que aparece apenas 1x
            laje_sup = float(Counter(sup_nearby).most_common(1)[0][0]) if sup_nearby else 0.0
            laje_inf = float(Counter(inf_nearby).most_common(1)[0][0]) if inf_nearby else 0.0

            # Verificar inconsistência: laje_sup e laje_inf apontando para o mesmo texto
            if laje_sup > 0 and laje_inf > 0 and laje_sup == laje_inf:
                laje_inf = 0.0

            if laje_sup > 0 and not _has_laje_box(x_left, x_right, y_bot, y_top, 'top'):
                laje_sup = 0.0
            if laje_inf > 0 and not _has_laje_box(x_left, x_right, y_bot, y_top, 'bottom'):
                laje_inf = 0.0

            h_total = round(h_body + laje_sup + laje_inf, 1) if (laje_sup + laje_inf) > 0 else h_body
            return h_total, laje_sup, laje_inf

        def _per_seg_slab(segs: list, fg: dict, ls_global: float, li_global: float) -> list:
            """Refina laje_sup/inf por segmento com COTA texts no range X de cada painel.
            Atualiza slab_top/slab_bottom (alias robot-schema) além de laje_sup/inf_local.
            """
            y_top = fg['y_top']
            y_bot = fg['y_bot']
            excl = all_panel_ws | {b_round}

            for seg in segs:
                xl = seg.get('_xl', 0.0)
                xr = seg.get('_xr', 0.0)
                if xl >= xr:
                    seg['slab_top']    = ls_global
                    seg['slab_bottom'] = li_global
                    continue

                # slab_top: COTA perto de y_top dentro do X do segmento
                top_cota = [
                    v for cx, cy, v in cota_txts
                    if xl - 5 <= cx <= xr + 5
                    and y_top - 45 <= cy <= y_top + 70
                    and 2 < v <= 35 and round(v) not in excl
                ]
                # slab_bottom: COTA perto de y_bot
                bot_cota = [
                    v for cx, cy, v in cota_txts
                    if xl - 5 <= cx <= xr + 5
                    and y_bot - 70 <= cy <= y_bot + 45
                    and 2 < v <= 35 and round(v) not in excl
                ]
                ls_seg = float(max(set(top_cota))) if top_cota else ls_global
                li_seg = float(max(set(bot_cota))) if bot_cota else li_global
                if ls_seg > 0 and not _has_laje_box(xl, xr, y_bot, y_top, 'top'):
                    ls_seg = 0.0
                if li_seg > 0 and not _has_laje_box(xl, xr, y_bot, y_top, 'bottom'):
                    li_seg = 0.0

                seg['laje_sup_local'] = ls_seg
                seg['laje_inf_local'] = li_seg
                seg['slab_top']       = ls_seg
                seg['slab_bottom']    = li_seg

                # slab_center: COTA na faixa central da face (indicador de laje embutida)
                mid_y = (y_top + y_bot) / 2
                center_cota = [
                    v for cx, cy, v in cota_txts
                    if xl - 5 <= cx <= xr + 5
                    and mid_y - 60 <= cy <= mid_y + 60
                    and 2 < v <= 35 and round(v) not in excl
                    and v != ls_seg and v != li_seg
                ]
                seg['slab_center'] = float(max(set(center_cota))) if center_cota else 0.0
            return segs

        h_tot_A, ls_A, li_A = _face_heights(face_A) if face_A else (0.0, 0.0, 0.0)
        h_tot_B, ls_B, li_B = _face_heights(face_B) if face_B else (0.0, 0.0, 0.0)

        # ── 6. Detecção de pilar (Madeira V-lines nas bordas) ─────────────────
        def _detect_pillar(fg: dict, side: str) -> dict:
            base = {'active': False, 'width': 0.0, 'length': 0.0}
            if fg is None:
                return base
            x_edge = fg['x_left'] if side == 'left' else fg['x_right']
            h_body = fg['h_body']
            cands = [(yb, yt) for x, yb, yt in madeira_v
                     if abs(x - x_edge) < 8 and (yt - yb) < h_body * 0.85]
            if cands:
                span = max(yt - yb for yb, yt in cands)
                return {'active': True, 'width': result['b_geom'], 'length': round(span, 1)}
            return base

        # ── 7. Consolidar ─────────────────────────────────────────────────────
        def _propagate_laje(segs: list, ls: float, li: float, fg: dict) -> list:
            """Distribui laje globais como fallback e refina por segmento."""
            for s in segs:
                s['laje_sup_local'] = ls
                s['laje_inf_local'] = li
                s['slab_top']       = ls
                s['slab_bottom']    = li
                if s['panel_type'] == 'Sarrafeado':
                    s['height1'] = max(0.0, s['height1'] - 0.0)
            # Refinamento per-segmento via COTA texts locais
            return _per_seg_slab(segs, fg, ls, li)

        if face_A:
            result['h_A']        = h_tot_A if h_tot_A >= face_A['h_body'] else face_A['h_body']
            result['laje_sup_A'] = ls_A
            result['laje_inf_A'] = li_A
            result['panels_A']   = _propagate_laje(panels_A, ls_A, li_A, face_A)
            result['pillar_left']  = _detect_pillar(face_A, 'left')
            result['pillar_right'] = _detect_pillar(face_A, 'right')

        if face_B:
            result['h_B']        = h_tot_B if h_tot_B >= face_B['h_body'] else face_B['h_body']
            result['laje_sup_B'] = ls_B
            result['laje_inf_B'] = li_B
            result['panels_B']   = _propagate_laje(panels_B, ls_B, li_B, face_B)

        # Espelhar se apenas uma face foi detectada
        if face_A and not face_B:
            result['h_B']        = result['h_A']
            result['laje_sup_B'] = ls_A
            result['laje_inf_B'] = li_A
            result['panels_B']   = _propagate_laje(
                [dict(s) for s in panels_A], ls_A, li_A, face_A)
        elif face_B and not face_A:
            result['h_A']        = result['h_B']
            result['laje_sup_A'] = ls_B
            result['laje_inf_A'] = li_B
            result['panels_A']   = _propagate_laje(
                [dict(s) for s in panels_B], ls_B, li_B, face_B)

        # Fallback: laje_sup de seção transversal quando lateral não detectou
        # (ex.: DXF sem layer Hachura → _has_laje_box sempre False)
        # Usa h_A − h_body_A da seção mais próxima ao h_body da face,
        # mas só aceita seções cuja h_body_* difere ≤10 cm do h_body lateral
        # (evita falsos positivos de seções de vigas vizinhas no mesmo DXF).
        if local_section_views:
            def _sv_laje(face_dict: dict | None, sv_key_body: str, sv_key_h: str) -> float:
                if face_dict is None:
                    return 0.0
                h_body = float(face_dict.get('h_body', 0.0))
                candidates = [
                    v for v in local_section_views
                    if float(v.get(sv_key_body, 0) or 0) > 0
                    and abs(float(v.get(sv_key_body, 0) or 0) - h_body) <= 10.0
                ]
                if not candidates:
                    return 0.0
                best = min(candidates,
                           key=lambda v: abs(float(v.get(sv_key_body, 0) or 0) - h_body))
                laje = float(best.get(sv_key_h, 0) or 0) - float(best.get(sv_key_body, 0) or 0)
                return round(laje, 1) if 2.0 < laje <= 35.0 else 0.0

            if result.get('laje_sup_A', 0) == 0:
                lj = _sv_laje(face_A, 'h_body_A', 'h_A')
                if lj > 0:
                    result['laje_sup_A'] = lj
                    result['panels_A'] = _propagate_laje(panels_A, lj, result.get('laje_inf_A', 0.0), face_A)
            if result.get('laje_sup_B', 0) == 0:
                lj = _sv_laje(face_B, 'h_body_B', 'h_B')
                if lj > 0:
                    result['laje_sup_B'] = lj
                    result['panels_B'] = _propagate_laje(panels_B, lj, result.get('laje_inf_B', 0.0), face_B)

        # 7a. Unidades visuais por face/continuação. Mantém panels_A/B para
        # compatibilidade, mas expõe o modelo correto para validação N2 vision:
        # cada label da viga vira uma ficha unitária com seus próprios segmentos.
        def _build_face_units() -> list:
            units: list = []
            units_by_bbox: dict = {}

            def _pontaletes_for_pair(pair: dict) -> list[dict] | int:
                xl = float(pair.get('x_left', 0.0))
                xr = float(pair.get('x_right', 0.0))
                yb = float(pair.get('y_bot', 0.0))
                yt = float(pair.get('y_top', 0.0))
                vals = [
                    {
                        'x_offset': round(x - xl, 1),
                        'y_offset': round(y - yb, 1),
                        'count': count,
                        'text': _txt,
                    }
                    for x, y, count, _txt, _layer, _color, _height in pontalete_txts
                    if xl - 8.0 <= x <= xr + 8.0 and yb - 8.0 <= y <= yt + 8.0
                ]
                for value, (_x, _y, _count, _txt, _layer, _color, _height) in zip(vals, [
                    item for item in pontalete_txts
                    if xl - 8.0 <= item[0] <= xr + 8.0 and yb - 8.0 <= item[1] <= yt + 8.0
                ]):
                    value['layer'] = _layer
                    value['color'] = _color
                    value['height'] = round(_height, 1)
                if not vals:
                    return 0
                return vals

            def _grade_layer_style(pair: dict, segs: list) -> str:
                if not any(seg.get('panel_type') == 'Grade' for seg in segs):
                    return 'native'
                xl = float(pair.get('x_left', 0.0))
                xr = float(pair.get('x_right', 0.0))
                yb = float(pair.get('y_bot', 0.0))
                yt = float(pair.get('y_top', 0.0))
                has_sarr = any(
                    not (x2 < xl - 4.0 or x1 > xr + 4.0 or y2 < yb - 4.0 or y1 > yt + 4.0)
                    for _layer, x1, y1, x2, y2 in sarr_lines
                )
                return 'native' if has_sarr else 'paineis'

            def _local_total_height(pair: dict, segs: list, current: float) -> float:
                """Promove h_total local quando há detalhe de laje/miolo confirmado.

                Algumas unidades trazem h_body pelas H-lines e uma cota total
                maior no mesmo bloco (ex.: 103 corpo, 124 total). Só aceitamos
                esse total quando a própria segmentação encontrou slab/laje
                local, evitando reintroduzir cotas externas como altura.
                """
                if not any(
                    float(seg.get('slab_center', 0) or 0) > 0
                    or float(seg.get('laje_sup_local', 0) or 0) > 0
                    or float(seg.get('laje_inf_local', 0) or 0) > 0
                    for seg in segs
                ):
                    return current
                xl = float(pair.get('x_left', 0.0))
                xr = float(pair.get('x_right', 0.0))
                yb = float(pair.get('y_bot', 0.0))
                yt = float(pair.get('y_top', 0.0))
                h_body = float(pair.get('h_body', 0.0) or 0.0)
                if h_body < 80.0:
                    return current
                candidates = [
                    round(v, 1) for cx, cy, v in (cota_txts + panel_num_txts)
                    if xl - 25.0 <= cx <= xr + 90.0
                    and yb - 85.0 <= cy <= yt + 95.0
                    and h_body - 1.0 <= v <= h_body + 60.0
                    and round(v) not in (all_panel_ws | {b_round})
                ]
                if not candidates:
                    return current
                return max(float(current or h_body), max(candidates))

            def _raw_holes_face(pair: dict) -> list:
                """LWPOLYLINE DASHED que intersectam o bbox da face (coords brutas).

                Usado pelo gerador N4 para desenhar perfis em L/degrau sem
                precisar reconstruir a abertura a partir de sub-segmentos.
                """
                xl = float(pair.get('x_left', 0.0))
                xr = float(pair.get('x_right', 0.0))
                yb = float(pair.get('y_bot',  0.0))
                yt = float(pair.get('y_top',  0.0))
                result = []
                for hxl, hyl, hxr, hyr in holes_lwpoly:
                    ovl_x = min(hxr, xr) - max(hxl, xl)
                    ovl_y = min(hyr, yt) - max(hyl, yb)
                    if ovl_x > 5.0 and ovl_y > 5.0:
                        result.append({
                            'x_left':  round(hxl, 1),
                            'y_bot':   round(hyl, 1),
                            'x_right': round(hxr, 1),
                            'y_top':   round(hyr, 1),
                            'width':   round(hxr - hxl, 1),
                            'height':  round(hyr - hyl, 1),
                        })
                return result

            def _edge_vertical_sarrafos(pair: dict) -> tuple[bool, bool]:
                """Detecta sarrafos verticais nas extremidades físicas da face.

                A presença é mantida por lado (esquerda/direita) para o N4;
                não deve ser inferida apenas porque a face é sarrafeada.
                """
                xl = float(pair.get('x_left', 0.0))
                xr = float(pair.get('x_right', 0.0))
                yb = float(pair.get('y_bot', 0.0))
                yt = float(pair.get('y_top', 0.0))
                height = max(yt - yb, 1.0)
                candidates = [
                    (x, syb, syt) for x, syb, syt in sarr_v
                    if min(syt, yt) - max(syb, yb) >= height * 0.55
                ]
                # O par de sarrafos fica a 15/18.5 cm da borda no STOG;
                # margem de 28 cm cobre as duas linhas sem capturar divisores.
                return (
                    any(xl + 4.0 <= x <= xl + 28.0 for x, _, _ in candidates),
                    any(xr - 28.0 <= x <= xr - 4.0 for x, _, _ in candidates),
                )

            relevant_labels = [
                (lx, ly, txt, side) for lx, ly, txt, side in face_labels
                if elem_prefix and elem_prefix in txt.strip().upper()
            ]
            relevant_labels.sort(key=lambda t: (-t[1], t[0]))
            for lx, ly, txt, side in relevant_labels:
                anchor = (
                    _find_pair_for_label(lx, ly)
                    or _infer_anchor_from_row(lx, ly)
                )
                if not anchor:
                    continue
                anchor_key = (
                    round(anchor.get('x_left', 0.0), 1),
                    round(anchor.get('x_right', 0.0), 1),
                    round(anchor.get('y_bot', 0.0), 1),
                    round(anchor.get('y_top', 0.0), 1),
                )
                anchor_center = (
                    float(anchor.get('x_left', 0))
                    + float(anchor.get('x_right', 0))
                ) / 2
                for pair in _row_pairs_for_anchor(anchor):
                    key = (
                        round(pair.get('x_left', 0.0), 1),
                        round(pair.get('x_right', 0.0), 1),
                        round(pair.get('y_bot', 0.0), 1),
                        round(pair.get('y_top', 0.0), 1),
                    )
                    is_named_anchor = key == anchor_key
                    pair_center = (
                        float(pair.get('x_left', 0))
                        + float(pair.get('x_right', 0))
                    ) / 2
                    side_distance = abs(pair_center - anchor_center)
                    if key in units_by_bbox:
                        existing = units_by_bbox[key]
                        if (
                            is_named_anchor
                            or side_distance < existing.get(
                                '_side_distance', float('inf'))
                        ):
                            existing['side'] = side
                            existing['_side_distance'] = side_distance
                        if is_named_anchor and not existing.get('label'):
                            existing['label'] = txt.strip()
                            existing['label_x'] = round(lx, 1)
                            existing['label_y'] = round(ly, 1)
                            existing['label_source'] = 'text'
                        continue

                    h_total, ls_u, li_u = _face_heights(pair)
                    segs_u = _propagate_laje(
                        _panel_segments(pair), ls_u, li_u, pair)
                    h_total = _local_total_height(pair, segs_u, h_total)
                    sarrafo_left, sarrafo_right = _edge_vertical_sarrafos(pair)
                    unit = {
                        'label': txt.strip() if is_named_anchor else '',
                        'side': side,
                        'label_x': round(lx, 1) if is_named_anchor else None,
                        'label_y': round(ly, 1) if is_named_anchor else None,
                        'label_source': (
                            'text' if is_named_anchor else 'row_inference'),
                        '_side_distance': side_distance,
                        'bbox': {
                            'x_left': round(pair.get('x_left', 0.0), 1),
                            'x_right': round(pair.get('x_right', 0.0), 1),
                            'y_bot': round(pair.get('y_bot', 0.0), 1),
                            'y_top': round(pair.get('y_top', 0.0), 1),
                        },
                        'h_body': pair.get('h_body', 0.0),
                        'h_total': (
                            h_total if h_total > 0
                            else pair.get('h_body', 0.0)),
                        'laje_sup': ls_u,
                        'laje_inf': li_u,
                        'pontaletes_face': _pontaletes_for_pair(pair),
                        'grade_layer_style': _grade_layer_style(pair, segs_u),
                        'sarrafo_vertical_esquerdo': sarrafo_left,
                        'sarrafo_vertical_direito': sarrafo_right,
                        'segments_count': len(segs_u),
                        'panels': segs_u,
                        'raw_holes': _raw_holes_face(pair),
                    }
                    units_by_bbox[key] = unit
                    units.append(unit)
            present_sides = {u.get('side') for u in units if u.get('side')}
            if len(units) >= 2 and len(present_sides) == 1:
                # Alguns recortes trazem o mesmo sufixo em todas as fileiras
                # (ex.: V331.B/V331.B). Nesse caso o desenho, nao o texto,
                # define a ficha A/B: fileira superior = A, inferior = B.
                row_keys = sorted(
                    {
                        round(float((u.get('bbox') or {}).get('y_top', 0.0)) / 8.0) * 8.0
                        for u in units
                    },
                    reverse=True,
                )
                row_side = {
                    row_key: ('A' if idx % 2 == 0 else 'B')
                    for idx, row_key in enumerate(row_keys)
                }
                for unit in units:
                    bbox = unit.get('bbox') or {}
                    row_key = round(float(bbox.get('y_top', 0.0)) / 8.0) * 8.0
                    inferred_side = row_side.get(row_key, unit.get('side'))
                    unit['side'] = inferred_side
                    label = unit.get('label') or ''
                    if label and re.search(r'\.[AB]$', label.strip(), re.IGNORECASE):
                        unit['label'] = re.sub(
                            r'\.[AB]$',
                            f'.{inferred_side}',
                            label.strip(),
                            flags=re.IGNORECASE,
                        )

            for unit in units:
                unit.pop('_side_distance', None)
            return units

        result['face_units'] = _build_face_units()

        # Corrigir h_A/h_B quando a atribuição por posição (y_top) trocou as faces.
        # Em DXFs STOG ambas as faces começam no mesmo y_top → assignment ambígua.
        # Estratégia: usar mediana das face_units com label explícito. Aplicar apenas
        # quando há evidência de troca consistente (labeled_A.h ≈ current_h_B E
        # labeled_B.h ≈ current_h_A). Evita sobre-correção em casos onde h_A/h_B já
        # estão corretos mas um face_unit espúrio tem h_body anômalo.
        _fu_A_lbl = [u for u in result['face_units'] if u.get('side') == 'A' and u.get('label')]
        _fu_B_lbl = [u for u in result['face_units'] if u.get('side') == 'B' and u.get('label')]
        _fu_A_src = _fu_A_lbl or [u for u in result['face_units'] if u.get('side') == 'A']
        _fu_B_src = _fu_B_lbl or [u for u in result['face_units'] if u.get('side') == 'B']
        _fu_A_hs = sorted([float(u.get('h_body') or 0) for u in _fu_A_src if float(u.get('h_body') or 0) > 0])
        _fu_B_hs = sorted([float(u.get('h_body') or 0) for u in _fu_B_src if float(u.get('h_body') or 0) > 0])
        _h_a_now = result.get('h_A', 0)
        _h_b_now = result.get('h_B', 0)
        _h_a_lbl = _fu_A_hs[len(_fu_A_hs) // 2] if _fu_A_hs else 0
        _h_b_lbl = _fu_B_hs[len(_fu_B_hs) // 2] if _fu_B_hs else 0
        # Verificar se há troca: labeled_A ≈ h_B_now E labeled_B ≈ h_A_now
        _swap_A = _h_a_lbl > 0 and _h_a_now > 0 and abs(_h_a_lbl - _h_a_now) > 1.0
        _swap_B = _h_b_lbl > 0 and _h_b_now > 0 and abs(_h_b_lbl - _h_b_now) > 1.0
        _consistent_swap = _swap_A and _swap_B and (
            abs(_h_a_lbl - _h_b_now) <= max(5.0, 0.1 * _h_b_now) or
            abs(_h_b_lbl - _h_a_now) <= max(5.0, 0.1 * _h_a_now)
        )
        _only_A_wrong = _swap_A and not _swap_B
        if _consistent_swap or _only_A_wrong:
            if _h_a_lbl > 0 and _swap_A:
                result['h_A']          = _h_a_lbl
                result['total_height'] = _h_a_lbl
            if _h_b_lbl > 0 and _swap_B and _consistent_swap:
                result['h_B'] = _h_b_lbl

        # ── 7b. section_views: múltiplas seções transversais ─────────────────
        # Estratégia A: labels CONT.* no DXF → cada grupo tem faces próprias com h distinto
        # Estratégia B: segmentos com laje diferente da global → seção adicional
        def _build_section_views() -> list:
            h_A  = result.get('h_A', 0)
            h_B  = result.get('h_B', 0)
            ls_a = result.get('laje_sup_A', 0)
            li_a = result.get('laje_inf_A', 0)
            ls_b = result.get('laje_sup_B', 0)
            li_b = result.get('laje_inf_B', 0)
            b    = result.get('b_geom', 19.0)
            h_s  = result.get('h_section', 0)
            h_section_values = [
                float(v) for v in result.get('h_section_all', [])
                if isinstance(v, (int, float)) and float(v) > 0
            ]
            if not h_section_values and h_s:
                h_section_values = [float(h_s)]

            # View 1: valores primários (face_A/face_B já extraídos)
            views = [{'h_A': h_A, 'h_B': h_B, 'b': b,
                      'laje_sup_A': ls_a, 'laje_inf_A': li_a,
                      'laje_sup_B': ls_b, 'laje_inf_B': li_b,
                      'h_section': h_s, 'label': elem_prefix}]

            # Estratégia A: labels de continuação "CONT.* V301.*"
            # Esses labels NÃO começam com elem_prefix + '.' mas contêm elem_prefix
            cont_labels = [
                (lx, ly, txt, side) for lx, ly, txt, side in face_labels
                if elem_prefix in txt.strip().upper()
                and not txt.strip().upper().startswith(elem_prefix + '.')
            ]
            if cont_labels:
                cont_face_A = cont_face_B = None
                for lx, ly, txt, side in cont_labels:
                    pair = _find_pair_for_label(lx, ly)
                    if pair:
                        if side == 'A' and cont_face_A is None:
                            cont_face_A = pair
                        elif side == 'B' and cont_face_B is None:
                            cont_face_B = pair
                if cont_face_A or cont_face_B:
                    c_h_A, c_ls_a, c_li_a = (_face_heights(cont_face_A)
                                               if cont_face_A else (0.0, 0.0, 0.0))
                    c_h_B, c_ls_b, c_li_b = (_face_heights(cont_face_B)
                                               if cont_face_B else (c_h_A, c_ls_a, c_li_a))
                    # CONT. sempre gera uma view extra (mesmo h idêntico = span visualmente distinto)
                    # fallback: usa h primário quando extração retorna 0
                    eff_h_A = c_h_A if c_h_A > 0 else h_A
                    eff_h_B = c_h_B if c_h_B > 0 else h_B
                    cont_lbl = next(txt for _, _, txt, _ in cont_labels)
                    views.append({'h_A': eff_h_A, 'h_B': eff_h_B, 'b': b,
                                  'laje_sup_A': c_ls_a, 'laje_inf_A': c_li_a,
                                  'laje_sup_B': c_ls_b, 'laje_inf_B': c_li_b,
                                  'h_section': h_s, 'label': cont_lbl})

            # Estratégia B: segmentos com laje diferente da global → seção adicional
            seen_combos: set = {(round(ls_a,1), round(li_a,1), round(ls_b,1), round(li_b,1))}
            panels_b_list = result.get('panels_B', [])
            for i, seg_a in enumerate(result.get('panels_A', [])):
                seg_b = panels_b_list[i] if i < len(panels_b_list) else {}
                ls_sa = round(seg_a.get('slab_top', ls_a), 1)
                li_sa = round(seg_a.get('slab_bottom', li_a), 1)
                ls_sb = round(seg_b.get('slab_top', ls_b), 1)
                li_sb = round(seg_b.get('slab_bottom', li_b), 1)
                combo = (ls_sa, li_sa, ls_sb, li_sb)
                if combo not in seen_combos:
                    seen_combos.add(combo)
                    views.append({'h_A': h_A, 'h_B': h_B, 'b': b,
                                  'laje_sup_A': float(ls_sa), 'laje_inf_A': float(li_sa),
                                  'laje_sup_B': float(ls_sb), 'laje_inf_B': float(li_sb),
                                  'h_section': h_s, 'label': ''})

            # As cotas da camada "Cota Seção (2x)" podem trazer mais de uma
            # altura transversal para a mesma viga. Preservar a ordem visual
            # evita repetir o menor valor em views de continuação.
            if h_section_values:
                while len(views) < len(h_section_values):
                    base = dict(views[-1]) if views else {
                        'h_A': h_A, 'h_B': h_B, 'b': b,
                        'laje_sup_A': ls_a, 'laje_inf_A': li_a,
                        'laje_sup_B': ls_b, 'laje_inf_B': li_b,
                    }
                    base['label'] = f'{elem_prefix}_secao_{len(views) + 1}'
                    views.append(base)
                for idx, view in enumerate(views):
                    view['h_section'] = h_section_values[min(idx, len(h_section_values) - 1)]
            return views

        result['section_views'] = (
            local_section_views
            if local_section_views
            else _build_section_views()
        )

        # ── 8. Tipo de viga ───────────────────────────────────────────────────
        all_segs = result['panels_A'] + result['panels_B']
        has_grade    = any(s.get('panel_type') == 'Grade' for s in all_segs)
        has_sarr     = any(s.get('panel_type') == 'Sarrafeado' for s in all_segs)
        # laje_inf real > 5cm = viga invertida (3cm pode ser só arredondamento)
        has_laje_inf = (result['laje_inf_A'] > 5 or result['laje_inf_B'] > 5)
        if has_grade and has_sarr:
            tipo = 'mista'
        elif has_grade:
            tipo = 'gradeada'
        else:
            tipo = 'sarrafeada'
        if has_laje_inf:
            tipo = (tipo + '_invertida') if tipo != 'sarrafeada' else 'invertida'
        result['tipo_viga'] = tipo

        # ── 9. Confiança ──────────────────────────────────────────────────────
        conf = 0.45
        if my_labels:                          conf += 0.15
        if face_A and face_B:                  conf += 0.10
        if result['h_A'] > 0:                 conf += 0.10
        if panels_A and len(panels_A) >= 2:    conf += 0.08
        if secao_near:                         conf += 0.05
        if result['laje_sup_A'] > 0 or result['laje_sup_B'] > 0:
                                               conf += 0.05
        result['_confianca_extracao'] = min(conf, 0.93)

    except Exception as ex:
        result['_extracao_erro'] = str(ex)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def extrair_ficha_lateral_viga(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
) -> dict:
    """
    Extrai ficha N2 completa para um recorte de lateral de viga.

    Estratégia:
      1. Extrai geometria completa do DXF (fonte primária).
      2. Complementa campos ausentes com dados do JSON Fase-4 (se existir).

    Retorna dict com TODOS os campos que gerar_lv_dxf_stog.py consome,
    mais campos extras N2 (h_A, h_B, panels_A/B, ...) para o ficha_adapter.
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name

    # 1. Extração geométrica do DXF
    geom = _extract_lv_geom_from_dxf(recorte_path, elemento_id)
    conf = geom.pop('_confianca_extracao', 0.4)
    err  = geom.pop('_extracao_erro', None)

    # 2. JSON Fase-4 como base opcional (campos estruturais)
    fase4 = None
    if obra_root_path:
        fase4 = _lookup_fase4_lv(elemento_id, obra_root_path)

    base_id = re.sub(r'_[AB]$', '', elemento_id)
    num_str  = re.sub(r'[^\d]', '', base_id)
    side     = (elemento_id.split('_')[-1]
                if '_' in elemento_id and elemento_id[-1] in 'AB' else 'A')

    if fase4:
        result = {k: v for k, v in fase4.items() if k not in ('_sa_meta', '_er_meta')}
    else:
        result = {
            'number':       num_str,
            'name':         base_id,
            'floor':        'Pavimento',
            'side':         side if side in ('A', 'B') else 'A',
            'total_width':  geom.get('b_geom', 19.0),
            'total_height': geom.get('h_A', 0.0),
            'panels':       [],
            'holes':        [],
            'pillar_left':  {'active': False, 'width': 0.0, 'length': 0.0},
            'pillar_right': {'active': False, 'width': 0.0, 'length': 0.0},
        }

    # 3. Sobrescrever com geometria extraída (prioridade sobre Fase-4)
    result['total_width']  = geom.get('b_geom', result.get('total_width', 19.0))
    result['total_height'] = geom.get('h_A', result.get('total_height', 0.0))

    if geom.get('panels_A'):
        h_a = geom.get('h_A', 0.0)
        result['panels'] = [
            {
                'width':            p['width'],
                'height1':          h_a,
                'height2':          h_a,
                'grade_h1':         0.0,
                'grade_h2':         0.0,
                'laje_central_alt': 0.0,
                'reuse':            False,
                'panel_type':       p.get('panel_type', 'Sarrafeado'),
            }
            for p in geom['panels_A'] if p['width'] > 0
        ]

    if geom.get('pillar_left', {}).get('active'):
        result['pillar_left'] = geom['pillar_left']
    if geom.get('pillar_right', {}).get('active'):
        result['pillar_right'] = geom['pillar_right']

    if not result.get('holes'):
        result['holes'] = [
            {'active': False, 'width': 0.0, 'height': 0.0, 'position': 0.0}
        ] * 4

    # 4. Campos extras N2 (para ficha_adapter → fichas_lv_v2.json)
    result['h_A']           = geom.get('h_A', 0.0)
    result['h_B']           = geom.get('h_B', geom.get('h_A', 0.0))
    result['b_geom']        = geom.get('b_geom', 19.0)
    result['h_section']     = geom.get('h_section', 55.0)
    result['h_section_all'] = geom.get('h_section_all', [])
    result['laje_sup_A']    = geom.get('laje_sup_A', 0.0)
    result['laje_inf_A']    = geom.get('laje_inf_A', 0.0)
    result['laje_sup_B']    = geom.get('laje_sup_B', 0.0)
    result['laje_inf_B']    = geom.get('laje_inf_B', 0.0)
    result['tipo_viga']     = geom.get('tipo_viga', 'sarrafeada')
    result['section_views'] = geom.get('section_views', [])
    result['continuation']  = geom.get('continuation', '')
    result['text_left']     = geom.get('text_left', '')
    result['text_right']    = geom.get('text_right', '')
    result['face_units']    = geom.get('face_units', [])
    result['panels_A']      = geom.get('panels_A', [])
    result['panels_B']      = geom.get('panels_B', [])

    # 5. Metadados
    source = 'dxf_geom' if conf >= 0.55 else 'dxf_geom_parcial'
    if err:
        source = 'dxf_geom_erro'
        print(f"DEBUG EXCEPTION: {err}")
    result['_er_meta'] = {
        'source':    source,
        'dxf_path':  str(recorte_path),
        'confianca': conf,
    }
    if err:
        result['_er_meta']['erro'] = err
    result['_confianca'] = conf

    return result


# ──────────────────────────────────────────────────────────────────────────────
# CLI de teste
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    path  = sys.argv[1] if len(sys.argv) > 1 else ""
    elem  = sys.argv[2] if len(sys.argv) > 2 else "V1_A"
    obra  = sys.argv[3] if len(sys.argv) > 3 else None
    r = extrair_ficha_lateral_viga(path, elem, obra)
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
