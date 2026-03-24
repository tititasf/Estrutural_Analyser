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
    'hachura-chapa':     251,   # chapas na CIMA
    'Hachura':           251,
    'Paineis':           200,   # layer faces (sem acento, como SCR)
    'SARRAFO':           251,
    'SARR_2.2x7':        40,
    'SARR_2.2x10':       60,
    'SARR_3.5x7':        81,
    'GRAVATA':           224,
    'COTA':              241,
    'NOMENCLATURA':        7,
    'Nivel':             160,
    'COTAS FURACAO':      16,
    'Defpoints':           7,
    'Texto Secao':         7,
    'CONCRETO':          251,
    '0':                   7,   # default layer
}


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


def dim_h(msp, x0, x1, y_base, layer='COTA', dimstyle='PAINEL-NOVA', offset=8):
    """Horizontal dimension."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - offset),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0,
            dimstyle=dimstyle,
            dxfattribs={'layer': layer}
        )
        d.render()
    except Exception:
        pass


def dim_v(msp, y0, y1, x_base, layer='COTA', dimstyle='PAINEL-NOVA', offset=8):
    """Vertical dimension."""
    try:
        d = msp.add_linear_dim(
            base=(x_base + offset, y0),
            p1=(x_base, y0), p2=(x_base, y1),
            angle=90,
            dimstyle=dimstyle,
            dxfattribs={'layer': layer}
        )
        d.render()
    except Exception:
        pass


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
    Draw CIMA zone at origin (ox, oy).
    All geometry is drawn at 1:1, then scaled 2x around (ox, oy) at the end.

    Anatomy (SCR reference for P11 56x46):
      - Concreto: rect at Y 70-116 (46cm), X -42 to 14 (56cm)
      - 4 chapas around concreto (layer hachura-chapa)
      - Sarrafos around chapas (layer SARRAFO)
      - Gravatas around sarrafos (layer GRAVATA)
      - HP hatch fills (6 solid fills)
      - Blocks: B1A.E/D, B1B.E/D, B2A.E, PAR.CIM/BAI/ESQ/DIR, PAR_CIMA/BAIXO
      - Dimstyle: cotax2
      - Final _SCALE 2.0
    """
    hc = comp / 2.0   # half-comp
    hl = larg / 2.0   # half-larg
    tc = T_CHAPA       # 1.2
    ts = T_SARRAFO     # 2.2
    tg = T_GRAVATA     # 1.5

    entities = []  # collect all entities for 2x scaling

    # ── 1. Concreto core ─────────────────────────────────────────────────────
    e = rect_pline(msp, ox - hc, oy - hl, comp, larg, 'CONCRETO', lw=50)
    entities.append(e)
    # AR-CONC hatch inside concreto
    e = hatch_rect(msp, ox - hc, oy - hl, comp, larg, 'Hachura', 'AR-CONC', scale=2.5)
    entities.append(e)

    # ── 2. Chapas (4 faces, layer hachura-chapa) ─────────────────────────────
    # Face A (bottom, horizontal) — full width including corners
    e = rect_pline(msp, ox - hc - tc, oy - hl - tc, comp + 2 * tc, tc, 'hachura-chapa', lw=18)
    entities.append(e)
    e = hatch_solid(msp, ox - hc - tc, oy - hl - tc, comp + 2 * tc, tc, 'hachura-chapa')
    entities.append(e)
    # Face C (top, horizontal)
    e = rect_pline(msp, ox - hc - tc, oy + hl, comp + 2 * tc, tc, 'hachura-chapa', lw=18)
    entities.append(e)
    e = hatch_solid(msp, ox - hc - tc, oy + hl, comp + 2 * tc, tc, 'hachura-chapa')
    entities.append(e)
    # Face B (left, vertical)
    e = rect_pline(msp, ox - hc - tc, oy - hl, tc, larg, 'hachura-chapa', lw=18)
    entities.append(e)
    e = hatch_solid(msp, ox - hc - tc, oy - hl, tc, larg, 'hachura-chapa')
    entities.append(e)
    # Face D (right, vertical)
    e = rect_pline(msp, ox + hc, oy - hl, tc, larg, 'hachura-chapa', lw=18)
    entities.append(e)
    e = hatch_solid(msp, ox + hc, oy - hl, tc, larg, 'hachura-chapa')
    entities.append(e)

    # ── 3. Sarrafos around chapas (layer SARRAFO) ────────────────────────────
    # Face A sarrafo (bottom)
    e = rect_pline(msp, ox - hc - tc - ts, oy - hl - tc - ts, comp + 2 * (tc + ts), ts, 'SARRAFO', lw=13)
    entities.append(e)
    # Face C sarrafo (top)
    e = rect_pline(msp, ox - hc - tc - ts, oy + hl + tc, comp + 2 * (tc + ts), ts, 'SARRAFO', lw=13)
    entities.append(e)
    # Face B sarrafo (left)
    e = rect_pline(msp, ox - hc - tc - ts, oy - hl, ts, larg, 'SARRAFO', lw=13)
    entities.append(e)
    # Face D sarrafo (right)
    e = rect_pline(msp, ox + hc + tc, oy - hl, ts, larg, 'SARRAFO', lw=13)
    entities.append(e)

    # ── 4. Gravatas (perfis metálicos, layer GRAVATA) ────────────────────────
    ext_h = tc + ts   # chapa + sarrafo
    gw = comp + 2 * (ext_h + tg + 3.0)   # +3.0 extension beyond
    gh = larg + 2 * (ext_h + tg)
    # Bottom gravata (face A)
    e = rect_pline(msp, ox - gw / 2, oy - hl - ext_h - tg, gw, tg, 'GRAVATA', lw=50)
    entities.append(e)
    # Top gravata (face C)
    e = rect_pline(msp, ox - gw / 2, oy + hl + ext_h, gw, tg, 'GRAVATA', lw=50)
    entities.append(e)
    # Left gravata (face B)
    e = rect_pline(msp, ox - hc - ext_h - tg, oy - gh / 2, tg, gh, 'GRAVATA', lw=50)
    entities.append(e)
    # Right gravata (face D)
    e = rect_pline(msp, ox + hc + ext_h, oy - gh / 2, tg, gh, 'GRAVATA', lw=50)
    entities.append(e)

    # ── 5. Sarrafo corner fills (HP hatch — 6 solid fills) ───────────────────
    # Corner sarrafo fills at each corner intersection
    corners = [
        (ox - hc - tc - ts, oy - hl - tc - ts, ts, ts),  # bottom-left
        (ox + hc + tc,      oy - hl - tc - ts, ts, ts),  # bottom-right
        (ox - hc - tc - ts, oy + hl + tc,      ts, ts),  # top-left
        (ox + hc + tc,      oy + hl + tc,      ts, ts),  # top-right
    ]
    for cx, cy, cw, ch in corners:
        e = hatch_solid(msp, cx, cy, cw, ch, 'hachura-chapa')
        entities.append(e)
    # Two additional HP fills (mid-face sarrafo extensions)
    e = hatch_solid(msp, ox - hc - tc, oy - hl - tc, tc, tc, 'hachura-chapa')
    entities.append(e)
    e = hatch_solid(msp, ox + hc, oy + hl, tc, tc, 'hachura-chapa')
    entities.append(e)

    # ── 6. Block insertions ──────────────────────────────────────────────────
    # B1A.E (left of face A), B1A.D (right of face A)
    e = msp.add_blockref('B1A.E', (ox - hc - ext_h - 3, oy - hl - ext_h - 8),
                         dxfattribs={'layer': 'SARR_2.2x7'})
    entities.append(e)
    e = msp.add_blockref('B1A.D', (ox + hc + ext_h + 1, oy - hl - ext_h - 8),
                         dxfattribs={'layer': 'SARR_2.2x7'})
    entities.append(e)
    # B1B.E / B1B.D (face B/D side sarrafos)
    e = msp.add_blockref('B1B.E', (ox - hc - ext_h - 3, oy + hl + ext_h + 1),
                         dxfattribs={'layer': 'SARR_2.2x7'})
    entities.append(e)
    e = msp.add_blockref('B1B.D', (ox + hc + ext_h + 1, oy + hl + ext_h + 1),
                         dxfattribs={'layer': 'SARR_2.2x7'})
    entities.append(e)
    # B2A.E (extra sarrafo block — left side only)
    e = msp.add_blockref('B2A.E', (ox - hc - ext_h - 6, oy - 3.5),
                         dxfattribs={'layer': 'SARR_2.2x7'})
    entities.append(e)

    # PAR blocks (parafuso markers — 4 at cardinal positions)
    e = msp.add_blockref('PAR.CIM', (ox, oy + hl + ext_h + tg + 3),
                         dxfattribs={'layer': 'COTA'})
    entities.append(e)
    e = msp.add_blockref('PAR.BAI', (ox, oy - hl - ext_h - tg - 3),
                         dxfattribs={'layer': 'COTA'})
    entities.append(e)
    e = msp.add_blockref('PAR.ESQ', (ox - hc - ext_h - tg - 3, oy),
                         dxfattribs={'layer': 'COTA'})
    entities.append(e)
    e = msp.add_blockref('PAR.DIR', (ox + hc + ext_h + tg + 3, oy),
                         dxfattribs={'layer': 'COTA'})
    entities.append(e)

    # PAR_CIMA / PAR_BAIXO (position markers)
    e = msp.add_blockref('PAR_CIMA', (ox - hc - 5, oy + hl + ext_h + tg + 6),
                         dxfattribs={'layer': 'COTA'})
    entities.append(e)
    e = msp.add_blockref('PAR_BAIXO', (ox + hc + 3, oy - hl - ext_h - tg - 6),
                         dxfattribs={'layer': 'COTA'})
    entities.append(e)

    # ── 7. Dimensions (cotax2) ───────────────────────────────────────────────
    dim_y_base = oy - hl - ext_h - tg - 5
    dim_h(msp, ox - hc, ox + hc, dim_y_base, 'COTA', 'cotax2', offset=6)
    dim_h(msp, ox - hc - tc, ox + hc + tc, dim_y_base - 8, 'COTA', 'cotax2', offset=6)
    dim_h(msp, ox - hc - ext_h, ox + hc + ext_h, dim_y_base - 16, 'COTA', 'cotax2', offset=6)

    dim_x_base = ox + hc + ext_h + tg + 5
    dim_v(msp, oy - hl, oy + hl, dim_x_base, 'COTA', 'cotax2', offset=6)
    dim_v(msp, oy - hl - tc, oy + hl + tc, dim_x_base + 8, 'COTA', 'cotax2', offset=6)
    dim_v(msp, oy - hl - ext_h, oy + hl + ext_h, dim_x_base + 16, 'COTA', 'cotax2', offset=6)

    # Additional dims for chapa thickness
    dim_h(msp, ox - hc - tc, ox - hc, dim_y_base, 'COTA', 'cotax2', offset=6)
    dim_h(msp, ox + hc, ox + hc + tc, dim_y_base, 'COTA', 'cotax2', offset=6)

    # Dims for sarrafo width
    dim_h(msp, ox - hc - tc - ts, ox - hc - tc, dim_y_base - 8, 'COTA', 'cotax2', offset=6)
    dim_h(msp, ox + hc + tc, ox + hc + tc + ts, dim_y_base - 8, 'COTA', 'cotax2', offset=6)

    dim_v(msp, oy - hl - tc, oy - hl, dim_x_base, 'COTA', 'cotax2', offset=6)
    dim_v(msp, oy + hl, oy + hl + tc, dim_x_base, 'COTA', 'cotax2', offset=6)
    dim_v(msp, oy - hl - ext_h, oy - hl - tc, dim_x_base + 8, 'COTA', 'cotax2', offset=6)

    # ── 8. Section label ─────────────────────────────────────────────────────
    secao = f'{comp:.0f}x{larg:.0f}'
    mtext(msp, ox, oy, secao, height=4, layer='COTA', anchor=5)

    # ── 9. Pilar name ────────────────────────────────────────────────────────
    e = msp.add_mtext(nome, dxfattribs={
        'layer': 'NOMENCLATURA', 'insert': (ox, oy + hl + ext_h + tg + 15),
        'char_height': 6, 'attachment_point': 8,
    })
    entities.append(e)

    # ── 10. _SCALE 2.0 — scale all CIMA entities by 2x around center ────────
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
    Draw ABCD zone starting at base_x, base_y.
    4 faces: A(comp), B(larg), C(comp), D(larg) spaced horizontally.

    Anatomy:
      - Layer: Paineis (simple rectangles, no hatch)
      - Vertical sarrafos SARR_2.2x7 inside each panel
      - Sarrafos: DASHED below (lower portion), CONTINUOUS above
      - Blocks: MULDURA (1), SLIPTEE (2), SLIPTDD (2), furacao (5/face = 20)
      - Dimstyle: PAINEL-NOVA
      - Horizontal sarrafo labels "9 sarr." / "2 sarr." on C/D faces
    """
    face_widths = {
        'A': comp, 'B': larg, 'C': comp, 'D': larg
    }
    face_labels = ['A', 'B', 'C', 'D']

    entity_count = 0
    fx = base_x

    # Parafuso spacing from JSON
    par_keys = ['par_1_2', 'par_2_3', 'par_3_4', 'par_4_5',
                'par_5_6', 'par_6_7', 'par_7_8', 'par_8_9']
    par_vals = []
    for pk in par_keys:
        v = pj.get(pk, 0)
        try:
            fv = float(str(v).replace(',', '.')) if v else 0
        except (ValueError, TypeError):
            fv = 0
        if fv > 0:
            par_vals.append(fv)

    # Get face heights
    def get_face_heights(fid):
        h1 = float(pj.get(f'h1_{fid}', 0))
        h2 = float(pj.get(f'h2_{fid}', 0))
        h3 = float(pj.get(f'h3_{fid}', 0))
        if h1 + h2 + h3 <= 0:
            total = altura
            h1, h3 = 2.0, min(34.0, total - 246)
            h2 = total - h1 - h3
        return h1, h2, h3

    for fid in face_labels:
        fw = face_widths[fid]
        h1, h2, h3 = get_face_heights(fid)
        total_h = h1 + h2 + h3

        if total_h <= 0 or fw <= 0:
            fx += fw + FACE_SPACING
            continue

        # ── Panel rectangle (layer Paineis) ──────────────────────────────
        rect_pline(msp, fx, base_y, fw, total_h, 'Paineis', lw=35)
        entity_count += 1

        # ── Horizontal dividers between segments ─────────────────────────
        if h1 > 0 and h2 > 0:
            msp.add_line((fx, base_y + h1), (fx + fw, base_y + h1),
                         dxfattribs={'layer': 'Paineis', 'lineweight': 18})
            entity_count += 1
        if h2 > 0 and h3 > 0:
            msp.add_line((fx, base_y + h1 + h2), (fx + fw, base_y + h1 + h2),
                         dxfattribs={'layer': 'Paineis', 'lineweight': 18})
            entity_count += 1

        # ── Vertical sarrafos SARR_2.2x7 inside panel ───────────────────
        sarr_w = 2.2
        # For faces A/B: vertical sarrafos with DASHED bottom, CONTINUOUS top
        if fid in ('A', 'B'):
            n_sarr = max(1, int(fw / 8))  # ~1 sarrafo every 8cm
            spacing = fw / (n_sarr + 1)
            dash_boundary = h1  # below h1 is dashed
            for i in range(1, n_sarr + 1):
                sx = fx + i * spacing
                # Lower portion (DASHED)
                if h1 > 0:
                    msp.add_line((sx, base_y), (sx, base_y + dash_boundary),
                                 dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 13,
                                             'linetype': 'DASHED'})
                    entity_count += 1
                # Upper portion (CONTINUOUS)
                msp.add_line((sx, base_y + dash_boundary), (sx, base_y + total_h),
                             dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 13})
                entity_count += 1
        else:
            # Faces C/D: horizontal sarrafos with count annotation
            n_sarr_h = max(1, int(total_h / 30))
            if n_sarr_h > 1:
                h_spacing = total_h / (n_sarr_h + 1)
                for i in range(1, n_sarr_h + 1):
                    sy = base_y + i * h_spacing
                    msp.add_line((fx, sy), (fx + fw, sy),
                                 dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 13})
                    entity_count += 1
            # Annotation: "N sarr."
            n_ann = max(2, n_sarr_h)
            msp.add_mtext(f'{n_ann} sarr.', dxfattribs={
                'layer': 'NOMENCLATURA', 'insert': (fx + fw + 5, base_y + total_h / 2),
                'char_height': 4, 'attachment_point': 4,
            })
            entity_count += 1

        # ── Nivel lines (dashed horizontal at top/bottom) ────────────────
        msp.add_line((fx - 4, base_y + total_h), (fx + fw + 4, base_y + total_h),
                     dxfattribs={'layer': 'Nivel', 'linetype': 'DASHED'})
        msp.add_line((fx - 4, base_y), (fx + fw + 4, base_y),
                     dxfattribs={'layer': 'Nivel', 'linetype': 'DASHED'})
        entity_count += 2

        # ── Furacao blocks (5 per face, spaced vertically) ───────────────
        if par_vals:
            y_furo = base_y
            furo_count = 0
            for pv in par_vals:
                y_furo += pv
                if furo_count >= 5:
                    break
                # Place furacao on both sides of face
                msp.add_blockref('furacao', (fx - 3, y_furo),
                                 dxfattribs={'layer': 'COTAS FURACAO'})
                msp.add_blockref('furacao', (fx + fw + 3, y_furo),
                                 dxfattribs={'layer': 'COTAS FURACAO'})
                entity_count += 2
                furo_count += 1

        # ── Dimensions (PAINEL-NOVA) ─────────────────────────────────────
        dim_h(msp, fx, fx + fw, base_y, 'COTA', 'PAINEL-NOVA', offset=12)
        dim_v(msp, base_y, base_y + total_h, fx + fw, 'COTA', 'PAINEL-NOVA', offset=12)
        entity_count += 2

        # ── Face label ───────────────────────────────────────────────────
        msp.add_mtext(f'{nome}.{fid}', dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (fx + fw / 2, base_y + total_h + 8),
            'char_height': 5, 'attachment_point': 8,
        })
        entity_count += 1

        fx += fw + FACE_SPACING

    # ── MULDURA block (1x, at first face center top) ────────────────────────
    msp.add_blockref('MULDURA', (base_x + comp / 2 - 2, base_y + altura - 5),
                     dxfattribs={'layer': 'Paineis'})
    entity_count += 1

    # ── SLIPTEE blocks (2x) ─────────────────────────────────────────────────
    slip_y1 = base_y + altura * 0.3
    slip_y2 = base_y + altura * 0.7
    msp.add_blockref('SLIPTEE', (base_x - 5, slip_y1),
                     dxfattribs={'layer': 'Paineis'})
    msp.add_blockref('SLIPTEE', (base_x - 5, slip_y2),
                     dxfattribs={'layer': 'Paineis'})
    entity_count += 2

    # ── SLIPTDD blocks (2x) ─────────────────────────────────────────────────
    face_b_x = base_x + comp + FACE_SPACING
    msp.add_blockref('SLIPTDD', (face_b_x - 5, slip_y1),
                     dxfattribs={'layer': 'Paineis'})
    msp.add_blockref('SLIPTDD', (face_b_x - 5, slip_y2),
                     dxfattribs={'layer': 'Paineis'})
    entity_count += 2

    return entity_count


# ═════════════════════════════════════════════════════════════════════════════
# GRADES — Grade rectangles with LINE entities
# ═════════════════════════════════════════════════════════════════════════════

def draw_grades(msp, base_x, base_y, grade_1, grade_2, comp, larg, altura, nome, pj):
    """
    Draw GRADES zone at base_x, base_y.
    Two grades side by side (grade_1 and grade_2 widths).

    Anatomy (SCR reference):
      - 56 LINEs (14 rectangles x 4 lines each)
      - Uses LINE entities (NOT PLINE) and LAYER command
      - 2 grades: Grade1 (base_x to base_x+grade_w) + Grade2 (gap=22)
      - Base: grade_width x 2.2cm
      - Left vertical: SARR_2.2x7 (7cm wide)
      - Right vertical: SARR_3.5x7 (3.5cm wide) — interlocking
      - Horizontal: SARR_2.2x10 (10cm tall) at regular intervals
      - GRA-E and GRA-D triangle blocks at top
      - Dimstyle: PAINEL-NOVA
    """
    entity_count = 0
    grade_gap = 22  # gap between grade 1 and grade 2

    grades = []
    if grade_1 > 0:
        grades.append(('Grade1', grade_1))
    if grade_2 > 0:
        grades.append(('Grade2', grade_2))

    gx = base_x

    for gname, gwidth in grades:
        grade_h = 2.2   # base height

        # ── Base rectangle (grade_width x 2.2) ──────────────────────────
        rect_lines(msp, gx, base_y, gwidth, grade_h, 'SARR_2.2x7')
        entity_count += 4  # 4 LINE entities per rectangle

        # ── Left vertical: SARR_2.2x7 (7cm wide, full height) ───────────
        sarr_left_w = 7
        sarr_left_h = altura  # full pilar height
        rect_lines(msp, gx, base_y, sarr_left_w, sarr_left_h, 'SARR_2.2x7')
        entity_count += 4

        # ── Right vertical: SARR_3.5x7 (3.5cm wide, interlocking) ───────
        sarr_right_w = 3.5
        rect_lines(msp, gx + gwidth - sarr_right_w, base_y, sarr_right_w, sarr_left_h, 'SARR_3.5x7')
        entity_count += 4

        # ── Horizontal sarrafos: SARR_2.2x10 (10cm tall) at intervals ───
        # Positions from SCR anatomy: Y=32, 122, 212, 272 (for h=280)
        # Generalize: space them evenly
        n_horiz = max(2, int(altura / 70))
        h_positions = []
        if n_horiz > 0:
            interval = (sarr_left_h - 10) / (n_horiz + 1)
            for i in range(1, n_horiz + 1):
                h_positions.append(base_y + i * interval)

        for hy in h_positions:
            rect_lines(msp, gx + sarr_left_w, hy, gwidth - sarr_left_w - sarr_right_w, 10, 'SARR_2.2x10')
            entity_count += 4

        # ── GRA-E triangle block (top-left) ──────────────────────────────
        msp.add_blockref('GRA-E', (gx, base_y + sarr_left_h),
                         dxfattribs={'layer': 'SARR_2.2x7'})
        entity_count += 1

        # ── GRA-D triangle block (top-right) ─────────────────────────────
        msp.add_blockref('GRA-D', (gx + gwidth - 7, base_y + sarr_left_h),
                         dxfattribs={'layer': 'SARR_2.2x7'})
        entity_count += 1

        # ── Dimensions ───────────────────────────────────────────────────
        dim_h(msp, gx, gx + gwidth, base_y, 'COTA', 'PAINEL-NOVA', offset=10)
        dim_v(msp, base_y, base_y + sarr_left_h, gx + gwidth, 'COTA', 'PAINEL-NOVA', offset=10)
        # Width dims for sarrafos
        dim_h(msp, gx, gx + sarr_left_w, base_y - 15, 'COTA', 'PAINEL-NOVA', offset=5)
        dim_h(msp, gx + gwidth - sarr_right_w, gx + gwidth, base_y - 15, 'COTA', 'PAINEL-NOVA', offset=5)
        entity_count += 4

        # ── Grade label ──────────────────────────────────────────────────
        msp.add_mtext(f'{nome} - {gname}', dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (gx + gwidth / 2, base_y + sarr_left_h + 12),
            'char_height': 5, 'attachment_point': 8,
        })
        entity_count += 1

        gx += gwidth + grade_gap

    return entity_count


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
    if grade_1 > 0 or grade_2 > 0:
        grades_x = ZONE_GRADES_X
        grades_y = row_y_offset
        n = draw_grades(msp, grades_x, grades_y, grade_1, grade_2,
                       comp, larg, altura, nome, pj)
        total_entities += n

    return total_entities


def main():
    parser = argparse.ArgumentParser(
        description='Generate STOG-quality PL DXF with 3 separate zones (ABCD, CIMA, GRADES)')
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max', type=int, default=999)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    json_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Pilares'
    out_dir = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    pilar_files = sorted(
        json_dir.glob('P*.json'),
        key=lambda p: int(p.stem[1:]) if p.stem[1:].isdigit() else 999
    )[:args.max]

    if not pilar_files:
        print(f'[ERRO] Nenhum P*.json em {json_dir}')
        return

    obra_nome = obra_path.name
    print(f'Processando {len(pilar_files)} pilares (3 zones: ABCD/CIMA/GRADES)')
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
        pj = json.load(open(pf, encoding='utf-8'))
        nome = pj.get('nome', pf.stem)
        comp = pj.get('comprimento', '?')
        larg_v = pj.get('largura', '?')
        altura = float(pj.get('altura', 280))

        n = generate_pilar(msp, pj, row_y)
        total_entities += n

        print(f'  [{idx + 1:2d}] {nome}: {comp}x{larg_v}cm h={altura:.0f}cm  entities={n}')

        row_y -= (altura + row_gap)

    out_dxf = out_dir / 'PL_stog_quality.dxf'
    doc.saveas(str(out_dxf))
    print(f'\nTotal entities: {total_entities}')
    print(f'DXF: {out_dxf}')

    # ── PNG preview ──────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        fig, axes = plt.subplots(1, 3, figsize=(30, 10), facecolor='#0a0a14')

        # First pilar data for zoom views
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
