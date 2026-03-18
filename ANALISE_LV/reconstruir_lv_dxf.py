#!/usr/bin/env python3
"""
reconstruir_lv_dxf.py — Gerador de DXF a partir da ficha v3.

Uso:
  python reconstruir_lv_dxf.py --viga V302
  python reconstruir_lv_dxf.py --viga V302 V303 V304
  python reconstruir_lv_dxf.py --all
  python reconstruir_lv_dxf.py --obra Obra_TREINO_1

Saída: D:/Agente-cad-PYSIDE/ANALISE_LV/reconstructed/{obra}_{viga}.dxf
"""
import sys, io, os, json, re, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json'
CATALOG_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json'
OUT_DIR = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/reconstructed')

# Layers com nomes e cores originais STOG
LAYER_DEFS = {
    'Painéis':              200,
    'CONCRETO':             251,
    'SARR_3.5x7':           81,
    'Madeira':              126,
    'Texto Seção':          7,
    'COTA':                 4,    # cyan — igual às cotas de seção (padrão visual STOG)
    'Cota Seção (2x)':      4,    # cyan — cotas de seção transversal
    'NOMENCLATURA':         7,
    'Hachura':              253,
    'REAPROVEITAMENTO':     251,
    'SARR_2.2x7':           40,
    'SARR_2.2x10':          40,
    'SARR_EDITAR':          141,
    'Sarrafo de Pressão':   40,
    'Escoras':              2,
    'Demarcação 1':         251,  # grade: demarcação de painéis
    'Demarcação 2':         254,  # grade: demarcação de painéis
    'Forcador':             251,  # grade: forcador
    'GARFOS':               7,    # grade: garfos
    'BARRA DE ANCORAGEM':   7,    # grade: ancoragem
    'Perfil Metálico':      251,  # grade: perfis
    'PONTALETE':            2,    # grade: pontalete (amarelo)
    'MEIO_PONT':            2,    # grade: meio pontalete (amarelo)
    # Layers de alta frequência sem cor definida → cores originais STOG
    '0':                    7,    # layer padrão AutoCAD (branco)
    '5':                    3,    # layer STOG genérico (verde)
    'detalhes':             7,    # detalhes (branco)
    'texto':                7,    # texto genérico (branco)
    'TEXTO':                7,    # texto maiúsculo (branco)
    'CARIMBO':              7,    # carimbo/title block (branco)
    'presilha':             2,    # presilha (amarelo)
    'barrote':              126,  # barrote (mesma cor madeira)
    'TENSOR':               2,    # tensor (amarelo)
    'SCO-___-LAJ':          4,    # slab layer (cyan)
    'Sarr 2.2x7':           40,   # variante sarrafo 2.2x7 (amarelo)
    'cotas':                4,    # variante cotas (cyan)
    'Cotas':                4,    # variante cotas maiúscula (cyan)
    'material do compensado': 126, # compensado (madeira)
    'Folhas':               7,    # folhas (branco)
    'TEXTO PILAR':          7,    # texto pilar (branco)
    'CHAPA REAPROV':        251,  # chapa reaproveitamento (cinza)
    'fundo':                253,  # fundo (cinza escuro)
    'HACHURA MADEIRAS':     126,  # hachura madeiras (marrom)
}
# Cor padrão para layers extras do original que não estão em LAYER_DEFS
LAYER_EXTRA_COLOR = 7

# Mapa de variantes conhecidas → nome canônico com acento
LAYER_MAP = {
    'Paineis':        'Painéis',
    'Painis':         'Painéis',
    'TextoSecao':     'Texto Seção',
    'Texto Secao':    'Texto Seção',
    'Texto Se??o':    'Texto Seção',
}

def safe_layer(layer):
    """Retorna o nome canônico do layer (com acento), ou o original se desconhecido."""
    mapped = LAYER_MAP.get(layer)
    if mapped:
        return mapped
    if layer in LAYER_DEFS:
        return layer
    return layer


def ensure_layers(doc):
    for name, color in LAYER_DEFS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def add_lwpoly(msp, vertices, layer, closed=True):
    if not vertices or len(vertices) < 2:
        return
    pts = [(v[0], v[1]) for v in vertices]
    pl = msp.add_lwpolyline(pts, dxfattribs={'layer': layer})
    if closed:
        pl.close(True)


