#!/usr/bin/env python3
"""
Atlas Lajes -- 15 paginas com todo o pipeline do robo de lajes.
Gera diagramas sinteticos matplotlib que simulam o que o robo desenha no DXF.
Executa: python scripts/gerar_atlas_lajes.py
"""
import sys, math, textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from pathlib import Path

OUT = Path(__file__).parent.parent / 'docs' / 'fichas' / 'atlas_lajes.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)

# -- Paleta ----------------------------------------------------------------
BG      = '#12121f'
PAINEL  = '#e8b84b'
LAJE_C  = '#8be9fd'
TEXTO   = '#f8f8f2'
COTA_C  = '#ffb86c'
GRADE   = '#44475a'
APOIO_C = '#6272a4'
VIGA_C  = '#50fa7b'
GARFO_C = '#ff79c6'
PILAR_C = '#ff7b54'
SARRAFO = '#b8860b'
WARN    = '#ff5555'
VERDE   = '#27ae60'
ARCO_C  = '#bd93f9'

# -- Helpers ----------------------------------------------------------------
def new_fig(title='', subtitle=''):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(0.5, 0.975, title, ha='center', va='top',
                 fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    if subtitle:
        fig.text(0.5, 0.955, subtitle, ha='center', va='top',
                 fontsize=8, color=APOIO_C)
    return fig


def setup(ax, title=''):
    ax.set_facecolor(BG)
    ax.set_aspect('equal')
    ax.axis('off')
    if title:
        ax.set_title(title, color=PAINEL, fontsize=9, fontweight='bold',
                     pad=5, fontfamily='monospace')


def rct(ax, x, y, w, h, fc=PAINEL, ec='white', lw=1.2, alpha=0.9, zorder=2):
    p = mpatches.Rectangle((x, y), w, h, linewidth=lw,
                            edgecolor=ec, facecolor=fc, alpha=alpha, zorder=zorder)
    ax.add_patch(p)
    return p


def lbl(ax, x, y, w, h, txt, fc=TEXTO, fs=8, bold=True):
    ax.text(x + w / 2, y + h / 2, txt, color=fc, fontsize=fs,
            ha='center', va='center',
            fontweight='bold' if bold else 'normal', zorder=5)


def cota(ax, x1, y1, x2, y2, label, fc=COTA_C, fs=7, off=0.25, voff=0):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return
    nx, ny = -dy / L * off, dx / L * off
    ax.annotate('', xy=(x2 + nx, y2 + ny), xytext=(x1 + nx, y1 + ny),
                arrowprops=dict(arrowstyle='<->', color=fc, lw=1.0), zorder=6)
    mx, my = (x1 + x2) / 2 + nx * 1.6 + voff, (y1 + y2) / 2 + ny * 1.6 + voff
    ax.text(mx, my, label, color=fc, fontsize=fs,
            ha='center', va='center', fontweight='bold', zorder=6,
            bbox=dict(facecolor=BG, alpha=0.7, pad=1, edgecolor='none'))


def arrow(ax, x1, y1, x2, y2, label='', fc=COTA_C, fs=6.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=fc, lw=1.1), zorder=6)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my, label, color=fc, fontsize=fs,
                ha='center', va='bottom', fontweight='bold', zorder=6,
                bbox=dict(facecolor=BG, alpha=0.75, pad=1.5, edgecolor='none'))


def rodape(fig, pg, txt):
    fig.text(0.5, 0.012, f'Pagina {pg}/15 | {txt}', ha='center', va='bottom',
             fontsize=6.5, color=APOIO_C, style='italic')


def tag(ax, x, y, txt, fc=LAJE_C, fs=7):
    ax.text(x, y, txt, color=fc, fontsize=fs,
            ha='center', va='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=BG,
                      edgecolor=fc, lw=0.8, alpha=0.9), zorder=7)


def mono_block(ax, x, y, lines, fs=6.5, fc=TEXTO, lh=0.045):
    for i, line in enumerate(lines):
        ax.text(x, y - i * lh, line, color=fc, fontsize=fs,
                fontfamily='monospace', va='top', transform=ax.transAxes, zorder=5)


def draw_laje_contour(ax, x, y, w, h, fc=LAJE_C, lw=2.0):
    """Desenha contorno retangular de laje."""
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=fc, lw=lw, zorder=3)


def draw_grid(ax, x0, y0, w, h, n_cols, n_rows, fc=GRADE, lw=0.8):
    """Desenha grade de pontaletes."""
    step_x = w / n_cols
    step_y = h / n_rows
    for i in range(1, n_cols):
        xi = x0 + i * step_x
        ax.plot([xi, xi], [y0, y0 + h], color=fc, lw=lw, ls='--', zorder=2)
    for j in range(1, n_rows):
        yj = y0 + j * step_y
        ax.plot([x0, x0 + w], [yj, yj], color=fc, lw=lw, ls='--', zorder=2)


def draw_pontaletes(ax, x0, y0, w, h, n_cols, n_rows, sz=0.12):
    """Marca pontaletes como circulos no centro de cada celula."""
    step_x = w / n_cols
    step_y = h / n_rows
    for i in range(n_cols):
        for j in range(n_rows):
            cx = x0 + (i + 0.5) * step_x
            cy = y0 + (j + 0.5) * step_y
            c = plt.Circle((cx, cy), sz, fc=PILAR_C, ec='white', lw=0.5, zorder=4)
            ax.add_patch(c)


# =========================================================================
#  PG 1: CAPA
# =========================================================================
def page_capa(pdf):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.axis('off')

    fig.text(0.5, 0.80, 'ATLAS DE LAJES', ha='center', va='center',
             fontsize=30, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.74, 'Robo Slab  --  Pipeline de Formas e Escoramento',
             ha='center', fontsize=11, color=LAJE_C, fontfamily='monospace')
    fig.text(0.5, 0.70, '15 fichas tecnicas do sistema de lajes',
             ha='center', fontsize=9, color=APOIO_C)

    # Laje estilizada na capa
    ax2 = fig.add_axes([0.18, 0.28, 0.64, 0.35])
    setup(ax2)
    W, H = 10, 7
    draw_laje_contour(ax2, 0, 0, W, H, LAJE_C, 2.5)
    draw_grid(ax2, 0, 0, W, H, 4, 3, GRADE, 1.0)
    draw_pontaletes(ax2, 0, 0, W, H, 4, 3, 0.2)
    # Paineis como retangulos finos sobrepostos
    sx, sy = W / 4, H / 3
    for i in range(4):
        for j in range(3):
            rct(ax2, i * sx + 0.05, j * sy + 0.05, sx - 0.1, sy - 0.1,
                fc=PAINEL, ec=PAINEL, lw=0.6, alpha=0.15)
    tag(ax2, W / 2, H / 2, 'L101', LAJE_C, 14)
    ax2.set_xlim(-1, W + 1)
    ax2.set_ylim(-1, H + 1)

    fig.text(0.5, 0.22, 'Agente-cad-PYSIDE', ha='center', fontsize=9,
             color=APOIO_C, fontfamily='monospace')
    fig.text(0.5, 0.18, 'Motor Fase 4: LAJE_GRID_STEP=122cm | Layer Contorno + Paineis',
             ha='center', fontsize=7, color=GRADE)

    rodape(fig, 1, 'Atlas Lajes v1.0')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 2: INDICE
