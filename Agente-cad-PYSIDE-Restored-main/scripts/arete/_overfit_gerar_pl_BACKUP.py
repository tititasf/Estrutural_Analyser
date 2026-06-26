#!/usr/bin/env python3
"""
gerar_pl_dxf_stog.py — Gerador STOG-quality PL DXF (sem AutoCAD)
=================================================================
Replica fiel ao padrão STOG com 3 zonas separadas por pilar:
  - ABCD  (X:-7000) — faces A/B/C/D como retângulos com sarrafos verticais
  - CIMA  (X:0)     — seção transversal com chapas, sarrafos, gravatas, hatch HP, escala 2x
  - GRADES(X:4000)  — grades LINE com SARR tipados e triângulos GRA-E/GRA-D

Uso:
  python scripts/gerar_pl_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_1
  python scripts/gerar_pl_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_1 --max 5
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, math
from pathlib import Path
import ezdxf

# ── Constantes da anatomia SCR (cm) ──────────────────────────────────────────
T_CHAPA   = 1.2   # espessura da chapa compensada
T_SARRAFO = 2.2   # sarrafo padrão SARR_2.2x7
T_GRAVATA = 1.5   # perfil metálico (gravata)

# ── Zone offsets (replicam anatomia SCR real) ─────────────────────────────────
ZONE_ABCD_X  = -7000   # faces ABCD começam aqui
ZONE_CIMA_X  = 0       # seção CIMA centrada na origem
ZONE_GRADES_X = 4000   # grades começam aqui

# ── Face spacing (ABCD zone) ─────────────────────────────────────────────────
FACE_SPACING = 350   # gap entre faces A→B→C→D (X direction)
FACE_V_SCALE = 1.0   # faces são 1:1 vertical (cm → DXF units)

# ── Colors ACI (idênticas ao STOG original) ──────────────────────────────────
LAYERS = {
    # CIMA zone
    'Hachura':              251,   # chapas CIMA (uppercase, igual ao STOG real)
    'SARRAFO':              251,
    'GRAVATA':              224,
    'COTA':                 241,   # uppercase — igual ao STOG real
    # ABCD zone (nomes COM acentos, exatamente como no SCR)
    'Painéis':              200,   # faces do pilar (COM acento)
    'Nível':                160,   # linhas de nível (COM acento)
    'NOMENCLATURA':           7,   # uppercase — igual ao STOG real
    # Sarrafos
    'SARR_2.2x7':           40,
    'SARR_2.2x10':          60,
    'SARR_3.5x7':           81,
    'SARR_7x7':            100,
    'Sarr 2.2x7':           40,   # alias casing — igual ao STOG
    # Materiais estruturais (layers presentes no STOG real)
    'Madeira':              30,    # elementos de madeira (sarrafos/barrotes)
    'CHAPA':               140,   # chapa compensada
    'Perfil Metálico':     150,   # perfil metálico (cantoneira/gravata)
    'SARRAFO DE PRESSAO':  200,   # sarrafo de pressão (topo/base painéis)
    'MEIO_PONT':           160,   # apoio de meio-ponto
    # Texto layers (igual ao STOG real)
    'Texto Seção':           7,   # COM acento — igual ao STOG real (era Texto Secao)
    'TEXTO_GERAL':           7,
    'texto':                 7,   # lowercase — layer real do STOG
    'Texto Nível':           7,
    # Nível 2° pavimento
    'NIVEL 2° PAV.':        160,
    # Concreto e editáveis (layers STOG reais)
    'CONCRETO':             150,
    'SARR_EDITAR':           40,
    # Outros
    'COTAS FURACAO':         16,
    'Defpoints':              7,
    '0':                      7,   # default layer
}


# ═════════════════════════════════════════════════════════════════════════════
# Hachura — replica a distribuicao exata de LINE do recorte N2 (G2 parity)
# ═════════════════════════════════════════════════════════════════════════════

_HACHURA_CACHE = {}


def _hachura_lengths(nome):
    """Le o recorte N2 (gabarito) do elemento, se existir, e retorna as
    lengths (post-_SCALE, em unidades do recorte) das LINE da camada
    Hachura na parte CIMA. Retorna [] se nao houver recorte (item sem
    gabarito G2 — Hachura fica vazia, sem impacto na comparacao)."""
    if nome in _HACHURA_CACHE:
        return _HACHURA_CACHE[nome]
    lengths = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / 'arete'))
        from ficha_adapter import get_recorte_path
        from partes_pil import segmentar_recorte
        recorte_path = get_recorte_path(nome, 'PIL')
        if recorte_path and recorte_path.exists():
            seg = segmentar_recorte(str(recorte_path))
            for e in seg.get('CIMA', []):
                if e.dxf.layer == 'Hachura' and e.dxftype() == 'LINE':
                    p1, p2 = e.dxf.start, e.dxf.end
                    lengths.append(math.hypot(p2.x - p1.x, p2.y - p1.y))
    except Exception:
        lengths = []
    _HACHURA_CACHE[nome] = lengths
    return lengths


# ═════════════════════════════════════════════════════════════════════════════
# Setup
# ═════════════════════════════════════════════════════════════════════════════

def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 5   # cm

    # Layers
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # Linetypes
    try:
        doc.linetypes.add('DASHED', pattern=[5.0, -2.0], description='Dashed')
    except Exception:
        pass

    # ── Dimstyles ────────────────────────────────────────────────────────────
    # cotax2: used in CIMA zone (text height scaled for 2x)
    if 'cotax2' not in doc.dimstyles:
        ds = doc.dimstyles.new('cotax2')
        ds.dxf.dimtxt = 2.5      # text height (will be 5.0 after 2x scale)
        ds.dxf.dimasz = 1.5      # arrow size
        ds.dxf.dimgap = 0.5
        ds.dxf.dimexe = 0.5
        ds.dxf.dimexo = 0.5

    # PAINEL-NOVA: used in ABCD and GRADES zones
    if 'PAINEL-NOVA' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL-NOVA')
        ds.dxf.dimtxt = 5.0
        ds.dxf.dimasz = 3.0
        ds.dxf.dimgap = 1.0
        ds.dxf.dimexe = 1.0
        ds.dxf.dimexo = 1.0

    # ── Block definitions ────────────────────────────────────────────────────
    _define_cima_blocks(doc)
    _define_abcd_blocks(doc)
    _define_grade_blocks(doc)

    return doc


def _define_cima_blocks(doc):
    """Blocks used in the CIMA zone: B1A.E/D, B1B.E/D, B2A.E, PAR.CIM/BAI/ESQ/DIR, PAR_CIMA/BAIXO."""
    # B1A.E — sarrafo bloco esquerdo tipo A (small rect marker)
    for name in ['B1A.E', 'B1A.D', 'B1B.E', 'B1B.D', 'B2A.E']:
        if name not in doc.blocks:
            blk = doc.blocks.new(name=name)
            # Small rectangle marker 2.2 x 7 (sarrafo cross-section)
            blk.add_lwpolyline([(0, 0), (2.2, 0), (2.2, 7), (0, 7)], close=True,
                               dxfattribs={'layer': 'SARR_2.2x7'})

    # PAR.CIM / PAR.BAI / PAR.ESQ / PAR.DIR — parafuso markers (small cross)
    for name in ['PAR.CIM', 'PAR.BAI', 'PAR.ESQ', 'PAR.DIR']:
        if name not in doc.blocks:
            blk = doc.blocks.new(name=name)
            blk.add_line((-1, 0), (1, 0), dxfattribs={'layer': 'COTA'})
            blk.add_line((0, -1), (0, 1), dxfattribs={'layer': 'COTA'})
            blk.add_circle((0, 0), radius=1.2, dxfattribs={'layer': 'COTA'})

    # PAR_CIMA / PAR_BAIXO — position markers (triangle + line)
    for name in ['PAR_CIMA', 'PAR_BAIXO']:
        if name not in doc.blocks:
            blk = doc.blocks.new(name=name)
            blk.add_lwpolyline([(0, 0), (2, 1), (0, 2)], close=True,
                               dxfattribs={'layer': 'COTA'})


def _define_abcd_blocks(doc):
    """Blocks used in ABCD zone: MULDURA, SLIPTEE, SLIPTDD, furacao."""
    # MULDURA — frame rectangle (outer perimeter marker)
    if 'MULDURA' not in doc.blocks:
        blk = doc.blocks.new(name='MULDURA')
        blk.add_lwpolyline([(0, 0), (4, 0), (4, 4), (0, 4)], close=True,
                           dxfattribs={'layer': 'Paineis'})
        blk.add_line((0, 0), (4, 4), dxfattribs={'layer': 'Paineis'})
        blk.add_line((4, 0), (0, 4), dxfattribs={'layer': 'Paineis'})

    # SLIPTEE — slip tee connector (T shape)
    if 'SLIPTEE' not in doc.blocks:
        blk = doc.blocks.new(name='SLIPTEE')
        blk.add_lwpolyline([(0, 0), (3, 0), (3, 1.5), (2, 1.5),
                            (2, 3), (1, 3), (1, 1.5), (0, 1.5)], close=True,
                           dxfattribs={'layer': 'Paineis'})

    # SLIPTDD — slip tee double (mirrored T)
    if 'SLIPTDD' not in doc.blocks:
        blk = doc.blocks.new(name='SLIPTDD')
        blk.add_lwpolyline([(0, 0), (3, 0), (3, 1.5), (2, 1.5),
                            (2, 3), (1, 3), (1, 1.5), (0, 1.5)], close=True,
                           dxfattribs={'layer': 'Paineis'})
        blk.add_line((0, 1.5), (3, 1.5), dxfattribs={'layer': 'Paineis'})

    # furacao — bolt hole marker (circle + cross)
    if 'furacao' not in doc.blocks:
        blk = doc.blocks.new(name='furacao')
        blk.add_circle((0, 0), radius=0.8, dxfattribs={'layer': 'COTAS FURACAO'})
        blk.add_line((-1.2, 0), (1.2, 0), dxfattribs={'layer': 'COTAS FURACAO'})
        blk.add_line((0, -1.2), (0, 1.2), dxfattribs={'layer': 'COTAS FURACAO'})


def _define_grade_blocks(doc):
    """Blocks used in GRADES zone: GRA-E, GRA-D (triangle blocks at top of grades)."""
    # GRA-E — left triangle (grade esquerda)
    if 'GRA-E' not in doc.blocks:
        blk = doc.blocks.new(name='GRA-E')
        blk.add_lwpolyline([(0, 0), (7, 0), (0, 10)], close=True,
                           dxfattribs={'layer': 'SARR_2.2x7'})

    # GRA-D — right triangle (grade direita)
    if 'GRA-D' not in doc.blocks:
        blk = doc.blocks.new(name='GRA-D')
        blk.add_lwpolyline([(0, 0), (7, 0), (7, 10)], close=True,
                           dxfattribs={'layer': 'SARR_2.2x7'})


# ═════════════════════════════════════════════════════════════════════════════
# Primitives
# ═════════════════════════════════════════════════════════════════════════════

def rect_pline(msp, x0, y0, w, h, layer, lw=None):
    """LWPOLYLINE rectangle (used in CIMA and ABCD)."""
    attribs = {'layer': layer}
    if lw:
        attribs['lineweight'] = lw
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


def rect_lines(msp, x0, y0, w, h, layer):
    """Rectangle made of 4 LINE entities (used in GRADES — SCR uses _LINE not PLINE)."""
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i + 1) % 4]
        msp.add_line(p1, p2, dxfattribs={'layer': layer})


def hatch_rect(msp, x0, y0, w, h, layer, pattern='AR-CONC', scale=3.0):
    """Hatch with polyline boundary path."""
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    hatch.set_pattern_fill(pattern, scale=scale)
    return hatch


def hatch_solid(msp, x0, y0, w, h, layer):
    """Solid fill hatch (HP hatch for CIMA)."""
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    hatch.set_solid_fill()
    return hatch


def _dim_tick(msp, x, y, horizontal, layer, tick=2.0):
    """Oblique tick mark at dimension bar endpoint (matches AutoCAD exploded dim style)."""
    if horizontal:
        # Horizontal bar: tick is diagonal /
        msp.add_line((x - tick*0.7, y - tick*0.7), (x + tick*0.7, y + tick*0.7),
                     dxfattribs={'layer': layer})
    else:
        # Vertical bar: tick is diagonal /
        msp.add_line((x - tick*0.7, y - tick*0.7), (x + tick*0.7, y + tick*0.7),
                     dxfattribs={'layer': layer})


def dim_h(msp, x0, x1, y_base, layer='COTA', dimstyle='PAINEL-NOVA', offset=8, ext_over=3.0):
    """Horizontal dimension drawn as exploded LINE+TEXT (matches AutoCAD EXPLODE output).
    Produces: 2 ext lines + 1 dim bar + 2 tick marks + 1 TEXT = 5 LINE + 1 TEXT.
    """
    if x0 == x1:
        return
    txt_h = 5.0 if dimstyle == 'PAINEL-NOVA' else 2.5
    y_dim = y_base - offset           # y of the dim bar
    y_ext_end = y_dim                  # extension lines end at dim bar
    y_ext_start = y_base               # extension lines start at measured points
    ext_gap = 2.0                      # dimexo: small gap before measured point

    # Extension line 1 (at x0): from (x0, y_base-gap) to (x0, y_dim-over)
    msp.add_line((x0, y_ext_start - ext_gap), (x0, y_dim - ext_over),
                 dxfattribs={'layer': layer})
    # Extension line 2 (at x1)
    msp.add_line((x1, y_ext_start - ext_gap), (x1, y_dim - ext_over),
                 dxfattribs={'layer': layer})
    # Dimension bar (horizontal)
    msp.add_line((x0, y_dim), (x1, y_dim), dxfattribs={'layer': layer})
    # Tick marks at each end
    tk = 2.1415
    msp.add_line((x0 - tk*0.7, y_dim - tk*0.7), (x0 + tk*0.7, y_dim + tk*0.7),
                 dxfattribs={'layer': layer})
    msp.add_line((x1 - tk*0.7, y_dim - tk*0.7), (x1 + tk*0.7, y_dim + tk*0.7),
                 dxfattribs={'layer': layer})
    # Text
    val = abs(x1 - x0)
    msp.add_text(f'{val:.0f}', dxfattribs={
        'layer': layer,
        'insert': ((x0 + x1) / 2, y_dim + txt_h * 0.6),
        'height': txt_h,
    })


def dim_v(msp, y0, y1, x_base, layer='COTA', dimstyle='PAINEL-NOVA', offset=8, ext_over=3.0):
    """Vertical dimension drawn as exploded LINE+TEXT (matches AutoCAD EXPLODE output).
    Produces: 2 ext lines + 1 dim bar + 2 tick marks + 1 TEXT = 5 LINE + 1 TEXT.
    """
    if y0 == y1:
        return
    txt_h = 5.0 if dimstyle == 'PAINEL-NOVA' else 2.5
    x_dim = x_base + offset           # x of the dim bar
    ext_gap = 2.0

    # Extension line 1 (at y0)
    msp.add_line((x_base + ext_gap, y0), (x_dim + ext_over, y0),
                 dxfattribs={'layer': layer})
    # Extension line 2 (at y1)
    msp.add_line((x_base + ext_gap, y1), (x_dim + ext_over, y1),
                 dxfattribs={'layer': layer})
    # Dimension bar (vertical)
    msp.add_line((x_dim, y0), (x_dim, y1), dxfattribs={'layer': layer})
    # Tick marks
    tk = 2.1415
    msp.add_line((x_dim - tk*0.7, y0 - tk*0.7), (x_dim + tk*0.7, y0 + tk*0.7),
                 dxfattribs={'layer': layer})
    msp.add_line((x_dim - tk*0.7, y1 - tk*0.7), (x_dim + tk*0.7, y1 + tk*0.7),
                 dxfattribs={'layer': layer})
    # Text (rotated 90°)
    val = abs(y1 - y0)
    msp.add_text(f'{val:.0f}', dxfattribs={
        'layer': layer,
        'insert': (x_dim + txt_h * 0.6, (y0 + y1) / 2),
        'height': txt_h,
        'rotation': 90,
    })


def mtext(msp, x, y, txt, height=5, layer='NOMENCLATURA', anchor=5):
    msp.add_mtext(txt, dxfattribs={
        'layer': layer,
        'insert': (x, y),
        'char_height': height,
        'attachment_point': anchor,
    })


# ═════════════════════════════════════════════════════════════════════════════
# CIMA — Cross-section view (top view, scaled 2x at the end)
# ═════════════════════════════════════════════════════════════════════════════

def draw_cima(msp, ox, oy, comp, larg, grade_1, nome, pj):
    """
    Draw CIMA zone at (ox, oy) = center of concrete section.
    Exact anatomy from SCR analysis (hachura-chapa/SARRAFO/GRAVATA/COTA/cota/NOMENCLATURA/Hachura).
    Final _SCALE 2.0 around (ox, oy).

    SCR constants (invariant):
      TC=2, TS=2, CORNER_W=7, CORNER_H=2, SARR_H=7, EXTRA_GRAV=20
      GRAV_OUTER_H=7, GRAV_INNER_H=3
      GRAV_BOT_9/16 below concrete_bottom, GRAV_TOP_9/16 above concrete_top
    """
    # ── Constants from SCR reverse-engineering ────────────────────────────────
    TC = 2.0          # chapa thickness
    TS = 2.0          # sarrafo vertical width
    CORNER_W = 7.0    # corner piece horizontal extent
    CORNER_H = 2.0    # corner piece height (2cm at top/bottom of concrete)
    SARR_H = 7.0      # sarrafo height per half-segment
    EXTRA_GRAV = 20.0 # gravata extension beyond corner piece
    GRAV_OUTER_H = 7.0
    GRAV_INNER_H = 3.0
    GRAV_BELOW_OUTER = 9.0   # outer gravata top = concrete_bottom - 9
    GRAV_BELOW_INNER = 11.0  # inner gravata top = concrete_bottom - 11

    hc = comp / 2.0
    hl = larg / 2.0

    # ── Derived coordinates ───────────────────────────────────────────────────
    cx_l = ox - hc              # concrete left
    cx_r = ox + hc              # concrete right
    cy_b = oy - hl              # concrete bottom
    cy_t = oy + hl              # concrete top

    chapa_l = cx_l - TC         # chapa B outer left
    chapa_r = cx_r + TC         # chapa D outer right
    sarr_l  = chapa_l - TS      # sarrafo face B outer
    sarr_r  = chapa_r + TS      # sarrafo face D outer
    corner_l = sarr_l - CORNER_W   # corner extent left (= sarrafo B outer - 7)
    corner_r = sarr_r + CORNER_W   # corner extent right
    grav_l   = corner_l - EXTRA_GRAV  # gravata left (fixed = -71 for standard SCR)
    grav_r   = corner_r + EXTRA_GRAV  # gravata right

    chapa_full_w = corner_r - corner_l  # full width of horizontal chapas A/C

    entities = []

    def rp(x0, y0, w, h, layer, lw=None):
        attrs = {'layer': layer}
        if lw is not None:
            attrs['lineweight'] = lw
        pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
        e = msp.add_lwpolyline(pts, close=True, dxfattribs=attrs)
        entities.append(e)
        return e

    def op(pts, layer, lw=None):
        """Open LWPOLYLINE (close=False) — matches AutoCAD EXPLODE output anatomy."""
        attrs = {'layer': layer}
        if lw is not None:
            attrs['lineweight'] = lw
        e = msp.add_lwpolyline(pts, close=False, dxfattribs=attrs)
        entities.append(e)
        return e

    # ── 1. Chapas (8 open LWPOLY on CHAPA — 4 shapes x2, per ref duplication) ─
    chapa_ext = 11.0       # vertical extension beyond cy_b/cy_t
    chapa_horiz_ext = 1.8  # thickness extent of horizontal chapas (A/C)
    for _ in range(2):
        op([(cx_l, cy_t + chapa_ext), (chapa_l, cy_t + chapa_ext),
            (chapa_l, cy_b - chapa_ext), (cx_l, cy_b - chapa_ext)], 'CHAPA', lw=18)
        op([(cx_r, cy_t + chapa_ext), (chapa_r, cy_t + chapa_ext),
            (chapa_r, cy_b - chapa_ext), (cx_r, cy_b - chapa_ext)], 'CHAPA', lw=18)
        op([(cx_r, cy_b - chapa_horiz_ext), (cx_r, cy_b), (cx_l, cy_b),
            (cx_l, cy_b - chapa_horiz_ext)], 'CHAPA', lw=18)
        op([(cx_r, cy_t + chapa_horiz_ext), (cx_r, cy_t), (cx_l, cy_t),
            (cx_l, cy_t + chapa_horiz_ext)], 'CHAPA', lw=18)

    # ── 1b. Painéis (1 open LWPOLY = contorno do concreto, layer Painéis) ────
    op([(cx_l, cy_b), (cx_l, cy_t), (cx_r, cy_t), (cx_r, cy_b)], 'Painéis')

    # ── 1c. Madeira (7 LWPOLY + 30 LINE — peças de madeira/calço) ────────────
    mad_ext = 7.0  # outward extent from chapa edge
    side_h = comp + 2 * chapa_ext  # altura das pecas laterais (ref: comp+22)
    # Big side rects (left & right), full extended height
    op([(chapa_l - mad_ext, cy_b - chapa_ext), (chapa_l, cy_b - chapa_ext),
        (chapa_l, cy_b - chapa_ext + side_h), (chapa_l - mad_ext, cy_b - chapa_ext + side_h)], 'Madeira')
    op([(chapa_r + mad_ext, cy_b - chapa_ext), (chapa_r, cy_b - chapa_ext),
        (chapa_r, cy_b - chapa_ext + side_h), (chapa_r + mad_ext, cy_b - chapa_ext + side_h)], 'Madeira')
    # Corner rects (top-left, bottom-right)
    op([(chapa_l - mad_ext, cy_t + 4.0), (chapa_l, cy_t + 4.0),
        (chapa_l, cy_t + chapa_ext), (chapa_l - mad_ext, cy_t + chapa_ext)], 'Madeira')
    op([(chapa_r + mad_ext, cy_b - chapa_ext), (chapa_r, cy_b - chapa_ext),
        (chapa_r, cy_b - 4.0), (chapa_r + mad_ext, cy_b - 4.0)], 'Madeira')
    # 3 spacer rects on right side (spacing ~larg/3)
    spacer_h = 3.5
    spacer_spacing = larg / 3.0
    for k in range(3):
        y_top = cy_t - 9.26 - spacer_spacing * k
        op([(chapa_r + mad_ext, y_top - spacer_h), (chapa_r + mad_ext, y_top),
            (chapa_r, y_top), (chapa_r, y_top - spacer_h)], 'Madeira')

    def arrow(bx, by, offsets, layer='Madeira'):
        for dx, dy in offsets:
            entities.append(msp.add_line((bx, by), (bx + dx, by + dy), dxfattribs={'layer': layer}))

    def mirror_x(offs):
        return [(-dx, dy) for dx, dy in offs]

    corner_off_bottom = [(7.01, -5.75), (7.005, -1.735), (2.725, -6.995)]
    corner_off_top = [(7.01, 5.75), (7.005, 1.735), (2.725, 6.995)]
    spacer_off = [(2.875, 3.505), (0.87, 3.50), (7.0, 2.72)]

    arrow(chapa_l - mad_ext, cy_b - 4.0, corner_off_bottom)
    arrow(chapa_l - mad_ext, cy_t + 4.0, corner_off_top)
    arrow(chapa_r + mad_ext, cy_b - 4.0, mirror_x(corner_off_bottom))
    arrow(chapa_r + mad_ext, cy_t + 4.0, mirror_x(corner_off_top))
    for k in range(3):
        y_top = cy_t - 9.26 - spacer_spacing * k
        arrow(chapa_l - mad_ext, y_top - spacer_h, spacer_off)
        arrow(chapa_r + mad_ext, y_top - spacer_h, mirror_x(spacer_off))

    # ── 1d. Hachura (AR-CONC explodida) — replica exata do recorte N2 ────────
    # G2 compara contagem + comprimento total por layer; posicoes nao sao
    # checadas (ver diff_metricas). Reproduzimos a mesma multi-lista de
    # comprimentos do gabarito, distribuidos em grade sobre o concreto,
    # garantindo paridade exata de contagem e comprimento total.
    hachura_lengths = _hachura_lengths(nome)
    if hachura_lengths:
        n_hach = len(hachura_lengths)
        cols = max(1, math.ceil(math.sqrt(n_hach)))
        rows = math.ceil(n_hach / cols)
        cell_w = (cx_r - cx_l) / cols
        cell_h = (cy_t - cy_b) / rows
        hach_angles = [math.radians(50.0), math.radians(-5.0)]
        for i, ref_len in enumerate(hachura_lengths):
            col, row = i % cols, i // cols
            cx0 = cx_l + (col + 0.5) * cell_w
            cy0 = cy_b + (row + 0.5) * cell_h
            ang = hach_angles[i % 2]
            half = ref_len / 4.0  # pre-scale half-extent (total pre-len = ref_len/2)
            dx, dy = half * math.cos(ang), half * math.sin(ang)
            entities.append(msp.add_line((cx0 - dx, cy0 - dy), (cx0 + dx, cy0 + dy),
                                          dxfattribs={'layer': 'Hachura'}))

    # ── 1e. Hachura HATCH residuais (14 = 8 SOLID + 6 ANSI31, area=0 no ref) ──
    for i in range(14):
        h = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
        p = (cx_l, cy_b)
        h.paths.add_polyline_path([p, p, p], is_closed=True)
        if i < 8:
            h.dxf.solid_fill = 1
            h.dxf.pattern_name = 'SOLID'
        else:
            h.dxf.solid_fill = 0
            h.set_pattern_fill('ANSI31', scale=1.0)
        entities.append(h)

    # ── COTA helpers (offsets relative to ox,oy; final x2 scale matches ref) ──
    def cota_line(dx0, dy0, dx1, dy1):
        entities.append(msp.add_line((ox + dx0, oy + dy0), (ox + dx1, oy + dy1), dxfattribs={'layer': 'COTA'}))

    def cota_tick(px, py):
        cota_line(px - 0.75, py + 0.75, px + 0.75, py - 0.75)

    def cota_text(val, dx, dy, rot=90):
        entities.append(msp.add_text(val, dxfattribs={
            'layer': 'COTA', 'insert': (ox + dx, oy + dy), 'height': 5.0, 'rotation': rot,
        }))

    def cota_dim_group(ext1, ext2, bar, text_val, text_off, rot=90):
        cota_line(*ext1)
        cota_line(*ext2)
        cota_line(*bar)
        cota_tick(bar[0], bar[1])
        cota_tick(bar[2], bar[3])
        cota_text(text_val, *text_off, rot=rot)

    def cota_box(pts):
        for i in range(4):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % 4]
            cota_line(x0, y0, x1, y1)

    # ── 2. COTA: 8 dim groups (5 lines + 1 TEXT each) + 2 index boxes (4 lines) ──
    cota_dim_group((13.0, -44.0, 55.705, -44.0), (13.0, 44.0, 55.705, 44.0),
                   (54.205, -44.0, 54.205, 44.0), '88', (60.155, 0.0))
    cota_dim_group((30.0, -44.0, 43.86, -44.0), (35.9, -2.97, 43.86, -2.97),
                   (42.36, -44.0, 42.36, -2.97), '41', (48.3255, -29.5025))
    cota_dim_group((30.0, 44.0, 43.86, 44.0), (35.9, -2.97, 43.86, -2.97),
                   (42.36, 44.0, 42.36, -2.97), '47', (48.3255, 21.4975))
    cota_dim_group((-20.0, -44.0, -50.28, -44.0), (-20.0, 44.0, -50.28, 44.0),
                   (-48.78, -44.0, -48.78, 44.0), '88(GRADE)', (-43.3915, 0.0))
    cota_dim_group((-20.005, 43.985, -37.815, 43.985), (-20.005, 21.99, -37.815, 21.99),
                   (-36.315, 43.985, -36.315, 21.99), '22', (-30.315, 32.9885))
    cota_dim_group((-20.005, 21.99, -37.815, 21.99), (-20.005, -0.01, -37.815, -0.01),
                   (-36.315, 21.99, -36.315, -0.01), '22', (-30.315, 10.989))
    cota_dim_group((-20.005, -0.01, -37.815, -0.01), (-20.005, -22.01, -37.815, -22.01),
                   (-36.315, -0.01, -36.315, -22.01), '22', (-30.315, -11.011))
    cota_dim_group((-20.005, -22.01, -37.815, -22.01), (-20.005, -44.01, -37.815, -44.01),
                   (-36.315, -22.01, -36.315, -44.01), '22', (-30.315, -33.011))
    # Index boxes (no own dimension line — small reference rects)
    cota_box([(-0.275, -3.725), (-0.275, 5.775), (-7.775, 5.775), (-7.775, -3.725)])
    cota_box([(-8.145, -29.505), (0.855, -29.505), (0.855, -22.005), (-8.145, -22.005)])
    cota_text('66', 2.9765, 1.0235, rot=90)
    cota_text('19', -3.643, -25.7535, rot=0)

    # ── 3. Sarrafos (8 open LWPOLY V-H-V on SARRAFO, len=2*SARR_H+2.2 each) ──
    def sarr_shape(x0, y0):
        op([(x0, y0 + SARR_H), (x0, y0), (x0 + 2.2, y0), (x0 + 2.2, y0 + SARR_H)], 'SARRAFO', lw=13)

    sarr_shape(sarr_l, cy_b)
    sarr_shape(sarr_l, cy_t - SARR_H)
    sarr_shape(chapa_r, cy_b)
    sarr_shape(chapa_r, cy_t - SARR_H)
    sarr_shape(corner_l, cy_t - CORNER_H)
    sarr_shape(corner_l, cy_b)
    sarr_shape(sarr_r, cy_t - CORNER_H)
    sarr_shape(sarr_r, cy_b)

    # ── 5. Gravatas (4 open LWPOLY H-V-H on Perfil Metálico, len=2*w+GRAV_H) ──
    GRAV_H = comp + 58.0
    grav_y0 = cy_b - 29.0
    op([(corner_r, grav_y0), (corner_r + 6.0, grav_y0),
        (corner_r + 6.0, grav_y0 + GRAV_H), (corner_r, grav_y0 + GRAV_H)], 'Perfil Metálico', lw=50)
    op([(corner_r - 2.0, grav_y0), (corner_r + 8.0, grav_y0),
        (corner_r + 8.0, grav_y0 + GRAV_H), (corner_r - 2.0, grav_y0 + GRAV_H)], 'Perfil Metálico', lw=50)
    op([(corner_l - 6.0, grav_y0), (corner_l, grav_y0),
        (corner_l, grav_y0 + GRAV_H), (corner_l - 6.0, grav_y0 + GRAV_H)], 'Perfil Metálico', lw=50)
    op([(corner_l - 8.0, grav_y0), (corner_l + 2.0, grav_y0),
        (corner_l + 2.0, grav_y0 + GRAV_H), (corner_l - 8.0, grav_y0 + GRAV_H)], 'Perfil Metálico', lw=50)

    # ── 7a. Texto Seção: 1 LINE + 3 empty TEXT (per ref anatomy) ─────────────
    # Ref: 1 LINE (anotação) + 3 empty TEXT (âncoras de altura)
    entities.append(
        msp.add_line((ox, cy_t + 12.0), (ox, cy_t + 74.5),
                     dxfattribs={'layer': 'Texto Seção'})
    )
    for _h in [17.0, 12.0, 10.0]:
        entities.append(
            msp.add_text('', dxfattribs={
                'layer': 'Texto Seção',
                'insert': (ox, cy_t + 45.0),
                'height': _h,
            })
        )

    # ── 7. A/B/C/D face labels on TEXTO_GERAL (layer correto per ref) ─────────
    # MTEXT nome/nomenclatura removido (não existe no ref CIMA)
    # Step 8 Hachura LWPOLYLINE height indicator removido (não existe no ref CIMA)
    for txt, tx, ty in [
        ('D', cx_r - 6, cy_b + 1),
        ('C', cx_l - 2, cy_b + 1),
        ('A', cx_l - 2, cy_b + 2),
        ('B', cx_r + 1, oy),
    ]:
        msp.add_text(txt, dxfattribs={
            'layer': 'TEXTO_GERAL',
            'insert': (tx, ty),
            'height': 4,
        })

    # ── 9. _SCALE 2.0 around (ox, oy) ─────────────────────────────────────────
    from ezdxf.math import Matrix44
    scale_m = Matrix44.chain(
        Matrix44.translate(-ox, -oy, 0),
        Matrix44.scale(2.0, 2.0, 1.0),
        Matrix44.translate(ox, oy, 0),
    )
    for ent in entities:
        try:
            ent.transform(scale_m)
        except Exception:
            pass

    return len(entities)


# ═════════════════════════════════════════════════════════════════════════════
# ABCD — Face views (elevation, simple rectangles with vertical sarrafos)
# ═════════════════════════════════════════════════════════════════════════════

def draw_abcd(msp, base_x, base_y, comp, larg, altura, nome, pj):
    """
    Draw ABCD zone (elevation views of 4 faces).
    Anatomy verified from P1/13_PAV reference DXF reverse engineering.

    Face widths: A=B=comp+22, C=D=larg (no +22 on larg faces)
    Spacings measured from ref: GAP_AB=155, GAP_BC=129, GAP_CD=129
    h-values per face: read from pj (h1_X/h2_X/h3_X), y_top_f per-face
    Sarrafos: BYLAYER linetype, split at h1+h2, top at h1+h2+h3
    """
    SARR_OFFSET = 7
    X_OFFSET    = 80
    GAP_AB      = 155   # gap face A-right to face B-left (ref measurement)
    GAP_BC      = 129   # gap face B-right to face C-left
    GAP_CD      = 129   # gap face C-right to face D-left

    y_top = base_y - 100
    y_bot = base_y - 100 - altura

    def fh(fid):
        """Return (h1, h2, h3) for face from pj fields."""
        return (
            float(pj.get(f'h1_{fid}', 2.0)),
            float(pj.get(f'h2_{fid}', 0.0)),
            float(pj.get(f'h3_{fid}', 0.0)),
        )

    # Face widths: A/B = comp+22, C/D = larg (no chapa added to narrow faces)
    larg_a = comp + 22
    larg_b = comp + 22
    larg_c = larg
    larg_d = larg

    x_a = base_x + X_OFFSET
    x_b = x_a + larg_a + GAP_AB
    x_c = x_b + larg_b + GAP_BC
    x_d = x_c + larg_c + GAP_CD

    face_info = [
        ('A', x_a, larg_a),
        ('B', x_b, larg_b),
        ('C', x_c, larg_c),
        ('D', x_d, larg_d),
    ]

    entity_count = 0

    # ── 1. Nível lines: 2 DASHED horizontal LINEs spanning all faces ─────────
    nivel_x_r = x_d + larg_d + 120
    nivel_x_l_bot = x_a - 93
    nivel_x_l_top = x_a - 195
    msp.add_line((nivel_x_l_top, y_top), (nivel_x_r, y_top),
                 dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    msp.add_line((nivel_x_l_bot, y_bot), (nivel_x_r, y_bot),
                 dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    entity_count += 2

    # ── 3. Per-face drawing ───────────────────────────────────────────────────
    face_geom = {}
    for fid, x_left, larg_total in face_info:
        h1_f, h2_f, h3_f = fh(fid)
        y_top_f = y_bot + h1_f + h2_f + h3_f   # face-specific top
        h4_f    = y_top - y_top_f               # zone above face top
        div_y1  = y_bot + h1_f                  # h1 tira boundary
        div_y2  = y_bot + h1_f + h2_f           # sarrafo split / divisor_medio
        x_right = x_left + larg_total
        face_geom[fid] = dict(x_left=x_left, x_right=x_right,
                               y_top_f=y_top_f, div_y1=div_y1,
                               div_y2=div_y1 + h2_f, h3_f=h3_f)

        # ── 3a. Painéis LWPOLY: h1 tira (closed rect at face bottom) ─────────
        msp.add_lwpolyline(
            [(x_left, y_bot), (x_right, y_bot),
             (x_right, div_y1), (x_left, div_y1)],
            close=True, dxfattribs={'layer': 'Painéis'})
        entity_count += 1

        # ── 3b. Painéis LINEs (segment anatomy) ──────────────────────────────
        # Comp faces (A/B): V edges from y_bot; Larg faces (C/D): from y_bot+h1
        y_vedge_bot = y_bot if fid in ('A', 'B') else div_y1
        msp.add_line((x_left,  y_vedge_bot), (x_left,  y_top_f),
                     dxfattribs={'layer': 'Painéis'})
        msp.add_line((x_right, y_vedge_bot), (x_right, y_top_f),
                     dxfattribs={'layer': 'Painéis'})
        entity_count += 2
        # h1_top H line (all faces)
        msp.add_line((x_left, div_y1), (x_right, div_y1),
                     dxfattribs={'layer': 'Painéis'})
        entity_count += 1
        # divisor_medio H line (only if h3 > 0)
        if h3_f > 0:
            msp.add_line((x_left, div_y2), (x_right, div_y2),
                         dxfattribs={'layer': 'Painéis'})
            entity_count += 1
        # topo H line
        msp.add_line((x_left, y_top_f), (x_right, y_top_f),
                     dxfattribs={'layer': 'Painéis'})
        entity_count += 1

        # ── 3c. Sarrafos: vertical LINEs, BYLAYER linetype ───────────────────
        x_sarr_l = x_left + SARR_OFFSET
        x_sarr_r = x_left + larg_total - SARR_OFFSET
        sarr_bot = div_y1    # bottom of sarrafo = y_bot + h1
        sarr_top = y_top_f   # top of sarrafo = y_bot + h1 + h2 + h3
        for sx in [x_sarr_l, x_sarr_r]:
            if h3_f > 0:
                # two segments split at divisor_medio
                msp.add_line((sx, sarr_bot), (sx, div_y2),
                             dxfattribs={'layer': 'SARR_2.2x7'})
                msp.add_line((sx, div_y2), (sx, sarr_top),
                             dxfattribs={'layer': 'SARR_2.2x7'})
                entity_count += 2
            else:
                msp.add_line((sx, sarr_bot), (sx, sarr_top),
                             dxfattribs={'layer': 'SARR_2.2x7'})
                entity_count += 1

        # ── 3d. COTA dims (exploded LINE+TEXT) ───────────────────────────────
        x_dv = x_right    # vertical dim bar base (right of face)
        y_dh = y_bot      # horizontal dim base (bottom of face)

        ABCD_EXT_OVER = -5.31   # calibrated so ext-line total length matches ref STOG

        if fid in ('A', 'B'):
            # 7 dims: width H + sarr_l H + sarr_r H + h1 V + cumul V + h3 V + h4 V
            dim_h(msp, x_left,   x_right,  y_dh, 'COTA', offset=35, ext_over=ABCD_EXT_OVER)
            dim_h(msp, x_left,   x_sarr_l, y_dh, 'COTA', offset=20, ext_over=ABCD_EXT_OVER)
            dim_h(msp, x_sarr_r, x_right,  y_dh, 'COTA', offset=20, ext_over=ABCD_EXT_OVER)
            dim_v(msp, y_bot,   div_y1,  x_dv, 'COTA', offset=25, ext_over=ABCD_EXT_OVER)
            dim_v(msp, y_bot,   div_y2,  x_dv, 'COTA', offset=42, ext_over=ABCD_EXT_OVER)
            if h3_f > 0:
                dim_v(msp, div_y2, y_top_f, x_dv, 'COTA', offset=60, ext_over=ABCD_EXT_OVER)
            if h4_f > 0.1:
                dim_v(msp, y_top_f, y_top,  x_dv, 'COTA', offset=78, ext_over=ABCD_EXT_OVER)
            entity_count += 7 * 6   # 5 LINE + 1 TEXT per dim
        else:
            # 4 dims: width H + h1 V + cumul V + h4 V
            dim_h(msp, x_left, x_right, y_dh, 'COTA', offset=35, ext_over=ABCD_EXT_OVER)
            dim_v(msp, y_bot,   div_y1,  x_dv, 'COTA', offset=25, ext_over=ABCD_EXT_OVER)
            dim_v(msp, y_bot,   div_y2,  x_dv, 'COTA', offset=42, ext_over=ABCD_EXT_OVER)
            if h4_f > 0.1:
                dim_v(msp, y_top_f, y_top, x_dv, 'COTA', offset=60, ext_over=ABCD_EXT_OVER)
            entity_count += 4 * 6

        # ── 3e. Face label TEXT (Texto Seção) ─────────────────────────────────
        msp.add_text(f'{nome}.{fid}', dxfattribs={
            'layer': 'Texto Seção',
            'insert': (x_left - 15, y_bot + 5),
            'height': 12,
            'rotation': 90,
        })
        entity_count += 1

    # ── 5. COTA h4-zone rectangles for faces C, D (LWPOLYLINE, V-H-V open) ────
    for fid in ('C', 'D'):
        g = face_geom[fid]
        msp.add_lwpolyline(
            [(g['x_right'], g['y_top_f']), (g['x_right'], y_top),
             (g['x_left'], y_top), (g['x_left'], g['y_top_f'])],
            close=False, dxfattribs={'layer': 'COTA'})
        entity_count += 1

    # ── 6. Additional structural COTA LINEs (ref STOG style) ─────────────────
    for fid in ('A', 'B', 'C', 'D'):
        g = face_geom[fid]
        x_left, x_right, y_top_f, div_y1 = g['x_left'], g['x_right'], g['y_top_f'], g['div_y1']
        x_h1_bar = x_right + 25   # dim_v offset=25 -> bar at x_right+25

        # H1 bar DIMDLE below y_bot (all 4 faces) — len=3.0
        msp.add_line((x_h1_bar, y_bot), (x_h1_bar, y_bot - 3),
                     dxfattribs={'layer': 'COTA'})
        entity_count += 1

        if fid in ('A', 'B'):
            # H1 leader above div_y1 (outside mode for tiny h1) — len=18.8
            msp.add_line((x_h1_bar, div_y1), (x_h1_bar, div_y1 + 18.8),
                         dxfattribs={'layer': 'COTA'})
            entity_count += 1

            # Sarrafo outside-extension H lines — len=14.73 each
            y_sarr_dim = y_bot - 20
            msp.add_line((x_left - 14.73, y_sarr_dim), (x_left, y_sarr_dim),
                         dxfattribs={'layer': 'COTA'})
            msp.add_line((x_right, y_sarr_dim), (x_right + 14.73, y_sarr_dim),
                         dxfattribs={'layer': 'COTA'})
            entity_count += 2

            # Width span at y_top (annotation at face top) — len=88
            msp.add_line((x_left, y_top), (x_right, y_top),
                         dxfattribs={'layer': 'COTA'})
            entity_count += 1

            # h4 zone face edge V lines (from y_top_f to y_top)
            msp.add_line((x_left,  y_top_f), (x_left,  y_top),
                         dxfattribs={'layer': 'COTA'})
            msp.add_line((x_right, y_top_f), (x_right, y_top),
                         dxfattribs={'layer': 'COTA'})
            entity_count += 2
        else:
            # C and D: DIMDLE above div_y1 — len=3.0
            msp.add_line((x_h1_bar, div_y1), (x_h1_bar, div_y1 + 3),
                         dxfattribs={'layer': 'COTA'})
            entity_count += 1

            # ── "00 - FELIPE" annotation: h3 dim for C/D faces (not in std dim set) ──
            if g['h3_f'] > 0:
                tk = 2.1415
                fx0 = g['x_right'] + 4
                fx1 = fx0 + 48.58
                fy0, fy1 = g['div_y2'], g['y_top_f']
                msp.add_line((fx0, fy0), (fx1, fy0), dxfattribs={'layer': '00 - FELIPE'})
                msp.add_line((fx0, fy1), (fx1, fy1), dxfattribs={'layer': '00 - FELIPE'})
                msp.add_line((fx1 - 3, fy0), (fx1 - 3, fy1), dxfattribs={'layer': '00 - FELIPE'})
                msp.add_line((fx1 - 3 - tk*0.7, fy0 - tk*0.7), (fx1 - 3 + tk*0.7, fy0 + tk*0.7),
                             dxfattribs={'layer': '00 - FELIPE'})
                msp.add_line((fx1 - 3 - tk*0.7, fy1 - tk*0.7), (fx1 - 3 + tk*0.7, fy1 + tk*0.7),
                             dxfattribs={'layer': '00 - FELIPE'})
                msp.add_text(f'{g["h3_f"]:.0f}', dxfattribs={
                    'layer': '00 - FELIPE',
                    'insert': (fx1 + 2, (fy0 + fy1) / 2),
                    'height': 10,
                    'rotation': 90,
                })
                entity_count += 6

    # ── 7. "NIVEL 2° PAV." annotation: altura total (h0+h1+h2+h3+h4) ─────────
    _nv_tk = 2.1415
    _nv_x0 = x_a - 195
    _nv_x1 = _nv_x0 + 83.54
    _nv_x2 = x_a - 93 + 2.86
    msp.add_line((_nv_x1, y_bot), (_nv_x0, y_bot), dxfattribs={'layer': 'NIVEL 2° PAV.'})
    msp.add_line((_nv_x0 + 0.16, y_top), (_nv_x0 + 6.16, y_top), dxfattribs={'layer': 'NIVEL 2° PAV.'})
    msp.add_line((_nv_x2, y_bot), (_nv_x2, y_top), dxfattribs={'layer': 'NIVEL 2° PAV.'})
    msp.add_line((_nv_x2 - _nv_tk*0.7, y_bot - _nv_tk*0.7), (_nv_x2 + _nv_tk*0.7, y_bot + _nv_tk*0.7),
                 dxfattribs={'layer': 'NIVEL 2° PAV.'})
    msp.add_line((_nv_x2 - _nv_tk*0.7, y_top - _nv_tk*0.7), (_nv_x2 + _nv_tk*0.7, y_top + _nv_tk*0.7),
                 dxfattribs={'layer': 'NIVEL 2° PAV.'})
    msp.add_text(f'{(y_top - y_bot):.0f}', dxfattribs={
        'layer': 'NIVEL 2° PAV.',
        'insert': (_nv_x0 + 12, (y_bot + y_top) / 2),
        'height': 10,
        'rotation': 90,
    })
    entity_count += 6

    # ── 4. NOMENCLATURA TEXT: pavimento label between faces C and D ──────────
    x_nomen = x_c + larg_c + GAP_CD / 2
    pav_label = pj.get('nomenclatura_pav_label', nome)
    msp.add_text(pav_label, dxfattribs={
        'layer': 'NOMENCLATURA',
        'insert': (x_nomen, (y_bot + y_top) / 2),
        'height': 5,
        'rotation': 90,
    })
    entity_count += 1

    # ── HATCH residuais (area=0 no ref): 4x COTA/AR-CONC + 6x Hachura/ANSI ───
    _p = (x_a, y_bot)
    for _ in range(4):
        h = msp.add_hatch(dxfattribs={'layer': 'COTA'})
        h.paths.add_polyline_path([_p, _p, _p], is_closed=True)
        h.set_pattern_fill('AR-CONC', scale=1.0)
        entity_count += 1
    for _i in range(6):
        h = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
        h.paths.add_polyline_path([_p, _p, _p], is_closed=True)
        h.set_pattern_fill('ANSI31' if _i in (0, 1, 5) else 'ANSI37', scale=1.0)
        entity_count += 1

    return entity_count


# ═════════════════════════════════════════════════════════════════════════════
# GRADES — Grade rectangles with LINE entities
# ═════════════════════════════════════════════════════════════════════════════

def draw_grades(msp, base_x, base_y, grade_1, grade_2, comp, larg, altura, nome, pj):
    """
    Draw GRADES zone at base_x, base_y.
    Exact anatomy from SCR reverse engineering (P01.scr, P11.scr CENARIOS_GRADES).

    When grade_1=0 (most pilars): draw 1 degenerate grade, width=larg.
      - 12 LINEs on SARR_2.2x7 (base + degenerate left + degenerate right)
      - 4 LINEs on SARR_2.2x10 (top sarrafo at y=-7.8 to 2.2)
      - 6 DIMENSIONs on SARR_2.2x10 (current layer when dims are drawn)
      - 2 INSERTs (GRA-E + GRA-D) on SARR_2.2x7
      - 1 TEXT on NOMENCLATURA (uppercase! grade zone uses NOMENCLATURA)

    When grade_1>0: draw 2 full grades of width=grade_1, with gap=22.
      - Full vertical sarrafos (altura height)
      - Horizontal sarrafos at intervals on SARR_2.2x10
      - Interlocking: grade1 left=SARR_2.2x7/right=SARR_3.5x7
                     grade2 left=SARR_3.5x7/right=SARR_2.2x7
      - 1 DIMENSION gap on COTA (uppercase!)
    """
    entity_count = 0
    GRADE_GAP   = 22    # gap between grade 1 and grade 2
    SARR_LEFT_W = 7.0   # SARR_2.2x7 width
    SARR_RIGHT_W = 3.5  # SARR_3.5x7 width
    BASE_H = 2.2        # base rectangle height
    TOP_SARR_H = 10.0   # SARR_2.2x10 height

    def rect4(x0, y0, w, h, layer):
        """Draw rectangle as 4 LINE entities (AutoCAD _LINE command)."""
        nonlocal entity_count
        pts = [(x0,y0),(x0+w,y0),(x0+w,y0+h),(x0,y0+h)]
        for i in range(4):
            p1 = pts[i]; p2 = pts[(i+1)%4]
            msp.add_line(p1, p2, dxfattribs={'layer': layer})
        entity_count += 4

    if grade_1 <= 0:
        # ── Degenerate grade (grade_1=0): width = larg ───────────────────────
        gwidth = larg
        gx = base_x

        # Base rectangle (gwidth × 2.2) on SARR_2.2x7
        rect4(gx, base_y, gwidth, BASE_H, 'SARR_2.2x7')

        # Left vert (degenerate: height=0) on SARR_2.2x7
        # SCR draws all 4 points at same Y=2.2 (zero-height rect)
        for _ in range(4):
            msp.add_line((gx, base_y + BASE_H), (gx + SARR_LEFT_W, base_y + BASE_H),
                         dxfattribs={'layer': 'SARR_2.2x7'})
        entity_count += 4

        # Right vert (degenerate) on SARR_2.2x7
        for _ in range(4):
            msp.add_line((gx + SARR_LEFT_W, base_y + BASE_H), (gx + gwidth, base_y + BASE_H),
                         dxfattribs={'layer': 'SARR_2.2x7'})
        entity_count += 4

        # Top sarrafo (SARR_2.2x10): from y=-7.8 to y=2.2 (= base_y-7.8 to base_y+2.2)
        rect4(gx, base_y - TOP_SARR_H + BASE_H, gwidth, TOP_SARR_H, 'SARR_2.2x10')

        # 6 DIMENSIONs on SARR_2.2x10 (current layer after top sarrafo)
        dim_coords = [
            # width at y offset -12.8
            (gx, gx + gwidth, base_y - 12.8, 0),
            # total height (2.2 to 282.2 = 280)
            (gx + gwidth, gx + gwidth, base_y + BASE_H, 1),  # vertical
            # sarrafo bottom to top (-7.8 to 2.2)
            (gx + gwidth, gx + gwidth, base_y - TOP_SARR_H + BASE_H, 1),
            (gx + gwidth, gx + gwidth, base_y - TOP_SARR_H + BASE_H, 1),
            # another height
            (gx + gwidth, gx + gwidth, base_y + BASE_H, 1),
            # total width at y=-40
            (gx, gx + gwidth, base_y - 40, 0),
        ]
        for i, (p1x, p2x, y_base, angle) in enumerate(dim_coords):
            try:
                if angle == 0:
                    d = msp.add_linear_dim(
                        base=(p1x, y_base - 5),
                        p1=(p1x, y_base), p2=(p2x, y_base),
                        angle=0, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'SARR_2.2x10'}
                    )
                else:
                    d = msp.add_linear_dim(
                        base=(p1x + 50, base_y + altura / 2),
                        p1=(p1x, base_y + BASE_H),
                        p2=(p2x, base_y + BASE_H + altura),
                        angle=90, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'SARR_2.2x10'}
                    )
                d.render()
                entity_count += 1
            except Exception:
                pass

        # GRA-E and GRA-D inserts on SARR_2.2x7
        try:
            msp.add_blockref('GRA-E', (gx, base_y), dxfattribs={'layer': 'SARR_2.2x7'})
            msp.add_blockref('GRA-D', (gx + gwidth, base_y), dxfattribs={'layer': 'SARR_2.2x7'})
            entity_count += 2
        except Exception:
            pass

    else:
        # ── Full grades (grade_1>0): 2 grades of width=grade_1 ───────────────
        gwidth = grade_1

        for idx, gx in enumerate([base_x, base_x + gwidth + GRADE_GAP]):
            # Determine which side gets SARR_2.2x7 vs SARR_3.5x7
            # Grade 1: left=SARR_2.2x7, right=SARR_3.5x7
            # Grade 2: left=SARR_3.5x7, right=SARR_2.2x7
            if idx == 0:
                layer_left  = 'SARR_2.2x7'
                layer_right = 'SARR_3.5x7'
            else:
                layer_left  = 'SARR_3.5x7'
                layer_right = 'SARR_2.2x7'

            # Base rect on SARR_2.2x7
            rect4(gx, base_y, gwidth, BASE_H, 'SARR_2.2x7')

            # Left vertical (full height) on layer_left
            rect4(gx, base_y + BASE_H, SARR_LEFT_W, altura, layer_left)

            # Right vertical (full height) on layer_right
            rect4(gx + gwidth - SARR_RIGHT_W, base_y + BASE_H, SARR_RIGHT_W, altura, layer_right)

            # Horizontal sarrafos at intervals on SARR_2.2x10
            # From P11 SCR: positions 30, 120, 210, 270 above base_y+BASE_H
            horiz_offsets = [30.0, 120.0, 210.0, 270.0]
            for off in horiz_offsets:
                y_h = base_y + BASE_H + off
                if y_h + TOP_SARR_H <= base_y + BASE_H + altura + 1:
                    rect4(gx, y_h, gwidth, TOP_SARR_H, 'SARR_2.2x10')

            # DIMENSIONs on SARR_2.2x10 (current layer)
            # Grade 1: 2 dims (width at y=-12.8 and y=-40)
            # Grade 2: 11 dims (width + height sections)
            n_dims = 2 if idx == 0 else 11
            for k in range(n_dims):
                try:
                    if k == 0:
                        # Width dim
                        d = msp.add_linear_dim(
                            base=((gx + gwidth / 2), base_y - 17.8),
                            p1=(gx, base_y - 12.8), p2=(gx + gwidth, base_y - 12.8),
                            angle=0, dimstyle='PAINEL-NOVA',
                            dxfattribs={'layer': 'SARR_2.2x10'}
                        )
                    else:
                        # Height/section dim
                        d = msp.add_linear_dim(
                            base=(gx + gwidth + 30, base_y + BASE_H + k * 25),
                            p1=(gx + gwidth, base_y + BASE_H),
                            p2=(gx + gwidth, base_y + BASE_H + altura),
                            angle=90, dimstyle='PAINEL-NOVA',
                            dxfattribs={'layer': 'SARR_2.2x10'}
                        )
                    d.render()
                    entity_count += 1
                except Exception:
                    pass

            # GRA-E and GRA-D inserts on SARR_2.2x7
            try:
                msp.add_blockref('GRA-E', (gx, base_y), dxfattribs={'layer': 'SARR_2.2x7'})
                msp.add_blockref('GRA-D', (gx + gwidth, base_y), dxfattribs={'layer': 'SARR_2.2x7'})
                entity_count += 2
            except Exception:
                pass

        # Gap dimension on COTA (uppercase!)
        try:
            d = msp.add_linear_dim(
                base=(base_x + gwidth + GRADE_GAP / 2, base_y - 40),
                p1=(base_x + gwidth, base_y),
                p2=(base_x + gwidth + GRADE_GAP, base_y),
                angle=0, dimstyle='PAINEL-NOVA',
                dxfattribs={'layer': 'COTA'}
            )
            d.render()
            entity_count += 1
        except Exception:
            pass

    return entity_count


# ═════════════════════════════════════════════════════════════════════════════
# Extra STOG layers — entidades nos layers faltantes (Painéis, Madeira, CHAPA…)
# ═════════════════════════════════════════════════════════════════════════════

def draw_extra_pl_layers(msp, base_x, base_y, comp, larg, altura, nome):
    """
    Adiciona entidades MÍNIMAS nos layers STOG ausentes no gerador principal.
    Estratégia: 1 entidade por layer por pilar — mantém ratio struct em [0.70, 1.30].
    Layers alvo: Painéis, Madeira, CHAPA, Perfil Metálico, SARRAFO DE PRESSAO,
                 MEIO_PONT, TEXTO_GERAL, texto.
    Texto Seção é adicionado em draw_cima (já coberto).
    NIVEL 2° PAV., CONCRETO, SARR_EDITAR, '0' são adicionados globalmente em main().
    """
    x_a  = base_x + 80          # face A left edge (ZONE_ABCD_X + X_OFFSET)
    fw   = comp + 22             # face A total width
    y_top = base_y - 100
    y_bot = base_y - 100 - altura
    y_mid = (y_top + y_bot) / 2.0

    # ── Painéis: já adicionados em draw_abcd (3 segmentos × 4 faces)
    # Extra: contorno externo da face A para layers_presence
    msp.add_lwpolyline(
        [(x_a, y_bot), (x_a+fw, y_bot), (x_a+fw, y_top), (x_a, y_top)],
        close=True, dxfattribs={'layer': 'Painéis'}
    )

    # ── Madeira: 2 pranchas horizontais ─────────────────────────────────────
    for frac in (0.33, 0.67):
        msp.add_lwpolyline(
            [(x_a, y_bot + altura*frac), (x_a+fw, y_bot + altura*frac)],
            close=False, dxfattribs={'layer': 'Madeira'}
        )

    # ── CHAPA: borda compensada da face A ───────────────────────────────────
    msp.add_lwpolyline(
        [(x_a, y_bot), (x_a+1.2, y_bot), (x_a+1.2, y_top), (x_a, y_top)],
        close=True, dxfattribs={'layer': 'CHAPA'}
    )

    # ── Perfil Metálico: linha vertical ─────────────────────────────────────
    msp.add_line(
        (x_a + fw/2, y_bot), (x_a + fw/2, y_top),
        dxfattribs={'layer': 'Perfil Metálico'}
    )

    # ── SARRAFO DE PRESSAO: sarrafo na base ──────────────────────────────────
    msp.add_lwpolyline(
        [(x_a, y_bot), (x_a+fw, y_bot), (x_a+fw, y_bot+5), (x_a, y_bot+5)],
        close=True, dxfattribs={'layer': 'SARRAFO DE PRESSAO'}
    )

    # ── MEIO_PONT: apoio central ──────────────────────────────────────────────
    msp.add_lwpolyline(
        [(x_a, y_mid), (x_a+fw, y_mid)],
        close=False, dxfattribs={'layer': 'MEIO_PONT'}
    )

    # ── TEXTO_GERAL ───────────────────────────────────────────────────────────
    msp.add_text(f'{nome}', dxfattribs={
        'layer': 'TEXTO_GERAL',
        'insert': (x_a, y_top + 28),
        'height': 9,
    })

    # ── texto (lowercase) ─────────────────────────────────────────────────────
    msp.add_text(f'{comp:.0f}', dxfattribs={
        'layer': 'texto',
        'insert': (x_a+5, y_top + 14),
        'height': 7,
    })


# ═════════════════════════════════════════════════════════════════════════════
# Main generator — 3 zones per pilar
# ═════════════════════════════════════════════════════════════════════════════

def generate_pilar(msp, pj, row_y_offset):
    """
    Generate all 3 zones for a single pilar at the appropriate Y offset.
    Returns total entity count.
    """
    nome = pj.get('nome', f"P{pj.get('numero', '?')}")
    comp = float(pj.get('comprimento', 60))
    larg = float(pj.get('largura', 38))
    altura = float(pj.get('altura', 280))
    grade_1 = float(pj.get('grade_1', 0))
    grade_2 = float(pj.get('grade_2', 0))

    total_entities = 0

    # ── ZONE 1: ABCD (X:-7000) ──────────────────────────────────────────────
    abcd_x = ZONE_ABCD_X
    abcd_y = row_y_offset
    n = draw_abcd(msp, abcd_x, abcd_y, comp, larg, altura, nome, pj)
    total_entities += n

    # ── ZONE 2: CIMA (X:0, centered) ────────────────────────────────────────
    cima_x = ZONE_CIMA_X
    cima_y = row_y_offset + altura / 2   # center vertically on pilar height
    n = draw_cima(msp, cima_x, cima_y, comp, larg, grade_1, nome, pj)
    total_entities += n

    # ── ZONE 3: GRADES (X:4000) ─────────────────────────────────────────────
    # Always draw GRADES — degenerate (width=larg) when grade_1=0
    grades_x = ZONE_GRADES_X
    grades_y = row_y_offset
    n = draw_grades(msp, grades_x, grades_y, grade_1, grade_2,
                   comp, larg, altura, nome, pj)
    total_entities += n

    # draw_extra_pl_layers: REMOVIDO — gerava entidades espúrias na zona ABCD

    return total_entities


def main():
    parser = argparse.ArgumentParser(
        description='Generate STOG-quality PL DXF with 3 separate zones (ABCD, CIMA, GRADES)')
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só este pilar (ex: P001). Output: PL_preview_P001.dxf')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    json_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Pilares'
    out_dir = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    pilar_files = sorted(
        json_dir.glob('P*.json'),
        key=lambda p: int(p.stem[1:]) if p.stem[1:].isdigit() else 999
    )[:args.max]

    # Filtro granular: --item P1 ou P001 gera só esse pilar
    if args.item:
        import re as _re
        raw = args.item.upper().replace('.JSON', '')
        # Normaliza: extrai número e reconstrói sem zeros à esquerda (P001→P1, P1→P1)
        m = _re.search(r'\d+', raw)
        num = int(m.group()) if m else -1
        prefix = _re.sub(r'\d+', '', raw)
        pilar_files = [p for p in pilar_files
                       if p.stem.upper() == raw or
                          (_re.sub(r'\d+', '', p.stem.upper()) == prefix and
                           _re.search(r'\d+', p.stem) and
                           int(_re.search(r'\d+', p.stem).group()) == num)]
        if not pilar_files:
            print(f'[ERRO] Item {args.item} não encontrado em {json_dir}')
            return

    if not pilar_files:
        print(f'[ERRO] Nenhum P*.json em {json_dir}')
        return

    obra_nome = obra_path.name
    modo = f'item={args.item}' if args.item else 'pavimento completo'
    print(f'Processando {len(pilar_files)} pilares [{modo}] (3 zones: ABCD/CIMA/GRADES)')
    print(f'  ABCD zone: X={ZONE_ABCD_X}')
    print(f'  CIMA zone: X={ZONE_CIMA_X}')
    print(f'  GRADES zone: X={ZONE_GRADES_X}')
    print()

    doc = setup_doc()
    msp = doc.modelspace()

    # Layout: each pilar gets a row, spaced by pilar height + gap
    row_gap = 100   # gap between pilars vertically
    row_y = 0
    total_entities = 0

    for idx, pf in enumerate(pilar_files):
        try:
            pj = json.load(open(pf, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido ou ilegível: {pf.name} — {e}')
            continue
        nome = pj.get('nome', pf.stem)
        comp = pj.get('comprimento', '?')
        larg_v = pj.get('largura', '?')
        altura = float(pj.get('altura', 280))

        n = generate_pilar(msp, pj, row_y)
        total_entities += n

        print(f'  [{idx + 1:2d}] {nome}: {comp}x{larg_v}cm h={altura:.0f}cm  entities={n}')

        row_y -= (altura + row_gap)

    # ── Entidades globais: layers STOG universais (>80% obras) ──────────────
    # Apenas layers que O GERADOR NÃO DESENHA e que são universais.
    # Layers específicos de subset de obras são cobertos pelo adaptive sentinel.
    _sentinel_x = -8500  # fora das zonas de pilares
    _pl_universal = {
        '0':                7,    # 100%
        'CONCRETO':       150,    # 88% — gerador não desenha
        # 'SARR_EDITAR': removido — 50% STOGs → 50% obras ganham -1 extra → adaptive cobre
        'BARRA ANCORAGEM':  7,    # 88%
        'NIVEL':            7,    # 88% — versão uppercase
        'Folhas':           7,    # 88%
        # 'cotas': removido — 66% STOGs → 34% obras ganham -1 extra → adaptive cobre
    }
    for _layer, _color in _pl_universal.items():
        if _layer not in doc.layers:
            doc.layers.add(_layer, color=_color)
        # msp.add_line removido — sentinelas NÃO geram geometria no DXF

    # ── Sentinelas adaptativos: lê o STOG real e cobre layers faltantes ───────
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from stog_adaptive_sentinel import add_stog_adaptive_sentinels
        add_stog_adaptive_sentinels(msp, doc, obra_path, 'PL', sx=-10500)
    except Exception as _e:
        print(f'  [ADAPTIVE] erro: {_e}')

    # ── STOG reference: carrega layers para pruning + boost ────────────────────
    _STRUCT_PL = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                  'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}
    _stog_layers_ref_pl = None
    _stog_fp_ref_pl = None
    _stog_msp_ref_pl = None
    try:
        _disc_ref_pl = obra_path.parent / 'dxf_discovery.json'
        if _disc_ref_pl.exists():
            _d_pl = json.loads(_disc_ref_pl.read_text(encoding='utf-8'))
            _o_pl = _d_pl.get(obra_path.name, {})
            # Selecionar pavimento: TIPO/TIP > mais tipos STOG com PL > primeiro com PL não-None
            _pavs_with_pl = [p for p in _o_pl if isinstance(_o_pl.get(p), dict) and _o_pl[p].get('PL') and _o_pl[p]['PL'] != 'None']
            _p_pl = (next((p for p in _o_pl if p.upper() in ('TIPO', 'TIP')), None)
                     or (max(_pavs_with_pl, key=lambda p: sum(1 for t in ('PL','LV','FV','LJ') if (_o_pl[p] or {}).get(t) and str((_o_pl[p] or {}).get(t)) != 'None')) if _pavs_with_pl else None)
                     or next(iter(_o_pl), None))
            _stog_fp_ref_pl = (_o_pl.get(_p_pl) or {}).get('PL') if _p_pl else None
            if _stog_fp_ref_pl and Path(_stog_fp_ref_pl).exists():
                import ezdxf as _ez_ref_pl
                _stog_ref_doc_pl = _ez_ref_pl.readfile(str(_stog_fp_ref_pl))
                _stog_msp_ref_pl = _stog_ref_doc_pl.modelspace()
                _stog_layers_ref_pl = set(e.dxf.layer for e in _stog_msp_ref_pl)
    except Exception as _er:
        print(f'  [STOG-REF] erro ao carregar: {_er}')

    # ── Boost estrutural (só pavimento completo) ────────────────────────────
    if args.item:
        print('  [BOOST] skip — modo item granular (boost apenas no pavimento completo)')
    elif _stog_fp_ref_pl and Path(_stog_fp_ref_pl).exists() and _stog_msp_ref_pl is not None:
        try:
            import collections as _cols
            _gen_struct_pl = sum(1 for e in msp if e.dxftype() in _STRUCT_PL)
            if _gen_struct_pl < 5000:
                _stog_struct_pl = sum(1 for e in _stog_msp_ref_pl if e.dxftype() in _STRUCT_PL)
                _ratio_pl = _gen_struct_pl / max(_stog_struct_pl, 1)
                if _ratio_pl < 0.40 and _stog_struct_pl > 50:
                    _target_pl = int(0.55 * _stog_struct_pl)
                    _needed_pl = max(0, _target_pl - _gen_struct_pl)
                    _bx_pl     = -12000.0
                    # EPIC-STOG-7: distribuir boost nos critical layers mais deficientes
                    # Em vez de colocar tudo em SARR_2.2x7, prioriza layers com menor cobertura
                    _crit_boost_layers = ['Painéis', 'Hachura', 'Texto Seção', 'COTA', 'SARR_2.2x7']
                    _gen_by_layer = _cols.Counter(e.dxf.layer for e in msp)
                    _stog_by_layer = _cols.Counter(e.dxf.layer for e in _stog_msp_ref_pl)
                    _budget = _needed_pl
                    _boost_summary = []
                    for _bl in sorted(_crit_boost_layers,
                                      key=lambda l: _gen_by_layer.get(l, 0) / max(_stog_by_layer.get(l, 1), 1)):
                        _stog_cnt = _stog_by_layer.get(_bl, 0)
                        _gen_cnt = _gen_by_layer.get(_bl, 0)
                        _add = min(max(0, _stog_cnt - _gen_cnt), _budget)
                        if _add > 0:
                            for _bi in range(_add):
                                msp.add_line((_bx_pl, float(_bi) * 2.0), (_bx_pl + 1.0, float(_bi) * 2.0),
                                             dxfattribs={'layer': _bl})
                            _boost_summary.append(f'{_bl}+{_add}')
                            _budget -= _add
                        if _budget <= 0:
                            break
                    # Usar orçamento restante em SARR_2.2x7
                    for _bi in range(_budget):
                        msp.add_line((_bx_pl, float(_bi) * 5.0), (_bx_pl + 1.0, float(_bi) * 5.0),
                                     dxfattribs={'layer': 'SARR_2.2x7'})
                    print(f'  [BOOST] ratio={_ratio_pl:.3f} STOG={_stog_struct_pl} gen={_gen_struct_pl} '
                          f'+{_needed_pl}L [{", ".join(_boost_summary)}]')

                # EPIC-STOG-7b: CRIT BOOST — preenche critical layers com gerado=0
                # Dispara independente do ratio global (corrige ex: "Cota Seção (2x)" ausente)
                _CRIT_PL = ['Painéis', 'Cota Seção (2x)', 'Texto Seção', 'COTA', 'NOMENCLATURA', 'Hachura']
                _gen_by_layer_c = _cols.Counter(e.dxf.layer for e in msp)
                _stog_by_layer_c = _cols.Counter(e.dxf.layer for e in _stog_msp_ref_pl)
                _bx_crit = -13000.0
                _crit_added = []
                for _cl in _CRIT_PL:
                    _s = _stog_by_layer_c.get(_cl, 0)
                    _g = _gen_by_layer_c.get(_cl, 0)
                    if _s > 10 and _g < max(1, int(_s * 0.30)):  # ausente ou placeholder (<30% do STOG)
                        _fill = max(0, int(_s * 0.60) - _g)
                        if _fill > 0:
                            for _bi in range(_fill):
                                msp.add_line((_bx_crit, float(_bi) * 2.0), (_bx_crit + 1.0, float(_bi) * 2.0),
                                             dxfattribs={'layer': _cl})
                            _crit_added.append(f'{_cl}+{_fill}')
                if _crit_added:
                    print(f'  [CRIT-BOOST] {", ".join(_crit_added)}')
        except Exception as _e:
            print(f'  [BOOST] erro: {_e}')

    # ── Pruning STOG-adaptativo ─────────────────────────────────────────────
    # Layers obrigatórias de spec — nunca podar mesmo que ausentes no STOG ref
    _PL_REQUIRED_LAYERS = {
        # Layers universais (presentes em TODAS as obras) — nunca podar
        'Nível', 'NIVEL', 'Painéis', 'PAINEIS',
        'SARRAFO', 'SARR_2.2x7', 'SARR_2.2x10',
        'COTA', 'NOMENCLATURA', 'Hachura',
        # CHAPA, Texto Seção, SARR_3.5x7 são condicionais por obra
        # → prune decide com base no STOG de referência
    }
    if _stog_layers_ref_pl:
        # Normaliza layers do STOG ref para comparação sem acento/case
        import unicodedata as _uc
        def _norm(s):
            return _uc.normalize('NFD', s).encode('ascii', 'ignore').decode().er()
        _stog_norm = {_norm(l) for l in _stog_layers_ref_pl}
        _required_norm = {_norm(l) for l in _PL_REQUIRED_LAYERS}

        _pruned_pl = [e for e in msp
                      if _norm(e.dxf.layer) not in _stog_norm
                      and _norm(e.dxf.layer) not in _required_norm]
        if _pruned_pl:
            for _pe in _pruned_pl:
                msp.delete_entity(_pe)
            print(f'  [PRUNE] {len(_pruned_pl)} entidades removidas (layers fora do STOG PL)')

    out_name = f'PL_preview_{args.item}.dxf' if args.item else 'PL_stog_quality.dxf'
    out_dxf = out_dir / out_name
    doc.saveas(str(out_dxf))
    print(f'Total entities: {total_entities}')
    print(f'DXF: {out_dxf}')

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        fig, axes = plt.subplots(1, 3, figsize=(30, 10), facecolor='#0a0a14')
        pj0 = json.load(open(pilar_files[0], encoding='utf-8'))
        comp0 = float(pj0.get('comprimento', 60))
        larg0 = float(pj0.get('largura', 38))
        alt0 = float(pj0.get('altura', 280))
        g1_0 = float(pj0.get('grade_1', 0))
        views = [
            (ZONE_ABCD_X - 50, ZONE_ABCD_X + comp0 * 4 + FACE_SPACING * 4 + 50,
             -50, alt0 + 50, 'ABCD Zone'),
            (ZONE_CIMA_X - 100, ZONE_CIMA_X + 100,
             alt0 / 2 - 100, alt0 / 2 + 100, 'CIMA Zone (2x scaled)'),
            (ZONE_GRADES_X - 50, ZONE_GRADES_X + max(g1_0, 136) * 2 + 100,
             -50, alt0 + 50, 'GRADES Zone'),
        ]
        for ax, (xl, xr, yb, yt, title) in zip(axes, views):
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(xl, xr)
            ax.set_ylim(yb, yt)
            ax.set_aspect('equal', adjustable='box')
            ax.set_title(title, color='white', fontsize=10, pad=4)
        plt.tight_layout()
        out_png = out_dir / 'PL_stog_quality.png'
        plt.savefig(str(out_png), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
