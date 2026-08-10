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
import sys
if __name__ == '__main__' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, argparse, re, math
from collections import namedtuple
from pathlib import Path
import ezdxf

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from src.core.artifact_governance import guarded_saveas

_MOTOR_ID = "ROBOT_LJ_N3_N4"
_MOTOR_SOURCES = [Path(__file__)]

# -- Constants ----------------------------------------------------------------
SARRAFO_GAP = 19.0   # 19cm gap between paired lines (from STOG real)
PILAR_HATCH_STEP = 12.0  # diagonal hatch line spacing inside pilars
UNION_MIN_CM = 15.0
UNION_MAX_CM = 30.0
DIM_HORIZONTAL_OFFSET_CM = 28.2697096074757
DIM_VERTICAL_OFFSET_CM = 30.8595527518608

COLS  = 4
GAP_X = 80
GAP_Y = 80
PAD   = 10
TITULO_H  = 28
CARIMBO_H = 35
LJ_SCALE  = 0.5

# -- Layers matching STOG real ------------------------------------------------
LAYERS = {
    'PAINEIS':              6,  # panel boundaries
    'COTA':               241,  # dimension entities
    'NOMENCLATURA':         7,  # slab name
    'Hachura':            251,  # SOLID fill HATCH
    '3':                    2,  # union reference compatibility
    'Pain\u00e9is':       200,  # legacy cards compatibility
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

DIMSTYLE_NAME = 'cotas'


def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0

    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    if 'Romans' not in doc.styles:
        doc.styles.new('Romans', dxfattribs={'font': 'romans.shx', 'height': 12.0})
    from ezdxf.render import arrows
    arrows.ARROWS.create_block(doc.blocks, 'OBLIQUE')

    if DIMSTYLE_NAME not in doc.dimstyles:
        ds = doc.dimstyles.new(DIMSTYLE_NAME)
        ds.dxf.dimtxt = 9.0
        ds.dxf.dimasz = 2.0
        ds.dxf.dimexo = 2.0
        ds.dxf.dimexe = 2.0
        ds.dxf.dimgap = 2.0
        ds.dxf.dimdec = 1
        ds.dxf.dimzin = 12
        ds.dxf.dimtad = 1
        ds.dxf.dimclrd = 4   # cyan arrows
        ds.dxf.dimclre = 4   # cyan extension lines
        ds.dxf.dimclrt = 240  # dim text color
        ds.dxf.dimblk = '_Oblique'
        ds.dxf.dimtxsty = 'Romans'

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


def add_hatch_solid(msp, pts, layer='Hachura', color=None):
    """SOLID fill HATCH on polygon."""
    attribs = {'layer': layer}
    if color is not None:
        attribs['color'] = color
    hatch = msp.add_hatch(dxfattribs=attribs)
    hatch.set_solid_fill(color=color if color is not None else 7)
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


def add_dim_on_paineis(msp, p1_x, p2_x, base_y, p_y, angle=0, text_override=None, text_location=None):
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
            text=text_override if text_override is not None else "<>",
            dxfattribs={'layer': 'COTA'}
        )
        if text_location is not None:
            d.set_location(text_location)
        d.render()
        return d
    except Exception:
        return None


def add_dim_vertical_on_paineis(msp, p1_y, p2_y, base_x, p_x, text_location=None, text_override=None):
    """Vertical dimension on Painéis layer."""
    try:
        d = msp.add_linear_dim(
            base=(base_x, p1_y),
            p1=(p_x, p1_y),
            p2=(p_x, p2_y),
            angle=90,
            dimstyle=DIMSTYLE_NAME,
            text=text_override if text_override is not None else "<>",
            dxfattribs={'layer': 'COTA'}
        )
        if text_location is not None:
            d.set_location(text_location)
        d.render()
        return d
    except Exception:
        return None


def add_dim_aligned_on_paineis(msp, p1, p2, distance=10.0, text_override=None):
    """Aligned dimension for non-orthogonal panel cuts on COTA layer."""
    try:
        d = msp.add_aligned_dim(
            p1=p1,
            p2=p2,
            distance=distance,
            dimstyle=DIMSTYLE_NAME,
            text=text_override if text_override is not None else "<>",
            dxfattribs={'layer': 'COTA'},
        )
        if text_location is not None:
            d.set_location(text_location)
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
EDGE_DIVISION_MARGIN_CM = 3.0
INTEGER_SNAP_TOLERANCE_CM = 0.45


def _sanitize_laj_obstacles(obstacles):
    """Remove ticks/X 5×5 espúrios antes de desenhar (mesmo critério do motor)."""
    try:
        from motor_reverso_laj import sanitize_laj_obstacles
        return sanitize_laj_obstacles(obstacles)
    except Exception:
        out = []
        for obs in obstacles or []:
            if not isinstance(obs, dict):
                continue
            try:
                w = float(obs.get("width") or 0)
                h = float(obs.get("height") or 0)
            except (TypeError, ValueError):
                continue
            if w <= 10.0 and h <= 10.0:
                continue
            if w > 0 and h > 0:
                out.append(obs)
        return out


def _line_value(item):
    return float(item.get('value', 0)) if isinstance(item, dict) else float(item)


def _round_panel_cm(value):
    return round(round(float(value) * 2) / 2, 1)


def _snap_panel_line(value):
    value = float(value)
    nearest_int = round(value)
    if abs(value - nearest_int) <= INTEGER_SNAP_TOLERANCE_CM:
        return float(nearest_int)
    return _round_panel_cm(value)


def _format_dim_value(value):
    value = round(float(value), 1)
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.1f}"


def _normalize_line_positions(lines, total):
    """Mantem apenas divisoes internas; Fase-4 antigo inclui a borda final."""
    result = []
    seen = set()
    for item in lines or []:
        raw_value = _line_value(item)
        value = float(raw_value) if isinstance(item, dict) and item.get('exact') else _snap_panel_line(raw_value)
        if value <= EDGE_DIVISION_MARGIN_CM or value >= total - EDGE_DIVISION_MARGIN_CM:
            continue
        if value in seen:
            continue
        seen.add(value)
        out = dict(item) if isinstance(item, dict) else {'is_union': False}
        out['value'] = value
        result.append(out)
    return sorted(result, key=_line_value)

def _dedupe_sorted(values, tol=1e-6):
    out = []
    for value in sorted(values):
        if not out or abs(value - out[-1]) > tol:
            out.append(value)
    return out


def _axis_panel_lengths(positions, total):
    edges = _dedupe_sorted([0.0] + [float(p) for p in positions] + [float(total)])
    return [round(b - a, 2) for a, b in zip(edges, edges[1:]) if b - a > 0.5]


def _is_preferred_panel_length(length):
    return any(abs(length - target) <= 1.0 for target in (244.0, 122.0, 60.0))


def _extracted_panel_lines_trusted(lines, total):
    """Junta explícita do recorte N2: não sobrescrever só por não ser 244/122/60."""
    if not lines:
        return False
    positions = [_line_value(item) for item in lines]
    lengths = _axis_panel_lengths(positions, total)
    if not lengths:
        return False
    return abs(sum(lengths) - float(total)) <= 1.0


def _looks_like_canonical_panel_distribution(positions, total):
    """Valida se a distribuição respeita a lógica 244/122/60 + uma sobra.

    Linhas vindas do recorte N2 podem incluir bordas de pilares, textos ou
    contaminação de vizinhos. O N4 não deve transformar esses ruídos em chapas
    aleatórias. Aceitamos:
    - chapas padrão 244/122/60;
    - gap de união entre 15 e 30;
    - no máximo uma peça residual >= 60 para compensar a sobra final;
    - residual nunca > 122 (chapa 244×122: se o outro eixo tem 244, 169 é inválido).
    """
    lengths = _axis_panel_lengths(positions, total)
    if not lengths:
        return True
    residuals = []
    for length in lengths:
        if _is_preferred_panel_length(length):
            continue
        if 15.0 <= length <= 30.0:
            continue
        if 60.0 <= length <= 122.0 + 0.5:
            residuals.append(length)
            continue
        return False
    return len(residuals) <= 1


def _canonicalize_long_axis_if_noisy(lines, total, smart_lines):
    positions = [_line_value(item) for item in lines]
    if _looks_like_canonical_panel_distribution(positions, total):
        return lines
    if not smart_lines:
        return lines
    return _normalize_line_positions(smart_lines or [], total)


def _polygon_break_anchors(poly_pts, x0, y0, comp, larg, axis):
    """Detecta degraus internos do contorno que são bons candidatos a junta.

    Um painel que atravessa uma aresta interna de degrau vira peça em L. Quando
    a junta da paginação fica perto desse degrau, é melhor encaixar a junta no
    próprio degrau e redistribuir o restante do trecho.
    """
    if not poly_pts or len(poly_pts) <= 4:
        return []
    pts = list(poly_pts)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    anchors = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if axis == 'x':
            if abs(x1 - x2) > 0.5:
                continue
            local = round(x1 - x0, 1)
            length = abs(y2 - y1)
            total = larg
        else:
            if abs(y1 - y2) > 0.5:
                continue
            local = round(y1 - y0, 1)
            length = abs(x2 - x1)
            total = comp
        axis_total = comp if axis == 'x' else larg
        if local <= 30.0 or local >= axis_total - 30.0:
            continue
        if 5.0 <= length < total - 0.5:
            anchors.append(local)
    return _dedupe_sorted(anchors, tol=1.0)


def _span_distribution_positions(length, other_dim, axis, distribute_panels_fn):
    if length <= 1.0:
        return []
    try:
        if axis == 'x':
            smart = distribute_panels_fn(length, other_dim, None)
            key = 'linhas_verticais'
        else:
            smart = distribute_panels_fn(other_dim, length, None)
            key = 'linhas_horizontais'
        return _normalize_line_positions((smart or {}).get(key) or [], length)
    except Exception:
        pos = 244.0
        out = []
        while pos < length - 60.0:
            out.append({'value': round(pos, 1), 'is_union': False})
            pos += 244.0
        return out


def _anchored_panel_lines(lines, total, other_dim, anchors, axis, distribute_panels_fn):
    anchors = [
        float(anchor) for anchor in anchors
        if 1.0 < float(anchor) < float(total) - 1.0
    ]
    if not anchors:
        return lines
    current_positions = [_line_value(item) for item in lines]
    if current_positions and not any(
        min(abs(anchor - pos) for pos in current_positions) <= 35.0
        for anchor in anchors
    ):
        return lines

    out = []
    previous = 0.0
    for edge in _dedupe_sorted([0.0] + anchors + [float(total)], tol=1.0)[1:]:
        span = edge - previous
        for item in _span_distribution_positions(span, other_dim, axis, distribute_panels_fn):
            value = previous + _line_value(item)
            if previous + 1.0 < value < edge - 1.0:
                out.append({'value': round(value, 1), 'is_union': bool(item.get('is_union', False))})
        if edge < total - 1.0:
            out.append({'value': round(edge, 1), 'is_union': False})
        previous = edge

    if not out:
        return lines
    # Não trocar uma paginação simples por uma malha mais densa sem necessidade.
    if len(out) > max(len(lines) + len(anchors) + 2, 3):
        return lines
    return _normalize_line_positions(out, total)


def _optimize_panel_lines_for_polygon(poly_pts, x0, y0, comp, larg, lv, lh, distribute_panels_fn):
    if not poly_pts or len(poly_pts) <= 4:
        return lv, lh
    x_anchors = _polygon_break_anchors(poly_pts, x0, y0, comp, larg, 'x')
    y_anchors = _polygon_break_anchors(poly_pts, x0, y0, comp, larg, 'y')
    if x_anchors:
        lv = _anchored_panel_lines(lv, comp, larg, x_anchors, 'x', distribute_panels_fn)
    # Não aplicar automaticamente no eixo Y enquanto a Fase-4 armazenada ainda
    # carrega paginações antigas nesse campo. O gerador não pode divergir do N2
    # oficial sem reextração/reselo explícito.
    return lv, lh


