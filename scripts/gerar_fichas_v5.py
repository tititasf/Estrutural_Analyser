#!/usr/bin/env python3
"""Fichas Instrutivas v5 — CAD-ANALYZER
ReportLab + matplotlib diagrams embutidos
"""
import sys, math, tempfile
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle, Rectangle
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Preformatted, Image
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus.flowables import Flowable

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUT   = Path('D:/Agente-cad-PYSIDE/docs/fichas')
IMGS  = OUT / 'imgs'
OUT.mkdir(parents=True, exist_ok=True)
IMGS.mkdir(parents=True, exist_ok=True)

# ── PALETA ──────────────────────────────────────────────────────────────────
NAVY    = HexColor('#0d1b2e')
GRAY1   = HexColor('#f5f6f8')
GRAY2   = HexColor('#edf0f4')
BORDER  = HexColor('#ced4da')
TEXT    = HexColor('#1a1a2e')
TEXT2   = HexColor('#6b7280')
CODE_FG = HexColor('#1e3a5f')

ORANGE    = HexColor('#c94f00'); ORANGE_BG = HexColor('#fff4ee')
BLUE      = HexColor('#005fb8'); BLUE_BG   = HexColor('#eef4ff')
GREEN     = HexColor('#006b3f'); GREEN_BG  = HexColor('#edfff5')

WARN_BG = HexColor('#fffbea'); WARN_BD = HexColor('#d97706')
OK_BG   = HexColor('#f0fdf4'); OK_BD   = HexColor('#15803d')
ERR_BG  = HexColor('#fff1f1'); ERR_BD  = HexColor('#dc2626')
INFO_BG = HexColor('#eff6ff'); INFO_BD = HexColor('#2563eb')

PW, PH = A4
ML = 22*mm; MR = 22*mm; MT = 32*mm; MB = 24*mm
CW = PW - ML - MR   # ~166mm

# ── ESTILOS ─────────────────────────────────────────────────────────────────
def _make_styles():
    ss = getSampleStyleSheet()
    def add(name, **kw):
        try: ss.add(ParagraphStyle(name, **kw))
        except: pass
    add('Capa',    fontName='Helvetica-Bold', fontSize=26, textColor=NAVY, alignment=TA_CENTER, spaceAfter=4*mm)
    add('CapaSub', fontName='Helvetica',      fontSize=12, textColor=TEXT2, alignment=TA_CENTER, spaceAfter=2*mm)
    add('T1',      fontName='Helvetica-Bold', fontSize=14, textColor=NAVY, spaceBefore=5*mm, spaceAfter=2*mm)
    add('T2',      fontName='Helvetica-Bold', fontSize=11, textColor=TEXT, spaceBefore=4*mm, spaceAfter=1.5*mm)
    add('T3',      fontName='Helvetica-Bold', fontSize=9.5, textColor=TEXT, spaceBefore=3*mm, spaceAfter=1*mm)
    add('Body',    fontName='Helvetica',      fontSize=9,  textColor=TEXT, leading=14, spaceAfter=1.5*mm)
    add('Small',   fontName='Helvetica',      fontSize=8,  textColor=TEXT2, leading=12)
    add('Code',    fontName='Courier',        fontSize=8,  textColor=CODE_FG, leading=11, backColor=GRAY2)
    add('TH',      fontName='Helvetica-Bold', fontSize=8.5, textColor=white, alignment=TA_CENTER)
    add('TC',      fontName='Helvetica',      fontSize=8.5, textColor=TEXT, leading=12)
    add('TCc',     fontName='Courier',        fontSize=8,  textColor=HexColor('#1e3a5f'), leading=11)
    add('TCb',     fontName='Helvetica-Bold', fontSize=8.5, textColor=TEXT, leading=12)
    add('TCr',     fontName='Helvetica',      fontSize=8.5, textColor=TEXT, leading=12, alignment=TA_CENTER)
    add('Caption', fontName='Helvetica-Oblique', fontSize=7.5, textColor=TEXT2, alignment=TA_CENTER, spaceAfter=3*mm)
    return ss

SS = _make_styles()

def p(txt, s='Body'): return Paragraph(txt, SS[s])
def h1(txt):          return p(txt, 'T1')
def h2(txt):          return p(txt, 'T2')
def h3(txt):          return p(txt, 'T3')
def sp(n=3):          return Spacer(1, n*mm)
def hr(c=BORDER):     return HRFlowable(width='100%', thickness=0.4, color=c, spaceAfter=2*mm)
def caption(txt):     return p(txt, 'Caption')

def esc(t): return str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

# ── CODE BLOCK ──────────────────────────────────────────────────────────────
def cb(lines, title='', ec=ORANGE):
    code_text = '\n'.join(lines)
    pre = Preformatted(code_text, SS['Code'])
    inner = Table([[pre]], colWidths=[CW - 6*mm])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,-1), GRAY2),
        ('BOX',        (0,0),(-1,-1), 0.4, BORDER),
        ('LEFTPADDING',(0,0),(-1,-1), 10), ('RIGHTPADDING',(0,0),(-1,-1), 8),
        ('TOPPADDING', (0,0),(-1,-1),  7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    outer = Table([['', inner]], colWidths=[6*mm, CW - 6*mm])
    outer.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,-1), ec),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING', (0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('VALIGN',     (0,0),(-1,-1),'TOP'),
    ]))
    out = []
    if title:
        out.append(p(f'<font color="#{ec.hexval()[1:]}"><b>{esc(title)}</b></font>', 'Small'))
        out.append(sp(1))
    out.append(outer)
    return out

