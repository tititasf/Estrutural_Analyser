#!/usr/bin/env python3
"""
Fichas Instrutivas Tecnicas - Robo de CAD de Escoramento/Formas de Concreto.

Gera 3 PDFs:
  1. fichas_pilares_instrutivas.pdf  (30 paginas A3 landscape)
  2. fichas_vigas_instrutivas.pdf    (30 paginas A3 landscape)
  3. fichas_lajes_instrutivas.pdf    (15 paginas A3 landscape)

Executa: python scripts/gerar_fichas_instrutivas.py
"""
import sys
import math
import os
import traceback
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc, Polygon, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ==========================================================================
# CONSTANTS
# ==========================================================================
BG      = '#0a0a14'
FG      = '#e0e0e0'
GOLD    = '#ffbf00'
RED     = '#ff0000'
CYAN    = '#00ffff'
GRAY    = '#888888'
DGRAY   = '#5b5b5b'
YELLOW  = '#ffff00'
GREEN   = '#00ff00'
WHITE   = '#ffffff'
LGRAY   = '#c8c8c8'
ACCENT  = '#e8b84b'   # titulos

plt.rcParams.update({
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'axes.edgecolor': '#333355',
    'text.color': FG,
    'xtick.color': '#666666',
    'ytick.color': '#666666',
    'font.family': 'monospace',
    'figure.max_open_warning': 200,
})

# ==========================================================================
# FILE PATHS
# ==========================================================================
BASE = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
REV  = "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
OUT_DIR = Path("D:/Agente-cad-PYSIDE/docs/fichas")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PL_1 = BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- PL - R00.dxf"
LV_1 = BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- LV - R00.dxf"
LJ_1 = BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- LJ - R00.dxf"
FV_1 = BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- FV - R00.dxf"
PL_2 = BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-PL-R01_R2018_ASCII_ODA.dxf"
LV_2 = BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LV-R00_R2018_ASCII_ODA.dxf"
LJ_2 = BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LJ-R00_R2018_ASCII_ODA.dxf"
PL_3 = BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - PL - R00_R2018_ASCII_ODA.dxf"
LV_3 = BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO  - LV - R00_R2018_ASCII_ODA.dxf"
LJ_3 = BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - LJ - R00_R2018_ASCII_ODA.dxf"
FV_2 = BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-FV-R00_R2018_ASCII_ODA.dxf"

OBRA_NAMES = {
    'Obra_TREINO_1':  'ALIMONTI Paraiso',
    'Obra_TREINO_11': 'NOVA-SCHWARTZ GWT',
    'Obra_TREINO_13': 'SKR LEAF',
}

# Zoom regions (from validated atlas scripts)
PL_ZOOM_P1P2 = (4280, 12060, 6040, 12760)
PL_ZOOM_FULL = (2600, 11900, 8700, 12800)
LV_ZOOM_1    = (3000, 5500, 6000, 7100)
LV_AREA_ALL  = (3000, 700, 9100, 7100)
LJ_AREA_ALL  = (3500, 1500, 7200, 2900)

# ==========================================================================
# LAYER COLORS (real ACI extractions from DXFs)
# ==========================================================================
LAYER_COLORS = {
    '0':                   '#ffffff',
    'Pain\u00e9is':        '#888888',
    'Paineis':             '#888888',
    'SARRAFO':             '#5b5b5b',
    'SARR_2.2x7':          '#ffbf00',
    'SARR_2.2x10':         '#7fff00',
    'SARR_2.2x15':         '#888888',
    'SARR_2.2x20':         '#00ff7f',
    'SARR_3.5x7':          '#888888',
    'SARR_7x7':            '#ffbf00',
    'SARR_7x10':           '#ff007f',
    'SARR_EDITAR':         '#888888',
    'Sarr 2.2x7':          '#ffbf00',
    'SARRAFO DE PRESSAO':  '#5b5b5b',
    'Sarrafo de Press\u00e3o': '#888888',
    'Madeira':             '#888888',
    'MEIO_PONT':           '#888888',
    'PONTALETE':           '#ffffff',
    'CHAPA':               '#ff0000',
    'Perfil Met\u00e1lico':'#888888',
    'BARRA ANCORAGEM':     '#5b5b5b',
    'BARRA DE ANCORAGEM':  '#5b5b5b',
    'CONCRETO':            '#5b5b5b',
    'COTA':                '#888888',
    'cotas':               '#00ffff',
    'Hachura':             '#5b5b5b',
    'Demarca\u00e7\u00e3o 1': '#5b5b5b',
    'Demarca\u00e7\u00e3o 2': '#d6d6d6',
    'NOMENCLATURA':        '#ffffff',
    'texto':               '#ffffff',
    'TEXTO_GERAL':         '#ffffff',
    'Texto Se\u00e7\u00e3o': '#ffffff',
    'Texto N\u00edvel':    '#5b5b5b',
    'NIVEL':               '#ffffff',
    'N\u00edvel':          '#3b3b3b',
    'Laje_Perimetro':      '#ffffff',
    'Folhas':              '#ffffff',
    'CARIMBO':             '#ffffff',
    'GARFOS':              '#ffffff',
    'HACHURA MADEIRAS':    '#ff0000',
    'Escoras':             '#ffff00',
    'Forcador':            '#5b5b5b',
    'TENSOR':              '#00ff00',
    'presilha':            '#ff0000',
    'fundo':               '#007fff',
    'barrote':             '#5b5b5b',
    '5':                   '#0000ff',
    'REAPROVEITAMENTO':    '#ffff00',
    'Pilares':             '#888888',
    'VIGAS':               '#888888',
    'FOLHA':               '#ffffff',
    'FELIPE':              '#ffff00',
    'GRAVATA':             '#ffff00',
    '1-2 PONTALETE':       '#ffffff',
    'va165-sec':           '#0000ff',
    '00 - FELIPE':         '#ffff00',
}

ACI_COLORS = {
    1: '#ff0000', 2: '#ffff00', 3: '#00ff00', 4: '#00ffff', 5: '#0000ff',
    6: '#ff00ff', 7: '#ffffff', 8: '#808080', 9: '#c0c0c0',
    40: '#ffbf00', 41: '#888888', 60: '#7fff00', 61: '#888888',
    80: '#00ff7f', 81: '#888888', 93: '#888888', 100: '#007fff',
    111: '#888888', 121: '#888888', 126: '#888888', 140: '#ff007f',
    141: '#888888', 160: '#333333', 200: '#888888', 224: '#888888',
    241: '#888888', 251: '#5b5b5b', 254: '#d6d6d6', 255: '#ffffff',
}

def aci_to_hex(aci):
    if aci == 0:
        return '#ffffff'
    if aci < 0:
        aci = -aci
    return ACI_COLORS.get(aci, '#888888')


# ==========================================================================
# FIGURE HELPERS
# ==========================================================================
def fig_a3(title='', subtitle=''):
    """A3 landscape: 42 x 29.7 cm."""
    fig = plt.figure(figsize=(16.54, 11.69))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(0.5, 0.97, title, ha='center', va='top',
                 fontsize=13, color=ACCENT, fontweight='bold', fontfamily='monospace')
    if subtitle:
        fig.text(0.5, 0.945, subtitle, ha='center', va='top',
                 fontsize=8, color=LGRAY)
    return fig

def setup_ax(ax, title=''):
    ax.set_facecolor(BG)
    ax.set_aspect('equal')
    ax.axis('off')
    if title:
        ax.set_title(title, color=ACCENT, fontsize=10, fontweight='bold',
                     pad=6, fontfamily='monospace')
    # S1-T1: Tighten subplot margins for better layout fill
    if ax.figure is not None:
        ax.figure.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.06)
    # S1-T4: Scale bar on drawing subplots
    draw_scale_bar(ax)

def rodape(fig, pg, total, txt):
    fig.text(0.5, 0.012, f'Pagina {pg}/{total} | {txt}', ha='center', va='bottom',
             fontsize=6.5, color=LGRAY, style='italic')


# ==========================================================================
# DRAWING PRIMITIVES
# ==========================================================================
def draw_painel(ax, x, y, w, h, color=GRAY, hatch=True, lw=1.0, alpha=0.85):
    """Desenha um painel retangular com hachura ANSI31 (diagonal 45 graus) se hatch=True."""
    r = mpatches.Rectangle((x, y), w, h, linewidth=lw,
                            edgecolor='white', facecolor=color, alpha=alpha, zorder=2)
    ax.add_patch(r)
    if hatch:
        # S1-T3: Hachura diagonal mais densa e visivel (ANSI31)
        spacing = max(w, h) * 0.10
        if spacing < 0.5:
            spacing = 0.5
        diag = max(w, h) * 2
        n = int(diag / spacing) + 2
        for i in range(-n, n):
            offset = i * spacing
            x1h = x + offset
            y1h = y
            x2h = x + offset + h
            y2h = y + h
            # Clip to rectangle
            xs, ys, xe, ye = _clip_line_to_rect(x1h, y1h, x2h, y2h, x, y, x + w, y + h)
            if xs is not None:
                ax.plot([xs, xe], [ys, ye], color='#aaaaaa', lw=0.5, alpha=0.8, zorder=3)
    return r


def _clip_line_to_rect(x1, y1, x2, y2, xmin, ymin, xmax, ymax):
    """Cohen-Sutherland simple line clipping to rectangle."""
    dx = x2 - x1
    dy = y2 - y1
    t0, t1 = 0.0, 1.0
    for edge in [(-dx, x1 - xmin), (dx, xmax - x1), (-dy, y1 - ymin), (dy, ymax - y1)]:
        p, q = edge
        if abs(p) < 1e-12:
            if q < 0:
                return None, None, None, None
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
    if t0 > t1:
        return None, None, None, None
    return x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy


def draw_sarrafo(ax, x, y, w, h, color=GOLD, lw=1.0, alpha=0.9):
    """Desenha secao de sarrafo."""
    r = mpatches.Rectangle((x, y), w, h, linewidth=lw,
                            edgecolor='white', facecolor=color, alpha=alpha, zorder=3)
    ax.add_patch(r)
    return r


def draw_chapa(ax, x, y, h, color=RED, w=4, lw=0.8):
    """Chapa estreita W=4mm."""
    r = mpatches.Rectangle((x, y), w, h, linewidth=lw,
                            edgecolor=RED, facecolor=color, alpha=0.9, zorder=4)
    ax.add_patch(r)
    return r


def draw_pontalete(ax, cx, cy, size=14, color=WHITE):
    """Quadrado com arco de 90 graus (pontalete)."""
    hs = size / 2
    r = mpatches.Rectangle((cx - hs, cy - hs), size, size, linewidth=1.0,
                            edgecolor=color, facecolor=BG, alpha=0.9, zorder=4)
    ax.add_patch(r)
    arc = Arc((cx - hs, cy - hs), size * 0.8, size * 0.8, angle=0,
              theta1=0, theta2=90, color=color, lw=0.8, zorder=5)
    ax.add_patch(arc)


def draw_ht20ct(ax, cx, cy, w=80, h=80, color=YELLOW, lw=1.5):
    """Forma em U/H (escora HT20CT)."""
    # Perna esquerda
    ax.plot([cx - w/2, cx - w/2], [cy, cy + h], color=color, lw=lw, zorder=4)
    # Perna direita
    ax.plot([cx + w/2, cx + w/2], [cy, cy + h], color=color, lw=lw, zorder=4)
    # Topo horizontal
    ax.plot([cx - w/2, cx + w/2], [cy + h, cy + h], color=color, lw=lw, zorder=4)


def draw_grade(ax, x, y, w, h, color=GRAY, grid_spacing=50, alpha=0.7):
    """Painel de grade metalica - retangulo azul-acinzentado + grid interno."""
    # S1-T2: Cores distinguiveis em fundo escuro
    GRADE_BG = '#1a2a4a'    # azul escuro distinguivel
    GRADE_GRID = '#5b9bd5'  # azul medio
    r = mpatches.Rectangle((x, y), w, h, linewidth=1.5,
                            edgecolor='#8ab4d4', facecolor=GRADE_BG, alpha=0.85, zorder=2)
    ax.add_patch(r)
    # Grid vertical (mais visivel)
    gx = x + grid_spacing
    while gx < x + w - 1:
        ax.plot([gx, gx], [y, y + h], color=GRADE_GRID, lw=0.5, alpha=0.7, zorder=3)
        gx += grid_spacing
    # Grid horizontal (mais visivel)
    gy = y + grid_spacing
    while gy < y + h - 1:
        ax.plot([x, x + w], [gy, gy], color=GRADE_GRID, lw=0.5, alpha=0.7, zorder=3)
        gy += grid_spacing


def draw_scale_bar(ax, scale_mm_per_unit=1.0, bar_length_mm=100):
    """S1-T4: Desenha barra de escala no canto inferior direito do ax em coordenadas de axes."""
    bar_units = bar_length_mm / scale_mm_per_unit
    # Posicao em axes coords (0.97 right, 0.04 bottom)
    x_end = 0.97
    x_start = x_end - 0.15  # 15% da largura do axes
    y_pos = 0.04
    # Linha principal
    ax.plot([x_start, x_end], [y_pos, y_pos], transform=ax.transAxes,
            color=FG, lw=1.5, solid_capstyle='butt', clip_on=False, zorder=20)
    # Marcadores nas extremidades
    for xp in [x_start, x_end]:
        ax.plot([xp, xp], [y_pos - 0.015, y_pos + 0.015], transform=ax.transAxes,
                color=FG, lw=1.5, clip_on=False, zorder=20)
    # Texto
    ax.text((x_start + x_end) / 2, y_pos + 0.02, f'{bar_length_mm:.0f}mm',
            transform=ax.transAxes, ha='center', va='bottom',
            fontsize=6, color=FG, zorder=20)


def draw_cota(ax, x1, y1, x2, y2, offset, label, cor=CYAN, fs=6.5, orientation='auto'):
    """
    Cota estilo ABNT: 2 linhas de extensao + linha de cota + setas nas pontas + texto.

    x1,y1 -> x2,y2: os dois pontos sendo cotados
    offset: distancia perpendicular da linha de cota aos pontos
    label: texto a exibir (ex: '200mm')
    orientation: 'h' = horizontal, 'v' = vertical, 'auto' = detectar
    """
    dx = x2 - x1
    dy = y2 - y1
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 1e-6:
        return

    # Detectar orientacao
    if orientation == 'auto':
        orientation = 'h' if abs(dx) >= abs(dy) else 'v'

    if orientation == 'h':
        # Cota horizontal: offset vai em Y
        ex1, ey1 = x1, y1 + offset * 0.1  # ponto inicio linha extensao
        ex2, ey2 = x1, y1 + offset         # ponta da extensao
        ex3, ey3 = x2, y2 + offset * 0.1
        ex4, ey4 = x2, y2 + offset
        # Linha de extensao 1
        ax.plot([ex1, ex2], [ey1, ey2], color=cor, lw=0.6, zorder=8)
        # Linha de extensao 2
        ax.plot([ex3, ex4], [ey3, ey4], color=cor, lw=0.6, zorder=8)
        # Linha de cota com setas
        ax.annotate('', xy=(ex2, ey2), xytext=(ex4, ey4),
                    arrowprops=dict(arrowstyle='<->', color=cor, lw=0.8), zorder=8)
        # Texto no meio
        mx, my = (ex2 + ex4) / 2, ey2 + abs(offset) * 0.08
        ax.text(mx, my, label, ha='center', va='bottom', color=cor, fontsize=fs,
                fontweight='bold', zorder=9,
                bbox=dict(facecolor=BG, alpha=0.85, pad=1.5, edgecolor='none'))
    else:
        # Cota vertical: offset vai em X
        ex1, ey1 = x1 + offset * 0.1, y1
        ex2, ey2 = x1 + offset, y1
        ex3, ey3 = x2 + offset * 0.1, y2
        ex4, ey4 = x2 + offset, y2
        ax.plot([ex1, ex2], [ey1, ey2], color=cor, lw=0.6, zorder=8)
        ax.plot([ex3, ex4], [ey3, ey4], color=cor, lw=0.6, zorder=8)
        ax.annotate('', xy=(ex2, ey2), xytext=(ex4, ey4),
                    arrowprops=dict(arrowstyle='<->', color=cor, lw=0.8), zorder=8)
        mx, my = ex2 + abs(offset) * 0.08, (ey2 + ey4) / 2
        ax.text(mx, my, label, ha='left', va='center', color=cor, fontsize=fs,
                fontweight='bold', rotation=90 if abs(offset) > 0 else 0, zorder=9,
                bbox=dict(facecolor=BG, alpha=0.85, pad=1.5, edgecolor='none'))


def draw_carimbo(fig, titulo, obra='', escala='1:20', folha='01', total_folhas='30'):
    """
    Carimbo profissional no canto inferior direito (estilo prancha tecnica).
    Usa fig.add_axes em coordenadas figure (0-1).
    """
    # Area do carimbo: 28% largura, 8% altura, canto inferior direito
    ax_c = fig.add_axes([0.72, 0.01, 0.27, 0.065])
    ax_c.set_facecolor('#0d0d1a')
    ax_c.set_xlim(0, 100)
    ax_c.set_ylim(0, 100)
    ax_c.axis('off')

    # Borda
    border = mpatches.Rectangle((0, 0), 100, 100, fill=False,
                                  edgecolor='#335577', lw=1.0)
    ax_c.add_patch(border)

    # Linha divisoria interna
    ax_c.plot([0, 100], [55, 55], color='#335577', lw=0.5)
    ax_c.plot([50, 50], [0, 55], color='#335577', lw=0.5)

    # Titulo
    ax_c.text(50, 88, titulo[:40], ha='center', va='center',
              color=ACCENT, fontsize=5.5, fontweight='bold', fontfamily='monospace')

    # Obra
    if obra:
        ax_c.text(50, 70, f'Obra: {obra[:30]}', ha='center', va='center',
                  color=FG, fontsize=4.5, fontfamily='monospace')

    # Escala (esquerda)
    ax_c.text(5, 40, 'ESCALA', ha='left', va='center', color=LGRAY, fontsize=4, fontfamily='monospace')
    ax_c.text(5, 22, escala, ha='left', va='center', color=WHITE, fontsize=5.5, fontweight='bold', fontfamily='monospace')

    # Folha (direita)
    ax_c.text(55, 40, 'FOLHA', ha='left', va='center', color=LGRAY, fontsize=4, fontfamily='monospace')
    ax_c.text(55, 22, f'{folha}/{total_folhas}', ha='left', va='center', color=WHITE, fontsize=5.5, fontweight='bold', fontfamily='monospace')


def draw_decision_box(ax, x, y, w, h, text, color=None, text_color=None, fontsize=7, zorder=5):
    """Caixa retangular de processo no fluxograma."""
    if color is None:
        color = '#1a3a5a'
    if text_color is None:
        text_color = '#e0e0e0'
    r = mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.015',
                                  facecolor=color, edgecolor='#5599cc', lw=1.0, zorder=zorder)
    ax.add_patch(r)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        ax.text(x + w/2, y + h/2 + (len(lines)-1-2*i)*h*0.18,
                line, ha='center', va='center',
                color=text_color, fontsize=fontsize, fontweight='bold', zorder=zorder+1)


def draw_decision_diamond(ax, cx, cy, w, h, text, color=None, text_color=None, fontsize=6.5):
    """Losango de decisao condicional no fluxograma."""
    if color is None:
        color = '#4a3000'
    if text_color is None:
        text_color = GOLD
    diamond = Polygon([(cx, cy+h/2), (cx+w/2, cy), (cx, cy-h/2), (cx-w/2, cy)],
                       closed=True, facecolor=color, edgecolor=GOLD, lw=1.0, zorder=5)
    ax.add_patch(diamond)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        ax.text(cx, cy + (len(lines)-1-2*i)*h*0.2,
                line, ha='center', va='center',
                color=text_color, fontsize=fontsize, fontweight='bold', zorder=6)


def draw_flow_arrow(ax, x1, y1, x2, y2, label='', color=None):
    """Seta de fluxo entre elementos do diagrama."""
    if color is None:
        color = '#7799bb'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.0,
                                connectionstyle='arc3,rad=0.0'), zorder=4)
    if label:
        mx, my = (x1 + x2) / 2 + 3, (y1 + y2) / 2
        ax.text(mx, my, label, color=color, fontsize=6, va='center', zorder=6,
                bbox=dict(facecolor=BG, alpha=0.7, pad=1, edgecolor='none'))


def draw_json_schema(ax, x, y, title, fields, w=0.45, fs=6.0):
    """
    Bloco visual de JSON schema para o robo.
    fields = list of (nome, tipo, exemplo, obrigatorio)
    Renderiza em coordenadas de axes (transAxes).
    """
    # Fundo do bloco
    bg_rect = mpatches.FancyBboxPatch((x, y - len(fields)*0.038 - 0.06), w, len(fields)*0.038 + 0.07,
                                        boxstyle='round,pad=0.01',
                                        facecolor='#050510', edgecolor='#335577',
                                        lw=1.0, zorder=4, transform=ax.transAxes)
    ax.add_patch(bg_rect)
    # Titulo
    ax.text(x + 0.01, y - 0.01, f'// {title}', color='#66aacc', fontsize=fs+0.5,
            fontfamily='monospace', va='top', transform=ax.transAxes, zorder=5)
    ax.text(x + 0.01, y - 0.025, '{', color=FG, fontsize=fs+1,
            fontfamily='monospace', va='top', transform=ax.transAxes, zorder=5)
    for i, (nome, tipo, exemplo, obrig) in enumerate(fields):
        req_marker = '\u25cf' if obrig else '\u25cb'
        req_color = GREEN if obrig else DGRAY
        line = f'  {req_marker} "{nome}": {tipo} = {exemplo}'
        ax.text(x + 0.01, y - 0.05 - i*0.038, line,
                color=CYAN if obrig else LGRAY, fontsize=fs,
                fontfamily='monospace', va='top', transform=ax.transAxes, zorder=5)
    ax.text(x + 0.01, y - 0.05 - len(fields)*0.038, '}',
            color=FG, fontsize=fs+1, fontfamily='monospace',
            va='top', transform=ax.transAxes, zorder=5)
    # Legenda de obrigatoriedade
    ax.text(x + w - 0.01, y - 0.01, '\u25cf obrigatorio  \u25cb opcional',
            color=LGRAY, fontsize=fs-1, fontfamily='monospace',
            va='top', ha='right', transform=ax.transAxes, zorder=5)


