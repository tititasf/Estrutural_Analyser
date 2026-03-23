#!/usr/bin/env python3
"""
Fichas Instrutivas v2 — CAD-ANALYZER (Spec-Driven)
===================================================
Cada pagina responde: "dado este DXF entity, que campo JSON extrair?"
Fonte da verdade: docs/specs/SPEC-*.md + CONFIG-LAYERS.yaml + DECISION-MATRIX.md

Gera 3 PDFs A3 landscape:
  docs/fichas/fichas_pilares_instrutivas.pdf  (12 paginas)
  docs/fichas/fichas_vigas_instrutivas.pdf    (12 paginas)
  docs/fichas/fichas_lajes_instrutivas.pdf    (8 paginas)

Executa: python scripts/gerar_fichas_v2.py
"""
import sys
import math
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ==========================================================================
# CONSTANTS
# ==========================================================================
BG     = '#0a0a14'
FG     = '#e0e0e0'
GOLD   = '#ffbf00'
RED    = '#ff4444'
CYAN   = '#00ffff'
GREEN  = '#00cc66'
WHITE  = '#ffffff'
LGRAY  = '#c8c8c8'
DGRAY  = '#555555'
ACCENT = '#e8b84b'
BLUE   = '#4488cc'
PURPLE = '#9966cc'
CODE_BG   = '#050510'
CODE_BD   = '#225588'
WARN_BG   = '#2a1800'
WARN_FG   = '#ffaa44'
OK_BG     = '#002215'
OK_FG     = '#44ff88'

plt.rcParams.update({
    'figure.facecolor': BG,
    'axes.facecolor':   BG,
    'axes.edgecolor':   '#222244',
    'text.color':       FG,
    'font.family':      'monospace',
    'figure.max_open_warning': 200,
})

OUT_DIR = Path("D:/Agente-cad-PYSIDE/docs/fichas")
OUT_DIR.mkdir(parents=True, exist_ok=True)

VERSION = "v2.0 | 2026-03-19 | CAD-ANALYZER"

# ==========================================================================
# LAYOUT HELPERS
# ==========================================================================

def fig_a3():
    """A3 landscape: 420 x 297 mm."""
    fig = plt.figure(figsize=(16.54, 11.69))
    fig.patch.set_facecolor(BG)
    return fig


def header_bar(fig, element_type, section_code, section_title):
    """Barra de cabecalho com tipo de elemento + codigo de secao."""
    # Fundo da barra
    bar = mpatches.FancyBboxPatch((0.01, 0.935), 0.98, 0.055,
        boxstyle='round,pad=0.002', facecolor='#0d0d24', edgecolor='#334477',
        lw=1.2, transform=fig.transFigure, zorder=10)
    fig.add_artist(bar)

    # Tag de elemento (pilar / viga / laje)
    elem_colors = {'PILAR': '#cc6600', 'VIGA': '#0066cc', 'LAJE': '#006644'}
    ec = elem_colors.get(element_type.upper(), ACCENT)
    fig.text(0.015, 0.962, element_type.upper(), ha='left', va='center',
             fontsize=9, color=ec, fontweight='bold', fontfamily='monospace',
             transform=fig.transFigure)

    fig.text(0.10, 0.962, f'[{section_code}]', ha='left', va='center',
             fontsize=8, color=CYAN, fontfamily='monospace',
             transform=fig.transFigure)

    fig.text(0.20, 0.962, section_title, ha='left', va='center',
             fontsize=9, color=ACCENT, fontweight='bold', fontfamily='monospace',
             transform=fig.transFigure)

    fig.text(0.99, 0.962, VERSION, ha='right', va='center',
             fontsize=6, color=DGRAY, fontfamily='monospace',
             transform=fig.transFigure)


def footer_bar(fig, pg, total, note=''):
    fig.text(0.5, 0.008, f'Pagina {pg}/{total}  |  {note}', ha='center', va='bottom',
             fontsize=6, color=DGRAY, style='italic', transform=fig.transFigure)


def divider(fig, y_frac=0.5):
    """Linha divisoria vertical central."""
    fig.add_artist(plt.Line2D([0.50, 0.50], [0.04, 0.93],
                   transform=fig.transFigure, color='#223355', lw=0.8))


def section_ax(fig, rect, title='', bg=CODE_BG, border=CODE_BD):
    """Cria axes com moldura e titulo opcional em coordenadas figure."""
    ax = fig.add_axes(rect)
    ax.set_facecolor(bg)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    border_r = mpatches.FancyBboxPatch((0, 0), 100, 100,
        boxstyle='round,pad=0.0', facecolor='none', edgecolor=border, lw=0.8)
    ax.add_patch(border_r)
    if title:
        ax.text(2, 97, title, ha='left', va='top', fontsize=7,
                color=ACCENT, fontweight='bold', fontfamily='monospace')
    return ax


# ==========================================================================
# CONTENT PRIMITIVES
# ==========================================================================

def code_lines(ax, lines, x=3, y=93, fs=6.5, leading=7.2, title='',
               highlight=None):
    """
    Renderiza linhas de codigo Python em ax (coordenadas 0-100).
    highlight: lista de indices de linhas para destacar em amarelo.
    """
    if highlight is None:
        highlight = []
    if title:
        ax.text(x, y, f'# {title}', ha='left', va='top',
                fontsize=fs, color='#668899', fontfamily='monospace')
        y -= leading * 1.1

    for i, line in enumerate(lines):
        color = GOLD if i in highlight else FG
        if line.lstrip().startswith('#'):
            color = '#557799'
        elif any(kw in line for kw in ('def ', 'class ', 'import ', 'from ')):
            color = '#88aaff'
        elif any(kw in line for kw in ('return ', 'yield ')):
            color = '#ff88aa'
        elif line.strip().startswith('"') or line.strip().startswith("'"):
            color = '#88cc88'
        ax.text(x, y - i * leading, line, ha='left', va='top',
                fontsize=fs, color=color, fontfamily='monospace')


def json_block(ax, fields, x=3, y=93, fs=6.2, leading=7.0, title='FichaFase3'):
    """
    Renderiza bloco JSON schema.
    fields: list of (key, value_example, comment, is_critical)
    """
    ax.text(x, y, f'// {title}', ha='left', va='top',
            fontsize=fs, color='#558899', fontfamily='monospace')
    ax.text(x, y - leading, '{', ha='left', va='top',
            fontsize=fs + 1, color=FG, fontfamily='monospace')
    for i, (key, val, cmt, crit) in enumerate(fields):
        yp = y - leading * 2 - i * leading
        crit_dot = '* ' if crit else '  '
        dot_color = '#ff6644' if crit else DGRAY
        ax.text(x, yp, crit_dot, ha='left', va='top',
                fontsize=fs, color=dot_color, fontfamily='monospace')
        ax.text(x + 4, yp, f'"{key}": {val}', ha='left', va='top',
                fontsize=fs, color=CYAN if crit else LGRAY, fontfamily='monospace')
        if cmt:
            ax.text(x + 4 + len(f'"{key}": {val}') * 2.5, yp, f'  // {cmt}',
                    ha='left', va='top', fontsize=fs - 0.5,
                    color='#446655', fontfamily='monospace')
    ax.text(x, y - leading * 2 - len(fields) * leading, '}', ha='left', va='top',
            fontsize=fs + 1, color=FG, fontfamily='monospace')


def layer_table(ax, rows, x=3, y=95, col_w=(30, 28, 20, 19), fs=6.2, title='Layers'):
    """
    Tabela de layers: Layer DXF | Canonical | Elemento | Confianca
    rows: list of (layer_name, canonical, elemento, conf)
    """
    headers = ('Layer DXF', 'Canonical', 'Uso', 'Conf')
    header_y = y
    cols = [x, x + col_w[0], x + col_w[0]+col_w[1], x + col_w[0]+col_w[1]+col_w[2]]

    ax.text(x, y + 4, title, ha='left', va='bottom', fontsize=7,
            color=ACCENT, fontweight='bold', fontfamily='monospace')

    # Header
    conf_colors = {'HIGH': OK_FG, 'MEDIUM': GOLD, 'LOW': WARN_FG, 'N/A': DGRAY}
    for col, hdr in zip(cols, headers):
        ax.text(col, header_y, hdr, ha='left', va='top', fontsize=fs,
                color=BLUE, fontweight='bold', fontfamily='monospace')

    # Divisor
    ax.plot([x, x + sum(col_w)], [header_y - 2, header_y - 2], color='#334466', lw=0.6)

    for i, (layer, canonical, uso, conf) in enumerate(rows):
        ry = header_y - 7 - i * 7
        # Highlight alternado
        if i % 2 == 0:
            bg = mpatches.Rectangle((x - 1, ry - 2), sum(col_w) + 2, 6.5,
                facecolor='#0d0d22', edgecolor='none', alpha=0.6)
            ax.add_patch(bg)
        ax.text(cols[0], ry, layer, ha='left', va='top', fontsize=fs - 0.3,
                color=LGRAY, fontfamily='monospace')
        ax.text(cols[1], ry, canonical, ha='left', va='top', fontsize=fs - 0.3,
                color=CYAN, fontfamily='monospace')
        ax.text(cols[2], ry, uso, ha='left', va='top', fontsize=fs - 0.3,
                color=FG, fontfamily='monospace')
        conf_c = conf_colors.get(conf, DGRAY)
        ax.text(cols[3], ry, conf, ha='left', va='top', fontsize=fs - 0.3,
                color=conf_c, fontweight='bold', fontfamily='monospace')