# ── TABLE ───────────────────────────────────────────────────────────────────
def tbl(headers, rows, col_widths=None, hdr_color=NAVY, col_styles=None):
    if col_widths is None:
        col_widths = [CW / len(headers)] * len(headers)
    def cell(c, i):
        if isinstance(c, Flowable): return c
        cs = col_styles[i] if col_styles and i < len(col_styles) else 'TC'
        return p(esc(str(c)), cs)
    data = [[p(esc(h),'TH') for h in headers]]
    for row in rows:
        data.append([cell(c,i) for i,c in enumerate(row)])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  hdr_color),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [GRAY1, white]),
        ('FONTSIZE',      (0,0),(-1,-1), 8.5),
        ('LEFTPADDING',   (0,0),(-1,-1), 6), ('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',    (0,0),(-1,-1), 4), ('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('GRID',          (0,0),(-1,-1), 0.3, BORDER),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    return t

# ── NOTE BOX ────────────────────────────────────────────────────────────────
def note(txt, kind='info'):
    bgs = {'info':(INFO_BG,INFO_BD,'▸'),'warn':(WARN_BG,WARN_BD,'⚠'),
           'ok':(OK_BG,OK_BD,'✓'),'err':(ERR_BG,ERR_BD,'✗')}
    bg, bd, ic = bgs.get(kind, bgs['info'])
    esc_txt = esc(txt)
    t = Table([[p(f'{ic}  {esc_txt}','Body')]], colWidths=[CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),bg), ('BOX',(0,0),(-1,-1),0.8,bd),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING', (0,0),(-1,-1), 6),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    return t

# ── INLINE IMAGE ────────────────────────────────────────────────────────────
def img(path, width_mm=None, caption_txt=''):
    w = (width_mm or 150) * mm
    items = [Image(str(path), width=w, height=None)]
    if caption_txt:
        items.append(p(f'<i>{esc(caption_txt)}</i>', 'Caption'))
    return items

# ── SECTION HEADER ──────────────────────────────────────────────────────────
class SH(Flowable):
    def __init__(self, num, title, ec=ORANGE, bg=ORANGE_BG):
        super().__init__()
        self.num=num; self.title=title; self.ec=ec; self.bg=bg
    def wrap(self, aW, aH):
        self._w = aW; return aW, 13*mm
    def draw(self):
        c=self.canv; w=self._w; h=13*mm
        c.setFillColor(self.bg); c.roundRect(0,0,w,h,3,fill=1,stroke=0)
        c.setFillColor(self.ec); c.roundRect(0,0,5,h,1,fill=1,stroke=0)
        c.setFillColor(self.ec); c.circle(13*mm,h/2,4.5*mm,fill=1,stroke=0)
        c.setFillColor(white); c.setFont('Helvetica-Bold',8)
        c.drawCentredString(13*mm,h/2-3,self.num)
        c.setFillColor(NAVY); c.setFont('Helvetica-Bold',10.5)
        c.drawString(22*mm,h/2-4,self.title)

# ── PAGE HEADER/FOOTER ──────────────────────────────────────────────────────
class PageHF:
    def __init__(self, elem, ec):
        self.elem=elem; self.ec=ec
    def __call__(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, PH-MT+6*mm, PW, MT-6*mm, fill=1, stroke=0)
        canvas.setFillColor(self.ec)
        canvas.rect(0, PH-MT+6*mm, 6, MT-6*mm, fill=1, stroke=0)
        canvas.setFillColor(white); canvas.setFont('Helvetica-Bold',9)
        canvas.drawString(ML, PH-11*mm, f'CAD-ANALYZER  ·  FICHAS {self.elem}')
        canvas.setFont('Helvetica',8); canvas.setFillColor(HexColor('#8ba0cc'))
        canvas.drawRightString(PW-MR, PH-11*mm, 'v5.0  ·  2026-03-19')
        canvas.setFillColor(BORDER); canvas.setLineWidth(0.3)
        canvas.line(ML, MB-5*mm, PW-MR, MB-5*mm)
        canvas.setFillColor(TEXT2); canvas.setFont('Helvetica',7.5)
        canvas.drawString(ML, MB-10*mm, 'CAD-ANALYZER  ·  Referência técnica para robô extrator DXF')
        canvas.drawRightString(PW-MR, MB-10*mm, f'Página {doc.page}')
        canvas.restoreState()

def make_doc(path, elem, ec):
    hf = PageHF(elem, ec)
    return SimpleDocTemplate(str(path), pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        onFirstPage=hf, onLaterPages=hf,
        title=f'CAD-ANALYZER · Fichas {elem}', author='Diana Corporação Senciente')

# ════════════════════════════════════════════════════════════════════════════
# DIAGRAMAS MATPLOTLIB → PNG
# ════════════════════════════════════════════════════════════════════════════
FIGW = 7.0   # largura padrão em polegadas

def _save(fig, name, dpi=150):
    path = IMGS / name
    fig.savefig(str(path), dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return path

def fig_3raios_pilar():
    """Diagrama dos 3 raios de associação texto→polígono (Pilares)."""
    fig, ax = plt.subplots(figsize=(FIGW, 4.2))
    ax.set_aspect('equal'); ax.axis('off'); ax.set_xlim(-1100,1100); ax.set_ylim(-700,700)

    # Zonas
    for r, color, alpha, label in [
        (800, '#ffe0cc', 0.50, ''),
        (5,   '#c0e0ff', 0.70, ''),
    ]:
        ax.add_patch(plt.Circle((0,0), r, color=color, alpha=alpha, zorder=1))

    # Borda zona próxima
    ax.add_patch(plt.Circle((0,0), 800, fill=False, edgecolor='#c94f00', lw=1.5, ls='--', zorder=2))
    ax.add_patch(plt.Circle((0,0), 5,   fill=False, edgecolor='#005fb8', lw=1.5, zorder=2))

    # Polígono (pilar)
    poly = plt.Polygon([(-120,-90),( 120,-90),(120,90),(-120,90)],
                        facecolor='#e8f0fe', edgecolor='#0d1b2e', lw=2, zorder=3)
    ax.add_patch(poly)
    ax.text(0, 0, 'P17', ha='center', va='center', fontsize=14,
            fontweight='bold', color='#0d1b2e', zorder=4)

    # Pontos de texto em cada zona
    # Dentro
    ax.plot(40, 30, 's', color='#006b3f', ms=9, zorder=5)
    ax.annotate('texto DENTRO\nscore = 1.0', (40,30), (250,200),
                fontsize=8, color='#006b3f', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#006b3f', lw=1.2))

    # Tocando (≤5mm)
    ax.plot(124, 30, 's', color='#005fb8', ms=9, zorder=5)
    ax.annotate('tocando (≤ 5mm)\nscore = 0.8', (124,30), (420,180),
                fontsize=8, color='#005fb8', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#005fb8', lw=1.2))

    # Próximo
    ax.plot(500, -200, 's', color='#c94f00', ms=9, zorder=5)
    ax.annotate('próximo\nscore decai\n0.5 → 0.0', (500,-200), (680,-380),
                fontsize=8, color='#c94f00', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#c94f00', lw=1.2))

    # Fora
    ax.plot(950, 400, 's', color='#6b7280', ms=9, zorder=5)
    ax.annotate('fora do raio\nignordo (0.0)', (950,400), (780,550),
                fontsize=8, color='#6b7280',
                arrowprops=dict(arrowstyle='->', color='#6b7280', lw=1.2))

    # Setas de raio
    ax.annotate('', (800,0), (0,0),
                arrowprops=dict(arrowstyle='<->', color='#c94f00', lw=1.5))
    ax.text(400, 30, 'PILAR_SEARCH_RADIUS = 800 mm',
            ha='center', va='bottom', fontsize=7.5, color='#c94f00')

    ax.set_title('Lógica 3 Raios — TextAssociator (Pilares)',
                 fontsize=11, fontweight='bold', color='#0d1b2e', pad=10)
    return _save(fig, 'pilar_3raios.png')


def fig_pilar_secao():
    """Diagrama de seção do pilar com dimensões."""
    fig, axes = plt.subplots(1, 2, figsize=(FIGW, 3.2))

    for ax, title, w, h, cambotado in [
        (axes[0], 'Pilar Retangular', 2.0, 5.0, False),
        (axes[1], 'Pilar Cambotado (bulge > 0.3)', 3.0, 3.0, True),
    ]:
        ax.set_aspect('equal'); ax.axis('off')
        ax.set_xlim(-1, 5); ax.set_ylim(-1, 7)

        if not cambotado:
            rect = plt.Rectangle((0.5, 0.5), w, h,
                                  facecolor='#fff4ee', edgecolor='#c94f00', lw=2)
            ax.add_patch(rect)
            cx, cy = 0.5 + w/2, 0.5 + h/2
            ax.text(cx, cy, 'P17', ha='center', va='center',
                    fontsize=13, fontweight='bold', color='#c94f00')
            # Cotas
            ax.annotate('', (0.5, -0.3), (2.5, -0.3),
                        arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.2))
            ax.text(1.5, -0.55, f'largura\n{int(w*10)}cm',
                    ha='center', va='top', fontsize=7.5, color='#0d1b2e')
            ax.annotate('', (-0.3, 0.5), (-0.3, 5.5),
                        arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.2))
            ax.text(-0.55, 3.0, f'comprimento\n{int(h*10)}cm',
                    ha='right', va='center', fontsize=7.5, color='#0d1b2e',
                    rotation=90)
            ax.text(cx, 6.3, 'comprimento ≥ largura (sempre)', ha='center',
                    fontsize=7, color='#6b7280', style='italic')
        else:
            # Polígono irregular com curva
            theta = np.linspace(0, np.pi/2, 30)
            xs = np.concatenate([[0.5], 0.5 + 2.5*np.cos(theta), [0.5]])
            ys = np.concatenate([[0.5], 0.5 + 2.5*np.sin(theta), [3.0]])
            ax.fill(xs, ys, facecolor='#ffeee0', edgecolor='#c94f00', lw=2, zorder=2)
            ax.text(1.5, 1.5, 'PC-1', ha='center', va='center',
                    fontsize=12, fontweight='bold', color='#c94f00')
            ax.annotate('bulge > 0.3\nneste vértice', (0.5, 3.0), (2.0, 4.5),
                        fontsize=8, color='#c94f00',
                        arrowprops=dict(arrowstyle='->', color='#c94f00', lw=1.2))
            ax.text(1.2, 5.8, 'pilar_especial = True\ntipo = "CAMBOTADO"',
                    ha='center', fontsize=7.5, color='#006b3f',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#f0fdf4',
                              edgecolor='#15803d', lw=1))

        ax.set_title(title, fontsize=9, fontweight='bold',
                     color='#0d1b2e', pad=8)

    fig.suptitle('Seção Transversal do Pilar — Tipos',
                 fontsize=11, fontweight='bold', color='#0d1b2e', y=1.02)
    return _save(fig, 'pilar_secao.png')


def fig_pilar_layers():
    """Diagrama de layers do pilar em perspectiva."""
    fig, ax = plt.subplots(figsize=(FIGW, 3.8))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis('off')

    layers = [
        (1.0, '#edf0f4', '#ced4da', 'Layer: COTA', 'TEXT/MTEXT  →  "20x50"  →  comprimento=50cm, largura=20cm'),
        (2.5, '#fff4ee', '#c94f00', 'Layer: NOMENCLATURA', 'TEXT/MTEXT  →  "P17"  →  texto ID do pilar'),
        (4.0, '#eef4ff', '#005fb8', 'Layer: Painéis  (pode vir "Pain?is" CP1252)', 'LWPOLYLINE closed=True  →  contorno do pilar  →  outline_segs[]'),
        (5.5, '#edfff5', '#006b3f', 'Layer: SARRAFO, SARR_2.2x7, CHAPA, etc.', 'LWPOLYLINE/LINE  →  componentes de fôrma  →  extraídos separadamente'),
    ]

    for y, bg, border, layer_name, description in layers:
        ax.add_patch(FancyBboxPatch((0.2, y-0.55), 9.6, 0.9,
                                    boxstyle='round,pad=0.05',
                                    facecolor=bg, edgecolor=border, lw=1.5))
        ax.text(0.5, y-0.02, layer_name, fontsize=8.5, fontweight='bold',
                color='#0d1b2e', va='center')
        ax.text(3.8, y-0.02, description, fontsize=7.5, color='#444466', va='center')

    ax.text(5.0, 0.35, 'normalize_layer("Painéis") == normalize_layer("Pain?is") == "PAINEIS"',
            ha='center', fontsize=7.5, color='#d97706', style='italic')
    ax.set_title('Layers do Pilar — O que cada layer contém',
                 fontsize=11, fontweight='bold', color='#0d1b2e', pad=10)
    return _save(fig, 'pilar_layers.png')


def fig_pilar_confidence():
    """Diagrama da fórmula de confidence."""
    fig, ax = plt.subplots(figsize=(FIGW, 3.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 5.5); ax.axis('off')

    ax.text(5, 5.2, 'Fórmula de Confidence — Pilares', ha='center',
            fontsize=11, fontweight='bold', color='#0d1b2e')

    # Componentes
    components = [
        (1.0, '#fff4ee', '#c94f00', 'raio_score', 'base', '+1.0 / +0.8 / 0.0–0.5'),
        (2.2, '#edfff5', '#006b3f', '- tem_dimensao', 'penalidade', '−0.30 se sem "20x50"'),
        (3.1, '#fff1f1', '#dc2626', '- tem_texto_id', 'penalidade severa', '−0.40 se sem ID P*/V*/L*'),
        (4.0, '#eff6ff', '#2563eb', '- tem_contorno', 'penalidade', '−0.20 se sem LWPOLYLINE'),
    ]
    for y, bg, border, term, kind, val in components:
        ax.add_patch(FancyBboxPatch((0.3, y-0.35), 4.5, 0.65,
                                    boxstyle='round,pad=0.05',
                                    facecolor=bg, edgecolor=border, lw=1.5))
        ax.text(0.6, y-0.02, term, fontsize=9, fontweight='bold', color='#0d1b2e', va='center')
        ax.text(5.1, y-0.02, val, fontsize=8, color='#444466', va='center')
        ax.text(4.9, y-0.02, f'({kind})', fontsize=7, color='#6b7280', va='center', ha='right')

    # Thresholds
    y0 = 0.2
    for x, w, color, label in [
        (0.3,  2.5, '#dc2626', '< 0.30\nREJEITAR'),
        (2.8,  1.5, '#d97706', '0.30–0.49\nREVISÃO'),
        (4.3,  2.0, '#2563eb', '0.50–0.79\nACEITAR+LOG'),
        (6.3,  2.5, '#15803d', '≥ 0.80\nAUTO'),
    ]:
        ax.add_patch(plt.Rectangle((x, y0), w, 0.55, facecolor=color+'33',
                                   edgecolor=color, lw=1.5))
        ax.text(x + w/2, y0 + 0.28, label, ha='center', va='center',
                fontsize=7, fontweight='bold', color=color)

    ax.text(5, -0.05, 'max(0.0, min(conf, 1.0))  →  aplicar threshold', ha='center',
            fontsize=7.5, color='#6b7280', style='italic')

    return _save(fig, 'pilar_confidence.png')


def fig_viga_lv_fv():
    """Diagrama corte transversal da viga mostrando LV (lateral) vs FV (fundo)."""
    fig, axes = plt.subplots(1, 2, figsize=(FIGW, 4.0))

    # Vista isométrica simplificada
    ax = axes[0]
    ax.set_xlim(-0.5, 6.5); ax.set_ylim(-0.5, 5.5); ax.axis('off')
    ax.set_title('Componentes da Viga\n(Vista Frontal)', fontsize=9, fontweight='bold',
                 color='#0d1b2e', pad=6)

    # FV (fundo)
    fv = plt.Rectangle((0.5, 0.3), 5.0, 0.4, facecolor='#eef4ff',
                        edgecolor='#005fb8', lw=2.5, zorder=3)
    ax.add_patch(fv)
    ax.text(3.0, 0.5, 'FV (Fundo da Viga)', ha='center', va='center',
            fontsize=8, fontweight='bold', color='#005fb8')

    # LV esquerda
    lv_l = plt.Rectangle((0.3, 0.7), 0.35, 3.2, facecolor='#fff4ee',
                          edgecolor='#c94f00', lw=2.5, zorder=3)
    ax.add_patch(lv_l)
    ax.text(0.47, 2.3, 'LV', ha='center', va='center', fontsize=8,
            fontweight='bold', color='#c94f00', rotation=90)

    # LV direita
    lv_r = plt.Rectangle((5.35, 0.7), 0.35, 3.2, facecolor='#fff4ee',
                          edgecolor='#c94f00', lw=2.5, zorder=3)
    ax.add_patch(lv_r)
    ax.text(5.52, 2.3, 'LV', ha='center', va='center', fontsize=8,
            fontweight='bold', color='#c94f00', rotation=90)

    # Escoras
    for x in [1.2, 2.5, 3.8, 5.0]:
        ax.plot([x, x], [-0.3, 0.3], color='#555577', lw=3, zorder=2)
        ax.add_patch(plt.Circle((x, -0.35), 0.12, color='#555577', zorder=3))
    ax.text(3.0, -0.7, 'Escoras (layer: Escoras)', ha='center', fontsize=7.5, color='#555577')

    # Dimensão h
    ax.annotate('', (0.0, 0.7), (0.0, 3.9),
                arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.2))
    ax.text(-0.3, 2.3, 'h\n(altura)', ha='center', fontsize=7.5, color='#0d1b2e')

    # Dimensão b
    ax.annotate('', (0.3, 4.3), (5.7, 4.3),
                arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.2))
    ax.text(3.0, 4.55, 'b (largura, sempre b < h)', ha='center',
            fontsize=7.5, color='#0d1b2e')

    # Labels de layer
    ax.text(3.0, 1.5, 'layer: fundo\n(LINE/LWPOLY)', ha='center', va='center',
            fontsize=7.5, color='#005fb8', style='italic')

    # Vista planta (apoios)
    ax = axes[1]
    ax.set_xlim(-0.5, 7.0); ax.set_ylim(-1.0, 4.0); ax.axis('off')
    ax.set_title('Vista Superior — Apoios\ne Comprimento', fontsize=9, fontweight='bold',
                 color='#0d1b2e', pad=6)

    # Pilares
    for x, pid in [(0.0,'P5'), (6.0,'P6')]:
        ax.add_patch(plt.Rectangle((x-0.4, 0.5), 0.8, 1.5,
                                   facecolor='#fff4ee', edgecolor='#c94f00', lw=2))
        ax.text(x, 1.25, pid, ha='center', va='center', fontsize=9,
                fontweight='bold', color='#c94f00')

    # Viga (linha de fundo)
    ax.plot([0.4, 5.6], [1.8, 1.8], color='#005fb8', lw=4, solid_capstyle='round')
    ax.plot([0.4, 5.6], [0.7, 0.7], color='#005fb8', lw=4, solid_capstyle='round')
    # Rótulo V101
    ax.text(3.0, 1.25, 'V101', ha='center', va='center', fontsize=11,
            fontweight='bold', color='#005fb8')

    # Comprimento
    ax.annotate('', (0.4, -0.3), (5.6, -0.3),
                arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.5))
    ax.text(3.0, -0.65, 'comprimento = 450 cm\n(math.hypot(end - start) / 10)',
            ha='center', fontsize=7.5, color='#0d1b2e')

    # Apoio labels
    ax.text(0.0, 3.5, 'apoio_ini\n= "P5"', ha='center', fontsize=8,
            color='#006b3f', fontweight='bold')
    ax.text(6.0, 3.5, 'apoio_fim\n= "P6"', ha='center', fontsize=8,
            color='#006b3f', fontweight='bold')
    ax.plot([0.0, 0.0], [3.2, 2.0], color='#006b3f', lw=1, ls=':')
    ax.plot([6.0, 6.0], [3.2, 2.0], color='#006b3f', lw=1, ls=':')

    fig.tight_layout()
    return _save(fig, 'viga_lv_fv.png')


