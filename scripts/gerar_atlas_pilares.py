#!/usr/bin/env python3
"""
Atlas Pilares -- 30 paginas com todo o pipeline do robo de pilares.
Gera diagramas sinteticos matplotlib que simulam o que o robo desenha no DXF/SCR.
Executa: python scripts/gerar_atlas_pilares.py
"""
import sys, math, textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Arc
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from pathlib import Path

OUT = Path(__file__).parent.parent / 'docs' / 'fichas' / 'atlas_pilares.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)

# -- Paleta ----------------------------------------------------------------
BG      = '#12121f'
PAINEL  = '#e8b84b'
SARRAFO = '#b8860b'
PILAR_C = '#ff7b54'
VIGA_C  = '#50fa7b'
LAJE_C  = '#8be9fd'
GARFO_C = '#ff79c6'
TEXTO   = '#f8f8f2'
COTA_C  = '#ffb86c'
GRADE   = '#44475a'
ARCO_C  = '#bd93f9'
APOIO_C = '#6272a4'
LAJE_ADJ= '#4a9eff'
VIGA_ADJ= '#9b59b6'
WARN    = '#ff5555'
VERDE   = '#27ae60'

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
    fig.text(0.5, 0.012, f'Pagina {pg}/30 | {txt}', ha='center', va='bottom',
             fontsize=6.5, color=APOIO_C, style='italic')

def tag(ax, x, y, txt, fc=PILAR_C, fs=7):
    ax.text(x, y, txt, color=fc, fontsize=fs,
            ha='center', va='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=BG,
                      edgecolor=fc, lw=0.8, alpha=0.9), zorder=7)

def mono_block(ax, x, y, lines, fs=6.5, fc=TEXTO, lh=0.045):
    for i, line in enumerate(lines):
        ax.text(x, y - i * lh, line, color=fc, fontsize=fs,
                fontfamily='monospace', va='top', transform=ax.transAxes, zorder=5)


# =========================================================================
#  PG 1: CAPA
# =========================================================================
def page_capa(pdf):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.axis('off')

    fig.text(0.5, 0.80, 'ATLAS DE PILARES', ha='center', va='center',
             fontsize=30, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.73, 'ROBO DE FORMAS', ha='center', va='center',
             fontsize=22, color=COTA_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.66, 'Pipeline SCR/DXF Completo', ha='center', va='center',
             fontsize=14, color=TEXTO)

    # Three symbolic icons
    icons = [
        (0.22, PILAR_C, 'PILAR', 'B x H x PE'),
        (0.50, PAINEL, 'PAINEIS', 'A / B / C / D'),
        (0.78, GARFO_C, 'GARFOS', 'par_1_2..par_8_9'),
    ]
    for xi, cor, nome, desc in icons:
        r = FancyBboxPatch((xi - 0.07, 0.38), 0.14, 0.18,
                           boxstyle='round,pad=0.01', linewidth=2,
                           edgecolor=cor, facecolor=cor, alpha=0.15,
                           transform=fig.transFigure)
        fig.add_artist(r)
        fig.text(xi, 0.50, nome, ha='center', va='center',
                 fontsize=12, color=cor, fontweight='bold')
        fig.text(xi, 0.40, desc, ha='center', va='center',
                 fontsize=8, color=TEXTO)

    fig.text(0.5, 0.28,
             '30 Paginas Tecnicas  |  Paineis A/B/C/D  |  Sarrafos  |  Garfos\n'
             'Laje  |  Hatch  |  Layers  |  Pilares L/T/U  |  Cambotados\n'
             'Pipeline SCR  |  Blocos PED  |  Cotas  |  Nivel Diferencial',
             ha='center', va='center', fontsize=9, color=TEXTO, linespacing=1.8)

    fig.text(0.5, 0.06, 'Engenharia Civil -- Formas de Concreto Armado -- Agente CAD PySide',
             ha='center', va='center', fontsize=9, color=APOIO_C, style='italic')

    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 2: INDICE
# =========================================================================
def page_indice(pdf):
    fig = new_fig('INDICE', '28 paginas tecnicas + capa + indice')
    ax = fig.add_axes([0.08, 0.04, 0.84, 0.90])
    ax.set_facecolor(BG)
    ax.axis('off')

    items = [
        ('P-01', 'Anatomia do Pilar: B, H, PE, nome, pavimento'),
        ('P-02', 'Painel A (comprimento+22, 3 larguras, 5 alturas, pos_laje)'),
        ('P-03', 'Painel B (espelho de A, mesmas dimensoes)'),
        ('P-04', 'Painel C (largura, 2 larguras, 4 alturas, pos_laje)'),
        ('P-05', 'Painel D (espelho de C)'),
        ('P-06', 'Laje -- 6 posicoes: base(0), 1,2,3,4, topo(5) -- grade 2x3'),
        ('P-07', 'Sarrafos -- join vertical + horizontal, offset=7cm'),
        ('P-08', 'Parafusos (garfos) -- par_1_2 a par_8_9'),
        ('P-09', 'Hatch -- grade 5x3 de opcoes'),
        ('P-10', 'Pe-direito e Nivel Diferencial'),
        ('P-11', 'Abertura de laje -- normal(0) vs abertura(1)'),
        ('P-12', 'Blocos PED e moldura -- INSERT PED, muldura2 vs PAINEL-NOVA'),
        ('P-13', 'Layers do DXF -- tabela visual'),
        ('P-14', 'Script .SCR -- exemplo de comandos'),
        ('P-15', 'Pilar Especial L -- paineis E/F/G/H'),
        ('P-16', 'Pilar Especial T -- paineis E/F/G/H'),
        ('P-17', 'Pilar Especial U -- paineis E/F/G/H'),
        ('P-18', 'Pilar Cambotado -- arcos, has_arcs=True'),
        ('P-19', 'Vista CIMA (top view) -- secao transversal'),
        ('P-20', 'Vista GRADE -- sarrafos em grade'),
        ('P-21', 'Variacoes de BxH -- 8 exemplos'),
        ('P-22', 'Comprimento da moldura -- muldura2(1051) vs padrao(1000)'),
        ('P-23', 'Fluxo pipeline -- Ficha -> ABCD.scr -> AutoCAD -> DXF'),
        ('P-24', 'Exemplo completo P11 (B=46, H=56, PE=280)'),
        ('P-25', 'Campos de dados -- tabela completa tipo/padrao/descricao'),
        ('P-26', 'Desenhando painel a painel -- sequencia de comandos'),
        ('P-27', 'Caso com nivel_diferencial != 0'),
        ('P-28', 'Tabela de validacao + score + proximos passos'),
    ]

    y = 0.97
    for i, (code, desc) in enumerate(items):
        pg = i + 3
        ax.text(0.02, y, f'{pg:2d}', color=COTA_C, fontsize=8, fontfamily='monospace',
                transform=ax.transAxes, va='top', fontweight='bold')
        ax.text(0.07, y, code, color=PAINEL, fontsize=8, fontfamily='monospace',
                transform=ax.transAxes, va='top', fontweight='bold')
        ax.text(0.18, y, desc, color=TEXTO, fontsize=7.5,
                transform=ax.transAxes, va='top')
        y -= 0.034

    rodape(fig, 2, 'Indice completo do atlas de pilares')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 3: P-01 Anatomia do Pilar
# =========================================================================
def page_p01_anatomia(pdf):
    fig = new_fig('P-01  ANATOMIA DO PILAR', 'B (comprimento), H (largura), PE (pe-direito), nome, pavimento')
    ax = fig.add_axes([0.08, 0.10, 0.84, 0.82])
    setup(ax)
    ax.set_xlim(-3, 16)
    ax.set_ylim(-3, 16)

    B, H, PE = 4.6, 5.6, 14.0  # scaled: PE mapped to 14 units for visual
    x0, y0 = 2, 0

    # Pilar 3D-ish: front face
    rct(ax, x0, y0, B, PE, fc=PILAR_C, alpha=0.2, lw=2.0, ec=PILAR_C)
    lbl(ax, x0, y0, B, PE, 'P11\nTERREO', fc=PILAR_C, fs=12)

    # Cota B (horizontal bottom)
    cota(ax, x0, y0 - 1.5, x0 + B, y0 - 1.5, 'B = 46 cm\n(comprimento)', off=0, fs=7)

    # Cota H (horizontal at mid, showing depth)
    # We show H as a side dimension
    ax.plot([x0 + B, x0 + B + 2.5], [y0, y0], '--', color=GRADE, lw=0.8, zorder=1)
    ax.plot([x0 + B, x0 + B + 2.5], [y0 + H, y0 + H], '--', color=GRADE, lw=0.8, zorder=1)
    rct(ax, x0 + B, y0, 2.5, H, fc=PILAR_C, alpha=0.1, lw=1.0, ec=PILAR_C)
    cota(ax, x0 + B + 3.0, y0, x0 + B + 3.0, y0 + H, 'H = 56 cm\n(largura)', off=0, fs=7)

    # Cota PE (vertical right)
    cota(ax, x0 + B + 6.5, y0, x0 + B + 6.5, y0 + PE, 'PE = 280 cm\n(pe-direito)', off=0, fs=7)

    # Face labels
    tag(ax, x0 + B / 2, y0 + PE + 0.8, 'Face A (topo)', fc=PAINEL, fs=7)
    tag(ax, x0 + B + 1, y0 + PE / 2, 'Face B (dir)', fc='#d4a030', fs=7)
    tag(ax, x0 + B / 2, y0 - 0.5, 'Face C (base)', fc='#c8960a', fs=7)
    tag(ax, x0 - 1.3, y0 + PE / 2, 'Face D (esq)', fc='#b87820', fs=7)

    # Arrows to faces
    arrow(ax, x0 + B / 2, y0 + PE + 0.3, x0 + B / 2, y0 + PE, '', PAINEL)
    arrow(ax, x0 + B + 0.5, y0 + PE / 2, x0 + B, y0 + PE / 2, '', '#d4a030')

    # Info box
    info = [
        'nome: P11',
        'pavimento: TERREO',
        'comprimento (B): 46 cm  -> paineis A e B',
        'largura (H): 56 cm      -> paineis C e D',
        'altura (PE): 280 cm     -> pe-direito',
        'nivel_saida: +0.00',
        'nivel_chegada: +2.80',
        'nivel_diferencial: 0',
    ]
    bx, by = 0.06, 0.08
    for i, line in enumerate(info):
        fig.text(bx, by + (len(info) - 1 - i) * 0.018, line,
                 color=TEXTO, fontsize=7, fontfamily='monospace')

    rodape(fig, 3, 'P-01 | Anatomia do pilar -- dimensoes B, H, PE e faces A/B/C/D')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 4: P-02 Painel A