def add_cota_dim(msp, dim):
    """Reconstrói uma DIMENSION como LINE + TEXT simples (sem dependência de dimstyle)."""
    if 'x3' not in dim:
        return  # sem defpoint3 não há como desenhar as duas ext lines
    layer = safe_layer(dim.get('layer', 'Cota Seção (2x)'))
    # Todas as cotas de painel devem aparecer em cyan (Cota Seção 2x = cor 4)
    if layer not in ('COTA', 'Cota Seção (2x)'):
        layer = 'Cota Seção (2x)'

    x2, y2 = dim['x2'], dim['y2']   # defpoint2 — 1ª origem de extensão
    x3, y3 = dim['x3'], dim['y3']   # defpoint3 — 2ª origem de extensão
    x1, y1 = dim['x1'], dim['y1']   # defpoint   — ponto de ref na linha de cota
    actual  = dim['actual']

    dx_meas = abs(x2 - x3)
    dy_meas = abs(y2 - y3)

    if dx_meas >= dy_meas:
        # ── DIMENSÃO HORIZONTAL: linha de cota horizontal ──
        y_dl = y1  # Y da linha de cota
        msp.add_line((min(x2, x3), y_dl), (max(x2, x3), y_dl),
                     dxfattribs={'layer': layer})
        # linhas de extensão: do ponto medido → passa a linha de cota (+5 unid)
        ext = 5
        for xi, yi in [(x2, y2), (x3, y3)]:
            d = -1 if y_dl < yi else 1          # direção da extensão além da cota
            msp.add_line((xi, yi), (xi, y_dl + ext * d),
                         dxfattribs={'layer': layer})
        tx = dim.get('text_x', (x2 + x3) / 2)
        ty = dim.get('text_y', y_dl)
    else:
        # ── DIMENSÃO VERTICAL: linha de cota vertical ──
        x_dl = x1  # X da linha de cota
        msp.add_line((x_dl, min(y2, y3)), (x_dl, max(y2, y3)),
                     dxfattribs={'layer': layer})
        ext = 5
        for xi, yi in [(x2, y2), (x3, y3)]:
            d = -1 if x_dl < xi else 1
            msp.add_line((xi, yi), (x_dl + ext * d, yi),
                         dxfattribs={'layer': layer})
        tx = dim.get('text_x', x_dl)
        ty = dim.get('text_y', (y2 + y3) / 2)

    msp.add_text(str(round(actual)), dxfattribs={
        'insert': (tx, ty), 'height': 4, 'layer': layer})


def add_hatch_poly(msp, boundary, layer, pattern, scale):
    """Adiciona hatch com boundary polyline."""
    if len(boundary) < 3:
        return
    try:
        h = msp.add_hatch(dxfattribs={'layer': layer})
        if pattern == 'SOLID':
            h.set_solid_fill(color=8)
        else:
            h.set_pattern_fill(pattern, scale=max(scale, 0.01))
        h.paths.add_polyline_path(
            [(p[0], p[1]) for p in boundary], is_closed=True
        )
    except Exception:
        pass


def _x_in_face_range(cx, fa, margin_factor=0.3):
    fx_min = fa.get('face_x_min', 0)
    fx_max = fa.get('face_x_max', 0)
    if fx_min == fx_max == 0:
        return True
    # margem pequena: inclui seção transversal (≈250 u à esq.) mas exclui vigas vizinhas (≈900+ u)
    margin = max((fx_max - fx_min) * margin_factor, 300)
    return (fx_min - margin) <= cx <= (fx_max + margin)


def _y_in_face_range(cy, fa, margin=1400):
    """Verifica se um centroide Y está dentro do range da face_a (±margin).
    Margem padrão 1400u: acomoda face_b (~500u abaixo) + seção (~800u abaixo) com folga.
    """
    fy_min = fa.get('y_min')
    fy_max = fa.get('y_max')
    if fy_min is None or fy_max is None or fy_max <= fy_min:
        return True  # sem bounds: não filtrar
    face_h = fy_max - fy_min
    y_margin = max(face_h * 3.0, margin)
    return (fy_min - y_margin) <= cy <= (fy_max + y_margin)


