#!/usr/bin/env python3
"""
gerar_lv_dxf_stog.py — Gerador STOG-quality LV DXF (Vigas Laterais, sem AutoCAD)
==================================================================================
Refactored based on real SCR anatomy (cad-scr-anatomy-lv.md):
  - Sarrafo distribution by panel height (h<15, 15-30, 30-80, >=80)
  - Grade mode: horizontal SARR_2.2x7 + vertical SARR_2.2x3.5 legs
  - Visao de Corte with MLINE-style sarrafos, BARRA_ANCORAGEM, blocks
  - 7cm inset on first/last panels for horizontal sarrafos
  - Correct layers: SARR_2.2x7, SARR_2.2x5, SARR_2.2x3.5, SARRAFO_2_2X7,
    BARRA_ANCORAGEM, HACHURACONCRETO

JSON input (Fase-4_Sincronizacao/JSON_Vigas_Laterais/V*_A.json):
  total_width  = b   (largura da secao transversal, cm)
  total_height = h   (altura lateral dos paineis, cm)
  panels[].width = comprimento de cada segmento de painel original

Uso:
  python scripts/gerar_lv_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/gerar_lv_dxf_stog.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, re
from pathlib import Path
import ezdxf

# ── Constantes de layout (calibradas nos DXFs STOG) ────────────────────────
GAP_ROW_LV     = 100    # gap vertical entre linhas de vigas (cm)
NOM_ABOVE      = 9      # y = painel_top + NOM_ABOVE -> NOMENCLATURA
DIM_BELOW      = 37     # y = painel_bottom - DIM_BELOW -> cotas paineis individuais
DIM_TOTAL_BELOW= 60     # y = painel_bottom - DIM_TOTAL_BELOW -> cota total
DIM_H_RIGHT    = 28     # x = painel_right + DIM_H_RIGHT -> cota h_lateral vertical
GAP_AB         = 50     # gap horizontal entre Face A (right) e Face B (left)
NOM_H          = 16.5   # altura texto NOMENCLATURA
PID_H          = 12.0   # altura texto panel-ID interno

# ── Modulo de paineis LV (engenharia reversa NIK SUNSET Laje Tecnica) ───────
PAINEL_MODULO_LV = 122   # modulo painel lateral STOG (cm)
PAINEL_MIN_LV    = 30    # largura minima de painel (abaixo -> agrega no anterior)

# ── Sarrafo constants from SCR anatomy ────────────────────────────────────────
LV_SARR_LAYER  = 'SARR_3.5x7'
LV_SARR_W      = 3.5    # largura de cada sarrafo (cm)
LV_SARR_INSET  = 15.0   # inset das bordas extremas para SARR_3.5x7 (cm)
SARR_INSET_H   = 7.0    # inset from panel edge for horizontal sarrafos on first/last panels

# ── Detalhe de secao transversal ─────────────────────────────────────────────
SECT_W         = 160    # largura reservada para o detalhe de secao (cm)
SECT_GAP       = 30     # gap entre secao e Face A
SECT_PANEL_W   = 4      # espessura do painel na secao (Paineis layer)
SECT_BOARD_W   = 14     # espessura tabua externa (Madeira layer)

# ── Cards de folha ───────────────────────────────────────────────────────────
CARD_W     = 1485
CARD_H     = 1050
CARD_IN_DX = 75
CARD_IN_DY = 40
CARD_GAP   = 100
CARD_Y_GAP = 200

# ── Layers STOG LV ───────────────────────────────────────────────────────────
LAYERS = {
    'Painéis':          200,
    'COTA':             241,
    'NOMENCLATURA':       7,
    '5':                  5,
    'Folhas':           255,
    'CARIMBO':          255,
    LV_SARR_LAYER:       81,   # SARR_3.5x7
    'SARR_2.2x7':        40,
    'SARR_2.2x5':        40,
    'SARR_2.2x3.5':      40,
    'CONCRETO':         251,
    'Hachura':          251,
    'Madeira':          126,
    'barrote':          126,
    'SCO-___-LAJ':      224,
    'TENSOR':           224,
    'presilha':         224,
    'Forcador':         224,
    'Escoras':          224,
    'Defpoints':          7,
    '0':                  7,
    'detalhes':           7,
    'Texto Seção':        7,
    'Cota Seção (2x)':  241,
    'texto':              7,
    'REAPROVEITAMENTO': 251,
    # VC-specific layers from SCR anatomy
    'SARRAFO_2_2X7':     40,
    'BARRA_ANCORAGEM':  126,
    'HACHURACONCRETO':  251,
    'ESTRUTURACAO':       7,
}


# ──────────────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────────────

def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0   # sem unidades definidas (igual ao FV aprovado)
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # Dimstyle PAINEL
    if 'PAINEL' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL')
    else:
        ds = doc.dimstyles.get('PAINEL')
    ds.set_arrows('OBLIQUE', 'OBLIQUE')
    ds.dxf.dimasz  = 3.0
    ds.dxf.dimtxt  = 10.0
    ds.dxf.dimgap  = 3.0
    ds.dxf.dimexe  = 3.0
    ds.dxf.dimexo  = 3.0
    ds.dxf.dimclrd = 4
    ds.dxf.dimclrt = 240
    ds.dxf.dimclre = 4
    ds.dxf.dimtad  = 1
    ds.dxf.dimtih  = 0

    # Dimstyle SECAO2X
    if 'SECAO2X' not in doc.dimstyles:
        ds2 = doc.dimstyles.new('SECAO2X')
    else:
        ds2 = doc.dimstyles.get('SECAO2X')
    ds2.set_arrows('OBLIQUE', 'OBLIQUE')
    ds2.dxf.dimasz  = 5.0
    ds2.dxf.dimtxt  = 7.0
    ds2.dxf.dimgap  = 2.0
    ds2.dxf.dimexe  = 3.0
    ds2.dxf.dimexo  = 3.0
    ds2.dxf.dimclrd = 4
    ds2.dxf.dimclrt = 1
    ds2.dxf.dimclre = 4
    ds2.dxf.dimtad  = 3
    ds2.dxf.dimtih  = 0

    # Block definitions for VC (Visao de Corte)
    _define_vc_blocks(doc)

    return doc


def _define_vc_blocks(doc):
    """Define block references used in Visao de Corte (VC) SCR anatomy."""
    block_names = ['PAR_ESQ', 'PAR_FUNDO_ESQ', 'PAR_FUNDO_DIR',
                   'par_int_esq', 'par_int_dir']
    for bname in block_names:
        if bname not in doc.blocks:
            blk = doc.blocks.new(name=bname)
            # Simple screw/bolt representation: cross mark 2cm
            sz = 1.0
            blk.add_line((-sz, -sz), (sz, sz), dxfattribs={'layer': '0'})
            blk.add_line((-sz, sz), (sz, -sz), dxfattribs={'layer': '0'})


# ──────────────────────────────────────────────────────────────────────────────
# Distribuicao de paineis LV
# ──────────────────────────────────────────────────────────────────────────────

def extract_panels_from_json(panels_json, laje_central_alt_global=0.0):
    """Extrai dados reais dos paineis do JSON.
    Retorna lista de dicts: [{width, height1, height2, grade_h1, grade_h2, laje_central_alt, reuse, panel_type}, ...]
    """
    panels = []
    for p in (panels_json or []):
        w = float(p.get('width', 0))
        if w <= 0:
            continue
        lca = float(p.get('laje_central_alt', laje_central_alt_global) or laje_central_alt_global)
        panels.append({
            'width':            w,
            'height1':          float(p.get('height1', 0)),
            'height2':          float(p.get('height2', 0)),
            'grade_h1':         float(p.get('grade_h1', 0) or 0),
            'grade_h2':         float(p.get('grade_h2', 0) or 0),
            'laje_central_alt': lca,
            'reuse':            bool(p.get('reuse', False)),
            'panel_type':       str(p.get('panel_type', 'Sarrafeado')),
        })
    return panels


# ──────────────────────────────────────────────────────────────────────────────
# Primitivos de desenho
# ──────────────────────────────────────────────────────────────────────────────

def add_text(msp, x, y, text, height, layer, halign=0, valign=0):
    attribs = {'insert': (x, y), 'height': height, 'layer': layer}
    if halign or valign:
        attribs['halign'] = halign
        attribs['valign'] = valign
        attribs['align_point'] = (x, y)
    msp.add_text(text, dxfattribs=attribs)


def draw_panel_lines(msp, x0, y0, pw, h):
    """4 LINE entities por painel LV (borda inferior, superior, esquerda, direita)."""
    a = {'layer': 'Painéis'}
    msp.add_line((x0,    y0),   (x0+pw, y0),   dxfattribs=a)   # bottom
    msp.add_line((x0,    y0+h), (x0+pw, y0+h), dxfattribs=a)   # top
    msp.add_line((x0,    y0),   (x0,    y0+h), dxfattribs=a)   # left
    msp.add_line((x0+pw, y0),   (x0+pw, y0+h), dxfattribs=a)   # right


# ──────────────────────────────────────────────────────────────────────────────
# Sarrafo distribution by height (SCR anatomy rules)
# ──────────────────────────────────────────────────────────────────────────────

def _get_sarrafo_positions(h):
    """Return (layer_name, sarrafo_width, positions_from_bottom) based on panel height h.

    SCR anatomy rules:
      h < 15cm:  2x SARR_2.2x5 at 5cm from edges
      h 15-30:   2x SARR_2.2x7 at 7cm from edges
      h 30-80:   4x SARR_2.2x7 at 7cm edges + center +/- 3.5cm
      h >= 80:   8x SARR_2.2x7 at 7cm edges + center +/- 3.5 + quarter +/- 3.5
    """
    if h < 15:
        layer = 'SARR_2.2x5'
        sw = 5.0
        positions = [5.0, h - 5.0]
    elif h < 30:
        layer = 'SARR_2.2x7'
        sw = 7.0
        positions = [7.0, h - 7.0]
    elif h < 80:
        layer = 'SARR_2.2x7'
        sw = 7.0
        center = h / 2.0
        positions = [7.0, center - 3.5, center + 3.5, h - 7.0]
    else:
        layer = 'SARR_2.2x7'
        sw = 7.0
        center = h / 2.0
        quarter = h / 4.0
        three_q = 3 * h / 4.0
        positions = [
            7.0,
            quarter - 3.5, quarter + 3.5,
            center - 3.5, center + 3.5,
            three_q - 3.5, three_q + 3.5,
            h - 7.0,
        ]
    # Remove duplicate or out-of-range positions
    positions = sorted(set(p for p in positions if 0.5 < p < h - 0.5))
    return layer, sw, positions


def draw_sarrafos_by_height(msp, x0, y0, h, pw, layer, sarr_w, positions,
                            is_first, is_last):
    """Draw horizontal sarrafo rectangles for a single panel.

    Each sarrafo is a rectangle sarr_w tall (2.2cm), spanning the panel width.
    On first panel: 7cm inset from left edge.
    On last panel: 7cm inset from right edge.
    """
    x_left = x0 + (SARR_INSET_H if is_first else 0)
    x_right = x0 + pw - (SARR_INSET_H if is_last else 0)
    if x_right <= x_left + 1.0:
        return

    for y_pos in positions:
        # Sarrafo rectangle: 2.2cm tall, centered at y_pos
        y_bot = y0 + y_pos - 1.1
        y_top = y0 + y_pos + 1.1
        # Draw as 4 lines (matching LINE entity style of STOG)
        a = {'layer': layer}
        msp.add_line((x_left, y_bot), (x_right, y_bot), dxfattribs=a)  # bottom
        msp.add_line((x_left, y_top), (x_right, y_top), dxfattribs=a)  # top
        msp.add_line((x_left, y_bot), (x_left, y_top), dxfattribs=a)   # left
        msp.add_line((x_right, y_bot), (x_right, y_top), dxfattribs=a) # right


def draw_sarr_lv_vertical_pairs(msp, x0, y0, h, panel_widths):
    """SARR_3.5x7 vertical pairs at outer edges ONLY.

    SCR anatomy calibration: the real STOG has very few SARR_3.5x7 entities
    (~105 for 22 vigas = ~2-3 per face). Only outer edge pairs are drawn;
    divisor-zone sarrafos are handled by the horizontal sarrafo distribution.
    """
    L = sum(panel_widths)
    s35 = LV_SARR_LAYER    # 'SARR_3.5x7'
    h_inner = h - 2.2

    if L < 2 * LV_SARR_INSET:
        return

    def line35(x_abs, h_use):
        msp.add_line((x_abs, y0), (x_abs, y0 + h_use), dxfattribs={'layer': s35})

    def bot35(xl_abs, xr_abs):
        msp.add_line((xl_abs, y0), (xr_abs, y0), dxfattribs={'layer': s35})

    # Left edge pair: [15, 18.5]
    xl = x0 + LV_SARR_INSET
    xr = xl + LV_SARR_W
    if xr < x0 + L + 0.1:
        line35(xl, h)
        line35(xr, h_inner)
        bot35(xl, xr)

    # Right edge pair: [L-18.5, L-15]
    xr = x0 + L - LV_SARR_INSET
    xl = xr - LV_SARR_W
    if xl > x0 - 0.1:
        line35(xl, h_inner)
        line35(xr, h)
        bot35(xl, xr)


def draw_grade_mode(msp, x_cur, y_grade_top, pw, grade_h,
                    is_first, is_last):
    """Draw grade (Grade panel type) elements.

    Grade mode anatomy from SCR:
    - Horizontal rectangle 2.2cm tall at top (layer SARR_2.2x7)
    - Two vertical rectangles 3.5cm wide descending (layer SARR_2.2x3.5)
    - Height = grade_h - 2.2, inset 15cm from edges
    """
    if grade_h <= 2.2:
        return

    # Horizontal bar at top: full panel width, 2.2cm tall
    x_gi = x_cur + (SARR_INSET_H if is_first else 0)
    x_gf = x_cur + pw - (SARR_INSET_H if is_last else 0)
    if x_gf <= x_gi:
        return

    # Horizontal rect (SARR_2.2x7 layer)
    a22 = {'layer': 'SARR_2.2x7'}
    msp.add_line((x_gi, y_grade_top - 2.2), (x_gf, y_grade_top - 2.2), dxfattribs=a22)
    msp.add_line((x_gi, y_grade_top),       (x_gf, y_grade_top),       dxfattribs=a22)
    msp.add_line((x_gi, y_grade_top - 2.2), (x_gi, y_grade_top),       dxfattribs=a22)
    msp.add_line((x_gf, y_grade_top - 2.2), (x_gf, y_grade_top),       dxfattribs=a22)

    # Vertical legs (SARR_2.2x3.5 layer)
    leg_h = grade_h - 2.2
    leg_w = 3.5
    inset_leg = 15.0  # 15cm inset from edges
    a35 = {'layer': 'SARR_2.2x3.5'}

    y_leg_top = y_grade_top - 2.2
    y_leg_bot = y_leg_top - leg_h

    # Left leg
    xl = x_cur + inset_leg
    if xl + leg_w < x_cur + pw:
        msp.add_line((xl, y_leg_bot), (xl + leg_w, y_leg_bot), dxfattribs=a35)
        msp.add_line((xl, y_leg_top), (xl + leg_w, y_leg_top), dxfattribs=a35)
        msp.add_line((xl, y_leg_bot), (xl, y_leg_top),         dxfattribs=a35)
        msp.add_line((xl + leg_w, y_leg_bot), (xl + leg_w, y_leg_top), dxfattribs=a35)

    # Right leg
    xr = x_cur + pw - inset_leg - leg_w
    if xr > x_cur:
        msp.add_line((xr, y_leg_bot), (xr + leg_w, y_leg_bot), dxfattribs=a35)
        msp.add_line((xr, y_leg_top), (xr + leg_w, y_leg_top), dxfattribs=a35)
        msp.add_line((xr, y_leg_bot), (xr, y_leg_top),         dxfattribs=a35)
        msp.add_line((xr + leg_w, y_leg_bot), (xr + leg_w, y_leg_top), dxfattribs=a35)


# ──────────────────────────────────────────────────────────────────────────────
# Cotas (dimensoes)
# ──────────────────────────────────────────────────────────────────────────────

def dim_panel_lv(msp, x0, x1, y_base):
    """Cota horizontal de painel individual -- 1o nivel."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_BELOW),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0, dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_total_lv(msp, x0, x1, y_base):
    """Cota horizontal total da face -- 2o nivel."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_TOTAL_BELOW),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0, dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_h_lateral(msp, x_right, y0, h):
    """Cota vertical de h_lateral -- lado direito."""
    if h <= 0:
        return
    try:
        x_base = x_right + DIM_H_RIGHT
        d = msp.add_linear_dim(
            base=(x_base, y0),
            p1=(x_right, y0), p2=(x_right, y0 + h),
            angle=90, dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Detalhe de secao transversal (Visao de Corte)
# ──────────────────────────────────────────────────────────────────────────────

def draw_section_detail(msp, x_center, y0, b, h, viga_nome='', b_alma=19,
                        h_A=None, h_B=None):
    """Detalhe de secao transversal -- ALL STOG elements (eng. reversa DXF V22).

    Enhanced with SCR anatomy VC elements:
    - MLINE-style double lines for sarrafos (pairs 4.4cm apart) on SARRAFO_2_2X7
    - BARRA_ANCORAGEM rectangles connecting faces
    - Block inserts: PAR_ESQ, PAR_FUNDO_ESQ, PAR_FUNDO_DIR, par_int_esq, par_int_dir
    - HACHURACONCRETO between faces
    """
    CAP_H = 4.4

    # X anchors (confirmed DXF V22)
    x_ml_l = x_center - 32   # Madeira L left
    x_ml_r = x_center - 18   # Madeira L right / Paineis L left
    x_pl_r = x_center - 14   # Paineis L right = concreto left (x_cl)
    x_cl   = x_center - 14   # concreto left
    x_wr   = x_center + 24   # web right (x_cl + 38)
    x_pr_r = x_center + 28   # Paineis R right
    x_mr_r = x_center + 42   # Madeira R right
    x_fr   = x_center + 24 + b  # flange right (varies with b)

    # Heights reflect faces A and B
    h_left      = h_A if h_A is not None else (h + 8)
    h_flange_bot = max(h - 16, CAP_H + 5)
    h_right     = h_B if h_B is not None else max(h - 20, h_flange_bot)
    h_right     = max(h_right, h_flange_bot)

    la = {'layer': 'Madeira'}
    lp = {'layer': 'Painéis'}
    l0 = {'layer': '0'}

    # ═══════════════════════════════════════════════════════════════════════
    # 1. BARROTE (layer 'barrote') -- base horizontal
    # ═══════════════════════════════════════════════════════════════════════
    bw2 = (140 + b) / 2
    msp.add_lwpolyline(
        [(x_center - bw2, y0-20), (x_center + bw2, y0-20),
         (x_center + bw2, y0),    (x_center - bw2, y0)],
        close=True, dxfattribs={'layer': 'barrote'}
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. SCO-___-LAJ (layer 'SCO-LAJ') -- strip on top of barrote
    # ═══════════════════════════════════════════════════════════════════════
    sco_l = x_center - bw2 + 19
    sco_r = x_center + bw2 - 9
    msp.add_lwpolyline(
        [(sco_l, y0-3.2), (sco_r, y0-3.2), (sco_r, y0), (sco_l, y0)],
        close=True, dxfattribs={'layer': 'SCO-___-LAJ'}
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. MADEIRA -- 9 LWPOLYLINEs (boards + caps + bases)
    # ═══════════════════════════════════════════════════════════════════════
    # 3a. Madeira LEFT main board (14cm x h_left)
    msp.add_lwpolyline(
        [(x_ml_l, y0), (x_ml_r, y0), (x_ml_r, y0+h_left), (x_ml_l, y0+h_left)],
        close=True, dxfattribs=la)
    # 3b. Madeira RIGHT main board
    msp.add_lwpolyline(
        [(x_pr_r, y0), (x_mr_r, y0), (x_mr_r, y0+h_right), (x_pr_r, y0+h_right)],
        close=True, dxfattribs=la)
    # 3c. LEFT base plate (20cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_ml_l-20, y0), (x_ml_l, y0), (x_ml_l, y0+CAP_H), (x_ml_l-20, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3d. RIGHT base plate (20cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_mr_r, y0), (x_mr_r+20, y0), (x_mr_r+20, y0+CAP_H), (x_mr_r, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3e. LEFT board bottom cap (14cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_ml_l, y0), (x_ml_r, y0), (x_ml_r, y0+CAP_H), (x_ml_l, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3f. LEFT board top cap
    msp.add_lwpolyline(
        [(x_ml_l, y0+h_left-CAP_H), (x_ml_r, y0+h_left-CAP_H),
         (x_ml_r, y0+h_left),       (x_ml_l, y0+h_left)],
        close=True, dxfattribs=la)
    # 3g. RIGHT board top cap
    msp.add_lwpolyline(
        [(x_pr_r, y0+h_right-CAP_H), (x_mr_r, y0+h_right-CAP_H),
         (x_mr_r, y0+h_right),       (x_pr_r, y0+h_right)],
        close=True, dxfattribs=la)
    # 3h. Concrete-left base (10cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_cl, y0), (x_cl+10, y0), (x_cl+10, y0+CAP_H), (x_cl, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3i. Web-right base (10cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_wr-10, y0), (x_wr, y0), (x_wr, y0+CAP_H), (x_wr-10, y0+CAP_H)],
        close=True, dxfattribs=la)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. PAINEIS -- 4 LWPOLYLINEs
    # ═══════════════════════════════════════════════════════════════════════
    # 4a. Paineis LEFT (4cm x h_left)
    msp.add_lwpolyline(
        [(x_ml_r, y0), (x_pl_r, y0), (x_pl_r, y0+h_left), (x_ml_r, y0+h_left)],
        close=True, dxfattribs=lp)
    # 4b. Paineis RIGHT (4cm x h_right)
    msp.add_lwpolyline(
        [(x_wr, y0), (x_pr_r, y0), (x_pr_r, y0+h_right), (x_wr, y0+h_right)],
        close=True, dxfattribs=lp)
    # 4c. Paineis HORIZONTAL -- flange strip
    msp.add_lwpolyline(
        [(x_wr, y0+h_right),        (x_fr, y0+h_right),
         (x_fr, y0+h_flange_bot),   (x_wr, y0+h_flange_bot)],
        close=True, dxfattribs=lp)
    # 4d. Paineis BOTTOM STRIP -- base (38cm x 3.6cm)
    msp.add_lwpolyline(
        [(x_cl, y0+CAP_H), (x_wr, y0+CAP_H), (x_wr, y0+8), (x_cl, y0+8)],
        close=True, dxfattribs=lp)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. CONCRETO em L (layer 'CONCRETO') -- 6-vertex polygon
    # ═══════════════════════════════════════════════════════════════════════
    conc_pts = [
        (x_cl, y0+8),             (x_cl, y0+h+8),
        (x_fr, y0+h+8),           (x_fr, y0+h_flange_bot),
        (x_wr, y0+h_flange_bot),  (x_wr, y0+8),
    ]
    msp.add_lwpolyline(conc_pts, close=True, dxfattribs={'layer': 'CONCRETO'})
    # Hachura concreto
    hatch = msp.add_hatch(dxfattribs={'layer': 'COTA'})
    hatch.set_pattern_fill('ANSI31', scale=0.4)
    hatch.paths.add_polyline_path(conc_pts, is_closed=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 6. TENSOR + holders (layer 'TENSOR' / '0')
    # ═══════════════════════════════════════════════════════════════════════
    y_tensor = y0 + 50
    msp.add_line(
        (x_center - 57, y_tensor), (x_fr - 2, y_tensor),
        dxfattribs={'layer': 'TENSOR'}
    )

    lx1, lx2 = x_center - 52, x_center - 22
    rx1, rx2 = x_mr_r, x_mr_r + 30
    yt, yb = y0 + 56, y0 + 44
    yi1, yi2 = y0 + 51, y0 + 49

    for (a1, a2, tab_dir) in [(lx1, lx2, -1), (rx1, rx2, +1)]:
        msp.add_line((a1, yt), (a2, yt), dxfattribs=l0)
        msp.add_line((a1, yb), (a2, yb), dxfattribs=l0)
        outer_x = a1 if tab_dir == -1 else a2
        msp.add_line((outer_x, yt), (outer_x, yb), dxfattribs=l0)
        msp.add_line((a1, yi2), (a2, yi2), dxfattribs=l0)
        msp.add_line((a1, yi1), (a2, yi1), dxfattribs=l0)
        tx = outer_x + tab_dir * 2
        msp.add_line((outer_x, y0+47), (tx, y0+47), dxfattribs=l0)
        msp.add_line((tx, y0+53), (tx, y0+47), dxfattribs=l0)
        msp.add_line((outer_x, y0+53), (tx, y0+53), dxfattribs=l0)

    # ═══════════════════════════════════════════════════════════════════════
    # 7. PRESILHA (layer 'presilha')
    # ═══════════════════════════════════════════════════════════════════════
    lpr = {'layer': 'presilha'}
    for px in [x_center - 65, x_center + 75]:
        sz = 5
        msp.add_line((px-sz, y0-8-sz), (px+sz, y0-8+sz), dxfattribs=lpr)
        msp.add_line((px-sz, y0-8+sz), (px+sz, y0-8-sz), dxfattribs=lpr)

    # ═══════════════════════════════════════════════════════════════════════
    # 7b. HATCHING -- Wood (ANSI31) + Panel solid fills
    # ═══════════════════════════════════════════════════════════════════════
    def _hatch_rect(x1, y1, x2, y2, pattern='ANSI31', scale=0.5,
                    layer='Hachura', color=None):
        att = {'layer': layer}
        if color is not None:
            att['color'] = color
        ht = msp.add_hatch(dxfattribs=att)
        ht.set_pattern_fill(pattern, scale=scale)
        ht.paths.add_polyline_path(
            [(x1,y1),(x2,y1),(x2,y2),(x1,y2)], is_closed=True)

    # Wood boards ANSI31 hatching (7 fills)
    _hatch_rect(x_ml_l, y0, x_ml_r, y0+h_left)
    _hatch_rect(x_pr_r, y0, x_mr_r, y0+h_right)
    _hatch_rect(x_ml_l-20, y0, x_ml_l, y0+CAP_H)
    _hatch_rect(x_mr_r, y0, x_mr_r+20, y0+CAP_H)
    _hatch_rect(x_ml_l, y0+h_left-CAP_H, x_ml_r, y0+h_left)
    _hatch_rect(x_pr_r, y0+h_right-CAP_H, x_mr_r, y0+h_right)
    _hatch_rect(x_cl, y0, x_cl+10, y0+CAP_H)

    # Panel solid fills (4 fills)
    _hatch_rect(x_ml_r, y0, x_pl_r, y0+h_left, 'SOLID', 1.0, color=253)
    _hatch_rect(x_wr, y0, x_pr_r, y0+h_right, 'SOLID', 1.0, color=253)
    _hatch_rect(x_wr, y0+h_right, x_fr, y0+h-16, 'SOLID', 1.0, color=253)
    _hatch_rect(x_cl, y0+CAP_H, x_wr, y0+8, 'SOLID', 1.0, color=253)

    # ═══════════════════════════════════════════════════════════════════════
    # 8. MLINE-style sarrafos in VC (SARRAFO_2_2X7 layer)
    #    SCR anatomy: _MLINE SAR3 style, scale 4.400 -> pairs of lines 4.4cm apart
    # ═══════════════════════════════════════════════════════════════════════
    sar_vc = {'layer': 'SARRAFO_2_2X7'}
    # Get sarrafo positions for each face
    _, _, positions_A = _get_sarrafo_positions(h_left)
    _, _, positions_B = _get_sarrafo_positions(h_right)

    # Face A sarrafos (left panel in VC): vertical double lines at each sarrafo y
    # MLINE style: two vertical lines 4.4cm apart (panel width)
    for y_pos in positions_A:
        y_sarr = y0 + y_pos
        # Double line pair spanning panel thickness (x_ml_r to x_pl_r = 4cm)
        msp.add_line((x_ml_r, y_sarr - 2.2), (x_ml_r, y_sarr + 2.2), dxfattribs=sar_vc)
        msp.add_line((x_pl_r, y_sarr - 2.2), (x_pl_r, y_sarr + 2.2), dxfattribs=sar_vc)
        msp.add_line((x_ml_r, y_sarr - 2.2), (x_pl_r, y_sarr - 2.2), dxfattribs=sar_vc)
        msp.add_line((x_ml_r, y_sarr + 2.2), (x_pl_r, y_sarr + 2.2), dxfattribs=sar_vc)

    # Face B sarrafos (right panel in VC)
    for y_pos in positions_B:
        y_sarr = y0 + y_pos
        msp.add_line((x_wr, y_sarr - 2.2), (x_wr, y_sarr + 2.2), dxfattribs=sar_vc)
        msp.add_line((x_pr_r, y_sarr - 2.2), (x_pr_r, y_sarr + 2.2), dxfattribs=sar_vc)
        msp.add_line((x_wr, y_sarr - 2.2), (x_pr_r, y_sarr - 2.2), dxfattribs=sar_vc)
        msp.add_line((x_wr, y_sarr + 2.2), (x_pr_r, y_sarr + 2.2), dxfattribs=sar_vc)

    # ═══════════════════════════════════════════════════════════════════════
    # 9. BARRA_ANCORAGEM rectangles connecting faces A and B
    # ═══════════════════════════════════════════════════════════════════════
    ba_layer = {'layer': 'BARRA_ANCORAGEM'}
    # Anchor bars at ~1/3 and ~2/3 of the shorter height
    h_min = min(h_left, h_right)
    bar_positions = [h_min * 0.33, h_min * 0.67]
    bar_h = 2.0  # bar height
    for bp in bar_positions:
        yb = y0 + bp - bar_h / 2
        yt_bar = y0 + bp + bar_h / 2
        # Spans from Face A panel right edge to Face B panel left edge
        msp.add_line((x_pl_r, yb), (x_wr, yb), dxfattribs=ba_layer)
        msp.add_line((x_pl_r, yt_bar), (x_wr, yt_bar), dxfattribs=ba_layer)
        msp.add_line((x_pl_r, yb), (x_pl_r, yt_bar), dxfattribs=ba_layer)
        msp.add_line((x_wr, yb), (x_wr, yt_bar), dxfattribs=ba_layer)

    # ═══════════════════════════════════════════════════════════════════════
    # 10. Block inserts: PAR_ESQ, PAR_FUNDO_ESQ, PAR_FUNDO_DIR, par_int_esq, par_int_dir
    # ═══════════════════════════════════════════════════════════════════════
    # Screw/bolt positions from SCR anatomy
    mid_h = y0 + h_min / 2
    msp.add_blockref('PAR_ESQ', (x_ml_r, mid_h), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('PAR_FUNDO_ESQ', (x_pl_r, y0 + 10), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('PAR_FUNDO_DIR', (x_wr, y0 + 10), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('par_int_esq', (x_pl_r, mid_h + 10), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('par_int_dir', (x_wr, mid_h + 10), dxfattribs={'layer': 'Painéis'})

    # ═══════════════════════════════════════════════════════════════════════
    # 11. HACHURACONCRETO -- hatched region between faces
    # ═══════════════════════════════════════════════════════════════════════
    hc_layer = {'layer': 'HACHURACONCRETO'}
    # Rectangle between panel inner edges, from CAP_H to min height
    hc_pts = [(x_pl_r, y0+CAP_H), (x_wr, y0+CAP_H),
              (x_wr, y0+h_min), (x_pl_r, y0+h_min)]
    msp.add_lwpolyline(hc_pts, close=True, dxfattribs=hc_layer)
    ht_hc = msp.add_hatch(dxfattribs={'layer': 'HACHURACONCRETO'})
    ht_hc.set_pattern_fill('ANSI31', scale=0.3)
    ht_hc.paths.add_polyline_path(hc_pts, is_closed=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 12. TEXTOS 'detalhes' (layer 'detalhes')
    # ═══════════════════════════════════════════════════════════════════════
    add_text(msp, x_center - 29, y0 + 27.3, 'a', 9.6, 'detalhes')
    add_text(msp, x_center + 31, y0 + 27.3, 'b', 9.6, 'detalhes')
    add_text(msp, x_center - 4,  y0 + 10.5, 'c', 9.6, 'detalhes')

    # ═══════════════════════════════════════════════════════════════════════
    # 13. TEXTO SECAO -- title (layer 'Texto Secao')
    # ═══════════════════════════════════════════════════════════════════════
    if viga_nome:
        add_text(msp, x_center + 15, y0 + h + 8, f'{viga_nome}.A',
                 13.0, 'Texto Seção')
        add_text(msp, x_center - 10, y0 + h + 24,
                 f'{viga_nome} ({int(b_alma)}x{int(h)})',
                 10.0, 'Texto Seção')

    # ═══════════════════════════════════════════════════════════════════════
    # 14. DIMENSOES -- 6 cotas da secao transversal
    # ═══════════════════════════════════════════════════════════════════════
    dim_x_right = x_fr + 43

    def add_dim_v(p1, p2, base_x, layer='COTA', style='PAINEL'):
        try:
            d = msp.add_linear_dim(
                base=(base_x, p1[1]), p1=p1, p2=p2,
                angle=90, dimstyle=style, dxfattribs={'layer': layer})
            d.render()
        except Exception:
            pass

    def add_dim_h(p1, p2, base_y, layer='COTA', style='PAINEL'):
        try:
            d = msp.add_linear_dim(
                base=(p1[0], base_y), p1=p1, p2=p2,
                angle=0, dimstyle=style, dxfattribs={'layer': layer})
            d.render()
        except Exception:
            pass

    # 14a. Full LEFT height
    add_dim_v((x_ml_l-20, y0), (x_ml_l, y0+h_left), x_center - 108)
    # 14b. Concrete height
    add_dim_v((x_cl, y0+8), (x_cl, y0+h+8),
              x_center + 18, layer='Cota Seção (2x)', style='SECAO2X')
    # 14c. Tensor height
    add_dim_v((x_mr_r, y0), (x_mr_r, y0+50), x_fr + 3)
    # 14d. Madeira RIGHT height
    add_dim_v((x_mr_r, y0), (x_mr_r, y0+h_right), dim_x_right)
    # 14e. Flange height
    add_dim_v((x_fr, y0+h_flange_bot), (x_fr, y0+h+8), dim_x_right)
    # 14f. Web width (38cm)
    add_dim_h((x_cl, y0), (x_wr, y0), y0 - 45)


# ──────────────────────────────────────────────────────────────────────────────
# Face da viga (A ou B)
# ──────────────────────────────────────────────────────────────────────────────

def draw_lv_face(msp, x0, y0, panels, h, nome_face,
                 holes=None, pillar_left=None, pillar_right=None,
                 laje_sup=7.0, laje_inf=7.0):
    """Desenha uma face (A ou B) da viga lateral -- todos elementos visuais.
    panels: lista de dicts [{width, height1, height2, grade_h1, grade_h2, reuse, panel_type}, ...]
    holes: lista de aberturas [{active, width, height, position}, ...]
    pillar_left/right: dict {active, width, length}
    laje_sup/inf: alturas default de laje superior/inferior (cm)
    Retorna comprimento total da face.
    """
    panel_widths = [p['width'] for p in panels]
    comprimento = sum(panel_widths)
    n = len(panels)
    if comprimento <= 0 or h <= 0:
        return comprimento

    # ── 1. LAJE INFERIOR -- retangulo fechado com hachura POR PAINEL ─────
    if laje_inf > 0:
        x_cur = x0
        for p in panels:
            pw = p['width']
            pts = [(x_cur, y0-laje_inf), (x_cur+pw, y0-laje_inf),
                   (x_cur+pw, y0), (x_cur, y0)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            x_cur += pw

    # ── 2. LAJE SUPERIOR -- retangulo fechado com hachura POR PAINEL ─────
    if laje_sup > 0:
        x_cur = x0
        for p in panels:
            pw = p['width']
            pts = [(x_cur, y0+h), (x_cur+pw, y0+h),
                   (x_cur+pw, y0+h+laje_sup), (x_cur, y0+h+laje_sup)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            x_cur += pw

    # ── 3. Contornos dos paineis + lajes centrais + grades + sarrafos ───
    x_cur = x0
    for idx, p in enumerate(panels):
        pw = p['width']
        h1 = p['height1']
        h2 = p['height2']
        gh1 = p['grade_h1']
        gh2 = p['grade_h2']
        is_first = (idx == 0)
        is_last  = (idx == n - 1)
        panel_type = p.get('panel_type', 'Sarrafeado')
        is_reuse = p.get('reuse', False)

        lc_alt = p.get('laje_central_alt', 0)
        has_laje_central = (lc_alt > 0) or (h1 > 0 and h2 > 0 and abs(h1 - h2) > 0.5)

        # Positions in drawing space: scale proportionally when real dims > face height
        if lc_alt > 0:
            total_real = h1 + lc_alt + h2
            if total_real > 0:
                _s = h / total_real if total_real > h else 1.0
                h1_d   = h1 * _s
                lc_h_d = lc_alt * _s
            else:
                h1_d, lc_h_d = h1, lc_alt
        elif has_laje_central:
            h1_d   = h1
            lc_h_d = h - h1 - (h - h2) if h2 < h else h - h1
        else:
            h1_d, lc_h_d = h, 0

        # Contorno externo do painel
        draw_panel_lines(msp, x_cur, y0, pw, h)

        # REAPROVEITAMENTO hatch -- only when panel has reuse flag
        if is_reuse:
            pts_reuse = [(x_cur, y0), (x_cur+pw, y0),
                         (x_cur+pw, y0+h), (x_cur, y0+h)]
            ht_r = msp.add_hatch(dxfattribs={'layer': 'REAPROVEITAMENTO'})
            ht_r.set_pattern_fill('ANSI31', scale=0.8)
            ht_r.paths.add_polyline_path(pts_reuse, is_closed=True)

        if has_laje_central and lc_h_d > 0.5:
            # Laje central: retangulo fechado + hachura ANSI31
            laje_y = y0 + h1_d
            pts_lc = [(x_cur, laje_y), (x_cur+pw, laje_y),
                      (x_cur+pw, laje_y+lc_h_d), (x_cur, laje_y+lc_h_d)]
            msp.add_lwpolyline(pts_lc, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts_lc, is_closed=True)

        # ── Sarrafos / Grades for H1 zone ──────────────────────────────
        h1_zone = h1_d if has_laje_central else h
        if panel_type == 'Grade' and gh1 > 0:
            # Grade mode
            y_grade_top = y0 + h1_zone if has_laje_central else y0 + h
            draw_grade_mode(msp, x_cur, y_grade_top, pw, gh1, is_first, is_last)
        else:
            # Standard sarrafo mode: horizontal sarrafos by height
            sarr_layer, sarr_w, positions = _get_sarrafo_positions(h1_zone)
            draw_sarrafos_by_height(msp, x_cur, y0, h1_zone, pw,
                                    sarr_layer, sarr_w, positions,
                                    is_first, is_last)

        # ── Sarrafos / Grades for H2 zone (only with laje central) ────
        if has_laje_central and lc_h_d > 0.5:
            h2_zone = h - h1_d - lc_h_d
            y0_h2 = y0 + h1_d + lc_h_d
            if h2_zone > 2:
                if panel_type == 'Grade' and gh2 > 0:
                    draw_grade_mode(msp, x_cur, y0_h2 + h2_zone, pw, gh2,
                                    is_first, is_last)
                else:
                    sarr_layer2, sarr_w2, positions2 = _get_sarrafo_positions(h2_zone)
                    draw_sarrafos_by_height(msp, x_cur, y0_h2, h2_zone, pw,
                                            sarr_layer2, sarr_w2, positions2,
                                            is_first, is_last)

        # Divisor entre paineis
        if not is_last:
            msp.add_line((x_cur+pw, y0), (x_cur+pw, y0+h),
                         dxfattribs={'layer': 'Painéis'})

        x_cur += pw

    # ── 4. SARR_3.5x7 -- vertical pairs at edges and divisors ──────────
    draw_sarr_lv_vertical_pairs(msp, x0, y0, h, panel_widths)

    # ── 5. PILARES/OBSTACULOS -- retangulos hachurados nas bordas ─────────
    def _draw_pillar(px, py, pw_p, ph_p):
        pts = [(px, py), (px+pw_p, py), (px+pw_p, py+ph_p), (px, py+ph_p)]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={'layer': 'Painéis', 'linetype': 'DASHED'})
        ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
        ht.set_pattern_fill('ANSI31', scale=0.5)
        ht.paths.add_polyline_path(pts, is_closed=True)
        add_text(msp, px + pw_p/2, py + ph_p/2, 'PILAR',
                 5.0, '5', halign=1, valign=2)

    if pillar_left and pillar_left.get('active'):
        pw_pl = float(pillar_left.get('width', 0))
        pl_len = float(pillar_left.get('length', 0))
        if pw_pl > 0:
            _draw_pillar(x0 + pl_len, y0, pw_pl, h)

    if pillar_right and pillar_right.get('active'):
        pw_pr = float(pillar_right.get('width', 0))
        pr_len = float(pillar_right.get('length', 0))
        if pw_pr > 0:
            _draw_pillar(x0 + comprimento - pr_len - pw_pr, y0, pw_pr, h)

    # ── 6. NOMENCLATURA acima do topo ─────────────────────────────────────
    add_text(msp, x0 + 3, y0 + h + laje_sup + NOM_ABOVE, nome_face,
             NOM_H, 'NOMENCLATURA')

    # ── 7. IDs + info de painel + MTEXT ponteiro ─────────────────────────
    x_cur = x0
    for i, p in enumerate(panels):
        pw = p['width']
        cx = x_cur + pw / 2
        cy = y0 + h / 2
        add_text(msp, cx, cy + 4, str(i + 1), PID_H, '5', halign=1, valign=2)
        if pw >= 20:
            add_text(msp, cx, cy - PID_H + 2, f'{pw:.0f}',
                     7.0, '5', halign=1, valign=2)
        if pw >= 30:
            n_pont = max(2, round(pw / 24.4))
            msp.add_mtext(
                f'{n_pont} 1/2pont',
                dxfattribs={'layer': 'texto', 'char_height': 6.0,
                            'insert': (cx, cy - PID_H - 8, 0),
                            'attachment_point': 5})
        x_cur += pw

    # ── 8. Cotas horizontais individuais + total ─────────────────────────
    x_cur = x0
    for pw in panel_widths:
        dim_panel_lv(msp, x_cur, x_cur + pw, y0)
        x_cur += pw
    if len(panel_widths) > 1:
        dim_total_lv(msp, x0, x0 + comprimento, y0)

    # ── 9. COTAS VERTICAIS SEGMENTADAS (Laje Inf + Altura + Laje Sup) ────
    def _dim_seg_v(x_base, segments, side='left'):
        x_dim = x_base - DIM_H_RIGHT if side == 'left' else x_base + DIM_H_RIGHT
        y_cur = y0 - laje_inf
        for label, seg_h in segments:
            if seg_h <= 0:
                continue
            try:
                d = msp.add_linear_dim(
                    base=(x_dim, y_cur),
                    p1=(x_base, y_cur), p2=(x_base, y_cur + seg_h),
                    angle=90, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA'})
                d.render()
            except Exception:
                pass
            y_cur += seg_h

    p0 = panels[0]
    h1_0, h2_0 = p0['height1'], p0['height2']
    lc_alt_0 = p0.get('laje_central_alt', 0)
    has_lc = (lc_alt_0 > 0) or (h1_0 > 0 and h2_0 > 0 and abs(h1_0 - h2_0) > 0.5)
    if lc_alt_0 > 0:
        total_real_0 = h1_0 + lc_alt_0 + h2_0
        _s0 = h / total_real_0 if (total_real_0 > h and total_real_0 > 0) else 1.0
        h1_0_d = h1_0 * _s0
        lc_h   = lc_alt_0 * _s0
        h2_0_d = h2_0 * _s0
    else:
        h1_0_d = h1_0
        h2_0_d = h2_0
        lc_h = (h - h1_0 - (h - h2_0)) if has_lc and h2_0 < h else 0
    seg_left = [
        ('Laje Inf', laje_inf),
        ('Altura 1', h1_0_d if has_lc else h),
        ('Laje Central', max(lc_h, 0)),
        ('Altura 2', h2_0_d if has_lc else 0),
        ('Laje Sup', laje_sup),
    ]
    _dim_seg_v(x0, seg_left, 'left')

    # Lado direito (ultimo painel) -- cota total
    dim_h_lateral(msp, x0 + comprimento, y0 - laje_inf,
                  h + laje_inf + laje_sup)

    # ── 10. ABERTURAS -- retangulos fechados + hachura diagonal ────────────
    if holes:
        xr = x0 + comprimento
        for i, hole in enumerate(holes):
            if not hole.get('active'):
                continue
            hw = float(hole.get('width', 0))
            hh = float(hole.get('height', 0))
            hdist = float(hole.get('position', 0))
            if hw <= 0 or hh <= 0:
                continue
            if i == 0:    hx, hy = x0, y0 + h - hdist - hh
            elif i == 1:  hx, hy = x0, y0 + hdist
            elif i == 2:  hx, hy = xr - hw, y0 + h - hdist - hh
            elif i == 3:  hx, hy = xr - hw, y0 + hdist
            else: continue
            pts = [(hx, hy), (hx+hw, hy), (hx+hw, hy+hh), (hx, hy+hh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'Painéis', 'linetype': 'DASHED'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            add_text(msp, hx + hw/2, hy + hh/2, f'{hw:.0f}x{hh:.0f}',
                     7.0, '5', halign=1, valign=2)

    return comprimento


# ──────────────────────────────────────────────────────────────────────────────
# Viga lateral completa (secao + Face A + Face B)
# ──────────────────────────────────────────────────────────────────────────────

def draw_viga_lateral(msp, x_origin, y_top, viga_nome,
                      h_A, h_B, b, h_section=None, b_alma=19,
                      panels_A=None, panels_B=None,
                      holes_A=None, holes_B=None,
                      pillar_left_A=None, pillar_right_A=None,
                      pillar_left_B=None, pillar_right_B=None,
                      laje_sup=7.0, laje_inf=7.0):
    """Desenha uma viga lateral completa em uma linha horizontal.
    Positions: [Secao] [SECT_GAP] [Face A] [GAP_AB] [Face B]
    """
    h = max(h_A, h_B, 1.0)
    comp_A = sum(p['width'] for p in panels_A)
    comp_B = sum(p['width'] for p in panels_B)
    comprimento = max(comp_A, comp_B, 1.0)

    sect_total = max(SECT_W + SECT_GAP, int(b) + 178)
    x_A = x_origin + sect_total
    x_sect_center = max(x_origin + 40, x_A - 124 - int(b))

    h_sect = h_section if h_section else h_A
    y0_sect = y_top - h_A
    draw_section_detail(msp, x_sect_center, y0_sect, b, h_sect,
                        viga_nome=viga_nome, b_alma=b_alma,
                        h_A=h_A, h_B=h_B)

    y0_A = y_top - h_A
    draw_lv_face(msp, x_A, y0_A, panels_A, h_A, f'{viga_nome}.A',
                 holes=holes_A,
                 pillar_left=pillar_left_A, pillar_right=pillar_right_A,
                 laje_sup=laje_sup, laje_inf=laje_inf)

    x_B  = x_A + comprimento + GAP_AB
    y0_B = y_top - h_B
    draw_lv_face(msp, x_B, y0_B, panels_B, h_B, f'{viga_nome}.B',
                 holes=holes_B,
                 pillar_left=pillar_left_B, pillar_right=pillar_right_B,
                 laje_sup=laje_sup, laje_inf=laje_inf)

    x_max = x_B + comprimento + DIM_H_RIGHT + 40
    y_min = min(y0_A, y0_B) - laje_inf - DIM_TOTAL_BELOW - 15
    return x_max, y_min


# ──────────────────────────────────────────────────────────────────────────────
# Cards de folha
# ──────────────────────────────────────────────────────────────────────────────

def draw_cards(msp, x0, y_bottom, obra_nome=''):
    """Desenha 2 blocos Folhas 1485x1050 (bordas + carimbo)."""
    for i in range(2):
        cx = x0 + i * (CARD_W + CARD_GAP)
        cy = y_bottom
        pts = [(cx, cy), (cx+CARD_W, cy), (cx+CARD_W, cy+CARD_H), (cx, cy+CARD_H)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 50})
        cx2 = cx + CARD_IN_DX; cy2 = cy + CARD_IN_DY
        w2 = CARD_W - 2*CARD_IN_DX; h2 = CARD_H - 2*CARD_IN_DY
        msp.add_lwpolyline(
            [(cx2, cy2), (cx2+w2, cy2), (cx2+w2, cy2+h2), (cx2, cy2+h2)],
            close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 25}
        )
        cab_h = 80
        msp.add_line((cx, cy+cab_h), (cx+CARD_W, cy+cab_h),
                     dxfattribs={'layer': 'CARIMBO', 'lineweight': 35})
        mid_x = cx + CARD_W / 2
        for txt, ty, th in [
            ('NOVA SISTEMAS CONSTRUTIVOS', cy+cab_h/2+30, 14),
            ('STOG',                       cy+cab_h/2+12, 12),
            (obra_nome,                    cy+cab_h/2-5,  12),
            ('LATERAL DE VIGAS',           cy+cab_h/2-22, 14),
        ]:
            msp.add_text(txt, dxfattribs={'insert': (mid_x, ty), 'height': th, 'layer': 'CARIMBO'})
        msp.add_text(str(i+1), dxfattribs={
            'insert': (cx+CARD_W-60, cy+cab_h/2), 'height': 40, 'layer': 'CARIMBO'})


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Gera LV DXF STOG-quality a partir de JSON_Vigas_Laterais/')
    parser.add_argument('--obra', required=True,
                        help='Caminho da obra (ex: DADOS-OBRAS/Obra_TREINO_21)')
    parser.add_argument('--max', type=int, default=999,
                        help='Maximo de vigas a processar')
    parser.add_argument('--simulate', action='store_true',
                        help='Injeta dados de teste na 1a viga (aberturas, pilares, h1!=h2)')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    lv_dir    = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
    vs_path   = obra_path / 'Fase-4_Sincronizacao' / 'vigas_salvas.json'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    vigas_salvas = {}
    if vs_path.exists():
        vigas_salvas = json.load(open(vs_path, encoding='utf-8'))

    # Coletar arquivos V*_A.json e encontrar parceiro V*_B.json
    a_files = sorted(
        lv_dir.glob('V*_A.json'),
        key=lambda p: (re.search(r'\d+', p.stem).group().zfill(5), p.stem)
    )[:args.max]

    if not a_files:
        print(f'[ERRO] Nenhum V*_A.json em {lv_dir}')
        return

    vigas = []
    for af in a_files:
        vname = re.sub(r'_A$', '', af.stem)
        bf    = af.parent / f'{vname}_B.json'

        da = json.load(open(af, encoding='utf-8'))
        db = json.load(open(bf, encoding='utf-8')) if bf.exists() else da

        b = float(vigas_salvas.get(vname, {}).get('b', da.get('total_width', 14)))
        b_alma = float(da.get('total_width', b))

        comp_A = sum(float(p.get('width', 0)) for p in da.get('panels', []))
        comp_B = sum(float(p.get('width', 0)) for p in db.get('panels', []))
        comprimento = max(comp_A, comp_B, 1.0)

        h_raw = float(vigas_salvas.get(vname, {}).get('h', da.get('total_height', 38)))
        h_section = h_raw / 2.0
        h_A = h_section + 4
        h_B = max(h_section - 10, 10)

        lca_A = float(da.get('laje_central_alt', 0) or 0)
        lca_B = float(db.get('laje_central_alt', 0) or 0)
        panels_A = extract_panels_from_json(da.get('panels', []), lca_A)
        panels_B = extract_panels_from_json(db.get('panels', []), lca_B)

        pl_A = da.get('pillar_left', {})
        pr_A = da.get('pillar_right', {})
        pl_B = db.get('pillar_left', {})
        pr_B = db.get('pillar_right', {})

        if comprimento > 0 and (h_A > 0 or h_B > 0) and (panels_A or panels_B):
            if not panels_A:
                panels_A = panels_B
            if not panels_B:
                panels_B = panels_A
            vigas.append({
                'nome':     vname,
                'b':        b,
                'b_alma':   b_alma,
                'comp':     comprimento,
                'h_section': h_section,
                'h_A':      max(h_A, 1.0),
                'h_B':      max(h_B, 1.0),
                'holes_A':  da.get('holes', []),
                'holes_B':  db.get('holes', []),
                'panels_A': panels_A,
                'panels_B': panels_B,
                'pl_A': pl_A, 'pr_A': pr_A,
                'pl_B': pl_B, 'pr_B': pr_B,
            })

    if not vigas:
        print('[ERRO] Nenhuma viga valida encontrada'); return

    # ── Injetar dados de simulacao na 1a viga (--simulate) ─────────────
    if args.simulate and vigas:
        v0 = vigas[0]
        print(f'[SIMULATE] Injetando dados de teste em {v0["nome"]}')
        v0['holes_A'] = [
            {'active': True, 'width': 15, 'height': 10, 'position': 5},
            {'active': True, 'width': 12, 'height': 8,  'position': 3},
            {'active': True, 'width': 15, 'height': 10, 'position': 5},
            {'active': True, 'width': 12, 'height': 8,  'position': 3},
        ]
        v0['pl_A'] = {'active': True, 'width': 20, 'length': 10}
        v0['pr_A'] = {'active': True, 'width': 25, 'length': 15}
        if len(v0['panels_A']) >= 2:
            v0['panels_A'][1]['height1'] = v0['h_A'] * 0.6
            v0['panels_A'][1]['height2'] = v0['h_A'] * 0.8

    vigas.sort(key=lambda v: (-v['b'], -v['comp']))
    print(f'Processando {len(vigas)} vigas laterais -> LV_stog_quality.dxf')

    doc = setup_doc()
    msp = doc.modelspace()

    y_cursor    = 0.0
    x_max_all   = 0.0
    y_min_all   = 0.0

    for v in vigas:
        panels_A = v['panels_A']
        panels_B = v['panels_B']
        if not panels_A:
            continue

        h_max = max(v['h_A'], v['h_B'])
        n_panels = max(len(panels_A), len(panels_B))
        pw_list = [f"{p['width']:.0f}" for p in panels_A]

        x_max, y_min = draw_viga_lateral(
            msp,
            x_origin  = 0.0,
            y_top     = y_cursor,
            viga_nome = v['nome'],
            h_A       = v['h_A'],
            h_B       = v['h_B'],
            b         = v['b'],
            h_section = v.get('h_section'),
            b_alma    = v.get('b_alma', v['b']),
            panels_A  = panels_A,
            panels_B  = panels_B,
            holes_A   = v.get('holes_A'),
            holes_B   = v.get('holes_B'),
            pillar_left_A  = v.get('pl_A'),
            pillar_right_A = v.get('pr_A'),
            pillar_left_B  = v.get('pl_B'),
            pillar_right_B = v.get('pr_B'),
        )

        print(f'  {v["nome"]:8s}: comp={v["comp"]:.0f}cm  '
              f'h_A={v["h_A"]:.0f}  h_B={v["h_B"]:.0f}  '
              f'b={v["b"]:.0f}  paineis={n_panels}  widths=[{",".join(pw_list)}]')

        x_max_all = max(x_max_all, x_max)
        y_min_all = min(y_min_all, y_min)

        y_cursor -= h_max + NOM_ABOVE + DIM_TOTAL_BELOW + GAP_ROW_LV

    # ── Cards de folha acima das vigas ─────────────────────────────────────
    obra_nome = obra_path.name.replace('_', ' ')
    draw_cards(msp, 0, CARD_Y_GAP, obra_nome=obra_nome)

    # ── Salvar DXF ─────────────────────────────────────────────────────────
    import time
    ts = time.strftime('%H%M%S')
    out_dxf = out_dir / f'LV_stog_{ts}.dxf'
    try:
        doc.saveas(str(out_dxf))
    except PermissionError:
        out_dxf = out_dir / f'LV_stog_{ts}_b.dxf'
        doc.saveas(str(out_dxf))
    print(f'\nDXF: {out_dxf}')

    # ── PNG preview ─────────────────────────────────────────────────────────
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        v0 = vigas[0]
        h0 = max(v0['h_A'], v0['h_B'])
        y_first_bot = -(h0 + DIM_TOTAL_BELOW + 20)

        fig, axes = plt.subplots(1, 2, figsize=(28, 12), facecolor='#0a0a14')
        views = [
            ((-50, min(x_max_all + 50, 3000)),
             (y_cursor + (len(vigas)-4)*(h0+GAP_ROW_LV) - 50, 60),
             f'Detalhe -- primeiras vigas'),
            ((-50, max(x_max_all + 50, CARD_W*2 + CARD_GAP + 100)),
             (y_min_all - 50, CARD_Y_GAP + CARD_H + 50),
             f'Vista completa -- {len(vigas)} vigas'),
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
        out_png = out_dir / 'LV_stog_quality.png'
        plt.savefig(str(out_png), dpi=120, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