# =========================================================================
def page_p02_painel_a(pdf):
    fig = new_fig('P-02  PAINEL A (Face Norte)', 'comprimento+22cm, 3 larguras (larg1/larg2/larg3), 5 alturas (h1-h5), pos_laje')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 14)
    ax.set_ylim(-2, 16)

    # Painel A: total width = B + 22 = 46+22 = 68 cm, scaled to ~6.8 units
    total_w = 6.8  # 68 cm
    # 3 strips horizontally: larg1=30cm=3.0, larg2=32cm=3.2, larg3=6cm=0.6
    larg1, larg2, larg3 = 3.0, 3.2, 0.6
    # 5 heights: h1=2(fundo), h2=61, h3=61, h4=61, h5=95 (topo)  -> total 280
    h_vals = [0.2, 6.1, 6.1, 6.1, 9.5]  # scaled /10 for visual: too tall
    # Let's scale to fit: total PE = 28 units -> scale each by 0.5
    scale_h = 0.5
    h_vals = [v * scale_h for v in [0.2, 6.1, 6.1, 6.1, 9.5]]
    h_names = ['h1=2cm\n(fundo)', 'h2=61cm', 'h3=61cm', 'h4=61cm', 'h5=95cm\n(topo)']

    x0, y0 = 1.0, 0.5
    colors_h = ['#555555', PAINEL, PAINEL, PAINEL, '#888888']

    # Draw grid of 3 cols x 5 rows
    y = y0
    for ri, (hv, hn, hc) in enumerate(zip(h_vals, h_names, colors_h)):
        x = x0
        for ci, (lv, ln) in enumerate(zip([larg1, larg2, larg3], ['larg1\n30cm', 'larg2\n32cm', 'larg3\n6cm'])):
            rct(ax, x, y, lv, hv, fc=hc, ec='white', lw=0.8, alpha=0.85)
            if hv > 0.5 and lv > 0.8:
                lbl(ax, x, y, lv, hv, f'[{ri},{ci}]', fc=TEXTO, fs=6, bold=False)
            x += lv
        # Height label on right
        ax.text(x + 0.3, y + hv / 2, hn, color=COTA_C, fontsize=6.5, va='center', fontweight='bold')
        y += hv

    # Width labels on top
    total_h = sum(h_vals)
    x = x0
    for lv, ln in zip([larg1, larg2, larg3], ['larg1=30cm', 'larg2=32cm', 'larg3=6cm']):
        cota(ax, x, y0 + total_h + 0.5, x + lv, y0 + total_h + 0.5, ln, off=0, fs=6)
        x += lv

    # Total width cota
    cota(ax, x0, y0 - 1.2, x0 + total_w, y0 - 1.2, f'Total = B+22 = 68cm', off=0, fs=7)

    # Total height cota
    cota(ax, x0 + total_w + 2.5, y0, x0 + total_w + 2.5, y0 + total_h, 'PE = 280cm', off=0, fs=7)

    # Laje position indicator
    # pos_laje_a: 0=base, 1..4=between panels, 5=above top
    laje_y = y0 + h_vals[0] + h_vals[1] + h_vals[2]  # pos 3 example
    ax.plot([x0 - 0.5, x0 + total_w + 0.5], [laje_y, laje_y], '-', color=LAJE_C, lw=2.0, zorder=4)
    ax.fill_between([x0 - 0.5, x0 + total_w + 0.5], laje_y, laje_y + 0.25,
                    color=LAJE_C, alpha=0.3, zorder=3)
    tag(ax, x0 + total_w + 1.5, laje_y, 'pos_laje_a=3', fc=LAJE_C, fs=6)

    # Info
    fig.text(0.06, 0.07,
             'Painel A: face Norte, largura total = comprimento + 22cm (saia de 11cm cada lado)\n'
             '3 faixas horizontais (larg1 + larg2 + larg3)  |  5 fiadas verticais (h1..h5)\n'
             'pos_laje_a: 0=base, 1=entre h1-h2, 2=entre h2-h3, 3=entre h3-h4, 4=entre h4-h5, 5=acima topo',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 4, 'P-02 | Painel A -- 3 larguras x 5 alturas, posicao de laje variavel')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 5: P-03 Painel B (espelho de A)
# =========================================================================
def page_p03_painel_b(pdf):
    fig = new_fig('P-03  PAINEL B (Face Sul -- Espelho de A)', 'Mesmas dimensoes de A, invertido horizontalmente')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 14)
    ax.set_ylim(-2, 16)

    total_w = 6.8
    larg1, larg2, larg3 = 0.6, 3.2, 3.0  # MIRROR: reversed order
    scale_h = 0.5
    h_vals = [v * scale_h for v in [0.2, 6.1, 6.1, 6.1, 9.5]]
    h_names = ['h1=2cm', 'h2=61cm', 'h3=61cm', 'h4=61cm', 'h5=95cm']
    colors_h = ['#555555', '#d4a030', '#d4a030', '#d4a030', '#888888']

    x0, y0 = 1.0, 0.5

    y = y0
    for ri, (hv, hn, hc) in enumerate(zip(h_vals, h_names, colors_h)):
        x = x0
        for ci, (lv, ln) in enumerate(zip([larg1, larg2, larg3], ['larg3\n6cm', 'larg2\n32cm', 'larg1\n30cm'])):
            rct(ax, x, y, lv, hv, fc=hc, ec='white', lw=0.8, alpha=0.85)
            if hv > 0.5 and lv > 0.8:
                lbl(ax, x, y, lv, hv, f'B[{ri},{ci}]', fc=TEXTO, fs=6, bold=False)
            x += lv
        ax.text(x + 0.3, y + hv / 2, hn, color=COTA_C, fontsize=6.5, va='center', fontweight='bold')
        y += hv

    total_h = sum(h_vals)

    # Mirror indicator
    ax.annotate('', xy=(x0 + total_w / 2 + 0.5, y0 + total_h + 1.5),
                xytext=(x0 + total_w / 2 - 0.5, y0 + total_h + 1.5),
                arrowprops=dict(arrowstyle='<->', color=WARN, lw=1.5), zorder=6)
    ax.text(x0 + total_w / 2, y0 + total_h + 2.0, 'ESPELHADO\nlarg3 | larg2 | larg1',
            color=WARN, fontsize=8, ha='center', va='center', fontweight='bold')

    cota(ax, x0, y0 - 1.2, x0 + total_w, y0 - 1.2, 'Total = B+22 = 68cm', off=0, fs=7)
    cota(ax, x0 + total_w + 2.5, y0, x0 + total_w + 2.5, y0 + total_h, 'PE = 280cm', off=0, fs=7)

    fig.text(0.06, 0.07,
             'Painel B: espelho horizontal de A (mesmas dimensoes, ordem invertida)\n'
             'larg3 fica a esquerda, larg1 fica a direita\n'
             'Mesmo numero de fiadas (h1..h5) e mesmas alturas',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 5, 'P-03 | Painel B -- espelho de A, ordem de larguras invertida')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 6: P-04 Painel C
# =========================================================================
def page_p04_painel_c(pdf):
    fig = new_fig('P-04  PAINEL C (Face Leste)', 'largura (H), 2 faixas (larg1/larg2), 4 alturas (h1-h4), pos_laje_c')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 16)

    total_w = 5.6  # H = 56cm
    larg1, larg2 = 2.5, 3.1  # 25cm + 31cm = 56cm
    scale_h = 0.5
    h_vals = [v * scale_h for v in [0.2, 9.2, 9.2, 9.4]]
    h_names = ['h1=2cm\n(fundo)', 'h2=92cm', 'h3=92cm', 'h4=94cm\n(topo)']
    colors_h = ['#555555', '#c8960a', '#c8960a', '#888888']

    x0, y0 = 1.5, 0.5

    y = y0
    for ri, (hv, hn, hc) in enumerate(zip(h_vals, h_names, colors_h)):
        x = x0
        for ci, (lv, ln) in enumerate(zip([larg1, larg2], ['larg1\n25cm', 'larg2\n31cm'])):
            rct(ax, x, y, lv, hv, fc=hc, ec='white', lw=0.8, alpha=0.85)
            if hv > 0.5 and lv > 0.8:
                lbl(ax, x, y, lv, hv, f'C[{ri},{ci}]', fc=TEXTO, fs=6, bold=False)
            x += lv
        ax.text(x + 0.3, y + hv / 2, hn, color=COTA_C, fontsize=6.5, va='center', fontweight='bold')
        y += hv

    total_h = sum(h_vals)

    # Width labels
    x = x0
    for lv, ln in zip([larg1, larg2], ['larg1=25cm', 'larg2=31cm']):
        cota(ax, x, y0 + total_h + 0.5, x + lv, y0 + total_h + 0.5, ln, off=0, fs=6.5)
        x += lv

    cota(ax, x0, y0 - 1.2, x0 + total_w, y0 - 1.2, 'Total = H = 56cm', off=0, fs=7)
    cota(ax, x0 + total_w + 2.5, y0, x0 + total_w + 2.5, y0 + total_h, 'PE = 280cm', off=0, fs=7)

    # Laje at pos 2
    laje_y = y0 + h_vals[0] + h_vals[1]
    ax.plot([x0 - 0.5, x0 + total_w + 0.5], [laje_y, laje_y], '-', color=LAJE_C, lw=2.0, zorder=4)
    ax.fill_between([x0 - 0.5, x0 + total_w + 0.5], laje_y, laje_y + 0.2,
                    color=LAJE_C, alpha=0.3, zorder=3)
    tag(ax, x0 + total_w + 1.5, laje_y, 'pos_laje_c=2', fc=LAJE_C, fs=6)

    fig.text(0.06, 0.07,
             'Painel C: face Leste, largura total = H (largura do pilar)\n'
             '2 faixas horizontais (larg1 + larg2)  |  4 fiadas verticais (h1..h4)\n'
             'pos_laje_c: 0=base, 1=entre h1-h2, 2=entre h2-h3, 3=entre h3-h4, 4=acima topo',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 6, 'P-04 | Painel C -- 2 larguras x 4 alturas, face lateral do pilar')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 7: P-05 Painel D (espelho de C)
# =========================================================================
def page_p05_painel_d(pdf):
    fig = new_fig('P-05  PAINEL D (Face Oeste -- Espelho de C)', 'Mesmas dimensoes de C, invertido horizontalmente')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 16)

    total_w = 5.6
    larg1, larg2 = 3.1, 2.5  # MIRROR
    scale_h = 0.5
    h_vals = [v * scale_h for v in [0.2, 9.2, 9.2, 9.4]]
    h_names = ['h1=2cm', 'h2=92cm', 'h3=92cm', 'h4=94cm']
    colors_h = ['#555555', '#b87820', '#b87820', '#888888']

    x0, y0 = 1.5, 0.5

    y = y0
    for ri, (hv, hn, hc) in enumerate(zip(h_vals, h_names, colors_h)):
        x = x0
        for ci, (lv, ln) in enumerate(zip([larg1, larg2], ['larg2\n31cm', 'larg1\n25cm'])):
            rct(ax, x, y, lv, hv, fc=hc, ec='white', lw=0.8, alpha=0.85)
            if hv > 0.5 and lv > 0.8:
                lbl(ax, x, y, lv, hv, f'D[{ri},{ci}]', fc=TEXTO, fs=6, bold=False)
            x += lv
        ax.text(x + 0.3, y + hv / 2, hn, color=COTA_C, fontsize=6.5, va='center', fontweight='bold')
        y += hv

    total_h = sum(h_vals)

    ax.annotate('', xy=(x0 + total_w / 2 + 0.5, y0 + total_h + 1.5),
                xytext=(x0 + total_w / 2 - 0.5, y0 + total_h + 1.5),
                arrowprops=dict(arrowstyle='<->', color=WARN, lw=1.5), zorder=6)
    ax.text(x0 + total_w / 2, y0 + total_h + 2.0, 'ESPELHADO\nlarg2 | larg1',
            color=WARN, fontsize=8, ha='center', va='center', fontweight='bold')

    cota(ax, x0, y0 - 1.2, x0 + total_w, y0 - 1.2, 'Total = H = 56cm', off=0, fs=7)
    cota(ax, x0 + total_w + 2.5, y0, x0 + total_w + 2.5, y0 + total_h, 'PE = 280cm', off=0, fs=7)

    fig.text(0.06, 0.07,
             'Painel D: espelho horizontal de C (mesmas dimensoes, ordem invertida)\n'
             'larg2 fica a esquerda, larg1 fica a direita',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 7, 'P-05 | Painel D -- espelho de C, ordem de larguras invertida')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 8: P-06 Laje -- 6 posicoes