def draw_pilar_isometrico(ax, cw, ch, ph=300, scale=0.4):
    """
    Pilar em projecao cavaleira isometrica (30 graus).
    cw = largura, ch = altura/comprimento, ph = pe direito (altura real da forma).
    """
    s = scale
    ang = math.radians(30)
    cos_a = math.cos(ang) * 0.5  # fator de profundidade reduzido
    sin_a = math.sin(ang) * 0.5

    cw_s, ch_s, ph_s = cw * s, ch * s, ph * s
    depth = min(cw_s, ch_s) * 0.6  # profundidade da vista iso

    # iso(x, y, z) -> (px, py) em unidades do plot
    def iso(x, y, z):
        return x * s + z * cos_a, y * s + z * sin_a

    pe = 22 * s   # espessura painel

    # --- Concreto: caixa 3D (3 faces visiveis) ---
    conc_front = [iso(0,0,0), iso(cw,0,0), iso(cw,ph,0), iso(0,ph,0)]
    conc_right = [iso(cw,0,0), iso(cw,0,depth), iso(cw,ph,depth), iso(cw,ph,0)]
    conc_top   = [iso(0,ph,0), iso(cw,ph,0), iso(cw,ph,depth), iso(0,ph,depth)]

    for pts, alpha in [(conc_top, 0.35), (conc_right, 0.25), (conc_front, 0.4)]:
        poly = Polygon(pts, closed=True, facecolor=DGRAY, edgecolor='#444466', lw=0.6, alpha=alpha, zorder=2)
        ax.add_patch(poly)

    # --- Painel frontal (esquerda): z=0 ---
    pan_left_front = [iso(-pe,0,0), iso(0,0,0), iso(0,ph,0), iso(-pe,ph,0)]
    poly_plf = Polygon(pan_left_front, closed=True, facecolor=GRAY, edgecolor='white', lw=0.5, alpha=0.7, zorder=3)
    ax.add_patch(poly_plf)

    # Painel direito frente
    pan_right_front = [iso(cw,0,0), iso(cw+pe,0,0), iso(cw+pe,ph,0), iso(cw,ph,0)]
    poly_prf = Polygon(pan_right_front, closed=True, facecolor=GRAY, edgecolor='white', lw=0.5, alpha=0.7, zorder=3)
    ax.add_patch(poly_prf)

    # Painel superior (topo) direito
    pan_right_top = [iso(cw,ph,0), iso(cw+pe,ph,0), iso(cw+pe,ph,depth), iso(cw,ph,depth)]
    poly_prt = Polygon(pan_right_top, closed=True, facecolor='#666666', edgecolor='white', lw=0.5, alpha=0.6, zorder=3)
    ax.add_patch(poly_prt)

    # Sarrafos (dourado) na junta central
    sarr_pts = [iso(-pe, ph*0.4, 0), iso(-pe-22*s/s, ph*0.4, 0),
                iso(-pe-22*s/s, ph*0.6, 0), iso(-pe, ph*0.6, 0)]
    poly_sarr = Polygon(sarr_pts, closed=True, facecolor=GOLD, edgecolor='white', lw=0.5, alpha=0.85, zorder=4)
    ax.add_patch(poly_sarr)

    # CHAPA (vermelho) na quina
    chapa_pts = [iso(-pe-4*s/s, 0, 0), iso(-pe, 0, 0), iso(-pe, ph, 0), iso(-pe-4*s/s, ph, 0)]
    poly_chapa = Polygon(chapa_pts, closed=True, facecolor=RED, edgecolor=RED, lw=0.5, alpha=0.9, zorder=5)
    ax.add_patch(poly_chapa)

    # Anotacoes
    tx, ty = iso(-pe*1.8, ph*0.5, 0)
    ax.text(tx - 10, ty, 'Painel', ha='right', va='center', color=GRAY, fontsize=6.5, fontweight='bold', zorder=10)
    tx2, ty2 = iso(cw+pe*1.5, ph*0.5, 0)
    ax.text(tx2 + 5, ty2, 'Painel', ha='left', va='center', color=GRAY, fontsize=6.5, fontweight='bold', zorder=10)
    tx3, ty3 = iso(cw/2, ph+20*s/s, 0)
    ax.text(tx3, ty3, f'{cw}x{ch}mm', ha='center', va='bottom', color=CYAN, fontsize=7, fontweight='bold', zorder=10)
    tx4, ty4 = iso(-pe*2.5, ph*0.45, 0)
    ax.text(tx4-8, ty4, 'SARR', ha='right', va='center', color=GOLD, fontsize=6, fontweight='bold', zorder=10)
    tx5, ty5 = iso(-pe*1.3, ph*0.2, 0)
    ax.text(tx5-5, ty5, 'CHAPA', ha='right', va='center', color=RED, fontsize=6, fontweight='bold', zorder=10)
    # Label PD (altura)
    lx, ly = iso(-pe-40*s/s, ph/2, 0)
    ax.annotate('', xy=iso(-pe-30*s/s, ph, 0), xytext=iso(-pe-30*s/s, 0, 0),
                arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8), zorder=8)
    ax.text(lx-5, ly, f'PD={ph}mm', ha='right', va='center', color=CYAN, fontsize=6,
            fontweight='bold', zorder=10)


def draw_concreto(ax, x, y, w, h, color=DGRAY, alpha=0.5):
    """Secao de concreto com hachura AR-CONC (diagonais cruzadas)."""
    r = mpatches.Rectangle((x, y), w, h, linewidth=1.0,
                            edgecolor=DGRAY, facecolor=color, alpha=alpha * 0.5, zorder=1)
    ax.add_patch(r)
    spacing = max(w, h) * 0.12
    if spacing < 1:
        spacing = 1
    diag = max(w, h) * 2
    n = int(diag / spacing) + 2
    # Diagonal 45
    for i in range(-n, n):
        offset = i * spacing
        xs, ys, xe, ye = _clip_line_to_rect(x + offset, y, x + offset + h, y + h,
                                             x, y, x + w, y + h)
        if xs is not None:
            ax.plot([xs, xe], [ys, ye], color=DGRAY, lw=0.3, alpha=0.4, zorder=1)
    # Diagonal -45
    for i in range(-n, n):
        offset = i * spacing
        xs, ys, xe, ye = _clip_line_to_rect(x + offset + h, y, x + offset, y + h,
                                             x, y, x + w, y + h)
        if xs is not None:
            ax.plot([xs, xe], [ys, ye], color=DGRAY, lw=0.3, alpha=0.3, zorder=1)


def draw_pilar_topo(ax, cx, cy, cw, ch, painel_esp=22, sarr_w=22, sarr_h=70,
                    scale=1.0, annotate_parts=True):
    """Pilar completo em vista de cima (planta)."""
    s = scale
    cw_s, ch_s = cw * s, ch * s
    pe = painel_esp * s
    sw, sh = sarr_w * s, sarr_h * s
    chapa_w = 4 * s
    perf_w = 15 * s
    pont_sz = 14 * s

    # Concreto central
    draw_concreto(ax, cx - cw_s/2, cy - ch_s/2, cw_s, ch_s)

    # 4 faces de paineis
    # Face Sul (baixo)
    draw_painel(ax, cx - cw_s/2 - pe, cy - ch_s/2 - pe, cw_s + 2*pe, pe, GRAY)
    # Face Norte (cima)
    draw_painel(ax, cx - cw_s/2 - pe, cy + ch_s/2, cw_s + 2*pe, pe, GRAY)
    # Face Oeste (esquerda)
    draw_painel(ax, cx - cw_s/2 - pe, cy - ch_s/2, pe, ch_s, GRAY)
    # Face Leste (direita)
    draw_painel(ax, cx + cw_s/2, cy - ch_s/2, pe, ch_s, GRAY)

    # Sarrafos nas juntas (centro de cada face)
    # Sul
    draw_sarrafo(ax, cx - sw/2, cy - ch_s/2 - pe - sh, sw, sh, GOLD)
    # Norte
    draw_sarrafo(ax, cx - sw/2, cy + ch_s/2 + pe, sw, sh, GOLD)
    # Oeste
    draw_sarrafo(ax, cx - cw_s/2 - pe - sh, cy - sw/2, sh, sw, GOLD)
    # Leste
    draw_sarrafo(ax, cx + cw_s/2 + pe, cy - sw/2, sh, sw, GOLD)

    # Chapas nas 4 quinas
    corners = [
        (cx - cw_s/2 - pe - chapa_w, cy - ch_s/2 - pe),
        (cx + cw_s/2 + pe, cy - ch_s/2 - pe),
        (cx - cw_s/2 - pe - chapa_w, cy + ch_s/2),
        (cx + cw_s/2 + pe, cy + ch_s/2),
    ]
    for (qx, qy) in corners:
        draw_chapa(ax, qx, qy, pe + ch_s, RED, w=chapa_w * s)

    # Perfil Metalico fora da CHAPA
    for (qx, qy) in corners:
        px = qx - perf_w if qx < cx else qx + chapa_w * s
        r = mpatches.Rectangle((px, qy), perf_w, pe + ch_s, lw=0.6,
                                edgecolor=LGRAY, facecolor=LGRAY, alpha=0.4, zorder=3)
        ax.add_patch(r)

    # Pontaletes nos cantos externos
    pont_offsets = [
        (cx - cw_s/2 - pe - sh - pont_sz, cy - ch_s/2 - pe - pont_sz),
        (cx + cw_s/2 + pe + sh + pont_sz, cy - ch_s/2 - pe - pont_sz),
        (cx - cw_s/2 - pe - sh - pont_sz, cy + ch_s/2 + pe + pont_sz),
        (cx + cw_s/2 + pe + sh + pont_sz, cy + ch_s/2 + pe + pont_sz),
    ]
    for (px, py) in pont_offsets:
        draw_pontalete(ax, px, py, pont_sz)

    if annotate_parts:
        ann_kw = dict(fontsize=6.5, color=FG, fontweight='bold',
                      bbox=dict(facecolor=BG, alpha=0.8, pad=1, edgecolor='none'),
                      zorder=10)
        # Concreto
        ax.text(cx, cy, 'CONCRETO', ha='center', va='center', fontsize=7,
                color=DGRAY, fontweight='bold', zorder=10)
        # Painel
        annotate_arrow(ax, f'Painel W={painel_esp}mm', (cx, cy - ch_s/2 - pe/2),
                       (cx + cw_s * 0.6, cy - ch_s/2 - pe * 3), GRAY)
        # Sarrafo
        annotate_arrow(ax, 'SARR_2.2x7', (cx - sw/2, cy - ch_s/2 - pe - sh/2),
                       (cx - cw_s * 0.7, cy - ch_s * 0.9), GOLD)
        # CHAPA
        annotate_arrow(ax, 'CHAPA', corners[0], (cx - cw_s * 0.9, cy - ch_s * 0.1), RED)
        # Perfil Met.
        annotate_arrow(ax, 'Perfil Met.', (corners[1][0] + perf_w, corners[1][1] + pe),
                       (cx + cw_s * 0.9, cy - ch_s * 0.3), LGRAY)
        # Pontalete
        annotate_arrow(ax, 'Pontalete', pont_offsets[0],
                       (cx - cw_s * 1.1, cy + ch_s * 0.3), WHITE)


def draw_viga_corte(ax, cx, cy, vw, vh, com_garfo=True, tipo='sarr', scale=1.0,
                    annotate_parts=True):
    """Corte transversal de viga."""
    s = scale
    vw_s, vh_s = vw * s, vh * s
    pe = 22 * s   # espessura painel

    # Concreto central
    draw_concreto(ax, cx - vw_s/2, cy - vh_s/2, vw_s, vh_s)

    # Fundo de viga (painel horizontal embaixo)
    draw_painel(ax, cx - vw_s/2 - pe, cy - vh_s/2 - pe, vw_s + 2*pe, pe, GRAY)

    # Laterais
    if tipo == 'sarr':
        # Sarrafeado: painel + sarrafo externo
        draw_painel(ax, cx - vw_s/2 - pe, cy - vh_s/2, pe, vh_s, GRAY)
        draw_painel(ax, cx + vw_s/2, cy - vh_s/2, pe, vh_s, GRAY)
        draw_sarrafo(ax, cx - vw_s/2 - pe - 22*s, cy - vh_s/4, 22*s, 70*s, GOLD)
        draw_sarrafo(ax, cx + vw_s/2 + pe, cy - vh_s/4, 22*s, 70*s, GOLD)
    else:
        # Grade
        draw_grade(ax, cx - vw_s/2 - pe, cy - vh_s/2, pe, vh_s, GRAY, grid_spacing=15*s)
        draw_grade(ax, cx + vw_s/2, cy - vh_s/2, pe, vh_s, GRAY, grid_spacing=15*s)

    # HT20CT por cima
    draw_ht20ct(ax, cx, cy + vh_s/2 + pe, w=vw_s + 2*pe + 40*s, h=30*s,
                color=YELLOW, lw=1.5)

    if com_garfo:
        # Barra de ancoragem horizontal
        ax.plot([cx - vw_s/2 - pe - 40*s, cx + vw_s/2 + pe + 40*s],
                [cy, cy], color=DGRAY, lw=1.5, zorder=5, linestyle='-.')
        # Bloco C nas pontas
        for gx in [cx - vw_s/2 - pe - 30*s, cx + vw_s/2 + pe + 30*s]:
            ax.plot(gx, cy, 'o', color=WHITE, markersize=5, zorder=6)
        # TENSOR vertical
        ax.plot([cx, cx], [cy - vh_s/2 - pe - 20*s, cy + vh_s/2 + pe + 10*s],
                color=GREEN, lw=1.5, zorder=5, linestyle='--')

    if annotate_parts:
        annotate_arrow(ax, 'Concreto', (cx, cy), (cx + vw_s * 0.8, cy + vh_s * 0.6), DGRAY)
        annotate_arrow(ax, 'FV', (cx, cy - vh_s/2 - pe/2),
                       (cx + vw_s * 0.8, cy - vh_s * 0.8), GRAY)
        annotate_arrow(ax, 'HT20CT', (cx, cy + vh_s/2 + pe + 30*s),
                       (cx + vw_s * 0.8, cy + vh_s * 0.9), YELLOW)
        if com_garfo:
            annotate_arrow(ax, 'Garfo/Barra', (cx + vw_s/4, cy),
                           (cx + vw_s * 1.0, cy - vh_s * 0.3), WHITE)
            annotate_arrow(ax, 'Tensor', (cx, cy + vh_s/4),
                           (cx - vw_s * 0.9, cy + vh_s * 0.5), GREEN)


def annotate_arrow(ax, texto, xy_alvo, xy_texto, cor=FG):
    """S1-T5: Anotacao com seta - legibilidade melhorada."""
    ax.annotate(texto, xy=xy_alvo, xytext=xy_texto,
                fontsize=7.0, color=cor, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=cor, lw=1.0,
                                connectionstyle='arc3,rad=0.1'),
                bbox=dict(facecolor='#0a0a20', alpha=0.9, pad=2.5,
                          edgecolor=cor, linewidth=0.5, boxstyle='round,pad=0.3'),
                zorder=10)


def tabela_regras(ax, x, y, titulo, regras, fs=6.5, fc=FG, title_color=ACCENT):
    """Caixa de texto estilo tabela de regras."""
    ax.text(x, y, titulo, color=title_color, fontsize=8, fontweight='bold',
            fontfamily='monospace', va='top', transform=ax.transAxes, zorder=8)
    for i, regra in enumerate(regras):
        ax.text(x + 0.01, y - 0.035 - i * 0.028, regra, color=fc, fontsize=fs,
                fontfamily='monospace', va='top', transform=ax.transAxes, zorder=8)


def tabela_dados(ax, x, y, headers, rows, col_widths=None, fs=6, fc=FG):
    """Tabela de dados simples com headers."""
    if col_widths is None:
        col_widths = [0.15] * len(headers)
    # Header
    cx = x
    for j, h in enumerate(headers):
        ax.text(cx, y, h, color=ACCENT, fontsize=fs + 0.5, fontweight='bold',
                fontfamily='monospace', va='top', transform=ax.transAxes, zorder=8)
        cx += col_widths[j]
    # Rows
    for i, row in enumerate(rows):
        cx = x
        for j, cell in enumerate(row):
            ax.text(cx, y - 0.025 - i * 0.022, str(cell), color=fc, fontsize=fs,
                    fontfamily='monospace', va='top', transform=ax.transAxes, zorder=8)
            cx += col_widths[j]


# ==========================================================================
# DXF RENDERING
# ==========================================================================
try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False
    print("[WARN] ezdxf nao encontrado -- paginas com render DXF serao placeholder")


def _get_entity_color(e, layer_name, dxf_layer_colors):
    """Resolve entity color: entity override > LAYER_COLORS dict > DXF layer > fallback."""
    try:
        ec = getattr(e.dxf, 'color', 256)
        if ec not in (0, 256) and ec > 0:
            c = aci_to_hex(ec)
            if c != '#888888':
                return c
    except Exception:
        pass
    c = LAYER_COLORS.get(layer_name)
    if c:
        return c
    c = dxf_layer_colors.get(layer_name)
    if c:
        return c
    return '#888888'


def _resolve_linestyle(layer_name):
    up = layer_name.upper()
    if 'PRESSAO' in up or 'PRESS' in up or 'DASHED' in up or 'HIDDEN' in up:
        return '--'
    return '-'


def _resolve_linewidth(layer_name, etype):
    if layer_name in ('Pain\u00e9is', 'Paineis', 'PAINEL'):
        return 1.0
    if layer_name in ('CHAPA',):
        return 0.8
    if layer_name.startswith('SARR_') or layer_name == 'SARRAFO':
        return 0.8
    if layer_name in ('CONCRETO',):
        return 0.6
    if etype == 'LINE':
        return 0.3
    if etype == 'ARC':
        return 0.4
    return 0.5


def render_entities(ax, entities, dxf_layer_colors, show_layers=None, hide_layers=None,
                    max_text=5000, alpha_override=None):
    """Render a list of DXF entities onto matplotlib ax."""
    text_count = 0
    for e in entities:
        try:
            layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
            if show_layers and layer not in show_layers:
                continue
            if hide_layers and layer in hide_layers:
                continue
            color = _get_entity_color(e, layer, dxf_layer_colors)
            if color in ('#000000', '#0a0a14', '#080808'):
                color = '#444444'
            etype = e.dxftype()
            lw = _resolve_linewidth(layer, etype)
            ls = _resolve_linestyle(layer)
            a = alpha_override if alpha_override else 0.9

            if etype == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if e.is_closed:
                    xs.append(xs[0])
                    ys.append(ys[0])
                ax.plot(xs, ys, color=color, lw=lw, solid_capstyle='round',
                        linestyle=ls, alpha=a, zorder=2)
            elif etype == 'LINE':
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                ax.plot([x1, x2], [y1, y2], color=color, lw=lw, linestyle=ls,
                        alpha=a, zorder=2)
            elif etype == 'ARC':
                cx, cy = e.dxf.center.x, e.dxf.center.y
                r = e.dxf.radius
                sa, ea = e.dxf.start_angle, e.dxf.end_angle
                arc_patch = Arc((cx, cy), 2 * r, 2 * r, angle=0,
                                theta1=sa, theta2=ea, color=color, lw=lw, alpha=a)
                ax.add_patch(arc_patch)
            elif etype == 'CIRCLE':
                cx, cy = e.dxf.center.x, e.dxf.center.y
                r = e.dxf.radius
                circ = plt.Circle((cx, cy), r, fill=False, edgecolor=color, lw=lw, alpha=a)
                ax.add_patch(circ)
            elif etype == 'HATCH':
                pattern = getattr(e.dxf, 'pattern_name', '')
                ha = 0.15 if pattern == 'ANSI31' else 0.25 if pattern == 'SOLID' else 0.1
                if alpha_override:
                    ha = min(ha, alpha_override * 0.3)
                for bp in e.paths:
                    pts_h = []
                    if hasattr(bp, 'vertices'):
                        pts_h = [(v[0], v[1]) for v in bp.vertices]
                    elif hasattr(bp, 'edges'):
                        for edge in bp.edges:
                            if hasattr(edge, 'start'):
                                pts_h.append((edge.start[0], edge.start[1]))
                            if hasattr(edge, 'end'):
                                pts_h.append((edge.end[0], edge.end[1]))
                    if len(pts_h) >= 3:
                        poly = Polygon(pts_h, closed=True, facecolor=color,
                                       alpha=ha, edgecolor='none', zorder=1)
                        ax.add_patch(poly)
            elif etype in ('TEXT', 'MTEXT'):
                text_count += 1
                if text_count > max_text:
                    continue
                if etype == 'TEXT':
                    txt = e.dxf.text
                    x, y = e.dxf.insert.x, e.dxf.insert.y
                    h = e.dxf.height
                else:
                    txt = e.plain_mtext() if hasattr(e, 'plain_mtext') else ''
                    if '\n' in txt:
                        txt = txt.split('\n')[0]
                    txt = txt[:30]
                    x, y = e.dxf.insert.x, e.dxf.insert.y
                    h = getattr(e.dxf, 'char_height', 50)
                fontsize = max(3, min(8, h / 15))
                ax.text(x, y, txt[:20], color=color, fontsize=fontsize,
                        ha='left', va='bottom', clip_on=True, alpha=a, zorder=3)
            elif etype == 'SPLINE':
                try:
                    pts = list(e.flattening(0.5))
                    if pts:
                        xs = [p.x for p in pts]
                        ys = [p.y for p in pts]
                        ax.plot(xs, ys, color=color, lw=lw, alpha=a, zorder=2)
                except Exception:
                    pass
        except Exception:
            continue


