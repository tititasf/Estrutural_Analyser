#!/usr/bin/env python3
"""
combinar_vigas_dxf.py — Coloca todas as vigas em um unico DXF para analise.

Cada viga e traduzida para uma posicao em grid (linha x coluna).
O ponto de ancoragem e o insert_x, insert_y da viga (centro do bloco de titulo STOG).

Uso:
  python combinar_vigas_dxf.py                   # todas as 249 vigas
  python combinar_vigas_dxf.py --obra Obra_TREINO_1
  python combinar_vigas_dxf.py --cols 10          # 10 colunas por linha
"""
import sys, io, json, re, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

PARAMS_FILE  = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json'
CATALOG_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json'
OUT_DIR      = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/combined')

# Importar o reconstrutor
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

# Layer name constants (with correct accents for LAYER_DEFS compatibility)
_LY_PAINEIS = 'Painéis'       # Paineis
_LY_TEXTO_SECAO = 'Texto Seção'  # Texto Secao
_LY_DEMARCACAO1 = 'Demarcação 1'  # Demarcacao 1


def _line_in_face(l, face, margin=8):
    """Verifica se uma linha esta dentro dos bounds de uma face (com margem)."""
    xmin = face.get('face_x_min'); xmax = face.get('face_x_max')
    ymin = face.get('y_min');      ymax = face.get('y_max')
    if not all([xmin is not None, xmax is not None, ymin is not None, ymax is not None]):
        return True  # sem bounds definidos: nao filtrar
    mx = (l['x1'] + l['x2']) / 2
    my = (l['y1'] + l['y2']) / 2
    return (xmin - margin <= mx <= xmax + margin and
            ymin - margin <= my <= ymax + margin)


# ---------------------------------------------------------------------------
# Section zone detection & gap compaction
# ---------------------------------------------------------------------------
# No DXF original, vigas frequentemente tem a secao transversal (corte)
# posicionada 300-1200u abaixo da elevacao (face). Quando ambas sao incluidas
# no bbox, o conteudo traduzido fica com um gap visual grande entre face e
# secao. A compactacao fecha esse gap para SECTION_GAP_TARGET.
# ---------------------------------------------------------------------------

SECTION_DETECT_THRESHOLD = 200  # min gap para considerar zone separado
SECTION_GAP_TARGET = 30         # gap alvo apos compactacao


def _collect_all_rendered_ys(vdata):
    """Collect Y values from ALL elements that translate_viga renders,
    including hatches and cotas. Used for multi-gap detection."""
    fa = vdata.get('face_a') or {}
    all_ys = []

    # face_a hlines/vlines
    for hl in (fa.get('face_hlines') or []):
        all_ys.append(hl['y'])
    for vl in (fa.get('face_vlines') or []):
        all_ys.extend([vl['y1'], vl['y2']])

    # face_b
    fb = vdata.get('face_b') or {}
    for hl in (fb.get('face_hlines') or []):
        all_ys.append(hl['y'])
    for vl in (fb.get('face_vlines') or []):
        all_ys.extend([vl['y1'], vl['y2']])

    # sarr22_lines filtrados
    for sl in (vdata.get('sarr22_lines') or []):
        cx = (sl['x1'] + sl['x2']) / 2
        cy = (sl['y1'] + sl['y2']) / 2
        if R._x_in_face_range(cx, fa) and R._y_in_face_range(cy, fa):
            all_ys.extend([sl['y1'], sl['y2']])

    # sarr35_lines filtrados
    for sl in (vdata.get('all_sarr35_lines') or []):
        if _line_in_face(sl, fa):
            all_ys.extend([sl['y1'], sl['y2']])

    # Polys (concreto, sarr35, madeira, sarr22, panel)
    for polys_key in ('all_concreto_polys', 'all_sarr35_polys', 'all_madeira_polys',
                      'all_sarr22_polys', 'panel_polys'):
        for poly in R._filter_polys(vdata.get(polys_key) or [], fa):
            for v in (poly.get('vertices') or []):
                if len(v) >= 2:
                    all_ys.append(v[1])

    # Hatches
    for h in R._filter_hatches(vdata.get('hatches_data') or [], fa):
        for boundary in h.get('boundary_polys', []):
            for pt in (boundary or []):
                if len(pt) >= 2:
                    all_ys.append(pt[1])

    # Cota dims
    for dim in (vdata.get('cota_dims') or []):
        for yk in ('y1', 'y2', 'y3', 'text_y'):
            yv = dim.get(yk)
            if yv is not None:
                all_ys.append(yv)

    return all_ys


