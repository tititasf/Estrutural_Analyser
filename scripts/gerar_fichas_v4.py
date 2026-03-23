#!/usr/bin/env python3
"""Fichas Instrutivas v4 — CAD-ANALYZER | ReportLab (PDF real, tipografia profissional)"""
import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Preformatted
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus.flowables import Flowable

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUT = Path('D:/Agente-cad-PYSIDE/docs/fichas')
OUT.mkdir(parents=True, exist_ok=True)

# ── PALETA ──────────────────────────────────────────────────────────────────
NAVY    = HexColor('#0d1b2e')
GRAY1   = HexColor('#f5f6f8')
GRAY2   = HexColor('#edf0f4')
BORDER  = HexColor('#ced4da')
TEXT    = HexColor('#1a1a2e')
TEXT2   = HexColor('#6b7280')
CODE_FG = HexColor('#1e3a5f')

ORANGE    = HexColor('#c94f00'); ORANGE_BG = HexColor('#fff4ee'); ORANGE_L = HexColor('#ffdcc8')
BLUE      = HexColor('#005fb8'); BLUE_BG   = HexColor('#eef4ff'); BLUE_L   = HexColor('#c0d8ff')
GREEN     = HexColor('#006b3f'); GREEN_BG  = HexColor('#edfff5'); GREEN_L  = HexColor('#b3f0d6')

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
    add('Capa',   fontName='Helvetica-Bold', fontSize=26, textColor=NAVY,
        alignment=TA_CENTER, spaceAfter=4*mm)
    add('CapaSub',fontName='Helvetica',      fontSize=12, textColor=TEXT2,
        alignment=TA_CENTER, spaceAfter=2*mm)
    add('T1',     fontName='Helvetica-Bold', fontSize=14, textColor=NAVY,
        spaceBefore=5*mm, spaceAfter=2*mm)
    add('T2',     fontName='Helvetica-Bold', fontSize=11, textColor=TEXT,
        spaceBefore=4*mm, spaceAfter=1.5*mm)
    add('T3',     fontName='Helvetica-Bold', fontSize=9.5, textColor=TEXT,
        spaceBefore=3*mm, spaceAfter=1*mm)
    add('Body',   fontName='Helvetica',      fontSize=9,  textColor=TEXT,
        leading=14, spaceAfter=1.5*mm)
    add('Small',  fontName='Helvetica',      fontSize=8,  textColor=TEXT2, leading=12)
    add('Code',   fontName='Courier',        fontSize=8,  textColor=CODE_FG,
        leading=11, backColor=GRAY2)
    add('TH',     fontName='Helvetica-Bold', fontSize=8.5, textColor=white,
        alignment=TA_CENTER)
    add('TC',     fontName='Helvetica',      fontSize=8.5, textColor=TEXT, leading=12)
    add('TCc',    fontName='Courier',        fontSize=8,  textColor=HexColor('#1e3a5f'), leading=11)
    add('TCb',    fontName='Helvetica-Bold', fontSize=8.5, textColor=TEXT, leading=12)
    add('TCr',    fontName='Helvetica',      fontSize=8.5, textColor=TEXT,
        leading=12, alignment=TA_CENTER)
    return ss

SS = _make_styles()

def p(txt, s='Body'): return Paragraph(txt, SS[s])
def h1(txt):          return p(txt, 'T1')
def h2(txt):          return p(txt, 'T2')
def h3(txt):          return p(txt, 'T3')
def sp(n=3):          return Spacer(1, n*mm)
def hr(c=BORDER):     return HRFlowable(width='100%', thickness=0.4, color=c, spaceAfter=2*mm)

# ── CODE BLOCK ──────────────────────────────────────────────────────────────
def cb(lines, title='', ec=ORANGE):
    code_text = '\n'.join(lines)
    pre = Preformatted(code_text, SS['Code'])
    inner = Table([[pre]], colWidths=[CW - 6*mm])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAY2),
        ('BOX',        (0,0), (-1,-1), 0.4, BORDER),
        ('LEFTPADDING',(0,0), (-1,-1), 10),
        ('RIGHTPADDING',(0,0),(-1,-1),  8),
        ('TOPPADDING', (0,0), (-1,-1),  7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
    ]))
    outer = Table([['', inner]], colWidths=[6*mm, CW - 6*mm])
    outer.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,-1), ec),
        ('LEFTPADDING', (0,0),(-1,-1), 0),('RIGHTPADDING',(0,0),(-1,-1), 0),
        ('TOPPADDING',  (0,0),(-1,-1), 0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('VALIGN',      (0,0),(-1,-1),'TOP'),
    ]))
    out = []
    if title:
        out.append(p(f'<font color="#{ec.hexval()[1:]}"><b>{title}</b></font>', 'Small'))
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
        safe = str(c).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return p(safe, cs)
    esc = lambda t: str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    data = [[p(esc(h),'TH') for h in headers]]
    for row in rows:
        data.append([cell(c, i) for i, c in enumerate(row)])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  hdr_color),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [GRAY1, white]),
        ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 8.5),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('RIGHTPADDING',  (0,0),(-1,-1), 6),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('GRID',          (0,0),(-1,-1), 0.3, BORDER),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    return t

# ── NOTE BOX ────────────────────────────────────────────────────────────────
def note(txt, kind='info'):
    bgs = {'info':(INFO_BG,INFO_BD,'▸'),'warn':(WARN_BG,WARN_BD,'⚠'),
           'ok':(OK_BG,OK_BD,'✓'),'err':(ERR_BG,ERR_BD,'✗')}
    bg, bd, ic = bgs.get(kind, bgs['info'])
    esc_txt = txt.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    t = Table([[p(f'{ic}  {esc_txt}','Body')]], colWidths=[CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), bg),
        ('BOX',       (0,0),(-1,-1), 0.8, bd),
        ('LEFTPADDING',(0,0),(-1,-1), 10),('RIGHTPADDING',(0,0),(-1,-1), 10),
        ('TOPPADDING', (0,0),(-1,-1),  6),('BOTTOMPADDING',(0,0),(-1,-1), 6),
    ]))
    return t

# ── SECTION HEADER ──────────────────────────────────────────────────────────
class SH(Flowable):
    def __init__(self, num, title, ec=ORANGE, bg=ORANGE_BG):
        super().__init__()
        self.num=num; self.title=title; self.ec=ec; self.bg=bg
        self._h = 13*mm
    def wrap(self, aW, aH):
        self._w = aW; return aW, self._h
    def draw(self):
        c = self.canv; w = self._w; h = self._h
        c.setFillColor(self.bg)
        c.roundRect(0, 0, w, h, 3, fill=1, stroke=0)
        c.setFillColor(self.ec)
        c.roundRect(0, 0, 5, h, 1, fill=1, stroke=0)
        # badge
        bx = 13*mm; by = h/2
        c.setFillColor(self.ec)
        c.circle(bx, by, 4.5*mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(bx, by - 3, self.num)
        # title
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 10.5)
        c.drawString(22*mm, by - 4, self.title)

