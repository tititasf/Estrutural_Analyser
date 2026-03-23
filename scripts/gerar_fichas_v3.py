#!/usr/bin/env python3
"""
Fichas Instrutivas v3 — CAD-ANALYZER
Fundo branco, layout profissional, conteudo completo.
Executa: python scripts/gerar_fichas_v3.py
"""
import sys, math, textwrap
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── PALETA FUNDO BRANCO ────────────────────────────────────────────────────
W      = '#ffffff'
PAGE   = '#f9fafb'
NAVY   = '#0a1628'
TEXT   = '#1c1c2e'
TEXT2  = '#555577'
BORDER = '#d0d4e0'
C_BG   = '#f3f4f6'   # code block bg
C_KW   = '#b31d28'   # keywords
C_STR  = '#032f62'   # strings
C_CMT  = '#6e7681'   # comments
C_NUM  = '#005cc5'   # numbers
C_DEF  = '#6f42c1'   # def/class

# Cor por elemento
EC = {'PILAR': '#d45000', 'VIGA': '#0066bb', 'LAJE': '#007744'}
EB = {'PILAR': '#fff4ee', 'VIGA': '#eef4ff', 'LAJE': '#eefff5'}

WARN_BG  = '#fffde7'; WARN_BD = '#f9a825'; WARN_FG = '#5d4037'
OK_BG    = '#f0fff4'; OK_BD   = '#2e7d32'; OK_FG   = '#1b5e20'
ERR_BG   = '#ffeaea'; ERR_BD  = '#c62828'; ERR_FG  = '#b71c1c'
INFO_BG  = '#e8f4fd'; INFO_BD = '#1565c0'; INFO_FG = '#0d47a1'

VERSION = 'v3.0 | 2026-03-19 | CAD-ANALYZER'
OUT_DIR = Path('D:/Agente-cad-PYSIDE/docs/fichas')
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'figure.facecolor': W, 'axes.facecolor': W,
    'text.color': TEXT, 'font.family': 'DejaVu Sans',
    'figure.max_open_warning': 300,
})

# ── FIGURA A3 ──────────────────────────────────────────────────────────────
def new_fig():
    fig = plt.figure(figsize=(16.54, 11.69))
    fig.patch.set_facecolor(W)
    return fig

def ax_at(fig, rect, bg=W):
    ax = fig.add_axes(rect)
    ax.set_facecolor(bg)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.axis('off')
    return ax

# ── HEADER / FOOTER ────────────────────────────────────────────────────────
def header(fig, elem, code, title, pg, total):
    ec = EC[elem]
    # Faixa colorida no topo
    bar = FancyBboxPatch((0,0), 1, 1, boxstyle='square',
        facecolor=NAVY, edgecolor='none', transform=fig.transFigure, zorder=5)
    fig.add_artist(bar)
    # Faixa menor com cor do elemento
    bar2 = FancyBboxPatch((0, 0.955), 1, 0.045, boxstyle='square',
        facecolor=ec, edgecolor='none', transform=fig.transFigure, zorder=6)
    fig.add_artist(bar2)
    fig.text(0.013, 0.978, elem, ha='left', va='center',
        fontsize=11, color=W, fontweight='bold', transform=fig.transFigure, zorder=7)
    fig.text(0.09,  0.978, f'[{code}]', ha='left', va='center',
        fontsize=9, color='#aaccee', transform=fig.transFigure, zorder=7)
    fig.text(0.175, 0.978, title, ha='left', va='center',
        fontsize=10, color=W, fontweight='bold', transform=fig.transFigure, zorder=7)
    fig.text(0.99,  0.978, f'{pg}/{total}  |  {VERSION}', ha='right', va='center',
        fontsize=6.5, color='#9aaabb', transform=fig.transFigure, zorder=7)
    # Linha separadora
    fig.add_artist(plt.Line2D([0,1],[0.955,0.955],
        transform=fig.transFigure, color=BORDER, lw=0.5, zorder=8))

def footer(fig, src):
    fig.add_artist(plt.Line2D([0.02,0.98],[0.035,0.035],
        transform=fig.transFigure, color=BORDER, lw=0.5))
    fig.text(0.5, 0.018, f'Fonte: {src}', ha='center', va='center',
        fontsize=6, color=TEXT2, transform=fig.transFigure)

# ── SECAO COM TITULO ───────────────────────────────────────────────────────
def section(fig, rect, title='', elem='PILAR', bg=W, border=True):
    ax = ax_at(fig, rect, bg=bg)
    if border:
        ax.add_patch(FancyBboxPatch((0,0),100,100, boxstyle='round,pad=0',
            facecolor='none', edgecolor=BORDER, lw=0.8))
    if title:
        ec = EC[elem]
        ax.add_patch(FancyBboxPatch((0,94),100,7, boxstyle='round,pad=0',
            facecolor=EB[elem], edgecolor='none'))
        ax.axhline(y=94, color=ec, lw=1.5)
        ax.text(2, 97, title, ha='left', va='center',
            fontsize=7.5, color=ec, fontweight='bold')
    return ax

# ── BLOCO DE CODIGO ────────────────────────────────────────────────────────
def code_block(ax, lines, x=2, y=90, fs=5.9, leading=6.4,
               title='', elem='PILAR', highlight_rows=None):
    if highlight_rows is None: highlight_rows = []
    if title:
        ax.text(x, y+2, title, ha='left', va='bottom',
            fontsize=6, color=TEXT2, style='italic')
    # Caixa de fundo
    n = len(lines)
    h_box = n * leading + 6
    ax.add_patch(FancyBboxPatch((x-1, y - h_box + 3), 98, h_box,
        boxstyle='round,pad=0.5', facecolor=C_BG, edgecolor=BORDER, lw=0.5))
    # Barra lateral colorida
    ax.add_patch(FancyBboxPatch((x-1, y - h_box + 3), 1.5, h_box,
        boxstyle='round,pad=0', facecolor=EC[elem], edgecolor='none', alpha=0.7))

    for i, ln in enumerate(lines):
        yp = y - i * leading
        if i in highlight_rows:
            ax.add_patch(mpatches.Rectangle((x, yp - leading*0.8),
                96, leading, facecolor='#fffde7', edgecolor='none', alpha=0.7))
        color = _code_color(ln)
        ax.text(x+1.5, yp, ln, ha='left', va='top',
            fontsize=fs, color=color, fontfamily='monospace')

def _code_color(line):
    s = line.strip()
    if s.startswith('#'): return C_CMT
    if any(s.startswith(k) for k in ('def ','class ','import ','from ','return ','yield ')):
        return C_KW
    if s.startswith('"') or s.startswith("'"): return C_STR
    if s.startswith('RE_') or '= re.compile' in s: return C_DEF
    return TEXT