# =========================================================================
def page_indice(pdf):
    fig = new_fig('INDICE', 'Mapa das 15 fichas do Atlas de Lajes')
    ax = fig.add_axes([0.08, 0.08, 0.84, 0.85])
    ax.set_facecolor(BG)
    ax.axis('off')

    entries = [
        ('PG 1',  'Capa'),
        ('PG 2',  'Indice'),
        ('PG 3',  'L-01  Anatomia da Laje: contorno, area, espessura, grade'),
        ('PG 4',  'L-02  Forma Fundo: paineis retangulares'),
        ('PG 5',  'L-03  Grade de Pontaletes: LAJE_GRID_STEP=122cm'),
        ('PG 6',  'L-04  Espessuras: h=10/12/14/15/20cm'),
        ('PG 7',  'L-05  Laje Irregular: poligono com vertices'),
        ('PG 8',  'L-06  Laje com Abertura/Ilha: contorno + hole'),
        ('PG 9',  'L-07  Acrescimo de Borda: bordas livres +cm'),
        ('PG 10', 'L-08  Bordering Vigas: vigas nos 4 lados'),
        ('PG 11', 'L-09  Corte Transversal: laje+pontalete+forma+viga'),
        ('PG 12', 'L-10  Tipos: regular / irregular / cantilever'),
        ('PG 13', 'L-11  Nomenclatura: TERREO - L101 100.0x100.0cm paineis: 2x1'),
        ('PG 14', 'L-12  Exemplo Completo L101: 100x100cm, 2x1 paineis'),
        ('PG 15', 'L-13  Campos de Dados + Validacao'),
    ]

    y = 0.95
    for pg, desc in entries:
        color = LAJE_C if pg in ('PG 3', 'PG 5', 'PG 11', 'PG 14') else TEXTO
        ax.text(0.04, y, pg, color=PAINEL, fontsize=8, fontweight='bold',
                fontfamily='monospace', va='top', transform=ax.transAxes)
        ax.text(0.15, y, desc, color=color, fontsize=7.5,
                fontfamily='monospace', va='top', transform=ax.transAxes)
        y -= 0.055

    # Legenda de cores
    ax.text(0.04, y - 0.04, 'Legenda de cores:', color=APOIO_C, fontsize=7,
            va='top', transform=ax.transAxes, fontweight='bold')
    legend_items = [
        (LAJE_C, 'Contorno da laje (layer Contorno)'),
        (PAINEL, 'Paineis de forma (layer Paineis)'),
        (PILAR_C, 'Pontaletes (escoras)'),
        (VIGA_C, 'Vigas de borda (bordering_vigas)'),
        (COTA_C, 'Cotas e dimensoes'),
        (GRADE, 'Grade de distribuicao'),
    ]
    for i, (cor, desc) in enumerate(legend_items):
        yi = y - 0.08 - i * 0.035
        ax.plot([0.06, 0.10], [yi, yi], color=cor, lw=3, transform=ax.transAxes)
        ax.text(0.12, yi, desc, color=TEXTO, fontsize=6.5, va='center',
                fontfamily='monospace', transform=ax.transAxes)

    rodape(fig, 2, 'Indice do Atlas de Lajes')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 3: L-01 Anatomia da Laje
# =========================================================================
def page_l01_anatomia(pdf):
    fig = new_fig('L-01  ANATOMIA DA LAJE', 'Contorno, area, espessura e grade de pontaletes')

    # --- Diagrama principal ---
    ax = fig.add_axes([0.08, 0.45, 0.84, 0.47])
    setup(ax, 'Planta Baixa -- Laje L101')

    W, H = 10, 7
    # Contorno externo ciano
    draw_laje_contour(ax, 0, 0, W, H, LAJE_C, 2.5)

    # Grade 4x3 (n_cols=4, n_rows=3)
    n_c, n_r = 4, 3
    draw_grid(ax, 0, 0, W, H, n_c, n_r, GRADE, 0.8)
    draw_pontaletes(ax, 0, 0, W, H, n_c, n_r, 0.15)

    # Cotas
    cota(ax, 0, -0.8, W, -0.8, f'{W*100/W:.0f}0 cm (W)', COTA_C, 7, 0)
    cota(ax, -0.8, 0, -0.8, H, f'{H*100/H:.0f}0 cm (H)', COTA_C, 7, 0)

    # Area
    tag(ax, W / 2, H / 2, 'L101', LAJE_C, 12)
    ax.text(W / 2, H / 2 - 0.8, f'Area = {W*H:.0f} u2', color=TEXTO, fontsize=7,
            ha='center', va='center', zorder=5)
    ax.text(W / 2, H / 2 - 1.3, f'Grade: {n_c}x{n_r} (step=122cm)', color=GRADE,
            fontsize=6.5, ha='center', va='center', zorder=5)

    # Espessura seta lateral
    ax.text(W + 1.5, H / 2, 'h=15cm', color=COTA_C, fontsize=8, ha='center',
            va='center', rotation=90, fontweight='bold')

    # Labels callouts
    arrow(ax, -1.5, H + 0.5, 0, H, 'Contorno\n(LWPOLYLINE)', LAJE_C, 6)
    arrow(ax, W + 2.5, H + 0.5, W / 4 * 0.5 + 0.05, H / 3 * 0.5, 'Pontalete', PILAR_C, 6)
    arrow(ax, W + 2.5, -1, W / 4 * 1.5, H / 3 * 0.5, 'Grid\n(LAJE_GRID_STEP)', GRADE, 6)

    ax.set_xlim(-3, W + 4)
    ax.set_ylim(-2.5, H + 2)

    # --- Bloco de dados ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.35])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'CAMPOS DA LAJE (Motor Fase 4):',
        '  label ........... "L101"         -- nome unico',
        '  area ............ 25.0 m2        -- width * height',
        '  width ........... 500.0 cm       -- largura do bbox',
        '  height .......... 500.0 cm       -- altura do bbox',
        '  espessura (h) ... 15 cm          -- espessura da laje',
        '  n_cols .......... 4              -- ceil(W / 122)',
        '  n_rows .......... 3              -- ceil(H / 122)',
        '  grid_step_x ..... 125.0 cm       -- W / n_cols',
        '  grid_step_y ..... 116.7 cm       -- H / n_rows',
        '  outline ......... [[x,y], ...]   -- poligono externo',
        '  bordering_vigas . ["V1","V2",..]  -- vigas de borda',
        '',
        'CONSTANTES:',
        '  LAJE_GRID_STEP ......... 122.0 cm',
        '  LAJE_ESPESSURA_DEFAULT . 12.0 cm',
        '  MAX_PAINEL_LARGURA ..... 244.0 cm',
    ], fs=6, fc=TEXTO, lh=0.052)

    rodape(fig, 3, 'L-01 Anatomia da Laje')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 4: L-02 Forma Fundo -- Paineis retangulares