def compute_bbox(entities, show_layers=None, hide_layers=None, max_coord=50000):
    """Compute bounding box, ignoring far-off outlier coordinates."""
    xmin, ymin = float('inf'), float('inf')
    xmax, ymax = float('-inf'), float('-inf')
    def add_pt(x, y):
        nonlocal xmin, xmax, ymin, ymax
        if abs(x) > max_coord or abs(y) > max_coord:
            return
        xmin, xmax = min(xmin, x), max(xmax, x)
        ymin, ymax = min(ymin, y), max(ymax, y)
    for e in entities:
        try:
            layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
            if show_layers and layer not in show_layers:
                continue
            if hide_layers and layer in hide_layers:
                continue
            etype = e.dxftype()
            if etype == 'LWPOLYLINE':
                for p in e.get_points('xy'):
                    add_pt(p[0], p[1])
            elif etype == 'LINE':
                for pt in (e.dxf.start, e.dxf.end):
                    add_pt(pt.x, pt.y)
            elif etype in ('ARC', 'CIRCLE'):
                cx, cy, r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
                add_pt(cx - r, cy - r)
                add_pt(cx + r, cy + r)
            elif etype in ('TEXT', 'MTEXT', 'INSERT', 'POINT'):
                pt = e.dxf.insert if hasattr(e.dxf, 'insert') else (
                    e.dxf.location if hasattr(e.dxf, 'location') else None)
                if pt:
                    add_pt(pt.x, pt.y)
        except Exception:
            continue
    if xmin == float('inf'):
        return (0, 0, 100, 100)
    margin = max((xmax - xmin), (ymax - ymin)) * 0.02
    return (xmin - margin, ymin - margin, xmax + margin, ymax + margin)


def load_dxf(path):
    """Load DXF and return (doc, msp, layer_colors, entity_list, layer_stats)."""
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    lc = {}
    for layer in doc.layers:
        name = layer.dxf.name
        aci = layer.dxf.color
        lc[name] = aci_to_hex(aci)
    entities = list(msp)
    stats = defaultdict(int)
    for e in entities:
        ly = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
        stats[ly] += 1
    return doc, msp, lc, entities, stats


def render_dxf_zona(ax, path, crop=None, hide_layers=None, show_layers=None, title=None):
    """Render de zona especifica do DXF com bbox filtering (abs>50000 ignorados)."""
    if not HAS_EZDXF:
        ax.text(0.5, 0.5, f'[ezdxf nao disponivel]\n{Path(path).name}',
                ha='center', va='center', color=RED, fontsize=10, transform=ax.transAxes)
        setup_ax(ax, title)
        return
    if not Path(path).exists():
        ax.text(0.5, 0.5, f'[arquivo nao encontrado]\n{Path(path).name}',
                ha='center', va='center', color=RED, fontsize=10, transform=ax.transAxes)
        setup_ax(ax, title)
        return
    try:
        doc, msp, lc, entities, stats = load_dxf(path)
        hide_set = set(hide_layers) if hide_layers else None
        show_set = set(show_layers) if show_layers else None
        render_entities(ax, entities, lc, show_layers=show_set, hide_layers=hide_set)
        if crop:
            ax.set_xlim(crop[0], crop[2])
            ax.set_ylim(crop[1], crop[3])
        else:
            bbox = compute_bbox(entities, show_layers=show_set, hide_layers=hide_set)
            ax.set_xlim(bbox[0], bbox[2])
            ax.set_ylim(bbox[1], bbox[3])
        setup_ax(ax, title)
    except Exception as exc:
        ax.text(0.5, 0.5, f'[erro render]\n{exc}',
                ha='center', va='center', color=RED, fontsize=8, transform=ax.transAxes)
        setup_ax(ax, title)


def dxf_annotations(ax, annotations):
    """Add annotation arrows over a DXF render.
    annotations = list of (texto, xy_alvo, xy_texto, cor)
    """
    for (texto, xy_a, xy_t, cor) in annotations:
        annotate_arrow(ax, texto, xy_a, xy_t, cor)


