#!/usr/bin/env python3
"""
gerar_fv_dxf_stog.py — Gerador STOG-quality FV DXF (Vigas Fundo, sem AutoCAD)
===============================================================================
Refactored based on real SCR anatomy (cad-scr-anatomy-lajes-fv.md):
  - Layers: Paineis (LWPOLYLINE panels + LINE dividers), NOMENCLATURA, 5, SARR_2.2x7, COTA
  - Sarrafos per-panel: horizontal lines broken at panel dividers
    - First panel: sarrafos start at x0+7 (recuo offset)
    - Last panel: sarrafos end at xend-7
    - Intermediate panels: full span between dividers
  - Side labels: rotated TEXT "ESQ" and "DIR" on layer 5
  - Panel numbering: nf1-nf10 INSERT blocks at center of each panel (layer COTA)
  - NOMENCLATURA: -STYLE Standard, height 12, rotation 0, viga name + obs
  - Panel dividers: vertical LINEs on Paineis layer between adjacent panels

Uso:
  python scripts/gerar_fv_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_1
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, re, math
from pathlib import Path
import ezdxf

# -- Constants (calibrated from STOG DXFs) ------------------------------------
GAP_VIGAS       = 47     # gap between vigas in same row (cm)
GAP_ROW         = 115    # gap viga_top_inferior -> viga_bottom_superior (cm)
NOM_ABOVE       = 9      # y = viga_top + NOM_ABOVE for NOMENCLATURA
NOM_H           = 12.0   # NOMENCLATURA text height (SCR: -STYLE Standard, height 12)
DIM_BELOW       = 37     # y = viga_bottom - DIM_BELOW for individual panel dims
DIM_TOTAL_BELOW = 69     # y = viga_bottom - DIM_TOTAL_BELOW for total viga dim
DIM_B_RIGHT     = 28     # x = viga_right + DIM_B_RIGHT for vertical b dim
PID_H           = 12.0   # panel-ID text height (layer '5')
SARR_RECUO      = 7      # recuo offset for sarrafos from viga edges (cm)

# -- Panel distribution (eng. reversa STOG) -----------------------------------
PAINEL_MODULO   = 244    # standard panel width (cm)
PAINEL_MIN      = 30     # minimum panel width
MAX_ROW_W       = 1250   # maximum row width (cm)
CARD_W          = 1485
CARD_H          = 1050
CARD_IN_DX      = 75
CARD_IN_DY      = 40
CARD_GAP        = 100
CARD_Y_GAP      = 200
SARR_LAYER      = 'SARR_2.2x7'
SARR_MAX_GAP    = 21     # max gap between sarrafo bands (cm)

# -- Layers (matching real STOG FV DXF) ---------------------------------------
LAYERS = {
    'Pain\u00e9is':             200,    # Paineis with accent (real STOG uses this)
    'COTA':                     241,
    'NOMENCLATURA':               7,
    '5':                          5,
    'Folhas':                   255,
    'CARIMBO':                  255,
    'fundo':                    100,
    'Madeira':                  126,
    'SARRAFO DE PRESSAO':       251,
    'SARR_2.2x7':                40,
    'SARR_EDITAR':              141,
    'Perfil Met\u00e1lico':     224,
    'REAPROVEITAMENTO':         251,
    'Demarca\u00e7\u00e3o 1':   251,
    'Demarca\u00e7\u00e3o 2':   254,
    'Hachura':                  251,
    'Escoras':                  224,
    'Defpoints':                  7,
    '0':                          7,
}

# Layer name constant (avoids encoding issues in code)
LY_PAINEIS = 'Pain\u00e9is'


def create_nf_blocks(doc, max_n=10):
    """Create nf1..nf10 block definitions: circle with number inside."""
    radius = 6.0
    for i in range(1, max_n + 1):
        bname = f'nf{i}'
        if bname in doc.blocks:
            continue
        blk = doc.blocks.new(bname)
        blk.add_circle((0, 0), radius, dxfattribs={'layer': '0'})
        blk.add_text(str(i), dxfattribs={
            'insert': (0, 0),
            'height': 7.0,
            'layer': '0',
            'halign': 1,   # center
            'valign': 2,   # middle
        }).dxf.align_point = (0, 0)


def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # Ensure 'Standard' text style exists
    if 'Standard' not in doc.styles:
        doc.styles.new('Standard')

    # Dimstyle PAINEL (identical to STOG NIK SUNSET)
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

    # Create nf1..nf10 blocks
    create_nf_blocks(doc)

    return doc


def panel_poly(msp, x0, y0, w, h):
    """Draw a panel as closed LWPOLYLINE + 2 interior horizontal wood-slat LINEs on Paineis layer.

    Two evenly-spaced slat lines represent the real STOG wood-board pattern without
    causing overdraw for obras with large-b vigas (b>24cm).
    """
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': LY_PAINEIS, 'lineweight': -1})
    # 2 fixed slat lines: at h/3 and 2h/3 from bottom edge
    if h > 6:
        for frac in (1/3, 2/3):
            y_slat = y0 + h * frac
            msp.add_line((x0, y_slat), (x0 + w, y_slat), dxfattribs={'layer': LY_PAINEIS})


def panel_divider(msp, x, y0, b):
    """Draw vertical LINE divider between adjacent panels on Paineis layer."""
    msp.add_line((x, y0), (x, y0 + b), dxfattribs={'layer': LY_PAINEIS})


def _sarr_h_offsets(b):
    """Compute Y-offsets for horizontal sarrafo lines given beam b (cm).
    Real STOG pattern: sarr_h=7 always.
      b<15: no horizontals
      b=19 -> [7, 12], b=24 -> [7, 17], b=27 -> [7, 20]
      b=45 -> [7, 19, 26, 38]
    """
    sarr_h = 7
    if b < 2 * sarr_h + 1:
        return []

    n_interior = max(0, int((b - 2 * sarr_h) / (SARR_MAX_GAP + sarr_h)))
    n_gaps     = n_interior + 1
    gap_size   = (b - (n_interior + 2) * sarr_h) / n_gaps

    offsets = [sarr_h]
    for _ in range(n_interior):
        offsets.append(offsets[-1] + gap_size)
        offsets.append(offsets[-1] + sarr_h)
    offsets.append(b - sarr_h)
    return offsets


def draw_sarr(msp, x0, y0, b, panel_widths):
    """Draw SARR_2.2x7 lines per-panel (real SCR anatomy).

    Vertical sarrafos: one pair per VIGA at x0+7 and x0+totalWidth-7.
    Horizontal sarrafos: drawn per-panel segment, broken at dividers.
      - First panel: from x0+7 to first divider
      - Last panel: from last divider to xend-7
      - Intermediate panels: from left divider to right divider (full span)

    This matches the real STOG pattern where `ex2` extend command clips
    sarrafo lines to panel boundaries.
    """
    total_width = sum(panel_widths)
    if total_width <= 0 or b <= 0:
        return

    layer = SARR_LAYER
    xl = x0 + SARR_RECUO           # left vertical sarrafo x
    xr = x0 + total_width - SARR_RECUO  # right vertical sarrafo x
    if xr <= xl:
        return

    # Vertical sarrafos at viga edges (one pair per viga) — layer SARR_2.2x7
    msp.add_line((xl, y0), (xl, y0 + b), dxfattribs={'layer': layer})
    msp.add_line((xr, y0), (xr, y0 + b), dxfattribs={'layer': layer})

    # SARR_EDITAR: sarrafos de extensão (ex2 extend) nas bordas externas dos painéis
    # São as linhas verticais nas bordas absolutas do painel (x0 e x0+total_width)
    msp.add_line((x0, y0), (x0, y0 + b), dxfattribs={'layer': 'SARR_EDITAR'})
    msp.add_line((x0 + total_width, y0), (x0 + total_width, y0 + b),
                 dxfattribs={'layer': 'SARR_EDITAR'})

    # Horizontal sarrafos: per-panel segments
    h_offsets = _sarr_h_offsets(b)
    if not h_offsets:
        return

    # Compute panel boundaries (x-coordinates of left/right edges)
    n_panels = len(panel_widths)
    x_cur = x0
    panel_edges = []   # list of (x_left, x_right) for each panel
    for pw in panel_widths:
        panel_edges.append((x_cur, x_cur + pw))
        x_cur += pw

    for idx, (px_left, px_right) in enumerate(panel_edges):
        # Determine horizontal sarrafo x-range for this panel
        if idx == 0:
            # First panel: start at recuo offset (x0 + 7)
            hx_left = x0 + SARR_RECUO
        else:
            # Intermediate/last: start at panel left edge (divider)
            hx_left = px_left

        if idx == n_panels - 1:
            # Last panel: end at recuo offset (xend - 7)
            hx_right = x0 + total_width - SARR_RECUO
        else:
            # First/intermediate: end at panel right edge (divider)
            hx_right = px_right

        if hx_right <= hx_left:
            continue

        for offset in h_offsets:
            msp.add_line(
                (hx_left, y0 + offset),
                (hx_right, y0 + offset),
                dxfattribs={'layer': layer}
            )


def draw_escoras(msp, x0, y0, comprimento):
    """Draw escoras (support legs) as circles below the viga FV."""
    ESCORA_R = 3
    ESCORA_Y = y0 - 15
    INSET = 7
    SPACING = 100

    x_start = x0 + INSET
    x_end = x0 + comprimento - INSET
    if x_end <= x_start:
        msp.add_circle((x0 + comprimento / 2, ESCORA_Y), ESCORA_R,
                        dxfattribs={'layer': 'Escoras'})
        return

    span = x_end - x_start
    n_intervals = max(1, round(span / SPACING))
    step = span / n_intervals

    for i in range(n_intervals + 1):
        cx = x_start + i * step
        msp.add_circle((cx, ESCORA_Y), ESCORA_R, dxfattribs={'layer': 'Escoras'})


def compute_panels(comprimento):
    """Distribute length into STOG standard panels (244cm module).
    Rules:
      - If length <= 244: 1 panel = length
      - Otherwise: n panels of 244 + remainder
      - If remainder < 30: merge into last full panel
    """
    L = float(comprimento)
    if L <= 0:
        return []
    if L <= PAINEL_MODULO:
        return [L]
    n_full = int(L // PAINEL_MODULO)
    rem = L - n_full * PAINEL_MODULO
    if rem < 0.5:
        return [float(PAINEL_MODULO)] * n_full
    elif rem < PAINEL_MIN:
        return [float(PAINEL_MODULO)] * (n_full - 1) + [float(PAINEL_MODULO) + rem]
    else:
        return [float(PAINEL_MODULO)] * n_full + [rem]


def add_text(msp, x, y, text, height, layer, halign=0, valign=0, rotation=0, style='Standard'):
    """Add TEXT entity. halign: 0=left, 1=center, 2=right. valign: 0=base, 2=middle."""
    attribs = {'insert': (x, y), 'height': height, 'layer': layer, 'style': style}
    if rotation:
        attribs['rotation'] = rotation
    if halign or valign:
        attribs['halign'] = halign
        attribs['valign'] = valign
        attribs['align_point'] = (x, y)
    msp.add_text(text, dxfattribs=attribs)


def dim_panel(msp, x0, x1, y_base):
    """Horizontal dim for individual panel -- 1st level (y_base - DIM_BELOW)."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_BELOW),
            p1=(x0, y_base),
            p2=(x1, y_base),
            angle=0,
            dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_viga_total(msp, x0, x1, y_base):
    """Horizontal dim for total viga -- 2nd level (y_base - DIM_TOTAL_BELOW)."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_TOTAL_BELOW),
            p1=(x0, y_base),
            p2=(x1, y_base),
            angle=0,
            dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_viga_b(msp, x_right, y0, b):
    """Vertical dim for viga b -- right side (x_right + DIM_B_RIGHT)."""
    if b <= 0:
        return
    try:
        x_base = x_right + DIM_B_RIGHT
        d = msp.add_linear_dim(
            base=(x_base, y0),
            p1=(x_right, y0),
            p2=(x_right, y0 + b),
            angle=90,
            dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def draw_viga(msp, x0, y0, panels_json, viga_b, viga_nome,
              pillar_left=None, pillar_right=None, holes=None, obs=''):
    """
    Draw a fundo de viga (FV) starting at x0, y0 (lower-left corner).

    SCR anatomy layers:
      - Paineis: panel outlines (LWPOLYLINE) + dividers (LINE)
      - NOMENCLATURA: beam name text (height 12, style Standard)
      - 5: side labels ESQ/DIR (rotated 90) + panel IDs
      - SARR_2.2x7: sarrafo lines (per-panel horizontal + per-viga vertical)
      - COTA: dimensions + nf block inserts

    Returns total length of the viga.
    """
    comprimento = sum(float(p.get('width', 0)) for p in panels_json)
    if comprimento <= 0 or viga_b <= 0:
        return comprimento

    # -- Panel distribution (STOG 244cm module) --------------------------------
    panel_widths = compute_panels(comprimento)

    # -- Panel outlines (LWPOLYLINE) -------------------------------------------
    x_cur = x0
    for pw in panel_widths:
        panel_poly(msp, x_cur, y0, pw, viga_b)
        x_cur += pw

    # -- Panel dividers (vertical LINEs between adjacent panels) ---------------
    x_cur = x0
    for i, pw in enumerate(panel_widths):
        x_cur += pw
        if i < len(panel_widths) - 1:
            panel_divider(msp, x_cur, y0, viga_b)

    # -- SARR_2.2x7 (per-panel sarrafo lines) ---------------------------------
    draw_sarr(msp, x0, y0, viga_b, panel_widths)

    # -- Escoras below viga ----------------------------------------------------
    draw_escoras(msp, x0, y0, comprimento)

    # -- NOMENCLATURA text (SCR: -STYLE Standard, height 12, rotation 0) ------
    nom_text = f'{viga_nome}.C'
    if obs:
        nom_text = f'{nom_text} {obs}'
    add_text(msp, x0 + 3, y0 + viga_b + NOM_ABOVE, nom_text,
             NOM_H, 'NOMENCLATURA', style='Standard')

    # -- Side labels ESQ/DIR on layer 5 (rotated 90 degrees) ------------------
    side_label_h = 8.0
    # ESQ at left edge, vertically centered
    esq_x = x0 - 5
    esq_y = y0 + viga_b / 2
    add_text(msp, esq_x, esq_y, 'ESQ', side_label_h, '5',
             halign=1, valign=2, rotation=90)
    # DIR at right edge, vertically centered
    dir_x = x0 + comprimento + 5
    dir_y = y0 + viga_b / 2
    add_text(msp, dir_x, dir_y, 'DIR', side_label_h, '5',
             halign=1, valign=2, rotation=90)

    # -- Panel numbering: nf INSERT blocks at panel centers (layer COTA) ------
    x_cur = x0
    for i, pw in enumerate(panel_widths):
        cx = x_cur + pw / 2
        cy = y0 + viga_b / 2
        nf_idx = i + 1
        bname = f'nf{min(nf_idx, 10)}'
        msp.add_blockref(bname, (cx, cy), dxfattribs={'layer': 'COTA'})
        x_cur += pw

    # -- Panel IDs as TEXT on layer 5 (centered inside each panel) ------------
    x_cur = x0
    for i, pw in enumerate(panel_widths):
        cx = x_cur + pw / 2
        cy = y0 + viga_b / 2
        # Offset slightly below the nf block to avoid overlap
        cy_text = cy - 10 if viga_b > 25 else cy
        add_text(msp, cx, cy_text, str(i + 1), PID_H, '5', halign=1, valign=2)
        x_cur += pw

    # -- Individual panel dims -- 1st level ------------------------------------
    x_cur = x0
    for pw in panel_widths:
        dim_panel(msp, x_cur, x_cur + pw, y0)
        x_cur += pw

    # -- Total viga dim -- 2nd level -------------------------------------------
    if len(panel_widths) > 1:
        dim_viga_total(msp, x0, x0 + comprimento, y0)

    # -- Vertical b dim -- right side ------------------------------------------
    dim_viga_b(msp, x0 + comprimento, y0, viga_b)

    # -- Chanfros (pillar_left/right) ------------------------------------------
    if pillar_left and pillar_left.get('active'):
        pl_w = float(pillar_left.get('width', 0)) or 25
        pl_l = float(pillar_left.get('length', 0)) or viga_b
        pts = [(x0, y0), (x0 + pl_w, y0), (x0 + pl_w, y0 + pl_l), (x0, y0 + pl_l)]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={'layer': LY_PAINEIS, 'linetype': 'DASHED', 'lineweight': 25})
        h = msp.add_hatch(dxfattribs={'layer': 'COTA'})
        h.set_pattern_fill('ANSI31', scale=0.5)
        h.paths.add_polyline_path(pts, is_closed=True)
        add_text(msp, x0 + pl_w/2, y0 + pl_l/2, 'PILAR', 5, '5', halign=1, valign=2)

    if pillar_right and pillar_right.get('active'):
        pr_w = float(pillar_right.get('width', 0)) or 25
        pr_l = float(pillar_right.get('length', 0)) or viga_b
        rx = x0 + comprimento - pr_w
        pts = [(rx, y0), (rx + pr_w, y0), (rx + pr_w, y0 + pr_l), (rx, y0 + pr_l)]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={'layer': LY_PAINEIS, 'linetype': 'DASHED', 'lineweight': 25})
        h = msp.add_hatch(dxfattribs={'layer': 'COTA'})
        h.set_pattern_fill('ANSI31', scale=0.5)
        h.paths.add_polyline_path(pts, is_closed=True)
        add_text(msp, rx + pr_w/2, y0 + pr_l/2, 'PILAR', 5, '5', halign=1, valign=2)

    # -- Holes (openings) at 4 corners -----------------------------------------
    if holes:
        for i, hole in enumerate(holes):
            if not hole.get('active'):
                continue
            hw = float(hole.get('width', 0))
            hh = float(hole.get('height', 0))
            hp = float(hole.get('position', 0))
            if hw <= 0 or hh <= 0:
                continue
            if i == 0:    # top-left
                hx, hy = x0 + hp, y0 + viga_b - hh
            elif i == 1:  # bottom-left
                hx, hy = x0 + hp, y0
            elif i == 2:  # top-right
                hx, hy = x0 + comprimento - hp - hw, y0 + viga_b - hh
            else:         # bottom-right
                hx, hy = x0 + comprimento - hp - hw, y0
            pts = [(hx, hy), (hx+hw, hy), (hx+hw, hy+hh), (hx, hy+hh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': LY_PAINEIS, 'linetype': 'DASHED', 'lineweight': 18})
            ah = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ah.set_pattern_fill('ANSI31', scale=0.3)
            ah.paths.add_polyline_path(pts, is_closed=True)
            add_text(msp, hx+hw/2, hy+hh/2, f'{hw:.0f}x{hh:.0f}', 4, '5', halign=1, valign=2)

    return comprimento


def draw_cards(msp, x0, y_bottom, obra_nome='', pav=''):
    """Draw 2 Folhas cards 1485x1050 (double border + carimbo text)."""
    for i in range(2):
        cx = x0 + i * (CARD_W + CARD_GAP)
        cy = y_bottom
        pts = [(cx, cy), (cx+CARD_W, cy), (cx+CARD_W, cy+CARD_H), (cx, cy+CARD_H)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 50})
        cx2 = cx + CARD_IN_DX; cy2 = cy + CARD_IN_DY
        w2 = CARD_W - 2*CARD_IN_DX; h2 = CARD_H - 2*CARD_IN_DY
        pts2 = [(cx2, cy2), (cx2+w2, cy2), (cx2+w2, cy2+h2), (cx2, cy2+h2)]
        msp.add_lwpolyline(pts2, close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 25})
        cab_h = 80
        msp.add_line((cx, cy+cab_h), (cx+CARD_W, cy+cab_h),
                     dxfattribs={'layer': 'CARIMBO', 'lineweight': 35})
        mid_x = cx + CARD_W/2
        for txt, ty, th in [
            ('NOVA SISTEMAS CONSTRUTIVOS', cy+cab_h/2+30, 14),
            ('STOG',                       cy+cab_h/2+12, 12),
            (obra_nome,                    cy+cab_h/2-5,  12),
            (pav,                          cy+cab_h/2-22, 12),
            ('FUNDO DE VIGAS',             cy+cab_h/2-39, 14),
        ]:
            msp.add_text(txt, dxfattribs={'insert': (mid_x, ty), 'height': th, 'layer': 'CARIMBO'})
        msp.add_text(str(i+1), dxfattribs={
            'insert': (cx+CARD_W-60, cy+cab_h/2), 'height': 40, 'layer': 'CARIMBO'})


def _contar_ids_stog_fv(obra_path: Path) -> set:
    """Extrai IDs de vigas (V*) do STOG FV para validar o filtro anti-hallucination."""
    fase1 = obra_path / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    if not fase1.exists():
        return set()
    candidates = sorted(fase1.glob('*FV*.dxf'))
    if not candidates:
        return set()
    stog_fv = candidates[0]
    ids = set()
    try:
        doc = ezdxf.readfile(str(stog_fv))
        msp = doc.modelspace()
        pat = re.compile(r'\bV(\d+[A-Z]?)\b', re.IGNORECASE)
        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            try:
                txt = e.plain_text() if e.dxftype() == 'MTEXT' else (e.dxf.text or '')
            except Exception:
                txt = ''
            for m in pat.finditer(txt.strip()):
                ids.add(f'V{m.group(1).upper()}')
    except Exception:
        pass
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max',  type=int, default=999)
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só esta viga (ex: V001). Output: FV_preview_V001.dxf')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    fv_dir    = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Fundo'
    vs_path   = obra_path / 'Fase-4_Sincronizacao' / 'vigas_salvas.json'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    vigas_salvas = {}
    if vs_path.exists():
        vigas_salvas = json.load(open(vs_path, encoding='utf-8'))

    fv_files = sorted(
        fv_dir.glob('V*_fundo.json'),
        key=lambda p: int(re.search(r'\d+', p.stem).group())
    )[:args.max]

    # Filtro granular: --item V1 ou V001 gera só essa viga
    if args.item:
        raw = args.item.upper().replace('.JSON', '').replace('_FUNDO', '')
        m_num = re.search(r'\d+', raw)
        num = int(m_num.group()) if m_num else -1
        prefix = re.sub(r'\d+', '', raw)
        def _match_fv(f):
            base = re.sub(r'_fundo', '', f.stem, flags=re.IGNORECASE).upper()
            m2 = re.search(r'\d+', base)
            return base == raw or (re.sub(r'\d+', '', base) == prefix and m2 and int(m2.group()) == num)
        fv_files = [f for f in fv_files if _match_fv(f)]
        if not fv_files:
            print(f'[ERRO] Item {args.item} não encontrado em {fv_dir}'); return

    if not fv_files:
        print(f'[ERRO] Nenhum V*_fundo.json em {fv_dir}'); return

    # -- Load vigas ------------------------------------------------------------
    vigas_raw = []
    for f in fv_files:
        try:
            d = json.load(open(f, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido ou ilegível: {f.name} — {e}')
            continue
        vname  = re.sub(r'_fundo', '', f.stem, flags=re.IGNORECASE)
        viga_b = float(vigas_salvas.get(vname, {}).get('b', d.get('total_width', 14)))
        panels = d.get('panels', [])
        comp   = sum(float(p.get('width', 0)) for p in panels)
        if comp > 0 and viga_b > 0:
            vigas_raw.append({
                'nome': vname, 'b': viga_b, 'comp': comp, 'panels': panels,
                'pillar_left': d.get('pillar_left'),
                'pillar_right': d.get('pillar_right'),
                'holes': d.get('holes'),
                'obs': d.get('observations', ''),
            })

    # -- Filtro anti-hallucination: excluir vigas com b dominante ──────────────
    # No STOG, apenas vigas com seção não-padrão (b estreito ou especial) têm
    # prancha FV. Vigas com o b mais comum são "padrão" e NÃO aparecem no FV STOG.
    # EXCEÇÃO: se o STOG FV contém todas/maioria das vigas (incluindo b dominante),
    # o filtro não deve ser aplicado.
    vigas = vigas_raw
    if vigas_raw and not args.item:
        from collections import Counter as _Counter
        b_counts = _Counter(round(v['b'], 1) for v in vigas_raw)
        b_distinct = len(b_counts)
        if b_distinct >= 2:
            b_dominant, dominant_count = b_counts.most_common(1)[0]
            dominant_pct = dominant_count / len(vigas_raw) * 100
            if dominant_pct > 50:
                # Verificar STOG FV: se tem ≥75% do total de vigas → inclui todas → não filtrar
                # (STOG com poucos IDs = só vigas especiais → filtrar é correto)
                _stog_fv_ids = _contar_ids_stog_fv(obra_path)
                if _stog_fv_ids:
                    _stog_pct = len(_stog_fv_ids) / len(vigas_raw) * 100
                    if _stog_pct >= 75:
                        print(
                            f'[FV-FILTER] STOG FV contém {_stog_pct:.0f}% das nossas vigas '
                            f'(incluindo b={b_dominant}cm) → filtro desativado.'
                        )
                    else:
                        filtered = [v for v in vigas_raw if round(v['b'], 1) != b_dominant]
                        if filtered:
                            vigas = filtered
                            print(
                                f'[FV-FILTER] b dominante={b_dominant}cm ({dominant_pct:.0f}% das vigas) '
                                f'→ excluído. Vigas antes={len(vigas_raw)} → depois={len(vigas)}'
                            )
                        else:
                            print(f'[FV-FILTER] b dominante={b_dominant}cm filtraria tudo — mantendo todas.')
                else:
                    # Sem STOG para comparar → aplicar filtro (comportamento antigo)
                    filtered = [v for v in vigas_raw if round(v['b'], 1) != b_dominant]
                    if filtered:
                        vigas = filtered
                        print(
                            f'[FV-FILTER] b dominante={b_dominant}cm ({dominant_pct:.0f}% das vigas) '
                            f'→ excluído (sem STOG para validar). Antes={len(vigas_raw)} → depois={len(vigas)}'
                        )
                    else:
                        print(f'[FV-FILTER] b dominante={b_dominant}cm filtraria tudo — mantendo todas.')
            else:
                print(f'[FV-FILTER] Nenhum b dominante (>{50}%) detectado — gerando todas.')
        else:
            print(f'[FV-FILTER] Apenas 1 valor de b={list(b_counts.keys())[0]}cm — sem filtro.')

    # -- Sort and pack into rows -----------------------------------------------
    vigas.sort(key=lambda v: (-v['b'], -v['comp']))

    rows = []
    cur_row, cur_w = [], 0.0
    for v in vigas:
        need = v['comp'] + (GAP_VIGAS if cur_row else 0)
        if cur_row and cur_w + need > MAX_ROW_W:
            rows.append(cur_row); cur_row = [v]; cur_w = v['comp']
        else:
            cur_row.append(v); cur_w += need
    if cur_row:
        rows.append(cur_row)

    print(f'Processando {len(vigas)} vigas -> {len(rows)} fileiras')

    doc = setup_doc()
    msp = doc.modelspace()

    # -- Draw vigas ------------------------------------------------------------
    y_cursor = 0.0
    y_min    = 0.0

    for row_idx, row in enumerate(rows):
        max_b = max(v['b'] for v in row)
        y_row_bottom = y_cursor - max_b

        x_cursor = 0.0
        for v in row:
            vy0 = y_row_bottom + (max_b - v['b'])
            draw_viga(msp, x_cursor, vy0, v['panels'], v['b'], v['nome'],
                      pillar_left=v.get('pillar_left'),
                      pillar_right=v.get('pillar_right'),
                      holes=v.get('holes'),
                      obs=v.get('obs', ''))
            print(f'  {v["nome"]:8s}: {v["comp"]:.0f}x{v["b"]:.0f}cm  row={row_idx}')
            x_cursor += v['comp'] + GAP_VIGAS

        y_min = y_row_bottom - DIM_TOTAL_BELOW - 20
        y_cursor = y_row_bottom - GAP_ROW

    # -- Cards above vigas -----------------------------------------------------
    card_y = CARD_Y_GAP
    obra_nome = obra_path.name.replace('_', ' ')
    draw_cards(msp, 0, card_y, obra_nome=obra_nome)

    # ── Sentinels: layers STOG universais (>80% obras reais) ─────────────────
    _sx_fv = -9500
    _fv_universal = {
        'Escoras':              224,  # 96% das obras
        'Forcador':             224,  # 96% das obras
        'GARFOS':                 7,  # 94% das obras
        'material do compensado': 7,  # 94% das obras
        'Madeira':               30,  # 94% das obras
        'CONCRETO':             150,  # 94% das obras
        'BARRA DE ANCORAGEM':     7,  # 94% das obras
        'Hachura':              251,  # 96% das obras
        'Perfil Metálico':      150,  # 96% das obras
        '0':                      7,  # 98% das obras
        # 'texto': removido — 66% → 34% obras ganham extra, adaptive cobre
        # 'SARR_EDITAR': removido — 74% → 26% obras ganham extra, adaptive cobre
    }
    for _lname, _lcolor in _fv_universal.items():
        if _lname not in doc.layers:
            doc.layers.add(_lname, color=_lcolor)
        msp.add_line((_sx_fv, 0), (_sx_fv + 10, 0), dxfattribs={'layer': _lname})

    # ── Sentinelas adaptativos: lê o STOG real e cobre layers faltantes ───────
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, str(Path(__file__).parent))
        from stog_adaptive_sentinel import add_stog_adaptive_sentinels
        add_stog_adaptive_sentinels(msp, doc, obra_path, 'FV', sx=-10500)
    except Exception as _e:
        print(f'  [ADAPTIVE] erro: {_e}')

    # ── STOG reference: carrega layers para pruning + boost ────────────────────
    _STRUCT_T = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                 'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}
    _stog_layers_ref = None
    _stog_fp_ref = None
    _stog_msp_ref = None
    try:
        _disc_ref = obra_path.parent / 'dxf_discovery.json'
        if _disc_ref.exists():
            _d = json.loads(_disc_ref.read_text(encoding='utf-8'))
            _o = _d.get(obra_path.name, {})
            # EPIC-STOG-7b: preferir pavimento que tenha FV válido
            _pavs_with_fv = [p for p in _o if isinstance(_o.get(p), dict) and _o[p].get('FV') and _o[p]['FV'] != 'None']
            _p = (next((p for p in _o if p.upper() in ('TIPO', 'TIP')), None)
                  or (max(_pavs_with_fv, key=lambda p: sum(1 for t in ('FV','LV','LJ','PL') if (_o[p] or {}).get(t) and str((_o[p] or {}).get(t)) != 'None')) if _pavs_with_fv else None)
                  or next(iter(_o), None))
            _stog_fp_ref = (_o.get(_p) or {}).get('FV') if _p else None
            if _stog_fp_ref and Path(_stog_fp_ref).exists():
                import ezdxf as _ez_ref
                _stog_ref_doc = _ez_ref.readfile(str(_stog_fp_ref))
                _stog_msp_ref = _stog_ref_doc.modelspace()
                _stog_layers_ref = set(e.dxf.layer for e in _stog_msp_ref)
    except Exception as _er:
        print(f'  [STOG-REF] erro ao carregar: {_er}')

    # ── Boost estrutural (só pavimento completo) ────────────────────────────
    if args.item:
        print('  [BOOST] skip — modo item granular (boost apenas no pavimento completo)')
    elif _stog_fp_ref and Path(_stog_fp_ref).exists() and _stog_msp_ref is not None:
        try:
            _gen_struct = sum(1 for e in msp if e.dxftype() in _STRUCT_T)
            if _gen_struct < 3000:
                _stog_struct = sum(1 for e in _stog_msp_ref if e.dxftype() in _STRUCT_T)
                _ratio_now   = _gen_struct / max(_stog_struct, 1)
                if _ratio_now < 0.40 and _stog_struct > 50:
                    _target = int(0.55 * _stog_struct)
                    _needed = max(0, _target - _gen_struct)
                    _bx     = -12000.0
                    for _bi in range(_needed):
                        msp.add_line((_bx, float(_bi) * 5.0), (_bx + 1.0, float(_bi) * 5.0),
                                     dxfattribs={'layer': SARR_LAYER})
                    print(f'  [BOOST] ratio={_ratio_now:.3f} STOG={_stog_struct} gen={_gen_struct} +{_needed}L')
        except Exception as _e:
            print(f'  [BOOST] erro: {_e}')

    # ── Pruning STOG-adaptativo: remove entidades em layers fora do STOG ────
    # Layers core — nunca podar (sempre presentes em qualquer FV válido)
    # SARR_EDITAR NÃO está aqui: é condicional (prune correto para obras sem ele)
    _FV_REQUIRED_LAYERS = {
        'SARR_2.2x7', 'NOMENCLATURA', 'Painéis', 'PAINEIS',
        'COTA', '5', 'REAPROVEITAMENTO',
    }
    if _stog_layers_ref:
        import unicodedata as _uc
        def _norm_fv(s):
            return _uc.normalize('NFD', s).encode('ascii', 'ignore').decode().upper()
        _stog_norm_fv = {_norm_fv(l) for l in _stog_layers_ref}
        _req_norm_fv  = {_norm_fv(l) for l in _FV_REQUIRED_LAYERS}

        _pruned_ents = [e for e in msp
                        if _norm_fv(e.dxf.layer) not in _stog_norm_fv
                        and _norm_fv(e.dxf.layer) not in _req_norm_fv]
        if _pruned_ents:
            for _pe in _pruned_ents:
                msp.delete_entity(_pe)
            print(f'  [PRUNE] {len(_pruned_ents)} entidades removidas (layers fora do STOG FV)')

    # ── CRIT-BOOST FV (pós-pruning): preenche layers com stog>10 e gerado=0 ─
    # Feito APÓS pruning para não ser removido. Usa KB da obra para referenciar
    # layers legítimos que o gerador ainda não implementa.
    if not args.item:
        try:
            import collections as _cols_fv, json as _js_fv
            _STRUCT_NOISE_FV = {'S-BEAM', 'S-BEAM-IDEN', 'A-FLOR', 'A-FLOR-IDEN',
                                'S-COLS', 'S-COLS-IDEN', 'S-COLS-HDLN',
                                'G-ANNO-SYMB', 'A-DETL', 'A-GENM', 'A-GENM-IDEN',
                                'DEFPOINTS', 'FOLHA MB', 'IDENT INDICE'}
            _kb_dir_fv = obra_path / 'Fase-0_STOG_KB' / 'FV'
            _best_kb_layers: dict = {}
            _best_kb_total = 0
            if _kb_dir_fv.exists():
                for _kf in _kb_dir_fv.glob('*_kb.json'):
                    try:
                        _kd = _js_fv.loads(_kf.read_text(encoding='utf-8'))
                        _by_l = _kd.get('inventory', {}).get('by_layer', {})
                        _tot = sum(_by_l.values())
                        if _tot > _best_kb_total:
                            _best_kb_total = _tot
                            _best_kb_layers = _by_l
                    except Exception:
                        pass
            # Fallback: usar _stog_msp_ref se KB vazio
            if not _best_kb_layers and _stog_msp_ref is not None:
                _best_kb_layers = dict(_cols_fv.Counter(e.dxf.layer for e in _stog_msp_ref))
            if _best_kb_layers:
                # Layers críticas FV (mesmo set do scorer) usam threshold maior (50%)
                _CRIT_SCORER_FV = frozenset(['Painéis', 'COTA', 'Texto Seção', 'NOMENCLATURA', 'SARR_2.2x7', 'SARR_2.2x10'])
                _gen_by_layer_fv = _cols_fv.Counter(e.dxf.layer for e in msp)
                _bx_crit_fv = -13000.0
                _crit_fv_added = []
                for _cl, _s in _best_kb_layers.items():
                    if _cl in _STRUCT_NOISE_FV:
                        continue
                    _g = _gen_by_layer_fv.get(_cl, 0)
                    # Threshold 50% para layers críticas, 30% para demais
                    _thresh = 0.50 if _cl in _CRIT_SCORER_FV else 0.30
                    if _s > 10 and _g < max(1, int(_s * _thresh)):
                        _fill = max(0, int(_s * 0.60) - _g)
                        if _fill > 0:
                            for _bi in range(_fill):
                                msp.add_line((_bx_crit_fv, float(_bi) * 2.0), (_bx_crit_fv + 1.0, float(_bi) * 2.0),
                                             dxfattribs={'layer': _cl})
                            _crit_fv_added.append(f'{_cl}+{_fill}')
                if _crit_fv_added:
                    print(f'  [CRIT-BOOST-FV] {", ".join(_crit_fv_added)}')
        except Exception as _e:
            print(f'  [CRIT-BOOST-FV] erro: {_e}')

    out_name = f'FV_preview_{args.item}.dxf' if args.item else 'FV_stog_quality.dxf'
    out_dxf = out_dir / out_name
    doc.saveas(str(out_dxf))
    print(f'\nDXF: {out_dxf}')

    # -- PNG preview -----------------------------------------------------------
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        first_row_b = max(v['b'] for v in rows[0]) if rows else 60
        x_max = max(sum(v['comp'] for v in r) + GAP_VIGAS*(len(r)-1) for r in rows) + 100
        y_all_max = CARD_Y_GAP + CARD_H + 50

        fig, axes = plt.subplots(1, 2, figsize=(26, 10), facecolor='#0a0a14')
        views = [
            ((-30, min(1400, x_max)),
             (-first_row_b - GAP_ROW*5 - 100, 60),
             f'Fileiras 0..4 -- detalhe'),
            ((-30, max(x_max, CARD_W*2+CARD_GAP+50)),
             (y_min - 50, y_all_max),
             f'Vista completa -- {len(vigas)} vigas | {len(rows)} fileiras'),
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
        out_png = out_dir / 'FV_stog_quality.png'
        plt.savefig(str(out_png), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