# =========================================================================
def page_l02_forma_fundo(pdf):
    fig = new_fig('L-02  FORMA FUNDO', 'Paineis retangulares da laje -- layer Paineis')

    # --- Vista planta ---
    ax = fig.add_axes([0.08, 0.50, 0.84, 0.42])
    setup(ax, 'Laje 300x200cm -- 3 paineis V x 2 paineis H')

    W, H = 9, 6  # escala visual
    # Contorno
    draw_laje_contour(ax, 0, 0, W, H, LAJE_C, 2.0)

    # Linhas de divisao (linhas_verticais e linhas_horizontais)
    lv = [3.0, 6.0]   # 2 cortes verticais -> 3 paineis
    lh = [3.0]          # 1 corte horizontal -> 2 paineis
    for xv in lv:
        ax.plot([xv, xv], [0, H], color=PAINEL, lw=1.5, ls='-', zorder=3)
    for yh in lh:
        ax.plot([0, W], [yh, yh], color=PAINEL, lw=1.5, ls='-', zorder=3)

    # Preencher paineis
    xs = [0] + lv + [W]
    ys = [0] + lh + [H]
    pn = 1
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            px, py = xs[i], ys[j]
            pw, ph = xs[i + 1] - xs[i], ys[j + 1] - ys[j]
            rct(ax, px + 0.05, py + 0.05, pw - 0.1, ph - 0.1,
                fc=PAINEL, ec=PAINEL, lw=0.5, alpha=0.15)
            ax.text(px + pw / 2, py + ph / 2, f'P{pn}', color=PAINEL,
                    fontsize=8, ha='center', va='center', fontweight='bold', zorder=5)
            pn += 1

    # Cotas paineis
    cota(ax, 0, -0.6, lv[0], -0.6, '100cm', COTA_C, 6.5, 0)
    cota(ax, lv[0], -0.6, lv[1], -0.6, '100cm', COTA_C, 6.5, 0)
    cota(ax, lv[1], -0.6, W, -0.6, '100cm', COTA_C, 6.5, 0)
    cota(ax, -0.6, 0, -0.6, lh[0], '100cm', COTA_C, 6.5, 0)
    cota(ax, -0.6, lh[0], -0.6, H, '100cm', COTA_C, 6.5, 0)

    tag(ax, W / 2, H + 0.8, 'L101  300x200cm  paineis: 3x2', LAJE_C, 7)

    ax.set_xlim(-2, W + 2)
    ax.set_ylim(-2, H + 2)

    # --- Explicacao ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.40])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'FORMA FUNDO -- Paineis de compensado:',
        '',
        '  linhas_verticais ... [100, 200]    -- posicoes x dos cortes',
        '  linhas_horizontais  [100]           -- posicoes y dos cortes',
        '  n_paineis_v ........ 3              -- len(lv) + 1',
        '  n_paineis_h ........ 2              -- len(lh) + 1',
        '  total paineis ...... 6              -- 3 x 2',
        '',
        'COMO O ROBO DESENHA:',
        '  1. Poligono externo: LWPOLYLINE no layer "Contorno"',
        '  2. Para cada celula (xi, yj) -> (xi+1, yj+1):',
        '     - Desenha LWPOLYLINE retangular no layer "Paineis"',
        '  3. Unioes nos bordes: is_union=True para faixas <= 30cm',
        '     - Esses paineis NAO sao desenhados separados',
        '',
        'DXF LAYERS:',
        '  Contorno .......... cor 7 (branco) -- poligono externo',
        '  Paineis ........... cor 3 (verde)  -- retangulos dos paineis',
        '  Texto Secao ....... cor 2 (amarelo) -- label "L101"',
        '  NOMENCLATURA ...... cor 2           -- titulo completo',
        '  Obstaculos ........ cor 1 (vermelho) -- furos/ilhas',
    ], fs=6, fc=TEXTO, lh=0.048)

    rodape(fig, 4, 'L-02 Forma Fundo')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 5: L-03 Grade de pontaletes
# =========================================================================
def page_l03_grade(pdf):
    fig = new_fig('L-03  GRADE DE PONTALETES', 'LAJE_GRID_STEP=122cm -- distribuicao de escoras')

    # --- Grade esquematica ---
    ax = fig.add_axes([0.08, 0.52, 0.84, 0.40])
    setup(ax, 'Laje 488x366cm (4x3 pontaletes)')

    W, H = 12, 9
    n_c, n_r = 4, 3
    draw_laje_contour(ax, 0, 0, W, H, LAJE_C, 2.0)
    draw_grid(ax, 0, 0, W, H, n_c, n_r, GRADE, 1.0)
    draw_pontaletes(ax, 0, 0, W, H, n_c, n_r, 0.22)

    # Cotas celula
    sx, sy = W / n_c, H / n_r
    cota(ax, 0, -0.8, sx, -0.8, f'step_x={sx * 122 / (W / n_c):.0f}cm', COTA_C, 6, 0)
    cota(ax, -0.8, 0, -0.8, sy, f'step_y={sy * 122 / (H / n_r):.0f}cm', COTA_C, 6, 0)

    # Formulas
    ax.text(W + 1, H - 0.5, 'n_cols = ceil(W/122)', color=TEXTO, fontsize=6.5,
            fontfamily='monospace', va='top')
    ax.text(W + 1, H - 1.5, f'  = ceil(488/122) = 4', color=LAJE_C, fontsize=6.5,
            fontfamily='monospace', va='top')
    ax.text(W + 1, H - 2.8, 'n_rows = ceil(H/122)', color=TEXTO, fontsize=6.5,
            fontfamily='monospace', va='top')
    ax.text(W + 1, H - 3.8, f'  = ceil(366/122) = 3', color=LAJE_C, fontsize=6.5,
            fontfamily='monospace', va='top')
    ax.text(W + 1, H - 5.5, 'grid_step_x = W/n_cols', color=TEXTO, fontsize=6.5,
            fontfamily='monospace', va='top')
    ax.text(W + 1, H - 6.5, '  = 488/4 = 122.0cm', color=COTA_C, fontsize=6.5,
            fontfamily='monospace', va='top')

    # Marca 1 pontalete detalhado
    cx, cy = 0.5 * sx, 0.5 * sy
    ax.annotate('Pontalete\n(centro da celula)', xy=(cx, cy), xytext=(cx - 3, cy + 3),
                fontsize=6.5, color=PILAR_C, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=PILAR_C, lw=0.8))

    ax.set_xlim(-2.5, W + 9)
    ax.set_ylim(-2.5, H + 2)

    # --- Tabela de exemplos ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.42])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'CONSTANTE: LAJE_GRID_STEP = 122.0 cm',
        '',
        'EXEMPLOS DE CALCULO:',
        '',
        '  Laje     W(cm)   H(cm)  n_cols  n_rows  step_x  step_y  Total',
        '  ------  ------  ------  ------  ------  ------  ------  -----',
        '  L101     244      244      2       2    122.0   122.0     4',
        '  L102     366      244      3       2    122.0   122.0     6',
        '  L103     488      366      4       3    122.0   122.0    12',
        '  L104     610      488      5       4    122.0   122.0    20',
        '  L105     200      150      2       1    100.0   150.0     2',
        '',
        'FORMULA:',
        '  n_cols = max(1, round(width / 122))',
        '  n_rows = max(1, round(height / 122))',
        '  grid_step_x = width / n_cols',
        '  grid_step_y = height / n_rows',
        '',
        'CADA CELULA = 1 pontalete (escora metalica) posicionado no centro.',
        'Grid lines sao desenhadas como LINE ou LWPOLYLINE no layer Paineis.',
    ], fs=6, fc=TEXTO, lh=0.046)

    rodape(fig, 5, 'L-03 Grade de Pontaletes')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 6: L-04 Espessuras
