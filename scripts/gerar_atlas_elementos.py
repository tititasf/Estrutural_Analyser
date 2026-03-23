#!/usr/bin/env python3
"""
Atlas Ilustrado de Elementos Estruturais — ~30 páginas
Casos visuais com setas, cotas, labels, sarrafos, garfos, lajes, vigas.
Executa: python scripts/gerar_atlas_elementos.py
"""
import sys, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, Wedge, Arc, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from pathlib import Path

OUT = Path(__file__).parent.parent / 'docs' / 'fichas' / 'atlas_elementos.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)

# ── Paleta ──────────────────────────────────────────────────────────────────
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

# ── Helpers ──────────────────────────────────────────────────────────────────
def new_fig(rows=1, cols=1, title=''):
    fig, axes = plt.subplots(rows, cols, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(0.5, 0.975, title, ha='center', va='top',
                 fontsize=13, color=TEXTO, fontweight='bold',
                 fontfamily='monospace')
    return fig, axes

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
    ax.text(x+w/2, y+h/2, txt, color=fc, fontsize=fs,
            ha='center', va='center',
            fontweight='bold' if bold else 'normal', zorder=5)

def cota(ax, x1, y1, x2, y2, label, fc=COTA_C, fs=7, off=0.25, voff=0):
    """Cota com setas duplas."""
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy)
    if L < 1e-6: return
    nx, ny = -dy/L*off, dx/L*off
    ax.annotate('', xy=(x2+nx, y2+ny), xytext=(x1+nx, y1+ny),
                arrowprops=dict(arrowstyle='<->', color=fc, lw=1.0), zorder=6)
    mx, my = (x1+x2)/2+nx*1.6+voff, (y1+y2)/2+ny*1.6+voff
    ax.text(mx, my, label, color=fc, fontsize=fs,
            ha='center', va='center', fontweight='bold', zorder=6,
            bbox=dict(facecolor=BG, alpha=0.7, pad=1, edgecolor='none'))

def arrow(ax, x1, y1, x2, y2, label='', fc=COTA_C, fs=6.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=fc, lw=1.1), zorder=6)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my, label, color=fc, fontsize=fs,
                ha='center', va='bottom', fontweight='bold', zorder=6,
                bbox=dict(facecolor=BG, alpha=0.75, pad=1.5, edgecolor='none'))

def rodape(fig, txt):
    fig.text(0.5, 0.01, txt, ha='center', va='bottom',
             fontsize=6.5, color=APOIO_C, style='italic')

def tag(ax, x, y, txt, fc=PILAR_C, fs=7):
    ax.text(x, y, txt, color=fc, fontsize=fs,
            ha='center', va='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=BG,
                      edgecolor=fc, lw=0.8, alpha=0.9), zorder=7)