def _filter_polys(polys, fa):
    out = []
    for p in polys:
        verts = p.get('vertices', [])
        if not verts:
            out.append(p); continue
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        if _x_in_face_range(cx, fa) and _y_in_face_range(cy, fa):
            out.append(p)
    return out


def _filter_hatches(hatches, fa):
    out = []
    for h in hatches:
        bps = h.get('boundary_polys', [])
        if not bps or not bps[0]:
            out.append(h); continue
        all_pts = [pt for bp in bps for pt in bp]
        cx = sum(pt[0] for pt in all_pts) / len(all_pts)
        cy = sum(pt[1] for pt in all_pts) / len(all_pts)
        if _x_in_face_range(cx, fa) and _y_in_face_range(cy, fa):
            out.append(h)
    return out


def reconstruct_viga(msp, viga_data):
    """Reconstrói todas as entidades de uma viga no modelspace."""
    fa = viga_data.get('face_a') or {}
    fb = viga_data.get('face_b') or {}
    sg = viga_data.get('section_geometry') or {}
    aberturas = viga_data.get('aberturas') or []
    continuacoes = viga_data.get('continuacoes') or []
    panel_texts = viga_data.get('panel_texts_positioned') or []
    sarr22_lines      = viga_data.get('sarr22_lines') or []
    panel_polys        = _filter_polys(viga_data.get('panel_polys') or [], fa)
    all_concreto_polys = _filter_polys(viga_data.get('all_concreto_polys') or [], fa)
    all_madeira_polys  = _filter_polys(viga_data.get('all_madeira_polys') or [], fa)
    all_sarr35_polys   = _filter_polys(viga_data.get('all_sarr35_polys') or [], fa)
    hatches_data       = _filter_hatches(viga_data.get('hatches_data') or [], fa)

    # ── 1. FACE A: linhas H (de LINEs originais) ────────────────────
    for hl in fa.get('face_hlines', []):
        msp.add_line((hl['x1'], hl['y']), (hl['x2'], hl['y']),
                     dxfattribs={'layer': 'Painéis'})

    # ── 2. FACE A: linhas V ──────────────────────────────────────────
    for vl in fa.get('face_vlines', []):
        msp.add_line((vl['x'], vl['y1']), (vl['x'], vl['y2']),
                     dxfattribs={'layer': 'Painéis'})

    # ── 3. FACE B ────────────────────────────────────────────────────
    for hl in fb.get('face_hlines', []):
        msp.add_line((hl['x1'], hl['y']), (hl['x2'], hl['y']),
                     dxfattribs={'layer': 'Painéis'})
    for vl in fb.get('face_vlines', []):
        msp.add_line((vl['x'], vl['y1']), (vl['x'], vl['y2']),
                     dxfattribs={'layer': 'Painéis'})

    # ── 3b. PAINÉIS LWPOLYLINEs (contornos laje + perfis sarrafo) ───
    for pp in panel_polys:
        if pp.get('vertices'):
            add_lwpoly(msp, pp['vertices'], 'Painéis', closed=pp.get('closed', True))

    # ── 4. CONCRETO: TODOS os polys ──────────────────────────────────
    for cp in all_concreto_polys:
        if cp.get('vertices'):
            add_lwpoly(msp, cp['vertices'], 'CONCRETO', closed=cp.get('closed', True))
    if not all_concreto_polys:  # fallback legado
        sc = sg.get('seccao_concreto')
        if sc and sc.get('vertices'):
            add_lwpoly(msp, sc['vertices'], 'CONCRETO', closed=sc.get('closed', True))

    # ── 5. SARR_3.5x7: TODOS os polys ───────────────────────────────
    for sp in all_sarr35_polys:
        if sp.get('vertices'):
            add_lwpoly(msp, sp['vertices'], 'SARR_3.5x7', closed=sp.get('closed', True))
    if not all_sarr35_polys:
        for sp in sg.get('sarrafos_35x7', []):
            if sp.get('vertices'):
                add_lwpoly(msp, sp['vertices'], 'SARR_3.5x7', closed=sp.get('closed', True))

    # ── 6. MADEIRA: TODOS os polys ───────────────────────────────────
    for mp in all_madeira_polys:
        if mp.get('vertices'):
            add_lwpoly(msp, mp['vertices'], 'Madeira', closed=mp.get('closed', True))
    if not all_madeira_polys:
        for mp in sg.get('barrotes_madeira', []):
            if mp.get('vertices'):
                add_lwpoly(msp, mp['vertices'], 'Madeira', closed=mp.get('closed', True))

    # ── 7. ABERTURAS DE PILAR (CONCRETO polys dentro da face) ───────
    for ab in aberturas:
        if ab.get('subtype') in ('pilar_face_a', 'pilar_face_b', 'pilar'):
            if ab.get('vertices'):
                add_lwpoly(msp, ab['vertices'], 'CONCRETO')
            else:
                xmn, xmx = ab['x_min'], ab['x_max']
                ymn, ymx = ab['y_min'], ab['y_max']
                add_lwpoly(msp, [(xmn,ymn),(xmx,ymn),(xmx,ymx),(xmn,ymx)], 'CONCRETO')

    # ── 8. TÍTULO (TEXT simples — sem block copy para evitar refs quebradas)
    ti = sg.get('titulo_insert')
    if ti:
        msp.add_text(ti.get('titulo', ''), dxfattribs={
            'insert': (ti['x'], ti['y'] + 5), 'height': 8, 'layer': 'Texto Seção'})
        secao = ti.get('secao', '')
        if secao:
            msp.add_text(secao, dxfattribs={
                'insert': (ti['x'], ti['y'] - 10), 'height': 6, 'layer': 'Texto Seção'})

    # ── 9. CONTINUAÇÕES ─────────────────────────────────────────────
    for cont in continuacoes:
        msp.add_text(cont['text'], dxfattribs={
            'insert': (cont['x'], cont['y']), 'height': 5, 'layer': 'Texto Seção'})

    # ── 10. LABELS DE PAINEL ────────────────────────────────────────
    for pt in panel_texts:
        msp.add_text(pt['text'], dxfattribs={
            'insert': (pt['x'], pt['y']), 'height': 5, 'layer': 'NOMENCLATURA'})

    # ── 10b. CONTAGEM DE SARRAFOS ("8 1/2pont", etc.) ───────────────
    for pl in viga_data.get('panel_labels') or []:
        msp.add_text(pl['text'], dxfattribs={
            'insert': (pl['x'], pl['y']), 'height': 5, 'layer': 'NOMENCLATURA'})

    # ── 11. HATCHES ─────────────────────────────────────────────────
    for h in hatches_data:
        pattern = h.get('pattern', 'SOLID')
        layer   = safe_layer(h.get('layer', '0'))
        if layer not in LAYER_DEFS:
            layer = 'Hachura'
        scale = h.get('scale') or 1.0
        for boundary in h.get('boundary_polys', []):
            add_hatch_poly(msp, boundary, layer, pattern, scale)

    # ── 12. COTAS (DIMENSION → LINE + TEXT) ─────────────────────────
    for dim in viga_data.get('cota_dims') or []:
        add_cota_dim(msp, dim)

    # ── 13. SARR_2.2x7 / SARR_EDITAR (marcas de sarrafo nos painéis) ─
    for sl in sarr22_lines:
        layer_orig = sl.get('layer', 'SARR_2.2x7')
        up = layer_orig.upper()
        # normalizar variantes → nome canônico presente em LAYER_DEFS
        if 'EDITAR' in up:
            layer_out = 'SARR_EDITAR'
        elif '2.2X10' in up.replace('.', '').replace(' ', ''):
            layer_out = 'SARR_2.2x10'
        elif '2.2' in layer_orig or 'SARR' in up or 'PRESS' in up:
            layer_out = 'SARR_2.2x7'
        else:
            layer_out = layer_orig
        msp.add_line(
            (sl['x1'], sl['y1']), (sl['x2'], sl['y2']),
            dxfattribs={'layer': layer_out}
        )

    # ── 14. GRADE ENTITIES (Forcador, GARFOS, Escoras, Demarcação, etc.) ─
    grade = viga_data.get('grade_entities') or {}
    for gl in grade.get('grade_lines', []):
        layer = gl.get('layer', 'Forcador')
        if layer not in LAYER_DEFS:
            doc = msp.doc
            if layer not in doc.layers:
                doc.layers.add(layer, color=LAYER_EXTRA_COLOR)
        msp.add_line((gl['x1'], gl['y1']), (gl['x2'], gl['y2']),
                     dxfattribs={'layer': layer})
    for gp in grade.get('grade_polys', []):
        layer = gp.get('layer', 'Forcador')
        if layer not in LAYER_DEFS:
            doc = msp.doc
            if layer not in doc.layers:
                doc.layers.add(layer, color=LAYER_EXTRA_COLOR)
        if gp.get('vertices'):
            add_lwpoly(msp, gp['vertices'], layer, closed=gp.get('closed', True))
    for gh in grade.get('grade_hatches', []):
        layer = gh.get('layer', 'Demarcação 1')
        pattern = 'SOLID' if gh.get('solid') else gh.get('pattern', 'SOLID')
        scale = 1.0
        for boundary in gh.get('boundary_polys', []):
            add_hatch_poly(msp, boundary, layer if layer in LAYER_DEFS else 'Hachura', pattern, scale)
    for gt in grade.get('grade_texts', []):
        layer = gt.get('layer', 'GARFOS')
        msp.add_text(gt.get('text', ''), dxfattribs={
            'insert': (gt['x'], gt['y']), 'height': 4,
            'layer': layer if layer in LAYER_DEFS else 'NOMENCLATURA'})


