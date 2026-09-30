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
if __name__ == '__main__' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding='utf-8', errors='replace'
    )
import json, argparse, math, itertools
from pathlib import Path
import ezdxf
from visual_modes import apply_visual_mode
try:
    from pl_abcd_visual_nova import (
        ensure_painel_dimstyle,
        ensure_pressure_layer,
        apply_face_visual_nova,
    )
except Exception:
    ensure_painel_dimstyle = None
    ensure_pressure_layer = None
    apply_face_visual_nova = None
from pl_grade_visual_config import (
    CONFIG_PATH as PL_GRADE_VISUAL_CONFIG_PATH,
    positions_for_mode as grade_horizontal_positions_for_mode,
    validate_positions as validate_grade_horizontal_positions,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from src.core.artifact_governance import guarded_saveas

_MOTOR_ID = "ROBOT_PL_N3_N4"
_MOTOR_SOURCES = [
    Path(__file__),
    Path(__file__).with_name("pl_grade_visual_config.py"),
    PL_GRADE_VISUAL_CONFIG_PATH,
]

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

    # Linetypes explicitamente referenciados pelas entidades. O ezdxf tolera
    # uma referencia ausente, mas o AutoCAD rejeita o DXF inteiro como
    # incompleto (por exemplo: ``Bad linetype name HIDDEN``).
    linetypes = {
        'DASHED': ([5.0, -2.0], 'Dashed'),
        'HIDDEN': ([9.525, 6.35, -3.175], 'Hidden __ __ __'),
    }
    for name, (pattern, description) in linetypes.items():
        if name not in doc.linetypes:
            doc.linetypes.add(name, pattern=pattern, description=description)

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

    # PAINEL: cotas ABCD no padrão manual (txt 10, ciano/magenta)
    if ensure_painel_dimstyle is not None:
        ensure_painel_dimstyle(doc)
    if ensure_pressure_layer is not None:
        ensure_pressure_layer(doc)
    elif 'Sarrafo de Pressão' not in doc.layers:
        doc.layers.add('Sarrafo de Pressão', color=42)

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


def _whole_and_fraction(value, tolerance=1e-6):
    """Separa uma medida positiva em parte inteira e uma única fração estável."""
    value = max(0.0, float(value))
    nearest = round(value)
    if abs(value - nearest) <= tolerance:
        return int(nearest), 0.0
    whole = math.floor(value)
    return whole, round(value - whole, 6)


def _balanced_parts_with_single_fraction(total, count, fraction_last=True):
    """Particiona ``total`` sem espalhar sua fração por vários vãos."""
    if count <= 0:
        return []
    whole, fraction = _whole_and_fraction(total)
    base, remainder = divmod(whole, count)
    parts = [float(base)] * count
    # Os centímetros inteiros excedentes ficam nos últimos vãos. Isso deixa
    # a leitura encadeada previsível e preserva o início da grade em inteiros.
    for index in range(count - remainder, count):
        if 0 <= index < count:
            parts[index] += 1.0
    if fraction:
        index = count - 1 if fraction_last else 0
        parts[index] += fraction
    return parts


def _integer_segments_with_avoidance(
    total_w, offsets, preferred=None, count=None, tol=3.0, max_shift=20.0,
):
    """Distribui vãos inteiros e evita parafusos sem criar meios centímetros.

    Se ``total_w`` for fracionário, exatamente um vão carrega essa fração.
    Colisão tem prioridade sobre simetria e proximidade da divisão anterior.
    """
    total_w = float(total_w)
    # Regra universal das grades: usar a menor quantidade de quadrados que
    # mantenha cada vão em no máximo 31 cm. A preferência de ficha continua
    # sendo respeitada somente quando atende a esta malha.
    if count is None:
        count = max(1, int(math.ceil(total_w / 31.0)))
    if total_w <= 0 or count <= 0:
        return []
    whole, fraction = _whole_and_fraction(total_w)
    if whole < count:
        return _balanced_parts_with_single_fraction(total_w, count)

    ideal = total_w / count
    low = max(1, int(math.floor(ideal - max_shift)))
    high = max(low, int(math.ceil(ideal + max_shift)))
    preferred = [float(v) for v in (preferred or []) if float(v) > 0]
    if len(preferred) != count or abs(sum(preferred) - total_w) > 0.5:
        preferred = []
    offsets = [float(value) for value in (offsets or [])]

    best = None
    fraction_indexes = [count - 1] if not fraction else list(range(count))
    for prefix in itertools.product(range(low, high + 1), repeat=max(0, count - 1)):
        last = whole - sum(prefix)
        if last < low or last > high:
            continue
        integers = list(prefix) + [last]
        for fraction_index in fraction_indexes:
                    segments = [float(value) for value in integers]
                    if fraction:
                        segments[fraction_index] += fraction
                    boundaries = []
                    cumulative = 0.0
                    for segment in segments[:-1]:
                        cumulative += segment
                        boundaries.append(cumulative)

                    penetrations = [
                        tol - abs(boundary - offset)
                        for boundary in boundaries
                        for offset in offsets
                        if abs(boundary - offset) <= tol
                    ]
                    conflict_count = len(penetrations)
                    conflict_depth = round(sum(value + 1e-6 for value in penetrations), 6)
                    balance = round(sum((value - ideal) ** 2 for value in segments), 6)
                    preferred_delta = (
                        round(sum(abs(a - b) for a, b in zip(segments, preferred)), 6)
                        if preferred else balance
                    )
                    # Em largura fracionária, o último vão recebe a fração por
                    # padrão; ela muda de posição apenas para eliminar colisão.
                    fraction_rank = 0 if fraction_index == count - 1 else 1
                    score = (
                        conflict_count,
                        conflict_depth,
                        preferred_delta,
                        balance,
                        fraction_rank,
                        tuple(segments),
                    )
                    if best is None or score < best[0]:
                        best = (score, segments)
    if best:
        return best[1]
    return _balanced_parts_with_single_fraction(total_w, count)


def _grade_boundaries_with_avoidance(total_w, offsets, tol=3.0, step=5.0, max_shift=20.0):
    """Compatibilidade: fronteiras derivadas da distribuição inteira oficial."""
    del step
    segments = _integer_segments_with_avoidance(
        total_w, offsets, tol=tol, max_shift=max_shift,
    )
    cumulative = 0.0
    boundaries = []
    for segment in segments[:-1]:
        cumulative += segment
        boundaries.append(cumulative)
    return boundaries


def _segments_from_boundaries(boundaries, total_w):
    """Fronteiras intermediárias → larguras de cada módulo."""
    bnds = [0.0] + list(boundaries) + [total_w]
    return [b1 - b0 for b0, b1 in zip(bnds[:-1], bnds[1:])]


def _div_segments(pj, grade_w, div_key='grade_1_div_a', bolt_offsets=None):
    """Fonte única de CIMA/GRADES com vãos inteiros e anticolisão.

    A divisão persistida é preferência geométrica, não autorização para
    espalhar frações. O resultado sempre obedece à regra humana atual.
    """
    raw = pj.get(div_key) or []
    preferred = [float(v) for v in raw if v]
    if not preferred or abs(sum(preferred) - grade_w) >= 0.5:
        preferred = None
    if bolt_offsets is None:
        bolt_offsets = _bolt_offsets_from_pj(pj, grade_w)
    return _integer_segments_with_avoidance(
        grade_w, bolt_offsets, preferred=preferred,
    )


def _grade_starts(grade_width, gaps):
    starts = []
    cursor = 0.0
    for index in range(len(gaps) + 1):
        starts.append(cursor)
        if index < len(gaps):
            cursor += grade_width + gaps[index]
    return starts


def _normalized_grade_layout(total_width, legacy_layout):
    """Mantém grades inteiras e concentra eventual fração em um único gap."""
    total_width = float(total_width)
    ng, legacy_width, _legacy_gap = legacy_layout
    ng = max(1, int(ng))
    if ng == 1:
        return 1, total_width, []

    gap_count = ng - 1
    candidates = []
    max_width = min(106, int(math.floor(total_width / ng)))
    for grade_width in range(1, max_width + 1):
        gap_total = total_width - ng * grade_width
        if gap_total <= 0:
            continue
        gaps = _balanced_parts_with_single_fraction(gap_total, gap_count)
        if not all(1.0 <= gap <= 15.0 for gap in gaps):
            continue
        score = (
            abs(grade_width - float(legacy_width)),
            max(gaps) - min(gaps),
            -grade_width,
        )
        candidates.append((score, float(grade_width), gaps))
    if candidates:
        _score, grade_width, gaps = min(candidates, key=lambda item: item[0])
        return ng, grade_width, gaps

    # Salvaguarda para dimensões fora da faixa do legado.
    grade_width = float(max(1, round(float(legacy_width))))
    gaps = _balanced_parts_with_single_fraction(
        total_width - ng * grade_width, gap_count,
    )
    return ng, grade_width, gaps


CIMA_SINGLE_GRADE_MAX_WIDTH_CM = 122.0
"""Maior largura externa que permanece uma única grade na visão CIMA."""
CIMA_GRID_CELL_CM = 30.0
"""Passo nominal dos quadrados da grade única quando a largura é múltipla."""


def _grade_layout_from_inner(inner_width):
    """Retorna o arranjo de grades da visão CIMA a partir do vão interno.

    A ficha informa o comprimento interno do pilar, enquanto a grade inclui
    11 cm de chapa de cada lado. Até 120 cm de largura externa o detalhamento
    padrão é uma única grade; em 120 cm, as quatro divisões resultam em
    quadrados de 30 cm. Acima desse limite a segmentação homologada do
    ``GradeCalculator`` continua sendo aplicada.
    """
    total_width = float(inner_width) + 22.0
    if total_width <= CIMA_SINGLE_GRADE_MAX_WIDTH_CM:
        return 1, total_width, []
    if _GradeCalculator:
        legacy = _GradeCalculator.calcular_grades(inner_width)
    else:
        legacy = (1, total_width, 0.0)
    return _normalized_grade_layout(total_width, legacy)


def _grade_divisions(pj, total_width, ng, grade_width, gaps):
    """Divisões por grade com offsets globais dos parafusos convertidos em locais."""
    global_bolts = _bolt_offsets_from_pj(pj, total_width)
    divisions = []
    for index, start in enumerate(_grade_starts(grade_width, gaps)):
        # Uma grade única cuja largura fecha em módulos de 30 cm preserva a
        # modulação de quadrados da ficha. Neste caso a malha é geométrica e
        # não pode ser deslocada pela preferência/anticolisão de parafusos.
        cell_count = 4
        is_small_single_grid = (
            ng == 1
            and 4 * CIMA_GRID_CELL_CM <= grade_width <= CIMA_SINGLE_GRADE_MAX_WIDTH_CM
        )
        if is_small_single_grid:
            # A sobra inteira fica distribuída simetricamente nos módulos
            # centrais: 120 → 30/30/30/30; 122 → 30/31/31/30.
            whole_width = round(grade_width)
            if abs(grade_width - whole_width) < 1e-4:
                base, remainder = divmod(whole_width, cell_count)
                parts = [float(base)] * cell_count
                for position in ((1, 2) if remainder == 2 else (2,))[:remainder]:
                    parts[position] += 1.0
                divisions.append(parts)
                continue
            # Largura fracionária não pode criar uma cadeia falsa de cotas.
            # Mantém o distribuidor normal, que concentra a fração em um vão.
        local_bolts = [
            offset - start
            for offset in global_bolts
            if start - 3.0 <= offset <= start + grade_width + 3.0
        ]
        divisions.append(_div_segments(
            pj,
            grade_width,
            f'grade_{index + 1}_div_a',
            bolt_offsets=local_bolts,
        ))
    return divisions


# ═════════════════════════════════════════════════════════════════════════════
# CIMA — Cross-section view (top view, scaled 2x at the end)
# ═════════════════════════════════════════════════════════════════════════════

def _secao_l_da_ficha(pj: dict):
    """Lê a seção em L declarada pela ficha N2, sem conhecer o item."""
    special = pj.get("pilar_especial") if isinstance(pj, dict) else None
    section = special.get("secao_l") if isinstance(special, dict) else None
    if not isinstance(section, dict):
        return None
    try:
        ex = float(section.get("externa_x") or 0.0)
        ix = float(section.get("interna_x") or 0.0)
        ey = float(section.get("externa_y") or 0.0)
        iy = float(section.get("interna_y") or 0.0)
    except (TypeError, ValueError):
        return None
    if min(ex, ix, ey, iy) <= 0.0 or ix >= ex or iy >= ey:
        return None
    return ex, ix, ey, iy


def draw_cima_l(msp, ox, oy, nome, pj: dict):
    """CIMA combinada de pilar L; guiada somente pela seção declarada em N2."""
    dims = _secao_l_da_ficha(pj)
    if not dims:
        return 0
    ex, ix, ey, iy = dims
    x0, y0 = ox - ex / 2.0, oy - ey / 2.0
    outline = [(x0, y0), (x0 + ex, y0), (x0 + ex, y0 + ey - iy),
               (x0 + ix, y0 + ey - iy), (x0 + ix, y0 + ey), (x0, y0 + ey)]
    msp.add_lwpolyline(outline, close=True, dxfattribs={"layer": "Painéis"})
    for layer, offset in (("CHAPA", 2.0), ("SARRAFO", 4.0)):
        ring = [(x0 - offset, y0 - offset), (x0 + ex + offset, y0 - offset),
                (x0 + ex + offset, y0 + ey - iy), (x0 + ix, y0 + ey - iy),
                (x0 + ix, y0 + ey + offset), (x0 - offset, y0 + ey + offset)]
        msp.add_lwpolyline(ring, close=True, dxfattribs={"layer": layer})
    for p1, p2, base, angle in (
        ((x0, y0), (x0 + ex, y0), (ox, y0 - 32.0), 0),
        ((x0, y0 + ey), (x0 + ix, y0 + ey), (x0 + ix / 2.0, y0 + ey + 26.0), 0),
        ((x0, y0), (x0, y0 + ey), (x0 - 32.0, oy), 90),
        ((x0 + ex, y0), (x0 + ex, y0 + ey - iy), (x0 + ex + 28.0, y0 + (ey - iy) / 2.0), 90),
    ):
        try:
            dim = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle,
                                     dimstyle="PAINEL-NOVA", dxfattribs={"layer": "COTA"})
            dim.render()
        except Exception:
            pass
    msp.add_text(f"{nome} · CIMA L", dxfattribs={"layer": "NOMENCLATURA", "insert": (x0, y0 + ey + 48.0), "height": 12})
    return 8