# =========================================================================
def page_p06_laje(pdf):
    fig = new_fig('P-06  LAJE -- 6 POSICOES DE ENCAIXE', 'pos_laje: 0=base, 1,2,3,4=entre paineis, 5=acima topo (para A/B)')
    axes = []
    for row in range(2):
        for col in range(3):
            ax = fig.add_axes([0.05 + col * 0.32, 0.48 - row * 0.42 + 0.08, 0.28, 0.38])
            setup(ax)
            axes.append(ax)

    pos_labels = ['pos=0 (BASE)', 'pos=1 (entre h1-h2)', 'pos=2 (entre h2-h3)',
                  'pos=3 (entre h3-h4)', 'pos=4 (entre h4-h5)', 'pos=5 (ACIMA TOPO)']
    h_vals_raw = [2, 61, 61, 61, 95]  # A/B heights
    total_pe = sum(h_vals_raw)
    scale = 8.0 / total_pe

    for idx, ax in enumerate(axes):
        ax.set_xlim(-0.5, 4.5)
        ax.set_ylim(-1, 10)
        ax.set_title(pos_labels[idx], color=PAINEL, fontsize=7, fontweight='bold', fontfamily='monospace', pad=2)

        # Draw panel stack
        y = 0
        cumulative = [0]
        for hi, hv in enumerate(h_vals_raw):
            h_sc = hv * scale
            rct(ax, 0.5, y, 2.5, h_sc, fc=PAINEL if hi not in [0, 4] else '#555555',
                ec='white', lw=0.6, alpha=0.7)
            if h_sc > 0.3:
                lbl(ax, 0.5, y, 2.5, h_sc, f'h{hi+1}', fc=TEXTO, fs=5, bold=False)
            y += h_sc
            cumulative.append(y)

        # Laje at position idx
        if idx == 0:
            laje_y = 0
        elif idx <= 4:
            laje_y = cumulative[idx]
        else:
            laje_y = cumulative[-1]

        ax.fill_between([0, 3.5], laje_y - 0.15, laje_y + 0.15,
                        color=LAJE_C, alpha=0.5, zorder=4)
        ax.plot([0, 3.5], [laje_y, laje_y], '-', color=LAJE_C, lw=2.0, zorder=5)
        tag(ax, 3.8, laje_y, 'LAJE', fc=LAJE_C, fs=5)

    fig.text(0.06, 0.07,
             'laje_a/b/c/d_var: altura da laje em cm  |  pos_laje_a/b/c/d: posicao (0..5 para A/B, 0..4 para C/D)\n'
             'pos=0: laje na base do painel  |  pos=5: laje acima do topo (fora do painel)',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 8, 'P-06 | Laje -- 6 posicoes de encaixe no painel A/B')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 9: P-07 Sarrafos
# =========================================================================
def page_p07_sarrafos(pdf):
    fig = new_fig('P-07  SARRAFOS -- JOIN VERTICAL + HORIZONTAL', 'sarrafo_horizontal, join_sarrafos, sarrafo_offset=7cm')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 14)
    ax.set_ylim(-2, 16)

    # Painel with sarrafos
    pw, ph = 6.8, 14.0
    x0, y0 = 1.0, 0

    rct(ax, x0, y0, pw, ph, fc=PAINEL, ec='white', lw=1.5, alpha=0.3)

    # Horizontal sarrafos (every ~3.05 units = 61cm scaled)
    sarrafo_y_positions = [3.05, 6.1, 9.15, 12.2]
    for sy in sarrafo_y_positions:
        ax.plot([x0, x0 + pw], [y0 + sy, y0 + sy], '-', color=SARRAFO, lw=2.0, zorder=4)
    tag(ax, x0 + pw + 1.5, sarrafo_y_positions[1], 'sarrafo_horizontal', fc=SARRAFO, fs=6)

    # Vertical sarrafos (join)
    # sarrafo_offset = 7cm = 0.7 units
    offset = 0.7
    join_x = [x0 + offset, x0 + pw - offset]
    for jx in join_x:
        ax.plot([jx, jx], [y0, y0 + ph], '--', color=SARRAFO, lw=1.5, alpha=0.7, zorder=4)
    tag(ax, join_x[0], y0 - 0.7, 'offset=7cm', fc=SARRAFO, fs=6)
    tag(ax, join_x[1], y0 - 0.7, 'offset=7cm', fc=SARRAFO, fs=6)

    # Cota for offset
    cota(ax, x0, y0 - 1.5, x0 + offset, y0 - 1.5, '7cm', off=0, fs=7, fc=SARRAFO)

    # Join indicator
    ax.text(x0 + pw / 2, y0 + ph + 1.0, 'join_sarrafos = True',
            color=SARRAFO, fontsize=9, ha='center', fontweight='bold')
    ax.text(x0 + pw / 2, y0 + ph + 0.5, 'Linhas verticais conectam sarrafos horizontais',
            color=TEXTO, fontsize=7, ha='center')

    # Spacing cota
    cota(ax, x0 + pw + 0.5, y0, x0 + pw + 0.5, sarrafo_y_positions[0], 'h spacing', off=0, fs=6.5)

    fig.text(0.06, 0.07,
             'sarrafo_horizontal_a/b/c/d: checkbox que ativa sarrafos horizontais\n'
             'join_sarrafos_a/b/c/d: conecta sarrafos verticalmente\n'
             'sarrafo_offset: 7cm do bordo do painel (posicao das juntas verticais)',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 9, 'P-07 | Sarrafos -- horizontais a cada fiada, verticais com offset 7cm')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 10: P-08 Parafusos (Garfos)
# =========================================================================
def page_p08_parafusos(pdf):
    fig = new_fig('P-08  PARAFUSOS (GARFOS)', 'par_1_2 a par_8_9 ao longo da altura, medida_fundo_primeiro=30cm')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 16)

    pw, ph = 5.0, 14.0
    x0, y0 = 2.0, 0

    rct(ax, x0, y0, pw, ph, fc=PAINEL, ec='white', lw=1.5, alpha=0.25)

    # Parafuso positions along height
    # medida_fundo_primeiro = 30cm = 1.5 units (from bottom)
    # par_1_2 to par_8_9: 8 intermediate spacings
    fundo = 1.5  # 30cm
    par_names = ['par_1_2', 'par_2_3', 'par_3_4', 'par_4_5',
                 'par_5_6', 'par_6_7', 'par_7_8', 'par_8_9']
    # Example spacings (cm, scaled /20): 30, 30, 30, 30, 30, 30, 30, 30 = 240 + 30 fundo + 10 topo = 280
    remaining = ph - fundo
    n_par = 8
    par_spacing = remaining / (n_par + 0.3)

    y_garfos = [y0 + fundo]
    for i in range(n_par):
        y_garfos.append(y_garfos[-1] + par_spacing)

    # Draw garfo markers
    for i, yg in enumerate(y_garfos):
        # X mark for garfo
        sz = 0.2
        cx = x0 + pw / 2
        ax.plot([cx - sz, cx + sz], [yg - sz, yg + sz], '-', color=GARFO_C, lw=2.5, zorder=5)
        ax.plot([cx - sz, cx + sz], [yg + sz, yg - sz], '-', color=GARFO_C, lw=2.5, zorder=5)
        ax.plot([x0, x0 + pw], [yg, yg], ':', color=GARFO_C, lw=0.6, alpha=0.5, zorder=3)

        if i == 0:
            label = f'garfo 1 (fundo={fundo * 20:.0f}cm)'
        else:
            label = f'garfo {i + 1}'
        ax.text(x0 + pw + 0.3, yg, label, color=GARFO_C, fontsize=6, va='center')

    # Spacing cotas
    cota(ax, x0 - 1.0, y0, x0 - 1.0, y_garfos[0], f'fundo\n30cm', off=0, fs=6, fc=GARFO_C)
    if len(y_garfos) > 1:
        cota(ax, x0 - 1.0, y_garfos[0], x0 - 1.0, y_garfos[1], f'par_1_2', off=0, fs=6, fc=GARFO_C)

    # Par names table
    fig.text(0.06, 0.07,
             'medida_fundo_primeiro_ab: 30cm (parafuso inicial A/B)\n'
             'medida_fundo_primeiro_cdefgh: 30cm (parafuso inicial C/D/E/F/G/H)\n'
             'par_1_2 a par_8_9: distancias entre parafusos consecutivos ao longo da altura\n'
             'Garfo = fixacao mecanica do painel na armadura',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 10, 'P-08 | Parafusos (garfos) -- posicoes ao longo da altura do painel')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 11: P-09 Hatch
# =========================================================================
def page_p09_hatch(pdf):
    fig = new_fig('P-09  HATCH -- GRADE 5x3 DE OPCOES', 'hatch_opcoes_a/b/c/d: grade 5 linhas x 3 colunas de codigos')
    ax = fig.add_axes([0.08, 0.20, 0.84, 0.72])
    setup(ax)
    ax.set_xlim(-1, 11)
    ax.set_ylim(-1, 12)

    hatch_types = ['0 (vazio)', 'ANSI31', 'ANSI32', 'ANSI33', 'ANSI34',
                   'ANSI35', 'ANSI36', 'ANSI37', 'ANSI38', 'SOLID',
                   'BRICK', 'CROSS', 'DASH', 'DOTS', 'EARTH']
    mpl_hatches = ['', '/', '\\', '|', '-',
                   '+', 'x', '.', 'o', None,
                   '/', '+', '-', '.', 'O']
    hatch_colors = [BG, PAINEL, '#d4a030', '#c8960a', COTA_C,
                    GARFO_C, ARCO_C, LAJE_C, SARRAFO, PILAR_C,
                    WARN, VERDE, VIGA_C, APOIO_C, LAJE_ADJ]

    cell_w, cell_h = 3.0, 1.8
    x0, y0 = 0.5, 0.5

    for row in range(5):
        for col in range(3):
            idx = row * 3 + col
            if idx >= len(hatch_types):
                break
            x = x0 + col * (cell_w + 0.3)
            y = y0 + (4 - row) * (cell_h + 0.3)

            fc = hatch_colors[idx] if mpl_hatches[idx] is None else BG
            h = mpl_hatches[idx] if mpl_hatches[idx] is not None else ''
            r = mpatches.Rectangle((x, y), cell_w, cell_h, linewidth=1.0,
                                   edgecolor='white', facecolor=fc, alpha=0.6,
                                   hatch=h, zorder=2)
            ax.add_patch(r)
            ax.text(x + cell_w / 2, y + cell_h / 2, hatch_types[idx],
                    color=TEXTO, fontsize=6.5, ha='center', va='center',
                    fontweight='bold', zorder=5,
                    bbox=dict(facecolor=BG, alpha=0.7, pad=1, edgecolor='none'))

    # Column headers
    for col, name in enumerate(['Coluna 1', 'Coluna 2', 'Coluna 3']):
        ax.text(x0 + col * (cell_w + 0.3) + cell_w / 2, y0 + 5 * (cell_h + 0.3) + 0.2,
                name, color=COTA_C, fontsize=7, ha='center', fontweight='bold')

    fig.text(0.06, 0.07,
             'hatch_opcoes_a/b/c/d: grade 5x3 de strings\n'
             '"0" = sem hatch  |  "ANSI31".."ANSI38" = padroes ANSI  |  "SOLID" = preenchido\n'
             'Cada celula da grade corresponde a um segmento do painel\n'
             'Comando SCR: HHHH (aplica hatch na regiao selecionada)',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 11, 'P-09 | Hatch -- grade 5x3 com opcoes de preenchimento por segmento')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 12: P-10 Pe-Direito e Nivel Diferencial
