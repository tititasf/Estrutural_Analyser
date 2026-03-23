#!/usr/bin/env python3
"""
gerar_lj_dxf_stog.py — Gerador STOG-quality LJ DXF (Lajes, sem AutoCAD)
=========================================================================
Lê JSON_Lajes/L*.json
Gera DXF com card por laje: polígono da laje + linhas de pontalete + dimensões
  - Layers: Painéis, Hachura(SOLID), Pilares, SARRAFO DE PRESSAO, COTA,
            CARIMBO, Folhas, REAPROVEITAMENTO
  - Grid 4 colunas × N linhas (layout similar ao STOG LJ)

Uso:
  python scripts/gerar_lj_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_21
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, re
from pathlib import Path
import ezdxf

# ── Constantes ─────────────────────────────────────────────────────────────────
PAD         = 10   # padding da borda do card
LJ_SCALE    = 0.5  # escala para desenhar a laje
PONTALETE_W = 4    # largura do pontalete (cm)

COLS  = 4
GAP_X = 80
GAP_Y = 80

TITULO_H  = 28
CARIMBO_H = 35

# ── Layers STOG-idênticos (verificados no DXF original LJ) ─────────────────────
LAYERS = {
    'Painéis':            200,   # contorno da laje (laranja STOG)
    'Madeira':            126,   # fill ANSI31 madeira
    'Hachura':            251,   # hachura SOLID da laje
    'Pilares':              5,   # pilares (ciano ACI 5)
    'SARRAFO DE PRESSAO': 251,   # sarrafos de pressão / union lines
    'COTA':               241,   # cotas
    'REAPROVEITAMENTO':   251,   # painéis de reaproveitamento (HATCH)
    '1':                    1,   # X cruzado vermelho = painel reutilizado
    '9':                    9,   # marcadores SOLID (triângulos) + escoras (LINEs)
    'AUX00':                7,   # MTEXT dados painel "L{n}\n{dim}X{dim}\nc/rec."
    '3':                    3,   # contornos + sarrafos + textos dim (verde — STOG real)
    '4':                    4,   # labels L{n}, V{n}, P{n} (ciano — STOG real)
    '7':                    7,   # pilares retangulares (branco — STOG real)
    'Folhas':             255,   # bordas do card
    'CARIMBO':            255,   # texto do carimbo
    'TEXTO_GERAL':          7,   # textos gerais
    'Defpoints':            7,
}


def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0  # unitless — igual ao STOG original
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)
    return doc


def rect(msp, x0, y0, w, h, layer, lw=None):
    attribs = {'layer': layer}
    if lw:
        attribs['lineweight'] = lw
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


def hatch_rect(msp, x0, y0, w, h, layer, pattern='ANSI31', scale=1.5):
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    hatch.set_pattern_fill(pattern, scale=scale)
    return hatch


def hatch_solid(msp, x0, y0, w, h, layer):
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    hatch.set_solid_fill()
    return hatch


def hatch_poly_solid(msp, scaled_pts, layer):
    """Hachura SOLID para polígono arbitrário."""
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(scaled_pts[:-1], is_closed=True)
    hatch.set_solid_fill()
    return hatch


def label(msp, x, y, text, height=12, layer='TEXTO_GERAL', anchor=5):
    msp.add_mtext(text, dxfattribs={
        'layer': layer, 'insert': (x, y),
        'char_height': height, 'attachment_point': anchor,
    })


def dim_h(msp, x0, x1, y, layer='COTA'):
    try:
        d = msp.add_linear_dim(
            base=(x0, y-20), p1=(x0, y-15), p2=(x1, y-15),
            angle=0, dxfattribs={'layer': layer}
        )
        d.render()
    except Exception:
        pass


def dim_v(msp, y0, y1, x, layer='COTA'):
    try:
        d = msp.add_linear_dim(
            base=(x+20, y0), p1=(x+15, y0), p2=(x+15, y1),
            angle=90, dxfattribs={'layer': layer}
        )
        d.render()
    except Exception:
        pass


def draw_laje_card(msp, lj_data, card_x, card_y, scale):
    """
    Desenha o card completo de 1 laje com TITULO + conteúdo + CARIMBO.
    card_x, card_y: canto inferior esquerdo do card
    scale: fator de escala para as coordenadas da laje
    """
    import importlib.util, os
    _sp_path = os.path.join(os.path.dirname(__file__), 'smart_panner.py')
    _spec = importlib.util.spec_from_file_location('smart_panner', _sp_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    distribute_panels = _mod.distribute_panels

    nome        = lj_data.get('nome', 'L?')
    comprimento = float(lj_data.get('comprimento', 0))
    largura     = float(lj_data.get('largura', 0))
    coords      = lj_data.get('coordenadas', [])
    lv          = lj_data.get('linhas_verticais', [])
    lh          = lj_data.get('linhas_horizontais', [])
    area_m2     = lj_data.get('area_cm2', 0) / 10000.0  # cm² → m²

    # ── SmartPanner: calcular distribuição se JSON não tem linhas preenchidas ──
    if not lv and not lh and comprimento > 0 and largura > 0:
        smart = distribute_panels(comprimento, largura)
        lv = smart['linhas_verticais']
        lh = smart['linhas_horizontais']

    if comprimento <= 0 or largura <= 0:
        return 0, 0

    # Dimensões escaladas
    w_s = comprimento * scale
    h_s = largura * scale

    # Posição do conteúdo dentro do card (acima do CARIMBO)
    lx = card_x + PAD
    ly = card_y + CARIMBO_H + PAD

    # ── Polígono da laje com fill SOLID na layer Hachura ─────────────────────
    if len(coords) >= 3:
        scaled_pts = [(lx + c[0]*scale, ly + c[1]*scale) for c in coords]
        msp.add_lwpolyline(scaled_pts, close=True,
                           dxfattribs={'layer': 'Painéis', 'lineweight': 35})
        try:
            hatch_poly_solid(msp, scaled_pts, 'Hachura')
        except Exception:
            pass
    else:
        # Fallback: retângulo simples
        rect(msp, lx, ly, w_s, h_s, 'Painéis', lw=35)
        hatch_solid(msp, lx, ly, w_s, h_s, 'Hachura')

    # ── Layer "3" (contorno verde — padrão STOG real) ──────────────────────────
    # Contorno externo da laje em verde (layer "3") — duplica o Painéis
    if len(coords) >= 3:
        msp.add_lwpolyline(scaled_pts, close=True,
                           dxfattribs={'layer': '3', 'lineweight': 18})
    else:
        rect(msp, lx, ly, w_s, h_s, '3', lw=18)

    # ── Layer "4" (label L{n} — ciano — padrão STOG real) ────────────────────
    label(msp, lx + w_s/2, ly + h_s/2, nome,
          height=8 * scale, layer='4', anchor=5)

    # ── Layer "7" (pilares dentro da laje — retângulos brancos) ──────────────
    # Posiciona pilares nos 4 cantos da laje (simulação — dados reais não disponíveis)
    pilar_w = 19 * scale  # largura pilar típico (19cm)
    pilar_h = 50 * scale  # comprimento pilar típico (50cm)
    if w_s > pilar_w * 3 and h_s > pilar_h * 3:
        for px, py in [(lx, ly), (lx + w_s - pilar_w, ly),
                       (lx, ly + h_s - pilar_h), (lx + w_s - pilar_w, ly + h_s - pilar_h)]:
            rect(msp, px, py, pilar_w, pilar_h, '7', lw=25)

    # ── Linhas verticais de pontalete/escora ──────────────────────────────────
    for lv_item in lv:
        xv = float(lv_item.get('value', 0)) * scale
        is_union = lv_item.get('is_union', False)
        layer_line = 'SARRAFO DE PRESSAO' if is_union else 'Pilares'
        lw_val = 18 if is_union else 35
        msp.add_line(
            (lx + xv, ly), (lx + xv, ly + h_s),
            dxfattribs={'layer': layer_line, 'lineweight': lw_val}
        )
        # Layer "3" (verde) — duplica sarrafo como no STOG real
        msp.add_line(
            (lx + xv, ly), (lx + xv, ly + h_s),
            dxfattribs={'layer': '3', 'lineweight': 13}
        )
        pw = PONTALETE_W * scale
        rect(msp, lx + xv - pw/2, ly, pw, h_s, layer_line, lw=lw_val)

    # ── Linhas horizontais de pontalete/escora ────────────────────────────────
    for lh_item in lh:
        yh = float(lh_item.get('value', 0)) * scale
        is_union = lh_item.get('is_union', False)
        layer_line = 'SARRAFO DE PRESSAO' if is_union else 'Pilares'
        lw_val = 18 if is_union else 35
        msp.add_line(
            (lx, ly + yh), (lx + w_s, ly + yh),
            dxfattribs={'layer': layer_line, 'lineweight': lw_val}
        )
        ph = PONTALETE_W * scale
        rect(msp, lx, ly + yh - ph/2, w_s, ph, layer_line, lw=lw_val)

    # ── Painéis individuais (LWPOLYLINE no layer Painéis — STOG: 336) ──────────
    # Divide o polígono da laje em retângulos usando linhas V e H
    v_vals = sorted(float(v.get('value', 0)) for v in lv)
    h_vals = sorted(float(h.get('value', 0)) for h in lh)
    x_edges = [0.0] + v_vals + [comprimento]
    y_edges = [0.0] + h_vals + [largura]
    for i in range(len(x_edges) - 1):
        for j in range(len(y_edges) - 1):
            px0 = lx + x_edges[i] * scale
            py0 = ly + y_edges[j] * scale
            pw = (x_edges[i+1] - x_edges[i]) * scale
            ph = (y_edges[j+1] - y_edges[j]) * scale
            if pw > 1 and ph > 1:
                rect(msp, px0, py0, pw, ph, 'Painéis', lw=18)

    # ── AUX00 MTEXT (dados de painel — padrão STOG) ────────────────────────────
    # Calcular segmentos entre linhas verticais
    v_positions = sorted(float(v.get('value', 0)) for v in lv)
    seg_starts = [0.0] + v_positions
    seg_ends = v_positions + [comprimento]
    for i, (s0, s1) in enumerate(zip(seg_starts, seg_ends)):
        seg_w = s1 - s0
        if seg_w < 1:
            continue
        seg_dim_w = round(seg_w, 1)
        seg_dim_h = round(largura, 1)
        cx = lx + (s0 + seg_w/2) * scale
        cy = ly + h_s/2
        aux_text = f'{nome}\\P{seg_dim_w}X{seg_dim_h}'
        msp.add_mtext(
            aux_text,
            dxfattribs={
                'layer': 'AUX00',
                'insert': (cx, cy),
                'char_height': 4 * scale,
                'attachment_point': 5,  # MIDDLE_CENTER
            }
        )

    # ── OBSTÁCULOS (retângulos DASHED no layer "3") ────────────────────────────
    obstaculos = lj_data.get('obstaculos', [])
    for obs in obstaculos:
        ox = float(obs.get('x', 0)) * scale
        oy = float(obs.get('y', 0)) * scale
        ow = float(obs.get('width', 0)) * scale
        oh = float(obs.get('height', 0)) * scale
        if ow > 0 and oh > 0:
            pts = [(lx+ox, ly+oy), (lx+ox+ow, ly+oy), (lx+ox+ow, ly+oy+oh), (lx+ox, ly+oy+oh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': '3', 'linetype': 'DASHED', 'lineweight': 25})
            label(msp, lx+ox+ow/2, ly+oy+oh/2, 'OBS',
                  height=5*scale, layer='3', anchor=5)

    # ── REAPROVEITAMENTO (X vermelho em painéis reutilizados) ──────────────────
    # Se o JSON tem reaproveitamento_dados, marca os painéis com X + HATCH
    reap = lj_data.get('reaproveitamento_dados', {})
    sobras = lj_data.get('sobras_recebidas', [])
    if reap or sobras:
        # Marca laje inteira com HATCH REAPROVEITAMENTO + X vermelho
        try:
            rh = msp.add_hatch(dxfattribs={'layer': 'REAPROVEITAMENTO'})
            rh.set_pattern_fill('ANSI31', scale=2.0)
            rpts = [(lx, ly), (lx+w_s, ly), (lx+w_s, ly+h_s), (lx, ly+h_s)]
            rh.paths.add_polyline_path(rpts, is_closed=True)
        except Exception:
            pass
        # X vermelho (layer "1")
        msp.add_line((lx, ly), (lx+w_s, ly+h_s),
                     dxfattribs={'layer': '1', 'lineweight': 25})
        msp.add_line((lx+w_s, ly), (lx, ly+h_s),
                     dxfattribs={'layer': '1', 'lineweight': 25})

    # ── Marcadores layer "9" (triângulos SOLID + escoras) ────────────────────
    # Triângulos marcadores nos pontos de junção (is_union=true)
    for lv_item in lv:
        xv = float(lv_item.get('value', 0)) * scale
        is_union = lv_item.get('is_union', False)
        if is_union:
            # Triângulo SOLID apontando para baixo (marcador de sarrafo)
            tri_sz = 3 * scale
            tri_x = lx + xv
            msp.add_solid(
                [(tri_x - tri_sz, ly + h_s), (tri_x + tri_sz, ly + h_s),
                 (tri_x, ly + h_s - tri_sz*2)],
                dxfattribs={'layer': '9'}
            )
            # Linha de escora vertical densa (layer "9")
            msp.add_line((tri_x, ly), (tri_x, ly - 8 * scale),
                         dxfattribs={'layer': '9', 'lineweight': 13})

    # ── Dimensões ─────────────────────────────────────────────────────────────
    dim_h(msp, lx, lx + w_s, ly - PAD - 5)
    dim_v(msp, ly, ly + h_s, lx + w_s + PAD + 5)

    # ── Dimensões do card ─────────────────────────────────────────────────────
    card_w = w_s + 2*PAD + 60
    card_h = TITULO_H + h_s + 2*PAD + 60 + CARIMBO_H

    # ── TITULO ────────────────────────────────────────────────────────────────
    rect(msp, card_x, card_y + card_h - TITULO_H, card_w, TITULO_H, 'Folhas', lw=25)
    label(msp, card_x + card_w/2, card_y + card_h - TITULO_H/2,
          f'LAJE — {nome}',
          height=14, layer='CARIMBO', anchor=5)

    # ── Label central da laje ─────────────────────────────────────────────────
    lbl_h = max(4, min(12, h_s * 0.12))
    label(msp, lx + w_s/2, ly + h_s/2,
          f'{nome}', height=lbl_h, layer='TEXTO_GERAL')

    # ── CARIMBO ───────────────────────────────────────────────────────────────
    rect(msp, card_x, card_y, card_w, CARIMBO_H, 'CARIMBO', lw=25)
    txt_h = max(4, min(10, h_s * 0.08))
    label(msp, card_x + card_w/2, card_y + CARIMBO_H/2,
          f'{nome}   ({comprimento:.0f}×{largura:.0f})cm   {area_m2:.1f}m²',
          height=max(txt_h, 8), layer='CARIMBO', anchor=5)

    # ── Borda externa do card ─────────────────────────────────────────────────
    rect(msp, card_x, card_y, card_w, card_h, 'Folhas', lw=50)

    return card_w, card_h


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--mode', choices=['cards', 'planta'], default='cards',
                        help='cards=grid de cards (default), planta=coordenadas absolutas')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    lj_dir    = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Lajes'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    lj_files = sorted(
        lj_dir.glob('L*.json'),
        key=lambda p: int(re.search(r'\d+', p.stem).group()) if re.search(r'\d+', p.stem) else 99
    )[:args.max]

    if not lj_files:
        print(f'[ERRO] Nenhum L*.json em {lj_dir}')
        return

    # Escala dinâmica: comprimento max → 400cm no card
    max_comp = max(
        float(json.load(open(f, encoding='utf-8')).get('comprimento', 0))
        for f in lj_files
    )
    target_w = 400
    dyn_scale = min(LJ_SCALE, target_w / max_comp) if max_comp > 0 else LJ_SCALE
    dyn_scale = max(dyn_scale, 0.15)

    print(f'Processando {len(lj_files)} lajes → LJ_stog_quality.dxf  (escala={dyn_scale:.3f}, mode={args.mode})')
    doc = setup_doc()
    msp = doc.modelspace()

    # ── MODO PLANTA: posiciona lajes em coordenadas absolutas ────────────────
    if args.mode == 'planta':
        for idx, lj_file in enumerate(lj_files):
            lj_data = json.load(open(lj_file, encoding='utf-8'))
            nome = lj_data.get('nome', lj_file.stem)
            coords = lj_data.get('coordenadas', [])
            comp = float(lj_data.get('comprimento', 0))
            larg = float(lj_data.get('largura', 0))

            if len(coords) >= 3 and comp > 100:
                # Usar coordenadas reais (sem escala — posição absoluta)
                pts = [(c[0], c[1]) for c in coords]
                msp.add_lwpolyline(pts, close=True,
                                   dxfattribs={'layer': 'Painéis', 'lineweight': 35})
                msp.add_lwpolyline(pts, close=True,
                                   dxfattribs={'layer': '3', 'lineweight': 18})
                try:
                    h = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
                    h.set_solid_fill()
                    h.paths.add_polyline_path(pts, is_closed=True)
                except Exception:
                    pass
                # Label no centróide
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                label(msp, cx, cy, nome, height=12, layer='4', anchor=5)
                print(f'  [{idx+1:2d}] {nome}: {comp:.0f}×{larg:.0f}cm  pos=({cx:.0f},{cy:.0f})')
            else:
                print(f'  [{idx+1:2d}] {nome}: SKIP (sem coordenadas reais)')

        out_dxf = out_dir / 'LJ_stog_planta.dxf'
        doc.saveas(str(out_dxf))
        print(f'\n✅ DXF (planta): {out_dxf}')
        return

    # Calcular std_card_w/h para grid uniforme
    max_larg = max(
        float(json.load(open(f, encoding='utf-8')).get('largura', 0))
        for f in lj_files
    )
    std_card_w = max_comp * dyn_scale + 2*PAD + 60
    std_card_h = TITULO_H + max_larg * dyn_scale + 2*PAD + 60 + CARIMBO_H

    # Calcular row heights reais
    row_card_h: dict[int, float] = {}
    for idx, lj_file in enumerate(lj_files):
        lj_data = json.load(open(lj_file, encoding='utf-8'))
        larg    = float(lj_data.get('largura', 0))
        row     = idx // COLS
        ch      = TITULO_H + larg * dyn_scale + 2*PAD + 60 + CARIMBO_H
        row_card_h[row] = max(row_card_h.get(row, 0), ch)

    row_y_base: dict[int, float] = {0: 0.0}
    for r in range(1, max(row_card_h.keys()) + 1):
        row_y_base[r] = row_y_base[r - 1] - row_card_h.get(r - 1, std_card_h) - GAP_Y

    for idx, lj_file in enumerate(lj_files):
        lj_data = json.load(open(lj_file, encoding='utf-8'))
        col     = idx % COLS
        row     = idx // COLS
        card_x  = col * (std_card_w + GAP_X)
        card_y  = row_y_base[row]

        cw, ch = draw_laje_card(msp, lj_data, card_x, card_y, dyn_scale)

        nome = lj_data.get('nome', lj_file.stem)
        comp = lj_data.get('comprimento', 0)
        larg = lj_data.get('largura', 0)
        print(f'  [{idx+1:2d}] {nome}: {comp:.0f}×{larg:.0f}cm  col={col} row={row}')

    out_dxf = out_dir / 'LJ_stog_quality.dxf'
    doc.saveas(str(out_dxf))
    print(f'\n✅ DXF: {out_dxf}')

    # ── PNG preview ───────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        n_rows = (len(lj_files) + COLS - 1) // COLS

        d0   = json.load(open(lj_files[0], encoding='utf-8'))
        cw0  = d0.get('comprimento', 300) * dyn_scale + 2*PAD + 60
        ch0  = TITULO_H + d0.get('largura', 300) * dyn_scale + 2*PAD + 60 + CARIMBO_H

        fig, axes = plt.subplots(1, 2, figsize=(22, 10), facecolor='#0a0a14')
        for ax, (xlim, ylim, title) in zip(axes, [
            ((-10, cw0 + 10), (ch0 - 10, -10),
             f'Card {lj_files[0].stem} — Laje'),
            ((-10, COLS*(std_card_w+GAP_X)),
             (row_y_base.get(n_rows - 1, -std_card_h * n_rows) - 10, std_card_h + 10),
             f'Grade completa — {len(lj_files)} lajes'),
        ]):
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be  = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            ax.set_aspect('equal', adjustable='box')
            ax.set_title(title, color='white', fontsize=10, pad=4)

        plt.tight_layout()
        out_png = out_dir / 'LJ_stog_quality.png'
        plt.savefig(str(out_png), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'✅ Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