# ==========================================================================
# PDF 1: FICHAS PILARES
# ==========================================================================
def gerar_pilares(pdf_path):
    total = 30
    with PdfPages(str(pdf_path)) as pdf:

        # --- Pg 1: CAPA ---
        print(f'  [Pg 1/{total}] Capa Pilares')
        fig = fig_a3('FICHAS INSTRUTIVAS - PILARES',
                     'Robo de CAD de Escoramento/Formas de Concreto')
        ax = fig.add_axes([0.05, 0.05, 0.9, 0.85])
        ax.set_facecolor(BG)
        ax.axis('off')
        fig.text(0.5, 0.85, 'FICHAS INSTRUTIVAS', ha='center', fontsize=28,
                 color=ACCENT, fontweight='bold', fontfamily='monospace')
        fig.text(0.5, 0.78, 'PILARES', ha='center', fontsize=22,
                 color=WHITE, fontfamily='monospace')
        fig.text(0.5, 0.72, f'30 paginas A3 | Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                 ha='center', fontsize=10, color=LGRAY)
        # Sumario
        sumario = [
            'Pg 2:  Anatomia do Pilar (vista de cima)',
            'Pg 3:  Variacoes por Tamanho',
            'Pg 4:  Representacao dos Paineis (elevacao)',
            'Pg 5:  Sarrafos: Tipos e Posicionamento',
            'Pg 6:  Grades: O que sao e como desenhar',
            'Pg 7:  Blocos: Pontalete, Meio Pontalete, Chapa',
            'Pg 8:  Visao Corte Transversal',
            'Pg 9:  Nomenclatura e Labels',
            'Pg 10: Campos do Robo - Parametros Completos',
            'Pg 11-15: Exemplos Reais (renders DXF anotados)',
            'Pg 16-20: Catalogo de Variacoes',
            'Pg 21-25: Regras de Distribuicao de Paineis',
            'Pg 26-30: Padroes por Obra (dados reais)',
        ]
        for i, s in enumerate(sumario):
            fig.text(0.2, 0.60 - i * 0.032, s, fontsize=9, color=FG, fontfamily='monospace')
        rodape(fig, 1, total, 'Fichas Instrutivas - Pilares')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 2: ANATOMIA DO PILAR (vista de cima/planta) ---
        print(f'  [Pg 2/{total}] Anatomia do Pilar (vista de cima)')
        fig = fig_a3('PG 2 - ANATOMIA DO PILAR (VISTA DE CIMA / PLANTA)')
        ax = fig.add_axes([0.05, 0.08, 0.55, 0.82])
        setup_ax(ax, 'Pilar 200x300mm - Vista de Cima')
        draw_pilar_topo(ax, 0, 0, 200, 300, painel_esp=22, sarr_w=22, sarr_h=70,
                        scale=1.0, annotate_parts=True)
        # Cotas ABNT
        draw_cota(ax, -100, 150, 100, 150, 80, '200mm', CYAN, orientation='h')   # largura pilar
        draw_cota(ax, -100, -150, -100, 150, -180, '300mm', CYAN, orientation='v')  # altura pilar
        draw_cota(ax, 100, -150, 122, -150, -70, '22mm', '#00ffff', orientation='h')  # espessura painel
        ax.set_xlim(-280, 280)
        ax.set_ylim(-350, 350)
        # Tabela de regras a direita
        ax2 = fig.add_axes([0.62, 0.08, 0.35, 0.82])
        ax2.set_facecolor(BG)
        ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'REGRAS VISTA DE CIMA:', [
            '* Paineis envolvem as 4 faces do pilar',
            '* Sarrafos nas juntas entre paineis',
            '* CHAPA nas quinas (ACI=1, vermelho)',
            '* Perfil Met. fora da CHAPA',
            '* Pontaletes no perimetro externo',
            '* Layer CONCRETO = secao real do pilar',
        ])
        tabela_regras(ax2, 0.05, 0.65, 'LAYERS E CORES:', [
            f'Paineis      -> ACI 200 -> {GRAY}  (cinza)',
            f'SARR_2.2x7   -> ACI 40  -> {GOLD}  (dourado)',
            f'CHAPA        -> ACI 1   -> {RED}    (vermelho)',
            f'Perfil Met.  -> ACI 224 -> {LGRAY}  (cinza claro)',
            f'CONCRETO     -> ACI 251 -> {DGRAY}  (cinza escuro)',
            f'PONTALETE    -> ACI 7   -> {WHITE}  (branco)',
        ])
        tabela_regras(ax2, 0.05, 0.35, 'PARAMETROS DO ROBO:', [
            'largura_pilar (mm): 200',
            'altura_pilar  (mm): 300',
            'tipo_panel: PA-022x100',
            'esp_painel: 22mm',
            'sarrafo_tipo: SARR_2.2x7',
        ])
        draw_carimbo(fig, 'ANATOMIA DO PILAR', 'Vista de Cima / Planta', '1:5', '02', '30')
        rodape(fig, 2, total, 'Anatomia do Pilar - Vista de Cima')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 3: VARIACOES POR TAMANHO ---
        print(f'  [Pg 3/{total}] Variacoes por Tamanho')
        fig = fig_a3('PG 3 - VARIACOES POR TAMANHO DO PILAR')
        configs = [
            ('PEQUENO 150x150mm', 150, 150),
            ('MEDIO 200x300mm', 200, 300),
            ('GRANDE 300x500mm', 300, 500),
            ('EM L (canto)', 0, 0),  # special
        ]
        for idx, (label, cw, ch) in enumerate(configs):
            row, col = idx // 2, idx % 2
            ax = fig.add_axes([0.05 + col * 0.48, 0.08 + (1 - row) * 0.44, 0.42, 0.40])
            setup_ax(ax, label)
            if cw > 0:
                sc = 0.8 if max(cw, ch) <= 150 else (0.7 if max(cw, ch) <= 300 else 0.55)
                draw_pilar_topo(ax, 0, 0, cw, ch, scale=sc, annotate_parts=False)
                span = max(cw, ch) * sc + 100
                ax.set_xlim(-span, span)
                ax.set_ylim(-span, span)
                # Dimension annotation
                ax.text(0, -ch * sc * 0.5 - 60, f'{cw}x{ch}mm',
                        ha='center', va='center', color=CYAN, fontsize=8,
                        fontweight='bold', zorder=10,
                        bbox=dict(facecolor=BG, alpha=0.8, pad=2, edgecolor='none'))
            else:
                # Pilar em L
                s = 0.5
                # Braço horizontal
                draw_concreto(ax, 0, 0, 300 * s, 150 * s)
                # Braço vertical
                draw_concreto(ax, 0, 0, 150 * s, 300 * s)
                # Paineis ao redor (simplified)
                pe = 22 * s
                for rect_args in [
                    (-pe, -pe, 300 * s + 2*pe, pe),
                    (-pe, 300 * s, 150 * s + 2*pe, pe),
                    (150 * s, 150 * s - pe, 150 * s + pe, pe),
                    (-pe, 0, pe, 300 * s),
                    (300 * s, -pe, pe, 150 * s + pe),
                    (150 * s, 150 * s, pe, 150 * s),
                ]:
                    draw_painel(ax, *rect_args, GRAY, hatch=False)
                ax.set_xlim(-50, 200)
                ax.set_ylim(-50, 200)
                ax.text(75, -30, 'Pilar L (canto)', ha='center', color=CYAN, fontsize=7,
                        fontweight='bold')
        fig.text(0.5, 0.04, 'Nota: A distribuicao dos paineis segue a largura do pilar',
                 ha='center', fontsize=9, color=FG, style='italic')
        rodape(fig, 3, total, 'Variacoes por Tamanho do Pilar')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 4: REPRESENTACAO DOS PAINEIS (elevacao lateral) ---
        print(f'  [Pg 4/{total}] Representacao dos Paineis (elevacao)')
        fig = fig_a3('PG 4 - PAINEIS EM ELEVACAO (LATERAL DO PILAR)')
        ax = fig.add_axes([0.05, 0.08, 0.55, 0.82])
        setup_ax(ax, 'Elevacao 1 Face - Paineis Empilhados')
        # Empilhar 5 paineis verticalmente
        panel_h_list = [120, 100, 80, 100, 60]
        y_base = 0
        for i, ph in enumerate(panel_h_list):
            draw_painel(ax, 0, y_base, 300, ph, GRAY, hatch=True)
            # Sarrafo na junta (exceto ultimo topo)
            if i < len(panel_h_list) - 1:
                draw_sarrafo(ax, -30, y_base + ph - 11, 360, 22, GOLD)
            # Cota
            ax.annotate('', xy=(320, y_base), xytext=(320, y_base + ph),
                        arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8), zorder=6)
            ax.text(350, y_base + ph/2, f'{ph}mm', color=CYAN, fontsize=6.5,
                    ha='left', va='center', zorder=10)
            y_base += ph
        # SARRAFO DE PRESSAO tracejado no topo e base
        ax.plot([0, 300], [0, 0], color=DGRAY, lw=1.5, linestyle='--', zorder=5)
        ax.plot([0, 300], [y_base, y_base], color=DGRAY, lw=1.5, linestyle='--', zorder=5)
        ax.text(150, -20, 'SARRAFO DE PRESSAO', ha='center', color=DGRAY, fontsize=6,
                fontweight='bold')
        ax.text(150, y_base + 15, 'SARRAFO DE PRESSAO', ha='center', color=DGRAY, fontsize=6,
                fontweight='bold')
        ax.set_xlim(-80, 420)
        ax.set_ylim(-60, y_base + 50)
        # Legenda e regras
        ax2 = fig.add_axes([0.62, 0.08, 0.35, 0.82])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'REGRAS - PAINEIS EM ELEVACAO:', [
            '* Paineis sempre verticais em pilares',
            '* Juntas nao devem coincidir faces opostas',
            '* SARRAFO DE PRESSAO topo e base',
            '* SARR_2.2x7 (dourado) nas juntas',
            '* Hachura ANSI31 diagonal (madeira)',
        ])
        tabela_dados(ax2, 0.05, 0.65, ['TIPO', 'W(mm)', 'H(mm)', 'Uso'],
                     [['PA-015x050', '150', '500', 'Pilar std'],
                      ['PA-022x100', '220', '1000', 'Pilar medio'],
                      ['PA-030x150', '300', '1500', 'Pilar grande']],
                     col_widths=[0.25, 0.15, 0.15, 0.25])
        draw_carimbo(fig, 'PAINEIS EM ELEVACAO', '', '1:10', '04', '30')
        rodape(fig, 4, total, 'Paineis em Elevacao Lateral')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 5: SARRAFOS: TIPOS E POSICIONAMENTO ---
        print(f'  [Pg 5/{total}] Sarrafos: Tipos e Posicionamento')
        fig = fig_a3('PG 5 - SARRAFOS: TIPOS E POSICIONAMENTO')
        # Subplot 1: secao transversal
        ax1 = fig.add_axes([0.05, 0.55, 0.28, 0.35])
        setup_ax(ax1, 'Secao Transversal SARR_2.2x7')
        draw_sarrafo(ax1, 0, 0, 22, 70, GOLD)
        ax1.annotate('', xy=(0, -5), xytext=(22, -5),
                     arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8))
        ax1.text(11, -12, '22mm', ha='center', color=CYAN, fontsize=7)
        ax1.annotate('', xy=(-5, 0), xytext=(-5, 70),
                     arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8))
        ax1.text(-15, 35, '70mm', ha='center', va='center', color=CYAN, fontsize=7, rotation=90)
        ax1.set_xlim(-25, 50); ax1.set_ylim(-20, 85)

        # Subplot 2: vista topo com sarrafos entre paineis
        ax2 = fig.add_axes([0.37, 0.55, 0.28, 0.35])
        setup_ax(ax2, 'Vista Topo - Sarrafos entre Paineis')
        for i in range(4):
            x0 = i * 80
            draw_painel(ax2, x0, 0, 60, 100, GRAY, hatch=False)
            if i < 3:
                draw_sarrafo(ax2, x0 + 60, 0, 20, 100, GOLD)
        ax2.set_xlim(-20, 340); ax2.set_ylim(-20, 120)

        # Subplot 3: variantes
        ax3 = fig.add_axes([0.68, 0.55, 0.28, 0.35])
        setup_ax(ax3, 'Variantes de Sarrafo')
        sarrafos_v = [
            ('SARR_2.2x7', 22, 70, GOLD),
            ('SARR_3.5x7', 35, 70, GRAY),
            ('SARR_7x7', 70, 70, GOLD),
            ('SARR_2.2x10', 22, 100, '#7fff00'),
            ('SARR_2.2x15', 22, 150, GRAY),
        ]
        y = 0
        for name, w, h, c in sarrafos_v:
            # Scale down for display
            sw, sh = w * 0.5, h * 0.5
            draw_sarrafo(ax3, 0, y, sw, sh, c)
            ax3.text(sw + 10, y + sh / 2, f'{name} ({w}x{h}mm)', color=FG, fontsize=6.5,
                     va='center')
            y += sh + 10
        ax3.set_xlim(-10, 180); ax3.set_ylim(-10, y + 10)

        # Regras
        ax_r = fig.add_axes([0.05, 0.08, 0.9, 0.38])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.9, 'REGRAS - SARRAFOS:', [
            '* SARR_2.2x7 e o padrao em juntas de 22mm',
            '* SARR_7x7 em quinas de pilar grande',
            '* SARR_2.2x10 para viga com pe direito > 3m',
            '* Todos posicionados nas juntas entre paineis',
            '* Layer: SARR_2.2x7 (ACI 40, dourado)',
        ])
        tabela_regras(ax_r, 0.05, 0.42, 'IDENTIFICACAO NO DXF:', [
            '* Layer SARR_2.2x7 -> sarrafo em junta',
            '* Layer SARR_7x7 -> quina de pilar grande',
            '* Layer SARRAFO DE PRESSAO -> contorno perimet.',
            '* ACI=40 (dourado) -> qualquer sarrafo',
            '* LWPOLYLINE fechada -> outline do painel',
        ])
        tabela_regras(ax_r, 0.05, 0.20, 'CASO ESPECIAL - SARR 2.2x7:', [
            '* Nomenclatura: 2.2 = 22mm esp painel',
            '* 7 = 70mm largura do sarrafo',
            '* Material: tira de compensado resinado',
            '* NAO e sarrafo bruto de madeira macica',
        ])
        rodape(fig, 5, total, 'Sarrafos - Tipos e Posicionamento')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 6: GRADES ---
        print(f'  [Pg 6/{total}] Grades: O que sao')
        fig = fig_a3('PG 6 - GRADES: O QUE SAO E COMO DESENHAR')
        # Coluna 1: Sarrafeado
        ax1 = fig.add_axes([0.05, 0.35, 0.42, 0.55])
        setup_ax(ax1, 'SARRAFEADO (paineis individuais)')
        for i in range(3):
            draw_painel(ax1, i * 85, 0, 65, 200, GRAY, hatch=True)
            if i < 2:
                draw_sarrafo(ax1, i * 85 + 65, 0, 20, 200, GOLD)
        ax1.set_xlim(-20, 280); ax1.set_ylim(-30, 240)
        # Coluna 2: Grade
        ax2 = fig.add_axes([0.52, 0.35, 0.42, 0.55])
        setup_ax(ax2, 'GRADE (painel metalico pre-fabricado)')
        draw_grade(ax2, 0, 0, 255, 200, GRAY, grid_spacing=50)
        ax2.set_xlim(-20, 280); ax2.set_ylim(-30, 240)
        # Regras
        ax_r = fig.add_axes([0.05, 0.08, 0.9, 0.22])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.9, 'REGRAS - SARRAFEADO vs GRADE:', [
            '* SARRAFEADO: paineis de madeira individuais + sarrafos nas juntas',
            '* GRADE: painel metalico pre-fabricado, sem juntas visiveis',
            '* Quando usar GRADE: pilares circulares, curvas, esp. < 15cm',
            '* Identificacao DXF: LWPOLYLINE + hachura SOLID interna + layer "Paineis"',
            '* Grid interno: linhas finas espacadas 50x50mm (lw=0.3, cor #5b5b5b)',
        ])
        rodape(fig, 6, total, 'Grades - Sarrafeado vs Grade')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 7: BLOCOS: PONTALETE, MEIO PONTALETE, CHAPA ---
        print(f'  [Pg 7/{total}] Blocos: Pontalete, Chapa')
        fig = fig_a3('PG 7 - BLOCOS: PONTALETE, MEIO PONTALETE, CHAPA, PERFIL METALICO')
        # 4 subplots (compactados para dar espaco ao zoom)
        ax1 = fig.add_axes([0.05, 0.58, 0.20, 0.32])
        setup_ax(ax1, 'PONTALETE 7x7cm (escala 2x)')
        draw_pontalete(ax1, 0, 0, size=14)
        ax1.set_xlim(-20, 20); ax1.set_ylim(-20, 20)
        ax1.text(0, -16, '14x14cm (escala 2x)', ha='center', color=CYAN, fontsize=7, fontweight='bold')

        ax2 = fig.add_axes([0.28, 0.58, 0.20, 0.32])
        setup_ax(ax2, 'MEIO PONTALETE 3.5x7cm')
        hs = 7
        r = mpatches.Rectangle((-3.5/2, -hs/2), 3.5, hs, lw=1.0,
                                edgecolor=WHITE, facecolor=BG, zorder=4)
        ax2.add_patch(r)
        arc = Arc((-3.5/2, -hs/2), 3.5 * 0.8, hs * 0.8, angle=0,
                  theta1=0, theta2=90, color=WHITE, lw=0.8, zorder=5)
        ax2.add_patch(arc)
        ax2.set_xlim(-10, 10); ax2.set_ylim(-10, 10)
        ax2.text(0, -8, '7x14cm (escala 2x)', ha='center', color=CYAN, fontsize=7,
                 fontweight='bold')

        ax3 = fig.add_axes([0.51, 0.58, 0.20, 0.32])
        setup_ax(ax3, 'CHAPA 4x176mm')
        draw_chapa(ax3, -2, -88, 176, RED, w=4)
        ax3.set_xlim(-20, 20); ax3.set_ylim(-100, 100)
        ax3.text(0, -95, '4x176mm', ha='center', color=CYAN, fontsize=7, fontweight='bold')
        ax3.text(15, 0, 'Ancoragem\nmetalica', ha='center', color=RED, fontsize=6)

        ax4 = fig.add_axes([0.74, 0.58, 0.22, 0.32])
        setup_ax(ax4, 'Perfil Met. 15x248mm')
        r = mpatches.Rectangle((-7.5, -124), 15, 248, lw=0.8,
                                edgecolor=LGRAY, facecolor=LGRAY, alpha=0.5, zorder=3)
        ax4.add_patch(r)
        ax4.set_xlim(-25, 25); ax4.set_ylim(-140, 140)
        ax4.text(0, -132, '15x248mm', ha='center', color=CYAN, fontsize=7, fontweight='bold')

        # --- Subplot: ZOOM DETALHE CANTO ---
        ax_zoom = fig.add_axes([0.62, 0.08, 0.35, 0.42])
        setup_ax(ax_zoom, 'ZOOM: Detalhe Canto (escala 5x)')
        # Canto de pilar 200x300 em escala 5x (tudo x5)
        s5 = 5.0
        pe5 = 22 * s5   # 110
        cw5, ch5 = 80 * s5, 60 * s5  # fracao do pilar
        # Concreto (parcial)
        draw_concreto(ax_zoom, 0, 0, cw5, ch5)
        # Painel lateral (direito)
        draw_painel(ax_zoom, cw5, 0, pe5, ch5, GRAY, hatch=True)
        # Painel inferior
        draw_painel(ax_zoom, 0, -pe5, cw5 + pe5, pe5, GRAY, hatch=True)
        # CHAPA na quina
        draw_chapa(ax_zoom, cw5 + pe5, -pe5, pe5 + ch5, RED, w=4 * s5)
        # Perfil Metalico fora da CHAPA
        r_perf = mpatches.Rectangle((cw5 + pe5 + 4*s5, -pe5), 15*s5, pe5+ch5,
                                     lw=0.8, edgecolor=LGRAY, facecolor=LGRAY, alpha=0.4, zorder=3)
        ax_zoom.add_patch(r_perf)
        # Pontalete no canto
        draw_pontalete(ax_zoom, cw5 + pe5 + 4*s5 + 15*s5 + 7*s5,
                       -pe5 - 7*s5, 14*s5)
        # Cotas no zoom
        draw_cota(ax_zoom, cw5, 0, cw5 + pe5, 0, -pe5 * 0.6, '22mm (painel)', CYAN, orientation='h')
        draw_cota(ax_zoom, cw5 + pe5, 0, cw5 + pe5 + 4*s5, 0, -pe5 * 1.1, '4mm (chapa)', RED, orientation='h')
        # Anotacoes
        annotate_arrow(ax_zoom, 'CHAPA (4mm)', (cw5 + pe5 + 2*s5, ch5/2),
                       (cw5 + pe5 + 4*s5 + 80, ch5*0.8), RED)
        annotate_arrow(ax_zoom, 'Perfil Met.', (cw5 + pe5 + 4*s5 + 7*s5, ch5/2),
                       (cw5 + pe5 + 4*s5 + 80, ch5*0.4), LGRAY)
        annotate_arrow(ax_zoom, 'Concreto', (cw5/2, ch5/2), (cw5*0.3, ch5*0.8), DGRAY)
        ax_zoom.set_xlim(-30, cw5 + pe5 + 4*s5 + 15*s5 + 14*s5 + 40)
        ax_zoom.set_ylim(-pe5 - 14*s5 - 20, ch5 + 40)

        # Regras
        ax_r = fig.add_axes([0.05, 0.08, 0.55, 0.42])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.9, 'REGRAS DE POSICIONAMENTO:', [
            '* PONTALETE: quadrado 7x7cm (70x70mm) com arcos (escala 2x no DXF)',
            '* MEIO PONTALETE: 3.5x7cm (35x70mm) - meia largura',
            '* CHAPA: W=4mm, H=176mm, sempre vermelho, nas quinas do pilar',
            '* Perfil Met.: W=12-20mm, H=248mm, fora da CHAPA',
            '* Pontaletes no perimetro externo a cada painel',
        ])
        tabela_dados(ax_r, 0.05, 0.45, ['Bloco', 'W(mm)', 'H(mm)', 'Layer', 'Cor'],
                     [['PONTALETE', '70', '70', 'PONTALETE', 'branco'],
                      ['MEIO PONT.', '35', '70', 'MEIO_PONT', 'cinza'],
                      ['CHAPA', '4', '176', 'CHAPA', 'vermelho'],
                      ['Perfil Met.', '15', '248', 'Perfil Met.', 'cinza claro']],
                     col_widths=[0.18, 0.10, 0.10, 0.20, 0.18])
        rodape(fig, 7, total, 'Blocos - Pontalete, Chapa, Perfil')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 8: VISAO CORTE TRANSVERSAL DO PILAR ---
        print(f'  [Pg 8/{total}] Corte Transversal do Pilar')
        fig = fig_a3('PG 8 - CORTE TRANSVERSAL DO PILAR')
        ax = fig.add_axes([0.05, 0.15, 0.50, 0.75])
        setup_ax(ax, 'Corte Pilar 200x300mm')
        s = 1.0
        cw, ch = 200, 300
        pe = 22
        # Concreto
        draw_concreto(ax, -cw/2, -ch/2, cw, ch)
        # Paineis laterais
        draw_painel(ax, -cw/2 - pe, -ch/2, pe, ch, GRAY, hatch=True)
        draw_painel(ax, cw/2, -ch/2, pe, ch, GRAY, hatch=True)
        # Sarrafo externo
        draw_sarrafo(ax, -cw/2 - pe - 22, -35, 22, 70, GOLD)
        draw_sarrafo(ax, cw/2 + pe, -35, 22, 70, GOLD)
        # Chapas nas quinas
        draw_chapa(ax, -cw/2 - pe - 4, -ch/2, ch, RED, w=4)
        draw_chapa(ax, cw/2 + pe, -ch/2, ch, RED, w=4)
        # Barra de ancoragem (horizontal)
        ax.plot([-cw/2 - pe - 50, cw/2 + pe + 50], [0, 0],
                color=DGRAY, lw=1.5, linestyle='-.', zorder=5)
        ax.text(0, -10, 'BARRA ANCORAGEM', ha='center', color=DGRAY, fontsize=6, zorder=10)
        # Tensor vertical
        ax.plot([0, 0], [-ch/2 - pe - 30, ch/2 + pe + 30],
                color=GREEN, lw=1.5, linestyle='--', zorder=5)
        ax.text(10, ch/2 + pe + 25, 'TENSOR', ha='left', color=GREEN, fontsize=6, zorder=10)
        # Pontaletes
        draw_pontalete(ax, -cw/2 - pe - 40, -ch/2 - 20, 14)
        draw_pontalete(ax, cw/2 + pe + 40, -ch/2 - 20, 14)
        # Cotas ABNT no corte
        draw_cota(ax, -100, 170, 100, 170, 50, '200mm', CYAN, orientation='h')   # largura
        draw_cota(ax, -220, -150, -220, 150, -30, '300mm', CYAN, orientation='v')  # altura
        draw_cota(ax, 100, -200, 122, -200, -30, '22mm', CYAN, orientation='h')   # painel
        ax.set_xlim(-260, 240); ax.set_ylim(-250, 240)
        # Cotas
        annotate_arrow(ax, f'{cw}mm', (0, ch/2 + 5), (0, ch/2 + 60), CYAN)
        annotate_arrow(ax, f'{pe}mm painel', (-cw/2 - pe/2, -ch/2 - 30),
                       (-cw/2 - 80, -ch/2 - 80), CYAN)
        # Regras
        ax2 = fig.add_axes([0.57, 0.15, 0.40, 0.30])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'REGRAS - CORTE TRANSVERSAL:', [
            '* Barra ancoragem passa pelo concreto',
            '* Tensor segura as 2 laterais',
            '* CHAPA nas quinas (vermelho)',
            '* Sarrafos externos (dourado)',
            '* Pontaletes nos cantos',
        ])
        # Isometrica do pilar
        ax_iso = fig.add_axes([0.55, 0.30, 0.43, 0.60])
        ax_iso.set_facecolor('#0d1530'); ax_iso.set_aspect('equal'); ax_iso.axis('off')
        # Borda visual para delimitar a area isometrica
        for spine_pos in [('bottom', 0), ('top', 1), ('left', 0), ('right', 1)]:
            pass  # axis off handles it
        border_rect = mpatches.FancyBboxPatch((0.01, 0.01), 0.98, 0.98,
                                              transform=ax_iso.transAxes,
                                              boxstyle='round,pad=0',
                                              facecolor='none', edgecolor='#334466',
                                              lw=1.0, clip_on=False, zorder=0)
        ax_iso.add_patch(border_rect)
        draw_pilar_isometrico(ax_iso, 200, 300, ph=300, scale=0.32)
        ax_iso.set_xlim(-90, 200)
        ax_iso.set_ylim(-40, 230)
        ax_iso.set_title('Vista Isometrica Pilar 200x300mm', color=ACCENT,
                         fontsize=8, fontweight='bold', pad=4, fontfamily='monospace')
        draw_scale_bar(ax_iso)
        draw_carimbo(fig, 'CORTE TRANSVERSAL', '', '1:5', '08', '30')
        rodape(fig, 8, total, 'Corte Transversal do Pilar')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 9: DECISION TREE DO ROBO (PILARES) ---
        print(f'  [Pg 9/{total}] Decision Tree do Robo')
        fig = fig_a3('PG 9 - ARVORE DE DECISAO: ROBO DE PILARES')
        ax = fig.add_axes([0.03, 0.08, 0.96, 0.82])
        ax.set_facecolor(BG); ax.axis('off')
        ax.set_xlim(0, 1000); ax.set_ylim(0, 600)

        # === FLUXO 1: Tipo de painel (sarrafeado vs grade) ===
        # Input box
        draw_decision_box(ax, 20, 520, 140, 40, 'INPUT DXF:\nlayer Paineis', color='#0d2040')
        draw_flow_arrow(ax, 160, 540, 210, 540)
        # Decisao
        draw_decision_diamond(ax, 280, 540, 140, 50, 'SARR_2.2x7\npresente?')
        draw_flow_arrow(ax, 350, 540, 400, 540, 'SIM')
        draw_decision_box(ax, 400, 520, 130, 40, 'tipo_painel\n= SARRAFEADO', color='#1a3a1a', text_color=GREEN)
        draw_flow_arrow(ax, 280, 515, 280, 470, 'NAO')
        draw_decision_box(ax, 210, 450, 140, 40, 'tipo_painel\n= GRADE', color='#1a2a4a', text_color='#5b9bd5')

        # === FLUXO 2: Tipo de sarrafo por secao ===
        draw_decision_box(ax, 20, 380, 140, 40, 'INPUT:\nsecao_x, secao_y', color='#0d2040')
        draw_flow_arrow(ax, 160, 400, 210, 400)
        draw_decision_diamond(ax, 280, 400, 140, 50, 'max(X,Y)\n< 200mm?')
        draw_flow_arrow(ax, 350, 400, 400, 420, 'SIM')
        draw_decision_box(ax, 400, 405, 130, 40, 'sarrafo\n= SARR_2.2x7', color='#2a2a00', text_color=GOLD)
        draw_flow_arrow(ax, 280, 375, 280, 330, 'NAO')
        draw_decision_diamond(ax, 280, 310, 140, 50, 'max(X,Y)\n< 400mm?')
        draw_flow_arrow(ax, 350, 310, 400, 325, 'SIM')
        draw_decision_box(ax, 400, 310, 130, 40, 'sarrafo\n= SARR_3.5x7', color='#2a2a00', text_color=GOLD)
        draw_flow_arrow(ax, 280, 285, 280, 250, 'NAO')
        draw_decision_box(ax, 210, 230, 140, 40, 'sarrafo\n= SARR_7x7', color='#3a2a00', text_color=GOLD)

        # === FLUXO 3: Sarrafo por PD ===
        draw_decision_box(ax, 580, 520, 140, 40, 'INPUT:\nPD (m)', color='#0d2040')
        draw_flow_arrow(ax, 720, 540, 770, 540)
        draw_decision_diamond(ax, 840, 540, 130, 50, 'PD > 3.0m?')
        draw_flow_arrow(ax, 905, 540, 940, 555, 'SIM')
        draw_decision_box(ax, 940, 540, 50, 40, 'SARR\n2.2x10', color='#2a2a00', text_color=GOLD, fontsize=6)
        draw_flow_arrow(ax, 840, 515, 840, 470, 'NAO')
        draw_decision_box(ax, 775, 450, 130, 40, 'SARR\n2.2x7 (padrao)', color='#2a2a00', text_color=GOLD)

        # === FLUXO 4: Tipo de pilar por secao ===
        draw_decision_box(ax, 580, 380, 140, 40, 'INPUT:\nsecao concreto', color='#0d2040')
        draw_flow_arrow(ax, 720, 400, 770, 400)
        draw_decision_diamond(ax, 840, 400, 130, 50, 'max(X,Y)\n< 200mm?')
        draw_flow_arrow(ax, 905, 400, 940, 415, 'SIM')
        draw_decision_box(ax, 940, 400, 50, 40, 'TIPO\nPEQUENO', color='#1a4a1a', text_color=GREEN, fontsize=6)
        draw_flow_arrow(ax, 840, 375, 840, 330, 'NAO')
        draw_decision_diamond(ax, 840, 310, 130, 50, 'max(X,Y)\n< 400mm?')
        draw_flow_arrow(ax, 905, 310, 940, 325, 'SIM')
        draw_decision_box(ax, 940, 310, 50, 40, 'TIPO\nMEDIO', color='#1a3a4a', text_color=CYAN, fontsize=6)
        draw_flow_arrow(ax, 840, 285, 840, 250, 'NAO')
        draw_decision_box(ax, 775, 230, 130, 40, 'TIPO\nGRANDE', color='#3a1a1a', text_color=RED)

        # Labels dos fluxos
        ax.text(280, 590, 'FLUXO 1: Tipo de Painel', color=ACCENT, fontsize=8,
                fontweight='bold', ha='center', zorder=10)
        ax.text(280, 440, 'FLUXO 2: Tipo de Sarrafo', color=ACCENT, fontsize=8,
                fontweight='bold', ha='center', zorder=10)
        ax.text(840, 590, 'FLUXO 3: Sarrafo por PD', color=ACCENT, fontsize=8,
                fontweight='bold', ha='center', zorder=10)
        ax.text(840, 440, 'FLUXO 4: Tipo de Pilar', color=ACCENT, fontsize=8,
                fontweight='bold', ha='center', zorder=10)

        # Legenda
        ax.text(500, 190, 'LEGENDA:', color=ACCENT, fontsize=8, fontweight='bold', ha='center', zorder=10)
        ax.text(390, 165, 'Azul escuro = INPUT', color='#5599cc', fontsize=7, zorder=10)
        ax.text(390, 145, 'Losango dourado = CONDICAO', color=GOLD, fontsize=7, zorder=10)
        ax.text(570, 165, 'Verde = resultado SARRAFEADO', color=GREEN, fontsize=7, zorder=10)
        ax.text(570, 145, 'Azul = resultado GRADE', color='#5b9bd5', fontsize=7, zorder=10)
        ax.text(730, 165, 'Dourado = tipo SARRAFO', color=GOLD, fontsize=7, zorder=10)

        # Nomenclatura (mantida como referencia lateral)
        ax.text(80, 100, 'NOMENCLATURA DXF:', color=ACCENT, fontsize=8, fontweight='bold', zorder=10)
        ax.text(80, 78, 'P{n}.{face}  |  PD: {m}  |  NS: {z_base}  |  NC: {z_topo}', color=CYAN,
                fontsize=7.5, fontfamily='monospace', zorder=10,
                bbox=dict(facecolor='#050510', edgecolor='#335577', pad=5, lw=0.8))
        ax.text(80, 52, 'Faces: A = principal (maior dim) | B,C,D = secundarias', color=FG,
                fontsize=7, fontfamily='monospace', zorder=10)

        # Tolerancias - tabela na parte inferior da Pg 9
        tol_x = 20
        tol_data = [
            ('FOLGA FORMA-CONCRETO', '2-3mm', 'Entre painel e concreto para desmoldagem'),
            ('SOBRA MINIMA PAINEL', '50mm', 'Minimo para painel cortado por face'),
            ('OFFSET JUNTAS OPOSTAS', '100mm', 'Juntas de faces opostas nao coincidem'),
            ('SARRAFO EM JUNTA', 'OBRIG.', 'Todo painel < 22mm de largura recebe sarrafo'),
            ('PONTALETE ESPAC. MAX', '600mm', 'Distancia maxima entre pontaletes'),
        ]
        ax.text(tol_x, 48, 'TOLERANCIAS E LIMITES:', color=ACCENT, fontsize=8, fontweight='bold', zorder=10)
        headers_t = ['Parametro', 'Valor', 'Regra']
        widths_t = [220, 80, 380]
        hx = tol_x + 5
        for j, (h, w) in enumerate(zip(headers_t, widths_t)):
            ax.text(hx, 38, h, color=ACCENT, fontsize=6.5, fontweight='bold', zorder=10)
            hx += w
        for i, (param, val, regra) in enumerate(tol_data):
            hx = tol_x + 5
            row_y = 28 - i * 8
            for txt, w in zip([param, val, regra], widths_t):
                ax.text(hx, row_y, txt, color=FG if i%2==0 else LGRAY, fontsize=6, zorder=10)
                hx += w

        rodape(fig, 9, total, 'Decision Tree - Robo de Pilares')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 10: CAMPOS DO ROBO + JSON SCHEMA ---
        print(f'  [Pg 10/{total}] Campos do Robo + JSON Schema')
        fig = fig_a3('PG 10 - CAMPOS DO ROBO: PARAMETROS COMPLETOS')
        ax = fig.add_axes([0.02, 0.08, 0.48, 0.82])
        ax.set_facecolor(BG); ax.axis('off')
        params = [
            ('pilar_id', 'str', 'P1', 'Identificador do pilar'),
            ('secao_x', 'int (mm)', '200', 'Dimensao X do concreto'),
            ('secao_y', 'int (mm)', '300', 'Dimensao Y do concreto'),
            ('altura (PD)', 'float (m)', '3.24', 'Pe direito = altura da forma'),
            ('nivel_saida', 'float', '778.92', 'Cota Z base (mm)'),
            ('nivel_chegada', 'float', '1002.92', 'Cota Z topo (mm)'),
            ('tipo_painel', 'str', 'PA-022x100', 'Codigo do painel'),
            ('esp_painel', 'int (mm)', '21', 'Espessura: 21mm(plastico) / 22mm(pinus)'),
            ('sarrafo_tipo', 'str', 'SARR_2.2x7', 'Tipo de sarrafo nas juntas'),
            ('com_grade', 'bool', 'False', 'Usar grade metalica?'),
            ('chapa_cor', 'ACI', '1 (vermelho)', 'Cor da chapa de ancoragem'),
            ('layer_concreto', 'str', 'CONCRETO', 'Layer do contorno concreto'),
            ('layer_paineis', 'str', 'Paineis', 'Layer dos paineis'),
        ]
        tabela_dados(ax, 0.05, 0.95, ['Campo', 'Tipo', 'Exemplo', 'Descricao'],
                     [[p[0], p[1], p[2], p[3]] for p in params],
                     col_widths=[0.20, 0.15, 0.18, 0.40])
        # Valores tipicos por tipo de pilar
        ax.text(0.05, 0.55, 'VALORES TIPICOS POR TIPO DE PILAR:', color=ACCENT, fontsize=8,
                fontweight='bold', fontfamily='monospace', transform=ax.transAxes, zorder=10)
        tabela_dados(ax, 0.05, 0.52,
            ['Tipo', 'Secao', 'Sarrafo junta', 'Painel', 'Pont.'],
            [['PEQUENO', '< 200mm', 'SARR_2.2x7', 'PA-022x100', '2/face'],
             ['MEDIO',   '200-400mm', 'SARR_2.2x7 ou 3.5x7', 'PA-022x100', '4/face'],
             ['GRANDE',  '> 400mm', 'SARR_7x7 nas quinas', 'PA-022x100', '6+/face']],
            col_widths=[0.13, 0.14, 0.24, 0.14, 0.10])
        ax.text(0.05, 0.37, 'REGRAS RAPIDAS:', color=ACCENT, fontsize=8,
                fontweight='bold', fontfamily='monospace', transform=ax.transAxes, zorder=10)
        quick_rules = [
            '* chapa_cor ACI=1 (vermelho) em TODAS as quinas — sempre',
            '* esp_painel: 21mm=plastico (alta res.) / 22mm=pinus (padrao)',
            '* com_grade=True quando dim_face > 400mm ou estrutural',
            '* nivel_saida e nivel_chegada: coordenadas Z absolutas (mm)',
            '* faces lista: ordem anti-horaria, comeca pela Face A principal',
            '* pilar_id: nomenclatura do projeto DXF (ex: P1, P2, P-A3)',
        ]
        for i, q in enumerate(quick_rules):
            ax.text(0.05, 0.325 - i * 0.050, q, color=FG, fontsize=6.5,
                    fontfamily='monospace', transform=ax.transAxes, zorder=10)
        # JSON schema visual (metade direita)
        ax10b = fig.add_axes([0.52, 0.08, 0.46, 0.82])
        ax10b.set_facecolor(BG); ax10b.axis('off')
        draw_json_schema(ax10b, 0.02, 0.97, 'pilar.json (schema)',
            [
                ('pilar_id',     '"str"',      '"P1"',          True),
                ('secao_x',      'int (mm)',    '200',           True),
                ('secao_y',      'int (mm)',    '300',           True),
                ('altura_pd',    'float (m)',   '3.24',          True),
                ('nivel_saida',  'float',       '778.92',        True),
                ('nivel_chegada','float',       '1002.92',       True),
                ('tipo_painel',  '"sarr"|"grade"', '"sarr"',     True),
                ('faces',        'list[str]',   '["P1.A","P1.B","P1.C","P1.D"]', True),
                ('esp_painel',   '21|22|18',    '21',            True),
                ('sarrafo_tipo', '"str"',       '"SARR_2.2x7"', True),
                ('com_grade',    'bool',        'false',         False),
                ('chapa_aci',    'int',         '1',             False),
                ('layer_concreto','str',        '"CONCRETO"',    False),
                ('ordem_montagem','list[int]',  '[1,2,3,4]',     False),
            ], w=0.96)
        rodape(fig, 10, total, 'Campos do Robo - Parametros Pilares')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 11-15: EXEMPLOS REAIS DXF ANOTADOS ---
        dxf_pages_pl = [
            (11, PL_1, PL_ZOOM_P1P2, 'Pilar P1 e P2 - ALIMONTI', [
                ('CHAPA (ACI=1)', (4600, 12400), (4300, 12600), RED),
                ('SARR_2.2x7 = 22x70mm', (4700, 12350), (4400, 12200), GOLD),
                ('Painel W=22mm', (4800, 12300), (5100, 12550), GRAY),
                ('Perfil Met. 15mm', (4550, 12500), (4250, 12350), LGRAY),
            ]),
            (12, PL_1, (4800, 12200, 5600, 12700), 'Pilar P3-P4 zona central - ALIMONTI', [
                ('Concreto', (5100, 12400), (5350, 12550), DGRAY),
                ('Pontalete', (5000, 12300), (4800, 12200), WHITE),
            ]),
            (13, PL_2, None, 'Vista completa PL - GWT', []),
            (14, PL_3, None, 'Vista completa PL - LEAF', []),
            (15, PL_1, PL_ZOOM_FULL, 'Vista panoramica PL - ALIMONTI', []),
        ]
        for pg, dxf_path, crop, title, annots in dxf_pages_pl:
            print(f'  [Pg {pg}/{total}] Exemplo Real PL - {title}')
            fig = fig_a3(f'PG {pg} - EXEMPLO REAL: {title}')
            ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
            render_dxf_zona(ax, dxf_path, crop=crop, title=title)
            for (txt, xy_a, xy_t, c) in annots:
                annotate_arrow(ax, txt, xy_a, xy_t, c)
            rodape(fig, pg, total, f'Exemplo Real - {title}')
            pdf.savefig(fig); plt.close(fig)

        # --- Pg 16-20: CATALOGO DE VARIACOES ---
        variations = [
            (16, [('Simples (2 faces sarr.)', 200, 200, False),
                  ('Simples (4 faces)', 200, 300, False),
                  ('2 sarr. + 2 grade', 150, 200, True),
                  ('CHAPA extra quinas int.', 250, 400, False)]),
            (17, [('Pilar canto L', 0, 0, False),
                  ('Pilar quadrado 150x150', 150, 150, False),
                  ('Pilar retangular 200x400', 200, 400, False),
                  ('Pilar largo 300x600', 300, 600, False)]),
            (18, [('Pilar com grade total', 150, 150, True),
                  ('Pilar grande 400x400', 400, 400, False),
                  ('Pilar estreito 120x300', 120, 300, False),
                  ('Pilar medio 200x250', 200, 250, False)]),
            (19, [('Pilar 150x200 padrao', 150, 200, False),
                  ('Pilar 200x200 quadrado', 200, 200, False),
                  ('Pilar 250x350', 250, 350, False),
                  ('Pilar 300x300', 300, 300, False)]),
            (20, [('Pilar 350x500', 350, 500, False),
                  ('Pilar 400x600', 400, 600, False),
                  ('Pilar 200x500', 200, 500, False),
                  ('Pilar 150x400', 150, 400, False)]),
        ]
        for pg, configs in variations:
            print(f'  [Pg {pg}/{total}] Catalogo de Variacoes')
            fig = fig_a3(f'PG {pg} - CATALOGO DE VARIACOES (PILARES)')
            for idx, (label, cw, ch, grade) in enumerate(configs):
                row, col = idx // 2, idx % 2
                ax = fig.add_axes([0.05 + col * 0.48, 0.08 + (1 - row) * 0.44, 0.42, 0.40])
                setup_ax(ax, label)
                if cw > 0:
                    sc = min(0.4, 80 / max(cw, ch))
                    draw_pilar_topo(ax, 0, 0, cw, ch, scale=sc, annotate_parts=False)
                    span = max(cw, ch) * sc + 60
                    ax.set_xlim(-span, span); ax.set_ylim(-span, span)
                    ax.text(0, -span + 10, f'{cw}x{ch}mm', ha='center', color=CYAN,
                            fontsize=7, fontweight='bold')
                else:
                    # Pilar L
                    draw_concreto(ax, 0, 0, 60, 30)
                    draw_concreto(ax, 0, 0, 30, 60)
                    ax.set_xlim(-20, 80); ax.set_ylim(-20, 80)
                    ax.text(30, -15, 'L shape', ha='center', color=CYAN, fontsize=7)
            rodape(fig, pg, total, 'Catalogo de Variacoes')
            pdf.savefig(fig); plt.close(fig)

        # --- Pg 21-25: REGRAS DE DISTRIBUICAO ---
        rules_pages = [
            (21, 'Regra de inicio/fim de linha de paineis', [
                '* Paineis iniciam na quina inferior esquerda',
                '* Direcao de crescimento: anti-horario',
                '* Ultimo painel pode ser cortado para ajustar',
                '* Sobra minima = 5cm (abaixo disso, ajustar painel anterior)',
                '* Face A = lateral principal (maior comprimento)',
            ]),
            (22, 'Regra de juntas (faces opostas)', [
                '* Juntas de paineis NAO podem coincidir entre faces opostas',
                '* Offset minimo entre juntas: 10cm',
                '* Face A e C = opostas | Face B e D = opostas',
                '* Se pilar quadrado: juntas alternadas a cada face',
                '* Sarrafo sempre na junta entre paineis',
                '* Quina: painel FACE A sobrepoe painel FACE B (anti-horario sempre)',
                '* Painel maior sempre externo na quina',
            ]),
            (23, 'Regra de pontaletes', [
                '* Pontalete a cada painel ou a cada 2 paineis',
                '* Pilares < 200mm: 1 pontalete por face',
                '* Pilares 200-400mm: 2 pontaletes por face',
                '* Pilares > 400mm: 3+ pontaletes por face',
                '* Sempre nos cantos do pilar',
            ]),
            (24, 'Regra de sarrafos por tamanho', [
                '* Pilar < 200mm: SARR_2.2x7 (padrao)',
                '* Pilar 200-400mm: SARR_2.2x7 ou SARR_3.5x7',
                '* Pilar > 400mm: SARR_7x7 nas quinas',
                '* SARR_2.2x10 para pe direito > 3m',
                '* Sarrafo de Pressao perimetral: sempre presente',
            ]),
            (25, 'Tabela de padroes por obra', [
                'ALIMONTI: secoes 150x200 a 300x500, SARR_2.2x7, PA-022',
                'GWT:      secoes 200x200 a 400x600, SARR_2.2x7, PA-022',
                'LEAF:     secoes 150x200 a 250x400, SARR_2.2x7, PA-022',
                '',
                '* Espessura padrao: 22mm em todas as obras',
                '* Chapa: ACI=1 (vermelho) em todas',
            ]),
        ]
        for pg, title, rules in rules_pages:
            print(f'  [Pg {pg}/{total}] Regras Distribuicao')
            fig = fig_a3(f'PG {pg} - {title.upper()}')
            ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
            ax.set_facecolor(BG); ax.axis('off')
            tabela_regras(ax, 0.05, 0.90, title.upper(), rules)
            # Desenho ilustrativo
            if pg == 21:
                ax2 = fig.add_axes([0.55, 0.15, 0.40, 0.65])
                setup_ax(ax2, 'Inicio/Fim do Painel')
                draw_pilar_topo(ax2, 0, 0, 200, 300, scale=0.5, annotate_parts=False)
                ax2.annotate('INICIO', xy=(-70, -100), fontsize=8, color=GREEN,
                             fontweight='bold')
                ax2.annotate('FIM', xy=(60, -100), fontsize=8, color=RED,
                             fontweight='bold')
                ax2.set_xlim(-140, 140); ax2.set_ylim(-140, 140)
                # Formula de quantidade de paineis
                ax.text(0.05, 0.55, 'FORMULA DE DISTRIBUICAO:', color=ACCENT, fontsize=8,
                        fontweight='bold', transform=ax.transAxes, zorder=10)
                formula_lines = [
                    'n_paineis = ceil(dim_face / larg_painel)',
                    'sobra = dim_face - (n_paineis - 1) x larg_painel',
                    '',
                    'SE sobra < 50mm:',
                    '  -> n_paineis -= 1',
                    '  -> ultimo painel = larg_painel + sobra / 2 (ajustado)',
                    'SE sobra >= 50mm:',
                    '  -> adicionar painel cortado (sobra mm)',
                    '',
                    'Exemplo: face=800mm, painel=220mm',
                    '  n = ceil(800/220) = 4 paineis',
                    '  sobra = 800 - 3x220 = 140mm >= 50 -> ok',
                    '  distribuicao: 220 | 220 | 220 | 140mm',
                ]
                for i, line in enumerate(formula_lines):
                    c = CYAN if '->' in line or 'n_paineis' in line or 'sobra' in line else (GOLD if 'Exemplo' in line else FG)
                    ax.text(0.05, 0.50 - i * 0.035, line, color=c, fontsize=7,
                            fontfamily='monospace', transform=ax.transAxes, zorder=10)
            elif pg == 22:
                ax2 = fig.add_axes([0.55, 0.15, 0.40, 0.65])
                setup_ax(ax2, 'Juntas Alternadas')
                # Face A (base)
                for i in range(4):
                    draw_painel(ax2, i * 40, 0, 35, 50, GRAY, hatch=False)
                ax2.text(80, -10, 'Face A', color=FG, fontsize=7, ha='center')
                # Face C (offset +20mm para simular desalinhamento de junta)
                for i in range(4):
                    draw_painel(ax2, i * 40 + 20, 70, 35, 50, GRAY, hatch=False)
                ax2.text(100, 60, 'Face C', color=FG, fontsize=7, ha='center')
                # Linhas de referencia das juntas Face A
                for xj in [0, 40, 80, 120, 160]:
                    ax2.axvline(x=xj, color='#224466', lw=0.6, linestyle=':', alpha=0.8, zorder=1)
                # Seta mostrando offset entre juntas
                ax2.annotate('', xy=(20, 72), xytext=(0, 52),
                             arrowprops=dict(arrowstyle='->', color=CYAN, lw=1.2))
                ax2.text(22, 62, '~20mm\noffset', color=CYAN, fontsize=5.5, ha='left', fontfamily='monospace')
                ax2.set_xlim(-10, 200); ax2.set_ylim(-20, 140)
                # Conteudo extra no lado esquerdo (ax)
                ax.text(0.05, 0.56, 'EXEMPLO: PILAR 200x300mm', color=ACCENT, fontsize=8,
                        fontweight='bold', fontfamily='monospace', transform=ax.transAxes, zorder=10)
                exemplo_lines = [
                    'Face A (300mm): paineis @ X=0, 220, 440 -> junta @ 220mm',
                    'Face C (300mm): paineis @ X=110, 330 -> junta @ 330mm',
                    '  -> offset entre juntas: 330 - 220 = 110mm  (OK >= 100mm)',
                    '',
                    'Face B (200mm): paineis @ X=0, 200 -> junta @ 200mm',
                    'Face D (200mm): paineis @ X=100 -> junta @ 300mm',
                    '  -> offset = 100mm  (OK = 100mm minimo)',
                ]
                for i, line in enumerate(exemplo_lines):
                    c = CYAN if '->' in line else (GOLD if 'OK' in line else FG)
                    ax.text(0.05, 0.51 - i * 0.047, line, color=c, fontsize=6.5,
                            fontfamily='monospace', transform=ax.transAxes, zorder=10)
                ax.text(0.05, 0.17, 'REGRA DA QUINA (SOBREPOSICAO):', color=ACCENT, fontsize=8,
                        fontweight='bold', fontfamily='monospace', transform=ax.transAxes, zorder=10)
                quina_rules = [
                    '* Montagem anti-horaria: A -> B -> C -> D',
                    '* Face A sobrepoe Face B no canto (painel A passa por fora)',
                    '* Maior painel sempre externo na quina',
                    '* Nunca cortar na quina — usar sarrafo para ajuste fino',
                ]
                for i, q in enumerate(quina_rules):
                    ax.text(0.05, 0.12 - i * 0.048, q, color=FG, fontsize=7,
                            fontfamily='monospace', transform=ax.transAxes, zorder=10)
            rodape(fig, pg, total, f'Regras - {title}')
            pdf.savefig(fig); plt.close(fig)

        # --- Pg 26-30: PADROES POR OBRA ---
        obras_data = [
            (26, 'ALIMONTI Paraiso', PL_1,
             [('P1', '200x300', 'PA-022x100', 'SARR_2.2x7', '3.24'),
              ('P2', '150x200', 'PA-022x100', 'SARR_2.2x7', '3.24'),
              ('P3', '250x400', 'PA-022x100', 'SARR_2.2x7', '3.24'),
              ('P4', '300x500', 'PA-022x100', 'SARR_2.2x7', '3.24')]),
            (27, 'NOVA-SCHWARTZ GWT', PL_2,
             [('P1', '200x200', 'PA-022x100', 'SARR_2.2x7', '3.00'),
              ('P2', '200x400', 'PA-022x100', 'SARR_2.2x7', '3.00'),
              ('P3', '300x600', 'PA-022x100', 'SARR_2.2x7', '3.00')]),
            (28, 'SKR LEAF', PL_3,
             [('P1', '150x200', 'PA-022x100', 'SARR_2.2x7', '2.80'),
              ('P2', '200x300', 'PA-022x100', 'SARR_2.2x7', '2.80'),
              ('P3', '250x400', 'PA-022x100', 'SARR_2.2x7', '2.80')]),
            (29, 'Comparacao 3 Obras - Secoes', None, []),
            (30, 'Comparacao 3 Obras - Estatisticas', None, []),
        ]
        for pg, obra_name, dxf_path, data in obras_data:
            print(f'  [Pg {pg}/{total}] Padroes por Obra - {obra_name}')
            fig = fig_a3(f'PG {pg} - PADROES: {obra_name.upper()}')
            if dxf_path and data:
                ax = fig.add_axes([0.05, 0.45, 0.50, 0.45])
                render_dxf_zona(ax, dxf_path, title=f'{obra_name} - PL')
                ax2 = fig.add_axes([0.05, 0.08, 0.9, 0.32])
                ax2.set_facecolor(BG); ax2.axis('off')
                tabela_dados(ax2, 0.05, 0.90,
                             ['Pilar', 'Secao', 'Painel', 'Sarrafo', 'PD(m)'],
                             data, col_widths=[0.12, 0.18, 0.22, 0.22, 0.12])
            elif pg == 29:
                ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
                ax.set_facecolor(BG); ax.axis('off')
                tabela_dados(ax, 0.05, 0.90,
                             ['Obra', 'Secoes', 'Painel', 'PD med', 'Qtd Pilares'],
                             [['ALIMONTI', '150x200 a 300x500', 'PA-022', '3.24m', '~40'],
                              ['GWT', '200x200 a 300x600', 'PA-022', '3.00m', '~35'],
                              ['LEAF', '150x200 a 250x400', 'PA-022', '2.80m', '~30']],
                             col_widths=[0.18, 0.25, 0.15, 0.15, 0.18])
            else:
                ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
                ax.set_facecolor(BG); ax.axis('off')
                tabela_regras(ax, 0.05, 0.90, 'ESTATISTICAS GERAIS:', [
                    '* Espessura padrao de painel: 22mm (universal)',
                    '* Sarrafo padrao: SARR_2.2x7 (universal)',
                    '* Chapa: ACI=1 (vermelho) em todas as obras',
                    '* Perfil Metalico: ACI=224 em todas',
                    '* Variacoes principais: secao do pilar e pe direito',
                    '',
                    '* ALIMONTI: maior variedade de secoes',
                    '* GWT: secoes maiores (ate 300x600mm)',
                    '* LEAF: secoes menores, pe direito menor',
                ])
            rodape(fig, pg, total, f'Padroes - {obra_name}')
            pdf.savefig(fig); plt.close(fig)

    print(f'  Salvo: {pdf_path}')