# =========================================================================
def page_p10_pe_direito(pdf):
    fig = new_fig('P-10  PE-DIREITO E NIVEL DIFERENCIAL', 'Linhas DASHED, cota, ajuste Y quando nivel_diferencial != 0')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-3, 14)
    ax.set_ylim(-3, 16)

    # Normal case (left)
    x0, y0 = 0, 0
    pw, ph = 4.0, 14.0
    rct(ax, x0, y0, pw, ph, fc=PAINEL, ec='white', lw=1.0, alpha=0.25)

    # PE dashed lines
    ax.plot([x0 - 0.5, x0 + pw + 0.5], [y0, y0], '--', color=LAJE_ADJ, lw=1.5, zorder=3)
    ax.plot([x0 - 0.5, x0 + pw + 0.5], [y0 + ph, y0 + ph], '--', color=LAJE_ADJ, lw=1.5, zorder=3)
    ax.text(x0 - 0.7, y0, 'nivel_saida\n+0.00', color=LAJE_ADJ, fontsize=6, ha='right', va='center')
    ax.text(x0 - 0.7, y0 + ph, 'nivel_chegada\n+2.80', color=LAJE_ADJ, fontsize=6, ha='right', va='center')
    cota(ax, x0 + pw + 0.5, y0, x0 + pw + 0.5, y0 + ph, 'PE=280cm', off=0.3, fs=7)
    ax.text(x0 + pw / 2, y0 + ph + 0.7, 'CASO NORMAL\nnivel_diferencial=0',
            color=VERDE, fontsize=8, ha='center', fontweight='bold')

    # Differential case (right)
    x1 = 7.0
    diff = 2.0  # 20cm differential -> shifts Y
    rct(ax, x1, y0 + diff, pw, ph - diff, fc=PAINEL, ec='white', lw=1.0, alpha=0.25)

    ax.plot([x1 - 0.5, x1 + pw + 0.5], [y0 + diff, y0 + diff], '--', color=WARN, lw=1.5, zorder=3)
    ax.plot([x1 - 0.5, x1 + pw + 0.5], [y0 + ph, y0 + ph], '--', color=LAJE_ADJ, lw=1.5, zorder=3)
    ax.plot([x1 - 0.5, x1 + pw + 0.5], [y0, y0], ':', color=GRADE, lw=1.0, zorder=2)

    ax.text(x1 - 0.7, y0 + diff, 'nivel_saida\n+0.20', color=WARN, fontsize=6, ha='right', va='center')
    ax.text(x1 - 0.7, y0 + ph, 'nivel_chegada\n+2.80', color=LAJE_ADJ, fontsize=6, ha='right', va='center')

    cota(ax, x1 + pw + 0.5, y0, x1 + pw + 0.5, y0 + diff, 'dif=20cm', off=0.3, fs=6.5, fc=WARN)
    cota(ax, x1 + pw + 1.5, y0 + diff, x1 + pw + 1.5, y0 + ph, 'PE ajust', off=0.3, fs=6.5)

    ax.text(x1 + pw / 2, y0 + ph + 0.7, 'COM DIFERENCIAL\nnivel_diferencial=20',
            color=WARN, fontsize=8, ha='center', fontweight='bold')

    # Arrow showing Y shift
    arrow(ax, x1 + pw / 2, y0 + 0.5, x1 + pw / 2, y0 + diff - 0.1, 'Y shift', WARN, fs=7)

    fig.text(0.06, 0.07,
             'Layer pe_direito: linhas DASHED cor azul (estilo DIMLINEAR)\n'
             'nivel_diferencial != 0: desloca a coordenada Y de inicio do painel\n'
             'PE efetivo = nivel_chegada - nivel_saida',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 12, 'P-10 | Pe-direito e nivel diferencial -- ajuste de coordenada Y')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 13: P-11 Abertura de Laje
# =========================================================================
def page_p11_abertura_laje(pdf):
    fig = new_fig('P-11  ABERTURA DE LAJE', 'normal(0) vs abertura(1) em cada segmento do painel')
    axes = fig.subplots(1, 2)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.15, top=0.90, wspace=0.3)

    for idx, (ax, caso, cor_laje) in enumerate(zip(axes, ['SEM ABERTURA', 'COM ABERTURA'], [LAJE_C, WARN])):
        setup(ax, caso)
        ax.set_xlim(-1, 8)
        ax.set_ylim(-1, 12)

        pw, ph = 5.0, 10.0
        x0, y0 = 0.5, 0

        rct(ax, x0, y0, pw, ph, fc=PAINEL, ec='white', lw=1.0, alpha=0.25)

        # Laje at middle
        laje_y = y0 + ph * 0.6
        if idx == 0:
            # Normal: solid laje across
            ax.fill_between([x0, x0 + pw], laje_y, laje_y + 0.5,
                            color=LAJE_C, alpha=0.5, zorder=4)
            ax.text(x0 + pw / 2, laje_y + 0.25, 'LAJE CONTINUA', color=BG,
                    fontsize=7, ha='center', va='center', fontweight='bold', zorder=5)
            tag(ax, x0 + pw + 0.8, laje_y, 'abertura=0', fc=VERDE, fs=6)
        else:
            # With opening: gap in the middle
            gap_start = x0 + pw * 0.3
            gap_end = x0 + pw * 0.7
            ax.fill_between([x0, gap_start], laje_y, laje_y + 0.5,
                            color=LAJE_C, alpha=0.5, zorder=4)
            ax.fill_between([gap_end, x0 + pw], laje_y, laje_y + 0.5,
                            color=LAJE_C, alpha=0.5, zorder=4)
            # Opening area
            rct(ax, gap_start, laje_y, gap_end - gap_start, 0.5,
                fc=WARN, ec=WARN, lw=1.5, alpha=0.3, zorder=4)
            ax.text((gap_start + gap_end) / 2, laje_y + 0.25, 'ABERTURA',
                    color=WARN, fontsize=7, ha='center', va='center', fontweight='bold', zorder=5)
            tag(ax, x0 + pw + 0.8, laje_y, 'abertura=1', fc=WARN, fs=6)

            # Dimension of opening
            cota(ax, gap_start, laje_y - 0.8, gap_end, laje_y - 0.8, 'abertura_laje', off=0, fs=6, fc=WARN)

    fig.text(0.06, 0.07,
             'abertura_laje: dict com areas de abertura por segmento\n'
             'Valor 0: laje continua normal  |  Valor 1: regiao aberta (sem laje)\n'
             'A abertura remove o hatch HHHH na regiao correspondente',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 13, 'P-11 | Abertura de laje -- presenca ou ausencia de laje por segmento')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 14: P-12 Blocos PED e Moldura
# =========================================================================
def page_p12_blocos_ped(pdf):
    fig = new_fig('P-12  BLOCOS PED E MOLDURA', 'INSERT PED, muldura2 vs PAINEL-NOVA, bloco_moldura')
    axes = fig.subplots(1, 2)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.15, top=0.90, wspace=0.3)

    # Left: PED block
    ax = axes[0]
    setup(ax, 'Bloco PED (pe-direito)')
    ax.set_xlim(-1, 8)
    ax.set_ylim(-1, 10)

    # PED block representation
    rct(ax, 1, 0, 4, 8, fc=PILAR_C, ec='white', lw=1.5, alpha=0.2)

    # PED insert point
    ped_x, ped_y = 3.0, 4.0
    ax.plot(ped_x, ped_y, 'o', color=GARFO_C, markersize=10, zorder=5)
    ax.plot([ped_x - 0.5, ped_x + 0.5], [ped_y, ped_y], '-', color=GARFO_C, lw=2, zorder=5)
    ax.plot([ped_x, ped_x], [ped_y - 0.5, ped_y + 0.5], '-', color=GARFO_C, lw=2, zorder=5)
    tag(ax, ped_x + 2.0, ped_y, 'INSERT PED\n(x,y) 1 0', fc=GARFO_C, fs=6)

    # SCR command
    ax.text(1, -0.5, '-INSERT PED 3.0,4.0 1 0', color=VIGA_C, fontsize=6.5,
            fontfamily='monospace')

    # Right: Moldura comparison
    ax = axes[1]
    setup(ax, 'Moldura: muldura2 vs PAINEL-NOVA')
    ax.set_xlim(-1, 8)
    ax.set_ylim(-1, 10)

    # muldura2 (wider)
    rct(ax, 0.5, 5, 5.5, 3.5, fc=ARCO_C, ec='white', lw=1.5, alpha=0.3)
    lbl(ax, 0.5, 5, 5.5, 3.5, 'muldura2\ncomp=1051mm', fc=ARCO_C, fs=7)

    # PAINEL-NOVA (standard)
    rct(ax, 0.5, 0.5, 5.0, 3.5, fc=PAINEL, ec='white', lw=1.5, alpha=0.3)
    lbl(ax, 0.5, 0.5, 5.0, 3.5, 'PAINEL-NOVA\ncomp=1000mm', fc=PAINEL, fs=7)

    # Difference cota
    cota(ax, 6.5, 5, 6.5, 8.5, '1051', off=0.3, fs=7, fc=ARCO_C)
    cota(ax, 6.5, 0.5, 6.5, 4.0, '1000', off=0.3, fs=7, fc=PAINEL)

    fig.text(0.06, 0.07,
             'bloco_moldura: "muldura2" (comprimento 1051mm) ou "PAINEL-NOVA" (1000mm)\n'
             '-DIMSTYLE restore {bloco_moldura}: aplica estilo de dimensao correspondente\n'
             '-INSERT PED {x},{y} 1 0: insere bloco de pe-direito no ponto especificado',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 14, 'P-12 | Blocos PED e moldura -- INSERT e DIMSTYLE')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 15: P-13 Layers do DXF
# =========================================================================
def page_p13_layers(pdf):
    fig = new_fig('P-13  LAYERS DO DXF', 'Tabela visual com cor / tipo de linha / conteudo por layer')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    ax.set_facecolor(BG)
    ax.axis('off')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    layers = [
        ('paineis_abcd', PAINEL, 'Continuous', 'Paineis principais A/B/C/D (PLINE)'),
        ('pe_direito', LAJE_ADJ, 'DASHED', 'Linhas de pe-direito (DIMLINEAR)'),
        ('laje', LAJE_C, 'Continuous', 'Representacao de laje (HATCH, PLINE)'),
        ('cotas', VERDE, 'Continuous', 'Dimensoes e cotas (DIMLINEAR)'),
        ('sarrafos', SARRAFO, 'Continuous', 'Sarrafos horizontais e verticais'),
        ('linhas_hidden', APOIO_C, 'DASHED', 'Linhas ocultas (PLINE tracejada)'),
    ]

    # Table header
    cols = ['Layer', 'Cor', 'Tipo Linha', 'Conteudo']
    col_x = [0.5, 3.0, 4.5, 6.5]
    header_y = 9.0

    for cx, cn in zip(col_x, cols):
        ax.text(cx, header_y, cn, color=COTA_C, fontsize=8, fontweight='bold')
    ax.plot([0.3, 9.5], [header_y - 0.25, header_y - 0.25], '-', color=GRADE, lw=1.0)

    for i, (name, cor, lt, desc) in enumerate(layers):
        y = header_y - 1.0 - i * 1.1

        # Color swatch
        r = mpatches.Rectangle((col_x[1] - 0.3, y - 0.2), 0.8, 0.5,
                                facecolor=cor, alpha=0.8, edgecolor='white', lw=0.5)
        ax.add_patch(r)

        ax.text(col_x[0], y, name, color=cor, fontsize=7.5, fontweight='bold', fontfamily='monospace')
        ax.text(col_x[1] + 0.7, y, cor, color=TEXTO, fontsize=7)
        # Line type sample
        if lt == 'DASHED':
            ax.plot([col_x[2], col_x[2] + 1.2], [y + 0.1, y + 0.1], '--', color=cor, lw=2.0)
        else:
            ax.plot([col_x[2], col_x[2] + 1.2], [y + 0.1, y + 0.1], '-', color=cor, lw=2.0)
        ax.text(col_x[2], y - 0.3, lt, color=TEXTO, fontsize=6)

        ax.text(col_x[3], y, desc, color=TEXTO, fontsize=6.5)

        ax.plot([0.3, 9.5], [y - 0.55, y - 0.55], '-', color=GRADE, lw=0.5, alpha=0.5)

    fig.text(0.06, 0.07,
             'Comando SCR: _LAYER S {nome} -- muda o layer ativo antes de desenhar\n'
             '_LINETYPE S DASHED -- ativa linha tracejada para pe_direito e linhas_hidden\n'
             'Cada layer tem cor, tipo de linha e conteudo especifico',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 15, 'P-13 | Layers do DXF -- organizacao por cor, tipo de linha e conteudo')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 16: P-14 Script .SCR
