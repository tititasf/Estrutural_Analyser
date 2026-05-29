#!/usr/bin/env python3
"""
extrair_reverso_laj.py - Extrai fichas de lajes do DXF LJ (engenharia reversa STOG).

v2 — Fix critico:
  Os textos "comp/larg" da layer 3 SAO seccoes de sarrafo (ex: "19/55" = sarrafo 19mm x 55mm),
  NAO dimensoes de forma. As medidas reais dos paineis de forma estao nas entidades DIMENSION
  da layer Paineis.

Estrutura correta do LJ:
  - Layer 4  : TEXT  — nomes das lajes (L1, L2...) e refs de V*/P* (ignorar)
  - Paineis  : DIMENSION — medidas reais dos paineis de forma (usar ESTA)
  - Layer 3  : TEXT "h=N"     — nivel delta em cm
  - Layer 3  : TEXT "-X.XX"   — nivel absoluto offset
  - Layer 3  : TEXT "comp/larg" — SECCAO SARRAFO (ignorar para dimensoes de forma)

Saida: fichas_reverso_LAJ.json
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf, math, re, json, argparse, os
from collections import defaultdict


def dist2d(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def get_dim_info(e):
    """Retorna {'meas': float, 'orient': 'H'|'V', 'center': (x,y),
                'dp': (x1,y1), 'dp2': (x2,y2)} ou None."""
    try:
        v = e.dxf.actual_measurement
        if not v or v <= 0:
            v = None
    except Exception:
        v = None

    try:
        dp  = (float(e.dxf.defpoint[0]),  float(e.dxf.defpoint[1]))
        dp2 = (float(e.dxf.defpoint2[0]), float(e.dxf.defpoint2[1]))
        dx = abs(dp[0] - dp2[0])
        dy = abs(dp[1] - dp2[1])
        if v is None:
            raw = math.sqrt(dx * dx + dy * dy)
            v = round(raw, 1) if raw > 0 else None
        if v is None:
            return None
        orient = 'H' if dx > dy else 'V'
        center = ((dp[0] + dp2[0]) / 2, (dp[1] + dp2[1]) / 2)
    except Exception:
        return None

    return {'meas': round(v, 1), 'orient': orient, 'center': center,
            'dp': dp, 'dp2': dp2}


def _get_text_and_pos(e):
    """Return (plain_text, (x, y)) for TEXT or MTEXT entity, or None on error."""
    try:
        if e.dxftype() == 'TEXT':
            return e.dxf.text.strip(), (float(e.dxf.insert[0]), float(e.dxf.insert[1]))
        elif e.dxftype() == 'MTEXT':
            try:
                txt = e.plain_text().strip()
            except Exception:
                txt = e.dxf.text.strip()
            # Strip MTEXT paragraph/line breaks
            txt = txt.replace('\n', ' ').replace('\r', '').strip()
            return txt, (float(e.dxf.insert[0]), float(e.dxf.insert[1]))
    except Exception:
        pass
    return None, None


def extrair_lajes(lj_path, verbose=False):
    """Extract slab data from LJ DXF using Paineis DIMENSION entities."""
    doc = ezdxf.readfile(lj_path)
    msp = doc.modelspace()

    # ── 1. Laje name anchors — auto-detect layer (STOG: '4'/'44', structural: 'L-N'/'ES-LAJE-NOME') ──
    # Collect all candidate layers that contain TEXT or MTEXT matching 'L\d+' pattern
    laje_nome_candidates = defaultdict(list)
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        txt, pos = _get_text_and_pos(e)
        if txt is None:
            continue
        m = re.match(r'^L(\d+)$', txt)
        if m:
            laje_nome_candidates[e.dxf.layer].append({
                'nome': txt,
                'num':  int(m.group(1)),
                'pos':  pos,
            })
    # Pick the layer with the most matching names (typically '4', '44', or 'L-N')
    if laje_nome_candidates:
        best_layer = max(laje_nome_candidates, key=lambda k: len(laje_nome_candidates[k]))
    else:
        best_layer = '4'
    laje_names = laje_nome_candidates.get(best_layer, [])

    # ── 2. Paineis DIMENSION entities (medidas reais dos paineis) ─────────────
    # Fallback: COBERTURA-style DXFs colocam DIMENSIONs na layer COTA (nao Paineis)
    paineis_dims = []
    for e in msp:
        if e.dxftype() == 'DIMENSION' and 'Pain' in str(e.dxf.layer):
            info = get_dim_info(e)
            if info and info['meas'] > 0:
                paineis_dims.append(info)

    dim_source = 'Paineis'
    if not paineis_dims:
        # Fallback 1: tentar layer COTA (ex: COBERTURA)
        for e in msp:
            if e.dxftype() == 'DIMENSION' and e.dxf.layer == 'COTA':
                info = get_dim_info(e)
                if info and info['meas'] >= 50:  # threshold maior: COTA tem muitos dims estruturais pequenos
                    paineis_dims.append(info)
        if paineis_dims:
            dim_source = 'COTA_fallback'
            if verbose:
                print(f"  COTA fallback: {len(paineis_dims)} dims")
    if not paineis_dims:
        # Fallback 2: layer '0' com threshold >= 60cm (ex: TREINO_8 — DIMENSIONs em layer 0)
        for e in msp:
            if e.dxftype() == 'DIMENSION' and e.dxf.layer == '0':
                info = get_dim_info(e)
                if info and info['meas'] >= 60:
                    paineis_dims.append(info)
        if paineis_dims:
            dim_source = 'layer0_fallback'
            if verbose:
                print(f"  Layer-0 fallback: {len(paineis_dims)} dims")


    # ── 2b. Paineis LINE entities — used as fallback for largura bbox ─────────
    # When max_V dim < V_BBOX_THRESHOLD, the V dims represent individual boards,
    # not total slab width. Use the Y-extent of all Paineis LINEs in the band.
    paineis_lines = []
    for e in msp:
        if e.dxftype() != 'LINE' or 'ain' not in str(e.dxf.layer):
            continue
        try:
            sx, sy = float(e.dxf.start[0]), float(e.dxf.start[1])
            ex, ey = float(e.dxf.end[0]),   float(e.dxf.end[1])
            length = math.sqrt((ex-sx)**2 + (ey-sy)**2)
            if length > 20:  # ignore tiny lines
                paineis_lines.append({
                    'sx': sx, 'sy': sy, 'ex': ex, 'ey': ey,
                    'mcy': (sy+ey)/2, 'mcx': (sx+ex)/2,
                    'length': length,
                })
        except Exception:
            pass

    if verbose:
        from collections import Counter
        vals = sorted(Counter(round(d['meas'], 0) for d in paineis_dims).items())
        print(f"  DIMENSION entities ({dim_source}): {len(paineis_dims)}")
        print(f"  Distribuicao de valores: {vals}")

    # ── 3. h=N nivel TEXT/MTEXT — auto-detect layer ('3', '47', 'L-D', etc.) ──────────────
    # Find the layer that contains 'h=\d+' texts (TEXT or MTEXT)
    nivel_layer_candidates = defaultdict(int)
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        txt, _ = _get_text_and_pos(e)
        if txt and re.match(r'^h=\d+$', txt):
            nivel_layer_candidates[e.dxf.layer] += 1
    nivel_layer = max(nivel_layer_candidates, key=nivel_layer_candidates.get) if nivel_layer_candidates else '3'

    nivel_texts  = []
    offset_texts = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT') or e.dxf.layer != nivel_layer:
            continue
        txt, pos = _get_text_and_pos(e)
        if txt is None:
            continue

        m_h = re.match(r'^h=(\d+)$', txt)
        if m_h:
            nivel_texts.append({'valor': int(m_h.group(1)), 'pos': pos})
            continue

        m_off = re.match(r'^-?\d+\.\d+$', txt)
        if m_off:
            offset_texts.append({'valor': float(txt), 'pos': pos})

    # ── 4. Sort laje names by Y (descending) para bands adaptativas ──────────
    laje_names.sort(key=lambda l: l['pos'][1], reverse=True)
    ys = [l['pos'][1] for l in laje_names]

    MAX_HALF = 600  # unidades DXF = cm
    MIN_HALF = 100

    def y_band(i):
        ay = ys[i]
        half_up   = min(MAX_HALF, (ys[i-1] - ay) * 0.48) if i > 0          else MAX_HALF
        half_down = min(MAX_HALF, (ay - ys[i+1]) * 0.48) if i < len(ys) - 1 else MAX_HALF
        return ay - max(MIN_HALF, half_down), ay + max(MIN_HALF, half_up)

    # ── 5. Agrupar dims por laje ──────────────────────────────────────────────
    NOISE_THRESHOLD = 15  # dims < 15cm = sarrafo/ruido — ignorar

    lajes = {}
    for idx, laje in enumerate(laje_names):
        nome = laje['nome']
        ax, ay = laje['pos']

        # Y-band adaptativa
        if len(ys) > 1:
            y_lo, y_hi = y_band(idx)
        else:
            y_lo, y_hi = ay - MAX_HALF, ay + MAX_HALF

        # X-band: laje se extende para a direita do anchor
        x_lo = ax - 300
        x_hi = ax + 6000

        h_dims = []
        v_dims = []
        for d in paineis_dims:
            cx, cy = d['center']
            if x_lo <= cx <= x_hi and y_lo <= cy <= y_hi:
                if d['meas'] >= NOISE_THRESHOLD:
                    if d['orient'] == 'H':
                        h_dims.append(d['meas'])
                    else:
                        v_dims.append(d['meas'])

        # ── Calculos de comprimento e largura ─────────────────────────────────
        # Estrategia:
        #   comprimento = max(max_H, max_V) — maior dimensao encontrada
        #     → garante que lajes orientadas 90° (ex: max_V=244 > max_H=122)
        #       usem o valor correto como comprimento
        #   largura = min(max_H, max_V) — menor das duas dimensoes principais
        #     → se max_V < V_BBOX_THRESHOLD (boards individuais, nao span total),
        #       usa Y-bbox das LINEs da layer Paineis como proxy de largura total
        V_BBOX_THRESHOLD = 50  # cm — V dims < 50cm = planchas individuais, nao span

        h_sorted = sorted(h_dims, reverse=True)
        v_sorted = sorted(v_dims, reverse=True)

        max_h = h_sorted[0] if h_sorted else 0
        max_v = v_sorted[0] if v_sorted else 0

        if max_h > 0 and max_v > 0:
            comprimento_total = max(max_h, max_v)
            if max_v >= V_BBOX_THRESHOLD:
                largura_total = min(max_h, max_v)
            else:
                # V dims are individual boards — use LINE bbox for total width
                band_ys = [l['sy'] for l in paineis_lines if x_lo <= l['mcx'] <= x_hi and y_lo <= l['mcy'] <= y_hi]
                band_ys += [l['ey'] for l in paineis_lines if x_lo <= l['mcx'] <= x_hi and y_lo <= l['mcy'] <= y_hi]
                if band_ys:
                    largura_total = round(max(band_ys) - min(band_ys), 1)
                else:
                    largura_total = min(max_h, max_v)  # fallback to old behavior
        elif max_h > 0:
            comprimento_total = max_h
            largura_total     = 0
        else:
            comprimento_total = max_v
            largura_total     = 0

        # ── Nivel delta ────────────────────────────────────────────────────────
        nivel_delta = 0
        best_h_dist = 99999
        for nt in nivel_texts:
            d = dist2d(nt['pos'], (ax, ay))
            if d < 1200 and d < best_h_dist:
                best_h_dist = d
                nivel_delta = nt['valor']

        # ── Offset absoluto ───────────────────────────────────────────────────
        offset = 0.0
        best_off_dist = 99999
        for ot in offset_texts:
            d = dist2d(ot['pos'], (ax, ay))
            if d < 1200 and d < best_off_dist:
                best_off_dist = d
                offset = ot['valor']

        # ── Confianca ─────────────────────────────────────────────────────────
        conf = 1.0
        if not h_dims and not v_dims:
            conf -= 0.5
        elif not h_dims or not v_dims:
            conf -= 0.2

        lajes[nome] = {
            'nome':              nome,
            'comprimento_total': comprimento_total,
            'largura_total':     largura_total,
            'nivel_delta':       nivel_delta,
            'offset':            offset,
            'n_paineis':         len(h_dims) + len(v_dims),
            'confidence':        round(conf, 2),
            '_h_dims':           h_sorted,
            '_v_dims':           v_sorted,
            '_y_band':           [round(y_lo), round(y_hi)],
        }

    return lajes


def main():
    parser = argparse.ArgumentParser(
        description='Extrai fichas de lajes do DXF LJ (STOG reverso) v2'
    )
    parser.add_argument('--lj',     required=True, help='Caminho do DXF LJ')
    parser.add_argument('--output', default='fichas_reverso_LAJ.json', help='Saida JSON')
    parser.add_argument('--verbose', action='store_true', help='Mostrar diagnosticos')
    args = parser.parse_args()

    print(f"Lendo LJ: {args.lj}")
    lajes = extrair_lajes(args.lj, verbose=args.verbose)
    print(f"  -> {len(lajes)} lajes extraidas")

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as fp:
        json.dump(lajes, fp, ensure_ascii=False, indent=2)

    # ── Relatorio ──────────────────────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print(f"{'LAJE':<8} {'COMP':>6} {'LARG':>6} {'h=':>4} {'H-DIMS':>25} {'CONF':>5}")
    print(f"{'=' * 72}")
    for nome in sorted(lajes, key=lambda x: int(re.search(r'\d+', x).group())):
        l = lajes[nome]
        h_str  = str(l['nivel_delta']) if l['nivel_delta'] > 0 else '-'
        hd_str = '+'.join(str(int(v)) for v in l['_h_dims'][:6])
        if not hd_str:
            hd_str = '(sem dims H)'
        print(f"  {nome:<6} {l['comprimento_total']:>6.0f} {l['largura_total']:>6.0f}"
              f" {h_str:>4} {hd_str:>25} {l['confidence']:>5.2f}")

    n_ok   = sum(1 for l in lajes.values() if l['comprimento_total'] > 0)
    n_h    = sum(1 for l in lajes.values() if l['nivel_delta'] > 0)
    print(f"\nTotal: {len(lajes)} lajes | Com comprimento: {n_ok} | Com nivel h=: {n_h}")
    print(f"Saida: {args.output}")


if __name__ == '__main__':
    main()
