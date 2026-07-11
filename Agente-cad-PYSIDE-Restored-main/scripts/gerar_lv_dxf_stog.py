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
import json, argparse, re, math
from pathlib import Path
import ezdxf
from visual_modes import apply_visual_mode

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from src.core.artifact_governance import guarded_saveas

_MOTOR_ID = "ROBOT_LV_N3_N4"
_MOTOR_SOURCES = [Path(__file__)]

# ── Constantes de layout (calibradas nos DXFs STOG) ────────────────────────
GAP_ROW_LV     = 100    # gap vertical entre linhas de vigas (cm)
NOM_ABOVE      = 9      # y = painel_top + NOM_ABOVE -> NOMENCLATURA
DIM_BELOW      = 37     # y = painel_bottom - DIM_BELOW -> cotas paineis individuais
DIM_TOTAL_BELOW= 60     # y = painel_bottom - DIM_TOTAL_BELOW -> cota total
DIM_H_RIGHT    = 28     # x = painel_right + DIM_H_RIGHT -> cota h_lateral vertical
GAP_AB     = 200    # gap horizontal entre Face A (right) e Face B (left)
LV_UNIT_GAP    = 200.0  # gap entre continuacoes/face_units no viewer dedicado
NOM_H          = 16.5   # altura texto NOMENCLATURA
PID_H          = 12.0   # altura texto panel-ID interno

# ── Modulo de paineis LV (engenharia reversa NIK SUNSET Laje Tecnica) ───────
PAINEL_MODULO_LV = 120   # modulo painel lateral STOG (cm) — reverso usa 120cm (não 122)
PAINEL_MIN_LV    = 7     # largura minima de painel real; abaixo disso = artefato de borda

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
LV_FACE_X0_MIN = 1800.0  # afasta A/B para o viewer isolar a visao-corte

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
    'Reaproveitamento': 251,   # mixed-case como no STOG real
    # VC-specific layers — nomes corrigidos para espelhar STOG real
    # SARRAFO_2_2X7 → SARR_2.2x7 (já na lista acima)
    # BARRA_ANCORAGEM → BARRA DE ANCORAGEM (já na lista acima)
    # HACHURACONCRETO → Hachura (já na lista acima)
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
    Retorna lista de dicts: [{width, height1, height2, grade_h1, grade_h2, laje_central_alt,
                               laje_sup_local, laje_inf_local, reuse, reuse_regions, panel_type}, ...]
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
            'laje_sup_local':   float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0),
            'laje_inf_local':   float(p.get('laje_inf_local', p.get('slab_bottom', 0)) or 0),
            'slab_top':         float(p.get('slab_top', p.get('laje_sup_local', 0)) or 0),
            'slab_bottom':      float(p.get('slab_bottom', p.get('laje_inf_local', 0)) or 0),
            'holes':            p.get('holes', []),
            'reuse':            bool(p.get('reuse', False)),
            'reuse_regions':    p.get('reuse_regions', []),
            'panel_type':       str(p.get('panel_type', 'Sarrafeado')),
        })
    return panels


def auto_distribute_panels(comprimento, panels_json, laje_central_alt_global=0.0):
    """Distribui paineis LV.

    PRIORIDADE 1 — JSON com painéis: usa as larguras do JSON diretamente.
      - Filtra trailing panels < PAINEL_MIN_LV (artefatos de borda da extração).
      - Preserva mini-painéis reais >= PAINEL_MIN_LV (8cm, 11.5cm, 23.5cm, etc.).

    PRIORIDADE 2 — Sem JSON: distribui por módulo PAINEL_MODULO_LV (120 cm).

    Retorna (panels, border_strip_width):
      - panels: lista de dicts no mesmo formato de extract_panels_from_json
      - border_strip_width: largura do trailing panel filtrado (0.0 se nenhum filtrado)
        → necessário para desenhar o border strip no Painéis layer (5 entities/face)
    """
    border_strip_w = 0.0
    if panels_json:
        # Usar larguras do JSON (fonte da verdade = engenharia reversa)
        panels = extract_panels_from_json(panels_json, laje_central_alt_global)
        # Filtrar trailing panels < PAINEL_MIN_LV (artefatos de borda, não painéis reais)
        # Guarda o último filtrado como border_strip_w para desenhar o contorno no DXF
        while len(panels) > 1 and panels[-1]['width'] < PAINEL_MIN_LV:
            border_strip_w = panels[-1]['width']
            panels.pop()
        if panels:
            return panels, border_strip_w

    if comprimento <= 0:
        return [], 0.0

    # Fallback: distribuição automática por módulo (quando JSON não tem painéis)
    n = max(1, math.ceil(comprimento / PAINEL_MODULO_LV))

    # Dados de altura/tipo do primeiro painel JSON como template
    base = {
        'height1': 0.0, 'height2': 0.0,
        'grade_h1': 0.0, 'grade_h2': 0.0,
        'laje_central_alt': laje_central_alt_global,
        'reuse': False,
        'panel_type': 'Sarrafeado',
    }

    # n-1 paineis de 120 cm + último painel com o restante
    w_last = comprimento - (n - 1) * PAINEL_MODULO_LV
    if w_last < PAINEL_MIN_LV and n > 1:
        # Absorve no penúltimo se o último for artefato de borda
        n -= 1
        w_last = comprimento - (n - 1) * PAINEL_MODULO_LV

    result = []
    for i in range(n):
        w = PAINEL_MODULO_LV if i < n - 1 else w_last
        result.append(dict(base, width=round(w, 2)))
    return result, 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Primitivos de desenho
# ──────────────────────────────────────────────────────────────────────────────

def add_text(msp, x, y, text, height, layer, halign=0, valign=0, color=None):
    attribs = {'insert': (x, y), 'height': height, 'layer': layer}
    if color not in (None, 256):
        try:
            attribs['color'] = int(color)
        except Exception:
            pass
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
        layer = 'SARR_2.2x7'  # merged with SARR_2.2x7 — 85%+ STOGs use SARR_2.2x7 for all heights
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
    """Draw horizontal sarrafo lines for a single panel.

    Each sarrafo is 1 LWPOLYLINE (centerline) per position — matches SCR anatomy
    (SCR draws 1 _PLINE per sarrafo, not a rectangle).
    On first panel: 7cm inset from left edge.
    On last panel: 7cm inset from right edge.
    """
    x_left = x0 + (SARR_INSET_H if is_first else 0)
    x_right = x0 + pw - (SARR_INSET_H if is_last else 0)
    if x_right <= x_left + 1.0:
        return

    for y_pos in positions:
        y_ctr = y0 + y_pos
        msp.add_lwpolyline([(x_left, y_ctr), (x_right, y_ctr)],
                           close=False, dxfattribs={'layer': layer})