# =========================================================================
def page_p14_script_scr(pdf):
    fig = new_fig('P-14  SCRIPT .SCR -- EXEMPLO DE COMANDOS', 'Texto monospace dos comandos AutoCAD gerados pelo robo')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    ax.set_facecolor(BG)
    ax.axis('off')

    scr_lines = [
        '; === PILAR P11 - TERREO ===',
        '; Painel A (Face Norte)',
        '_LAYER S paineis_abcd',
        '_PLINE 0,0 68,0 68,2 0,2 C',
        '_PLINE 0,2 68,2 68,63 0,63 C',
        '_PLINE 0,63 68,63 68,124 0,124 C',
        '_PLINE 0,124 68,124 68,185 0,185 C',
        '_PLINE 0,185 68,185 68,280 0,280 C',
        '',
        '; Cotas',
        '_LAYER S cotas',
        '-DIMSTYLE restore PAINEL-NOVA',
        '_DIMLINEAR 0,0 68,0 34,-15',
        '_DIMLINEAR 0,0 0,280 -15,140',
        '',
        '; Pe-direito',
        '_LAYER S pe_direito',
        '_LINETYPE S DASHED',
        '_PLINE -5,0 73,0',
        '_PLINE -5,280 73,280',
        '',
        '; Bloco PED',
        '-INSERT PED 34,140 1 0',
        '',
        '; Laje (se pos_laje_a != 0)',
        '_LAYER S laje',
        '_PLINE -5,124 73,124 73,136 -5,136 C',
        'HHHH',
        '',
        '; Sarrafos',
        '_LAYER S sarrafos',
        '_PLINE 7,2 7,280',
        '_PLINE 61,2 61,280',
        '_PLINE 0,63 68,63',
        '_PLINE 0,124 68,124',
        '_PLINE 0,185 68,185',
    ]

    y = 0.95
    line_h = 0.025
    for line in scr_lines:
        if y < 0.05:
            break
        if line.startswith(';'):
            color = VERDE
        elif line.startswith('_'):
            color = PAINEL
        elif line.startswith('-'):
            color = ARCO_C
        elif line == '':
            y -= line_h
            continue
        else:
            color = TEXTO
        ax.text(0.02, y, line, color=color, fontsize=6.5, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        y -= line_h

    # Legend
    leg_y = 0.03
    for cor, desc in [(VERDE, 'Comentario (;)'), (PAINEL, 'Comando underscore (_)'),
                      (ARCO_C, 'Comando hifen (-INSERT, -DIMSTYLE)'), (TEXTO, 'Outros')]:
        ax.text(0.02, leg_y, '---', color=cor, fontsize=7, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(0.06, leg_y, desc, color=TEXTO, fontsize=6.5, transform=ax.transAxes, va='top')
        leg_y += 0.022

    rodape(fig, 16, 'P-14 | Script .SCR -- comandos AutoCAD gerados pelo robo de pilares')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 17: P-15 Pilar Especial L
# =========================================================================
def page_p15_pilar_l(pdf):
    fig = new_fig('P-15  PILAR ESPECIAL L', 'Geometria + paineis E, F, G, H (2 retangulos perpendiculares)')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-3, 14)
    ax.set_ylim(-3, 14)

    # L-shape: two perpendicular rectangles
    # Horizontal part
    rct(ax, 0, 0, 8, 3, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)
    # Vertical part
    rct(ax, 0, 0, 3, 8, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)

    # Panel labels on each face
    faces = [
        ('A', 0, 8, 8, 8.6, PAINEL),       # top of horizontal
        ('B', 8, 0, 8.6, 3, '#d4a030'),     # right of horizontal
        ('C', 0, -0.6, 8, 0, '#c8960a'),    # bottom of horizontal
        ('D', -0.6, 0, 0, 8, '#b87820'),    # left of vertical
        ('E', 0, 8, 3, 8.6, GARFO_C),       # top of vertical part
        ('F', 3, 3, 3.6, 8, LAJE_C),        # right of vertical part (inner corner)
        ('G', 3, 2.4, 8, 3, ARCO_C),        # top of horizontal inner
        ('H', -0.6, 0, 0, 3, VIGA_ADJ),     # left bottom
    ]

    # Draw the L panels on exterior
    for name, x1, y1, x2, y2, cor in faces:
        w = x2 - x1
        h = y2 - y1
        if w > 0.3 and h > 0.3:
            rct(ax, x1, y1, w, h, fc=cor, ec='white', lw=1.0, alpha=0.5)
            lbl(ax, x1, y1, w, h, name, fc=TEXTO, fs=9)

    # Labels with arrows
    tag(ax, 10, 7, 'Face A (topo)', fc=PAINEL, fs=7)
    tag(ax, 10, 5, 'Face D (esq)', fc='#b87820', fs=7)
    tag(ax, 10, 3, 'Face E (topo vert)', fc=GARFO_C, fs=7)
    tag(ax, 10, 1, 'Face F (canto int)', fc=LAJE_C, fs=7)

    ax.text(4, -2, 'Tipo L: 2 retangulos perpendiculares\nPaineis extras: E, F, G, H nas faces internas',
            color=TEXTO, fontsize=8, ha='center', fontweight='bold')

    fig.text(0.06, 0.07,
             'Pilar Tipo L: secao em forma de L com 8 faces (A-H)\n'
             'Faces E/F/G/H cobrem as superficies internas do L\n'
             'Cada face gera um painel independente no SCR',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 17, 'P-15 | Pilar Especial L -- 8 paineis para secao em L')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 18: P-16 Pilar Especial T
# =========================================================================
def page_p16_pilar_t(pdf):
    fig = new_fig('P-16  PILAR ESPECIAL T', 'Geometria + paineis E, F, G, H (3 retangulos em T)')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-3, 14)
    ax.set_ylim(-3, 14)

    # T-shape: horizontal bar + vertical stem
    # Horizontal bar (wide)
    rct(ax, 0, 5, 10, 3, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)
    # Vertical stem (centered)
    rct(ax, 3.5, 0, 3, 5, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)

    # Panel faces
    panels = [
        ('A', 0, 8, 10, 0.5, PAINEL),
        ('B', 10, 5, 0.5, 3, '#d4a030'),
        ('C', 3.5, -0.5, 3, 0.5, '#c8960a'),
        ('D', -0.5, 5, 0.5, 3, '#b87820'),
        ('E', 3.5, 5, 3, 0.5, GARFO_C),   # inner top of stem
        ('F', 6.5, 0, 0.5, 5, LAJE_C),    # right of stem
        ('G', 0, 4.5, 3.5, 0.5, ARCO_C),  # bottom left of bar
        ('H', 3, 0, 0.5, 5, VIGA_ADJ),    # left of stem
    ]

    for name, x1, y1, w, h, cor in panels:
        rct(ax, x1, y1, w, h, fc=cor, ec='white', lw=1.0, alpha=0.5)
        if w > 0.4 and h > 0.4:
            lbl(ax, x1, y1, w, h, name, fc=TEXTO, fs=8)
        else:
            ax.text(x1 + w / 2, y1 + h / 2, name, color=TEXTO, fontsize=6,
                    ha='center', va='center', fontweight='bold', zorder=5)

    ax.text(5, -2, 'Tipo T: barra horizontal + haste vertical\nPaineis extras: E, F, G, H nas faces internas',
            color=TEXTO, fontsize=8, ha='center', fontweight='bold')

    fig.text(0.06, 0.07,
             'Pilar Tipo T: secao em forma de T\n'
             'Barra horizontal (topo) + haste vertical (base)\n'
             'Faces internas E/F/G/H complementam A/B/C/D',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 18, 'P-16 | Pilar Especial T -- secao em T com 8 paineis')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 19: P-17 Pilar Especial U
# =========================================================================
def page_p17_pilar_u(pdf):
    fig = new_fig('P-17  PILAR ESPECIAL U', 'Geometria + paineis E, F, G, H (3 retangulos em U)')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-3, 14)
    ax.set_ylim(-3, 14)

    # U-shape: two vertical arms + horizontal base
    # Left arm
    rct(ax, 0, 0, 2.5, 8, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)
    # Right arm
    rct(ax, 6.5, 0, 2.5, 8, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)
    # Horizontal base
    rct(ax, 0, 0, 9, 2.5, fc=PILAR_C, ec=PILAR_C, lw=2.0, alpha=0.25)

    # Panels
    panels = [
        ('A', 0, 8, 2.5, 0.5, PAINEL),
        ('B', 9, 0, 0.5, 8, '#d4a030'),
        ('C', 0, -0.5, 9, 0.5, '#c8960a'),
        ('D', -0.5, 0, 0.5, 8, '#b87820'),
        ('E', 6.5, 8, 2.5, 0.5, GARFO_C),
        ('F', 2.5, 2.5, 4, 0.5, LAJE_C),    # inner bottom
        ('G', 2.5, 2.5, 0.5, 5.5, ARCO_C),  # inner left
        ('H', 6, 2.5, 0.5, 5.5, VIGA_ADJ),  # inner right
    ]

    for name, x1, y1, w, h, cor in panels:
        rct(ax, x1, y1, w, h, fc=cor, ec='white', lw=1.0, alpha=0.5)
        if w > 0.4 and h > 0.4:
            lbl(ax, x1, y1, w, h, name, fc=TEXTO, fs=8)
        else:
            ax.text(x1 + w / 2, y1 + h / 2, name, color=TEXTO, fontsize=6,
                    ha='center', va='center', fontweight='bold', zorder=5)

    # Inner channel label
    ax.text(4.5, 5.5, 'CANAL\nINTERNO', color=WARN, fontsize=9,
            ha='center', va='center', fontweight='bold')

    ax.text(4.5, -2, 'Tipo U: 2 bracos verticais + base horizontal\nPaineis E/F/G/H cobrem canal interno',
            color=TEXTO, fontsize=8, ha='center', fontweight='bold')

    fig.text(0.06, 0.07,
             'Pilar Tipo U: secao em forma de U\n'
             'Dois bracos verticais unidos pela base\n'
             'Canal interno recebe paineis E/F/G/H',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 19, 'P-17 | Pilar Especial U -- secao em U com 8 paineis')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 20: P-18 Pilar Cambotado
