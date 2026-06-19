# -*- coding: utf-8 -*-
"""Motor Reverso LV — Extrai ficha N2 de recorte DXF STOG lateral viga.

Produz todos os campos que o gerador gerar_lv_dxf_stog.py consome, incluindo:
  h_A, h_B          — altura total de painéis Face A e B (h_body + lajesSup + lajesInf)
  b_geom            — largura da seção transversal (de "Cota Seção (2x)" TEXT)
  h_section         — altura da seção na VC (de "Cota Seção (2x)" TEXT)
  laje_sup_A/B      — laje superior por face (de COTA TEXT perto da face)
  laje_inf_A/B      — laje inferior por face
  panels_A/B        — segmentos com largura_cm (de V-lines em Painéis)
  pillar_left/right — pilar ativo se detectado (Madeira V-lines de borda)
  holes             — aberturas (placeholder vazio por padrão)

Estratégia de detecção de faces:
  1. Usa face labels ("V13.A", "V13.B") da camada "Texto Seção" / "5"
     para ancorar cada face — robusto contra múltiplas vigas por sheet.
  2. Encontra par de H-lines da camada Painéis (h_body 8-130 cm) abaixo
     de cada label e alinhado horizontalmente com o label.
  3. Extrai V-lines dentro do range xy da face → larguras dos painéis.
  4. Associa COTA TEXT próximos à face → h_total, laje_sup, laje_inf.
  5. Filtra "Cota Seção (2x)" por proximidade à face ativa.
"""