# =========================================================================
def page_l04_espessuras(pdf):
    fig = new_fig('L-04  ESPESSURAS', 'h=10 / 12 / 14 / 15 / 20cm -- comparacao visual')

    espessuras = [10, 12, 14, 15, 20]
    colors = [LAJE_C, '#66d9ef', '#a6e1f4', PAINEL, PILAR_C]

    # --- Cortes laterais comparativos ---
    ax = fig.add_axes([0.08, 0.50, 0.84, 0.42])
    setup(ax, 'Corte Lateral -- Espessuras de Laje')

    base_w = 8
    x0 = 0.5
    for i, (h_val, cor) in enumerate(zip(espessuras, colors)):
        y_base = 1.0 + i * 3.5
        h_visual = h_val / 5.0  # escala visual

        # Laje retangulo
        rct(ax, x0, y_base, base_w, h_visual, fc=cor, ec='white', lw=1.2, alpha=0.7)
        lbl(ax, x0, y_base, base_w, h_visual, f'h = {h_val} cm', TEXTO, 8)

        # Cota lateral
        cota(ax, x0 - 0.5, y_base, x0 - 0.5, y_base + h_visual,
             f'{h_val}cm', COTA_C, 6, 0)

        # Label
        ax.text(x0 + base_w + 0.5, y_base + h_visual / 2, f'Laje h={h_val}',
                color=cor, fontsize=7, va='center', fontfamily='monospace')

    ax.set_xlim(-1.5, base_w + 4)
    ax.set_ylim(0, 19)

    # --- Dados ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.40])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'ESPESSURAS TIPICAS:',
        '',
        '  h=10cm ... Lajes em balanco, marquises pequenas',
        '  h=12cm ... Lajes residenciais padrao (DEFAULT motor)',
        '  h=14cm ... Lajes com vaos intermediarios',
        '  h=15cm ... Lajes comerciais, garagens',
        '  h=20cm ... Lajes com grandes vaos, cargas pesadas',
        '',
        'CAMPO NO MOTOR:',
        '  config_dict["espessura"] = self.laje_espessura',
        '  DEFAULT: LAJE_ESPESSURA_DEFAULT = 12.0 cm',
        '',
        'IMPACTO NO ESCORAMENTO:',
        '  - Maior espessura -> maior peso proprio -> mais pontaletes',
        '  - h >= 15cm: considerar reescora (re-shoring)',
        '  - Garfo do pe direito: pe_direito - espessura_laje',
        '',
        'NO DXF:',
        '  A espessura NAO eh desenhada na planta (vista top-down).',
        '  Aparece na nomenclatura e no corte transversal (ficha L-09).',
    ], fs=6, fc=TEXTO, lh=0.048)

    rodape(fig, 6, 'L-04 Espessuras')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 7: L-05 Laje Irregular
# =========================================================================
def page_l05_irregular(pdf):
    fig = new_fig('L-05  LAJE IRREGULAR', 'Poligono com vertices -- contorno nao retangular')

    ax = fig.add_axes([0.08, 0.45, 0.84, 0.47])
    setup(ax, 'Laje L201 -- Poligono Irregular (6 vertices)')

    # Poligono irregular
    verts = [(0, 0), (8, 0), (10, 3), (9, 7), (4, 8), (0, 5)]
    xs = [v[0] for v in verts] + [verts[0][0]]
    ys = [v[1] for v in verts] + [verts[0][1]]
    ax.fill(xs, ys, fc=LAJE_C, alpha=0.08, zorder=1)
    ax.plot(xs, ys, color=LAJE_C, lw=2.5, zorder=3)

    # Vertices numerados
    for i, (vx, vy) in enumerate(verts):
        ax.plot(vx, vy, 'o', color=PILAR_C, markersize=6, zorder=5)
        ox = -0.6 if vx < 5 else 0.6
        oy = -0.5 if vy < 4 else 0.5
        ax.text(vx + ox, vy + oy, f'V{i}\n({vx},{vy})', color=PILAR_C,
                fontsize=5.5, ha='center', va='center', fontweight='bold',
                bbox=dict(facecolor=BG, alpha=0.8, pad=1, edgecolor='none'))

    # Bbox tracejado
    bx0, by0 = min(xs), min(ys)
    bx1, by1 = max(xs), max(ys)
    bbox_rect = mpatches.Rectangle((bx0, by0), bx1 - bx0, by1 - by0,
                                    ls='--', lw=1.0, ec=GRADE, fc='none', zorder=2)
    ax.add_patch(bbox_rect)
    ax.text(bx1 + 0.3, (by0 + by1) / 2, 'bbox\n(fallback)', color=GRADE,
            fontsize=6, ha='left', va='center')

    tag(ax, 5, 3.5, 'L201', LAJE_C, 10)

    ax.set_xlim(-2, 13)
    ax.set_ylim(-2, 10)

    # --- Dados ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.35])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'LAJE IRREGULAR -- Contorno via points_json ou outline:',
        '',
        '  outline = [[0,0], [8,0], [10,3], [9,7], [4,8], [0,5]]',
        '  type = "irregular"',
        '',
        'MOTOR FASE 4:',
        '  1. Tenta parsear points_json (JSON string do DXF)',
        '  2. Se falhar, gera retangulo a partir da bbox (fallback)',
        '     outline = [[x_min,y_min],[x_max,y_min],[x_max,y_max],[x_min,y_max]]',
        '',
        'NO DXF:',
        '  draw_polygon(msp, coords, "Contorno")',
        '  -> LWPOLYLINE fechada com close=True',
        '  -> Vertices em coordenadas cm (ou mm conforme escala)',
        '',
        'DATACLASS Laje:',
        '  coordenadas: List[Tuple[float, float]]  # [(x,y), ...] em cm',
        '  Maximo 1000 vertices (protecao em from_dict)',
    ], fs=6, fc=TEXTO, lh=0.052)

    rodape(fig, 7, 'L-05 Laje Irregular')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 8: L-06 Laje com Abertura/Ilha
# =========================================================================
def page_l06_abertura(pdf):
    fig = new_fig('L-06  LAJE COM ABERTURA / ILHA', 'Contorno externo + holes (obstaculos)')

    ax = fig.add_axes([0.08, 0.45, 0.84, 0.47])
    setup(ax, 'Laje L301 com Abertura para Escada')

    W, H = 10, 8
    # Contorno externo
    draw_laje_contour(ax, 0, 0, W, H, LAJE_C, 2.5)
    ax.fill([0, W, W, 0, 0], [0, 0, H, H, 0], fc=LAJE_C, alpha=0.06, zorder=1)

    # Abertura (hole)
    hx, hy, hw, hh = 3, 2.5, 3.5, 3
    hole_pts_x = [hx, hx + hw, hx + hw, hx, hx]
    hole_pts_y = [hy, hy, hy + hh, hy + hh, hy]
    ax.fill(hole_pts_x, hole_pts_y, fc=BG, zorder=2)
    ax.plot(hole_pts_x, hole_pts_y, color=WARN, lw=2.0, ls='-', zorder=3)
    # Hachura X no hole
    ax.plot([hx, hx + hw], [hy, hy + hh], color=WARN, lw=0.8, ls='--', alpha=0.5, zorder=2)
    ax.plot([hx + hw, hx], [hy, hy + hh], color=WARN, lw=0.8, ls='--', alpha=0.5, zorder=2)

    tag(ax, W / 2, 1, 'L301', LAJE_C, 10)
    tag(ax, hx + hw / 2, hy + hh / 2, 'ABERTURA\n(escada)', WARN, 7)

    # Cotas
    cota(ax, hx, -0.6, hx + hw, -0.6, f'{hw * 100 / W * 10:.0f}cm', COTA_C, 6, 0)
    cota(ax, W + 0.5, hy, W + 0.5, hy + hh, f'{hh * 100 / H * 8:.0f}cm', COTA_C, 6, 0)

    ax.set_xlim(-2, W + 3)
    ax.set_ylim(-2, H + 2)

    # --- Dados ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.35])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'ABERTURAS / ILHAS -- Campo "obstaculos" no Laje dataclass:',
        '',
        '  obstaculos: List[List[Tuple[float,float]]]',
        '  Cada obstaculo e um poligono fechado (min 3 pontos)',
        '',
        'NO DXF (gerar_dxf_lajes.py):',
        '  for ob in obstaculos:',
        '      if ob["active"]:',
        '          pts = [(ox,oy), (ox+ow,oy), ...]',
        '          LWPOLYLINE no layer "Obstaculos" (cor 1 = vermelho)',
        '',
        'PROTECAO (from_dict):',
        '  - Max 50 obstaculos por laje',
        '  - Min 3 pontos para formar poligono valido',
        '  - Coordenadas validadas (NaN, Inf, limites)',
        '',
        'USOS COMUNS:',
        '  - Abertura para escada',
        '  - Furo para instalacoes (shaft)',
        '  - Recorte para pilar embutido',
    ], fs=6, fc=TEXTO, lh=0.052)

    rodape(fig, 8, 'L-06 Laje com Abertura')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 9: L-07 Acrescimo de Borda