def fig_viga_balanco():
    """Diagrama viga em balanço BA* vs viga normal."""
    fig, axes = plt.subplots(1, 2, figsize=(FIGW, 3.5))

    for ax, titulo, apoio_fim, code_label in [
        (axes[0], 'Viga Normal  V101', '"P6"',  'apoio_fim = "P6"\n✓ 2 apoios'),
        (axes[1], 'Viga Balanço  BA-5', '""',    'apoio_fim = ""\n✓ CORRETO — 1 apoio'),
    ]:
        ax.set_xlim(-0.5, 7.0); ax.set_ylim(-1.5, 3.5); ax.axis('off')
        ax.set_title(titulo, fontsize=9, fontweight='bold', color='#0d1b2e', pad=6)

        # Pilar ini (sempre presente)
        ax.add_patch(plt.Rectangle((-0.3, 0.3), 0.8, 1.4,
                                   facecolor='#fff4ee', edgecolor='#c94f00', lw=2))
        ax.text(0.1, 1.0, 'P8', ha='center', va='center', fontsize=9,
                fontweight='bold', color='#c94f00')
        ax.text(0.1, -0.2, 'apoio_ini\n="P8"', ha='center', fontsize=7.5, color='#006b3f')

        if apoio_fim != '""':
            # Pilar fim presente
            ax.add_patch(plt.Rectangle((5.5, 0.3), 0.8, 1.4,
                                       facecolor='#fff4ee', edgecolor='#c94f00', lw=2))
            ax.text(5.9, 1.0, 'P6', ha='center', va='center', fontsize=9,
                    fontweight='bold', color='#c94f00')
            ax.text(5.9, -0.2, 'apoio_fim\n="P6"', ha='center', fontsize=7.5, color='#006b3f')
            ax.plot([0.5, 5.5], [1.0, 1.0], color='#005fb8', lw=5, solid_capstyle='round')
        else:
            # Sem pilar fim — balanço
            ax.plot([0.5, 6.0], [1.0, 1.0], color='#005fb8', lw=5, solid_capstyle='round')
            # Seta livre
            ax.annotate('', (6.5, 1.0), (5.8, 1.0),
                        arrowprops=dict(arrowstyle='->', color='#dc2626', lw=2))
            ax.text(6.2, 0.3, 'livre', fontsize=8, color='#dc2626')
            ax.text(5.9, -0.2, 'apoio_fim\n= ""  OK!', ha='center', fontsize=7.5, color='#006b3f')

        # Label da viga
        ax.text(3.0, 1.35, titulo.split()[1], ha='center', fontsize=10,
                fontweight='bold', color='#005fb8')

        # Code badge
        color = '#15803d' if '✓' in code_label else '#dc2626'
        ax.text(3.0, -1.1, code_label, ha='center', fontsize=8.5,
                color=color, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#f0fdf4' if '✓' in code_label else '#fff1f1',
                          edgecolor=color, lw=1))

    fig.suptitle('Viga Normal vs Balanço (BA*/VB*)', fontsize=11,
                 fontweight='bold', color='#0d1b2e')
    fig.tight_layout()
    return _save(fig, 'viga_balanco.png')


def fig_laje_contorno():
    """Diagrama de laje com contorno, h=, ID e aberturas."""
    fig, ax = plt.subplots(figsize=(FIGW, 4.8))
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_xlim(-200, 6400); ax.set_ylim(-400, 4700)

    # Laje principal
    lx, ly, lw, lh = 0, 0, 6200, 4300
    ax.add_patch(plt.Rectangle((lx,ly), lw, lh,
                                facecolor='#edfff5', edgecolor='#006b3f', lw=2.5))

    # Contorno label
    ax.text(lx+lw/2, -250, 'LWPOLYLINE  layer="Painéis"  closed=True',
            ha='center', fontsize=8.5, color='#006b3f', style='italic')

    # Texto L5
    ax.text(1200, 3800, 'L5', fontsize=20, fontweight='bold', color='#006b3f')
    ax.text(1200, 3550, 'layer: EST-LAJE-TEXT', fontsize=8, color='#555577', style='italic')

    # Texto h=12
    ax.add_patch(FancyBboxPatch((2800-180, 2200-130), 360, 260,
                                boxstyle='round,pad=20', facecolor='white',
                                edgecolor='#d97706', lw=1.5))
    ax.text(2800, 2300, 'h=12', ha='center', fontsize=14, color='#d97706', fontweight='bold')
    ax.text(2800, 2000, 'layer: COTA', ha='center', fontsize=8, color='#555577', style='italic')
    ax.text(2800, 1750, '→ espessura = 12.0 cm', ha='center', fontsize=8.5, color='#006b3f')

    # Abertura (Vazio)
    ax.add_patch(plt.Rectangle((4200, 1200), 800, 600,
                                facecolor='white', edgecolor='#dc2626', lw=2, ls='--'))
    ax.text(4600, 1500, 'Abertura', ha='center', va='center', fontsize=9,
            fontweight='bold', color='#dc2626')
    ax.text(4600, 1100, 'layer: "Vázio"  ou  "V?zio"', ha='center',
            fontsize=7.5, color='#dc2626', style='italic')
    ax.text(4600, 900, '→ is_void_layer() com normalize()', ha='center',
            fontsize=7.5, color='#555577')

    # Recorte de pilar
    ax.add_patch(plt.Rectangle((400, 300), 300, 400,
                                facecolor='#fff4ee', edgecolor='#c94f00', lw=2))
    ax.text(550, 500, 'P5', ha='center', va='center', fontsize=10,
            fontweight='bold', color='#c94f00')
    ax.text(550, 150, 'layer: Pilares', ha='center', fontsize=7.5, color='#c94f00', style='italic')

    # Vigas adjacentes
    ax.plot([0, 6200], [0, 0], color='#005fb8', lw=3, zorder=2)
    ax.text(3100, -120, 'Viga V102  (layer: VIGAS)', ha='center', fontsize=7.5, color='#005fb8')
    ax.plot([0, 0], [0, 4300], color='#005fb8', lw=3, zorder=2)

    # Dimensões bbox
    ax.annotate('', (0, 4500), (6200, 4500),
                arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.5))
    ax.text(3100, 4620, 'comprimento = 620 cm  (bbox)', ha='center', fontsize=8, color='#0d1b2e')
    ax.annotate('', (6400, 0), (6400, 4300),
                arrowprops=dict(arrowstyle='<->', color='#0d1b2e', lw=1.5))
    ax.text(6500, 2150, 'largura\n430 cm', ha='left', va='center', fontsize=8, color='#0d1b2e')

    ax.set_title('Anatomia da Laje no DXF — Todos os Elementos',
                 fontsize=11, fontweight='bold', color='#0d1b2e', pad=12)
    return _save(fig, 'laje_contorno.png')