def _compute_section_gaps(vdata):
    """Compute compaction shifts for section zone elements.

    Two-phase compaction:
    1. Close ALL gaps > SECTION_DETECT_THRESHOLD to SECTION_GAP_TARGET
    2. If after gap-closing, elements below face_a.y_min still span > 200u
       from the face, add a proportional compression shift

    Returns a list of (boundary_y, cumulative_shift) tuples sorted by
    boundary_y ascending. Elements at y_orig < boundary_y get shifted up by
    the corresponding cumulative_shift.

    Returns empty list if no compaction needed.
    """
    fa = vdata.get('face_a') or {}
    fa_ymin = fa.get('y_min')
    fa_ymax = fa.get('y_max')
    if fa_ymin is None or fa_ymax is None:
        return []

    all_ys = _collect_all_rendered_ys(vdata)

    if len(all_ys) < 4:
        return []

    sorted_ys = sorted(set(round(y, 1) for y in all_ys))

    # Phase 1: Find ALL gaps > threshold
    gaps = []
    for i in range(1, len(sorted_ys)):
        gap = sorted_ys[i] - sorted_ys[i - 1]
        if gap >= SECTION_DETECT_THRESHOLD:
            face_y_min = sorted_ys[i]      # top of gap
            section_y_max = sorted_ys[i-1]  # bottom of gap
            gaps.append((face_y_min, section_y_max, gap))

    if not gaps:
        return []

    # Sort gaps by boundary_y descending (top gaps first) to compute
    # cumulative shifts for elements below multiple gaps
    gaps.sort(key=lambda g: -g[0])

    result = []
    cumulative_shift = 0
    for face_y_min, section_y_max, gap in gaps:
        shift_this_gap = gap - SECTION_GAP_TARGET
        cumulative_shift += shift_this_gap
        result.append((face_y_min, cumulative_shift))

    # Phase 2: After gap-closing, check if content below face still has a
    # residual span that keeps sub-face elements far from the face zone.
    # This catches intermediate annotation elements (cotas, hatches) that sit
    # between the section core and face_a.y_min with sub-threshold gaps.
    def _apply_shifts(y):
        for boundary_y, cs in sorted(result, key=lambda r: r[0]):
            if y < boundary_y:
                return y + cs
        return y

    below_face = [_apply_shifts(y) for y in all_ys if y < fa_ymin]
    if below_face:
        max_below_shifted = max(below_face)
        residual_gap = fa_ymin - max_below_shifted
        if residual_gap > SECTION_GAP_TARGET * 2:
            extra_shift = residual_gap - SECTION_GAP_TARGET
            # Add extra_shift to ALL existing Phase 1 entries (elements below
            # Phase 1 boundaries also need to close the residual gap)
            result = [(bnd, cs + extra_shift) for bnd, cs in result]
            # Add new entry at fa_ymin for elements between the highest Phase 1
            # boundary and fa_ymin (they need ONLY the residual closure)
            result.append((fa_ymin, extra_shift))

    # Sort by boundary_y ascending for lookup
    result.sort(key=lambda r: r[0])
    return result


def _compute_section_boundary(vdata):
    """Legacy API: returns info about the largest gap for backward compatibility.

    Returns (face_y_min_boundary, section_y_max_boundary, gap) or None.
    """
    fa = vdata.get('face_a') or {}
    fa_ymin = fa.get('y_min')
    fa_ymax = fa.get('y_max')
    if fa_ymin is None or fa_ymax is None:
        return None

    all_ys = _collect_all_rendered_ys(vdata)

    if len(all_ys) < 4:
        return None

    sorted_ys = sorted(set(round(y, 1) for y in all_ys))
    max_gap = 0
    gap_idx = -1
    for i in range(1, len(sorted_ys)):
        gap = sorted_ys[i] - sorted_ys[i - 1]
        if gap > max_gap:
            max_gap = gap
            gap_idx = i

    if max_gap < SECTION_DETECT_THRESHOLD:
        return None

    section_y_max = sorted_ys[gap_idx - 1]
    face_y_min = sorted_ys[gap_idx]

    return (face_y_min, section_y_max, max_gap)


def compute_content_bbox(vdata):
    """Bounding box real de todos os elementos de uma viga (exceto cotas/textos).
    Aplica os mesmos filtros de face_a que translate_viga usa para evitar que
    sarr22_lines / polys de contextos externos corrompam o calculo de ox/oy.

    Quando ha section zone separada (gap > 200u entre face e secao transversal),
    compacta o gap para SECTION_GAP_TARGET e retorna o bbox compactado.
    """
    xs, ys = [], []
    fa = vdata.get('face_a') or {}

    def _pts(pts):
        for p in (pts or []):
            if len(p) >= 2:
                xs.append(p[0]); ys.append(p[1])

    def _polys(polys):
        for poly in (polys or []):
            _pts(poly.get('vertices') or [])

    # face_a hlines/vlines
    for hl in (fa.get('face_hlines') or []):
        ys.extend([hl['y'], hl['y']])
        cx_hl = (hl['x1'] + hl['x2']) / 2
        if R._x_in_face_range(cx_hl, fa, margin_factor=1.0):
            xs.extend([hl['x1'], hl['x2']])
    for vl in (fa.get('face_vlines') or []):
        ys.extend([vl['y1'], vl['y2']])
        if R._x_in_face_range(vl['x'], fa, margin_factor=1.0):
            xs.extend([vl['x'], vl['x']])
    # face_b hlines/vlines: APENAS ys
    fb_data = vdata.get('face_b') or {}
    for hl in (fb_data.get('face_hlines') or []):
        ys.extend([hl['y'], hl['y']])
    for vl in (fb_data.get('face_vlines') or []):
        ys.extend([vl['y1'], vl['y2']])

    # Polys
    _polys(R._filter_polys(vdata.get('all_concreto_polys') or [], fa))
    _polys(R._filter_polys(vdata.get('all_sarr35_polys') or [], fa))
    _polys(R._filter_polys(vdata.get('all_madeira_polys') or [], fa))
    _polys(R._filter_polys(vdata.get('all_sarr22_polys') or [], fa))
    _polys(R._filter_polys(vdata.get('panel_polys') or [], fa))

    # sarr22_lines
    for sl in (vdata.get('sarr22_lines') or []):
        cx = (sl['x1'] + sl['x2']) / 2
        cy = (sl['y1'] + sl['y2']) / 2
        if R._x_in_face_range(cx, fa) and R._y_in_face_range(cy, fa):
            xs.extend([sl['x1'], sl['x2']]); ys.extend([sl['y1'], sl['y2']])

    # all_sarr35_lines
    for sl in (vdata.get('all_sarr35_lines') or []):
        if _line_in_face(sl, fa):
            xs.extend([sl['x1'], sl['x2']]); ys.extend([sl['y1'], sl['y2']])

    # Grade NAO entra no bbox (grade pode ter coords longe de face_a)

    if not xs:
        return None

    # --- Compactacao de section zone (multi-gap) ---
    gap_shifts = _compute_section_gaps(vdata)
    if gap_shifts:
        ys_compacted = []
        for y in ys:
            # Find cumulative shift for this y: sum shifts for all gaps ABOVE y
            shift = 0
            for boundary_y, cumul_shift in gap_shifts:
                if y < boundary_y:
                    shift = cumul_shift
                    break
            ys_compacted.append(y + shift)
        return (min(xs), max(xs), min(ys_compacted), max(ys_compacted))

    return (min(xs), max(xs), min(ys), max(ys))