# =========================================================================
def page_l07_acrescimo(pdf):
    fig = new_fig('L-07  ACRESCIMO DE BORDA', 'Bordas livres com acrescimo em cm')

    ax = fig.add_axes([0.08, 0.45, 0.84, 0.47])
    setup(ax, 'Laje L401 com acrescimo_borda = 5cm')

    W, H = 8, 6
    acr = 0.8  # visual scale para 5cm

    # Laje original (tracejada)
    pts_orig = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
    ax.plot([p[0] for p in pts_orig], [p[1] for p in pts_orig],
            color=GRADE, lw=1.5, ls='--', zorder=2)

    # Laje com acrescimo (borda livre no topo e direita)
    # Supondo vigas embaixo (V1) e esquerda (V2), bordas livres topo e direita
    ext_pts = [(-0, -0), (W + acr, -0), (W + acr, H + acr), (-0, H + acr), (-0, -0)]
    ax.plot([p[0] for p in ext_pts], [p[1] for p in ext_pts],
            color=LAJE_C, lw=2.5, zorder=3)
    ax.fill([p[0] for p in ext_pts], [p[1] for p in ext_pts],
            fc=LAJE_C, alpha=0.06, zorder=1)

    # Faixa de acrescimo (hachura)
    # Direita
    rct(ax, W, 0, acr, H + acr, fc=COTA_C, ec=COTA_C, lw=0.5, alpha=0.15)
    # Topo
    rct(ax, 0, H, W, acr, fc=COTA_C, ec=COTA_C, lw=0.5, alpha=0.15)

    # Cotas
    cota(ax, W, -0.6, W + acr, -0.6, '+5cm', COTA_C, 7, 0)
    cota(ax, -0.6, H, -0.6, H + acr, '+5cm', COTA_C, 7, 0)

    # Vigas nos lados com apoio (sem acrescimo)
    ax.plot([0, 0], [-0.3, H + 0.3], color=VIGA_C, lw=4, alpha=0.5, zorder=2)
    ax.text(-0.8, H / 2, 'V2\n(apoio)', color=VIGA_C, fontsize=6, ha='center',
            va='center', fontweight='bold')
    ax.plot([-0.3, W + 0.3], [0, 0], color=VIGA_C, lw=4, alpha=0.5, zorder=2)
    ax.text(W / 2, -1, 'V1 (apoio)', color=VIGA_C, fontsize=6, ha='center',
            va='center', fontweight='bold')

    # Bordas livres
    ax.text(W + acr + 0.8, H / 2, 'BORDA\nLIVRE', color=WARN, fontsize=7,
            ha='center', va='center', fontweight='bold')
    ax.text(W / 2, H + acr + 0.6, 'BORDA LIVRE', color=WARN, fontsize=7,
            ha='center', va='center', fontweight='bold')

    tag(ax, W / 2, H / 2, 'L401', LAJE_C, 10)

    ax.set_xlim(-2.5, W + 3)
    ax.set_ylim(-2, H + 3)

    # --- Dados ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.35])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'ACRESCIMO DE BORDA:',
        '',
        '  acrescimo_borda = 5  (cm, default: 0)',
        '',
        '  Aplicado APENAS em bordas livres (sem viga de apoio).',
        '  Bordas com viga: sem acrescimo (forma encosta na viga).',
        '',
        '  CALCULO:',
        '    Se borda_livre[i] == True:',
        '      contorno[i] += acrescimo_borda  (na direcao normal)',
        '',
        '  PROPOSITO:',
        '    - Compensar irregularidades na concretagem',
        '    - Garantir cobrimento adequado nas bordas',
        '    - Evitar vazamento de concreto',
        '',
        '  NO DXF:',
        '    Contorno externo ja inclui o acrescimo.',
        '    Paineis se estendem ate a borda expandida.',
    ], fs=6, fc=TEXTO, lh=0.052)

    rodape(fig, 9, 'L-07 Acrescimo de Borda')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 10: L-08 Bordering Vigas
# =========================================================================
def page_l08_bordering(pdf):
    fig = new_fig('L-08  BORDERING VIGAS', 'Vigas que delimitam a laje nos 4 lados')

    ax = fig.add_axes([0.08, 0.45, 0.84, 0.47])
    setup(ax, 'Laje L501 com 4 vigas de borda')

    W, H = 9, 7
    vw = 0.5  # largura visual da viga

    # Vigas nos 4 lados
    # V1 embaixo
    rct(ax, -vw, -vw, W + 2 * vw, vw, fc=VIGA_C, ec='white', lw=1.0, alpha=0.6)
    ax.text(W / 2, -vw / 2, 'V1', color=BG, fontsize=8, fontweight='bold',
            ha='center', va='center', zorder=5)
    # V2 topo
    rct(ax, -vw, H, W + 2 * vw, vw, fc=VIGA_C, ec='white', lw=1.0, alpha=0.6)
    ax.text(W / 2, H + vw / 2, 'V3', color=BG, fontsize=8, fontweight='bold',
            ha='center', va='center', zorder=5)
    # V3 esquerda
    rct(ax, -vw, 0, vw, H, fc=VIGA_C, ec='white', lw=1.0, alpha=0.6)
    ax.text(-vw / 2, H / 2, 'V2', color=BG, fontsize=8, fontweight='bold',
            ha='center', va='center', rotation=90, zorder=5)
    # V4 direita
    rct(ax, W, 0, vw, H, fc=VIGA_C, ec='white', lw=1.0, alpha=0.6)
    ax.text(W + vw / 2, H / 2, 'V4', color=BG, fontsize=8, fontweight='bold',
            ha='center', va='center', rotation=90, zorder=5)

    # Pilares nos cantos
    ps = 0.6
    pilares = [(-vw, -vw), (W, -vw), (W, H), (-vw, H)]
    for px, py in pilares:
        rct(ax, px, py, ps, ps, fc=PILAR_C, ec='white', lw=1.0, alpha=0.7)

    # Laje no centro
    draw_laje_contour(ax, 0, 0, W, H, LAJE_C, 2.0)
    ax.fill([0, W, W, 0], [0, 0, H, H], fc=LAJE_C, alpha=0.06, zorder=1)
    n_c, n_r = 3, 3
    draw_grid(ax, 0, 0, W, H, n_c, n_r, GRADE, 0.6)
    draw_pontaletes(ax, 0, 0, W, H, n_c, n_r, 0.14)
    tag(ax, W / 2, H / 2, 'L501', LAJE_C, 10)

    ax.set_xlim(-2.5, W + 3)
    ax.set_ylim(-2.5, H + 3)

    # --- Dados ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.35])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'BORDERING VIGAS -- Vigas que bordejam a laje:',
        '',
        '  bordering_vigas = ["V1", "V2", "V3", "V4"]',
        '',
        'DETECCAO NO MOTOR FASE 4:',
        '  1. Busca relacionamentos VIGA_BORDA_LAJE no ObraKnowledge (kb)',
        '  2. rel.entity_a_label = viga, rel.entity_b_label = laje',
        '  3. Agrupa por laje: laje_bordering_vigas[laje_label].append(viga)',
        '',
        '  rels = kb.buscar_relacionamentos("VIGA_BORDA_LAJE")',
        '  for rel in rels:',
        '      laje_label = rel["entity_b_label"]',
        '      viga_label = rel["entity_a_label"]',
        '      laje_bordering_vigas[laje_label].append(viga_label)',
        '',
        'USO:',
        '  - Determinar quais bordas tem apoio (viga)',
        '  - Bordas SEM viga = borda livre -> acrescimo',
        '  - Informacao passada ao config_dict final',
    ], fs=6, fc=TEXTO, lh=0.050)

    rodape(fig, 10, 'L-08 Bordering Vigas')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 11: L-09 Corte Transversal