# ==========================================================================
# PDF 2: FICHAS VIGAS
# ==========================================================================
def gerar_vigas(pdf_path):
    total = 30
    with PdfPages(str(pdf_path)) as pdf:

        # --- Pg 1: CAPA ---
        print(f'  [Pg 1/{total}] Capa Vigas')
        fig = fig_a3('FICHAS INSTRUTIVAS - VIGAS (LV + FV)')
        ax = fig.add_axes([0.05, 0.05, 0.9, 0.85])
        ax.set_facecolor(BG); ax.axis('off')
        fig.text(0.5, 0.85, 'FICHAS INSTRUTIVAS', ha='center', fontsize=28,
                 color=ACCENT, fontweight='bold', fontfamily='monospace')
        fig.text(0.5, 0.78, 'VIGAS (LV + FV)', ha='center', fontsize=22,
                 color=WHITE, fontfamily='monospace')
        fig.text(0.5, 0.72, f'30 paginas A3 | Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                 ha='center', fontsize=10, color=LGRAY)
        sumario = [
            'Pg 2:  Anatomia da Viga (visao geral)',
            'Pg 3:  Fundo de Viga (FV)',
            'Pg 4:  Lateral A (Sarrafeada)',
            'Pg 5:  Lateral A (com Grade)',
            'Pg 6:  Lateral B: diferencas',
            'Pg 7:  Corte Transversal: 4 variantes',
            'Pg 8:  Garfos (bloco C)',
            'Pg 9:  Escoras HT20CT',
            'Pg 10: Presilhas Metalicas',
            'Pg 11-15: Exemplos Reais LV Anotados',
            'Pg 16-20: Exemplos Reais FV Anotados',
            'Pg 21-25: Variacoes por Obra',
            'Pg 26-30: Campos do Robo + Regras',
        ]
        for i, s in enumerate(sumario):
            fig.text(0.2, 0.60 - i * 0.032, s, fontsize=9, color=FG, fontfamily='monospace')
        rodape(fig, 1, total, 'Fichas Instrutivas - Vigas')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 2: ANATOMIA DA VIGA ---
        print(f'  [Pg 2/{total}] Anatomia da Viga')
        fig = fig_a3('PG 2 - ANATOMIA DA VIGA (VISAO GERAL)')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        setup_ax(ax, 'Diagrama Isometrico Simplificado')
        # Isometric projection of a beam
        # Concreto (3D box)
        vw, vh, vl = 200, 500, 600  # width, height, length
        s = 0.3
        iso_angle = 30
        dx = math.cos(math.radians(iso_angle)) * vl * s * 0.4
        dy = math.sin(math.radians(iso_angle)) * vl * s * 0.4
        # Front face
        x0, y0 = 0, 0
        draw_concreto(ax, x0, y0, vw * s, vh * s)
        ax.text(x0 + vw * s / 2, y0 + vh * s / 2, 'CONCRETO', ha='center', va='center',
                color=FG, fontsize=7, fontweight='bold', zorder=10)
        # FV (fundo)
        fv_h = 22 * s
        draw_painel(ax, x0 - 10, y0 - fv_h, vw * s + 20, fv_h, GRAY, hatch=True)
        ax.text(x0 + vw * s / 2, y0 - fv_h / 2, 'FV', ha='center', va='center',
                color=WHITE, fontsize=7, fontweight='bold', zorder=10)
        # Lateral A
        pe = 22 * s
        draw_painel(ax, x0 - pe, y0, pe, vh * s, GRAY, hatch=True)
        ax.text(x0 - pe / 2, y0 + vh * s / 2, 'Lat.A', ha='center', va='center',
                color=WHITE, fontsize=6, fontweight='bold', rotation=90, zorder=10)
        # Lateral B
        draw_painel(ax, x0 + vw * s, y0, pe, vh * s, GRAY, hatch=True)
        ax.text(x0 + vw * s + pe / 2, y0 + vh * s / 2, 'Lat.B', ha='center', va='center',
                color=WHITE, fontsize=6, fontweight='bold', rotation=90, zorder=10)
        # HT20CT
        ht_y = y0 + vh * s + pe + 5
        draw_ht20ct(ax, x0 + vw * s / 2, ht_y, w=vw * s + 2*pe + 20, h=20, color=YELLOW)
        ax.text(x0 + vw * s / 2, ht_y + 25, 'HT20CT', ha='center', color=YELLOW,
                fontsize=7, fontweight='bold', zorder=10)
        # PRESILHA
        pre_y = y0 + vh * s * 0.7
        ax.plot([x0 - pe - 15, x0 - pe - 15, x0 - pe - 5],
                [pre_y + 20, pre_y, pre_y], color=RED, lw=2, zorder=5)
        ax.text(x0 - pe - 30, pre_y + 10, 'PRESILHA', ha='center', color=RED,
                fontsize=6, fontweight='bold', rotation=90, zorder=10)
        # Garfo
        garfo_y = y0 + vh * s * 0.3
        ax.plot([x0 - pe - 30, x0 + vw * s + pe + 30], [garfo_y, garfo_y],
                color=WHITE, lw=1.5, linestyle='-.', zorder=5)
        ax.text(x0 + vw * s + pe + 35, garfo_y, 'GARFO', ha='left', color=WHITE,
                fontsize=6, fontweight='bold', zorder=10)
        ax.set_xlim(-80, 200); ax.set_ylim(-30, 200)
        # Legenda
        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        legend_items = [
            (DGRAY, 'Concreto (viga)'),
            (GRAY, 'FV = Fundo de Viga'),
            (GRAY, 'Lat.A = Lateral principal'),
            (GRAY, 'Lat.B = Lateral secundaria'),
            (YELLOW, 'HT20CT = Escora em U'),
            (RED, 'Presilha Metalica'),
            (WHITE, 'Garfo/Bloco C = Conector'),
            (GREEN, 'Tensor'),
        ]
        for i, (c, t) in enumerate(legend_items):
            ax2.plot(0.05, 0.90 - i * 0.06, 's', color=c, markersize=10,
                     transform=ax2.transAxes, zorder=5)
            ax2.text(0.15, 0.90 - i * 0.06, t, color=FG, fontsize=8,
                     va='center', transform=ax2.transAxes, zorder=5)
        rodape(fig, 2, total, 'Anatomia da Viga')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 3: FUNDO DE VIGA ---
        print(f'  [Pg 3/{total}] Fundo de Viga (FV)')
        fig = fig_a3('PG 3 - FUNDO DE VIGA (FV): ESTRUTURA E REGRAS')
        ax = fig.add_axes([0.05, 0.35, 0.55, 0.55])
        setup_ax(ax, 'FV Sarrafeado - Vista Superior')
        # Paineis horizontais
        for i in range(5):
            draw_painel(ax, 0, i * 65, 300, 55, GRAY, hatch=True)
            if i < 4:
                draw_sarrafo(ax, 0, i * 65 + 55, 300, 10, GOLD)
        # SARRAFO DE PRESSAO
        ax.plot([-10, -10], [0, 5 * 65 - 10], color=DGRAY, lw=2, linestyle='--', zorder=5)
        ax.plot([310, 310], [0, 5 * 65 - 10], color=DGRAY, lw=2, linestyle='--', zorder=5)
        ax.text(-30, 150, 'SDP', color=DGRAY, fontsize=6, rotation=90, va='center',
                fontweight='bold')
        ax.set_xlim(-50, 370); ax.set_ylim(-20, 340)
        # FV Grade
        ax2 = fig.add_axes([0.05, 0.08, 0.55, 0.22])
        setup_ax(ax2, 'FV com Grade')
        draw_grade(ax2, 0, 0, 300, 200, GRAY, grid_spacing=40)
        ax2.set_xlim(-20, 340); ax2.set_ylim(-20, 230)
        # Regras
        ax_r = fig.add_axes([0.62, 0.08, 0.35, 0.82])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.95, 'FUNDO DE VIGA:', [
            '* Paineis na horizontal (W = larg. viga)',
            '* Juntas perpendiculares ao comprimento',
            '* SARRAFO DE PRESSAO nas 2 bordas long.',
            '* Layer: Paineis + SARR_2.2x7',
            '* FV grade: quando largura > 60cm',
        ])
        tabela_regras(ax_r, 0.05, 0.60, 'PARAMETROS DO ROBO:', [
            'largura_viga (mm): 200',
            'tipo_fundo: sarr / grade',
            'comprimento_fundo: 4800mm',
        ])
        rodape(fig, 3, total, 'Fundo de Viga (FV)')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 4: LATERAL A (SARRAFEADA) ---
        print(f'  [Pg 4/{total}] Lateral A (Sarrafeada)')
        fig = fig_a3('PG 4 - LATERAL A (SARRAFEADA): ESTRUTURA COMPLETA')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        setup_ax(ax, 'Lateral A - Elevacao com Paineis Individuais')
        # Paineis verticais
        n_panels = 6
        pw = 80
        for i in range(n_panels):
            x0 = i * (pw + 15)
            draw_painel(ax, x0, 0, pw, 250, GRAY, hatch=True)
            if i < n_panels - 1:
                draw_sarrafo(ax, x0 + pw, 0, 15, 250, GOLD)
        total_w = n_panels * (pw + 15) - 15
        # SARRAFO DE PRESSAO topo e base
        ax.plot([0, total_w], [0, 0], color=DGRAY, lw=2, linestyle='--', zorder=5)
        ax.plot([0, total_w], [250, 250], color=DGRAY, lw=2, linestyle='--', zorder=5)
        ax.text(total_w / 2, -15, 'SARRAFO DE PRESSAO', ha='center', color=DGRAY,
                fontsize=6, fontweight='bold')
        # HT20CT a cada ~2 paineis
        for i in range(0, n_panels, 2):
            cx = i * (pw + 15) + pw / 2
            draw_ht20ct(ax, cx, 250, w=60, h=30, color=YELLOW, lw=1.2)
        # PRESILHA
        ax.plot([-10, -10, -5], [230, 200, 200], color=RED, lw=2, zorder=5)
        ax.text(-25, 215, 'PRESILHA', color=RED, fontsize=6, rotation=90, fontweight='bold')
        # Barra de ancoragem
        ax.plot([0, total_w], [125, 125], color=DGRAY, lw=1.5, linestyle='-.', zorder=5)
        # Label
        ax.text(total_w / 2, 300, 'V1.A - CMT: 95,4', ha='center', color=WHITE,
                fontsize=9, fontweight='bold',
                bbox=dict(facecolor='#1a1a2e', edgecolor=WHITE, pad=5), zorder=10)
        ax.set_xlim(-40, total_w + 30); ax.set_ylim(-30, 320)
        # Regras
        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'LATERAL A:', [
            '* Label A = lateral principal',
            '* HT20CT a cada 400-600mm',
            '* PRESILHA MET. 1 no topo, 2 no meio',
            '* SARRAFO DE PRESSAO sup/inf',
            '* CMT (comprimento) no label',
            '* Barra ancoragem horizontal',
        ])
        rodape(fig, 4, total, 'Lateral A (Sarrafeada)')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 5: LATERAL A (COM GRADE) ---
        print(f'  [Pg 5/{total}] Lateral A (com Grade)')
        fig = fig_a3('PG 5 - LATERAL A (COM GRADE): PAINEL PRE-FABRICADO')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        setup_ax(ax, 'Lateral A - Grade Metalica')
        total_w = 500
        total_h = 250
        draw_grade(ax, 0, 0, total_w, total_h, GRAY, grid_spacing=50)
        # HT20CT
        for i in range(0, 6):
            cx = i * 100 + 50
            draw_ht20ct(ax, cx, total_h, w=60, h=30, color=YELLOW, lw=1.2)
        # PRESILHA
        ax.plot([-10, -10, -5], [230, 200, 200], color=RED, lw=2, zorder=5)
        # Barra ancoragem
        ax.plot([0, total_w], [125, 125], color=DGRAY, lw=1.5, linestyle='-.', zorder=5)
        ax.text(total_w / 2, total_h + 50, 'V1.A (GRADE) - CMT: 95,4',
                ha='center', color=WHITE, fontsize=9, fontweight='bold',
                bbox=dict(facecolor='#1a1a2e', edgecolor=WHITE, pad=5), zorder=10)
        ax.set_xlim(-40, total_w + 30); ax.set_ylim(-30, total_h + 80)
        # Regras
        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'LATERAL A COM GRADE:', [
            '* Um unico painel cobre toda a altura',
            '* Grid metalico interno visivel',
            '* Mesma posicao de HT20CT e presilhas',
            '* Quando usar: h < 50cm ou repeticao',
            '* DXF: LWPOLYLINE + hachura SOLID',
            '  layer "Paineis"',
        ])
        tabela_regras(ax2, 0.05, 0.50, 'DIFERENCA SARR vs GRADE:', [
            '* Grade = sem sarrafos individuais',
            '* Grade = painel unico metalico',
            '* Sarrafeado = multiplos paineis madeira',
        ])
        rodape(fig, 5, total, 'Lateral A (com Grade)')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 6: LATERAL B ---
        print(f'  [Pg 6/{total}] Lateral B')
        fig = fig_a3('PG 6 - LATERAL B: DIFERENCAS EM RELACAO A A')
        ax1 = fig.add_axes([0.05, 0.15, 0.42, 0.75])
        setup_ax(ax1, 'Lateral A (principal)')
        for i in range(6):
            x0 = i * 70
            draw_painel(ax1, x0, 0, 55, 200, GRAY, hatch=False)
            if i < 5:
                draw_sarrafo(ax1, x0 + 55, 0, 15, 200, GOLD)
        ax1.text(210, 220, 'V1.A - CMT: 95,4', ha='center', color=WHITE, fontsize=8,
                 fontweight='bold')
        ax1.set_xlim(-20, 430); ax1.set_ylim(-20, 240)

        ax2 = fig.add_axes([0.52, 0.15, 0.42, 0.75])
        setup_ax(ax2, 'Lateral B (secundaria)')
        for i in range(5):
            x0 = i * 70
            draw_painel(ax2, x0, 0, 55, 200, '#6688aa', hatch=False)
            if i < 4:
                draw_sarrafo(ax2, x0 + 55, 0, 15, 200, GOLD)
        ax2.text(175, 220, 'V1.B - CMT: 85,0', ha='center', color=WHITE, fontsize=8,
                 fontweight='bold')
        ax2.set_xlim(-20, 380); ax2.set_ylim(-20, 240)

        fig.text(0.5, 0.08, 'Quando A = B: mesmas dimensoes, identificacao diferente '
                 'para posicionamento em obra', ha='center', fontsize=9, color=FG,
                 style='italic')
        rodape(fig, 6, total, 'Lateral B vs Lateral A')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 7: CORTE TRANSVERSAL - 4 VARIANTES ---
        print(f'  [Pg 7/{total}] Corte Transversal - 4 Variantes')
        fig = fig_a3('PG 7 - CORTE TRANSVERSAL: 4 VARIANTES')
        configs_corte = [
            ('SEM garfo + Sarrafeado', False, 'sarr'),
            ('COM garfo + Sarrafeado', True, 'sarr'),
            ('SEM garfo + Grade', False, 'grade'),
            ('COM garfo + Grade', True, 'grade'),
        ]
        for idx, (label, garfo, tipo) in enumerate(configs_corte):
            row, col = idx // 2, idx % 2
            ax = fig.add_axes([0.05 + col * 0.48, 0.08 + (1 - row) * 0.44, 0.42, 0.40])
            setup_ax(ax, label)
            draw_viga_corte(ax, 0, 0, 200, 400, com_garfo=garfo, tipo=tipo,
                            scale=0.15, annotate_parts=(idx == 0))
            ax.set_xlim(-30, 30); ax.set_ylim(-45, 45)
            draw_scale_bar(ax, scale_mm_per_unit=1.0/0.15, bar_length_mm=100)
        draw_carimbo(fig, 'CORTE VIGA - 4 VARIANTES', '', '1:5', '07', '30')
        rodape(fig, 7, total, 'Corte Transversal - 4 Variantes')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 8: GARFOS ---
        print(f'  [Pg 8/{total}] Garfos (bloco C)')
        fig = fig_a3('PG 8 - GARFOS (BLOCO C): ANATOMIA E POSICIONAMENTO')
        ax = fig.add_axes([0.05, 0.35, 0.42, 0.55])
        setup_ax(ax, 'Bloco C - Parafuso de Aco')
        # Corpo do garfo (simplificado)
        ax.plot([0, 60], [0, 0], color=WHITE, lw=3, zorder=5)
        ax.plot(0, 0, 'o', color=WHITE, markersize=10, zorder=6)
        ax.plot(60, 0, 'o', color=WHITE, markersize=10, zorder=6)
        # Porca
        hex_pts = [(60 + 8*math.cos(a), 8*math.sin(a))
                   for a in np.linspace(0, 2*math.pi, 7)]
        hex_poly = Polygon(hex_pts, closed=True, facecolor=LGRAY, edgecolor=WHITE,
                           lw=1.0, zorder=7)
        ax.add_patch(hex_poly)
        ax.text(30, -15, '~60mm total', ha='center', color=CYAN, fontsize=7, fontweight='bold')
        ax.set_xlim(-20, 80); ax.set_ylim(-25, 25)

        ax2 = fig.add_axes([0.52, 0.35, 0.42, 0.55])
        setup_ax(ax2, 'Posicionamento em Elevacao')
        # Viga lateral com garfos
        draw_painel(ax2, 0, 0, 300, 200, GRAY, hatch=False)
        for gy in [50, 100, 150]:
            ax2.plot([-20, 320], [gy, gy], color=WHITE, lw=1.5, linestyle='-.', zorder=5)
            ax2.plot(-20, gy, 'o', color=WHITE, markersize=4, zorder=6)
            ax2.plot(320, gy, 'o', color=WHITE, markersize=4, zorder=6)
        ax2.text(150, -15, 'Espc. 300-500mm', ha='center', color=CYAN, fontsize=7,
                 fontweight='bold')
        ax2.set_xlim(-40, 350); ax2.set_ylim(-25, 220)

        ax_r = fig.add_axes([0.05, 0.08, 0.9, 0.22])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.9, 'GARFOS:', [
            '* Posicao: centro da secao do concreto',
            '* Espacamento vertical: 300-500mm',
            '* Presente em vigas com h > 50cm ou grandes cargas',
            '* Layer: GARFOS (ACI=7, branco) | Bloco: C (INSERT)',
            '* Identificacao: "CMT: XX,X" no texto V1.A',
        ])
        rodape(fig, 8, total, 'Garfos (Bloco C)')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 9: ESCORAS HT20CT ---
        print(f'  [Pg 9/{total}] Escoras HT20CT')
        fig = fig_a3('PG 9 - ESCORAS HT20CT: ANATOMIA E POSICIONAMENTO')
        ax = fig.add_axes([0.05, 0.35, 0.42, 0.55])
        setup_ax(ax, 'Bloco HT20CT - Forma em U/H')
        draw_ht20ct(ax, 0, 0, w=200, h=200, color=YELLOW, lw=3)
        ax.annotate('', xy=(-100, 0), xytext=(100, 0),
                    arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8))
        ax.text(0, -20, '200mm', ha='center', color=CYAN, fontsize=8, fontweight='bold')
        ax.annotate('', xy=(-110, 0), xytext=(-110, 200),
                    arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8))
        ax.text(-130, 100, '200mm', ha='center', va='center', color=CYAN, fontsize=8,
                fontweight='bold', rotation=90)
        ax.set_xlim(-160, 160); ax.set_ylim(-40, 230)

        ax2 = fig.add_axes([0.52, 0.35, 0.42, 0.55])
        setup_ax(ax2, 'Posicao na Lateral da Viga')
        draw_painel(ax2, 0, 0, 400, 200, GRAY, hatch=False)
        for i in range(5):
            cx = i * 100 + 50
            draw_ht20ct(ax2, cx, 200, w=40, h=25, color=YELLOW, lw=1.5)
        ax2.text(200, -15, 'Esp. 400-600mm', ha='center', color=CYAN, fontsize=7,
                 fontweight='bold')
        ax2.set_xlim(-20, 420); ax2.set_ylim(-25, 250)

        ax_r = fig.add_axes([0.05, 0.08, 0.9, 0.22])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.9, 'HT20CT:', [
            '* 3 LWPOLYLINEs = 2 pernas verticais + topo horizontal',
            '* Dimensoes: larg ~200mm, alt ~200mm, esp. linha ~10mm',
            '* Posicao: exterior da lateral, espc. 400-600mm',
            '* Layer: Escoras (ACI=2, amarelo)',
        ])
        rodape(fig, 9, total, 'Escoras HT20CT')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 10: PRESILHAS METALICAS ---
        print(f'  [Pg 10/{total}] Presilhas Metalicas')
        fig = fig_a3('PG 10 - PRESILHAS METALICAS: TIPOS E POSICIONAMENTO')
        ax = fig.add_axes([0.05, 0.35, 0.42, 0.55])
        setup_ax(ax, 'PRESILHA MET. 1 (Topo)')
        # C shape
        ax.plot([0, 0, 40, 40], [60, 0, 0, 10], color=RED, lw=3, zorder=5)
        ax.text(20, -15, 'Topo', ha='center', color=RED, fontsize=8, fontweight='bold')
        ax.set_xlim(-20, 60); ax.set_ylim(-25, 80)

        ax2 = fig.add_axes([0.52, 0.35, 0.42, 0.55])
        setup_ax(ax2, 'PRESILHA MET. 2 (Meio)')
        ax2.plot([0, 0, 40, 40], [50, 0, 0, 10], color=RED, lw=3, zorder=5)
        ax2.text(20, -15, 'Terco intermediario', ha='center', color=RED, fontsize=8,
                 fontweight='bold')
        ax2.set_xlim(-20, 60); ax2.set_ylim(-25, 70)

        ax_r = fig.add_axes([0.05, 0.08, 0.9, 0.22])
        ax_r.set_facecolor(BG); ax_r.axis('off')
        tabela_regras(ax_r, 0.05, 0.9, 'PRESILHAS:', [
            '* PRESILHA 1: forma de C (topo), cobre parte superior',
            '* PRESILHA 2: forma de C (meio), no terco intermediario',
            '* Layer: presilha (ACI=1, vermelho)',
            '* Posicao: exterior da lateral da viga',
        ])
        rodape(fig, 10, total, 'Presilhas Metalicas')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 11-15: EXEMPLOS REAIS LV ---
        lv_pages = [
            (11, LV_1, LV_ZOOM_1, 'Lateral A sarrafeada - ALIMONTI', [
                ('HT20CT', (4500, 6500), (4200, 6800), YELLOW),
                ('Paineis', (3500, 6200), (3200, 5800), GRAY),
            ]),
            (12, LV_1, (5000, 5500, 7000, 7100), 'Lateral B - ALIMONTI', []),
            (13, LV_1, (3500, 6500, 5000, 7000), 'Zona HT20CT - ALIMONTI', [
                ('Escoras HT20CT', (4000, 6700), (3800, 6900), YELLOW),
            ]),
            (14, LV_2, None, 'LV completo - GWT', []),
            (15, LV_3, None, 'LV completo - LEAF', []),
        ]
        for pg, dxf_path, crop, title, annots in lv_pages:
            print(f'  [Pg {pg}/{total}] Exemplo Real LV - {title}')
            fig = fig_a3(f'PG {pg} - EXEMPLO REAL LV: {title}')
            ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
            render_dxf_zona(ax, dxf_path, crop=crop, title=title)
            for (txt, xy_a, xy_t, c) in annots:
                annotate_arrow(ax, txt, xy_a, xy_t, c)
            rodape(fig, pg, total, f'Exemplo Real LV - {title}')
            pdf.savefig(fig); plt.close(fig)

        # --- Pg 16-20: EXEMPLOS REAIS FV ---
        fv_pages = [
            (16, FV_1, None, 'FV completo - ALIMONTI', []),
            (17, FV_2 if FV_2.exists() else FV_1, None, 'FV completo - GWT', []),
            (18, FV_1, (3500, 1500, 5500, 3000), 'FV zoom zona A - ALIMONTI', []),
            (19, FV_1, (5000, 1500, 7000, 3000), 'FV zoom zona B - ALIMONTI', []),
            (20, LV_1, LV_AREA_ALL, 'Visao geral LV - referencia FV', []),
        ]
        for pg, dxf_path, crop, title, annots in fv_pages:
            print(f'  [Pg {pg}/{total}] Exemplo Real FV - {title}')
            fig = fig_a3(f'PG {pg} - EXEMPLO REAL FV: {title}')
            ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
            render_dxf_zona(ax, dxf_path, crop=crop, title=title)
            rodape(fig, pg, total, f'Exemplo Real FV - {title}')
            pdf.savefig(fig); plt.close(fig)

        # --- Pg 21-25: VARIACOES POR OBRA ---
        var_vigas = [
            (21, 'ALIMONTI - Vigas', LV_1,
             [('V1', '200x500', 'sarr', 'Sim', '4.80'),
              ('V2', '200x400', 'sarr', 'Sim', '3.60'),
              ('V3', '150x300', 'sarr', 'Nao', '2.40')]),
            (22, 'GWT - Vigas', LV_2,
             [('V1', '200x500', 'sarr', 'Sim', '5.00'),
              ('V2', '250x600', 'grade', 'Sim', '6.00')]),
            (23, 'LEAF - Vigas', LV_3,
             [('V1', '200x400', 'sarr', 'Sim', '4.00'),
              ('V2', '150x300', 'sarr', 'Nao', '3.00')]),
            (24, 'Comparacao 3 Obras - Vigas', None, []),
            (25, 'Estatisticas Vigas', None, []),
        ]
        for pg, obra, dxf_path, data in var_vigas:
            print(f'  [Pg {pg}/{total}] Variacoes Vigas - {obra}')
            fig = fig_a3(f'PG {pg} - {obra.upper()}')
            if dxf_path and data:
                ax = fig.add_axes([0.05, 0.45, 0.50, 0.45])
                render_dxf_zona(ax, dxf_path, title=f'{obra} - LV')
                ax2 = fig.add_axes([0.05, 0.08, 0.9, 0.32])
                ax2.set_facecolor(BG); ax2.axis('off')
                tabela_dados(ax2, 0.05, 0.90,
                             ['Viga', 'Secao', 'Tipo', 'Garfo', 'Comp(m)'],
                             data, col_widths=[0.12, 0.18, 0.15, 0.12, 0.15])
            elif pg == 24:
                ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
                ax.set_facecolor(BG); ax.axis('off')
                tabela_dados(ax, 0.05, 0.90,
                             ['Obra', 'Secoes', 'Tipo Lat.', 'Garfo', 'Comp.Med'],
                             [['ALIMONTI', '150x300 a 200x500', 'sarr', 'maioria', '~4m'],
                              ['GWT', '200x500 a 250x600', 'sarr/grade', 'todos', '~5m'],
                              ['LEAF', '150x300 a 200x400', 'sarr', 'parcial', '~3.5m']],
                             col_widths=[0.18, 0.25, 0.15, 0.15, 0.15])
            else:
                ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
                ax.set_facecolor(BG); ax.axis('off')
                tabela_regras(ax, 0.05, 0.90, 'ESTATISTICAS VIGAS:', [
                    '* Espessura padrao painel: 22mm (universal)',
                    '* Sarrafo padrao: SARR_2.2x7',
                    '* HT20CT: presente em todas as obras',
                    '* Garfos: vigas com h > 400mm geralmente',
                    '* Presilhas: sempre presentes',
                ])
            rodape(fig, pg, total, f'Variacoes - {obra}')
            pdf.savefig(fig); plt.close(fig)

        # --- Pg 26-30: CAMPOS DO ROBO + REGRAS GERAIS ---
        print(f'  [Pg 26/{total}] Campos do Robo - Vigas')
        fig = fig_a3('PG 26 - CAMPOS DO ROBO: PARAMETROS VIGAS')
        ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
        ax.set_facecolor(BG); ax.axis('off')
        params_v = [
            ('viga_id', 'str', 'V1', 'ID da viga'),
            ('largura_viga', 'int mm', '200', 'Largura secao concreto'),
            ('altura_viga', 'int mm', '500', 'Altura secao concreto'),
            ('comprimento', 'float m', '4.80', 'Comprimento da viga'),
            ('nivel_saida', 'float', '778.92', 'Cota Z base'),
            ('nivel_chegada', 'float', '1002.92', 'Cota Z topo'),
            ('tipo_lateral', 'str', 'sarr/grade', 'Tipo paineis laterais'),
            ('tipo_fundo', 'str', 'sarr/grade', 'Tipo painel do fundo'),
            ('tem_garfo', 'bool', 'True', 'Usar ancoragem com garfos?'),
            ('esp_garfo', 'int mm', '400', 'Espacamento entre garfos'),
            ('qtd_ht20ct', 'int', '8', 'Quantidade escoras HT20CT'),
            ('label_A', 'str', 'V1.A', 'Label lateral A'),
            ('label_B', 'str', 'V1.B', 'Label lateral B'),
            ('cmt_A', 'float', '95.4', 'Comprimento lateral A (cm)'),
            ('cmt_B', 'float', '95.4', 'Comprimento lateral B (cm)'),
        ]
        tabela_dados(ax, 0.05, 0.95, ['Campo', 'Tipo', 'Exemplo', 'Descricao'],
                     [[p[0], p[1], p[2], p[3]] for p in params_v],
                     col_widths=[0.20, 0.15, 0.18, 0.40])
        rodape(fig, 26, total, 'Campos do Robo - Vigas')
        pdf.savefig(fig); plt.close(fig)

        # Pg 27-30: regras gerais complementares
        rules_v = [
            (27, 'Regras de Distribuicao - Laterais', [
                '* Paineis da lateral sao verticais',
                '* SARR_2.2x7 nas juntas entre paineis',
                '* HT20CT: esp=600mm (comp<3m), esp=400mm (comp>=3m)',
                '* Presilha 1 topo, Presilha 2 tercos',
                '* SARRAFO DE PRESSAO sup e inf',
            ]),
            (28, 'Regras de Fundo de Viga', [
                '* FV = paineis horizontais',
                '* SARRAFO DE PRESSAO nas bordas longitudinais',
                '* Juntas perpendiculares ao comprimento',
                '* FV grade: largura > 60cm',
                '* Layer: Paineis + SARR_2.2x7',
            ]),
            (29, 'Regras de Ancoragem e Escoras', [
                '* Garfos (bloco C): centro da secao, esp. 300-500mm',
                '* HT20CT: exterior da lateral',
                '* Tensor: vertical, segura as 2 laterais',
                '* Barra de ancoragem: horizontal pelo concreto',
                '* PRESILHA: exterior da lateral',
            ]),
            (30, 'Resumo Geral - Vigas', [
                '* Viga = FV (fundo) + Lat.A + Lat.B + ancoragem',
                '* Sarrafeado ou Grade (2 tipos)',
                '* HT20CT, Presilha, Garfo = elementos metalicos',
                '* Nomenclatura: V{n}.{face} - CMT: {comp}',
                '* PD, NS, NC = pe direito, nivel saida, nivel chegada',
            ]),
        ]
        for pg, title, rules in rules_v:
            print(f'  [Pg {pg}/{total}] Regras Vigas')
            fig = fig_a3(f'PG {pg} - {title.upper()}')
            # Regras a esquerda
            ax_l = fig.add_axes([0.05, 0.08, 0.44, 0.82])
            ax_l.set_facecolor(BG); ax_l.axis('off')
            tabela_regras(ax_l, 0.03, 0.95, title.upper(), rules)
            # Decision flow a direita
            ax_r = fig.add_axes([0.52, 0.08, 0.46, 0.82])
            ax_r.set_facecolor(BG); ax_r.axis('off')
            ax_r.set_xlim(0, 500); ax_r.set_ylim(0, 550)
            if pg == 27:  # Laterais
                ax_r.text(250, 530, 'DECISAO: TIPO LATERAL', color=ACCENT, fontsize=9,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 150, 480, 200, 35, 'INPUT: layer Paineis\n+ presenca SARR_2.2x7', color='#0d2040')
                draw_flow_arrow(ax_r, 250, 480, 250, 440)
                draw_decision_diamond(ax_r, 250, 415, 180, 45, 'SARR_2.2x7\nno layer?')
                draw_flow_arrow(ax_r, 340, 415, 400, 430, 'SIM')
                draw_decision_box(ax_r, 400, 415, 85, 35, 'tipo_lateral\n= sarr', color='#1a3a1a', text_color=GREEN, fontsize=6.5)
                draw_flow_arrow(ax_r, 250, 392, 250, 355, 'NAO')
                draw_decision_box(ax_r, 170, 335, 160, 35, 'tipo_lateral = grade\n(grid azul #1a2a4a)', color='#1a2a4a', text_color='#5b9bd5')
                # HT20CT spacing
                ax_r.text(250, 300, 'DECISAO: ESPACAMENTO HT20CT', color=ACCENT, fontsize=8,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 150, 255, 200, 35, 'INPUT: comprimento_viga (m)', color='#0d2040')
                draw_flow_arrow(ax_r, 250, 255, 250, 215)
                draw_decision_diamond(ax_r, 250, 192, 180, 45, 'comp\n< 3.0m?')
                draw_flow_arrow(ax_r, 340, 192, 400, 205, 'SIM')
                draw_decision_box(ax_r, 400, 187, 90, 35, 'HT20CT\nesp=600mm', color='#1a1a3a', text_color=YELLOW, fontsize=6.5)
                draw_flow_arrow(ax_r, 250, 170, 250, 135, 'NAO')
                draw_decision_box(ax_r, 170, 115, 160, 35, 'HT20CT esp=400mm\n(max 8 unidades)', color='#1a1a3a', text_color=YELLOW)
                # Decisao: Presilhas
                ax_r.text(250, 97, 'DECISAO: PRESILHAS', color=ACCENT, fontsize=8,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 80, 65, 340, 27, 'PRESILHA 1: topo da lateral (sempre obrigatoria)',
                                  color='#3a0000', text_color=RED, fontsize=6)
                draw_flow_arrow(ax_r, 250, 65, 250, 45)
                draw_decision_diamond(ax_r, 250, 28, 180, 38, 'comp >= 2.0m?')
                draw_flow_arrow(ax_r, 340, 28, 400, 38, 'SIM')
                draw_decision_box(ax_r, 398, 21, 95, 28, 'PRESILHA 2\nem 1/3 alt.',
                                  color='#3a0000', text_color=RED, fontsize=6)
                # Extra info on left side
                ax_l = fig.axes[0]  # first axes = ax_l (rules side)
                ax_l.text(0.03, 0.45, 'ELEMENTOS METALICOS LATERAL:', color=ACCENT, fontsize=8,
                          fontweight='bold', fontfamily='monospace', transform=ax_l.transAxes, zorder=10)
                metal_items = [
                    ('HT20CT', YELLOW, 'Escora em U/H — exterior da lateral'),
                    ('Presilha', RED, 'Grampo metalico — topo + 1/3'),
                    ('Tensor', GREEN, 'Barra vertical — atravessa forma'),
                    ('Garfo', CYAN, 'Bloco C — ancora altura > 400mm'),
                    ('Chapa', RED, 'Ancoragem nas quinas'),
                ]
                for i, (elem, cor, desc) in enumerate(metal_items):
                    ax_l.text(0.03, 0.40 - i * 0.060, f'{elem:<10}', color=cor, fontsize=7.5,
                              fontfamily='monospace', fontweight='bold', transform=ax_l.transAxes, zorder=10)
                    ax_l.text(0.22, 0.40 - i * 0.060, f'= {desc}', color=FG, fontsize=7,
                              fontfamily='monospace', transform=ax_l.transAxes, zorder=10)
            elif pg == 28:  # Fundo
                ax_r.text(250, 530, 'DECISAO: TIPO FUNDO DE VIGA', color=ACCENT, fontsize=9,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 150, 480, 200, 35, 'INPUT: largura_viga (mm)', color='#0d2040')
                draw_flow_arrow(ax_r, 250, 480, 250, 440)
                draw_decision_diamond(ax_r, 250, 415, 180, 45, 'largura\n> 600mm?')
                draw_flow_arrow(ax_r, 340, 415, 400, 430, 'SIM')
                draw_decision_box(ax_r, 400, 415, 85, 35, 'tipo_fundo\n= grade', color='#1a2a4a', text_color='#5b9bd5', fontsize=6.5)
                draw_flow_arrow(ax_r, 250, 392, 250, 355, 'NAO')
                draw_decision_box(ax_r, 170, 335, 160, 35, 'tipo_fundo\n= sarrafeado', color='#1a3a1a', text_color=GREEN)
                # Paineis FV
                ax_r.text(250, 295, 'DISTRIBUICAO PAINEIS FV:', color=ACCENT, fontsize=8,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 80, 250, 340, 35, 'n_paineis = floor(comp / larg_painel)', color='#0d2040')
                draw_flow_arrow(ax_r, 250, 250, 250, 210)
                draw_decision_diamond(ax_r, 250, 185, 200, 45, 'sobra\n< 50mm?')
                draw_flow_arrow(ax_r, 350, 185, 400, 200, 'SIM')
                draw_decision_box(ax_r, 395, 182, 100, 35, 'ajustar ultimo\npainel anterior', color='#3a1a1a', text_color=RED, fontsize=6)
                draw_flow_arrow(ax_r, 250, 162, 250, 125, 'NAO')
                draw_decision_box(ax_r, 155, 105, 190, 35, 'adicionar painel\ncortado (sobra)', color='#2a2a00', text_color=GOLD)
            elif pg == 29:  # Ancoragem
                ax_r.text(250, 530, 'DECISAO: SISTEMA DE ANCORAGEM', color=ACCENT, fontsize=9,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 150, 480, 200, 35, 'INPUT: altura_viga (mm)', color='#0d2040')
                draw_flow_arrow(ax_r, 250, 480, 250, 440)
                draw_decision_diamond(ax_r, 250, 415, 180, 45, 'altura\n> 400mm?')
                draw_flow_arrow(ax_r, 340, 415, 400, 430, 'SIM')
                draw_decision_box(ax_r, 398, 415, 90, 35, 'tem_garfo\n= True', color='#1a3a1a', text_color=GREEN, fontsize=6.5)
                draw_flow_arrow(ax_r, 250, 392, 250, 355, 'NAO')
                draw_decision_box(ax_r, 170, 335, 160, 35, 'tem_garfo = False\n(opcional)', color='#3a1a1a', text_color=RED)
                # PRESILHA
                ax_r.text(250, 295, 'POSICAO DAS PRESILHAS:', color=ACCENT, fontsize=8,
                          fontweight='bold', ha='center', zorder=10)
                draw_decision_box(ax_r, 80, 250, 340, 35, 'PRESILHA tipo 1: topo da lateral', color='#3a0000', text_color=RED)
                draw_flow_arrow(ax_r, 250, 250, 250, 210)
                draw_decision_diamond(ax_r, 250, 185, 200, 45, 'PD > 2.5m?')
                draw_flow_arrow(ax_r, 350, 185, 400, 200, 'SIM')
                draw_decision_box(ax_r, 395, 182, 100, 35, 'PRESILHA 2\n+ PRESILHA 3', color='#3a0000', text_color=RED, fontsize=6)
                draw_flow_arrow(ax_r, 250, 162, 250, 125, 'NAO')
                draw_decision_box(ax_r, 155, 105, 190, 35, 'apenas\nPRESILHA tipo 1', color='#3a0000', text_color=RED)
            elif pg == 30:  # Resumo -- JSON schema
                draw_json_schema(ax_r, 0.02, 0.97, 'viga.json (schema)',
                    [
                        ('viga_id',        '"str"',          '"V1"',      True),
                        ('faces',          'list[str]',      '["V1.A","V1.B","V1.FV"]', True),
                        ('largura_viga',   'int (mm)',       '200',       True),
                        ('altura_viga',    'int (mm)',       '500',       True),
                        ('comprimento',    'float (m)',      '4.80',      True),
                        ('tipo_lateral',   '"sarr"|"grade"', '"sarr"',   True),
                        ('tipo_fundo',     '"sarr"|"grade"', '"sarr"',   True),
                        ('tem_garfo',      'bool',           'true',      True),
                        ('esp_garfo',      'int (mm)',       '400',       False),
                        ('qtd_ht20ct',     'int',            '8',         False),
                        ('nivel_saida',    'float',          '778.92',    False),
                        ('nivel_chegada',  'float',          '1002.92',   False),
                    ], w=0.96)
                # Checklist de montagem
                ax_l.text(0.03, 0.45, 'CHECKLIST DE MONTAGEM - VIGA:', color=ACCENT,
                          fontsize=8, fontweight='bold', transform=ax_l.transAxes, zorder=10)
                checklist = [
                    '1. Posicionar FV (fundo de viga)',
                    '2. Instalar Lateral A (com pontaletes)',
                    '3. Instalar Lateral B (com pontaletes)',
                    '4. Posicionar HT20CT exteriores',
                    '5. Inserir garfos/barras de ancoragem',
                    '6. Apertar tensor vertical',
                    '7. Instalar presilhas (topo + 1/3)',
                    '8. Instalar SARRAFO DE PRESSAO (sup/inf)',
                    '9. Conferir nivel de saida/chegada',
                    '10. Validar plombo das laterais',
                ]
                for i, item in enumerate(checklist):
                    c = GREEN if i < 4 else (GOLD if i < 7 else CYAN)
                    ax_l.text(0.03, 0.40 - i*0.038, item, color=c, fontsize=7,
                              fontfamily='monospace', transform=ax_l.transAxes, zorder=10)
            rodape(fig, pg, total, f'Regras Vigas - {title}')
            pdf.savefig(fig); plt.close(fig)

    print(f'  Salvo: {pdf_path}')