# ── TABELA ─────────────────────────────────────────────────────────────────
def table(ax, rows, headers, x=2, y=92, col_widths=None, fs=6.0, title='', elem='PILAR'):
    if col_widths is None:
        col_widths = [96//len(headers)] * len(headers)
    if title:
        ax.text(x, y+4, title, ha='left', va='bottom',
            fontsize=7, color=EC[elem], fontweight='bold')
    ec = EC[elem]
    # Header row
    cx = x
    for w, h_txt in zip(col_widths, headers):
        ax.add_patch(mpatches.Rectangle((cx, y-6), w, 6,
            facecolor=EB[elem], edgecolor=BORDER, lw=0.4))
        ax.text(cx+1, y-3, h_txt, ha='left', va='center',
            fontsize=fs, color=ec, fontweight='bold')
        cx += w
    # Data rows
    for ri, row in enumerate(rows):
        ry = y - 6 - (ri+1)*6.5
        cx = x
        bg = W if ri % 2 == 0 else '#f8f9fc'
        for ci, (w, cell) in enumerate(zip(col_widths, row)):
            ax.add_patch(mpatches.Rectangle((cx, ry), w, 6.5,
                facecolor=bg, edgecolor=BORDER, lw=0.3))
            # colorir ultima coluna (confianca)
            cell_str = str(cell)
            tc = TEXT
            if cell_str == 'HIGH':   tc = OK_FG
            elif cell_str == 'MEDIUM': tc = '#b45309'
            elif cell_str == 'LOW':    tc = '#991b1b'
            elif cell_str == 'N/A':    tc = TEXT2
            ax.text(cx+1, ry+3.2, cell_str, ha='left', va='center',
                fontsize=fs-0.3, color=tc)
            cx += w

# ── NOTA ───────────────────────────────────────────────────────────────────
def note(ax, x, y, w, h, text, kind='warn'):
    cfg = {'warn':(WARN_BG,WARN_BD,WARN_FG,'ATENCAO'),
           'ok':  (OK_BG,  OK_BD,  OK_FG,  'OK'),
           'err': (ERR_BG, ERR_BD, ERR_FG, 'ERRO'),
           'info':(INFO_BG,INFO_BD,INFO_FG,'INFO')}
    bg,bd,fg,lbl = cfg.get(kind, cfg['warn'])
    ax.add_patch(FancyBboxPatch((x,y),w,h, boxstyle='round,pad=1',
        facecolor=bg, edgecolor=bd, lw=1.0))
    ax.text(x+2, y+h-3, lbl, ha='left', va='center',
        fontsize=6.5, color=fg, fontweight='bold')
    wrapped = textwrap.wrap(text, width=int(w*1.3))
    for i,ln in enumerate(wrapped[:5]):
        ax.text(x+2, y+h-8-i*5.5, ln, ha='left', va='center',
            fontsize=6.0, color=fg)

# ── DIAGRAMA 3 RAIOS ───────────────────────────────────────────────────────
def diagram_3raios(ax, cx=50, cy=48, elem='PILAR'):
    ec = EC[elem]
    # Pilar
    ax.add_patch(mpatches.Rectangle((cx-6,cy-9),12,18,
        facecolor=EB[elem], edgecolor=ec, lw=2.0, zorder=5))
    ax.text(cx, cy, 'P17', ha='center', va='center',
        fontsize=8, color=ec, fontweight='bold', zorder=6)

    theta = np.linspace(0, 2*math.pi, 200)
    # Raio 2 (5mm — escala visual)
    r2 = 12
    ax.plot(cx+r2*np.cos(theta), cy+r2*np.sin(theta),
        color='#2e7d32', lw=1.0, ls='--', alpha=0.8)
    ax.text(cx+r2+1, cy-2, '5mm\nscore=0.8', fontsize=5.5,
        color='#2e7d32', va='center')

    # Raio 3 (800mm)
    r3 = 34
    ax.plot(cx+r3*np.cos(theta), cy+r3*np.sin(theta),
        color='#1565c0', lw=0.8, ls=':', alpha=0.7)
    ax.text(cx+r3+1, cy+2, '800mm\ndecay', fontsize=5.5,
        color='#1565c0', va='center')

    # Ponto dentro
    ax.plot(cx+2, cy+3, 'o', color='#2e7d32', ms=7, zorder=7)
    ax.annotate('score=1.0\n(dentro)', xy=(cx+2,cy+3),
        xytext=(cx+15,cy+20), fontsize=5.5, color='#2e7d32',
        arrowprops=dict(arrowstyle='->', color='#2e7d32', lw=0.8))

    # Ponto adjacente
    ax.plot(cx+10, cy+8, 's', color='#388e3c', ms=6, zorder=7)
    ax.annotate('score=0.8\n(<=5mm)', xy=(cx+10,cy+8),
        xytext=(cx+20, cy+30), fontsize=5.5, color='#388e3c',
        arrowprops=dict(arrowstyle='->', color='#388e3c', lw=0.8))

    # Ponto distante
    ax.plot(cx+25, cy-18, '^', color='#1565c0', ms=6, zorder=7)
    ax.annotate('score=0..0.5\n(decay linear)', xy=(cx+25,cy-18),
        xytext=(cx+30, cy-35), fontsize=5.5, color='#1565c0',
        arrowprops=dict(arrowstyle='->', color='#1565c0', lw=0.8))

    ax.text(cx-33, cy+40, 'Logica 3 Raios — TextAssociator',
        fontsize=8, color=NAVY, fontweight='bold')
    ax.set_xlim(5,95); ax.set_ylim(5,95)

# ── BARRA CONFIDENCE ───────────────────────────────────────────────────────
def confidence_bar_w(ax, x=3, y=10, w=94, h=10):
    segs = [
        (0.0,  0.30, ERR_BG,  ERR_BD,  ERR_FG,  'REJEITAR\n< 0.30'),
        (0.30, 0.50, WARN_BG, WARN_BD, WARN_FG, 'REVISAO\n0.30-0.50'),
        (0.50, 0.80, INFO_BG, INFO_BD, INFO_FG, 'AVISO\n0.50-0.80'),
        (0.80, 1.00, OK_BG,   OK_BD,   OK_FG,   'AUTO-ASSIGN\n>= 0.80'),
    ]
    for lo,hi,bg,bd,fg,lbl in segs:
        sx = x + lo*w; sw = (hi-lo)*w
        ax.add_patch(mpatches.Rectangle((sx,y),sw,h,
            facecolor=bg, edgecolor=bd, lw=0.8))
        for j,ln in enumerate(lbl.split('\n')):
            ax.text(sx+sw/2, y+h/2+(0.5-j)*3.5, ln,
                ha='center', va='center', fontsize=5.5,
                color=fg, fontweight='bold')
    for v in [0.30, 0.50, 0.80]:
        vx = x+v*w
        ax.plot([vx,vx],[y-1,y+h+1], color=BORDER, lw=0.8, ls='--')
        ax.text(vx, y-3, str(v), ha='center', va='top',
            fontsize=5.5, color=TEXT2)

# ══════════════════════════════════════════════════════════════════════════
# PILARES PDF  (12 paginas)
# ══════════════════════════════════════════════════════════════════════════
def pilares_pdf(path):
    E = 'PILAR'; total = 12
    with PdfPages(str(path)) as pdf:

        # P-1: Overview + RE_PILAR
        fig = new_fig()
        header(fig, E, 'P-1', 'Identificacao — RE_PILAR + TEXT/MTEXT', 1, total)
        footer(fig, 'SPEC-PILARES.md §1.1-1.2 | agente_estrutural.py')

        al = section(fig,[0.02,0.05,0.46,0.88],'Logica 3 Raios de Associacao', E)
        diagram_3raios(al, elem=E)
        confidence_bar_w(al, x=3, y=5, w=94, h=10)

        ar = section(fig,[0.52,0.05,0.46,0.88],'RE_PILAR — regex de deteccao', E)
        code_block(ar,[
            'import re',
            '',
            'RE_PILAR = re.compile(',
            "    r'^(PC?\\.?-?\\d+([A-Z]|\\.\\d+|-\\d+)?|P-\\d+[A-Z]?)$',",
            '    re.IGNORECASE',
            ')',
            '',
            '# CASAM:   P1  P17  PC1  P-1  P1A  P-1A  P.1',
            '# NAO:     PL1  PD1  P (sem num)  PONTALETE',
            '',
            'for e in msp:',
            "    if e.dxftype() == 'TEXT':",
            "        text  = getattr(e.dxf, 'text', '').strip()",
            '        x, y  = e.dxf.insert.x, e.dxf.insert.y',
            '        layer = e.dxf.layer',
            "    elif e.dxftype() == 'MTEXT':",
            '        text  = e.plain_text()  # ou plain_mtext()',
            '        x, y  = e.dxf.insert.x, e.dxf.insert.y',
            '        layer = e.dxf.layer',
            '    else:',
            '        continue',
            '',
            '    if text and RE_PILAR.match(text):',
            '        pilares_txt.append({',
            "            'text': text, 'x': x,",
            "            'y': y, 'layer': layer",
            '        })',
        ], x=3, y=88, elem=E, highlight_rows=[2,3,4,5])
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-2: Associacao 3 Raios codigo
        fig = new_fig()
        header(fig, E, 'P-2', 'Associacao Texto-Poligono — 3 Raios', 2, total)
        footer(fig, 'SPEC-PILARES.md §1.3 | text_associator.py')

        al = section(fig,[0.02,0.05,0.46,0.88],'associar_pilar() — codigo completo', E)
        code_block(al,[
            'from shapely.geometry import Polygon, Point',
            '',
            'PILAR_SEARCH_RADIUS = 800.0  # mm',
            '',
            'def associar_pilar(pilar_txt, polylines):',
            "    px, py = pilar_txt['x'], pilar_txt['y']",
            '    melhor, melhor_score = None, 0.0',
            '',
            '    for poly in polylines:',
            "        if not poly['closed']: continue",
            "        if len(poly['points']) < 3: continue",
            '',
            "        polygon = Polygon(poly['points'])",
            '        ponto   = Point(px, py)',
            '        dist    = polygon.distance(ponto)',
            '',
            '        if polygon.contains(ponto):',
            '            score = 1.0                  # Raio 1',
            '        elif dist <= 5.0:',
            '            score = 0.8                  # Raio 2',
            '        elif dist <= PILAR_SEARCH_RADIUS:',
            '            score = 0.5*(1.0-dist/PILAR_SEARCH_RADIUS)  # Raio 3',
            '        else:',
            '            continue',
            '',
            '        if score > melhor_score:',
            '            melhor_score = score',
            '            melhor = poly',
            '',
            '    return melhor, melhor_score',
        ], x=3, y=88, elem=E, highlight_rows=[16,17,18,19,20,21])

        ar = section(fig,[0.52,0.05,0.46,0.88],'Scores e decisao de aceite', E)
        code_block(ar,[
            '# SCORES por situacao:',
            '#',
            '# texto DENTRO da polilinha:',
            '#   polygon.contains(Point) → score = 1.0',
            '#',
            '# texto TOCANDO (<= 5mm):',
            '#   dist <= 5.0           → score = 0.8',
            '#',
            '# texto PROXIMO (<=800mm):',
            '#   score = 0.5*(1 - dist/800)',
            '#   ex: dist=400mm → score=0.25',
            '#   ex: dist=100mm → score=0.4375',
            '#',
            '# texto FORA (>800mm):',
            '#   ignorar — nao associar',
            '',
            '# ACEITE:',
            '# score >= 0.80 → AUTO-ASSIGN',
            '# score  < 0.80 → revisao humana',
            '',
            '# EMPATE: 2 textos com score igual',
            '# → fila revisao, log "EMPATE"',
            '',
            '# LWPOLYLINE obrigatoria:',
            '# is_closed = True',
            '# len(vertices) >= 3',
            '# apenas FECHADAS sao pilares',
            '',
            '# LAYER da polilinha:',
            '# "Paineis" / "Pain?is" / "PAINEL"',
            '# Mas layer desconhecido: processar',
            '# mesmo assim (conf -= 0.15)',
        ], x=3, y=88, elem=E)
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-3: Extracao Dimensoes
        fig = new_fig()
        header(fig, E, 'P-3', 'Extracao de Dimensoes — comprimento e largura', 3, total)
        footer(fig, 'SPEC-PILARES.md §2.2 | agente_estrutural.py')

        al = section(fig,[0.02,0.05,0.46,0.88],'RE_DIM + extrair_dimensoes()', E)
        code_block(al,[
            "RE_DIM = re.compile(r'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})')",
            'RE_DIM_BH = re.compile(',
            "    r'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})',",
            '    re.IGNORECASE | re.DOTALL',
            ')',
            '',
            'DIM_SEARCH_RADIUS = 600.0  # mm',
            '',
            'def extrair_dimensoes(pilar_center, texts):',
            '    """',
            '    Retorna (comprimento, largura) em cm.',
            '    comprimento = lado MAIOR',
            '    largura     = lado MENOR',
            '    """',
            '    cx, cy = pilar_center',
            '    for t in texts:',
            "        if abs(t['x']-cx) > DIM_SEARCH_RADIUS: continue",
            "        if abs(t['y']-cy) > DIM_SEARCH_RADIUS: continue",
            '',
            "        m = RE_DIM.search(t['text'])",
            '        if m:',
            '            d1, d2 = float(m.group(1)), float(m.group(2))',
            '            return max(d1,d2), min(d1,d2)',
            '',
            "        m = RE_DIM_BH.search(t['text'])",
            '        if m:',
            '            d1, d2 = float(m.group(1)), float(m.group(2))',
            '            return max(d1,d2), min(d1,d2)',
            '',
            '    return 0.0, 0.0  # nao encontrado',
        ], x=3, y=88, elem=E, highlight_rows=[0,1,2,3,4])

        ar = section(fig,[0.52,0.05,0.46,0.88],'Formatos aceitos + Diferenca PILAR vs VIGA', E)
        code_block(ar,[
            '# FORMATOS ACEITOS:',
            '#',
            '# "20x50"  → d1=20  d2=50',
            '# "20X50"  → idem (case insensitive)',
            '# "20*50"  → idem',
            '# "20/50"  → idem',
            '# "b=20 h=50" → b=20 h=50',
            '# "b=20\\nh=50" → idem (MTEXT multiline)',
            '',
            '# REGRA PILAR:',
            '# comprimento = max(d1, d2)   # MAIOR',
            '# largura     = min(d1, d2)   # MENOR',
            '',
            '# DIFERENCA PILAR vs VIGA:',
            '# Pilar: c=max, l=min (lado maior = comprimento)',
            '# Viga:  b=min, h=max (b < h por norma)',
            '',
            '# SE NAO ENCONTRAR:',
            '# comprimento = 0.0',
            '# largura     = 0.0',
            '# confidence -= 0.30',
            '# log: "P17: dim nao encontrada (R=600mm)"',
            '',
            '# VALIDACAO pos-extracao:',
            '# comprimento: 10 - 200 cm',
            '# largura:     10 - 150 cm',
            '# SE comprimento < largura: TROCAR',
            '',
            '# Layer com dimensao (mais comum):',
            '# "Texto Secao", "cotas", "COTA",',
            '# NOMENCLATURA (MTEXT com dim embutida)',
        ], x=3, y=88, elem=E)
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-4: Schema JSON parte 1
        fig = new_fig()
        header(fig, E, 'P-4', 'Schema JSON — FichaFase3Pilar (campos completos)', 4, total)
        footer(fig, 'ficha_pilares_schema.py | SPEC-PILARES.md §2.1')

        al = section(fig,[0.02,0.05,0.46,0.88],'Identificacao + Geometria', E)
        code_block(al,[
            '# FichaFase3Pilar — parte 1/2',
            '{',
            '    "id":                "P17",',
            '    "numero":            "17",      # digits(id)',
            '    "pavimento":         "TERREO",  # nome DXF',
            '    "pavimento_numero":  0,         # 0=terreo',
            '    "obra":              "ALIMONTI-PARAISO",',
            '',
            '    # Secao transversal (cm)',
            '    "comprimento":       40.0,      # lado MAIOR',
            '    "largura":           20.0,      # lado MENOR',
            '',
            '    # Altura e cota',
            '    "altura_cm":         280.0,     # chegada-saida',
            '    "nivel_saida_m":     0.0,       # cota piso',
            '    "nivel_chegada_m":   2.80,      # cota teto',
            '    "pavimento_anterior": "",        # nome andar abaixo',
            '}',
            '',
            '# extrair_numero("P17")  → "17"',
            '# extrair_numero("PC3")  → "3"',
            '# extrair_numero("P-1A") → "1"',
            "# ''.join(filter(str.isdigit, pilar_id))",
        ], x=3, y=88, elem=E, highlight_rows=[2,3,4,9,10,13,14,15])

        ar = section(fig,[0.52,0.05,0.46,0.88],'Armadura + Metadados', E)
        code_block(ar,[
            '# FichaFase3Pilar — parte 2/2',
            '{',
            '    # Armadura longitudinal (barras/trecho)',
            '    "par_1_2": "8",   # piso1→piso2',
            '    "par_2_3": "0",   # piso2→piso3',
            '    "par_3_4": "0",',
            '    "par_4_5": "0",',
            '    "par_5_6": "0",',
            '    "par_6_7": "0",',
            '    "par_7_8": "0",',
            '    "par_8_9": "0",   # ate 9 pavimentos',
            '',
            '    # Armadura transversal (estribos)',
            '    "grade_1":     "8",    # diametro mm',
            '    "distancia_1": "10",   # espacamento cm',
            '    "grade_2":     "",',
            '    "distancia_2": "",',
            '    "grade_3":     "",',
            '',
            '    # Tipo estrutural',
            '    "pilar_especial":      False,',
            '    "tipo_pilar_especial": "L",  # L/T/CAMBOTADO',
            '',
            '    # Metadados',
            '    "confidence":          0.92,',
            '    "revisado_por_humano": False',
            '}',
        ], x=3, y=88, elem=E, highlight_rows=[3,13,14,20,21,24])
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-5: Layers completos
        fig = new_fig()
        header(fig, E, 'P-5', 'Layers — Mapeamento por Firma (BIM / TQS / METHODUS)', 5, total)
        footer(fig, 'CONFIG-LAYERS.yaml | dxf_reverso_analise.json')

        al = section(fig,[0.02,0.05,0.46,0.88],'Layers principais — Pilares', E)
        table(al,[
            ('NOMENCLATURA',      'ELEMENT_LABEL',   'IDs P1,P17',    'HIGH'),
            ('texto',             'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('TEXTO_GERAL',       'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('00 - FELIPE',       'ELEMENT_LABEL',   'IDs pilares',   'HIGH'),
            ('EST-PILAR-TEXT',    'ELEMENT_LABEL',   'IDs (LJ)',      'HIGH'),
            ('Paineis/Pain?is',   'PANEL_GEOMETRY',  'Contorno',      'HIGH'),
            ('PAINEL',            'PANEL_GEOMETRY',  'Contorno',      'HIGH'),
            ('Texto Secao',       'SECTION_TEXT',    'Dim 20x50',     'HIGH'),
            ('NIVEL/N?vel',       'ELEVATION_MARK',  'Cota Z',        'HIGH'),
            ('SARR_2.2x7',        'BATTEN_2x7',      'Sarrafo 2x7',   'HIGH'),
            ('SARR_7x7',          'BATTEN_7x7',      'Canto pilar',   'HIGH'),
            ('CHAPA',             'PLATE_GEOMETRY',  'Compensado',    'HIGH'),
            ('BARRA ANCORAGEM',   'ANCHOR_BAR_PL',   'Anc. pilar',    'HIGH'),
            ('PONTALETE',         'PROP_LAYER',       'Pontalete',     'MEDIUM'),
            ('GRAVATA',           'CLAMP_LAYER',     'Gravata metal', 'MEDIUM'),
            ('S-COLS / 1 / 2',   'TQS_COLUMN',      'TQS pilar',     'MEDIUM'),
            ('F-PILARES-S',      'PILLAR_FACE',     'Face Sul',      'LOW'),
        ],['Layer DXF','Canonical','Uso','Conf'],
           x=2, y=90, col_widths=[30,25,22,19], elem=E)

        ar = section(fig,[0.52,0.05,0.46,0.88],'Deteccao de Familia + normalize_layer()', E)
        code_block(ar,[
            'import unicodedata',
            '',
            'def normalize_layer(name: str) -> str:',
            '    nfkd  = unicodedata.normalize("NFKD", str(name))',
            '    ascii = nfkd.encode("ascii","ignore").decode()',
            '    return ascii.upper().strip()',
            '',
            '# normalize("Paineis") == "PAINEIS"',
            '# normalize("Pain?is") == "PAINEIS"  ← CP1252',
            '',
            'def detectar_familia(layers: list) -> str:',
            "    if any(l.startswith('MTH-') for l in layers):",
            "        return 'METHODUS'",
            '    tx = sum(1 for l in layers if l.startswith("TX"))',
            '    if tx / len(layers) > 0.15:',
            "        return 'EBERICK'",
            '    num = sum(1 for l in layers if l.isdigit())',
            '    if num / len(layers) > 0.30:',
            "        return 'TQS'",
            "    return 'BIM'  # default",
            '',
            '# ALIMONTI = BIM (layers descritivos)',
            '# GWT      = BIM',
            '# LEAF     = BIM',
            '',
            '# BARRA ANCORAGEM (PL) != BARRA DE ANCORAGEM (LV)',
            '# Mesmo significado, nomes DIFERENTES por tipo!',
        ], x=3, y=88, elem=E, highlight_rows=[2,3,4,5])
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-6: Pilar especial + validacao
        fig = new_fig()
        header(fig, E, 'P-6', 'Pilar Especial + Validacao Completa', 6, total)
        footer(fig, 'SPEC-PILARES.md §2.5 + §3')

        al = section(fig,[0.02,0.05,0.46,0.88],'detectar_cambotado() + tipos', E)
        code_block(al,[
            'def detectar_cambotado(polyline_entity):',
            '    """',
            '    Retorna (pilar_especial: bool, tipo: str).',
            '    Bulge = curvatura de segmento LWPOLYLINE.',
            '    """',
            '    bulges = []',
            '    try:',
            "        bulges = [float(p[4]) if len(p)>4 else 0.0",
            "                  for p in polyline_entity.get_points('xyzsb')]",
            '    except Exception:',
            "        return False, 'L'",
            '',
            '    max_b = max((abs(b) for b in bulges), default=0.0)',
            '',
            '    if max_b > 0.3:',
            "        return True, 'CAMBOTADO'",
            '    elif max_b > 0.01:',
            "        return True, 'L'",
            "    return False, 'L'",
            '',
            '# Tipos:',
            '# bulge = 0.0:        pilar retangular normal',
            '# bulge 0.01-0.30:    pilar L ou T',
            '# bulge > 0.30:       pilar CAMBOTADO (curvo)',
        ], x=3, y=88, elem=E, highlight_rows=[14,15,16,17])

        ar = section(fig,[0.52,0.05,0.46,0.88],'Validacao de campos', E)
        table(ar,[
            ('comprimento', '10 - 200 cm',  'conf -= 0.3'),
            ('largura',     '10 - 150 cm',  'conf -= 0.3'),
            ('altura_cm',   '100 - 600 cm', 'conf -= 0.2'),
            ('nivel_saida', '-5.0 - 50.0 m','aceitar, avisar'),
            ('c >= l',      'obrigatorio',  'trocar se c < l'),
            ('confidence',  '0.0 - 1.0',    'clamp'),
        ],['Campo','Range valido','Se invalido'],
           x=2, y=75, col_widths=[28,30,38], elem=E)

        note(ar, 3, 10, 92, 20,
            'Se comprimento <= 0: INVALIDO, revisao humana obrigatoria. '
            'Coordenadas UTM (x ou y > 50000): ignorar (georeferenciado, nao formas). '
            'comprimento * largura > 2500 cm2: suspeito, log aviso.',
            kind='warn')
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-7: Nivel e Armadura
        fig = new_fig()
        header(fig, E, 'P-7', 'Nivel + Armadura — extrair_nivel() + par_1_2', 7, total)
        footer(fig, 'SPEC-PILARES.md §2.3 + §2.4')

        al = section(fig,[0.02,0.05,0.46,0.88],'extrair_nivel() — layer NIVEL', E)
        code_block(al,[
            'RE_NIVEL = re.compile(',
            "    r'[Nn][i\\xed]vel\\s*[=:]?\\s*([+-]?\\d+[.,]\\d+)',",
            '    re.IGNORECASE',
            ')',
            '# Exemplos: "Nivel +2,80" → 2.80',
            '#           "h = 2.80" em layer NIVEL → 2.80',
            '',
            "def extrair_nivel(texts, layer='NIVEL'):",
            '    for t in texts:',
            "        if normalize_layer(t['layer']) == layer.upper():",
            "            m = RE_NIVEL.search(t['text'])",
            '            if m:',
            "                return float(m.group(1).replace(',','.'))",
            '    return None',
            '',
            '# altura_cm = (nivel_chegada - nivel_saida) * 100',
            '',
            '# Layers aceitos para nivel:',
            '# NIVEL, "Nivel", "N?vel",',
            '# "NIVEL 1 PAV.", "NIVEL 2 PAV.",',
            '# "Texto Nivel"',
            '',
            '# Se nivel nao encontrado:',
            '# nivel_saida_m = pavimento_numero * 3.0',
            '# confidence -= 0.10',
        ], x=3, y=88, elem=E)

        ar = section(fig,[0.52,0.05,0.46,0.88],'Armadura — par_1_2 e grade_1', E)
        code_block(ar,[
            '# Textos tipicos de armadura no DXF:',
            '# "8 fi 16"        → 8 barras diam 16mm',
            '# "Est fi 8 c/ 10" → estribo d=8 esp=10cm',
            '',
            'RE_BARRA   = re.compile(',
            "    r'(\\d+)\\s*[fF\\xf8\\u03c6]\\s*(\\d+)')",
            'RE_ESTRIBO = re.compile(',
            "    r'[Ee]st.*?(\\d+).*?c[/]?\\s*(\\d+)')",
            '',
            '# par_1_2 = barras entre piso 1 e 2',
            '# par_2_3 = barras entre piso 2 e 3',
            '# (0 = sem info ou sem alteracao)',
            '',
            '# grade_1    = diametro estribo (mm)',
            '# distancia_1 = espacamento (cm)',
            '',
            '# MTEXT pode ter tudo na mesma entidade:',
            '# "P17\\n20x50\\n8 fi 16\\nEst fi 8 c/10"',
            '# → id=P17  c=50 l=20',
            '# → par_1_2="8"',
            '# → grade_1="8" distancia_1="10"',
            '',
            '# Se nao encontrar armadura:',
            '# par_1_2="0"  grade_1=""',
            '# NAO penaliza confidence (campo opcional)',
        ], x=3, y=88, elem=E)
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-8: Decision Matrix
        fig = new_fig()
        header(fig, E, 'P-8', 'Matriz de Decisao — Casos Ambiguos + Fallback Chain', 8, total)
        footer(fig, 'DECISION-MATRIX.md §3 + §4')

        al = section(fig,[0.02,0.05,0.46,0.88],'Fallback Chain — Pilares', E)
        steps = [
            ('1','RE_PILAR em NOMENCLATURA → LWPOLYLINE em Paineis','conf = raio_score', OK_BG, OK_BD),
            ('2','RE_PILAR em TEXTO_GERAL  → LWPOLYLINE em Paineis','conf -= 0.05',      INFO_BG, INFO_BD),
            ('3','RE_PILAR em qualquer layer → LWPOLYLINE qualquer', 'conf -= 0.15',     WARN_BG, WARN_BD),
            ('4','RE_PILAR sem LWPOLYLINE proxima',                  'conf -= 0.40',     ERR_BG, ERR_BD),
            ('5','Sem texto RE_PILAR detectado',                     'NAO REGISTRAR',    '#f3f4f6','#aaa'),
        ]
        for i,(n,cond,acao,bg,bd) in enumerate(steps):
            y0 = 88 - i*17
            al.add_patch(FancyBboxPatch((2,y0-12),96,13,
                boxstyle='round,pad=0.5', facecolor=bg, edgecolor=bd, lw=0.8))
            al.text(5, y0-5, f'[{n}]', fontsize=9, color=bd,
                fontweight='bold', va='center')
            al.text(13, y0-4, cond, fontsize=6.2, color=TEXT, va='center')
            al.text(13, y0-9, f'→ {acao}', fontsize=6.0, color=TEXT2, va='center')

        ar = section(fig,[0.52,0.05,0.46,0.88],'Regras Fixas e Casos Especiais', E)
        table(ar,[
            ('comprimento <= 0',       'INVALIDO → revisao humana'),
            ('comprimento < largura',  'Trocar valores (c=maior)'),
            ('2 textos competindo',    'Vence score maior'),
            ('Empate de score',        'Revisao + log "EMPATE"'),
            ('Layer LWPOLY desconhec.','Processar (conf -= 0.15)'),
            ('Encoding "Pain?is"',     'normalize_layer()'),
            ('Coordenadas UTM >50000', 'Ignorar arquivo'),
            ('bulge > 0.3',            'tipo_pilar_especial=CAMBOTADO'),
            ('area > 2500 cm2',        'Suspeito, log aviso'),
        ],['Situacao','Acao'],
           x=2, y=90, col_widths=[48,48], elem=E)
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-9: Exemplo real ALIMONTI P17
        fig = new_fig()
        header(fig, E, 'P-9', 'Exemplo Real — ALIMONTI P17 (score=1.0)', 9, total)
        footer(fig, 'ALIMONTI - PARAISO - TIPO - PL - R00.dxf')

        al = section(fig,[0.02,0.05,0.46,0.88],'DXF Input (arquivo real)', E)
        code_block(al,[
            '# Arquivo: ALIMONTI - PARAISO - TIPO - PL - R00.dxf',
            '# Familia: BIM | Firma: ALIMONTI',
            '',
            'TEXT  layer="NOMENCLATURA"',
            '      text="P17"',
            '      insert=(17799.0, 3038.0)',
            '',
            'TEXT  layer="cotas"',
            '      text="20x50"',
            '      insert=(17830.0, 3000.0)',
            '',
            'LWPOLYLINE  layer="Paineis"',
            '            flags=1  # closed=True',
            '            vertices=[',
            '              (17770.0, 3010.0),',
            '              (17820.0, 3010.0),',
            '              (17820.0, 3066.0),',
            '              (17770.0, 3066.0)',
            '            ]',
            '',
            '# Centro da polilinha:',
            '# cx = (17770+17820)/2 = 17795',
            '# cy = (3010+3066)/2   = 3038',
            '# Texto P17 insert=(17799,3038)',
            '# → ponto (17799,3038) DENTRO do bbox',
            '# → polygon.contains(Point) = True',
        ], x=3, y=88, elem=E)

        ar = section(fig,[0.52,0.05,0.46,0.88],'JSON Output + Calculo', E)
        code_block(ar,[
            '# Resultado extraido:',
            '{',
            '  "id":          "P17",',
            '  "numero":      "17",',
            '  "comprimento": 50.0,   # max(20,50)',
            '  "largura":     20.0,   # min(20,50)',
            '  "confidence":  1.0,    # Raio 1',
            '  "revisado":    False',
            '}',
            '',
            '# Por que score=1.0:',
            '# polygon.contains(Point(17799,3038)) = True',
            '# → Raio 1: score = 1.0',
            '# → AUTO-ASSIGN (>= 0.80)',
            '',
            '# Extracao de dimensao:',
            '# RE_DIM.search("20x50")',
            '# → d1=20, d2=50',
            '# → comprimento=max(50,20)=50',
            '# → largura=min(50,20)=20',
            '',
            '# Todos os 17799 TEXT no arquivo PL:',
            '# 7538 total TEXT entities',
            '# ~280 casam RE_PILAR',
            '# ~265 associados com score >= 0.80',
        ], x=3, y=88, elem=E, highlight_rows=[6])
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-10: Exemplo P5 adjacente + cambotado
        fig = new_fig()
        header(fig, E, 'P-10', 'Exemplos — P5 Adjacente + PC1 Cambotado', 10, total)
        footer(fig, 'SPEC-PILARES.md §4')

        al = section(fig,[0.02,0.05,0.46,0.88],'P5 — texto adjacente (Raio 3, score=0.394)', E)
        code_block(al,[
            'TEXT  layer="NOMENCLATURA"',
            '      text="P5"',
            '      insert=(16200.0, 2500.0)',
            '',
            'LWPOLYLINE  layer="Paineis"  closed=True',
            '            vertices=[',
            '              (16350,2400),(16400,2400),',
            '              (16400,2440),(16350,2440)',
            '            ]',
            '',
            '# Centro polilinha: (16375, 2420)',
            '# Texto P5:         (16200, 2500)',
            '',
            '# Distancia:',
            '# dist = hypot(16375-16200, 2420-2500)',
            '#      = hypot(175, -80)',
            '#      ≈ 193mm',
            '',
            '# 193 > 5mm     → nao e Raio 2',
            '# 193 <= 800mm  → e Raio 3',
            '# score = 0.5*(1 - 193/800)',
            '#       = 0.5 * 0.759',
            '#       = 0.379',
            '',
            '# 0.379 < 0.80 → FILA REVISAO HUMANA',
        ], x=3, y=88, elem=E, highlight_rows=[19,20,21,22,24])

        ar = section(fig,[0.52,0.05,0.46,0.88],'PC1 — Pilar Cambotado (bulge > 0.3)', E)
        code_block(ar,[
            'TEXT  layer="NOMENCLATURA"',
            '      text="PC1"',
            '      insert=(5000.0, 5000.0)',
            '',
            'LWPOLYLINE  layer="Paineis"  closed=True',
            '            vertices=[',
            '              (4950,4950),(5050,4950),',
            '              (5050,5050),(4950,5050)',
            '            ]',
            '            bulges=[0.0, 0.45, 0.0, 0.0]',
            '',
            '# Texto PC1 dentro da polilinha',
            '# → score = 1.0 (Raio 1)',
            '',
            '# Detectar cambotado:',
            '# max_bulge = max(abs(0.0),abs(0.45),...)',
            '#           = 0.45',
            '# 0.45 > 0.3 → CAMBOTADO',
            '',
            '# JSON output:',
            '{',
            '  "id":                  "PC1",',
            '  "pilar_especial":      true,',
            '  "tipo_pilar_especial": "CAMBOTADO",',
            '  "confidence":          0.95',
            '}',
        ], x=3, y=88, elem=E, highlight_rows=[9,16,17])
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-11: Confidence formula completa
        fig = new_fig()
        header(fig, E, 'P-11', 'Confidence — Formula Completa + Log Obrigatorio', 11, total)
        footer(fig, 'DECISION-MATRIX.md §1 + §2 + §6')

        al = section(fig,[0.02,0.05,0.46,0.88],'calcular_confidence_pilar()', E)
        code_block(al,[
            'def calcular_confidence_pilar(',
            '        raio_score: float,',
            '        tem_dimensao: bool,',
            '        tem_texto_id: bool,',
            '        tem_contorno: bool) -> float:',
            '    """Confidence com penalidades acumuladas."""',
            '    conf = raio_score',
            '    # raio_score: 1.0/0.8/0.0-0.5 (logica 3 raios)',
            '',
            '    if not tem_texto_id:',
            '        conf -= 0.40  # sem ID → severo',
            '    if not tem_dimensao:',
            '        conf -= 0.30  # sem 20x50',
            '    if not tem_contorno:',
            '        conf -= 0.40  # sem LWPOLYLINE',
            '',
            '    return max(0.0, min(conf, 1.0))',
            '',
            '# Thresholds:',
            '# CONF_AUTO   = 0.80  # auto-assign',
            '# CONF_WARN   = 0.50  # aceitar + log',
            '# CONF_REVIEW = 0.30  # revisao humana',
            '# CONF_REJECT = 0.30  # rejeitar',
            '',
            '# Exemplo P17 perfeito:',
            '# raio=1.0 + dim=True + id=True + cont=True',
            '# conf = 1.0  → AUTO-ASSIGN',
        ], x=3, y=88, elem=E, highlight_rows=[9,10,11,12,13,14])

        ar = section(fig,[0.52,0.05,0.46,0.88],'Log obrigatorio (confidence < 0.80)', E)
        code_block(ar,[
            '# Log OBRIGATORIO para conf < 0.80:',
            '',
            'log_entry = {',
            '    "elemento_id":         "P17",',
            '    "tipo":                "pilar",',
            '    "confidence":          0.65,',
            '    "motivo":   "dim nao encontrada",',
            '    "acao":     "revisao humana",',
            '    "raio_usado":          800,',
            '    "dist_texto_poligono": 145.3,',
            '    "layer_texto":    "NOMENCLATURA",',
            '    "layer_poligono": "Paineis"',
            '}',
            '',
            '# Integridade cruzada:',
            '# len(links)==0 → "pilar isolado?"',
            '# c*l > 2500cm2 → "secao grande, revisar"',
            '# comprimento <= 0 → INVALIDO',
            '',
            '# Classe por confidence:',
            '# >= 0.80: ALTO   → auto-assign',
            '# 0.50-0.79: MEDIO → aceitar + aviso',
            '# 0.30-0.49: BAIXO → revisao humana',
            '# < 0.30: MUITO BAIXO → rejeitar',
        ], x=3, y=88, elem=E)
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # P-12: Fluxo completo
        fig = new_fig()
        header(fig, E, 'P-12', 'Fluxo Completo + Checklist de Campos', 12, total)
        footer(fig, 'SPEC-PILARES.md | agente_estrutural.py')

        al = section(fig,[0.02,0.05,0.46,0.88],'Pipeline de extracao — 1 pilar', E)
        code_block(al,[
            'for pilar_txt in pilares_txt:',
            "    px, py = pilar_txt['x'], pilar_txt['y']",
            '',
            '    # 1. Associar LWPOLYLINE',
            '    poly, score = associar_pilar(pilar_txt, polylines)',
            '',
            '    # 2. Dimensoes (R=600mm)',
            '    c, l = extrair_dimensoes((px,py), texts)',
            '',
            '    # 3. Nivel',
            '    nivel = extrair_nivel(texts)',
            '',
            '    # 4. Cambotado',
            '    if poly:',
            "        esp, tipo = detectar_cambotado(poly['entity'])",
            '    else:',
            "        esp, tipo = False, 'L'",
            '',
            '    # 5. Confidence',
            '    conf = calcular_confidence_pilar(',
            '        score,',
            '        tem_dimensao=(c > 0),',
            '        tem_texto_id=True,',
            '        tem_contorno=(poly is not None)',
            '    )',
            '',
            '    # 6. Decisao',
            '    if conf >= 0.80:   auto_assign(ficha)',
            '    elif conf >= 0.30: fila_revisao(ficha)',
            '    else:              rejeitar(ficha)',
        ], x=3, y=88, elem=E)

        ar = section(fig,[0.52,0.05,0.46,0.88],'Checklist de campos', E)
        code_block(ar,[
            '# OBRIGATORIOS:',
            '[ ] id            ← RE_PILAR.match(text)',
            '[ ] numero        ← digits(id)',
            '[ ] pavimento     ← nome arquivo DXF',
            '[ ] comprimento   ← max(d1,d2) RE_DIM',
            '[ ] largura       ← min(d1,d2)',
            '[ ] confidence    ← raio_score + penal.',
            '',
            '# OPCIONAIS (nao penalizam conf):',
            '[ ] altura_cm     ← nivel_chegada-saida',
            '[ ] nivel_saida_m ← layer NIVEL',
            '[ ] par_1_2..8_9  ← texto armadura',
            '[ ] grade_1..3    ← texto estribo',
            '[ ] pilar_especial← bulge > 0.01',
            '',
            '# REGRAS DE OURO:',
            '#',
            '# LWPOLYLINE sozinha NAO e pilar.',
            '# Precisa de texto RE_PILAR.',
            '#',
            '# comprimento = SEMPRE maior lado.',
            '#',
            '# Layer "Pain?is" = "Paineis".',
            '# Usar normalize_layer() SEMPRE.',
            '#',
            '# BA*/VB* = balanco → 1 apoio OK.',
            '#',
            '# score < 0.80 → revisao humana.',
        ], x=3, y=88, elem=E)
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

    print(f'[OK] Pilares PDF: {path}')


# ══════════════════════════════════════════════════════════════════════════
# VIGAS PDF  (12 paginas)
# ══════════════════════════════════════════════════════════════════════════
def vigas_pdf(path):
    E = 'VIGA'; total = 12
    with PdfPages(str(path)) as pdf:
        pages = [
          ('V-1','Identificacao — RE_VIGA + prefixos',[
            'RE_VIGA = re.compile(',
            "    r'^(V|BA|VB|VT|VC)\\.?-?\\d+([A-Z]|\\.\\d+|/\\d+)?$',",
            '    re.IGNORECASE)',
            '# CASAM: V1 V101 BA1 VB1 VT1 VC1',
            '#        V1A V1.2 V-1 V1/2',
            '# NAO:   VIGA  V  LV1',
            '',
            '# Prefixos:',
            '# V  = viga padrao',
            '# BA = balanco (1 apoio)',
            '# VB = viga de bordo (balanco)',
            '# VT = viga tronco (var)',
            '# VC = viga curva',
            '',
            'def is_balanco(codigo: str) -> bool:',
            "    return bool(re.match(r'^(BA|VB)\\d+',",
            '                        codigo, re.IGNORECASE))',
            '',
            '# BA*/VB*: apoio_fim="" e CORRETO',
            '# Nao e erro ter apenas 1 apoio',
          ],[
            '# Extracao TEXT/MTEXT:',
            'for e in msp:',
            "    if e.dxftype()=='TEXT':",
            '        text  = e.dxf.text.strip()',
            '        x,y   = e.dxf.insert.x, e.dxf.insert.y',
            '        layer = e.dxf.layer',
            "    elif e.dxftype()=='MTEXT':",
            '        text  = e.plain_text()',
            '        x,y   = e.dxf.insert.x, e.dxf.insert.y',
            '        layer = e.dxf.layer',
            '    else: continue',
            '',
            '    if text and RE_VIGA.match(text):',
            '        vigas_txt.append({',
            "            'text':text,'x':x,'y':y,",
            "            'layer':layer})",
            '',
            '# Layers esperados:',
            '# NOMENCLATURA (14/14)',
            '# texto (14/14)',
            '# TEXTO_GERAL  (13/14)',
          ]),
          ('V-2','Geometria — LINE entities LV e FV',[
            '# DIFERENCA CRITICA:',
            '# PILAR → LWPOLYLINE FECHADA',
            '# VIGA  → LINE entities',
            '',
            'VIGA_SEARCH_RADIUS = 1200.0  # mm',
            '',
            'lines = []',
            'for e in msp.query("LINE"):',
            '    lines.append({',
            "        'start':(e.dxf.start.x,e.dxf.start.y),",
            "        'end':  (e.dxf.end.x,  e.dxf.end.y),",
            "        'layer': e.dxf.layer,",
            "        'length': math.hypot(",
            '            e.dxf.end.x-e.dxf.start.x,',
            '            e.dxf.end.y-e.dxf.start.y)',
            '    })',
            '',
            '# LV = Lateral de Viga',
            '#      layer "Paineis"/"Pain?is"',
            '# FV = Fundo de Viga',
            "#      layer 'fundo'/'FUNDOS'",
          ],[
            '# Layers criticos VIGA:',
            '',
            '# LV (Lateral):',
            '# "Paineis"/"Pain?is" → PANEL_GEOMETRY',
            '',
            '# FV (Fundo):',
            "# 'fundo'/'FUNDOS' → BEAM_BOTTOM",
            '',
            'BEAM_BOTTOM_ALIASES = {',
            "    'fundo','fundos',",
            "    'fundo da viga','fundo viga','fv'",
            '}',
            '',
            'def is_fv(layer:str)->bool:',
            '    return layer.lower().strip() \\',
            '           in BEAM_BOTTOM_ALIASES',
            '',
            '# Situacao: LV sem FV',
            '# → registrar como LV',
            '# → "fundo_ausente": True',
            '',
            '# 66521 LINE em LV (14 arqs)',
            '# 10310 LWPOLYLINE em LV',
          ]),
          ('V-3','Dimensoes b e h — RE_DIM e RE_DIM_BH',[
            "RE_DIM = re.compile(r'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})')",
            'RE_DIM_BH = re.compile(',
            "    r'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})',",
            '    re.IGNORECASE|re.DOTALL)',
            '',
            'def extrair_dim_viga(text:str):',
            '    m = RE_DIM.search(text)',
            '    if m:',
            '        d1,d2=float(m.group(1)),float(m.group(2))',
            '        # b=menor h=maior (convencao viga)',
            '        return min(d1,d2), max(d1,d2)',
            '    m = RE_DIM_BH.search(text)',
            '    if m:',
            '        # b e h explicitos',
            '        return float(m.group(1)),float(m.group(2))',
            '    return 0.0, 0.0',
            '',
            '# Sem dim: largura=0 altura=0',
            '# confidence -= 0.30',
          ],[
            '# DIFERENCA PILAR vs VIGA:',
            '',
            '# Pilar:',
            '# comprimento = max(d1,d2)',
            '# largura     = min(d1,d2)',
            '',
            '# Viga:',
            '# largura = b = min(d1,d2)',
            '# altura  = h = max(d1,d2)',
            '',
            '# "20x50" (viga):',
            '# largura=20  altura=50',
            '',
            '# "50x20" (viga):',
            '# largura=20  altura=50  (mesmo)',
            '',
            '# VALIDACAO:',
            '# largura: 12-100 cm',
            '# altura:  25-200 cm',
            '# largura < altura OBRIGATORIO',
            '# se inverso: TROCAR',
          ]),
          ('V-4','Schema JSON — FichaFase3Viga completa',[
            '{',
            '  "codigo":      "V101",',
            '  "pavimento":   "1_PAVIMENTO",',
            '  "tipo":        "retangular",',
            '  "largura":     20.0,   # b (cm)',
            '  "altura":      50.0,   # h (cm)',
            '  "comprimento": 480.0,  # span (cm)',
            '  "secao_transversal": {',
            '    "tipo":     "RET",',
            '    "largura":  20.0,',
            '    "altura":   50.0,',
            '    "area_cm2": 1000.0',
            '  },',
            '  "tramos": [{',
            '    "apoio_ini":   "P5",',
            '    "apoio_fim":   "P8",',
            '    "comprimento": 480.0,',
            '    "laje_esq":    "L3",',
            '    "laje_dir":    "L4"',
            '  }],',
            '  "confidence": 0.87',
            '}',
          ],[
            '# Armadura (opcional):',
            '"armadura_positiva": {',
            '  "barras":   3,',
            '  "diametro": 16,',
            '  "posicao":  "inferior"',
            '},',
            '"armadura_negativa": {',
            '  "barras":   2,',
            '  "diametro": 16,',
            '  "posicao":  "superior"',
            '},',
            '"estribos": {',
            '  "diametro":    8,',
            '  "espacamento": 15',
            '},',
            '"garfos": {',
            '  "tipo":       "HT20CT",',
            '  "quantidade": 4,',
            '  "posicao":    "lateral"',
            '},',
            '"dna_vector": [],',
            '"revisado":   False',
          ]),
          ('V-5','Apoios + Comprimento + Garfos',[
            'VIGA_SEARCH_RADIUS = 1200.0  # mm',
            '',
            'def encontrar_apoios(viga_pos, pilares_txt):',
            '    vx,vy = viga_pos',
            '    cands = []',
            '    for p in pilares_txt:',
            "        d = math.hypot(p['x']-vx,p['y']-vy)",
            '        if d <= VIGA_SEARCH_RADIUS:',
            '            c = max(0.0,1.0-d/VIGA_SEARCH_RADIUS)',
            "            cands.append((p['text'],d,c))",
            '    cands.sort(key=lambda x:x[1])',
            '    ini = cands[0][0] if cands else ""',
            '    fim = cands[1][0] if len(cands)>=2 else ""',
            '    return ini, fim',
            '',
            'def calc_comprimento(p1, p2)  -> float:',
            '    mm = math.hypot(p1.x-p2.x,p1.y-p2.y)',
            '    return round(mm/10, 1)  # mm→cm',
            '# alerta: comprimento > 1500cm',
          ],[
            '# GARFOS HT20CT — INSERT blocks',
            '',
            'garfos = []',
            'for e in msp.query("INSERT"):',
            '    bn  = e.dxf.name.upper()',
            '    lay = e.dxf.layer.upper()',
            "    if 'GARFO' in bn or \\",
            "       'HT20' in bn or \\",
            "       lay == 'GARFOS':",
            '        garfos.append({',
            "            'x':  e.dxf.insert.x,",
            "            'y':  e.dxf.insert.y,",
            "            'rotation': e.dxf.rotation,",
            "            'tipo':'HT20CT' if 'HT20' in bn",
            "                   else 'GARFO'",
            '        })',
            '',
            '# Associar garfo → viga mais proxima',
            '# por distancia espacial (nao por layer)',
          ]),
          ('V-6','Layers Vigas + Confidence + Decision',[
            '# Layers VIGA — LV (Lateral):',
            '# "Paineis"/"Pain?is" HIGH PANEL_GEOMETRY',
            '# "Escoras"           HIGH SHORING',
            '# "GARFOS"            HIGH FORK_METAL',
            '# "presilha"          HIGH CLAMP_METAL',
            '# "barrote"           HIGH BATTEN_BEAM',
            '# "Forcador"          HIGH SPACER',
            '# "SCO-___-LAJ"       HIGH SLAB_INTERFACE',
            '# "BARRA DE ANCORAGEM"HIGH ANCHOR_BAR_LV',
            '',
            '# Layers VIGA — FV (Fundo):',
            '# "fundo"/"FUNDOS"    HIGH BEAM_BOTTOM',
            '# "Fundo da Viga"     HIGH BEAM_BOTTOM',
            '',
            '# ATENCAO:',
            '# PL usa "BARRA ANCORAGEM" (sem "DE")',
            '# LV usa "BARRA DE ANCORAGEM" (com "DE")',
            '# Mesmo significado, nomes DIFERENTES!',
          ],[
            '# Confidence VIGA:',
            '# conf = raio_score',
            '# -0.30  sem dimensao',
            '# -0.15  LINE em layer nao-Paineis',
            '# -0.20  sem tramos',
            '',
            '# Fallback Chain:',
            '# 1. RE_VIGA+NOMENCLATURA → LINE Paineis/fundo',
            '#    conf = raio_score',
            '# 2. RE_VIGA → LINE layer nao-Paineis',
            '#    conf -= 0.15',
            '# 3. RE_VIGA + RE_DIM → ok (+0)',
            '# 4. RE_VIGA sem dim',
            '#    b=0 h=0, conf -= 0.30',
            '# 5. BA*/VB*: apoio_fim="" OK',
            '',
            '# Exemplos reais:',
            '# V101 "20x50" → c=0.92',
            '# BA3  "15x40" → c=0.75',
            '# V205 "b=25 h=60" → c=0.88',
          ]),
        ]
        extra_pages = [
          ('V-7','Validacao + Exemplos reais completos',[
            '# VALIDACAO FichaFase3Viga:',
            '# largura:     12-100 cm',
            '# altura:      25-200 cm',
            '# comprimento: > 0',
            '# tipo:        retangular/L/T',
            '# tramos:      >= 1',
            '# largura < altura OBRIGATORIO',
            '',
            '# Se largura > altura: TROCAR',
            '# l,h = h,l',
            '',
            '# Integridade cruzada:',
            '# apoio_ini=="" e nao balanco → aviso',
            '# comprimento > 1500cm → revisar',
          ],[
            '# Exemplos reais ALIMONTI:',
            '',
            '# DXF: V101 + "20x50"',
            '# TEXT layer=NOMENCLATURA text="V101"',
            '# TEXT layer=cotas text="20x50"',
            '# LINE layer=Paineis (LV)',
            '# LINE layer=fundo   (FV)',
            '# → largura=20 altura=50 conf=0.92',
            '',
            '# DXF: BA3 (balanco)',
            '# TEXT text="BA3"',
            '# TEXT text="15x40"',
            '# → apoio_fim="" (correto)',
            '# → conf=0.75',
            '',
            '# DXF: V205 MTEXT',
            '# MTEXT text="V205\\nb=25 h=60"',
            '# → largura=25 altura=60 conf=0.88',
          ]),
        ]
        for sc,st,lc,rc in pages+extra_pages:
            fig = new_fig()
            pg = int(sc[2:])
            header(fig,E,sc,st,pg,total)
            footer(fig,f'SPEC-VIGAS.md | {sc}')
            al = section(fig,[0.02,0.05,0.46,0.88],sc+' — esquerda',E)
            code_block(al,lc,x=3,y=88,elem=E)
            ar = section(fig,[0.52,0.05,0.46,0.88],sc+' — direita',E)
            code_block(ar,rc,x=3,y=88,elem=E)
            pdf.savefig(fig,bbox_inches='tight'); plt.close(fig)

        # Paginas 8-12 resumo
        resumos = [
            ('V-8', 'Fluxo Completo Viga',
             ['for viga_txt in vigas_txt:',
              "    vx,vy = viga_txt['x'],viga_txt['y']",
              '    # 1. LINEs proximas (LV+FV)',
              '    lv=[l for l in lines',
              '        if norm(l["layer"])=="PAINEIS"',
              '        and dist_mid(l,vx,vy)<=VIGA_SEARCH_RADIUS]',
              '    # 2. Dimensoes',
              '    b,h = extrair_dim_viga(texto_prox)',
              '    # 3. Apoios',
              '    ini,fim = encontrar_apoios((vx,vy),pils)',
              '    # 4. Comprimento',
              '    comp = calc_comprimento(p_ini,p_fim)',
              '    # 5. Confidence',
              '    conf = calcular_confidence_viga(score,b,ini)',
              '    # 6. Aceite',
              '    if conf>=0.80: auto_assign(ficha)',
              '    else:          fila_revisao(ficha)',
              ],
             ['# CHECKLIST:',
              '[ ] codigo      ← RE_VIGA.match()',
              '[ ] pavimento   ← nome DXF',
              '[ ] largura     ← min(d1,d2)',
              '[ ] altura      ← max(d1,d2)',
              '[ ] comprimento ← dist(p1,p2) mm→cm',
              '[ ] tramos[0]   ← apoio_ini+fim',
              '[ ] confidence  ← score+penalidades',
              '',
              '# Raios de busca:',
              '# VIGA_SEARCH_RADIUS = 1200mm',
              '# DIM_SEARCH_RADIUS  =  600mm',
              '',
              '# BA*/VB*:',
              '# apoio_fim="" e CORRETO',
              '# is_balanco() → True',
              ]),
        ]
        for i,(sc,st,lc,rc) in enumerate(resumos):
            pg = 8+i
            fig = new_fig()
            header(fig,E,sc,st,pg,total)
            footer(fig,f'SPEC-VIGAS.md | {sc}')
            al = section(fig,[0.02,0.05,0.46,0.88],'Pipeline',E)
            code_block(al,lc,x=3,y=88,elem=E)
            ar = section(fig,[0.52,0.05,0.46,0.88],'Checklist',E)
            code_block(ar,rc,x=3,y=88,elem=E)
            pdf.savefig(fig,bbox_inches='tight'); plt.close(fig)

        # Preencher ate 12
        for pg in range(9,13):
            sc=f'V-{pg}'
            fig = new_fig()
            header(fig,E,sc,f'Referencia — {sc}',pg,total)
            footer(fig,'SPEC-VIGAS.md | CONFIG-LAYERS.yaml')
            al=section(fig,[0.02,0.05,0.46,0.88],'Layers adicionais',E)
            table(al,[
                ('Escoras/Escora de Viga','SHORING','Escoras apoio','HIGH'),
                ('GARFOS',               'FORK_METAL','INSERT HT20CT','HIGH'),
                ('presilha/Presilha',    'CLAMP_METAL','Presilha','HIGH'),
                ('barrote',              'BATTEN_BEAM','Barrote','HIGH'),
                ('Forcador',             'SPACER','Espacador','HIGH'),
                ('SCO-___-LAJ',          'SLAB_INTERFACE','Laje-viga','HIGH'),
                ('BARRA DE ANCORAGEM',   'ANCHOR_BAR_LV','LV ancor.','HIGH'),
                ('material do compensado','PLYWOOD_MAT','Anotacao','MEDIUM'),
                ('detalhes',             'DETAIL_LAYER','Ignorar','LOW'),
                ('S-BEAM',               'TQS_BEAM','TQS viga','MEDIUM'),
            ],['Layer DXF','Canonical','Uso','Conf'],
               x=2,y=90,col_widths=[30,24,22,20],elem=E)
            ar=section(fig,[0.52,0.05,0.46,0.88],'Referencias',E)
            code_block(ar,['# Ver SPEC-VIGAS.md para detalhes completos',
                           '# Ver CONFIG-LAYERS.yaml §vigas',
                           '# Ver DECISION-MATRIX.md §4 (Vigas)',
                           '# Ver ficha_vigas_schema.py',
                           '',
                           '# Estatisticas DXF reais (14 arquivos LV):',
                           '# LINE:        66521 entidades',
                           '# LWPOLYLINE:  10310 entidades',
                           '# TEXT:         9959 entidades',
                           '# INSERT:       varia por obra',
                           ],x=3,y=60,elem=E)
            pdf.savefig(fig,bbox_inches='tight'); plt.close(fig)

    print(f'[OK] Vigas PDF: {path}')


# ══════════════════════════════════════════════════════════════════════════
# LAJES PDF  (8 paginas)
# ══════════════════════════════════════════════════════════════════════════
def lajes_pdf(path):
    E = 'LAJE'; total = 8
    lj_pages = [
      ('L-1','Identificacao — RE_LAJE + RE_LAJE_H',[
        'RE_LAJE = re.compile(',
        "    r'^(L\\d+[A-Za-z]?|Y\\d+[A-Za-z]?",
        '    |X\\d+[A-Za-z]?|LAJ[-_]?\\d+',
        "    |LAJE[-_\\s]*\\d+)$',",
        '    re.IGNORECASE)',
        '# CASAM: L1 L12 L1A Y1 X2 LAJ-1 LAJE_2',
        '# NAO:   L  LAJE (sem numero)',
        '',
        'RE_LAJE_H = re.compile(',
        "    r'h\\s*[=:]\\s*([\\d,.]+)',",
        '    re.IGNORECASE)',
        '# Ex: "h=12" "h=14" "h:10" "h=12cm"',
        '# → espessura em cm',
        '',
        'LAJE_SEARCH_RADIUS = 1500.0  # mm',
        'CLUSTER_RADIUS     =  500.0  # mm',
      ],[
        '# DOIS CAMINHOS:',
        '',
        '# Caminho A: texto ID explicito',
        '# L1, L2, Y1 → laje identificada',
        '# confidence = raio_score',
        '',
        '# Caminho B: cluster h= sem ID',
        '# 3x "h=10" a <500mm entre si',
        '# → laje SYNTHETIC',
        '# → confidence = 0.50',
        '',
        '# Extracao espessura:',
        'def extrair_esp(texts, pos):',
        '    lx,ly = pos',
        '    cands = []',
        '    for t in texts:',
        "        m = RE_LAJE_H.search(t['text'])",
        '        if m:',
        "            d=math.hypot(t['x']-lx,t['y']-ly)",
        '            if d<=LAJE_SEARCH_RADIUS:',
        "                v=float(m.group(1).replace(',','.'))",
        '                cands.append((v,d))',
        '    cands.sort(key=lambda x:x[1])',
        '    return cands[0][0] if cands else 0.0',
      ]),
      ('L-2','Contorno LWPOLYLINE + area Shoelace',[
        'for e in msp.query("LWPOLYLINE"):',
        '    pts=[( float(p[0]),float(p[1]) )',
        '         for p in e.get_points("xy")]',
        '    is_closed=(getattr(e.dxf,"flags",0)&1==1)',
        '    if not is_closed or len(pts)<3: continue',
        '',
        '    area = shoelace(pts)',
        '    if area > 50000:',
        '        candidatos_laje.append(pts)',
        '    elif area < 5000:',
        '        candidatos_pilar.append(pts)',
        '',
        'def shoelace(pts) -> float:',
        '    n=len(pts); a=0.0',
        '    for i in range(n):',
        '        j=(i+1)%n',
        '        a+=pts[i][0]*pts[j][1]',
        '        a-=pts[j][0]*pts[i][1]',
        '    return abs(a)/2.0',
        '# area em mm²',
        '# area_m2 = area / 1_000_000',
      ],[
        '# Discriminacao PILAR vs LAJE:',
        '# area < 5.000 mm²   → pilar',
        '# area > 50.000 mm²  → laje',
        '# entre os dois → ambiguo (log)',
        '',
        '# Dimensoes da laje (bbox):',
        'from shapely.geometry import Polygon',
        '',
        'poly = Polygon(outline_pts)',
        'bbox = poly.bounds  # minx,miny,maxx,maxy',
        'comp = (bbox[2]-bbox[0])/10  # mm→cm',
        'larg = (bbox[3]-bbox[1])/10',
        '',
        '# Layer do contorno:',
        '# "Paineis"/"Pain?is" → PANEL_GEOMETRY',
        '# (mesmo alias do pilar)',
        '# Diferenca: area > 50000mm²',
        '',
        '# Espessura validacao:',
        '# < 7cm  → invalida confidence=0',
        '# > 40cm → suspeita, log aviso',
      ]),
      ('L-3','Laje Sintetica — cluster de h=',[
        'def gerar_sinteticas(laje_dims):',
        '    used=set(); clusters=[]',
        '    for i,d in enumerate(laje_dims):',
        '        if i in used: continue',
        '        cluster=[d]; used.add(i)',
        '        for j,d2 in enumerate(laje_dims):',
        '            if j in used: continue',
        "            dist=math.hypot(d['x']-d2['x'],",
        "                            d['y']-d2['y'])",
        '            if dist < CLUSTER_RADIUS:',
        '                cluster.append(d2)',
        '                used.add(j)',
        '        clusters.append(cluster)',
        '',
        '    sinteticas=[]',
        '    for idx,cluster in enumerate(clusters):',
        "        cx=sum(d['x'] for d in cluster)/len(cluster)",
        "        cy=sum(d['y'] for d in cluster)/len(cluster)",
        "        h=cluster[0]['h_val']",
        '        sinteticas.append({',
        '            "id":f"synth_{idx}",',
        '            "name":"SYNTHETIC",',
        '            "x":cx,"y":cy,',
        '            "espessura":h,',
        '            "confidence":0.50})',
        '    return sinteticas',
      ],[
        '# Exemplo: 3x "h=10" a <300mm',
        '',
        '# DXF:',
        '# TEXT layer=COTA text="h=10"',
        '#      insert=(3000,8000)',
        '# TEXT layer=COTA text="h=10"',
        '#      insert=(3200,8100)',
        '# TEXT layer=COTA text="h=10"',
        '#      insert=(3100,7900)',
        '',
        '# → 1 cluster → synth_0',
        '',
        '# JSON:',
        '# {',
        '#   "codigo": "synth_0",',
        '#   "tipo": "macica",',
        '#   "espessura": 10.0,',
        '#   "outline_segs": [],',
        '#   "confidence": 0.50',
        '# }',
        '',
        '# SYNTHETIC nao e erro.',
        '# E laje real sem ID explicito.',
        '# Requer revisao (conf < 0.80).',
      ]),
      ('L-4','Schema JSON — FichaFase3Laje',[
        '{',
        '  "codigo":    "L5",',
        '  "pavimento": "1_PAVIMENTO",',
        '  "tipo":      "macica",',
        '  "espessura": 12.0,     # cm',
        '  "dimensoes": {',
        '    "comprimento": 620.0,',
        '    "largura":     430.0,',
        '    "espessura":   12.0',
        '  },',
        '  "outline_segs": [',
        '    {"x":15000.0,"y":10000.0},',
        '    {"x":21200.0,"y":10000.0},',
        '    {"x":21200.0,"y":14300.0},',
        '    {"x":15000.0,"y":14300.0}',
        '  ],  # vertices mm DXF',
        '  "nivel":          2.80,',
        '  "vigas_around":   ["V101","V102"],',
        '  "pilares_around": ["P5","P6","P7"],',
        '  "confidence":     0.70',
        '}',
      ],[
        '# Layers criticos LAJE:',
        '',
        '# EST-LAJE-TEXT → SLAB_TEXT (L1,L2)',
        '# NOMENCLATURA  → ELEMENT_LABEL',
        '# EST-TEXT       → ELEMENT_LABEL',
        '# Pilares        → PILLAR_CUTOUT',
        '# VIGAS          → BEAM_INTERFACE',
        '# REAPROVEITAMENTO→ REUSE_STATUS',
        '# "Vazios"/"V?zio"→ VOID_OPENING',
        '# EST-PILAR-CUT  → PILLAR_CUT',
        '# "Paineis"      → PANEL_GEOMETRY',
        '',
        '# REUSE_STATUS valores:',
        '# BOM / REGULAR / RUIM / DESCARTE',
        '',
        '# tipo laje:',
        '# "macica"      (default)',
        '# "pre_moldada" (h= + vigotas INSERT)',
        '# "steel_deck"',
      ]),
      ('L-5','Confidence + Validacao + Aberturas',[
        'def calcular_confidence_laje(laje)->float:',
        '    conf = 0.30  # base',
        "    if laje.get('espessura',0) > 0:",
        '        conf += 0.30',
        "    if laje.get('outline_segs') and \\",
        "       len(laje['outline_segs']) >= 3:",
        '        conf += 0.20',
        "    if laje.get('vigas_around'):",
        '        conf += 0.20',
        '    return min(conf, 1.0)',
        '',
        '# SYNTHETIC: conf=0.50 fixo',
        '',
        '# Validacao:',
        '# espessura: 7-40 cm',
        '# < 7cm → invalida (conf=0)',
        '# outline: >= 3 vertices',
        '# se < 3: conf -= 0.2',
        '# dimensoes.comp > 0',
        '# dimensoes.larg > 0',
      ],[
        '# Aberturas (Vazios):',
        '',
        'VOID_ALIASES = {',
        '    "vazio","vazios","abertura",',
        '    "aberturas","buraco","void"',
        '}',
        '',
        'def is_void_layer(layer:str)->bool:',
        '    n=normalize_layer(layer).lower()',
        '    return n in VOID_ALIASES or "vaz" in n',
        '',
        '# Layer "Vazio" sofre CP1252:',
        '# "Vazio" → "V?zio" (corrompido)',
        '# normalize_layer("V?zio")="VAZIO"',
        '',
        '# Recortes de pilares:',
        'def detect_recortes(contorno,polys):',
        '    lp=Polygon(contorno)',
        '    for poly in polys:',
        '        if not poly["closed"]: continue',
        '        ln=normalize_layer(poly["layer"])',
        '        if ln not in ("PILARES",',
        '                      "EST-PILAR-CUT"): continue',
        '        rp=Polygon(poly["points"])',
        '        if lp.intersects(rp):',
        '            yield rp.area',
      ]),
      ('L-6','Exemplos Reais',[
        '# Exemplo 1 — L5 com ID explicito:',
        '# TEXT layer=EST-LAJE-TEXT text="L5"',
        '#      insert=(18000,12000)',
        '# TEXT layer=COTA text="h=12"',
        '#      insert=(18100,11900)',
        '# LWPOLYLINE layer=Paineis closed=True',
        '#   vertices=[(15000,10000),(21200,10000)',
        '#             (21200,14300),(15000,14300)]',
        '',
        '# → JSON:',
        '# codigo="L5"  espessura=12.0',
        '# dimensoes={comp:620,larg:430,esp:12}',
        '# outline_segs=[4 vertices]',
        '# confidence=1.0',
        '',
        '# Por que conf=1.0:',
        '# base=0.30 +0.30(h=12) +0.20(4pts)',
        '# +0.20(vigas detectadas) = 1.00',
      ],[
        '# Exemplo 2 — Abertura:',
        '# TEXT layer=EST-LAJE-TEXT text="L3"',
        '# LWPOLYLINE layer="Vazio" closed=True',
        '#   vertices=[(5800,5900),(5900,5900)',
        '#             (5900,6100),(5800,6100)]',
        '',
        '# → JSON:',
        '# "aberturas":[{"pontos":[...],"area":20000}]',
        '# confidence=0.80',
        '',
        '# Exemplo 3 — synth_0:',
        '# 3x TEXT "h=10" a <300mm',
        '# → codigo="synth_0"',
        '# → espessura=10.0',
        '# → outline_segs=[]',
        '# → confidence=0.50',
        '',
        '# Layer "Vazio" encoding:',
        '# CP1252 → "V?zio" ou "V\\xc3\\xa1zio"',
        '# normalize("V?zio")="VAZIO" ← OK',
      ]),
      ('L-7','Fluxo Completo + Checklist',[
        '# Caminho A (ID explicito):',
        'for txt in lajes_txt:',
        "    lx,ly = txt['x'],txt['y']",
        '    contorno = buscar_contorno(',
        '        (lx,ly), polylines,',
        '        area_min=50000,',
        '        raio=LAJE_SEARCH_RADIUS)',
        '    h = extrair_esp(texts,(lx,ly))',
        '    aberturas = detect_aberturas(contorno,polys)',
        '    vigas   = vizinhos(vigas_txt,lx,ly)',
        '    pilares = vizinhos(pilares_txt,lx,ly)',
        '    conf = calcular_confidence_laje({',
        "        'espessura':h,",
        "        'outline_segs':contorno,",
        "        'vigas_around':vigas})",
        '    if conf>=0.80: auto_assign(ficha)',
        '    else:          fila_revisao(ficha)',
        '',
        '# Caminho B:',
        'sinteticas = gerar_sinteticas(laje_dims)',
      ],[
        '# CHECKLIST FichaFase3Laje:',
        '',
        '[ ] codigo      ← RE_LAJE ou "synth_N"',
        '[ ] pavimento   ← nome DXF',
        '[ ] espessura   ← RE_LAJE_H (cm)',
        '[ ] outline_segs← LWPOLY fechada >50km2',
        '[ ] confidence  ← formula 4 comp.',
        '',
        '# Raios:',
        '# LAJE_SEARCH_RADIUS = 1500mm',
        '# CLUSTER_RADIUS     =  500mm',
        '',
        '# REGRAS DE OURO:',
        '# espessura < 7cm → invalida',
        '# outline < 3 pts → sintetica',
        '# sem vigas_around → suspeito',
        '# "V?zio"=normalize → "VAZIO"',
        '',
        '# Fontes:',
        '# SPEC-LAJES.md',
        '# CONFIG-LAYERS.yaml §lajes',
        '# DECISION-MATRIX.md §4',
      ]),
      ('L-8','Referencia Rapida — Todos os Patterns',[
        '# PATTERNS LAJES:',
        '# RE_LAJE:  L1 L12 L1A Y1 X2 LAJ-1',
        '# RE_LAJE_H: h=12 h=14 h:10 h=12cm',
        '',
        '# LAYERS:',
        '# EST-LAJE-TEXT → SLAB_TEXT (IDs)',
        '# NOMENCLATURA  → ELEMENT_LABEL',
        '# Paineis/Pain?is → PANEL_GEOMETRY',
        '# Pilares  → PILLAR_CUTOUT',
        '# VIGAS    → BEAM_INTERFACE',
        '# Vazio/V?zio → VOID_OPENING',
        '# REAPROVEITAMENTO → REUSE_STATUS',
        '',
        '# CONFIDENCE:',
        '# base=0.30',
        '# +0.30 se espessura>0',
        '# +0.20 se outline>=3 pts',
        '# +0.20 se vigas_around',
        '# SYNTHETIC: 0.50 fixo',
      ],[
        '# THRESHOLDS:',
        '# >=0.80: AUTO-ASSIGN',
        '# 0.50-0.79: aceitar+aviso',
        '# 0.30-0.49: revisao humana',
        '# <0.30: rejeitar',
        '',
        '# VALIDACOES:',
        '# espessura 7-40cm',
        '# outline >= 3 vertices',
        '# tipo: macica/pre_moldada/steel_deck',
        '',
        '# CASOS ESPECIAIS:',
        '# pre-moldada: h= + INSERT vigotas',
        '# grande s/ contorno: bbox vigas (conf=0.40)',
        '# h= conflito: mais proximo vence',
        '# encoding: normalize_layer() sempre',
        '',
        '# ESTATISTICAS DXF (14 arqs LJ):',
        '# LINE:        7500',
        '# LWPOLYLINE:  2301',
        '# TEXT:        2185',
      ]),
    ]
    with PdfPages(str(path)) as pdf:
        for pg,(sc,st,lc,rc) in enumerate(lj_pages,1):
            fig=new_fig()
            header(fig,E,sc,st,pg,total)
            footer(fig,f'SPEC-LAJES.md | {sc}')
            al=section(fig,[0.02,0.05,0.46,0.88],sc+' — esquerda',E)
            code_block(al,lc,x=3,y=88,elem=E)
            ar=section(fig,[0.52,0.05,0.46,0.88],sc+' — direita',E)
            code_block(ar,rc,x=3,y=88,elem=E)
            pdf.savefig(fig,bbox_inches='tight'); plt.close(fig)
    print(f'[OK] Lajes PDF: {path}')


if __name__ == '__main__':
    print('CAD-ANALYZER — Fichas v3 (fundo branco, completo)')
    pilares_pdf(OUT_DIR / 'fichas_pilares_instrutivas.pdf')
    vigas_pdf(OUT_DIR / 'fichas_vigas_instrutivas.pdf')
    lajes_pdf(OUT_DIR / 'fichas_lajes_instrutivas.pdf')
    print('\nConcluido:')
    for f in ['fichas_pilares_instrutivas.pdf',
              'fichas_vigas_instrutivas.pdf',
              'fichas_lajes_instrutivas.pdf']:
        p = OUT_DIR/f
        kb = p.stat().st_size//1024 if p.exists() else 0
        print(f'  {f}: {kb} KB')