# =========================================================================
def page_l09_corte(pdf):
    fig = new_fig('L-09  CORTE TRANSVERSAL', 'Laje + pontalete + forma fundo + viga apoio')

    ax = fig.add_axes([0.08, 0.38, 0.84, 0.54])
    setup(ax, 'Secao AA -- Corte Transversal do Escoramento')

    # Escala vertical exagerada para visibilidade
    base_y = 0
    piso_y = base_y
    pd = 8.0   # pe direito visual
    h_laje = 1.2  # espessura laje visual

    # Piso
    ax.plot([-2, 16], [piso_y, piso_y], color=APOIO_C, lw=2, zorder=2)
    ax.text(-1.5, piso_y - 0.5, 'PISO', color=APOIO_C, fontsize=7, fontweight='bold')

    # Pontaletes (escoras)
    pontalete_xs = [2, 6, 10, 14]
    for px in pontalete_xs:
        # Escora metalica (retangulo fino vertical)
        rct(ax, px - 0.1, piso_y, 0.2, pd, fc=PILAR_C, ec='white', lw=0.8, alpha=0.8)
        # Base
        rct(ax, px - 0.4, piso_y - 0.15, 0.8, 0.15, fc=PILAR_C, ec='white', lw=0.5, alpha=0.6)

    # Forma fundo (paineis de compensado)
    forma_y = piso_y + pd
    forma_h = 0.25
    # 3 paineis
    painel_xs = [(0, 5.3), (5.5, 10.3), (10.5, 16)]
    for x1, x2 in painel_xs:
        rct(ax, x1, forma_y, x2 - x1, forma_h, fc=PAINEL, ec='white', lw=1.0, alpha=0.85)

    # Laje (concreto em cima da forma)
    laje_y = forma_y + forma_h
    rct(ax, -0.5, laje_y, 17, h_laje, fc=LAJE_C, ec='white', lw=1.5, alpha=0.3)
    ax.text(8, laje_y + h_laje / 2, f'LAJE (h={h_laje / 1.2 * 15:.0f}cm)', color=LAJE_C,
            fontsize=8, ha='center', va='center', fontweight='bold', zorder=5)

    # Vigas de apoio nas laterais
    viga_h = 2.0
    viga_w = 0.8
    # Viga esquerda
    rct(ax, -0.5 - viga_w, forma_y - viga_h + forma_h + h_laje, viga_w, viga_h,
        fc=VIGA_C, ec='white', lw=1.0, alpha=0.6)
    ax.text(-0.5 - viga_w / 2, forma_y - viga_h / 2 + forma_h + h_laje, 'V1',
            color=BG, fontsize=7, fontweight='bold', ha='center', va='center', zorder=5)
    # Viga direita
    rct(ax, 16.5, forma_y - viga_h + forma_h + h_laje, viga_w, viga_h,
        fc=VIGA_C, ec='white', lw=1.0, alpha=0.6)
    ax.text(16.5 + viga_w / 2, forma_y - viga_h / 2 + forma_h + h_laje, 'V2',
            color=BG, fontsize=7, fontweight='bold', ha='center', va='center', zorder=5)

    # Cotas
    cota(ax, -2, piso_y, -2, forma_y, f'PD = 280cm', COTA_C, 6, 0)
    cota(ax, 17.5, laje_y, 17.5, laje_y + h_laje, f'h={h_laje / 1.2 * 15:.0f}cm', COTA_C, 6, 0)
    cota(ax, pontalete_xs[0], -1, pontalete_xs[1], -1, 'grid_step_x', COTA_C, 6, 0)

    # Labels
    arrow(ax, -2, pd + 1.5, 2, pd + 0.25 / 2, 'Forma fundo\n(compensado)', PAINEL, 6)
    arrow(ax, 18, pd / 2 + 2, pontalete_xs[2], pd / 2, 'Pontalete\n(escora)', PILAR_C, 6)

    ax.set_xlim(-4, 20)
    ax.set_ylim(-2, pd + h_laje + 3)

    # --- Legenda ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.28])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'CORTE TRANSVERSAL -- Elementos empilhados:',
        '',
        '  PISO ............................. base',
        '  PONTALETES (escoras metalicas) ... suporte vertical',
        '  FORMA FUNDO (paineis compensado).. superficie de apoio',
        '  LAJE (concreto armado) ........... elemento estrutural',
        '  VIGAS DE BORDA ................... apoio lateral',
        '',
        '  PE DIREITO (pd) = 280cm default',
        '  Altura real pontalete = pd - espessura_laje - forma_fundo',
        '',
        '  Motor Fase 4:',
        '    garfo["pe_direito"] = pe_direito',
        '    garfo["espessura_laje"] = self.laje_espessura',
    ], fs=6, fc=TEXTO, lh=0.055)

    rodape(fig, 11, 'L-09 Corte Transversal')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 12: L-10 Tipos de Laje
# =========================================================================
def page_l10_tipos(pdf):
    fig = new_fig('L-10  TIPOS DE LAJE', 'regular / irregular / cantilever')

    # --- 3 diagramas lado a lado ---
    # Regular
    ax1 = fig.add_axes([0.05, 0.55, 0.28, 0.37])
    setup(ax1, 'REGULAR')
    W, H = 6, 4
    draw_laje_contour(ax1, 0, 0, W, H, LAJE_C, 2.0)
    draw_grid(ax1, 0, 0, W, H, 2, 2, GRADE, 0.6)
    draw_pontaletes(ax1, 0, 0, W, H, 2, 2, 0.15)
    tag(ax1, W / 2, H / 2, 'L101', LAJE_C, 8)
    ax1.text(W / 2, -0.8, 'type="regular"', color=VERDE, fontsize=6,
             ha='center', fontfamily='monospace')
    ax1.set_xlim(-1, W + 1)
    ax1.set_ylim(-1.5, H + 1)

    # Irregular
    ax2 = fig.add_axes([0.37, 0.55, 0.28, 0.37])
    setup(ax2, 'IRREGULAR')
    verts = [(0, 0), (5, 0), (6, 2), (5, 4.5), (2, 5), (0, 3)]
    xs = [v[0] for v in verts] + [verts[0][0]]
    ys = [v[1] for v in verts] + [verts[0][1]]
    ax2.fill(xs, ys, fc=LAJE_C, alpha=0.08)
    ax2.plot(xs, ys, color=LAJE_C, lw=2.0)
    for vx, vy in verts:
        ax2.plot(vx, vy, 'o', color=PILAR_C, markersize=4, zorder=5)
    tag(ax2, 3, 2, 'L201', LAJE_C, 8)
    ax2.text(3, -0.8, 'type="irregular"', color=COTA_C, fontsize=6,
             ha='center', fontfamily='monospace')
    ax2.set_xlim(-1, 7)
    ax2.set_ylim(-1.5, 6)

    # Cantilever
    ax3 = fig.add_axes([0.69, 0.55, 0.28, 0.37])
    setup(ax3, 'CANTILEVER')
    W2, H2 = 5, 3
    draw_laje_contour(ax3, 0, 0, W2, H2, LAJE_C, 2.0)
    # Apoio em 1 lado apenas (esquerda)
    ax3.plot([0, 0], [-0.3, H2 + 0.3], color=VIGA_C, lw=5, alpha=0.6, zorder=2)
    ax3.text(-0.6, H2 / 2, 'V1', color=VIGA_C, fontsize=7, fontweight='bold',
             ha='center', va='center')
    # Seta mostrando balanco
    ax3.annotate('', xy=(W2, H2 / 2), xytext=(0.5, H2 / 2),
                 arrowprops=dict(arrowstyle='->', color=WARN, lw=1.5))
    ax3.text(W2 / 2, H2 / 2 + 0.5, 'BALANCO', color=WARN, fontsize=6.5,
             ha='center', fontweight='bold')
    tag(ax3, W2 / 2, H2 / 2 - 0.5, 'L301', LAJE_C, 8)
    ax3.text(W2 / 2, -0.8, 'type="cantilever"', color=WARN, fontsize=6,
             ha='center', fontfamily='monospace')
    ax3.set_xlim(-1.5, W2 + 1)
    ax3.set_ylim(-1.5, H2 + 1)

    # --- Tabela comparativa ---
    ax4 = fig.add_axes([0.08, 0.06, 0.84, 0.44])
    ax4.set_facecolor(BG)
    ax4.axis('off')
    mono_block(ax4, 0.03, 0.95, [
        'COMPARACAO DE TIPOS:',
        '',
        '  Tipo        Contorno       Apoios      Observacao',
        '  ---------   -----------    ---------   ---------------------------',
        '  regular     Retangular     >= 2 lados  Caso padrao, grid uniforme',
        '  irregular   Poligono N     >= 2 lados  points_json com N vertices',
        '  cantilever  Retangular     1 lado so   Balanco, laje em consola',
        '',
        'DETERMINACAO DO TIPO:',
        '  Motor Fase 4 nao classifica explicitamente.',
        '  O campo "type" vem do StructuralVectorizer (Fase 3):',
        '    - Se 4 vertices perpendiculares -> "regular"',
        '    - Se N > 4 vertices ou angulos != 90 -> "irregular"',
        '    - Se apoio em 1 lado apenas -> "cantilever"',
        '',
        'IMPACTO NO ESCORAMENTO:',
        '  regular ...... Grid padrao (n_cols x n_rows)',
        '  irregular .... Grid sobre bbox, pontaletes fora do poligono removidos',
        '  cantilever ... Reforco proximo ao apoio, verificar flecha',
        '',
        'DATACLASS LAJE:',
        '  modo_selecionado: int  # 0=M1 (Verticais), 1=M2 (Horizontais)',
        '  unioes_nos_bordes: bool  # juncoes nos cantos',
    ], fs=6, fc=TEXTO, lh=0.044)

    rodape(fig, 12, 'L-10 Tipos de Laje')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 13: L-11 Nomenclatura
