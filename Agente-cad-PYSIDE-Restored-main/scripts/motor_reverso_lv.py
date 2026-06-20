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
import json, re

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

# ── Tolerâncias geométricas ──────────────────────────────────────────────────
_EPS_LINE    = 0.5    # tolerância horizontal/vertical (cm)
_EPS_Y       = 1.0    # agrupar H-lines pelo mesmo y
_MIN_FACE_W  = 80     # largura mínima de H-line para ser borda de face (não VC)
_H_BODY_MIN  = 8      # h_body mínimo válido (cm)
_H_BODY_MAX  = 130    # h_body máximo válido (cm)
_MIN_OVERLAP = 40     # sobreposição x mínima entre H-lines do mesmo par (cm)
_LABEL_Y_GAP = 120    # máximo de distância y abaixo do label para encontrar face (cm)
_LABEL_X_GAP = 80     # máximo de distância x entre label e face (cm)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

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
        madeira_v:    list = []   # (x, y_bot, y_top)
        holes_lwpoly: list = []   # (xl, yl, xr, yr) LWPOLYLINE DASHED = aberturas
        cota_txts:    list = []   # (x, y, val)
        secao_txts:   list = []   # (x, y, val)  camada "Cota Seção (2x)"
        face_labels:  list = []   # (x, y, txt, side)  camada "Texto Seção" / "5"
        other_labels: list = []   # (x, y, txt)  pilar/viga refs da camada "5"

        for e in msp:
            layer = e.dxf.layer
            etype = e.dxftype()

            if etype == 'LINE':
                try:
                    p1, p2 = e.dxf.start, e.dxf.end
                    x1, y1 = float(p1[0]), float(p1[1])
                    x2, y2 = float(p2[0]), float(p2[1])
                    _collect_seg_line(layer, x1, y1, x2, y2,
                                      paineis_h, paineis_v, sarr_v, madeira_v, sarr3_v)
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
                except Exception:
                    pass

            elif etype == 'TEXT':
                try:
                    txt = e.dxf.text.strip()
                    ix, iy = float(e.dxf.insert[0]), float(e.dxf.insert[1])
                    if layer == 'COTA':
                        val = float(txt)
                        cota_txts.append((ix, iy, val))
                    elif 'Cota Seção' in layer or layer.upper().startswith('COTA SECAO'):
                        val = float(txt)
                        secao_txts.append((ix, iy, val))
                    elif layer in ('Texto Seção', '5', 'texto', 'NOMENCLATURA'):
                        tu = txt.strip().upper()
                        if re.search(r'\.[AB]$', tu):
                            side = 'A' if tu.endswith('.A') else 'B'
                            face_labels.append((ix, iy, txt.strip(), side))
                        elif re.match(r'^P\d', tu) or re.match(r'^VF?\d', tu):
                            # Pilar/viga labels (P19, VF203, etc.) — texto de referência
                            other_labels.append((ix, iy, txt.strip()))
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
            xl_min = min(s[0] for s in spans)
            xr_max = max(s[1] for s in spans)
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
            """Par de H-lines para um face label, com confirmação por COTA."""
            # Candidatos a y_top: H-lines wide abaixo (ou ligeiramente acima) do label
            tops = [
                (y, xl, xr) for y, xl, xr, w in ys
                if (ly - _LABEL_Y_GAP <= y <= ly + 5)
                and (xl - _LABEL_X_GAP <= lx <= xr + _LABEL_X_GAP)
            ]
            tops.sort(key=lambda t: abs(ly - t[0]))  # mais próximo do label primeiro

            best_confirmed: dict | None = None
            best_fallback: dict | None = None

            for y_top, xl_t, xr_t in tops:
                for y_bot, xl_b, xr_b, w_b in ys:
                    if y_bot >= y_top:
                        continue
                    h_body = y_top - y_bot
                    if not (20 < h_body < _H_BODY_MAX):
                        continue
                    x_ov = min(xr_t, xr_b) - max(xl_t, xl_b)
                    if x_ov < _MIN_OVERLAP:
                        continue
                    # Construir par
                    x_right = max(xr_t, xr_b)
                    pair = {
                        'y_bot':   y_bot,   'y_top':   y_top,
                        'h_body':  round(h_body, 1),
                        'x_left':  min(xl_t, xl_b),
                        'x_right': x_right,
                        'total_w': round(x_right - min(xl_t, xl_b), 1),
                    }
                    # Confirmação COTA: h_body deve aparecer como cota próxima
                    cota_near = {
                        round(v) for cx, cy, v in cota_txts
                        if (x_right - 10 <= cx <= x_right + 160)
                        and (y_bot - 40 <= cy <= y_top + 40)
                    }
                    if round(h_body) in cota_near:
                        if best_confirmed is None:
                            best_confirmed = pair
                    else:
                        if best_fallback is None or h_body > best_fallback['h_body']:
                            best_fallback = pair

                if best_confirmed is not None:
                    break  # encontrou par confirmado para este y_top

            return best_confirmed or best_fallback

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

        # Filtrar labels do elemento atual (elem_prefix = "V13", etc.)
        my_labels = [(lx, ly, txt, side) for lx, ly, txt, side in face_labels
                     if txt.upper().startswith(elem_prefix + '.')]

        face_A: dict | None = None
        face_B: dict | None = None

        if my_labels:
            for lx, ly, txt, side in my_labels:
                pair = _find_pair_for_label(lx, ly)
                if side == 'A' and pair:
                    face_A = pair
                elif side == 'B' and pair:
                    face_B = pair

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
            return result

        # Garantir que A é a face mais alta
        if face_A and face_B and face_A['y_top'] < face_B['y_top']:
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
                return [_make_seg(x_left, x_right, h_body, ptype_face, gh,
                                  is_first=True, is_last=True)]

            segs: list = []
            n = len(deduped)
            # Recalcular is_last corretamente com filtragem de w > 5
            valid_ks = [k for k in range(n - 1)
                        if round(deduped[k + 1] - deduped[k], 1) > 5]
            for idx, k in enumerate(valid_ks):
                xl, xr = deduped[k], deduped[k + 1]
                gh = _extract_grade_h(xl, xr, y_bot, y_top) if face_grade else 0.0
                segs.append(_make_seg(xl, xr, h_body, ptype_face, gh,
                                      is_first=(idx == 0),
                                      is_last=(idx == len(valid_ks) - 1)))
            return segs

        def _make_seg(xl: float, xr: float, h_body: float,
                      ptype: str, gh: float,
                      is_first: bool, is_last: bool) -> dict:
            """Constrói o dict canônico de um segmento (campos do gerador)."""
            w = round(xr - xl, 1)
            holes = _detect_holes_seg(xl, xr, 0, h_body)  # y_bot/top corrigidos depois
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
                'reuse':          False,
                'codigos_forma':  [],
                '_xl':            xl,         # guardado para per-seg slab lookup
                '_xr':            xr,
            }

        panels_A = _panel_segments(face_A) if face_A else []
        panels_B = _panel_segments(face_B) if face_B else []

        # ── 4. b e h_section de "Cota Seção (2x)" próximos à face ativa ─────
        # Filtrar textos dentro do range x das faces (± 250 cm)
        fa_xl = face_A['x_left']  if face_A else 0
        fa_xr = face_A['x_right'] if face_A else 9999
        secao_near = [v for cx, cy, v in secao_txts
                      if (fa_xl - 50 <= cx <= fa_xr + 250) and v > 0]
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

        # ── 5. Alturas (h_total, laje_sup, laje_inf) de COTA TEXT ────────────
        # Excluir TODAS as larguras de painel (não só as >100) e o valor de b.
        all_panel_ws = {round(p['width']) for p in panels_A + panels_B}
        b_round = round(result['b_geom'])

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
                    laje_sup = float(lo[0]) if lo else laje_total
                    laje_inf = max(0.0, round(laje_total - laje_sup, 1))
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
            return views

        result['section_views'] = _build_section_views()

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
    result['panels_A']      = geom.get('panels_A', [])
    result['panels_B']      = geom.get('panels_B', [])

    # 5. Metadados
    source = 'dxf_geom' if conf >= 0.55 else 'dxf_geom_parcial'
    if err:
        source = 'dxf_geom_erro'
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
