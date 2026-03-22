#!/usr/bin/env python3
"""
gerar_fv_dxf_stog.py — Gerador STOG-quality FV DXF (Vigas Fundo, sem AutoCAD)
===============================================================================
Layout idêntico ao STOG FV original (engenharia reversa dos DXFs):
  - Cada painel = LWPOLYLINE individual (sem fill — só outline)
  - Painéis adjacentes de uma viga = gap 0 (tocando)
  - Gap entre vigas na mesma fileira ≈ 27 cm
  - NOMENCLATURA 9 cm acima do topo da viga ("V22.C")
  - Dimensões COTA 37 cm abaixo do fundo (painéis individuais)
  - Cota total viga 69 cm abaixo do fundo
  - Cota b vertical 28 cm à direita da viga
  - IDs de painel (layer '5') centralizados DENTRO de cada painel
  - Fileiras agrupadas por b decrescente, max 1250 cm por fileira
  - Gap entre fileiras ≈ 95 cm (do topo da inferior ao fundo da superior)
  - 2 blocos Folhas 1485×1050 no topo (identicos ao STOG)

Uso:
  python scripts/gerar_fv_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_21
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, re
from pathlib import Path
import ezdxf

# ── Constantes (calibradas nos DXFs STOG) ──────────────────────────────────
GAP_VIGAS       = 47     # gap entre vigas na mesma fileira (cm) [+20 sobre original 27]
GAP_ROW         = 115    # gap viga_top_inferior → viga_bottom_superior (cm) [+20 sobre original 95]
NOM_ABOVE       = 9      # y = viga_top + NOM_ABOVE para NOMENCLATURA
DIM_BELOW       = 37     # y = viga_bottom - DIM_BELOW para cotas de painéis individuais (calibrado STOG)
DIM_TOTAL_BELOW = 69     # y = viga_bottom - DIM_TOTAL_BELOW para cota total da viga (STOG: 68.7)
DIM_B_RIGHT     = 28     # x = viga_right + DIM_B_RIGHT para cota b vertical (STOG: ~28)
NOM_H           = 16.5   # altura texto NOMENCLATURA
PID_H           = 12.0   # altura texto panel-ID (layer '5') — centralizado dentro do painel

# ── Distribuição inteligente de painéis (eng. reversa STOG) ───────────────────
# NIK SUNSET: 244cm = painel duplo padrão (380 ocorrências vs 53 de 122)
# Algoritmo: preenche com 244, último painel = resto (min 30cm)
# Se resto < PAINEL_MIN → agrega no painel anterior
PAINEL_MODULO   = 244    # largura do painel duplo padrão STOG (cm)
PAINEL_MODULO_H = 122    # metade — painel simples STOG (cm)
PAINEL_MIN      = 30     # largura mínima de painel (abaixo → agrega no anterior)
MAX_ROW_W       = 1250   # largura máxima por fileira (cm)
CARD_W          = 1485
CARD_H          = 1050
CARD_IN_DX      = 75
CARD_IN_DY      = 40
CARD_GAP        = 100    # gap entre os 2 cards
CARD_Y_GAP      = 200    # gap entre topo das vigas e fundo dos cards
SARR_LAYER      = 'SARR_2.2x7'   # layer das linhas de sarrafo interno
SARR_MAX_GAP    = 21     # gap máximo entre faixas de sarrafo (cm)

# ── Layers STOG-idênticos ───────────────────────────────────────────────────
LAYERS = {
    'Painéis':              200,
    'COTA':                 241,
    'NOMENCLATURA':           7,
    '5':                      5,
    'Folhas':               255,
    'CARIMBO':              255,
    'fundo':                100,
    'Madeira':              126,
    'SARRAFO DE PRESSAO':   251,
    'SARR_2.2x7':            40,
    'SARR_EDITAR':          141,
    'Perfil Metálico':      224,
    'REAPROVEITAMENTO':     251,
    'Demarcação 1':         251,
    'Demarcação 2':         254,
    'Hachura':              251,
    'Escoras':              224,
    'Defpoints':              7,
    '0':                      7,
}


def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # ── Dimstyle PAINEL (idêntico ao STOG NIK SUNSET) ─────────────────────
    # Engenharia reversa: _Oblique ticks, cor=4 (cyan), texto acima da linha
    if 'PAINEL' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL')
    else:
        ds = doc.dimstyles.get('PAINEL')
    ds.set_arrows('OBLIQUE', 'OBLIQUE')     # traço oblíquo (não seta) — idêntico ao _Oblique do STOG
    ds.dxf.dimasz  = 3.0    # tamanho do tick
    ds.dxf.dimtxt  = 10.0   # altura do texto
    ds.dxf.dimgap  = 3.0    # gap texto ↔ linha
    ds.dxf.dimexe  = 3.0    # extensão acima da dim line
    ds.dxf.dimexo  = 3.0    # offset da linha de extensão
    ds.dxf.dimclrd = 4      # cor linha de cota (cyan ACI 4)
    ds.dxf.dimclrt = 240    # cor texto
    ds.dxf.dimclre = 4      # cor linhas de extensão
    ds.dxf.dimtad  = 1      # texto ACIMA da linha
    ds.dxf.dimtih  = 0      # texto segue ângulo da dim

    return doc


def panel_poly(msp, x0, y0, w, h):
    """Desenha um painel como LWPOLYLINE (outline, sem fill) na layer Painéis."""
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'Painéis', 'lineweight': -1})


def _sarr_h_offsets(b):
    """Calcula offsets Y das linhas horizontais SARR dado o b da viga (cm).
    Engenharia reversa: b=14→[5,9], b=19→[7,12], b=24→[7,17],
                        b=45→[7,19,26,38], b=100→[7,23,30,46,53,69,76,93]
    """
    sarr_h = 7 if b >= 19 else 5
    n_interior = max(0, int((b - 2 * sarr_h) / (SARR_MAX_GAP + sarr_h)))
    n_gaps     = n_interior + 1
    gap_size   = (b - (n_interior + 2) * sarr_h) / n_gaps

    offsets = [sarr_h]
    for _ in range(n_interior):
        offsets.append(offsets[-1] + gap_size)    # fundo do sarrafo interior
        offsets.append(offsets[-1] + sarr_h)      # topo do sarrafo interior
    offsets.append(b - sarr_h)                    # fundo do sarrafo superior
    return offsets


def draw_sarr(msp, x0, y0, b, total_width):
    """Desenha as linhas SARR_2.2x7 (sarrafo interno) dentro da viga.
    Geometria calibrada nos DXFs STOG ALIMONTI 1 PAV FV:
      - Linhas verticais com inset sarr_h em cada borda lateral
      - Linhas horizontais nos offsets do padrão de sarrafo
    """
    sarr_h = 7 if b >= 19 else 5
    xl = x0 + sarr_h
    xr = x0 + total_width - sarr_h
    if xr <= xl:
        return
    layer = SARR_LAYER
    # Verticais nas bordas laterais
    msp.add_line((xl, y0), (xl, y0 + b), dxfattribs={'layer': layer})
    msp.add_line((xr, y0), (xr, y0 + b), dxfattribs={'layer': layer})
    # Horizontais nas faixas de sarrafo
    for offset in _sarr_h_offsets(b):
        msp.add_line((xl, y0 + offset), (xr, y0 + offset), dxfattribs={'layer': layer})


def draw_escoras(msp, x0, y0, comprimento):
    """Desenha escoras (support legs) como círculos abaixo da viga FV.
    Posição: y0 - 15 (abaixo do fundo da viga).
    Distribuição: uma em cada extremidade (x0+7, x0+L-7) + intermediárias a cada ~100cm.
    """
    ESCORA_R = 3        # raio do círculo (cm)
    ESCORA_Y = y0 - 15  # 15cm abaixo do fundo da viga
    INSET = 7           # recuo das extremidades (cm)
    SPACING = 100       # espaçamento máximo entre escoras (cm)

    x_start = x0 + INSET
    x_end = x0 + comprimento - INSET
    if x_end <= x_start:
        # Viga muito curta — uma escora no centro
        msp.add_circle((x0 + comprimento / 2, ESCORA_Y), ESCORA_R,
                        dxfattribs={'layer': 'Escoras'})
        return

    # Calcular posições: extremidades + intermediárias
    span = x_end - x_start
    n_intervals = max(1, round(span / SPACING))
    step = span / n_intervals

    for i in range(n_intervals + 1):
        cx = x_start + i * step
        msp.add_circle((cx, ESCORA_Y), ESCORA_R, dxfattribs={'layer': 'Escoras'})


def compute_panels(comprimento):
    """Distribui comprimento em painéis STOG padrão (engenharia reversa NIK SUNSET).
    Padrão detectado: módulo 244cm (painel duplo) domina com 380 ocorrências.
    Regras:
      - Se comprimento <= PAINEL_MODULO: 1 painel = comprimento
      - Caso contrário: n painéis de 244 + resto
      - Se resto < PAINEL_MIN: agrega no último painel de 244 → (244+resto)
    Retorna lista de larguras (float).
    """
    L = float(comprimento)
    if L <= 0:
        return []
    if L <= PAINEL_MODULO:
        return [L]
    n_full = int(L // PAINEL_MODULO)
    rem = L - n_full * PAINEL_MODULO
    if rem < 0.5:
        return [float(PAINEL_MODULO)] * n_full
    elif rem < PAINEL_MIN:
        # Resto muito pequeno: agrega no último painel completo
        return [float(PAINEL_MODULO)] * (n_full - 1) + [float(PAINEL_MODULO) + rem]
    else:
        return [float(PAINEL_MODULO)] * n_full + [rem]


def add_text(msp, x, y, text, height, layer, halign=0, valign=0):
    """Adiciona texto. halign: 0=esq, 1=centro, 2=dir. valign: 0=base, 2=meio."""
    attribs = {'insert': (x, y), 'height': height, 'layer': layer}
    if halign or valign:
        attribs['halign'] = halign
        attribs['valign'] = valign
        attribs['align_point'] = (x, y)
    msp.add_text(text, dxfattribs=attribs)


def dim_panel(msp, x0, x1, y_base):
    """Cota horizontal individual de painel — 1º nível (y_base − DIM_BELOW)."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_BELOW),
            p1=(x0, y_base),
            p2=(x1, y_base),
            angle=0,
            dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_viga_total(msp, x0, x1, y_base):
    """Cota horizontal total da viga — 2º nível (y_base − DIM_TOTAL_BELOW).
    Engenharia reversa STOG NIK SUNSET: V22 base_y=2094.1 → offset=68.7cm.
    """
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_TOTAL_BELOW),
            p1=(x0, y_base),
            p2=(x1, y_base),
            angle=0,
            dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_viga_b(msp, x_right, y0, b):
    """Cota vertical do b da viga — lado direito (x_right + DIM_B_RIGHT).
    Engenharia reversa STOG NIK SUNSET: defpoint offset ≈ +28cm à direita.
    """
    if b <= 0:
        return
    try:
        x_base = x_right + DIM_B_RIGHT
        d = msp.add_linear_dim(
            base=(x_base, y0),
            p1=(x_right, y0),
            p2=(x_right, y0 + b),
            angle=90,
            dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def draw_viga(msp, x0, y0, panels_json, viga_b, viga_nome):
    """
    Desenha uma viga fundo a partir de x0, y0 (canto inf-esq do 1º painel).
    panels_json: lista de dicts com 'width' (JSON original — comprimento preservado).
    Aplica distribuição inteligente STOG (módulo 244cm) sobre o comprimento total.
    Retorna comprimento total da viga.
    """
    comprimento = sum(float(p.get('width', 0)) for p in panels_json)
    if comprimento <= 0 or viga_b <= 0:
        return comprimento

    # ── Distribuição inteligente de painéis (STOG 244cm) ──────────────────
    panel_widths = compute_panels(comprimento)

    # ── Painéis individuais (outline) + Reaproveitamento hatch ─────────────
    x_cur = x0
    for pw in panel_widths:
        panel_poly(msp, x_cur, y0, pw, viga_b)
        # Reaproveitamento hatch (ANSI31 escala 1.0) — padrão STOG
        rpts = [(x_cur, y0), (x_cur+pw, y0), (x_cur+pw, y0+viga_b), (x_cur, y0+viga_b)]
        rh = msp.add_hatch(dxfattribs={'layer': 'REAPROVEITAMENTO'})
        rh.set_pattern_fill('ANSI31', scale=1.0)
        rh.paths.add_polyline_path(rpts, is_closed=True)
        x_cur += pw

    # ── Linhas SARR_2.2x7 (sarrafo interno) ───────────────────────────────
    draw_sarr(msp, x0, y0, viga_b, comprimento)

    # ── Escoras (support legs) abaixo da viga ────────────────────────────
    draw_escoras(msp, x0, y0, comprimento)

    # ── NOMENCLATURA acima do topo da viga ────────────────────────────────
    add_text(msp, x0 + 3, y0 + viga_b + NOM_ABOVE, f'{viga_nome}.C', NOM_H, 'NOMENCLATURA')

    # ── IDs de painel DENTRO de cada painel (centralizados) ───────────────
    x_cur = x0
    for i, pw in enumerate(panel_widths):
        cx = x_cur + pw / 2          # centro X do painel
        cy = y0 + viga_b / 2         # centro Y do painel (meio da altura b)
        add_text(msp, cx, cy, str(i + 1), PID_H, '5', halign=1, valign=2)
        x_cur += pw

    # ── Cotas individuais de painéis — 1º nível ───────────────────────────
    x_cur = x0
    for pw in panel_widths:
        dim_panel(msp, x_cur, x_cur + pw, y0)
        x_cur += pw

    # ── Cota total da viga — 2º nível ─────────────────────────────────────
    if len(panel_widths) > 1:
        dim_viga_total(msp, x0, x0 + comprimento, y0)

    # ── Cota b vertical — lado direito ────────────────────────────────────
    dim_viga_b(msp, x0 + comprimento, y0, viga_b)

    return comprimento


def draw_cards(msp, x0, y_bottom, obra_nome='', pav=''):
    """Desenha 2 blocos Folhas 1485×1050 (borda dupla + texto carimbo)."""
    for i in range(2):
        cx = x0 + i * (CARD_W + CARD_GAP)
        cy = y_bottom
        # Borda externa
        pts = [(cx, cy), (cx+CARD_W, cy), (cx+CARD_W, cy+CARD_H), (cx, cy+CARD_H)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 50})
        # Borda interna
        cx2 = cx + CARD_IN_DX; cy2 = cy + CARD_IN_DY
        w2 = CARD_W - 2*CARD_IN_DX; h2 = CARD_H - 2*CARD_IN_DY
        pts2 = [(cx2, cy2), (cx2+w2, cy2), (cx2+w2, cy2+h2), (cx2, cy2+h2)]
        msp.add_lwpolyline(pts2, close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 25})
        # Linha carimbo
        cab_h = 80
        msp.add_line((cx, cy+cab_h), (cx+CARD_W, cy+cab_h),
                     dxfattribs={'layer': 'CARIMBO', 'lineweight': 35})
        # Textos
        mid_x = cx + CARD_W/2
        for txt, ty, th in [
            ('NOVA SISTEMAS CONSTRUTIVOS', cy+cab_h/2+30, 14),
            ('STOG',                       cy+cab_h/2+12, 12),
            (obra_nome,                    cy+cab_h/2-5,  12),
            (pav,                          cy+cab_h/2-22, 12),
            ('FUNDO DE VIGAS',             cy+cab_h/2-39, 14),
        ]:
            msp.add_text(txt, dxfattribs={'insert': (mid_x, ty), 'height': th, 'layer': 'CARIMBO'})
        # Número da folha
        msp.add_text(str(i+1), dxfattribs={
            'insert': (cx+CARD_W-60, cy+cab_h/2), 'height': 40, 'layer': 'CARIMBO'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max',  type=int, default=999)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    fv_dir    = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Fundo'
    vs_path   = obra_path / 'Fase-4_Sincronizacao' / 'vigas_salvas.json'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    vigas_salvas = {}
    if vs_path.exists():
        vigas_salvas = json.load(open(vs_path, encoding='utf-8'))

    fv_files = sorted(
        fv_dir.glob('V*_fundo.json'),
        key=lambda p: int(re.search(r'\d+', p.stem).group())
    )[:args.max]

    if not fv_files:
        print(f'[ERRO] Nenhum V*_fundo.json em {fv_dir}'); return

    # ── Carregar vigas ────────────────────────────────────────────────────────
    vigas = []
    for f in fv_files:
        d      = json.load(open(f, encoding='utf-8'))
        vname  = re.sub(r'_fundo', '', f.stem, flags=re.IGNORECASE)
        viga_b = float(vigas_salvas.get(vname, {}).get('b', d.get('total_width', 14)))
        panels = d.get('panels', [])
        comp   = sum(float(p.get('width', 0)) for p in panels)
        if comp > 0 and viga_b > 0:
            vigas.append({'nome': vname, 'b': viga_b, 'comp': comp, 'panels': panels})

    # ── Ordenar e empacotar em fileiras ──────────────────────────────────────
    vigas.sort(key=lambda v: (-v['b'], -v['comp']))

    rows = []
    cur_row, cur_w = [], 0.0
    for v in vigas:
        need = v['comp'] + (GAP_VIGAS if cur_row else 0)
        if cur_row and cur_w + need > MAX_ROW_W:
            rows.append(cur_row); cur_row = [v]; cur_w = v['comp']
        else:
            cur_row.append(v); cur_w += need
    if cur_row:
        rows.append(cur_row)

    print(f'Processando {len(vigas)} vigas → {len(rows)} fileiras')

    doc = setup_doc()
    msp = doc.modelspace()

    # ── Desenhar vigas ────────────────────────────────────────────────────────
    # Fileira 0: topo → y_cursor começa em 0 e decresce (vigas crescem para baixo)
    # Convenção: cards acima de y=CARD_Y_GAP; vigas abaixo de y=0

    y_cursor = 0.0       # fundo da primeira fileira (bottom do row mais acima)
    y_min    = 0.0

    for row_idx, row in enumerate(rows):
        max_b = max(v['b'] for v in row)
        # y_top desta fileira = y_cursor (vai "para cima" = maior y)
        # y_bottom = y_cursor - max_b
        y_row_bottom = y_cursor - max_b

        x_cursor = 0.0
        for v in row:
            # Desenhar alinhando topo de cada viga ao topo da fileira
            # (vigas com b menor ficam alinhadas ao topo)
            vy0 = y_row_bottom + (max_b - v['b'])   # alinha topo
            draw_viga(msp, x_cursor, vy0, v['panels'], v['b'], v['nome'])
            print(f'  {v["nome"]:8s}: {v["comp"]:.0f}x{v["b"]:.0f}cm  row={row_idx}')
            x_cursor += v['comp'] + GAP_VIGAS

        y_min = y_row_bottom - DIM_TOTAL_BELOW - 20  # espaço abaixo para cotas (IDs agora internos)
        y_cursor = y_row_bottom - GAP_ROW       # próxima fileira abaixo

    # ── 2 cards Folhas acima das vigas ────────────────────────────────────────
    card_y = CARD_Y_GAP          # fundo dos cards
    obra_nome = obra_path.name.replace('_', ' ')
    draw_cards(msp, 0, card_y, obra_nome=obra_nome)

    out_dxf = out_dir / 'FV_stog_quality.dxf'
    doc.saveas(str(out_dxf))
    print(f'\nDXF: {out_dxf}')

    # ── PNG preview ───────────────────────────────────────────────────────────
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        first_row_b = max(v['b'] for v in rows[0]) if rows else 60
        x_max = max(sum(v['comp'] for v in r) + GAP_VIGAS*(len(r)-1) for r in rows) + 100
        y_all_max = CARD_Y_GAP + CARD_H + 50

        fig, axes = plt.subplots(1, 2, figsize=(26, 10), facecolor='#0a0a14')
        views = [
            # Primeiras 5 fileiras
            ((-30, min(1400, x_max)),
             (-first_row_b - GAP_ROW*5 - 100, 60),
             f'Fileiras 0..4 — detalhe'),
            # Vista completa
            ((-30, max(x_max, CARD_W*2+CARD_GAP+50)),
             (y_min - 50, y_all_max),
             f'Vista completa — {len(vigas)} vigas | {len(rows)} fileiras'),
        ]
        for ax, (xlim, ylim, title) in zip(axes, views):
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be  = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(*xlim); ax.set_ylim(*ylim)
            ax.set_aspect('equal', adjustable='box')
            ax.set_title(title, color='white', fontsize=9, pad=4)

        plt.tight_layout()
        out_png = out_dir / 'FV_stog_quality.png'
        plt.savefig(str(out_png), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