def radius_diagram(ax, cx=50, cy=50, r1=8, r2=20, r3=40,
                   label1='score=1.0\n(dentro)',
                   label2='score=0.8\n(<=5mm)',
                   label3='score=0..0.5\n(decay)'):
    """Diagrama visual dos 3 raios de busca."""
    import numpy as np
    theta = np.linspace(0, 2 * math.pi, 200)

    # Pilar (quadrado central)
    pilar_w, pilar_h = r1 * 1.2, r1 * 1.8
    pilar = mpatches.Rectangle((cx - pilar_w/2, cy - pilar_h/2), pilar_w, pilar_h,
        facecolor='#443300', edgecolor=GOLD, lw=1.5, zorder=5)
    ax.add_patch(pilar)
    ax.text(cx, cy, 'P17', ha='center', va='center',
            fontsize=6, color=GOLD, fontweight='bold', fontfamily='monospace', zorder=6)

    # Raio 2 (5mm)
    ax.plot(cx + r2 * np.cos(theta), cy + r2 * np.sin(theta),
            color='#00cc44', lw=0.8, ls='--', alpha=0.7, zorder=3)
    ax.text(cx + r2, cy + 2, '5mm', fontsize=5.5, color='#00cc44', fontfamily='monospace')

    # Raio 3 (search radius)
    ax.plot(cx + r3 * np.cos(theta), cy + r3 * np.sin(theta),
            color=CYAN, lw=0.8, ls=':', alpha=0.6, zorder=3)
    ax.text(cx + r3, cy + 2, '800mm', fontsize=5.5, color=CYAN, fontfamily='monospace')

    # Texto dentro (raio 1)
    ax.plot(cx + 2, cy + 2, 'o', color=GREEN, ms=5, zorder=7)
    ax.text(cx + 5, cy + 8, label1, fontsize=5.5, color=GREEN,
            fontfamily='monospace', va='bottom')

    # Texto adjacente (raio 2)
    tx2 = cx + r2 * 0.7
    ty2 = cy + r2 * 0.7
    ax.plot(tx2, ty2, 's', color='#00cc44', ms=5, zorder=7)
    ax.text(tx2 + 3, ty2 + 3, label2, fontsize=5.5, color='#00cc44',
            fontfamily='monospace', va='bottom')

    # Texto distante (raio 3)
    tx3 = cx + r3 * 0.65
    ty3 = cy - r3 * 0.40
    ax.plot(tx3, ty3, '^', color=CYAN, ms=5, zorder=7)
    ax.text(tx3 + 3, ty3 - 6, label3, fontsize=5.5, color=CYAN,
            fontfamily='monospace', va='top')

    # Legenda
    ax.text(cx - r3, cy - r3 + 3, 'Logica 3 Raios', fontsize=6.5,
            color=ACCENT, fontweight='bold', fontfamily='monospace')


def confidence_bar(ax, x=5, y=15, w=90, h=8):
    """Barra visual de confidence thresholds."""
    import numpy as np
    segments = [
        (0.0, 0.30, '#550000', 'REJEITAR\n<0.30'),
        (0.30, 0.50, '#664400', 'REVISAO\n0.30-0.50'),
        (0.50, 0.80, '#665500', 'AVISO\n0.50-0.80'),
        (0.80, 1.00, '#005500', 'AUTO-ASSIGN\n>=0.80'),
    ]
    label_colors = [RED, WARN_FG, GOLD, OK_FG]
    for (lo, hi, bg, lbl), lc in zip(segments, label_colors):
        sx = x + lo * w
        sw = (hi - lo) * w
        r = mpatches.Rectangle((sx, y), sw, h, facecolor=bg, edgecolor='#000022', lw=0.5)
        ax.add_patch(r)
        lines = lbl.split('\n')
        for j, ln in enumerate(lines):
            ax.text(sx + sw / 2, y + h / 2 + (0.5 - j) * 3.5, ln,
                    ha='center', va='center', fontsize=5.5,
                    color=lc, fontfamily='monospace', fontweight='bold')
    # Marcadores numericos
    for v, lbl in [(0.30, '0.30'), (0.50, '0.50'), (0.80, '0.80')]:
        vx = x + v * w
        ax.plot([vx, vx], [y - 1, y + h + 1], color=FG, lw=0.8, ls='--', alpha=0.5)
        ax.text(vx, y - 3, lbl, ha='center', va='top', fontsize=5.5, color=LGRAY,
                fontfamily='monospace')