# =========================================================================
def page_l11_nomenclatura(pdf):
    fig = new_fig('L-11  NOMENCLATURA', 'TERREO - L101 100.0x100.0cm paineis: 2x1')

    ax = fig.add_axes([0.08, 0.55, 0.84, 0.37])
    setup(ax, 'Anatomia da Nomenclatura')

    # String de nomenclatura grande
    nome_str = 'TERREO - L101  300.0x200.0cm  paineis: 3x2'
    ax.text(0.5, 0.75, nome_str, color=PAINEL, fontsize=12, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, fontfamily='monospace',
            bbox=dict(facecolor=GRADE, alpha=0.3, pad=8, edgecolor=PAINEL, lw=1.5))

    # Setas de callout para cada parte
    parts = [
        (0.11, 0.55, 'TERREO', 'pavimento\n(pav)', LAJE_C),
        (0.24, 0.55, '-', 'separador', APOIO_C),
        (0.33, 0.55, 'L101', 'label\n(lid)', PILAR_C),
        (0.52, 0.55, '300.0x200.0cm', 'comp x larg\n(cm)', COTA_C),
        (0.78, 0.55, 'paineis: 3x2', 'n_paineis_v x\nn_paineis_h', PAINEL),
    ]
    for px, py, part_text, desc, cor in parts:
        ax.text(px, py, part_text, color=cor, fontsize=8, fontweight='bold',
                ha='center', va='top', transform=ax.transAxes)
        ax.text(px, py - 0.12, desc, color=cor, fontsize=6.5,
                ha='center', va='top', transform=ax.transAxes, fontfamily='monospace')
        ax.annotate('', xy=(px, 0.68), xytext=(px, py + 0.01),
                    arrowprops=dict(arrowstyle='->', color=cor, lw=0.8),
                    xycoords='axes fraction', textcoords='axes fraction')

    # Label layer info
    ax.text(0.5, 0.15, 'Layer: NOMENCLATURA | MTEXT | char_height=10.0 | insert=(0, larg+30)',
            color=APOIO_C, fontsize=6.5, ha='center', va='center',
            transform=ax.transAxes, fontfamily='monospace')

    # --- Exemplos ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.45])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'FORMATO DA NOMENCLATURA:',
        '  f"{pav} - {lid}  {comp:.1f}x{larg:.1f}cm  paineis: {nv}x{nh}"',
        '',
        'CODIGO (gerar_dxf_lajes.py):',
        '  n_paineis_v = len(linhas_v) + 1 if linhas_v else 1',
        '  n_paineis_h = len(linhas_h) + 1 if linhas_h else 1',
        '  header = f"{pav} - {lid}  {comp:.1f}x{larg:.1f}cm  paineis: {nv}x{nh}"',
        '  msp.add_mtext(header, dxfattribs={',
        '      "layer": "NOMENCLATURA",',
        '      "insert": (0.0, larg + 30.0, 0),',
        '      "char_height": 10.0,',
        '  })',
        '',
        'LABEL DA LAJE:',
        '  msp.add_mtext(lid, dxfattribs={',
        '      "layer": "Texto Secao",',
        '      "insert": (cx, cy, 0),  # centro da laje',
        '      "char_height": max(10.0, comp * 0.05),',
        '      "attachment_point": 5,  # center',
        '  })',
        '',
        'EXEMPLOS:',
        '  TERREO - L101  300.0x200.0cm  paineis: 3x2',
        '  1PAVTO - L201  488.0x366.0cm  paineis: 4x3',
        '  COBERTURA - L301  150.0x100.0cm  paineis: 1x1',
    ], fs=6, fc=TEXTO, lh=0.044)

    rodape(fig, 13, 'L-11 Nomenclatura')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 14: L-12 Exemplo Completo L101