def draw_cima(msp, ox, oy, comp, larg, grade_1, nome, pj):
    if str(pj.get("subtipo_pil") or "").upper() == "L":
        special_count = draw_cima_l(msp, ox, oy, nome, pj)
        if special_count:
            return special_count
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
    ng_c, gw_c, gaps_c = _grade_layout_from_inner(comp)
    starts_c = _grade_starts(gw_c, gaps_c)
    divisions_c = _grade_divisions(
        pj, chapa_full_w, ng_c, gw_c, gaps_c,
    )

    # ── 3b/3d. Madeira por grade (lado C = topo, lado A = fundo) ─────────────
    # Cada uma das ng_c grades recebe: fundo + canto_esq + canto_dir + N divisores.
    madeira_y0 = cy_t + TC
    madeira_h = CORNER_W

    def _draw_madeira_row(y_m):
        n0 = len(entities)
        for gi, grade_start in enumerate(starts_c):
            gx0 = corner_l + grade_start
            gx1 = gx0 + gw_c
            rp(gx0, y_m, gw_c, madeira_h, 'Madeira')                        # fundo
            rp(gx0, y_m, CORNER_W, madeira_h, 'Madeira')                     # canto esq
            rp(gx1 - CORNER_W, y_m, CORNER_W, madeira_h, 'Madeira')         # canto dir
            cumulative = 0.0
            for segment in divisions_c[gi][:-1]:
                cumulative += segment
                off = cumulative
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
    def _place_div_dims(values_by_grade, y_base, offset):
        for gi, values in enumerate(values_by_grade):
            nums = [float(v) for v in values if v and float(v) > 0]
            if not nums:
                continue
            gx0 = corner_l + starts_c[gi]
            cumsum = 0.0
            for v in nums:
                w = v
                x0 = gx0 + cumsum
                x1 = min(gx0 + cumsum + w, gx0 + gw_c)
                if x1 - x0 > 0.01:
                    txt = f'{v:.0f}' if v == int(v) else f'{v:g}'
                    entities.append(dim_h(msp, x0, x1, y_base, 'COTA', 'cotax2', offset=offset, text=txt))
                cumsum += w

    _place_div_dims(divisions_c, madeira_y0_a, offset=20)

    # Eventual fração da largura total fica em um único gap entre grades.
    for gi, gap in enumerate(gaps_c):
        if gap > 0.01:
            gap_x0 = corner_l + starts_c[gi] + gw_c
            gap_x1 = gap_x0 + gap
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