def note_box(ax, x, y, w, h, text, bg=WARN_BG, fg=WARN_FG, label='ATENCAO'):
    """Caixa de nota/aviso."""
    r = mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.5',
        facecolor=bg, edgecolor=fg, lw=1.0)
    ax.add_patch(r)
    ax.text(x + 3, y + h - 4, f'[{label}]', ha='left', va='top',
            fontsize=6.5, color=fg, fontweight='bold', fontfamily='monospace')
    # Quebrar texto
    wrapped = textwrap.wrap(text, width=max(int(w // 2.2), 20))
    for i, ln in enumerate(wrapped[:6]):
        ax.text(x + 3, y + h - 10 - i * 7, ln, ha='left', va='top',
                fontsize=6.0, color=fg, fontfamily='monospace')


def example_dxf_json(ax, dxf_lines, json_lines, x=3, y=95, fs=6.0, leading=6.8):
    """Renderiza par DXF input / JSON output lado a lado."""
    mid = 50
    # DXF
    ax.text(x, y, 'DXF input:', ha='left', va='top', fontsize=fs,
            color=BLUE, fontweight='bold', fontfamily='monospace')
    for i, ln in enumerate(dxf_lines):
        ax.text(x, y - leading - i * leading, ln, ha='left', va='top',
                fontsize=fs, color=LGRAY, fontfamily='monospace')

    # JSON
    ax.text(mid, y, 'JSON output:', ha='left', va='top', fontsize=fs,
            color=GREEN, fontweight='bold', fontfamily='monospace')
    for i, ln in enumerate(json_lines):
        ax.text(mid, y - leading - i * leading, ln, ha='left', va='top',
                fontsize=fs, color=CYAN, fontfamily='monospace')


# ==========================================================================
# PILARES — 12 PAGINAS
# ==========================================================================

def pilares_pdf(path):
    total = 12
    with PdfPages(str(path)) as pdf:

        # ---- P-1: Visao Geral + Regex RE_PILAR ----
        pg = 1
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-1', 'Identificacao — RE_PILAR + Texto DXF')
        divider(fig)

        # Esquerda: diagrama visual pilar
        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'Diagrama: TEXT → LWPOLYLINE')
        radius_diagram(ax_l)
        # Confidence bar
        confidence_bar(ax_l, x=5, y=5, w=90, h=8)

        # Direita: regex + codigo de extracao
        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'RE_PILAR — regex de deteccao')
        code_lines(ax_r, [
            'import re',
            '',
            'RE_PILAR = re.compile(',
            '    r\'^(PC?\\.?-?\\d+([A-Z]|\\.\\d+|-\\d+)?|P-\\d+[A-Z]?)$\',',
            '    re.IGNORECASE',
            ')',
            '',
            '# CASAM:  P1  P17  PC1  P-1  P1A  P-1A  P.1',
            '# NAO:    PL1  PD1  P (sem num)  PONTALETE',
            '',
            'for e in msp:',
            '    etype = e.dxftype()',
            '    if etype == \'TEXT\':',
            '        text  = getattr(e.dxf, \'text\', \'\').strip()',
            '        x, y  = float(e.dxf.insert.x), float(e.dxf.insert.y)',
            '        layer = e.dxf.layer',
            '    elif etype == \'MTEXT\':',
            '        text = e.plain_text()  # ou plain_mtext()',
            '        x, y  = float(e.dxf.insert.x), float(e.dxf.insert.y)',
            '        layer = e.dxf.layer',
            '    else:',
            '        continue',
            '',
            '    if text and RE_PILAR.match(text):',
            '        pilares_txt.append({',
            '            \'text\': text, \'x\': x, \'y\': y, \'layer\': layer',
            '        })',
        ], highlight=[3, 4, 5])

        footer_bar(fig, pg, total, 'SPEC-PILARES.md §1.1-1.2')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-2: Associacao Texto-Poligono (3 Raios) ----
        pg = 2
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-2', 'Associacao Texto-Poligono — Logica 3 Raios')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'PILAR_SEARCH_RADIUS = 800mm')
        radius_diagram(ax_l, r1=7, r2=18, r3=42)

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Codigo: associar_pilar()')
        code_lines(ax_r, [
            'from shapely.geometry import Polygon, Point',
            '',
            'PILAR_SEARCH_RADIUS = 800.0  # mm',
            '',
            'def associar_pilar(pilar_txt, polylines):',
            '    px, py = pilar_txt[\'x\'], pilar_txt[\'y\']',
            '    melhor, melhor_score = None, 0.0',
            '',
            '    for poly in polylines:',
            '        if not poly[\'closed\'] or len(poly[\'points\']) < 3:',
            '            continue  # apenas LWPOLYLINE FECHADAS',
            '',
            '        polygon = Polygon(poly[\'points\'])',
            '        ponto   = Point(px, py)',
            '        dist    = polygon.distance(ponto)',
            '',
            '        # Raio 1: texto DENTRO do poligono',
            '        if polygon.contains(ponto):',
            '            score = 1.0',
            '        # Raio 2: tocando (dist <= 5mm)',
            '        elif dist <= 5.0:',
            '            score = 0.8',
            '        # Raio 3: decaimento linear ate search_radius',
            '        elif dist <= PILAR_SEARCH_RADIUS:',
            '            score = 0.5 * (1.0 - dist / PILAR_SEARCH_RADIUS)',
            '        else:',
            '            continue  # fora do raio',
            '',
            '        if score > melhor_score:',
            '            melhor_score = score',
            '            melhor = poly',
            '',
            '    return melhor, melhor_score',
        ], highlight=[18, 21, 24, 25])

        footer_bar(fig, pg, total, 'SPEC-PILARES.md §1.3')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-3: Extracao de Dimensoes ----
        pg = 3
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-3', 'Extracao de Dimensoes — comprimento e largura')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'DIM_SEARCH_RADIUS = 600mm')
        # Diagrama: pilar com texto de dimensao
        ax_l.text(50, 90, 'Pilar P17 (secao 20x50)', ha='center', va='top',
                  fontsize=7, color=ACCENT, fontweight='bold', fontfamily='monospace')
        # Pilar retangular
        pw, ph = 12, 28
        ax_l.add_patch(mpatches.Rectangle((38, 48), pw, ph,
            facecolor='#332200', edgecolor=GOLD, lw=2.0))
        ax_l.text(44, 62, 'P17', ha='center', va='center',
                  fontsize=8, color=GOLD, fontfamily='monospace', fontweight='bold')
        # Texto de dimensao (dentro do raio)
        ax_l.plot(58, 73, 's', color=GREEN, ms=7)
        ax_l.text(62, 73, '"20x50"', ha='left', va='center',
                  fontsize=7, color=GREEN, fontfamily='monospace')
        # Circulo de raio
        import numpy as np
        theta = np.linspace(0, 2 * math.pi, 200)
        r_dim = 25
        ax_l.plot(44 + r_dim * np.cos(theta), 62 + r_dim * np.sin(theta),
                  color=CYAN, lw=0.7, ls='--', alpha=0.6)
        ax_l.text(44 + r_dim + 1, 62, 'R=600mm', fontsize=5.5, color=CYAN,
                  fontfamily='monospace')
        # Resultado
        ax_l.text(25, 25, 'comprimento = max(50,20) = 50 cm', ha='left', va='top',
                  fontsize=6.5, color=CYAN, fontfamily='monospace')
        ax_l.text(25, 18, 'largura     = min(50,20) = 20 cm', ha='left', va='top',
                  fontsize=6.5, color=LGRAY, fontfamily='monospace')
        note_box(ax_l, 5, 3, 90, 12,
                 'comprimento = SEMPRE o lado MAIOR. Se comprimento < largura: trocar valores.',
                 label='REGRA PILAR')

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Codigo: extrair_dimensoes()')
        code_lines(ax_r, [
            'RE_DIM    = re.compile(r\'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})\')',
            'RE_DIM_BH = re.compile(',
            '    r\'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})\',',
            '    re.IGNORECASE | re.DOTALL',
            ')',
            '',
            'DIM_SEARCH_RADIUS = 600.0  # mm',
            '',
            'def extrair_dimensoes(pilar_center, texts):',
            '    """Retorna (comprimento, largura) em cm.',
            '    comprimento = lado MAIOR, largura = lado MENOR.',
            '    """',
            '    cx, cy = pilar_center',
            '    for t in texts:',
            '        if abs(t[\'x\'] - cx) > DIM_SEARCH_RADIUS: continue',
            '        if abs(t[\'y\'] - cy) > DIM_SEARCH_RADIUS: continue',
            '',
            '        # Formato "20x50"',
            '        m = RE_DIM.search(t[\'text\'])',
            '        if m:',
            '            d1, d2 = float(m.group(1)), float(m.group(2))',
            '            return max(d1, d2), min(d1, d2)  # c, l',
            '',
            '        # Formato "b=20 h=50"',
            '        m = RE_DIM_BH.search(t[\'text\'])',
            '        if m:',
            '            d1, d2 = float(m.group(1)), float(m.group(2))',
            '            return max(d1, d2), min(d1, d2)',
            '',
            '    return 0.0, 0.0  # nao encontrado → revisao humana',
        ], highlight=[0, 20, 21])

        footer_bar(fig, pg, total, 'SPEC-PILARES.md §2.2')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-4: Schema JSON FichaFase3Pilar ----
        pg = 4
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-4', 'Schema JSON — FichaFase3Pilar (todos os campos)')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'Campos de Identificacao e Geometria')
        json_block(ax_l, [
            ('id',               '"P17"',    'texto original DXF',          True),
            ('numero',           '"17"',     'so digitos do id',            True),
            ('pavimento',        '"TERREO"', 'nome do arquivo DXF',         True),
            ('pavimento_numero', '0',        '0=terreo 1=1pav etc',         False),
            ('obra',             '"ALIMONTI-PARAISO"', 'pasta raiz',        True),
            ('comprimento',      '40.0',     'cm — lado MAIOR',             True),
            ('largura',          '20.0',     'cm — lado MENOR',             True),
            ('altura_cm',        '280.0',    'nivel_chegada-nivel_saida',   True),
            ('nivel_saida_m',    '0.0',      'cota piso (m)',               False),
            ('nivel_chegada_m',  '2.80',     'cota teto (m)',               False),
        ], title='FichaFase3Pilar — parte 1')

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Armadura e Metadados')
        json_block(ax_r, [
            ('par_1_2',  '"8"',   'barras piso1→piso2',     False),
            ('par_2_3',  '"0"',   'barras piso2→piso3',     False),
            ('par_3_4',  '"0"',   '...',                    False),
            ('par_8_9',  '"0"',   'ate par_8_9',            False),
            ('grade_1',  '"8"',   'diametro estribo mm',    False),
            ('distancia_1', '"10"', 'espacamento cm',       False),
            ('grade_2',  '""',    'diametro 2o estribo',    False),
            ('pilar_especial', 'False', 'L / T / CAMBOTADO',True),
            ('tipo_pilar_especial', '"L"', 'se pilar_especial=True', False),
            ('confidence', '0.92', '0.0-1.0',               True),
            ('revisado_por_humano', 'False', '',             False),
        ], title='FichaFase3Pilar — parte 2')

        footer_bar(fig, pg, total, 'SPEC-PILARES.md §2.1 | ficha_pilares_schema.py')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-5: Layers de Pilar ----
        pg = 5
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-5', 'Layers — CONFIG-LAYERS por Familia')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'Layers para Textos e Geometria')
        layer_table(ax_l, [
            ('NOMENCLATURA',       'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('texto',              'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('TEXTO_GERAL',        'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('00 - FELIPE',        'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('Paineis / Pain?is',  'PANEL_GEOMETRY',  'Contorno pilar','HIGH'),
            ('PAINEL',             'PANEL_GEOMETRY',  'Contorno pilar','HIGH'),
            ('Texto Secao',        'SECTION_TEXT',    'Dim 20x50',     'HIGH'),
            ('COTA / cotas',       'DIMENSION_LINES', 'Ignorar',       'N/A'),
            ('NIVEL',              'ELEVATION_MARK',  'Cota Z',        'HIGH'),
            ('SARR_2.2x7',         'BATTEN_2x7',      'Sarrafo',       'HIGH'),
            ('SARR_7x7',           'BATTEN_7x7',      'Canto pilar',   'HIGH'),
            ('CHAPA',              'PLATE_GEOMETRY',  'Compensado',    'HIGH'),
            ('GRAVATA',            'CLAMP_LAYER',     'Gravata metal', 'MEDIUM'),
            ('S-COLS / 1 / 2',     'TQS_COLUMN',      'Pilar TQS',     'MEDIUM'),
        ], title='Mapeamento Layer → Canonical (BIM + TQS)')

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Deteccao de Familia + normalize_layer()')
        code_lines(ax_r, [
            'import unicodedata',
            '',
            'def normalize_layer(name: str) -> str:',
            '    """Normaliza para comparacao sem acentos e case."""',
            '    nfkd = unicodedata.normalize(\'NFKD\', str(name))',
            '    ascii = nfkd.encode(\'ascii\', \'ignore\').decode()',
            '    return ascii.upper().strip()',
            '',
            '# norm("Paineis") == norm("Pain?is") == "PAINEIS"',
            '',
            'def detectar_familia(layers: list) -> str:',
            '    """BIM / TQS / METHODUS / EBERICK."""',
            '    if any(l.startswith(\'MTH-\') for l in layers):',
            '        return \'METHODUS\'',
            '    tx_count = sum(1 for l in layers if l.startswith(\'TX\'))',
            '    if tx_count / len(layers) > 0.15:',
            '        return \'EBERICK\'',
            '    num_count = sum(1 for l in layers if l.isdigit())',
            '    if num_count / len(layers) > 0.30:',
            '        return \'TQS\'',
            '    return \'BIM\'  # default',
            '',
            '# Layer "Paineis" sofre corrupcao CP1252:',
            '# DXF salvo em CP1252 → lido como UTF-8 → "Pain?is"',
            '# SEMPRE usar normalize_layer() antes de comparar',
        ], highlight=[2, 3, 4, 5, 6, 8])

        footer_bar(fig, pg, total, 'CONFIG-LAYERS.yaml | SPEC-PILARES.md §1')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-6: Deteccao Pilar Cambotado ----
        pg = 6
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-6', 'Pilar Especial — Cambotado + Validacao')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'Tipos de Pilar Especial')
        # Retangular
        ax_l.add_patch(mpatches.Rectangle((10, 60), 15, 25,
            facecolor='#332200', edgecolor=GOLD, lw=1.5))
        ax_l.text(17, 50, 'RET', ha='center', fontsize=6, color=GOLD, fontfamily='monospace')
        ax_l.text(17, 44, 'bulge=0.0', ha='center', fontsize=5.5, color=LGRAY, fontfamily='monospace')

        # L-shape
        pts_L = [(35, 60), (35, 85), (43, 85), (43, 73), (50, 73), (50, 60)]
        ax_l.add_patch(mpatches.Polygon(pts_L, closed=True,
            facecolor='#003322', edgecolor=CYAN, lw=1.5))
        ax_l.text(42, 50, 'PILAR L', ha='center', fontsize=6, color=CYAN, fontfamily='monospace')
        ax_l.text(42, 44, 'bulge=0.01-0.3', ha='center', fontsize=5.5, color=LGRAY, fontfamily='monospace')

        # Cambotado (curvo)
        theta_arc = np.linspace(-math.pi/2, math.pi/2, 30)
        xs_arc = [65 + 8 * math.cos(t) for t in theta_arc]
        ys_arc = [72 + 12 * math.sin(t) for t in theta_arc]
        xs_arc += [65 + 15, 65 - 3, 65 - 3]
        ys_arc += [72 - 12, 72 - 12, 72 + 12]
        ax_l.add_patch(mpatches.Polygon(list(zip(xs_arc, ys_arc)), closed=True,
            facecolor='#330022', edgecolor=RED, lw=1.5))
        ax_l.text(66, 50, 'CAMBOTADO', ha='center', fontsize=6, color=RED, fontfamily='monospace')
        ax_l.text(66, 44, 'bulge > 0.3', ha='center', fontsize=5.5, color=LGRAY, fontfamily='monospace')

        # Validacao
        ax_l.text(5, 36, 'VALIDACAO OBRIGATORIA:', ha='left', fontsize=6.5,
                  color=ACCENT, fontweight='bold', fontfamily='monospace')
        validacoes = [
            ('comprimento',  '10 - 200 cm',  'conf -= 0.3 se invalido'),
            ('largura',      '10 - 150 cm',  'conf -= 0.3 se invalido'),
            ('altura_cm',    '100 - 600 cm', 'conf -= 0.2 se invalido'),
            ('nivel_saida_m','-5.0 - 50.0 m','aceitar, avisar'),
            ('c >= l',       'obrigatorio',  'trocar se c < l'),
        ]
        for i, (campo, rng, acao) in enumerate(validacoes):
            y_v = 30 - i * 6
            ax_l.text(5,  y_v, campo, ha='left', fontsize=6, color=CYAN, fontfamily='monospace')
            ax_l.text(35, y_v, rng,   ha='left', fontsize=6, color=LGRAY, fontfamily='monospace')
            ax_l.text(62, y_v, acao,  ha='left', fontsize=6, color=WARN_FG, fontfamily='monospace')

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Codigo: detectar_cambotado()')
        code_lines(ax_r, [
            'def detectar_cambotado(polyline_entity):',
            '    """',
            '    Retorna (pilar_especial: bool, tipo: str).',
            '    Bulge = fator de curvatura do segmento LWPOLYLINE.',
            '    """',
            '    bulges = []',
            '    try:',
            '        bulges = [float(p[4]) if len(p) > 4 else 0.0',
            '                  for p in polyline_entity.get_points(\'xyzsb\')]',
            '    except Exception:',
            '        return False, \'L\'',
            '',
            '    max_bulge = max((abs(b) for b in bulges), default=0.0)',
            '',
            '    if max_bulge > 0.3:',
            '        return True, \'CAMBOTADO\'   # pilar curvo',
            '    elif max_bulge > 0.01:',
            '        return True, \'L\'           # pilar L ou T',
            '    return False, \'L\'',
            '',
            '# Uso:',
            'pilar_especial, tipo = detectar_cambotado(entity)',
            'ficha[\'pilar_especial\']      = pilar_especial',
            'ficha[\'tipo_pilar_especial\'] = tipo',
        ], highlight=[14, 15, 16, 17])

        footer_bar(fig, pg, total, 'SPEC-PILARES.md §2.5 + §3')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-7: Exemplo Real ALIMONTI P17 ----
        pg = 7
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-7', 'Exemplo Real — ALIMONTI P17 (Raio 1: score=1.0)')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'DXF Entrada (ALIMONTI - PARAISO - PL)')
        example_dxf_json(ax_l,
            dxf_lines=[
                'TEXT  layer=NOMENCLATURA',
                '      text="P17"',
                '      insert=(17799, 3038)',
                '',
                'TEXT  layer=cotas',
                '      text="20x50"',
                '      insert=(17830, 3000)',
                '',
                'LWPOLYLINE layer=Paineis',
                '      closed=True',
                '      vertices=[',
                '        (17770,3010),',
                '        (17820,3010),',
                '        (17820,3066),',
                '        (17770,3066)',
                '      ]',
            ],
            json_lines=[
                '{',
                '  "id": "P17",',
                '  "numero": "17",',
                '  "comprimento": 50.0,',
                '  "largura": 20.0,',
                '  "confidence": 1.0,',
                '',
                '  // texto DENTRO da polilinha',
                '  // → Raio 1 → score = 1.0',
                '  // → AUTO-ASSIGN sem revisao',
                '}',
            ]
        )
        note_box(ax_l, 5, 3, 90, 10,
                 'Texto "P17" insert=(17799,3038) esta DENTRO da LWPOLYLINE '
                 '[(17770,3010)→(17820,3066)] → distance=0 → contains=True → score=1.0',
                 bg=OK_BG, fg=OK_FG, label='POR QUE score=1.0')

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Exemplo 2 — P5 adjacente (score=0.394)')
        example_dxf_json(ax_r,
            dxf_lines=[
                'TEXT  layer=NOMENCLATURA',
                '      text="P5"',
                '      insert=(16200, 2500)',
                '',
                'LWPOLYLINE layer=Paineis  closed=True',
                '      vertices=[',
                '        (16350,2400),(16400,2400),',
                '        (16400,2440),(16350,2440)',
                '      ]',
                '      # centro_poly ≈ (16375, 2420)',
                '      # dist("P5", centro) ≈ 170mm',
            ],
            json_lines=[
                '{',
                '  "id": "P5",',
                '  # dist = 170mm > 5mm',
                '  # dist < 800mm → Raio 3',
                '  # score = 0.5*(1 - 170/800)',
                '  #       = 0.5 * 0.7875',
                '  #       = 0.394',
                '',
                '  "confidence": 0.394,',
                '  "revisao": true,',
                '  // 0.394 < 0.80 →',
                '  // fila revisao humana',
                '}',
            ]
        )

        footer_bar(fig, pg, total, 'SPEC-PILARES.md §4')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-8: Decision Matrix Pilares ----
        pg = 8
        fig = fig_a3()
        header_bar(fig, 'PILAR', 'P-8', 'Matriz de Decisao — Casos Ambiguos')
        divider(fig)

        ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'Fallback Chain — Pilares')
        fallbacks = [
            ('1', 'RE_PILAR em NOMENCLATURA → LWPOLYLINE em Paineis', 'confidence = raio_score', OK_FG),
            ('2', 'RE_PILAR em TEXTO_GERAL  → LWPOLYLINE em Paineis', 'confidence -= 0.05',    GOLD),
            ('3', 'RE_PILAR em qualquer layer → LWPOLYLINE em qualquer', 'confidence -= 0.15', WARN_FG),
            ('4', 'RE_PILAR sem LWPOLYLINE proxima',                    'confidence -= 0.40',   RED),
            ('5', 'Sem texto RE_PILAR',                                 'NAO registrar',         DGRAY),
        ]
        for i, (num, cond, acao, cor) in enumerate(fallbacks):
            y_f = 90 - i * 16
            ax_l.add_patch(mpatches.FancyBboxPatch((3, y_f - 10), 94, 12,
                boxstyle='round,pad=0.3', facecolor='#0d0d22', edgecolor=cor, lw=0.8, alpha=0.7))
            ax_l.text(6, y_f - 2, f'[{num}]', ha='left', va='top',
                      fontsize=7, color=cor, fontweight='bold', fontfamily='monospace')
            ax_l.text(14, y_f - 2, cond, ha='left', va='top',
                      fontsize=6.2, color=FG, fontfamily='monospace')
            ax_l.text(14, y_f - 8, acao, ha='left', va='top',
                      fontsize=6.0, color=cor, fontfamily='monospace')

        ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Casos Especiais + Regras Fixas')
        casos = [
            ('comprimento <= 0',           'INVALIDO → revisao humana'),
            ('comprimento < largura',       'Trocar valores (c = maior)'),
            ('2 textos competindo',         'Vence score maior'),
            ('Empate exato de score',       'Fila revisao + log "EMPATE"'),
            ('Layer LWPOLYLINE desconhecido','Processar mesmo assim (-0.15)'),
            ('Encoding "Pain?is"',          'normalize_layer() sem penalidade'),
            ('Coordenadas UTM (x>50000)',   'Ignorar (nao e DXF de formas)'),
            ('bulge > 0.3',                 'tipo_pilar_especial = "CAMBOTADO"'),
        ]
        for i, (caso, acao) in enumerate(casos):
            yc = 90 - i * 10
            ax_r.text(3, yc, caso, ha='left', va='top', fontsize=6.2,
                      color=WARN_FG, fontfamily='monospace')
            ax_r.text(3, yc - 5.5, f'→ {acao}', ha='left', va='top', fontsize=6.0,
                      color=LGRAY, fontfamily='monospace')
            ax_r.plot([3, 97], [yc - 8, yc - 8], color='#1a1a33', lw=0.4)

        footer_bar(fig, pg, total, 'DECISION-MATRIX.md §3 + §4')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # ---- P-9 a P-12: campos restantes e confidence ----
        for pg, (sec_code, sec_title, left_title, right_title, lcode, rcode) in enumerate([
            ('P-9',  'Nivel e Altura — nivel_saida_m e altura_cm',
             'RE_NIVEL + layer NIVEL',
             'extrair_nivel() + calcular_altura()',
             ['RE_NIVEL = re.compile(',
              '    r\'[Nn][i\\xed]vel\\s*[=:]?\\s*',
              '    ([+-]?\\d+[.,]\\d+)\',',
              '    re.IGNORECASE',
              ')',
              '# Ex: "Nivel +2,80" → 2.80',
              '',
              'def extrair_nivel(texts, layer_target=\'NIVEL\'):',
              '    for t in texts:',
              '        if t[\'layer\'].upper() == layer_target.upper():',
              '            m = RE_NIVEL.search(t[\'text\'])',
              '            if m:',
              '                val = m.group(1).replace(\',\', \'.\')',
              '                return float(val)',
              '    return None',
              '',
              '# altura_cm = (nivel_chegada - nivel_saida) * 100',
              ],
             ['# Layers esperados para nivel:',
              '# NIVEL, "Nivel", "N?vel", "NIVEL 1 PAV.", "Texto Nivel"',
              '',
              '# Exemplo de texto no DXF:',
              '# TEXT layer=NIVEL text="h = 2.80" → 2.80',
              '# TEXT layer=NIVEL text="Nivel +2,80" → 2.80',
              '',
              '# Se nao encontrar nivel:',
              '# nivel_saida_m = pavimento_numero * 3.0  (estimativa)',
              '# nivel_chegada_m = nivel_saida_m + 2.80',
              '# confidence -= 0.10 (nivel estimado)',
              '',
              '# Pavimentos:',
              '# "TERREO" → pavimento_numero = 0',
              '# "1_PAVIMENTO" → 1',
              '# "2_PAVIMENTO" → 2  etc.',
              ]),
            ('P-10', 'Armadura — par_1_2..par_8_9 e grade_1..grade_3',
             'Texto de armadura em TEXT/MTEXT',
             'Patterns de armadura longitudinal + estribo',
             ['# Textos de armadura tipicos no DXF:',
              '# "8 fi 16" → 8 barras, diam 16mm',
              '# "Est fi 8 c/ 10" → estribo d=8 esp=10cm',
              '',
              'RE_BARRA = re.compile(',
              '    r\'(\\d+)\\s*[fF\\xf8\\u03c6]\\s*(\\d+)\')',
              'RE_ESTRIBO = re.compile(',
              '    r\'[Ee]st.*?(\\d+).*?c[/]?\\s*(\\d+)\')',
              '',
              '# par_1_2 = barras entre piso 1 e piso 2',
              '# par_2_3 = barras entre piso 2 e piso 3',
              '# (0 = sem info / sem mudanca)',
              '',
              '# grade_1 = diametro do estribo em mm',
              '# distancia_1 = espacamento em cm',
              '',
              '# Se nao encontrar texto de armadura:',
              '# par_1_2 = "0"  grade_1 = ""  (campos vazios)',
              '# Nao penaliza confidence (dado opcional)',
              ],
             ['# Layers com texto de armadura:',
              '# Texto Secao, NOMENCLATURA, texto',
              '',
              '# Exemplo DXF input:',
              '# MTEXT text="P17\\n20x50\\n8 fi 16\\nEst fi 8 c/10"',
              '',
              '# → par_1_2 = "8"',
              '# → comprimento = 50, largura = 20',
              '# → grade_1 = "8", distancia_1 = "10"',
              '',
              '# Extrair numero de pilar:',
              'def extrair_numero(pilar_id: str) -> str:',
              '    """P17 → 17  PC3 → 3  P-1A → 1"""',
              '    return \'\'.join(filter(str.isdigit, pilar_id)) or \'0\'',
              ]),
            ('P-11', 'Confidence — Formula e Log Obrigatorio',
             'Calcular confidence por pilar',
             'Log obrigatorio se confidence < 0.80',
             ['def calcular_confidence_pilar(',
              '        raio_score: float,',
              '        tem_dimensao: bool,',
              '        tem_texto_id: bool,',
              '        tem_contorno: bool) -> float:',
              '    """Confidence com penalidades acumuladas."""',
              '    conf = raio_score  # 1.0 / 0.8 / 0.0..0.5',
              '',
              '    if not tem_texto_id:',
              '        conf -= 0.40  # sem ID → penalidade severa',
              '    if not tem_dimensao:',
              '        conf -= 0.30  # sem dimensao',
              '    if not tem_contorno:',
              '        conf -= 0.40  # sem LWPOLYLINE',
              '',
              '    return max(0.0, min(conf, 1.0))',
              '',
              '# CONF_AUTO    = 0.80  # auto-assign',
              '# CONF_WARN    = 0.50  # aceitar com aviso',
              '# CONF_REVIEW  = 0.30  # revisao humana',
              '# CONF_REJECT  = 0.30  # rejeitar',
              ],
             ['# Log OBRIGATORIO para confidence < 0.80:',
              '',
              'log_entry = {',
              '    "elemento_id": "P17",',
              '    "tipo": "pilar",',
              '    "confidence": 0.65,',
              '    "motivo": "dim nao encontrada",',
              '    "acao": "revisao humana",',
              '    "raio_usado": 800,',
              '    "dist_texto_poligono": 145.3,',
              '    "layer_texto": "NOMENCLATURA",',
              '    "layer_poligono": "Paineis"',
              '}',
              '',
              '# Integridade cruzada:',
              '# pilar sem viga: len(links)==0 → "pilar isolado?"',
              '# area secao > 2500cm²: revisar',
              '# comprimento <= 0: INVALIDO',
              ]),
            ('P-12', 'Resumo — Fluxo Completo de Extracao',
             'Pipeline de extracao pilar (pseudocodigo)',
             'Checklist de campos obrigatorios',
             ['# FLUXO COMPLETO — 1 pilar:',
              '',
              'for pilar_txt in pilares_txt:',
              '    px, py = pilar_txt["x"], pilar_txt["y"]',
              '',
              '    # 1. Associar LWPOLYLINE',
              '    poly, raio_score = associar_pilar(pilar_txt, polylines)',
              '',
              '    # 2. Extrair dimensoes (DIM_SEARCH_RADIUS=600mm)',
              '    c, l = extrair_dimensoes((px,py), texts)',
              '',
              '    # 3. Extrair nivel',
              '    nivel = extrair_nivel(texts)',
              '',
              '    # 4. Detectar cambotado',
              '    esp, tipo = detectar_cambotado(poly["entity"])',
              '',
              '    # 5. Calcular confidence',
              '    conf = calcular_confidence_pilar(',
              '        raio_score,',
              '        tem_dimensao=(c > 0),',
              '        tem_texto_id=True,',
              '        tem_contorno=(poly is not None)',
              '    )',
              '',
              '    # 6. Decisao de aceite',
              '    if conf >= 0.80: auto_assign(ficha)',
              '    elif conf >= 0.30: fila_revisao(ficha)',
              '    else: rejeitar(ficha)',
              ],
             ['# CHECKLIST — campos obrigatorios:',
              '',
              '[ ] id            ← RE_PILAR match',
              '[ ] numero        ← digits(id)',
              '[ ] pavimento     ← nome DXF',
              '[ ] comprimento   ← max(d1,d2) via RE_DIM',
              '[ ] largura       ← min(d1,d2)',
              '[ ] confidence    ← raio_score + penalidades',
              '',
              '# CHECKLIST — campos opcionais:',
              '',
              '[ ] altura_cm     ← nivel_chegada-nivel_saida',
              '[ ] nivel_saida_m ← layer NIVEL',
              '[ ] par_1_2..8_9  ← texto armadura',
              '[ ] grade_1..3    ← texto estribo',
              '[ ] pilar_especial← bulge > 0.01',
              '',
              '# Se nao encontrar texto RE_PILAR:',
              '#   LWPOLYLINE sozinha NAO e pilar.',
              '#   Nao registrar.',
              ]),
        ], start=9):
            pg_num = pg + 8
            fig = fig_a3()
            header_bar(fig, 'PILAR', sec_code, sec_title)
            divider(fig)
            ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], left_title)
            code_lines(ax_l, lcode)
            ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], right_title)
            code_lines(ax_r, rcode)
            footer_bar(fig, pg_num, total, f'SPEC-PILARES.md | {sec_code}')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    print(f'[OK] Pilares: {path}')


