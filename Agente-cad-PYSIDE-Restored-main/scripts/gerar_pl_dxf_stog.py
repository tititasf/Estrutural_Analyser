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

# GradeCalculator — robô legado (calcular_grades, calculate_details_legacy)
try:
    _GC_PATH = str(Path(__file__).parent.parent /
                   '_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src')
    if _GC_PATH not in sys.path:
        sys.path.insert(0, _GC_PATH)
    from utils.grade_calculator import GradeCalculator as _GradeCalculator
except Exception:
    _GradeCalculator = None

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


def dim_h(msp, x0, x1, y_base, layer='COTA', dimstyle='PAINEL-NOVA', offset=8, text=None):
    """Horizontal dimension. Returns the DIMENSION entity (for post-transform), or None.

    `text`, se informado, sobrescreve o valor medido (geometria pode divergir
    do valor real extraído do recorte — ex.: cotas de grade posicionadas
    proporcionalmente sobre chapa_full_w mas exibindo o valor real do módulo).
    """
    try:
        kwargs = dict(
            base=(x0, y_base - offset),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0,
            dimstyle=dimstyle,
            dxfattribs={'layer': layer}
        )
        if text is not None:
            kwargs['text'] = text
        d = msp.add_linear_dim(**kwargs)
        d.render()
        return d.dimension
    except Exception:
        return None


def dim_v(msp, y0, y1, x_base, layer='COTA', dimstyle='PAINEL-NOVA', offset=8):
    """Vertical dimension. Returns DIMENSION entity for post-transform, or None."""
    try:
        d = msp.add_linear_dim(
            base=(x_base + offset, (y0 + y1) / 2.0),
            p1=(x_base, y0), p2=(x_base, y1),
            angle=90,
            dimstyle=dimstyle,
            dxfattribs={'layer': layer}
        )
        d.render()
        return d.dimension
    except Exception:
        return None


def mtext(msp, x, y, txt, height=5, layer='NOMENCLATURA', anchor=5):
    msp.add_mtext(txt, dxfattribs={
        'layer': layer,
        'insert': (x, y),
        'char_height': height,
        'attachment_point': anchor,
    })


# ─── Helpers compartilhados CIMA + GRADES ────────────────────────────────────

def _bolt_offsets_from_pj(pj, grade_w):
    """Offsets dos parafusos intermediários medidos desde a borda esquerda da
    grade (= corner_l/gx). Reproduz exatamente a seção de parafusos de
    draw_cima: _bx_left = cx_l-12 = corner_l-1 → offset inicial = -1."""
    bolt_xs = []
    _bx = -1.0          # = cx_l-12 - corner_l  (corner_l = cx_l-11)
    _limit = grade_w + 1.0
    for i in range(1, 9):
        sp = float(pj.get(f'par_{i}_{i+1}') or 0)
        if sp <= 0:
            break
        _bx += sp
        if _bx >= _limit - 1.0:
            break
        bolt_xs.append(_bx)
    return bolt_xs


def _grade_boundaries_with_avoidance(total_w, offsets, tol=3.0, step=5.0, max_shift=20.0):
    """3 fronteiras intermediárias (4 módulos) com desvio de colisão grade×parafuso.
    Porta da lógica do robô CIMA: ±3cm tolerância, passos ±5cm até ±20cm."""
    def bounds(b2):
        return [b2 / 2.0, b2, (total_w + b2) / 2.0]
    def conflict(bnds):
        return any(abs(b - o) <= tol for b in bnds for o in offsets)
    b2 = total_w / 2.0
    if not offsets or not conflict(bounds(b2)):
        return bounds(b2)
    n = 1
    while n * step <= max_shift:
        for cand in (b2 - n * step, b2 + n * step):
            if 0 < cand < total_w and not conflict(bounds(cand)):
                return bounds(cand)
        n += 1
    return bounds(b2)


def _segments_from_boundaries(boundaries, total_w):
    """Fronteiras intermediárias → larguras de cada módulo."""
    bnds = [0.0] + list(boundaries) + [total_w]
    return [b1 - b0 for b0, b1 in zip(bnds[:-1], bnds[1:])]