from __future__ import annotations
from pathlib import Path
from collections import defaultdict
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
                      sarr_v: list, madeira_v: list) -> None:
    """Classifica um segmento de linha nas listas corretas."""
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    if layer == 'Painéis':
        if dy < _EPS_LINE and dx > 5:
            paineis_h.append((min(y1, y2), min(x1, x2), max(x1, x2)))
        elif dx < _EPS_LINE and dy > 5:
            paineis_v.append((min(x1, x2), min(y1, y2), max(y1, y2)))
    elif layer in ('SARR_2.2x7', 'SARR_EDITAR', 'SARR_3.5x7'):
        if dx < _EPS_LINE and dy > 5:
            sarr_v.append((min(x1, x2), min(y1, y2), max(y1, y2)))
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
        'h_A': 0.0, 'h_B': 0.0,
        'b_geom': 19.0, 'h_section': 55.0,
        'laje_sup_A': 0.0, 'laje_inf_A': 0.0,
        'laje_sup_B': 0.0, 'laje_inf_B': 0.0,
        'panels_A': [], 'panels_B': [],
        'pillar_left':  {'active': False, 'width': 0.0, 'length': 0.0},
        'pillar_right': {'active': False, 'width': 0.0, 'length': 0.0},
        'holes': [],
        '_confianca_extracao': 0.35,
    }

    # Prefixo do elemento para filtrar labels no sheet (ex: "V13", "VF203")
    elem_prefix = re.sub(r'_[AB]$', '', elem_id).upper()

    try:
        import ezdxf

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        paineis_h:   list = []   # (y, x_left, x_right)
        paineis_v:   list = []   # (x, y_bot, y_top)
        sarr_v:      list = []   # (x, y_bot, y_top)
        madeira_v:   list = []   # (x, y_bot, y_top)
        cota_txts:   list = []   # (x, y, val)
        secao_txts:  list = []   # (x, y, val)  camada "Cota Seção (2x)"
        face_labels: list = []   # (x, y, txt, side)  camada "Texto Seção" / "5"

        for e in msp:
            layer = e.dxf.layer
            etype = e.dxftype()

            if etype == 'LINE':
                try:
                    p1, p2 = e.dxf.start, e.dxf.end
                    x1, y1 = float(p1[0]), float(p1[1])
                    x2, y2 = float(p2[0]), float(p2[1])
                    _collect_seg_line(layer, x1, y1, x2, y2,
                                      paineis_h, paineis_v, sarr_v, madeira_v)
                except Exception:
                    pass

            elif etype == 'LWPOLYLINE':
                try:
                    pts = list(e.get_points('xy'))
                    n = len(pts)
                    if n == 2:
                        (x1, y1), (x2, y2) = pts[0], pts[1]
                        _collect_seg_line(layer, x1, y1, x2, y2,
                                          paineis_h, paineis_v, sarr_v, madeira_v)
                    elif n >= 3:
                        closed = bool(e.closed)
                        limit = n if closed else n - 1
                        for i in range(limit):
                            x1, y1 = pts[i]
                            x2, y2 = pts[(i + 1) % n]
                            _collect_seg_line(layer, x1, y1, x2, y2,
                                              paineis_h, paineis_v, sarr_v, madeira_v)
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
                        if re.search(r'\.[AB]$', txt.strip().upper()):
                            side = 'A' if txt.strip().upper().endswith('.A') else 'B'
                            face_labels.append((ix, iy, txt.strip(), side))
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

        # ── 3. Larguras dos segmentos de painel (V-lines Painéis) ────────────
        def _panel_widths(fg: dict) -> list:
            y_bot, y_top = fg['y_bot'], fg['y_top']
            x_left, x_right = fg['x_left'], fg['x_right']
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
                return [{'width': fg['total_w'], 'panel_type': 'Sarrafeado',
                         'height1': 0.0, 'height2': 0.0, 'grade_h1': 0.0,
                         'grade_h2': 0.0, 'laje_central_alt': 0.0, 'reuse': False}]
            panels: list = []
            for k in range(len(deduped) - 1):
                w = round(deduped[k + 1] - deduped[k], 1)
                if w > 5:
                    panels.append({'width': w, 'panel_type': 'Sarrafeado',
                                   'height1': 0.0, 'height2': 0.0, 'grade_h1': 0.0,
                                   'grade_h2': 0.0, 'laje_central_alt': 0.0,
                                   'reuse': False})
            return panels

        panels_A = _panel_widths(face_A) if face_A else []
        panels_B = _panel_widths(face_B) if face_B else []

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
                result['h_section'] = float(min(large))  # usar mínimo (evita ruído de outra viga)

        # ── 5. Alturas (h_total, laje_sup, laje_inf) de COTA TEXT ────────────
        # Excluir TODAS as larguras de painel (não só as >100) e o valor de b.
        all_panel_ws = {round(p['width']) for p in panels_A + panels_B}
        b_round = round(result['b_geom'])

        def _face_heights(fg: dict) -> tuple[float, float, float]:
            y_bot, y_top = fg['y_bot'], fg['y_top']
            x_left, x_right = fg['x_left'], fg['x_right']
            h_body = fg['h_body']

            # Dimensões de altura ficam SEMPRE à direita da face em STOG (DIM_H_RIGHT)
            # Permitir também pequena margem à esquerda para lajeInf que às vezes fica lá.
            x_min_h = x_right - 10   # não tomar COTA de dentro da face ou à esquerda
            x_max_h = x_right + 150  # largura da zona de cotas à direita

            nearby = [
                v for cx, cy, v in cota_txts
                if (x_min_h <= cx <= x_max_h)
                and (y_bot - 100 <= cy <= y_top + 70)
                and v > 0
            ]
            # Excluir larguras de painel e b da seção
            exclude = all_panel_ws | {b_round}
            h_cands = sorted(
                {round(v, 1) for v in nearby
                 if 2 < v < 200 and round(v) not in exclude},
                reverse=True,
            )
            if not h_cands:
                return h_body, 0.0, 0.0

            # h_total: maior valor >= h_body
            h_total_opts = [v for v in h_cands if v >= h_body - 1]
            h_total = float(h_total_opts[0]) if h_total_opts else float(h_body)

            laje_total = round(h_total - h_body, 1)
            if laje_total <= 0:
                return h_total, 0.0, 0.0

            # Valor individual de laje (≤ laje_total+2 e ≤ 35 cm)
            laje_opts = sorted(
                [v for v in h_cands if 2 < v <= min(35, laje_total + 3)],
                reverse=True,
            )
            if laje_opts:
                laje_sup = float(laje_opts[0])
                laje_inf = max(0.0, round(laje_total - laje_sup, 1))
            else:
                laje_sup = laje_total
                laje_inf = 0.0

            return h_total, laje_sup, laje_inf

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
        if face_A:
            result['h_A']        = h_tot_A if h_tot_A >= face_A['h_body'] else face_A['h_body']
            result['laje_sup_A'] = ls_A
            result['laje_inf_A'] = li_A
            result['panels_A']   = panels_A
            result['pillar_left']  = _detect_pillar(face_A, 'left')
            result['pillar_right'] = _detect_pillar(face_A, 'right')

        if face_B:
            result['h_B']        = h_tot_B if h_tot_B >= face_B['h_body'] else face_B['h_body']
            result['laje_sup_B'] = ls_B
            result['laje_inf_B'] = li_B
            result['panels_B']   = panels_B

        # Espelhar se apenas uma face foi detectada
        if face_A and not face_B:
            result['h_B']        = result['h_A']
            result['laje_sup_B'] = ls_A
            result['laje_inf_B'] = li_A
            result['panels_B']   = panels_A[:]
        elif face_B and not face_A:
            result['h_A']        = result['h_B']
            result['laje_sup_A'] = ls_B
            result['laje_inf_A'] = li_B
            result['panels_A']   = panels_B[:]

        # ── 8. Confiança ──────────────────────────────────────────────────────
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
    result['h_A']        = geom.get('h_A', 0.0)
    result['h_B']        = geom.get('h_B', geom.get('h_A', 0.0))
    result['b_geom']     = geom.get('b_geom', 19.0)
    result['h_section']  = geom.get('h_section', 55.0)
    result['laje_sup_A'] = geom.get('laje_sup_A', 0.0)
    result['laje_inf_A'] = geom.get('laje_inf_A', 0.0)
    result['laje_sup_B'] = geom.get('laje_sup_B', 0.0)
    result['laje_inf_B'] = geom.get('laje_inf_B', 0.0)
    result['panels_A']   = geom.get('panels_A', [])
    result['panels_B']   = geom.get('panels_B', [])

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