def fig_laje_sintetica():
    """Diagrama de laje sintética a partir de clusters h=."""
    fig, axes = plt.subplots(1, 2, figsize=(FIGW, 3.6))

    ax = axes[0]
    ax.set_aspect('equal'); ax.axis('off'); ax.set_xlim(-300, 1800); ax.set_ylim(-300, 1600)
    ax.set_title('Entrada: textos h= sem ID L*', fontsize=9,
                 fontweight='bold', color='#0d1b2e', pad=6)

    pts = [(200,200),(350,220),(280,320),(250,260)]
    isolado = (1400, 1200)

    # CLUSTER_RADIUS
    cx = sum(p[0] for p in pts)/len(pts)
    cy = sum(p[1] for p in pts)/len(pts)
    ax.add_patch(plt.Circle((cx,cy), 500, color='#edfff5', alpha=0.6, zorder=1))
    ax.add_patch(plt.Circle((cx,cy), 500, fill=False, edgecolor='#006b3f',
                              lw=1.5, ls='--', zorder=2))
    ax.text(cx, cy+520, 'CLUSTER_RADIUS = 500mm', ha='center', fontsize=8,
            color='#006b3f')

    for x, y in pts:
        ax.add_patch(FancyBboxPatch((x-80, y-55), 160, 110,
                                    boxstyle='round,pad=10', facecolor='#fffbea',
                                    edgecolor='#d97706', lw=1.5, zorder=3))
        ax.text(x, y, 'h=10', ha='center', va='center', fontsize=9,
                fontweight='bold', color='#d97706')

    # Isolado
    ax.add_patch(FancyBboxPatch((isolado[0]-80, isolado[1]-55), 160, 110,
                                boxstyle='round,pad=10', facecolor='#fffbea',
                                edgecolor='#d97706', lw=1.5, alpha=0.5, zorder=3))
    ax.text(isolado[0], isolado[1], 'h=10', ha='center', va='center',
            fontsize=9, color='#d97706', alpha=0.5)

    ax.text(cx, -250, f'Cluster: {len(pts)} textos → centróide ({int(cx)},{int(cy)})',
            ha='center', fontsize=7.5, color='#0d1b2e')
    ax.text(isolado[0], isolado[1]-180, 'Isolado\n(cluster separado)', ha='center',
            fontsize=7.5, color='#6b7280')

    ax = axes[1]
    ax.set_aspect('equal'); ax.axis('off'); ax.set_xlim(-300,1800); ax.set_ylim(-300,1600)
    ax.set_title('Saída: Lajes Sintéticas geradas', fontsize=9,
                 fontweight='bold', color='#0d1b2e', pad=6)

    ax.add_patch(plt.Rectangle((cx-400, cy-300), 800, 600,
                                facecolor='#edfff5', edgecolor='#006b3f', lw=2, ls='--'))
    ax.text(cx, cy, 'synth_0', ha='center', va='center', fontsize=11,
            fontweight='bold', color='#006b3f')
    ax.text(cx, cy-180, 'espessura=10cm\nconfidence=0.50', ha='center',
            fontsize=8, color='#006b3f')
    ax.text(cx, cy+230, 'outline_segs=[]  (estimado)', ha='center',
            fontsize=7.5, color='#6b7280', style='italic')

    ax.add_patch(plt.Rectangle((isolado[0]-200, isolado[1]-150), 400, 300,
                                facecolor='#edfff5', edgecolor='#006b3f', lw=2, ls='--',
                                alpha=0.5))
    ax.text(isolado[0], isolado[1], 'synth_1', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#006b3f', alpha=0.6)

    fig.suptitle('Laje Sintética — Geração por Clusters de h=',
                 fontsize=11, fontweight='bold', color='#0d1b2e')
    fig.tight_layout()
    return _save(fig, 'laje_sintetica.png')


def fig_laje_confidence():
    """Diagrama visual do cálculo de confidence para laje."""
    fig, ax = plt.subplots(figsize=(FIGW, 3.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 4.5); ax.axis('off')
    ax.set_title('Confidence da Laje — Composição', fontsize=11,
                 fontweight='bold', color='#0d1b2e', pad=10)

    items = [
        (3.8, '#f5f6f8', '#ced4da', 'conf = 0.30', 'base mínima'),
        (3.1, '#edfff5', '#15803d', '+ 0.30', 'espessura h= encontrada (7–40cm)'),
        (2.4, '#eff6ff', '#2563eb', '+ 0.20', 'outline_segs ≥ 3 vértices (contorno)'),
        (1.7, '#fff4ee', '#c94f00', '+ 0.20', 'vigas_around não vazio'),
    ]
    for y, bg, color, term, desc in items:
        ax.add_patch(FancyBboxPatch((0.3, y-0.28), 9.4, 0.55,
                                    boxstyle='round,pad=0.05',
                                    facecolor=bg, edgecolor=color, lw=1.5))
        ax.text(0.7, y, term, fontsize=10, fontweight='bold', color=color, va='center')
        ax.text(2.5, y, desc, fontsize=8.5, color='#444466', va='center')

    # Totais
    totais = [(0.30,'0.30','#dc2626'), (0.60,'0.60','#d97706'),
              (0.80,'0.80','#2563eb'), (1.00,'1.00','#15803d')]
    for conf, label, color in totais:
        x = 0.3 + conf * 9.4
        ax.plot([x], [0.5], 'v', color=color, ms=8, zorder=3)
        ax.text(x, 0.1, label, ha='center', fontsize=7.5, color=color, fontweight='bold')

    ax.plot([0.3, 9.7], [0.55, 0.55], color='#ced4da', lw=1)
    ax.text(5.0, 0.75, '↑ Thresholds: 0.30=revisar  0.50=aceitar  0.80=auto',
            ha='center', fontsize=7.5, color='#6b7280', style='italic')
    ax.text(5.0, 4.3, 'Laje SYNTHETIC: sempre confidence = 0.50 (independente da fórmula)',
            ha='center', fontsize=8, color='#d97706', style='italic')

    return _save(fig, 'laje_confidence.png')


def fig_pipeline_pilares():
    """Fluxo do pipeline de extração de pilares."""
    fig, ax = plt.subplots(figsize=(FIGW, 5.0))
    ax.set_xlim(0, 10); ax.set_ylim(-0.5, 11.5); ax.axis('off')
    ax.set_title('Pipeline de Extração — Pilares', fontsize=11,
                 fontweight='bold', color='#0d1b2e', pad=8)

    steps = [
        (10.5, '#fff4ee', '#c94f00', '1  ezdxf.readfile(path)', 'Carregar DXF → msp (modelspace)'),
        (9.5,  '#edf0f4', '#555577', '2  normalize_layer()',     'NFKD → ASCII → UPPER em todos os layers'),
        (8.5,  '#edf0f4', '#555577', '3  Coletar textos',        'TEXT/MTEXT → filtrar RE_PILAR → lista pilares_txt'),
        (7.5,  '#edf0f4', '#555577', '4  Coletar polígonos',     'LWPOLYLINE closed=True, area > 0 → poly_candidates'),
        (6.5,  '#fff4ee', '#c94f00', '5  TextAssociator',        'Parear texto↔poly: score 1.0 / 0.8 / 0.0–0.5'),
        (5.5,  '#edf0f4', '#555577', '6  Extrair dimensões',     'RE_DIM / RE_DIM_BH em raio DIM_SEARCH_RADIUS=600mm'),
        (4.5,  '#edf0f4', '#555577', '7  Detectar cambotado',    'get_points("xyb") → bulge > 0.3 → tipo="CAMBOTADO"'),
        (3.5,  '#edf0f4', '#555577', '8  Extrair nível',         'Layer NIVEL → RE_NIVEL → cota_m'),
        (2.5,  '#fff4ee', '#c94f00', '9  Confidence',            'calcular_confidence(raio, dim, id, contorno)'),
        (1.5,  '#edfff5', '#15803d', '10 Threshold',             '≥0.80:auto  0.50–0.79:warn  0.30–0.49:review  <0.30:❌'),
        (0.5,  '#eff6ff', '#2563eb', '11 JSON',                  'FichaFase3Pilar → salvar por obra/pavimento'),
    ]

    for y, bg, color, num_action, detail in steps:
        ax.add_patch(FancyBboxPatch((0.2, y-0.38), 9.6, 0.75,
                                    boxstyle='round,pad=0.05',
                                    facecolor=bg, edgecolor=color, lw=1.5))
        ax.text(0.5, y, num_action, fontsize=8.5, fontweight='bold', color=color, va='center')
        ax.text(3.2, y, detail, fontsize=7.5, color='#444466', va='center')
        if y > 0.5:
            ax.annotate('', (5.0, y-0.38), (5.0, y-0.5),
                        arrowprops=dict(arrowstyle='->', color='#ced4da', lw=1))

    return _save(fig, 'pipeline_pilares.png')


# ════════════════════════════════════════════════════════════════════════════
# CONTEÚDO — PILARES
# ════════════════════════════════════════════════════════════════════════════
def build_pilares():
    ec = ORANGE; bg = ORANGE_BG
    def sec(n, t): return SH(n, t, ec, bg)

    s = []

    # ── CAPA ────────────────────────────────────────────────────────────────
    s += [
        sp(12), p('CAD-ANALYZER', 'Capa'), p('Fichas de Extração — PILARES', 'CapaSub'),
        sp(2),
        note('Esta ficha responde: dado um texto/polígono no DXF, qual campo JSON extrair e como.', 'info'),
        sp(3), hr(ec), sp(2),
    ]
    s.append(tbl(['#','Seção','Conteúdo'],
        [['1','Identificação','RE_PILAR · padrões · exemplos'],
         ['2','Associação texto→polígono','3 raios · scores · algoritmo + diagrama'],
         ['3','Seção Transversal','comprimento·largura·cambotado + diagrama'],
         ['4','Layers','NOMENCLATURA·Painéis·aliases + diagrama'],
         ['5','Schema JSON Completo','FichaFase3Pilar · todos os campos'],
         ['6','Confidence e Fallbacks','fórmula + diagrama visual · cadeia de 5 níveis'],
         ['7','Matriz de Decisão','todos os casos ambíguos'],
         ['8','Exemplos Reais ALIMONTI','P17 (1.0) · P5 (0.394) · PC-1 cambotado'],
         ['9','Pipeline Completo','fluxo E2E + diagrama · checklist'],
        ], [12*mm, 52*mm, CW-64*mm]))
    s.append(PageBreak())

    # ── 1. IDENTIFICAÇÃO ────────────────────────────────────────────────────
    s.append(sec('1', 'Identificação — RE_PILAR'))
    s.append(sp(2))
    s += cb([
        "RE_PILAR = re.compile(",
        "    r'^(PC?\\.?-?\\d+([A-Z]|\\.-?\\d+)?'",
        "    r'|P-\\d+[A-Z]?'",
        "    r'|PILAR[-_\\s]*\\d+)',",
        "    re.IGNORECASE",
        ")",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Texto DXF','Casou?','Campo extraído'],
        [['P17','✓ SIM','codigo = "P17"'],
         ['P17A','✓ SIM','codigo = "P17A" (sufixo letra)'],
         ['PC-1','✓ SIM','codigo = "PC-1" (pilar de canto)'],
         ['P.17','✓ SIM','codigo = "P.17"'],
         ['P-8','✓ SIM','codigo = "P-8"'],
         ['PILAR 3','✓ SIM','codigo = "PILAR 3"'],
         ['V5','✗ NÃO','— (é viga, não pilar)'],
         ['P','✗ NÃO','— (sem número)'],
        ], [28*mm, 26*mm, CW-54*mm], col_styles=['TCc','TC','TCc']))
    s.append(sp(2))
    s += cb([
        "for e in msp:",
        "    if e.dxftype() not in ('TEXT','MTEXT'): continue",
        "    txt   = e.dxf.text.strip() if e.dxftype()=='TEXT' else e.plain_text().strip()",
        "    x, y  = float(e.dxf.insert.x), float(e.dxf.insert.y)",
        "    layer = e.dxf.layer",
        "    if RE_PILAR.match(txt):",
        "        pilares_txt.append({'text': txt, 'x': x, 'y': y, 'layer': layer})",
    ], ec=ec)
    s.append(PageBreak())

    # ── 2. ASSOCIAÇÃO ───────────────────────────────────────────────────────
    s.append(sec('2', 'Associação Texto → Polígono (3 Raios)'))
    s.append(sp(2))
    s.append(note('Um texto "P17" sozinho NÃO é pilar. Precisa de LWPOLYLINE fechada próxima.', 'warn'))
    s.append(sp(2))
    img_path = fig_3raios_pilar()
    s += img(img_path, 148, 'Figura 1 — TextAssociator: 3 zonas de associação texto→polígono')
    s.append(sp(2))
    s += cb([
        "from shapely.geometry import Point, Polygon",
        "PILAR_SEARCH_RADIUS = 800.0  # mm",
        "TOUCH_DIST = 5.0             # mm",
        "",
        "def score_texto_poligono(txt_pt, poly_pts):",
        "    poly = Polygon(poly_pts); pt = Point(txt_pt)",
        "    dist = poly.exterior.distance(pt)",
        "    if poly.contains(pt):                return 1.0",
        "    elif dist <= TOUCH_DIST:             return 0.8",
        "    elif dist <= PILAR_SEARCH_RADIUS:",
        "        return max(0.0, 0.5*(1.0 - dist/PILAR_SEARCH_RADIUS))",
        "    return 0.0",
    ], ec=ec)
    s.append(PageBreak())

    # ── 3. SEÇÃO TRANSVERSAL ────────────────────────────────────────────────
    s.append(sec('3', 'Seção Transversal — Dimensões'))
    s.append(sp(2))
    img_path2 = fig_pilar_secao()
    s += img(img_path2, 148, 'Figura 2 — Pilar retangular (comprimento ≥ largura) e cambotado (bulge > 0.3)')
    s.append(sp(2))
    s += cb([
        "# Formatos aceitos:",
        "RE_DIM    = re.compile(r'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})')",
        "RE_DIM_BH = re.compile(r'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})', re.I)",
        "",
        "# Normalização: comprimento >= largura",
        "comp = max(a, b); larg = min(a, b)  # cm",
        "",
        "# Cambotado (arco na LWPOLYLINE):",
        "for pt in lwpoly.get_points('xyb'):  # x, y, bulge",
        "    if abs(pt[2]) > 0.3:",
        "        pilar_especial = True; tipo = 'CAMBOTADO'",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Caso','Condição','Ação'],
        [['Pilar retangular normal','bulge == 0','comprimento = max(a,b), largura = min(a,b)'],
         ['Pilar cambotado','bulge > 0.3','pilar_especial=True, tipo="CAMBOTADO", usar bbox'],
         ['Sem dimensão no raio','nenhum texto NNxMM em 600mm','comp=0, larg=0, confidence−=0.30'],
         ['Coordenadas UTM','x ou y > 50000','Ignorar — georreferenciamento, não fôrmas'],
        ], [34*mm, 46*mm, CW-80*mm]))
    s.append(PageBreak())

    # ── 4. LAYERS ───────────────────────────────────────────────────────────
    s.append(sec('4', 'Layers Canônicos'))
    s.append(sp(2))
    img_layers = fig_pilar_layers()
    s += img(img_layers, 148, 'Figura 3 — Estrutura de layers do pilar: o que cada um contém')
    s.append(sp(2))
    s.append(tbl(['Canônico','Aliases reais no DXF','Uso'],
        [['ELEMENT_LABEL','NOMENCLATURA, texto, "00 - FELIPE", EST-PILAR-TEXT','Textos ID (P17, V101, L5)'],
         ['PANEL_GEOMETRY','Painéis, PAINEIS, "Pain?is", PAINEL','LWPOLYLINE fechada — contorno'],
         ['WOOD_BATTEN','SARRAFO, "SARRAFO DE PRESSAO"','Sarrafos de madeira'],
         ['BATTEN_2x7','SARR_2.2x7, "Sarr 2.2x7"','Sarrafo 2,2×7cm (mais comum)'],
         ['BATTEN_7x7','SARR_7x7, SARR_7x10','Cantos de pilar'],
         ['ANCHOR_BAR_PL','"BARRA ANCORAGEM"','Barras (≠ LV: "BARRA DE ANCORAGEM")'],
         ['ELEVATION_MARK','NIVEL, "Nível", "N?vel"','Cota Z — TEXT/MTEXT'],
         ['SECTION_TEXT','"Texto Seção", "Texto de Titulo"','Textos "20x50", "b=20 h=50"'],
         ['TQS_COLUMN','S-COLS, "1", "2", "3"','Pilar família TQS'],
        ], [34*mm, CW-76*mm, 28*mm]))
    s.append(sp(2))
    s += cb([
        "import unicodedata",
        "def normalize_layer(name):",
        "    nfkd = unicodedata.normalize('NFKD', str(name))",
        "    return nfkd.encode('ascii','ignore').decode().upper().strip()",
        "",
        "# normalize_layer('Painéis') == normalize_layer('Pain?is') == 'PAINEIS'",
    ], ec=ec)
    s.append(PageBreak())

    # ── 5. SCHEMA JSON ──────────────────────────────────────────────────────
    s.append(sec('5', 'Schema JSON Completo — FichaFase3Pilar'))
    s.append(sp(2))
    s += cb([
        "{",
        '  "codigo":          "P17",         # str  — ID',
        '  "pavimento":       "1_PAVIMENTO",  # str  — nome do arquivo DXF',
        '  "obra_nome":       "ALIMONTI",     # str',
        '',
        '  "comprimento":     50.0,           # float cm — dimensão maior',
        '  "largura":         20.0,           # float cm — dimensão menor',
        '  "pilar_especial":  false,          # bool',
        '  "tipo_pilar_especial": "",         # "CAMBOTADO" | ""',
        '',
        '  "outline_segs": [                  # LWPOLYLINE em mm',
        '      {"x": 15000.0, "y": 10000.0},',
        '      {"x": 15200.0, "y": 10000.0},',
        '      {"x": 15200.0, "y": 10500.0},',
        '      {"x": 15000.0, "y": 10500.0}',
        '  ],',
        '',
        '  "nivel":          2.80,            # float m — cota Z',
        '  "armadura": {"tipo": "longitudinal", "diametro": 12.5, "espacamento": 15},',
        '  "vigas_ligadas":  ["V101","V102"],  # inferido por proximidade',
        '',
        '  "confidence":     0.85,',
        '  "revisado":       false',
        "}",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Campo','Tipo','Origem DXF'],
        [['codigo','str','TEXT/MTEXT layer NOMENCLATURA → RE_PILAR'],
         ['comprimento','float','RE_DIM/RE_DIM_BH mais próximo ≤ 600mm → max(a,b)'],
         ['largura','float','idem → min(a,b)'],
         ['outline_segs','list','LWPOLYLINE closed=True layer Painéis'],
         ['pilar_especial','bool','bulge > 0.3 em qualquer vértice'],
         ['nivel','float','TEXT layer NIVEL → RE_NIVEL → valor em metros'],
         ['confidence','float','calcular_confidence(raio, dim, id, contorno)'],
        ], [30*mm, 20*mm, CW-50*mm]))
    s.append(PageBreak())

    # ── 6. CONFIDENCE ───────────────────────────────────────────────────────
    s.append(sec('6', 'Confidence e Fallbacks'))
    s.append(sp(2))
    img_conf = fig_pilar_confidence()
    s += img(img_conf, 148, 'Figura 4 — Composição do score de confidence e thresholds')
    s.append(sp(2))
    s += cb([
        "def calcular_confidence(raio_score, tem_dimensao, tem_texto_id, tem_contorno):",
        "    conf = raio_score",
        "    if not tem_dimensao:  conf -= 0.30",
        "    if not tem_texto_id:  conf -= 0.40  # penalidade severa",
        "    if not tem_contorno:  conf -= 0.20",
        "    return max(0.0, min(conf, 1.0))",
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('Cadeia de Fallbacks'))
    s.append(tbl(['Nível','Condição','Confidence'],
        [['1','Texto em NOMENCLATURA → LWPOLYLINE em Painéis','raio_score'],
         ['2','Texto em TEXTO_GERAL → mesma LWPOLYLINE','raio_score − 0.05'],
         ['3','Texto em qualquer layer → LWPOLYLINE qualquer','raio_score − 0.15'],
         ['4','Texto RE_PILAR sem LWPOLYLINE próxima','raio_score − 0.40'],
         ['5','Nenhum texto RE_PILAR','NÃO REGISTRAR'],
        ], [10*mm, CW-52*mm, 30*mm]))
    s.append(PageBreak())

    # ── 7. MATRIZ DE DECISÃO ────────────────────────────────────────────────
    s.append(sec('7', 'Matriz de Decisão'))
    s.append(sp(2))
    s.append(tbl(['Situação','Ação','Confidence','Log'],
        [['Texto dentro do polígono','Auto-assign','1.0','—'],
         ['Texto tocando (dist ≤ 5mm)','Auto-assign','0.8','—'],
         ['Texto próximo (≤ 800mm)','Score decaimento','0.0–0.5','avisar se < 0.50'],
         ['Texto fora do raio (> 800mm)','Ignorar','0.0','—'],
         ['2 textos competindo','Vence score maior','vencedor','log ambos'],
         ['Empate exato de score','Revisão humana','score','log "EMPATE"'],
         ['ID sem dimensão próxima','Registrar sem dim','conf−0.30','"dim não encontrada"'],
         ['Layer desconhecido','Processar mesmo assim','conf−0.10','"layer UNKNOWN"'],
         ['Encoding "Pain?is"','normalize_layer()','sem penalidade','—'],
        ], [52*mm, 36*mm, 26*mm, CW-114*mm]))
    s.append(PageBreak())

    # ── 8. EXEMPLOS REAIS ───────────────────────────────────────────────────
    s.append(sec('8', 'Exemplos Reais — Obra ALIMONTI-PARAISO'))
    s.append(sp(2))
    s.append(h2('Exemplo A — P17 (texto dentro do polígono → confidence = 1.0)'))
    s += cb([
        "# DXF:",
        "TEXT  layer='NOMENCLATURA'  text='P17'   insert=(15100,10250)",
        "TEXT  layer='NOMENCLATURA'  text='20x50' insert=(15050,10350)",
        "LWPOLYLINE layer='Paineis'  closed=True",
        "  vertices=[(15000,10000),(15200,10000),(15200,10500),(15000,10500)]",
        "",
        "# Cálculo:",
        "# texto P17 está DENTRO do polígono → raio_score = 1.0",
        "# tem_dimensao=True, tem_contorno=True → penalidades = 0",
        "# confidence = 1.0 → AUTO-ASSIGN",
        "",
        '# JSON: {"codigo":"P17","comprimento":50.0,"largura":20.0,"confidence":1.0}',
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo B — P5 (texto distante → rejeitado)'))
    s += cb([
        "# Texto P5 a 315mm do polígono mais próximo, sem dimensão próxima:",
        "# raio_score = 0.5 * (1 - 315/800) = 0.304",
        "# tem_dimensao=False → conf -= 0.30 → conf = 0.004",
        "# 0.004 < 0.30 → REJEITAR — não gravar no banco",
        '# Log: {"elemento_id":"P5","confidence":0.004,"motivo":"texto distante+sem dim"}',
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo C — PC-1 cambotado'))
    s += cb([
        "# LWPOLYLINE com bulge = 0.414 em um vértice → cambotado",
        '# {"codigo":"PC-1","pilar_especial":true,"tipo_pilar_especial":"CAMBOTADO",',
        '#  "comprimento":40.0,"largura":40.0,"confidence":0.85}',
    ], ec=ec)
    s.append(PageBreak())

    # ── 9. PIPELINE ─────────────────────────────────────────────────────────
    s.append(sec('9', 'Pipeline Completo'))
    s.append(sp(2))
    img_pipe = fig_pipeline_pilares()
    s += img(img_pipe, 148, 'Figura 5 — Fluxo completo de extração de pilares (11 passos)')

    return s


# ════════════════════════════════════════════════════════════════════════════
# CONTEÚDO — VIGAS
# ════════════════════════════════════════════════════════════════════════════
def build_vigas():
    ec = BLUE; bg = BLUE_BG
    def sec(n, t): return SH(n, t, ec, bg)

    s = []

    # ── CAPA ────────────────────────────────────────────────────────────────
    s += [
        sp(12), p('CAD-ANALYZER', 'Capa'), p('Fichas de Extração — VIGAS', 'CapaSub'),
        sp(2), note('Esta ficha responde: dado um texto/linha do DXF, qual campo JSON extrair e como.', 'info'),
        sp(3), hr(ec), sp(2),
    ]
    s.append(tbl(['#','Seção','Conteúdo'],
        [['1','Identificação','RE_VIGA · padrões · balanço BA*/VB*'],
         ['2','Geometria LV vs FV','LINE entities · diagrama corte + planta'],
         ['3','Balanço','BA*/VB* → apoio_fim="" + diagrama'],
         ['4','Dimensões b/h','RE_DIM · RE_DIM_BH · convenção b menor que h'],
         ['5','Schema JSON Completo','FichaFase3Viga · tramos · apoios'],
         ['6','Layers Canônicos','fundo · Escoras · GARFOS · aliases'],
         ['7','Confidence e Fallbacks','fórmula · cadeia de 6 níveis'],
         ['8','Matriz de Decisão','balanço · sem dimensão · layer desconhecido'],
         ['9','Exemplos Reais','V101 · BA-5 (balanço)'],
         ['10','Pipeline Completo','fluxo E2E · checklist 12 passos'],
        ], [12*mm, 50*mm, CW-62*mm]))
    s.append(PageBreak())

    # ── 1. IDENTIFICAÇÃO ────────────────────────────────────────────────────
    s.append(sec('1', 'Identificação — RE_VIGA'))
    s.append(sp(2))
    s += cb([
        "RE_VIGA = re.compile(",
        "    r'^(V|BA|VB|VT|VC)\\.?-?\\d+([A-Z]|\\./\\d+)?',",
        "    re.IGNORECASE",
        ")",
        "# V=normal  BA*=balanço  VB*=borda  VT*=topo  VC*=coroamento",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Texto DXF','Casou?','Tipo','Obs'],
        [['V101','✓','Normal','2 apoios esperados'],
         ['V101A','✓','Normal','Sufixo letra'],
         ['BA-5','✓','Balanço','apoio_fim="" é CORRETO'],
         ['VB3','✓','Borda balanço','apoio_fim="" é CORRETO'],
         ['VT-2','✓','Topo','Travamento'],
         ['VC1','✓','Coroamento','—'],
         ['L5','✗','—','É laje'],
         ['P3','✗','—','É pilar'],
        ], [24*mm, 20*mm, 28*mm, CW-72*mm], col_styles=['TCc','TC','TC','TC']))
    s.append(PageBreak())

    # ── 2. GEOMETRIA LV vs FV ───────────────────────────────────────────────
    s.append(sec('2', 'Geometria — LV (lateral) vs FV (fundo)'))
    s.append(sp(2))
    s.append(note('LV = painéis laterais (layer Painéis). FV = prancha de fundo (layer fundo). Distinção CRÍTICA para cálculo de material.', 'warn'))
    s.append(sp(2))
    img_lv = fig_viga_lv_fv()
    s += img(img_lv, 148, 'Figura 1 — Corte transversal da viga (LV/FV/Escoras) e vista superior com apoios')
    s.append(sp(2))
    s += cb([
        "# Acesso às LINEs de fundo (FV):",
        "for e in msp.query('LINE'):",
        "    if normalize_layer(e.dxf.layer) not in ('FUNDO','FUNDOS'): continue",
        "    start = (float(e.dxf.start.x), float(e.dxf.start.y))",
        "    end   = (float(e.dxf.end.x),   float(e.dxf.end.y))",
        "    comp_cm = math.hypot(end[0]-start[0], end[1]-start[1]) / 10",
        "    fv_candidates.append({'start':start,'end':end,'comp':comp_cm})",
    ], ec=ec)
    s.append(PageBreak())

    # ── 3. BALANÇO ──────────────────────────────────────────────────────────
    s.append(sec('3', 'Viga em Balanço — BA* e VB*'))
    s.append(sp(2))
    img_bal = fig_viga_balanco()
    s += img(img_bal, 148, 'Figura 2 — Viga normal (2 apoios) vs viga em balanço BA*/VB* (1 apoio, apoio_fim="")')
    s.append(sp(2))
    s.append(note('BA* ou VB* com apoio_fim="" NÃO é erro. É o comportamento correto e esperado.', 'ok'))
    s.append(sp(2))
    s += cb([
        "# Lógica de detecção:",
        "is_balanco = bool(re.match(r'^(BA|VB)', codigo, re.I))",
        "",
        "tramo = {",
        "    'apoio_ini': 'P8',   # sempre preenchido",
        "    'apoio_fim': '',     # '' se é balanço — CORRETO",
        "    'comprimento': 220.0",
        "}",
        "# is_balanco=True → NÃO penalizar confidence por apoio_fim vazio",
    ], ec=ec)
    s.append(PageBreak())

    # ── 4. DIMENSÕES ────────────────────────────────────────────────────────
    s.append(sec('4', 'Dimensões b e h'))
    s.append(sp(2))
    s += cb([
        "RE_DIM    = re.compile(r'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})')",
        "RE_DIM_BH = re.compile(r'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})', re.I)",
        "",
        "# CONVENÇÃO: b (largura) < h (altura)",
        "largura = min(a, b)  # cm — b",
        "altura  = max(a, b)  # cm — h",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Texto DXF','largura b','altura h','Obs'],
        [['"20x50"','20 cm','50 cm','b < h ✓'],
         ['"50x20"','20 cm','50 cm','Reordenado: b=min, h=max'],
         ['"b=20 h=50"','20 cm','50 cm','RE_DIM_BH'],
        ], [30*mm, 26*mm, 26*mm, CW-82*mm], col_styles=['TCc','TCc','TCc','TC']))
    s.append(sp(2))
    s.append(note('Sem dimensão em VIGA_SEARCH_RADIUS=1200mm: largura=0, altura=0, confidence −= 0.30', 'warn'))
    s.append(PageBreak())

    # ── 5. SCHEMA JSON ──────────────────────────────────────────────────────
    s.append(sec('5', 'Schema JSON Completo — FichaFase3Viga'))
    s.append(sp(2))
    s += cb([
        "{",
        '  "codigo":    "V101",',
        '  "pavimento": "1_PAVIMENTO",  "obra_nome": "ALIMONTI",',
        '',
        '  "largura":   20.0,           # cm — b',
        '  "altura":    50.0,           # cm — h',
        '',
        '  "tramos": [{',
        '      "apoio_ini": "P5",       # pilar inicial (extremidade start)',
        '      "apoio_fim": "P6",       # pilar final  ("" se BA*/VB*)',
        '      "comprimento": 450.0,    # cm',
        '      "nivel": 2.80            # m',
        '  }],',
        '',
        '  "fv_segs": [{"start":[15000,10000],"end":[19500,10000]}],',
        '',
        '  "escoras":  12,              # COUNT LINEs layer Escoras',
        '  "garfos":    6,              # COUNT INSERTs layer GARFOS',
        '',
        '  "confidence": 0.90,  "revisado": false',
        "}",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Campo','Origem DXF'],
        [['codigo','TEXT/MTEXT → RE_VIGA'],
         ['largura / altura','RE_DIM/RE_DIM_BH ≤ 1200mm → b=min, h=max'],
         ['tramos.apoio_ini/fim','Extremidades da LINE de fundo → pilar mais próximo ≤ 1200mm'],
         ['tramos.comprimento','math.hypot(end − start) em mm → / 10 para cm'],
         ['fv_segs','LINE layer fundo: start + end em mm (coordenadas DXF)'],
         ['escoras','COUNT(LINE layer Escoras) próximas à viga'],
         ['garfos','COUNT(INSERT layer GARFOS) próximos à viga'],
        ], [32*mm, CW-32*mm]))
    s.append(PageBreak())

    # ── 6. LAYERS ───────────────────────────────────────────────────────────
    s.append(sec('6', 'Layers Canônicos — Viga'))
    s.append(sp(2))
    s.append(tbl(['Canônico','Aliases reais','Entidade','Uso'],
        [['BEAM_BOTTOM','fundo, FUNDOS, "Fundo da Viga"','LINE/LWPOLY','FV — comprimento da viga'],
         ['SHORING','Escoras, "Escora de Viga"','LINE/INSERT','Apoio vertical'],
         ['FORK_METAL','GARFOS','INSERT/LINE','Garfos HT20CT'],
         ['CLAMP_METAL','presilha, Presilha, PRESILHA','LWPOLY/LINE','Presilhas metálicas'],
         ['ANCHOR_BAR_LV','"BARRA DE ANCORAGEM"','LINE','Barras (≠ PL: "BARRA ANCORAGEM")'],
         ['SPACER','Forcador','INSERT/LINE','Espaçadores'],
         ['BATTEN_BEAM','barrote','LINE/LWPOLY','Barrotes da viga'],
         ['ELEMENT_LABEL','NOMENCLATURA, texto','TEXT/MTEXT','Textos ID (V101)'],
        ], [34*mm, CW-108*mm, 26*mm, 34*mm]))
    s.append(PageBreak())

    # ── 7. CONFIDENCE ───────────────────────────────────────────────────────
    s.append(sec('7', 'Confidence e Fallbacks'))
    s.append(sp(2))
    s.append(tbl(['Nível','Condição','Confidence'],
        [['1','Texto em NOMENCLATURA → LINE em fundo/Painéis ≤ 1200mm','raio_score'],
         ['2','Texto → LINE em qualquer layer (não fundo/Painéis)','raio_score − 0.15'],
         ['3','Texto + RE_DIM → dimensões extraídas','+0 (esperado)'],
         ['4','Texto + RE_DIM_BH (b=20 h=50)','+0 (aceito)'],
         ['5','Texto sem dimensão ≤ 1200mm','conf − 0.30'],
         ['6','BA*/VB* com apoio_fim=""','OK — balanço não penaliza'],
        ], [10*mm, CW-50*mm, 36*mm]))
    s.append(PageBreak())

    # ── 8. MATRIZ DE DECISÃO ────────────────────────────────────────────────
    s.append(sec('8', 'Matriz de Decisão'))
    s.append(sp(2))
    s.append(tbl(['Situação','Ação','Confidence'],
        [['Viga BA*/VB* (balanço)','apoio_fim="" — correto','sem penalidade'],
         ['apoio_ini="" (não é balanço)','Alerta: viga sem apoio inicial','conf − 0.20'],
         ['comprimento > 1500cm','Alerta: revisar','log "comprimento suspeito"'],
         ['Largura menor que altura','OK — convenção b menor que h','sem penalidade'],
         ['Nenhuma LINE de fundo próxima','fv_segs=[], comprimento estimado','conf − 0.25'],
         ['2 LINEs competindo','Vence a mais próxima ao texto','log ambas'],
        ], [52*mm, CW-102*mm, 34*mm]))
    s.append(PageBreak())

    # ── 9. EXEMPLOS REAIS ───────────────────────────────────────────────────
    s.append(sec('9', 'Exemplos Reais — Obra ALIMONTI-PARAISO'))
    s.append(sp(2))
    s.append(h2('Exemplo A — V101'))
    s += cb([
        "# DXF:",
        "TEXT  layer='NOMENCLATURA'  text='V101'  insert=(17000,10000)",
        "TEXT  layer='NOMENCLATURA'  text='20x50' insert=(17100,10050)",
        "LINE  layer='fundo'  start=(15000,10000)  end=(19500,10000)",
        "",
        '# JSON: {"codigo":"V101","largura":20.0,"altura":50.0,',
        '#   "tramos":[{"apoio_ini":"P5","apoio_fim":"P6","comprimento":450.0}],',
        '#   "fv_segs":[{"start":[15000,10000],"end":[19500,10000]}],',
        '#   "confidence":0.90}',
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo B — BA-5 (viga em balanço)'))
    s += cb([
        "# BA* → apoio_fim='' é CORRETO (sem penalidade de confidence)",
        '# {"codigo":"BA-5","tramos":[{"apoio_ini":"P8","apoio_fim":"",',
        '#   "comprimento":220.0}],"confidence":0.88}',
    ], ec=ec)
    s.append(PageBreak())

    # ── 10. PIPELINE ────────────────────────────────────────────────────────
    s.append(sec('10', 'Pipeline Completo — Extração de Vigas'))
    s.append(sp(2))
    passos = [
        ('1','Carregar DXF','ezdxf.readfile(path) → msp'),
        ('2','normalize_layer()','NFKD → ASCII → UPPER'),
        ('3','Coletar textos RE_VIGA','TEXT/MTEXT → filtrar → lista vigas_txt'),
        ('4','Coletar LINEs de fundo','layer FUNDO/FUNDOS → lista fv_lines'),
        ('5','Associar texto→LINE','TextAssociator: raio 1200mm → score → par'),
        ('6','Extrair b/h','RE_DIM/RE_DIM_BH em 1200mm → b=min, h=max'),
        ('7','Associar apoios','Extremidades da LINE → pilares_dict → apoio_ini/fim'),
        ('8','Detectar balanço','BA*/VB* → apoio_fim="" é correto'),
        ('9','Contar escoras/garfos','COUNT LINEs Escoras + INSERTs GARFOS'),
        ('10','Calcular confidence','raio_score − penalidades → threshold'),
        ('11','Salvar JSON','FichaFase3Viga → JSON por obra/pavimento'),
    ]
    s.append(tbl(['Passo','Ação','Detalhe'], passos, [14*mm, 40*mm, CW-54*mm]))

    return s


# ════════════════════════════════════════════════════════════════════════════
# CONTEÚDO — LAJES
# ════════════════════════════════════════════════════════════════════════════
def build_lajes():
    ec = GREEN; bg = GREEN_BG
    def sec(n, t): return SH(n, t, ec, bg)

    s = []

    # ── CAPA ────────────────────────────────────────────────────────────────
    s += [
        sp(12), p('CAD-ANALYZER', 'Capa'), p('Fichas de Extração — LAJES', 'CapaSub'),
        sp(2), note('Esta ficha responde: dado um texto/polígono do DXF, qual campo JSON extrair e como.', 'info'),
        sp(3), hr(ec), sp(2),
    ]
    s.append(tbl(['#','Seção','Conteúdo'],
        [['1','Identificação','RE_LAJE · RE_LAJE_H · caminhos A e B'],
         ['2','Contorno e Área','LWPOLYLINE · fórmula Shoelace + diagrama anatômico'],
         ['3','Espessura h=','extrair h= · range 7–40cm · casos especiais'],
         ['4','Laje Sintética','clusters h= + diagrama · CLUSTER_RADIUS=500mm'],
         ['5','Schema JSON Completo','FichaFase3Laje · todos os campos'],
         ['6','Layers Canônicos','EST-LAJE-TEXT·Painéis·Vázio·encoding CP1252'],
         ['7','Confidence','fórmula + diagrama · thresholds'],
         ['8','Aberturas e Recortes','layer Vázio · is_void_layer() · Pilares'],
         ['9','Exemplos Reais','L5 (1.0) · synth_0 (0.50) · L3 abertura'],
         ['10','Pipeline Completo','fluxo E2E · checklist 10 passos'],
        ], [12*mm, 50*mm, CW-62*mm]))
    s.append(PageBreak())

    # ── 1. IDENTIFICAÇÃO ────────────────────────────────────────────────────
    s.append(sec('1', 'Identificação — RE_LAJE e RE_LAJE_H'))
    s.append(sp(2))
    s += cb([
        "# Caminho A — ID explícito",
        "RE_LAJE = re.compile(",
        "    r'^(L\\d+[A-Za-z]?|Y\\d+[A-Za-z]?|X\\d+[A-Za-z]?'",
        "    r'|LAJ[-_]?\\d+|LAJE[-_\\s]*\\d+)$',",
        "    re.IGNORECASE",
        ")",
        "",
        "# Caminho B — espessura h= (sem ID explícito)",
        "RE_LAJE_H = re.compile(r'h\\s*[=:]\\s*([\\d,.]+)', re.IGNORECASE)",
        "# Ex: 'h=12' 'h = 14' 'h:10' → espessura em cm",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Texto DXF','RE_LAJE?','RE_LAJE_H?','Resultado'],
        [['L5','✓','—','codigo="L5"'],
         ['L12A','✓','—','codigo="L12A"'],
         ['Y1','✓','—','codigo="Y1"'],
         ['LAJE 1','✓','—','codigo="LAJE 1"'],
         ['h=12','—','✓','espessura=12.0cm'],
         ['L5 h=12','✓','✓','codigo="L5", espessura=12.0cm'],
         ['L','✗','—','sem número — não casa'],
        ], [26*mm, 22*mm, 26*mm, CW-74*mm], col_styles=['TCc','TC','TC','TC']))
    s.append(PageBreak())

    # ── 2. CONTORNO E ÁREA ──────────────────────────────────────────────────
    s.append(sec('2', 'Contorno e Área — LWPOLYLINE'))
    s.append(sp(2))
    img_laje = fig_laje_contorno()
    s += img(img_laje, 148, 'Figura 1 — Anatomia completa da laje: contorno, ID, h=, abertura, recorte pilar, vigas')
    s.append(sp(2))
    s += cb([
        "LAJE_SEARCH_RADIUS = 1500.0  # mm",
        "",
        "for e in msp.query('LWPOLYLINE'):",
        "    pts = [(float(p[0]),float(p[1])) for p in e.get_points('xy')]",
        "    is_closed = (getattr(e.dxf,'flags',0) & 1 == 1) or e.is_closed",
        "    if is_closed and len(pts) >= 3:",
        "        area = Polygon(pts).area",
        "        if area > 50_000:   # mm² → provável LAJE",
        "            laje_polys.append({'pts':pts,'layer':e.dxf.layer})",
        "        elif area < 5_000:  # mm² → provável PILAR",
        "            pilar_polys.append({'pts':pts,'layer':e.dxf.layer})",
        "",
        "# Fórmula Shoelace (área sem shapely):",
        "def area_shoelace(pts):",
        "    n=len(pts); area=0.0",
        "    for i in range(n):",
        "        j=(i+1)%n",
        "        area += pts[i][0]*pts[j][1] - pts[j][0]*pts[i][1]",
        "    return abs(area)/2.0",
    ], ec=ec)
    s.append(PageBreak())

    # ── 3. ESPESSURA ────────────────────────────────────────────────────────
    s.append(sec('3', 'Espessura — Extração de h='))
    s.append(sp(2))
    s += cb([
        "def extrair_espessura(textos_h, laje_pos, raio=1500.0):",
        "    lx, ly = laje_pos; candidatos = []",
        "    for t in textos_h:",
        "        m = RE_LAJE_H.search(t['text'])",
        "        if not m: continue",
        "        dist = math.hypot(t['x']-lx, t['y']-ly)",
        "        if dist <= raio:",
        "            val = float(m.group(1).replace(',','.'))",
        "            candidatos.append((val, dist))",
        "    if candidatos:",
        "        candidatos.sort(key=lambda x: x[1])  # mais próximo",
        "        return candidatos[0][0]",
        "    return 0.0",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(['Valor','Válido?','Ação'],
        [['h=12','SIM (7–40cm)','espessura=12.0'],
         ['h=5','NÃO (< 7cm)','confidence −= 0.30, log "espessura inválida (norma)"'],
         ['h=45','NÃO (> 40cm)','confidence −= 0.30, log "espessura fora do range"'],
         ['ausente','—','espessura=0.0, confidence −= 0.30'],
         ['2 valores conflitantes','—','usar o mais próximo ao centróide da laje'],
        ], [24*mm, 28*mm, CW-52*mm]))
    s.append(PageBreak())

    # ── 4. LAJE SINTÉTICA ───────────────────────────────────────────────────
    s.append(sec('4', 'Laje Sintética — Clusters de h='))
    s.append(sp(2))
    img_sint = fig_laje_sintetica()
    s += img(img_sint, 148, 'Figura 2 — Múltiplos textos h= dentro de CLUSTER_RADIUS → uma laje SYNTHETIC por cluster')
    s.append(sp(2))
    s += cb([
        "CLUSTER_RADIUS = 500.0  # mm",
        "",
        "def gerar_lajes_sinteticas(laje_dims):",
        "    used=set(); clusters=[]",
        "    for i,d in enumerate(laje_dims):",
        "        if i in used: continue",
        "        cluster=[d]; used.add(i)",
        "        for j,d2 in enumerate(laje_dims):",
        "            if j in used: continue",
        "            if math.hypot(d['x']-d2['x'],d['y']-d2['y']) < CLUSTER_RADIUS:",
        "                cluster.append(d2); used.add(j)",
        "        clusters.append(cluster)",
        "    result=[]",
        "    for idx,cluster in enumerate(clusters):",
        "        cx=sum(d['x'] for d in cluster)/len(cluster)",
        "        cy=sum(d['y'] for d in cluster)/len(cluster)",
        "        result.append({'id':f'synth_{idx}','name':'SYNTHETIC',",
        "            'x':cx,'y':cy,'espessura':cluster[0]['h_val'],",
        "            'confidence':0.50})",
        "    return result",
    ], ec=ec)
    s.append(PageBreak())

    # ── 5. SCHEMA JSON ──────────────────────────────────────────────────────
    s.append(sec('5', 'Schema JSON Completo — FichaFase3Laje'))
    s.append(sp(2))
    s += cb([
        "{",
        '  "codigo":    "L5",              # str — ID ("synth_0" se sintética)',
        '  "pavimento": "1_PAVIMENTO",     "obra_nome": "ALIMONTI",',
        '',
        '  "tipo":      "macica",          # "macica"|"pre_moldada"|"steel_deck"',
        '  "espessura": 12.0,              # float cm — de h=NN',
        '',
        '  "dimensoes": {',
        '      "comprimento": 620.0,       # cm — bbox do contorno',
        '      "largura":     430.0,       # cm — bbox do contorno',
        '      "espessura":   12.0',
        '  },',
        '',
        '  "outline_segs": [               # vértices em mm',
        '      {"x":15000.0,"y":10000.0}, {"x":21200.0,"y":10000.0},',
        '      {"x":21200.0,"y":14300.0}, {"x":15000.0,"y":14300.0}',
        '  ],',
        '',
        '  "aberturas": [{"pontos":[[5800,5900],[5900,5900],[5900,6100],[5800,6100]],',
        '                 "area":20000.0}],',
        '',
        '  "vigas_around":   ["V101","V102","V103"],',
        '  "pilares_around": ["P5","P6","P7","P8"],',
        '',
        '  "nivel": 2.80,  "confidence": 0.70,  "revisado": false',
        "}",
    ], ec=ec)
    s.append(PageBreak())

    # ── 6. LAYERS ───────────────────────────────────────────────────────────
    s.append(sec('6', 'Layers Canônicos — Laje'))
    s.append(sp(2))
    s.append(note('ENCODING CRÍTICO: "Vázio" pode chegar como "V?zio" em DXF CP1252. Sempre use is_void_layer().', 'err'))
    s.append(sp(2))
    s.append(tbl(['Canônico','Aliases reais','Uso'],
        [['SLAB_TEXT','EST-LAJE-TEXT, NOMENCLATURA, EST-TEXT','IDs de lajes (L1, L2…)'],
         ['PANEL_GEOMETRY','Painéis, PAINEIS, "Pain?is"','Contorno da laje — LWPOLY'],
         ['PILLAR_CUTOUT','Pilares, EST-PILAR, EST-PILAR-CUT','Recortes de pilares no contorno'],
         ['BEAM_INTERFACE_LJ','VIGAS, EST-VIGA','Interface vigas na laje'],
         ['VOID_OPENING','Vázio, Vazio, "V?zio", ABERTURA, VOID','Aberturas — encoding crítico!'],
         ['REUSE_STATUS','REAPROVEITAMENTO','BOM/REGULAR/RUIM/DESCARTE'],
        ], [34*mm, CW-80*mm, 32*mm]))
    s.append(sp(2))
    s += cb([
        "VOID_ALIASES = {'vazio','vazios','abertura','aberturas','buraco','void'}",
        "",
        "def is_void_layer(layer):",
        "    import unicodedata",
        "    n = unicodedata.normalize('NFKD',layer).encode('ascii','ignore').decode().lower()",
        "    return n in VOID_ALIASES or 'vaz' in n",
    ], ec=ec)
    s.append(PageBreak())

    # ── 7. CONFIDENCE ───────────────────────────────────────────────────────
    s.append(sec('7', 'Confidence'))
    s.append(sp(2))
    img_conf = fig_laje_confidence()
    s += img(img_conf, 148, 'Figura 3 — Composição do score de confidence para lajes')
    s.append(sp(2))
    s += cb([
        "def calcular_confidence_laje(laje):",
        "    conf = 0.30                                     # base",
        "    if laje.get('espessura',0) > 0:    conf += 0.30",
        "    if len(laje.get('outline_segs',[])) >= 3: conf += 0.20",
        "    if laje.get('vigas_around'):        conf += 0.20",
        "    return min(conf, 1.0)",
        "",
        "# Laje SYNTHETIC: sempre 0.50 (espessura ok, contorno incerto)",
    ], ec=ec)
    s.append(PageBreak())

    # ── 8. ABERTURAS ────────────────────────────────────────────────────────
    s.append(sec('8', 'Aberturas e Recortes de Pilares'))
    s.append(sp(2))
    s += cb([
        "def detectar_aberturas(laje_contorno, polylines):",
        "    laje_poly = Polygon(laje_contorno)",
        "    aberturas = []",
        "    for poly in polylines:",
        "        if not poly['closed']: continue",
        "        if not is_void_layer(poly['layer']): continue",
        "        ab_poly = Polygon(poly['points'])",
        "        if laje_poly.intersects(ab_poly):",
        "            aberturas.append({'pontos':poly['points'],'area':ab_poly.area})",
        "    return aberturas",
        "",
        "def detectar_recortes_pilares(laje_contorno, polylines):",
        "    laje_poly = Polygon(laje_contorno); recortes=[]",
        "    for poly in polylines:",
        "        if not poly['closed']: continue",
        "        ln = normalize_layer(poly['layer'])",
        "        if ln not in ('PILARES','EST-PILAR-CUT','PILLAR-CUT'): continue",
        "        if laje_poly.intersects(Polygon(poly['points'])):",
        "            recortes.append({'pontos':poly['points'],'area':Polygon(poly['points']).area})",
        "    return recortes",
    ], ec=ec)
    s.append(PageBreak())

    # ── 9. EXEMPLOS REAIS ───────────────────────────────────────────────────
    s.append(sec('9', 'Exemplos Reais — Obra ALIMONTI-PARAISO'))
    s.append(sp(2))
    s.append(h2('Exemplo A — L5 (confidence = 1.0)'))
    s += cb([
        "TEXT  layer='EST-LAJE-TEXT'  text='L5'    insert=(18000,12000)",
        "TEXT  layer='COTA'           text='h=12'  insert=(18100,11900)",
        "LWPOLY layer='Paineis' closed=True",
        "  vertices=[(15000,10000),(21200,10000),(21200,14300),(15000,14300)]",
        "",
        '# JSON: {"codigo":"L5","espessura":12.0,',
        '#   "dimensoes":{"comprimento":620.0,"largura":430.0,"espessura":12.0},',
        '#   "confidence":1.0}',
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('Exemplo B — synth_0 (laje sintética, confidence = 0.50)'))
    s += cb([
        "# 3 textos h=10 dentro de 300mm → 1 cluster → synth_0",
        '# {"codigo":"synth_0","espessura":10.0,"outline_segs":[],"confidence":0.50}',
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('Exemplo C — L3 com abertura'))
    s += cb([
        "TEXT   layer='EST-LAJE-TEXT' text='L3'   insert=(6000,6000)",
        "LWPOLY layer='Vazio' closed=True",
        "  vertices=[(5800,5900),(5900,5900),(5900,6100),(5800,6100)]",
        "",
        '# JSON: {"codigo":"L3","aberturas":[{"area":20000.0,...}],"confidence":0.80}',
    ], ec=ec)
    s.append(PageBreak())

    # ── 10. PIPELINE ────────────────────────────────────────────────────────
    s.append(sec('10', 'Pipeline Completo — Extração de Lajes'))
    s.append(sp(2))
    passos = [
        ('1','Carregar DXF','ezdxf.readfile(path) → msp'),
        ('2','normalize_layer()','NFKD → ASCII → UPPER'),
        ('3','Coletar textos RE_LAJE','TEXT/MTEXT → filtrar → lajes_txt'),
        ('4','Coletar textos RE_LAJE_H','Todos h=NN → laje_dims'),
        ('5','Coletar LWPOLYLINE','closed=True, area > 50000mm² → laje_polys'),
        ('6','Associar texto→poly','TextAssociator: raio 1500mm → score'),
        ('7','Extrair espessura h=','extrair_espessura() → mais próximo ao centróide'),
        ('8','Gerar sintéticas','gerar_lajes_sinteticas() se clusters de h='),
        ('9','Detectar aberturas','is_void_layer() + intersects(laje_poly)'),
        ('10','Calcular confidence','calcular_confidence_laje() → thresholds'),
    ]
    s.append(tbl(['Passo','Ação','Detalhe'], passos, [14*mm, 42*mm, CW-56*mm]))

    return s


# ════════════════════════════════════════════════════════════════════════════
# GERAR PDFs
# ════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('CAD-ANALYZER — Fichas v5 (ReportLab + diagramas instrutivos)')
    print('Gerando diagramas...')

    tasks = [
        ('fichas_pilares_instrutivas.pdf', 'PILARES', ORANGE, build_pilares),
        ('fichas_vigas_instrutivas.pdf',   'VIGAS',   BLUE,   build_vigas),
        ('fichas_lajes_instrutivas.pdf',   'LAJES',   GREEN,  build_lajes),
    ]

    for fname, elem, ec, builder in tasks:
        print(f'  Montando {elem}...')
        path = OUT / fname
        doc  = make_doc(path, elem, ec)
        story = builder()
        doc.build(story)
        kb = path.stat().st_size // 1024
        print(f'  [OK] {fname}: {kb} KB')

    print('\nConcluido:')
    for fname, *_ in tasks:
        path = OUT / fname
        print(f'  {path}: {path.stat().st_size // 1024} KB')