# ==========================================================================
# VIGAS — 12 PAGINAS
# ==========================================================================

def vigas_pdf(path):
    total = 12
    with PdfPages(str(path)) as pdf:

        pages = [
            ('V-1', 'Identificacao — RE_VIGA + prefixos',
             'RE_VIGA e prefixos',
             'Extracao TEXT/MTEXT',
             ['RE_VIGA = re.compile(',
              '    r\'^(V|BA|VB|VT|VC)\\.?-?\\d+([A-Z]|\\.\\d+|/\\d+)?$\',',
              '    re.IGNORECASE',
              ')',
              '# CASAM: V1 V101 BA1 VB1 VT1 VC1 V1A V1.2 V-1',
              '# NAO:   VIGA  V  LV1',
              '',
              '# Prefixos:',
              '# V  → viga padrao (mais comum)',
              '# BA → balanco (_is_balanco = True)',
              '# VB → viga de bordo (balanco)',
              '# VT → viga tronco (secao variavel)',
              '# VC → viga curva (secao especial)',
              '',
              'def is_balanco(codigo: str) -> bool:',
              '    return bool(re.match(r\'^(BA|VB)\\d+\',',
              '                        codigo, re.IGNORECASE))',
              '# BA* e VB*: apoio_fim = "" e normal (nao e erro)',
              ],
             ['for e in msp:',
              '    if e.dxftype() == \'TEXT\':',
              '        text  = e.dxf.text.strip()',
              '        x, y  = e.dxf.insert.x, e.dxf.insert.y',
              '        layer = e.dxf.layer',
              '    elif e.dxftype() == \'MTEXT\':',
              '        text  = e.plain_text()  # MTEXT multi-linha',
              '        x, y  = e.dxf.insert.x, e.dxf.insert.y',
              '        layer = e.dxf.layer',
              '    else:',
              '        continue',
              '',
              '    if text and RE_VIGA.match(text):',
              '        vigas_txt.append({',
              '            \'text\': text, \'x\': x, \'y\': y,',
              '            \'layer\': layer',
              '        })',
              '',
              '# Layer esperado: NOMENCLATURA, texto, TEXTO_GERAL',
              ]),
            ('V-2', 'Geometria — LINE entities (LV e FV)',
             'VIGA usa LINE, nao LWPOLYLINE',
             'Layers: LV=Paineis  FV=fundo',
             ['# DIFERENCA CRITICA: PILAR vs VIGA',
              '# PILAR → LWPOLYLINE FECHADA (poligono)',
              '# VIGA  → LINE entities (LV + FV)',
              '',
              'VIGA_SEARCH_RADIUS = 1200.0  # mm',
              '',
              'lines = []',
              'for e in msp.query("LINE"):',
              '    lines.append({',
              '        \'start\': (e.dxf.start.x, e.dxf.start.y),',
              '        \'end\':   (e.dxf.end.x,   e.dxf.end.y),',
              '        \'layer\': e.dxf.layer,',
              '        \'length\': math.hypot(',
              '            e.dxf.end.x - e.dxf.start.x,',
              '            e.dxf.end.y - e.dxf.start.y',
              '        )',
              '    })',
              '',
              '# LV (Lateral de Viga) → layer "Paineis"',
              '# FV (Fundo de Viga)   → layer "fundo"',
              '# Ambos sao LINE, nao LWPOLYLINE',
              ],
             ['# Layers criticos de VIGA:',
              '',
              '# LV = Lateral',
              '# "Paineis" / "PAINEIS" / "Pain?is" → PANEL_GEOMETRY',
              '',
              '# FV = Fundo',
              '# "fundo" / "FUNDOS" / "Fundo da Viga" → BEAM_BOTTOM',
              '',
              'BEAM_BOTTOM_ALIASES = {',
              '    \'fundo\', \'fundos\',',
              '    \'fundo da viga\', \'fundo viga\', \'fv\'',
              '}',
              '',
              'def is_beam_bottom(layer: str) -> bool:',
              '    return layer.lower().strip() in BEAM_BOTTOM_ALIASES',
              '',
              '# Situacao: LV sem FV:',
              '# → registrar como LV somente',
              '# → marcar "fundo_ausente": True',
              ]),
            ('V-3', 'Dimensoes — largura e altura (b e h)',
             'RE_DIM e RE_DIM_BH (formato viga)',
             'DIFERENCA: viga b=menor h=maior (inverso do pilar)',
             ['RE_DIM    = re.compile(r\'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})\')',
              'RE_DIM_BH = re.compile(',
              '    r\'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})\',',
              '    re.IGNORECASE | re.DOTALL',
              ')',
              '',
              'def extrair_dim_viga(text: str):',
              '    """Retorna (largura, altura) em cm.',
              '    VIGA: largura=b (hor), altura=h (vert).',
              '    """',
              '    m = RE_DIM.search(text)',
              '    if m:',
              '        d1 = float(m.group(1))',
              '        d2 = float(m.group(2))',
              '        # b=menor, h=maior (convencao viga)',
              '        return min(d1,d2), max(d1,d2)',
              '',
              '    m = RE_DIM_BH.search(text)',
              '    if m:',
              '        # b e h ja explicitos no texto',
              '        return float(m.group(1)), float(m.group(2))',
              '',
              '    return 0.0, 0.0',
              ],
             ['# DIFERENCA PILAR vs VIGA:',
              '',
              '# Pilar:  comprimento = max(d1,d2)',
              '#         largura     = min(d1,d2)',
              '',
              '# Viga:   largura = b = min(d1,d2)',
              '#         altura  = h = max(d1,d2)',
              '',
              '# "20x50" → Viga: largura=20 altura=50',
              '# "50x20" → Viga: largura=20 altura=50 (mesmo)',
              '',
              '# VALIDACAO:',
              '# largura: 12 - 100 cm',
              '# altura:  25 - 200 cm',
              '# largura < altura (obrigatorio, b<h)',
              '',
              '# Sem dimensao (dist > DIM_SEARCH_RADIUS=600mm):',
              '#   largura=0, altura=0',
              '#   confidence -= 0.30',
              '#   log: "V1: dimensao nao encontrada"',
              ]),
            ('V-4', 'Schema JSON — FichaFase3Viga',
             'Campos principais',
             'Tramos + Armadura',
             ['# FichaFase3Viga — campos de geometria:',
              '',
              '{',
              '  "codigo": "V101",',
              '  "pavimento": "1_PAVIMENTO",',
              '  "tipo": "retangular",  # L / T',
              '  "largura": 20.0,       # b (cm)',
              '  "altura": 50.0,        # h (cm)',
              '  "comprimento": 480.0,  # span (cm)',
              '  "secao_transversal": {',
              '    "tipo": "RET",',
              '    "largura": 20.0,',
              '    "altura": 50.0,',
              '    "area_cm2": 1000.0',
              '  },',
              '  "confidence": 0.87',
              '}',
              ],
             ['"tramos": [',
              '  {',
              '    "apoio_ini": "P5",',
              '    "apoio_fim": "P8",  # "" se balanco',
              '    "comprimento": 480.0,',
              '    "laje_esq": "L3",',
              '    "laje_dir": "L4"',
              '  }',
              '],',
              '',
              '"armadura_positiva": {',
              '  "barras": 3,',
              '  "diametro": 16,',
              '  "posicao": "inferior"',
              '},',
              '"estribos": {',
              '  "diametro": 8,',
              '  "espacamento": 15',
              '},',
              '"garfos": {',
              '  "tipo": "HT20CT",',
              '  "quantidade": 4',
              '}',
              ]),
            ('V-5', 'Apoios — encontrar_apoios() + comprimento',
             'Pilares vizinhos → apoio_ini e apoio_fim',
             'INSERT blocks → GARFOS HT20CT',
             ['VIGA_SEARCH_RADIUS = 1200.0  # mm',
              '',
              'def encontrar_apoios(viga_pos, pilares_txt):',
              '    vx, vy = viga_pos',
              '    candidatos = []',
              '    for p in pilares_txt:',
              '        dist = math.hypot(p[\'x\']-vx, p[\'y\']-vy)',
              '        if dist <= VIGA_SEARCH_RADIUS:',
              '            conf = max(0.0, 1.0-dist/VIGA_SEARCH_RADIUS)',
              '            candidatos.append((p[\'text\'], dist, conf))',
              '    candidatos.sort(key=lambda x: x[1])',
              '    apoio_ini = candidatos[0][0] if candidatos else \'\'',
              '    apoio_fim = candidatos[1][0] if len(candidatos)>=2 else \'\'',
              '    return apoio_ini, apoio_fim',
              '',
              '# comprimento = distancia entre apoios:',
              'def calc_comprimento(p1, p2):',
              '    dist_mm = math.hypot(p1.x-p2.x, p1.y-p2.y)',
              '    return round(dist_mm / 10, 1)  # mm → cm',
              '# alerta: comprimento > 1500cm → revisar',
              ],
             ['# GARFOS HT20CT — INSERT blocks',
              '',
              'garfos = []',
              'for e in msp.query("INSERT"):',
              '    bn  = e.dxf.name.upper()',
              '    lay = e.dxf.layer.upper()',
              '    if \'GARFO\' in bn or \'HT20\' in bn or lay==\'GARFOS\':',
              '        garfos.append({',
              '            \'x\': e.dxf.insert.x,',
              '            \'y\': e.dxf.insert.y,',
              '            \'rotation\': e.dxf.rotation,',
              '            \'tipo\': \'HT20CT\' if \'HT20\' in bn else \'GARFO\'',
              '        })',
              '',
              '# Associar garfo → viga mais proxima',
              '# por proximidade espacial',
              '',
              '# Layer GARFOS → entidade INSERT',
              '# Block name: "HT20CT", "GARFO-HT20", etc.',
              ]),
            ('V-6', 'Layers Viga + Confidence',
             'CONFIG-LAYERS vigas (LV e FV)',
             'Confidence formula + Exemplos reais',
             ['# Layers criticos VIGA:',
              '',
              '# LV (Lateral de Viga):',
              '# "Paineis"/"Pain?is" → PANEL_GEOMETRY HIGH',
              '',
              '# FV (Fundo de Viga):',
              '# "fundo"/"FUNDOS"/"Fundo da Viga" → BEAM_BOTTOM HIGH',
              '',
              '# Outros layers LV:',
              '# Escoras → SHORING HIGH',
              '# GARFOS  → FORK_METAL HIGH',
              '# presilha → CLAMP_METAL HIGH',
              '# barrote  → BATTEN_BEAM HIGH',
              '# Forcador → SPACER HIGH',
              '# "BARRA DE ANCORAGEM" → ANCHOR_BAR_LV HIGH',
              '# (DIFERENTE de "BARRA ANCORAGEM" em PL!)',
              '# "SCO-___-LAJ" → SLAB_INTERFACE HIGH',
              '',
              '# NUNCA confundir:',
              '# PL layer "BARRA ANCORAGEM"    (sem "DE")',
              '# LV layer "BARRA DE ANCORAGEM" (com "DE")',
              ],
             ['# EXEMPLOS REAIS:',
              '',
              '# DXF: V101 + "20x50" + LINE em Paineis/fundo',
              '# → largura=20 altura=50 confidence=0.92',
              '',
              '# DXF: BA3 + "15x40" (balanco)',
              '# → apoio_fim="" (esperado)',
              '# → confidence=0.75',
              '',
              '# DXF: V205 MTEXT "V205\\nb=25 h=60"',
              '# → largura=25 altura=60 confidence=0.88',
              '',
              '# Confidence viga:',
              '# base = raio_score',
              '# -0.30 sem dimensao',
              '# -0.15 se line em layer nao-Paineis',
              '# -0.20 sem tramos',
              '# alerta: comprimento > 1500cm',
              '# alerta: largura > altura (b<h obrigatorio)',
              ]),
        ]

        for pg_num, (sec_code, sec_title, lt, rt, lc, rc) in enumerate(pages, start=1):
            fig = fig_a3()
            header_bar(fig, 'VIGA', sec_code, sec_title)
            divider(fig)
            ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], lt)
            code_lines(ax_l, lc)
            ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], rt)
            code_lines(ax_r, rc)
            footer_bar(fig, pg_num, total, f'SPEC-VIGAS.md | {sec_code}')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

        # Paginas 7-12: camadas adicionais
        extra = [
            ('V-7', 'Validacao Completa + Decision Matrix',
             ['# VALIDACAO — FichaFase3Viga:',
              '',
              '# largura:     12 - 100 cm',
              '# altura:      25 - 200 cm',
              '# comprimento: > 0 cm',
              '# tipo:        retangular / L / T',
              '# tramos:      >= 1',
              '# largura < altura OBRIGATORIO',
              '',
              '# Se largura > altura: TROCAR',
              '# largura, altura = altura, largura',
              '',
              '# Fallback Chain Vigas:',
              '# 1. RE_VIGA em NOMENCLATURA → LINE em Paineis/fundo',
              '#    confidence = raio_score',
              '# 2. RE_VIGA → LINE em layer nao-Paineis',
              '#    confidence -= 0.15',
              '# 3. RE_VIGA + RE_DIM → dim extraida (+0)',
              '# 4. RE_VIGA sem dimensao',
              '#    largura=0, altura=0, confidence -= 0.30',
              '# 5. BA*/VB* → apoio_fim="" e correto',
              ],
             ['# Integridade cruzada VIGAS:',
              '',
              '# viga sem apoio_ini (e nao balanco):',
              '#   apoio_ini == "" → log aviso',
              '',
              '# comprimento estimado > 1500cm:',
              '#   → "revisar comprimento"',
              '',
              '# Casos especiais:',
              '# MTEXT pode conter ID + dim na mesma entidade:',
              '# "V205\\nb=25 h=60"',
              '# → extrair V205 (RE_VIGA)',
              '# → extrair b=25 h=60 (RE_DIM_BH)',
              '',
              '# Garfos INSERT → associar por proximidade',
              '# (nao por layer do texto de ID)',
              '',
              '# Layer "fundo" vs "Paineis":',
              '# LV (lateral): linhas verticais (Paineis)',
              '# FV (fundo):   linha horizontal inferior (fundo)',
              ]),
        ]
        for page_data in extra:
            sec_code, sec_title, lc, rc = page_data
            pg_num += 1
            fig = fig_a3()
            header_bar(fig, 'VIGA', sec_code, sec_title)
            divider(fig)
            ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], 'Validacao e Fallbacks')
            code_lines(ax_l, lc)
            ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], 'Casos Especiais')
            code_lines(ax_r, rc)
            footer_bar(fig, pg_num, total, f'SPEC-VIGAS.md | {sec_code}')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

        # Preencher ate 12 paginas com resumos compactos
        summaries = [
            ('V-8',  'Fluxo Completo Viga', 'Pipeline de extracao', 'Checklist'),
            ('V-9',  'Secao Transversal',   'Tipos RET/L/T',        'area_cm2'),
            ('V-10', 'Lajes vizinhas',      'laje_esq e laje_dir',  'vigas_around'),
            ('V-11', 'Encoding + TQS',      'Pain?is no DXF',       'S-BEAM layer TQS'),
            ('V-12', 'Referencia rapida',   'Raios e thresholds',   'Todos os patterns'),
        ]
        flow_left = [
            '# FLUXO — 1 viga:',
            'for viga_txt in vigas_txt:',
            '    vx, vy = viga_txt["x"], viga_txt["y"]',
            '',
            '    # 1. Encontrar LINEs proximas',
            '    lv_lines = [l for l in lines',
            '        if norm(l["layer"]) == "PAINEIS"',
            '        and math.hypot(midx(l)-vx, midy(l)-vy)',
            '           <= VIGA_SEARCH_RADIUS]',
            '',
            '    # 2. Extrair dimensoes',
            '    b, h = extrair_dim_viga(text_proximo)',
            '',
            '    # 3. Encontrar apoios',
            '    ini, fim = encontrar_apoios((vx,vy), pilares)',
            '',
            '    # 4. Comprimento',
            '    comp = calc_comprimento(p_ini, p_fim)',
            '',
            '    # 5. Confidence',
            '    conf = calcular_confidence_viga(raio, b, ini)',
            '',
            '    # 6. Aceite',
            '    if conf >= 0.80: auto_assign(ficha)',
            '    else: fila_revisao(ficha)',
        ]
        flow_right = [
            '# CHECKLIST — FichaFase3Viga:',
            '',
            '[ ] codigo        ← RE_VIGA match',
            '[ ] pavimento     ← nome DXF',
            '[ ] largura       ← min(d1,d2) via RE_DIM',
            '[ ] altura        ← max(d1,d2)',
            '[ ] comprimento   ← dist(apoio_ini, apoio_fim)',
            '[ ] tramos[0]     ← apoio_ini + apoio_fim',
            '[ ] confidence    ← raio_score + penalidades',
            '',
            '# Opcionais:',
            '[ ] garfos        ← INSERT blocks',
            '[ ] armadura_pos  ← texto barras',
            '[ ] estribos      ← texto estribo',
            '',
            '# BA*/VB*: apoio_fim="" e CORRETO',
            '# NAO penalizar balanco sem apoio_fim',
            '',
            '# Raios de busca:',
            '# VIGA_SEARCH_RADIUS = 1200mm',
            '# DIM_SEARCH_RADIUS  =  600mm',
        ]
        for i, (sc, st, lt, rt) in enumerate(summaries):
            pg_num = 8 + i
            fig = fig_a3()
            header_bar(fig, 'VIGA', sc, st)
            divider(fig)
            ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], lt)
            ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], rt)
            if i == 0:
                code_lines(ax_l, flow_left)
                code_lines(ax_r, flow_right)
            else:
                code_lines(ax_l, [f'# {lt}', '', '# Ver SPEC-VIGAS.md para detalhes'])
                code_lines(ax_r, [f'# {rt}', '', '# Ver CONFIG-LAYERS.yaml para aliases'])
            footer_bar(fig, pg_num, total, f'SPEC-VIGAS.md | {sc}')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    print(f'[OK] Vigas: {path}')


