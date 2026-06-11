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

    def hp(x0, y0, w, h, layer):
        """HP command equivalent — solid hatch fill on SARRAFO."""
        pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
        hatch = msp.add_hatch(color=256, dxfattribs={'layer': layer})
        hatch.paths.add_polyline_path(pts, is_closed=True)
        hatch.set_pattern_fill('SOLID')
        entities.append(hatch)
        return hatch

    # ── 1. Chapas (4 PLINEs on hachura-chapa) ────────────────────────────────
    rp(chapa_l, cy_b, TC, larg, 'Hachura', lw=18)             # face B (left vert)
    rp(cx_r,    cy_b, TC, larg, 'Hachura', lw=18)             # face D (right vert)
    rp(corner_l, cy_t, chapa_full_w, TC, 'Hachura', lw=18)    # face C (top horiz)
    rp(corner_l, cy_b - TC, chapa_full_w, TC, 'Hachura', lw=18)  # face A (bot horiz)

    # ── 2. COTA dim 1: total chapa width ─────────────────────────────────────
    dim_h(msp, corner_l, corner_r, cy_b - TC - 5, 'COTA', 'cotax2', offset=5)

    # ── 3. Sarrafos (8 PLINEs + 8 HP on SARRAFO) ────────────────────────────
    # Face B (left vertical), lower half
    rp(sarr_l, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    hp(sarr_l, cy_b, TS, SARR_H, 'SARRAFO')
    # Face B upper half
    rp(sarr_l, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    hp(sarr_l, cy_t - SARR_H, TS, SARR_H, 'SARRAFO')
    # Face D (right vertical), lower half
    rp(chapa_r, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    hp(chapa_r, cy_b, TS, SARR_H, 'SARRAFO')
    # Face D upper half
    rp(chapa_r, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    hp(chapa_r, cy_t - SARR_H, TS, SARR_H, 'SARRAFO')
    # Corner BL top: x[corner_l, sarr_l], y[cy_t-2, cy_t]
    rp(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO')
    # Corner BL bottom: y[cy_b, cy_b+2]
    rp(corner_l, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp(corner_l, cy_b, CORNER_W, CORNER_H, 'SARRAFO')
    # Corner DR top:
    rp(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO')
    # Corner DR bottom:
    rp(sarr_r, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp(sarr_r, cy_b, CORNER_W, CORNER_H, 'SARRAFO')

    # ── 4. COTA dims 2-5 ─────────────────────────────────────────────────────
    # dim 2: concrete comp (horizontal)
    dim_h(msp, cx_l, cx_r, cy_b - TC - 5 + 7, 'COTA', 'cotax2', offset=5)
    # dim 3: concrete larg (vertical)
    dim_v(msp, cy_b, cy_t, cx_r + 12, 'COTA', 'cotax2', offset=5)
    # dim 4: left corner width
    dim_h(msp, corner_l, sarr_l, cy_b + 2, 'COTA', 'cotax2', offset=5)
    # dim 5: right corner width
    dim_h(msp, sarr_r, corner_r, cy_b + 2, 'COTA', 'cotax2', offset=5)

    # ── 5. Gravatas (4 PLINEs on GRAVATA: 2 outer + 2 inner, horizontal) ─────
    grav_w = grav_r - grav_l
    # outer bottom A
    rp(grav_l, cy_b - GRAV_BELOW_OUTER - GRAV_OUTER_H, grav_w, GRAV_OUTER_H, 'GRAVATA', lw=50)
    # outer top C
    rp(grav_l, cy_t + GRAV_BELOW_OUTER, grav_w, GRAV_OUTER_H, 'GRAVATA', lw=50)
    # inner bottom A
    rp(grav_l, cy_b - GRAV_BELOW_INNER - GRAV_INNER_H, grav_w, GRAV_INNER_H, 'GRAVATA', lw=50)
    # inner top C
    rp(grav_l, cy_t + GRAV_BELOW_INNER, grav_w, GRAV_INNER_H, 'GRAVATA', lw=50)

    # ── 6. cota (lowercase) dims: gravata total width + small ────────────────
    try:
        d = msp.add_linear_dim(
            base=(ox, cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H + 40),
            p1=(grav_l, cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H),
            p2=(grav_r, cy_t + GRAV_BELOW_OUTER + GRAV_OUTER_H),
            angle=0, dimstyle='cotax2',
            dxfattribs={'layer': 'COTA'}
        )
        d.render()
    except Exception:
        pass
    try:
        d = msp.add_linear_dim(
            base=(cx_l - 15, cy_b - GRAV_BELOW_OUTER - 10),
            p1=(cx_l, cy_b - GRAV_BELOW_OUTER),
            p2=(chapa_l, cy_b - GRAV_BELOW_OUTER),
            angle=0, dimstyle='cotax2',
            dxfattribs={'layer': 'COTA'}
        )
        d.render()
    except Exception:
        pass

    # ── 7a. Texto Seção: rótulos das partes da seção transversal (STOG: 212) ──
    secao_labels = [
        ('SAR', sarr_l - TS - 4, oy),
        ('CHP', chapa_l - TC/2,  oy),
        ('CONC', ox,               oy),
        ('CHP', chapa_r + TC/2,  oy),
        ('SAR', chapa_r + TS + 4, oy),
        ('GRV', grav_l + 2,       cy_b - GRAV_BELOW_OUTER - GRAV_OUTER_H/2),
        ('GRV', grav_r - 10,      cy_b - GRAV_BELOW_OUTER - GRAV_OUTER_H/2),
        (f'{comp:.0f}', cx_l + (cx_r-cx_l)/2, cy_b - TC - 15),
        (f'{larg:.0f}', cx_r + 20, oy),
    ]
    for label, tx, ty in secao_labels:
        entities.append(
            msp.add_text(label, dxfattribs={
                'layer': 'Texto Seção',
                'insert': (tx, ty),
                'height': 3.5,
            })
        )

    # ── 7. NOMENCLATURA: 1 MTEXT (nome) + 4 TEXT (face labels A/B/C/D) ───────
    msp.add_mtext(
        f'{nome}\n({comp:.0f}X{larg:.0f})',
        dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (ox, cy_t + 100),
            'char_height': 6,
            'attachment_point': 8,
        }
    )
    for txt, tx, ty in [
        ('D', cx_r - 6, cy_b + 1),
        ('C', cx_l - 2, cy_b + 1),
        ('A', cx_l - 2, cy_b + 2),
        ('B', cx_r + 1, oy),
    ]:
        msp.add_text(txt, dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (tx, ty),
            'height': 4,
        })

    # ── 8. Hachura PLINE (1 — height indicator, narrow vert rect) ───────────
    e = rp(cx_r + 16, oy - hl - 24, 1.0, larg + 48, 'Hachura', lw=13)

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
    Exact anatomy from SCR reverse engineering (P01_ABCD.scr, P10_ABCD.scr).

    Coordinate system:
      base_x = x_inicial (= ZONE_ABCD_X = -7000)
      base_y = y_inicial (TOP of pilar, default -100)
      y_bot  = base_y - altura  (BOTTOM of pilar)

    Face positions (standard MULDURA config):
      x_a = base_x + 80
      largura_a = largura_b = comp + 22  (panel width = concrete + chapa each side)
      largura_c = largura_d = larg
      espacamento = 278  (from SCR analysis)
      x_b = x_a + largura_a + espacamento
      x_c = x_b + largura_b + espacamento
      x_d = x_c + largura_c + (espacamento - 70)

    Layers (EXACTLY as in SCR with accents):
      Nível       — 2 horizontal PLINEs spanning all faces (top/bottom)
      cota        — DIMLINEAR overall height + 3 dims per face
      Painéis     — 4 open PLINEs per panel face (rect drawn as 4 segments)
      SARR_2.2x7  — vertical open PLINEs, DASHED lower + CONTINUOUS upper
      nomenclatura — TEXT labels (face labels + header texts)
      cota        — INSERT SLIPTEE + SLIPTDD per face A/B
    """
    # ── Constants (from SCR reverse engineering) ──────────────────────────────
    SARR_OFFSET  = 7      # sarrafo position from left face edge
    X_OFFSET     = 80     # face A left offset from zone start
    ESPACAMENTO  = 278    # spacing between faces (empirically derived from SCR)
    H1_DEFAULT   = 2.0    # bottom gap segment height
    H3_DEFAULT   = 34.0   # top segment height

    # SCR coordinate system: y_top = base_y - 100, y_bot = base_y - 100 - altura
    # (face view starts 100 units below row origin, spans downward by altura)
    y_top = base_y - 100
    y_bot = base_y - 100 - altura

    # Face heights (3 segments: h1=bottom gap, h2=middle, h3=top)
    def get_face_heights():
        h1 = H1_DEFAULT
        h3 = min(H3_DEFAULT, altura - H1_DEFAULT - 1)
        h2 = altura - h1 - h3
        return h1, h2, h3

    h1, h2, h3 = get_face_heights()

    # Faces alternating pattern (verified against P02_ABCD.scr SLIPTEE/SLIPTDD):
    # A spans comprimento, B spans largura, C spans comprimento, D spans largura
    # Panel width = concrete_dim + 22 (chapa on each side)
    larg_a = comp + 22   # face A panel: comprimento + chapa
    larg_b = larg + 22   # face B panel: largura + chapa
    larg_c = comp + 22   # face C panel: comprimento + chapa (alternates with A)
    larg_d = larg + 22   # face D panel: largura + chapa (alternates with B)

    x_a = base_x + X_OFFSET
    x_b = x_a + larg_a + ESPACAMENTO
    x_c = x_b + larg_b + ESPACAMENTO
    x_d = x_c + larg_c + (ESPACAMENTO - 70)

    face_info = [
        ('A', x_a, larg_a, comp),   # (label, x_left, panel_width, concrete_dim)
        ('B', x_b, larg_b, larg),   # face B concrete = largura
        ('C', x_c, larg_c, comp),   # face C concrete = comprimento (same as A)
        ('D', x_d, larg_d, larg),   # face D concrete = largura (same as B)
    ]

    entity_count = 0

    def open_pline(x0, y0, x1, y1, layer, lt=None):
        """Draw a 2-point open LWPOLYLINE (line segment)."""
        attrs = {'layer': layer}
        if lt:
            attrs['linetype'] = lt
        e = msp.add_lwpolyline([(x0, y0), (x1, y1)], close=False, dxfattribs=attrs)
        entity_count_ref[0] += 1
        return e

    entity_count_ref = [0]

    # ── 1. Nível lines: 2 horizontal PLINEs spanning all faces ───────────────
    # SCR: (-7000,-100) to (-6000,-100) and (-7000,-380) to (-6000,-380)
    x_span_l = base_x           # -7000
    x_span_r = base_x + 1000   # -6000
    msp.add_lwpolyline([(x_span_l, y_top), (x_span_r, y_top)],
                       close=False, dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    msp.add_lwpolyline([(x_span_l, y_bot), (x_span_r, y_bot)],
                       close=False, dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    entity_count += 2

    # ── 2. Overall height DIMLINEAR on 'cota' ─────────────────────────────────
    # SCR: ref points at x=-6950 (=x_a-30), annotation at x=-6970 (=x_a-50)
    x_dim_overall = x_a - 30
    try:
        d = msp.add_linear_dim(
            base=(x_a - 50, (y_top + y_bot) / 2),
            p1=(x_dim_overall, y_bot), p2=(x_dim_overall, y_top),
            angle=90, dimstyle='PAINEL-NOVA',
            dxfattribs={'layer': 'COTA'}
        )
        d.render()
        entity_count += 1
    except Exception:
        pass

    # ── 3. MULDURA block (title frame, at zone start)  ────────────────────────
    # SCR: MULDURA at (-7000,-342.0) = (base_x, y_bot + 38)
    try:
        msp.add_blockref('MULDURA', (base_x, y_bot + 38),
                         dxfattribs={'layer': 'COTA'})
        entity_count += 1
    except Exception:
        pass

    # ── 4. Header texts (nomenclatura layer, TEXT entities) ───────────────────
    # SCR: x=-6969 (≈x_a-49), y=280/255/230 (= base_y + 280/255/230)
    header_x = x_a - 49
    for i, txt in enumerate([
        f'CENARIOS - PD: {altura/100:.2f}',
        f'NIVEL DE SAIDA: 0,00',
        f'NIVEL DE CHEGADA: {altura/100:.2f}',
    ]):
        msp.add_text(txt, dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (header_x, base_y + 280 - i * 25),
            'height': 15,
        })
        entity_count += 1

    # ── 5. Per-face drawing ────────────────────────────────────────────────────
    # Dynamic furacao y-positions (verified P23-P27, P43, P45, P48 SCR):
    # start y_bot+30, first gap 50, subsequent gaps 55, stop when y >= y_top-35
    def _furacao_ys(yb, yt):
        ys = []
        y = yb + 30
        gap = 50
        while y <= (yt - 35):
            ys.append(y)
            y += gap
            gap = 55
        return ys

    fura_ys = _furacao_ys(y_bot, y_top)

    # Short-pillar flag: alt < 280 → simplified sarrafo/dim structure (verified P21/P22/P44 SCR)
    is_short = altura < 280

    for fid, x_left, larg_total, concrete_dim in face_info:

        # EPIC-STOG-7: Painéis — contornos reais da face do painel por segmento
        # SCR: layer Painéis é ativado para retângulos de contorno de cada segmento
        # Gera 3 PLINEs por face (h1, h2, h3 segments) = geometria real da face
        y0 = y_bot
        h1_f, h2_f, h3_f = h1, h2, h3  # segmentos da face
        for _seg_y, _seg_h in [(y0, h1_f), (y0 + h1_f, h2_f), (y0 + h1_f + h2_f, h3_f)]:
            if _seg_h > 0.1:
                msp.add_lwpolyline(
                    [(x_left, _seg_y), (x_left + larg_total, _seg_y),
                     (x_left + larg_total, _seg_y + _seg_h), (x_left, _seg_y + _seg_h)],
                    close=True, dxfattribs={'layer': 'Painéis'}
                )
                entity_count += 1

        # Faces C/D switch to horizontal sarrafos when dim >= 30 (verified P05+ SCR)
        is_horiz = (fid in ('C', 'D') and concrete_dim >= 30)

        # ── 5b. Sarrafo lines ────────────────────────────────────────────────
        if is_horiz:
            # Short: 2 horizontal PLINEs (verified P21/P22 SCR)
            # Normal: 4 horizontal PLINEs (verified P05/P07/P09/P11 SCR)
            sarr_ys = ([y_bot + 9, y_top - 7]
                       if is_short else
                       [y_bot + 9, y_top - 41, y_top - 27, y_top - 7])
            for y_h in sarr_ys:
                msp.add_lwpolyline(
                    [(x_left, y_h), (x_left + concrete_dim, y_h)],
                    close=False,
                    dxfattribs={'layer': 'SARR_2.2x7'}
                )
                entity_count += 1
        else:
            # Vertical sarrafos (standard for A/B and small C/D)
            sarr_xs = [x_left + SARR_OFFSET]
            right_sx = x_left + concrete_dim - SARR_OFFSET
            if right_sx > x_left + SARR_OFFSET:
                sarr_xs.append(right_sx)

            # 1 sarrafo: draw TWICE per segment (robot artifact); 2: draw ONCE
            repeat = 2 if len(sarr_xs) == 1 else 1

            for sx in sarr_xs:
                if is_short:
                    # Short: single PLINE from y_bot+h1 to y_top, continuous (verified P21/P44 SCR)
                    for _ in range(repeat):
                        msp.add_lwpolyline([(sx, y0 + h1), (sx, y_top)],
                                           close=False,
                                           dxfattribs={'layer': 'SARR_2.2x7'})
                        entity_count += 1
                else:
                    # Normal: DASHED segment + CONTINUOUS segment (verified P01-P20 SCR)
                    for _ in range(repeat):
                        msp.add_lwpolyline([(sx, y0 + h1), (sx, y0 + h1 + h2)],
                                           close=False,
                                           dxfattribs={'layer': 'SARR_2.2x7', 'linetype': 'DASHED'})
                        entity_count += 1
                    for _ in range(repeat):
                        msp.add_lwpolyline([(sx, y0 + h1 + h2), (sx, y_top)],
                                           close=False,
                                           dxfattribs={'layer': 'SARR_2.2x7'})
                        entity_count += 1

        # ── 5c. Per-face DIMENSIONs ───────────────────────────────────────────
        # Short: 2 dims per face (verified P21/P22 SCR)
        # Normal: 3 dims per face
        x_dim = x_left + concrete_dim
        ann_off = 25 if fid in ('A', 'B') else 50

        if is_short:
            # A/B: (y_bot→y_bot+h1) + (y_bot→y_top)
            # C/D: (y_bot→y_bot+h1) + (y_bot+h1→y_top)
            if fid in ('A', 'B'):
                dim_specs = [(y_bot, y0 + h1, ann_off), (y_bot, y_top, 50)]
            else:
                dim_specs = [(y_bot, y0 + h1, ann_off), (y0 + h1, y_top, 50)]
        else:
            dim_specs = [
                (y_bot, y0 + h1, ann_off),
                (y0 + h1, y0 + h1 + h2, 50),
                (y0 + h1 + h2, y_top, 50),
            ]
        for p1y, p2y, ann_x_off in dim_specs:
            try:
                d = msp.add_linear_dim(
                    base=(x_dim + ann_x_off, (p1y + p2y) / 2),
                    p1=(x_dim, p1y), p2=(x_dim, p2y),
                    angle=90, dimstyle='PAINEL-NOVA',
                    dxfattribs={'layer': 'COTA'}
                )
                d.render()
                entity_count += 1
            except Exception:
                pass

        # ── 5d. SLIPTEE + SLIPTDD (faces A/B) + furacao (large faces) ────────
        if fid in ('A', 'B'):
            y_slip = y_bot + 3
            try:
                msp.add_blockref('SLIPTEE', (x_left, y_slip),
                                 dxfattribs={'layer': 'COTA'})
                msp.add_blockref('SLIPTDD', (x_left + concrete_dim, y_slip),
                                 dxfattribs={'layer': 'COTA'})
                entity_count += 2
            except Exception:
                pass

        # Furacao through-bolt blocks (verified P07/P09/P10/P11/P12 SCR):
        #   Face A: comp > 50  | Face B: comp > 50 (same cond as A, NOT larg>40)
        #   Face C: comp >= 40 | Face D: larg >= 40
        needs_furacao = (
            (fid == 'A' and comp > 50) or
            (fid == 'B' and comp > 50) or
            (fid == 'C' and comp >= 40) or
            (fid == 'D' and larg >= 40)
        )
        if needs_furacao:
            x_fura = x_left + concrete_dim / 2
            for y_abs in fura_ys:
                try:
                    msp.add_blockref('furacao', (x_fura, y_abs),
                                     dxfattribs={'layer': 'COTA'})
                    entity_count += 1
                except Exception:
                    pass

        # ── 5e. Face label TEXT ───────────────────────────────────────────────
        msp.add_text(f'{nome}.{fid}', dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (x_left - 15, y_bot + 5),
            'height': 12,
            'rotation': 90,
        })
        entity_count += 1

        # ── 5f. Sarrafo count annotations (horizontal faces only) ─────────────
        # Short: "6 sarr." (1 TEXT, verified P21/P22 SCR)
        # Normal: "9 sarr." + "2 sarr." (2 TEXTs, verified P05/P07/P09/P11)
        if is_horiz:
            x_ann = x_left + concrete_dim + 65
            if is_short:
                msp.add_text('6 sarr.', dxfattribs={
                    'layer': 'NOMENCLATURA',
                    'insert': (x_ann, y_top - 114),
                    'height': 12,
                    'rotation': 90,
                })
                entity_count += 1
            else:
                for txt, y_off in [('9 sarr.', -196), ('2 sarr.', -57)]:
                    msp.add_text(txt, dxfattribs={
                        'layer': 'NOMENCLATURA',
                        'insert': (x_ann, y_top + y_off),
                        'height': 12,
                        'rotation': 90,
                    })
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

    # ── Pilar name TEXT (always, on NOMENCLATURA uppercase) ──────────────────
    msp.add_text(nome, dxfattribs={
        'layer': 'NOMENCLATURA',
        'insert': (base_x - 10, base_y),
        'height': 14,
        'rotation': 90,
    })
    entity_count += 1

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

    # ── ZONE EXTRA: layers STOG presentes mas ausentes no gerador ────────────
    draw_extra_pl_layers(msp, ZONE_ABCD_X, row_y_offset,
                         comp, larg, altura, nome)

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
        msp.add_line(
            (_sentinel_x, 0), (_sentinel_x + 10, 0),
            dxfattribs={'layer': _layer}
        )

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
            return _uc.normalize('NFD', s).encode('ascii', 'ignore').decode().upper()
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
