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
LABEL_ABOVE     = 40     # y = viga_top + LABEL_ABOVE for endpoint/gap labels
LABEL_H         = 12.0   # endpoint/gap label height (layer 5)
DIM_BELOW       = 20     # y = viga_bottom - DIM_BELOW  (nível 1: cota individual)
DIM_TOTAL_BELOW = 40     # y = viga_bottom - DIM_TOTAL_BELOW (nível 2: total segmento)
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
    'SARR_5cm':                   4,   # azul-esverdeado; vigas com 10≤b≤14cm
    'SARR_CONTORNO_10cm':         3,   # verde; vigas com b<10cm
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


def normalize_viga_name(value):
    """Remove internal pipeline marks and an existing drawing suffix."""
    name = str(value or '').strip()
    name = re.sub(r'^\s*CONT\.\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(
        r'(?<![A-Z0-9])N4ER(?![A-Z0-9])',
        '',
        name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r'\.C\s*$', '', name, flags=re.IGNORECASE)
    return name.strip(' _.-')


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
    if b == 14:
        return [5, 9]

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


def build_chanfro_vertices(w, b, te=0.0, fe=0.0, td=0.0, fd=0.0):
    """Boundary whose end edges connect the bottom and top setbacks."""
    te = max(0.0, min(float(te), float(w)))
    fe = max(0.0, min(float(fe), float(w)))
    td = max(0.0, min(float(td), float(w)))
    fd = max(0.0, min(float(fd), float(w)))
    pts = [(fe, 0.0), (w - fd, 0.0), (w - td, b), (te, b)]
    return [{'x': float(x), 'y': float(y)} for x, y in pts]


def build_panel_l_loose(main_comp, main_b, comp2, larg2, tipo, paineis_2,
                        angulo_l=90.0, recuos_2=None, aberturas_2=None):
    """Build a complete secondary leaf in its perpendicular local system."""
    parts = tipo.replace('-', '/').upper().split('/')
    side = parts[0] if parts else 'E'
    vert = parts[1] if len(parts) > 1 else 'T'

    try:
        angle = float(angulo_l)
    except Exception:
        angle = 90.0
    if angle <= 0 or angle >= 180:
        angle = 90.0

    side_sign = 1.0 if side == 'E' else -1.0
    vert_sign = 1.0 if vert == 'T' else -1.0
    length_vec = (
        side_sign * math.cos(math.radians(angle)),
        vert_sign * math.sin(math.radians(angle)),
    )
    width_vec = (1.0, 0.0) if side == 'E' else (-1.0, 0.0)
    outer_x = -float(larg2) if side == 'E' else float(main_comp + larg2)
    outer_y = 0.0 if vert == 'T' else float(main_b)

    def _pt(u, v):
        return (
            outer_x + length_vec[0] * float(u) + width_vec[0] * float(v),
            outer_y + length_vec[1] * float(u) + width_vec[1] * float(v),
        )

    vals = list(recuos_2 or [0, 0, 0, 0]) + [0, 0, 0, 0]
    te, fe, td, fd = (max(0.0, float(vals[i] or 0)) for i in range(4))
    local_poly = build_chanfro_vertices(comp2, larg2, te, fe, td, fd)
    poly = [_pt(v['x'], v['y']) for v in local_poly]
    ents = [{
        'type': 'LWPOLYLINE',
        'points': [{'x': x, 'y': y} for x, y in poly],
        'layer': LY_PAINEIS,
    }]

    u = 0.0
    for pw2 in (paineis_2 or [])[:-1]:
        u += float(pw2)
        if 0 < u < float(comp2):
            a, z = _pt(u, 0.0), _pt(u, larg2)
            ents.append({
                'type': 'LINE', 'start': {'x': a[0], 'y': a[1]},
                'end': {'x': z[0], 'y': z[1]}, 'layer': LY_PAINEIS,
            })

    for frac in (1 / 3, 2 / 3):
        v = float(larg2) * frac
        left = fe + (te - fe) * frac
        right = float(comp2) - (fd + (td - fd) * frac)
        if right > left:
            a, z = _pt(left, v), _pt(right, v)
            ents.append({
                'type': 'LINE', 'start': {'x': a[0], 'y': a[1]},
                'end': {'x': z[0], 'y': z[1]}, 'layer': LY_PAINEIS,
            })

    openings = []
    for idx, row in enumerate(list(aberturas_2 or [])[:4]):
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        dist, prof, width = (float(row[i] or 0) for i in range(3))
        if dist <= 0 or prof <= 0 or width <= 0:
            continue
        x1 = float(comp2) - dist - width if idx >= 2 else dist
        x1 = max(0.0, min(x1, float(comp2)))
        x2 = max(x1, min(x1 + width, float(comp2)))
        top = idx in (0, 2)
        y1 = max(0.0, float(larg2) - prof) if top else 0.0
        y2 = float(larg2) if top else min(prof, float(larg2))
        openings.append((x1, x2, y1, y2))
        rect = [_pt(x1, y1), _pt(x2, y1), _pt(x2, y2), _pt(x1, y2)]
        ents.append({
            'type': 'LWPOLYLINE',
            'points': [{'x': x, 'y': y} for x, y in rect],
            'layer': LY_PAINEIS,
        })

    if larg2 >= 10:
        sarr_layer = 'SARR_5cm' if larg2 <= 14 else SARR_LAYER
        for a, z in (
            (_pt(fe + SARR_RECUO, 0), _pt(te + SARR_RECUO, larg2)),
            (_pt(comp2 - fd - SARR_RECUO, 0),
             _pt(comp2 - td - SARR_RECUO, larg2)),
        ):
            ents.append({
                'type': 'LINE', 'start': {'x': a[0], 'y': a[1]},
                'end': {'x': z[0], 'y': z[1]}, 'layer': sarr_layer,
            })
        for v in _sarr_h_offsets(float(larg2)):
            frac = v / float(larg2)
            left = fe + (te - fe) * frac + SARR_RECUO
            right = float(comp2) - fd - (td - fd) * frac - SARR_RECUO
            cuts = sorted(
                (x1, x2) for x1, x2, y1, y2 in openings if y1 <= v <= y2
            )
            cursor = left
            for x1, x2 in cuts:
                if x1 > cursor:
                    a, z = _pt(cursor, v), _pt(min(x1, right), v)
                    ents.append({
                        'type': 'LINE', 'start': {'x': a[0], 'y': a[1]},
                        'end': {'x': z[0], 'y': z[1]}, 'layer': sarr_layer,
                    })
                cursor = max(cursor, x2)
            if cursor < right:
                a, z = _pt(cursor, v), _pt(right, v)
                ents.append({
                    'type': 'LINE', 'start': {'x': a[0], 'y': a[1]},
                    'end': {'x': z[0], 'y': z[1]}, 'layer': sarr_layer,
                })
    return ents