# ==========================================================================
# LAJES — 8 PAGINAS
# ==========================================================================

def lajes_pdf(path):
    total = 8
    with PdfPages(str(path)) as pdf:

        pages_lj = [
            ('L-1', 'Identificacao — RE_LAJE + RE_LAJE_H',
             ['RE_LAJE = re.compile(',
              '    r\'^(L\\d+[A-Za-z]?|Y\\d+[A-Za-z]?|X\\d+[A-Za-z]?',
              '    |LAJ[-_]?\\d+|LAJE[-_\\s]*\\d+)$\',',
              '    re.IGNORECASE',
              ')',
              '# CASAM: L1 L12 L1A Y1 X2 LAJ-1 LAJE_2 LAJE 1',
              '# NAO:   L (sem num) LAJE (sem num)',
              '',
              'RE_LAJE_H = re.compile(',
              '    r\'h\\s*[=:]\\s*([\\d,.]+)\',',
              '    re.IGNORECASE',
              ')',
              '# Ex: "h=12" "h = 14" "h:10" "h=12cm"',
              '# → espessura em cm',
              '',
              'LAJE_SEARCH_RADIUS = 1500.0  # mm (maior)',
              'CLUSTER_RADIUS     =  500.0  # mm (h= cluster)',
              ],
             ['# Dois caminhos de identificacao:',
              '',
              '# Caminho A: texto ID explicito (L1, L2, Y1...)',
              '# - Mais confiavel, confidence base = raio_score',
              '',
              '# Caminho B: cluster de h= sem ID',
              '# - Gera laje SYNTHETIC',
              '# - confidence = 0.50 (contorno incerto)',
              '',
              '# Laje SYNTHETIC:',
              '# LajeDXF.name = "SYNTHETIC"',
              '# LajeDXF.id   = "synth_0", "synth_1"...',
              '',
              '# Extracao espessura:',
              'def extrair_espessura(texts, laje_pos):',
              '    lx, ly = laje_pos',
              '    candidatos = []',
              '    for t in texts:',
              '        m = RE_LAJE_H.search(t["text"])',
              '        if m:',
              '            dist = math.hypot(t["x"]-lx, t["y"]-ly)',
              '            if dist <= LAJE_SEARCH_RADIUS:',
              '                val = float(m.group(1).replace(",","."))',
              '                candidatos.append((val, dist))',
              '    candidatos.sort(key=lambda x: x[1])',
              '    return candidatos[0][0] if candidatos else 0.0',
              ]),
            ('L-2', 'Contorno — LWPOLYLINE + area Shoelace',
             ['# LWPOLYLINE FECHADA → contorno da laje',
              '# Discriminar por area:',
              '',
              'for e in msp.query("LWPOLYLINE"):',
              '    pts = [(float(p[0]),float(p[1]))',
              '           for p in e.get_points("xy")]',
              '    is_closed = (getattr(e.dxf,"flags",0) & 1 == 1)',
              '              or e.is_closed',
              '',
              '    if is_closed and len(pts) >= 3:',
              '        area = calcular_area_shoelace(pts)',
              '        if area > 50000:   # > 50.000 mm² → LAJE',
              '            candidatos_laje.append(pts)',
              '        elif area < 5000:  # < 5.000 mm² → PILAR',
              '            candidatos_pilar.append(pts)',
              '',
              'def calcular_area_shoelace(pts) -> float:',
              '    """Area em mm²."""',
              '    n = len(pts)',
              '    area = 0.0',
              '    for i in range(n):',
              '        j = (i+1) % n',
              '        area += pts[i][0] * pts[j][1]',
              '        area -= pts[j][0] * pts[i][1]',
              '    return abs(area) / 2.0',
              ],
             ['# Layers de contorno de laje:',
              '# "Paineis"/"Pain?is" → PANEL_GEOMETRY',
              '# (mesmos aliases do pilar, mas area > 50000mm²)',
              '',
              '# Discrimicacao PILAR vs LAJE:',
              '# area < 5.000 mm²  → pilar',
              '# area > 50.000 mm² → laje',
              '# 5.000 < area < 50.000 → ambiguo (log)',
              '',
              '# dimensoes da laje a partir do bbox:',
              'from shapely.geometry import Polygon',
              '',
              'poly = Polygon(outline_pts)',
              'bbox = poly.bounds  # (minx,miny,maxx,maxy)',
              'comp = (bbox[2]-bbox[0]) / 10  # mm → cm',
              'larg = (bbox[3]-bbox[1]) / 10',
              '',
              '# area_m2 = area_mm2 / 1_000_000',
              '# espessura validacao:',
              '# < 7cm → invalida (confidence = 0)',
              '# > 40cm → suspeita (log aviso)',
              ]),
            ('L-3', 'Laje Sintetica — cluster de h=',
             ['def gerar_lajes_sinteticas(laje_dims) -> list:',
              '    """Agrupa h= proximos → laje SYNTHETIC."""',
              '    used = set()',
              '    clusters = []',
              '    for i, d in enumerate(laje_dims):',
              '        if i in used: continue',
              '        cluster = [d]',
              '        used.add(i)',
              '        for j, d2 in enumerate(laje_dims):',
              '            if j in used: continue',
              '            dist = math.hypot(',
              '                d["x"]-d2["x"], d["y"]-d2["y"])',
              '            if dist < CLUSTER_RADIUS:  # 500mm',
              '                cluster.append(d2)',
              '                used.add(j)',
              '        clusters.append(cluster)',
              '',
              '    sinteticas = []',
              '    for idx, cluster in enumerate(clusters):',
              '        cx = sum(d["x"] for d in cluster)/len(cluster)',
              '        cy = sum(d["y"] for d in cluster)/len(cluster)',
              '        h_val = cluster[0]["h_val"]',
              '        sinteticas.append({',
              '            "id": f"synth_{idx}",',
              '            "name": "SYNTHETIC",',
              '            "x": cx, "y": cy,',
              '            "espessura": h_val,',
              '            "confidence": 0.50',
              '        })',
              '    return sinteticas',
              ],
             ['# Exemplo:',
              '# 3 textos "h=10" dentro de 300mm entre si',
              '# → 1 cluster → 1 laje synth_0',
              '',
              '# DXF input:',
              '# TEXT layer=COTA text="h=10" insert=(3000,8000)',
              '# TEXT layer=COTA text="h=10" insert=(3200,8100)',
              '# TEXT layer=COTA text="h=10" insert=(3100,7900)',
              '',
              '# JSON output:',
              '# {',
              '#   "codigo": "synth_0",',
              '#   "tipo": "macica",',
              '#   "espessura": 10.0,',
              '#   "outline_segs": [],',
              '#   "confidence": 0.50',
              '# }',
              '',
              '# SYNTHETIC nao e erro — e laje real',
              '# sem ID explicito no DXF',
              '# Requer revisao (confidence=0.50 < 0.80)',
              ]),
            ('L-4', 'Schema JSON + Layers Laje',
             ['"FichaFase3Laje":',
              '{',
              '  "codigo": "L5",',
              '  "pavimento": "1_PAVIMENTO",',
              '  "tipo": "macica",  # pre_moldada / steel_deck',
              '  "espessura": 12.0,  # cm via RE_LAJE_H',
              '  "dimensoes": {',
              '    "comprimento": 620.0,  # cm bbox',
              '    "largura": 430.0,',
              '    "espessura": 12.0',
              '  },',
              '  "outline_segs": [  # vertices em mm DXF',
              '    {"x":15000.0,"y":10000.0},',
              '    {"x":21200.0,"y":10000.0},',
              '    ...',
              '  ],',
              '  "nivel": 2.80,',
              '  "vigas_around": ["V101","V102","V103","V104"],',
              '  "pilares_around": ["P5","P6","P7","P8"],',
              '  "confidence": 0.70',
              '}',
              ],
             ['# Layers criticos LAJE:',
              '',
              '# EST-LAJE-TEXT → SLAB_TEXT  (IDs L1,L2...)',
              '# NOMENCLATURA  → ELEMENT_LABEL',
              '# Pilares       → PILLAR_CUTOUT (recortes)',
              '# VIGAS         → BEAM_INTERFACE',
              '# "Vazios"/"V?zio" → VOID_OPENING',
              '# REAPROVEITAMENTO → REUSE_STATUS',
              '# "Paineis"     → PANEL_GEOMETRY (fundo)',
              '# EST-PILAR-CUT → PILLAR_CUT',
              '',
              '# Encoding CRITICO — layer "Vazio":',
              'VOID_ALIASES = {',
              '    "vazio","vazios","abertura",',
              '    "aberturas","buraco","void"',
              '}',
              '',
              'def is_void_layer(layer: str) -> bool:',
              '    n = normalize_layer(layer).lower()',
              '    return n in VOID_ALIASES or "vaz" in n',
              ]),
            ('L-5', 'Confidence Laje + Recortes + Validacao',
             ['def calcular_confidence_laje(laje) -> float:',
              '    conf = 0.30  # base',
              '    if laje.get("espessura", 0) > 0:',
              '        conf += 0.30',
              '    if laje.get("outline_segs") and \\',
              '       len(laje["outline_segs"]) >= 3:',
              '        conf += 0.20',
              '    if laje.get("vigas_around"):',
              '        conf += 0.20',
              '    return min(conf, 1.0)',
              '',
              '# SYNTHETIC: conf=0.50 (espessura OK, contorno nao)',
              '',
              '# Recortes de pilares na laje:',
              'def detectar_recortes(laje_contorno, polylines):',
              '    laje_poly = Polygon(laje_contorno)',
              '    recortes = []',
              '    for poly in polylines:',
              '        if not poly["closed"]: continue',
              '        ln = normalize_layer(poly["layer"])',
              '        if ln not in ("PILARES","EST-PILAR-CUT"):',
              '            continue',
              '        rp = Polygon(poly["points"])',
              '        if laje_poly.intersects(rp):',
              '            recortes.append({',
              '                "pontos": poly["points"],',
              '                "area": rp.area',
              '            })',
              '    return recortes',
              ],
             ['# VALIDACAO — FichaFase3Laje:',
              '',
              '# espessura:  7 - 40 cm',
              '# < 7cm: invalida → confidence = 0',
              '',
              '# outline_segs: >= 3 vertices',
              '# se < 3: confidence -= 0.2, marcar SYNTHETIC',
              '',
              '# dimensoes.comprimento: > 0 cm',
              '# dimensoes.largura:     > 0 cm',
              '',
              '# tipo: "macica"/"pre_moldada"/"steel_deck"',
              '# default: "macica"',
              '',
              '# Integridade cruzada:',
              '# laje sem vigas vizinhas → "suspeito"',
              '# espessura==0 e nao SYNTHETIC → erro',
              '',
              '# Pre-moldada:',
              '# "h=12" + INSERT blocks de vigotas',
              '# Layer tipico: "barrote" ou "EST-SIMB"',
              '# tipo = "pre_moldada"',
              '',
              '# Laje grande sem contorno:',
              '# usar bbox das vigas_around (conf=0.40)',
              ]),
            ('L-6', 'Exemplos Reais — L5 e synth_0 e L3 com Abertura',
             ['# Exemplo 1 — L5 com ID explicito:',
              '# TEXT layer=EST-LAJE-TEXT text="L5"',
              '#      insert=(18000, 12000)',
              '# TEXT layer=COTA text="h=12"',
              '#      insert=(18100, 11900)',
              '# LWPOLYLINE layer=Paineis closed=True',
              '#   vertices=[(15000,10000),(21200,10000),',
              '#             (21200,14300),(15000,14300)]',
              '',
              '# → JSON:',
              '# codigo = "L5"',
              '# espessura = 12.0 cm',
              '# dimensoes = {comp:620, larg:430, esp:12}',
              '# confidence = 1.0',
              '',
              '# Exemplo 2 — synth_0:',
              '# 3x TEXT "h=10" dentro de 300mm',
              '# → codigo = "synth_0"',
              '# → espessura = 10.0 cm',
              '# → confidence = 0.50',
              ],
             ['# Exemplo 3 — L3 com Abertura:',
              '# TEXT layer=EST-LAJE-TEXT text="L3"',
              '#      insert=(6000, 6000)',
              '# LWPOLYLINE layer=Vazio closed=True',
              '#   vertices=[(5800,5900),(5900,5900),',
              '#             (5900,6100),(5800,6100)]',
              '',
              '# → JSON:',
              '# codigo = "L3"',
              '# aberturas = [',
              '#   {pontos: [...], area: 20000.0}',
              '# ]',
              '# confidence = 0.80',
              '',
              '# Encoding "Vazio":',
              '# CP1252 → UTF-8 → "V?zio"',
              '# normalize_layer("V?zio") == "VAZIO"',
              '# → is_void_layer() retorna True',
              '',
              '# SEMPRE usar normalize_layer() para',
              '# comparar layers com acentos',
              ]),
            ('L-7', 'Fluxo Completo Laje + Checklist',
             ['# FLUXO — 1 laje:',
              '',
              '# Caminho A (ID explicito):',
              'for laje_txt in lajes_txt:',
              '    lx, ly = laje_txt["x"], laje_txt["y"]',
              '',
              '    # 1. Buscar LWPOLYLINE grande proxima',
              '    contorno = buscar_contorno(',
              '        (lx,ly), polylines,',
              '        area_min=50000,',
              '        raio=LAJE_SEARCH_RADIUS',
              '    )',
              '',
              '    # 2. Extrair espessura',
              '    h = extrair_espessura(texts, (lx,ly))',
              '',
              '    # 3. Detectar aberturas',
              '    aberturas = detectar_aberturas(contorno, polys)',
              '',
              '    # 4. Vigas e pilares vizinhos',
              '    vigas   = vizinhos(vigas_txt,   lx, ly)',
              '    pilares = vizinhos(pilares_txt, lx, ly)',
              '',
              '    # 5. Confidence',
              '    conf = calcular_confidence_laje({',
              '        "espessura": h,',
              '        "outline_segs": contorno,',
              '        "vigas_around": vigas',
              '    })',
              ],
             ['# Caminho B (SYNTHETIC):',
              'sinteticas = gerar_lajes_sinteticas(laje_dims)',
              '',
              '# CHECKLIST — FichaFase3Laje:',
              '',
              '[ ] codigo      ← RE_LAJE ou "synth_N"',
              '[ ] pavimento   ← nome DXF',
              '[ ] espessura   ← RE_LAJE_H (cm)',
              '[ ] outline_segs← LWPOLYLINE fechada grande',
              '[ ] confidence  ← formula 4 componentes',
              '',
              '# Opcionais:',
              '[ ] aberturas   ← LWPOLYLINE em Vazio',
              '[ ] nivel       ← layer NIVEL',
              '[ ] vigas_around← pilares proximos',
              '[ ] armadura    ← texto proximo',
              '',
              '# Raios de busca:',
              '# LAJE_SEARCH_RADIUS = 1500mm',
              '# CLUSTER_RADIUS     =  500mm',
              '# DIM_SEARCH_RADIUS  =  600mm',
              '',
              '# area minima para contorno laje: 50000mm²',
              ]),
            ('L-8', 'Referencia Rapida — Lajes',
             ['# TODOS OS PATTERNS — LAJES:',
              '',
              '# RE_LAJE:  L1 L12 L1A Y1 X2 LAJ-1 LAJE_2',
              '# RE_LAJE_H: h=12 h=14 h:10 h=12cm',
              '',
              '# LAYERS CANONICOS:',
              '# EST-LAJE-TEXT → SLAB_TEXT (IDs)',
              '# NOMENCLATURA  → ELEMENT_LABEL (alt)',
              '# Paineis/Pain?is → PANEL_GEOMETRY (contorno)',
              '# Pilares        → PILLAR_CUTOUT (recortes)',
              '# VIGAS          → BEAM_INTERFACE',
              '# Vazio/V?zio    → VOID_OPENING',
              '# REAPROVEITAMENTO → REUSE_STATUS',
              '',
              '# CONFIDENCE FORMULA:',
              '# base = 0.30',
              '# +0.30 se espessura > 0',
              '# +0.20 se outline_segs >= 3 vertices',
              '# +0.20 se vigas_around nao vazio',
              '# SYNTHETIC = 0.50 fixo',
              ],
             ['# THRESHOLDS:',
              '# >= 0.80: AUTO-ASSIGN',
              '# 0.50-0.79: aceitar com log aviso',
              '# 0.30-0.49: fila revisao humana',
              '# < 0.30: rejeitar',
              '',
              '# VALIDACOES:',
              '# espessura 7-40cm (< 7: invalida)',
              '# outline >= 3 vertices',
              '# tipo: macica/pre_moldada/steel_deck',
              '',
              '# CASOS ESPECIAIS:',
              '# pre-moldada: h= + INSERT vigotas',
              '# laje grande sem contorno: bbox vigas',
              '# h= conflito: usar texto mais proximo',
              '# encoding: normalize_layer() sempre',
              '',
              '# FONTES:',
              '# SPEC-LAJES.md',
              '# CONFIG-LAYERS.yaml §lajes',
              '# DECISION-MATRIX.md §4 (Lajes)',
              '# ficha_lajes_schema.py',
              ]),
        ]

        for pg_num, (sec_code, sec_title, lc, rc) in enumerate(pages_lj, start=1):
            fig = fig_a3()
            header_bar(fig, 'LAJE', sec_code, sec_title)
            divider(fig)
            ax_l = section_ax(fig, [0.02, 0.06, 0.46, 0.86], sec_code + ' — esquerda')
            code_lines(ax_l, lc)
            ax_r = section_ax(fig, [0.52, 0.06, 0.46, 0.86], sec_code + ' — direita')
            code_lines(ax_r, rc)
            footer_bar(fig, pg_num, total, f'SPEC-LAJES.md | {sec_code}')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    print(f'[OK] Lajes: {path}')


# ==========================================================================
# MAIN
# ==========================================================================

if __name__ == '__main__':
    print('CAD-ANALYZER — Fichas Instrutivas v2')
    print('Fonte da verdade: docs/specs/')
    print()

    pilares_pdf(OUT_DIR / 'fichas_pilares_instrutivas.pdf')
    vigas_pdf(OUT_DIR / 'fichas_vigas_instrutivas.pdf')
    lajes_pdf(OUT_DIR / 'fichas_lajes_instrutivas.pdf')

    print()
    print('Concluido:')
    for f in ['fichas_pilares_instrutivas.pdf',
              'fichas_vigas_instrutivas.pdf',
              'fichas_lajes_instrutivas.pdf']:
        p = OUT_DIR / f
        size = p.stat().st_size // 1024 if p.exists() else 0
        print(f'  {f}: {size} KB')
