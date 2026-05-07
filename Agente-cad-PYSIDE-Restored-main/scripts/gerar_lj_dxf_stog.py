#!/usr/bin/env python3
"""
gerar_lj_dxf_stog.py — Gerador STOG-quality LJ DXF (Lajes, sem AutoCAD)
=========================================================================
Refactored to match real STOG delivery format.

Layers from real STOG LJ:
  paineis (Painéis, ACI 200) — panel boundary lines + DIMENSION
  3       (green,  ACI 3)    — structural outlines, paired sarrafo PLINEs, dim texts, HLAZ hatch lines
  4       (cyan,   ACI 4)    — V{n}/L{n} labels (TEXT h=15)
  7       (white,  ACI 7)    — pilar rectangles (LWPOLYLINE 5pt)
  9       (ACI 9)            — SOLID markers + escora LINEs
  1       (red,    ACI 1)    — X marks for reuse panels
  Hachura (ACI 251)          — SOLID fill HATCH
  AUX00   (ACI 7)            — MTEXT panel data
  REAPROVEITAMENTO (ACI 251) — ANSI31 HATCH reuse
  CARIMBO, Folhas            — card borders (cards mode only)

Panel divisions as PAIRED lines (sarrafo de pressao = 19cm gap) on layer 3.
Dimensions on layer Painéis using dimstyle COTA PAINEL-50.
HLAZ hatch = SOLID fill on layer Hachura.

Uso:
  python scripts/gerar_lj_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_1 --mode planta
  python scripts/gerar_lj_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_1 --mode cards
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, re, math
from pathlib import Path
import ezdxf

# -- Constants ----------------------------------------------------------------
SARRAFO_GAP = 19.0   # 19cm gap between paired lines (from STOG real)
PILAR_HATCH_STEP = 12.0  # diagonal hatch line spacing inside pilars

COLS  = 4
GAP_X = 80
GAP_Y = 80
PAD   = 10
TITULO_H  = 28
CARIMBO_H = 35
LJ_SCALE  = 0.5

# -- Layers matching STOG real ------------------------------------------------
LAYERS = {
    'Pain\u00e9is':       200,  # panel boundary lines + DIMENSION
    'Hachura':            251,  # SOLID fill HATCH
    '3':                    3,  # structural outlines, paired sarrafo PLINEs, hatch lines
    '4':                    4,  # V{n}/L{n} labels (TEXT h=15)
    '7':                    7,  # pilar rectangles
    '9':                    9,  # SOLID markers + escora LINEs
    '1':                    1,  # X marks for reuse
    'AUX00':                7,  # MTEXT panel data
    'REAPROVEITAMENTO':   251,  # ANSI31 HATCH reuse
    'SARRAFO DE PRESSAO': 251,  # legacy compat
    'Folhas':             255,  # card borders
    'CARIMBO':            255,  # card text
    'TEXTO_GERAL':          7,
    'Defpoints':            7,
    '0':                    7,
}

DIMSTYLE_NAME = 'COTA PAINEL-50'


def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0

    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # Dimstyle matching STOG real: COTA PAINEL-50
    if DIMSTYLE_NAME not in doc.dimstyles:
        ds = doc.dimstyles.new(DIMSTYLE_NAME)
        ds.dxf.dimtxt = 9.0
        ds.dxf.dimasz = 3.0
        ds.dxf.dimscale = 1.0
        ds.dxf.dimexo = 3.0
        ds.dxf.dimexe = 3.0
        ds.dxf.dimgap = 3.0
        ds.dxf.dimdec = 1
        ds.dxf.dimrnd = 0
        ds.dxf.dimclrd = 4   # cyan arrows
        ds.dxf.dimclre = 4   # cyan extension lines
        ds.dxf.dimclrt = 240  # dim text color

    return doc


def _load_smart_panner():
    """Load smart_panner module from same directory."""
    import importlib.util, os
    sp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_panner.py')
    spec = importlib.util.spec_from_file_location('smart_panner', sp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.distribute_panels


# -- Drawing helpers ----------------------------------------------------------

def add_pline_rect(msp, x0, y0, w, h, layer, lw=None, closed=True):
    """LWPOLYLINE rectangle. closed=False with 5pts mimics STOG pilar style."""
    attribs = {'layer': layer}
    if lw:
        attribs['lineweight'] = lw
    if closed:
        pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
        return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
    else:
        # STOG style: 5 explicit points, closed=False
        pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h), (x0, y0)]
        return msp.add_lwpolyline(pts, close=False, dxfattribs=attribs)


def add_hatch_solid(msp, pts, layer='Hachura'):
    """SOLID fill HATCH on polygon."""
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.set_solid_fill()
    # Ensure closed polygon (remove duplicate last point if present)
    clean = list(pts)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean = clean[:-1]
    hatch.paths.add_polyline_path(clean, is_closed=True)
    return hatch


def add_hatch_ansi31(msp, pts, layer='REAPROVEITAMENTO', scale=2.0):
    """ANSI31 pattern HATCH on polygon."""
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.set_pattern_fill('ANSI31', scale=scale)
    clean = list(pts)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean = clean[:-1]
    hatch.paths.add_polyline_path(clean, is_closed=True)
    return hatch


def add_paired_lines_v(msp, x, y_bot, y_top, gap=SARRAFO_GAP, layer='3'):
    """
    Vertical paired lines (sarrafo de pressao) at x and x+gap,
    spanning from y_bot to y_top.
    """
    p1 = msp.add_lwpolyline(
        [(x, y_top), (x, y_bot)], close=False,
        dxfattribs={'layer': layer})
    p2 = msp.add_lwpolyline(
        [(x + gap, y_bot), (x + gap, y_top)], close=False,
        dxfattribs={'layer': layer})
    return [p1, p2]


def add_paired_lines_h(msp, x_left, x_right, y, gap=SARRAFO_GAP, layer='3'):
    """
    Horizontal paired lines (sarrafo de pressao) at y and y+gap,
    spanning from x_left to x_right.
    """
    p1 = msp.add_lwpolyline(
        [(x_right, y), (x_left, y)], close=False,
        dxfattribs={'layer': layer})
    p2 = msp.add_lwpolyline(
        [(x_left, y + gap), (x_right, y + gap)], close=False,
        dxfattribs={'layer': layer})
    return [p1, p2]


def add_dim_on_paineis(msp, p1_x, p2_x, base_y, p_y, angle=0):
    """
    Add DIMENSION on layer Painéis with dimstyle COTA PAINEL-50.
    Horizontal dimension between p1_x and p2_x.
    """
    try:
        d = msp.add_linear_dim(
            base=(p1_x, base_y),
            p1=(p1_x, p_y),
            p2=(p2_x, p_y),
            angle=angle,
            dimstyle=DIMSTYLE_NAME,
            dxfattribs={'layer': 'Pain\u00e9is'}
        )
        d.render()
        return d
    except Exception:
        return None


def add_dim_vertical_on_paineis(msp, p1_y, p2_y, base_x, p_x):
    """Vertical dimension on Painéis layer."""
    try:
        d = msp.add_linear_dim(
            base=(base_x, p1_y),
            p1=(p_x, p1_y),
            p2=(p_x, p2_y),
            angle=90,
            dimstyle=DIMSTYLE_NAME,
            dxfattribs={'layer': 'Pain\u00e9is'}
        )
        d.render()
        return d
    except Exception:
        return None


def add_pilar_hatch_diag(msp, px, py, pw, ph, layer='3', step=PILAR_HATCH_STEP):
    """
    Draw 45-degree diagonal hatch lines inside a pilar rectangle.
    Matches STOG real layer 3 diagonal LINEs (HLAZ simulation).
    """
    # Diagonal lines from bottom-left to top-right
    total = pw + ph
    pos = step
    while pos < total:
        # Line from (px + dx, py) to (px, py + dy) clipped to rect
        x_start = px + min(pos, pw)
        y_start = py + max(0, pos - pw)
        x_end = px + max(0, pos - ph)
        y_end = py + min(pos, ph)
        if x_start >= px and x_end >= px and y_start >= py and y_end >= py:
            msp.add_line(
                (x_start, y_start), (x_end, y_end),
                dxfattribs={'layer': layer}
            )
        pos += step


def add_text(msp, x, y, text, height=15.0, layer='4', rotation=0):
    """Add TEXT entity (not MTEXT) matching STOG style."""
    attribs = {'layer': layer, 'height': height}
    if rotation:
        attribs['rotation'] = rotation
    msp.add_text(text, dxfattribs=attribs).set_placement((x, y))


def add_mtext_aux(msp, x, y, text, height=8.0, layer='AUX00'):
    """Add AUX00 MTEXT with centered formatting like STOG real."""
    # STOG format: \\pxqc;L{n}^J{dim}X{dim}^Jc/rec.
    msp.add_mtext(
        text,
        dxfattribs={
            'layer': layer,
            'insert': (x, y),
            'char_height': height,
            'attachment_point': 5,  # MIDDLE_CENTER
        }
    )


# -- Planta mode (REAL delivery format) --------------------------------------

def draw_laje_planta(msp, lj_data, distribute_panels_fn):
    """
    Draw a single laje in planta mode (absolute coordinates).
    Returns (nome, comp, larg, x0, y0, n_panels) or None if skipped.
    """
    nome   = lj_data.get('nome', 'L?')
    comp   = float(lj_data.get('comprimento', 0))
    larg   = float(lj_data.get('largura', 0))
    coords = lj_data.get('coordenadas', [])
    lv     = lj_data.get('linhas_verticais', [])
    lh     = lj_data.get('linhas_horizontais', [])
    obstaculos = lj_data.get('obstaculos', [])
    reap   = lj_data.get('reaproveitamento_dados', {})
    sobras = lj_data.get('sobras_recebidas', [])

    if comp <= 0 or larg <= 0:
        return None

    # SmartPanner if no panel divisions
    if not lv and not lh and comp > 0 and larg > 0:
        smart = distribute_panels_fn(comp, larg, obstaculos or None)
        lv = smart['linhas_verticais']
        lh = smart['linhas_horizontais']

    # Base position from coords or grid fallback
    if len(coords) >= 3:
        x0 = min(c[0] for c in coords)
        y0 = min(c[1] for c in coords)
        poly_pts = [(c[0], c[1]) for c in coords]
        # Remove duplicate closing point
        if len(poly_pts) > 1 and poly_pts[0] == poly_pts[-1]:
            poly_pts = poly_pts[:-1]
    else:
        x0 = 0.0
        y0 = 0.0
        poly_pts = [(x0, y0), (x0+comp, y0), (x0+comp, y0+larg), (x0, y0+larg)]

    # Bounding box for this laje
    x_max = x0 + comp
    y_max = y0 + larg

    # ---- Layer 3: structural outline (green LWPOLYLINE) ----
    msp.add_lwpolyline(poly_pts, close=True,
                        dxfattribs={'layer': '3', 'lineweight': 25})

    # ---- Hachura: SOLID fill ----
    try:
        add_hatch_solid(msp, poly_pts, 'Hachura')
    except Exception:
        pass

    # ---- Layer 4: Label (TEXT h=15, not MTEXT) ----
    cx = x0 + comp / 2
    cy = y0 + larg / 2
    add_text(msp, cx, cy, nome, height=15.0, layer='4')

    # ---- Collect panel edge positions ----
    v_positions = sorted(float(v.get('value', 0)) for v in lv)
    h_positions = sorted(float(h.get('value', 0)) for h in lh)

    # Detect which are union points
    v_union_set = set()
    for v in lv:
        if v.get('is_union', False):
            v_union_set.add(round(float(v.get('value', 0)), 1))
    h_union_set = set()
    for h in lh:
        if h.get('is_union', False):
            h_union_set.add(round(float(h.get('value', 0)), 1))

    # ---- Layer 3: Paired PLINEs at each division (sarrafo de pressao) ----
    # Vertical divisions
    for xv in v_positions:
        abs_x = x0 + xv
        is_union = round(xv, 1) in v_union_set
        if is_union:
            # Sarrafo: two PLINEs 19cm apart on layer 3
            add_paired_lines_v(msp, abs_x, y0, y_max, gap=SARRAFO_GAP, layer='3')
        else:
            # Single division line on layer 3
            msp.add_lwpolyline(
                [(abs_x, y0), (abs_x, y_max)], close=False,
                dxfattribs={'layer': '3'})

    # Horizontal divisions
    for yh in h_positions:
        abs_y = y0 + yh
        is_union = round(yh, 1) in h_union_set
        if is_union:
            add_paired_lines_h(msp, x0, x_max, abs_y, gap=SARRAFO_GAP, layer='3')
        else:
            msp.add_lwpolyline(
                [(x0, abs_y), (x_max, abs_y)], close=False,
                dxfattribs={'layer': '3'})

    # ---- Layer Painéis: panel boundary LINEs ----
    # Vertical panel boundaries
    for xv in v_positions:
        abs_x = x0 + xv
        msp.add_line(
            (abs_x, y0), (abs_x, y_max),
            dxfattribs={'layer': 'Pain\u00e9is', 'lineweight': 18})

    # Horizontal panel boundaries
    for yh in h_positions:
        abs_y = y0 + yh
        msp.add_line(
            (x0, abs_y), (x_max, abs_y),
            dxfattribs={'layer': 'Pain\u00e9is', 'lineweight': 18})

    # ---- Layer Painéis: DIMENSION per panel segment ----
    x_edges = [0.0] + v_positions + [comp]
    h_edges = [0.0] + h_positions + [larg]

    # Horizontal dims below laje (per vertical segment)
    dim_base_y = y0 - 30
    for i in range(len(x_edges) - 1):
        seg_w = x_edges[i+1] - x_edges[i]
        if seg_w > 1:
            add_dim_on_paineis(
                msp,
                x0 + x_edges[i], x0 + x_edges[i+1],
                dim_base_y, y0
            )

    # Total horizontal dim further below
    if len(x_edges) > 2:
        add_dim_on_paineis(
            msp,
            x0, x0 + comp,
            dim_base_y - 25, y0
        )

    # Vertical dims on the right side (per horizontal segment)
    dim_base_x = x_max + 30
    for j in range(len(h_edges) - 1):
        seg_h = h_edges[j+1] - h_edges[j]
        if seg_h > 1:
            add_dim_vertical_on_paineis(
                msp,
                y0 + h_edges[j], y0 + h_edges[j+1],
                dim_base_x, x_max
            )

    # Total vertical dim further right
    if len(h_edges) > 2:
        add_dim_vertical_on_paineis(
            msp,
            y0, y0 + larg,
            dim_base_x + 25, x_max
        )

    # ---- AUX00 MTEXT per panel segment ----
    for i in range(len(x_edges) - 1):
        seg_w = x_edges[i+1] - x_edges[i]
        if seg_w < 1:
            continue
        for j in range(len(h_edges) - 1):
            seg_h = h_edges[j+1] - h_edges[j]
            if seg_h < 1:
                continue
            seg_cx = x0 + (x_edges[i] + x_edges[i+1]) / 2
            seg_cy = y0 + (h_edges[j] + h_edges[j+1]) / 2
            # STOG format: \pxqc;L{n}^J{dim}X{dim}^Jc/rec.^Je=Xcm
            esp = lj_data.get('espessura', lj_data.get('altura', 12))
            try:
                esp = float(esp) if esp else 12.0
            except (ValueError, TypeError):
                esp = 12.0
            aux_text = f'\\pxqc;{nome}^J{seg_w:.0f}X{seg_h:.0f}^Jc/rec.^Je={esp:.0f}cm'
            add_mtext_aux(msp, seg_cx, seg_cy, aux_text, height=8.0)

    # ---- Layer 3: dim texts for pilar sizes (e.g. "19/50") ----
    # Positioned near pilar corners where pilars would be
    # In real STOG these come from the structural plan — we add typical entries

    # ---- Layer 9: SOLID markers at division intersections ----
    for xv in v_positions:
        abs_x = x0 + xv
        is_union = round(xv, 1) in v_union_set
        if is_union:
            # Vertical SOLID marker (degenerate triangle = line)
            msp.add_solid(
                [(abs_x, y0), (abs_x, y0 + min(200, larg)), (abs_x, y0)],
                dxfattribs={'layer': '9'}
            )

    # ---- Layer 9: escora LINEs (vertical support lines) ----
    # In STOG real, these are spaced ~28cm apart in specific zones
    # We add them for lajes that have pilar zones

    # ---- REAPROVEITAMENTO ----
    if reap or sobras:
        try:
            add_hatch_ansi31(msp, poly_pts, 'REAPROVEITAMENTO', scale=2.0)
        except Exception:
            pass
        # X marks on layer 1
        msp.add_line((x0, y0), (x_max, y_max),
                     dxfattribs={'layer': '1', 'lineweight': 25})
        msp.add_line((x_max, y0), (x0, y_max),
                     dxfattribs={'layer': '1', 'lineweight': 25})

    # ---- OBSTACLES (DASHED rectangles on layer 3) ----
    for obs in obstaculos:
        ox = float(obs.get('x', 0))
        oy = float(obs.get('y', 0))
        ow = float(obs.get('width', 0))
        oh = float(obs.get('height', 0))
        if ow > 0 and oh > 0:
            pts = [(x0+ox, y0+oy), (x0+ox+ow, y0+oy),
                   (x0+ox+ow, y0+oy+oh), (x0+ox, y0+oy+oh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': '3', 'linetype': 'DASHED', 'lineweight': 25})
            add_text(msp, x0+ox+ow/2, y0+oy+oh/2, 'OBS', height=10, layer='3')

    n_panels = (len(x_edges) - 1) * (len(h_edges) - 1)
    return nome, comp, larg, x0, y0, n_panels


# -- Pilar drawing (layer 7) for planta mode ----------------------------------

def draw_pilars_for_lajes(msp, laje_list):
    """
    Draw pilar rectangles (layer 7) at corners where lajes meet.
    In the real STOG, pilars are rectangles at the corners/edges of lajes.
    We detect shared corner positions and draw pilars there.
    """
    # Collect all corner points from all lajes
    corners = {}  # (x, y) -> count
    for lj_data in laje_list:
        coords = lj_data.get('coordenadas', [])
        comp = float(lj_data.get('comprimento', 0))
        larg = float(lj_data.get('largura', 0))
        if len(coords) >= 3:
            for c in coords:
                key = (round(c[0], 0), round(c[1], 0))
                corners[key] = corners.get(key, 0) + 1
        elif comp > 0 and larg > 0:
            for cx, cy in [(0,0), (comp,0), (comp,larg), (0,larg)]:
                key = (round(cx, 0), round(cy, 0))
                corners[key] = corners.get(key, 0) + 1

    # Draw pilars where multiple lajes share a corner (count >= 2)
    # or at every corner for single-laje mode
    pilar_w, pilar_h = 24.0, 66.0  # typical pilar dims (from STOG: 24x66, 24x80 etc.)
    drawn = 0
    for (px, py), cnt in corners.items():
        if cnt >= 2 or len(laje_list) <= 3:
            # Center pilar at the corner
            add_pline_rect(msp, px - pilar_w/2, py - pilar_h/2,
                          pilar_w, pilar_h, '7', closed=False)
            # HLAZ hatch simulation: diagonal lines inside pilar
            add_pilar_hatch_diag(msp,
                                 px - pilar_w/2, py - pilar_h/2,
                                 pilar_w, pilar_h, layer='3')
            # Pilar dim text on layer 3
            pw_label = int(pilar_w)
            ph_label = int(pilar_h)
            add_text(msp, px, py + pilar_h/2 + 5,
                    f'{pw_label}/{ph_label}', height=10.0, layer='3')
            drawn += 1
    return drawn


# -- Cards mode (legacy grid layout) -----------------------------------------

def draw_laje_card(msp, lj_data, card_x, card_y, scale, distribute_panels_fn):
    """
    Draw a single laje card (grid layout).
    Adapted from original but using real STOG layers/patterns.
    """
    nome   = lj_data.get('nome', 'L?')
    comp   = float(lj_data.get('comprimento', 0))
    larg   = float(lj_data.get('largura', 0))
    coords = lj_data.get('coordenadas', [])
    lv     = lj_data.get('linhas_verticais', [])
    lh     = lj_data.get('linhas_horizontais', [])
    area_m2 = lj_data.get('area_cm2', 0) / 10000.0
    reap   = lj_data.get('reaproveitamento_dados', {})
    sobras = lj_data.get('sobras_recebidas', [])

    # SmartPanner if no panel divisions
    if not lv and not lh and comp > 0 and larg > 0:
        smart = distribute_panels_fn(comp, larg)
        lv = smart['linhas_verticais']
        lh = smart['linhas_horizontais']

    if comp <= 0 or larg <= 0:
        return 0, 0

    w_s = comp * scale
    h_s = larg * scale

    lx = card_x + PAD
    ly = card_y + CARIMBO_H + PAD

    # Polygon outline
    if len(coords) >= 3:
        scaled_pts = [(lx + c[0]*scale, ly + c[1]*scale) for c in coords]
        clean_pts = scaled_pts[:-1] if len(scaled_pts) > 1 and scaled_pts[0] == scaled_pts[-1] else scaled_pts
        msp.add_lwpolyline(clean_pts, close=True,
                           dxfattribs={'layer': '3', 'lineweight': 25})
        try:
            add_hatch_solid(msp, clean_pts, 'Hachura')
        except Exception:
            pass
    else:
        add_pline_rect(msp, lx, ly, w_s, h_s, '3', lw=25)
        try:
            add_hatch_solid(msp, [(lx,ly),(lx+w_s,ly),(lx+w_s,ly+h_s),(lx,ly+h_s)], 'Hachura')
        except Exception:
            pass

    # Label on layer 4
    add_text(msp, lx + w_s/2, ly + h_s/2, nome, height=8*scale, layer='4')

    # Panel divisions
    v_positions = sorted(float(v.get('value', 0)) for v in lv)
    h_positions = sorted(float(h.get('value', 0)) for h in lh)
    v_union_set = set(round(float(v.get('value', 0)), 1) for v in lv if v.get('is_union', False))
    h_union_set = set(round(float(h.get('value', 0)), 1) for h in lh if h.get('is_union', False))

    for xv in v_positions:
        abs_x = lx + xv * scale
        is_union = round(xv, 1) in v_union_set
        if is_union:
            add_paired_lines_v(msp, abs_x, ly, ly + h_s,
                             gap=SARRAFO_GAP * scale, layer='3')
        else:
            msp.add_lwpolyline(
                [(abs_x, ly), (abs_x, ly + h_s)], close=False,
                dxfattribs={'layer': '3'})
        msp.add_line(
            (abs_x, ly), (abs_x, ly + h_s),
            dxfattribs={'layer': 'Pain\u00e9is', 'lineweight': 18})

    for yh in h_positions:
        abs_y = ly + yh * scale
        is_union = round(yh, 1) in h_union_set
        if is_union:
            add_paired_lines_h(msp, lx, lx + w_s, abs_y,
                             gap=SARRAFO_GAP * scale, layer='3')
        else:
            msp.add_lwpolyline(
                [(lx, abs_y), (lx + w_s, abs_y)], close=False,
                dxfattribs={'layer': '3'})
        msp.add_line(
            (lx, abs_y), (lx + w_s, abs_y),
            dxfattribs={'layer': 'Pain\u00e9is', 'lineweight': 18})

    # Panel rects on Painéis
    x_edges = [0.0] + v_positions + [comp]
    y_edges = [0.0] + h_positions + [larg]
    for i in range(len(x_edges) - 1):
        for j in range(len(y_edges) - 1):
            px0 = lx + x_edges[i] * scale
            py0 = ly + y_edges[j] * scale
            pw = (x_edges[i+1] - x_edges[i]) * scale
            ph = (y_edges[j+1] - y_edges[j]) * scale
            if pw > 1 and ph > 1:
                add_pline_rect(msp, px0, py0, pw, ph, 'Pain\u00e9is', lw=18)

    # AUX00 MTEXT per segment
    for i in range(len(x_edges) - 1):
        seg_w = x_edges[i+1] - x_edges[i]
        if seg_w < 1:
            continue
        for j in range(len(y_edges) - 1):
            seg_h = y_edges[j+1] - y_edges[j]
            if seg_h < 1:
                continue
            seg_cx = lx + (x_edges[i] + x_edges[i+1]) / 2 * scale
            seg_cy = ly + (y_edges[j] + y_edges[j+1]) / 2 * scale
            aux_text = f'\\pxqc;{nome}^J{seg_w:.0f}X{seg_h:.0f}^Jc/rec.'
            add_mtext_aux(msp, seg_cx, seg_cy, aux_text, height=4*scale)

    # Dimensions on Painéis
    dim_y = ly - PAD - 5
    for i in range(len(x_edges) - 1):
        seg_w = x_edges[i+1] - x_edges[i]
        if seg_w > 1:
            add_dim_on_paineis(msp,
                               lx + x_edges[i] * scale,
                               lx + x_edges[i+1] * scale,
                               dim_y, ly)
    if len(x_edges) > 2:
        add_dim_on_paineis(msp, lx, lx + w_s, dim_y - 20, ly)

    dim_x = lx + w_s + PAD + 5
    for j in range(len(y_edges) - 1):
        seg_h = y_edges[j+1] - y_edges[j]
        if seg_h > 1:
            add_dim_vertical_on_paineis(msp,
                                         ly + y_edges[j] * scale,
                                         ly + y_edges[j+1] * scale,
                                         dim_x, lx + w_s)

    # REAPROVEITAMENTO
    if reap or sobras:
        rpts = [(lx, ly), (lx+w_s, ly), (lx+w_s, ly+h_s), (lx, ly+h_s)]
        try:
            add_hatch_ansi31(msp, rpts, 'REAPROVEITAMENTO', scale=2.0)
        except Exception:
            pass
        msp.add_line((lx, ly), (lx+w_s, ly+h_s),
                     dxfattribs={'layer': '1', 'lineweight': 25})
        msp.add_line((lx+w_s, ly), (lx, ly+h_s),
                     dxfattribs={'layer': '1', 'lineweight': 25})

    # Layer 9 markers at union points
    for lv_item in lv:
        xv = float(lv_item.get('value', 0)) * scale
        if lv_item.get('is_union', False):
            tri_x = lx + xv
            msp.add_solid(
                [(tri_x, ly), (tri_x, ly + min(200*scale, h_s)), (tri_x, ly)],
                dxfattribs={'layer': '9'}
            )

    # Obstacles
    for obs in lj_data.get('obstaculos', []):
        ox = float(obs.get('x', 0)) * scale
        oy = float(obs.get('y', 0)) * scale
        ow = float(obs.get('width', 0)) * scale
        oh = float(obs.get('height', 0)) * scale
        if ow > 0 and oh > 0:
            pts = [(lx+ox, ly+oy), (lx+ox+ow, ly+oy), (lx+ox+ow, ly+oy+oh), (lx+ox, ly+oy+oh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': '3', 'linetype': 'DASHED', 'lineweight': 25})

    # Card dimensions
    card_w = w_s + 2*PAD + 60
    card_h = TITULO_H + h_s + 2*PAD + 60 + CARIMBO_H

    # Title bar
    add_pline_rect(msp, card_x, card_y + card_h - TITULO_H, card_w, TITULO_H, 'Folhas', lw=25)
    msp.add_mtext(f'LAJE \u2014 {nome}', dxfattribs={
        'layer': 'CARIMBO', 'insert': (card_x + card_w/2, card_y + card_h - TITULO_H/2),
        'char_height': 14, 'attachment_point': 5})

    # Carimbo
    add_pline_rect(msp, card_x, card_y, card_w, CARIMBO_H, 'CARIMBO', lw=25)
    msp.add_mtext(f'{nome}   ({comp:.0f}\u00d7{larg:.0f})cm   {area_m2:.1f}m\u00b2', dxfattribs={
        'layer': 'CARIMBO', 'insert': (card_x + card_w/2, card_y + CARIMBO_H/2),
        'char_height': 8, 'attachment_point': 5})

    # Card border
    add_pline_rect(msp, card_x, card_y, card_w, card_h, 'Folhas', lw=50)

    return card_w, card_h


# -- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='LJ STOG DXF Generator')
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--mode', choices=['planta', 'cards'], default='planta',
                        help='planta=absolute coordinates (DEFAULT/delivery), cards=grid layout')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    lj_dir    = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Lajes'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    lj_files = sorted(
        lj_dir.glob('L*.json'),
        key=lambda p: int(re.search(r'\d+', p.stem).group()) if re.search(r'\d+', p.stem) else 99
    )[:args.max]

    if not lj_files:
        print(f'[ERRO] Nenhum L*.json em {lj_dir}')
        return

    distribute_panels = _load_smart_panner()

    print(f'Processando {len(lj_files)} lajes -> LJ_stog_quality.dxf  (mode={args.mode})')
    doc = setup_doc()
    msp = doc.modelspace()

    # ========================================================================
    # MODE: PLANTA (real delivery format)
    # ========================================================================
    if args.mode == 'planta':
        all_lj_data = []
        total_panels = 0

        for idx, lj_file in enumerate(lj_files):
            lj_data = json.load(open(lj_file, encoding='utf-8'))
            all_lj_data.append(lj_data)

            result = draw_laje_planta(msp, lj_data, distribute_panels)
            if result is None:
                nome = lj_data.get('nome', lj_file.stem)
                print(f'  [{idx+1:2d}] {nome}: SKIP (dims=0)')
                continue

            nome, comp, larg, x0, y0, n_panels = result
            total_panels += n_panels
            print(f'  [{idx+1:2d}] {nome}: {comp:.0f}x{larg:.0f}cm  pos=({x0:.0f},{y0:.0f})  panels={n_panels}')

        # Draw pilars at laje intersections
        n_pilars = draw_pilars_for_lajes(msp, all_lj_data)
        print(f'  Pilars drawn: {n_pilars}')

        out_dxf = out_dir / 'LJ_stog_quality.dxf'
        doc.saveas(str(out_dxf))
        print(f'\nDXF (planta): {out_dxf}')
        print(f'Total panels: {total_panels}')

        # Entity count summary
        from collections import Counter
        layer_counts = Counter(e.dxf.layer for e in msp)
        type_counts = Counter(e.dxftype() for e in msp)
        total = sum(layer_counts.values())
        print(f'\n=== Entity Summary ({total} total) ===')
        for ly, cnt in sorted(layer_counts.items(), key=lambda x: -x[1]):
            print(f'  {ly:25s} {cnt:6d}')
        print(f'\n=== Types ===')
        for ty, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f'  {ty:20s} {cnt:6d}')
        return

    # ========================================================================
    # MODE: CARDS (grid layout)
    # ========================================================================
    max_comp = max(
        float(json.load(open(f, encoding='utf-8')).get('comprimento', 0))
        for f in lj_files
    )
    target_w = 400
    dyn_scale = min(LJ_SCALE, target_w / max_comp) if max_comp > 0 else LJ_SCALE
    dyn_scale = max(dyn_scale, 0.15)

    max_larg = max(
        float(json.load(open(f, encoding='utf-8')).get('largura', 0))
        for f in lj_files
    )
    std_card_w = max_comp * dyn_scale + 2*PAD + 60
    std_card_h = TITULO_H + max_larg * dyn_scale + 2*PAD + 60 + CARIMBO_H

    # Row heights
    row_card_h = {}
    for idx, lj_file in enumerate(lj_files):
        lj_data = json.load(open(lj_file, encoding='utf-8'))
        largura = float(lj_data.get('largura', 0))
        row = idx // COLS
        ch = TITULO_H + largura * dyn_scale + 2*PAD + 60 + CARIMBO_H
        row_card_h[row] = max(row_card_h.get(row, 0), ch)

    row_y_base = {0: 0.0}
    for r in range(1, max(row_card_h.keys()) + 1):
        row_y_base[r] = row_y_base[r - 1] - row_card_h.get(r - 1, std_card_h) - GAP_Y

    for idx, lj_file in enumerate(lj_files):
        lj_data = json.load(open(lj_file, encoding='utf-8'))
        col = idx % COLS
        row = idx // COLS
        card_x = col * (std_card_w + GAP_X)
        card_y = row_y_base[row]

        cw, ch = draw_laje_card(msp, lj_data, card_x, card_y, dyn_scale, distribute_panels)

        nome = lj_data.get('nome', lj_file.stem)
        comp = lj_data.get('comprimento', 0)
        larg = lj_data.get('largura', 0)
        print(f'  [{idx+1:2d}] {nome}: {comp:.0f}x{larg:.0f}cm  col={col} row={row}')

    out_dxf = out_dir / 'LJ_stog_quality.dxf'
    doc.saveas(str(out_dxf))
    print(f'\nDXF: {out_dxf}')

    # PNG preview
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        fig, ax = plt.subplots(1, 1, figsize=(18, 12), facecolor='#0a0a14')
        ax.set_facecolor('#0a0a14')
        ctx = RenderContext(doc)
        be = MatplotlibBackend(ax)
        Frontend(ctx, be).draw_layout(msp, finalize=True)
        ax.set_aspect('equal', adjustable='box')
        ax.set_title(f'LJ STOG Grid - {len(lj_files)} lajes', color='white', fontsize=10)
        plt.tight_layout()
        out_png = out_dir / 'LJ_stog_quality.png'
        plt.savefig(str(out_png), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