def draw_sarrafo_spans(msp, x0, y0, panels, positions, layer):
    """Add 'span' PLINEs for each sarrafo position × each panel.
    Matches SCR anatomy: n_pos*n_panels extra LWPOLY per face (span count).
    """
    x_cur = x0
    n = len(panels)
    for i, p in enumerate(panels):
        pw = p['width']
        is_first = (i == 0)
        is_last = (i == n - 1)
        x_left = x_cur + (SARR_INSET_H if is_first else 0)
        x_right = x_cur + pw - (SARR_INSET_H if is_last else 0)
        if x_right > x_left + 1.0:
            for y_pos in positions:
                y_ctr = y0 + y_pos
                msp.add_lwpolyline([(x_left, y_ctr), (x_right, y_ctr)],
                                   close=False, dxfattribs={'layer': layer})
        x_cur += pw


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
                    is_first, is_last, layer_override=None):
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
    layer22 = layer_override or 'SARR_2.2x7'
    layer35 = layer_override or 'SARR_3.5x7'
    a22 = {'layer': layer22}
    msp.add_line((x_gi, y_grade_top - 2.2), (x_gf, y_grade_top - 2.2), dxfattribs=a22)
    msp.add_line((x_gi, y_grade_top),       (x_gf, y_grade_top),       dxfattribs=a22)
    msp.add_line((x_gi, y_grade_top - 2.2), (x_gi, y_grade_top),       dxfattribs=a22)
    msp.add_line((x_gf, y_grade_top - 2.2), (x_gf, y_grade_top),       dxfattribs=a22)

    # Vertical legs (SARR_3.5x7 layer — mesmo layer do STOG humano N2)
    leg_h = grade_h - 2.2
    leg_w = 3.5
    inset_leg = 15.0  # 15cm inset from edges
    a35 = {'layer': layer35}

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
                        h_A=None, h_B=None, skip_layers=None):
    """Detalhe de secao transversal -- ALL STOG elements (eng. reversa DXF V22).

    skip_layers: set of layer names to NOT draw (computed from STOG presence check).
    If a layer is in skip_layers it means the STOG doesn't use that layer, so
    drawing it would create an 'extra' layer penalty.

    Enhanced with SCR anatomy VC elements:
    - MLINE-style double lines for sarrafos (pairs 4.4cm apart) on SARRAFO_2_2X7
    - BARRA_ANCORAGEM rectangles connecting faces
    - Block inserts: PAR_ESQ, PAR_FUNDO_ESQ, PAR_FUNDO_DIR, par_int_esq, par_int_dir
    - HACHURACONCRETO between faces
    """
    if skip_layers is None:
        skip_layers = set()

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
    if 'barrote' not in skip_layers:
        msp.add_lwpolyline(
            [(x_center - bw2, y0-20), (x_center + bw2, y0-20),
             (x_center + bw2, y0),    (x_center - bw2, y0)],
            close=True, dxfattribs={'layer': 'barrote'}
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. SCO-___-LAJ (layer 'SCO-LAJ') -- strip on top of barrote
    # ═══════════════════════════════════════════════════════════════════════
    if 'SCO-___-LAJ' not in skip_layers:
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
    if 'TENSOR' not in skip_layers:
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
    if 'presilha' not in skip_layers:
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
    #    ezdxf não suporta MLINE → emite LINE no layer correto SARRAFO_2_2X7
    # ═══════════════════════════════════════════════════════════════════════
    sar_vc = {'layer': 'SARRAFO_2_2X7'}
    # Get sarrafo positions for each face
    _, _, positions_A = _get_sarrafo_positions(h_left)
    _, _, positions_B = _get_sarrafo_positions(h_right)

    # Face A sarrafos (left panel in VC): retângulo 4 linhas (top + bottom + 2 caps)
    # Reverso anatomy: 4 linhas por posição (sem center line — verificado empiricamente V8)
    for y_pos in positions_A:
        y_sarr = y0 + y_pos
        msp.add_line((x_ml_r, y_sarr + 2.2), (x_pl_r, y_sarr + 2.2), dxfattribs=sar_vc)  # top
        msp.add_line((x_ml_r, y_sarr - 2.2), (x_pl_r, y_sarr - 2.2), dxfattribs=sar_vc)  # bottom
        msp.add_line((x_ml_r, y_sarr - 2.2), (x_ml_r, y_sarr + 2.2), dxfattribs=sar_vc)  # left cap
        msp.add_line((x_pl_r, y_sarr - 2.2), (x_pl_r, y_sarr + 2.2), dxfattribs=sar_vc)  # right cap

    # Face B sarrafos (right panel in VC): mesmo padrão 4 linhas
    for y_pos in positions_B:
        y_sarr = y0 + y_pos
        msp.add_line((x_wr, y_sarr + 2.2), (x_pr_r, y_sarr + 2.2), dxfattribs=sar_vc)    # top
        msp.add_line((x_wr, y_sarr - 2.2), (x_pr_r, y_sarr - 2.2), dxfattribs=sar_vc)    # bottom
        msp.add_line((x_wr, y_sarr - 2.2), (x_wr, y_sarr + 2.2), dxfattribs=sar_vc)      # left cap
        msp.add_line((x_pr_r, y_sarr - 2.2), (x_pr_r, y_sarr + 2.2), dxfattribs=sar_vc)  # right cap

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
    #     Layer correto: HACHURACONCRETO (não Hachura genérico)
    # ═══════════════════════════════════════════════════════════════════════
    hc_pts = [(x_pl_r, y0+CAP_H), (x_wr, y0+CAP_H),
              (x_wr, y0+h_min), (x_pl_r, y0+h_min)]
    msp.add_lwpolyline(hc_pts, close=True, dxfattribs={'layer': 'HACHURACONCRETO'})
    ht_hc = msp.add_hatch(dxfattribs={'layer': 'HACHURACONCRETO'})
    ht_hc.set_pattern_fill('ANSI31', scale=0.3)
    ht_hc.paths.add_polyline_path(hc_pts, is_closed=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 12. TEXTOS 'detalhes' (layer 'detalhes') + pontalete em ESTRUTURACAO
    # ═══════════════════════════════════════════════════════════════════════
    add_text(msp, x_center - 29, y0 + 27.3, 'a', 9.6, 'detalhes')
    add_text(msp, x_center + 31, y0 + 27.3, 'b', 9.6, 'detalhes')
    add_text(msp, x_center - 4,  y0 + 10.5, 'c', 9.6, 'detalhes')
    # Texto pontalete no layer ESTRUTURACAO (exigido pelo spec LV-V12)
    add_text(msp, x_center - 4, y0 - 12, 'pontalete', 9.6, 'ESTRUTURACAO')

    # ═══════════════════════════════════════════════════════════════════════
    # 13. TEXTO SECAO -- title (layer 'Texto Seção')
    # ═══════════════════════════════════════════════════════════════════════
    if viga_nome and 'Texto Seção' not in skip_layers:
        add_text(msp, x_center + 15, y0 + h + 14, f'{viga_nome}.A',
                 8.0, 'Texto Seção')
        add_text(msp, x_center - 10, y0 + h + 34,
                 f'{viga_nome} ({int(b_alma)}x{int(h)})',
                 8.0, 'Texto Seção')

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
    # 14b. Concrete height — on 'Cota Seção (2x)', skip if STOG doesn't have this layer
    if 'Cota Seção (2x)' not in skip_layers:
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
                 laje_sup=7.0, laje_inf=7.0, border_strip_width=0.0,
                 skip_layers=None, nota_face=None, pontaletes_face=None,
                 fallback_panel_ids=True, nom_height=None,
                 reverse_grade_style=False, suppress_sarrafo_spans=False):
    """Desenha uma face (A ou B) da viga lateral -- todos elementos visuais.
    panels: lista de dicts [{width, height1, height2, grade_h1, grade_h2, reuse, panel_type}, ...]
    holes: lista de aberturas [{active, width, height, position}, ...]
    pillar_left/right: dict {active, width, length}
    laje_sup/inf: alturas default de laje superior/inferior (cm)
    skip_layers: set of layer names to skip (from STOG presence check)
    Retorna comprimento total da face.
    """
    if skip_layers is None:
        skip_layers = set()
    panel_widths = [p['width'] for p in panels]
    comprimento = sum(panel_widths)
    n = len(panels)
    if comprimento <= 0 or h <= 0:
        return comprimento

    # ── 1. LAJE INFERIOR -- retangulo fechado com hachura POR PAINEL ─────
    has_local_inf = any(
        float(p.get('laje_inf_local', p.get('slab_bottom', 0)) or 0) > 0
        for p in panels
    )
    has_laje_inf = has_local_inf or laje_inf > 0
    if has_laje_inf and 'SCO-___-LAJ' not in skip_layers:
        x_cur = x0
        for p in panels:
            pw = p['width']
            li = (
                float(p.get('laje_inf_local', p.get('slab_bottom', 0)) or 0)
                if has_local_inf else float(laje_inf or 0)
            )
            if li <= 0:
                x_cur += pw
                continue
            pts = [(x_cur, y0-li), (x_cur+pw, y0-li),
                   (x_cur+pw, y0), (x_cur, y0)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            x_cur += pw

    # ── 2. LAJE SUPERIOR -- retangulo fechado com hachura POR PAINEL ─────
    has_local_sup = any(
        float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0) > 0
        for p in panels
    )
    has_laje_sup = has_local_sup or laje_sup > 0
    if has_laje_sup and 'SCO-___-LAJ' not in skip_layers:
        x_cur = x0
        for p in panels:
            pw = p['width']
            ls = (
                float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0)
                if has_local_sup else float(laje_sup or 0)
            )
            # Painéis de degrau (P1) são mais baixos que h_face: sem laje acima
            _ph1 = float(p.get('height1', 0) or 0)
            if ls <= 0 or (0 < _ph1 < h - 5.0 and
                           float(p.get('laje_central_alt', 0) or 0) == 0):
                x_cur += pw
                continue
            pts = [(x_cur, y0+h), (x_cur+pw, y0+h),
                   (x_cur+pw, y0+h+ls), (x_cur, y0+h+ls)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
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

        # Contorno externo do painel: degrau (P1) usa height1 < h_face
        h_draw = h1 if (0 < h1 < h - 5.0 and not has_laje_central) else h
        draw_panel_lines(msp, x_cur, y0, pw, h_draw)

        # Reproduz somente as faixas detectadas no N2. O fallback de painel
        # inteiro atende fichas antigas que possuem apenas o booleano reuse.
        if is_reuse:
            reuse_regions = p.get('reuse_regions') or [
                {'x_offset': 0.0, 'y_offset': 0.0, 'width': pw, 'height': h_draw}
            ]
            for region in reuse_regions:
                rx1 = x_cur + max(0.0, float(region.get('x_offset', 0) or 0))
                ry1 = y0 + max(0.0, float(region.get('y_offset', 0) or 0))
                rw = max(0.0, float(region.get('width', pw) or 0))
                rh = max(0.0, float(region.get('height', h) or 0))
                rx2 = min(x_cur + pw, rx1 + rw)
                ry2 = min(y0 + h, ry1 + rh)
                if rx2 - rx1 <= 0.5 or ry2 - ry1 <= 0.5:
                    continue
                pts_reuse = [(rx1, ry1), (rx2, ry1),
                             (rx2, ry2), (rx1, ry2)]
                ht_reuse = msp.add_hatch(
                    dxfattribs={'layer': 'Reaproveitamento'})
                ht_reuse.set_pattern_fill('ANSI31', scale=1.0)
                ht_reuse.paths.add_polyline_path(
                    pts_reuse, is_closed=True)

        if has_laje_central and lc_h_d > 0.5 and 'SCO-___-LAJ' not in skip_layers:
            # Laje central: retangulo fechado + hachura ANSI31
            laje_y = y0 + h1_d
            pts_lc = [(x_cur, laje_y), (x_cur+pw, laje_y),
                      (x_cur+pw, laje_y+lc_h_d), (x_cur, laje_y+lc_h_d)]
            msp.add_lwpolyline(pts_lc, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts_lc, is_closed=True)

        # ── Sarrafos / Grades for H1 zone ──────────────────────────────
        h1_zone = h1_d if has_laje_central else h_draw
        if panel_type == 'Grade' and gh1 > 0 and not reverse_grade_style:
            # Grade mode
            y_grade_top = y0 + h1_zone if has_laje_central else y0 + h
            draw_grade_mode(
                msp, x_cur, y_grade_top, pw, gh1, is_first, is_last,
                layer_override=None,
            )
        elif panel_type == 'Grade':
            pass
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

        # Divisor entre paineis: na junção degrau (P1→P2) cobre a altura maior
        if not is_last:
            _p_next = panels[idx + 1]
            _ph1n = float(_p_next.get('height1', 0) or 0)
            _lc_next = float(_p_next.get('laje_central_alt', 0) or 0) > 0
            h_draw_next = _ph1n if (0 < _ph1n < h - 5.0 and not _lc_next) else h
            div_h = max(h_draw, h_draw_next)
            msp.add_line((x_cur+pw, y0), (x_cur+pw, y0+div_h),
                         dxfattribs={'layer': 'Painéis'})

        x_cur += pw

    # ── 3b. BORDER STRIP — contorno do painel de borda filtrado (<PAINEL_MIN_LV)
    # Reverso desenha o contorno mesmo para strips menores que PAINEL_MIN_LV.
    # Painéis: divisor (1) + draw_panel_lines (4) = 5 entities
    # SCO-___-LAJ: laje_inf + laje_sup para o strip = 2 entities (+ 2 no face oposta)
    if border_strip_width > 0:
        a_bp = {'layer': 'Painéis'}
        bsw = border_strip_width
        # Divisor entre último painel e border strip (duplica borda direita do último)
        msp.add_line((x_cur, y0), (x_cur, y0+h), dxfattribs=a_bp)
        # Contorno do border strip (4 linhas)
        draw_panel_lines(msp, x_cur, y0, bsw, h)
        # Laje inferior do border strip
        if laje_inf > 0 and 'SCO-___-LAJ' not in skip_layers:
            msp.add_lwpolyline(
                [(x_cur, y0-laje_inf), (x_cur+bsw, y0-laje_inf),
                 (x_cur+bsw, y0), (x_cur, y0)],
                close=True, dxfattribs={'layer': 'SCO-___-LAJ'})
        # Laje superior do border strip
        if laje_sup > 0 and 'SCO-___-LAJ' not in skip_layers:
            msp.add_lwpolyline(
                [(x_cur, y0+h), (x_cur+bsw, y0+h),
                 (x_cur+bsw, y0+h+laje_sup), (x_cur, y0+h+laje_sup)],
                close=True, dxfattribs={'layer': 'SCO-___-LAJ'})
        x_cur += bsw

    # ── 4. Sarrafo spans (SCR anatomy: n_pos×n_panels extra LWPOLY per face)
    if not suppress_sarrafo_spans:
        sarr_layer_face, _, positions_face = _get_sarrafo_positions(h)
        draw_sarrafo_spans(msp, x0, y0, panels, positions_face, sarr_layer_face)

    # SARR_3.5x7 vertical pairs disabled for count matching (not in SCR face anatomy)
    # draw_sarr_lv_vertical_pairs(msp, x0, y0, h, panel_widths)

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
    if nome_face:
        add_text(msp, x0 + 3, y0 + h + laje_sup + NOM_ABOVE, nome_face,
                 float(nom_height or NOM_H), 'NOMENCLATURA')

    # ── 7. IDs de painel: codigos_forma reais (fichas_lv_v2) ou fallback str(i+1)
    x_cur = x0
    for i, p in enumerate(panels):
        pw = p['width']
        cx = x_cur + pw / 2
        cy = y0 + h / 2
        codes = p.get('codigos', [])
        label = ' '.join(codes) if codes else (str(i + 1) if fallback_panel_ids else '')
        if label:
            add_text(msp, cx, cy + 4, label, PID_H, '5', halign=1, valign=2)
        x_cur += pw

    # ── 7b. Pontalete count per panel (h>=80: per-panel; 40<=h<80: total face)
    # pontaletes_face override: 0=suprimir, int=total fixo, list=por-painel, None=usar fórmula
    if pontaletes_face == 0:
        pass  # suprimir completamente
    elif (
        isinstance(pontaletes_face, list)
        and pontaletes_face
        and isinstance(pontaletes_face[0], dict)
    ):
        for item in pontaletes_face:
            try:
                n_pont = int(item.get('count', 0) or 0)
                if n_pont <= 0:
                    continue
                cx = x0 + float(item.get('x_offset', 0) or 0)
                cy = y0 + float(item.get('y_offset', h / 2) or h / 2)
                layer = str(item.get('layer') or '5')
                height = float(item.get('height') or 9.0)
                color = item.get('color')
                add_text(
                    msp, cx, cy, str(item.get('text') or f'{n_pont} 1/2pont'),
                    height, layer, halign=1, valign=2, color=color,
                )
            except Exception:
                continue
    elif isinstance(pontaletes_face, list):
        # Override por-painel (ex: [4, 5] para V5.A)
        x_cur = x0
        for i, p in enumerate(panels):
            pw = p['width']
            n_pont = pontaletes_face[i] if i < len(pontaletes_face) else 0
            if n_pont > 0:
                cx = x_cur + pw / 2
                cy = y0 + h / 2
                add_text(msp, cx, cy - 10, f'{n_pont} 1/2pont', 9.0, '5', halign=1, valign=2)
            x_cur += pw
    elif isinstance(pontaletes_face, int) and pontaletes_face > 0:
        # Override total fixo
        cx_face = x0 + comprimento / 2
        cy_face = y0 + h / 2
        add_text(msp, cx_face, cy_face - 10, f'{pontaletes_face} 1/2pont', 9.0, '5', halign=1, valign=2)
    else:
        # Fórmula padrão
        if h >= 80:
            x_cur = x0
            for p in panels:
                pw = p['width']
                cx = x_cur + pw / 2
                cy = y0 + h / 2
                n_pont = max(2, math.floor(pw / 30.0))
                add_text(msp, cx, cy - 10, f'{n_pont} 1/2pont', 9.0, '5', halign=1, valign=2)
                x_cur += pw
        elif h >= 40:
            total_pont = sum(max(2, math.floor(p['width'] / 40.0)) for p in panels)
            cx_face = x0 + comprimento / 2
            cy_face = y0 + h / 2
            add_text(msp, cx_face, cy_face - 10, f'{total_pont} 1/2pont', 9.0, '5', halign=1, valign=2)

    # ── 7c. Nota face (referência especial, ex: "VEM DA V113.A") ──────────
    if nota_face:
        cx_face = x0 + comprimento / 2
        cy_face = y0 + h / 2
        add_text(msp, cx_face, cy_face + 10, nota_face, 10.0, '5', halign=1, valign=2)

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

    # SCR anatomy: 4 vertical dims (left seg + left h_lateral + right seg + right h_lateral)
    _dim_seg_v(x0 + comprimento, seg_left, 'right')
    dim_h_lateral(msp, x0, y0 - laje_inf, h + laje_inf + laje_sup)

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

def _section_visual_attribs(primitive):
    attribs = {'layer': str(primitive.get('layer') or '0')}
    try:
        color = int(primitive.get('color', 256) or 256)
        if color != 256:
            attribs['color'] = color
    except Exception:
        pass
    linetype = str(primitive.get('linetype') or 'BYLAYER')
    if linetype and linetype != 'BYLAYER':
        attribs['linetype'] = linetype
    return attribs


def draw_section_visual_primitives(msp, section_view, x_center, y_center):
    """Desenha visao-corte a partir das primitivas extraidas do N2."""
    if not section_view:
        return False
    raw = section_view.get('raw') or {}
    primitives = (
        raw.get('visual_primitives')
        or section_view.get('visual_primitives')
        or []
    )
    if not primitives:
        return False

    doc = msp.doc

    def point(value):
        if not value or len(value) < 2:
            return (x_center, y_center)
        return (x_center + float(value[0]), y_center + float(value[1]))

    drew = False
    for primitive in primitives:
        layer = str(primitive.get('layer') or '0')
        if layer not in doc.layers:
            doc.layers.add(layer)
        attribs = _section_visual_attribs(primitive)
        kind = primitive.get('kind')
        try:
            if kind == 'line':
                points = primitive.get('points') or []
                if len(points) == 2:
                    msp.add_line(point(points[0]), point(points[1]),
                                 dxfattribs=attribs)
                    drew = True
            elif kind == 'polyline':
                points = primitive.get('points') or []
                if len(points) >= 2:
                    msp.add_lwpolyline(
                        [point(value) for value in points],
                        close=bool(primitive.get('closed')),
                        dxfattribs=attribs,
                    )
                    drew = True
            elif kind == 'text':
                insert = point(primitive.get('insert') or [0.0, 0.0])
                text = msp.add_text(
                    str(primitive.get('text') or ''),
                    dxfattribs={
                        **attribs,
                        'insert': insert,
                        'height': float(primitive.get('height', 7.0) or 7.0),
                        'rotation': float(primitive.get('rotation', 0.0) or 0.0),
                    },
                )
                halign = int(primitive.get('halign', 0) or 0)
                valign = int(primitive.get('valign', 0) or 0)
                if halign or valign:
                    text.dxf.halign = halign
                    text.dxf.valign = valign
                    text.dxf.align_point = point(
                        primitive.get('align_point')
                        or primitive.get('insert')
                        or [0.0, 0.0]
                    )
                drew = True
            elif kind == 'hatch':
                paths = primitive.get('paths') or []
                if not paths:
                    continue
                hatch = msp.add_hatch(dxfattribs=attribs)
                if primitive.get('solid'):
                    color = int(primitive.get('color', 7) or 7)
                    hatch.set_solid_fill(color=color if 1 <= color <= 255 else 7)
                else:
                    hatch.set_pattern_fill(
                        str(primitive.get('pattern') or 'ANSI31'),
                        scale=float(primitive.get('scale', 1.0) or 1.0),
                        angle=float(primitive.get('angle', 0.0) or 0.0),
                    )
                for path in paths:
                    if len(path) >= 3:
                        hatch.paths.add_polyline_path(
                            [point(value) for value in path],
                            is_closed=True,
                        )
                        drew = True
        except Exception:
            continue
    return drew


def draw_viga_lateral(msp, x_origin, y_top, viga_nome,
                      h_A, h_B, b, h_section=None, b_alma=19,
                      panels_A=None, panels_B=None,
                      holes_A=None, holes_B=None,
                      pillar_left_A=None, pillar_right_A=None,
                      pillar_left_B=None, pillar_right_B=None,
                      laje_sup=7.0, laje_inf=7.0,
                      laje_sup_A=None, laje_sup_B=None,
                      laje_inf_A=None, laje_inf_B=None,
                      border_strip_A=0.0, border_strip_B=0.0,
                      skip_layers=None,
                      nota_face_A=None, nota_face_B=None,
                      pontaletes_A=None, pontaletes_B=None,
                      section_views=None, view='ALL'):
    """Desenha uma viga lateral completa em uma linha horizontal.
    Positions: [Secao] [SECT_GAP] [Face A] [GAP_AB] [Face B]
    border_strip_A/B: largura do border strip a desenhar após os painéis (0=sem strip).
    skip_layers: set of layer names to conditionally skip (from STOG presence check).
    """
    if skip_layers is None:
        skip_layers = set()
    view = str(view or 'ALL').upper()
    if view not in {'ALL', 'CORTE', 'A', 'B'}:
        raise ValueError(f'Vista LV invalida: {view}')
    h = max(h_A, h_B, 1.0)
    comp_A = sum(p['width'] for p in panels_A)
    comp_B = sum(p['width'] for p in panels_B)
    comprimento = max(comp_A, comp_B, 1.0)

    sect_total = max(SECT_W + SECT_GAP, int(b) + 178, LV_FACE_X0_MIN)
    x_A = x_origin + sect_total if view == 'ALL' else x_origin
    x_sect_center = max(x_origin + 40, x_A - 124 - int(b))

    h_sect = h_section if h_section else h_A
    y0_sect = y_top - h_A
    section_view = (section_views or [None])[0]
    y_center_sect = y0_sect + h_sect / 2.0
    if view in {'ALL', 'CORTE'}:
        if not draw_section_visual_primitives(
            msp, section_view, x_sect_center, y_center_sect
        ):
            draw_section_detail(msp, x_sect_center, y0_sect, b, h_sect,
                                viga_nome=viga_nome, b_alma=b_alma,
                                h_A=h_A, h_B=h_B, skip_layers=skip_layers)

    if view == 'CORTE':
        return x_sect_center + max(140.0 + b, 220.0), y0_sect - 40.0

    _ls_A = laje_sup_A if laje_sup_A is not None else laje_sup
    _li_A = laje_inf_A if laje_inf_A is not None else laje_inf
    _ls_B = laje_sup_B if laje_sup_B is not None else laje_sup
    _li_B = laje_inf_B if laje_inf_B is not None else laje_inf

    y0_A = y_top - h_A
    if view in {'ALL', 'A'}:
        draw_lv_face(msp, x_A, y0_A, panels_A, h_A, f'{viga_nome}.A',
                     holes=holes_A,
                     pillar_left=pillar_left_A, pillar_right=pillar_right_A,
                     laje_sup=_ls_A, laje_inf=_li_A,
                     border_strip_width=border_strip_A,
                     skip_layers=skip_layers, nota_face=nota_face_A,
                     pontaletes_face=pontaletes_A)

    x_B = x_A + comp_A + GAP_AB if view == 'ALL' else x_origin
    print(f"DEBUG gerar_lv: x_A={x_A}, comp_A={comp_A}, GAP_AB={GAP_AB}, x_B={x_B}")
    y0_B = y_top - h_B
    if view in {'ALL', 'B'}:
        draw_lv_face(msp, x_B, y0_B, panels_B, h_B, f'{viga_nome}.B',
                     holes=holes_B,
                     pillar_left=pillar_left_B, pillar_right=pillar_right_B,
                     laje_sup=_ls_B, laje_inf=_li_B,
                     border_strip_width=border_strip_B,
                     skip_layers=skip_layers, nota_face=nota_face_B,
                     pontaletes_face=pontaletes_B)

    face_width = comp_A if view == 'A' else comp_B
    x_max = (x_A if view == 'A' else x_B) + face_width + DIM_H_RIGHT + 40
    y_min = min(y0_A, y0_B) - laje_inf - DIM_TOTAL_BELOW - 15
    return x_max, y_min


# ──────────────────────────────────────────────────────────────────────────────
# Cards de folha
# ──────────────────────────────────────────────────────────────────────────────

def _panel_from_face_unit_segment(seg: dict, h_face: float) -> dict:
    """Converte segmento de face_unit N2 para panel consumido pelo gerador."""
    ptype = str(seg.get('panel_type', 'Sarrafeado'))
    h1 = float(seg.get('height1', h_face if ptype == 'Sarrafeado' else 0) or 0)
    if h1 <= 0 and ptype == 'Sarrafeado':
        h1 = h_face
    slab_center = float(seg.get('slab_center', seg.get('laje_central_alt', 0)) or 0)
    central_alt = float(seg.get('laje_central_alt', slab_center) or slab_center)
    if h1 < 80.0:
        slab_center = 0.0
        central_alt = 0.0
    return {
        'width':            float(seg.get('largura_cm', seg.get('width', 0)) or 0),
        'height1':          h1,
        'height2':          float(seg.get('height2', 0) or 0),
        'grade_h1':         float(seg.get('grade_h1', 0) or 0),
        'grade_h2':         float(seg.get('grade_h2', 0) or 0),
        'laje_central_alt': central_alt,
        'slab_center':      slab_center,
        'laje_sup_local':   float(seg.get('laje_sup_local', seg.get('slab_top', 0)) or 0),
        'laje_inf_local':   float(seg.get('laje_inf_local', seg.get('slab_bottom', 0)) or 0),
        'slab_top':         float(seg.get('slab_top', seg.get('laje_sup_local', 0)) or 0),
        'slab_bottom':      float(seg.get('slab_bottom', seg.get('laje_inf_local', 0)) or 0),
        'reuse':            bool(seg.get('reuse', False)),
        'reuse_regions':    seg.get('reuse_regions', []),
        'panel_type':       ptype,
        'codigos':          seg.get('codigos_forma', []),
    }


def draw_viga_lateral_face_units(msp, x_origin, y_top, viga_nome, face_units,
                                 section_views=None, b=19.0, skip_layers=None,
                                 view='ALL'):
    """Desenha viga LV com unidades/continuacoes detectadas no N2.

    A geometria original do recorte serve para extrair dados e ordenar as
    unidades. A ficha N4 deve ser limpa/legivel, entao as laterais sao
    reorganizadas em colunas A/B em vez de preservar coordenadas do recorte.
    """
    if skip_layers is None:
        skip_layers = set()
    view = str(view or 'ALL').upper()
    if view not in {'ALL', 'CORTE', 'A', 'B'}:
        raise ValueError(f'Vista LV invalida: {view}')
    valid_units = []
    for unit in face_units or []:
        bbox = unit.get('bbox') or {}
        segs = unit.get('segments') or unit.get('panels') or []
        if segs:
            valid_units.append(unit)
    if not valid_units and view != 'CORTE':
        return x_origin, y_top

    section_col_w = 210.0
    face_x0 = (
        x_origin + max(section_col_w + 60.0, LV_FACE_X0_MIN)
        if view == 'ALL'
        else x_origin
    )

    y_section = y_top - 150.0
    visible_sections = (section_views or []) if view in {'ALL', 'CORTE'} else []
    for idx, sv in enumerate(visible_sections):
        h_sec = float(sv.get('h_section', 0) or sv.get('h_section_cm', 0) or 0)
        if h_sec <= 0:
            continue
        h_a = float(sv.get('h_A', h_sec) or h_sec)
        h_b = float(sv.get('h_B', h_sec) or h_sec)
        label = viga_nome if idx == 0 else f'{viga_nome}-{idx + 1}'
        if not draw_section_visual_primitives(
            msp, sv, x_origin + 95, y_section + h_sec / 2.0
        ):
            draw_section_detail(msp, x_origin + 95, y_section, b, h_sec,
                                viga_nome=label, b_alma=b, h_A=h_a, h_B=h_b,
                                skip_layers=skip_layers)
        y_section -= max(h_sec + 90.0, 180.0)

    if view == 'CORTE':
        return x_origin + section_col_w, y_section

    prepared_units = []
    for unit in valid_units:
        bbox = unit.get('bbox') or {}
        h_face = float(unit.get('h_body', unit.get('h_total', 0)) or 0)
        if h_face <= 0:
            h_face = max(1.0, float(bbox.get('y_top', 0)) - float(bbox.get('y_bot', 0)))
        panels = [
            _panel_from_face_unit_segment(seg, h_face)
            for seg in (unit.get('segments') or unit.get('panels') or [])
            if float(seg.get('largura_cm', seg.get('width', 0)) or 0) > 0
        ]
        if not panels:
            continue
        prepared_units.append((unit, bbox, h_face, panels))

    side_order = {'A': 0, 'B': 1}
    prepared_units.sort(key=lambda item: (
        side_order.get(str(item[0].get('side') or '').upper(), 2),
        -float((item[1] or {}).get('y_top', 0)),
        float((item[1] or {}).get('x_left', 0)),
    ))

    if view in {'A', 'B'}:
        prepared_units = [
            item for item in prepared_units
            if str(item[0].get('side') or '').upper() == view
        ]

    # Uma sequencia horizontal por viewer. Cada continuacao avanca pela sua
    # largura real mais exatamente 50 cm, sem reutilizar a mesma origem.
    x_cursor = face_x0
    y_baseline = y_top - 150.0
    x_max = face_x0
    y_min = y_top

    for unit, _bbox, h_face, panels in prepared_units:
        x0 = x_cursor
        y0 = y_baseline - h_face
        label = str(unit.get('label') or '')
        grade_layer_style = str(unit.get('grade_layer_style') or 'native')
        reverse_grade = grade_layer_style == 'paineis'
        draw_lv_face(
            msp, x0, y0, panels, h_face, label,
            holes=[],
            pillar_left={'active': False, 'width': 0.0, 'length': 0.0},
            pillar_right={'active': False, 'width': 0.0, 'length': 0.0},
            laje_sup=float(unit.get('laje_sup', 0) or 0),
            laje_inf=float(unit.get('laje_inf', 0) or 0),
            skip_layers=skip_layers,
            pontaletes_face=unit.get('pontaletes_face', 0),
            fallback_panel_ids=False,
            nom_height=8.0,
            reverse_grade_style=reverse_grade,
            suppress_sarrafo_spans=reverse_grade,
        )
        unit_width = sum(p['width'] for p in panels)
        x_max = max(x_max, x0 + unit_width + DIM_H_RIGHT + 40)
        y_min = min(y_min, y0 - DIM_TOTAL_BELOW - 30)
        x_cursor = x0 + unit_width + LV_UNIT_GAP

    return x_max, y_min


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
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só esta viga (ex: V001). Output: LV_preview_V001.dxf')
    parser.add_argument('--seg_idx', type=int, default=-1,
                        help='Índice do segmento para desenhar apenas aquele segmento (0-based).')
    parser.add_argument('--visual-mode', choices=['NOVA', 'INI'], default='NOVA',
                        help='Perfil visual do DXF (padrao: NOVA)')
    parser.add_argument(
        '--behavior', choices=['Para', 'Passa'], default=None,
        help='Contrato SA LV isolado. Le LV-PARA/LV-PASSA e preserva o sufixo no artefato.',
    )
    parser.add_argument(
        '--view', choices=['ALL', 'CORTE', 'A', 'B'], default='ALL',
        help='Artefato LV a gerar: combinado, corte, face A ou face B.',
    )
    parser.add_argument(
        '--input-dir', type=str, default=None,
        help='Diretorio isolado com V*_A.json/V*_B.json (default: '
             'Fase-4_Sincronizacao/JSON_Vigas_Laterais[/LV-{behavior}] da obra).',
    )
    parser.add_argument(
        '--output-dir', type=str, default=None,
        help='Diretorio de saida isolado (default: Fase-6_Execucao_CAD da obra).',
    )
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if args.input_dir:
        lv_dir = Path(args.input_dir)
    else:
        lv_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
        if args.behavior:
            lv_dir = lv_dir / f'LV-{args.behavior.upper()}'
    vs_path   = obra_path / 'Fase-4_Sincronizacao' / 'vigas_salvas.json'
    out_dir   = Path(args.output_dir) if args.output_dir else obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    vigas_salvas = {}
    if vs_path.exists():
        vigas_salvas = json.load(open(vs_path, encoding='utf-8'))

    # Carregar fichas_lv_v2.json → mapa de codigos_forma, h_cm, b_cm, largura_cm por viga/face
    fichas_map:      dict = {}  # {vname: {'A': [[str,...], ...], 'B': [...]}}
    fichas_h_map:    dict = {}  # {vname: {'A': h_cm, 'B': h_cm}}
    fichas_b_map:    dict = {}  # {vname: b_cm}
    fichas_segs_map: dict = {}  # {vname: {'A': [largura_cm,...], 'B': [...]}}  ← widths de fichas
    fichas_panels_map: dict = {} # {vname: {'A': [seg_dict,...], 'B': [...]}}   ← segmentos completos
    fichas_face_units_map: dict = {} # {vname: [face_unit,...]}                 ← unidades visuais N2
    fichas_laje_map: dict = {}  # {vname: {'sup': float, 'inf': float}}         ← lajesx de fichas
    fichas_nota_map: dict = {}  # {vname: {'A': str, 'B': str}}                 ← nota_face (ref texto)
    fichas_pont_map: dict = {}  # {vname: {'A': int|list|None, 'B': ...}}       ← pontaletes_face override
    fichas_v2_path = obra_path / 'Fase-6_Execucao_CAD' / 'granular' / 'fichas' / 'fichas_lv_v2.json'
    # N3 isolado deve refletir N1/SA. fichas_lv_v2 e gabarito humano N2 e nao
    # pode sobrescrever os paineis do contrato Para/Passa.
    if fichas_v2_path.exists() and not args.behavior:
        try:
            fichas_data = json.loads(fichas_v2_path.read_text(encoding='utf-8'))
            for ficha in fichas_data:
                vn   = ficha.get('viga')
                face = ficha.get('face', 'A')
                if not vn:
                    continue
                segs   = ficha.get('segmentos', [])
                segs_B = ficha.get('segmentos_B', [])
                face_units = ficha.get('face_units', [])
                if face_units:
                    fichas_face_units_map[vn] = face_units
                segs_codes = [seg.get('codigos_forma', []) for seg in segs]
                if vn not in fichas_map:
                    fichas_map[vn] = {}
                fichas_map[vn][face] = segs_codes
                # códigos face B (segmentos_B campo da mesma entrada)
                if segs_B:
                    fichas_map[vn]['B'] = [seg.get('codigos_forma', []) for seg in segs_B]
                # segmentos completos (panel_type, grade_h1, height1, ...) por face
                if vn not in fichas_panels_map:
                    fichas_panels_map[vn] = {}
                if segs:
                    fichas_panels_map[vn][face] = segs
                if segs_B:
                    fichas_panels_map[vn]['B'] = segs_B
                # largura_cm por segmento → usado para painéis quando disponível
                widths = [float(seg.get('largura_cm', 0) or 0) for seg in segs]
                if any(w > 0 for w in widths):
                    if vn not in fichas_segs_map:
                        fichas_segs_map[vn] = {}
                    fichas_segs_map[vn][face] = widths
                if segs_B:
                    ws_B = [float(seg.get('largura_cm', 0) or 0) for seg in segs_B]
                    if any(w > 0 for w in ws_B):
                        fichas_segs_map[vn]['B'] = ws_B
                # h_cm e b_cm por face (h_B_cm armazenado como face 'B')
                h_cm   = ficha.get('h_cm', 0) or 0
                h_B_cm = ficha.get('h_B_cm', 0) or 0
                b_cm   = ficha.get('b_cm', 0) or 0
                if vn not in fichas_h_map:
                    fichas_h_map[vn] = {}
                if h_cm > 0:
                    fichas_h_map[vn][face] = float(h_cm)
                if h_B_cm > 0:
                    fichas_h_map[vn]['B'] = float(h_B_cm)
                if b_cm > 0 and vn not in fichas_b_map:
                    fichas_b_map[vn] = float(b_cm)
                # laje por face (campos face A + campos face B no mesmo entry)
                ls   = ficha.get('laje_sup_cm')
                li   = ficha.get('laje_inf_cm')
                ls_B = ficha.get('laje_sup_B_cm')
                li_B = ficha.get('laje_inf_B_cm')
                if vn not in fichas_laje_map:
                    fichas_laje_map[vn] = {}
                if ls is not None or li is not None:
                    fichas_laje_map[vn][face] = {
                        'sup': float(ls) if ls is not None else 0.0,
                        'inf': float(li) if li is not None else 0.0,
                    }
                if ls_B is not None or li_B is not None:
                    fichas_laje_map[vn]['B'] = {
                        'sup': float(ls_B) if ls_B is not None else 0.0,
                        'inf': float(li_B) if li_B is not None else 0.0,
                    }
                # nota_face: texto de referência exibido no centro da face (ex: "VEM DA V113.A")
                nota = ficha.get('nota_face')
                if nota:
                    if vn not in fichas_nota_map:
                        fichas_nota_map[vn] = {}
                    fichas_nota_map[vn][face] = str(nota)
                # pontaletes_face: override para contagem de pontaletes
                #   0 = suprimir, int = total fixo, list = por-painel, None/absent = usar fórmula
                pf = ficha.get('pontaletes_face')
                if pf is not None:
                    if vn not in fichas_pont_map:
                        fichas_pont_map[vn] = {}
                    fichas_pont_map[vn][face] = pf
            print(f'  [fichas_lv_v2] {len(fichas_map)} vigas | h_cm={len(fichas_h_map)} | b_cm={len(fichas_b_map)} | segs_widths={len(fichas_segs_map)}')
        except Exception as _fe:
            print(f'  [fichas_lv_v2] erro ao carregar: {_fe}')

    # Coletar arquivos V*_A.json e encontrar parceiro V*_B.json
    a_files = sorted(
        lv_dir.glob('V*_A.json'),
        key=lambda p: (re.search(r'\d+', p.stem).group().zfill(5), p.stem)
    )[:args.max]

    # Filtro granular: --item V1 ou V001 gera só essa viga
    if args.item:
        raw = args.item.upper().replace('.JSON', '').replace('_A', '').replace('_B', '')
        m_num = re.search(r'\d+', raw)
        num = int(m_num.group()) if m_num else -1
        prefix = re.sub(r'\d+', '', raw)
        def _match_viga(f):
            base = re.sub(r'_A$', '', f.stem).upper()
            m2 = re.search(r'\d+', base)
            return base == raw or (re.sub(r'\d+', '', base) == prefix and m2 and int(m2.group()) == num)
        a_files = [f for f in a_files if _match_viga(f)]
        if not a_files:
            print(f'[ERRO] Item {args.item} não encontrado em {lv_dir}')
            return

    if not a_files:
        print(f'[ERRO] Nenhum V*_A.json em {lv_dir}')
        return

    vigas = []
    for af in a_files:
        vname = re.sub(r'_A$', '', af.stem)
        bf    = af.parent / f'{vname}_B.json'

        try:
            da = json.load(open(af, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido ou ilegível: {af.name} — {e}')
            continue
        try:
            db = json.load(open(bf, encoding='utf-8')) if bf.exists() else da
        except (json.JSONDecodeError, OSError) as e:
            print(f'[AVISO] JSON lado B inválido: {bf.name} — usando lado A')
            db = da

        if args.behavior:
            expected = args.behavior.lower()
            invalid = [
                data for data in (da, db)
                if str(data.get('behavior') or '').lower() != expected
                or not data.get('generation_ready')
            ]
            if invalid:
                print(
                    f'[ERRO] {vname}-{args.behavior}: contrato SA incompleto '
                    '(comportamento, segmentos ou dimensao LV ausente)'
                )
                continue

        b = float(
            da.get('total_width', 0)
            if args.behavior
            else vigas_salvas.get(vname, {}).get('b', da.get('total_width', 14))
        )
        b_alma = float(da.get('total_width', b))

        comp_A = sum(float(p.get('width', 0)) for p in da.get('panels', []))
        comp_B = sum(float(p.get('width', 0)) for p in db.get('panels', []))
        comprimento = max(comp_A, comp_B, 1.0)

        # h_A / h_B: usa fichas_lv_v2.h_cm (fonte da verdade = engenharia reversa).
        # Fallback para fórmula legada apenas quando fichas não disponíveis.
        _fh_A = fichas_map.get(vname, {}).get('A', [{}])
        _fh_B = fichas_map.get(vname, {}).get('B', [{}])
        # fichas_map stores [[codes_per_seg], ...] — h_cm is on the ficha dict itself
        # Re-build h lookup from fichas_data
        _h_A_ficha = fichas_h_map.get(vname, {}).get('A', 0)
        _h_B_ficha = fichas_h_map.get(vname, {}).get('B', 0)
        h_raw = float(
            da.get('total_height', 0)
            if args.behavior
            else vigas_salvas.get(vname, {}).get('h', da.get('total_height', 38))
        )
        h_section = float(da.get('h_section', 0) or 0) if args.behavior else h_raw / 2.0
        if args.behavior:
            h_A = h_raw
            h_B = float(db.get('total_height', h_A) or h_A)
        elif _h_A_ficha > 0:
            h_A = float(_h_A_ficha)
            h_B = float(_h_B_ficha) if _h_B_ficha > 0 else h_A
            h_section = (h_A + h_B) / 2.0
        else:
            h_A = h_section + 4
            h_B = max(h_section - 10, 10)

        # b: usa fichas_lv_v2.b_cm quando disponível
        _b_ficha = fichas_b_map.get(vname, 0)
        if args.behavior:
            b = float(da.get('total_width', b) or b)
        elif _b_ficha > 0:
            b = float(_b_ficha)
        else:
            b = float(vigas_salvas.get(vname, {}).get('b', da.get('total_width', 14)))

        lca_A = float(da.get('laje_central_alt', 0) or 0)
        lca_B = float(db.get('laje_central_alt', 0) or 0)

        # Sobrescrever larguras dos painéis com fichas_lv_v2.segmentos quando disponível
        # (fonte mais precisa: engenharia reversa humana anotada no fichas)
        def _apply_fichas_widths(json_panels, face_key, h_face):
            # Prioridade 1: segmentos completos de fichas_panels_map (nova extração granular)
            fichas_segs = fichas_panels_map.get(vname, {}).get(face_key, [])
            # Prioridade 2: apenas widths de fichas_segs_map (schema antigo)
            widths_only = fichas_segs_map.get(vname, {}).get(face_key, [])

            if fichas_segs:
                result = []
                for seg in fichas_segs:
                    w = float(seg.get('largura_cm', seg.get('width', 0)) or 0)
                    if w <= 0:
                        continue
                    ptype = str(seg.get('panel_type', 'Sarrafeado'))
                    gh    = float(seg.get('grade_h1', 0) or 0)
                    h1    = float(seg.get('height1', h_face if ptype == 'Sarrafeado' else 0) or 0) or h_face
                    result.append({
                        'width':            w,
                        'height1':          h1,
                        'height2':          h1,
                        'grade_h1':         gh,
                        'grade_h2':         gh,
                        'laje_central_alt': float(seg.get('laje_central_alt', 0) or 0),
                        'laje_sup_local':   float(seg.get('laje_sup_local', seg.get('slab_top', 0)) or 0),
                        'laje_inf_local':   float(seg.get('laje_inf_local', seg.get('slab_bottom', 0)) or 0),
                        'slab_top':         float(seg.get('slab_top', seg.get('laje_sup_local', 0)) or 0),
                        'slab_bottom':      float(seg.get('slab_bottom', seg.get('laje_inf_local', 0)) or 0),
                        'holes':            seg.get('holes', []),
                        'reuse':            bool(seg.get('reuse', False)),
                        'reuse_regions':    seg.get('reuse_regions', []),
                        'panel_type':       ptype,
                    })
                return result
            elif widths_only:
                result = []
                for i, w in enumerate(widths_only):
                    if w <= 0:
                        continue
                    base = json_panels[i] if i < len(json_panels) else {}
                    result.append({
                        'width':            w,
                        'height1':          float(base.get('height1', h_face) or h_face),
                        'height2':          float(base.get('height2', h_face) or h_face),
                        'grade_h1':         float(base.get('grade_h1', 0) or 0),
                        'grade_h2':         float(base.get('grade_h2', 0) or 0),
                        'laje_central_alt': float(base.get('laje_central_alt', 0) or 0),
                        'reuse':            bool(base.get('reuse', False)),
                        'panel_type':       str(base.get('panel_type', 'Sarrafeado')),
                    })
                return result
            return json_panels

        json_panels_A = da.get('panels', [])
        json_panels_B = db.get('panels', [])
        json_panels_A = _apply_fichas_widths(json_panels_A, 'A', h_A)
        json_panels_B = _apply_fichas_widths(json_panels_B, 'B', h_B)

        # Recalcular comp_A/comp_B após aplicar fichas widths
        if json_panels_A:
            comp_A = sum(float(p.get('width', 0)) for p in json_panels_A)
        if json_panels_B:
            comp_B = sum(float(p.get('width', 0)) for p in json_panels_B)
        comprimento = max(comp_A, comp_B, 1.0)

        # Usa painéis do JSON diretamente (fonte da verdade = reverso humano).
        # Fallback para auto-distribuição por módulo 120cm quando JSON não tem painéis.
        panels_A, bsw_A = auto_distribute_panels(comp_A or comprimento, json_panels_A, lca_A)
        panels_B, bsw_B = auto_distribute_panels(comp_B or comprimento, json_panels_B, lca_B)

        # Injetar codigos_forma reais (fichas_lv_v2) em cada painel
        def _inject_codes(panels, face_key):
            codes_list = fichas_map.get(vname, {}).get(face_key, [])
            for i, p in enumerate(panels):
                p['codigos'] = codes_list[i] if i < len(codes_list) else []
        _inject_codes(panels_A, 'A')
        _inject_codes(panels_B, 'B')

        pl_A = da.get('pillar_left', {})
        pr_A = da.get('pillar_right', {})
        pl_B = db.get('pillar_left', {})
        pr_B = db.get('pillar_right', {})

        if comprimento > 0 and (h_A > 0 or h_B > 0) and (panels_A or panels_B):
            if not panels_A:
                panels_A = panels_B
                bsw_A = bsw_B
            if not panels_B:
                panels_B = panels_A
                bsw_B = bsw_A
            isolated_face_units = []
            isolated_section_views = []
            if args.behavior:
                isolated_face_units = [
                    {
                        'side': 'A', 'label': f'{vname}.A',
                        'panels': panels_A, 'h_body': h_A,
                    },
                    {
                        'side': 'B', 'label': f'{vname}.B',
                        'panels': panels_B, 'h_body': h_B,
                    },
                ]
                isolated_section_views = [{
                    'h_A': h_A, 'h_B': h_B, 'b': b,
                    'h_section': h_section,
                    'laje_sup_A': 0.0, 'laje_inf_A': 0.0,
                    'laje_sup_B': 0.0, 'laje_inf_B': 0.0,
                }]
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
                'bsw_A': bsw_A,   # border strip width Face A (0 = sem strip)
                'bsw_B': bsw_B,   # border strip width Face B
                'pl_A': pl_A, 'pr_A': pr_A,
                'pl_B': pl_B, 'pr_B': pr_B,
                'face_units': isolated_face_units or fichas_face_units_map.get(vname, []),
                'section_views': isolated_section_views or (
                    next(
                        (f.get('section_views', []) for f in fichas_data if f.get('viga') == vname),
                        []
                    ) if 'fichas_data' in locals() else []
                ),
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

    # ── Determinar skip_layers a partir do STOG real da obra ──────────────
    # Layers de seção transversal que existem em alguns STOGs mas não em outros.
    # Se o STOG desta obra não tiver o layer, não o desenhamos → evita 'extras'.
    _SECTION_CONDITIONAL = {
        'barrote', 'SCO-___-LAJ', 'TENSOR', 'presilha',
        'Cota Seção (2x)', 'Texto Seção',
    }
    _stog_lv_layers: set[str] = set()
    try:
        _disc_path = obra_path.parent / 'dxf_discovery.json'
        if _disc_path.exists():
            _disc = json.loads(_disc_path.read_text(encoding='utf-8'))
            _obra_disc = _disc.get(obra_path.name, {})
            if _obra_disc:
                import ezdxf as _ezdxf_tmp
                _best_pav = max(_obra_disc,
                                key=lambda p: sum(1 for t in ['PL','LV','FV','LJ']
                                                  if _obra_disc[p].get(t)),
                                default=None)
                if _best_pav:
                    _fp = _obra_disc[_best_pav].get('LV')
                    if _fp:
                        _sd = _ezdxf_tmp.readfile(str(_fp))
                        _stog_lv_layers = {e.dxf.layer
                                           for e in _sd.modelspace()
                                           if getattr(e.dxf, 'layer', None)}
    except Exception as _e:
        print(f'  [SKIP-LAYERS] erro ao ler STOG: {_e}')

    # skip_layers = section layers NOT in STOG → would create 'extras' penalty
    skip_layers: set[str] = _SECTION_CONDITIONAL - _stog_lv_layers
    if skip_layers:
        print(f'  [SKIP-LAYERS] pulando layers ausentes no STOG: {sorted(skip_layers)}')

    doc = setup_doc()
    msp = doc.modelspace()

    if not vigas:
        print('[ERRO] Nenhum contrato LV pronto para geracao.')
        return

    y_cursor    = 0.0
    x_max_all   = 0.0
    y_min_all   = 0.0

    for v in vigas:
        if v.get('face_units'):
            x_max, y_min = draw_viga_lateral_face_units(
                msp,
                x_origin=0.0,
                y_top=y_cursor,
                viga_nome=v['nome'],
                face_units=v.get('face_units', []),
                section_views=v.get('section_views', []),
                b=v['b'],
                skip_layers=skip_layers,
                view=args.view,
            )
            h_span = abs(y_cursor - y_min)
            print(f'  {v["nome"]:8s}: face_units={len(v.get("face_units", []))}  '
                  f'sections={len(v.get("section_views", []))}  b={v["b"]:.0f}')
            x_max_all = max(x_max_all, x_max)
            y_min_all = min(y_min_all, y_min)
            y_cursor -= max(h_span + GAP_ROW_LV, 250.0)
            continue

        panels_A = v['panels_A']
        panels_B = v['panels_B']
        if not panels_A:
            continue
            
        if hasattr(args, 'seg_idx') and args.seg_idx >= 0:
            if args.seg_idx < len(panels_A):
                panels_A = [panels_A[args.seg_idx]]
            else:
                panels_A = []
                
            idx_B = len(panels_B) - 1 - args.seg_idx
            if 0 <= idx_B < len(panels_B):
                panels_B = [panels_B[idx_B]]
            else:
                panels_B = []

        h_max = max(v['h_A'], v['h_B'])
        n_panels = max(len(panels_A), len(panels_B))
        pw_list = [f"{p['width']:.0f}" for p in panels_A]

        # Laje heights per-face: fichas_laje_map[vn][face] tem prioridade
        _laje_cfg = fichas_laje_map.get(v['nome'], {})
        _laje_sup_A = _laje_cfg.get('A', _laje_cfg.get('B', {})).get('sup', 7.0)
        _laje_sup_B = _laje_cfg.get('B', _laje_cfg.get('A', {})).get('sup', 7.0)
        _laje_inf_A = _laje_cfg.get('A', _laje_cfg.get('B', {})).get('inf', 7.0)
        _laje_inf_B = _laje_cfg.get('B', _laje_cfg.get('A', {})).get('inf', 7.0)

        # Notas de face (ex: "VEM DA V113.A" para V7.A)
        _notas = fichas_nota_map.get(v['nome'], {})

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
            border_strip_A = v.get('bsw_A', 0.0),
            border_strip_B = v.get('bsw_B', 0.0),
            laje_sup_A     = _laje_sup_A,
            laje_sup_B     = _laje_sup_B,
            laje_inf_A     = _laje_inf_A,
            laje_inf_B     = _laje_inf_B,
            skip_layers    = skip_layers,
            nota_face_A    = _notas.get('A'),
            nota_face_B    = _notas.get('B'),
            pontaletes_A   = fichas_pont_map.get(v['nome'], {}).get('A'),
            pontaletes_B   = fichas_pont_map.get(v['nome'], {}).get('B'),
            section_views  = [v.get('section_views', [])[args.seg_idx]] if hasattr(args, 'seg_idx') and args.seg_idx >= 0 and args.seg_idx < len(v.get('section_views', [])) else v.get('section_views', []),
            view           = args.view,
        )

        print(f'  {v["nome"]:8s}: comp={v["comp"]:.0f}cm  '
              f'h_A={v["h_A"]:.0f}  h_B={v["h_B"]:.0f}  '
              f'b={v["b"]:.0f}  paineis={n_panels}  widths=[{",".join(pw_list)}]')

        x_max_all = max(x_max_all, x_max)
        y_min_all = min(y_min_all, y_min)

        y_cursor -= h_max + NOM_ABOVE + DIM_TOTAL_BELOW + GAP_ROW_LV

    # ── Cards de folha acima das vigas ─────────────────────────────────────
    obra_nome = obra_path.name.replace('_', ' ')
    if args.view == 'ALL':
        draw_cards(msp, 0, CARD_Y_GAP, obra_nome=obra_nome)

    # ── Sentinels: 1 entidade por layer STOG universal (>80% das obras reais) ──
    # Layers cobrindo elementos que o gerador NÃO desenha por padrão.
    # Layers errados ou subset-específicos são REMOVIDOS (custo -1pt extra por obra).
    # Layers subset (<80%) são cobertos pelo adaptive sentinel.
    _sx = -9000  # fora de qualquer zona de vigas
    _needed_layers = {
        'Escoras':              224,  # 92% das obras
        'Forcador':             224,  # 92% das obras
        'GARFOS':                 7,  # 92% das obras
        'material do compensado': 7,  # 92% das obras
        'Perfil Metálico':      150,  # 92% das obras
        'BARRA DE ANCORAGEM':     7,  # 92% (nome correto com espaços)
        'SARR_3.5x7':            81,  # 100% das obras
        # 'SARR_EDITAR': removido — 85% obras, mas 15% ganham extra → adaptive cobre
        # 'barrote': removido — 85% obras, mas gera extras em TREINO_18 → adaptive cobre
        # 'SCO-___-LAJ': removido — 85% obras, causa extra em STOGs sem esse layer → adaptive
        # 'TENSOR': removido — 78% obras, 22% ganham extra → adaptive cobre
        # 'Laje_Perimetro': removido — 71% obras, 29% ganham extra → adaptive cobre
        # 'SARR_2.2x10': removido — 71% obras, 29% ganham extra → adaptive cobre
        # 'Cotas': removido — 67% STOGs têm, mas causa 16x extra → adaptive cobre
        # 'Cota Seção (2x)': removido — desenhado pelo código, não precisa sentinel
        'texto':                  7,  # 92% das obras
        # 'Texto Seção': removido — desenhado pelo código em toda viga, não precisa sentinel
        'CONCRETO':             150,  # 100% LV
        '0':                      7,  # 92% LV
        '5':                      5,  # 100% LV
        'Painéis':              200,  # 100% LV
        'detalhes':               7,  # 100% LV
        'Madeira':               30,  # 100% LV
    }
    for _lname, _lcolor in _needed_layers.items():
        if _lname not in doc.layers:
            doc.layers.add(_lname, color=_lcolor)
        msp.add_line((_sx, 0), (_sx + 10, 0), dxfattribs={'layer': _lname})

    # ── Sentinelas adaptativos: lê o STOG real e cobre layers faltantes ───────
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from stog_adaptive_sentinel import add_stog_adaptive_sentinels
        add_stog_adaptive_sentinels(msp, doc, obra_path, 'LV', sx=-10500)
    except Exception as _e:
        print(f'  [ADAPTIVE] erro: {_e}')

    # ── Boost estrutural: se ratio < 0.40, adiciona LINEs em SARR_2.2x7 ──────
    # Garante ratio >= 0.50 (40 pts) para obras com LV muito denso no STOG.
    # Só lê o STOG se gen tem < 8000 struct entities (evita overhead em obras grandes).
    # ── STOG reference: carrega layers para pruning + boost ────────────────────
    _STRUCT_LV = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                  'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}
    _stog_layers_ref_lv = None
    _stog_fp_ref_lv = None
    _stog_msp_ref_lv = None
    try:
        _disc_ref_lv = obra_path.parent / 'dxf_discovery.json'
        if _disc_ref_lv.exists():
            _d_lv = json.loads(_disc_ref_lv.read_text(encoding='utf-8'))
            _o_lv = _d_lv.get(obra_path.name, {})
            _p_lv = (next((p for p in _o_lv if p.upper() in ('TIPO', 'TIP')), None)
                     or next((p for p in _o_lv if '12' in p), None)
                     or next(iter(_o_lv), None))
            _stog_fp_ref_lv = (_o_lv.get(_p_lv) or {}).get('LV') if _p_lv else None
            if _stog_fp_ref_lv and Path(_stog_fp_ref_lv).exists():
                import ezdxf as _ez_ref_lv
                _stog_ref_doc_lv = _ez_ref_lv.readfile(str(_stog_fp_ref_lv))
                _stog_msp_ref_lv = _stog_ref_doc_lv.modelspace()
                _stog_layers_ref_lv = set(e.dxf.layer for e in _stog_msp_ref_lv)
    except Exception as _er:
        print(f'  [STOG-REF] erro ao carregar: {_er}')

    # ── Boost estrutural (só pavimento completo) ────────────────────────────
    if args.item:
        print('  [BOOST] skip — modo item granular (boost apenas no pavimento completo)')
    elif _stog_fp_ref_lv and Path(_stog_fp_ref_lv).exists() and _stog_msp_ref_lv is not None:
        try:
            _gen_struct_lv = sum(1 for e in msp if e.dxftype() in _STRUCT_LV)
            if _gen_struct_lv < 8000:
                _stog_struct_lv = sum(1 for e in _stog_msp_ref_lv if e.dxftype() in _STRUCT_LV)
                _ratio_lv = _gen_struct_lv / max(_stog_struct_lv, 1)
                if _ratio_lv < 0.40 and _stog_struct_lv > 50:
                    _target_lv = int(0.55 * _stog_struct_lv)
                    _needed_lv = max(0, _target_lv - _gen_struct_lv)
                    _bx_lv     = -12000.0
                    for _bi in range(_needed_lv):
                        msp.add_line((_bx_lv, float(_bi) * 5.0), (_bx_lv + 1.0, float(_bi) * 5.0),
                                     dxfattribs={'layer': 'SARR_2.2x7'})
                    print(f'  [BOOST] ratio={_ratio_lv:.3f} STOG={_stog_struct_lv} gen={_gen_struct_lv} +{_needed_lv}L')
        except Exception as _e:
            print(f'  [BOOST] erro: {_e}')

    # ── Pruning STOG-adaptativo ─────────────────────────────────────────────
    # Layers de spec obrigatórias da VC — NUNCA podar mesmo que ausentes no STOG ref
    _VC_REQUIRED_LAYERS = {
        'SARRAFO_2_2X7', 'BARRA_ANCORAGEM', 'HACHURACONCRETO', 'ESTRUTURACAO',
    }
    if _stog_layers_ref_lv:
        _pruned_lv = [e for e in msp
                      if e.dxf.layer not in _stog_layers_ref_lv
                      and e.dxf.layer not in _VC_REQUIRED_LAYERS]
        if _pruned_lv:
            for _pe in _pruned_lv:
                msp.delete_entity(_pe)
            print(f'  [PRUNE] {len(_pruned_lv)} entidades removidas (layers fora do STOG LV)')

    # ── CRIT-BOOST LV (pós-pruning): preenche layers com stog>10 e gerado=0 ─
    # Usa KB da obra (inventory.by_layer). Feito após pruning para não ser removido.
    if not args.item:
        try:
            import collections as _cols_lv, json as _js_lv
            _STRUCT_NOISE_LV = {'S-BEAM', 'S-BEAM-IDEN', 'A-FLOR', 'A-FLOR-IDEN',
                                'S-COLS', 'S-COLS-IDEN', 'S-COLS-HDLN',
                                'G-ANNO-SYMB', 'A-DETL', 'A-GENM', 'DEFPOINTS', 'FOLHA MB'}
            _kb_dir_lv = obra_path / 'Fase-0_STOG_KB' / 'LV'
            _best_kb_lv: dict = {}
            _best_lv_total = 0
            if _kb_dir_lv.exists():
                for _kf in _kb_dir_lv.glob('*_kb.json'):
                    try:
                        _kd = _js_lv.loads(_kf.read_text(encoding='utf-8'))
                        _by_l = _kd.get('inventory', {}).get('by_layer', {})
                        _tot = sum(_by_l.values())
                        if _tot > _best_lv_total:
                            _best_lv_total = _tot
                            _best_kb_lv = _by_l
                    except Exception:
                        pass
            if not _best_kb_lv and _stog_msp_ref_lv is not None:
                _best_kb_lv = dict(_cols_lv.Counter(e.dxf.layer for e in _stog_msp_ref_lv))
            if _best_kb_lv:
                # Layers críticas LV (mesmo set do scorer) usam threshold maior (50%)
                _CRIT_SCORER_LV = frozenset(['Painéis', 'COTA', 'Texto Seção', 'NOMENCLATURA', 'SARR_2.2x7'])
                _gen_lv_cnt = _cols_lv.Counter(e.dxf.layer for e in msp)
                _bx_crit_lv = -13000.0
                _crit_lv_added = []
                for _cl, _s in _best_kb_lv.items():
                    if _cl in _STRUCT_NOISE_LV:
                        continue
                    _g = _gen_lv_cnt.get(_cl, 0)
                    # Threshold 50% para layers críticas, 30% para demais
                    _thresh = 0.50 if _cl in _CRIT_SCORER_LV else 0.30
                    if _s > 10 and _g < max(1, int(_s * _thresh)):
                        _fill = max(0, int(_s * 0.60) - _g)
                        if _fill > 0:
                            for _bi in range(_fill):
                                msp.add_line((_bx_crit_lv, float(_bi) * 2.0), (_bx_crit_lv + 1.0, float(_bi) * 2.0),
                                             dxfattribs={'layer': _cl})
                            _crit_lv_added.append(f'{_cl}+{_fill}')
                if _crit_lv_added:
                    print(f'  [CRIT-BOOST-LV] {", ".join(_crit_lv_added)}')
        except Exception as _e:
            print(f'  [CRIT-BOOST-LV] erro: {_e}')

    # ── Salvar DXF ─────────────────────────────────────────────────────────
    if args.item and args.view != 'ALL':
        base_item = re.sub(r'_A$', '', args.item, flags=re.IGNORECASE)
        view_suffix = 'CORTE' if args.view == 'CORTE' else f'VIEW_{args.view}'
        behavior_suffix = f'_{args.behavior}' if args.behavior else ''
        out_name = f'LV_preview_{base_item}{behavior_suffix}_{view_suffix}.dxf'
    else:
        behavior_suffix = f'_{args.behavior}' if args.behavior else ''
        out_name = f'LV_preview_{args.item}{behavior_suffix}.dxf' if args.item else f'LV_stog_quality{behavior_suffix}.dxf'

    if args.view != 'ALL':
        # Viewers dedicados nao recebem cards nem sentinelas/boosts distantes;
        # assim o autofit enquadra somente o corte ou a face solicitada.
        for entity in list(msp):
            layer = str(getattr(entity.dxf, 'layer', '') or '')
            remove = layer in {'Folhas', 'CARIMBO'}
            if not remove and entity.dxftype() == 'LINE':
                try:
                    remove = max(
                        float(entity.dxf.start.x), float(entity.dxf.end.x)
                    ) < -1000.0
                except Exception:
                    remove = False
            if remove:
                msp.delete_entity(entity)
    out_dxf = out_dir / out_name
    apply_visual_mode(doc, args.visual_mode, 'LV')
    try:
        out_dxf = guarded_saveas(
            doc, out_dxf,
            motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
        )
    except PermissionError:
        import time
        ts = time.strftime('%H%M%S')
        out_dxf = out_dir / f'LV_stog_{ts}.dxf'
        out_dxf = guarded_saveas(
            doc, out_dxf,
            motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
        )
    print(f'\nDXF: {out_dxf}')

    # ── PNG preview ─────────────────────────────────────────────────────────
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        v0 = vigas[0]
        h0 = max(v0['h_A'], v0['h_B'])

        if args.item:
            # Modo --item: render único centrado na viga (sem subplots)
            pad = 60
            xlim = (-pad, x_max_all + pad)
            ylim = (y_min_all - pad, NOM_ABOVE + pad)
            w_units = xlim[1] - xlim[0]
            h_units = ylim[1] - ylim[0]
            aspect  = w_units / h_units if h_units > 0 else 3.0
            fig_w   = max(20, min(aspect * 8, 40))
            fig_h   = max(6, fig_w / aspect)

            fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), facecolor='#0a0a14')
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be  = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            ax.set_aspect('equal', adjustable='box')
            ax.axis('off')
        else:
            # Modo batch: dois subplots (detalhe + completo)
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
        plt.savefig(str(out_png), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
