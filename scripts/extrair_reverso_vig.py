#!/usr/bin/env python3
"""
extrair_reverso_vig.py - Extrai fichas de vigas dos DXFs STOG (LV + FV).
Engenharia reversa: le os desenhos gerados pelos robos e reconstroi dados estruturais.

Correcoes v2:
- Raio de busca baseado na bbox real dos Paineis lines (nao raio fixo grande)
- Cada bloco de secao tem sua propria zona de busca de COTA
- Comprimento = maior COTA H dentro da bbox do bloco
- CONT. agrupado com o mesmo lote (mesmo viga+side, x adjacente)

Saida: fichas_reverso_VIG.json
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf, math, re, json, argparse, os
from collections import defaultdict


def dist2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)


def get_dim_value(e):
    """Valor real da dimensao ezdxf DIMENSION."""
    try:
        v = e.dxf.actual_measurement
        if v and v > 0: return round(v, 1)
    except Exception: pass
    try:
        dp = (float(e.dxf.defpoint[0]), float(e.dxf.defpoint[1]))
        dp2 = (float(e.dxf.defpoint2[0]), float(e.dxf.defpoint2[1]))
        dx = abs(dp[0]-dp2[0]); dy = abs(dp[1]-dp2[1])
        v = math.sqrt(dx*dx+dy*dy)
        return round(v, 1) if v > 0 else None
    except Exception: return None


def get_dim_info(e):
    v = get_dim_value(e)
    if v is None: return None
    try:
        dp = (float(e.dxf.defpoint[0]), float(e.dxf.defpoint[1]))
        dp2 = (float(e.dxf.defpoint2[0]), float(e.dxf.defpoint2[1]))
        dx = abs(dp[0]-dp2[0]); dy = abs(dp[1]-dp2[1])
        orient = 'H' if dx > dy else 'V'
        center = ((dp[0]+dp2[0])/2, (dp[1]+dp2[1])/2)
    except Exception: return None
    return {'meas': v, 'orient': orient, 'center': center}


# ── LV EXTRACTOR ─────────────────────────────────────────────────────────────

def extrair_pilar_refs_fv(fv_path):
    """Extrai referências de pilares (P-labels) do DXF FV (layer '5' ou 'TEXTO PILAR').
    Usado como pool suplementar quando os labels no LV estão fora do alcance das seções
    (ex: TREINO_17 1PV — LV refs em Y~27k, seções em Y~34k, gap ~6000 unidades).
    O FV frequentemente tem os P-labels co-localizados com as seções."""
    try:
        doc = ezdxf.readfile(fv_path)
        msp = doc.modelspace()
        refs = []
        for e in msp:
            if e.dxftype() != 'TEXT':
                continue
            lyr = e.dxf.layer
            if lyr not in ('5', 'TEXTO PILAR'):
                continue
            txt = e.dxf.text.strip()
            if re.match(r'^P\d+', txt):
                refs.append({'text': txt, 'pos': (float(e.dxf.insert[0]), float(e.dxf.insert[1]))})
        return refs
    except Exception:
        return []


def extrair_lv(lv_path, extra_pilar_refs=None):
    doc = ezdxf.readfile(lv_path)
    msp = doc.modelspace()

    # 1. Textos de secao (Texto Secao layer OU NOMENCLATURA)
    # TREINO_1+: layer 'Texto Seção' ou similar (contém 'Texto' e 'Se')
    # TREINO_5+: layer 'NOMENCLATURA' (contem V201.A, V201.B etc.)
    # Nota: DXFs gerados podem usar MTEXT em vez de TEXT (ex: TREINO_1 LV_gerado.dxf)
    secao_texts = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'): continue
        layer = str(e.dxf.layer)
        is_secao_layer = ('Texto' in layer and 'Se' in layer) or layer == 'NOMENCLATURA'
        if not is_secao_layer: continue
        if e.dxftype() == 'MTEXT':
            try:
                txt = e.plain_text().strip()
            except Exception:
                txt = e.dxf.text.strip()
        else:
            txt = e.dxf.text.strip()
        # Formato padrão: V1.A, V1_A, V10A.A (sufixo alfa em vigas compostas)
        m = re.match(r'^(CONT\.\s*)?V[F]?(\d+[A-Za-z]?)[._]([AB])$', txt)
        if m:
            _raw = m.group(2)
            _vid = f'V{_raw}' if re.search(r'[A-Za-z]$', _raw) else f'V{int(_raw)}'
            secao_texts.append({
                'viga': _vid,
                'side': m.group(3),
                'is_cont': bool(m.group(1)),
                'pos': (float(e.dxf.insert[0]), float(e.dxf.insert[1])),
                'text': txt,
            })
        else:
            # Compound format: 'V406.A-V406.B', 'V422.A-V425.A', 'V418A.A-V424.B' etc.
            # Múltiplos labels V-face num único TEXT entity (bloco de seção compartilhado).
            # Ex: TREINO_11 1PV LV usa este formato para vigas agrupadas na mesma seção.
            pieces = re.findall(r'V[F]?(\d+[A-Za-z]?)[._]([AB])', txt)
            if len(pieces) >= 2:
                pos = (float(e.dxf.insert[0]), float(e.dxf.insert[1]))
                for raw_num, side in pieces:
                    # Preservar sufixo alfa (ex: '418A') ou normalizar inteiro (ex: '406')
                    viga_id = f'V{raw_num}' if re.search(r'[A-Za-z]$', raw_num) else f'V{int(raw_num)}'
                    secao_texts.append({
                        'viga': viga_id,
                        'side': side,
                        'is_cont': False,
                        'pos': pos,
                        'text': txt,
                    })

    # 1b. NOMENCLATURA captions (DXFs gerados pelo robô LV TREINO_1 e similares):
    # Formato: '{PAV} - V{num}  b={b}cm  h={h}cm  L={L}cm'
    # Estes captions codificam diretamente b/h/L → usados como override quando
    # a extração por dimensões DXF falha (ex: Cota Seção 2x ausente no DXF gerado).
    caption_overrides = {}  # viga_id -> {b, h, comprimento}
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT') or e.dxf.layer != 'NOMENCLATURA':
            continue
        if e.dxftype() == 'MTEXT':
            try:
                txt = e.plain_text().strip()
            except Exception:
                txt = e.dxf.text.strip()
        else:
            txt = e.dxf.text.strip()
        mc = re.search(r'V(\d+)\s+b=(\d+)cm\s+h=(\d+)cm\s+L=(\d+)cm', txt)
        if mc:
            vid = f'V{int(mc.group(1))}'
            caption_overrides[vid] = {
                'b':          float(mc.group(2)),
                'h_secao':    float(mc.group(3)),
                'comprimento': float(mc.group(4)),
            }

    # 2. COTA dimensions
    cota_dims = []
    for e in msp:
        if e.dxftype() == 'DIMENSION' and e.dxf.layer == 'COTA':
            info = get_dim_info(e)
            if info: cota_dims.append(info)

    # 2b. Cota Seção (2x) — dimensões da seção transversal: b e h estruturais
    # Presente em TODOS os LV DXFs. Contém b (pequenos H-dims) e h_secao (V-dims),
    # mais próximos dos valores estruturais do TQS do que os COTA form-dims.
    secao_2x_dims = []
    for e in msp:
        if e.dxftype() != 'DIMENSION': continue
        lyr = str(e.dxf.layer)
        if 'Se' not in lyr or '2x' not in lyr: continue
        info = get_dim_info(e)
        if info: secao_2x_dims.append(info)

    # 3. Paineis lines para calcular bbox real de cada bloco
    paineis_lines = []
    for e in msp:
        if e.dxftype() == 'LINE' and 'Pain' in str(e.dxf.layer):
            s = (float(e.dxf.start[0]), float(e.dxf.start[1]))
            en = (float(e.dxf.end[0]), float(e.dxf.end[1]))
            mp = ((s[0]+en[0])/2, (s[1]+en[1])/2)
            paineis_lines.append({'s': s, 'e': en, 'mp': mp})

    # 4. Textos TEXTO PILAR (P1, P2 etc nas extremidades)
    # Layer '5' = pilar name labels no LV DXF (todos os pavimentos confirmados)
    # Layer 'TEXTO PILAR' = alias legacy (mantido como fallback)
    pilar_refs = []
    for e in msp:
        if e.dxftype() != 'TEXT': continue
        lyr = e.dxf.layer
        if lyr not in ('5', 'TEXTO PILAR'): continue
        txt = e.dxf.text.strip()
        if re.match(r'^P\d+', txt):
            pilar_refs.append({'text': txt, 'pos': (float(e.dxf.insert[0]), float(e.dxf.insert[1]))})

    # 4b. Pool suplementar do FV (quando LV labels estão fora do alcance das seções)
    # Ex: TREINO_17 1PV — LV pilar_refs em Y~27k, seções em Y~34k (gap ~6k > raio max 1200).
    # O FV tem P-labels co-localizados com as seções → merge correto por zona de raio.
    # Deduplicação por (texto, célula de grid 100u): evita entradas idênticas.
    if extra_pilar_refs:
        existing_keys = {(p['text'], round(p['pos'][0]/100), round(p['pos'][1]/100))
                         for p in pilar_refs}
        for p in extra_pilar_refs:
            key = (p['text'], round(p['pos'][0]/100), round(p['pos'][1]/100))
            if key not in existing_keys:
                pilar_refs.append(p)
                existing_keys.add(key)

    # 5. Agrupar secoes por (viga, side)
    groups = defaultdict(list)
    for s in secao_texts:
        groups[(s['viga'], s['side'])].append(s)

    vigas_lv = {}
    for (viga, side), sections in groups.items():
        # Calcular bbox dos Paineis lines ao redor de cada texto de secao (raio 600)
        all_xs, all_ys = [], []
        for sec in sections:
            anchor = sec['pos']
            nearby = [l for l in paineis_lines if dist2d(l['mp'], anchor) < 600]
            for l in nearby:
                all_xs += [l['s'][0], l['e'][0]]
                all_ys += [l['s'][1], l['e'][1]]

        if not all_xs:
            # fallback: usar posicao dos textos
            all_xs = [s['pos'][0] for s in sections]
            all_ys = [s['pos'][1] for s in sections]

        bbox_xmin, bbox_xmax = min(all_xs)-50, max(all_xs)+50
        bbox_ymin, bbox_ymax = min(all_ys)-50, max(all_ys)+100

        # 6. COTA dims dentro dessa bbox
        nearby_h, nearby_v = [], []
        for d in cota_dims:
            cx, cy = d['center']
            if bbox_xmin <= cx <= bbox_xmax and bbox_ymin <= cy <= bbox_ymax:
                if d['orient'] == 'H': nearby_h.append(d['meas'])
                else: nearby_v.append(d['meas'])

        h_sorted = sorted(nearby_h, reverse=True)
        v_sorted = sorted(nearby_v, reverse=True)

        comprimento_total = h_sorted[0] if h_sorted else round(bbox_xmax - bbox_xmin - 100, 0)

        # Paineis = dims H menores que o total, >= 50cm (exclui ruído: pilares, sarrafos)
        paineis = sorted([m for m in h_sorted if m >= 50 and m < comprimento_total - 5], reverse=True)

        # Altura (form h) = maior V dim no range 20-200cm em COTA
        bbox_h = round(max(all_ys) - min(all_ys), 1) if len(all_ys) >= 2 else 0
        altura = 0
        for m in v_sorted:
            if 20 <= m <= 200:
                altura = m
                break
        if not altura and v_sorted:
            altura = v_sorted[0]
        # Fallback: quando COTA não tem V-dims (v_sorted vazio), usar bbox_h dos Paineis lines.
        # bbox_h = span vertical das linhas de Paineis ao redor da seção = altura da forma.
        # Threshold 20-200cm: evita ruído (valores < 20cm = sarrafo) e outliers (>200cm).
        if not altura and 20.0 <= bbox_h <= 200.0:
            altura = bbox_h

        # Cota Seção (2x) — b_secao e h_secao (dimensões estruturais, mais precisas)
        # Bbox estendida: section details ficam próximos ao bloco principal (±600 units)
        SECAO_EXT = 600
        sx_lo, sx_hi = bbox_xmin - SECAO_EXT, bbox_xmax + SECAO_EXT
        sy_lo, sy_hi = bbox_ymin - SECAO_EXT, bbox_ymax + SECAO_EXT
        near_b = []   # H-dims 8-35cm → candidatos a b
        near_hs = []  # V-dims 20-200cm → candidatos a h estrutural
        for d in secao_2x_dims:
            cx, cy = d['center']
            if sx_lo <= cx <= sx_hi and sy_lo <= cy <= sy_hi:
                if d['orient'] == 'H' and 8 <= d['meas'] <= 35:
                    near_b.append(d['meas'])
                elif d['orient'] == 'V' and 20 <= d['meas'] <= 200:
                    near_hs.append(d['meas'])

        # b_secao: valor mais comum (mode) — evita pegar b de viga vizinha
        # h_secao: valor mais comum (mode) — evita pegar h de seção menor de viga vizinha
        if near_b:
            from collections import Counter as _Counter
            b_secao = _Counter(near_b).most_common(1)[0][0]
        else:
            b_secao = None
        if near_hs:
            from collections import Counter as _Counter
            h_secao = _Counter(near_hs).most_common(1)[0][0]
        else:
            h_secao = None

        # Pilares nas extremidades — adaptive radius: tenta 400 primeiro, expande se vazio
        # Evita falso positivo (viga vizinha) usando raio mínimo possível,
        # mas garante cobertura quando pilar_label está distante do bloco de secao.
        nearby_pilares = []
        for _r in (400, 600, 800, 1000, 1200):
            nearby_pilares = [p for p in pilar_refs
                              if bbox_xmin-_r <= p['pos'][0] <= bbox_xmax+_r
                              and bbox_ymin-_r <= p['pos'][1] <= bbox_ymax+_r]
            if nearby_pilares:
                break

        # Fase 2: Y-only fallback para extra_pilar_refs em espaço X diferente
        # (ex: TREINO_17 1PV — FV pilar refs em X~194k, seções LV em X~130k, gap ~60k).
        # O FV e o LV são desenhados em regiões X independentes, mas compartilham Y estrutural.
        # Threshold Y: 1200 unidades — generoso para cobrir layouts STOG variados.
        if not nearby_pilares and extra_pilar_refs:
            Y_ONLY_BAND = 1200
            nearby_pilares = [p for p in extra_pilar_refs
                              if bbox_ymin - Y_ONLY_BAND <= p['pos'][1] <= bbox_ymax + Y_ONLY_BAND]

        nearby_pilares.sort(key=lambda p: p['pos'][0])
        pillar_left = nearby_pilares[0]['text'] if nearby_pilares else None
        pillar_right = nearby_pilares[-1]['text'] if len(nearby_pilares) >= 2 else None

        if viga not in vigas_lv:
            vigas_lv[viga] = {}

        vigas_lv[viga][f'lado_{side}'] = {
            'comprimento_total': comprimento_total,
            'altura': altura,
            'b_secao': b_secao,
            'h_secao': h_secao,
            'paineis': paineis,
            'n_paineis': len(paineis),
            'pillar_left': pillar_left,
            'pillar_right': pillar_right,
            '_n_dims_h': len(nearby_h),
            '_bbox_w': round(bbox_xmax - bbox_xmin, 0),
            '_bbox_h': bbox_h,
        }

    # Apply NOMENCLATURA caption overrides to fill missing b_secao / h_secao
    for vid, cap in caption_overrides.items():
        if vid not in vigas_lv:
            continue
        for side_key in ('lado_A', 'lado_B'):
            if side_key not in vigas_lv[vid]:
                continue
            ld = vigas_lv[vid][side_key]
            if not ld.get('b_secao'):
                ld['b_secao'] = cap['b']
            if not ld.get('h_secao'):
                ld['h_secao'] = cap['h_secao']
            # Comprimento from caption (L field) — only override if extracted value
            # is missing or suspiciously small (< 20cm = fallback bbox artifact)
            if cap['comprimento'] > 0 and (not ld.get('comprimento_total') or ld['comprimento_total'] < 20):
                ld['comprimento_total'] = cap['comprimento']

    return vigas_lv


# ── FV EXTRACTOR ─────────────────────────────────────────────────────────────

def extrair_fv(fv_path):
    doc = ezdxf.readfile(fv_path)
    msp = doc.modelspace()

    # Nomes FV (layer NOMENCLATURA)
    nom_texts = []
    for e in msp:
        if e.dxftype() == 'TEXT' and e.dxf.layer == 'NOMENCLATURA':
            txt = e.dxf.text.strip()
            pos = (float(e.dxf.insert[0]), float(e.dxf.insert[1]))
            nom_texts.append({'text': txt, 'pos': pos})

    # COTA dims apenas (layer COTA — mais confiável que Painéis para FV)
    # Para V-orient dims: actual_measurement é preferencial (medida real anotada pelo STOG).
    # Fallback para geometria bruta quando actual_measurement < 8cm (claramente incorreto,
    # ex: TREINO_5 500-FV tem actual_measurement=2.0 para b=21.5cm real).
    cota_dims = []
    for e in msp:
        if e.dxftype() != 'DIMENSION' or e.dxf.layer != 'COTA':
            continue
        try:
            dp  = (float(e.dxf.defpoint[0]),  float(e.dxf.defpoint[1]))
            dp2 = (float(e.dxf.defpoint2[0]), float(e.dxf.defpoint2[1]))
            dx = abs(dp[0]-dp2[0]); dy = abs(dp[1]-dp2[1])
            orient = 'H' if dx > dy else 'V'
            cx, cy = (dp[0]+dp2[0])/2, (dp[1]+dp2[1])/2
            if orient == 'V':
                # Para V dims (b candidatos): usar actual_measurement se >= 8cm (plausível)
                # Fallback para geometria bruta quando actual_measurement é claramente errado (< 8cm)
                v = get_dim_value(e)
                if v is not None and v < 8:
                    raw_v = round(math.sqrt(dx*dx+dy*dy), 1)
                    if raw_v >= 8:
                        v = raw_v
                    else:
                        v = None  # descartado (ruído)
            else:
                v = get_dim_value(e)
            if v and v > 0:
                cota_dims.append({'meas': v, 'orient': orient, 'center': (cx, cy)})
        except Exception:
            pass

    # ── Estratégia FV v3 ──────────────────────────────────────────────────────
    # O FV é desenhado em projeção oblíqua (≈45°): b aparece como orient=H.
    # Cada texto NOMENCLATURA pode conter múltiplas vigas (ex: "V13.C - V15.C").
    # A âncora do texto está à ESQUERDA do desenho real (forma está à direita).
    # Y-band adaptativo: usa a distância entre âncoras vizinhas para separar grupos.

    # 1. Agrupar por texto-âncora (um grupo por NOMENCLATURA text, lista de V-ids)
    text_groups = []  # [{'pos': (x,y), 'vigas': [V1, V2, ...]}]
    for nt in nom_texts:
        txt = nt['text']
        parts = [p.strip() for p in txt.replace('–', '-').split('-')]
        vigas_in_text = []
        for part in parts:
            m = re.match(r'^(CONT\.\s*)?V(\d+)\.C$', part.strip())
            if m:
                vigas_in_text.append(f'V{int(m.group(2))}')
        if vigas_in_text:
            text_groups.append({'pos': nt['pos'], 'vigas': vigas_in_text})

    if not text_groups:
        return {}

    # 2. Calcular Y-bands adaptativas (entre grupos vizinhos)
    text_groups.sort(key=lambda g: g['pos'][1], reverse=True)  # Y decrescente (topo→base)
    ys = [g['pos'][1] for g in text_groups]
    MAX_HALF = 200
    MIN_HALF = 50

    def y_band(i):
        ay = ys[i]
        # upper: 0.95 (mais generoso — dims de b ficam acima do anchor no FV obliquo)
        # lower: 0.48 (conservador — evita contaminar grupo abaixo)
        half_up   = min(MAX_HALF, (ys[i-1] - ay) * 0.95) if i > 0          else MAX_HALF
        half_down = min(MAX_HALF, (ay - ys[i+1]) * 0.48) if i < len(ys) - 1 else MAX_HALF
        return ay - max(MIN_HALF, half_down), ay + max(MIN_HALF, half_up)

    # 3. Para cada grupo, extrair dims no X-band [anchor_x, anchor_x+3000] × Y-band
    vigas_fv = {}
    for idx, grp in enumerate(text_groups):
        ax, ay = grp['pos']
        y_lo, y_hi = y_band(idx)
        x_lo = ax          # forma sempre à direita do label
        x_hi = ax + 3000

        h_dims, small_h, small_v, v_candidates = [], [], [], []
        for d in cota_dims:
            cx, cy = d['center']
            if x_lo <= cx <= x_hi and y_lo <= cy <= y_hi:
                if d['orient'] == 'H':
                    h_dims.append(d['meas'])
                    # b no FV é sempre orient=H (projeção oblíqua ≈45°)
                    # range 8-35: exclui sarrafos empilhados (≥36) e noise (<8)
                    if 8 <= d['meas'] <= 35:
                        small_h.append((d['meas'], cx))  # (valor, cx para ordenação)
                else:  # orient == 'V'
                    # Fallback: algumas obras mostram b como dim vertical (ex: 1PAV)
                    # range 8-80: mais amplo para capturar vigas largas (b=60cm)
                    if 8 <= d['meas'] <= 80:
                        small_v.append((d['meas'], cx))
                    # Candidatos para h_fv: V-dims em 25-120cm (altura estrutural da seção)
                    if 25 <= d['meas'] <= 120:
                        v_candidates.append(d['meas'])

        h_sorted = sorted(h_dims, reverse=True)
        comprimento_total = h_sorted[0] if h_sorted else 0

        # b = menor H dim em range 8-35 (leftmost em caso de empate)
        # Fallback: se nenhum small_h, usar menor V dim em 8-80 (vigas com proj vertical)
        small_h_sorted = sorted(small_h, key=lambda s: (s[0], s[1]))  # menor val, depois leftmost
        if small_h_sorted:
            b = round(small_h_sorted[0][0], 1)
        elif small_v:
            small_v_sorted = sorted(small_v, key=lambda s: (s[0], s[1]))
            b = round(small_v_sorted[0][0], 1)
        else:
            b = 0

        # Fallback b — banda Y estendida ±2000 (apenas quando b=0 após passe principal)
        # Alguns DXFs (ex: TREINO_5 500-FV) posicionam as dims de b ~900 unidades
        # acima do anchor NOMENCLATURA, fora do MAX_HALF=200 normal.
        # Seguro porque: só ativa quando b=0, usa range [8-35] restrito, só lê V-dims
        # (H-dims nessa faixa seriam comprimentos de paineis ~244cm — fora do range).
        if b == 0:
            B_EXT_BAND = 2000
            ext_small_h, ext_small_v = [], []
            for d in cota_dims:
                cx, cy = d['center']
                if x_lo <= cx <= x_hi and ay - B_EXT_BAND <= cy <= ay + B_EXT_BAND:
                    if cy < y_lo or cy > y_hi:  # fora da banda normal
                        if d['orient'] == 'H' and 8 <= d['meas'] <= 35:
                            ext_small_h.append((d['meas'], cx))
                        elif d['orient'] == 'V' and 8 <= d['meas'] <= 35:
                            ext_small_v.append((d['meas'], cx))
            ext_h_sorted = sorted(ext_small_h, key=lambda s: (s[0], s[1]))
            ext_v_sorted = sorted(ext_small_v, key=lambda s: (s[0], s[1]))
            if ext_h_sorted:
                b = round(ext_h_sorted[0][0], 1)
            elif ext_v_sorted:
                b = round(ext_v_sorted[0][0], 1)

        # Paineis = H dims entre 40 e (total - 5) — excluindo comprimento total
        paineis = sorted([m for m in h_sorted if 40 < m < comprimento_total - 5], reverse=True)

        # h_fv: altura estrutural da seção, extraída de V-dims em 25-120cm.
        # Exclui o próprio b (±3cm) para evitar confundir largura com altura.
        # Usa valor mais comum (mode) dos candidatos restantes.
        h_fv = 0
        if v_candidates:
            h_candidates = [v for v in v_candidates if abs(v - b) > 3]
            if h_candidates:
                from collections import Counter as _Cnt
                h_fv = round(_Cnt([round(v) for v in h_candidates]).most_common(1)[0][0], 1)

        result = {
            'b': b,
            'h_fv': h_fv,
            'comprimento_total': comprimento_total,
            'paineis': paineis,
            'n_paineis': len(paineis),
            '_n_dims_h': len(h_dims),
            '_y_band': [round(y_lo), round(y_hi)],
        }

        for viga in grp['vigas']:
            existing = vigas_fv.get(viga)
            if existing is None:
                vigas_fv[viga] = result
            else:
                # Merge: CONT pode sobrescrever com b=0; preservar o melhor b
                # e o maior comprimento entre os grupos.
                merged_b    = result['b'] if result['b'] > existing['b'] else existing['b']
                merged_comp = max(result['comprimento_total'], existing['comprimento_total'])
                # Paineis: uniao, sem duplicatas exatas
                all_pain = sorted(set(result['paineis'] + existing['paineis']), reverse=True)
                vigas_fv[viga] = {
                    'b':                merged_b,
                    'comprimento_total': merged_comp,
                    'paineis':           all_pain,
                    'n_paineis':         len(all_pain),
                    '_n_dims_h':         result['_n_dims_h'] + existing['_n_dims_h'],
                    '_y_band':           existing['_y_band'],  # manter band principal (primeira)
                }

    return vigas_fv


# ── MERGE ─────────────────────────────────────────────────────────────────────

def merge_vigas(vigas_lv, vigas_fv):
    all_vigas = set(list(vigas_lv.keys()) + list(vigas_fv.keys()))
    fichas = {}
    for viga in sorted(all_vigas, key=lambda x: int(re.search(r'\d+', x).group())):
        ficha = {'nome': viga}
        if viga in vigas_lv:
            for k, v in vigas_lv[viga].items():
                ficha[k] = v
        if viga in vigas_fv:
            ficha['fundo'] = vigas_fv[viga]

        comp_vals, alt_vals, secao_b_vals, secao_h_vals = [], [], [], []
        for side in ('lado_A', 'lado_B'):
            if side in ficha:
                c = ficha[side].get('comprimento_total', 0)
                a = ficha[side].get('altura', 0)
                sb = ficha[side].get('b_secao')
                sh = ficha[side].get('h_secao')
                if c > 0: comp_vals.append(c)
                if a > 0: alt_vals.append(a)
                if sb: secao_b_vals.append(sb)
                if sh: secao_h_vals.append(sh)

        ficha['comprimento_cm'] = max(comp_vals) if comp_vals else (ficha['fundo']['comprimento_total'] if 'fundo' in ficha else 0)
        if alt_vals:
            ficha['altura_cm'] = round(sum(alt_vals)/len(alt_vals), 1)
        else:
            # Fallback: usar h_fv do FV quando LV não tem altura anotada
            h_fv = ficha['fundo']['h_fv'] if 'fundo' in ficha else 0
            ficha['altura_cm'] = float(h_fv) if h_fv else 0

        # b: preferir FV (tem projeção direta de b), fallback para Cota Seção (2x) do LV
        fv_b = ficha['fundo']['b'] if 'fundo' in ficha else 0
        lv_b_secao = min(secao_b_vals) if secao_b_vals else 0
        ficha['b'] = fv_b if fv_b > 0 else lv_b_secao

        # h_secao: dimensão estrutural da seção transversal (mais próxima do TQS)
        # Valor mais comum entre lados (mode) — evita h de seção vizinha menor
        if secao_h_vals:
            from collections import Counter as _Counter
            ficha['h_secao'] = _Counter(secao_h_vals).most_common(1)[0][0]
        else:
            ficha['h_secao'] = 0

        ficha['has_lv'] = viga in vigas_lv
        ficha['has_fv'] = viga in vigas_fv
        fichas[viga] = ficha
    return fichas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lv', required=True)
    parser.add_argument('--fv', default=None, help='Caminho do DXF FV (opcional)')
    parser.add_argument('--output', default='fichas_reverso_VIG.json')
    args = parser.parse_args()

    print(f"LV: {args.lv}")

    # Se FV fornecido, extrair pilar refs para suplementar pool do LV
    fv_pilar_refs = []
    if args.fv:
        fv_pilar_refs = extrair_pilar_refs_fv(args.fv)
        if fv_pilar_refs:
            print(f"  FV pilar refs (pool suplementar LV): {len(fv_pilar_refs)}")

    vigas_lv = extrair_lv(args.lv, extra_pilar_refs=fv_pilar_refs if fv_pilar_refs else None)
    print(f"  -> {len(vigas_lv)} vigas laterais")

    if args.fv:
        print(f"FV: {args.fv}")
        vigas_fv = extrair_fv(args.fv)
        print(f"  -> {len(vigas_fv)} vigas fundo")
    else:
        print("FV: (nao fornecido — apenas LV)")
        vigas_fv = {}

    fichas = merge_vigas(vigas_lv, vigas_fv)

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as fp:
        json.dump(fichas, fp, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"{'VIGA':<8} {'COMP':>6} {'ALT':>5} {'B':>4}  LV  FV  PAINEIS_A")
    print(f"{'='*70}")
    for viga in sorted(fichas, key=lambda x: int(re.search(r'\d+', x).group())):
        f = fichas[viga]
        pa = f.get('lado_A', {}).get('paineis', [])
        ps = '+'.join(str(int(p)) for p in pa[:4]) if pa else '-'
        print(f"  {viga:<6} {f['comprimento_cm']:>6.0f} {f['altura_cm']:>5.1f} {f['b']:>4.0f}  {'Y' if f['has_lv'] else '-':>2}  {'Y' if f['has_fv'] else '-':>2}  {ps}")

    n_lv = sum(1 for f in fichas.values() if f['has_lv'])
    n_fv = sum(1 for f in fichas.values() if f['has_fv'])
    print(f"\nTotal: {len(fichas)} vigas | LV: {n_lv} | FV: {n_fv} | Saida: {args.output}")


if __name__ == '__main__':
    main()