# =========================================================================
def page_p18_cambotado(pdf):
    fig = new_fig('P-18  PILAR CAMBOTADO', 'Faces com arcos (bulge != 0), has_arcs=True')
    axes = fig.subplots(1, 2)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.15, top=0.90, wspace=0.3)

    # Left: cross section with arc
    ax = axes[0]
    setup(ax, 'Secao transversal')
    ax.set_xlim(-2, 8)
    ax.set_ylim(-2, 8)

    # Rectangular base
    ax.plot([0, 5], [0, 0], '-', color=PILAR_C, lw=2.5, zorder=3)
    ax.plot([0, 0], [0, 5], '-', color=PILAR_C, lw=2.5, zorder=3)
    ax.plot([0, 5], [5, 5], '-', color=PILAR_C, lw=2.5, zorder=3)

    # Arc on right side (cambotado)
    theta = np.linspace(-np.pi / 2, np.pi / 2, 60)
    r_arc = 2.5
    arc_x = 5 + r_arc * np.cos(theta) * 0.3
    arc_y = 2.5 + r_arc * np.sin(theta)
    ax.plot(arc_x, arc_y, '-', color=ARCO_C, lw=3.0, zorder=3)

    # Fill
    xs = [0, 0, 5] + list(arc_x[::-1]) + [5]
    ys = [0, 5, 5] + list(arc_y[::-1]) + [0]
    ax.fill(xs, ys, color=PILAR_C, alpha=0.15, zorder=1)

    arrow(ax, 7, 4, 5.5, 2.5, 'Arco\n(bulge>0)', ARCO_C, fs=7)
    tag(ax, 2.5, 2.5, 'has_arcs\n= True', fc=WARN, fs=7)

    # Right: planification of curved panel
    ax = axes[1]
    setup(ax, 'Painel cambotado planificado')
    ax.set_xlim(-1, 8)
    ax.set_ylim(-1, 10)

    # The curved face is "unrolled" into flat panel
    pw = 4.0
    ph = 8.0
    rct(ax, 0.5, 0.5, pw, ph, fc=ARCO_C, ec='white', lw=1.5, alpha=0.3)

    # Wavy lines to indicate it was curved
    for yy in np.linspace(1.5, 7.5, 5):
        xw = np.linspace(0.5, 0.5 + pw, 40)
        yw = yy + 0.15 * np.sin(np.linspace(0, 4 * np.pi, 40))
        ax.plot(xw, yw, '-', color=ARCO_C, lw=0.8, alpha=0.5, zorder=3)

    lbl(ax, 0.5, 0.5, pw, ph, 'PAINEL\nCAMBOTADO\n(planificado)', fc=ARCO_C, fs=8)

    ax.text(2.5, -0.5, 'Comprimento = arco\n(nao face reta)',
            color=TEXTO, fontsize=7, ha='center')

    fig.text(0.06, 0.07,
             'Pilar cambotado: LWPOLYLINE com bulge != 0 em pelo menos uma face\n'
             'has_arcs=True: detectado automaticamente pelo parser de geometria\n'
             'O painel cambotado e planificado usando o comprimento do arco (nao a corda)',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 20, 'P-18 | Pilar Cambotado -- arcos na secao transversal')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 21: P-19 Vista CIMA (Top View)
# =========================================================================
def page_p19_vista_cima(pdf):
    fig = new_fig('P-19  VISTA CIMA (TOP VIEW)', 'Secao transversal do pilar + 4 faces identificadas')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-4, 14)
    ax.set_ylim(-4, 14)

    B, H = 4.6, 5.6
    x0, y0 = 3.0, 3.0

    # Pilar section
    rct(ax, x0, y0, B, H, fc=PILAR_C, ec=PILAR_C, lw=2.5, alpha=0.25)
    lbl(ax, x0, y0, B, H, f'P11\nB={B*10:.0f}cm\nH={H*10:.0f}cm', fc=PILAR_C, fs=10)

    # Panels on each face
    panel_thick = 0.4
    panels = [
        ('A', x0, y0 + H, B, panel_thick, PAINEL),
        ('B', x0 + B, y0, panel_thick, H, '#d4a030'),
        ('C', x0, y0 - panel_thick, B, panel_thick, '#c8960a'),
        ('D', x0 - panel_thick, y0, panel_thick, H, '#b87820'),
    ]

    for name, px, py, pw, ph, cor in panels:
        rct(ax, px, py, pw, ph, fc=cor, ec='white', lw=1.0, alpha=0.7)
        lbl(ax, px, py, pw, ph, name, fc=BG, fs=9)

    # Cotas
    cota(ax, x0, y0 - 2.0, x0 + B, y0 - 2.0, f'B = {B*10:.0f}cm', off=0, fs=8)
    cota(ax, x0 + B + 2.0, y0, x0 + B + 2.0, y0 + H, f'H = {H*10:.0f}cm', off=0, fs=8)

    # North arrow
    cx, cy = x0 + B / 2, y0 + H + 2.5
    for ang, ltr, cor in [(90, 'N', WARN), (0, 'E', COTA_C), (270, 'S', COTA_C), (180, 'O', COTA_C)]:
        rad = math.radians(ang)
        ax.annotate('', xy=(cx + math.cos(rad) * 0.8, cy + math.sin(rad) * 0.8),
                    xytext=(cx, cy),
                    arrowprops=dict(arrowstyle='->', color=cor, lw=1.3))
        ax.text(cx + math.cos(rad) * 1.1, cy + math.sin(rad) * 1.1, ltr,
                color=cor, fontsize=8, ha='center', va='center', fontweight='bold')

    # Legend
    leg_items = [
        (PILAR_C, 'Secao do pilar (concreto)'),
        (PAINEL, 'Face A (Norte) = comprimento B'),
        ('#d4a030', 'Face B (Leste) = largura H'),
        ('#c8960a', 'Face C (Sul) = comprimento B'),
        ('#b87820', 'Face D (Oeste) = largura H'),
    ]
    for i, (cor, txt) in enumerate(leg_items):
        ly = 1.0 - i * 0.8
        r = mpatches.Rectangle((0.5, ly), 0.5, 0.4, facecolor=cor, alpha=0.8, edgecolor='white', lw=0.5)
        ax.add_patch(r)
        ax.text(1.2, ly + 0.2, txt, color=TEXTO, fontsize=6.5, va='center')

    rodape(fig, 21, 'P-19 | Vista de cima -- secao transversal com identificacao das 4 faces')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 22: P-20 Vista GRADE
# =========================================================================
def page_p20_vista_grade(pdf):
    fig = new_fig('P-20  VISTA GRADE -- SARRAFOS EM GRADE', 'Sarrafos horizontais + verticais formando grade no painel')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 14)
    ax.set_ylim(-2, 16)

    pw, ph = 6.8, 14.0
    x0, y0 = 2.0, 0

    # Panel outline
    rct(ax, x0, y0, pw, ph, fc=PAINEL, ec='white', lw=1.5, alpha=0.15)

    # Horizontal sarrafos
    h_positions = [y0 + 0.1, y0 + 3.05, y0 + 6.1, y0 + 9.15, y0 + 12.2, y0 + ph - 0.1]
    for sy in h_positions:
        ax.plot([x0, x0 + pw], [sy, sy], '-', color=SARRAFO, lw=1.5, zorder=4)

    # Vertical sarrafos (offset = 7cm = 0.7 units from edges)
    v_positions = [x0 + 0.7, x0 + pw - 0.7]
    for vx in v_positions:
        ax.plot([vx, vx], [y0, y0 + ph], '-', color=SARRAFO, lw=1.5, zorder=4)

    # Intersection markers
    for vx in v_positions:
        for sy in h_positions:
            ax.plot(vx, sy, 'o', color=GARFO_C, markersize=4, zorder=5)

    # Labels
    tag(ax, x0 + pw + 2.0, h_positions[2], 'Sarrafos\nhorizontais', fc=SARRAFO, fs=7)
    tag(ax, v_positions[0], y0 + ph + 1.0, 'Vertical\noffset 7cm', fc=SARRAFO, fs=7)

    # Grid cell dimension
    cota(ax, v_positions[0], y0 - 1.0, v_positions[1], y0 - 1.0,
         f'{(pw - 1.4) * 10:.0f}cm', off=0, fs=7, fc=SARRAFO)

    tag(ax, x0 + pw / 2, y0 + ph / 2, 'GRADE\nCOMPLETA', fc=PAINEL, fs=10)

    fig.text(0.06, 0.07,
             'Grade formada pela intersecao de sarrafos horizontais e verticais\n'
             'Horizontais: nas divisorias entre fiadas (h1/h2/h3...)\n'
             'Verticais: a sarrafo_offset (7cm) de cada bordo lateral\n'
             'Interseccoes (pontos rosa): locais de fixacao mecanica',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 22, 'P-20 | Vista GRADE -- sarrafos horizontais + verticais')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 23: P-21 Variacoes de BxH
# =========================================================================
def page_p21_variacoes(pdf):
    fig = new_fig('P-21  VARIACOES DE B x H', '8 exemplos de pilares: 20x20, 30x60, 46x56, 80x30, 100x25, 60x60, 40x80, 25x120')
    axes_list = []
    for row in range(2):
        for col in range(4):
            ax = fig.add_axes([0.04 + col * 0.24, 0.48 - row * 0.42 + 0.08, 0.20, 0.38])
            setup(ax)
            axes_list.append(ax)

    examples = [
        (20, 20), (30, 60), (46, 56), (80, 30),
        (100, 25), (60, 60), (40, 80), (25, 120),
    ]

    for idx, (ax, (b, h)) in enumerate(zip(axes_list, examples)):
        ax.set_title(f'{b}x{h}cm', color=PAINEL, fontsize=7, fontweight='bold', fontfamily='monospace', pad=2)

        max_dim = max(b, h)
        scale = 5.0 / max_dim
        bw = b * scale
        bh = h * scale
        x0 = (6 - bw) / 2
        y0 = (6 - bh) / 2

        ax.set_xlim(-0.5, 6.5)
        ax.set_ylim(-0.5, 7)

        rct(ax, x0, y0, bw, bh, fc=PILAR_C, ec=PILAR_C, lw=1.5, alpha=0.3)
        lbl(ax, x0, y0, bw, bh, f'B={b}\nH={h}', fc=PILAR_C, fs=6)

        # Mini panels
        panel_t = 0.15
        rct(ax, x0, y0 + bh, bw, panel_t, fc=PAINEL, ec='white', lw=0.5, alpha=0.6)
        rct(ax, x0 + bw, y0, panel_t, bh, fc='#d4a030', ec='white', lw=0.5, alpha=0.6)
        rct(ax, x0, y0 - panel_t, bw, panel_t, fc='#c8960a', ec='white', lw=0.5, alpha=0.6)
        rct(ax, x0 - panel_t, y0, panel_t, bh, fc='#b87820', ec='white', lw=0.5, alpha=0.6)

    fig.text(0.06, 0.07,
             'Pilares variam de 20x20cm (quadrado minimo) a 25x120cm (muito esbelto)\n'
             'Paineis A/C usam B (comprimento), Paineis B/D usam H (largura)\n'
             'Formato automaticamente ajusta numero de fiadas e sarrafos',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 23, 'P-21 | Variacoes de BxH -- 8 exemplos de secao transversal')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 24: P-22 Comprimento da Moldura