# =========================================================================
def page_l12_exemplo(pdf):
    fig = new_fig('L-12  EXEMPLO COMPLETO: L101', '300x200cm, linhas_v=[100,200], linhas_h=[100]')

    # --- Planta completa ---
    ax = fig.add_axes([0.08, 0.48, 0.84, 0.44])
    setup(ax, 'DXF Output -- L101 Planta Baixa')

    W, H = 9, 6  # visual scale (300cm x 200cm)

    # Contorno (layer Contorno)
    draw_laje_contour(ax, 0, 0, W, H, LAJE_C, 2.5)

    # Paineis (layer Paineis)
    lv = [W / 3, 2 * W / 3]
    lh = [H / 2]
    xs = [0] + lv + [W]
    ys = [0] + lh + [H]

    pn = 1
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            px, py = xs[i], ys[j]
            pw, ph = xs[i + 1] - xs[i], ys[j + 1] - ys[j]
            rct(ax, px + 0.04, py + 0.04, pw - 0.08, ph - 0.08,
                fc=PAINEL, ec=PAINEL, lw=0.8, alpha=0.2)
            ax.text(px + pw / 2, py + ph / 2, f'P{pn}', color=PAINEL,
                    fontsize=7, ha='center', va='center', fontweight='bold', zorder=5)
            pn += 1

    # Linhas de divisao
    for xv in lv:
        ax.plot([xv, xv], [0, H], color=PAINEL, lw=1.2, zorder=3)
    for yh in lh:
        ax.plot([0, W], [yh, yh], color=PAINEL, lw=1.2, zorder=3)

    # Grid + pontaletes
    n_c, n_r = 3, 2
    draw_pontaletes(ax, 0, 0, W, H, n_c, n_r, 0.14)

    # Label centro (layer Texto Secao)
    tag(ax, W / 2, H / 2, 'L101', LAJE_C, 10)

    # Nomenclatura acima (layer NOMENCLATURA)
    ax.text(W / 2, H + 0.8, 'TERREO - L101  300.0x200.0cm  paineis: 3x2',
            color=PAINEL, fontsize=7.5, ha='center', va='center', fontweight='bold',
            fontfamily='monospace',
            bbox=dict(facecolor=GRADE, alpha=0.3, pad=4, edgecolor=PAINEL, lw=0.8))

    # Cotas
    cota(ax, 0, -0.6, lv[0], -0.6, '100cm', COTA_C, 6, 0)
    cota(ax, lv[0], -0.6, lv[1], -0.6, '100cm', COTA_C, 6, 0)
    cota(ax, lv[1], -0.6, W, -0.6, '100cm', COTA_C, 6, 0)
    cota(ax, 0, -1.3, W, -1.3, '300cm (total)', COTA_C, 6.5, 0)
    cota(ax, -0.6, 0, -0.6, lh[0], '100cm', COTA_C, 6, 0)
    cota(ax, -0.6, lh[0], -0.6, H, '100cm', COTA_C, 6, 0)
    cota(ax, -1.3, 0, -1.3, H, '200cm', COTA_C, 6.5, 0)

    # Layer legend
    legend_items = [
        Line2D([0], [0], color=LAJE_C, lw=2.5, label='Contorno'),
        mpatches.Patch(fc=PAINEL, ec=PAINEL, alpha=0.3, label='Paineis'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=PILAR_C,
               markersize=6, label='Pontaletes', lw=0),
        Line2D([0], [0], color=COTA_C, lw=1, label='Cotas'),
    ]
    ax.legend(handles=legend_items, loc='upper right', fontsize=6,
              facecolor=BG, edgecolor=GRADE, labelcolor=TEXTO,
              framealpha=0.9)

    ax.set_xlim(-2.5, W + 2)
    ax.set_ylim(-2.5, H + 2.5)

    # --- Config dict ---
    ax2 = fig.add_axes([0.08, 0.06, 0.84, 0.38])
    ax2.set_facecolor(BG)
    ax2.axis('off')
    mono_block(ax2, 0.03, 0.95, [
        'CONFIG_DICT (saida do Motor Fase 4):',
        '',
        '  {',
        '    "id": "laje_001",',
        '    "label": "L101",',
        '    "area": 60000.0,         # 300 x 200 cm2',
        '    "width": 300.0,',
        '    "height": 200.0,',
        '    "outline": [[0,0],[300,0],[300,200],[0,200]],',
        '    "n_cols": 3,             # ceil(300/122) = 3',
        '    "n_rows": 2,             # ceil(200/122) = 2',
        '    "grid_step_x": 100.0,    # 300/3',
        '    "grid_step_y": 100.0,    # 200/2',
        '    "espessura": 12.0,',
        '    "bordering_vigas": ["V1","V2","V3","V4"]',
        '  }',
        '',
        'DATACLASS (Robo_Lajes laje.py):',
        '  numero=101, nome="L101", comprimento=300, largura=200,',
        '  pavimento="TERREO", coordenadas=[(0,0),(300,0),...],',
        '  linhas_verticais=[{value:100},{value:200}],',
        '  linhas_horizontais=[{value:100}]',
    ], fs=5.5, fc=TEXTO, lh=0.044)

    rodape(fig, 14, 'L-12 Exemplo Completo L101')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  PG 15: L-13 Campos de Dados + Validacao
# =========================================================================
def page_l13_campos(pdf):
    fig = new_fig('L-13  CAMPOS DE DADOS + VALIDACAO', 'Todos os campos do dataclass Laje e config_dict')

    ax = fig.add_axes([0.06, 0.50, 0.88, 0.42])
    ax.set_facecolor(BG)
    ax.axis('off')

    mono_block(ax, 0.02, 0.98, [
        'DATACLASS Laje (Robo_Lajes/laje_src/models/laje.py):',
        '',
        '  CAMPO                TIPO                           DEFAULT',
        '  -------------------  ----------------------------   ----------',
        '  numero               int                            0',
        '  nome                 str                            ""',
        '  comprimento          float (cm)                     0.0',
        '  largura              float (cm)                     0.0',
        '  pavimento            str                            ""',
        '  coordenadas          List[Tuple[float,float]]       []',
        '  area_cm2             float                          0.0',
        '  linhas_verticais     List[Dict{value,is_union}]     []',
        '  linhas_horizontais   List[Dict{value,is_union}]     []',
        '  obstaculos           List[List[Tuple[float,float]]] []',
        '  modo_selecionado     int (0=M1, 1=M2)              0',
        '  unioes_nos_bordes    bool                           False',
        '  observacoes          str                            ""',
        '  reaproveitamento     Dict                           {}',
        '  sobras_recebidas     List[Dict]                     []',
        '  excluded_dimensions  List[Dict]                     []',
        '  manual_dimensions    List[Dict]                     []',
        '  marco_joined_pos     Dict{v:[],h:[]}                {v:[],h:[]}',
        '  dimension_positions  Dict{id:{pos_x,pos_y}}         {}',
    ], fs=5.5, fc=TEXTO, lh=0.044)

    ax2 = fig.add_axes([0.06, 0.06, 0.88, 0.42])
    ax2.set_facecolor(BG)
    ax2.axis('off')

    mono_block(ax2, 0.02, 0.98, [
        'CONFIG_DICT (Motor Fase 4 calcular_lajes):',
        '',
        '  CAMPO           TIPO        CALCULO',
        '  --------------- ----------  --------------------------------',
        '  id               str         entity id do vectorizer',
        '  label            str         "L101" (regex ou sequencial)',
        '  area             float       width * height (cm2)',
        '  width            float       abs(bbox_x_max - bbox_x_min)',
        '  height           float       abs(bbox_y_max - bbox_y_min)',
        '  outline          List[List]  points_json ou bbox fallback',
        '  n_cols           int         max(1, round(width/122))',
        '  n_rows           int         max(1, round(height/122))',
        '  grid_step_x      float       width / n_cols',
        '  grid_step_y      float       height / n_rows',
        '  espessura        float       self.laje_espessura (default 12)',
        '  bordering_vigas  List[str]   rel VIGA_BORDA_LAJE do kb',
        '',
        'VALIDACOES (from_dict):',
        '  - max 1000 coordenadas | max 50 obstaculos',
        '  - min 3 pontos para poligono valido',
        '  - coordenadas: nao NaN, nao Inf, abs < 10^7',
        '  - area < 1 cm2 -> laje invalida (skip)',
        '  - linhas_v/h: normalize (float->Dict) para compat',
    ], fs=5.5, fc=TEXTO, lh=0.044)

    rodape(fig, 15, 'L-13 Campos de Dados + Validacao')
    pdf.savefig(fig); plt.close(fig)


# =========================================================================
#  MAIN
# =========================================================================
def main():
    with PdfPages(str(OUT)) as pdf:
        page_capa(pdf)              # PG 1
        page_indice(pdf)            # PG 2
        page_l01_anatomia(pdf)      # PG 3
        page_l02_forma_fundo(pdf)   # PG 4
        page_l03_grade(pdf)         # PG 5
        page_l04_espessuras(pdf)    # PG 6
        page_l05_irregular(pdf)     # PG 7
        page_l06_abertura(pdf)      # PG 8
        page_l07_acrescimo(pdf)     # PG 9
        page_l08_bordering(pdf)     # PG 10
        page_l09_corte(pdf)         # PG 11
        page_l10_tipos(pdf)         # PG 12
        page_l11_nomenclatura(pdf)  # PG 13
        page_l12_exemplo(pdf)       # PG 14
        page_l13_campos(pdf)        # PG 15

    size_kb = OUT.stat().st_size // 1024
    print(f'Atlas Lajes: {OUT} ({size_kb}KB, 15 paginas)')


if __name__ == '__main__':
    main()