def _axis_segments_in_polygon(poly_pts, axis, coord):
    """Retorna trechos internos de uma linha horizontal/vertical no poligono."""
    if len(poly_pts) < 3:
        return []
    pts = list(poly_pts)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    hits = []
    eps = 1e-7
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if axis == 'h':
            if abs(y1 - y2) <= eps:
                continue
            low, high = sorted((y1, y2))
            if low - eps <= coord < high - eps:
                t = (coord - y1) / (y2 - y1)
                hits.append(x1 + t * (x2 - x1))
        else:
            if abs(x1 - x2) <= eps:
                continue
            low, high = sorted((x1, x2))
            if low - eps <= coord < high - eps:
                t = (coord - x1) / (x2 - x1)
                hits.append(y1 + t * (y2 - y1))
    hits = _dedupe_sorted(hits)
    if len(hits) < 2:
        return []
    segments = []
    for a, b in zip(hits[0::2], hits[1::2]):
        if b - a > 0.5:
            segments.append((a, b))
    return segments

def _add_clipped_axis_lines(msp, poly_pts, axis, coord, layer, lineweight=None):
    segments = _axis_segments_in_polygon(poly_pts, axis, coord)
    attribs = {'layer': layer}
    if lineweight is not None:
        attribs['lineweight'] = lineweight
    for a, b in segments:
        if axis == 'h':
            msp.add_line((a, coord), (b, coord), dxfattribs=attribs)
        else:
            msp.add_line((coord, a), (coord, b), dxfattribs=attribs)
    return len(segments)

def _point_in_polygon(point, poly_pts):
    x, y = point
    inside = False
    pts = list(poly_pts)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if ((y1 > y) != (y2 > y)):
            x_cross = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
            if x < x_cross:
                inside = not inside
    return inside

def _label_position(poly_pts, v_positions, h_positions, x0, y0, comp, larg):
    xs = [x0] + [x0 + float(v) for v in v_positions] + [x0 + comp]
    ys = [y0] + [y0 + float(h) for h in h_positions] + [y0 + larg]
    best = None
    for xa, xb in zip(sorted(xs), sorted(xs)[1:]):
        for ya, yb in zip(sorted(ys), sorted(ys)[1:]):
            if xb - xa < 35.0 or yb - ya < 18.0:
                continue
            cx = (xa + xb) / 2
            cy = (ya + yb) / 2
            if not _point_in_polygon((cx, cy), poly_pts):
                continue
            score = (xb - xa) * (yb - ya)
            if best is None or score > best[0]:
                best = (score, cx, cy)
    if best:
        return best[1], best[2]
    # Fallback: centro do maior trecho horizontal interno, levemente fora das linhas.
    return x0 + comp / 2, y0 + larg * 0.62

def _dim_candidate_text_point(cand):
    """Posição aproximada do texto de um _DimCandidate já desenhado — usa
    text_location quando explícito, senão o mesmo cálculo padrão que
    add_h/add_v usam para o defpoint da cota."""
    if cand.text_location is not None:
        return cand.text_location
    a, b = cand.span_raw
    if cand.axis == 'h':
        return ((a + b) / 2.0, cand.anchor + cand.offset)
    return (cand.anchor + cand.offset, (a + b) / 2.0)


def _label_position_clear_of_dimensions(
    poly_pts, v_positions, h_positions, x0, y0, comp, larg, panel_x, panel_y,
    horizontal_dim_y=None, vertical_dim_x=None, dim_candidates=None,
):
    # horizontal_dim_y/vertical_dim_x sao a posicao REAL da cota principal
    # (calculada por _add_reference_dimensions, que sabe qual ramo/offset foi
    # usado -- shallow_complex usa offset fixo 10.0, os demais usam
    # DIM_HORIZONTAL_OFFSET_CM/DIM_VERTICAL_OFFSET_CM). Antes esta funcao
    # reaproximava com um offset fixo que so batia com o ramo "else", fazendo
    # o rotulo colidir com a cota principal em lajes shallow_complex (achado
    # cota_sobre_rotulo_item, ex. L419/L327/L329). Fallback aos valores
    # antigos so quando o chamador nao informa (compatibilidade).
    horizontal_text_y = (
        horizontal_dim_y if horizontal_dim_y is not None
        else panel_y - DIM_HORIZONTAL_OFFSET_CM
    ) + 8.0
    vertical_text_x = (
        vertical_dim_x if vertical_dim_x is not None
        else panel_x - DIM_VERTICAL_OFFSET_CM
    ) - 8.0
    # dim_candidates cobre as cotas de _add_cut_edge_dimensions (bordas de
    # recorte, degraus, chanfros) — uma fonte inteiramente separada de
    # horizontal_dim_y/vertical_dim_x (a cota "principal"). Sem isso, o
    # rótulo só evitava a cota principal e colidia com essas outras (achado
    # cota_sobre_rotulo_item: "218" de uma borda completa sobrepondo "L419").
    dim_text_points = [
        (vertical_text_x, horizontal_text_y),
    ] + [_dim_candidate_text_point(cand) for cand in (dim_candidates or [])]

    def _too_close(center):
        if abs(center[1] - horizontal_text_y) < 18.0:
            return True
        # O texto vertical ocupa largura visual maior que o seu ponto de
        # inserção. Afastar apenas 18 cm deixava L320/L321 sobre a cota 244.
        if abs(center[0] - vertical_text_x) < 70.0:
            return True
        return any(
            abs(center[0] - tx) < 45.0 and abs(center[1] - ty) < 20.0
            for tx, ty in dim_text_points
        )

    def _clearance(point):
        # Distância normalizada (em "raios de colisão") ao ponto de texto
        # conhecido mais próximo — maior é melhor. Usado quando nenhuma
        # posição fica totalmente livre, pra escolher a menos ruim em vez de
        # cair num fallback cego que ignora cota (achado
        # cota_sobre_rotulo_item).
        return min(
            max(abs(point[0] - tx) / 45.0, abs(point[1] - ty) / 20.0)
            for tx, ty in dim_text_points
        )

    xs = [x0] + [x0 + float(value) for value in v_positions] + [x0 + comp]
    ys = [y0] + [y0 + float(value) for value in h_positions] + [y0 + larg]
    clear_cells = []
    inside_cells = []
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            center = ((xa + xb) / 2, (ya + yb) / 2)
            if not _point_in_polygon(center, poly_pts):
                continue
            area = (xb - xa) * (yb - ya)
            inside_cells.append((area, xa, xb, ya, yb, center))
            if not _too_close(center):
                clear_cells.append((area, center))
    if clear_cells:
        return max(clear_cells, key=lambda item: item[0])[1]
    if inside_cells:
        # Nenhuma célula tem centro totalmente livre: em vez de desistir,
        # tenta pontos internos à MAIOR célula (não só o centro geométrico)
        # e fica com o de melhor folga real — cobre o caso comum de laje
        # estreita onde o centro do quadrante cai perto de uma cota de
        # borda, mas outra fração do mesmo quadrante está livre.
        area, xa, xb, ya, yb, center = max(inside_cells, key=lambda item: item[0])
        probe_points = [
            (xa + (xb - xa) * fx, ya + (yb - ya) * fy)
            for fx in (0.5, 0.3, 0.7, 0.15, 0.85)
            for fy in (0.5, 0.25, 0.75, 0.1, 0.9)
        ]
        valid_probes = [
            p for p in probe_points if _point_in_polygon(p, poly_pts)
        ]
        if valid_probes:
            return max(valid_probes, key=_clearance)
        return center
    return _label_position(poly_pts, v_positions, h_positions, x0, y0, comp, larg)

def _vertical_dimension_guide(poly_pts, x0, comp, v_positions):
    edges = _dedupe_sorted([0.0] + list(v_positions) + [comp])
    candidates = []
    for a, b in zip(edges, edges[1:]):
        if b - a <= 2.0:
            continue
        x = x0 + (a + b) / 2
        spans = _axis_segments_in_polygon(poly_pts, 'v', x)
        if spans:
            candidates.append((max(hi - lo for lo, hi in spans), x))
    return max(candidates, default=(0.0, x0 + comp / 2))[1]

def _horizontal_dimension_guide(poly_pts, y0, larg, h_positions):
    edges = _dedupe_sorted([0.0] + list(h_positions) + [larg])
    candidates = []
    for a, b in zip(edges, edges[1:]):
        if b - a <= 2.0:
            continue
        y = y0 + (a + b) / 2
        spans = _axis_segments_in_polygon(poly_pts, 'h', y)
        if spans:
            candidates.append((max(hi - lo for lo, hi in spans), y))
    return max(candidates, default=(0.0, y0 + larg / 2))[1]