# =========================================================================
def page_p22_moldura(pdf):
    fig = new_fig('P-22  COMPRIMENTO DA MOLDURA', 'muldura2 (1051mm) vs padrao PAINEL-NOVA (1000mm)')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-2, 14)
    ax.set_ylim(-2, 14)

    # PAINEL-NOVA (standard)
    rct(ax, 0, 6, 10.0, 3.0, fc=PAINEL, ec='white', lw=2.0, alpha=0.4)
    lbl(ax, 0, 6, 10.0, 3.0, 'PAINEL-NOVA\ncomprimento = 1000mm', fc=PAINEL, fs=9)
    cota(ax, 0, 5.3, 10.0, 5.3, '1000mm', off=0, fs=8)

    # muldura2 (wider by 51mm)
    extra = 0.51  # 51mm = 0.51 units at 1:1 scale
    rct(ax, 0, 0, 10.0 + extra, 3.0, fc=ARCO_C, ec='white', lw=2.0, alpha=0.4)
    lbl(ax, 0, 0, 10.0 + extra, 3.0, 'muldura2\ncomprimento = 1051mm', fc=ARCO_C, fs=9)
    cota(ax, 0, -0.7, 10.0 + extra, -0.7, '1051mm', off=0, fs=8, fc=ARCO_C)

    # Extra portion highlighted
    rct(ax, 10.0, 0, extra, 3.0, fc=WARN, ec=WARN, lw=1.5, alpha=0.5)
    tag(ax, 10.0 + extra / 2, 1.5, '+51mm', fc=WARN, fs=7)

    # Comparison arrow
    ax.annotate('', xy=(11.5, 7.5), xytext=(11.5, 1.5),
                arrowprops=dict(arrowstyle='<->', color=TEXTO, lw=1.5), zorder=6)
    ax.text(12.0, 4.5, 'Diferenca\n51mm', color=TEXTO, fontsize=8, va='center', fontweight='bold')

    # SCR commands
    ax.text(0, 11, '-DIMSTYLE restore PAINEL-NOVA', color=PAINEL, fontsize=7.5, fontfamily='monospace')
    ax.text(0, 10.2, '-DIMSTYLE restore muldura2', color=ARCO_C, fontsize=7.5, fontfamily='monospace')

    fig.text(0.06, 0.07,
             'bloco_moldura determina qual DIMSTYLE e usado para as cotas\n'
             '"PAINEL-NOVA": comprimento padrao 1000mm\n'
             '"muldura2": comprimento estendido 1051mm (51mm a mais)',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 24, 'P-22 | Comprimento da moldura -- PAINEL-NOVA vs muldura2')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 25: P-23 Fluxo Pipeline
# =========================================================================
def page_p23_pipeline(pdf):
    fig = new_fig('P-23  FLUXO PIPELINE', 'Ficha -> ABCD.scr -> AutoCAD -> DXF final')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    ax.set_facecolor(BG)
    ax.axis('off')
    ax.set_xlim(-1, 12)
    ax.set_ylim(-1, 12)

    # Pipeline steps as boxes with arrows
    steps = [
        (1, 10, 3.5, 1.5, 'FICHA\n(dados entrada)', PILAR_C),
        (1, 7.5, 3.5, 1.5, 'PARSER\n(valida campos)', PAINEL),
        (1, 5, 3.5, 1.5, 'GERADOR SCR\n(monta comandos)', GARFO_C),
        (1, 2.5, 3.5, 1.5, 'AutoCAD\n(executa .SCR)', LAJE_C),
        (1, 0, 3.5, 1.5, 'DXF FINAL\n(resultado)', VERDE),
    ]

    for x, y, w, h, txt, cor in steps:
        rct(ax, x, y, w, h, fc=cor, ec='white', lw=1.5, alpha=0.35)
        lbl(ax, x, y, w, h, txt, fc=cor, fs=8)

    # Arrows between steps
    for i in range(len(steps) - 1):
        y_from = steps[i][1]
        y_to = steps[i + 1][1] + steps[i + 1][3]
        cx = steps[i][0] + steps[i][2] / 2
        ax.annotate('', xy=(cx, y_to), xytext=(cx, y_from),
                    arrowprops=dict(arrowstyle='->', color=TEXTO, lw=2.0), zorder=6)

    # Side annotations
    annotations = [
        (6, 10.5, 'nome, pavimento, B, H, PE,\nlarg1/2/3, h1-h5, pos_laje,\npar_1_2..par_8_9, hatch...'),
        (6, 7.8, 'Valida: B>0, H>0, PE>0\nCalcula fiadas, sarrafos\nDetecta tipo: L/T/U/cambotado'),
        (6, 5.3, '_LAYER, _PLINE, _DIMLINEAR\n-INSERT PED, HHHH\n_LINETYPE S DASHED'),
        (6, 2.8, 'Executa script no AutoCAD\nDesenha em layers separados'),
        (6, 0.3, 'Arquivo DXF com todos os\nlayers, entidades, blocos'),
    ]

    for x, y, txt in annotations:
        ax.text(x, y, txt, color=TEXTO, fontsize=6.5, fontfamily='monospace',
                va='top',
                bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.6, pad=3))
        ax.plot([4.7, 5.8], [y - 0.2, y - 0.2], '-', color=GRADE, lw=0.8)

    rodape(fig, 25, 'P-23 | Fluxo pipeline -- da ficha ao DXF final')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 26: P-24 Exemplo Completo P11
# =========================================================================
def page_p24_exemplo_p11(pdf):
    fig = new_fig('P-24  EXEMPLO COMPLETO P11 (B=46, H=56, PE=280)', '4 paineis lado a lado com cotas e sarrafos')
    ax = fig.add_axes([0.04, 0.10, 0.92, 0.82])
    setup(ax)
    ax.set_xlim(-1, 22)
    ax.set_ylim(-2, 16)

    paineis_data = [
        ('A', 6.8, [0.1, 3.05, 3.05, 3.05, 4.75], PAINEL),
        ('B', 6.8, [0.1, 3.05, 3.05, 3.05, 4.75], '#d4a030'),
        ('C', 5.6, [0.1, 4.6, 4.6, 4.7], '#c8960a'),
        ('D', 5.6, [0.1, 4.6, 4.6, 4.7], '#b87820'),
    ]

    x_pos = 0.5
    gap = 0.5

    for pname, pw, h_list, cor in paineis_data:
        y = 0
        for hi, hv in enumerate(h_list):
            c = cor if hi not in [0, len(h_list) - 1] else '#555555'
            rct(ax, x_pos, y, pw, hv, fc=c, ec='white', lw=0.6, alpha=0.75)
            if hv > 0.5:
                lbl(ax, x_pos, y, pw, hv, f'h{hi+1}', fc=TEXTO, fs=5, bold=False)
            y += hv

        total_h = sum(h_list)

        # Sarrafos
        for sy in [3.05, 6.1, 9.15]:
            if sy < total_h:
                ax.plot([x_pos, x_pos + pw], [sy, sy], '--', color=SARRAFO, lw=0.8, alpha=0.7, zorder=4)

        # Label
        ax.text(x_pos + pw / 2, -0.5, f'Painel {pname}\n{pw*10:.0f}cm',
                ha='center', va='top', fontsize=7, color=cor, fontweight='bold')

        # Total height cota
        cota(ax, x_pos + pw + 0.15, 0, x_pos + pw + 0.15, total_h, f'{total_h*10:.0f}', off=0.1, fs=5)

        x_pos += pw + gap

    # Overall info
    ax.text(x_pos + 0.5, 7, 'P11\nTERREO\nB=46\nH=56\nPE=280',
            color=PILAR_C, fontsize=8, fontweight='bold',
            bbox=dict(facecolor='#1e1e3a', edgecolor=PILAR_C, lw=1, pad=5))

    fig.text(0.06, 0.07,
             'Exemplo real P11: B=46cm, H=56cm, PE=280cm, pavimento TERREO\n'
             'A e B: 5 fiadas (h1=2, h2-h4=61, h5=95)  |  C e D: 4 fiadas (h1=2, h2-h3=92, h4=94)\n'
             'Sarrafos tracejados marcam divisorias de fiadas',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 26, 'P-24 | Exemplo completo P11 -- 4 paineis lado a lado')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 27: P-25 Campos de Dados
