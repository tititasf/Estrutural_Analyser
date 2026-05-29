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

def extrair_lv(lv_path):
    doc = ezdxf.readfile(lv_path)
    msp = doc.modelspace()

    # 1. Textos de secao (Texto Secao layer OU NOMENCLATURA)
    # TREINO_1+: layer 'Texto Seção' ou similar (contém 'Texto' e 'Se')
    # TREINO_5+: layer 'NOMENCLATURA' (contem V201.A, V201.B etc.)
    secao_texts = []
    for e in msp:
        if e.dxftype() != 'TEXT': continue
        layer = str(e.dxf.layer)
        is_secao_layer = ('Texto' in layer and 'Se' in layer) or layer == 'NOMENCLATURA'
        if not is_secao_layer: continue
        txt = e.dxf.text.strip()
        m = re.match(r'^(CONT\.\s*)?V[F]?(\d+)\.([AB])$', txt)
        if m:
            secao_texts.append({
                'viga': f'V{int(m.group(2))}',
                'side': m.group(3),
                'is_cont': bool(m.group(1)),
                'pos': (float(e.dxf.insert[0]), float(e.dxf.insert[1])),
                'text': txt,
            })

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

        # Pilares nas extremidades
        nearby_pilares = [p for p in pilar_refs
                          if bbox_xmin-400 <= p['pos'][0] <= bbox_xmax+400
                          and bbox_ymin-400 <= p['pos'][1] <= bbox_ymax+400]
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
    cota_dims = []
    for e in msp:
        if e.dxftype() == 'DIMENSION' and e.dxf.layer == 'COTA':
            info = get_dim_info(e)
            if info: cota_dims.append(info)

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

        h_dims, small_h, small_v = [], [], []
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

        # Paineis = H dims entre 40 e (total - 5) — excluindo comprimento total
        paineis = sorted([m for m in h_sorted if 40 < m < comprimento_total - 5], reverse=True)

        result = {
            'b': b,
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
        ficha['altura_cm'] = round(sum(alt_vals)/len(alt_vals), 1) if alt_vals else 0

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
    vigas_lv = extrair_lv(args.lv)
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