# ── PAGE HEADER/FOOTER ──────────────────────────────────────────────────────
class PageHF:
    def __init__(self, elem, ec):
        self.elem = elem; self.ec = ec
    def __call__(self, canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFillColor(NAVY)
        canvas.rect(0, PH - MT + 6*mm, PW, MT - 6*mm, fill=1, stroke=0)
        canvas.setFillColor(self.ec)
        canvas.rect(0, PH - MT + 6*mm, 6, MT - 6*mm, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(ML, PH - 11*mm, f'CAD-ANALYZER  ·  FICHAS {self.elem}')
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(HexColor('#8ba0cc'))
        canvas.drawRightString(PW - MR, PH - 11*mm, 'v4.0  ·  2026-03-19')
        # Footer
        canvas.setFillColor(BORDER)
        canvas.setLineWidth(0.3)
        canvas.line(ML, MB - 5*mm, PW - MR, MB - 5*mm)
        canvas.setFillColor(TEXT2)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(ML, MB - 10*mm,
            'CAD-ANALYZER  ·  Referência técnica para robô extrator DXF')
        canvas.drawRightString(PW - MR, MB - 10*mm, f'Página {doc.page}')
        canvas.restoreState()

def make_doc(path, elem, ec):
    hf = PageHF(elem, ec)
    return SimpleDocTemplate(str(path), pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        onFirstPage=hf, onLaterPages=hf,
        title=f'CAD-ANALYZER · Fichas {elem}',
        author='Diana Corporação Senciente')

# ══════════════════════════════════════════════════════════════════════════════
# PILARES
# ══════════════════════════════════════════════════════════════════════════════
def build_pilares():
    ec = ORANGE; bg = ORANGE_BG
    def sec(n, t): return SH(n, t, ec, bg)

    s = []

    # ── CAPA ─────────────────────────────────────────────────────────────────
    s += [
        sp(20),
        p('CAD-ANALYZER', 'Capa'),
        p('Fichas de Extração — PILARES', 'CapaSub'),
        sp(2),
        note('Esta ficha responde: dado um texto/polígono do DXF, qual campo JSON extrair e como.', 'info'),
        sp(4), hr(ec), sp(2),
    ]
    idx_rows = [
        ['1','Identificação','RE_PILAR · padrões · exemplos'],
        ['2','Associação texto→polígono','3 raios · scores · algoritmo'],
        ['3','Dimensões e Seção','RE_DIM · RE_DIM_BH · normalização'],
        ['4','Schema JSON Completo','FichaFase3Pilar · todos os campos'],
        ['5','Layers Canônicos','NOMENCLATURA · Painéis · aliases por firma'],
        ['6','Pilar Especial','cambotado · bulge · nível · armadura'],
        ['7','Confidence e Fallbacks','fórmula · cadeia de 5 níveis'],
        ['8','Matriz de Decisão','todos os casos ambíguos'],
        ['9','Exemplos Reais ALIMONTI','P17 (score 1.0) · P5 (0.394) · PC-1 cambotado'],
        ['10','Log e Validação','campos obrigatórios · regras de integridade'],
        ['11','Pipeline Completo','fluxo E2E · checklist 12 passos'],
    ]
    s.append(tbl(['#','Seção','Conteúdo'], idx_rows, [12*mm, 60*mm, CW-72*mm]))
    s.append(PageBreak())

    # ── 1. IDENTIFICAÇÃO ─────────────────────────────────────────────────────
    s.append(sec('1','Identificação — RE_PILAR'))
    s.append(sp(2))
    s.append(h2('1.1 Regex Principal'))
    s += cb([
        "RE_PILAR = re.compile(",
        "    r'^(PC?\\.?-?\\d+([A-Z]|\\.-?\\d+)?'",
        "    r'|P-\\d+[A-Z]?'",
        "    r'|PILAR[-_\\s]*\\d+)',",
        "    re.IGNORECASE",
        ")",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Texto DXF','Casou?','Campo extraído'],
        [
            ['P17',   '✓ SIM', 'codigo = "P17"'],
            ['P17A',  '✓ SIM', 'codigo = "P17A"'],
            ['PC-1',  '✓ SIM', 'codigo = "PC-1" (pilar de canto)'],
            ['P.17',  '✓ SIM', 'codigo = "P.17"'],
            ['P-8',   '✓ SIM', 'codigo = "P-8"'],
            ['PILAR 3','✓ SIM','codigo = "PILAR 3"'],
            ['V5',    '✗ NÃO', '— (é viga)'],
            ['P',     '✗ NÃO', '— (sem número)'],
            ['PA',    '✗ NÃO', '— (sem número)'],
        ],
        [28*mm, 24*mm, CW-52*mm],
        col_styles=['TCc','TC','TCc'],
    ))
    s.append(sp(2))
    s.append(h2('1.2 Extração de Textos no DXF'))
    s += cb([
        "for e in msp:",
        "    if e.dxftype() not in ('TEXT','MTEXT'): continue",
        "",
        "    if e.dxftype() == 'TEXT':",
        "        txt   = e.dxf.text.strip()",
        "        x, y  = float(e.dxf.insert.x), float(e.dxf.insert.y)",
        "        layer = e.dxf.layer",
        "    else:  # MTEXT",
        "        txt   = e.plain_text().strip()",
        "        x, y  = float(e.dxf.insert.x), float(e.dxf.insert.y)",
        "        layer = e.dxf.layer",
        "",
        "    if RE_PILAR.match(txt):",
        "        pilares_txt.append({'text': txt, 'x': x, 'y': y, 'layer': layer})",
    ], ec=ec)
    s.append(PageBreak())

    # ── 2. ASSOCIAÇÃO ────────────────────────────────────────────────────────
    s.append(sec('2','Associação Texto → Polígono (3 Raios)'))
    s.append(sp(2))
    s.append(note('Regra: um texto P17 sozinho NÃO é pilar. Precisa de LWPOLYLINE fechada próxima.', 'warn'))
    s.append(sp(2))
    s.append(h2('2.1 Constantes'))
    s.append(tbl(
        ['Constante','Valor','Descrição'],
        [
            ['PILAR_SEARCH_RADIUS','800 mm','Raio de busca máximo'],
            ['TOUCH_DIST',         '5 mm',  'Distância "tocando" → score 0.8'],
            ['DIM_SEARCH_RADIUS',  '600 mm','Raio para texto de dimensão (20x50)'],
        ],
        [52*mm, 24*mm, CW-76*mm],
    ))
    s.append(h2('2.2 Algoritmo TextAssociator'))
    s += cb([
        "from shapely.geometry import Point, Polygon",
        "",
        "PILAR_SEARCH_RADIUS = 800.0  # mm",
        "TOUCH_DIST = 5.0             # mm",
        "",
        "def score_texto_poligono(txt_pt, poly_pts):",
        "    poly   = Polygon(poly_pts)",
        "    pt     = Point(txt_pt)",
        "    dist   = poly.exterior.distance(pt)",
        "",
        "    if poly.contains(pt):          # texto DENTRO",
        "        return 1.0",
        "    elif dist <= TOUCH_DIST:       # tocando (<=5mm)",
        "        return 0.8",
        "    elif dist <= PILAR_SEARCH_RADIUS:  # próximo",
        "        # decaimento linear: 0.5 → 0.0",
        "        ratio = dist / PILAR_SEARCH_RADIUS",
        "        return max(0.0, 0.5 * (1.0 - ratio))",
        "    else:                          # fora do raio",
        "        return 0.0",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Situação','Score','Ação'],
        [
            ['Texto dentro do polígono',    '1.0',       'Auto-assign'],
            ['Texto tocando (dist ≤ 5mm)',  '0.8',       'Auto-assign'],
            ['Texto próximo (5mm < dist ≤ 800mm)', '0.0–0.5', 'Score com decaimento linear'],
            ['Texto fora do raio (> 800mm)','0.0',       'Ignorar'],
            ['2 textos competindo',          'vencedor',  'Vence score maior; log "EMPATE" se iguais'],
        ],
        [68*mm, 22*mm, CW-90*mm],
    ))
    s.append(PageBreak())

    # ── 3. DIMENSÕES ─────────────────────────────────────────────────────────
    s.append(sec('3','Dimensões e Seção Transversal'))
    s.append(sp(2))
    s.append(h2('3.1 Regexes de Dimensão'))
    s += cb([
        "# Formato NNxMM (ex: 20x50, 30X60)",
        "RE_DIM    = re.compile(r'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})')",
        "",
        "# Formato b=20 h=50",
        "RE_DIM_BH = re.compile(r'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})',",
        "                        re.IGNORECASE)",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Texto DXF','Regex','comprimento','largura'],
        [
            ['"20x50"',   'RE_DIM',    '50 cm','20 cm'],
            ['"30X70"',   'RE_DIM',    '70 cm','30 cm'],
            ['"b=20 h=50"','RE_DIM_BH','50 cm','20 cm'],
            ['"50/20"',   'RE_DIM',    '50 cm','20 cm'],
        ],
        [32*mm, 30*mm, 30*mm, 30*mm],
        col_styles=['TCc','TC','TCc','TCc'],
    ))
    s.append(sp(2))
    s.append(h2('3.2 Normalização (comprimento >= largura)'))
    s += cb([
        "def normalizar_secao(a, b):",
        "    '''Garante comprimento >= largura (convenção pilar)'''",
        "    comp = max(a, b)  # cm",
        "    larg = min(a, b)  # cm",
        "    return comp, larg",
        "",
        "# Pilar quadrado: comp == larg (ex: 20x20)",
        "# Pilar cambotado: usa bounding-box do polígono não-retangular",
    ], ec=ec)
    s.append(sp(2))
    s.append(note('Se nenhum texto de dimensão for encontrado em DIM_SEARCH_RADIUS=600mm: comprimento=0, largura=0, confidence -= 0.30', 'warn'))
    s.append(PageBreak())

    # ── 4. SCHEMA JSON ──────────────────────────────────────────────────────
    s.append(sec('4','Schema JSON Completo — FichaFase3Pilar'))
    s.append(sp(2))
    s += cb([
        "{",
        '    "codigo":        "P17",          # str  — ID do pilar',
        '    "pavimento":     "1_PAVIMENTO",  # str  — nome do arquivo DXF',
        '    "obra_nome":     "ALIMONTI",     # str  — nome da obra',
        "",
        '    # Geometria',
        '    "comprimento":   50.0,           # float cm — dimensão maior',
        '    "largura":       20.0,           # float cm — dimensão menor',
        '    "pilar_especial": false,         # bool  — verdadeiro se cambotado',
        '    "tipo_pilar_especial": "",       # str   — "CAMBOTADO" | ""',
        "",
        '    # Contorno (LWPOLYLINE em mm)',
        '    "outline_segs": [',
        '        {"x": 15000.0, "y": 10000.0},',
        '        {"x": 15200.0, "y": 10000.0},',
        '        {"x": 15200.0, "y": 10500.0},',
        '        {"x": 15000.0, "y": 10500.0}',
        '    ],',
        "",
        '    # Nível e estrutura',
        '    "nivel":          2.80,           # float m — cota Z',
        '    "altura_livre":   2.30,           # float m — calculada',
        "",
        '    # Armadura (do layer NOMENCLATURA ou texto adjacente)',
        '    "armadura": {',
        '        "tipo":          "longitudinal",',
        '        "quantidade":    8,',
        '        "diametro":      12.5,        # mm',
        '        "espacamento":   15,          # cm',
        '        "estribos":      "Φ5//15cm"',
        '    },',
        "",
        '    # Elementos vizinhos (inferidos por proximidade)',
        '    "vigas_ligadas": ["V101", "V102", "V103", "V104"],',
        "",
        '    # Qualidade',
        '    "confidence": 0.85,              # float 0.0–1.0',
        '    "revisado":   false              # bool',
        "}",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Campo','Tipo','Origem DXF','Obrigatório'],
        [
            ['codigo',      'str',  'TEXT/MTEXT layer NOMENCLATURA → RE_PILAR', 'SIM'],
            ['pavimento',   'str',  'Nome do arquivo .dxf',                     'SIM'],
            ['comprimento', 'float','Texto NNxMM/b=h= mais próximo (≤600mm)',    'SIM'],
            ['largura',     'float','Idem',                                      'SIM'],
            ['pilar_especial','bool','bulge > 0.3 em qualquer vértice',          'SIM'],
            ['outline_segs','list', 'LWPOLYLINE fechada layer Painéis',          'SIM'],
            ['nivel',       'float','TEXT layer NIVEL (ex: "cota 2.80")',        'NÃO'],
            ['armadura',    'dict', 'TEXT adjacente ao ID',                      'NÃO'],
            ['vigas_ligadas','list','Inferido por proximidade às vigas',         'NÃO'],
            ['confidence',  'float','Calculado (ver seção 7)',                   'SIM'],
        ],
        [30*mm, 16*mm, CW-76*mm, 22*mm],
    ))
    s.append(PageBreak())

    # ── 5. LAYERS ───────────────────────────────────────────────────────────
    s.append(sec('5','Layers Canônicos — Pilar'))
    s.append(sp(2))
    s.append(note('Sempre normalizar: unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().upper()', 'info'))
    s.append(sp(2))
    s.append(tbl(
        ['Layer Canônico','Aliases Reais no DXF','Firma','Uso'],
        [
            ['ELEMENT_LABEL','NOMENCLATURA, texto, "00 - FELIPE", EST-PILAR-TEXT','BIM/TQS','Textos P1, V1, L1'],
            ['PANEL_GEOMETRY','Painéis, PAINEIS, "Pain?is", PAINEL',            'BIM',    'LWPOLYLINE fechada do pilar'],
            ['WOOD_BATTEN',   'SARRAFO, "SARRAFO DE PRESSAO", Sarrafo de Pressão','BIM',  'Sarrafos de madeira'],
            ['BATTEN_2x7',    'SARR_2.2x7, "Sarr 2.2x7"',                       'BIM',   'Sarrafo 2,2×7cm'],
            ['BATTEN_7x7',    'SARR_7x7, SARR_7x10',                            'BIM',   'Cantos de pilar'],
            ['PLATE_GEOMETRY','CHAPA',                                            'BIM',   'Chapas de compensado'],
            ['ANCHOR_BAR_PL', '"BARRA ANCORAGEM"',                               'BIM',   'Barras (≠ LV usa "BARRA DE ANCORAGEM")'],
            ['ELEVATION_MARK','NIVEL, "Nível", "N?vel", "NIVEL 1° PAV."',        'BIM',   'Cota Z'],
            ['DIMENSION_LINES','COTA, cotas, "Cota Seção (2x)"',                 'BIM',   'Ignorado na extração'],
            ['SECTION_TEXT',  '"Texto Seção", "Texto de Titulo"',                'BIM',   'Textos 20x50, b=20 h=50'],
            ['PROP_LAYER',    'PONTALETE, "1-2 PONTALETE", MEIO_PONT',           'BIM',   'Pontaletes'],
            ['TQS_COLUMN',    'S-COLS, "1", "2", "3"',                           'TQS',   'Pilar em família TQS'],
        ],
        [34*mm, CW-108*mm, 20*mm, 40*mm],
    ))
    s.append(PageBreak())

    # ── 6. PILAR ESPECIAL ────────────────────────────────────────────────────
    s.append(sec('6','Pilar Especial — Cambotado, Nível e Armadura'))
    s.append(sp(2))
    s.append(h2('6.1 Detecção de Cambotado'))
    s += cb([
        "def detectar_cambotado(lwpoly):",
        "    '''Pilar com arco — bulge > 0.3 em qualquer vértice.'''",
        "    for pt in lwpoly.get_points('xyb'):  # x, y, bulge",
        "        if abs(pt[2]) > 0.3:",
        "            return True",
        "    return False",
        "",
        "# Se cambotado:",
        "#   pilar_especial = True",
        "#   tipo_pilar_especial = 'CAMBOTADO'",
        "#   comprimento/largura = bounding-box da geometria",
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('6.2 Extração de Nível (cota Z)'))
    s += cb([
        "import re",
        "RE_NIVEL = re.compile(r'(cota|nivel|nv)[\\s:=]*([\\d,.]+)', re.I)",
        "",
        "for e in textos_layer_nivel:",
        "    m = RE_NIVEL.search(e['text'])",
        "    if m:",
        "        nivel_m = float(m.group(2).replace(',', '.'))",
        "        # Associar ao pilar mais próximo dentro de PILAR_SEARCH_RADIUS",
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('6.3 Regras Fixas'))
    s.append(tbl(
        ['Caso','Condição','Ação'],
        [
            ['Pilar cambotado',          'bulge > 0.3',                    'tipo_pilar_especial = "CAMBOTADO"'],
            ['Comprimento < largura',    'comp < larg após extração',      'Trocar: comp=max(a,b), larg=min(a,b)'],
            ['Comprimento ≤ 0',          'comp <= 0',                      'confidence=0, revisão humana'],
            ['Área seção > 2500 cm²',   'comp × larg > 2500',             'Alerta: revisar dimensões'],
            ['Coordenadas UTM',          'x > 50000 ou y > 50000',         'Ignorar — não é DXF de fôrmas'],
        ],
        [42*mm, 48*mm, CW-90*mm],
    ))
    s.append(PageBreak())

    # ── 7. CONFIDENCE E FALLBACKS ────────────────────────────────────────────
    s.append(sec('7','Confidence e Fallbacks'))
    s.append(sp(2))
    s.append(h2('7.1 Fórmula de Confidence'))
    s += cb([
        "def calcular_confidence(raio_score, tem_dimensao, tem_texto_id, tem_contorno):",
        "    conf = raio_score       # base: score do TextAssociator",
        "",
        "    if not tem_dimensao:   conf -= 0.30  # sem 'NNxMM' próximo",
        "    if not tem_texto_id:   conf -= 0.40  # sem texto RE_PILAR (severo)",
        "    if not tem_contorno:   conf -= 0.20  # sem LWPOLYLINE fechada",
        "",
        "    return max(0.0, min(conf, 1.0))",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Score','Classe','Ação'],
        [
            ['≥ 0.80', '**ALTO',    'Auto-assign — aceitar sem revisão'],
            ['0.50–0.79','**MÉDIO', 'Aceitar com log de aviso'],
            ['0.30–0.49','**BAIXO', 'Fila de revisão humana'],
            ['< 0.30',  '**MUITO BAIXO','Rejeitar — não gravar no banco'],
        ],
        [22*mm, 28*mm, CW-50*mm],
    ))
    s.append(sp(2))
    s.append(h2('7.2 Cadeia de Fallbacks'))
    s.append(tbl(
        ['Nível','Condição','Confidence'],
        [
            ['1','Texto RE_PILAR em NOMENCLATURA → LWPOLYLINE em Painéis','raio_score'],
            ['2','Texto RE_PILAR em TEXTO_GERAL → mesma LWPOLYLINE',      'raio_score − 0.05'],
            ['3','Texto RE_PILAR em qualquer layer → LWPOLYLINE qualquer', 'raio_score − 0.15'],
            ['4','Texto RE_PILAR sem LWPOLYLINE próxima',                  'raio_score − 0.40'],
            ['5','Nenhum texto RE_PILAR encontrado',                       'NÃO REGISTRAR'],
        ],
        [10*mm, CW-42*mm, 30*mm],
    ))
    s.append(PageBreak())

    # ── 8. MATRIZ DE DECISÃO ─────────────────────────────────────────────────
    s.append(sec('8','Matriz de Decisão — Casos Ambíguos'))
    s.append(sp(2))
    s.append(tbl(
        ['Situação','Condição','Ação','Confidence','Log'],
        [
            ['Texto dentro do polígono', 'Polygon.contains(Point)', 'Auto-assign','1.0','—'],
            ['Texto tocando (≤5mm)',     'dist ≤ 5.0',             'Auto-assign','0.8','—'],
            ['Texto próximo (≤800mm)',   'dist ≤ radius',          'Score decaimento','0.0–0.5','avisar se < 0.50'],
            ['Texto fora do raio',       'dist > 800mm',           'Ignorar','0.0','—'],
            ['2 textos competindo',      'ambos dentro do raio',   'Vence score maior','vencedor','log ambos'],
            ['Empate exato de score',    'scores iguais',          'Revisão humana','score','log EMPATE'],
            ['ID sem dimensão próxima',  'RE_PILAR match, sem NNxMM','Registrar sem dim','conf−=0.30','"dim não encontrada"'],
            ['Dimensão sem ID',          'NNxMM, sem P/V texto',   'Desconsiderar dim','0.0','—'],
            ['Layer desconhecido',       'não está em CONFIG-LAYERS','Processar mesmo assim','conf−=0.10','"layer UNKNOWN"'],
            ['Encoding corrompido',      '"Pain?is" no DXF',       'normalize_layer()','sem penalidade','—'],
        ],
        [40*mm, 38*mm, 28*mm, 22*mm, CW-128*mm],
    ))
    s.append(PageBreak())

    # ── 9. EXEMPLOS REAIS ────────────────────────────────────────────────────
    s.append(sec('9','Exemplos Reais — Obra ALIMONTI-PARAISO'))
    s.append(sp(2))
    s.append(h2('Exemplo A — P17 (confidence = 1.0, texto DENTRO do polígono)'))
    s += cb([
        "# DXF:",
        "TEXT  layer='NOMENCLATURA'  text='P17'  insert=(15100, 10250)",
        "LWPOLYLINE layer='Painéis'  closed=True",
        "  vertices=[(15000,10000),(15200,10000),(15200,10500),(15000,10500)]",
        "TEXT  layer='NOMENCLATURA'  text='20x50'  insert=(15050, 10350)",
        "",
        "# Resultado JSON:",
        "{",
        '  "codigo": "P17",',
        '  "comprimento": 50.0, "largura": 20.0,',
        '  "outline_segs": [{"x":15000,"y":10000},{"x":15200,"y":10000},',
        '                    {"x":15200,"y":10500},{"x":15000,"y":10500}],',
        '  "confidence": 1.0,',
        '  "pilar_especial": false',
        "}",
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo B — P5 (confidence = 0.394, texto fora → revisão)'))
    s += cb([
        "# DXF: texto P5 a 315mm do polígono mais próximo",
        "# raio_score = 0.5 * (1 - 315/800) = 0.304",
        "# sem dimensão próxima → conf -= 0.30 → conf = 0.004 → arredonda 0.0",
        "# Ação: REJEITAR (< 0.30) — não gravar no banco",
        "# Log: {elemento_id:'P5', confianca:0.004, motivo:'texto distante + sem dim'}",
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo C — PC-1 cambotado (bulge = 0.414)'))
    s += cb([
        "# DXF:",
        "LWPOLYLINE layer='Painéis'  closed=True",
        "  get_points('xyb') → [..., (x, y, 0.414), ...]  # bulge > 0.3",
        "",
        "# Resultado:",
        "{",
        '  "codigo": "PC-1",',
        '  "pilar_especial": true,',
        '  "tipo_pilar_especial": "CAMBOTADO",',
        '  "comprimento": 40.0,  # bounding-box',
        '  "largura": 40.0,',
        '  "confidence": 0.85',
        "}",
    ], ec=ec)
    s.append(PageBreak())

    # ── 10. LOG E VALIDAÇÃO ──────────────────────────────────────────────────
    s.append(sec('10','Log e Validação'))
    s.append(sp(2))
    s.append(h2('10.1 Campos de Log Obrigatórios (confidence < 0.80)'))
    s += cb([
        "log_entry = {",
        '    "elemento_id":          "P17",',
        '    "tipo":                 "pilar",',
        '    "confidence":           0.65,',
        '    "motivo":               "dim nao encontrada (DIM_SEARCH_RADIUS=600mm)",',
        '    "acao":                 "revisao humana",',
        '    "raio_usado":           800,',
        '    "dist_texto_poligono":  145.3,',
        '    "layer_texto":          "NOMENCLATURA",',
        '    "layer_poligono":       "Paineis"',
        "}",
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('10.2 Regras de Integridade Cruzada'))
    s.append(tbl(
        ['Verificação','Condição de Alerta'],
        [
            ['Pilar sem viga em qualquer lado', 'len(vigas_ligadas) == 0 → "pilar isolado?"'],
            ['Comprimento ≤ 0',                 'comp <= 0 → inválido, revisão humana'],
            ['Área de seção > 2500 cm²',        'comp × larg > 2500 → dimensões suspeitas'],
            ['Coordenadas UTM',                  'x > 50000 → georreferenciamento, ignorar'],
        ],
        [58*mm, CW-58*mm],
    ))
    s.append(PageBreak())

    # ── 11. PIPELINE ────────────────────────────────────────────────────────
    s.append(sec('11','Pipeline Completo — Extração de Pilares'))
    s.append(sp(2))
    passos = [
        ('1','Carregar DXF', 'ezdxf.readfile(path) → doc = ezdxf.open(path)'),
        ('2','Detectar família','Checar prefixos MTH-, TX, layers numéricos → BIM/TQS/METHODUS/EBERICK'),
        ('3','normalize_layer()','unicodedata NFKD → ASCII → UPPER em todos os layer names'),
        ('4','Coletar textos','Iterar msp: TEXT/MTEXT → filtrar RE_PILAR → lista pilares_txt'),
        ('5','Coletar polígonos','LWPOLYLINE closed=True → lista poly_candidates'),
        ('6','Associar texto→poly','TextAssociator: 3-radius score → par (texto, poly, score)'),
        ('7','Extrair dimensões','RE_DIM / RE_DIM_BH no raio DIM_SEARCH_RADIUS=600mm'),
        ('8','Detectar cambotado','get_points("xyb") → bulge > 0.3 → pilar_especial=True'),
        ('9','Extrair nível','Layer NIVEL → RE_NIVEL → cota_m'),
        ('10','Calcular confidence','calcular_confidence(raio_score, tem_dim, tem_id, tem_contorno)'),
        ('11','Aplicar thresholds','≥0.80: auto | 0.50–0.79: warn | 0.30–0.49: review | <0.30: rejeitar'),
        ('12','Salvar JSON','FichaFase3Pilar → JSON por obra/pavimento'),
    ]
    s.append(tbl(
        ['Passo','Ação','Detalhe'],
        passos,
        [14*mm, 40*mm, CW-54*mm],
    ))

    return s


# ══════════════════════════════════════════════════════════════════════════════
# VIGAS
# ══════════════════════════════════════════════════════════════════════════════
def build_vigas():
    ec = BLUE; bg = BLUE_BG
    def sec(n, t): return SH(n, t, ec, bg)

    s = []

    # ── CAPA ─────────────────────────────────────────────────────────────────
    s += [
        sp(20),
        p('CAD-ANALYZER', 'Capa'),
        p('Fichas de Extração — VIGAS', 'CapaSub'),
        sp(2),
        note('Esta ficha responde: dado um texto/linha do DXF, qual campo JSON extrair e como.', 'info'),
        sp(4), hr(ec), sp(2),
    ]
    idx_rows = [
        ['1','Identificação','RE_VIGA · padrões · balanço BA*/VB*'],
        ['2','Geometria LV vs FV','LINE entities · layers fundo/Painéis'],
        ['3','Dimensões b/h','RE_DIM · RE_DIM_BH · convenção b<h'],
        ['4','Schema JSON Completo','FichaFase3Viga · tramos · apoios'],
        ['5','Apoios e Comprimento','apoio_ini/fim · distância entre pilares'],
        ['6','Layers Canônicos','fundo · Escoras · GARFOS · aliases por firma'],
        ['7','Confidence e Fallbacks','fórmula · cadeia de 6 níveis'],
        ['8','Matriz de Decisão','balanço · sem dimensão · layer desconhecido'],
        ['9','Exemplos Reais ALIMONTI','V101 · BA-5 (balanço) · VT-3'],
        ['10','Log e Validação','comprimento máx · integridade de apoios'],
        ['11','Pipeline Completo','fluxo E2E · checklist 12 passos'],
    ]
    s.append(tbl(['#','Seção','Conteúdo'], idx_rows, [12*mm, 50*mm, CW-62*mm]))
    s.append(PageBreak())

    # ── 1. IDENTIFICAÇÃO ─────────────────────────────────────────────────────
    s.append(sec('1','Identificação — RE_VIGA'))
    s.append(sp(2))
    s += cb([
        "RE_VIGA = re.compile(",
        "    r'^(V|BA|VB|VT|VC)\\.?-?\\d+([A-Z]|\\./\\d+)?',",
        "    re.IGNORECASE",
        ")",
        "",
        "# V   = viga normal",
        "# BA* = viga em balanço (apoio_fim = ''  — 1 apoio é CORRETO)",
        "# VB* = viga de borda em balanço",
        "# VT* = viga de topo / travamento",
        "# VC* = viga de coroamento",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Texto DXF','Casou?','Tipo','Obs'],
        [
            ['V101',  '✓','Viga normal',   '2 apoios esperados'],
            ['V101A', '✓','Viga normal',   'Sufixo letra'],
            ['BA-5',  '✓','Balanço',       'apoio_fim="" é correto'],
            ['VB3',   '✓','Borda balanço', 'apoio_fim="" é correto'],
            ['VT-2',  '✓','Viga de topo',  'Travamento'],
            ['VC1',   '✓','Coroamento',    '—'],
            ['L5',    '✗','—',             'É laje'],
            ['P3',    '✗','—',             'É pilar'],
        ],
        [24*mm, 20*mm, 30*mm, CW-74*mm],
        col_styles=['TCc','TC','TC','TC'],
    ))
    s.append(PageBreak())

    # ── 2. GEOMETRIA LV vs FV ────────────────────────────────────────────────
    s.append(sec('2','Geometria — LV (lateral) vs FV (fundo)'))
    s.append(sp(2))
    s.append(note('LV = lateral da viga (painéis verticais). FV = fundo da viga (prancha horizontal). Distinção CRÍTICA para cálculo de material.', 'warn'))
    s.append(sp(2))
    s.append(tbl(
        ['Componente','Layer','Entidade DXF','Atributos ezdxf'],
        [
            ['LV (lateral)','Painéis / PAINEIS','LWPOLYLINE (pode ser retangular)',
             '.get_points("xy") → lista de vértices'],
            ['FV (fundo)',  'fundo / FUNDOS',  'LINE ou LWPOLYLINE',
             '.dxf.start (Vec3) · .dxf.end (Vec3)'],
            ['Escoras',     'Escoras',          'LINE ou INSERT','Apoio vertical da viga'],
            ['Garfos HT20CT','GARFOS',          'INSERT ou LINE','Elemento metálico de apoio'],
        ],
        [28*mm, 30*mm, 34*mm, CW-92*mm],
    ))
    s.append(sp(2))
    s += cb([
        "# Acesso às LINEs de fundo (FV):",
        "for e in msp.query('LINE'):",
        "    layer_norm = normalize_layer(e.dxf.layer)",
        "    if layer_norm not in ('FUNDO', 'FUNDOS', 'FUNDO DA VIGA'):",
        "        continue",
        "    start = (float(e.dxf.start.x), float(e.dxf.start.y))",
        "    end   = (float(e.dxf.end.x),   float(e.dxf.end.y))",
        "    comprimento_mm = math.hypot(end[0]-start[0], end[1]-start[1])",
        "    fv_candidates.append({'start':start,'end':end,'comp':comprimento_mm})",
    ], ec=ec)
    s.append(PageBreak())

    # ── 3. DIMENSÕES ─────────────────────────────────────────────────────────
    s.append(sec('3','Dimensões — Largura (b) e Altura (h)'))
    s.append(sp(2))
    s += cb([
        "RE_DIM    = re.compile(r'(\\d{1,3})\\s*[xX*\\/]\\s*(\\d{1,3})')",
        "RE_DIM_BH = re.compile(r'b\\s*=\\s*(\\d{1,3}).*?h\\s*=\\s*(\\d{1,3})', re.I)",
        "",
        "# CONVENÇÃO VIGA: largura (b) SEMPRE < altura (h)",
        "# Ex: texto '20x50' → largura=20cm, altura=50cm  (b < h)",
        "# Ex: texto '50x20' → idem após reordenação",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Texto DXF','largura (b)','altura (h)','Obs'],
        [
            ['"20x50"',   '20 cm', '50 cm', 'b < h ✓'],
            ['"50x20"',   '20 cm', '50 cm', 'Reordenado: b=min, h=max'],
            ['"b=20 h=50"','20 cm','50 cm', 'RE_DIM_BH'],
            ['"b=20h=50"', '20 cm','50 cm', 'Sem espaço — ainda casa'],
        ],
        [28*mm, 26*mm, 26*mm, CW-80*mm],
        col_styles=['TCc','TCc','TCc','TC'],
    ))
    s.append(sp(2))
    s.append(note('Se nenhum texto de dimensão em VIGA_SEARCH_RADIUS=1200mm: largura=0, altura=0, confidence -= 0.30', 'warn'))
    s.append(PageBreak())

    # ── 4. SCHEMA JSON ──────────────────────────────────────────────────────
    s.append(sec('4','Schema JSON Completo — FichaFase3Viga'))
    s.append(sp(2))
    s += cb([
        "{",
        '    "codigo":    "V101",          # str',
        '    "pavimento": "1_PAVIMENTO",   # str — nome arquivo DXF',
        '    "obra_nome": "ALIMONTI",      # str',
        "",
        '    # Dimensões de seção',
        '    "largura":   20.0,            # float cm — b (menor dimensão)',
        '    "altura":    50.0,            # float cm — h (maior dimensão)',
        "",
        '    # Tramos (viga pode ter múltiplos vãos)',
        '    "tramos": [',
        '        {',
        '            "apoio_ini": "P5",    # str — ID do pilar inicial',
        '            "apoio_fim": "P6",    # str — ID do pilar final ("" se balanço)',
        '            "comprimento": 450.0, # float cm — distância entre apoios',
        '            "nivel": 2.80         # float m — cota do fundo da viga',
        '        }',
        '    ],',
        "",
        '    # Geometria das linhas de fundo (FV)',
        '    "fv_segs": [',
        '        {"start": [15000.0, 10000.0], "end": [19500.0, 10000.0]}',
        '    ],',
        "",
        '    # Elementos de apoio',
        '    "escoras":  12,               # int — contagem de escoras',
        '    "garfos":   6,                # int — garfos HT20CT',
        "",
        '    # Qualidade',
        '    "confidence": 0.90,',
        '    "revisado": false',
        "}",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Campo','Tipo','Obrigatório','Origem DXF'],
        [
            ['codigo',     'str',  'SIM','TEXT/MTEXT → RE_VIGA'],
            ['largura',    'float','SIM','RE_DIM/RE_DIM_BH ≤ 1200mm → min(a,b)'],
            ['altura',     'float','SIM','RE_DIM/RE_DIM_BH ≤ 1200mm → max(a,b)'],
            ['tramos',     'list', 'SIM','Associação com LINE em layer fundo'],
            ['apoio_ini',  'str',  'SIM','Pilar mais próximo à extremidade start'],
            ['apoio_fim',  'str',  'SIM','Pilar mais próximo à extremidade end ("" se BA*/VB*)'],
            ['comprimento','float','SIM','math.hypot(end-start) em mm → /10 para cm'],
            ['fv_segs',    'list', 'SIM','LINE layer fundo: start + end em mm'],
            ['escoras',    'int',  'NÃO','COUNT(LINE layer Escoras) próximas à viga'],
            ['garfos',     'int',  'NÃO','COUNT(INSERT layer GARFOS) próximos à viga'],
            ['confidence', 'float','SIM','Calculado (ver seção 7)'],
        ],
        [28*mm, 16*mm, 22*mm, CW-66*mm],
    ))
    s.append(PageBreak())

    # ── 5. APOIOS E COMPRIMENTO ──────────────────────────────────────────────
    s.append(sec('5','Apoios e Comprimento'))
    s.append(sp(2))
    s += cb([
        "def associar_apoios(fv_line, pilares_dict, raio=1200):",
        "    '''Encontra pilares nas extremidades da LINE de fundo.'''",
        "    sx, sy = fv_line['start']",
        "    ex, ey = fv_line['end']",
        "",
        "    apoio_ini = ''",
        "    apoio_fim = ''",
        "    min_d_ini = min_d_fim = float('inf')",
        "",
        "    for pid, pilar in pilares_dict.items():",
        "        cx = pilar['centroide_x']",
        "        cy = pilar['centroide_y']",
        "        d_ini = math.hypot(sx - cx, sy - cy)",
        "        d_fim = math.hypot(ex - cx, ey - cy)",
        "        if d_ini < min_d_ini and d_ini <= raio:",
        "            min_d_ini = d_ini; apoio_ini = pid",
        "        if d_fim < min_d_fim and d_fim <= raio:",
        "            min_d_fim = d_fim; apoio_fim = pid",
        "",
        "    comp_mm  = math.hypot(ex - sx, ey - sy)",
        "    comp_cm  = round(comp_mm / 10, 1)",
        "    return apoio_ini, apoio_fim, comp_cm",
        "",
        "# BALANÇO: BA* ou VB* → apoio_fim='' é ESPERADO, não é erro",
    ], ec=ec)
    s.append(PageBreak())

    # ── 6. LAYERS ───────────────────────────────────────────────────────────
    s.append(sec('6','Layers Canônicos — Viga'))
    s.append(sp(2))
    s.append(tbl(
        ['Layer Canônico','Aliases Reais','Entidade','Uso'],
        [
            ['BEAM_BOTTOM',   'fundo, FUNDOS, "Fundo da Viga", "fundo viga"','LINE/LWPOLY','FV — comprimento da viga'],
            ['SHORING',       'Escoras, "Escora de Viga"','LINE/INSERT','Escoras de apoio'],
            ['FORK_METAL',    'GARFOS','INSERT/LINE','Garfos HT20CT metálicos'],
            ['CLAMP_METAL',   'presilha, Presilha, PRESILHA','LWPOLY/LINE','Presilhas metálicas'],
            ['ANCHOR_BAR_LV', '"BARRA DE ANCORAGEM"','LINE','Barras de ancoragem (≠ PL)'],
            ['SPACER',        'Forcador','INSERT/LINE','Espaçadores da viga'],
            ['BATTEN_BEAM',   'barrote','LINE/LWPOLY','Barrotes da viga'],
            ['SLAB_INTERFACE','SCO-___-LAJ','LINE','Interface laje-viga'],
            ['DETAIL_LAYER',  'detalhes','qualquer','Ignorado na extração'],
            ['ELEMENT_LABEL', 'NOMENCLATURA, texto','TEXT/MTEXT','Textos de ID (V101)'],
        ],
        [34*mm, CW-110*mm, 26*mm, 36*mm],
    ))
    s.append(PageBreak())

    # ── 7. CONFIDENCE ───────────────────────────────────────────────────────
    s.append(sec('7','Confidence e Fallbacks'))
    s.append(sp(2))
    s.append(tbl(
        ['Nível','Condição','Confidence'],
        [
            ['1','Texto RE_VIGA em NOMENCLATURA → LINE em fundo/Painéis ≤ 1200mm','raio_score'],
            ['2','Texto RE_VIGA → LINE em qualquer layer (não fundo/Painéis)',     'raio_score − 0.15'],
            ['3','Texto RE_VIGA + RE_DIM → largura/altura extraídas',              '+0 (esperado)'],
            ['4','Texto RE_VIGA + RE_DIM_BH (b=20 h=50)',                          '+0 (aceito)'],
            ['5','Texto RE_VIGA sem dimensão próxima ≤ 1200mm',                    'conf − 0.30'],
            ['6','BA*/VB* com apoio_fim=""',                                        'OK — balanço não penaliza'],
        ],
        [10*mm, CW-52*mm, 38*mm],
    ))
    s.append(PageBreak())

    # ── 8. MATRIZ DE DECISÃO ─────────────────────────────────────────────────
    s.append(sec('8','Matriz de Decisão'))
    s.append(sp(2))
    s.append(tbl(
        ['Situação','Ação','Confidence'],
        [
            ['Viga BA*/VB* (balanço)',          'tramos[0].apoio_fim="" — correto','sem penalidade'],
            ['apoio_ini="" (não é balanço)',     'Alerta: viga sem apoio inicial',  'conf − 0.20'],
            ['comprimento > 1500cm',             'Alerta: revisar medida',          'log "comprimento suspeito"'],
            ['Largura < altura',                 'OK — convenção b < h',            'sem penalidade'],
            ['Nenhuma LINE de fundo próxima',    'fv_segs=[], estimado por texto',  'conf − 0.25'],
            ['2 LINEs competindo',               'Vence a mais próxima ao texto',   'log ambas'],
            ['Comprimento estimado',             'math.hypot entre pilares',        'conf − 0.10'],
        ],
        [52*mm, CW-102*mm, 34*mm],
    ))
    s.append(PageBreak())

    # ── 9. EXEMPLOS REAIS ────────────────────────────────────────────────────
    s.append(sec('9','Exemplos Reais — Obra ALIMONTI-PARAISO'))
    s.append(sp(2))
    s.append(h2('Exemplo A — V101 (confidence = 0.90)'))
    s += cb([
        "# DXF:",
        "TEXT  layer='NOMENCLATURA'  text='V101'  insert=(17000, 10000)",
        "TEXT  layer='NOMENCLATURA'  text='20x50' insert=(17100, 10050)",
        "LINE  layer='fundo'  start=(15000,10000)  end=(19500,10000)",
        "",
        "# Resultado:",
        "{",
        '  "codigo": "V101",',
        '  "largura": 20.0, "altura": 50.0,',
        '  "tramos": [{"apoio_ini":"P5","apoio_fim":"P6","comprimento":450.0}],',
        '  "fv_segs": [{"start":[15000,10000],"end":[19500,10000]}],',
        '  "confidence": 0.90',
        "}",
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo B — BA-5 (viga em balanço, 1 apoio)'))
    s += cb([
        "# DXF:",
        "TEXT  layer='NOMENCLATURA'  text='BA-5'  insert=(20000, 8000)",
        "LINE  layer='fundo'  start=(19000,8000)  end=(21200,8000)",
        "",
        "# BA* → apoio_fim='' é CORRETO (não penaliza confidence)",
        "{",
        '  "codigo": "BA-5",',
        '  "tramos": [{"apoio_ini":"P8","apoio_fim":"","comprimento":220.0}],',
        '  "confidence": 0.88',
        "}",
    ], ec=ec)
    s.append(PageBreak())

    # ── 10. LOG E VALIDAÇÃO ──────────────────────────────────────────────────
    s.append(sec('10','Log e Validação'))
    s.append(sp(2))
    s.append(tbl(
        ['Verificação','Condição de Alerta'],
        [
            ['Viga sem apoio_ini',          'apoio_ini=="" e não é BA*/VB* → erro'],
            ['Comprimento estimado > 1500cm','comprimento > 1500 → revisar'],
            ['Largura = 0',                  'sem dimensão → confidence < 0.60'],
            ['Nenhuma LINE de fundo',         'fv_segs=[] → log "sem fundo detectado"'],
        ],
        [50*mm, CW-50*mm],
    ))
    s.append(PageBreak())

    # ── 11. PIPELINE ────────────────────────────────────────────────────────
    s.append(sec('11','Pipeline Completo — Extração de Vigas'))
    s.append(sp(2))
    passos = [
        ('1', 'Carregar DXF',          'ezdxf.readfile(path) → msp'),
        ('2', 'Detectar família',       'Checar prefixos MTH-/TX/numérico → família'),
        ('3', 'normalize_layer()',      'NFKD → ASCII → UPPER em todos os layer names'),
        ('4', 'Coletar textos RE_VIGA', 'TEXT/MTEXT → filtrar RE_VIGA → lista vigas_txt'),
        ('5', 'Coletar LINEs de fundo', 'layer FUNDO/FUNDOS → lista fv_lines'),
        ('6', 'Associar texto→LINE',    'TextAssociator: raio 1200mm → score → par'),
        ('7', 'Extrair dimensões b/h',  'RE_DIM/RE_DIM_BH em 1200mm → b=min, h=max'),
        ('8', 'Associar apoios',        'Extremidades da LINE → pilares_dict → apoio_ini/fim'),
        ('9', 'Contar escoras/garfos',  'COUNT LINEs layer Escoras + INSERTs layer GARFOS'),
        ('10','Detectar balanço',       'BA*/VB* → apoio_fim="" é correto'),
        ('11','Calcular confidence',    'raio_score − penalidades → threshold'),
        ('12','Salvar JSON',            'FichaFase3Viga → JSON por obra/pavimento'),
    ]
    s.append(tbl(
        ['Passo','Ação','Detalhe'],
        passos,
        [14*mm, 42*mm, CW-56*mm],
    ))

    return s


# ══════════════════════════════════════════════════════════════════════════════
# LAJES
# ══════════════════════════════════════════════════════════════════════════════
def build_lajes():
    ec = GREEN; bg = GREEN_BG
    def sec(n, t): return SH(n, t, ec, bg)

    s = []

    # ── CAPA ─────────────────────────────────────────────────────────────────
    s += [
        sp(20),
        p('CAD-ANALYZER', 'Capa'),
        p('Fichas de Extração — LAJES', 'CapaSub'),
        sp(2),
        note('Esta ficha responde: dado um texto/polígono do DXF, qual campo JSON extrair e como.', 'info'),
        sp(4), hr(ec), sp(2),
    ]
    idx_rows = [
        ['1','Identificação','RE_LAJE · RE_LAJE_H · lajes sintéticas'],
        ['2','Contorno e Área','LWPOLYLINE · fórmula Shoelace'],
        ['3','Espessura h=','extrair h= · range válido 7–40cm'],
        ['4','Schema JSON Completo','FichaFase3Laje · todos os campos'],
        ['5','Layers Canônicos','EST-LAJE-TEXT · Painéis · Pilares · Vázio'],
        ['6','Laje Sintética','clusters h= · CLUSTER_RADIUS=500mm'],
        ['7','Aberturas e Recortes','layer Vázio · encoding CP1252 · Pilares'],
        ['8','Confidence e Fallbacks','fórmula · thresholds'],
        ['9','Exemplos Reais ALIMONTI','L5 (1.0) · synth_0 (0.50) · L3 abertura'],
        ['10','Pipeline Completo','fluxo E2E · checklist 10 passos'],
    ]
    s.append(tbl(['#','Seção','Conteúdo'], idx_rows, [12*mm, 50*mm, CW-62*mm]))
    s.append(PageBreak())

    # ── 1. IDENTIFICAÇÃO ─────────────────────────────────────────────────────
    s.append(sec('1','Identificação — RE_LAJE e RE_LAJE_H'))
    s.append(sp(2))
    s += cb([
        "# Caminho A — ID explícito (L1, Y1, LAJE-3...)",
        "RE_LAJE = re.compile(",
        "    r'^(L\\d+[A-Za-z]?|Y\\d+[A-Za-z]?|X\\d+[A-Za-z]?'",
        "    r'|LAJ[-_]?\\d+|LAJE[-_\\s]*\\d+)$',",
        "    re.IGNORECASE",
        ")",
        "",
        "# Caminho B — espessura 'h=' (laje sem ID explícito)",
        "RE_LAJE_H = re.compile(r'h\\s*[=:]\\s*([\\d,.]+)', re.IGNORECASE)",
        "# Exemplos: 'h=12', 'h = 14', 'h:10', 'h=12cm'  → espessura em cm",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Texto DXF','RE_LAJE?','RE_LAJE_H?','Resultado'],
        [
            ['L5',       '✓','—',  'codigo="L5"'],
            ['L12A',     '✓','—',  'codigo="L12A"'],
            ['Y1',       '✓','—',  'codigo="Y1"'],
            ['LAJ-3',    '✓','—',  'codigo="LAJ-3"'],
            ['LAJE 1',   '✓','—',  'codigo="LAJE 1"'],
            ['h=12',     '—','✓',  'espessura=12.0cm'],
            ['h = 14',   '—','✓',  'espessura=14.0cm'],
            ['L5 h=12',  '✓','✓',  'codigo="L5" espessura=12.0cm'],
            ['L',        '✗','—',  'sem número → NÃO casa'],
            ['LAJE',     '✗','—',  'sem número → NÃO casa'],
        ],
        [28*mm, 22*mm, 24*mm, CW-74*mm],
        col_styles=['TCc','TC','TC','TC'],
    ))
    s.append(PageBreak())

    # ── 2. CONTORNO E ÁREA ───────────────────────────────────────────────────
    s.append(sec('2','Contorno e Área — LWPOLYLINE'))
    s.append(sp(2))
    s += cb([
        "LAJE_SEARCH_RADIUS = 1500.0  # mm — raio de busca (lajes são grandes)",
        "",
        "for e in msp.query('LWPOLYLINE'):",
        "    pts = [(float(p[0]), float(p[1])) for p in e.get_points('xy')]",
        "    is_closed = (getattr(e.dxf, 'flags', 0) & 1 == 1) or e.is_closed",
        "",
        "    if is_closed and len(pts) >= 3:",
        "        from shapely.geometry import Polygon",
        "        area = Polygon(pts).area",
        "",
        "        if area > 50_000:   # > 50.000 mm² → provável LAJE",
        "            laje_polys.append({'pts': pts, 'area': area, 'layer': e.dxf.layer})",
        "        elif area < 5_000:  # < 5.000 mm² → provável PILAR",
        "            pilar_polys.append({'pts': pts, 'layer': e.dxf.layer})",
    ], ec=ec)
    s.append(sp(2))
    s.append(h2('Área pela Fórmula Shoelace'))
    s += cb([
        "def area_shoelace(pts):",
        "    n = len(pts); area = 0.0",
        "    for i in range(n):",
        "        j = (i + 1) % n",
        "        area += pts[i][0] * pts[j][1]",
        "        area -= pts[j][0] * pts[i][1]",
        "    return abs(area) / 2.0",
        "",
        "area_mm2 = area_shoelace(pts)",
        "area_m2  = area_mm2 / 1_000_000",
    ], ec=ec)
    s.append(PageBreak())

    # ── 3. ESPESSURA ────────────────────────────────────────────────────────
    s.append(sec('3','Espessura — Extração de h='))
    s.append(sp(2))
    s += cb([
        "def extrair_espessura(textos_h, laje_pos, raio=1500.0):",
        "    lx, ly = laje_pos",
        "    candidatos = []",
        "    for t in textos_h:",
        "        m = RE_LAJE_H.search(t['text'])",
        "        if not m: continue",
        "        dist = math.hypot(t['x'] - lx, t['y'] - ly)",
        "        if dist <= raio:",
        "            val = float(m.group(1).replace(',', '.'))",
        "            candidatos.append((val, dist))",
        "    if candidatos:",
        "        candidatos.sort(key=lambda x: x[1])  # mais próximo",
        "        return candidatos[0][0]",
        "    return 0.0",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Valor h=','Válido?','Ação'],
        [
            ['h=12','SIM (7–40cm)', 'espessura=12.0'],
            ['h=20','SIM',          'espessura=20.0'],
            ['h=5', 'NÃO (< 7cm)', 'confidence −= 0.30, log "espessura inválida"'],
            ['h=45', 'NÃO (> 40cm)','confidence −= 0.30, log "espessura fora do range"'],
            ['ausente','—',         'espessura=0.0, confidence −= 0.30'],
        ],
        [24*mm, 34*mm, CW-58*mm],
    ))
    s.append(sp(2))
    s.append(note('h= em 2 valores conflitantes no mesmo raio → usar o mais próximo ao centróide da laje', 'warn'))
    s.append(PageBreak())

    # ── 4. SCHEMA JSON ──────────────────────────────────────────────────────
    s.append(sec('4','Schema JSON Completo — FichaFase3Laje'))
    s.append(sp(2))
    s += cb([
        "{",
        '    "codigo":    "L5",              # str — ID ("synth_0" se sintética)',
        '    "pavimento": "1_PAVIMENTO",     # str',
        '    "obra_nome": "ALIMONTI",        # str',
        "",
        '    "tipo":      "macica",          # "macica"|"pre_moldada"|"steel_deck"',
        '    "espessura": 12.0,              # float cm — de h=NN',
        "",
        '    "dimensoes": {',
        '        "comprimento": 620.0,       # float cm — bbox do contorno',
        '        "largura":     430.0,       # float cm — bbox do contorno',
        '        "espessura":   12.0',
        '    },',
        "",
        '    "outline_segs": [               # vértices do contorno em mm',
        '        {"x": 15000.0, "y": 10000.0},',
        '        {"x": 21200.0, "y": 10000.0},',
        '        {"x": 21200.0, "y": 14300.0},',
        '        {"x": 15000.0, "y": 14300.0}',
        '    ],',
        "",
        '    "nivel":     2.80,              # float m — layer NIVEL',
        "",
        '    "aberturas": [                  # LWPOLYLINEs layer Vázio',
        '        {"pontos": [[5800,5900],[5900,5900],[5900,6100],[5800,6100]],',
        '         "area": 20000.0}',
        '    ],',
        "",
        '    "vigas_around":   ["V101","V102","V103","V104"],',
        '    "pilares_around": ["P5","P6","P7","P8"],',
        "",
        '    "confidence": 0.70,',
        '    "revisado": false',
        "}",
    ], ec=ec)
    s.append(PageBreak())

    # ── 5. LAYERS ───────────────────────────────────────────────────────────
    s.append(sec('5','Layers Canônicos — Laje'))
    s.append(sp(2))
    s.append(tbl(
        ['Layer Canônico','Aliases Reais','Entidade','Uso'],
        [
            ['SLAB_TEXT',       'EST-LAJE-TEXT, NOMENCLATURA, EST-TEXT','TEXT/MTEXT','IDs de lajes (L1, L2…)'],
            ['PANEL_GEOMETRY',  'Painéis, PAINEIS, "Pain?is"',          'LWPOLY',   'Contorno da laje'],
            ['PILLAR_CUTOUT',   'Pilares, EST-PILAR, EST-PILAR-CUT',    'LWPOLY',   'Recortes de pilares'],
            ['BEAM_INTERFACE_LJ','VIGAS, EST-VIGA, EST-VIGA-TEXT',      'LINE',     'Interface vigas na laje'],
            ['VOID_OPENING',    'Vázio, Vazio, "V?zio", ABERTURA, VOID','LWPOLY',   'Aberturas ⚠ encoding!'],
            ['REUSE_STATUS',    'REAPROVEITAMENTO',                      'LWPOLY/TEXT','BOM/REGULAR/RUIM/DESCARTE'],
            ['STRUCTURAL_SYMBOL','EST-SIMB, "EST-SIMB-Spot Elevations"','INSERT',   'Símbolos estruturais'],
            ['PILLAR_TEXT',     'EST-PILAR-TEXT',                        'TEXT',     'Textos de pilares na laje'],
        ],
        [34*mm, CW-108*mm, 24*mm, 36*mm],
    ))
    s.append(sp(2))
    s.append(note('ENCODING CRÍTICO: "Vázio" pode chegar como "V?zio" em CP1252. Sempre use is_void_layer() abaixo.', 'err'))
    s += cb([
        "VOID_ALIASES = {'vazio','vazios','abertura','aberturas','buraco','void'}",
        "",
        "def is_void_layer(layer: str) -> bool:",
        "    import unicodedata",
        "    n = unicodedata.normalize('NFKD', layer).encode('ascii','ignore').decode().lower()",
        "    return n in VOID_ALIASES or 'vaz' in n",
    ], ec=ec)
    s.append(PageBreak())

    # ── 6. LAJE SINTÉTICA ───────────────────────────────────────────────────
    s.append(sec('6','Laje Sintética — Clusters de h='))
    s.append(sp(2))
    s.append(note('Quando não há texto L1/L2 mas há múltiplos h= próximos → agrupar em laje SYNTHETIC.', 'info'))
    s.append(sp(2))
    s += cb([
        "CLUSTER_RADIUS = 500.0  # mm",
        "",
        "def gerar_lajes_sinteticas(laje_dims):",
        "    used = set(); clusters = []",
        "    for i, d in enumerate(laje_dims):",
        "        if i in used: continue",
        "        cluster = [d]; used.add(i)",
        "        for j, d2 in enumerate(laje_dims):",
        "            if j in used: continue",
        "            if math.hypot(d['x']-d2['x'], d['y']-d2['y']) < CLUSTER_RADIUS:",
        "                cluster.append(d2); used.add(j)",
        "        clusters.append(cluster)",
        "",
        "    result = []",
        "    for idx, cluster in enumerate(clusters):",
        "        cx = sum(d['x'] for d in cluster) / len(cluster)",
        "        cy = sum(d['y'] for d in cluster) / len(cluster)",
        "        result.append({",
        "            'id': f'synth_{idx}', 'name': 'SYNTHETIC',",
        "            'x': cx, 'y': cy,",
        "            'espessura': cluster[0]['h_val'],",
        "            'confidence': 0.50  # sempre 0.50 para sintéticas",
        "        })",
        "    return result",
    ], ec=ec)
    s.append(PageBreak())

    # ── 7. ABERTURAS ────────────────────────────────────────────────────────
    s.append(sec('7','Aberturas e Recortes de Pilares'))
    s.append(sp(2))
    s += cb([
        "def detectar_aberturas(laje_contorno, polylines):",
        "    from shapely.geometry import Polygon",
        "    laje_poly = Polygon(laje_contorno)",
        "    aberturas = []",
        "    for poly in polylines:",
        "        if not poly['closed']: continue",
        "        if not is_void_layer(poly['layer']): continue",
        "        ab_poly = Polygon(poly['points'])",
        "        if laje_poly.intersects(ab_poly):",
        "            aberturas.append({",
        "                'pontos': poly['points'],",
        "                'area': ab_poly.area",
        "            })",
        "    return aberturas",
        "",
        "def detectar_recortes_pilares(laje_contorno, polylines):",
        "    from shapely.geometry import Polygon",
        "    laje_poly = Polygon(laje_contorno)",
        "    recortes = []",
        "    for poly in polylines:",
        "        if not poly['closed']: continue",
        "        ln = normalize_layer(poly['layer'])",
        "        if ln not in ('PILARES','EST-PILAR-CUT','PILLAR-CUT'): continue",
        "        rp = Polygon(poly['points'])",
        "        if laje_poly.intersects(rp):",
        "            recortes.append({'pontos': poly['points'], 'area': rp.area})",
        "    return recortes",
    ], ec=ec)
    s.append(PageBreak())

    # ── 8. CONFIDENCE ───────────────────────────────────────────────────────
    s.append(sec('8','Confidence e Thresholds'))
    s.append(sp(2))
    s += cb([
        "def calcular_confidence_laje(laje):",
        "    conf = 0.30  # base",
        "    if laje.get('espessura', 0) > 0:              conf += 0.30",
        "    if len(laje.get('outline_segs', [])) >= 3:    conf += 0.20",
        "    if laje.get('vigas_around'):                   conf += 0.20",
        "    return min(conf, 1.0)",
        "",
        "# Laje SYNTHETIC começa em 0.50 (espessura ok, contorno incerto)",
    ], ec=ec)
    s.append(sp(2))
    s.append(tbl(
        ['Situação','Confidence','Ação'],
        [
            ['ID explícito + espessura + contorno + vigas', '1.0',  'Auto-assign'],
            ['ID + espessura + contorno (sem vigas)',        '0.80', 'Auto-assign'],
            ['ID + espessura (sem contorno)',                '0.60', 'Aceitar com log'],
            ['Laje SYNTHETIC (cluster h=)',                  '0.50', 'Aceitar com log "laje sintetica"'],
            ['ID sem espessura',                             '0.30', 'Revisão humana'],
            ['Espessura < 7cm',                              '0.0',  'Inválida por norma — rejeitar'],
        ],
        [CW-72*mm, 22*mm, 36*mm],
    ))
    s.append(PageBreak())

    # ── 9. EXEMPLOS REAIS ────────────────────────────────────────────────────
    s.append(sec('9','Exemplos Reais — Obra ALIMONTI-PARAISO'))
    s.append(sp(2))
    s.append(h2('Exemplo A — L5 (confidence = 1.0)'))
    s += cb([
        "# DXF:",
        "TEXT      layer='EST-LAJE-TEXT'  text='L5'    insert=(18000,12000)",
        "TEXT      layer='COTA'           text='h=12'  insert=(18100,11900)",
        "LWPOLY    layer='Paineis'  closed=True",
        "  vertices=[(15000,10000),(21200,10000),(21200,14300),(15000,14300)]",
        "",
        "# Resultado JSON:",
        '{"codigo":"L5","espessura":12.0,',
        ' "outline_segs":[{"x":15000,"y":10000},{"x":21200,"y":10000},',
        '                  {"x":21200,"y":14300},{"x":15000,"y":14300}],',
        ' "dimensoes":{"comprimento":620.0,"largura":430.0,"espessura":12.0},',
        ' "confidence":1.0}',
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo B — Laje Sintética synth_0 (confidence = 0.50)'))
    s += cb([
        "# DXF: 3 textos h=10 dentro de 300mm → 1 cluster",
        "TEXT  layer='COTA'  text='h=10'  insert=(3000,8000)",
        "TEXT  layer='COTA'  text='h=10'  insert=(3200,8100)",
        "TEXT  layer='COTA'  text='h=10'  insert=(3100,7900)",
        "",
        '{"codigo":"synth_0","tipo":"macica","espessura":10.0,',
        ' "outline_segs":[],"confidence":0.50}',
    ], ec=ec)
    s.append(sp(3))
    s.append(h2('Exemplo C — L3 com Abertura'))
    s += cb([
        "# DXF:",
        "TEXT    layer='EST-LAJE-TEXT'  text='L3'  insert=(6000,6000)",
        "LWPOLY  layer='Vazio'  closed=True",
        "  vertices=[(5800,5900),(5900,5900),(5900,6100),(5800,6100)]",
        "",
        '{"codigo":"L3","aberturas":[',
        '  {"pontos":[[5800,5900],[5900,5900],[5900,6100],[5800,6100]],',
        '   "area":20000.0}],"confidence":0.80}',
    ], ec=ec)
    s.append(PageBreak())

    # ── 10. PIPELINE ────────────────────────────────────────────────────────
    s.append(sec('10','Pipeline Completo — Extração de Lajes'))
    s.append(sp(2))
    passos = [
        ('1', 'Carregar DXF',           'ezdxf.readfile(path) → msp'),
        ('2', 'normalize_layer()',       'NFKD → ASCII → UPPER'),
        ('3', 'Coletar textos RE_LAJE',  'TEXT/MTEXT → filtrar RE_LAJE → lajes_txt'),
        ('4', 'Coletar textos RE_LAJE_H','Todos h=NN → laje_dims'),
        ('5', 'Coletar LWPOLYLINE',      'closed=True, area > 50000mm² → laje_polys'),
        ('6', 'Associar texto→poly',     'TextAssociator: raio 1500mm → score'),
        ('7', 'Extrair espessura h=',    'extrair_espessura() → mais próximo ao centróide'),
        ('8', 'Detectar lajes sintéticas','gerar_lajes_sinteticas() se cluster ≥ 2 textos h='),
        ('9', 'Detectar aberturas',      'is_void_layer() + intersects(laje_poly)'),
        ('10','Calcular confidence',     'calcular_confidence_laje() → thresholds'),
    ]
    s.append(tbl(
        ['Passo','Ação','Detalhe'],
        passos,
        [14*mm, 42*mm, CW-56*mm],
    ))

    return s


# ══════════════════════════════════════════════════════════════════════════════
# GERAR PDFs
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('CAD-ANALYZER — Fichas v4 (ReportLab, tipografia profissional)')

    tasks = [
        ('fichas_pilares_instrutivas.pdf', 'PILARES', ORANGE, build_pilares),
        ('fichas_vigas_instrutivas.pdf',   'VIGAS',   BLUE,   build_vigas),
        ('fichas_lajes_instrutivas.pdf',   'LAJES',   GREEN,  build_lajes),
    ]

    for fname, elem, ec, builder in tasks:
        path = OUT / fname
        doc  = make_doc(path, elem, ec)
        story = builder()
        doc.build(story)
        kb = path.stat().st_size // 1024
        print(f'  [OK] {fname}: {kb} KB')

    print('\nConcluido:')
    for fname, *_ in tasks:
        path = OUT / fname
        print(f'  {fname}: {path.stat().st_size // 1024} KB')