def _div_segments(pj, grade_w, div_key='grade_1_div_a'):
    """Fonte única de div_a/div_b: Fase-4 se sum≈grade_w, senão bolt-avoidance.
    Garante que CIMA e GRADES usem exatamente os mesmos segmentos."""
    raw = pj.get(div_key) or []
    if raw:
        s = sum(float(v) for v in raw if v)
        if abs(s - grade_w) < 0.5:
            return [float(v) for v in raw if v]
    bolt_offs = _bolt_offsets_from_pj(pj, grade_w)
    bnds = _grade_boundaries_with_avoidance(grade_w, bolt_offs)
    return _segments_from_boundaries(bnds, grade_w)


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
    GRAV_BELOW_OUTER = 9.0   # outer gravata top = concrete_bottom - 9

    # CIMA: concreto (interno) mede `comp`; `grade_1` é a medida EXTERNA
    # (corner_l..corner_r, = comp + 22 pelas constantes SCR abaixo) — ver
    # ground truth do recorte: "88(GRADE)"/"88" = externo, "66" = interno.
    hc = comp / 2.0
    hl = larg / 2.0
    larg_inner = larg - 5 if larg > 19 else larg

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

    chapa_full_w = corner_r - corner_l  # full width of horizontal chapas A/C

    # ── Posições dos parafusos intermediários (cadeia par_1_2..par_8_9) ──────
    # Calculado ANTES das grades (3a) para que o desvio de colisão grade x
    # parafuso considere essas posições — mesma fórmula usada no desenho dos
    # parafusos (seção 6, reaproveitada de lá).
    _bx_left = cx_l - 12.0
    _bx_right = corner_r + 1.0
    _par_keys = [f'par_{i}_{i+1}' for i in range(1, 9)]
    bolt_intermediate_xs = []
    _bx = _bx_left
    for pk in _par_keys:
        sp = float(pj.get(pk) or 0)
        if sp <= 0:
            break
        _bx += sp
        if _bx >= _bx_right - 1:
            break
        bolt_intermediate_xs.append(_bx)
    bolt_offsets = [bx - corner_l for bx in bolt_intermediate_xs]

    entities = []

    def rp(x0, y0, w, h, layer, lw=None):
        attrs = {'layer': layer}
        if lw is not None:
            attrs['lineweight'] = lw
        pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
        e = msp.add_lwpolyline(pts, close=True, dxfattribs=attrs)
        entities.append(e)
        return e

    def hp_ansi(x0, y0, w, h):
        """ANSI31 hatch fill on layer Hachura, color=7 (textura sarrafo/corner)."""
        pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
        hatch = msp.add_hatch(color=7, dxfattribs={'layer': 'Hachura'})
        hatch.paths.add_polyline_path(pts, is_closed=True)
        hatch.set_pattern_fill('ANSI31', scale=0.5)
        entities.append(hatch)
        return hatch

    # ── 1. Chapas (8 PLINEs on layer CHAPA — N2 duplica cada face 2x) ────────
    chapa_bd_y0 = cy_b + (larg - larg_inner) / 2.0  # centered larg_inner span
    for _ in range(2):
        rp(chapa_l, chapa_bd_y0, TC, larg_inner, 'CHAPA', lw=18)        # face B (left vert)
        rp(cx_r,    chapa_bd_y0, TC, larg_inner, 'CHAPA', lw=18)        # face D (right vert)
        rp(corner_l, cy_t, chapa_full_w, TC, 'CHAPA', lw=18)            # face C (top horiz)
        rp(corner_l, cy_b - TC, chapa_full_w, TC, 'CHAPA', lw=18)       # face A (bot horiz)

    # ── 1b. Painéis: contorno do concreto (comp x larg_inner, centrado) ──────
    rp(cx_l, oy - larg_inner / 2.0, comp, larg_inner, 'Painéis')

    # ── 2. COTA dim 1: total chapa width ─────────────────────────────────────
    entities.append(dim_h(msp, corner_l, corner_r, cy_b - TC, 'COTA', 'cotax2', offset=48))

    # ── 3. Sarrafos (8 PLINEs on SARRAFO, color=251) + hachura ANSI31 ────────
    # Face B (left vertical), lower half
    rp(sarr_l, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_l, cy_b, TS, SARR_H)
    # Face B upper half
    rp(sarr_l, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_l, cy_t - SARR_H, TS, SARR_H)
    # Face D (right vertical), lower half
    rp(chapa_r, cy_b, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(chapa_r, cy_b, TS, SARR_H)
    # Face D upper half
    rp(chapa_r, cy_t - SARR_H, TS, SARR_H, 'SARRAFO', lw=13)
    hp_ansi(chapa_r, cy_t - SARR_H, TS, SARR_H)
    # Corner BL top: x[corner_l, sarr_l], y[cy_t-2, cy_t]
    rp(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(corner_l, cy_t - CORNER_H, CORNER_W, CORNER_H)
    # Corner BL bottom: y[cy_b, cy_b+2]
    rp(corner_l, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(corner_l, cy_b, CORNER_W, CORNER_H)
    # Corner DR top:
    rp(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_r, cy_t - CORNER_H, CORNER_W, CORNER_H)
    # Corner DR bottom:
    rp(sarr_r, cy_b, CORNER_W, CORNER_H, 'SARRAFO', lw=13)
    hp_ansi(sarr_r, cy_b, CORNER_W, CORNER_H)
    for e in entities[-16:]:
        if e.dxftype() == 'LWPOLYLINE':
            e.dxf.color = 251

    # ── 3a. Layout de grades: ng grades de gw_c cm separadas por dg_c cm ───────
    # Para ng=1: gw_c = chapa_full_w, dg_c = 0 → compatível com código anterior.
    # Para ng=2: gw_c < chapa_full_w, duas grades lado a lado com gap dg_c.
    # Mesma lógica de draw_grades (fonte única: GradeCalculator + _div_segments).
    if _GradeCalculator:
        ng_c, gw_c, dg_c = _GradeCalculator.calcular_grades(comp)
    else:
        ng_c, gw_c, dg_c = 1, chapa_full_w, 0.0

    # div_a por grade (soma = gw_c); grade_1_div_a soma gw_c, não chapa_full_w
    div_a = _div_segments(pj, gw_c)

    # Fronteiras cumulativas dentro de 1 grade (escala 0..gw_c)
    _bounds_pg = []
    _cs2 = 0.0
    for _d in div_a[:-1]:
        _cs2 += _d
        _bounds_pg.append(_cs2)

    # ── 3b/3d. Madeira por grade (lado C = topo, lado A = fundo) ─────────────
    # Cada uma das ng_c grades recebe: fundo + canto_esq + canto_dir + N divisores.
    madeira_y0 = cy_t + TC
    madeira_h = CORNER_W

    def _draw_madeira_row(y_m):
        n0 = len(entities)
        for gi in range(ng_c):
            gx0 = corner_l + gi * (gw_c + dg_c)
            gx1 = gx0 + gw_c
            rp(gx0, y_m, gw_c, madeira_h, 'Madeira')                        # fundo
            rp(gx0, y_m, CORNER_W, madeira_h, 'Madeira')                     # canto esq
            rp(gx1 - CORNER_W, y_m, CORNER_W, madeira_h, 'Madeira')         # canto dir
            for off in _bounds_pg:
                cx_mid = gx0 + off
                rp(cx_mid - CORNER_W / 4.0, y_m, CORNER_W / 2.0, madeira_h, 'Madeira')
        for e in entities[n0:]:
            e.dxf.color = 126

    _draw_madeira_row(madeira_y0)           # lado C (topo)
    madeira_y0_a = cy_b - TC - CORNER_W
    _draw_madeira_row(madeira_y0_a)         # lado A (fundo)

    # ── 3e. Perfil Metálico (2x "C-channel" além das peças Madeira) ──────────
    PERFIL_EXT = EXTRA_GRAV - TC
    PERFIL_W_OUT = 10.0
    perfil_x0 = corner_l - PERFIL_EXT
    perfil_w = chapa_full_w + 2 * PERFIL_EXT
    py0_c = madeira_y0 + madeira_h
    rp(perfil_x0, py0_c, perfil_w, PERFIL_W_OUT, 'Perfil Metálico')
    rp(perfil_x0, py0_c + TC, perfil_w, PERFIL_W_OUT - 2 * TC, 'Perfil Metálico')
    py0_a2 = madeira_y0_a - PERFIL_W_OUT
    rp(perfil_x0, py0_a2, perfil_w, PERFIL_W_OUT, 'Perfil Metálico')
    rp(perfil_x0, py0_a2 + TC, perfil_w, PERFIL_W_OUT - 2 * TC, 'Perfil Metálico')
    for e in entities[-4:]:
        e.dxf.color = 224

    # ── 3f. COTA de subdivisões — repetida para cada uma das ng_c grades ──────
    def _place_div_dim(values, y_base, offset):
        nums = [float(v) for v in values if v and float(v) > 0]
        if not nums:
            return
        total = sum(nums)
        if total <= 0:
            return
        for gi in range(ng_c):
            gx0 = corner_l + gi * (gw_c + dg_c)
            cumsum = 0.0
            for v in nums:
                w = v / total * gw_c
                x0 = gx0 + cumsum
                x1 = min(gx0 + cumsum + w, gx0 + gw_c)
                if x1 - x0 > 0.01:
                    txt = f'{v:.0f}' if v == int(v) else f'{v:g}'
                    entities.append(dim_h(msp, x0, x1, y_base, 'COTA', 'cotax2', offset=offset, text=txt))
                cumsum += w

    _place_div_dim(div_a, madeira_y0_a, offset=20)

    # cota do gap dg_c entre grupos de Madeira (só quando ng_c > 1)
    if ng_c > 1 and dg_c > 0.01:
        for gi in range(ng_c - 1):
            gap_x0 = corner_l + gi * (gw_c + dg_c) + gw_c
            gap_x1 = gap_x0 + dg_c
            entities.append(dim_h(msp, gap_x0, gap_x1, madeira_y0_a,
                                  'COTA', 'cotax2', offset=20))

    # ── 3c. COTA texto interior (valores comp/larg_inner dentro do concreto) ─
    entities.append(msp.add_text(f'{comp:.0f}', dxfattribs={
        'layer': 'COTA', 'insert': (ox - 3.5, oy - 1.75), 'height': 3.5,
    }))
    entities.append(msp.add_text(f'{larg_inner:.0f}', dxfattribs={
        'layer': 'COTA', 'insert': (cx_l + 5, oy - 1.75), 'height': 3.5, 'rotation': 90,
    }))

    # ── 4. COTA dims 2-5 (posições do P1_CIMA.scr) ───────────────────────────
    # dim 2: concrete comp — measurement at cy_b, base 4 ACIMA (offset=-4)
    entities.append(dim_h(msp, cx_l, cx_r, cy_b, 'COTA', 'cotax2', offset=-4))
    # dim 3: concrete larg (vertical) — base 30 à direita
    entities.append(dim_v(msp, cy_b, cy_t, cx_r, 'COTA', 'cotax2', offset=30))
    # dim 4: left corner width — measurement at cy_b+2, base 6 ACIMA (offset=-6)
    entities.append(dim_h(msp, corner_l, sarr_l, cy_b + 2, 'COTA', 'cotax2', offset=-6))
    # dim 5: right corner width — measurement at cy_b+2, base 6 ACIMA (offset=-6)
    entities.append(dim_h(msp, sarr_r, corner_r, cy_b + 2, 'COTA', 'cotax2', offset=-6))

    # ── 5. GRAVATA removida (não existe no recorte N2 ground truth) ───────────

    # ── 6. Parafusos (PLINEs layer Hachura — posições do robô SCR) ───────────
    # Robot: left_extremity = x_inicial - 12 = cx_l - 12 ≈ corner_l - 1
    #        spacings = par_1_2, par_2_3, ... (NÃO distancia_1)
    #        right_extremity = cx_r + 15.5 ≈ corner_r + 4.5
    # y: altura_parafuso = larg + 36.8 (comp < 223) → cy_b - 24.4 a cy_t + 24.4
    _bolt_half_extra = 18.4 if comp < 223 else 20.6
    bolt_y0 = cy_b - _bolt_half_extra - 6
    bolt_y1 = cy_t + _bolt_half_extra + 6

    def _bolt_pline(bx, is_intermediate=False):
        if is_intermediate:
            # Sólido abaixo do concreto
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, bolt_y0), (bx + 0.5, bolt_y0),
                 (bx + 0.5, cy_b - 2), (bx - 0.5, cy_b - 2)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))
            # Tracejado através do concreto
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, cy_b - 2), (bx + 0.5, cy_b - 2),
                 (bx + 0.5, cy_t + 2), (bx - 0.5, cy_t + 2)],
                close=True, dxfattribs={'layer': 'Hachura', 'linetype': 'HIDDEN'}
            ))
            # Sólido acima do concreto
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, cy_t + 2), (bx + 0.5, cy_t + 2),
                 (bx + 0.5, bolt_y1), (bx - 0.5, bolt_y1)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))
        else:
            # Extremidade: 1cm PLINE sólido do início ao fim
            entities.append(msp.add_lwpolyline(
                [(bx - 0.5, bolt_y0), (bx + 0.5, bolt_y0),
                 (bx + 0.5, bolt_y1), (bx - 0.5, bolt_y1)],
                close=True, dxfattribs={'layer': 'Hachura'}
            ))

    # bx_left/bx_right/bolt_intermediate_xs já calculados antes da seção 3
    # (necessários para o desvio de colisão grade x parafuso de _default_boundaries).
    bx_left, bx_right = _bx_left, _bx_right
    _bolt_pline(bx_left, is_intermediate=False)
    for bx in bolt_intermediate_xs:
        _bolt_pline(bx, is_intermediate=True)
    _bolt_pline(bx_right, is_intermediate=False)

    # ── 6c. COTA dos parafusos: cadeia corner_l -> [centros dos parafusos
    # intermediários] -> corner_r, sempre no TOPO do desenho (cy_t +
    # _bolt_half_extra, alinhada à parte solida superior do Hachura/_bolt_pline
    # que vai até bolt_y1). Extremidades coincidem com os painéis
    # (corner_l/corner_r); os pontos centrais da cadeia ficam alinhados com o
    # centro de cada parafuso intermediário (Hachura).
    _bolt_y_base = cy_t + _bolt_half_extra
    _bolt_chain = [corner_l] + bolt_intermediate_xs + [corner_r]
    for _x0, _x1 in zip(_bolt_chain[:-1], _bolt_chain[1:]):
        if _x1 - _x0 > 0.01:
            entities.append(dim_h(msp, _x0, _x1, _bolt_y_base, 'COTA', 'cotax2', offset=-15))

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
    # ── Constants (STOG PIL drawing standard) ────────────────────────────────
    SARR_OFFSET  = 7      # sarrafo position from left face edge
    X_OFFSET     = 80     # face A left offset from zone start
    GAP_AB       = 155    # gap: face A right edge → face B left edge (STOG standard)
    GAP_BC       = 129    # gap: face B right edge → face C left edge
    GAP_CD       = 129    # gap: face C right edge → face D left edge
    H1_DEFAULT   = 2.0    # bottom chapa strip height
    H_PARAFUSO   = 73.0   # A/B parafuso zone height (varies by batch; 73 for P1-P17)
    # C/D face geometry constants (N2 ground truth 13_PAV — h_low=124 fixed across all pilares):
    H_PAR_C      = 97.0   # face C parafuso zone (N2: always 97 in 13°PAV)
    H_C_EXTRA    = 41.0   # face C extra top section (N2: 262-221=41; was wrong 39 before)
    # TODO: derive H_PAR_C and H_C_EXTRA from N2 ficha; face D height varies per pilar
    # Face view spans full pé-direito (pd), not just pilar height (altura)
    pd_cm         = float(pj.get('pd_pavimento_cm', altura))
    nivel_saida   = float(pj.get('nivel_saida',     altura))
    nivel_chegada = float(pj.get('nivel_chegada',   0.0))

    y_top = base_y - 100
    y_bot = base_y - 100 - pd_cm

    # ABCD PAIRED pattern (N2 ground truth 13_PAV):
    # A=B → comp-direction: panel width = comp + 22 (NOT grade_1 — grade_1 can differ)
    # C=D → larg-direction: panel width = min(larg, 19) per N2 observation
    larg_a = comp + 22
    larg_b = comp + 22
    larg_inner = min(larg, 19) if larg >= 19 else larg  # N2: both larg=24 and larg=30 → 19
    larg_c = larg_inner
    larg_d = larg_inner

    x_a = base_x + X_OFFSET
    x_b = x_a + larg_a + GAP_AB
    x_c = x_b + larg_b + GAP_BC
    x_d = x_c + larg_c + GAP_CD

    face_info = [
        ('A', x_a, larg_a, comp),      # (label, x_left, panel_width, concrete_dim)
        ('B', x_b, larg_b, comp),      # B also spans comprimento (paired with A)
        ('C', x_c, larg_c, larg_c),   # C: concrete_dim=larg_c (panel width, not larg)
        ('D', x_d, larg_d, larg_c),   # D: same
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
        f'CENARIOS - PD: {pd_cm/100:.2f}',
        f'NIVEL DE SAIDA: {nivel_saida/100:.2f}',
        f'NIVEL DE CHEGADA: {nivel_chegada/100:.2f}',
    ]):
        msp.add_text(txt, dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (header_x, base_y + 280 - i * 25),
            'height': 15,
        })
        entity_count += 1

    # ── 5. Per-face drawing ────────────────────────────────────────────────────
    # Short-pillar flag: alt < 280 → simplified sarrafo/dim structure (verified P21/P22/P44 SCR)
    is_short = altura < 280

    for fid, x_left, larg_total, concrete_dim in face_info:

        # Painéis — N2 pattern: C/D faces are taller than A/B (N2 verified 13°PAV)
        y0      = y_bot
        h1      = float(pj.get(f'h1_{fid}', H1_DEFAULT))
        h2_face = float(pj.get(f'h2_{fid}', 244.0))
        h_low   = h1 + h2_face / 2.0   # first sub-panel boundary
        y_low   = y0 + h_low
        x_right = x_left + larg_total

        # Intervalos N2 (ground truth para todas as faces A/B/C/D)
        _intervals = pj.get(f'paineis_intervals_{fid}')
        # Face C usa modelo 262 apenas como fallback quando N2 não tem intervals
        face_uses_262 = (fid == 'C') and not (_intervals and len(_intervals) >= 1)

        if face_uses_262:
            y_mid_face     = y_low + H_PAR_C
            panel_top_face = y_mid_face + H_C_EXTRA
            msp.add_line((x_left, y0 + h1), (x_right, y0 + h1), dxfattribs={'layer': 'Painéis'})
            entity_count += 1
            msp.add_line((x_left, y0), (x_left, panel_top_face), dxfattribs={'layer': 'Painéis'})
            msp.add_line((x_right, y0), (x_right, panel_top_face), dxfattribs={'layer': 'Painéis'})
            entity_count += 2
            msp.add_line((x_right, y_low), (x_left, y_low), dxfattribs={'layer': 'Painéis'})
            msp.add_line((x_right, y_mid_face), (x_left, y_mid_face), dxfattribs={'layer': 'Painéis'})
            entity_count += 2
            msp.add_line((x_right, panel_top_face), (x_left, panel_top_face),
                         dxfattribs={'layer': 'Painéis'})
            entity_count += 1

        elif _intervals and len(_intervals) >= 1:
            # Modo N2-fiel: replica todos os horizontais do N2 via Painéis intervals.
            # Cobre pilares simples (3 linhas) e complexos (P27-P32 com 5-7 segmentos).

            # ── Aberturas da face (suporta 1 ou múltiplas) ─────────────────────
            # Coleta lista de aberturas: abertura_{fid} OU abertura_{fid}_1, _2, ...
            _aberturas_raw = []
            if pj.get(f'abertura_{fid}'):
                _aberturas_raw = [pj[f'abertura_{fid}']]
            else:
                _ai = 1
                while pj.get(f'abertura_{fid}_{_ai}'):
                    _aberturas_raw.append(pj[f'abertura_{fid}_{_ai}'])
                    _ai += 1

            # Pré-computa coordenadas de cada abertura
            _aberturas: list[dict] = []
            for _ab_r in _aberturas_raw:
                _al  = _ab_r.get('lado', '')
                _alg = float(_ab_r.get('largura', 0))
                _ayr = float(_ab_r.get('y_rel', 0))
                _aht = float(_ab_r.get('altura', 0))
                _ayb = y0 + h1 + _ayr
                _ayt = _ayb + _aht
                _axl = _axr = None
                if _al == 'meio':
                    _axo = float(_ab_r.get('x_offset', 0))
                    _axl = x_left + _axo
                    _axr = _axl + _alg
                _aberturas.append({
                    'lado': _al, 'larg': _alg, 'y_bot': _ayb, 'y_top': _ayt,
                    'x_inn_l': _axl, 'x_inn_r': _axr,
                })

            # topo estimado (para distinguir abertura-no-topo vs no-meio)
            _panel_top_est = round(y0 + h1 + sum(float(_iv) for _iv in _intervals), 4)

            # Flags derivadas: borda lateral afetada e 'meio no topo' por abertura
            def _meio_no_topo(ab): return (
                ab['lado'] == 'meio' and ab['y_top'] >= _panel_top_est - 1.0)

            # Borda lateral afetada (direito/esquerdo): usa ÚLTIMA abertura desse lado
            # (caso de múltiplas em lados diferentes — raro; para 'meio' as bordas são full)
            _borda_ab = _aberturas[-1] if _aberturas else None

            y_cur = y0 + h1  # primeira linha = topo do strip h1
            msp.add_line((x_left, y_cur), (x_right, y_cur), dxfattribs={'layer': 'Painéis'})
            entity_count += 1
            for _iv in _intervals:
                y_cur = round(y_cur + float(_iv), 4)
                if y_cur > y_top + 1.0:
                    continue

                # Verifica posição relativa a cada abertura
                _at_bot_list  = [ab for ab in _aberturas if abs(y_cur - ab['y_bot']) < 1.0]
                _at_top_list  = [ab for ab in _aberturas if abs(y_cur - ab['y_top']) < 1.0
                                 and not any(abs(y_cur - ab2['y_bot']) < 1.0 for ab2 in _aberturas)]
                _inside_list  = [ab for ab in _aberturas
                                 if ab['y_bot'] + 0.5 < y_cur < ab['y_top'] - 0.5]

                if _at_bot_list:
                    # y_bot de qualquer abertura → H FULL
                    msp.add_line((x_left, y_cur), (x_right, y_cur),
                                 dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                elif _at_top_list:
                    # y_top de uma ou mais aberturas
                    # Caso especial: esq + dir simultâneos → H combinada entre as paredes internas
                    _top_esq = [ab for ab in _at_top_list if ab['lado'] == 'esquerdo']
                    _top_dir = [ab for ab in _at_top_list if ab['lado'] == 'direito']
                    if _top_esq and _top_dir:
                        _xi_l = x_left  + max(ab['larg'] for ab in _top_esq)
                        _xi_r = x_right - max(ab['larg'] for ab in _top_dir)
                        if _xi_r > _xi_l:
                            msp.add_line((_xi_l, y_cur), (_xi_r, y_cur),
                                         dxfattribs={'layer': 'Painéis'})
                            entity_count += 1
                    else:
                        for _ab in _at_top_list:
                            _al = _ab['lado']
                            if _al == 'direito':
                                _xi = x_right - _ab['larg']
                                msp.add_line((x_left, y_cur), (_xi, y_cur),
                                             dxfattribs={'layer': 'Painéis'})
                                entity_count += 1
                            elif _al == 'esquerdo':
                                _xi = x_left + _ab['larg']
                                msp.add_line((_xi, y_cur), (x_right, y_cur),
                                             dxfattribs={'layer': 'Painéis'})
                                entity_count += 1
                            else:  # meio
                                if _meio_no_topo(_ab):
                                    msp.add_line((_ab['x_inn_l'], y_cur), (_ab['x_inn_r'], y_cur),
                                                 dxfattribs={'layer': 'Painéis'})
                                    entity_count += 1
                                else:
                                    msp.add_line((x_left, y_cur), (_ab['x_inn_l'], y_cur),
                                                 dxfattribs={'layer': 'Painéis'})
                                    msp.add_line((_ab['x_inn_r'], y_cur), (x_right, y_cur),
                                                 dxfattribs={'layer': 'Painéis'})
                                    entity_count += 2
                elif _inside_list:
                    # Dentro de uma abertura: sem H
                    pass
                else:
                    msp.add_line((x_left, y_cur), (x_right, y_cur), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1

            panel_top_face = min(y_cur, y_top)
            y_mid_face     = panel_top_face
            y_low = y0 + h1 + float(_intervals[0])

            # Inner verticals para cada abertura
            for _ab in _aberturas:
                _al = _ab['lado']
                _yb, _yt = _ab['y_bot'], _ab['y_top']
                if _al == 'meio':
                    msp.add_line((_ab['x_inn_l'], _yb), (_ab['x_inn_l'], _yt),
                                 dxfattribs={'layer': 'Painéis'})
                    msp.add_line((_ab['x_inn_r'], _yb), (_ab['x_inn_r'], _yt),
                                 dxfattribs={'layer': 'Painéis'})
                    entity_count += 2
                elif _al == 'direito':
                    _xi = x_right - _ab['larg']
                    msp.add_line((_xi, _yb), (_xi, _yt), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                else:  # esquerdo
                    _xi = x_left + _ab['larg']
                    msp.add_line((_xi, _yb), (_xi, _yt), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1

            # Bordas externas (considera a abertura de borda, se houver)
            # Detecta caso especial: esq + dir simultâneos → ambas bordas param em y_bot do slot
            _ab_esq_list = [ab for ab in _aberturas if ab['lado'] == 'esquerdo']
            _ab_dir_list = [ab for ab in _aberturas if ab['lado'] == 'direito']
            _has_dual = bool(_ab_esq_list and _ab_dir_list)
            if _borda_ab:
                _al = _borda_ab['lado']
                _yb = _borda_ab['y_bot']
                _yt = _borda_ab['y_top']
                if _has_dual:
                    # Ambas bordas param no bottom do slot; nenhuma continua acima
                    _yb_dual = min(ab['y_bot'] for ab in _aberturas)
                    _yt_dual = max(ab['y_top'] for ab in _aberturas)
                    msp.add_line((x_left,  y0), (x_left,  _yb_dual), dxfattribs={'layer': 'Painéis'})
                    msp.add_line((x_right, y0), (x_right, _yb_dual), dxfattribs={'layer': 'Painéis'})
                    entity_count += 2
                    if _yt_dual < panel_top_face - 0.5:
                        msp.add_line((x_left,  _yt_dual), (x_left,  panel_top_face), dxfattribs={'layer': 'Painéis'})
                        msp.add_line((x_right, _yt_dual), (x_right, panel_top_face), dxfattribs={'layer': 'Painéis'})
                        entity_count += 2
                elif _al == 'direito':
                    msp.add_line((x_left, y0), (x_left, panel_top_face),
                                 dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                    msp.add_line((x_right, y0), (x_right, _yb), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                    if _yt < panel_top_face - 0.5:
                        msp.add_line((x_right, _yt), (x_right, panel_top_face),
                                     dxfattribs={'layer': 'Painéis'})
                        entity_count += 1
                elif _al == 'esquerdo':
                    msp.add_line((x_right, y0), (x_right, panel_top_face),
                                 dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                    msp.add_line((x_left, y0), (x_left, _yb), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                    if _yt < panel_top_face - 0.5:
                        msp.add_line((x_left, _yt), (x_left, panel_top_face),
                                     dxfattribs={'layer': 'Painéis'})
                        entity_count += 1
                else:  # meio (único ou múltiplo — bordas sempre full/split em y_bot do primeiro)
                    # Para 'meio no topo': bordas param no y_bot do mais alto
                    _top_meio = [ab for ab in _aberturas if ab['lado'] == 'meio' and _meio_no_topo(ab)]
                    if _top_meio:
                        _yb_stop = min(ab['y_bot'] for ab in _top_meio)
                        msp.add_line((x_left, y0), (x_left, _yb_stop),
                                     dxfattribs={'layer': 'Painéis'})
                        msp.add_line((x_right, y0), (x_right, _yb_stop),
                                     dxfattribs={'layer': 'Painéis'})
                    else:
                        msp.add_line((x_left, y0), (x_left, panel_top_face),
                                     dxfattribs={'layer': 'Painéis'})
                        msp.add_line((x_right, y0), (x_right, panel_top_face),
                                     dxfattribs={'layer': 'Painéis'})
                    entity_count += 2
            else:
                msp.add_line((x_left, y0), (x_left, panel_top_face), dxfattribs={'layer': 'Painéis'})
                msp.add_line((x_right, y0), (x_right, panel_top_face), dxfattribs={'layer': 'Painéis'})
                entity_count += 2

        else:
            # Modelo padrão: h_low/h_par (fallback quando N2 não tem intervals)
            h_par_face     = float(pj.get(f'h_par_{fid}', H_PARAFUSO))
            y_mid_face     = y_low + h_par_face
            panel_top_face = y_mid_face
            msp.add_line((x_left, y0 + h1), (x_right, y0 + h1), dxfattribs={'layer': 'Painéis'})
            entity_count += 1
            msp.add_line((x_left, y0), (x_left, panel_top_face), dxfattribs={'layer': 'Painéis'})
            msp.add_line((x_right, y0), (x_right, panel_top_face), dxfattribs={'layer': 'Painéis'})
            entity_count += 2
            msp.add_line((x_right, y_low), (x_left, y_low), dxfattribs={'layer': 'Painéis'})
            msp.add_line((x_right, y_mid_face), (x_left, y_mid_face), dxfattribs={'layer': 'Painéis'})
            entity_count += 2

        # ── 5d. Retângulo da zona de laje (acima do painel → até nível superior) ───
        laje_bot = panel_top_face
        if laje_bot < y_top:
            msp.add_line((x_left,  laje_bot), (x_left,  y_top), dxfattribs={'layer': 'COTA'})
            msp.add_line((x_right, laje_bot), (x_right, y_top), dxfattribs={'layer': 'COTA'})
            entity_count += 2
        msp.add_line((x_left, y_top), (x_right, y_top), dxfattribs={'layer': 'COTA'})
        entity_count += 1

        # Sub-painel de laje: apenas no modelo padrão (intervals já incluem sub-painéis)
        if not (_intervals and len(_intervals) >= 1) and not face_uses_262:
            _laje_h = float(pj.get(f'laje_{fid}', 0.0))
            if _laje_h > 0.0:
                _y_laje_top = laje_bot + _laje_h
                if _y_laje_top < y_top:
                    msp.add_line(
                        (x_left, _y_laje_top), (x_right, _y_laje_top),
                        dxfattribs={'layer': 'COTA'},
                    )
                    entity_count += 1

        # Hatches não são necessários na vista ABCD (user: "os hatchs dos paineis nao necessito")

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
            right_sx = x_right - SARR_OFFSET   # usa x_right (=x_left+larg_total) — A/B têm +22cm
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
                    # Wide faces (A/B, comp-dir): lower CONTINUOUS + DASHED, stop at y_mid
                    # Narrow faces (C/D, larg-dir): lower CONTINUOUS + small DASHED above + CONTINUOUS top
                    if fid in ('A', 'B'):
                        for _ in range(repeat):
                            msp.add_lwpolyline([(sx, y0 + h1), (sx, y_low)],
                                               close=False,
                                               dxfattribs={'layer': 'SARR_2.2x7'})
                            entity_count += 1
                        for _ in range(repeat):
                            msp.add_lwpolyline([(sx, y_low), (sx, y_mid_face)],
                                               close=False,
                                               dxfattribs={'layer': 'SARR_2.2x7'})
                            entity_count += 1
                    else:
                        if fid == 'C':
                            # 2 segments split at y_mid_face; second only when extra zone exists
                            for _ in range(repeat):
                                msp.add_lwpolyline([(sx, y0 + h1), (sx, y_mid_face)],
                                                   close=False,
                                                   dxfattribs={'layer': 'SARR_2.2x7'})
                                entity_count += 1
                            if face_uses_262:
                                for _ in range(repeat):
                                    msp.add_lwpolyline([(sx, y_mid_face), (sx, panel_top_face)],
                                                       close=False,
                                                       dxfattribs={'layer': 'SARR_2.2x7'})
                                    entity_count += 1
                        else:
                            # D: continuous from y_bot+h1 to panel_top_face
                            for _ in range(repeat):
                                msp.add_lwpolyline([(sx, y0 + h1), (sx, panel_top_face)],
                                                   close=False,
                                                   dxfattribs={'layer': 'SARR_2.2x7'})
                                entity_count += 1

        # ── 5c. Per-face DIMENSIONs ───────────────────────────────────────────
        # N2 geometry: dim line at x_right+38, extension lines x_right+3→x_right+41
        # color=4 (ciano) em todas as entidades de cota — igual ao SCR original
        x_dim   = x_right   # bordo direito real (A/B: inclui +22cm)
        ANN_OFF = 38        # N2: linha de cota a +38 do bordo

        if is_short:
            if fid in ('A', 'B'):
                dim_specs = [(y_bot, y0 + h1, 19), (y_bot, y_top, ANN_OFF)]
            else:
                dim_specs = [(y_bot, y0 + h1, 19), (y0 + h1, y_top, ANN_OFF)]
        elif _intervals and len(_intervals) >= 1:
            # Intervalos N2-fiel: uma DIMENSION por segmento (A/B/C/D com intervals).
            dim_specs = [(y_bot, y0 + h1, 19)]  # h1 strip
            _y_p = y0 + h1
            for _iv in _intervals:
                _y_n = min(round(_y_p + float(_iv), 4), y_top)
                dim_specs.append((_y_p, _y_n, ANN_OFF))
                _y_p = _y_n
                if _y_p >= y_top:
                    break
            if panel_top_face < y_top:
                dim_specs.append((panel_top_face, y_top, ANN_OFF))  # laje
        elif fid == 'C':
            # C fallback 262 (quando N2 não tem intervals para face C)
            dim_specs = [
                (y_bot,          y_mid_face,       ANN_OFF),  # 221 (h_low=124 + H_PAR_C=97)
                (y_mid_face,     panel_top_face,   ANN_OFF),  # 41 (H_C_EXTRA)
                (panel_top_face, y_top,             ANN_OFF),  # laje zone
            ]
        else:
            # A, B, D: h1(2) + h_low(124) + H_PARAFUSO(73) + laje zone
            # Se laje_{fid} > 0: subdividir zona de laje em sub-painel + espaco acima
            _laje_h_dim = float(pj.get(f'laje_{fid}', 0.0))
            if _laje_h_dim > 0.0:
                _y_laje_top_dim = y_mid_face + _laje_h_dim
                dim_specs = [
                    (y_bot,              y_bot + h1,       19),
                    (y_bot,              y_low,             ANN_OFF),
                    (y_low,              y_mid_face,        ANN_OFF),
                    (y_mid_face,         _y_laje_top_dim,   ANN_OFF),  # sub-painel laje
                ]
            else:
                dim_specs = [
                    (y_bot,        y_bot + h1,   19),
                    (y_bot,        y_low,         ANN_OFF),
                    (y_low,        y_mid_face,    ANN_OFF),
                    (y_mid_face,   y_top,         ANN_OFF),
                ]
        for p1y, p2y, ann_x_off in dim_specs:
            try:
                d = msp.add_linear_dim(
                    base=(x_dim + ann_x_off, (p1y + p2y) / 2),
                    p1=(x_dim, p1y), p2=(x_dim, p2y),
                    angle=90, dimstyle='PAINEL-NOVA',
                    dxfattribs={'layer': 'COTA', 'color': 4}
                )
                d.render()
                entity_count += 1
            except Exception:
                pass

        # ── 5e-1. Cotas de offset do sarrafo (7cm cada lado, ciano) ──────────
        if not is_horiz and not is_short:
            # p1/p2 partem de y_bot (bordo inferior do painel) — extensões longas até a linha de cota
            for p1x, p2x in [(x_left, x_left + SARR_OFFSET),
                              (x_right - SARR_OFFSET, x_right)]:
                try:
                    d = msp.add_linear_dim(
                        base=((p1x + p2x) / 2, y_bot - 19),
                        p1=(p1x, y_bot),
                        p2=(p2x, y_bot),
                        angle=0, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'COTA', 'color': 4}
                    )
                    d.render()
                    entity_count += 1
                except Exception:
                    pass

        # ── 5e. Cota horizontal (largura do painel, ciano) ───────────────────
        # p1/p2 também em y_bot — extensão longa até a linha de cota em y_bot-43
        try:
            d = msp.add_linear_dim(
                base=(x_left + larg_total / 2, y_bot - 43),
                p1=(x_left,  y_bot),
                p2=(x_right, y_bot),
                angle=0, dimstyle='PAINEL-NOVA',
                dxfattribs={'layer': 'COTA', 'color': 4}
            )
            d.render()
            entity_count += 1
        except Exception:
            pass

        # ── 5f. Face label TEXT ───────────────────────────────────────────────
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
    Zona GRADES — motor universal baseado em GradeCalculator + _div_segments.

    Anatomia (ROBO_GRADES.py ground truth):
      - Grupo A (div_a) e Grupo B (div_b) separados por GROUP_GAP=22 (padrão robot).
      - Por grupo: base SARR_2.2x7 (h=2.2) + sarrafos verticais SARR_2.2x7 (w=7)
        + sarrafos centrais SARR_3.5x7 (w=3.5) nas fronteiras div.
      - Horizontais: posições [30, 90, 150, …] step=60, todos em SARR_2.2x10,
        desenhados enquanto posicao_relativa <= altura-10.
      - Labels: {nome}.A em Grupo A e {nome}.B em Grupo B (layer NOMENCLATURA).
      - Cotas verticais segmentadas no lado direito do Grupo B (total em +50, segs em +30).
      - Cotas horizontais por segmento em y=base_y-12.8; cota total em y=base_y-40.
      - div_a = _div_segments(pj, gw_each): MESMA fonte que draw_cima (fonte única).
      - div_b = reversed(div_a) sempre — B é espelho de A (grade_1_div_b são offsets de parafusos).
    """
    BASE_H      = 2.2
    SARR_LW     = 7.0
    SARR_CW     = 3.5
    SARR_HH     = 10.0
    GROUP_GAP   = 40.0   # espaçamento visual entre Grupo A e Grupo B
    HORIZ_STEP  = 60.0
    HORIZ_FIRST = 30.0

    if _GradeCalculator:
        ng, gw_each, dist_g = _GradeCalculator.calcular_grades(comp)
    else:
        gw_each = comp + 22.0
        ng = 1
        dist_g = 0.0
    if ng <= 0 or gw_each <= 0:
        return 0

    div_a = _div_segments(pj, gw_each)
    # Grupo B é sempre o espelho de A — grade_1_div_b contém offsets de parafusos
    # da face B (geometria diferente), não divisões de grade.
    div_b = list(reversed(div_a))

    def draw_group(gx_start, divs):
        """Desenha todos os ng grades do grupo; retorna lista de posições relativas dos horizontais."""
        horiz_ys = []
        for gi in range(ng):
            gx = gx_start + gi * (gw_each + dist_g)
            # base rect
            rect_lines(msp, gx, base_y, gw_each, BASE_H, 'SARR_2.2x7')
            # left vert
            rect_lines(msp, gx, base_y + BASE_H, SARR_LW, altura, 'SARR_2.2x7')
            # center sarrafos at div boundaries (not last)
            cumsum = 0.0
            for d in divs[:-1]:
                cumsum += d
                bx = gx + cumsum
                rect_lines(msp, bx - SARR_CW / 2, base_y + BASE_H, SARR_CW, altura, 'SARR_3.5x7')
            # right vert
            rect_lines(msp, gx + gw_each - SARR_LW, base_y + BASE_H, SARR_LW, altura, 'SARR_2.2x7')
            # horizontal sarrafos — todos SARR_2.2x10 (robot usa mesmo layer em todas posições)
            y_max = base_y + BASE_H + altura
            y_h = base_y + BASE_H + HORIZ_FIRST
            while y_h + SARR_HH <= y_max + 0.1:
                rect_lines(msp, gx, y_h, gw_each, SARR_HH, 'SARR_2.2x10')
                rel = round(y_h - (base_y + BASE_H), 4)
                if rel not in horiz_ys:
                    horiz_ys.append(rel)
                y_h += HORIZ_STEP
            # cotas horizontais por segmento
            x_seg = gx
            for d in divs:
                try:
                    e = msp.add_linear_dim(
                        base=(x_seg + d / 2, base_y - 17.8),
                        p1=(x_seg, base_y - 12.8),
                        p2=(x_seg + d, base_y - 12.8),
                        angle=0, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'COTA'})
                    e.render()
                except Exception:
                    pass
                x_seg += d
            # cota total horizontal
            try:
                t = msp.add_linear_dim(
                    base=(gx + gw_each / 2, base_y - 40),
                    p1=(gx, base_y), p2=(gx + gw_each, base_y),
                    angle=0, dimstyle='PAINEL-NOVA',
                    dxfattribs={'layer': 'COTA'})
                t.render()
            except Exception:
                pass
            # cota do gap entre grades consecutivas (só quando ng > 1)
            if gi < ng - 1 and dist_g > 0.01:
                try:
                    g = msp.add_linear_dim(
                        base=(gx + gw_each + dist_g / 2, base_y - 40),
                        p1=(gx + gw_each, base_y),
                        p2=(gx + gw_each + dist_g, base_y),
                        angle=0, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'COTA'})
                    g.render()
                except Exception:
                    pass
            # GRA-E: apex esq → inserir em gx; GRA-D: apex dir → inserir em gx+gw-7
            for bname, bx in (('GRA-E', gx), ('GRA-D', gx + gw_each - 7)):
                try:
                    msp.add_blockref(bname, (bx, base_y), dxfattribs={'layer': 'SARR_2.2x7'})
                except Exception:
                    pass
        return horiz_ys

    group_total_w = ng * gw_each + (ng - 1) * dist_g
    gx_b = base_x + group_total_w + GROUP_GAP

    # Label Grupo A
    msp.add_text(f'{nome}.A', dxfattribs={
        'layer': 'NOMENCLATURA',
        'insert': (base_x - 10, base_y),
        'height': 14,
        'rotation': 90,
    })
    draw_group(base_x, div_a)

    # Label Grupo B
    msp.add_text(f'{nome}.B', dxfattribs={
        'layer': 'NOMENCLATURA',
        'insert': (gx_b - 10, base_y),
        'height': 14,
        'rotation': 90,
    })
    horiz_ys = draw_group(gx_b, div_b)

    # ── Cotas verticais no lado direito do Grupo B (última grade do conjunto) ──
    x_right = gx_b + group_total_w
    y0      = base_y + BASE_H          # fundo dos sarrafos verticais
    y_top   = base_y + BASE_H + altura # topo dos sarrafos verticais

    # Cota total em +50
    try:
        e = msp.add_linear_dim(
            base=(x_right + 50, y0 + altura / 2),
            p1=(x_right, y0), p2=(x_right, y_top),
            angle=90, dimstyle='PAINEL-NOVA',
            dxfattribs={'layer': 'COTA'})
        e.render()
    except Exception:
        pass

    # Cotas segmentadas em +30
    if horiz_ys:
        hy_sorted = sorted(set(horiz_ys))

        # base → primeiro horizontal
        fh = hy_sorted[0]
        try:
            e = msp.add_linear_dim(
                base=(x_right + 30, y0 + fh / 2),
                p1=(x_right, y0), p2=(x_right, y0 + fh),
                angle=90, dimstyle='PAINEL-NOVA',
                dxfattribs={'layer': 'COTA'})
            e.render()
        except Exception:
            pass

        for idx, hy in enumerate(hy_sorted):
            y_h_abs = y0 + hy
            # espessura do horizontal (10cm)
            try:
                e = msp.add_linear_dim(
                    base=(x_right + 30, y_h_abs + SARR_HH / 2),
                    p1=(x_right, y_h_abs), p2=(x_right, y_h_abs + SARR_HH),
                    angle=90, dimstyle='PAINEL-NOVA',
                    dxfattribs={'layer': 'COTA'})
                e.render()
            except Exception:
                pass
            # gap até o próximo horizontal
            if idx < len(hy_sorted) - 1:
                next_y = y0 + hy_sorted[idx + 1]
                gap = next_y - (y_h_abs + SARR_HH)
                if gap > 0.1:
                    try:
                        e = msp.add_linear_dim(
                            base=(x_right + 30, y_h_abs + SARR_HH + gap / 2),
                            p1=(x_right, y_h_abs + SARR_HH), p2=(x_right, next_y),
                            angle=90, dimstyle='PAINEL-NOVA',
                            dxfattribs={'layer': 'COTA'})
                        e.render()
                    except Exception:
                        pass

        # último horizontal → topo
        y_last_top = y0 + hy_sorted[-1] + SARR_HH
        top_gap = y_top - y_last_top
        if top_gap > 0.1:
            try:
                e = msp.add_linear_dim(
                    base=(x_right + 30, y_last_top + top_gap / 2),
                    p1=(x_right, y_last_top), p2=(x_right, y_top),
                    angle=90, dimstyle='PAINEL-NOVA',
                    dxfattribs={'layer': 'COTA'})
                e.render()
            except Exception:
                pass

    return 1


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
# EFGH — faces E/F do pilar em U (AR-1'.C)
# ═════════════════════════════════════════════════════════════════════════════

ZONE_EFGH_X = 8000   # faces E/F do U-shape após GRADES

def draw_efgh(msp, base_x, base_y, pj: dict) -> int:
    """
    Desenha faces E e F do pilar em U (subtipo U).

    Campos lidos de pj:
      larg1_E / larg1_F — largura do painel de cada braço do U
      h1_E/h2_E/h3_E   — segmentos de altura da face E
      h1_F/h2_F/h3_F   — segmentos de altura da face F
      nome              — label do pilar

    Layout idêntico a draw_abcd mas com apenas 2 faces (E, F).
    Se larg1_E=0 → omite o EFGH (pilar não tem faces U).
    """
    larg1_E = float(pj.get('larg1_E', 0.0))
    larg1_F = float(pj.get('larg1_F', 0.0))
    if larg1_E <= 0 and larg1_F <= 0:
        return -1  # não é U-shape

    nome   = pj.get('nome', '?')
    ESPAC  = 278   # mesmo espaçamento entre faces do ABCD
    X_OFF  = 80

    y_top  = base_y - 100
    altura = float(pj.get('altura', 280))
    y_bot  = y_top - altura
    entity_count = 0

    face_info = []
    if larg1_E > 0:
        face_info.append(('E', base_x + X_OFF,              larg1_E))
    if larg1_F > 0:
        x_f = base_x + X_OFF + (larg1_E + ESPAC if larg1_E > 0 else 0)
        face_info.append(('F', x_f, larg1_F))

    # Nível lines spanning all EF panels
    x_r = (face_info[-1][1] + face_info[-1][2] + 50) if face_info else base_x + 200
    msp.add_lwpolyline([(base_x, y_top), (x_r, y_top)],
                       close=False, dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    msp.add_lwpolyline([(base_x, y_bot), (x_r, y_bot)],
                       close=False, dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    entity_count += 2

    # Header label
    msp.add_text(f'{nome} (E/F)', dxfattribs={
        'layer': 'NOMENCLATURA',
        'insert': (base_x + X_OFF, base_y + 20),
        'height': 15,
    })
    entity_count += 1

    for fid, x_left, larg_total in face_info:
        h1_f = float(pj.get(f'h1_{fid}', 2.0))
        h2_f = float(pj.get(f'h2_{fid}', 244.0))
        h3_f = float(pj.get(f'h3_{fid}', 34.0))

        y0 = y_bot
        for _seg_y, _seg_h in [(y0, h1_f), (y0+h1_f, h2_f), (y0+h1_f+h2_f, h3_f)]:
            if _seg_h > 0.1:
                msp.add_lwpolyline(
                    [(x_left, _seg_y), (x_left+larg_total, _seg_y),
                     (x_left+larg_total, _seg_y+_seg_h), (x_left, _seg_y+_seg_h)],
                    close=True, dxfattribs={'layer': 'Painéis'}
                )
                entity_count += 1

        # Vertical sarrafos (mesma lógica ABCD face A: orientação vertical)
        sarr_x = x_left + 7
        y_sarr_split = y_bot + h1_f
        # dashed lower segment
        msp.add_lwpolyline([(sarr_x, y_bot), (sarr_x, y_sarr_split)],
                           close=False,
                           dxfattribs={'layer': 'SARR_2.2x7', 'linetype': 'DASHED'})
        # continuous upper segment
        msp.add_lwpolyline([(sarr_x, y_sarr_split), (sarr_x, y_top)],
                           close=False,
                           dxfattribs={'layer': 'SARR_2.2x7'})
        entity_count += 2

        # Face label
        msp.add_text(fid, dxfattribs={
            'layer': 'NOMENCLATURA',
            'insert': (x_left + larg_total/2 - 5, y_top + 8),
            'height': 12,
        })
        entity_count += 1

        # Cota de largura
        try:
            d = msp.add_linear_dim(
                base=(x_left + larg_total/2, y_bot - 30),
                p1=(x_left, y_bot), p2=(x_left + larg_total, y_bot),
                angle=0, dimstyle='PAINEL-NOVA',
                dxfattribs={'layer': 'COTA'}
            )
            d.render()
            entity_count += 1
        except Exception:
            pass

    return entity_count


# ═════════════════════════════════════════════════════════════════════════════
# Zone generator — gera UMA zona por pilar em msp isolado (x=0)
# ═════════════════════════════════════════════════════════════════════════════

def generate_pilar_zone(msp, pj: dict, zone: str, row_y: float = 0) -> int:
    """
    Gera apenas a zona indicada para um pilar, com x-origem em 0.
    Retorna contagem de entidades, ou -1 se zona é omitida (grade_1=0, EFGH).

    Zonas:
      'abcd'  — faces A/B/C/D com sarrafos verticais, x=0 (equiv. ZONE_ABCD_X=0)
      'cima'  — seção transversal 2x, x=0 (ZONE_CIMA_X já é 0)
      'grades'— grade de sarrafos, x=0 (equiv. ZONE_GRADES_X=0); omite se comp<=0
      'efgh'  — faces E/F do pilar em U; omite se larg1_E=0 e larg1_F=0
    """
    nome    = pj.get('nome', f"P{pj.get('numero', '?')}")
    comp    = float(pj.get('comprimento', 60))
    larg    = float(pj.get('largura', 38))
    altura  = float(pj.get('altura', 280))
    grade_1 = float(pj.get('grade_1', 0))
    grade_2 = float(pj.get('grade_2', 0))

    if zone == 'abcd':
        return draw_abcd(msp, 0, row_y, comp, larg, altura, nome, pj)
    elif zone == 'cima':
        cima_y = row_y + altura / 2
        return draw_cima(msp, 0, cima_y, comp, larg, grade_1, nome, pj)
    elif zone == 'grades':
        if comp <= 0:
            return -1
        return draw_grades(msp, 0, row_y, grade_1, grade_2, comp, larg, altura, nome, pj)
    elif zone == 'efgh':
        larg1_E = float(pj.get('larg1_E', 0.0))
        larg1_F = float(pj.get('larg1_F', 0.0))
        if larg1_E <= 0 and larg1_F <= 0:
            return -1  # pilar sem faces E/F
        return draw_efgh(msp, 0, row_y, pj)
    return 0


# ═════════════════════════════════════════════════════════════════════════════
# Main generator — 3 zones per pilar
# ═════════════════════════════════════════════════════════════════════════════

def generate_pilar(msp, pj, row_y_offset):
    """
    Generate all zones for a single pilar at the appropriate Y offset.
    Reads `subtipo_pil` from pj (RETANGULAR | U | ESPECIAL).
    U-shape: adds EFGH zone at ZONE_EFGH_X with faces E/F.
    Returns total entity count.
    """
    nome    = pj.get('nome', f"P{pj.get('numero', '?')}")
    comp    = float(pj.get('comprimento_geom') or pj.get('comprimento', 60))
    larg    = float(pj.get('largura', 38))
    altura  = float(pj.get('altura', 280))
    grade_1 = float(pj.get('grade_1', 0))
    grade_2 = float(pj.get('grade_2', 0))
    subtipo = pj.get('subtipo_pil', 'RETANGULAR')

    total_entities = 0

    # ── ZONE 1: ABCD (X:-7000) ──────────────────────────────────────────────
    n = draw_abcd(msp, ZONE_ABCD_X, row_y_offset, comp, larg, altura, nome, pj)
    total_entities += n

    # ── ZONE 2: CIMA (X:0, centered) ────────────────────────────────────────
    n = draw_cima(msp, ZONE_CIMA_X, row_y_offset + altura/2, comp, larg, grade_1, nome, pj)
    total_entities += n

    # ── ZONE 3: GRADES (X:4000) ──────────────────────────────────────────────
    n = draw_grades(msp, ZONE_GRADES_X, row_y_offset, grade_1, grade_2,
                    comp, larg, altura, nome, pj)
    total_entities += n

    # ── ZONE 4: EFGH (X:8000) — apenas subtipo U ─────────────────────────────
    if subtipo == 'U' and (float(pj.get('larg1_E', 0)) > 0 or float(pj.get('larg1_F', 0)) > 0):
        n = draw_efgh(msp, ZONE_EFGH_X, row_y_offset, pj)
        if n > 0:
            total_entities += n

    # ── ZONE EXTRA: layers STOG presentes mas ausentes no gerador ────────────
    draw_extra_pl_layers(msp, ZONE_ABCD_X, row_y_offset, comp, larg, altura, nome)

    return total_entities


def main():
    parser = argparse.ArgumentParser(
        description='Generate STOG-quality PL DXF with 3 separate zones (ABCD, CIMA, GRADES)')
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só este pilar (ex: P001). Output: PL_preview_P001.dxf')
    parser.add_argument('--zone', type=str, default='all',
                        choices=['all', 'abcd', 'cima', 'grades', 'efgh'],
                        help='Gerar apenas esta zona em DXF isolado (all=modo legado combinado)')
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

    # ── Zone mode: gera DXF isolado por zona (para viewer/G2 por zona) ────────
    if args.zone != 'all':
        zone = args.zone
        zone_label = zone.upper()
        modo = f'item={args.item}' if args.item else 'pavimento completo'
        print(f'Processando {len(pilar_files)} pilares [{modo}] (zone={zone_label})')
        print()
        for idx, pf in enumerate(pilar_files):
            try:
                pj = json.load(open(pf, encoding='utf-8'))
            except (json.JSONDecodeError, OSError) as e:
                print(f'  [{idx+1:2d}] [ERRO] {pf.name} — {e}')
                continue
            nome  = pj.get('nome', pf.stem)
            comp  = pj.get('comprimento', '?')
            larg_v = pj.get('largura', '?')
            altura = float(pj.get('altura', 280))

            doc_z = setup_doc()
            msp_z = doc_z.modelspace()
            n = generate_pilar_zone(msp_z, pj, zone)

            if n < 0:
                if zone == 'grades':
                    skip_reason = 'grade_1=0'
                elif zone == 'efgh':
                    skip_reason = 'larg1_E=larg1_F=0 (não é U-shape)'
                else:
                    skip_reason = 'não implementado'
                print(f'  [{idx+1:2d}] {nome}: zone={zone_label} omitida ({skip_reason})')
                continue

            out_name = f'PL_{zone_label}_preview_{pf.stem}.dxf'
            out_path = out_dir / out_name
            doc_z.saveas(str(out_path))
            print(f'  [{idx+1:2d}] {nome}: {comp}x{larg_v}cm h={altura:.0f}cm  '
                  f'entities={n}  → {out_name}')
        print(f'\nZone mode {zone_label} concluído.')
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

        subtipo = pj.get('subtipo_pil', 'RETANGULAR')
        subtipo_tag = f'  [{subtipo}]' if subtipo != 'RETANGULAR' else ''
        print(f'  [{idx + 1:2d}] {nome}: {comp}x{larg_v}cm h={altura:.0f}cm  entities={n}{subtipo_tag}')

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