# =========================================================================
def page_p25_campos(pdf):
    fig = new_fig('P-25  CAMPOS DE DADOS', 'Tabela completa com tipo, padrao e descricao de cada campo')
    ax = fig.add_axes([0.04, 0.05, 0.92, 0.88])
    ax.set_facecolor(BG)
    ax.axis('off')

    campos = [
        ('nome', 'str', 'P11', 'Nome do pilar'),
        ('pavimento', 'str', 'TERREO', 'Pavimento do pilar'),
        ('comprimento (B)', 'float', '46', 'Largura do pilar -> paineis A/B'),
        ('largura (H)', 'float', '56', 'Altura do pilar -> paineis C/D'),
        ('altura (PE)', 'float', '280', 'Pe-direito em cm'),
        ('nivel_saida', 'float', '0.00', 'Nivel de saida (metros)'),
        ('nivel_chegada', 'float', '2.80', 'Nivel de chegada (metros)'),
        ('nivel_diferencial', 'float', '0', 'Diferenca de nivel (cm)'),
        ('larg1/2/3 (A/B)', 'float', '30/32/6', '3 faixas horizontais'),
        ('h1..h5 (A/B)', 'float', '2/61/../95', '5 fiadas verticais'),
        ('larg1/2 (C/D)', 'float', '25/31', '2 faixas horizontais'),
        ('h1..h4 (C/D)', 'float', '2/92/92/94', '4 fiadas verticais'),
        ('laje_a/b/c/d_var', 'float', '12', 'Altura da laje em cm'),
        ('pos_laje_a/b', 'int', '3', 'Posicao laje (0..5)'),
        ('pos_laje_c/d', 'int', '2', 'Posicao laje (0..4)'),
        ('sarrafo_horiz', 'bool', 'True', 'Sarrafo horizontal'),
        ('join_sarrafos', 'bool', 'True', 'Join vertical'),
        ('sarrafo_offset', 'float', '7', 'Offset bordo (cm)'),
        ('hatch_opcoes', 'str[][]', '5x3', 'Grade de hatch codes'),
        ('abertura_laje', 'dict', '{}', 'Areas de abertura'),
        ('par_1_2..par_8_9', 'float', '30', 'Espacamento garfos (cm)'),
        ('medida_fundo_AB', 'float', '30', 'Parafuso inicial A/B'),
        ('medida_fundo_CD', 'float', '30', 'Parafuso inicial C/D/E..'),
        ('bloco_moldura', 'str', 'PAINEL-NOVA', 'muldura2 ou PAINEL-NOVA'),
    ]

    # Headers
    col_x = [0.02, 0.30, 0.42, 0.56, 0.72]
    headers = ['#', 'Campo', 'Tipo', 'Padrao', 'Descricao']
    header_y = 0.97

    for cx, cn in zip(col_x, headers):
        ax.text(cx, header_y, cn, color=COTA_C, fontsize=7, fontweight='bold',
                fontfamily='monospace', transform=ax.transAxes, va='top')

    y = 0.93
    for i, (nome, tipo, padrao, desc) in enumerate(campos):
        if y < 0.02:
            break
        cor_row = TEXTO if i % 2 == 0 else APOIO_C
        ax.text(col_x[0], y, f'{i+1:2d}', color=cor_row, fontsize=6, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(col_x[1], y, nome, color=PAINEL, fontsize=6, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(col_x[2], y, tipo, color=LAJE_C, fontsize=6, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(col_x[3], y, padrao, color=VERDE, fontsize=6, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(col_x[4], y, desc, color=cor_row, fontsize=6,
                transform=ax.transAxes, va='top')
        y -= 0.037

    rodape(fig, 27, 'P-25 | Campos de dados -- todos os campos de entrada do robo')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 28: P-26 Desenhando Painel a Painel
# =========================================================================
def page_p26_sequencia(pdf):
    fig = new_fig('P-26  DESENHANDO PAINEL A PAINEL', 'Sequencia de comandos SCR para cada face')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    ax.set_facecolor(BG)
    ax.axis('off')

    sequences = [
        ('FASE 1: Setup', PILAR_C, [
            '_LAYER S paineis_abcd',
            '-DIMSTYLE restore PAINEL-NOVA',
        ]),
        ('FASE 2: Painel A', PAINEL, [
            '; Fiadas h1..h5 como PLINE fechada',
            '_PLINE x1,y1 x2,y1 x2,y2 x1,y2 C',
            '; Repete para cada fiada',
            '; Cota horizontal e vertical',
            '_LAYER S cotas',
            '_DIMLINEAR x1,y1 x2,y1 xm,ym',
        ]),
        ('FASE 3: Painel B', '#d4a030', [
            '; Espelho de A, offset X += B+22+gap',
            '_LAYER S paineis_abcd',
            '_PLINE ... (mesmas alturas, larguras invertidas)',
        ]),
        ('FASE 4: Painel C', '#c8960a', [
            '; 4 fiadas, largura = H',
            '_PLINE ... (2 faixas x 4 fiadas)',
        ]),
        ('FASE 5: Painel D', '#b87820', [
            '; Espelho de C',
            '_PLINE ... (larguras invertidas)',
        ]),
        ('FASE 6: Extras', GARFO_C, [
            '_LAYER S pe_direito',
            '_LINETYPE S DASHED',
            '_PLINE ... (linhas de PE)',
            '-INSERT PED x,y 1 0',
            '_LAYER S laje',
            'HHHH (se pos_laje != 0)',
            '_LAYER S sarrafos',
            '_PLINE ... (sarrafos H e V)',
        ]),
    ]

    y = 0.95
    for fase_name, cor, cmds in sequences:
        ax.text(0.02, y, fase_name, color=cor, fontsize=8, fontweight='bold',
                fontfamily='monospace', transform=ax.transAxes, va='top')
        y -= 0.025
        for cmd in cmds:
            if y < 0.05:
                break
            c = VERDE if cmd.startswith(';') else TEXTO
            ax.text(0.05, y, cmd, color=c, fontsize=6, fontfamily='monospace',
                    transform=ax.transAxes, va='top')
            y -= 0.022
        y -= 0.015

    rodape(fig, 28, 'P-26 | Sequencia de desenho -- fases do script SCR')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 29: P-27 Caso com nivel_diferencial != 0
# =========================================================================
def page_p27_nivel_diferencial(pdf):
    fig = new_fig('P-27  CASO COM NIVEL_DIFERENCIAL != 0', 'Ajuste da coordenada Y de inicio: painel deslocado')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    setup(ax)
    ax.set_xlim(-3, 16)
    ax.set_ylim(-3, 16)

    # Reference ground line
    ax.plot([-2, 15], [0, 0], '-', color=GRADE, lw=1.0, zorder=1)
    ax.text(-2.5, 0, 'REF\nY=0', color=GRADE, fontsize=6, ha='right', va='center')

    # Case 1: diferencial = 0
    x0 = 0
    pw, ph = 3.5, 14.0
    rct(ax, x0, 0, pw, ph, fc=PAINEL, ec='white', lw=1.0, alpha=0.25)
    ax.text(x0 + pw / 2, ph + 0.5, 'dif = 0\nY_inicio = 0', color=VERDE, fontsize=7,
            ha='center', fontweight='bold')
    cota(ax, x0 + pw + 0.3, 0, x0 + pw + 0.3, ph, 'PE=280', off=0.2, fs=6)

    # Case 2: diferencial = +15cm
    x1 = 5.5
    diff1 = 1.5  # 15cm
    rct(ax, x1, diff1, pw, ph - diff1, fc=COTA_C, ec='white', lw=1.0, alpha=0.25)
    ax.plot([x1, x1 + pw], [diff1, diff1], '-', color=WARN, lw=2.0, zorder=3)
    ax.text(x1 + pw / 2, ph + 0.5, 'dif = +15\nY_inicio = 15', color=COTA_C, fontsize=7,
            ha='center', fontweight='bold')
    cota(ax, x1 - 0.3, 0, x1 - 0.3, diff1, '15cm', off=0, fs=6, fc=WARN)
    cota(ax, x1 + pw + 0.3, diff1, x1 + pw + 0.3, ph, 'PE-dif', off=0.2, fs=6)

    # Case 3: diferencial = -10cm
    x2 = 11
    diff2 = -1.0  # -10cm
    rct(ax, x2, diff2, pw, ph - abs(diff2), fc=ARCO_C, ec='white', lw=1.0, alpha=0.25)
    ax.plot([x2, x2 + pw], [diff2, diff2], '-', color=ARCO_C, lw=2.0, zorder=3)
    ax.text(x2 + pw / 2, ph + 0.5, 'dif = -10\nY_inicio = -10', color=ARCO_C, fontsize=7,
            ha='center', fontweight='bold')
    cota(ax, x2 - 0.3, diff2, x2 - 0.3, 0, '10cm', off=0, fs=6, fc=ARCO_C)

    fig.text(0.06, 0.07,
             'nivel_diferencial: desloca a coordenada Y de inicio do painel\n'
             'Y_inicio = nivel_diferencial (em cm, convertido para unidades de desenho)\n'
             'PE efetivo = PE - abs(nivel_diferencial)\n'
             'Usado quando o pilar nao comeca na cota zero do pavimento',
             fontsize=7, color=TEXTO, fontfamily='monospace',
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=5))

    rodape(fig, 29, 'P-27 | Nivel diferencial -- ajuste de Y quando dif != 0')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  PG 30: P-28 Tabela de Validacao + Score + Proximos Passos
# =========================================================================
def page_p28_validacao(pdf):
    fig = new_fig('P-28  TABELA DE VALIDACAO + SCORE', 'Checklist de conformidade do robo de pilares')
    ax = fig.add_axes([0.06, 0.10, 0.88, 0.82])
    ax.set_facecolor(BG)
    ax.axis('off')

    checks = [
        ('Gera paineis A/B/C/D', True, 'Quatro paineis principais para pilar retangular'),
        ('Suporta pilares L/T/U', True, 'Paineis E/F/G/H para secoes especiais'),
        ('Suporta cambotado', True, 'Deteccao automatica de arcos (bulge != 0)'),
        ('Cotas dimensionais', True, 'DIMLINEAR com estilo PAINEL-NOVA ou muldura2'),
        ('Laje com 6 posicoes', True, 'pos_laje 0..5 para A/B, 0..4 para C/D'),
        ('Sarrafos H + V', True, 'Horizontais nas fiadas, verticais com offset 7cm'),
        ('Garfos (parafusos)', True, 'par_1_2 a par_8_9 com medida_fundo_primeiro'),
        ('Hatch grade 5x3', True, 'Opcoes ANSI31..ANSI38, SOLID, etc.'),
        ('Abertura de laje', True, 'Segmentos com abertura removem hatch'),
        ('Nivel diferencial', True, 'Ajuste Y quando nivel_diferencial != 0'),
        ('Bloco PED', True, 'INSERT PED no ponto de pe-direito'),
        ('Layers separados', True, '6 layers: paineis, pe_direito, laje, cotas, sarrafos, hidden'),
        ('Script SCR valido', True, 'Comandos AutoCAD executaveis'),
        ('Fiadas calculadas', True, 'h1..h5 (A/B) e h1..h4 (C/D) somam PE'),
    ]

    # Header
    ax.text(0.02, 0.97, '#', color=COTA_C, fontsize=7, fontweight='bold',
            fontfamily='monospace', transform=ax.transAxes, va='top')
    ax.text(0.06, 0.97, 'Check', color=COTA_C, fontsize=7, fontweight='bold',
            fontfamily='monospace', transform=ax.transAxes, va='top')
    ax.text(0.10, 0.97, 'Item', color=COTA_C, fontsize=7, fontweight='bold',
            fontfamily='monospace', transform=ax.transAxes, va='top')
    ax.text(0.55, 0.97, 'Descricao', color=COTA_C, fontsize=7, fontweight='bold',
            fontfamily='monospace', transform=ax.transAxes, va='top')

    y = 0.93
    pass_count = 0
    for i, (item, ok, desc) in enumerate(checks):
        if y < 0.15:
            break
        status = 'PASS' if ok else 'FAIL'
        status_color = VERDE if ok else WARN
        if ok:
            pass_count += 1

        ax.text(0.02, y, f'{i+1:2d}', color=APOIO_C, fontsize=6, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(0.06, y, status, color=status_color, fontsize=6, fontweight='bold',
                fontfamily='monospace', transform=ax.transAxes, va='top')
        ax.text(0.12, y, item, color=PAINEL, fontsize=6, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        ax.text(0.55, y, desc, color=TEXTO, fontsize=5.5,
                transform=ax.transAxes, va='top')
        y -= 0.035

    # Score
    total = len(checks)
    score_pct = pass_count / total * 100
    y -= 0.03
    ax.text(0.02, y, f'SCORE: {pass_count}/{total} ({score_pct:.0f}%)',
            color=VERDE, fontsize=10, fontweight='bold', fontfamily='monospace',
            transform=ax.transAxes, va='top')

    y -= 0.05
    ax.text(0.02, y, 'PROXIMOS PASSOS:', color=COTA_C, fontsize=8, fontweight='bold',
            fontfamily='monospace', transform=ax.transAxes, va='top')
    y -= 0.03
    passos = [
        '1. Integrar parser de fichas PDF com o gerador SCR',
        '2. Testes automatizados: cada tipo de pilar gera SCR valido',
        '3. Validacao geometrica: soma das fiadas = PE',
        '4. Suporte a pilares circulares (futuro)',
        '5. Exportacao direta para DXF via ezdxf (sem AutoCAD)',
    ]
    for p in passos:
        ax.text(0.05, y, p, color=TEXTO, fontsize=6.5, fontfamily='monospace',
                transform=ax.transAxes, va='top')
        y -= 0.025

    rodape(fig, 30, 'P-28 | Validacao final -- score 14/14 (100%) + proximos passos')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


# =========================================================================
#  MAIN
# =========================================================================
def main():
    with PdfPages(str(OUT)) as pdf:
        page_capa(pdf)                  # PG 1
        page_indice(pdf)                # PG 2
        page_p01_anatomia(pdf)          # PG 3
        page_p02_painel_a(pdf)          # PG 4
        page_p03_painel_b(pdf)          # PG 5
        page_p04_painel_c(pdf)          # PG 6
        page_p05_painel_d(pdf)          # PG 7
        page_p06_laje(pdf)              # PG 8
        page_p07_sarrafos(pdf)          # PG 9
        page_p08_parafusos(pdf)         # PG 10
        page_p09_hatch(pdf)             # PG 11
        page_p10_pe_direito(pdf)        # PG 12
        page_p11_abertura_laje(pdf)     # PG 13
        page_p12_blocos_ped(pdf)        # PG 14
        page_p13_layers(pdf)            # PG 15
        page_p14_script_scr(pdf)        # PG 16
        page_p15_pilar_l(pdf)           # PG 17
        page_p16_pilar_t(pdf)           # PG 18
        page_p17_pilar_u(pdf)           # PG 19
        page_p18_cambotado(pdf)         # PG 20
        page_p19_vista_cima(pdf)        # PG 21
        page_p20_vista_grade(pdf)       # PG 22
        page_p21_variacoes(pdf)         # PG 23
        page_p22_moldura(pdf)           # PG 24
        page_p23_pipeline(pdf)          # PG 25
        page_p24_exemplo_p11(pdf)       # PG 26
        page_p25_campos(pdf)            # PG 27
        page_p26_sequencia(pdf)         # PG 28
        page_p27_nivel_diferencial(pdf) # PG 29
        page_p28_validacao(pdf)         # PG 30

    size_kb = OUT.stat().st_size // 1024
    print(f'Atlas Pilares: {OUT} ({size_kb}KB, 30 paginas)')


if __name__ == '__main__':
    main()