# ==========================================================================
# PDF 3: FICHAS LAJES
# ==========================================================================
def gerar_lajes(pdf_path):
    total = 15
    with PdfPages(str(pdf_path)) as pdf:

        # --- Pg 1: CAPA ---
        print(f'  [Pg 1/{total}] Capa Lajes')
        fig = fig_a3('FICHAS INSTRUTIVAS - LAJES (LJ)')
        ax = fig.add_axes([0.05, 0.05, 0.9, 0.85])
        ax.set_facecolor(BG); ax.axis('off')
        fig.text(0.5, 0.85, 'FICHAS INSTRUTIVAS', ha='center', fontsize=28,
                 color=ACCENT, fontweight='bold', fontfamily='monospace')
        fig.text(0.5, 0.78, 'LAJES (LJ)', ha='center', fontsize=22,
                 color=WHITE, fontfamily='monospace')
        fig.text(0.5, 0.72, f'15 paginas A3 | Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                 ha='center', fontsize=10, color=LGRAY)
        sumario = [
            'Pg 2:  Anatomia da Laje (vista de cima geral)',
            'Pg 3:  Distribuicao de Paineis na Laje',
            'Pg 4:  Recortes (Pilares e Aberturas)',
            'Pg 5:  Cotas e Dimensionamentos',
            'Pg 6:  Sarrafo de Pressao na Laje',
            'Pg 7:  Unioes entre Paineis',
            'Pg 8:  Reaproveitamento de Paineis',
            'Pg 9:  Comparacao 3 Obras (LJ)',
            'Pg 10: Layer Index + Campos do Robo',
            'Pg 11-15: Exemplos com Zoom e Anotacoes',
        ]
        for i, s in enumerate(sumario):
            fig.text(0.2, 0.60 - i * 0.032, s, fontsize=9, color=FG, fontfamily='monospace')
        rodape(fig, 1, total, 'Fichas Instrutivas - Lajes')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 2: ANATOMIA DA LAJE ---
        print(f'  [Pg 2/{total}] Anatomia da Laje')
        fig = fig_a3('PG 2 - ANATOMIA DA LAJE (VISTA DE CIMA)')
        ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
        render_dxf_zona(ax, LJ_1, crop=LJ_AREA_ALL, title='ALIMONTI - LJ - Vista Geral')
        # Annotations
        dxf_annotations(ax, [
            ('Paineis (W=22mm, cinza)', (5000, 2200), (5800, 2600), GRAY),
            ('REAPROVEITAMENTO (amarelo)', (4500, 1800), (3800, 1600), YELLOW),
            ('SARRAFO DE PRESSAO (tracejado)', (3600, 2400), (3600, 2700), DGRAY),
            ('Label: LB1', (4200, 2000), (4200, 1700), WHITE),
        ])
        fig.text(0.5, 0.04, 'Laje = vista de CIMA (planta) dos paineis horizontais',
                 ha='center', fontsize=9, color=FG, style='italic')
        rodape(fig, 2, total, 'Anatomia da Laje')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 3: DISTRIBUICAO DE PAINEIS ---
        print(f'  [Pg 3/{total}] Distribuicao de Paineis')
        fig = fig_a3('PG 3 - DISTRIBUICAO DE PAINEIS NA LAJE')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        setup_ax(ax, 'Laje 5x8m - Grid de Paineis')
        # Grid X direction
        laje_w, laje_h = 500, 800  # scaled
        for row in range(8):
            for col in range(5):
                x0 = col * 100
                y0 = row * 100
                offset = 50 if row % 2 == 1 else 0  # stagger
                draw_painel(ax, x0 + offset * 0.1, y0, 95, 95, GRAY, hatch=False, alpha=0.6)
        # Border
        ax.plot([0, laje_w, laje_w, 0, 0], [0, 0, laje_h, laje_h, 0],
                color=WHITE, lw=2, zorder=5)
        # Cotas
        ax.annotate('', xy=(0, -15), xytext=(laje_w, -15),
                    arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8))
        ax.text(laje_w/2, -25, '5000mm', ha='center', color=CYAN, fontsize=8,
                fontweight='bold')
        ax.annotate('', xy=(-15, 0), xytext=(-15, laje_h),
                    arrowprops=dict(arrowstyle='<->', color=CYAN, lw=0.8))
        ax.text(-30, laje_h/2, '8000mm', ha='center', va='center', color=CYAN,
                fontsize=8, fontweight='bold', rotation=90)
        ax.set_xlim(-50, laje_w + 50); ax.set_ylim(-40, laje_h + 40)

        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'DISTRIBUICAO DE PAINEIS:', [
            '* Paineis na direcao principal (maior span)',
            '* Juntas escalonadas entre filas',
            '* Borda minima de painel: 10cm',
            '* Paineis standard: 50x100, 50x200, 60x120cm',
            '* REAPROVEITAMENTO: regioes secundarias',
        ])
        rodape(fig, 3, total, 'Distribuicao de Paineis')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 4: RECORTES ---
        print(f'  [Pg 4/{total}] Recortes (Pilares e Aberturas)')
        fig = fig_a3('PG 4 - RECORTES (PILARES E ABERTURAS)')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        setup_ax(ax, 'Laje com Recortes de Pilar')
        # Laje base
        lw, lh = 400, 300
        draw_painel(ax, 0, 0, lw, lh, GRAY, hatch=False, alpha=0.4)
        ax.plot([0, lw, lw, 0, 0], [0, 0, lh, lh, 0], color=WHITE, lw=1.5, zorder=5)
        # Pilar quadrado
        pw1, ph1 = 30, 30
        px1, py1 = 80, 100
        r1 = mpatches.Rectangle((px1, py1), pw1, ph1, lw=1.5,
                                 edgecolor=RED, facecolor=BG, zorder=6)
        ax.add_patch(r1)
        ax.text(px1 + pw1/2, py1 - 15, 'P1 quad', ha='center', color=RED, fontsize=6,
                fontweight='bold')
        # Pilar retangular
        pw2, ph2 = 20, 40
        px2, py2 = 200, 120
        r2 = mpatches.Rectangle((px2, py2), pw2, ph2, lw=1.5,
                                 edgecolor=RED, facecolor=BG, zorder=6)
        ax.add_patch(r2)
        ax.text(px2 + pw2/2, py2 - 15, 'P2 ret', ha='center', color=RED, fontsize=6,
                fontweight='bold')
        # Pilar L
        px3, py3 = 320, 80
        ax.plot([px3, px3+30, px3+30, px3+15, px3+15, px3, px3],
                [py3, py3, py3+15, py3+15, py3+30, py3+30, py3],
                color=RED, lw=1.5, zorder=6)
        ax.fill([px3, px3+30, px3+30, px3+15, px3+15, px3, px3],
                [py3, py3, py3+15, py3+15, py3+30, py3+30, py3],
                color=BG, zorder=5)
        ax.text(px3 + 15, py3 - 15, 'P3 L', ha='center', color=RED, fontsize=6,
                fontweight='bold')
        ax.set_xlim(-30, lw + 30); ax.set_ylim(-30, lh + 30)

        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'RECORTES DE PILAR:', [
            '* Recorte = furo correspondente a secao pilar',
            '* Paineis cortados: ajuste minimo',
            '* Evitar pedacos < 10cm',
            '* Layer: Pilares (contorno do recorte)',
            '* VIGAS: recorte linear para travessia',
            '* Aberturas: mesmo tratamento + label',
        ])
        rodape(fig, 4, total, 'Recortes - Pilares e Aberturas')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 5: DECISION TREE LAJES ---
        print(f'  [Pg 5/{total}] Decision Tree Lajes')
        fig = fig_a3('PG 5 - ARVORE DE DECISAO: ROBO DE LAJES')
        ax = fig.add_axes([0.03, 0.08, 0.96, 0.82])
        ax.set_facecolor(BG); ax.axis('off')
        ax.set_xlim(0, 1000); ax.set_ylim(0, 580)

        # FLUXO 1: Tipo de painel por area
        ax.text(250, 560, 'FLUXO 1: Distribuicao de Paineis', color=ACCENT,
                fontsize=9, fontweight='bold', ha='center', zorder=10)
        draw_decision_box(ax, 130, 510, 220, 38, 'INPUT: largura_laje (mm)\ncomprimento_laje (mm)', color='#0d2040')
        draw_flow_arrow(ax, 350, 529, 400, 529)
        draw_decision_diamond(ax, 475, 529, 150, 46, 'larg\n> 3000mm?')
        draw_flow_arrow(ax, 550, 529, 620, 540, 'SIM')
        draw_decision_box(ax, 620, 523, 150, 34, 'dividir em\n2+ faixas', color='#1a3a1a', text_color=GREEN)
        draw_flow_arrow(ax, 475, 506, 475, 470, 'NAO')
        draw_decision_box(ax, 380, 452, 190, 34, 'faixa unica\nn=ceil(larg/220)', color='#1a2a4a', text_color=CYAN)

        # FLUXO 2: Recorte para pilares
        ax.text(250, 420, 'FLUXO 2: Recorte para Pilares', color=ACCENT,
                fontsize=9, fontweight='bold', ha='center', zorder=10)
        draw_decision_box(ax, 130, 375, 220, 38, 'INPUT: posicao_pilar\n(x, y, cw, ch)', color='#0d2040')
        draw_flow_arrow(ax, 350, 394, 400, 394)
        draw_decision_diamond(ax, 475, 394, 150, 46, 'pilar cruza\nborda laje?')
        draw_flow_arrow(ax, 550, 394, 620, 406, 'SIM')
        draw_decision_box(ax, 620, 390, 150, 34, 'recorte\nparcial', color='#3a1a1a', text_color=RED)
        draw_flow_arrow(ax, 475, 371, 475, 335, 'NAO')
        draw_decision_box(ax, 380, 317, 190, 34, 'recorte total\n(furo no painel)', color='#2a2a00', text_color=GOLD)

        # FLUXO 3: Sarrafo de Pressao
        ax.text(750, 560, 'FLUXO 3: Sarrafo de Pressao', color=ACCENT,
                fontsize=9, fontweight='bold', ha='center', zorder=10)
        draw_decision_box(ax, 630, 510, 200, 38, 'INPUT: perimetro\nda laje', color='#0d2040')
        draw_flow_arrow(ax, 830, 529, 860, 529)
        draw_decision_box(ax, 860, 512, 130, 34, 'SDP perimetral\n(sempre)', color='#2a1a3a', text_color=WHITE)

        # FLUXO 4: Unioes entre paineis
        ax.text(750, 420, 'FLUXO 4: Unioes', color=ACCENT,
                fontsize=9, fontweight='bold', ha='center', zorder=10)
        draw_decision_box(ax, 630, 375, 200, 38, 'INPUT: comprimento\ndo painel', color='#0d2040')
        draw_flow_arrow(ax, 830, 394, 860, 394)
        draw_decision_diamond(ax, 920, 394, 130, 46, 'comp\n> 1200mm?')
        draw_flow_arrow(ax, 985, 394, 1000, 406)
        draw_decision_box(ax, 860, 330, 130, 34, 'uniao com\nSARR_2.2x7', color='#1a3a1a', text_color=GREEN)
        draw_flow_arrow(ax, 920, 371, 920, 330)

        # Formula
        ax.text(100, 290, 'FORMULA DE DISTRIBUICAO:', color=ACCENT, fontsize=9,
                fontweight='bold', zorder=10)
        ax.text(100, 268, 'n = ceil(L / w_painel)   |   sobra = L - (n-1) x w', color=CYAN,
                fontsize=8, fontfamily='monospace', zorder=10,
                bbox=dict(facecolor='#050510', edgecolor='#335577', pad=6, lw=0.8))
        ax.text(100, 242, 'sobra < 50mm -> ajustar ultimo painel   |   sobra >= 50mm -> cortar novo painel',
                color=FG, fontsize=7.5, fontfamily='monospace', zorder=10)

        # Nomenclatura laje
        ax.text(100, 210, 'NOMENCLATURA DXF:', color=ACCENT, fontsize=9, fontweight='bold', zorder=10)
        ax.text(100, 188, 'L{n}  |  NS: {z_base}  |  Area: {m2}  |  paineis: [{P1,P2,...}]', color=CYAN,
                fontsize=8, fontfamily='monospace', zorder=10,
                bbox=dict(facecolor='#050510', edgecolor='#335577', pad=6, lw=0.8))

        # Tolerancias
        ax.text(600, 290, 'TOLERANCIAS LAJE:', color=ACCENT, fontsize=9, fontweight='bold', zorder=10)
        tols_lj = [
            'Folga painel-viga: 5-10mm',
            'Recorte pilar: +5mm folga cada lado',
            'Sobra minima painel: 50mm',
            'Sarrafo de pressao: perimetral sempre',
            'Painel min. reaproveitado: 100mm',
        ]
        for i, t in enumerate(tols_lj):
            ax.text(600, 268 - i*22, f'* {t}', color=FG, fontsize=7.5, zorder=10)

        # Tabela de reaproveitamento na base da pagina
        ax.text(100, 148, 'REAPROVEITAMENTO DE PAINEIS (LAJE):', color=ACCENT,
                fontsize=9, fontweight='bold', zorder=10)
        hdr_reap = 'Estado      | Condicao              | Uso                | Min.'
        ax.text(100, 128, hdr_reap, color=ACCENT, fontsize=7.5, fontfamily='monospace', zorder=10,
                bbox=dict(facecolor='#050510', edgecolor='#224433', pad=4, lw=0.8))
        reaprv_rows = [
            ('BOM        ', '| Sem dano visivel     ', '| Reuso direto       ', '| >100mm', GREEN),
            ('REGULAR    ', '| Arranhoes/marcas     ', '| Cortar e reusar    ', '| >100mm', GOLD),
            ('RUIM       ', '| Furo/quebra parcial  ', '| Preenchimento      ', '| >80mm', YELLOW),
            ('DESCARTE   ', '| Dano estrutural      ', '| Descartar          ', '| -', RED),
        ]
        for i, (estado, cond, uso, dim, cor) in enumerate(reaprv_rows):
            ax.text(100, 108 - i*23, f'{estado}{cond}{uso}{dim}',
                    color=cor, fontsize=7, fontfamily='monospace', zorder=10)

        rodape(fig, 5, total, 'Decision Tree - Robo de Lajes')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 6: SARRAFO DE PRESSAO NA LAJE ---
        print(f'  [Pg 6/{total}] Sarrafo de Pressao na Laje')
        fig = fig_a3('PG 6 - SARRAFO DE PRESSAO NA LAJE')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        setup_ax(ax, 'Laje com Sarrafo de Pressao Perimetral')
        lw, lh = 400, 300
        draw_painel(ax, 0, 0, lw, lh, GRAY, hatch=False, alpha=0.5)
        # SARRAFO DE PRESSAO perimetral
        for (x1, y1, x2, y2) in [
            (0, 0, lw, 0), (0, lh, lw, lh),
            (0, 0, 0, lh), (lw, 0, lw, lh),
        ]:
            ax.plot([x1, x2], [y1, y2], color=DGRAY, lw=2.5, linestyle='--', zorder=5)
        ax.text(lw/2, -20, 'SARRAFO DE PRESSAO', ha='center', color=DGRAY, fontsize=7,
                fontweight='bold')
        ax.set_xlim(-40, lw + 40); ax.set_ylim(-40, lh + 40)

        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'SARRAFO DE PRESSAO:', [
            '* Perimetral em todas as bordas livres',
            '* Trava lateral dos paineis',
            '* Layer: SARRAFO DE PRESSAO (DASHED)',
            '* Largura: 22mm (2.2cm)',
            '* Distancia da borda: 0',
        ])
        rodape(fig, 6, total, 'Sarrafo de Pressao na Laje')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 7: UNIOES ENTRE PAINEIS ---
        print(f'  [Pg 7/{total}] Unioes entre Paineis')
        fig = fig_a3('PG 7 - UNIOES ENTRE PAINEIS')
        union_types = [
            ('Simples (topo a topo)', 'uniao_simples'),
            ('Em T (3 paineis)', 'uniao_t'),
            ('Em L (canto)', 'uniao_l'),
            ('Com pilar (recortado)', 'uniao_pilar'),
        ]
        for idx, (label, tipo) in enumerate(union_types):
            row, col = idx // 2, idx % 2
            ax = fig.add_axes([0.05 + col * 0.48, 0.08 + (1 - row) * 0.44, 0.42, 0.40])
            setup_ax(ax, label)
            if tipo == 'uniao_simples':
                draw_painel(ax, 0, 0, 80, 60, GRAY, hatch=False)
                draw_painel(ax, 85, 0, 80, 60, GRAY, hatch=False)
                draw_sarrafo(ax, 80, 0, 5, 60, GOLD)
                ax.set_xlim(-10, 175); ax.set_ylim(-10, 70)
            elif tipo == 'uniao_t':
                draw_painel(ax, 0, 0, 80, 40, GRAY, hatch=False)
                draw_painel(ax, 85, 0, 80, 40, GRAY, hatch=False)
                draw_painel(ax, 40, 45, 80, 40, '#6688aa', hatch=False)
                draw_sarrafo(ax, 80, 0, 5, 40, GOLD)
                ax.set_xlim(-10, 175); ax.set_ylim(-10, 90)
            elif tipo == 'uniao_l':
                draw_painel(ax, 0, 0, 80, 40, GRAY, hatch=False)
                draw_painel(ax, 0, 45, 40, 60, '#6688aa', hatch=False)
                ax.set_xlim(-10, 100); ax.set_ylim(-10, 110)
            else:
                draw_painel(ax, 0, 0, 120, 80, GRAY, hatch=False, alpha=0.4)
                r = mpatches.Rectangle((40, 25), 30, 30, lw=1.5,
                                       edgecolor=RED, facecolor=BG, zorder=6)
                ax.add_patch(r)
                ax.text(55, 20, 'P', ha='center', color=RED, fontsize=7, fontweight='bold')
                ax.set_xlim(-10, 130); ax.set_ylim(-10, 90)
        rodape(fig, 7, total, 'Unioes entre Paineis')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 8: REAPROVEITAMENTO ---
        print(f'  [Pg 8/{total}] Reaproveitamento de Paineis')
        fig = fig_a3('PG 8 - REAPROVEITAMENTO DE PAINEIS')
        ax = fig.add_axes([0.05, 0.15, 0.55, 0.75])
        render_dxf_zona(ax, LJ_1, crop=LJ_AREA_ALL,
                        show_layers=['REAPROVEITAMENTO', 'Pain\u00e9is', 'Paineis'],
                        title='Layer REAPROVEITAMENTO - ALIMONTI LJ')
        ax2 = fig.add_axes([0.62, 0.15, 0.35, 0.75])
        ax2.set_facecolor(BG); ax2.axis('off')
        tabela_regras(ax2, 0.05, 0.95, 'REAPROVEITAMENTO:', [
            '* Layer: REAPROVEITAMENTO (ACI=2, amarelo)',
            '* Paineis marcados para reutilizacao',
            '* Posicao indica onde reusar',
            '* Hachura ANSI31 em amarelo',
            '* Identifica economia de material',
        ])
        rodape(fig, 8, total, 'Reaproveitamento de Paineis')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 9: COMPARACAO 3 OBRAS ---
        print(f'  [Pg 9/{total}] Comparacao 3 Obras (LJ)')
        fig = fig_a3('PG 9 - COMPARACAO 3 OBRAS (LAJES)')
        lj_files = [(LJ_1, 'ALIMONTI'), (LJ_2, 'GWT'), (LJ_3, 'LEAF')]
        for idx, (path, name) in enumerate(lj_files):
            ax = fig.add_axes([0.05 + idx * 0.32, 0.15, 0.28, 0.75])
            render_dxf_zona(ax, path, title=f'{name} - LJ')
        rodape(fig, 9, total, 'Comparacao 3 Obras - Lajes')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 10: LAYER INDEX + CAMPOS DO ROBO + JSON SCHEMA ---
        print(f'  [Pg 10/{total}] Layer Index + Campos do Robo + JSON Schema')
        fig = fig_a3('PG 10 - LAYER INDEX DA LAJE + CAMPOS DO ROBO')
        ax = fig.add_axes([0.05, 0.55, 0.48, 0.35])
        ax.set_facecolor(BG); ax.axis('off')
        tabela_dados(ax, 0.05, 0.90,
                     ['Layer', 'Cor', 'Entidade', 'Funcao'],
                     [['Paineis', 'cinza', 'LWPOLY+HATCH', 'Paineis de madeira'],
                      ['Pilares', 'cinza', 'LWPOLY', 'Contorno pilares'],
                      ['VIGAS', 'cinza', 'LWPOLY', 'Contorno vigas'],
                      ['SARRAFO DE PRESSAO', 'cinza dashed', 'LINE', 'Trava perimetral'],
                      ['REAPROVEITAMENTO', 'amarelo', 'LWPOLY+HATCH', 'Paineis reusados'],
                      ['COTA', 'ciano', 'DIMENSION', 'Dimensionamentos'],
                      ['Hachura', 'cinza', 'HATCH ANSI31', 'Hachura madeira'],
                      ['00 - FELIPE', 'amarelo', 'TEXT', 'Labels paineis']],
                     col_widths=[0.22, 0.15, 0.18, 0.30])

        ax2 = fig.add_axes([0.05, 0.08, 0.48, 0.40])
        ax2.set_facecolor(BG); ax2.axis('off')
        ax2.text(0.05, 0.95, 'PARAMETROS DO ROBO - LAJES:', color=ACCENT,
                 fontsize=9, fontweight='bold', fontfamily='monospace',
                 transform=ax2.transAxes)
        params_l = [
            ('laje_id', 'str', 'LB1', 'ID da laje'),
            ('area_m2', 'float', '24.5', 'Area total em m2'),
            ('nivel', 'float', '778.92', 'Cota Z do fundo'),
            ('esp_laje', 'int mm', '150', 'Espessura da laje'),
            ('tipo_painel', 'str', 'PA-050x100', 'Painel principal'),
            ('com_reaprov', 'bool', 'True', 'Marcar reaproveitamento?'),
            ('pilares_ids', 'list', '[P1,P2]', 'Pilares que cortam'),
            ('vigas_ids', 'list', '[V1,V2]', 'Vigas que cortam'),
        ]
        tabela_dados(ax2, 0.05, 0.82, ['Campo', 'Tipo', 'Exemplo', 'Descricao'],
                     [[p[0], p[1], p[2], p[3]] for p in params_l],
                     col_widths=[0.20, 0.12, 0.18, 0.35])
        # Dimensoes tipicas e regras de reaproveitamento
        ax2.text(0.05, 0.52, 'DIMENSOES TIPICAS:', color=ACCENT, fontsize=7.5,
                 fontweight='bold', fontfamily='monospace', transform=ax2.transAxes, zorder=10)
        tabela_dados(ax2, 0.05, 0.49,
            ['Tipo', 'Largura', 'Painel', 'Faixas'],
            [['PEQUENA', '< 3000mm', 'PA-050x100', '1 faixa'],
             ['MEDIA',   '3-5000mm', 'PA-050x100', '2+ faixas'],
             ['GRANDE',  '> 5000mm', 'PA-050x150', '3+ faixas']],
            col_widths=[0.16, 0.18, 0.20, 0.18])
        ax2.text(0.05, 0.33, 'REAPROVEITAMENTO:', color=ACCENT, fontsize=7.5,
                 fontweight='bold', fontfamily='monospace', transform=ax2.transAxes, zorder=10)
        reaprv_lines = [
            ('BOM     — sem dano: reuso direto (layer REAPROV.)', GREEN),
            ('REGULAR — arranhoes: cortar e reusar se > 100mm', GOLD),
            ('RUIM    — furo/quebra: usar como preenchimento', YELLOW),
            ('DESCARTE— dano estrutural: nao reusar', RED),
        ]
        for i, (line, cor) in enumerate(reaprv_lines):
            ax2.text(0.05, 0.28 - i * 0.068, f'* {line}', color=cor, fontsize=6.5,
                     fontfamily='monospace', transform=ax2.transAxes, zorder=10)
        # JSON schema visual para lajes (metade direita)
        ax_lj10b = fig.add_axes([0.52, 0.08, 0.46, 0.82])
        ax_lj10b.set_facecolor(BG); ax_lj10b.axis('off')
        draw_json_schema(ax_lj10b, 0.02, 0.97, 'laje.json (schema)',
            [
                ('laje_id',        '"str"',    '"L1"',      True),
                ('largura_laje',   'int (mm)', '3000',      True),
                ('comprimento_laje','int (mm)','4800',      True),
                ('tipo_painel',    '"str"',    '"sarr"',    True),
                ('esp_painel',     'int (mm)', '22',        True),
                ('sarrafo_tipo',   '"str"',    '"SARR_2.2x7"', True),
                ('pilares_recorte','list',     '[{"x":200,"y":300}]', False),
                ('nivel_laje',     'float',    '1002.92',   False),
                ('orientacao',     '"h"|"v"',  '"h"',       False),
            ], w=0.96)
        rodape(fig, 10, total, 'Layer Index + Campos do Robo')
        pdf.savefig(fig); plt.close(fig)

        # --- Pg 11-15: EXEMPLOS COM ZOOM E ANOTACOES ---
        lj_zoom_pages = [
            (11, LJ_1, (4000, 1800, 5000, 2500), 'Encontro Laje+Pilar (recorte)', [
                ('Recorte pilar', (4500, 2100), (4800, 2300), RED),
            ]),
            (12, LJ_1, (3500, 2200, 4500, 2800), 'Borda de laje (Sarrafo Pressao)', [
                ('Sarrafo Pressao', (3800, 2600), (3600, 2400), DGRAY),
            ]),
            (13, LJ_1, LJ_AREA_ALL, 'Area de Reaproveitamento', [
                ('REAPROVEITAMENTO', (5500, 2000), (6000, 2400), YELLOW),
            ]),
            (14, LJ_1, LJ_AREA_ALL, 'Cotas e Dimensionamentos (Layer COTA)', []),
            (15, LJ_1, LJ_AREA_ALL, 'Sintese - Laje completa + todos layers', [
                ('Paineis', (5000, 2000), (5500, 1700), GRAY),
                ('SARRAFO PRESSAO', (3600, 2600), (3600, 2800), DGRAY),
                ('REAPROVEITAMENTO', (6000, 2000), (6500, 2300), YELLOW),
                ('COTA', (4500, 2500), (4500, 2700), CYAN),
            ]),
        ]
        for pg, dxf_path, crop, title, annots in lj_zoom_pages:
            print(f'  [Pg {pg}/{total}] Exemplo LJ - {title}')
            fig = fig_a3(f'PG {pg} - {title.upper()}')
            ax = fig.add_axes([0.05, 0.08, 0.9, 0.82])
            if pg == 14:
                render_dxf_zona(ax, dxf_path, crop=crop,
                                show_layers=['COTA', 'cotas'], title=title)
            else:
                render_dxf_zona(ax, dxf_path, crop=crop, title=title)
            for (txt, xy_a, xy_t, c) in annots:
                annotate_arrow(ax, txt, xy_a, xy_t, c)
            rodape(fig, pg, total, f'Exemplo LJ - {title}')
            pdf.savefig(fig); plt.close(fig)

    print(f'  Salvo: {pdf_path}')