def _dedup_lines(lines):
    """Remove linhas duplicadas exatas (mesmo x1,y1,x2,y2)."""
    seen = set()
    result = []
    for l in lines:
        key = (round(l['x1'], 1), round(l['y1'], 1), round(l['x2'], 1), round(l['y2'], 1))
        if key not in seen:
            seen.add(key)
            result.append(l)
    return result


def translate_viga(msp, vdata, ox, oy, cell_bounds=None, section_y_shift=None):
    """Reconstroi viga aplicando offset (ox, oy) a todas as coordenadas.
    cell_bounds: (cell_x, cell_y, cell_w, cell_h) -- se fornecido, elementos
    completamente fora da celula sao suprimidos (evita 'pedacos soltos').

    section_y_shift: list of (boundary_y, cumulative_shift) tuples from
    _compute_section_gaps(). Elements below a boundary get the corresponding
    cumulative shift added to oy.
    """
    # Section zone compaction helper
    def _sy(y_orig):
        """Retorna o oy ajustado para o y original: se esta na section zone,
        aplica o shift extra para compactar o gap."""
        if not section_y_shift:
            return oy
        for boundary, cumul_shift in section_y_shift:
            if y_orig < boundary:
                return oy + cumul_shift
        return oy

    def _tl(x, y):
        """Translate com compactacao de section zone."""
        return (x + ox, y + _sy(y))

    def _tv(verts):
        """Translate vertices com compactacao de section zone."""
        return [(v[0] + ox, v[1] + _sy(v[1])) for v in verts]

    # Helpers de clipping espacial
    def _in_cell_line(tx1, ty1, tx2, ty2, tol=100):
        if cell_bounds is None: return True
        cx0, cy0, cw, ch = cell_bounds
        def _pt(x, y):
            return (cx0 - tol) <= x <= (cx0 + cw + tol) and (cy0 - tol) <= y <= (cy0 + ch + tol)
        return _pt(tx1, ty1) or _pt(tx2, ty2)

    def _in_cell_pt(tx, ty, tol=100):
        if cell_bounds is None: return True
        cx0, cy0, cw, ch = cell_bounds
        return (cx0 - tol) <= tx <= (cx0 + cw + tol) and (cy0 - tol) <= ty <= (cy0 + ch + tol)

    def _clip_line(tx1, ty1, tx2, ty2, margin=50):
        """Liang-Barsky: clip line to cell."""
        if cell_bounds is None:
            return tx1, ty1, tx2, ty2
        cx0, cy0, cw, ch = cell_bounds
        xmin, xmax = cx0 - margin, cx0 + cw + margin
        ymin, ymax = cy0 - margin, cy0 + ch + margin
        dx = tx2 - tx1; dy = ty2 - ty1
        t0, t1 = 0.0, 1.0
        for p, q in [(-dx, tx1 - xmin), (dx, xmax - tx1),
                     (-dy, ty1 - ymin), (dy, ymax - ty1)]:
            if abs(p) < 1e-10:
                if q < 0: return None
            else:
                t = q / p
                if p < 0: t0 = max(t0, t)
                else:      t1 = min(t1, t)
        if t0 > t1: return None
        return (tx1 + t0*dx, ty1 + t0*dy, tx1 + t1*dx, ty1 + t1*dy)

    fa = vdata.get('face_a') or {}
    fb = vdata.get('face_b') or {}
    sg = vdata.get('section_geometry') or {}
    aberturas = vdata.get('aberturas') or []
    continuacoes = vdata.get('continuacoes') or []
    panel_texts = vdata.get('panel_texts_positioned') or []
    sarr22_lines      = vdata.get('sarr22_lines') or []
    cota_dims         = vdata.get('cota_dims') or []
    panel_polys        = R._filter_polys(vdata.get('panel_polys') or [], fa)
    all_concreto_polys = R._filter_polys(vdata.get('all_concreto_polys') or [], fa)
    all_madeira_polys  = R._filter_polys(vdata.get('all_madeira_polys') or [], fa)
    all_sarr35_polys   = R._filter_polys(vdata.get('all_sarr35_polys') or [], fa)
    hatches_data       = R._filter_hatches(vdata.get('hatches_data') or [], fa)

    # Filtrar sarr35_lines
    raw_sarr35_lines = vdata.get('all_sarr35_lines') or []
    sarr35_lines_fa = [l for l in raw_sarr35_lines if _line_in_face(l, fa)]
    sarr35_lines_fb = [l for l in raw_sarr35_lines if fb and _line_in_face(l, fb)
                       and not _line_in_face(l, fa)]
    sarr35_lines = _dedup_lines(sarr35_lines_fa + sarr35_lines_fb)

    # Legacy tl/tv for backward compatibility (used by code that does not
    # need section compaction, e.g., grade uses tg)
    def tl(x, y):
        return _tl(x, y)

    def tv(verts):
        return _tv(verts)

    # --- Section X centering correction ---
    # Section geometry (concreto/sarr35/madeira) may be at a different X than
    # face_a hlines in the original DXF. After common ox translation, they appear
    # disconnected (280-570u gap). Compute correction to re-center onto face_a cx.
    #
    # KEY: filter polys by Y before computing centroid.
    # Some polys of section-type exist in the face view zone (cy >= fa_y_min).
    # Including those would pull sec_cx_orig toward face X, causing overcorrection.
    # Only use polys whose centroid Y is in the section zone (cy < fa_y_min - 50).
    fa_x_min = fa.get('face_x_min', 0)
    fa_x_max = fa.get('face_x_max', 0)
    fa_cx_orig = (fa_x_min + fa_x_max) / 2
    _fa_y_min_raw = fa.get('y_min')  # face_a y_min in original DXF
    _sec_polys_all = all_concreto_polys + all_sarr35_polys + all_madeira_polys
    # Filter to section-zone polys only (below face bottom)
    _sec_poly_cx_list = []
    for _pp in _sec_polys_all:
        _vv = [v for v in (_pp.get('vertices') or []) if len(v) >= 2]
        if not _vv:
            continue
        _cy = sum(v[1] for v in _vv) / len(_vv)
        _cx = sum(v[0] for v in _vv) / len(_vv)
        # Only include if in section zone (below face bottom by margin)
        if _fa_y_min_raw is None or _cy < (_fa_y_min_raw - 50):
            _sec_poly_cx_list.append(_cx)
    # Use all section polys (no Y filter - section polys can be in same Y as face).
    _sec_poly_cx_list = []
    for _pp in _sec_polys_all:
        _vv = [v for v in (_pp.get('vertices') or []) if len(v) >= 2]
        if _vv:
            _sec_poly_cx_list.append(sum(v[0] for v in _vv) / len(_vv))

    # Criteria: gap > EPS (truly isolated) AND tight cluster (spread < 200u).
    # Wide-spread clusters (multi-panel vigas) are skipped — mean would be unreliable.
    # Gap threshold = 260u (above eps=250 with small margin).
    SEC_GAP_MIN = 260   # min gap from fa_cx to apply correction
    SEC_SPREAD_MAX = 200  # max spread of section poly centroids for reliable mean
    if _sec_poly_cx_list and fa_x_max > fa_x_min:
        sec_cx_orig = sum(_sec_poly_cx_list) / len(_sec_poly_cx_list)
        raw_corr = fa_cx_orig - sec_cx_orig
        spread = max(_sec_poly_cx_list) - min(_sec_poly_cx_list)
        # Additional guard: only correct if sec_cx is INSIDE the face X range (±50u).
        # If section polys are outside face range, correction would move them away
        # from nearby sarr22 lines, creating new isolation.
        _sec_inside_face = (fa_x_min - 50 <= sec_cx_orig <= fa_x_max + 50)
        if abs(raw_corr) > SEC_GAP_MIN and spread < SEC_SPREAD_MAX and _sec_inside_face:
            sec_x_corr = raw_corr
        else:
            sec_x_corr = 0.0
    else:
        sec_cx_orig = fa_cx_orig
        sec_x_corr = 0.0
    ox_sec = ox + sec_x_corr

    def _tl_sec(x, y):
        """Translate com X correction para secao transversal."""
        return (x + ox_sec, y + _sy(y))

    def _tv_sec(verts):
        """Translate vertices com X correction para secao transversal."""
        return [(v[0] + ox_sec, v[1] + _sy(v[1])) for v in verts]

    # 1-3. Paineis -- linhas H e V (margin=0: evita bleed para celula vizinha)
    # Sem filtros de X/Y: incluir TODAS as linhas. Elementos soltos = problema de posicionamento.
    fb_x_min = fb.get('face_x_min', fa_x_min)
    fb_x_max = fb.get('face_x_max', fa_x_max)

    for hl in fa.get('face_hlines', []):
        tx1, ty = _tl(hl['x1'], hl['y']); tx2 = hl['x2'] + ox
        c = _clip_line(tx1, ty, tx2, ty, margin=0)
        if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': _LY_PAINEIS})
    for vl in fa.get('face_vlines', []):
        tx, ty1 = _tl(vl['x'], vl['y1']); ty2 = vl['y2'] + _sy(vl['y2'])
        c = _clip_line(tx, ty1, tx, ty2, margin=0)
        if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': _LY_PAINEIS})
    for hl in fb.get('face_hlines', []):
        tx1, ty = _tl(hl['x1'], hl['y']); tx2 = hl['x2'] + ox
        c = _clip_line(tx1, ty, tx2, ty, margin=0)
        if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': _LY_PAINEIS})
    for vl in fb.get('face_vlines', []):
        tx, ty1 = _tl(vl['x'], vl['y1']); ty2 = vl['y2'] + _sy(vl['y2'])
        c = _clip_line(tx, ty1, tx, ty2, margin=0)
        if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': _LY_PAINEIS})

    # 3a. Synthetic panel borders
    for face_data in (fa, fb):
        face_hlines = face_data.get('face_hlines') or []
        face_panels = face_data.get('panel_positions') or []
        panel_count = face_data.get('panel_count', 0)
        if panel_count <= 0 or not face_panels:
            continue
        if len(face_hlines) >= 4:
            continue
        f_y_min = face_data.get('y_min')
        f_y_max = face_data.get('y_max')
        face_w = face_data.get('total_width') or 0
        if f_y_min is None:
            continue
        INSET_TOP = 3.0
        if not face_hlines:
            panel_y_min = f_y_min
            panel_y_max = f_y_min + min(150, (f_y_max or f_y_min + 150) - f_y_min)
        else:
            threshold_w = max(face_w * 0.25, 50) if face_w > 0 else 50
            wide_hl = [h for h in face_hlines if h.get('len', 0) >= threshold_w]
            if len(wide_hl) >= 2:
                ys = sorted(set(h['y'] for h in wide_hl))
                panel_y_min = min(ys)
                upper_ys = [y for y in ys if y > panel_y_min + 5]
                panel_y_max = (min(upper_ys) - INSET_TOP) if upper_ys else (panel_y_min + 70)
            elif wide_hl:
                panel_y_min = min(h['y'] for h in wide_hl)
                panel_y_max = panel_y_min + 70
            else:
                panel_y_min = f_y_min
                panel_y_max = f_y_min + 70
        if panel_y_max <= panel_y_min:
            panel_y_max = panel_y_min + 56
        for pp in face_panels:
            xs = pp.get('x_start')
            xe = pp.get('x_end')
            if xs is None or xe is None:
                continue
            tx_s, ty_bot = _tl(xs, panel_y_min); tx_e = xe + ox
            tx_s2, ty_top = _tl(xs, panel_y_max)
            for p1, p2 in [((tx_s,ty_bot),(tx_e,ty_bot)), ((tx_s2,ty_top),(tx_e,ty_top)),
                           ((tx_s,ty_bot),(tx_s,ty_top)), ((tx_e,ty_bot),(tx_e,ty_top))]:
                c = _clip_line(p1[0], p1[1], p2[0], p2[1], margin=0)
                if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': _LY_PAINEIS})

    # Helper: centroide de poly traduzido dentro da celula?
    def _poly_in_cell(verts, tol=200, x_ofs=None):
        if not verts or cell_bounds is None: return True
        _ox_here = ox if x_ofs is None else (ox + x_ofs)
        tx_verts = [(_ox_here + v[0], v[1] + _sy(v[1])) for v in verts]
        cx = sum(v[0] for v in tx_verts) / len(tx_verts)
        cy = sum(v[1] for v in tx_verts) / len(tx_verts)
        return _in_cell_pt(cx, cy, tol=tol)

    # 3b. Paineis LWPOLYLINEs
    # Sem filtro de centroid X: incluir TODOS os panel_polys. Soltos = posicionamento.
    for pp in panel_polys:
        if not pp.get('vertices'):
            continue
        if _poly_in_cell(pp['vertices']):
            R.add_lwpoly(msp, tv(pp['vertices']), _LY_PAINEIS, closed=pp.get('closed', True))

    # 4. CONCRETO
    for cp in all_concreto_polys:
        if cp.get('vertices') and _poly_in_cell(cp['vertices'], x_ofs=sec_x_corr):
            R.add_lwpoly(msp, _tv_sec(cp['vertices']), 'CONCRETO', closed=cp.get('closed', True))
    if not all_concreto_polys:
        sc = sg.get('seccao_concreto')
        if sc and sc.get('vertices') and _poly_in_cell(sc['vertices'], x_ofs=sec_x_corr):
            R.add_lwpoly(msp, _tv_sec(sc['vertices']), 'CONCRETO', closed=sc.get('closed', True))

    # 5. SARR_3.5x7
    for sp in all_sarr35_polys:
        if sp.get('vertices') and _poly_in_cell(sp['vertices'], x_ofs=sec_x_corr):
            R.add_lwpoly(msp, _tv_sec(sp['vertices']), 'SARR_3.5x7', closed=sp.get('closed', True))
    if not all_sarr35_polys:
        for sp in sg.get('sarrafos_35x7', []):
            if sp.get('vertices') and _poly_in_cell(sp['vertices'], x_ofs=sec_x_corr):
                R.add_lwpoly(msp, _tv_sec(sp['vertices']), 'SARR_3.5x7', closed=sp.get('closed', True))

    # 5b. SARR_3.5x7 LINEs
    for sl in sarr35_lines:
        tx1, ty1 = _tl(sl['x1'], sl['y1']); tx2, ty2 = _tl(sl['x2'], sl['y2'])
        c = _clip_line(tx1, ty1, tx2, ty2)
        if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': 'SARR_3.5x7'})

    # 6. Madeira
    for mp in all_madeira_polys:
        if mp.get('vertices') and _poly_in_cell(mp['vertices'], x_ofs=sec_x_corr):
            R.add_lwpoly(msp, _tv_sec(mp['vertices']), 'Madeira', closed=mp.get('closed', True))
    if not all_madeira_polys:
        for mp in sg.get('barrotes_madeira', []):
            if mp.get('vertices') and _poly_in_cell(mp['vertices'], x_ofs=sec_x_corr):
                R.add_lwpoly(msp, _tv_sec(mp['vertices']), 'Madeira', closed=mp.get('closed', True))

    # 7. Aberturas
    for ab in aberturas:
        if ab.get('subtype') in ('pilar_face_a', 'pilar_face_b', 'pilar'):
            if ab.get('vertices'):
                if _poly_in_cell(ab['vertices']):
                    R.add_lwpoly(msp, tv(ab['vertices']), 'CONCRETO')
            else:
                xmn, xmx = ab['x_min'], ab['x_max']
                ymn, ymx = ab['y_min'], ab['y_max']
                cy_ab = (ymn + ymx) / 2
                cx_ab = (xmn + xmx) / 2 + ox
                cy_t = cy_ab + _sy(cy_ab)
                if _in_cell_pt(cx_ab, cy_t):
                    R.add_lwpoly(msp, tv([(xmn, ymn), (xmx, ymn), (xmx, ymx), (xmn, ymx)]), 'CONCRETO')

    # 8. Titulo
    ti = sg.get('titulo_insert')
    if ti:
        tx_ti, ty_ti = _tl_sec(ti['x'], ti['y'] + 5)
        if _in_cell_pt(tx_ti, ty_ti):
            msp.add_text(ti.get('titulo', ''), dxfattribs={
                'insert': (tx_ti, ty_ti), 'height': 8, 'layer': _LY_TEXTO_SECAO})
            secao = ti.get('secao', '')
            if secao:
                msp.add_text(secao, dxfattribs={
                    'insert': _tl_sec(ti['x'], ti['y'] - 10), 'height': 6, 'layer': _LY_TEXTO_SECAO})

    # 9. Continuacoes
    for cont in continuacoes:
        tx_c, ty_c = _tl(cont['x'], cont['y'])
        if _in_cell_pt(tx_c, ty_c):
            msp.add_text(cont['text'], dxfattribs={
                'insert': (tx_c, ty_c), 'height': 5, 'layer': _LY_TEXTO_SECAO})

    # 10. Labels de painel
    for pt in panel_texts:
        if not R._x_in_face_range(pt['x'], fa):
            continue
        tx_p, ty_p = _tl(pt['x'], pt['y'])
        if _in_cell_pt(tx_p, ty_p, tol=0):
            msp.add_text(pt['text'], dxfattribs={
                'insert': (tx_p, ty_p), 'height': 5, 'layer': 'NOMENCLATURA'})

    # 10b. Contagem de sarrafos
    for pl in vdata.get('panel_labels') or []:
        if not R._x_in_face_range(pl['x'], fa):
            continue
        tx_pl, ty_pl = _tl(pl['x'], pl['y'])
        if _in_cell_pt(tx_pl, ty_pl, tol=0):
            msp.add_text(pl['text'], dxfattribs={
                'insert': (tx_pl, ty_pl), 'height': 5, 'layer': 'NOMENCLATURA'})

    # 11. Hatches
    for h in hatches_data:
        pattern = h.get('pattern', 'SOLID')
        layer   = R.safe_layer(h.get('layer', '0'))
        if layer not in R.LAYER_DEFS:
            layer = 'Hachura'
        scale = h.get('scale') or 1.0
        for boundary in h.get('boundary_polys', []):
            if not boundary:
                continue
            # Determine if this hatch belongs to the section zone (needs X correction)
            # Section zone elements are at Y below face_a y_min in the original DXF.
            hatch_cy_orig = sum(p[1] for p in boundary) / len(boundary)
            _hatch_in_section = (
                sec_x_corr != 0.0 and
                _fa_y_min_raw is not None and
                hatch_cy_orig < (_fa_y_min_raw - 50)
            )
            _h_ox = ox_sec if _hatch_in_section else ox
            # Use consistent shift based on Y centroid to prevent stretching
            # when hatch boundary spans the section/face zone split
            hatch_cy = sum(p[1] for p in boundary) / len(boundary)
            hatch_oy = _sy(hatch_cy)
            tx_pts = [(p[0] + _h_ox, p[1] + hatch_oy) for p in boundary]
            ctr_x = sum(p[0] for p in tx_pts) / len(tx_pts)
            ctr_y = sum(p[1] for p in tx_pts) / len(tx_pts)
            if not _in_cell_pt(ctr_x, ctr_y, tol=5):
                continue
            HATCH_TOL = 50
            if cell_bounds is not None:
                hcx0, hcy0, hcw, hch = cell_bounds
                if not all((hcx0-HATCH_TOL) <= px <= (hcx0+hcw+HATCH_TOL) and
                           (hcy0-HATCH_TOL) <= py <= (hcy0+hch+HATCH_TOL)
                           for px, py in tx_pts):
                    continue
            R.add_hatch_poly(msp, tx_pts, layer, pattern, scale)

    # 12. Cotas
    COTA_TOL = 50
    for dim in cota_dims:
        dim_t = {k: v for k, v in dim.items()}
        for key in ('x1', 'x2', 'x3', 'text_x', 'x_mid'):
            if key in dim_t: dim_t[key] = dim_t[key] + ox
        # For y keys, apply section zone compaction using a CONSISTENT shift
        # per cota (based on Y centroid). This prevents cross-boundary cotas
        # from being stretched when some ys are below and others above boundary.
        cota_ys = [dim_t.get(k) for k in ('y1', 'y2', 'y3', 'text_y', 'y_mid')
                   if dim_t.get(k) is not None]
        cota_cy = sum(cota_ys) / len(cota_ys) if cota_ys else 0
        cota_oy = _sy(cota_cy)  # consistent offset for entire cota
        for key in ('y1', 'y2', 'y3', 'text_y', 'y_mid'):
            if key in dim_t:
                dim_t[key] = dim_t[key] + cota_oy
        skip = False
        if cell_bounds is not None:
            ccx0, ccy0, ccw, cch = cell_bounds
            for xk in ('x1', 'x2', 'x3', 'text_x', 'x_mid'):
                xv = dim_t.get(xk)
                if xv is not None and not ((ccx0-COTA_TOL) <= xv <= (ccx0+ccw+COTA_TOL)):
                    skip = True; break
            if not skip:
                for yk in ('y1', 'y2', 'y3', 'text_y', 'y_mid'):
                    yv = dim_t.get(yk)
                    if yv is not None and not ((ccy0-COTA_TOL) <= yv <= (ccy0+cch+COTA_TOL)):
                        skip = True; break
        if skip:
            continue
        R.add_cota_dim(msp, dim_t)

    # 13. SARR_2.2x7
    sarr22_polys = R._filter_polys(vdata.get('all_sarr22_polys') or [], fa)
    has_sarr_polys = len(sarr22_polys) > 0

    def sarr_layer_name(layer_orig):
        up = layer_orig.upper()
        if 'EDITAR' in up:
            return 'SARR_EDITAR'
        elif '2.2X10' in up.replace('.', '').replace(' ', ''):
            return 'SARR_2.2x10'
        elif '2.2' in layer_orig or 'SARR' in up or 'PRESS' in up:
            return 'SARR_2.2x7'
        return layer_orig

    # 13a. Intact SARR LWPOLYLINE polys
    for sp in sarr22_polys:
        layer_out = sarr_layer_name(sp.get('layer', 'SARR_2.2x7'))
        if sp.get('vertices') and _poly_in_cell(sp['vertices']):
            R.add_lwpoly(msp, tv(sp['vertices']), layer_out, closed=sp.get('closed', True))

    # 13b. LINE-origin sarr22 entries
    seen_sarr22 = set()
    SARR_MAX_EXTENSION = 200  # max units a sarr22 line can extend beyond face_x_max
    _fa_x_max_sarr = fa.get('face_x_max', float('inf'))
    for sl in sarr22_lines:
        if has_sarr_polys and sl.get('src') == 'POLY':
            continue
        # Skip outlier sarr22 lines entirely beyond face_x_max (e.g. V209)
        if (sl['x1'] > _fa_x_max_sarr + SARR_MAX_EXTENSION and
                sl['x2'] > _fa_x_max_sarr + SARR_MAX_EXTENSION):
            continue
        cx_orig = (sl['x1'] + sl['x2']) / 2
        cy_orig = (sl['y1'] + sl['y2']) / 2
        # Strict X filter: sarr22 outside face range by >200u are section-zone elements
        # that would appear isolated (>250u from face cluster) in the combined DXF.
        # 200u allows bridge sarr22 (e.g. V318 at 153-194u) while blocking far outliers.
        if cx_orig < fa_x_min - 200 or cx_orig > fa_x_max + 200:
            continue
        if not R._y_in_face_range(cy_orig, fa):
            continue
        key = (round(sl['x1'],1), round(sl['y1'],1), round(sl['x2'],1), round(sl['y2'],1))
        if key in seen_sarr22:
            continue
        seen_sarr22.add(key)
        tx1, ty1 = _tl(sl['x1'], sl['y1']); tx2, ty2 = _tl(sl['x2'], sl['y2'])
        layer_out = sarr_layer_name(sl.get('layer', 'SARR_2.2x7'))
        c = _clip_line(tx1, ty1, tx2, ty2)
        if c: msp.add_line(c[:2], c[2:], dxfattribs={'layer': layer_out})

    # 14. GRADE ENTITIES
    grade = vdata.get('grade_entities') or {}
    grade_lines = grade.get('grade_lines', [])

    def tg(x, y):
        """Translate para grade -- mesmo offset do restante (sem grade_shift)."""
        return _tl(x, y)

    for gl in grade_lines:
        tx1, ty1 = tg(gl['x1'], gl['y1'])
        tx2, ty2 = tg(gl['x2'], gl['y2'])
        c = _clip_line(tx1, ty1, tx2, ty2)
        if not c: continue
        layer = gl.get('layer', 'Forcador')
        if layer not in R.LAYER_DEFS:
            if layer not in msp.doc.layers:
                msp.doc.layers.add(layer, color=R.LAYER_EXTRA_COLOR)
        msp.add_line(c[:2], c[2:], dxfattribs={'layer': layer})
    for gp in grade.get('grade_polys', []):
        if not gp.get('vertices'):
            continue
        verts = _tv(gp['vertices'])
        ctr_gx = sum(v[0] for v in verts) / len(verts)
        ctr_gy = sum(v[1] for v in verts) / len(verts)
        if not _in_cell_pt(ctr_gx, ctr_gy, tol=30):
            continue
        layer = gp.get('layer', 'Forcador')
        if layer not in R.LAYER_DEFS:
            if layer not in msp.doc.layers:
                msp.doc.layers.add(layer, color=R.LAYER_EXTRA_COLOR)
        R.add_lwpoly(msp, verts, layer, closed=gp.get('closed', True))
    for gh in grade.get('grade_hatches', []):
        layer = gh.get('layer', _LY_DEMARCACAO1)
        pattern = 'SOLID' if gh.get('solid') else gh.get('pattern', 'SOLID')
        for boundary in gh.get('boundary_polys', []):
            if not boundary:
                continue
            gh_cy = sum(p[1] for p in boundary) / len(boundary)
            gh_oy = _sy(gh_cy)
            shifted = [(p[0] + ox, p[1] + gh_oy) for p in boundary]
            ctr_x = sum(p[0] for p in shifted) / len(shifted)
            ctr_y = sum(p[1] for p in shifted) / len(shifted)
            if not _in_cell_pt(ctr_x, ctr_y):
                continue
            R.add_hatch_poly(msp, shifted,
                             layer if layer in R.LAYER_DEFS else 'Hachura', pattern, 1.0)
    for gt in grade.get('grade_texts', []):
        if not R._x_in_face_range(gt['x'], fa, margin_factor=1.5):
            continue
        tx, ty = tg(gt['x'], gt['y'])
        if not _in_cell_pt(tx, ty):
            continue
        layer = gt.get('layer', 'GARFOS')
        msp.add_text(gt.get('text', ''), dxfattribs={
            'insert': (tx, ty), 'height': 4,
            'layer': layer if layer in R.LAYER_DEFS else 'NOMENCLATURA'})

    # 15. EXTRA ENTITIES — layers nao capturados pelo extrator principal
    # (detalhes, SCO-___-LAJ, layer 0, TENSOR, barrote, presilha, cotas, etc.)
    extra = vdata.get('extra_entities') or {}
    for el in extra.get('extra_lines', []):
        tx1, ty1 = _tl(el['x1'], el['y1'])
        tx2, ty2 = _tl(el['x2'], el['y2'])
        c = _clip_line(tx1, ty1, tx2, ty2)
        if not c:
            continue
        layer = el.get('layer', 'detalhes')
        if layer not in R.LAYER_DEFS and layer not in msp.doc.layers:
            msp.doc.layers.add(layer, color=R.LAYER_EXTRA_COLOR)
        msp.add_line(c[:2], c[2:], dxfattribs={'layer': layer})
    for ep in extra.get('extra_polys', []):
        if not ep.get('vertices'):
            continue
        verts = _tv(ep['vertices'])
        ctr_x = sum(v[0] for v in verts) / len(verts)
        ctr_y = sum(v[1] for v in verts) / len(verts)
        if not _in_cell_pt(ctr_x, ctr_y, tol=100):
            continue
        layer = ep.get('layer', 'SCO-___-LAJ')
        if layer not in R.LAYER_DEFS and layer not in msp.doc.layers:
            msp.doc.layers.add(layer, color=R.LAYER_EXTRA_COLOR)
        R.add_lwpoly(msp, verts, layer, closed=ep.get('closed', True))