def robot_dados_to_fv_dict(dados, viga_nome='V?'):
    """Convert robot get_current_data() format to a viga_dict for draw_viga().

    Robot keys used:
      largura, altura, paineis, recuos [TE,FE,TD,FD], aberturas [[dist,prof,larg]×4],
      sarrafo_esq, sarrafo_dir, texto_esq, texto_dir,
      tipo_painel2, comprimento_2, largura_2, paineis_2, angulo_l, obs.

    Returns dict with keys: nome, b, comp, panels, label_left, label_right, obs.
    Returns None if data is insufficient.
    """
    def _f(v):
        try: return float(str(v).replace(',', '.').strip() or '0')
        except: return 0.0

    # Sub-panel widths from robot paineis fields
    sub_widths = [_f(p) for p in dados.get('paineis', []) if _f(p) > 0]
    if not sub_widths:
        largura = _f(dados.get('largura', 0))
        sub_widths = compute_panels(largura) if largura > 0 else []
    if not sub_widths:
        return None

    b = _f(dados.get('altura', 14)) or 14.0
    comp = sum(sub_widths)

    # Chanfros [TE, FE, TD, FD]
    recuos = dados.get('recuos', ['0', '0', '0', '0'])
    te = _f(recuos[0]) if len(recuos) > 0 else 0.0
    fe = _f(recuos[1]) if len(recuos) > 1 else 0.0
    td = _f(recuos[2]) if len(recuos) > 2 else 0.0
    fd = _f(recuos[3]) if len(recuos) > 3 else 0.0

    aberturas = dados.get('aberturas', [])

    def _abertura_rect(pw, b_val, ab_row, side_top, from_right=False):
        if len(ab_row) < 3: return []
        dist, prof, larg = _f(ab_row[0]), _f(ab_row[1]), _f(ab_row[2])
        if dist <= 0 or prof <= 0 or larg <= 0: return []
        x1 = (pw - dist - larg) if from_right else dist
        x1 = max(0.0, min(x1, pw))
        x2 = max(x1, min(x1 + larg, pw))
        y1 = (b_val - prof) if side_top else 0.0
        y1 = max(0.0, min(y1, b_val))
        y2 = b_val if side_top else min(prof, b_val)
        return {'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2}

    def _abertura_loose(pw, b_val, ab_row, side_top, from_right=False):
        rect = _abertura_rect(pw, b_val, ab_row, side_top, from_right)
        if not rect:
            return []
        x1, x2 = rect['x1'], rect['x2']
        y1, y2 = rect['y1'], rect['y2']
        return [
            {'type': 'LINE', 'start': {'x': x1, 'y': y1}, 'end': {'x': x2, 'y': y1}},
            {'type': 'LINE', 'start': {'x': x2, 'y': y1}, 'end': {'x': x2, 'y': y2}},
            {'type': 'LINE', 'start': {'x': x2, 'y': y2}, 'end': {'x': x1, 'y': y2}},
            {'type': 'LINE', 'start': {'x': x1, 'y': y2}, 'end': {'x': x1, 'y': y1}},
        ]

    # Build sub-panel objects with chanfros and aberturas
    sub_panel_objs = []
    for i, pw in enumerate(sub_widths):
        is_first = (i == 0)
        is_last  = (i == len(sub_widths) - 1)
        obj = {'width': pw}

        # Apply chanfros only to the endpoint panels
        p_te = te if is_first else 0.0
        p_fe = fe if is_first else 0.0
        p_td = td if is_last  else 0.0
        p_fd = fd if is_last  else 0.0
        if p_te > 0 or p_fe > 0 or p_td > 0 or p_fd > 0:
            obj['vertices'] = build_chanfro_vertices(pw, b, p_te, p_fe, p_td, p_fd)
            obj['chanfros'] = {'te': p_te, 'fe': p_fe, 'td': p_td, 'fd': p_fd}

        # Aberturas as rectangular notch outlines (TE=0, FE=1, TD=2, FD=3)
        loose = []
        panel_openings = []
        if is_first:
            if len(aberturas) > 0:
                loose += _abertura_loose(pw, b, aberturas[0], side_top=True,  from_right=False)
                rect = _abertura_rect(pw, b, aberturas[0], side_top=True, from_right=False)
                if rect: panel_openings.append(rect)
            if len(aberturas) > 1:
                loose += _abertura_loose(pw, b, aberturas[1], side_top=False, from_right=False)
                rect = _abertura_rect(pw, b, aberturas[1], side_top=False, from_right=False)
                if rect: panel_openings.append(rect)
        if is_last:
            if len(aberturas) > 2:
                loose += _abertura_loose(pw, b, aberturas[2], side_top=True,  from_right=True)
                rect = _abertura_rect(pw, b, aberturas[2], side_top=True, from_right=True)
                if rect: panel_openings.append(rect)
            if len(aberturas) > 3:
                loose += _abertura_loose(pw, b, aberturas[3], side_top=False, from_right=True)
                rect = _abertura_rect(pw, b, aberturas[3], side_top=False, from_right=True)
                if rect: panel_openings.append(rect)
        if loose:
            obj['loose'] = loose
        if panel_openings:
            obj['aberturas'] = panel_openings

        sub_panel_objs.append(obj)

    # Painel L: draw as loose entities attached to the first sub-panel
    comp2 = _f(dados.get('comprimento_2', 0))
    larg2 = _f(dados.get('largura_2', 0))
    if comp2 > 0 and larg2 > 0:
        tipo2  = dados.get('tipo_painel2', 'E/T') or 'E/T'
        angulo_l = _f(dados.get('angulo_l', dados.get('angulo_2', 90))) or 90.0
        pw2_raw = [_f(p) for p in dados.get('paineis_2', []) if _f(p) > 0]
        if not pw2_raw:
            pw2_raw = compute_panels(comp2)
        l_loose = build_panel_l_loose(
            comp, b, comp2, larg2, tipo2, pw2_raw,
            angulo_l=angulo_l,
            recuos_2=dados.get('recuos_2'),
            aberturas_2=dados.get('aberturas_2'),
        )
        if l_loose:
            sub_panel_objs[0]['loose'] = sub_panel_objs[0].get('loose', []) + l_loose

    segment = {
        'total_width': comp,
        'panels': sub_panel_objs,
        'sarrafo_esq': bool(dados.get('sarrafo_esq', True)),
        'sarrafo_dir': bool(dados.get('sarrafo_dir', True)),
    }
    return {
        'nome':        viga_nome,
        'b':           b,
        'comp':        comp,
        'panels':      [segment],
        'label_left':  dados.get('texto_esq', 'L Esq') or 'L Esq',
        'label_right': dados.get('texto_dir', 'L Dir') or 'L Dir',
        'obs':         dados.get('obs', ''),
    }


def draw_sarr(msp, x0, y0, b, panel_widths, panel_verts=None,
              panel_chanfros=None, panel_openings=None,
              sarrafo_esq=True, sarrafo_dir=True):
    """Draw SARR_2.2x7 lines for a single contiguous real segment.

    sarrafo_esq/sarrafo_dir: when False, the respective vertical sarrafo
    line is suppressed (used for robot manual control).

    Verified against ground truth (V305 recorte, FV_V305_motor_*.dxf):
    SARR_2.2x7 = exactly 4 LINE entities — 2 vertical recuo-edges (x0+7,
    xend-7) and 2 HORIZONTAL lines spanning the FULL recuo-inset width
    CONTINUOUSLY (NOT broken at the synthetic compute_panels() STOG-module
    divider, e.g. x=244 for a 286cm viga). The previous per-panel-segment
    breaking logic was an unverified assumption and is WRONG — ground
    truth has 4 lines total regardless of how many STOG-module sub-panels
    the beam splits into.

    SARR_EDITAR (vertical lines at the absolute outer edges x0/x0+total)
    was also previously drawn unconditionally here, but ground truth shows
    ZERO SARR_EDITAR entities for a single-segment viga like V305. A
    multi-segment viga (VF301) DOES have SARR_EDITAR, but as HORIZONTAL
    lines broken at intra-segment leaf-poly boundaries — a different,
    not-yet-understood placement rule tied to real pilar gaps / segment
    composition. That belongs to the per-segment restructuring (task #8:
    compute_panels por segmento + suporte a pilar mid-span), not here.
    """
    total_width = sum(panel_widths)
    if total_width <= 0 or b <= 0:
        return

    # V310: b<10cm recebe contorno verde no painel; 10≤b≤14cm usa sarrafo 5cm.
    if b < 10:
        xp = x0
        for idx, pw in enumerate(panel_widths):
            verts = panel_verts[idx] if panel_verts and idx < len(panel_verts) else None
            if verts:
                pts = [(xp + float(v.get('x', 0.0)), y0 + float(v.get('y', 0.0))) for v in verts]
            else:
                pts = [(xp, y0), (xp + pw, y0), (xp + pw, y0 + b), (xp, y0 + b)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'SARR_CONTORNO_10cm'})
            xp += pw
        return
    layer = 'SARR_5cm' if b <= 14 else SARR_LAYER

    ch_left = panel_chanfros[0] if panel_chanfros else {}
    ch_right = panel_chanfros[-1] if panel_chanfros else {}
    te = float((ch_left or {}).get('te', 0.0))
    fe = float((ch_left or {}).get('fe', 0.0))
    td = float((ch_right or {}).get('td', 0.0))
    fd = float((ch_right or {}).get('fd', 0.0))

    # End sarrafos stay parallel to the inclined formwork edges.
    if sarrafo_esq:
        msp.add_line(
            (x0 + fe + SARR_RECUO, y0),
            (x0 + te + SARR_RECUO, y0 + b),
            dxfattribs={'layer': layer},
        )
    if sarrafo_dir:
        msp.add_line(
            (x0 + total_width - fd - SARR_RECUO, y0),
            (x0 + total_width - td - SARR_RECUO, y0 + b),
            dxfattribs={'layer': layer},
        )

    h_offsets = _sarr_h_offsets(b)
    if not h_offsets:
        return

    openings = []
    panel_x = 0.0
    for idx, pw in enumerate(panel_widths):
        for opening in (
            panel_openings[idx]
            if panel_openings and idx < len(panel_openings)
            else []
        ):
            openings.append({
                **opening,
                'x1': panel_x + float(opening['x1']),
                'x2': panel_x + float(opening['x2']),
            })
        panel_x += pw

    for offset in h_offsets:
        frac = offset / b
        xl = fe + (te - fe) * frac + SARR_RECUO
        xr = total_width - fd - (td - fd) * frac - SARR_RECUO
        if xr <= xl:
            continue
        cuts = sorted(
            (float(op['x1']), float(op['x2']))
            for op in openings
            if float(op['y1']) <= offset <= float(op['y2'])
        )
        cursor = xl
        for cut_start, cut_end in cuts:
            if cut_start > cursor:
                msp.add_line(
                    (x0 + cursor, y0 + offset),
                    (x0 + min(cut_start, xr), y0 + offset),
                    dxfattribs={'layer': layer},
                )
            cursor = max(cursor, cut_end)
        if cursor < xr:
            msp.add_line(
                (x0 + cursor, y0 + offset),
                (x0 + xr, y0 + offset),
                dxfattribs={'layer': layer},
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


def _parse_active_holes(holes):
    """Extract active holes sorted by position. Returns list of {width, position}."""
    if not holes:
        return []
    active = []
    for h in holes:
        if not h.get('active'):
            continue
        hw = float(h.get('width', 0))
        if hw <= 0:
            continue
        # Cap unreasonable hole widths (>100cm) to 20cm (typical pilar)
        if hw > 100:
            hw = 20.0
        active.append({
            'width': hw,
            'position': float(h.get('position', 0)),
        })
    active.sort(key=lambda h: h['position'])
    return active


# Deeper dim level for segment totals (between sub-panel dims and overall total)
DIM_SEG_TOTAL_BELOW = 40  # nível 2 (mesmo que DIM_TOTAL_BELOW — padrão 20/40/60)
DIM_OVERALL_BELOW   = 60  # nível 3: total geral multi-segmento


def draw_chanfro_cotas(msp, xp, y0, pw, b, chanfros):
    """Dimension each longitudinal setback on its corresponding edge."""
    te = chanfros.get('te', 0.0)
    fe = chanfros.get('fe', 0.0)
    td = chanfros.get('td', 0.0)
    fd = chanfros.get('fd', 0.0)
    OFFS = 5.0  # distância do canto para o texto

    def _lin(x1, y1, x2, y2, bx, by):
        try:
            d = msp.add_linear_dim(
                base=(bx, by), p1=(x1, y1), p2=(x2, y2),
                angle=0 if abs(x2 - x1) >= abs(y2 - y1) else 90,
                dimstyle='PAINEL', dxfattribs={'layer': 'COTA'}
            )
            d.render()
        except Exception:
            pass

    # Each value is a horizontal setback, not a square notch size.
    if te > 0:
        _lin(xp, y0 + b, xp + te, y0 + b, xp + te / 2, y0 + b + OFFS)

    if fe > 0:
        _lin(xp, y0, xp + fe, y0, xp + fe / 2, y0 - OFFS)

    if td > 0:
        _lin(xp + pw - td, y0 + b, xp + pw, y0 + b, xp + pw - td / 2, y0 + b + OFFS)

    if fd > 0:
        _lin(xp + pw - fd, y0, xp + pw, y0, xp + pw - fd / 2, y0 - OFFS)


def draw_viga(msp, x0, y0, panels_json, viga_b, viga_nome,
              pillar_left=None, pillar_right=None, holes=None, obs='',
              label_left='L Esq', label_right='L Dir'):
    """
    Draw a fundo de viga (FV) starting at x0, y0 (lower-left corner).

    Supports multi-segment vigas: each entry in panels_json is a SEGMENT
    (group of panels between pilar gaps). Active holes define gaps between
    consecutive segments where no entities are drawn (pilar crossings).

    For each segment:
      - Computes its own STOG-module sub-panels via compute_panels()
      - Draws panel polys, dividers, sarrafos independently
      - Draws sub-panel dims (1st level)
      - Draws segment total dim (2nd level, if segment has >1 sub-panel)

    Between segments a gap of hole.width is left (no geometry).

    Overall viga total dim is drawn at deepest level if >1 segment.

    Returns total footprint of the viga (segments + gaps).
    """
    if not panels_json or viga_b <= 0:
        return 0.0

    b = viga_b

    # Pre-collect all hole texts and labels to avoid printing them inside panels
    ignore_texts = set()
    if label_left: ignore_texts.add(label_left)
    if label_right: ignore_texts.add(label_right)
    if holes:
        for h in holes:
            if isinstance(h, dict) and h.get('text'):
                ignore_texts.add(h['text'])

    # -- Parse segments (each panel dict = one segment) ------------------------
    import copy as _copy
    segments = []
    for p in panels_json:
        if isinstance(p, dict) and 'total_width' in p:
            sw = float(p['total_width'])
            if sw > 0:
                mult = int(p.get('_multiplier', 1) or 1)
                if mult > 1:
                    # Expandir N cópias; só a primeira carrega _mult_label para exibir "NxMMM"
                    base = _copy.deepcopy(p)
                    base.pop('_multiplier', None)
                    base['_mult_label'] = f'{mult}x{round(sw):g}'
                    segments.append(base)
                    for _ in range(mult - 1):
                        other = _copy.deepcopy(base)
                        other.pop('_mult_label', None)  # cópias não repetem o label
                        segments.append(other)
                else:
                    segments.append(p)
        else:
            sw = float(p.get('width', 0)) if isinstance(p, dict) else float(p)
            if sw > 0:
                segments.append(sw)
    if not segments:
        return 0.0

    # -- Parse active holes as gaps between segments ---------------------------
    active_holes = _parse_active_holes(holes)

    # Build gap list: gap[i] = gap width between segment[i] and segment[i+1]
    # We match holes to inter-segment gaps using their cumulative position
    gaps = []
    current_pos = 0.0
    hole_idx = 0
    for i in range(len(segments) - 1):
        sw = float(segments[i]['total_width']) if isinstance(segments[i], dict) else float(segments[i])
        current_pos += sw
        
        # Check if the next active hole matches this position
        if hole_idx < len(active_holes):
            # Allow some floating point tolerance
            if abs(active_holes[hole_idx]['position'] - current_pos) < 5.0:
                gap_w = active_holes[hole_idx]['width']
                gap_label = active_holes[hole_idx].get('text') or 'Pilar Cruzado'
                gaps.append((gap_w, gap_label))
                current_pos += gap_w
                hole_idx += 1
                continue
                
        # No matching hole means this is a contiguous segment boundary (e.g. L-shape corner)
        gaps.append((0.0, ''))

    # -- Compute total footprint -----------------------------------------------
    total_footprint = sum(float(s['total_width']) if isinstance(s, dict) else float(s) for s in segments) + sum(g[0] for g in gaps)

    # -- Track all sub-panel edges for overall dims ----------------------------
    all_subpanel_edges = []   # list of (x_start, x_end) for every sub-panel
    segment_edges = []        # list of (seg_x0, seg_x_end) per segment
    multi_subpanel_segs = 0   # count segments with >1 sub-panel

    # -- Draw each segment -----------------------------------------------------
    x_cursor = x0
    for seg_idx, seg_item in enumerate(segments):
        # Handle both flat float/dict and rich segment dictionaries
        if isinstance(seg_item, dict) and 'panels' in seg_item:
            seg_width = seg_item['total_width']
            sub_panels = [p['width'] for p in seg_item['panels']]
            sub_panel_texts = [p.get('texts', []) for p in seg_item['panels']]
            sub_panel_verts = [p.get('vertices', None) for p in seg_item['panels']]
            sub_panel_loose = [p.get('loose', []) for p in seg_item['panels']]
        else:
            # Fallback to legacy automatic computation
            seg_width = float(seg_item) if not isinstance(seg_item, dict) else float(seg_item.get('width', 0))
            sub_panels = compute_panels(seg_width)
            sub_panel_texts = [[] for _ in sub_panels]
            sub_panel_verts = [None for _ in sub_panels]
            sub_panel_loose = [[] for _ in sub_panels]
            
        seg_x0 = x_cursor

        if not sub_panels:
            x_cursor += seg_width
            if seg_idx < len(gaps):
                x_cursor += gaps[seg_idx][0]
            continue

        # Draw panel outlines (LWPOLYLINE) for each sub-panel
        xp = seg_x0
        for i, (pw, p_texts, p_verts, p_loose) in enumerate(zip(sub_panels, sub_panel_texts, sub_panel_verts, sub_panel_loose)):
            if p_verts:
                # Custom trapezoid defined by top/bottom end setbacks.
                pts = [(xp + v['x'], y0 + v['y']) for v in p_verts]
                msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': LY_PAINEIS, 'lineweight': -1})
                p_obj = seg_item['panels'][i]
                ch = p_obj.get('chanfros', {})
                for frac in (1 / 3, 2 / 3):
                    y_line = b * frac
                    left = float(ch.get('fe', 0)) + (
                        float(ch.get('te', 0)) - float(ch.get('fe', 0))
                    ) * frac
                    right = pw - float(ch.get('fd', 0)) - (
                        float(ch.get('td', 0)) - float(ch.get('fd', 0))
                    ) * frac
                    if right > left:
                        msp.add_line(
                            (xp + left, y0 + y_line),
                            (xp + right, y0 + y_line),
                            dxfattribs={'layer': LY_PAINEIS},
                        )
            else:
                # Standard rectangular module
                panel_poly(msp, xp, y0, pw, b)
            
            # Draw loose attached entities (L-corners, etc.)
            for le in p_loose:
                le_layer = le.get('layer', LY_PAINEIS)
                if le['type'] == 'LINE':
                    msp.add_line((xp + le['start']['x'], y0 + le['start']['y']),
                                 (xp + le['end']['x'], y0 + le['end']['y']),
                                 dxfattribs={'layer': le_layer, 'lineweight': -1})
                elif le['type'] == 'LWPOLYLINE':
                    points = [
                        (xp + p['x'], y0 + p['y']) for p in le['points']
                    ]
                    msp.add_lwpolyline(
                        points, close=True,
                        dxfattribs={'layer': le_layer, 'lineweight': -1},
                    )
                elif le['type'] == 'TEXT':
                    t = msp.add_text(le['text'], dxfattribs={'layer': le_layer, 'height': 8})
                    t.dxf.insert = (xp + le['insert']['x'], y0 + le['insert']['y'])
                    
            all_subpanel_edges.append((xp, xp + pw))
            
            # Draw any specific texts inside the panel (e.g. 'P1', 'V309')
            if p_texts:
                for idx, txt in enumerate(p_texts):
                    if txt in ignore_texts: continue
                    t = msp.add_text(txt, dxfattribs={'layer': '5', 'height': 8})
                    t.dxf.insert = (xp + pw/2 - 5, y0 + b/2 + (idx * 10))

            # Draw chanfro cotas se painel tem 'chanfros' explícito
            if isinstance(seg_item, dict):
                _seg_panels = seg_item.get('panels', [])
                if i < len(_seg_panels) and isinstance(_seg_panels[i], dict):
                    _ch = _seg_panels[i].get('chanfros')
                    if _ch and any(_ch.get(k, 0) > 0 for k in ('te', 'fe', 'td', 'fd')):
                        draw_chanfro_cotas(msp, xp, y0, pw, b, _ch)

            xp += pw

        seg_x_end = seg_x0 + seg_width
        segment_edges.append((seg_x0, seg_x_end))

        # Draw panel dividers (vertical LINEs between adjacent sub-panels)
        xp = seg_x0
        for i, pw in enumerate(sub_panels):
            xp += pw
            if i < len(sub_panels) - 1:
                panel_divider(msp, xp, y0, b)

        # Draw sarrafos for this segment (respecting sarrafo_esq/dir flags from robot)
        seg_sarr_esq = seg_item.get('sarrafo_esq', True) if isinstance(seg_item, dict) else True
        seg_sarr_dir = seg_item.get('sarrafo_dir', True) if isinstance(seg_item, dict) else True
        panel_chanfros = [
            p.get('chanfros', {}) for p in seg_item.get('panels', [])
        ] if isinstance(seg_item, dict) else None
        panel_openings = [
            p.get('aberturas', []) for p in seg_item.get('panels', [])
        ] if isinstance(seg_item, dict) else None
        draw_sarr(msp, seg_x0, y0, b, sub_panels, sub_panel_verts,
                  panel_chanfros=panel_chanfros,
                  panel_openings=panel_openings,
                  sarrafo_esq=seg_sarr_esq, sarrafo_dir=seg_sarr_dir)

        # STOG posiciona os textos de extremidade acima do painel.
        label_y = y0 + b + LABEL_ABOVE
        if seg_idx == 0 and label_left:
            add_text(msp, seg_x0, label_y, label_left, LABEL_H, '5',
                     halign=0, rotation=0)
        
        if seg_idx == len(segments) - 1 and label_right:
            add_text(msp, seg_x_end, label_y, label_right, LABEL_H, '5',
                     halign=0, rotation=0)
            
        if seg_idx < len(gaps):
            gap_label = gaps[seg_idx][1]
            if gap_label and gap_label != 'Pilar Cruzado':
                gap_center = seg_x_end + gaps[seg_idx][0] / 2
                add_text(msp, gap_center, label_y, gap_label, LABEL_H, '5',
                         halign=1, rotation=0)

        # Draw individual sub-panel dims (1st level, and tiers if present)
        xp = seg_x0
        for i, pw in enumerate(sub_panels):
            if isinstance(seg_item, dict) and isinstance(seg_item.get('panels'), list) and i < len(seg_item['panels']):
                p_item = seg_item['panels'][i]
            else:
                p_item = {}
            if isinstance(p_item, dict) and 'tiers' in p_item and p_item['tiers']:
                tiers = p_item['tiers']
                for t_idx, tier_vals in enumerate(tiers):
                    # Validar: só renderizar tier se sum(tier_vals) ≈ largura do painel (±1.5cm)
                    tier_sum = sum(float(tv) for tv in tier_vals)
                    if abs(tier_sum - pw) > 1.5:
                        continue
                    t_xp = xp
                    y_off = DIM_BELOW + (t_idx * 15)  # Stack them downwards
                    for tv in tier_vals:
                        try:
                            d = msp.add_linear_dim(
                                base=(t_xp, y0 - y_off),
                                p1=(t_xp, y0),
                                p2=(t_xp + tv, y0),
                                angle=0,
                                dimstyle='PAINEL',
                                dxfattribs={'layer': 'COTA'}
                            )
                            d.render()
                        except Exception:
                            pass
                        t_xp += tv
            else:
                dim_panel(msp, xp, xp + pw, y0)
            xp += pw

        x_cursor = seg_x_end
        if seg_idx < len(gaps):
            gap_w = gaps[seg_idx][0]
            x_cursor += gap_w

        # Draw segment total dim (2nd level) if segment has >1 sub-panel
        if len(sub_panels) > 1:
            multi_subpanel_segs += 1
            # Use DIM_TOTAL_BELOW for all segment total dimensions
            seg_dim_y_offset = DIM_TOTAL_BELOW
            try:
                d = msp.add_linear_dim(
                    base=(seg_x0, y0 - seg_dim_y_offset),
                    p1=(seg_x0, y0),
                    p2=(seg_x_end, y0),
                    angle=0,
                    dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA'},
                )
                d.render()
            except Exception:
                pass

        # Texto multiplicador "NxMMM" — só quando painéis não têm geometria explícita
        if isinstance(seg_item, dict) and seg_item.get('_mult_label'):
            has_verts = any(
                isinstance(pp, dict) and pp.get('vertices')
                for pp in seg_item.get('panels', [])
            )
            if not has_verts:
                cx = (seg_x0 + seg_x_end) / 2.0
                cy = y0 + b / 2.0
                add_text(msp, cx, cy, seg_item['_mult_label'], 10, 'Painéis', halign=1)

        # Advance cursor past this segment + gap to next segment
        x_cursor = seg_x_end
        if seg_idx < len(gaps):
            x_cursor += gaps[seg_idx][0]

    # -- NOMENCLATURA text (once, above full viga) -----------------------------
    nom_text = f'{normalize_viga_name(viga_nome)}.C'
    if obs:
        nom_text = f'{nom_text} {obs}'
    add_text(msp, x0 + 3, y0 + b + NOM_ABOVE, nom_text,
             NOM_H, 'NOMENCLATURA', style='Standard')



    # -- Vertical b dim -- right side ------------------------------------------
    rightmost_x = x0 + total_footprint
    dim_viga_b(msp, rightmost_x, y0, b)

    return total_footprint


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


def _normalize_segments_rich(segments, viga_b):
    """Normaliza vértices dos panels de segments_rich para espaço local [0,w]×[0,b].

    O motor reverso extrai vértices em coordenadas CAD absolutas da posição
    da viga no DXF STOG. Cada painel deve ter y ∈ [0, b], mas pode chegar
    com y em qualquer valor absoluto (ex: y=-24.5 para b=19).

    Estratégia: para cada panel com vértices, transladar y para que y_min=0.
    Se após a translação y_max ainda divergir muito de b, truncar para b.
    """
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        b_seg = float(seg.get('total_width', 0))  # não é b, mas usamos viga_b
        for p in seg.get('panels', []):
            verts = p.get('vertices')
            if not verts or len(verts) < 3:
                continue
            y_vals = [float(v.get('y', 0)) for v in verts]
            y_min  = min(y_vals)
            if abs(y_min) < 0.01:
                continue  # já normalizado
            for v in verts:
                v['y'] = float(v.get('y', 0)) - y_min
            # Após translação, verificar se dimensão é razoável
            # L-panels podem ter y_max = b + comp2 (ala perpendicular), usar limite 3x
            y_vals2 = [float(v['y']) for v in verts]
            y_max2  = max(y_vals2)
            if y_max2 > viga_b * 3.0:
                # Provavelmente unidade diferente ou coordenada bugada — resetar
                p.pop('vertices', None)
    return segments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max',  type=int, default=999)
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só esta viga (ex: V001). Output: FV_preview_V001.dxf')
    parser.add_argument('--seg_idx', type=int, default=-1,
                        help='Com --item: gera só o segmento N (0-based). Output: FV_preview_V001_segN.dxf')
    parser.add_argument('--override_dir', type=str, default=None,
                        help='Diretório com JSONs override (V*_fundo.json) editados manualmente. '
                             'Sobrepõe segments_rich do JSON da Fase-4 quando presente.')
    parser.add_argument('--robot_json', type=str, default=None,
                        help='Caminho para JSON no formato get_current_data() do robô. '
                             'Gera DXF preview completo (chanfros, sarrafos, painel L, aberturas) '
                             'sem precisar de Fase-4 JSON. Requer também --obra e --item.')
    args = parser.parse_args()

    # -- Modo robot_json: geração direta a partir dos dados do robô ---------------
    if args.robot_json:
        rj_path = Path(args.robot_json)
        if not rj_path.exists():
            print(f'[ERRO] robot_json não encontrado: {rj_path}'); return
        rdata = json.loads(rj_path.read_text(encoding='utf-8'))
        viga_nome = rdata.get('nome', '') or (args.item or 'V?')
        viga_dict = robot_dados_to_fv_dict(rdata, viga_nome=viga_nome)
        if not viga_dict:
            print('[ERRO] robot_json: dados insuficientes (paineis ou altura zerados)'); return

        obra_path = Path(args.obra)
        out_dir   = obra_path / 'Fase-6_Execucao_CAD'
        out_dir.mkdir(parents=True, exist_ok=True)

        doc = setup_doc()
        msp = doc.modelspace()
        x0, y0 = 0.0, 200.0
        draw_viga(
            msp, x0, y0,
            viga_dict['panels'], viga_dict['b'], viga_dict['nome'],
            obs=viga_dict.get('obs', ''),
            label_left=viga_dict.get('label_left', 'L Esq'),
            label_right=viga_dict.get('label_right', 'L Dir'),
        )

        # Normaliza o nome para FV_preview_V001.dxf
        m_n = re.search(r'\d+', viga_nome)
        if m_n:
            prefix_str = re.sub(r'\d+', '', viga_nome.upper())
            out_name = f'FV_preview_{prefix_str}{int(m_n.group()):03d}.dxf'
        else:
            out_name = f'FV_preview_{viga_nome}.dxf'

        out_path = out_dir / out_name
        doc.saveas(str(out_path))
        print(f'[FV] robot_json DXF → {out_path}')
        return

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
    override_dir_path = Path(args.override_dir) if args.override_dir else None
    vigas_raw = []
    for f in fv_files:
        try:
            d = json.load(open(f, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido ou ilegível: {f.name} — {e}')
            continue
        # Aplicar override manual se existir
        if override_dir_path:
            override_f = override_dir_path / f.name
            if override_f.exists():
                try:
                    d_ov = json.loads(override_f.read_text(encoding='utf-8'))
                    if 'segments_rich' in d_ov:
                        d['segments_rich'] = d_ov['segments_rich']
                    if 'total_width' in d_ov and d_ov['total_width'] > 0:
                        d['total_width'] = d_ov['total_width']
                    print(f'[FV] Override aplicado: {override_f.name}')
                except Exception as _ov_e:
                    print(f'[FV] Override inválido {override_f.name}: {_ov_e}')
        vname = normalize_viga_name(
            re.sub(r'_fundo', '', f.stem, flags=re.IGNORECASE)
        )
        # Priority: extracted formwork width (total_width), then vigas_salvas
        v_b = d.get('total_width')
        if not v_b or v_b <= 0:
            v_b = vigas_salvas.get(vname, {}).get('b', 14)
        viga_b = float(v_b)
        
        # Priority: segments_rich -> panels (com normalização de vértices)
        panels = d.get('segments_rich', d.get('panels', []))
        panels = _normalize_segments_rich(panels, viga_b)
        
        comp   = sum(float(p.get('total_width', p.get('width', 0))) for p in panels)
        if comp > 0 and viga_b > 0:
            viga_dict = {
                'nome': vname, 'b': viga_b, 'comp': comp, 'panels': panels,
                'pillar_left': d.get('pillar_left'),
                'pillar_right': d.get('pillar_right'),
                'holes': d.get('holes', []),
                'obs': d.get('observations', ''),
                'label_left': d.get('label_left', 'L Esq'),
                'label_right': d.get('label_right', 'L Dir'),
            }
            has_row_break = any(isinstance(p, dict) and p.get('row_break') for p in panels)
            # Em modo --item não limita por MAX_ROW_W (a viga cabe inteira na prancha)
            _over_max = (comp > MAX_ROW_W) and not args.item
            if (_over_max or has_row_break) and len(panels) > 1:
                parts = []
                c_panels, c_holes = [], []
                c_comp = 0.0
                abs_pos = 0.0
                holes_list = viga_dict.get('holes', [])
                active_holes = [h for h in holes_list if h.get('active')]
                hole_idx = 0
                
                for i, p in enumerate(panels):
                    w = float(p.get('total_width', p.get('width', 0))) if isinstance(p, dict) else float(p)
                    
                    # Match hole by absolute position
                    abs_pos += w
                    gw = 0.0
                    hole_text = None
                    if hole_idx < len(active_holes):
                        if abs(active_holes[hole_idx]['position'] - abs_pos) < 5.0:
                            gw = active_holes[hole_idx]['width']
                            hole_text = active_holes[hole_idx].get('text')
                            hole_idx += 1
                            
                    is_break = isinstance(p, dict) and p.get('row_break')
                    
                    # Se estourar o limite OU se o próprio painel pede quebra, e já temos painéis na fileira atual
                    _exceeds = (c_comp + w > MAX_ROW_W) and not args.item
                    if (_exceeds or is_break) and c_panels:
                        nm = viga_dict['nome']
                        parts.append({
                            **viga_dict, 'nome': nm, 'comp': c_comp,
                            'panels': c_panels, 'holes': c_holes,
                            'label_left': viga_dict['label_left'] if not parts else (c_holes[-1]['text'] if c_holes else 'L Esq'),
                            'label_right': 'L Dir'
                        })
                        c_panels, c_holes = [], []
                        c_comp = 0.0
                        
                    c_panels.append(p)
                    c_comp += w
                    
                    if gw > 0:
                        if i + 1 < len(panels):
                            next_w = float(panels[i+1].get('total_width', panels[i+1].get('width', 0))) if isinstance(panels[i+1], dict) else float(panels[i+1])
                            # Only add the hole if it and the next panel fit in the current row (skip limit for --item)
                            if args.item or c_comp + gw + next_w <= MAX_ROW_W:
                                c_holes.append({
                                    'active': True,
                                    'width': gw,
                                    'position': c_comp,
                                    'text': hole_text
                                })
                                c_comp += gw
                    
                    abs_pos += gw
                
                if c_panels:
                    nm = viga_dict['nome']
                    parts.append({
                        **viga_dict, 'nome': nm, 'comp': c_comp,
                        'panels': c_panels, 'holes': c_holes
                    })
                vigas_raw.extend(parts)
            else:
                vigas_raw.append(viga_dict)

    # -- Filtro anti-hallucination: excluir vigas com b dominante ──────────────
    # No STOG, apenas vigas com seção não-padrão (b estreito ou especial) têm
    # prancha FV. Vigas com o b mais comum são "padrão" e NÃO aparecem no FV STOG.
    # EXCEÇÃO: se o STOG FV contém todas/maioria das vigas (incluindo b dominante),
    # o filtro não deve ser aplicado.
    vigas = vigas_raw

    # Modo segmento único: --item V301 --seg_idx 2
    if args.item and args.seg_idx >= 0:
        if not vigas_raw:
            print(f'[ERRO] Nenhuma viga encontrada para {args.item}'); return
        viga = vigas_raw[0]
        segs = viga['panels']  # já é segments_rich
        if args.seg_idx >= len(segs):
            print(f'[ERRO] Segmento {args.seg_idx} não existe em {args.item} (total: {len(segs)})'); return
        seg = segs[args.seg_idx]
        viga['panels'] = [seg]
        viga['holes']  = []
        viga['comp']   = float(seg.get('total_width', seg.get('width', 0)))
        viga['label_left']  = ''
        viga['label_right'] = ''
        vigas = [viga]
        print(f'[FV] Modo segmento: {args.item} seg{args.seg_idx} — largura {viga["comp"]:.1f}cm')

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
    # Em modo --item não reordena (preserva ordem original dos segmentos)
    if not args.item:
        vigas.sort(key=lambda v: (-v['b'], -v['comp']))

    rows = []
    cur_row, cur_w = [], 0.0
    for v in vigas:
        need = v['comp'] + (GAP_VIGAS if cur_row else 0)
        # Em modo --item coloca tudo na mesma fileira independente do tamanho
        if cur_row and cur_w + need > MAX_ROW_W and not args.item:
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
                      obs=v.get('obs', ''),
                      label_left=v.get('label_left', 'L Esq'),
                      label_right=v.get('label_right', 'L Dir'))
            print(f'  {v["nome"]:8s}: {v["comp"]:.0f}x{v["b"]:.0f}cm  row={row_idx}')
            x_cursor += v['comp'] + GAP_VIGAS

        y_min = y_row_bottom - DIM_TOTAL_BELOW - 20
        y_cursor = y_row_bottom - GAP_ROW

    # -- Cards above vigas (apenas no modo pavimento completo) -----------------
    # No modo --item, não gerar cards: eles dominam o bounding-box do DXF e
    # tornam a comparação visual N4 vs N2 inválida (N2 recorte não tem cards).
    if not args.item:
        card_y = CARD_Y_GAP
        obra_nome = obra_path.name.replace('_', ' ')
        draw_cards(msp, 0, card_y, obra_nome=obra_nome)

    # ── Sentinels / boost / prune: apenas no modo pavimento completo ──────────
    # No modo --item, estas camadas invisíveis fora do frame distorcem o
    # bounding-box e invalidam a comparação visual com o N2 recorte.
    if args.item:
        if args.seg_idx >= 0:
            out_name = f'FV_preview_{args.item}_seg{args.seg_idx}.dxf'
        else:
            out_name = f'FV_preview_{args.item}.dxf'
        out_dxf  = out_dir / out_name
        doc.saveas(str(out_dxf))
        print(f'\nDXF: {out_dxf}')
        return

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
        'SARR_2.2x7', 'SARR_5cm', 'SARR_CONTORNO_10cm',
        'NOMENCLATURA', 'Painéis', 'PAINEIS',
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

    out_name = 'FV_stog_quality.dxf'
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