# ═══════════════════════════════════════════════════════════════════════════
#  CAPA
# ═══════════════════════════════════════════════════════════════════════════
def page_capa(pdf):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG); ax.axis('off')

    # Título principal
    fig.text(0.5, 0.78, 'ATLAS DE ELEMENTOS', ha='center', va='center',
             fontsize=28, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.71, 'ESTRUTURAIS', ha='center', va='center',
             fontsize=28, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.62, 'CAD-ANALYZER v2.0', ha='center', va='center',
             fontsize=16, color=COTA_C, fontweight='bold')

    # Três ícones simbólicos lado a lado
    # Pilar (retângulo laranja)
    for xi, cor, nome in [(0.22, PILAR_C, 'PILARES'), (0.50, VIGA_C, 'VIGAS'), (0.78, LAJE_C, 'LAJES')]:
        r = mpatches.FancyBboxPatch((xi-0.07, 0.30), 0.14, 0.22,
            boxstyle='round,pad=0.01', linewidth=2,
            edgecolor=cor, facecolor=cor, alpha=0.2, transform=fig.transFigure)
        fig.add_artist(r)
        fig.text(xi, 0.415, nome, ha='center', va='center',
                 fontsize=11, color=cor, fontweight='bold')

    fig.text(0.5, 0.22,
             '10+ Casos por Elemento  ·  Sarrafos  ·  Garfos  ·  Painéis A/B/C/D\n'
             'Cambotados  ·  Grades de Laje  ·  Cortes  ·  Planificados',
             ha='center', va='center', fontsize=10, color=TEXTO, linespacing=1.8)

    fig.text(0.5, 0.06, 'Engenharia Civil — Formas de Concreto Armado',
             ha='center', va='center', fontsize=9, color=APOIO_C, style='italic')

    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-01: Simples Retangular com 4 Lados
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_01(pdf):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    setup(ax)
    ax.set_xlim(-4, 14); ax.set_ylim(-3, 13)

    fig.text(0.5, 0.97, 'PILAR — P-01: Simples Retangular (B=46cm H=56cm)', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Identificação dos 4 lados e orientação geográfica',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    B, H = 4.6, 5.6
    x0, y0 = 2.0, 2.5

    # Seção do pilar
    rct(ax, x0, y0, B, H, fc=PILAR_C, alpha=0.3, lw=2.5, ec=PILAR_C)
    ax.text(x0+B/2, y0+H/2, 'PILAR\nP11', color=PILAR_C,
            ha='center', va='center', fontsize=11, fontweight='bold', zorder=5)

    # Lado A — topo/Norte
    rct(ax, x0, y0+H, B, 0.85, fc=PAINEL, ec='white', lw=1.5)
    lbl(ax, x0, y0+H, B, 0.85, 'A', fc=BG, fs=11)
    arrow(ax, x0+B+0.5, y0+H+0.42, x0+B+0.1, y0+H+0.42, '', PAINEL)
    ax.text(x0+B+0.6, y0+H+0.42, 'LADO A — Norte/Topo\nlargura = B = 46 cm',
            color=PAINEL, fontsize=7.5, va='center')

    # Lado B — direita/Leste
    rct(ax, x0+B, y0, 0.85, H, fc='#d4a030', ec='white', lw=1.5)
    lbl(ax, x0+B, y0, 0.85, H, 'B', fc=BG, fs=11)
    arrow(ax, x0+B+0.85+0.4, y0+H*0.7, x0+B+0.85+0.1, y0+H*0.7, '', '#d4a030')
    ax.text(x0+B+0.85+0.5, y0+H*0.7, 'LADO B — Leste/Direita\nlargura = H = 56 cm',
            color='#d4a030', fontsize=7.5, va='center')

    # Lado C — base/Sul
    rct(ax, x0, y0-0.85, B, 0.85, fc='#c8960a', ec='white', lw=1.5)
    lbl(ax, x0, y0-0.85, B, 0.85, 'C', fc=BG, fs=11)
    arrow(ax, x0+B+0.5, y0-0.42, x0+B+0.1, y0-0.42, '', '#c8960a')
    ax.text(x0+B+0.6, y0-0.42, 'LADO C — Sul/Base\nlargura = B = 46 cm',
            color='#c8960a', fontsize=7.5, va='center')

    # Lado D — esquerda/Oeste
    rct(ax, x0-0.85, y0, 0.85, H, fc='#b87820', ec='white', lw=1.5)
    lbl(ax, x0-0.85, y0, 0.85, H, 'D', fc=BG, fs=11)
    arrow(ax, x0-0.85-0.5, y0+H*0.3, x0-0.85-0.1, y0+H*0.3, '', '#b87820')
    ax.text(x0-0.85-0.6, y0+H*0.3, 'LADO D\nOeste/Esq\nH=56cm',
            color='#b87820', fontsize=7.5, va='center', ha='right')

    # Cotas
    cota(ax, x0, y0-2.0, x0+B, y0-2.0, 'B = 46 cm', off=0)
    cota(ax, x0+B+3.8, y0, x0+B+3.8, y0+H, 'H = 56 cm', off=0)

    # Rosa dos ventos
    cx, cy = x0+B/2, y0+H+2.5
    for ang, ltr, cor in [(90,'N',WARN),(0,'E',COTA_C),(270,'S',COTA_C),(180,'O',COTA_C)]:
        rad = math.radians(ang)
        ax.annotate('', xy=(cx+math.cos(rad)*0.6, cy+math.sin(rad)*0.6),
                    xytext=(cx, cy),
                    arrowprops=dict(arrowstyle='->', color=cor, lw=1.3))
        ax.text(cx+math.cos(rad)*0.9, cy+math.sin(rad)*0.9, ltr,
                color=cor, fontsize=8, ha='center', va='center', fontweight='bold')

    # Legenda
    leg_y = -1.5
    for i, (cor, txt) in enumerate([(PAINEL,'Painel de forma (madeira)'),
                                     (PILAR_C,'Seção do pilar'),
                                     (COTA_C,'Cotas dimensionais')]):
        ax.add_patch(mpatches.Rectangle((0.5+i*4, leg_y), 0.5, 0.3,
                     facecolor=cor, alpha=0.8, edgecolor='white', lw=0.5))
        ax.text(1.1+i*4, leg_y+0.15, txt, color=TEXTO, fontsize=6.5, va='center')

    rodape(fig, 'P-01 | Pilar retangular simples — lados A=Norte B=Leste C=Sul D=Oeste')
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-02: Painéis Planificados A/B/C/D com Sarrafos e Fiadas
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_02(pdf):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    setup(ax)
    ax.set_xlim(-0.5, 10.5); ax.set_ylim(-0.8, 3.5)

    fig.text(0.5, 0.97, 'PILAR — P-02: Painéis Planificados A/B/C/D', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Pé-Direito=280cm → 3 fiadas: fundo 2cm | meio 244cm | topo 34cm  ·  sarrafos a cada 61cm',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    paineis = [
        ('A', 0.46, PAINEL),
        ('B', 0.56, '#d4a030'),
        ('C', 0.46, '#c8960a'),
        ('D', 0.56, '#b87820'),
    ]
    gap = 0.25
    x = 0.3

    fiadas_cor = ['#555', PAINEL, '#888']
    fiadas_alt = [0.02, 2.44, 0.34]
    fiadas_nom = ['fundo\n2cm', 'meio\n244cm', 'topo\n34cm']

    for pname, larg, cor in paineis:
        fiadas_cor[1] = cor
        y = 0
        for fh, fc, fn in zip(fiadas_alt, fiadas_cor, fiadas_nom):
            rct(ax, x, y, larg, fh, fc=fc, ec='white', lw=0.8, alpha=0.9)
            if fh > 0.15:
                lbl(ax, x, y, larg, fh, fn, fc=TEXTO, fs=6)
            else:
                lbl(ax, x, y, larg, fh, fn.replace('\n',' '), fc=TEXTO, fs=5)
            y += fh

        # Sarrafos (réguas horizontais tracejadas no painel meio)
        for sy in [0.02+0.61, 0.02+1.22, 0.02+1.83]:
            ax.plot([x, x+larg], [sy, sy], '--', color=SARRAFO, lw=1.0, alpha=0.85, zorder=4)

        # Label painel abaixo
        ax.text(x+larg/2, -0.12, f'PAINEL {pname}\n{larg*100:.0f} cm',
                ha='center', va='top', fontsize=8, color=cor, fontweight='bold')

        # Cota largura
        cota(ax, x, -0.55, x+larg, -0.55, f'{larg*100:.0f}cm', off=0, fs=6.5)
        x += larg + gap

    # Cota altura total (pé-direito)
    cota(ax, x+0.2, 0, x+0.2, 2.80, 'PE=280cm', off=0)

    # Legenda sarrafo
    ax.plot([7.0, 7.6], [1.22, 1.22], '--', color=SARRAFO, lw=1.0)
    ax.text(7.7, 1.22, 'Sarrafo (≈61cm spacing)', color=SARRAFO,
            fontsize=7, va='center')

    # Nota técnica
    fig.text(0.1, 0.08,
             '• MAX_PAINEL_LARGURA = 244 cm → painéis maiores são auto-divididos\n'
             '• Sarrafos posicionados a cada 61 cm (LAJE_GRID_STEP ÷ 2)\n'
             '• Fiada FUNDO = 2cm (base de assentamento)\n'
             '• Fiada TOPO = PE_DIREITO − 244 − 2 = 34cm (complemento)',
             va='bottom', fontsize=7.5, color=TEXTO,
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=6))

    rodape(fig, 'P-02 | Planificação de painéis — fiadas e sarrafos por pé-direito')
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-03: Pilar Cambotado (com arcos/bulges)
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_03(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'PILAR — P-03: Pilar Cambotado (Arcos/Bulges)', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'LWPOLYLINE com bulge ≠ 0 → has_arcs=True → cambotado detectado',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Esquerda: seção transversal com arco
    ax = axes[0]
    setup(ax, 'Seção Transversal — Pilar Cambotado')
    ax.set_xlim(-1.5, 6.5); ax.set_ylim(-1, 7)

    # Pilar com lado arredondado (cambotado)
    theta = np.linspace(np.pi/2, -np.pi/2, 60)
    r = 2.0
    xs = np.concatenate([[0], [0], r*np.cos(theta)+0])
    ys = np.concatenate([[0], [4.0], r*np.sin(theta)+2.0])
    # Desenho do pilar cambotado
    ax.fill([0, 0] + list(r*np.cos(theta)) + [0],
            [0, 4.0] + list(r*np.sin(theta)+2.0) + [0],
            color=PILAR_C, alpha=0.3, zorder=2)
    ax.plot([0, 0], [0, 4.0], color=PILAR_C, lw=2.5, zorder=3)
    th = np.linspace(np.pi/2, -np.pi/2, 60)
    ax.plot(r*np.cos(th), r*np.sin(th)+2.0, color=ARCO_C, lw=2.5, zorder=3)
    ax.plot([0, r*np.cos(np.pi/2)], [4.0, 4.0], color=PILAR_C, lw=2.0)
    ax.plot([0, r*np.cos(-np.pi/2)], [0, 0], color=PILAR_C, lw=2.0)

    # Seta indicando o arco
    arrow(ax, 3.5, 3.5, 2.1, 2.5, 'Arco cambotado\n(bulge > 0)', ARCO_C, fs=7)

    # Painel cambotado (amarelo, segue o arco)
    th2 = np.linspace(np.pi/2, -np.pi/2, 60)
    r2 = r + 0.3
    ax.plot(r2*np.cos(th2), r2*np.sin(th2)+2.0, color=PAINEL, lw=4.0, alpha=0.8, zorder=4)
    ax.text(r2+0.4, 2.0, 'Painel\ncambotado', color=PAINEL, fontsize=7, va='center')

    cota(ax, -0.8, 0, -0.8, 4.0, 'H=56cm', off=0)
    cota(ax, 0, -0.6, r, -0.6, 'R=B/2=23cm', off=0, fs=6)

    ax.text(0.5, 2.0, 'PILAR\nCAMBOTADO', color=PILAR_C,
            ha='center', va='center', fontsize=8, fontweight='bold')

    # Direita: explicação do bulge
    ax2 = axes[1]
    setup(ax2, 'Detecção de Bulge — LWPOLYLINE')
    ax2.set_xlim(-0.5, 5); ax2.set_ylim(-0.5, 7)

    # Mostrar segmentos com bulge
    segs = [(0.5, 1.0, 0.0, 'bulge=0\n(reta)'),
            (0.5, 2.5, 0.5, 'bulge=0.5\n(arco leve)'),
            (0.5, 4.0, 1.0, 'bulge=1.0\n(semicírculo)'),
            (0.5, 5.5, -1.0, 'bulge=-1.0\n(arco invertido)')]

    for x_start, y_pos, bulge, lbl_txt in segs:
        x_end = x_start + 2.0
        if abs(bulge) < 0.05:
            ax2.plot([x_start, x_end], [y_pos, y_pos], color=GRADE, lw=2)
        else:
            # Aproximação visual do arco
            t = np.linspace(0, np.pi, 40) if bulge > 0 else np.linspace(np.pi, 2*np.pi, 40)
            cx = (x_start+x_end)/2
            chord = x_end - x_start
            sagitta = bulge * chord / 2
            rx = chord / 2
            ry = abs(sagitta)
            xs_arc = cx + rx*np.cos(t if bulge < 0 else -t)
            ys_arc = y_pos + ry*np.sin(t if bulge > 0 else -t) * np.sign(bulge)
            color_arc = ARCO_C if abs(bulge) > 0.1 else GRADE
            ax2.plot(xs_arc, ys_arc, color=color_arc, lw=2.5)
        ax2.plot([x_start, x_end], [y_pos, y_pos], 'o', color=COTA_C,
                 ms=4, zorder=5)
        ax2.text(x_end+0.2, y_pos, lbl_txt, color=TEXTO,
                 fontsize=7, va='center')

    ax2.text(2.5, 0.1, 'get_points("xyzsb")[4] → bulge por vértice',
             color=APOIO_C, fontsize=7, ha='center', style='italic')

    # Código de detecção
    fig.text(0.08, 0.06,
             'Detecção:\n'
             '  bulges = [v[4] for v in ent.get_points("xyzsb")]\n'
             '  has_arcs = any(abs(b) > 0.01 for b in bulges)\n'
             '  max_bulge = max(abs(b) for b in bulges)\n'
             '  tipo = "cambotado" if has_arcs else "retangular"',
             va='bottom', fontsize=7.5, color=VERDE, fontfamily='monospace',
             bbox=dict(facecolor='#0d1117', edgecolor=GRADE, lw=0.8, pad=6))

    rodape(fig, 'P-03 | Pilar cambotado — detecção de arcos via bulge em LWPOLYLINE')
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-04: Adjacências (Lajes e Vigas nos 4 lados)
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_04(pdf):
    fig, axes = plt.subplots(2, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'PILAR — P-04: Configurações de Adjacência', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Pilar interno (4 lajes) · canto (2 lajes) · borda (1 laje) · isolado (0 lajes)',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    configs = [
        ('Pilar Interno\n4 lajes adjacentes', [(0,1),(1,0),(0,-1),(-1,0)], 'INTERNO'),
        ('Pilar de Canto\n2 lajes (NE)', [(0,1),(1,0)], 'CANTO'),
        ('Pilar de Borda\n1 laje (Norte)', [(0,1)], 'BORDA'),
        ('Pilar Isolado\n0 lajes', [], 'ISOLADO'),
    ]

    for (title, lajes_dirs, tipo), ax in zip(configs, axes.flat):
        setup(ax, title)
        ax.set_xlim(-3.5, 3.5); ax.set_ylim(-3.5, 3.5)

        B, H = 1.2, 1.4
        # Pilar central
        rct(ax, -B/2, -H/2, B, H, fc=PILAR_C, alpha=0.4, ec=PILAR_C, lw=2)
        ax.text(0, 0, tipo, color=PILAR_C, ha='center', va='center',
                fontsize=7, fontweight='bold')

        # Lajes adjacentes
        for dx, dy in lajes_dirs:
            if dx == 0 and dy == 1:  # Norte
                rct(ax, -1.5, H/2, 3.0, 1.2, fc=LAJE_ADJ, alpha=0.4, ec=LAJE_ADJ, lw=1.5)
                ax.text(0, H/2+0.6, 'LAJE', color=LAJE_ADJ, ha='center', va='center', fontsize=6.5)
            elif dx == 1 and dy == 0:  # Leste
                rct(ax, B/2, -1.5, 1.5, 3.0, fc=LAJE_ADJ, alpha=0.4, ec=LAJE_ADJ, lw=1.5)
                ax.text(B/2+0.75, 0, 'LAJE', color=LAJE_ADJ, ha='center', va='center', fontsize=6.5)
            elif dx == 0 and dy == -1:  # Sul
                rct(ax, -1.5, -H/2-1.2, 3.0, 1.2, fc=LAJE_ADJ, alpha=0.4, ec=LAJE_ADJ, lw=1.5)
                ax.text(0, -H/2-0.6, 'LAJE', color=LAJE_ADJ, ha='center', va='center', fontsize=6.5)
            elif dx == -1 and dy == 0:  # Oeste
                rct(ax, -B/2-1.5, -1.5, 1.5, 3.0, fc=LAJE_ADJ, alpha=0.4, ec=LAJE_ADJ, lw=1.5)
                ax.text(-B/2-0.75, 0, 'LAJE', color=LAJE_ADJ, ha='center', va='center', fontsize=6.5)

        # Vigas entre pilar e lajes
        for dx, dy in lajes_dirs:
            if dx == 0 and dy == 1:
                rct(ax, -0.2, H/2, 0.4, 1.2, fc=VIGA_ADJ, alpha=0.6, ec=VIGA_ADJ, lw=1)
            elif dx == 1 and dy == 0:
                rct(ax, B/2, -0.15, 1.5, 0.3, fc=VIGA_ADJ, alpha=0.6, ec=VIGA_ADJ, lw=1)
            elif dx == 0 and dy == -1:
                rct(ax, -0.2, -H/2-1.2, 0.4, 1.2, fc=VIGA_ADJ, alpha=0.6, ec=VIGA_ADJ, lw=1)
            elif dx == -1 and dy == 0:
                rct(ax, -B/2-1.5, -0.15, 1.5, 0.3, fc=VIGA_ADJ, alpha=0.6, ec=VIGA_ADJ, lw=1)

        n = len(lajes_dirs)
        ax.text(0, -3.0, f'n_lajes={n} | lados_livres={4-n}', color=COTA_C,
                ha='center', va='center', fontsize=6.5)

    # Legenda comum
    handles = [mpatches.Patch(color=PILAR_C, alpha=0.5, label='Pilar'),
               mpatches.Patch(color=LAJE_ADJ, alpha=0.5, label='Laje adjacente'),
               mpatches.Patch(color=VIGA_ADJ, alpha=0.5, label='Viga de ligação')]
    fig.legend(handles=handles, loc='lower center', ncol=3,
               fontsize=7, facecolor=BG, framealpha=0.8,
               labelcolor=TEXTO, edgecolor=GRADE)

    rodape(fig, 'P-04 | Configurações de adjacência: interno, canto, borda, isolado')
    plt.tight_layout(rect=[0, 0.05, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-05: Garfos — Posicionamento e Geometria
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_05(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'PILAR — P-05: Garfos — Geometria e Posicionamento', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Garfos = encaixes de topo que suportam lajes sobre o pilar',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Esquerda: vista frontal de pilar com garfos
    ax = axes[0]
    setup(ax, 'Vista Frontal — Pilar com Garfos')
    ax.set_xlim(-1.5, 6); ax.set_ylim(-0.5, 8)

    # Pilar (corpo)
    rct(ax, 0, 0, 2.0, 6.0, fc=PILAR_C, alpha=0.3, ec=PILAR_C, lw=2)
    ax.text(1.0, 3.0, 'PILAR\nB=46\nH=56', color=PILAR_C,
            ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Painéis laterais
    rct(ax, -0.4, 0, 0.4, 6.0, fc=PAINEL, alpha=0.85, lw=1)
    lbl(ax, -0.4, 0, 0.4, 6.0, 'A', fc=BG, fs=9)
    rct(ax, 2.0, 0, 0.4, 6.0, fc=PAINEL, alpha=0.85, lw=1)
    lbl(ax, 2.0, 0, 0.4, 6.0, 'C', fc=BG, fs=9)

    # Garfos no topo (2 garfos: esq e dir)
    garfo_h = 0.8
    garfo_w = 0.3
    garfo_y = 6.0

    for gx, gl in [(-0.4, 'G.ESQ'), (2.0+0.1, 'G.DIR')]:
        rct(ax, gx, garfo_y, garfo_w, garfo_h, fc=GARFO_C, alpha=0.9, ec='white', lw=1.5)
        ax.text(gx+garfo_w/2, garfo_y+garfo_h+0.15, gl,
                color=GARFO_C, fontsize=6.5, ha='center', va='bottom', fontweight='bold')

    # Laje suportada no topo
    rct(ax, -0.8, garfo_y+garfo_h, 3.8, 0.5, fc=LAJE_ADJ, alpha=0.4, ec=LAJE_ADJ, lw=1.5)
    ax.text(1.0, garfo_y+garfo_h+0.25, 'LAJE SUPERIOR', color=LAJE_ADJ,
            ha='center', va='center', fontsize=7)

    # Espessura laje
    cota(ax, 3.5, garfo_y+garfo_h, 3.5, garfo_y+garfo_h+0.5,
         'h_laje\n=15cm', off=0, fs=6)
    cota(ax, 3.5, garfo_y, 3.5, garfo_y+garfo_h, 'garfo\n=h', off=0, fs=6)
    cota(ax, -1.0, 0, -1.0, 6.0, 'PE=280cm', off=0, fs=6.5)

    # Direita: esquema cálculo garfo
    ax2 = axes[1]
    setup(ax2, 'Cálculo — calcular_garfos()')
    ax2.set_xlim(-0.5, 6); ax2.set_ylim(-0.5, 8)

    # Fórmula visual
    formulas = [
        ('INPUTS:', COTA_C, 8, True),
        ('  sec_largura = B = 46 cm', TEXTO, 7, False),
        ('  sec_altura  = H = 56 cm', TEXTO, 7, False),
        ('  comprimento (viga) = L', TEXTO, 7, False),
        ('  pe_direito = 280 cm', TEXTO, 7, False),
        ('  espessura_laje = h', TEXTO, 7, False),
        ('', TEXTO, 7, False),
        ('OUTPUTS:', COTA_C, 8, True),
        ('  n_garfos = n_paineis_viga + 1', VERDE, 7, False),
        ('  altura_garfo = espessura_laje', GARFO_C, 7, False),
        ('  largura_garfo = sec_largura', GARFO_C, 7, False),
        ('  posicoes = ao longo de L', GARFO_C, 7, False),
        ('', TEXTO, 7, False),
        ('REGRA:', WARN, 8, True),
        ('  Garfo em CADA junta de painel', TEXTO, 7, False),
        ('  + início e fim da viga', TEXTO, 7, False),
        ('  Encaixes = l_viga / MAX_PAINEL', TEXTO, 7, False),
        ('  (MAX_PAINEL = 244 cm)', APOIO_C, 6.5, False),
    ]

    y_pos = 7.5
    for txt, cor, fs, bold in formulas:
        ax2.text(0.2, y_pos, txt, color=cor, fontsize=fs, va='top',
                 fontweight='bold' if bold else 'normal',
                 fontfamily='monospace')
        y_pos -= 0.38

    # Desenho simplificado: viga com garfos
    vy = 1.5
    vl = 5.0
    rct(ax2, 0, vy, vl, 0.4, fc=VIGA_C, alpha=0.3, ec=VIGA_C, lw=1.5)
    ax2.text(vl/2, vy+0.2, 'VIGA  L=518cm', color=VIGA_C,
             ha='center', va='center', fontsize=7)
    # Juntas de painéis
    for gx in [0, 2.44/5.18*vl, vl]:
        rct(ax2, gx-0.1, vy+0.4, 0.2, 0.5, fc=GARFO_C, alpha=0.9, lw=1)
    ax2.text(2.44/5.18*vl/2, vy-0.25, '← 244cm →', color=COTA_C,
             ha='center', fontsize=6.5)
    ax2.text(2.5, vy-0.5, 'garfo em cada junta de painel',
             color=GARFO_C, ha='center', fontsize=7, style='italic')

    rodape(fig, 'P-05 | Garfos — geometria, cálculo e posicionamento ao longo da viga')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-06: Vista 3D Isométrica Simplificada com Sarrafos
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_06(pdf):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    setup(ax)
    ax.set_xlim(-2, 12); ax.set_ylim(-2, 12)

    fig.text(0.5, 0.97, 'PILAR — P-06: Vista Isométrica 3D com Sarrafos', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Representação 3D simplificada: 4 painéis + sarrafos horizontais por fiada',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Projeção isométrica simplificada
    # Parâmetros do pilar
    B, H_s, PE = 2.0, 2.4, 8.0  # escala visual

    # Transformação isométrica
    def iso(x, y, z):
        ix = (x - y) * math.cos(math.radians(30))
        iy = (x + y) * math.sin(math.radians(30)) + z
        return ix + 5, iy + 1

    # Faces do pilar (4 painéis)
    face_defs = [
        # Face A (frente-norte): x varia 0→B, y=0, z varia 0→PE
        ('A', [(0,0,0),(B,0,0),(B,0,PE),(0,0,PE)], PAINEL),
        # Face B (direita-leste): x=B, y varia 0→H_s, z varia 0→PE
        ('B', [(B,0,0),(B,H_s,0),(B,H_s,PE),(B,0,PE)], '#d4a030'),
        # Face C (fundo-sul): x varia 0→B, y=H_s (atrás)
        ('C', [(0,H_s,0),(B,H_s,0),(B,H_s,PE),(0,H_s,PE)], '#c8960a'),
        # Face D (esquerda-oeste): x=0
        ('D', [(0,0,0),(0,H_s,0),(0,H_s,PE),(0,0,PE)], '#b87820'),
    ]

    # Desenhar faces (algumas ocultas na vista iso)
    for fname, pts, cor in [face_defs[0], face_defs[1], face_defs[3]]:
        iso_pts = [iso(x, y, z) for x,y,z in pts]
        xs = [p[0] for p in iso_pts]
        ys = [p[1] for p in iso_pts]
        ax.fill(xs, ys, color=cor, alpha=0.35, zorder=2)
        ax.plot(xs + [xs[0]], ys + [ys[0]], color=cor, lw=1.5, zorder=3)
        # Label face
        cx = sum(xs)/4; cy = sum(ys)/4
        ax.text(cx, cy, fname, color=cor, ha='center', va='center',
                fontsize=11, fontweight='bold', zorder=5)

    # Sarrafos (linhas horizontais nas faces visíveis)
    for z_sarrof in [2.0, 4.1, 6.1]:
        # Sarrafo Face A
        p1 = iso(0, 0, z_sarrof); p2 = iso(B, 0, z_sarrof)
        ax.plot([p1[0],p2[0]], [p1[1],p2[1]], '--', color=SARRAFO, lw=1.5, alpha=0.9, zorder=4)
        # Sarrafo Face B
        p1 = iso(B, 0, z_sarrof); p2 = iso(B, H_s, z_sarrof)
        ax.plot([p1[0],p2[0]], [p1[1],p2[1]], '--', color=SARRAFO, lw=1.5, alpha=0.9, zorder=4)

    # Label sarrafo
    sp = iso(B, H_s, 2.0)
    ax.text(sp[0]+0.3, sp[1], 'sarrafo', color=SARRAFO, fontsize=7, va='center')
    arrow(ax, sp[0]+0.3, sp[1]-0.1, sp[0]+0.05, sp[1]-0.05, '', SARRAFO)

    # Eixos
    ox, oy = iso(0,0,0)
    for dx, dy, dz, lbl_t, cor_e in [
        (3,0,0,'X (largura B)',COTA_C),
        (0,3,0,'Y (prof H)',COTA_C),
        (0,0,3,'Z (altura PE)',COTA_C)
    ]:
        ex, ey = iso(dx, dy, dz)
        ax.annotate('', xy=(ex, ey), xytext=(ox, oy),
                    arrowprops=dict(arrowstyle='->', color=cor_e, lw=1.2))
        ax.text(ex, ey, lbl_t, color=cor_e, fontsize=6.5, va='center')

    # Cotas
    p_b1 = iso(0,0,0); p_b2 = iso(B,0,0)
    cota(ax, p_b1[0], p_b1[1]-0.5, p_b2[0], p_b2[1]-0.5, 'B=46cm', off=0, fs=7)
    p_pe1 = iso(B,0,0); p_pe2 = iso(B,0,PE)
    ax.annotate('', xy=p_pe2, xytext=p_pe1,
                arrowprops=dict(arrowstyle='<->', color=COTA_C, lw=1))
    ax.text(p_pe2[0]+0.5, (p_pe1[1]+p_pe2[1])/2, 'PE=280cm',
            color=COTA_C, fontsize=7, va='center')

    rodape(fig, 'P-06 | Vista isométrica: 4 painéis A/B/C/D + sarrafos horizontais')
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PILAR — P-07: Seção Transversal Detalhada + Confidence Map
# ═══════════════════════════════════════════════════════════════════════════
def page_pilar_07(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'PILAR — P-07: Seção Transversal + Campos de Dados', ha='center',
             va='top', fontsize=11, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Todos os campos extraídos pelo pipeline + accuracy por campo',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Seção detalhada
    ax = axes[0]
    setup(ax, 'Seção Transversal — Campos Extraídos')
    ax.set_xlim(-3, 8); ax.set_ylim(-2, 8)

    B, H = 4.6, 5.6
    x0, y0 = 0, 0

    rct(ax, x0, y0, B, H, fc=PILAR_C, alpha=0.25, ec=PILAR_C, lw=2.5)

    # Armadura (círculos internos)
    for xi, yi in [(0.4,0.4),(4.2,0.4),(0.4,5.2),(4.2,5.2),(2.3,0.4),(2.3,5.2)]:
        circ = plt.Circle((x0+xi, y0+yi), 0.15, color=TEXTO, alpha=0.6, zorder=4)
        ax.add_patch(circ)

    # Dimensões com setas
    cota(ax, x0, y0-1.2, x0+B, y0-1.2, 'B = 46 cm', off=0)
    cota(ax, x0+B+1.5, y0, x0+B+1.5, y0+H, 'H = 56 cm', off=0)

    # Campos com setas
    campos_pos = [
        (x0-0.5, y0+H+0.5, 'name = "P11"', PAINEL),
        (x0-1.5, y0+H/2+1, 'type = "retangular"', COTA_C),
        (x0-1.5, y0+H/2-0.5, 'area = 2576 cm²', COTA_C),
        (x0+B+0.5, y0+H-1, 'pe_direito = 280cm', VERDE),
        (x0+B+0.3, y0+H/2-1.5, 'n_paineis = 4', VERDE),
    ]
    for cx, cy, lbl_t, cor in campos_pos:
        ax.text(cx, cy, lbl_t, color=cor, fontsize=6.5, ha='left',
                bbox=dict(facecolor=BG, alpha=0.7, edgecolor=cor, lw=0.5, pad=2))

    # Confidence map (barras horizontais)
    ax2 = axes[1]
    setup(ax2, 'Confidence Map — Accuracy por Campo')
    ax2.set_xlim(-0.5, 5); ax2.set_ylim(-0.5, 8)

    campos_conf = [
        ('name',      0.95, VERDE),
        ('type',      0.92, VERDE),
        ('dim B',     0.90, VERDE),
        ('dim H',     0.90, VERDE),
        ('area',      0.88, VERDE),
        ('pe_direito',0.80, VERDE),
        ('n_paineis', 0.78, '#f1c40f'),
        ('lado A viga',0.55,'#f1c40f'),
        ('lado B laje',0.34, WARN),
        ('links_json', 0.20, WARN),
    ]

    for i, (campo, conf, cor) in enumerate(campos_conf):
        y_bar = 7.2 - i*0.70
        # Barra de fundo
        rct(ax2, 0, y_bar-0.2, 4.0, 0.4, fc=GRADE, alpha=0.4, lw=0, ec='none')
        # Barra de confiança
        rct(ax2, 0, y_bar-0.2, 4.0*conf, 0.4, fc=cor, alpha=0.7, lw=0, ec='none')
        ax2.text(-0.1, y_bar, campo, color=TEXTO, fontsize=7,
                 ha='right', va='center', fontfamily='monospace')
        ax2.text(4.0*conf+0.1, y_bar, f'{conf:.0%}', color=cor, fontsize=7,
                 ha='left', va='center', fontweight='bold')

    # Legenda cores
    for i, (label, cor) in enumerate([('>80% OK', VERDE), ('50-80% MÉDIO', '#f1c40f'), ('<50% BAIXO', WARN)]):
        ax2.add_patch(mpatches.Rectangle((0.5+i*1.3, -0.3), 0.3, 0.2, facecolor=cor, alpha=0.7))
        ax2.text(0.85+i*1.3, -0.2, label, color=TEXTO, fontsize=6, va='center')

    rodape(fig, 'P-07 | Campos extraídos e confidence map por campo do pilar')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  VIGA — V-01: Anatomia Completa (Face A, B, Fundo)
# ═══════════════════════════════════════════════════════════════════════════
def page_viga_01(pdf):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    setup(ax)
    ax.set_xlim(-1.5, 13); ax.set_ylim(-3, 7)

    fig.text(0.5, 0.97, 'VIGA — V-01: Anatomia Completa (Face A + Face B + Fundo)', ha='center',
             va='top', fontsize=11, color=VIGA_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'V101 — b=15cm h=120cm L=518cm — 3 faces planificadas em linha',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Viga planificada: FaceA | FaceB | Fundo — cada face tem n_paineis
    L = 5.18   # metros → 518 cm
    b = 0.15   # 15 cm
    h = 1.20   # 120 cm
    n_paineis = 3  # ceil(518/244) = 3 painéis por face

    # Larguras de cada painel (último pode ser menor)
    painel_max = 2.44
    paineis_larg = []
    resto = L
    while resto > 0:
        paineis_larg.append(min(resto, painel_max))
        resto -= painel_max

    # Face A (lateral esquerda) — cor verde
    gap = 0.25
    x_cur = 0.0

    for face_nome, cor_face, h_face in [
        ('FACE A\n(Lateral Esq)', '#27ae60', h),
        ('FACE B\n(Lateral Dir)', '#2980b9', h),
        ('FUNDO', '#8e44ad', b),
    ]:
        x_start = x_cur
        for pi, pl in enumerate(paineis_larg):
            rct(ax, x_cur, 0, pl, h_face, fc=cor_face, alpha=0.6, ec='white', lw=1.2)
            # Sarrafos
            for sy in [0.5, 1.0]:
                if sy < h_face:
                    ax.plot([x_cur, x_cur+pl], [sy, sy], '--',
                            color=SARRAFO, lw=0.9, alpha=0.8, zorder=4)
            # Número painel
            ax.text(x_cur+pl/2, h_face/2, f'P{pi+1}', color=TEXTO,
                    ha='center', va='center', fontsize=8, fontweight='bold', zorder=5)
            x_cur += pl

        # Label da face
        ax.text((x_start+x_cur)/2, h_face+0.25, face_nome,
                color=cor_face, ha='center', va='bottom', fontsize=8, fontweight='bold')

        # Cota comprimento face
        cota(ax, x_start, -0.5, x_cur, -0.5, f'L={L*100:.0f}cm', off=0, fs=6.5)

        x_cur += gap

    # Cotas altura
    for x_c, h_c, lbl_c, cor_c in [
        (-0.8, h, 'h=120cm', VIGA_C),
        (x_cur, b, 'b=15cm', '#8e44ad'),
    ]:
        cota(ax, x_c, 0, x_c, h_c, lbl_c, off=0, fs=6.5, fc=cor_c)

    # Nota divisão painéis
    fig.text(0.08, 0.08,
             f'• ceil(L / MAX_PAINEL) = ceil(518 / 244) = {math.ceil(518/244)} painéis por face\n'
             '• Painel final = L mod 244 = 30 cm (complemento)\n'
             '• Face A = lateral esquerda (olhando ao longo da viga)\n'
             '• Face B = lateral direita\n'
             '• Fundo = largura b = 15 cm (sob a viga)',
             va='bottom', fontsize=7.5, color=TEXTO,
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=6))

    rodape(fig, 'V-01 | Viga V101 — 3 faces planificadas: A (esq) · B (dir) · Fundo')
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  VIGA — V-02: Viga com Corte (h1 ≠ h2) e Laje Superior
# ═══════════════════════════════════════════════════════════════════════════
def page_viga_02(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'VIGA — V-02: Viga com Corte (h1 ≠ h2) e Laje Superior', ha='center',
             va='top', fontsize=11, color=VIGA_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'h1 = altura no extremo inicial · h2 = altura no extremo final · corte diagonal',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Esquerda: vista lateral
    ax = axes[0]
    setup(ax, 'Vista Lateral — Corte Diagonal')
    ax.set_xlim(-1.5, 7.5); ax.set_ylim(-1.5, 5.5)

    L = 6.0; h1 = 3.5; h2 = 1.5; b_viga = 0.4

    # Viga com corte (trapézio)
    verts_x = [0, L, L, 0, 0]
    verts_y = [0, 0, h2, h1, 0]
    ax.fill(verts_x, verts_y, color=VIGA_C, alpha=0.3, zorder=2)
    ax.plot(verts_x, verts_y, color=VIGA_C, lw=2.5, zorder=3)

    # Laje superior
    rct(ax, -0.5, h1, L+1.0, 0.5, fc=LAJE_ADJ, alpha=0.5, ec=LAJE_ADJ, lw=1.5)
    ax.text(L/2, h1+0.25, 'LAJE SUPERIOR', color=LAJE_ADJ,
            ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Apoios (pilares)
    for px, py, pn in [(0, -1.0, 'P-ESQ'), (L, -1.0, 'P-DIR')]:
        rct(ax, px-0.3, py, 0.6, 1.0, fc=PILAR_C, alpha=0.6, ec=PILAR_C, lw=1.5)
        ax.text(px, py+0.5, pn, color=PILAR_C, ha='center', va='center', fontsize=6.5)

    # Cotas h1, h2, L
    cota(ax, -1.0, 0, -1.0, h1, f'h1={h1*40:.0f}cm', off=0, fs=6.5)
    cota(ax, L+0.5, 0, L+0.5, h2, f'h2={h2*40:.0f}cm', off=0, fs=6.5)
    cota(ax, 0, -1.2, L, -1.2, 'L = comprimento', off=0, fs=6.5)

    # Setas
    arrow(ax, L/2+0.5, h1/2+h2/2+0.5, L/2, (h1+h2)/2, 'possui_corte=True', WARN, fs=7)
    ax.plot([0, L], [h1, h2], '--', color=WARN, lw=1.5, alpha=0.8, zorder=4)

    # Direita: seção transversal b×h
    ax2 = axes[1]
    setup(ax2, 'Seção Transversal b×h')
    ax2.set_xlim(-2, 5); ax2.set_ylim(-1, 5)

    bv, hv = 1.5, 4.0
    # Seção viga
    rct(ax2, 0, 0, bv, hv, fc=VIGA_C, alpha=0.3, ec=VIGA_C, lw=2.5)
    ax2.text(bv/2, hv/2, 'b×h', color=VIGA_C,
             ha='center', va='center', fontsize=11, fontweight='bold')

    # Laje superior
    rct(ax2, -0.8, hv, bv+1.6, 0.5, fc=LAJE_ADJ, alpha=0.5, ec=LAJE_ADJ, lw=1.5)

    # Face A e B
    rct(ax2, -0.25, 0, 0.25, hv, fc='#27ae60', alpha=0.8, lw=1)
    ax2.text(-0.25+0.125, hv/2, 'A', color=BG, ha='center', va='center',
             fontsize=9, fontweight='bold')
    rct(ax2, bv, 0, 0.25, hv, fc='#2980b9', alpha=0.8, lw=1)
    ax2.text(bv+0.125, hv/2, 'B', color=BG, ha='center', va='center',
             fontsize=9, fontweight='bold')
    rct(ax2, 0, -0.2, bv, 0.2, fc='#8e44ad', alpha=0.8, lw=1)
    ax2.text(bv/2, -0.1, 'FUNDO', color=TEXTO, ha='center', va='center', fontsize=6.5)

    cota(ax2, 0, -0.7, bv, -0.7, 'b=15cm', off=0, fs=6.5)
    cota(ax2, bv+1.0, 0, bv+1.0, hv, 'h=120cm', off=0, fs=6.5)

    # Campos extraídos
    campos = [
        'comprimento_total_a = L (face A)',
        'comprimento_total_b = L (face B)',
        'possui_corte = True',
        'altura_h1 = 140cm',
        'altura_h2 =  60cm',
        'nivel_a = cota apoio esq',
        'nivel_b = cota apoio dir',
        'laje_sup_a = nome laje esq',
        'laje_sup_b = nome laje dir',
    ]
    for i, c in enumerate(campos):
        ax2.text(0.05, 4.8 - i*0.38, c, color=COTA_C if i < 2 else TEXTO,
                 fontsize=6, va='top', fontfamily='monospace',
                 transform=ax2.transData)

    rodape(fig, 'V-02 | Viga com corte diagonal h1≠h2 — laje superior — seção transversal')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  VIGA — V-03: Auto-Divisão de Painéis (L > 244cm)
# ═══════════════════════════════════════════════════════════════════════════
def page_viga_03(pdf):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    setup(ax)
    ax.set_xlim(-0.5, 13); ax.set_ylim(-4, 5)

    fig.text(0.5, 0.97, 'VIGA — V-03: Auto-Divisão de Painéis (MAX_PAINEL=244cm)', ha='center',
             va='top', fontsize=11, color=VIGA_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Comprimentos > 244cm são automaticamente divididos em painéis menores',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    h = 2.0
    examples = [
        ('L = 200cm', 200, '#27ae60'),
        ('L = 250cm', 250, '#f1c40f'),
        ('L = 518cm', 518, '#ff79c6'),
        ('L = 732cm', 732, WARN),
    ]

    y_pos = 3.5
    for label, L_cm, cor in examples:
        L_scale = L_cm / 100  # escala: 100cm = 1 unidade

        max_p = 244
        paineis = []
        resto = L_cm
        while resto > 0:
            paineis.append(min(resto, max_p))
            resto -= max_p

        # Desenhar painéis
        x = 0
        for pi, pl in enumerate(paineis):
            pl_s = pl / 100
            shade = 0.5 + 0.4*(pi % 2)
            rct(ax, x, y_pos, pl_s, h, fc=cor, alpha=shade, ec='white', lw=1.5)
            lbl(ax, x, y_pos, pl_s, h, f'P{pi+1}\n{pl:.0f}cm', fc=TEXTO, fs=7)
            # Linha de junta
            if pi > 0:
                ax.plot([x, x], [y_pos, y_pos+h], '-', color='white', lw=2.5, alpha=0.9, zorder=5)
                ax.text(x, y_pos+h+0.1, '|', color=PAINEL, ha='center', fontsize=7, fontweight='bold')
            x += pl_s

        # Cota total
        cota(ax, 0, y_pos-0.5, L_scale, y_pos-0.5, f'{L_cm}cm', off=0, fs=6.5)

        # Info n_paineis
        ax.text(L_scale+0.3, y_pos+h/2,
                f'→ {len(paineis)} painéis\n  (último: {paineis[-1]:.0f}cm)',
                color=cor, fontsize=7, va='center', fontweight='bold')

        ax.text(-0.3, y_pos+h/2, label, color=cor, fontsize=8,
                ha='right', va='center', fontweight='bold')

        y_pos -= 3.2

    # Fórmula
    fig.text(0.08, 0.06,
             'n_paineis = math.ceil(L / MAX_PAINEL)\n'
             'paineis_larguras = [min(MAX_PAINEL, L - i*MAX_PAINEL) for i in range(n_paineis)]\n'
             'MAX_PAINEL_LARGURA = 244 cm  (limitação física do painel de madeira)',
             va='bottom', fontsize=8, color=VERDE, fontfamily='monospace',
             bbox=dict(facecolor='#0d1117', edgecolor=GRADE, lw=0.8, pad=6))

    rodape(fig, 'V-03 | Auto-divisão de painéis — L=200cm (1P) · 250cm (2P) · 518cm (3P) · 732cm (4P)')
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  VIGA — V-04: Faces A/B/Fundo Detalhadas com Sarrafos e Garfos
# ═══════════════════════════════════════════════════════════════════════════
def page_viga_04(pdf):
    fig, axes = plt.subplots(3, 1, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'VIGA — V-04: Face A · Face B · Fundo — Detalhamento', ha='center',
             va='top', fontsize=11, color=VIGA_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Sarrafos · garfos · n_paineis_larguras · alturas_face por painel',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    faces = [
        ('FACE A — Lateral Esquerda', '#27ae60', 3, [244, 244, 30], [120, 120, 120]),
        ('FACE B — Lateral Direita',  '#2980b9', 3, [244, 244, 30], [120, 120, 120]),
        ('FUNDO — Base da Viga',      '#8e44ad', 3, [244, 244, 30], [15, 15, 15]),
    ]

    for (title, cor, n, larguras, alturas), ax in zip(faces, axes):
        setup(ax, title)
        L_total = sum(larguras)
        h_max = max(alturas)
        scale_x = 7.0 / (L_total/100)
        scale_y = 2.5 / (h_max/100)

        ax.set_xlim(-1.0, 8.5); ax.set_ylim(-0.7, 3.8)

        x = 0
        for pi, (larg, alt) in enumerate(zip(larguras, alturas)):
            w = larg/100 * scale_x
            h = alt/100 * scale_y
            shade = 0.5 + 0.4*(pi%2)
            rct(ax, x, 0, w, h, fc=cor, alpha=shade, ec='white', lw=1.2)
            lbl(ax, x, 0, w, h,
                f'P{pi+1}\n{larg}cm × {alt}cm', fc=TEXTO, fs=6.5)

            # Sarrafos (a cada ~61cm)
            n_sarr = int(alt / 61)
            for si in range(1, n_sarr+1):
                sy = si*61/100 * scale_y
                if sy < h:
                    ax.plot([x, x+w], [sy, sy], '--', color=SARRAFO, lw=0.9, alpha=0.85, zorder=4)

            # Garfo na junta
            if pi < n-1:
                gx = x + w
                rct(ax, gx-0.05, h, 0.1, 0.35, fc=GARFO_C, alpha=0.9, lw=0.5)
                ax.text(gx, h+0.4, 'GARFO', color=GARFO_C, fontsize=5.5,
                        ha='center', va='bottom', fontweight='bold')
            x += w

        # Cota total
        cota(ax, 0, -0.45, x, -0.45, f'L = 518cm', off=0, fs=6)
        for pi_c, (larg, alt) in enumerate(zip(larguras, alturas)):
            xi = sum(larguras[:pi_c])/100 * scale_x
            wi = larg/100 * scale_x
            cota(ax, xi, -0.2, xi+wi, -0.2, f'{larg}cm', off=0, fs=5.5)

    # Legenda
    handles = [mpatches.Patch(color=SARRAFO, label='Sarrafos (≈61cm)'),
               mpatches.Patch(color=GARFO_C, label='Garfos (juntas)'),
               mpatches.Patch(color=PAINEL, label='Painel de forma')]
    fig.legend(handles=handles, loc='lower center', ncol=3, fontsize=7,
               facecolor=BG, framealpha=0.8, labelcolor=TEXTO, edgecolor=GRADE)

    rodape(fig, 'V-04 | Face A · B · Fundo com sarrafos e garfos nas juntas de painel')
    plt.tight_layout(rect=[0, 0.05, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  LAJE — L-01: Laje Retangular + Grid de Pontaletes
# ═══════════════════════════════════════════════════════════════════════════
def page_laje_01(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'LAJE — L-01: Retangular Simples + Grid de Pontaletes', ha='center',
             va='top', fontsize=11, color=LAJE_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'LAJE_GRID_STEP=122cm → grade de pontaletes n_cols × n_rows',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    ax = axes[0]
    setup(ax, 'Planta da Laje — Vista de Cima')
    ax.set_xlim(-1, 7); ax.set_ylim(-1, 7)

    W, H = 5.0, 4.0
    grid_s = 1.22

    # Contorno laje
    rct(ax, 0, 0, W, H, fc=LAJE_C, alpha=0.2, ec=LAJE_C, lw=2.5)

    # Grade de pontaletes
    n_cols = int(W / grid_s) + 1
    n_rows = int(H / grid_s) + 1
    for ci in range(n_cols):
        for ri in range(n_rows):
            gx = ci * grid_s
            gy = ri * grid_s
            if gx <= W and gy <= H:
                ax.plot(gx, gy, 'o', color=GARFO_C, ms=6, zorder=5)
                # Linhas de grade
                if ci < n_cols-1 and (ci+1)*grid_s <= W:
                    ax.plot([gx, gx+grid_s], [gy, gy], '-', color=GRADE, lw=0.8, alpha=0.5)
                if ri < n_rows-1 and (ri+1)*grid_s <= H:
                    ax.plot([gx, gx], [gy, gy+grid_s], '-', color=GRADE, lw=0.8, alpha=0.5)

    # Cotas
    cota(ax, 0, -0.6, W, -0.6, f'W={W*100:.0f}cm', off=0)
    cota(ax, -0.7, 0, -0.7, H, f'H={H*100:.0f}cm', off=0)
    cota(ax, 0, grid_s, grid_s, grid_s, '122cm', off=0.15, fs=6)

    ax.text(W/2, H+0.3, f'n_cols={n_cols}  n_rows={n_rows}', color=LAJE_C,
            ha='center', fontsize=8, fontweight='bold')

    # Pontalete (zoom)
    ax2 = axes[1]
    setup(ax2, 'Pontalete — Detalhe de Escoramento')
    ax2.set_xlim(-1, 5); ax2.set_ylim(-0.5, 8)

    # Desenho do pontalete
    bP = 0.3
    pe = 6.0
    # Laje no topo
    rct(ax2, -0.8, pe, 2.6, 0.5, fc=LAJE_C, alpha=0.5, ec=LAJE_C, lw=1.5)
    ax2.text(0.5, pe+0.25, 'LAJE', color=LAJE_C, ha='center', va='center',
             fontsize=8, fontweight='bold')
    # Forma fundo (madeira)
    rct(ax2, -0.5, pe-0.2, 2.0, 0.2, fc=PAINEL, alpha=0.8, lw=1)
    ax2.text(0.5, pe-0.1, 'Forma (fundo)', color=BG, ha='center', va='center', fontsize=6.5)
    # Pontalete (pé)
    rct(ax2, 0.5-bP/2, 0, bP, pe-0.2, fc='#8b5e3c', alpha=0.7, ec='white', lw=1)
    ax2.text(0.5, pe/2, 'PONTALETE', color=TEXTO, ha='center', va='center',
             fontsize=7, fontweight='bold', rotation=90)
    # Garfo no topo
    rct(ax2, 0.5-0.4, pe-0.2, 0.8, 0.3, fc=GARFO_C, alpha=0.9, lw=0.5)
    ax2.text(0.5, pe-0.05, 'garfo', color=BG, ha='center', va='center', fontsize=6)
    # Base
    rct(ax2, 0.0, -0.15, 1.0, 0.15, fc='#555', alpha=0.8, lw=1)

    cota(ax2, 1.5, 0, 1.5, pe, f'PE={pe*100/6:.0f}cm', off=0, fs=6.5)
    cota(ax2, 2.0, pe-0.2, 2.0, pe+0.5, 'esp_laje=15cm', off=0, fs=6)

    # Fórmula
    ax2.text(2.5, 3.5,
             'calcular_lajes():\n'
             '  n_cols = ceil(W/122)\n'
             '  n_rows = ceil(H/122)\n'
             '  grid_step_x = W/n_cols\n'
             '  grid_step_y = H/n_rows\n'
             '  espessura = 15cm\n'
             '  bordering_vigas = [...]',
             color=VERDE, fontsize=6.5, va='center', fontfamily='monospace')

    rodape(fig, 'L-01 | Laje retangular — grid de pontaletes LAJE_GRID_STEP=122cm')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  LAJE — L-02: Polígono Irregular + Abertura/Ilha
# ═══════════════════════════════════════════════════════════════════════════
def page_laje_02(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'LAJE — L-02: Polígono Irregular e Laje com Abertura (Ilha)', ha='center',
             va='top', fontsize=11, color=LAJE_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'Contorno points_json · outline_segs · abertura/ilha central',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Esquerda: polígono irregular
    ax = axes[0]
    setup(ax, 'Laje Irregular — Contorno Poligonal')
    ax.set_xlim(-1, 7); ax.set_ylim(-1, 7)

    pts = [(0,0),(4.5,0),(5.0,1.5),(5.0,4.0),(3.5,5.0),(1.0,5.5),(0,4.0),(0,0)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.fill(xs, ys, color=LAJE_C, alpha=0.25, zorder=2)
    ax.plot(xs, ys, color=LAJE_C, lw=2.5, zorder=3)

    # Vértices com coords
    for i, (xi, yi) in enumerate(pts[:-1]):
        ax.plot(xi, yi, 'o', color=PAINEL, ms=6, zorder=5)
        ax.text(xi+0.15, yi+0.1, f'V{i}\n({xi*100:.0f},{yi*100:.0f})cm',
                color=PAINEL, fontsize=5.5, va='bottom')

    # Centróide
    cx = sum(xs[:-1])/len(xs[:-1])
    cy = sum(ys[:-1])/len(ys[:-1])
    ax.plot(cx, cy, '+', color=WARN, ms=10, mew=2, zorder=6)
    ax.text(cx+0.2, cy, 'centróide', color=WARN, fontsize=7)

    # Bounding box
    ax.add_patch(mpatches.Rectangle((min(xs), min(ys)),
                                     max(xs)-min(xs), max(ys)-min(ys),
                 linewidth=1.5, edgecolor=APOIO_C, facecolor='none',
                 linestyle='--', alpha=0.6, zorder=4))
    cota(ax, min(xs), max(ys)+0.3, max(xs), max(ys)+0.3,
         f'bbox_W={max(xs)*100:.0f}cm', off=0, fs=6.5)
    cota(ax, max(xs)+0.3, min(ys), max(xs)+0.3, max(ys),
         f'bbox_H={max(ys)*100:.0f}cm', off=0, fs=6.5)

    # Direita: laje com abertura
    ax2 = axes[1]
    setup(ax2, 'Laje com Abertura Central (Ilha)')
    ax2.set_xlim(-1, 7); ax2.set_ylim(-1, 7)

    # Contorno externo
    ext_pts = [(0,0),(5,0),(5,5),(0,5),(0,0)]
    xs_e = [p[0] for p in ext_pts]
    ys_e = [p[1] for p in ext_pts]
    ax2.fill(xs_e, ys_e, color=LAJE_C, alpha=0.25, zorder=2)
    ax2.plot(xs_e, ys_e, color=LAJE_C, lw=2.5, zorder=3)

    # Abertura interna (ilha)
    ab_pts = [(1.5,1.5),(3.5,1.5),(3.5,3.5),(1.5,3.5),(1.5,1.5)]
    xs_a = [p[0] for p in ab_pts]
    ys_a = [p[1] for p in ab_pts]
    ax2.fill(xs_a, ys_a, color=BG, alpha=1.0, zorder=3)
    ax2.plot(xs_a, ys_a, color=WARN, lw=2.0, linestyle='--', zorder=4)
    ax2.text(2.5, 2.5, 'ABERTURA\n(Ilha/Vazio)', color=WARN,
             ha='center', va='center', fontsize=8, fontweight='bold')

    arrow(ax2, 4.5, 4.0, 3.6, 3.6, 'outline_segs\n(ilha)', WARN, fs=7)
    arrow(ax2, 5.5, 2.5, 5.1, 2.5, 'contorno\nexterno', LAJE_C, fs=7)

    cota(ax2, 0, -0.6, 5, -0.6, 'W=500cm', off=0)
    cota(ax2, -0.6, 0, -0.6, 5, 'H=500cm', off=0)
    cota(ax2, 1.5, 1.5-0.4, 3.5, 1.5-0.4, 'abertura=200cm', off=0, fs=6)

    ax2.text(2.5, 5.4, 'area_total - area_abertura = area_util',
             color=APOIO_C, ha='center', fontsize=7, style='italic')

    rodape(fig, 'L-02 | Laje irregular e laje com abertura/ilha — points_json e outline_segs')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  LAJE — L-03: Espessuras e Corte Transversal
# ═══════════════════════════════════════════════════════════════════════════
def page_laje_03(pdf):
    fig, axes = plt.subplots(2, 1, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'LAJE — L-03: Espessuras Típicas e Corte Transversal', ha='center',
             va='top', fontsize=11, color=LAJE_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'h=10/12/14/15/20cm — fundo da forma — pontaletes — viga apoio',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    # Comparação de espessuras
    ax = axes[0]
    setup(ax, 'Comparação de Espessuras Típicas')
    ax.set_xlim(-0.5, 13); ax.set_ylim(-0.5, 3.5)

    espessuras = [10, 12, 14, 15, 20]
    cores_e = ['#1a6985', '#1e7ea1', '#2195c4', '#27aae1', '#3bc9ff']
    x = 0
    for esp, cor in zip(espessuras, cores_e):
        w = 1.8; h = esp/50
        rct(ax, x, 0, w, h, fc=cor, alpha=0.8, ec='white', lw=1.5)
        ax.text(x+w/2, h/2, f'h={esp}cm', color=TEXTO,
                ha='center', va='center', fontsize=8, fontweight='bold')
        # Pontalete
        ax.plot([x+w/2, x+w/2], [-0.3, 0], '-', color='#8b5e3c', lw=4, solid_capstyle='round')
        ax.text(x+w/2, -0.4, f'{esp}cm', color=cor, ha='center', fontsize=7.5, fontweight='bold')
        cota(ax, x+w+0.05, 0, x+w+0.05, h, f'{esp}', off=0, fs=6, fc=cor)
        x += w + 0.5

    # Corte transversal completo
    ax2 = axes[1]
    setup(ax2, 'Corte Transversal — Forma + Pontaletes + Laje')
    ax2.set_xlim(-1, 10); ax2.set_ylim(-1.5, 6)

    # Componentes do corte
    L = 8.0
    h_laje = 0.6  # 15cm scaled
    h_forma = 0.15
    h_viga = 2.0
    b_viga = 0.5
    pe_form = 4.5

    # Laje de concreto
    rct(ax2, 0, pe_form+h_forma, L, h_laje, fc='#95a5a6', alpha=0.7, ec='white', lw=1.5)
    ax2.text(L/2, pe_form+h_forma+h_laje/2, 'LAJE CONCRETO', color=TEXTO,
             ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Forma (fundo de madeira)
    rct(ax2, 0, pe_form, L, h_forma, fc=PAINEL, alpha=0.9, lw=1)
    ax2.text(L/2, pe_form+h_forma/2, 'Forma (Fundo)', color=BG,
             ha='center', va='center', fontsize=7)

    # Pontaletes
    n_pont = 5
    for pi in range(n_pont):
        px = pi * L/(n_pont-1)
        bp = 0.18
        rct(ax2, px-bp/2, 0, bp, pe_form, fc='#8b5e3c', alpha=0.7, lw=0.8)

        # Garfo no topo de cada pontalete
        rct(ax2, px-0.3, pe_form, 0.6, 0.2, fc=GARFO_C, alpha=0.9, lw=0.3)

    # Viga apoio lateral
    rct(ax2, -b_viga, pe_form-h_viga+h_forma, b_viga, h_viga, fc=VIGA_C, alpha=0.4, ec=VIGA_C, lw=1.5)
    ax2.text(-b_viga/2, pe_form-h_viga/2+h_forma, 'VIGA\nAPOIO', color=VIGA_C,
             ha='center', va='center', fontsize=7)
    rct(ax2, L, pe_form-h_viga+h_forma, b_viga, h_viga, fc=VIGA_C, alpha=0.4, ec=VIGA_C, lw=1.5)
    ax2.text(L+b_viga/2, pe_form-h_viga/2+h_forma, 'VIGA\nAPOIO', color=VIGA_C,
             ha='center', va='center', fontsize=7)

    # Cotas
    cota(ax2, -0.8, pe_form, -0.8, pe_form+h_forma+h_laje, 'h_laje=15cm', off=0, fs=6)
    cota(ax2, L+0.8, 0, L+0.8, pe_form, 'PE=280cm', off=0, fs=6.5)
    cota(ax2, 0, -0.8, L, -0.8, 'Vão livre da laje', off=0)

    # Legenda
    handles = [mpatches.Patch(color='#95a5a6', label='Concreto armado'),
               mpatches.Patch(color=PAINEL, label='Forma (fundo)'),
               mpatches.Patch(color='#8b5e3c', label='Pontaletes'),
               mpatches.Patch(color=GARFO_C, label='Garfos de travamento'),
               mpatches.Patch(color=VIGA_C, alpha=0.5, label='Vigas de apoio')]
    ax2.legend(handles=handles, loc='upper right', fontsize=6.5,
               facecolor=BG, framealpha=0.8, labelcolor=TEXTO, edgecolor=GRADE)

    rodape(fig, 'L-03 | Espessuras h=10/12/14/15/20cm · Corte transversal forma+pontaletes+laje')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  LAJE — L-04: Acréscimo de Borda e Laje com Vigas Adjacentes
# ═══════════════════════════════════════════════════════════════════════════
def page_laje_04(pdf):
    fig, axes = plt.subplots(1, 2, figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.97, 'LAJE — L-04: Acréscimo de Borda + Vigas Bordejantes', ha='center',
             va='top', fontsize=11, color=LAJE_C, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.945, 'acrescimo_borda · bordering_vigas · borda livre vs borda com viga',
             ha='center', va='top', fontsize=8, color=APOIO_C)

    ax = axes[0]
    setup(ax, 'Acréscimo de Borda')
    ax.set_xlim(-1.5, 7); ax.set_ylim(-1.5, 7)

    # Laje principal
    W, H = 4.5, 4.0
    rct(ax, 0, 0, W, H, fc=LAJE_C, alpha=0.2, ec=LAJE_C, lw=2)
    ax.text(W/2, H/2, 'LAJE\nL101', color=LAJE_C, ha='center', va='center',
            fontsize=10, fontweight='bold')

    # Acréscimo (borda extra, ex: 15cm)
    ac = 0.3
    for bx, by, bw, bh, lbl_t in [
        (0, H, W, ac, 'borda\nNorte'),      # topo
        (W, 0, ac, H, 'borda\nLeste'),       # dir
        (0, -ac, W, ac, 'borda\nSul'),       # base
        (-ac, 0, ac, H, 'borda\nOeste'),     # esq
    ]:
        rct(ax, bx, by, bw, bh, fc=COTA_C, alpha=0.5, ec=COTA_C, lw=1.5)
        cx = bx + bw/2; cy = by + bh/2
        ax.text(cx, cy, lbl_t, color=BG, ha='center', va='center',
                fontsize=6, fontweight='bold')

    cota(ax, 0, H+ac+0.3, W, H+ac+0.3, f'W={W*100:.0f}cm', off=0)
    cota(ax, -ac-0.6, 0, -ac-0.6, H, f'H={H*100:.0f}cm', off=0)
    cota(ax, W+ac+0.2, 0, W+ac+0.2, ac, f'ac={ac*100:.0f}cm', off=0, fs=6)

    arrow(ax, 5.5, 3.0, W+ac+0.1, H/2, 'acrescimo_borda\n= 30cm', COTA_C, fs=7)

    ax2 = axes[1]
    setup(ax2, 'Vigas Bordejantes (bordering_vigas)')
    ax2.set_xlim(-1.5, 7); ax2.set_ylim(-1.5, 7)

    # Laje
    rct(ax2, 0, 0, W, H, fc=LAJE_C, alpha=0.2, ec=LAJE_C, lw=2)
    ax2.text(W/2, H/2, 'LAJE', color=LAJE_C, ha='center', va='center',
             fontsize=10, fontweight='bold')

    # Vigas bordejantes
    vt = 0.35
    for vx, vy, vw, vh, vname, cor_v in [
        (0, H, W, vt, 'V-Norte (A)', VIGA_C),
        (W, 0, vt, H, 'V-Leste (B)', '#2ecc71'),
        (0, -vt, W, vt, 'V-Sul (C)', '#27ae60'),
        (-vt, 0, vt, H, 'V-Oeste (D)', '#1e8449'),
    ]:
        rct(ax2, vx, vy, vw, vh, fc=cor_v, alpha=0.6, ec=cor_v, lw=1.5)
        ax2.text(vx+vw/2, vy+vh/2, vname, color=TEXTO,
                 ha='center', va='center', fontsize=6, fontweight='bold')

    # Pilares nos cantos
    pc = 0.3
    for ppx, ppy in [(0,0),(W,0),(W,H),(0,H)]:
        rct(ax2, ppx-pc/2, ppy-pc/2, pc, pc, fc=PILAR_C, alpha=0.9, ec=PILAR_C, lw=1)

    ax2.text(W/2, -1.0,
             'bordering_vigas = [V-Norte, V-Leste, V-Sul, V-Oeste]\n'
             'Laje bordejada em todos os 4 lados',
             color=VIGA_C, ha='center', fontsize=7, style='italic')

    rodape(fig, 'L-04 | Acréscimo de borda e vigas bordejantes por lado da laje')
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  PÁGINA ÍNDICE
# ═══════════════════════════════════════════════════════════════════════════
def page_indice(pdf):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0.08, 0.05, 0.84, 0.88])
    ax.set_facecolor(BG); ax.axis('off')

    fig.text(0.5, 0.96, 'ÍNDICE DO ATLAS', ha='center', va='top',
             fontsize=16, color=PAINEL, fontweight='bold', fontfamily='monospace')
    fig.text(0.5, 0.92, 'Atlas Ilustrado de Elementos Estruturais — CAD-ANALYZER v2.0',
             ha='center', va='top', fontsize=9, color=APOIO_C)

    items = [
        ('PILARES', PILAR_C, [
            ('P-01', 'Pilar Retangular Simples — 4 Lados A/B/C/D + orientação'),
            ('P-02', 'Painéis Planificados A/B/C/D — Fiadas + Sarrafos'),
            ('P-03', 'Pilar Cambotado — Arcos/Bulges + Detecção'),
            ('P-04', 'Configurações de Adjacência — Interno/Canto/Borda/Isolado'),
            ('P-05', 'Garfos — Geometria, Cálculo e Posicionamento'),
            ('P-06', 'Vista Isométrica 3D — 4 Painéis + Sarrafos'),
            ('P-07', 'Seção Transversal Detalhada + Confidence Map'),
        ]),
        ('VIGAS', VIGA_C, [
            ('V-01', 'Anatomia Completa — Face A · Face B · Fundo'),
            ('V-02', 'Viga com Corte (h1≠h2) + Laje Superior + Seção b×h'),
            ('V-03', 'Auto-Divisão de Painéis (MAX_PAINEL=244cm)'),
            ('V-04', 'Faces A/B/Fundo — Sarrafos + Garfos nas Juntas'),
        ]),
        ('LAJES', LAJE_C, [
            ('L-01', 'Laje Retangular Simples + Grid de Pontaletes (122cm)'),
            ('L-02', 'Polígono Irregular + Laje com Abertura/Ilha'),
            ('L-03', 'Espessuras h=10/12/14/15/20cm + Corte Transversal'),
            ('L-04', 'Acréscimo de Borda + Vigas Bordejantes'),
        ]),
    ]

    y = 0.87
    for section, cor, subitems in items:
        ax.text(0.02, y, f'■ {section}', color=cor, fontsize=13,
                fontweight='bold', transform=ax.transAxes, va='top')
        y -= 0.05
        for code, desc in subitems:
            ax.text(0.05, y, f'{code}', color=PAINEL, fontsize=9,
                    fontweight='bold', transform=ax.transAxes, va='top',
                    fontfamily='monospace')
            ax.text(0.16, y, desc, color=TEXTO, fontsize=9,
                    transform=ax.transAxes, va='top')
            y -= 0.04
        y -= 0.02

    # Rodapé com constantes
    fig.text(0.08, 0.04,
             'Constantes do Motor:  MAX_PAINEL=244cm  |  LAJE_GRID_STEP=122cm  |  PE_DIREITO=280cm',
             va='bottom', fontsize=8, color=COTA_C,
             bbox=dict(facecolor='#1e1e3a', edgecolor=GRADE, lw=0.8, pad=6))

    pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    print(f'Gerando Atlas: {OUT}')
    with PdfPages(str(OUT)) as pdf:
        print('  Capa...')
        page_capa(pdf)
        print('  Índice...')
        page_indice(pdf)

        print('  PILAR P-01: Simples retangular...')
        page_pilar_01(pdf)
        print('  PILAR P-02: Painéis planificados...')
        page_pilar_02(pdf)
        print('  PILAR P-03: Cambotado...')
        page_pilar_03(pdf)
        print('  PILAR P-04: Adjacências...')
        page_pilar_04(pdf)
        print('  PILAR P-05: Garfos...')
        page_pilar_05(pdf)
        print('  PILAR P-06: Vista isométrica...')
        page_pilar_06(pdf)
        print('  PILAR P-07: Seção detalhada + confidence...')
        page_pilar_07(pdf)

        print('  VIGA V-01: Anatomia completa...')
        page_viga_01(pdf)
        print('  VIGA V-02: Com corte + laje superior...')
        page_viga_02(pdf)
        print('  VIGA V-03: Auto-divisão painéis...')
        page_viga_03(pdf)
        print('  VIGA V-04: Faces A/B/Fundo detalhadas...')
        page_viga_04(pdf)

        print('  LAJE L-01: Retangular + grid pontaletes...')
        page_laje_01(pdf)
        print('  LAJE L-02: Irregular + abertura...')
        page_laje_02(pdf)
        print('  LAJE L-03: Espessuras + corte transversal...')
        page_laje_03(pdf)
        print('  LAJE L-04: Acréscimo borda + vigas bordejantes...')
        page_laje_04(pdf)

        # Metadata
        d = pdf.infodict()
        d['Title'] = 'Atlas Elementos Estruturais — CAD-ANALYZER v2.0'
        d['Author'] = 'CAD-ANALYZER Pipeline'
        d['Subject'] = 'Pilar, Viga, Laje — Formas de Concreto Armado'

    size_kb = OUT.stat().st_size // 1024
    print(f'\nAtlas gerado: {OUT}')
    print(f'Paginas: 16 (capa + indice + 7 pilar + 4 viga + 4 laje)')
    print(f'Tamanho: {size_kb} KB')
    return str(OUT)

if __name__ == '__main__':
    main()