def build_combined(params, out_path, cols=12):
    """Cria DXF com todas as vigas em grid.
    Ancora: bounding box real do conteudo (nao o insert).
    Celula: CELL_W x CELL_H com margem uniforme.
    Todas as vigas cabem dentro do retangulo da celula (p95 dos dados reais).
    """
    doc = ezdxf.new('R2000')
    R.ensure_layers(doc)
    if 'LABEL_ID' not in doc.layers:
        doc.layers.add('LABEL_ID', color=3)
    if 'CELL_BORDER' not in doc.layers:
        doc.layers.add('CELL_BORDER', color=8)   # cinza claro
    msp = doc.modelspace()

    CELL_W = 2900
    CELL_H = 1800
    MARGIN = 80

    # --- Deduplicacao ---
    from collections import defaultdict as _dd
    _groups = _dd(list)
    for p in params:
        ins = p.get('insert') or {}
        key = (p.get('_obra',''), p['viga'],
               round(ins.get('x',0)/5), round(ins.get('y',0)/5))
        _groups[key].append(p)

    deduped = []
    _name_count = _dd(int)
    for key, vs in _groups.items():
        obra, viga = key[0], key[1]
        best = max(vs, key=lambda v: (
            len(v.get('hatches_data') or []) +
            len(v.get('sarr22_lines') or []) +
            len((v.get('grade_entities') or {}).get('grade_lines', []))
        ))
        deduped.append(best)

    _name_tally = _dd(list)
    for p in deduped:
        _name_tally[(p.get('_obra',''), p['viga'])].append(p)
    for (obra, viga), vs in _name_tally.items():
        if len(vs) > 1:
            for i, v in enumerate(vs):
                v['_viga_label'] = f'{viga}_{chr(ord("a")+i)}'
        else:
            vs[0]['_viga_label'] = vs[0]['viga']

    params = deduped
    print(f'  Dedup: {len(deduped)} vigas unicas (de {len(list(_groups.values()))!r}... original={sum(len(v) for v in _groups.values())})')

    compacted_count = 0
    row, col = 0, 0
    for p in params:
        bbox = compute_content_bbox(p)

        target_x = col * CELL_W
        target_y = -row * CELL_H

        LABEL_RESERVED = 70
        CONTENT_TOP_Y = target_y + CELL_H - LABEL_RESERVED

        # Compute section_y_shift for translate_viga (multi-gap)
        gap_shifts = _compute_section_gaps(p)
        section_y_shift_param = gap_shifts if gap_shifts else None
        if gap_shifts:
            compacted_count += 1

        if bbox:
            bx_min, _, _, by_max = bbox
            ox = target_x + MARGIN - bx_min
            oy = CONTENT_TOP_Y - by_max
        else:
            ins = p.get('insert') or {}
            ox = target_x + MARGIN - ins.get('x', 0)
            oy = CONTENT_TOP_Y - ins.get('y', 0)

        try:
            translate_viga(msp, p, ox, oy,
                           cell_bounds=(target_x, target_y, CELL_W, CELL_H),
                           section_y_shift=section_y_shift_param)
        except Exception as ex:
            print(f'  ERRO {p["viga"]}: {ex}')

        bx0, bx1 = target_x, target_x + CELL_W
        by0, by1 = target_y, target_y + CELL_H
        msp.add_lwpolyline(
            [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)],
            close=True,
            dxfattribs={'layer': 'CELL_BORDER'})

        obra  = p.get('_obra', '')
        label = f'{obra} | {p.get("_viga_label", p["viga"])}'
        msp.add_text(label, dxfattribs={
            'insert': (target_x + MARGIN, target_y + CELL_H - 60),
            'height': 22, 'layer': 'LABEL_ID'})

        col += 1
        if col >= cols:
            col = 0
            row += 1

    doc.saveas(str(out_path))
    total = len(params)
    print(f'Salvo: {out_path}  ({total} vigas, {row + 1} linhas x {cols} colunas)')
    print(f'  Section zone compacted: {compacted_count} vigas')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra')
    parser.add_argument('--cols', type=int, default=12)
    parser.add_argument('--out')
    parser.add_argument('--params', default=PARAMS_FILE, help='Path to params JSON')
    args = parser.parse_args()

    with open(args.params, encoding='utf-8') as f:
        params = json.load(f)

    for p in params:
        p['_obra'] = p.get('obra') or 'desconhecida'

    if args.obra:
        params = [p for p in params if p['_obra'] == args.obra]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.out:
        out_path = Path(args.out)
    elif args.obra:
        out_path = OUT_DIR / f'combined_{args.obra}.dxf'
    else:
        out_path = OUT_DIR / 'combined_ALL.dxf'

    print(f'Combinando {len(params)} vigas -> {out_path}')
    build_combined(params, out_path, cols=args.cols)



if __name__ == '__main__':
    main()