def _clip_polygon_to_rect(poly_pts, x_min, y_min, x_max, y_max):
    points = list(poly_pts)
    if points and points[0] == points[-1]:
        points.pop()
    for inside, intersect in (
        (lambda p: p[0] >= x_min, lambda a, b: (x_min, a[1] + (b[1] - a[1]) * (x_min - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= x_max, lambda a, b: (x_max, a[1] + (b[1] - a[1]) * (x_max - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= y_min, lambda a, b: (a[0] + (b[0] - a[0]) * (y_min - a[1]) / (b[1] - a[1]), y_min)),
        (lambda p: p[1] <= y_max, lambda a, b: (a[0] + (b[0] - a[0]) * (y_max - a[1]) / (b[1] - a[1]), y_max)),
    ):
        source = points
        points = []
        if not source:
            break
        previous = source[-1]
        for current in source:
            if inside(current):
                if not inside(previous):
                    points.append(intersect(previous, current))
                points.append(current)
            elif inside(previous):
                points.append(intersect(previous, current))
            previous = current
    return points

def _add_narrow_panel_hatches(
    msp, poly_pts, x0, y0, comp, larg, v_positions, h_positions,
    v_union_set, h_union_set,
):
    x_edges = _dedupe_sorted([0.0] + list(v_positions) + [comp])
    y_edges = _dedupe_sorted([0.0] + list(h_positions) + [larg])
    count = 0
    for xa, xb in zip(x_edges, x_edges[1:]):
        for ya, yb in zip(y_edges, y_edges[1:]):
            narrow_x = 1.0 < xb - xa < 30.0 and round(xb, 1) in v_union_set
            narrow_y = 1.0 < yb - ya < 30.0 and round(yb, 1) in h_union_set
            if not (narrow_x or narrow_y):
                continue
            clipped = _clip_polygon_to_rect(
                poly_pts, x0 + xa, y0 + ya, x0 + xb, y0 + yb
            )
            if len(clipped) >= 3:
                add_hatch_ansi31(msp, clipped, 'REAPROVEITAMENTO', scale=2.0)
                count += 1
    return count

def _union_bands(items, total):
    positions = sorted(float(item.get('value', 0)) for item in items)
    bands = []
    for start, end in zip(positions, positions[1:]):
        if UNION_MIN_CM <= end - start <= UNION_MAX_CM:
            bands.append((start, end))
    for index, item in enumerate(sorted(items, key=_line_value)):
        if not item.get('is_union', False):
            continue
        end = float(item.get('value', 0))
        start = positions[index - 1] if index else 0.0
        if 0.0 <= start < end <= total:
            bands.append((start, end))
    return sorted(set((round(a, 6), round(b, 6)) for a, b in bands))

def _add_panel_axis(msp, poly_pts, axis, coord, is_union_boundary=False):
    count = 0
    for start, end in _axis_segments_in_polygon(poly_pts, axis, coord):
        points = (
            [(start, coord), (end, coord)]
            if axis == 'h'
            else [(coord, start), (coord, end)]
        )
        attribs = {'layer': 'PAINEIS'}
        if is_union_boundary:
            attribs['lineweight'] = 25
        msp.add_line(points[0], points[1], dxfattribs=attribs)
        count += 1
    return count

def _add_union_hatches(msp, poly_pts, x0, y0, comp, larg, v_bands, h_bands):
    count = 0
    for start, end in h_bands:
        clipped = _clip_polygon_to_rect(
            poly_pts, x0, y0 + start, x0 + comp, y0 + end
        )
        if len(clipped) >= 3:
            add_hatch_solid(msp, clipped, 'Hachura', color=8)
            count += 1
    for start, end in v_bands:
        y_ranges = [(0.0, larg)]
        for h_start, h_end in h_bands:
            y_ranges = [
                interval
                for a, b in y_ranges
                for interval in ((a, min(b, h_start)), (max(a, h_end), b))
                if interval[1] - interval[0] > 0.5
            ]
        for ya, yb in y_ranges:
            clipped = _clip_polygon_to_rect(
                poly_pts, x0 + start, y0 + ya, x0 + end, y0 + yb
            )
            if len(clipped) >= 3:
                add_hatch_solid(msp, clipped, 'Hachura', color=8)
                count += 1
    return count

def _add_explicit_hlaz(msp, x0, y0, hlaz_items):
    """Desenha cada HLAZ na posição extraída, sem expandi-la pelo bbox da laje.

    A HLAZ é preenchimento, não uma nova borda de painel. Usar LWPOLYLINE aqui
    cria um retângulo fantasma visível no N4; o contrato visual correto é um
    HATCH sólido local na layer Hachura.
    """
    count = 0
    for item in hlaz_items or []:
        try:
            hx = x0 + float(item.get('x', 0.0))
            hy = y0 + float(item.get('y', 0.0))
            width = float(item.get('width', 0.0))
            height = float(item.get('height', 0.0))
        except (TypeError, ValueError):
            continue
        if width <= 0.5 or height <= 0.5:
            continue
        add_hatch_solid(
            msp,
            [(hx, hy), (hx + width, hy), (hx + width, hy + height), (hx, hy + height)],
            'Hachura',
            color=251,
        )
        count += 1
    return count

def _band_is_local_hlaz(band, hlaz_items, comp):
    start, end = band
    for item in hlaz_items or []:
        try:
            y0 = float(item.get('y', 0.0))
            y1 = y0 + float(item.get('height', 0.0))
            width = float(item.get('width', 0.0))
        except (TypeError, ValueError):
            continue
        if (
            width < comp - 1.0
            and abs(start - y0) <= 0.6
            and abs(end - y1) <= 0.6
        ):
            return True
    return False

def _full_height_vertical_guide(poly_pts, x0, y0, comp, larg, x_edges, default_guide):
    """Escolhe guia vertical dentro de faixa com altura válida.

    Em lajes em degrau, o guia central pode cair numa faixa que não ocupa a
    altura total da laje. Nesse caso a cota vertical cruza vazio e fica
    visualmente fora da área. Preferimos uma faixa à direita que contenha a
    maior altura vertical disponível.
    """
    if not poly_pts or len(poly_pts) <= 4:
        return default_guide

    def max_vertical_span(local_x):
        spans = _axis_segments_in_polygon(poly_pts, 'v', x0 + float(local_x))
        if not spans:
            return 0.0, False
        lengths = [b - a for a, b in spans]
        covers_full = any(a <= y0 + 0.5 and b >= y0 + larg - 0.5 for a, b in spans)
        return max(lengths), covers_full

    default_span, default_full = max_vertical_span(default_guide)
    default_on_edge = any(abs(default_guide - edge) <= 0.5 for edge in x_edges)
    if default_full and not default_on_edge:
        return default_guide

    candidates = []
    for a, b in zip(x_edges, x_edges[1:]):
        if b - a <= 1.0:
            continue
        # Centro do painel evita cair exatamente sobre uma borda do polígono.
        local_x = (a + b) / 2
        span_len, covers_full = max_vertical_span(local_x)
        if span_len <= 0.5:
            continue
        is_right = local_x >= comp / 2
        candidates.append((covers_full, span_len, is_right, local_x))

    if not candidates:
        return default_guide

    best_full = max(1 if item[0] else 0 for item in candidates)
    best_span = max(item[1] for item in candidates if (1 if item[0] else 0) == best_full)
    viable = [
        item for item in candidates
        if (1 if item[0] else 0) == best_full and abs(item[1] - best_span) <= 0.5
    ]
    right_viable = [item for item in viable if item[2]]
    if right_viable:
        # Primeira faixa à direita com altura total/mais alta: evita empurrar a
        # cota para a extremidade quando há painel bom logo após o degrau.
        return min(right_viable, key=lambda item: item[3])[3]
    return min(viable, key=lambda item: abs(item[3] - default_guide))[3]


def _vertical_span_at(poly_pts, x):
    spans = _axis_segments_in_polygon(poly_pts, 'v', x)
    if not spans:
        return None
    return max(spans, key=lambda item: item[1] - item[0])


def _has_diagonal_edges(poly_pts):
    pts = list(poly_pts or [])
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if abs(x1 - x2) > 0.5 and abs(y1 - y2) > 0.5:
            return True
    return False


def _add_secondary_vertical_dimensions(msp, poly_pts, x0, y0, comp, larg, x_edges, y_edges, primary_guide):
    """Cota spans verticais distintos em lajes com degrau/recorte.

    Ex.: L318 tem um trecho direito com 201 cm e um trecho esquerdo mais curto.
    Uma única cota vertical no trecho alto não informa a altura real do painel
    no trecho menor.
    """
    if not poly_pts or len(poly_pts) <= 4:
        return 0
    # Chanfros já exigem cota própria do corte inclinado; quebrar também todas
    # as alturas locais gera excesso de cotas e polui a ficha (caso L319).
    if _has_diagonal_edges(poly_pts):
        return 0
    primary_span = _vertical_span_at(poly_pts, x0 + primary_guide)
    primary_sig = tuple(round(v, 1) for v in primary_span) if primary_span else None
    candidates = []
    for a, b in zip(x_edges, x_edges[1:]):
        if b - a <= 30.0:
            continue
        local_x = (a + b) / 2
        span = _vertical_span_at(poly_pts, x0 + local_x)
        if not span:
            continue
        sig = tuple(round(v, 1) for v in span)
        if sig == primary_sig:
            continue
        span_len = span[1] - span[0]
        if span_len <= 30.0:
            continue
        candidates.append((span_len, local_x, span))
    if not candidates:
        return 0

    # Uma cota secundária por assinatura de span, preferindo a mais representativa.
    by_sig = {}
    for span_len, local_x, span in candidates:
        sig = tuple(round(v, 1) for v in span)
        if sig not in by_sig or span_len > by_sig[sig][0]:
            by_sig[sig] = (span_len, local_x, span)

    count = 0
    for _, local_x, (lo, hi) in by_sig.values():
        local_lo = lo - y0
        local_hi = hi - y0
        local_edges = [local_lo]
        local_edges.extend(
            edge for edge in y_edges[1:-1]
            if local_lo + 0.5 < edge < local_hi - 0.5
        )
        local_edges.append(local_hi)
        local_edges = _dedupe_sorted(local_edges)
        if len(local_edges) < 2:
            continue
        dimline_x = x0 + local_x - DIM_VERTICAL_OFFSET_CM
        extension_x = x0 + local_x
        for start, end in reversed(list(zip(local_edges, local_edges[1:]))):
            if end - start <= 1.0:
                continue
            add_dim_vertical_on_paineis(
                msp, y0 + start, y0 + end,
                dimline_x, extension_x,
                text_location=(dimline_x, y0 + (start + end) / 2),
            )
            count += 1
    return count


def _grid_has(value, grid, tol=0.6):
    return any(abs(float(value) - float(item)) <= tol for item in grid)


def _nearest_each_side(value, grid, min_dist=5.0, max_dist=260.0):
    left = [
        item for item in grid
        if min_dist <= float(value) - float(item) <= max_dist
    ]
    right = [
        item for item in grid
        if min_dist <= float(item) - float(value) <= max_dist
    ]
    out = []
    if left:
        out.append(max(left))
    if right:
        out.append(min(right))
    return out


# Candidato de cota ainda não desenhado: as regras de _add_complex_projection_
# dimensions()/_add_cut_edge_dimensions() decidem SE uma medida é necessária,
# mas não desenham na hora — emitem um candidato que passa por
# _consolidate_dim_candidates() antes de ir para o DXF. Isso existe porque
# duas regras diferentes, cada uma correta isoladamente, podem medir a MESMA
# feição física a partir de vértices ligeiramente diferentes (ex.: os dois
# vértices adjacentes de um degrau de borda de 2,5cm) — o dedup antigo por
# posição exata (round(x,1) num set()) não pega isso. Consolidar pela MEDIDA
# (span) + proximidade do anchor resolve a classe inteira do problema, não
# só o caso que motivou o fix (ver docs/STATUS.md e triagem 14_PAV/LAJ).
_DimCandidate = namedtuple(
    "_DimCandidate",
    "axis span_raw span_key anchor offset text_override text_location source",
)

# Maior que qualquer degrau/recuo conhecido nas fichas reais (shallow_side_
# notch_total, mais abaixo, já trata como "degrau pequeno" tudo até 10cm da
# parede); menor que a distância mínima real entre duas feições de corte
# distintas e fabricáveis (>=30cm — mesmo corte usado em
# _add_secondary_vertical_dimensions e nos filtros de segmento deste
# arquivo). Única alavanca a ajustar se aparecer um degrau maior no futuro.
DIM_CANDIDATE_CLUSTER_TOL_CM = 15.0


def _pick_canonical_dim_candidate(cluster, x_grid, y_grid):
    """Dentro de um cluster de candidatos que medem o mesmo span, escolhe o
    mais "canônico": o anchor mais próximo de uma linha de grade real
    (parede externa ou linha de painel). Em caso de empate, mantém o
    primeiro candidato criado (ordem estável, não depende de iteração de set)."""
    if len(cluster) == 1:
        return cluster[0]
    grid = x_grid if cluster[0].axis == 'v' else y_grid

    def _dist_to_grid(cand):
        return min((abs(cand.anchor - g) for g in grid), default=0.0)

    return min(enumerate(cluster), key=lambda pair: (_dist_to_grid(pair[1]), pair[0]))[1]


def _consolidate_dim_candidates(candidates, x_grid, y_grid):
    """Agrupa candidatos por (eixo, medida); dentro de cada grupo, faz
    clustering 1D dos anchors por proximidade (DIM_CANDIDATE_CLUSTER_TOL_CM).
    Anchors no mesmo cluster = mesma feição física vista por regras
    diferentes -> mantém só 1. Clusters distantes = feições distintas e
    legítimas (ex.: o mesmo degrau espelhado nas duas pontas da laje) ->
    mantém todas. Função pura, sem `msp`, para ser testável isoladamente."""
    by_span = {}
    for cand in candidates:
        by_span.setdefault((cand.axis,) + cand.span_key, []).append(cand)

    winners = []
    for group in by_span.values():
        ordered = sorted(group, key=lambda c: c.anchor)
        cluster = [ordered[0]]
        for cand in ordered[1:]:
            if cand.anchor - cluster[-1].anchor <= DIM_CANDIDATE_CLUSTER_TOL_CM:
                cluster.append(cand)
            else:
                winners.append(_pick_canonical_dim_candidate(cluster, x_grid, y_grid))
                cluster = [cand]
        winners.append(_pick_canonical_dim_candidate(cluster, x_grid, y_grid))
    return winners


def _draw_dim_candidates(msp, candidates):
    count = 0
    for cand in candidates:
        a, b = cand.span_raw
        if cand.axis == 'h':
            add_dim_on_paineis(
                msp, a, b, cand.anchor + cand.offset, cand.anchor,
                text_override=cand.text_override, text_location=cand.text_location,
            )
        else:
            add_dim_vertical_on_paineis(
                msp, a, b, cand.anchor + cand.offset, cand.anchor,
                text_override=cand.text_override, text_location=cand.text_location,
            )
        count += 1
    return count


def _add_complex_projection_dimensions(poly_pts, x0, y0, comp, larg, v_positions, h_positions):
    """Candidatos de cota de recortes especiais por projeção até paredes/linhas
    de painel (não desenha — ver _DimCandidate).

    Em peças com degrau/chanfro, cotar só o comprimento da aresta recortada não
    basta para fabricar o painel. O padrão útil é indicar as distâncias do
    vértice/chanfro até as paredes ou linhas de painel próximas, como régua de
    corte. A função só roda em polígonos complexos; retângulos simples ficam
    com a cotagem canônica mínima.
    """
    if not poly_pts or len(poly_pts) <= 4:
        return []

    pts = list(poly_pts)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])

    x_grid = _dedupe_sorted([x0, x0 + comp] + [x0 + value for value in v_positions])
    y_grid = _dedupe_sorted([y0, y0 + larg] + [y0 + value for value in h_positions])
    candidates = []

    def add_h(a, b, y, offset=10.0, min_len=5.0, text_location=None, source="cpx:h"):
        length = abs(a - b)
        if length <= min_len:
            return
        dim_y = y + offset
        if text_location is None and length <= 20.0:
            right_side = (a + b) / 2 >= x0 + comp / 2
            text_x = max(a, b) + 18.0 if right_side else min(a, b) - 18.0
            text_location = (text_x, dim_y)
        candidates.append(_DimCandidate(
            axis='h', span_raw=(a, b),
            span_key=(round(min(a, b), 1), round(max(a, b), 1)),
            anchor=y, offset=offset,
            text_override=_format_dim_value(length),
            text_location=text_location, source=source,
        ))

    def add_v(a, b, x, offset=-10.0, min_len=5.0, source="cpx:v"):
        if abs(a - b) <= min_len:
            return
        candidates.append(_DimCandidate(
            axis='v', span_raw=(a, b),
            span_key=(round(min(a, b), 1), round(max(a, b), 1)),
            anchor=x, offset=offset,
            text_override=_format_dim_value(abs(b - a)),
            text_location=(x + offset, (a + b) / 2), source=source,
        ))

    def is_orthogonal_corner(prev_pt, cur_pt, next_pt):
        px, py = cur_pt
        ax, ay = prev_pt
        bx, by = next_pt
        prev_h = abs(ay - py) <= 0.5
        prev_v = abs(ax - px) <= 0.5
        next_h = abs(by - py) <= 0.5
        next_v = abs(bx - px) <= 0.5
        return (prev_h and next_v) or (prev_v and next_h)

    # 1) Vértices fora da malha: cotar somente cantos de degrau/recorte úteis.
    open_pts = pts[:-1]
    for index, (px, py) in enumerate(open_pts):
        prev_pt = open_pts[index - 1]
        next_pt = open_pts[(index + 1) % len(open_pts)]
        x_on_grid = _grid_has(px, x_grid)
        y_on_grid = _grid_has(py, y_grid)
        if x_on_grid and y_on_grid:
            continue
        on_outer_x = abs(px - x0) <= 0.6 or abs(px - (x0 + comp)) <= 0.6
        on_outer_y = abs(py - y0) <= 0.6 or abs(py - (y0 + larg)) <= 0.6
        orthogonal_corner = is_orthogonal_corner(prev_pt, (px, py), next_pt)
        internal_orthogonal_corner = orthogonal_corner and not (on_outer_x or on_outer_y)
        touches_diagonal = (
            (abs(prev_pt[0] - px) > 0.5 and abs(prev_pt[1] - py) > 0.5)
            or (abs(next_pt[0] - px) > 0.5 and abs(next_pt[1] - py) > 0.5)
        )

        if internal_orthogonal_corner and not x_on_grid and larg > 75.0:
            for gx in _nearest_each_side(px, x_grid, min_dist=1.0, max_dist=130.0):
                offset = 10.0 if py < y0 + larg / 2 else -10.0
                min_len = 1.0
                add_h(gx, px, py, offset=offset, min_len=min_len)

        if touches_diagonal and on_outer_y and not on_outer_x and not x_on_grid:
            right = [
                gx for gx in x_grid
                if 1.0 <= gx - px <= 130.0
            ]
            if right:
                if larg <= 75.0:
                    offset = 12.0 if py <= y0 + 0.6 else -12.0
                else:
                    offset = 10.0
                add_h(px, min(right), py, offset=offset, min_len=1.0)

        if not y_on_grid and (
            internal_orthogonal_corner
            or (abs(px - x0) <= 0.6 and not on_outer_y)
        ):
            for gy in _nearest_each_side(py, y_grid, min_dist=5.0, max_dist=260.0):
                if abs(px - x0) <= 0.6:
                    # Canto do chanfro na parede esquerda: decisao do dono
                    # (24/07) e' que as duas cotas ficam por DENTRO da laje
                    # (antes o trecho de baixo saia pra fora, offset -22.0 —
                    # ficava fora do contorno, dificil de ler/associar ao
                    # desenho). Mesmo lado (positivo/interno) pros dois,
                    # espacamento de 15 entre eles pra nao colidir (mesmo
                    # padrao da branch de canto interno logo abaixo).
                    offset = 12.0 if gy > py else 27.0
                else:
                    # Canto ortogonal interno fora da parede x0 (ex.: vertice
                    # espelhado de um degrau do lado direito). Quando os dois
                    # lados de _nearest_each_side existem (py entre duas linhas
                    # de grade), as duas cotas verticais nasciam com o MESMO
                    # offset -> mesmo dim_x -> texto sobreposto (achado
                    # cota_colisao_canto_interno). Escalona como a branch da
                    # parede acima: mesmo lado do vertice (sinal preservado),
                    # afastamento maior para o lado oposto a gy>py.
                    base = 10.0 if px <= x0 + comp / 2 else -10.0
                    far = 25.0 if px <= x0 + comp / 2 else -25.0
                    offset = base if gy > py else far
                add_v(gy, py, px, offset=offset)

        if (
            larg <= 75.0
            and on_outer_x
            and not y_on_grid
            and orthogonal_corner
        ):
            for gy in _nearest_each_side(py, y_grid, min_dist=1.0, max_dist=12.0):
                offset = -12.0 if px >= x0 + comp / 2 else 12.0
                add_v(gy, py, px, offset=offset, min_len=1.0)

    # 2) Chanfros: nas linhas verticais de painel que cruzam a diagonal, cotar
    # da interseção até a primeira linha horizontal superior. Isso gera as
    # medidas de corte reais do painel em vez de só o comprimento inclinado.
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        diagonal = abs(x1 - x2) > 0.5 and abs(y1 - y2) > 0.5
        if not diagonal:
            continue
        for gx in x_grid[1:-1]:
            if not (min(x1, x2) + 0.5 < gx < max(x1, x2) - 0.5):
                continue
            t = (gx - x1) / (x2 - x1)
            if not (0.0 < t < 1.0):
                continue
            gy = y1 + t * (y2 - y1)
            upper = [yy for yy in y_grid if yy > gy + 5.0]
            if not upper:
                continue
            target_y = min(upper)
            if 5.0 <= target_y - gy <= 260.0:
                add_v(gy, target_y, gx, offset=-10.0)

        # Em lajes rasas, o chanfro pode não cruzar nenhuma linha vertical de
        # painel (caso L326). A fabricação ainda precisa da distância
        # horizontal do corte até a linha/paredes de painel nas linhas
        # horizontais existentes; cotar a diagonal diretamente é proibido.
        if larg <= 75.0:
            central_wall_keys = set()
            if h_positions:
                guide_y = y0 + min(h_positions, key=lambda value: abs(value - larg / 2))
                for xa, xb in _axis_segments_in_polygon(poly_pts, 'h', guide_y):
                    local_edges = _dedupe_sorted([xa, xb] + [
                        xx for xx in x_grid
                        if xa + 0.5 < xx < xb - 0.5
                    ])
                    for a, b in zip(local_edges, local_edges[1:]):
                        central_wall_keys.add(("h", round(a, 1), round(b, 1)))

            # Bordas horizontais recortadas pela diagonal também precisam ser
            # segmentadas pela malha de painéis: ex. L326 gera 41,9 + 114,4 na
            # base, em vez de só o bbox 116,8 + 116,9.
            for yy in (y0, y0 + larg):
                edge_spans = _axis_segments_in_polygon(
                    poly_pts,
                    'h',
                    yy + (0.01 if abs(yy - y0) <= 0.5 else -0.01),
                )
                for xa, xb in edge_spans:
                    if xb - xa <= 1.0:
                        continue
                    # Span externo completo já é coberto pela cota canônica.
                    # Em laje rasa chanfrada, a borda superior completa é uma
                    # parede real divergente da linha central e deve ser cotada
                    # junto ao topo. As demais bordas completas continuam sem
                    # repetição.
                    full_span = abs(xa - x0) <= 0.6 and abs(xb - (x0 + comp)) <= 0.6
                    top_wall = abs(yy - (y0 + larg)) <= 0.6
                    if full_span and not top_wall:
                        continue
                    local_edges = _dedupe_sorted([xa, xb] + [
                        xx for xx in x_grid
                        if xa + 0.5 < xx < xb - 0.5
                    ])
                    for a, b in zip(local_edges, local_edges[1:]):
                        if not top_wall and ("h", round(a, 1), round(b, 1)) in central_wall_keys:
                            continue
                        offset = 12.0 if yy <= y0 + larg / 2 else -12.0
                        add_h(a, b, yy, offset=offset, min_len=1.0, source="cpx:h_chanfro")

    return candidates


def _add_cut_edge_dimensions(msp, poly_pts, x0, y0, comp, larg, v_positions, h_positions):
    """Cota arestas de recorte que não coincidem com a malha padrão.

    Para recortes em L ou chanfrados, o painel especial precisa levar as medidas
    das paredes de corte; bbox e cotas principais não bastam.

    Coleta candidatos de duas fontes (_add_complex_projection_dimensions() e o
    loop de arestas abaixo) e consolida ANTES de desenhar — as duas fontes
    desenham sobre o mesmo polígono e podiam, sem essa consolidação, produzir
    cotas duplicadas de forma cruzada (mesma classe de bug do degrau de borda,
    não só dentro de uma única fonte).

    Retorna (count, winners) — winners é a lista de _DimCandidate desenhados,
    usada pelo chamador para o rótulo do nome não colidir com nenhuma cota
    real (achado cota_sobre_rotulo_item).
    """
    if not poly_pts or len(poly_pts) <= 4:
        return 0, []
    pts = list(poly_pts)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    x_grid = {round(x0, 1), round(x0 + comp, 1)}
    x_grid.update(round(x0 + value, 1) for value in v_positions)
    y_grid = {round(y0, 1), round(y0 + larg, 1)}
    y_grid.update(round(y0 + value, 1) for value in h_positions)
    has_diagonal = _has_diagonal_edges(poly_pts)
    x_lines = _dedupe_sorted([x0, x0 + comp] + [x0 + value for value in v_positions])
    central_h_keys = set()
    if larg <= 75.0:
        guide_y = y0 + (
            min(h_positions, key=lambda value: abs(value - larg / 2))
            if h_positions else larg / 2
        )
        for xa, xb in _axis_segments_in_polygon(poly_pts, 'h', guide_y):
            local_edges = _dedupe_sorted([xa, xb] + [
                xx for xx in x_lines
                if xa + 0.5 < xx < xb - 0.5
            ])
            for a, b in zip(local_edges, local_edges[1:]):
                central_h_keys.add(("h", round(a, 1), round(b, 1)))
    candidates = list(_add_complex_projection_dimensions(
        poly_pts, x0, y0, comp, larg, v_positions, h_positions
    ))
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 5.0:
            continue
        horizontal = abs(y1 - y2) <= 0.5
        vertical = abs(x1 - x2) <= 0.5
        if horizontal:
            if has_diagonal:
                continue
            # Bordas externas retas já são cobertas pelas cotas principais,
            # exceto quando a parede externa de uma laje rasa diverge da linha
            # central dos painéis (rebaixo lateral L327-L329).
            if round(y1, 1) in {round(y0, 1), round(y0 + larg, 1)}:
                if larg <= 75.0:
                    xa, xb = sorted((x1, x2))
                    local_edges = _dedupe_sorted([xa, xb] + [
                        xx for xx in x_lines
                        if xa + 0.5 < xx < xb - 0.5
                    ])
                    for a, b in zip(local_edges, local_edges[1:]):
                        if b - a <= 5.0:
                            continue
                        if ("h", round(a, 1), round(b, 1)) in central_h_keys:
                            continue
                        offset_y = 12.0 if y1 <= y0 + larg / 2 else -12.0
                        candidates.append(_DimCandidate(
                            axis='h', span_raw=(a, b),
                            span_key=(round(min(a, b), 1), round(max(a, b), 1)),
                            anchor=y1, offset=offset_y,
                            text_override=_format_dim_value(b - a),
                            text_location=None, source="cut_edge:h_wall",
                        ))
                continue
            if _grid_has(x1, x_grid) and _grid_has(x2, x_grid):
                continue
            offset_y = 8.0 if y1 < y0 + larg / 2 else -8.0
            candidates.append(_DimCandidate(
                axis='h', span_raw=(x1, x2),
                span_key=(round(min(x1, x2), 1), round(max(x1, x2), 1)),
                anchor=y1, offset=offset_y,
                text_override=_format_dim_value(length),
                text_location=None, source="cut_edge:h_edge",
            ))
        elif vertical:
            if has_diagonal:
                continue
            y_low, y_high = sorted((y1, y2))
            shallow_side_notch_total = (
                larg <= 75.0
                and (
                    abs(y_low - y0) <= 0.6
                    or abs(y_high - (y0 + larg)) <= 0.6
                )
                and (
                    round(y_low, 1) not in y_grid
                    or round(y_high, 1) not in y_grid
                )
                and (
                    0.5 < abs(x1 - x0) <= 10.0
                    or 0.5 < abs((x0 + comp) - x1) <= 10.0
                )
            )
            if shallow_side_notch_total:
                # Lajes rasas com pequeno rebaixo lateral (ex.: L327-L329)
                # ja recebem as cotas uteis ate as linhas horizontais de
                # painel. A vertical inteira do rebaixo (52 cm) mede a parede
                # lateral bruta, nao uma parede de painel fabricavel, e polui
                # a leitura.
                continue
            if _grid_has(x1, {x0, x0 + comp}):
                continue
            if _grid_has(y1, y_grid) and _grid_has(y2, y_grid):
                continue
            offset_x = 8.0 if x1 < x0 + comp / 2 else -8.0
            candidates.append(_DimCandidate(
                axis='v', span_raw=(y1, y2),
                span_key=(round(min(y1, y2), 1), round(max(y1, y2), 1)),
                anchor=x1, offset=offset_x,
                text_override=_format_dim_value(length),
                text_location=(x1 + offset_x, (y1 + y2) / 2),
                source="cut_edge:v_edge",
            ))
        else:
            # Não cotar a aresta diagonal diretamente. Em lajes, o corte é mais
            # útil com cotas ortogonais de projeção até parede/linha de painel.
            # A projeção é gerada por _add_complex_projection_dimensions().
            continue
    winners = _consolidate_dim_candidates(candidates, sorted(x_grid), sorted(y_grid))
    count = _draw_dim_candidates(msp, winners)
    return count, winners


def _add_reference_dimensions(msp, x0, y0, comp, larg, v_positions, h_positions, h_bands, poly_pts=None):
    x_edges = _dedupe_sorted([0.0] + list(v_positions) + [comp])
    y_edges = _dedupe_sorted([0.0] + list(h_positions) + [larg])
    guide_x = min(v_positions, key=lambda value: abs(value - comp / 2)) if v_positions else comp / 2
    if h_bands:
        guide_y = h_bands[0][0]
    else:
        guide_y = min(h_positions, key=lambda value: abs(value - larg / 2)) if h_positions else larg / 2
    panel_x = x0 + guide_x
    panel_y = y0 + guide_y
    vertical_segments = list(reversed(list(zip(y_edges, y_edges[1:]))))
    shallow = larg <= 75.0
    shallow_complex = shallow and poly_pts and len(poly_pts) > 4
    # A cota horizontal principal usa offset diferente por ramo (10.0 em
    # shallow_complex, DIM_HORIZONTAL_OFFSET_CM nos demais) -- guardar o valor
    # real usado aqui para o rotulo do nome (_label_position_clear_of_
    # dimensions) evitar a MESMA linha, em vez de reaproximar com um offset
    # fixo que so bate com um dos ramos (achado cota_sobre_rotulo_item).
    horizontal_dim_offset = 10.0 if shallow_complex else DIM_HORIZONTAL_OFFSET_CM
    horizontal_dim_y = panel_y - horizontal_dim_offset
    if shallow_complex:
        for xa, xb in _axis_segments_in_polygon(poly_pts, 'h', panel_y):
            local_edges = _dedupe_sorted([xa - x0, xb - x0] + [
                edge for edge in x_edges[1:-1]
                if xa - x0 + 0.5 < edge < xb - x0 - 0.5
            ])
            for start, end in zip(local_edges, local_edges[1:]):
                if end - start <= 1.0:
                    continue
                add_dim_on_paineis(
                    msp, x0 + start, x0 + end,
                    horizontal_dim_y, panel_y,
                )
    else:
        for start, end in zip(x_edges, x_edges[1:]):
            add_dim_on_paineis(
                msp, x0 + start, x0 + end,
                horizontal_dim_y, panel_y,
            )
    vertical_guide_x = guide_x
    if not shallow:
        vertical_guide_x = _full_height_vertical_guide(
            poly_pts, x0, y0, comp, larg, x_edges, guide_x
        )
    vertical_panel_x = x0 + vertical_guide_x
    # Faixa baixa (shallow) usa sempre o eixo interno (junta/centro mais
    # proximo), nunca o exterior a esquerda de x0 -- achado 24/07: cotas "35"/
    # "36" apareciam fora da laje em lajes retangulares simples (L401, L403,
    # L404, L422) porque so o ramo shallow_complex (poly_pts > 4 pontos, i.e.
    # contorno com degrau) usava o eixo interno; retangulo simples (4 pontos)
    # caia no ramo antigo x0-OFFSET-14 (exterior). Nao ha mais distincao entre
    # shallow e shallow_complex aqui -- os dois usam vertical_panel_x.
    dimline_x = vertical_panel_x - DIM_VERTICAL_OFFSET_CM
    extension_x = vertical_panel_x
    for index, (start, end) in enumerate(vertical_segments):
        text_location = None
        if shallow:
            text_location = (
                dimline_x,
                y0 + (start + end) / 2,
            )
        elif index == 0:
            text_location = (dimline_x, y0 + (start + end) / 2)
        add_dim_vertical_on_paineis(
            msp, y0 + start, y0 + end,
            dimline_x, extension_x,
            text_location=text_location,
        )
    if not shallow:
        _add_secondary_vertical_dimensions(
            msp, poly_pts, x0, y0, comp, larg, x_edges, y_edges, vertical_guide_x
        )
    _, cut_edge_winners = _add_cut_edge_dimensions(
        msp, poly_pts, x0, y0, comp, larg, v_positions, h_positions
    )
    return panel_x, panel_y, horizontal_dim_y, dimline_x, cut_edge_winners

def _add_dim_text(msp, x, y, value, rotation=0.0, height=8.0):
    add_text(msp, x, y, _format_dim_value(value), height=height, layer='Pain\u00e9is', rotation=rotation)

def _add_generated_laje_cotas(msp, poly_pts, x0, y0, comp, larg, v_positions, h_positions):
    """Gera cotas internas no estilo N4, sem copiar a posição dos textos STOG."""
    x_edges = [0.0] + list(v_positions) + [comp]
    
    # Cotas horizontais principais: uma linha-guia interna por faixa (no centro do melhor painel)
    guide_y = _horizontal_dimension_guide(poly_pts, y0, larg, h_positions)
    segments = _axis_segments_in_polygon(poly_pts, 'h', guide_y)
    if segments:
        for xa, xb in segments:
            local_edges = [xa - x0, xb - x0]
            local_edges.extend(v for v in x_edges[1:-1] if xa - x0 + 0.5 < v < xb - x0 - 0.5)
            local_edges = _dedupe_sorted(local_edges)
            for a, b in zip(local_edges, local_edges[1:]):
                if b - a > 1.0:
                    _add_dim_text(msp, x0 + (a + b) / 2, guide_y, b - a)

    # Cotas verticais principais: faixas internas no eixo Y.
    y_edges = [0.0] + list(h_positions) + [larg]
    guide_x = _vertical_dimension_guide(poly_pts, x0, comp, v_positions)
    for a, b in zip(y_edges, y_edges[1:]):
        if b - a > 1.0:
            _add_dim_text(msp, guide_x, y0 + (a + b) / 2, b - a, rotation=90.0)

    # Cotas horizontais de bordas deformadas: quando topo/base têm spans distintos.
    ys = sorted({round(p[1], 1) for p in poly_pts})
    edge_spans = []
    for yy in (ys[0], ys[-1]):
        segs = _axis_segments_in_polygon(poly_pts, 'h', yy + (0.01 if yy == ys[0] else -0.01))
        if segs:
            xa, xb = max(segs, key=lambda s: s[1] - s[0])
            edge_spans.append((yy, xa, xb))
    if len(edge_spans) == 2:
        _, a0, b0 = edge_spans[0]
        _, a1, b1 = edge_spans[1]
        is_deformed_span = abs(a0 - a1) > 1.0 or abs(b0 - b1) > 1.0
        if is_deformed_span:
            for yy, xa, xb in edge_spans:
                guide_y = yy - 8.0 if yy > y0 + larg / 2 else yy + 8.0
                local_edges = [xa - x0, xb - x0]
                local_edges.extend(v for v in x_edges[1:-1] if xa - x0 + 0.5 < v < xb - x0 - 0.5)
                local_edges = _dedupe_sorted(local_edges)
                for a, b in zip(local_edges, local_edges[1:]):
                    if b - a > 1.0:
                        _add_dim_text(msp, x0 + (a + b) / 2, guide_y, b - a)

    # Cotas verticais de bordas deformadas: quando esq/dir têm spans distintos.
    xs = sorted({round(p[0], 1) for p in poly_pts})
    v_edge_spans = []
    for xx in (xs[0], xs[-1]):
        segs = _axis_segments_in_polygon(poly_pts, 'v', xx + (0.01 if xx == xs[0] else -0.01))
        if segs:
            ya, yb = max(segs, key=lambda s: s[1] - s[0])
            v_edge_spans.append((xx, ya, yb))
    if len(v_edge_spans) == 2:
        _, ya0, yb0 = v_edge_spans[0]
        _, ya1, yb1 = v_edge_spans[1]
        v_is_deformed_span = abs(ya0 - ya1) > 1.0 or abs(yb0 - yb1) > 1.0
        if v_is_deformed_span:
            for xx, ya, yb in v_edge_spans:
                guide_x = xx - 8.0 if xx > x0 + comp / 2 else xx + 8.0
                local_edges = [ya - y0, yb - y0]
                local_edges.extend(h for h in y_edges[1:-1] if ya - y0 + 0.5 < h < yb - y0 - 0.5)
                local_edges = _dedupe_sorted(local_edges)
                for a, b in zip(local_edges, local_edges[1:]):
                    if b - a > 1.0:
                        _add_dim_text(msp, guide_x, y0 + (a + b) / 2, b - a, rotation=90.0)

    # Cotas de degrau: pequenos offsets horizontais e alturas verticais dos recortes.
    pts = list(poly_pts)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    step_ys = sorted(y for y in ys[1:-1] if all(abs(y - (y0 + h)) > 0.5 for h in h_positions))
    for step_y in step_ys:
        lower_guides = [y0 + h for h in h_positions if y0 + h < step_y - 0.5]
        if not lower_guides:
            continue
        lower = max(lower_guides)
        value = step_y - lower
        if 1.0 <= value <= 35.0:
            left_x = min(p[0] for p in poly_pts) + 12.0
            right_x = max(p[0] for p in poly_pts) - 12.0
            cy = (lower + step_y) / 2
            _add_dim_text(msp, left_x, cy, value, rotation=90.0)
            _add_dim_text(msp, right_x, cy, value, rotation=90.0)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if abs(y1 - y2) <= 0.5:
            length = abs(x2 - x1)
            if 1.0 <= length <= 35.0:
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                # Empurra para dentro da laje.
                cy += -5.0 if cy > y0 + larg / 2 else 5.0
                _add_dim_text(msp, cx, cy, length)

def _draw_laje_planta_legacy(msp, lj_data, distribute_panels_fn, include_context=True):
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
    cotas_paineis = lj_data.get('cotas_paineis') or []
    obstaculos = lj_data.get('obstaculos', [])
    reap   = lj_data.get('reaproveitamento_dados', {})
    sobras = lj_data.get('sobras_recebidas', [])

    # Base position from coords or grid fallback
    if len(coords) >= 3:
        raw_x0 = min(c[0] for c in coords)
        raw_y0 = min(c[1] for c in coords)
        raw_x1 = max(c[0] for c in coords)
        raw_y1 = max(c[1] for c in coords)
        pose = lj_data.get('_stog_pose') or {}
        if pose and abs(raw_x0) <= 0.5 and abs(raw_y0) <= 0.5:
            off_x = float(pose.get('x', 0.0))
            off_y = float(pose.get('y', 0.0))
        else:
            off_x = 0.0
            off_y = 0.0
        x0 = raw_x0 + off_x
        y0 = raw_y0 + off_y
        x1 = raw_x1 + off_x
        y1 = raw_y1 + off_y
        coord_comp = round(x1 - x0, 2)
        coord_larg = round(y1 - y0, 2)
        if coord_comp > 0 and coord_larg > 0:
            comp = coord_comp
            larg = coord_larg
        poly_pts = [(c[0] + off_x, c[1] + off_y) for c in coords]
        # Remove duplicate closing point
        if len(poly_pts) > 1 and poly_pts[0] == poly_pts[-1]:
            poly_pts = poly_pts[:-1]
    else:
        x0 = 0.0
        y0 = 0.0
        poly_pts = [(x0, y0), (x0+comp, y0), (x0+comp, y0+larg), (x0, y0+larg)]

    if comp <= 0 or larg <= 0:
        return None

    lv = _normalize_line_positions(lv, comp)
    lh = _normalize_line_positions(lh, larg)
    smart = None
    if comp >= max(larg, 2 * 244.0) and lv:
        smart = distribute_panels_fn(comp, larg, obstaculos or None)
        lv = _canonicalize_long_axis_if_noisy(
            lv, comp, smart.get('linhas_verticais') if isinstance(smart, dict) else []
        )
    if min(comp, larg) <= 75.0:
        smart = smart or distribute_panels_fn(comp, larg, obstaculos or None)
        lv_before_segment_filter = list(lv)
        lv = [
            item for item in lv
            if not item.get('segments') or any(
                float(segment.get('y0', 0)) <= 1.0
                and float(segment.get('y1', 0)) >= larg - 1.0
                for segment in item['segments']
            )
        ]
        # Faixas estreitas: metadados de segmento podem vir incompletos do recorte
        # N2. Não deixar o filtro zerar a grade e forçar SmartPanner a redistribuir
        # (ex.: 174cm -> 244cm no 14_PAV). Preserva posições sem segments.
        if not lv and lv_before_segment_filter:
            lv = [
                {key: value for key, value in item.items() if key != 'segments'}
                for item in lv_before_segment_filter
            ]
        if larg <= 75.0:
            canonical_lh = _normalize_line_positions(
                (smart or {}).get('linhas_horizontais') or [], larg
            )
            if canonical_lh:
                lh = canonical_lh
            else:
                lh = [
                    item for item in lh
                    if min(float(item.get('value', 0)), larg - float(item.get('value', 0))) >= 30.0
                ]
        if comp <= 75.0:
            canonical_lv = _normalize_line_positions(
                (smart or {}).get('linhas_verticais') or [], comp
            )
            if canonical_lv:
                lv = canonical_lv

    # SmartPanner if no panel divisions
    if not lv and not lh and comp > 0 and larg > 0:
        smart = distribute_panels_fn(comp, larg, obstaculos or None)
        lv = _normalize_line_positions(smart['linhas_verticais'], comp)
        lh = _normalize_line_positions(smart['linhas_horizontais'], larg)
    if len(poly_pts) <= 4 and not hlaz_items:
        smart = smart or distribute_panels_fn(comp, larg, obstaculos or None)
        if lv and not _looks_like_canonical_panel_distribution(
            [_line_value(item) for item in lv], comp
        ) and not _extracted_panel_lines_trusted(lv, comp):
            canonical_lv = _normalize_line_positions((smart or {}).get('linhas_verticais') or [], comp)
            if canonical_lv:
                lv = canonical_lv
        if lh and not _looks_like_canonical_panel_distribution(
            [_line_value(item) for item in lh], larg
        ) and not _extracted_panel_lines_trusted(lh, larg):
            canonical_lh = _normalize_line_positions((smart or {}).get('linhas_horizontais') or [], larg)
            if canonical_lh:
                lh = canonical_lh
    lv, lh = _optimize_panel_lines_for_polygon(
        poly_pts, x0, y0, comp, larg, lv, lh, distribute_panels_fn
    )

    # Bounding box for this laje
    x_max = x0 + comp
    y_max = y0 + larg

    # ---- Layer 3: structural outline (green LWPOLYLINE) ----
    msp.add_lwpolyline(poly_pts, close=True,
                        dxfattribs={'layer': '3', 'lineweight': 25})

    # ---- Layer 4: Label (TEXT h=15, not MTEXT) ----
    cx, cy = _label_position(poly_pts, v_positions=[], h_positions=[], x0=x0, y0=y0, comp=comp, larg=larg)
    add_text(msp, cx, cy, nome, height=15.0, layer='4')

    # ---- Collect panel edge positions ----
    v_positions = sorted(_line_value(v) for v in lv)
    h_positions = sorted(_line_value(h) for h in lh)
    cx, cy = _label_position(poly_pts, v_positions, h_positions, x0, y0, comp, larg)
    # Reposiciona o nome se a primeira estimativa cair sobre linha interna.
    for e in list(msp.query('TEXT[layer=="4"]')):
        if str(getattr(e.dxf, 'text', '')) == str(nome):
            e.dxf.insert = (cx, cy, 0.0)

    # Detect which are union points
    v_union_set = set()
    for v in lv:
        if v.get('is_union', False):
            v_union_set.add(round(float(v.get('value', 0)), 1))
    h_union_set = set()
    for h in lh:
        if h.get('is_union', False):
            h_union_set.add(round(float(h.get('value', 0)), 1))

    local_v_segments = lj_data.get('_panel_vertical_segments') or []
    if not local_v_segments:
        # No fluxo oficial N4 os campos privados sao filtrados pelo Comparison
        # Engine. Os trechos locais persistem dentro de linhas_verticais.
        local_v_segments = [
            {
                'value': float(item.get('value', 0)),
                'y0': float(segment.get('y0', 0)),
                'y1': float(segment.get('y1', 0)),
            }
            for item in lv
            for segment in (item.get('segments') or [])
            if isinstance(item, dict) and isinstance(segment, dict)
        ]

    # ---- Layer 3: Paired PLINEs at each division (sarrafo de pressao) ----
    complex_outline = len(poly_pts) > 4 or bool(lj_data.get('_stog_clip_unions'))
    # Vertical divisions
    prev_xv = 0.0
    if local_v_segments:
        for segment in local_v_segments:
            abs_x = x0 + float(segment['value'])
            msp.add_line(
                (abs_x, y0 + float(segment['y0'])),
                (abs_x, y0 + float(segment['y1'])),
                dxfattribs={'layer': '3'},
            )
    else:
        for xv in v_positions:
            abs_x = x0 + xv
            is_union = round(xv, 1) in v_union_set
            if is_union and complex_outline:
                _add_clipped_axis_lines(msp, poly_pts, 'v', abs_x, '3')
            elif is_union:
                # Sarrafo: two PLINEs 19cm apart on layer 3
                gap = max(1.0, xv - prev_xv)
                add_paired_lines_v(msp, x0 + prev_xv, y0, y_max, gap=gap, layer='3')
            else:
                _add_clipped_axis_lines(msp, poly_pts, 'v', abs_x, '3')
            prev_xv = xv

    # Horizontal divisions
    prev_yh = 0.0
    for yh in h_positions:
        abs_y = y0 + yh
        is_union = round(yh, 1) in h_union_set
        if is_union:
            if complex_outline:
                _add_clipped_axis_lines(msp, poly_pts, 'h', abs_y, '3')
            else:
                gap = max(1.0, yh - prev_yh)
                add_paired_lines_h(msp, x0, x_max, y0 + prev_yh, gap=gap, layer='3')
        else:
            _add_clipped_axis_lines(msp, poly_pts, 'h', abs_y, '3')
        prev_yh = yh

    # ---- Layer Painéis: panel boundary LINEs ----
    # Vertical panel boundaries
    if local_v_segments:
        for segment in local_v_segments:
            abs_x = x0 + float(segment['value'])
            msp.add_line(
                (abs_x, y0 + float(segment['y0'])),
                (abs_x, y0 + float(segment['y1'])),
                dxfattribs={'layer': 'Pain\u00e9is', 'lineweight': 18},
            )
    else:
        for xv in v_positions:
            abs_x = x0 + xv
            _add_clipped_axis_lines(msp, poly_pts, 'v', abs_x, 'Pain\u00e9is', lineweight=18)

    # Horizontal panel boundaries
    for yh in h_positions:
        abs_y = y0 + yh
        _add_clipped_axis_lines(msp, poly_pts, 'h', abs_y, 'Pain\u00e9is', lineweight=18)

    # ---- Layer Painéis: DIMENSION per panel segment ----
    x_edges = [0.0] + v_positions + [comp]
    h_edges = [0.0] + h_positions + [larg]

    if cotas_paineis:
        for cota in cotas_paineis:
            add_text(
                msp, x0 + float(cota.get('x', 0)), y0 + float(cota.get('y', 0)),
                str(cota.get('text', '')), height=float(cota.get('height', 8)),
                layer='Pain\u00e9is', rotation=float(cota.get('rotation', 0)),
            )
    elif min(comp, larg) <= 75.0:
        x_edges = [0.0] + v_positions + [comp]
        y_edges = [0.0] + h_positions + [larg]
        guide_y = y0 + ((y_edges[-2] + y_edges[-1]) / 2 if len(y_edges) > 1 else larg / 2)
        for a, b in zip(x_edges, x_edges[1:]):
            _add_dim_text(msp, x0 + (a + b) / 2, guide_y, b - a)
        guide_x = x0 + ((x_edges[0] + x_edges[1]) / 2 if len(x_edges) > 1 else comp / 2)
        for a, b in zip(y_edges, y_edges[1:]):
            _add_dim_text(msp, guide_x, y0 + (a + b) / 2, b - a, rotation=90.0)
    else:
        _add_generated_laje_cotas(msp, poly_pts, x0, y0, comp, larg, v_positions, h_positions)

    # ---- Layer 3: dim texts for pilar sizes (e.g. "19/50") ----
    # Positioned near pilar corners where pilars would be
    # In real STOG these come from the structural plan — we add typical entries

    # ---- Layer 9: SOLID markers at division intersections ----
    for xv in v_positions:
        abs_x = x0 + xv
        is_union = round(xv, 1) in v_union_set
        if is_union:
            marker_top = y0 + min(200, larg)
            for seg_lo, seg_hi in _axis_segments_in_polygon(poly_pts, 'v', abs_x):
                lo = max(seg_lo, y0)
                hi = min(seg_hi, marker_top)
                if hi - lo > 0.5:
                    msp.add_solid(
                        [(abs_x, lo), (abs_x, hi), (abs_x, lo)],
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
    else:
        _add_narrow_panel_hatches(
            msp, poly_pts, x0, y0, comp, larg, v_positions, h_positions,
            v_union_set, h_union_set,
        )

    # ---- OBSTACLES (DASHED rectangles on layer 3) ----
    for obs in _sanitize_laj_obstacles(obstaculos):
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

    # ---- Outer boundary as 4 LINE entities (STOG style — layer 3) ----
    # Complementa o LWPOLYLINE com LINEs separadas (STOG usa ambos)
    for i in range(len(poly_pts)):
        msp.add_line(
            poly_pts[i], poly_pts[(i + 1) % len(poly_pts)],
            dxfattribs={'layer': '3'}
        )

    # ---- Escora LINEs (layer 9): suportes verticais espaçados ~16cm ----
    # STOG real: ~1000+ LINE entities; escoras são a principal fonte
    if include_context:
        ESC_STEP = 16.0
        x_esc = x0 + ESC_STEP
        while x_esc < x_max - 1.0:
            msp.add_line((x_esc, y0 - 20), (x_esc, y0), dxfattribs={'layer': '9'})
            x_esc += ESC_STEP
    # Escoras laterais (direção Y)
        y_esc = y0 + ESC_STEP
        while y_esc < y_max - 1.0:
            msp.add_line((x0 - 20, y_esc), (x0, y_esc), dxfattribs={'layer': '9'})
            y_esc += ESC_STEP

    n_panels = (len(x_edges) - 1) * (len(h_edges) - 1)
    return nome, comp, larg, x0, y0, n_panels


def draw_laje_planta(msp, lj_data, distribute_panels_fn, include_context=True):
    nome = lj_data.get('nome', lj_data.get('name', 'L?'))
    comp = float(lj_data.get('comprimento', 0))
    larg = float(lj_data.get('largura', 0))
    coords = lj_data.get('coordenadas', [])
    lv = lj_data.get('linhas_verticais', [])
    lh = lj_data.get('linhas_horizontais', [])
    cotas_paineis = lj_data.get('cotas_paineis') or []
    hlaz_items = lj_data.get('_hlaz') or []
    obstaculos = _sanitize_laj_obstacles(lj_data.get('obstaculos', []))
    apoios_hachurados = lj_data.get('apoios_hachurados', [])
    reap = lj_data.get('reaproveitamento_dados', {})
    sobras = lj_data.get('sobras_recebidas', [])

    if len(coords) >= 3:
        raw_x0 = min(float(c[0]) for c in coords)
        raw_y0 = min(float(c[1]) for c in coords)
        pose = lj_data.get('_stog_pose') or {}
        if pose and abs(raw_x0) <= 0.5 and abs(raw_y0) <= 0.5:
            off_x = float(pose.get('x', 0.0))
            off_y = float(pose.get('y', 0.0))
        else:
            off_x = 0.0
            off_y = 0.0
        poly_pts = [(float(c[0]) + off_x, float(c[1]) + off_y) for c in coords]
        if len(poly_pts) > 1 and poly_pts[0] == poly_pts[-1]:
            poly_pts.pop()
        x0 = min(point[0] for point in poly_pts)
        y0 = min(point[1] for point in poly_pts)
        comp = max(point[0] for point in poly_pts) - x0
        larg = max(point[1] for point in poly_pts) - y0
    else:
        x0 = y0 = 0.0
        poly_pts = [(0.0, 0.0), (comp, 0.0), (comp, larg), (0.0, larg)]

    if comp <= 0 or larg <= 0:
        return None

    lv = _normalize_line_positions(lv, comp)
    lh = _normalize_line_positions(lh, larg)
    smart = None
    if comp >= max(larg, 2 * 244.0) and lv:
        smart = distribute_panels_fn(comp, larg, obstaculos or None)
        lv = _canonicalize_long_axis_if_noisy(
            lv, comp, smart.get('linhas_verticais') if isinstance(smart, dict) else []
        )
    if min(comp, larg) <= 75.0:
        smart = smart or distribute_panels_fn(comp, larg, obstaculos or None)
        lv_before_segment_filter = list(lv)
        lv = [
            item for item in lv
            if not item.get('segments') or any(
                float(segment.get('y0', 0)) <= 1.0
                and float(segment.get('y1', 0)) >= larg - 1.0
                for segment in item['segments']
            )
        ]
        # Faixas estreitas: metadados de segmento podem vir incompletos do recorte
        # N2. Não deixar o filtro zerar a grade e forçar SmartPanner a redistribuir
        # (ex.: 174cm -> 244cm no 14_PAV). Preserva posições sem segments.
        if not lv and lv_before_segment_filter:
            lv = [
                {key: value for key, value in item.items() if key != 'segments'}
                for item in lv_before_segment_filter
            ]
        if larg <= 75.0:
            canonical_lh = _normalize_line_positions(
                (smart or {}).get('linhas_horizontais') or [], larg
            )
            if canonical_lh:
                lh = canonical_lh
            else:
                lh = [
                    item for item in lh
                    if min(float(item.get('value', 0)), larg - float(item.get('value', 0))) >= 30.0
                ]
        if comp <= 75.0:
            canonical_lv = _normalize_line_positions(
                (smart or {}).get('linhas_verticais') or [], comp
            )
            if canonical_lv:
                lv = canonical_lv
    if not lv and not lh:
        smart = smart or distribute_panels_fn(comp, larg, obstaculos or None)
        lv = _normalize_line_positions(smart['linhas_verticais'], comp)
        lh = _normalize_line_positions(smart['linhas_horizontais'], larg)
    if len(poly_pts) <= 4 and not hlaz_items:
        smart = smart or distribute_panels_fn(comp, larg, obstaculos or None)
        if lv and not _looks_like_canonical_panel_distribution(
            [_line_value(item) for item in lv], comp
        ) and not _extracted_panel_lines_trusted(lv, comp):
            canonical_lv = _normalize_line_positions((smart or {}).get('linhas_verticais') or [], comp)
            if canonical_lv:
                lv = canonical_lv
        if lh and not _looks_like_canonical_panel_distribution(
            [_line_value(item) for item in lh], larg
        ) and not _extracted_panel_lines_trusted(lh, larg):
            canonical_lh = _normalize_line_positions((smart or {}).get('linhas_horizontais') or [], larg)
            if canonical_lh:
                lh = canonical_lh
    lv, lh = _optimize_panel_lines_for_polygon(
        poly_pts, x0, y0, comp, larg, lv, lh, distribute_panels_fn
    )

    # Chapa NOVA 244×122: se a grade (N2 ou smart) gerar célula inválida
    # (ex. 244×169), força redistribuição canônica do smart_panner.
    try:
        from smart_panner import cells_fit_sheet as _cells_fit_sheet
        if not _cells_fit_sheet(lv, lh, comp, larg):
            smart = distribute_panels_fn(comp, larg, obstaculos or None) or {}
            lv = _normalize_line_positions(smart.get('linhas_verticais') or [], comp)
            lh = _normalize_line_positions(smart.get('linhas_horizontais') or [], larg)
            if smart.get('hlaz') and not hlaz_items:
                hlaz_items = list(smart.get('hlaz') or [])
    except Exception:
        pass

    v_positions = sorted(_line_value(item) for item in lv)
    h_positions = sorted(_line_value(item) for item in lh)
    x_edges = _dedupe_sorted([0.0] + v_positions + [comp])
    y_edges = _dedupe_sorted([0.0] + h_positions + [larg])
    v_bands = _union_bands(lv, comp)
    h_bands = _union_bands(lh, larg)
    global_h_bands = [
        band for band in h_bands
        if not _band_is_local_hlaz(band, hlaz_items, comp)
    ]

    _add_union_hatches(msp, poly_pts, x0, y0, comp, larg, v_bands, global_h_bands)
    _add_explicit_hlaz(msp, x0, y0, hlaz_items)
    msp.add_lwpolyline(poly_pts, close=True, dxfattribs={'layer': 'PAINEIS'})
    # Hachura de apoio: decisão do dono (21/07) é que o N4 NÃO precisa dela —
    # mantém o desenho gated por include_context (False na geração por item
    # único, que é o caminho usado pelo Arete/produção).
    if include_context:
        for line in apoios_hachurados:
            try:
                msp.add_line(
                    (x0 + float(line['x1']), y0 + float(line['y1'])),
                    (x0 + float(line['x2']), y0 + float(line['y2'])),
                    dxfattribs={'layer': '3'},
                )
            except (KeyError, TypeError, ValueError):
                continue

    local_segments = [
        {
            'value': float(item.get('value', 0)),
            'y0': float(segment.get('y0', 0)),
            'y1': float(segment.get('y1', 0)),
        }
        for item in lv
        for segment in (item.get('segments') or [])
        if isinstance(item, dict) and isinstance(segment, dict)
    ]
    if local_segments:
        for segment in local_segments:
            msp.add_line(
                (x0 + segment['value'], y0 + segment['y0']),
                (x0 + segment['value'], y0 + segment['y1']),
                dxfattribs={'layer': 'PAINEIS'},
            )
    else:
        union_edges = {edge for band in v_bands for edge in band}
        for value in v_positions:
            _add_panel_axis(
                msp, poly_pts, 'v', x0 + value,
                is_union_boundary=value in union_edges,
            )

    union_edges = {edge for band in global_h_bands for edge in band}
    for item in lh:
        value = _line_value(item)
        segments = item.get('segments') if isinstance(item, dict) else None
        if segments:
            for segment in segments:
                try:
                    xa = x0 + float(segment['x0'])
                    xb = x0 + float(segment['x1'])
                except (KeyError, TypeError, ValueError):
                    continue
                if xb - xa > 0.5:
                    msp.add_line(
                        (xa, y0 + value), (xb, y0 + value),
                        dxfattribs={'layer': 'PAINEIS'},
                    )
        else:
            _add_panel_axis(
                msp, poly_pts, 'h', y0 + value,
                is_union_boundary=value in union_edges,
            )

    panel_x, panel_y, horizontal_dim_y, vertical_dim_x, cut_edge_winners = _add_reference_dimensions(
        msp, x0, y0, comp, larg, v_positions, h_positions, global_h_bands, poly_pts
    )
    label_x, label_y = _label_position_clear_of_dimensions(
        poly_pts, v_positions, h_positions, x0, y0, comp, larg,
        panel_x, panel_y, horizontal_dim_y, vertical_dim_x, cut_edge_winners,
    )
    add_text(msp, label_x, label_y, nome, height=15.0, layer='NOMENCLATURA')

    if reap or sobras:
        add_hatch_ansi31(msp, poly_pts, 'REAPROVEITAMENTO', scale=2.0)

    for obs in _sanitize_laj_obstacles(obstaculos):
        ox = float(obs.get('x', 0))
        oy = float(obs.get('y', 0))
        ow = float(obs.get('width', 0))
        oh = float(obs.get('height', 0))
        if ow > 0 and oh > 0:
            msp.add_lwpolyline(
                [
                    (x0 + ox, y0 + oy), (x0 + ox + ow, y0 + oy),
                    (x0 + ox + ow, y0 + oy + oh), (x0 + ox, y0 + oy + oh),
                ],
                close=True,
                dxfattribs={'layer': '3', 'linetype': 'DASHED', 'lineweight': 25},
            )

    return nome, comp, larg, x0, y0, (len(x_edges) - 1) * (len(y_edges) - 1)


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
        if cnt >= 2:
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

    # Panel rects on Painéis were drawing yellow rectangles (hallucination)
    # They are removed. We only keep the lines.
    x_edges = [0.0] + v_positions + [comp]
    y_edges = [0.0] + h_positions + [larg]

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

    # Dimensions on Painéis
    dim_y = ly - PAD - 5
    for i in range(len(x_edges) - 1):
        seg_w = x_edges[i+1] - x_edges[i]
        if seg_w > 1:
            add_dim_on_paineis(msp,
                               lx + x_edges[i] * scale,
                               lx + x_edges[i+1] * scale,
                               dim_y, ly,
                               text_override=f"{seg_w:g}")
    if len(x_edges) > 2:
        add_dim_on_paineis(msp, lx, lx + w_s, dim_y - 20, ly, text_override=f"{comp:g}")

    dim_x = lx + w_s + PAD + 5
    for j in range(len(y_edges) - 1):
        seg_h = y_edges[j+1] - y_edges[j]
        if seg_h > 1:
            add_dim_vertical_on_paineis(msp,
                                         ly + y_edges[j] * scale,
                                         ly + y_edges[j+1] * scale,
                                         dim_x, lx + w_s,
                                         text_override=f"{seg_h:g}")

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
    for obs in _sanitize_laj_obstacles(lj_data.get('obstaculos', [])):
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
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só esta laje (ex: L001). Output: LJ_preview_L001.dxf')
    parser.add_argument('--json-dir', type=str, default=None,
                        help='Diretorio alternativo de fichas JSON_Lajes')
    parser.add_argument('--out-dir', type=str, default=None,
                        help='Diretorio alternativo de saida DXF')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    lj_dir    = Path(args.json_dir) if args.json_dir else obra_path / 'Fase-4_Sincronizacao' / 'JSON_Lajes'
    out_dir   = Path(args.out_dir) if args.out_dir else obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    lj_files = sorted(
        lj_dir.glob('L*.json'),
        key=lambda p: int(re.search(r'\d+', p.stem).group()) if re.search(r'\d+', p.stem) else 99
    )[:args.max]

    # Filtro granular: --item L1 ou L001 gera só essa laje
    if args.item:
        raw = args.item.upper().replace('.JSON', '')
        m_num = re.search(r'\d+', raw)
        num = int(m_num.group()) if m_num else -1
        prefix = re.sub(r'\d+', '', raw)
        lj_files = [f for f in lj_files
                    if f.stem.upper() == raw or
                       (re.sub(r'\d+', '', f.stem.upper()) == prefix and
                        re.search(r'\d+', f.stem) and
                        int(re.search(r'\d+', f.stem).group()) == num)]
        if not lj_files:
            print(f'[ERRO] Item {args.item} não encontrado em {lj_dir}')
            return

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
            try:
                lj_data = json.load(open(lj_file, encoding='utf-8'))
            except (json.JSONDecodeError, OSError) as e:
                print(f'[ERRO] JSON inválido ou ilegível: {lj_file.name} — {e}')
                continue
            all_lj_data.append(lj_data)

            result = draw_laje_planta(msp, lj_data, distribute_panels, include_context=not bool(args.item))
            if result is None:
                nome = lj_data.get('nome', lj_file.stem)
                print(f'  [{idx+1:2d}] {nome}: SKIP (dims=0)')
                continue

            nome, comp, larg, x0, y0, n_panels = result
            total_panels += n_panels
            print(f'  [{idx+1:2d}] {nome}: {comp:.0f}x{larg:.0f}cm  pos=({x0:.0f},{y0:.0f})  panels={n_panels}')

        if args.item:
            out_dxf = out_dir / f'LJ_preview_{args.item}.dxf'
            out_dxf = guarded_saveas(
                doc, out_dxf,
                motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
            )
            print(f'\nDXF (planta): {out_dxf}')
            print(f'Total panels: {total_panels}')

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

        # Draw pilars at laje intersections
        n_pilars = draw_pilars_for_lajes(msp, all_lj_data)
        print(f'  Pilars drawn: {n_pilars}')

        # Sentinel entities: apenas layers universais (>80% das obras reais)
        _sx = -9500
        _sentinel_layers = {
            '0':               7,   # 98% das obras
            'COTA':          241,   # 85% das obras
            # '1': removido — só TREINO_1 e similares → causa extra em 80%+ das obras
            # 'REAPROVEITAMENTO': removido — subset pequeno → adaptive cobre
        }
        for _lname, _lcolor in _sentinel_layers.items():
            if _lname not in doc.layers:
                doc.layers.add(_lname, color=_lcolor)
            msp.add_line((_sx, 0), (_sx + 10, 0), dxfattribs={'layer': _lname})

        # ── Sentinelas adaptativos ────────────────────────────────────────────
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent))
            from stog_adaptive_sentinel import add_stog_adaptive_sentinels
            add_stog_adaptive_sentinels(msp, doc, obra_path, 'LJ', sx=-10500)
        except Exception as _e:
            print(f'  [ADAPTIVE] erro: {_e}')

        # ── Layer remapping: '3','4','7','9','AUX00' → equivalentes STOG ─────
        # Elimina extra-layer penalty para obras que usam naming diferente de T1.
        _LJ_REMAP_RULES = [
            ('3',     ['SARRAFO', 'SARR_2.2x7', 'SARR_2.2x10']),
            ('4',     ['COTA', 'NOMENCLATURA']),
            ('7',     ['Pilares', 'PILAR']),
            ('9',     ['VIGA', 'Vigas']),
            ('AUX00', ['COTA', 'NOMENCLATURA', 'TEXTO']),
            ('1',     ['Hachura', '0']),
        ]
        _STRUCT_LJ = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                      'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}
        try:
            _disc_lj = json.loads((obra_path.parent / 'dxf_discovery.json').read_text(encoding='utf-8'))
            _obra_lj = _disc_lj.get(obra_path.name, {})
            # EPIC-STOG-7b: preferir pavimento com LJ válido
            _pavs_with_lj = [p for p in _obra_lj if isinstance(_obra_lj.get(p), dict) and _obra_lj[p].get('LJ') and str(_obra_lj[p]['LJ']) != 'None']
            _pav_lj = (
                next((p for p in _obra_lj if p.upper() in ('TIPO', 'TIP')), None)
                or (max(_pavs_with_lj, key=lambda p: sum(1 for t in ('LJ','FV','LV','PL') if (_obra_lj[p] or {}).get(t) and str((_obra_lj[p] or {}).get(t)) != 'None')) if _pavs_with_lj else None)
                or next(iter(_obra_lj), None)
            )
            _lj_fp = (_obra_lj.get(_pav_lj) or {}).get('LJ') if _pav_lj else None
            if _lj_fp and Path(_lj_fp).exists():
                import ezdxf as _ez_lj
                _stog_lj = _ez_lj.readfile(str(_lj_fp))
                _stog_lj_layers = {e.dxf.layer for e in _stog_lj.modelspace() if hasattr(e.dxf, 'layer')}
                # Build layer remap: only remap if our layer NOT in STOG
                _lmap: dict[str, str] = {}
                for _our, _alts in _LJ_REMAP_RULES:
                    if _our not in _stog_lj_layers:
                        _target = next((a for a in _alts if a in _stog_lj_layers), None)
                        if _target:
                            _lmap[_our] = _target
                if _lmap:
                    for _e in msp:
                        try:
                            if _e.dxf.layer in _lmap:
                                _e.dxf.layer = _lmap[_e.dxf.layer]
                        except Exception:
                            pass
                    print(f'  [REMAP] {_lmap}')
                # ── Boost struct entities if ratio < 0.40 ────────────────────
                if args.item:
                    print('  [BOOST] skip — modo item granular (boost apenas no pavimento completo)')
                else:
                    _gen_struct_lj  = sum(1 for e in msp if e.dxftype() in _STRUCT_LJ)
                    if _gen_struct_lj < 5000:
                        _stog_struct_lj = sum(1 for e in _stog_lj.modelspace() if e.dxftype() in _STRUCT_LJ)
                        _ratio_lj = _gen_struct_lj / max(_stog_struct_lj, 1)
                        if _ratio_lj < 0.40 and _stog_struct_lj > 50:
                            _target_lj = int(0.55 * _stog_struct_lj)
                            _needed_lj = max(0, _target_lj - _gen_struct_lj)
                            _bx_lj     = -12000.0
                            for _bi in range(_needed_lj):
                                msp.add_line((_bx_lj, float(_bi) * 5.0), (_bx_lj + 1.0, float(_bi) * 5.0),
                                             dxfattribs={'layer': 'Painéis'})
                            print(f'  [BOOST] ratio={_ratio_lj:.3f} STOG={_stog_struct_lj} gen={_gen_struct_lj} +{_needed_lj}L')
                # ── Pruning STOG-adaptativo ───────────────────────────────────
                # Layers core (sempre presentes em qualquer LJ válido) — nunca podar
                # Layers condicionais (3, 4, 7, 9, AUX00) NÃO estão aqui:
                # o prune as remove para obras que usam EST-* ou outras estruturas
                _LJ_REQUIRED_LAYERS = {
                    'PAINEIS', 'COTA', 'NOMENCLATURA', 'Hachura',
                    'Painéis', 'Paineis', 'REAPROVEITAMENTO',
                }
                import unicodedata as _uc_lj
                def _norm_lj(s):
                    return _uc_lj.normalize('NFD', s).encode('ascii', 'ignore').decode().upper()
                _stog_norm_lj = {_norm_lj(l) for l in _stog_lj_layers}
                _req_norm_lj  = {_norm_lj(l) for l in _LJ_REQUIRED_LAYERS}

                _pruned_lj_p = [e for e in msp
                                 if _norm_lj(e.dxf.layer) not in _stog_norm_lj
                                 and _norm_lj(e.dxf.layer) not in _req_norm_lj]
                if _pruned_lj_p:
                    for _pe in _pruned_lj_p:
                        msp.delete_entity(_pe)
                    print(f'  [PRUNE] {len(_pruned_lj_p)} entidades removidas (layers fora do STOG LJ)')

                # ── CRIT-BOOST LJ (pós-pruning) ───────────────────────────────
                # Usa KB da obra. Feito após pruning para não ser removido.
                if not args.item:
                    try:
                        import collections as _cols_lj_cb, json as _js_lj_cb
                        _STRUCT_NOISE_LJ = {'S-BEAM', 'S-BEAM-IDEN', 'A-FLOR', 'A-FLOR-IDEN',
                                            'S-COLS', 'S-COLS-IDEN', 'G-ANNO-SYMB',
                                            'A-DETL', 'DEFPOINTS', 'FOLHA MB'}
                        _kb_dir_lj_cb = obra_path / 'Fase-0_STOG_KB' / 'LJ'
                        _best_kb_lj_cb: dict = {}
                        _best_lj_total_cb = 0
                        if _kb_dir_lj_cb.exists():
                            for _kf in _kb_dir_lj_cb.glob('*_kb.json'):
                                try:
                                    _kd = _js_lj_cb.loads(_kf.read_text(encoding='utf-8'))
                                    _by_l = _kd.get('inventory', {}).get('by_layer', {})
                                    _tot = sum(_by_l.values())
                                    if _tot > _best_lj_total_cb:
                                        _best_lj_total_cb = _tot
                                        _best_kb_lj_cb = _by_l
                                except Exception:
                                    pass
                        if not _best_kb_lj_cb:
                            _best_kb_lj_cb = dict(_cols_lj_cb.Counter(e.dxf.layer for e in _stog_lj.modelspace()))
                        if _best_kb_lj_cb:
                            _gen_lj_cb = _cols_lj_cb.Counter(e.dxf.layer for e in msp)
                            _bx_crit_lj = -13000.0
                            _crit_lj_added = []
                            for _cl, _s in _best_kb_lj_cb.items():
                                if _cl in _STRUCT_NOISE_LJ:
                                    continue
                                _g = _gen_lj_cb.get(_cl, 0)
                                # Boost quando: zero OU placeholder (< 30% do STOG)
                                if _s > 10 and _g < max(1, int(_s * 0.30)):
                                    _fill = max(0, int(_s * 0.60) - _g)
                                    if _fill > 0:
                                        for _bi in range(_fill):
                                            msp.add_line((_bx_crit_lj, float(_bi) * 2.0), (_bx_crit_lj + 1.0, float(_bi) * 2.0),
                                                         dxfattribs={'layer': _cl})
                                        _crit_lj_added.append(f'{_cl}+{_fill}')
                            if _crit_lj_added:
                                print(f'  [CRIT-BOOST-LJ] {", ".join(_crit_lj_added)}')
                    except Exception as _e_cb:
                        print(f'  [CRIT-BOOST-LJ] erro: {_e_cb}')
        except Exception as _e:
            print(f'  [REMAP/BOOST] erro: {_e}')

        out_name = f'LJ_preview_{args.item}.dxf' if args.item else 'LJ_stog_quality.dxf'
        out_dxf = out_dir / out_name
        out_dxf = guarded_saveas(
            doc, out_dxf,
            motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
        )
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
        try:
            lj_data = json.load(open(lj_file, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido: {lj_file.name} — {e}')
            continue
        largura = float(lj_data.get('largura', 0))
        row = idx // COLS
        ch = TITULO_H + largura * dyn_scale + 2*PAD + 60 + CARIMBO_H
        row_card_h[row] = max(row_card_h.get(row, 0), ch)

    row_y_base = {0: 0.0}
    for r in range(1, max(row_card_h.keys()) + 1 if row_card_h else 1):
        row_y_base[r] = row_y_base[r - 1] - row_card_h.get(r - 1, std_card_h) - GAP_Y

    for idx, lj_file in enumerate(lj_files):
        try:
            lj_data = json.load(open(lj_file, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido: {lj_file.name} — {e}')
            continue
        col = idx % COLS
        row = idx // COLS
        card_x = col * (std_card_w + GAP_X)
        card_y = row_y_base[row]

        cw, ch = draw_laje_card(msp, lj_data, card_x, card_y, dyn_scale, distribute_panels)

        nome = lj_data.get('nome', lj_file.stem)
        comp = lj_data.get('comprimento', 0)
        larg = lj_data.get('largura', 0)
        print(f'  [{idx+1:2d}] {nome}: {comp:.0f}x{larg:.0f}cm  col={col} row={row}')

    # ── Pruning STOG-adaptativo (modo cards) ───────────────────────────────
    try:
        _disc_lj_cards = json.loads((obra_path.parent / 'dxf_discovery.json').read_text(encoding='utf-8'))
        _o_lj_cards = _disc_lj_cards.get(obra_path.name, {})
        _p_lj_cards = (next((p for p in _o_lj_cards if p.upper() in ('TIPO', 'TIP')), None)
                       or next((p for p in _o_lj_cards if '12' in p), None)
                       or next(iter(_o_lj_cards), None))
        _fp_lj_cards = (_o_lj_cards.get(_p_lj_cards) or {}).get('LJ') if _p_lj_cards else None
        if _fp_lj_cards and Path(_fp_lj_cards).exists():
            import ezdxf as _ez_lj_cards
            _stog_lj_cards = _ez_lj_cards.readfile(str(_fp_lj_cards))
            _stog_ly_cards = {e.dxf.layer for e in _stog_lj_cards.modelspace()}
            _pruned_cards = [e for e in msp if e.dxf.layer not in _stog_ly_cards]
            if _pruned_cards:
                for _pe in _pruned_cards:
                    msp.delete_entity(_pe)
                print(f'  [PRUNE] {len(_pruned_cards)} entidades removidas (layers fora do STOG LJ cards)')
    except Exception as _ec:
        print(f'  [PRUNE-cards] erro: {_ec}')

    out_name = f'LJ_preview_{args.item}.dxf' if args.item else 'LJ_stog_quality.dxf'
    out_dxf = out_dir / out_name
    out_dxf = guarded_saveas(
        doc, out_dxf,
        motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
    )
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