def reconstruct_all(targets_with_data, out_dir, skip_existing=True):
    """targets_with_data: lista de (obra, viga_name, suffix, vdata)"""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    skipped = 0

    for obra, viga_name, suffix, vdata in targets_with_data:
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', viga_name)
        fname = f'{obra}_{safe_name}{suffix}.dxf'
        out_path = out_dir / fname

        if skip_existing and out_path.exists():
            skipped += 1
            results.append(str(out_path))
            continue

        try:
            doc = ezdxf.new('R2000')   # R2000 = máxima compatibilidade
            ensure_layers(doc)
            msp = doc.modelspace()
            reconstruct_viga(msp, vdata)
            doc.saveas(str(out_path))
            print(f'  {viga_name:35s} → {fname}')
            results.append(str(out_path))
        except Exception as ex:
            print(f'  {viga_name}: ERRO — {ex}')

    if skipped:
        print(f'  ({skipped} já existiam, pulados)')
    return results


def build_targets(params, obra_filter=None, viga_filter=None):
    """Constrói lista (obra, viga_name, suffix, vdata) com sufixo p/ duplicatas."""
    # agrupar params por (obra, viga_name) para detectar duplicatas
    from collections import defaultdict
    groups = defaultdict(list)
    for p in params:
        groups[(p['_obra'], p['viga'])].append(p)

    targets = []
    for (obra, viga_name), instances in groups.items():
        if obra_filter and obra != obra_filter:
            continue
        if viga_filter and viga_name not in viga_filter:
            continue
        if len(instances) == 1:
            targets.append((obra, viga_name, '', instances[0]))
        else:
            for i, inst in enumerate(instances, start=1):
                targets.append((obra, viga_name, f'_{i}', inst))
    return targets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--viga', nargs='+')
    parser.add_argument('--obra')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--overwrite', action='store_true', help='Regerar mesmo se já existe')
    parser.add_argument('--out', default=str(OUT_DIR))
    args = parser.parse_args()

    print('Carregando ficha...')
    with open(PARAMS_FILE, encoding='utf-8') as f:
        params = json.load(f)

    for p in params:
        p['_obra'] = p.get('obra') or 'desconhecida'

    if args.all:
        targets = build_targets(params)
    elif args.obra:
        targets = build_targets(params, obra_filter=args.obra)
    elif args.viga:
        targets = build_targets(params, viga_filter=set(args.viga))
    else:
        parser.print_help()
        return

    out_dir = Path(args.out)
    print(f'\n=== RECONSTRUCAO DXF: {len(targets)} vigas -> {out_dir} ===\n')
    results = reconstruct_all(targets, out_dir,
                              skip_existing=not args.overwrite)
    print(f'\nTotal: {len(results)} DXFs em {out_dir}')


if __name__ == '__main__':
    main()