# ==========================================================================
# MAIN
# ==========================================================================
def main():
    print('=' * 60)
    print('GERACAO DE FICHAS INSTRUTIVAS TECNICAS')
    print(f'Data: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    out1 = OUT_DIR / 'fichas_pilares_instrutivas.pdf'
    out2 = OUT_DIR / 'fichas_vigas_instrutivas.pdf'
    out3 = OUT_DIR / 'fichas_lajes_instrutivas.pdf'

    print(f'\n[PDF 1/3] Pilares ({out1.name})')
    try:
        gerar_pilares(out1)
    except Exception as exc:
        print(f'  ERRO gerando pilares: {exc}')
        traceback.print_exc()

    print(f'\n[PDF 2/3] Vigas ({out2.name})')
    try:
        gerar_vigas(out2)
    except Exception as exc:
        print(f'  ERRO gerando vigas: {exc}')
        traceback.print_exc()

    print(f'\n[PDF 3/3] Lajes ({out3.name})')
    try:
        gerar_lajes(out3)
    except Exception as exc:
        print(f'  ERRO gerando lajes: {exc}')
        traceback.print_exc()

    print('\n' + '=' * 60)
    print('CONCLUIDO')
    print(f'  {out1}')
    print(f'  {out2}')
    print(f'  {out3}')
    print('=' * 60)


if __name__ == '__main__':
    main()