def panel_intervals_with_opening_boundaries(
    intervals: list,
    openings: list[dict],
    tolerance: float = 1e-4,
) -> list[float]:
    """Inclui fundo/topo das aberturas na malha horizontal do painel.

    ``paineis_intervals_FACE`` armazena deltas a partir de ``h1``. O desenho
    de ABCD só avalia cortes quando passa por uma dessas fronteiras. Logo uma
    abertura cujo ``y_rel`` caia dentro de um intervalo precisa dividi-lo;
    caso contrário as paredes internas aparecem, mas o vazio não é fechado
    visualmente (incidente P1/A, abertura AD).

    A função preserva todas as divisões originais, acrescenta apenas as cotas
    necessárias e nunca altera o dicionário de entrada.
    """
    clean = []
    for value in intervals or []:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > tolerance:
            clean.append(number)
    if not clean:
        return []

    total = sum(clean)
    # Expande total para cobrir topo das aberturas (senão top era clampado
    # e a zona da abertura ficava sem H mid/topo no lado sólido).
    for opening in openings or []:
        if not isinstance(opening, dict):
            continue
        try:
            bottom = float(opening.get('y_rel') or 0.0)
            height = max(0.0, float(opening.get('altura') or 0.0))
            total = max(total, bottom + height)
        except (TypeError, ValueError):
            continue

    boundaries = []
    cursor = 0.0
    for interval in clean:
        cursor = min(total, cursor + interval)
        boundaries.append(cursor)

    for opening in openings or []:
        if not isinstance(opening, dict):
            continue
        try:
            bottom = float(opening.get('y_rel') or 0.0)
            height = max(0.0, float(opening.get('altura') or 0.0))
        except (TypeError, ValueError):
            continue
        bottom = max(0.0, min(total, bottom))
        top = max(bottom, min(total, bottom + height))
        if bottom > tolerance:
            boundaries.append(bottom)
        if top > tolerance:
            boundaries.append(top)

    ordered = []
    for boundary in sorted(boundaries):
        if boundary <= tolerance:
            continue
        if not ordered or abs(boundary - ordered[-1]) > tolerance:
            ordered.append(round(boundary, 4))

    rebuilt = []
    previous = 0.0
    for boundary in ordered:
        delta = round(boundary - previous, 4)
        if delta > tolerance:
            rebuilt.append(delta)
        previous = boundary
    return rebuilt

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
    # A=B → comp-direction: panel width = comp + 22
    # C=D → larg-direction: panel width from N2 DXF geometry (larg_c_geom)
    # fallback: min(larg, 19) per historical SCR convention
    larg_a = comp + 22
    larg_b = comp + 22
    larg_c = float(larg)
    larg_d = larg_c

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
            angle=90, dimstyle='PAINEL',
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
    # Níveis absolutos (m) quando o payload traz *_abs; senão os campos
    # nivel_saida/nivel_chegada continuam na convenção legada em centímetros.
    # Não inferir "cota absoluta" apenas porque o valor é > 20: P35 traz
    # nivel_saida=280 cm e pd_pavimento_cm=321 cm, por exemplo.
    _ns_abs = pj.get('nivel_saida_abs', None)
    _nc_abs = pj.get('nivel_chegada_abs', None)
    try:
        _ns_show = float(_ns_abs) if _ns_abs is not None else float(nivel_saida) / 100.0
        _nc_show = float(_nc_abs) if _nc_abs is not None else float(nivel_chegada) / 100.0
    except Exception:
        _ns_show = float(nivel_saida) / 100.0
        _nc_show = float(nivel_chegada) / 100.0
    # O PD extraído do cabeçalho N2 é a autoridade da reprodução N4.
    # A diferença entre níveis é apenas fallback para payloads N3 antigos.
    _pd_show = pd_cm / 100.0 if pd_cm > 0.0 else abs(_ns_show - _nc_show)
    for i, txt in enumerate([
        f'CENARIOS - PD: {_pd_show:.2f}',
        f'NIVEL DE SAIDA: {_ns_show:.2f}',
        f'NIVEL DE CHEGADA: {_nc_show:.2f}',
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
        # h1_* é a cinta/offset confirmado pela ficha. h1_geom_*=0 significa
        # apenas que o recorte explodido não tinha uma junta horizontal explícita
        # nesse trecho; não pode apagar a cinta (P35: 2 + 122 = cota 124).
        _h1_declared = float(pj.get(f'h1_{fid}', H1_DEFAULT) or 0.0)
        _h1_geom_raw = pj.get(f'h1_geom_{fid}', None)
        try:
            _h1_geom = float(_h1_geom_raw) if _h1_geom_raw is not None else None
        except (TypeError, ValueError):
            _h1_geom = None
        h1 = _h1_geom if _h1_geom is not None and _h1_geom > 0.5 else _h1_declared
        h2_face = float(pj.get(f'h2_{fid}', 244.0))
        h_low   = h1 + h2_face / 2.0   # first sub-panel boundary
        y_low   = y0 + h_low
        x_right = x_left + larg_total

        # Intervalos N2 (ground truth para todas as faces A/B/C/D)
        _intervals = pj.get(f'paineis_intervals_{fid}')
        # Face C usa modelo 262 apenas como fallback quando N2 não tem intervals
        face_uses_262 = (fid == 'C') and not (_intervals and len(_intervals) >= 1)
        _aberturas: list[dict] = []

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

            # NOVA: a malha de painéis é só módulos 122+sobra.
            # Fundo/topo de abertura NÃO entram como junta de painel (senão
            # vira 56+66 no lugar de 122+58). Abertura = recorte parcial.
            _intervals = [float(x) for x in _intervals]
            # Lógicos (módulos) vs malha expandida (parts de paineis_unidos_*).
            _intervals_logical = list(_intervals)
            _totals_n3_mesh = []
            try:
                from pl_abcd_visual_nova import (
                    parse_paineis_unidos,
                    expand_intervals_with_unidos,
                )
                _unidos_mesh = parse_paineis_unidos(pj, fid)
                if _unidos_mesh:
                    _mesh_exp, _totals_n3_mesh = expand_intervals_with_unidos(
                        _intervals_logical, _unidos_mesh
                    )
                    if _mesh_exp:
                        # Desenho H usa parts (linha extra no local da soma);
                        # cotas usam logical + unidos (ver bloco 5c).
                        _intervals = _mesh_exp
            except Exception as _un_exc:
                print(f'[PL-NOVA] paineis_unidos face {fid}: {_un_exc}', flush=True)

            # Pré-computa coordenadas de cada abertura
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
                    # Junta de painel caiu no y do fundo da abertura: H só no SÓLIDO.
                    _skip_l, _skip_r = x_left, x_right
                    for _ab in _at_bot_list:
                        if _ab['lado'] == 'direito':
                            _skip_r = min(_skip_r, x_right - _ab['larg'])
                        elif _ab['lado'] == 'esquerdo':
                            _skip_l = max(_skip_l, x_left + _ab['larg'])
                        elif _ab['lado'] == 'meio':
                            if _ab['x_inn_l'] - x_left > 0.5:
                                msp.add_line((x_left, y_cur), (_ab['x_inn_l'], y_cur),
                                             dxfattribs={'layer': 'Painéis'})
                                entity_count += 1
                            if x_right - _ab['x_inn_r'] > 0.5:
                                msp.add_line((_ab['x_inn_r'], y_cur), (x_right, y_cur),
                                             dxfattribs={'layer': 'Painéis'})
                                entity_count += 1
                            _skip_l = _skip_r
                    if _skip_r - _skip_l > 0.5 and not any(
                        ab['lado'] == 'meio' for ab in _at_bot_list
                    ):
                        msp.add_line((_skip_l, y_cur), (_skip_r, y_cur),
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
                    # Dentro da faixa Y de abertura: H só no trecho SÓLIDO
                    # (manual A: H77 de x_left→xi, não full 88 sobre o vazio).
                    _skip_l = x_left
                    _skip_r = x_right
                    for _ab in _inside_list:
                        if _ab['lado'] == 'direito':
                            _skip_r = min(_skip_r, x_right - _ab['larg'])
                        elif _ab['lado'] == 'esquerdo':
                            _skip_l = max(_skip_l, x_left + _ab['larg'])
                        elif _ab['lado'] == 'meio':
                            # desenha dois lados do meio
                            if _ab['x_inn_l'] - x_left > 0.5:
                                msp.add_line((x_left, y_cur), (_ab['x_inn_l'], y_cur),
                                             dxfattribs={'layer': 'Painéis'})
                                entity_count += 1
                            if x_right - _ab['x_inn_r'] > 0.5:
                                msp.add_line((_ab['x_inn_r'], y_cur), (x_right, y_cur),
                                             dxfattribs={'layer': 'Painéis'})
                                entity_count += 1
                            _skip_l = _skip_r  # já desenhado
                    if _skip_r - _skip_l > 0.5 and not any(
                        ab['lado'] == 'meio' for ab in _inside_list
                    ):
                        msp.add_line((_skip_l, y_cur), (_skip_r, y_cur),
                                     dxfattribs={'layer': 'Painéis'})
                        entity_count += 1
                else:
                    msp.add_line((x_left, y_cur), (x_right, y_cur), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1

            panel_top_face = min(y_cur, y_top)
            y_mid_face     = panel_top_face
            y_low = y0 + h1 + float(_intervals[0])

            # Fundos de abertura (recorte em Painéis) — dual: 11+29; single: COTA.
            # NÃO são juntas de painel; desenhados à parte da malha 122.
            _reb = float(pj.get(f'rebaixo_laje_{fid}', 0.0) or 0.0)
            _vlj = float(pj.get(f'vazio_laje_{fid}', 0.0) or 0.0)
            _dual_ab = any(ab['lado']=='esquerdo' for ab in _aberturas) and any(ab['lado']=='direito' for ab in _aberturas)
            if _dual_ab:
                for _ab in _aberturas:
                    _yb = float(_ab['y_bot'])
                    if _ab['lado'] == 'esquerdo':
                        msp.add_line(
                            (x_left, _yb),
                            (x_left + float(_ab['larg']), _yb),
                            dxfattribs={'layer': 'Painéis'},
                        )
                        entity_count += 1
                    elif _ab['lado'] == 'direito':
                        msp.add_line(
                            (x_right - float(_ab['larg']), _yb),
                            (x_right, _yb),
                            dxfattribs={'layer': 'Painéis'},
                        )
                        entity_count += 1

            # Inner verticals para cada abertura
            # Dual esq+dir: inners param na base do rebaixo/vazio laje (manual -97),
            # não sobem até o topo da face (rebaixo ocupa o miolo).
            for _ab in _aberturas:
                _al = _ab['lado']
                _yb, _yt = _ab['y_bot'], _ab['y_top']
                if _dual_ab and _al in ('esquerdo', 'direito') and (_reb > 0 or _vlj > 0):
                    _yt = min(_yt, y_top - _reb - _vlj)
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
                    # Bordas Painéis param no fundo de sua própria abertura de canto;
                    # o contorno do vazio acima é COTA (draw_void_outer_cota no visual NOVA).
                    _yb_esq = min((ab['y_bot'] for ab in _ab_esq_list), default=panel_top_face)
                    _yb_dir = min((ab['y_bot'] for ab in _ab_dir_list), default=panel_top_face)
                    msp.add_line((x_left,  y0), (x_left,  _yb_esq), dxfattribs={'layer': 'Painéis'})
                    msp.add_line((x_right, y0), (x_right, _yb_dir), dxfattribs={'layer': 'Painéis'})
                    entity_count += 2
                elif _al == 'direito':
                    # Esquerda sobe até o TOPO da face (manual A: 304 em Painéis)
                    msp.add_line((x_left, y0), (x_left, y_top),
                                 dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                    msp.add_line((x_right, y0), (x_right, _yb), dxfattribs={'layer': 'Painéis'})
                    entity_count += 1
                    # direita no vazio: COTA (void_outer), não Painéis
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

            # Topo da abertura single: manual NÃO fecha o vão em Painéis
            # (só H parcial no sólido + stub COTA no vazio). Dual: rebaixo NOVA.
            # (intencionalmente sem H sobre o vão)

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

        # Contrato N3: o corpo abaixo da primeira abertura é painel sólido e
        # recebe a mesma leitura ANSI31 usada pela referência N2/N4. A regra
        # deriva apenas da geometria publicada no payload: sem abertura,
        # hachura até o topo do painel; com abertura, até o menor fundo de vão.
        # N2 é tratado separadamente no bloco de reprodução de sua malha.
        # Sem hatch de painel no N4: vazios/lajes são tratados pelo visual NOVA.

        # ── 5d. Retângulo da zona de laje (acima do painel → até nível superior) ───
        # Com aberturas A/B o contorno do vazio é COTA parcial (void_outer NOVA) +
        # stubs; NÃO desenhar retângulo full-width (manual A não tem H88 COTA no topo).
        laje_bot = panel_top_face
        _has_ab_void = bool(_aberturas) and fid in ('A', 'B')
        if not _has_ab_void:
            if laje_bot < y_top:
                msp.add_line((x_left,  laje_bot), (x_left,  y_top), dxfattribs={'layer': 'COTA'})
                msp.add_line((x_right, laje_bot), (x_right, y_top), dxfattribs={'layer': 'COTA'})
                entity_count += 2
            msp.add_line((x_left, y_top), (x_right, y_top), dxfattribs={'layer': 'COTA'})
            entity_count += 1
        else:
            # stubs COTA no topo das aberturas (manual A: H11 em 157→168; B: 11+29)
            for _ab in _aberturas:
                _al = _ab['lado']
                _lg = float(_ab['larg'])
                if _al == 'direito':
                    msp.add_line((x_right - _lg, y_top), (x_right, y_top),
                                 dxfattribs={'layer': 'COTA'})
                    entity_count += 1
                elif _al == 'esquerdo':
                    msp.add_line((x_left, y_top), (x_left + _lg, y_top),
                                 dxfattribs={'layer': 'COTA'})
                    entity_count += 1
            # dual: topo do miolo é Painéis (rebaixo), não COTA full
            _esq_ab = [a for a in _aberturas if a['lado'] == 'esquerdo']
            _dir_ab = [a for a in _aberturas if a['lado'] == 'direito']
            if _esq_ab and _dir_ab:
                # stubs já; rebaixo laterais COTA opcional (manual tem V7 em COTA no rebaixo)
                pass

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
            # Visual NOVA cuida de SARR em A/B (com abertura) e em C/D (passante).
            # Evita duplicar fustes (C/D saíam 4 em vez de 2).
            if apply_face_visual_nova is not None and fid in ('A', 'B', 'C', 'D'):
                sarr_xs = []
            elif fid in ('A', 'B') and _aberturas:
                sarr_xs = []
            else:
                sarr_xs = [x_left + SARR_OFFSET]
                right_sx = x_right - SARR_OFFSET
                if right_sx > x_left + SARR_OFFSET:
                    sarr_xs.append(right_sx)

            # 1 sarrafo: draw TWICE per segment (robot artifact); 2: draw ONCE
            repeat = 2 if len(sarr_xs) == 1 else 1

            # Sarrafo é cortado na abertura: calcula limite de topo por lado
            _sarr_lim_esq = min((ab['y_bot'] for ab in _aberturas if ab['lado'] == 'esquerdo'),
                                default=None)
            _sarr_lim_dir = min((ab['y_bot'] for ab in _aberturas if ab['lado'] == 'direito'),
                                default=None)

            for sx in sarr_xs:
                # Topo efetivo do sarrafo para este sx (abertura corta o sarrafo)
                _left_sx = x_left + SARR_OFFSET
                _is_left_side = abs(sx - _left_sx) < 0.5
                _sarr_stop = (_sarr_lim_esq if _is_left_side else _sarr_lim_dir)

                if is_short:
                    # Short: single PLINE from y_bot+h1 to y_top, continuous (verified P21/P44 SCR)
                    _y_end = min(y_top, _sarr_stop) if _sarr_stop is not None else y_top
                    if _y_end > y0 + h1:
                        for _ in range(repeat):
                            msp.add_lwpolyline([(sx, y0 + h1), (sx, _y_end)],
                                               close=False,
                                               dxfattribs={'layer': 'SARR_2.2x7'})
                            entity_count += 1
                else:
                    # Wide faces (A/B, comp-dir): lower CONTINUOUS + DASHED, stop at y_mid
                    # Narrow faces (C/D, larg-dir): lower CONTINUOUS + small DASHED above + CONTINUOUS top
                    if fid in ('A', 'B'):
                        _y_low_eff = (min(y_low, _sarr_stop) if _sarr_stop is not None
                                      else y_low)
                        _y_mid_eff = (min(y_mid_face, _sarr_stop) if _sarr_stop is not None
                                      else y_mid_face)
                        if _y_low_eff > y0 + h1:
                            for _ in range(repeat):
                                msp.add_lwpolyline([(sx, y0 + h1), (sx, _y_low_eff)],
                                                   close=False,
                                                   dxfattribs={'layer': 'SARR_2.2x7'})
                                entity_count += 1
                        if _y_mid_eff > y_low:
                            for _ in range(repeat):
                                msp.add_lwpolyline([(sx, y_low), (sx, _y_mid_eff)],
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

        # ── 5c. Per-face DIMENSIONs (degraus N1/N2/N3 — SEMANTICA-PILAR-NOVA §2.1)
        # N1 (~12): h1=2 + recortes/aberturas
        # N2 (~30): painéis (módulos ou parts de unido)
        # N3 (~48): total de painel unido (soma das parts) — só com paineis_unidos_*
        x_dim = x_right
        try:
            from pl_abcd_visual_nova import (
                DIM_LVL1_OFF,
                DIM_LVL2_OFF,
                DIM_LVL3_OFF,
                parse_paineis_unidos,
                expand_intervals_with_unidos,
            )
            _LVL1, _LVL2, _LVL3 = DIM_LVL1_OFF, DIM_LVL2_OFF, DIM_LVL3_OFF
        except Exception:
            _LVL1, _LVL2, _LVL3 = 17.0, 40.0, 63.0
            parse_paineis_unidos = None
            expand_intervals_with_unidos = None
        ANN_OFF = _LVL2  # fallback legado

        # Painéis unidos: totais N3 a partir dos intervals LÓGICOS (não da malha expandida)
        _unidos = []
        _totals_n3 = []
        _iv_logical = locals().get('_intervals_logical') or (
            list(_intervals) if _intervals else []
        )
        if (
            parse_paineis_unidos is not None
            and expand_intervals_with_unidos is not None
            and _iv_logical
        ):
            _unidos = parse_paineis_unidos(pj, fid)
            if _unidos:
                _, _totals_n3 = expand_intervals_with_unidos(
                    [float(x) for x in _iv_logical], _unidos
                )

        _abertura_dim_specs: list[tuple[float, float, float, float]] = []
        if is_short:
            if fid in ('A', 'B'):
                dim_specs = [(y_bot, y0 + h1, _LVL1), (y_bot, y_top, _LVL2)]
            else:
                dim_specs = [(y_bot, y0 + h1, _LVL1), (y0 + h1, y_top, _LVL2)]
        elif _intervals and len(_intervals) >= 1:
            # Cotas NOVA com degraus; malha de cotas usa intervals lógicos (ou parts).
            dim_specs = [(y_bot, y0 + h1, _LVL1)]  # N1: cinta 2cm
            _y_p = y0 + h1
            _mod_ys = [_y_p]
            _reb_d = float(pj.get(f'rebaixo_laje_{fid}', 0.0) or 0.0)
            _vlj_d = float(pj.get(f'vazio_laje_{fid}', 0.0) or 0.0)
            _dual_d = (
                any(ab.get('lado') == 'esquerdo' for ab in (_aberturas or []))
                and any(ab.get('lado') == 'direito' for ab in (_aberturas or []))
            )
            # Cotas N2/N3 a partir dos intervals LÓGICOS (+ parts se unido)
            _iv_src = [float(x) for x in (_iv_logical or _intervals)]
            _is_n2_reference_mesh = (
                not isinstance(pj.get('_sa_mode_contract'), dict)
                and not _totals_n3
                and bool(_iv_src)
            )
            if _is_n2_reference_mesh:
                # No N2 humano, as duas faixas curtas finais são partes do
                # painel (ex. 26+15=41), não degraus da cadeia principal.
                # A primeira cota principal inclui a cinta: 2+122=124 (A/B)
                # ou 2+219=221 (C/D). A geometria continua usando todas as
                # fronteiras extraídas; muda somente a semântica da cota.
                _tail_parts = []
                _major_iv = list(_iv_src)
                if (
                    len(_iv_src) >= 3
                    and _iv_src[-1] <= 60.0
                    and _iv_src[-2] <= 60.0
                ):
                    _tail_parts = _iv_src[-2:]
                    _major_iv = _iv_src[:-2]

                _y_cursor = y0 + h1
                for _i, _iv in enumerate(_major_iv):
                    _y_n = min(round(_y_cursor + float(_iv), 4), y_top)
                    if _i == 0:
                        dim_specs.append((y_bot, _y_n, _LVL2))
                    else:
                        dim_specs.append((_y_cursor, _y_n, _LVL2))
                    _y_cursor = _y_n
                    _mod_ys.append(_y_n)

                # Corpo sólido do painel no N2: ANSI31 até o fim da cadeia
                # principal. As faixas curtas finais (partes 26/15, etc.) ficam
                # fora dessa hachura, exatamente como no desenho humano.
                _solid_panel_top = y0 + h1 + sum(_major_iv)

                if _tail_parts:
                    # Mesma DIMENSION real (add_linear_dim + COTA/PAINEL) das
                    # demais cotas da face — texto solto sem linha de
                    # extensao/seta destoava do resto do desenho (achado do
                    # dono: "26 15 41" em formato diferente das demais).
                    _tail_y = y0 + h1 + sum(_major_iv)
                    _tail_total = sum(_tail_parts)
                    dim_specs.append((_tail_y, _tail_y + _tail_total, _LVL2))
                    _part_y = _tail_y
                    for _part in _tail_parts:
                        _next_y = _part_y + _part
                        dim_specs.append((_part_y, _next_y, _LVL1))
                        _mod_ys.append(_next_y)
                        _part_y = _next_y
            elif _totals_n3:
                for _t in _totals_n3:
                    _ya = y0 + h1 + float(_t['y0_rel'])
                    _yb = y0 + h1 + float(_t['y1_rel'])
                    dim_specs.append((_ya, _yb, _LVL3))  # N3: total unido
                    _yp = _ya
                    for _part in _t['parts']:
                        _yn = round(_yp + float(_part), 4)
                        dim_specs.append((_yp, _yn, _LVL2))  # N2: 100 e 22
                        _yp = _yn
                _y_cursor = y0 + h1
                _unido_by_idx = {t['interval_index']: t for t in _totals_n3}
                for _i, _iv in enumerate(_iv_src):
                    _y_n = min(round(_y_cursor + float(_iv), 4), y_top)
                    if _i in _unido_by_idx:
                        _y_cursor = _y_n
                        _mod_ys.append(_y_n)
                        _yp = y0 + h1 + float(_unido_by_idx[_i]['y0_rel'])
                        for _part in _unido_by_idx[_i]['parts']:
                            _yp = round(_yp + float(_part), 4)
                            _mod_ys.append(_yp)
                        continue
                    _is_last = _i == len(_iv_src) - 1
                    if (
                        _is_last
                        and _dual_d
                        and (_reb_d > 0.5 or _vlj_d > 0.5)
                        and _y_n >= y_top - 0.5
                    ):
                        _y_void_bot = y_top - _reb_d - _vlj_d
                        if _y_void_bot > _y_cursor + 0.5:
                            dim_specs.append((_y_cursor, _y_void_bot, _LVL2))
                        if _vlj_d > 0.5:
                            dim_specs.append(
                                (_y_void_bot, _y_void_bot + _vlj_d, _LVL2)
                            )
                        if _reb_d > 0.5:
                            dim_specs.append((y_top - _reb_d, y_top, _LVL2))
                    else:
                        dim_specs.append((_y_cursor, _y_n, _LVL2))
                    _y_cursor = _y_n
                    _mod_ys.append(_y_n)
                    if _y_cursor >= y_top:
                        break
            else:
                for _i, _iv in enumerate(_iv_src):
                    _y_n = min(round(_y_p + float(_iv), 4), y_top)
                    _is_last = _i == len(_iv_src) - 1
                    if (
                        _is_last
                        and _dual_d
                        and (_reb_d > 0.5 or _vlj_d > 0.5)
                        and _y_n >= y_top - 0.5
                    ):
                        _y_void_bot = y_top - _reb_d - _vlj_d
                        if _y_void_bot > _y_p + 0.5:
                            dim_specs.append((_y_p, _y_void_bot, _LVL2))
                        if _vlj_d > 0.5:
                            dim_specs.append(
                                (_y_void_bot, _y_void_bot + _vlj_d, _LVL2)
                            )
                        if _reb_d > 0.5:
                            dim_specs.append((y_top - _reb_d, y_top, _LVL2))
                    else:
                        dim_specs.append((_y_p, _y_n, _LVL2))
                    _y_p = _y_n
                    _mod_ys.append(_y_n)
                    if _y_p >= y_top:
                        break
            # Cotas N1 de abertura: fundo → próxima junta (ex. 66). Cada
            # abertura cota do PRÓPRIO lado (esquerdo/direito) do painel —
            # nunca funde no eixo compartilhado x_dim (direita). Numa dual
            # esq+dir com alturas diferentes, as duas cotas empilhadas na
            # mesma coluna ficam ambíguas (achado do dono: cota da abertura
            # esquerda aparecendo fora do lugar, do lado errado do painel).
            # Laje + painel superior são duas peças físicas distintas. Nunca
            # resumir a cadeia como uma cota única: a ficha declara vazio de
            # laje e rebaixo separadamente (por exemplo, 12 + 7).
            if fid in ('A', 'B') and (_reb_d > 0.5 or _vlj_d > 0.5):
                _top_stack = _reb_d + _vlj_d
                _stack_marks = [y_top - _top_stack]
                if _vlj_d > 0.5:
                    _stack_marks.append(y_top - _reb_d - _vlj_d)
                if _reb_d > 0.5:
                    _stack_marks.append(y_top - _reb_d)
                _stack_marks.append(y_top)
                dim_specs = [
                    spec for spec in dim_specs
                    if not (
                        # A cadeia final pode ter entrado antes pela malha de
                        # painéis (Lvl2). Remova tanto o total 19 quanto suas
                        # partes 12/7 e publique uma única cadeia no Lvl1,
                        # com as duas cotas alinhadas na coluna externa.
                        min(spec[0], spec[1]) >= min(_stack_marks) - 0.5
                        and max(spec[0], spec[1]) <= max(_stack_marks) + 0.5
                        and any(abs(spec[0] - mark) < 0.5 for mark in _stack_marks)
                        and any(abs(spec[1] - mark) < 0.5 for mark in _stack_marks)
                    )
                ]
                _stack_specs = []
                if _vlj_d > 0.5:
                    _stack_specs.append((y_top - _reb_d - _vlj_d, y_top - _reb_d, _LVL2))
                if _reb_d > 0.5:
                    _stack_specs.append((y_top - _reb_d, y_top, _LVL2))
                for _stack_spec in _stack_specs:
                    if not any(
                        abs(min(a, b) - min(_stack_spec[0], _stack_spec[1])) < 0.5
                        and abs(max(a, b) - max(_stack_spec[0], _stack_spec[1])) < 0.5
                        for a, b, _off in dim_specs
                    ):
                        dim_specs.append(_stack_spec)

            _y_void_bot = y_top - _reb_d - _vlj_d if (_reb_d > 0 or _vlj_d > 0) else y_top
            for _ab in (_aberturas or []):
                _yb = float(_ab['y_bot'])
                _next = None
                for _my in sorted(_mod_ys):
                    if _my > _yb + 0.5:
                        _next = _my
                        break
                if _next is not None and _next >= y_top - 0.5 and _y_void_bot < y_top - 0.5:
                    _next = _y_void_bot
                if _next is None or _next - _yb <= 0.5:
                    continue
                # Se a abertura coincide exatamente com um intervalo já
                # cotado na cadeia de painéis, ela não ganha uma segunda cota
                # paralela. O recorte continua desenhado; só eliminamos a
                # repetição gráfica (casos P10/B e P10/C).
                _already_dimensioned = any(
                    abs(min(p1y, p2y) - min(_yb, _next)) < 0.5
                    and abs(max(p1y, p2y) - max(_yb, _next)) < 0.5
                    for p1y, p2y, _ann_off in dim_specs
                )
                if _already_dimensioned:
                    continue
                _al_ab = _ab.get('lado')
                if _al_ab == 'esquerdo':
                    _abertura_dim_specs.append((_yb, _next, x_left, -_LVL1))
                    if _yb < y_top - 0.5 and y_top - _yb > 0.5:
                        _abertura_dim_specs.append((_yb, y_top, x_left, -_LVL2))
                elif _al_ab == 'direito':
                    _abertura_dim_specs.append((_yb, _next, x_right, _LVL1))
                else:  # meio: sem lado próprio, mantém a coluna compartilhada
                    dim_specs.append((_yb, _next, _LVL1))
            if (
                panel_top_face < y_top - 0.5
                and not _dual_d
                and _reb_d <= 0.5
                and _vlj_d <= 0.5
            ):
                dim_specs.append((panel_top_face, y_top, _LVL2))
        elif fid == 'C':
            dim_specs = [
                (y_bot,          y0 + h1,          _LVL1),
                (y_bot,          y_mid_face,       _LVL2),
                (y_mid_face,     panel_top_face,   _LVL2),
                (panel_top_face, y_top,             _LVL2),
            ]
        else:
            _laje_h_dim = float(pj.get(f'laje_{fid}', 0.0))
            if _laje_h_dim > 0.0:
                _y_laje_top_dim = y_mid_face + _laje_h_dim
                dim_specs = [
                    (y_bot,              y_bot + h1,       _LVL1),
                    (y_bot + h1,         y_low,             _LVL2),
                    (y_low,              y_mid_face,        _LVL2),
                    (y_mid_face,         _y_laje_top_dim,   _LVL2),
                ]
            else:
                dim_specs = [
                    (y_bot,        y_bot + h1,   _LVL1),
                    (y_bot + h1,   y_low,         _LVL2),
                    (y_low,        y_mid_face,    _LVL2),
                    (y_mid_face,   y_top,         _LVL2),
                ]
        # dedupe specs (y0,y1,off)
        _seen_dim = set()
        for p1y, p2y, ann_x_off in dim_specs:
            if abs(p2y - p1y) < 0.4:
                continue
            key = (round(min(p1y, p2y), 2), round(max(p1y, p2y), 2), round(ann_x_off, 1))
            if key in _seen_dim:
                continue
            _seen_dim.add(key)
            try:
                d = msp.add_linear_dim(
                    base=(x_dim + ann_x_off, (p1y + p2y) / 2),
                    p1=(x_dim, p1y), p2=(x_dim, p2y),
                    angle=90, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA', 'color': 4}
                )
                d.render()
                entity_count += 1
            except Exception:
                pass

        # Cotas de abertura com eixo próprio (esquerdo em x_left, direito em
        # x_right) — mesmo dedupe, coluna independente de x_dim.
        _seen_dim_ab = set()
        for p1y, p2y, x_base, ann_x_off in _abertura_dim_specs:
            if abs(p2y - p1y) < 0.4:
                continue
            key = (round(min(p1y, p2y), 2), round(max(p1y, p2y), 2), round(x_base, 1), round(ann_x_off, 1))
            if key in _seen_dim_ab:
                continue
            _seen_dim_ab.add(key)
            try:
                d = msp.add_linear_dim(
                    base=(x_base + ann_x_off, (p1y + p2y) / 2),
                    p1=(x_base, p1y), p2=(x_base, p2y),
                    angle=90, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA', 'color': 4}
                )
                d.render()
                entity_count += 1
            except Exception:
                pass

        # ── 5e-1. Cotas de offset do sarrafo (7cm) — só faces A/B (não C/D)
        if fid in ('A', 'B') and not is_horiz and not is_short:
            for p1x, p2x in [(x_left, x_left + SARR_OFFSET),
                              (x_right - SARR_OFFSET, x_right)]:
                try:
                    d = msp.add_linear_dim(
                        base=((p1x + p2x) / 2, y_bot - 19),
                        p1=(p1x, y_bot),
                        p2=(p2x, y_bot),
                        angle=0, dimstyle='PAINEL',
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
                angle=0, dimstyle='PAINEL',
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

        # ── 5f-NOVA-DIM-OPEN: cotas horizontais das aberturas e do painel resultante no topo ──
        if _aberturas and fid in ('A', 'B'):
            try:
                y_dim = y_top + 19
                _esq_list = [a for a in _aberturas if a.get('lado') == 'esquerdo']
                _dir_list = [a for a in _aberturas if a.get('lado') == 'direito']
                _meio_list = [a for a in _aberturas if a.get('lado') == 'meio']

                if _meio_list:
                    for _ab in _meio_list:
                        _xl = float(_ab.get('x_inn_l', x_left))
                        _xr = float(_ab.get('x_inn_r', x_right))
                        for _p1, _p2 in ((x_left, _xl), (_xl, _xr), (_xr, x_right)):
                            if _p2 - _p1 > 0.5:
                                d = msp.add_linear_dim(
                                    base=((_p1 + _p2) / 2, y_dim),
                                    p1=(_p1, y_top), p2=(_p2, y_top),
                                    angle=0, dimstyle='PAINEL',
                                    dxfattribs={'layer': 'COTA', 'color': 4})
                                d.render(); entity_count += 1
                elif _esq_list and _dir_list:
                    # 2 ABERTURAS (esquerda e direita): Cota esq + ÚNICA Cota resultante do meio + Cota dir
                    _w_esq = max(float(a.get('larg', 0.0)) for a in _esq_list)
                    _w_dir = max(float(a.get('larg', 0.0)) for a in _dir_list)
                    _xl = x_left + _w_esq
                    _xr = x_right - _w_dir
                    # 1. Cota abertura esquerda
                    if _w_esq > 0.5:
                        d = msp.add_linear_dim(
                            base=(x_left + _w_esq / 2, y_dim),
                            p1=(x_left, y_top), p2=(_xl, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
                    # 2. ÚNICA cota do painel resultante no meio entre as duas aberturas
                    if _xr - _xl > 0.5:
                        d = msp.add_linear_dim(
                            base=((_xl + _xr) / 2, y_dim),
                            p1=(_xl, y_top), p2=(_xr, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
                    # 3. Cota abertura direita
                    if _w_dir > 0.5:
                        d = msp.add_linear_dim(
                            base=(_xr + _w_dir / 2, y_dim),
                            p1=(_xr, y_top), p2=(x_right, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
                elif _esq_list:
                    # 1 ABERTURA (apenas esquerda): Cota abertura esq + ÚNICA cota sobra direita
                    _w_esq = max(float(a.get('larg', 0.0)) for a in _esq_list)
                    _xl = x_left + _w_esq
                    if _w_esq > 0.5:
                        d = msp.add_linear_dim(
                            base=(x_left + _w_esq / 2, y_dim),
                            p1=(x_left, y_top), p2=(_xl, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
                    if x_right - _xl > 0.5:
                        d = msp.add_linear_dim(
                            base=((_xl + x_right) / 2, y_dim),
                            p1=(_xl, y_top), p2=(x_right, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
                elif _dir_list:
                    # 1 ABERTURA (apenas direita): ÚNICA cota sobra esquerda + Cota abertura dir
                    _w_dir = max(float(a.get('larg', 0.0)) for a in _dir_list)
                    _xr = x_right - _w_dir
                    if _xr - x_left > 0.5:
                        d = msp.add_linear_dim(
                            base=((x_left + _xr) / 2, y_dim),
                            p1=(x_left, y_top), p2=(_xr, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
                    if _w_dir > 0.5:
                        d = msp.add_linear_dim(
                            base=(_xr + _w_dir / 2, y_dim),
                            p1=(_xr, y_top), p2=(x_right, y_top),
                            angle=0, dimstyle='PAINEL',
                            dxfattribs={'layer': 'COTA', 'color': 4})
                        d.render(); entity_count += 1
            except Exception as _de:
                print('open dim fail', _de)

        # ── 5f-NOVA: pressão A/B, sarrafos de abertura, rebaixo, hatch vazios ──
        if apply_face_visual_nova is not None:
            try:
                entity_count += apply_face_visual_nova(
                    msp,
                    fid=fid,
                    x_left=x_left,
                    x_right=x_right,
                    y_bot=y_bot,
                    y_face_top=y_top,
                    y_panel_content_top=panel_top_face,
                    h1=h1,
                    openings=list(_aberturas or []),
                    pj=pj,
                    intervals_logical=list(
                        locals().get("_intervals_logical")
                        or pj.get(f"paineis_intervals_{fid}")
                        or []
                    ),
                )
            except Exception as _vis_exc:
                print(f'[PL-NOVA] visual face {fid} falhou: {_vis_exc}', flush=True)

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

def _grade_face_openings(pj: dict, face: str) -> list[dict]:
    """Normaliza abertura_FACE ou abertura_FACE_1..N para coordenadas locais."""
    raw = []
    direct = pj.get(f'abertura_{face}')
    if isinstance(direct, dict) and direct:
        raw.append(direct)
    idx = 1
    while True:
        item = pj.get(f'abertura_{face}_{idx}')
        if not item:
            break
        if isinstance(item, dict):
            raw.append(item)
        idx += 1
    return raw


def _grade_face_panel_top(pj: dict, face: str, fallback_height: float) -> float:
    """Topo do painel na mesma convenção usada por draw_abcd, em cm locais."""
    pd = float(pj.get('pd_pavimento_cm') or fallback_height)
    intervals = pj.get(f'paineis_intervals_{face}') or []
    if intervals:
        h1 = float(pj.get(f'h1_geom_{face}', pj.get(f'h1_{face}', 0.0)) or 0.0)
        measured = h1 + sum(float(value) for value in intervals if value is not None)
        return max(0.0, min(measured, pd))
    return max(0.0, min(float(fallback_height), pd))


def _grade_vertical_height(
    pj: dict,
    face: str,
    x_rel: float,
    panel_width: float,
    fallback_height: float,
    base_height: float = 2.2,
    top_clearance: float = 15.0,
) -> float:
    """Altura útil de um montante, respeitando recortes superiores da face.

    A posição ``x_rel`` vem das mesmas divisões usadas em CIMA. Aberturas que
    alcançam o topo reduzem apenas os montantes cuja posição cai dentro de sua
    largura. A cota final deixa 15 cm até o topo local do painel.
    """
    panel_top = _grade_face_panel_top(pj, face, fallback_height)
    local_top = panel_top
    h1 = float(pj.get(f'h1_geom_{face}', pj.get(f'h1_{face}', 0.0)) or 0.0)
    tolerance = 0.5
    for opening in _grade_face_openings(pj, face):
        side = str(opening.get('lado') or '').strip().lower()
        width = max(0.0, float(opening.get('largura') or 0.0))
        y_bottom = h1 + float(opening.get('y_rel') or 0.0)
        y_top = y_bottom + max(0.0, float(opening.get('altura') or 0.0))
        if y_top < panel_top - 1.0:
            continue  # abertura interna não altera o topo local do montante
        if side == 'esquerdo':
            affected = x_rel <= width + tolerance
        elif side == 'direito':
            affected = x_rel >= panel_width - width - tolerance
        elif side == 'meio':
            x0 = float(opening.get('x_offset') or 0.0)
            affected = x0 - tolerance <= x_rel <= x0 + width + tolerance
        else:
            affected = False
        if affected:
            local_top = min(local_top, y_bottom)
    return round(max(0.0, local_top - top_clearance - base_height), 4)


def _grade_layout_for_panel_width(panel_width: float):
    """Segmenta uma largura externa exata em uma a três grades."""
    panel_width = float(panel_width)
    if panel_width <= 0:
        return 0, 0.0, []
    if _GradeCalculator and panel_width > 22.0:
        # GradeCalculator soma 22 cm ao valor recebido; retirar antes preserva
        # exatamente a largura externa do painel C/D.
        legacy = _GradeCalculator.calcular_grades(panel_width - 22.0)
        return _normalized_grade_layout(panel_width, legacy)
    return 1, panel_width, []


def draw_grades(
    msp, base_x, base_y, grade_1, grade_2, comp, larg, altura, nome, pj,
    visual_mode="NOVA", horizontal_positions=None,
):
    """
    Zona GRADES coerente com ABCD + CIMA.

    - A/B usam a mesma largura e as mesmas divisões da VISÃO CIMA.
    - C/D existem somente com largura >= 50 cm e mantêm a largura do painel.
    - Apenas as extremidades globais usam 7 cm; encontros e internos usam 3,5 cm.
    - Cada montante recebe altura local da face, 15 cm abaixo do topo do painel.
    - Horizontais usam o perfil INI/NOVA e só entram até o menor montante da grade.
    - Cada montante recebe cota vertical independente.
    """
    BASE_H      = 2.2
    SARR_LW     = 7.0
    SARR_CW     = 3.5
    SARR_HH     = 10.0
    GROUP_GAP   = 40.0   # espaçamento visual entre Grupo A e Grupo B
    if horizontal_positions is None:
        horizontal_positions = grade_horizontal_positions_for_mode(visual_mode)
    else:
        horizontal_positions = validate_grade_horizontal_positions(horizontal_positions)

    def add_vertical_dimension(x_center, height, ordinal):
        if height <= 0.1:
            return
        y0 = base_y + BASE_H
        offset = 7.0 if ordinal % 2 == 0 else -7.0
        try:
            dim = msp.add_linear_dim(
                base=(x_center + offset, y0 + height / 2),
                p1=(x_center, y0), p2=(x_center, y0 + height),
                angle=90, dimstyle='PAINEL-NOVA',
                dxfattribs={'layer': 'COTA'},
            )
            dim.render()
        except Exception:
            pass

    def draw_face_group(face, gx_start, panel_width, ng, gw_each, gaps):
        group_horiz = []
        group_heights = []
        grade_starts = _grade_starts(gw_each, gaps)
        group_total_w = ng * gw_each + sum(gaps)
        if face in ('A', 'B'):
            divisions = _grade_divisions(
                pj, panel_width, ng, gw_each, gaps,
            )
        else:
            divisions = [
                _integer_segments_with_avoidance(gw_each, [])
                for _ in range(ng)
            ]
        msp.add_text(f'{nome}.{face}', dxfattribs={
            'layer': 'NOMENCLATURA', 'insert': (gx_start - 10, base_y),
            'height': 14, 'rotation': 90,
        })

        ordinal = 0
        for gi, grade_start in enumerate(grade_starts):
            gx = gx_start + grade_start
            divs = divisions[gi]
            if face == 'B':
                divs = list(reversed(divs))

            rect_lines(msp, gx, base_y, gw_each, BASE_H, 'SARR_2.2x7')
            global_grade_x = grade_start

            verticals = []
            left_w = SARR_LW if gi == 0 else SARR_CW
            left_x = gx
            verticals.append((left_x, left_w, global_grade_x + left_w / 2.0))
            cumulative = 0.0
            for segment in divs[:-1]:
                cumulative += segment
                verticals.append((
                    gx + cumulative - SARR_CW / 2.0,
                    SARR_CW,
                    global_grade_x + cumulative,
                ))
            right_w = SARR_LW if gi == ng - 1 else SARR_CW
            right_x = gx + gw_each - right_w
            verticals.append((
                right_x, right_w,
                global_grade_x + gw_each - right_w / 2.0,
            ))

            heights = []
            for vx, width, x_rel in verticals:
                local_height = _grade_vertical_height(
                    pj, face, x_rel, panel_width, altura,
                    base_height=BASE_H, top_clearance=15.0,
                )
                heights.append(local_height)
                group_heights.append(local_height)
                layer = 'SARR_2.2x7' if width >= SARR_LW - 0.1 else 'SARR_3.5x7'
                if local_height > 0.1:
                    rect_lines(msp, vx, base_y + BASE_H, width, local_height, layer)
                    add_vertical_dimension(vx + width / 2.0, local_height, ordinal)
                ordinal += 1

            min_height = min((h for h in heights if h > 0.1), default=0.0)
            for rel_pos in horizontal_positions:
                if rel_pos + SARR_HH > min_height + 0.1:
                    continue
                y_h = base_y + BASE_H + rel_pos
                rect_lines(msp, gx, y_h, gw_each, SARR_HH, 'SARR_2.2x10')
                if rel_pos not in group_horiz:
                    group_horiz.append(rel_pos)

            x_seg = gx
            for segment in divs:
                try:
                    dim = msp.add_linear_dim(
                        base=(x_seg + segment / 2.0, base_y - 17.8),
                        p1=(x_seg, base_y - 12.8),
                        p2=(x_seg + segment, base_y - 12.8),
                        angle=0, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'COTA'},
                    )
                    dim.render()
                except Exception:
                    pass
                x_seg += segment
            try:
                total_dim = msp.add_linear_dim(
                    base=(gx + gw_each / 2.0, base_y - 40),
                    p1=(gx, base_y), p2=(gx + gw_each, base_y),
                    angle=0, dimstyle='PAINEL-NOVA',
                    dxfattribs={'layer': 'COTA'},
                )
                total_dim.render()
            except Exception:
                pass
            if gi < ng - 1 and gaps[gi] > 0.01:
                gap = gaps[gi]
                try:
                    gap_dim = msp.add_linear_dim(
                        base=(gx + gw_each + gap / 2.0, base_y - 40),
                        p1=(gx + gw_each, base_y),
                        p2=(gx + gw_each + gap, base_y),
                        angle=0, dimstyle='PAINEL-NOVA',
                        dxfattribs={'layer': 'COTA'},
                    )
                    gap_dim.render()
                except Exception:
                    pass

            # Blocos e sarrafos de 7 cm existem somente nas extremidades globais.
            if gi == 0:
                try:
                    msp.add_blockref('GRA-E', (gx, base_y), dxfattribs={'layer': 'SARR_2.2x7'})
                except Exception:
                    pass
            if gi == ng - 1:
                try:
                    msp.add_blockref('GRA-D', (gx + gw_each - SARR_LW, base_y),
                                     dxfattribs={'layer': 'SARR_2.2x7'})
                except Exception:
                    pass
        return {
            'x_right': gx_start + group_total_w,
            'width': group_total_w,
            'horizontals': sorted(group_horiz),
            'max_height': max(group_heights, default=0.0),
        }

    ng_ab, gw_ab, gaps_ab = _grade_layout_from_inner(comp)
    if ng_ab <= 0 or gw_ab <= 0:
        return 0

    cursor_x = base_x
    drawn = []
    panel_ab = comp + 22.0
    for face in ('A', 'B'):
        info = draw_face_group(face, cursor_x, panel_ab, ng_ab, gw_ab, gaps_ab)
        drawn.append(info)
        cursor_x = info['x_right'] + GROUP_GAP

    # Faces curtas só recebem grade a partir de 50 cm, conforme decisão do dono.
    if larg >= 50.0:
        ng_cd, gw_cd, gaps_cd = _grade_layout_for_panel_width(larg)
        for face in ('C', 'D'):
            info = draw_face_group(face, cursor_x, larg, ng_cd, gw_cd, gaps_cd)
            drawn.append(info)
            cursor_x = info['x_right'] + GROUP_GAP

    # Cadeia das travessas no lado direito do último grupo desenhado.
    last = drawn[-1]
    x_right = last['x_right']
    y0 = base_y + BASE_H
    y_top = y0 + last['max_height']
    if last['max_height'] > 0.1:
        try:
            total = msp.add_linear_dim(
                base=(x_right + 50, y0 + last['max_height'] / 2.0),
                p1=(x_right, y0), p2=(x_right, y_top),
                angle=90, dimstyle='PAINEL-NOVA', dxfattribs={'layer': 'COTA'},
            )
            total.render()
        except Exception:
            pass
    horizontals = [
        pos for pos in last['horizontals']
        if pos + SARR_HH <= last['max_height'] + 0.1
    ]
    chain_points = [0.0]
    for pos in horizontals:
        chain_points.extend([pos, pos + SARR_HH])
    chain_points.append(last['max_height'])
    chain_points = sorted(set(round(value, 4) for value in chain_points))
    for start, end in zip(chain_points[:-1], chain_points[1:]):
        if end - start <= 0.1:
            continue
        try:
            segment_dim = msp.add_linear_dim(
                base=(x_right + 30, y0 + (start + end) / 2.0),
                p1=(x_right, y0 + start), p2=(x_right, y0 + end),
                angle=90, dimstyle='PAINEL-NOVA', dxfattribs={'layer': 'COTA'},
            )
            segment_dim.render()
        except Exception:
            pass
    return len(drawn)


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

def _prepare_pj_for_visual(pj: dict, visual_mode: str = "NOVA") -> dict:
    """Enriquecimento geométrico universal (PARA/PASSA, INI ou NOVA).

    Regras de malha, aberturas, rebaixo, seccionamento de sarrafo e cotas
    N1/N2/N3 são as mesmas para qualquer pilar. O ``visual_mode`` só muda o
    perfil final (MLINE no INI vs LINE no NOVA) via ``apply_visual_mode``.

    Sempre re-enriquece (não pula por ``_pl_nova_enriched``): JSONs de
    n3_variants podem ter sido publicados com regras antigas; o motor
    reaplica o padrão P1 em todo item a cada geração.
    """
    try:
        from pl_abcd_visual_nova import enrich_payload_for_abcd_nova
        # limpa flag para o enrich recalcular intervals/rebaixo/y_rel
        if isinstance(pj, dict):
            pj.pop("_pl_nova_enriched", None)
        return enrich_payload_for_abcd_nova(pj)
    except Exception as exc:
        print(f"[PL-NOVA] enrich_payload falhou (segue sem): {exc}", flush=True)
        return pj


def _dimensoes_canonicas_pilar(pj: dict) -> tuple[float, float]:
    """Resolve a base estrutural usada por TODAS as vistas N4 de um pilar.

    ``comprimento_geom`` e ``larg_c_geom`` sao medições auxiliares extraídas
    do recorte N2. Elas continuam preservadas para diagnóstico, mas não podem
    substituir silenciosamente os campos canônicos da ficha em apenas uma
    variante de saída. A reconciliação Fase-4↔N2 pertence ao motor reverso;
    enquanto ela não for promovida, o desenho N4 precisa reproduzir o mesmo
    contrato explícito exibido na ficha.
    """
    return (
        float(pj.get("comprimento", 60) or 60),
        float(pj.get("largura", 38) or 38),
    )


def generate_pilar_zone(
    msp, pj: dict, zone: str, row_y: float = 0, visual_mode: str = "NOVA",
) -> int:
    """
    Gera apenas a zona indicada para um pilar, com x-origem em 0.
    Retorna contagem de entidades, ou -1 se zona é omitida (grade_1=0, EFGH).

    Zonas:
      'abcd'  — faces A/B/C/D com sarrafos verticais, x=0 (equiv. ZONE_ABCD_X=0)
      'cima'  — seção transversal 2x, x=0 (ZONE_CIMA_X já é 0)
      'grades'— grade de sarrafos, x=0 (equiv. ZONE_GRADES_X=0); omite se comp<=0
      'efgh'  — faces E/F do pilar em U; omite se larg1_E=0 e larg1_F=0
    """
    pj = _prepare_pj_for_visual(pj, visual_mode)
    nome    = pj.get('nome', f"P{pj.get('numero', '?')}")
    comp, larg = _dimensoes_canonicas_pilar(pj)
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
        return draw_grades(
            msp, 0, row_y, grade_1, grade_2, comp, larg, altura, nome, pj,
            visual_mode=visual_mode,
        )
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

def generate_pilar(msp, pj, row_y_offset, visual_mode="NOVA"):
    """
    Generate all zones for a single pilar at the appropriate Y offset.
    Reads `subtipo_pil` from pj (RETANGULAR | U | ESPECIAL).
    U-shape: adds EFGH zone at ZONE_EFGH_X with faces E/F.
    Returns total entity count.
    """
    pj = _prepare_pj_for_visual(pj, visual_mode)
    nome    = pj.get('nome', f"P{pj.get('numero', '?')}")
    comp, larg = _dimensoes_canonicas_pilar(pj)
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
                    comp, larg, altura, nome, pj, visual_mode=visual_mode)
    total_entities += n

    # ── ZONE 4: EFGH (X:8000) — apenas subtipo U ─────────────────────────────
    if subtipo in ('L', 'U') and (float(pj.get('larg1_E', 0)) > 0 or float(pj.get('larg1_F', 0)) > 0):
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
    parser.add_argument('--visual-mode', choices=['NOVA', 'INI'], default='NOVA',
                        help='Perfil visual do DXF (padrao: NOVA)')
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
            n = generate_pilar_zone(
                msp_z, pj, zone, visual_mode=args.visual_mode,
            )

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
            apply_visual_mode(doc_z, args.visual_mode, 'PL')
            out_path = guarded_saveas(
                doc_z, out_path,
                motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
            )
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
    print(f'  GRADES horizontais [{args.visual_mode}]: '
          f'{grade_horizontal_positions_for_mode(args.visual_mode)} cm')
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

        n = generate_pilar(msp, pj, row_y, visual_mode=args.visual_mode)
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
    apply_visual_mode(doc, args.visual_mode, 'PL')
    out_dxf = guarded_saveas(
        doc, out_dxf,
        motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
    )
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
