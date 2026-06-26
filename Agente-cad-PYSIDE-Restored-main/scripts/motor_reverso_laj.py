# -*- coding: utf-8 -*-
"""Motor Reverso LAJ — Extrai ficha N2 de recorte DXF STOG laje."""

from pathlib import Path
import json, re, math
import unicodedata

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
UNIAO_MIN = 15.0
UNIAO_MAX = 30.0
TOL = 0.5

def _infer_obra_root(recorte_path: str) -> Path | None:
    p = Path(recorte_path)
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx+1])
    return None

def _lookup_fase4_laj(elem_id: str, obra_root: Path) -> dict | None:
    p = obra_root / "Fase-4_Sincronizacao" / "JSON_Lajes" / f"{elem_id}.json"
    if p.exists():
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return None

def _entity_points(e) -> list[tuple[float, float]]:
    if e.dxftype() == 'LWPOLYLINE':
        return [(float(x), float(y)) for x, y, *_ in e.get_points()]
    if e.dxftype() == 'POLYLINE':
        return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
    return []

def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

def _area_bbox(box) -> float:
    if not box:
        return 0.0
    x0, y0, x1, y1 = box
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)

def _normalize_poly(points: list[tuple[float, float]]) -> list[list[float]]:
    box = _bbox(points)
    if not box:
        return []
    x0, y0, _, _ = box
    norm = [[round(x - x0, 2), round(y - y0, 2)] for x, y in points]
    if norm and norm[0] != norm[-1]:
        norm.append(norm[0])
    return norm

def _rect_from_bbox(box) -> list[list[float]]:
    x0, y0, x1, y1 = box
    return [[0.0, 0.0], [round(x1 - x0, 2), 0.0],
            [round(x1 - x0, 2), round(y1 - y0, 2)], [0.0, round(y1 - y0, 2)],
            [0.0, 0.0]]

def _poly_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    pts = points[:-1] if points[0] == points[-1] else list(points)
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0

def _axis_aligned_points(points: list[tuple[float, float]]) -> bool:
    if len(points) < 2:
        return False
    for a, b in zip(points, points[1:]):
        if abs(a[0] - b[0]) > TOL and abs(a[1] - b[1]) > TOL:
            return False
    return True

def _is_closed_poly(e, points: list[tuple[float, float]]) -> bool:
    if len(points) < 4:
        return False
    if getattr(e, 'is_closed', False) or getattr(e, 'closed', False):
        return True
    return math.hypot(points[0][0] - points[-1][0], points[0][1] - points[-1][1]) <= TOL

def _bbox_overlap(a, b) -> float:
    if not a or not b:
        return 0.0
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)

def _extract_outline_polygon(msp, fallback_box=None):
    """Extrai o poligono real da area interna LAJ quando ha contorno fechado."""
    candidates = []
    for e in msp:
        if e.dxftype() not in ('POLYLINE', 'LWPOLYLINE'):
            continue
        layer = str(getattr(e.dxf, 'layer', ''))
        layer_key = _layer_key(layer)
        if layer_key in {'7', 'HACHURA'}:
            continue
        pts = _entity_points(e)
        if not _is_closed_poly(e, pts) or not _axis_aligned_points(pts):
            continue
        box = _bbox(pts)
        if not box:
            continue
        w = box[2] - box[0]
        h = box[3] - box[1]
        area = _poly_area(pts)
        if w < 30.0 or h < 20.0 or area < 600.0:
            continue
        if fallback_box and _bbox_overlap(box, fallback_box) < min(area, _area_bbox(box)) * 0.25:
            continue
        score = area
        if 'REAPROVEITAMENTO' in layer_key:
            score *= 3.0
        elif 'PAIN' in layer_key or layer_key == '3':
            score *= 1.5
        candidates.append((score, box, pts))

    if not candidates:
        return None
    _, box, pts = max(candidates, key=lambda item: item[0])
    return box, _normalize_poly(pts)

def _extract_stepped_outline_from_segments(msp, fallback_box=None):
    """Reconstrói contorno em degrau quando o STOG não tem polyline fechada.

    Algumas lajes rasas trazem o outline só como segmentos horizontais longos
    nas layers do produto. A diferença de poucos centímetros entre a borda
    inferior e superior é a deformidade de encontro com pilar/viga.
    """
    h_by_y: dict[float, list[tuple[float, float]]] = {}
    short_vertical_tops: list[float] = []
    all_pts: list[tuple[float, float]] = []
    for e in msp:
        if e.dxftype() not in ('LINE', 'POLYLINE', 'LWPOLYLINE'):
            continue
        layer_key = _layer_key(getattr(e.dxf, 'layer', ''))
        if layer_key not in {'PAINEIS', '3'}:
            continue
        pts = _entity_points(e) if e.dxftype() != 'LINE' else [tuple(_line_points(e)[0]), tuple(_line_points(e)[1])]
        if len(pts) < 2:
            continue
        if fallback_box:
            box = _bbox(pts)
            env = (
                fallback_box[0] - 40, fallback_box[1] - 10,
                fallback_box[2] + 40, fallback_box[3] + 10,
            )
            if box and (box[2] < env[0] or box[0] > env[2] or box[3] < env[1] or box[1] > env[3]):
                continue
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) <= TOL:
                length_v = abs(a[1] - b[1])
                if 12.0 <= length_v <= 22.0:
                    short_vertical_tops.append(round(max(a[1], b[1]) * 2) / 2)
                continue
            if abs(a[1] - b[1]) > TOL:
                continue
            length = abs(a[0] - b[0])
            if length < 25.0:
                continue
            y = round(((a[1] + b[1]) / 2) * 2) / 2
            h_by_y.setdefault(y, []).append((a[0], b[0]))
            all_pts.extend([a, b])

    if len(h_by_y) < 2:
        return None

    def _merged_span(intervals: list[tuple[float, float]]):
        merged = _merge_intervals(intervals, gap_tol=3.0)
        if not merged:
            return None
        x0 = min(a for a, _ in merged)
        x1 = max(b for _, b in merged)
        return x0, x1, x1 - x0

    spans = []
    max_span = 0.0
    for y, intervals in h_by_y.items():
        span = _merged_span(intervals)
        if not span:
            continue
        max_span = max(max_span, span[2])
        spans.append((y, *span))
    if max_span < 80.0:
        return None
    major = [(y, x0, x1, span) for y, x0, x1, span in spans if span >= max_span * 0.75]
    if len(major) < 2:
        return None

    bottom = min(major, key=lambda item: item[0])
    top = max(major, key=lambda item: item[0])
    y0, bx0, bx1, bw = bottom
    y1, tx0, tx1, tw = top
    height = y1 - y0
    if height < 20.0 or height > 140.0:
        return None
    if abs(bw - tw) <= 1.0 and abs(bx0 - tx0) <= 1.0 and abs(bx1 - tx1) <= 1.0:
        return None
    # Só trata degraus pequenos de contorno; diferenças grandes são contexto.
    if max(abs(bx0 - tx0), abs(bx1 - tx1), abs(bw - tw)) > 35.0:
        return None

    short_candidates = [y for y in short_vertical_tops if y0 + height * 0.45 < y < y1 - TOL]
    middle_ys = [y for y, x0, x1, span in major if y0 + TOL < y < y1 - TOL]
    step_y = min(short_candidates) if short_candidates else (max(middle_ys) if middle_ys else y0 + height * 0.72)
    pts = [(bx0, y0), (bx1, y0)]
    if abs(tx1 - bx1) > 1.0:
        pts.extend([(bx1, step_y), (tx1, step_y)])
    pts.append((tx1, y1))
    pts.append((tx0, y1))
    if abs(tx0 - bx0) > 1.0:
        pts.extend([(tx0, step_y), (bx0, step_y)])
    pts.append((bx0, y0))
    box = _bbox(pts)
    if not box:
        return None
    return box, _normalize_poly(pts)

def _filter_internal_lines(lines: list[dict], total: float) -> list[dict]:
    edge_tol = max(5.0, min(8.0, total * 0.02))
    out = []
    seen = set()
    for item in lines or []:
        value = round(float(item.get('value', 0.0)), 1)
        if value <= edge_tol or value >= total - edge_tol:
            continue
        if value in seen:
            continue
        seen.add(value)
        clean = dict(item)
        clean['value'] = value
        out.append(clean)
    return sorted(out, key=lambda item: float(item.get('value', 0.0)))

def _extract_paineis_cotas(msp, slab_box) -> list[dict]:
    if not slab_box:
        return []
    x0, y0, x1, y1 = slab_box
    pad_x = max(30.0, (x1 - x0) * 0.10)
    pad_y = max(30.0, (y1 - y0) * 0.60)
    env = (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)
    cotas = []
    seen = set()
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        layer = str(getattr(e.dxf, 'layer', ''))
        if not _is_paineis_layer(layer):
            continue
        txt = _plain_text(e).replace(',', '.')
        if not re.fullmatch(r'\d+(?:\.\d+)?', txt):
            continue
        try:
            ins = e.dxf.insert
            px, py = float(ins.x), float(ins.y)
        except Exception:
            continue
        if not (env[0] <= px <= env[2] and env[1] <= py <= env[3]):
            continue
        key = (round(float(txt), 1), round(px - x0, 1), round(py - y0, 1))
        if key in seen:
            continue
        seen.add(key)
        cotas.append({
            'value': round(float(txt), 1),
            'x': round(px - x0, 2),
            'y': round(py - y0, 2),
            'rotation': round(float(getattr(e.dxf, 'rotation', 0.0)), 2),
            'height': round(float(getattr(e.dxf, 'height', 8.0)), 2),
            'tipo': 'painel',
        })
    return sorted(cotas, key=lambda c: (float(c['y']), float(c['x']), float(c['value'])))

def _line_points(e) -> tuple[tuple[float, float], tuple[float, float]]:
    a = e.dxf.start
    b = e.dxf.end
    return (float(a.x), float(a.y)), (float(b.x), float(b.y))

def _rel_point(point: tuple[float, float], anchor: tuple[float, float]) -> list[float]:
    return [round(point[0] - anchor[0], 2), round(point[1] - anchor[1], 2)]

def _plain_text(e) -> str:
    if e.dxftype() == 'MTEXT':
        try:
            return e.plain_text().strip()
        except Exception:
            return e.text.strip()
    return str(getattr(e.dxf, 'text', '')).strip()

def _line_len(e) -> float:
    a = e.dxf.start
    b = e.dxf.end
    return math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y))

def _line_axis(e) -> str | None:
    a = e.dxf.start
    b = e.dxf.end
    dx = abs(float(a.x) - float(b.x))
    dy = abs(float(a.y) - float(b.y))
    if dx < TOL and dy > TOL:
        return 'v'
    if dy < TOL and dx > TOL:
        return 'h'
    return None

def _layer_key(layer: str) -> str:
    text = unicodedata.normalize('NFKD', str(layer))
    return ''.join(c for c in text if not unicodedata.combining(c)).upper()

def _is_paineis_layer(layer: str) -> bool:
    return 'PAIN' in _layer_key(layer)

def _merge_intervals(intervals: list[tuple[float, float]], gap_tol: float = 1.0) -> list[tuple[float, float]]:
    if not intervals:
        return []
    ordered = sorted((min(a, b), max(a, b)) for a, b in intervals)
    merged = [ordered[0]]
    for a, b in ordered[1:]:
        la, lb = merged[-1]
        if a <= lb + gap_tol:
            merged[-1] = (la, max(lb, b))
        else:
            merged.append((a, b))
    return merged

def _panel_axis_groups(msp, min_len: float = 10.0) -> tuple[list[dict], list[dict]]:
    """Agrupa linhas da layer Paineis por eixo para inferir grade interna."""
    h_raw: dict[float, list[tuple[float, float]]] = {}
    v_raw: dict[float, list[tuple[float, float]]] = {}
    for e in msp:
        if e.dxftype() != 'LINE' or not _is_paineis_layer(getattr(e.dxf, 'layer', '')):
            continue
        axis = _line_axis(e)
        if not axis:
            continue
        a = e.dxf.start
        b = e.dxf.end
        x1, y1 = float(a.x), float(a.y)
        x2, y2 = float(b.x), float(b.y)
        length = math.hypot(x2 - x1, y2 - y1)
        if length < min_len:
            continue
        if axis == 'h':
            key = round(((y1 + y2) / 2) * 2) / 2
            h_raw.setdefault(key, []).append((x1, x2))
        else:
            key = round(((x1 + x2) / 2) * 2) / 2
            v_raw.setdefault(key, []).append((y1, y2))

    def _groups(raw: dict[float, list[tuple[float, float]]]) -> list[dict]:
        out = []
        for const, intervals in raw.items():
            ordered = sorted((min(a, b), max(a, b)) for a, b in intervals)
            merged = _merge_intervals(ordered)
            if not merged:
                continue
            mn = min(a for a, _ in merged)
            mx = max(b for _, b in merged)
            out.append({
                'const': const,
                'raw': ordered,
                'intervals': merged,
                'min': mn,
                'max': mx,
                'span': mx - mn,
            })
        return out

    return _groups(h_raw), _groups(v_raw)

def _is_union_position(pos: float, positions: list[float]) -> bool:
    prev = [p for p in positions if p < pos - TOL]
    if not prev:
        return False
    gap = pos - max(prev)
    return UNIAO_MIN <= gap <= UNIAO_MAX

def _dedupe_positions(values: list[float], tol: float = 0.5) -> list[float]:
    out: list[float] = []
    for value in sorted(values):
        if out and abs(value - out[-1]) <= tol:
            out[-1] = round((out[-1] + value) / 2, 1)
        else:
            out.append(round(value, 1))
    return out

def _extract_panel_geometry(msp):
    """Inferencia universal da area interna e linhas a partir da layer Paineis."""
    h_groups, v_groups = _panel_axis_groups(msp)
    if not h_groups or not v_groups:
        return None

    widest = max(h_groups, key=lambda g: g['span'])
    tallest = max(v_groups, key=lambda g: g['span'])
    if widest['span'] < 30 or tallest['span'] < 30:
        return None

    x0, x1 = widest['min'], widest['max']
    y0, y1 = tallest['min'], tallest['max']
    comp = x1 - x0
    larg = y1 - y0
    if comp <= 0 or larg <= 0:
        return None

    x_cuts: set[float] = set()
    edge_tol_x = min(5.0, comp * 0.03)
    def _significant_intervals(g: dict, total: float) -> list[tuple[float, float]]:
        min_seg = max(8.0, total * 0.025)
        return [(a, b) for a, b in g['raw'] if (b - a) >= min_seg]

    for g in h_groups:
        if g['span'] < comp * 0.55:
            continue
        intervals = _significant_intervals(g, comp)
        coverage = sum(b - a for a, b in intervals)
        large_parts = [1 for a, b in intervals if (b - a) >= comp * 0.10]
        if len(intervals) < 2 or len(large_parts) < 2 or coverage < comp * 0.75:
            continue
        for a, b in intervals:
            for x in (a, b):
                rel = round(x - x0, 1)
                if edge_tol_x < rel < comp - edge_tol_x:
                    x_cuts.add(rel)

    for g in v_groups:
        intervals = _significant_intervals(g, larg)
        if len(intervals) == 1 and g['span'] >= larg * 0.75:
            rel = round(g['const'] - x0, 1)
            if edge_tol_x < rel < comp - edge_tol_x:
                x_cuts.add(rel)

    y_cuts: set[float] = set()
    edge_tol_y = min(5.0, larg * 0.03)
    for g in v_groups:
        if g['span'] < larg * 0.55:
            continue
        intervals = _significant_intervals(g, larg)
        coverage = sum(b - a for a, b in intervals)
        large_parts = [1 for a, b in intervals if (b - a) >= larg * 0.10]
        if len(intervals) < 2 or len(large_parts) < 2 or coverage < larg * 0.75:
            continue
        for a, b in intervals:
            for y in (a, b):
                rel = round(y - y0, 1)
                if edge_tol_y < rel < larg - edge_tol_y:
                    y_cuts.add(rel)

    # Em lajes rasas, algumas divisoes horizontais so aparecem como linhas
    # longas de painel; usa esse fallback apenas quando as guias verticais
    # nao trouxeram cortes internos.
    if not y_cuts:
        for g in h_groups:
            intervals = _significant_intervals(g, comp)
            has_full_line = any((b - a) >= comp * 0.75 for a, b in intervals)
            if has_full_line and g['span'] >= comp * 0.75:
                rel = round(g['const'] - y0, 1)
                if edge_tol_y < rel < larg - edge_tol_y:
                    y_cuts.add(rel)

    xs = _dedupe_positions(list(x_cuts))
    ys = _dedupe_positions(list(y_cuts))
    linhas_v = [{'value': x, 'is_union': _is_union_position(x, xs)} for x in xs]
    linhas_h = [{'value': y, 'is_union': _is_union_position(y, ys)} for y in ys]
    return (x0, y0, x1, y1), linhas_v, linhas_h

def _canonical_lines_from_lengths(values: list[float], total: float) -> list[dict]:
    """Converte valores de cotas em distancias acumuladas internas."""
    clean = [round(v, 1) for v in values if TOL < v < total - TOL]
    acc = 0.0
    result = []
    for v in clean:
        if acc + v < total - TOL:
            acc = round(acc + v, 1)
            result.append({'value': acc, 'is_union': UNIAO_MIN <= v <= UNIAO_MAX})
    return result

def _best_subset_sum(values: list[float], target: float) -> tuple[list[float], list[float]]:
    """Divide valores em subset que melhor soma target e restante."""
    best = (float('inf'), [])
    n = len(values)
    for mask in range(1, 1 << n):
        subset = [values[i] for i in range(n) if mask & (1 << i)]
        delta = abs(sum(subset) - target)
        if delta < best[0]:
            best = (delta, subset)
    chosen = list(best[1])
    rest = list(values)
    for v in chosen:
        rest.remove(v)
    return chosen, rest

def _lines_from_segments(segments: list[float]) -> list[dict]:
    acc = 0.0
    lines = []
    for seg in segments[:-1]:
        acc = round(acc + seg, 1)
        lines.append({'value': acc, 'is_union': UNIAO_MIN <= seg <= UNIAO_MAX})
    return lines

def _extract_form_bbox(msp):
    """BBox do conteudo LAJ, evitando contexto de pilar/cota distante."""
    hatches = []
    painel_segments = []
    all_form_pts = []

    for e in msp:
        etype = e.dxftype()
        layer = str(getattr(e.dxf, 'layer', ''))
        if etype in ('POLYLINE', 'LWPOLYLINE'):
            pts = _entity_points(e)
            box = _bbox(pts)
            if not box:
                continue
            if layer.lower() == 'hachura':
                hatches.append((box, pts))
            elif layer in ('3', 'Painéis', 'Paineis'):
                all_form_pts.extend(pts)
        elif etype == 'LINE' and layer in ('3', 'Painéis', 'Paineis'):
            length = _line_len(e)
            if length >= 40:
                a = e.dxf.start
                b = e.dxf.end
                painel_segments.append((length, _line_axis(e), (float(a.x), float(a.y)), (float(b.x), float(b.y)), layer))
                all_form_pts.extend([(float(a.x), float(a.y)), (float(b.x), float(b.y))])

    if hatches:
        # HLAZ e a regua mais confiavel para o vao da laje no recorte.
        best_hatch = max(hatches, key=lambda item: _area_bbox(item[0]))
        hx0, hy0, hx1, hy1 = best_hatch[0]
        near_pts = [(x, y) for _, _, a, b, _ in painel_segments for x, y in (a, b)
                    if hx0 - 5 <= x <= hx1 + 5 and hy0 - 150 <= y <= hy1 + 150]
        if near_pts:
            return _bbox(near_pts), best_hatch[0]
        return best_hatch[0], best_hatch[0]

    if all_form_pts:
        return _bbox(all_form_pts), None
    return None, None

def _extract_obstacles(polys: list[tuple[str, list[tuple[float, float]]]], slab_box) -> list[dict]:
    if not slab_box:
        return []
    sx0, sy0, sx1, sy1 = slab_box
    obstacles = []
    for layer, pts in polys:
        box = _bbox(pts)
        if not box or layer.lower() == 'hachura':
            continue
        x0, y0, x1, y1 = box
        w = x1 - x0
        h = y1 - y0
        if w <= 1 or h <= 1:
            continue
        if x0 > sx0 + TOL and y0 > sy0 + TOL and x1 < sx1 - TOL and y1 < sy1 - TOL:
            obstacles.append({
                'x': round(x0 - sx0, 2), 'y': round(y0 - sy0, 2),
                'width': round(w, 2), 'height': round(h, 2),
                'coords': [[round(x - sx0, 2), round(y - sy0, 2)] for x, y in pts],
            })
    return obstacles

def _extract_laj_from_dxf(dxf_path: str) -> dict:
    """Extrai campos LAJ do DXF recorte."""
    result = {'_confianca_extracao': 0.4}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        polylines = []
        for e in msp:
            if e.dxftype() in ('POLYLINE', 'LWPOLYLINE'):
                pts = _entity_points(e)
                if len(pts) >= 2:
                    polylines.append((str(e.dxf.layer), pts))

        slab_box, hlaz_box = _extract_form_bbox(msp)
        panel_geom = _extract_panel_geometry(msp)
        panel_linhas_v = []
        panel_linhas_h = []
        panel_box = None
        if panel_geom:
            panel_box, panel_linhas_v, panel_linhas_h = panel_geom
            # A layer Paineis representa a area interna da laje. O bbox amplo
            # de layer 3 pode conter vigas/pilares de contexto ao redor.
            slab_box = panel_box
        outline = _extract_outline_polygon(msp, slab_box)
        if not outline:
            outline = _extract_stepped_outline_from_segments(msp, slab_box)
        outline_coords = None
        if outline:
            old_box = slab_box
            slab_box, outline_coords = outline
            if old_box:
                dx = old_box[0] - slab_box[0]
                dy = old_box[1] - slab_box[1]
                if abs(dx) > TOL:
                    for item in panel_linhas_v:
                        item['value'] = round(float(item.get('value', 0.0)) + dx, 1)
                if abs(dy) > TOL:
                    for item in panel_linhas_h:
                        item['value'] = round(float(item.get('value', 0.0)) + dy, 1)
        if slab_box:
            x0, y0, x1, y1 = slab_box
            comp = round(abs(x1-x0), 2)
            larg = round(abs(y1-y0), 2)
            result['comprimento'] = comp
            result['largura'] = larg
            result['coordenadas'] = outline_coords if outline_coords else _rect_from_bbox(slab_box)
            result['area_cm2'] = round(_poly_area([(float(x), float(y)) for x, y in result['coordenadas']]) or comp * larg, 2)
            result['_stog_pose'] = {'x': round(x0, 2), 'y': round(y0, 2)}
            cotas_paineis = _extract_paineis_cotas(msp, slab_box)
            if cotas_paineis:
                result['cotas_paineis'] = cotas_paineis

        # Textos numericos da layer Painéis sao os valores canonicos de cotas no recorte.
        cota_nums = []
        cota_entries = []
        textos = []
        for e in msp:
            if e.dxftype() in ('TEXT', 'MTEXT'):
                txt = _plain_text(e)
                if txt:
                    textos.append(txt)
                layer_norm = str(e.dxf.layer).upper().replace('É', 'E')
                if 'PAINE' in layer_norm:
                    try:
                        val = float(txt.replace(',', '.'))
                        cota_nums.append(val)
                        ins = e.dxf.insert
                        cota_entries.append({'value': val, 'x': float(ins.x), 'y': float(ins.y)})
                    except Exception:
                        pass

        linhas_v = []
        linhas_h = []
        comp = result.get('comprimento', 0)
        larg = result.get('largura', 0)
        if panel_linhas_v or panel_linhas_h:
            linhas_v = panel_linhas_v
            linhas_h = panel_linhas_h
        if not linhas_v and not linhas_h and cota_nums and comp and larg:
            # Classificacao por soma: valores que somam melhor o eixo X/Y.
            vals = sorted(cota_nums, reverse=True)
            x_vals = []
            y_vals = []
            for v in vals:
                target_x = abs((sum(x_vals) + v) - comp)
                target_y = abs((sum(y_vals) + v) - larg)
                if target_x <= target_y and sum(x_vals) + v <= comp + TOL:
                    x_vals.append(v)
                elif sum(y_vals) + v <= larg + TOL:
                    y_vals.append(v)
            linhas_v = _canonical_lines_from_lengths(list(reversed(x_vals)), comp)
            linhas_h = _canonical_lines_from_lengths(list(reversed(y_vals)), larg)

        # Fallback final: se ainda sem split lines, procurar LINEs isoladas na layer
        # Painéis que cruzam a laje (ex: L312 onde a classificação por cota_nums
        # falha porque o valor da linha não soma ao comprimento corretamente).
        if not linhas_v and not linhas_h and slab_box and comp and larg:
            _x0, _y0 = slab_box[0], slab_box[1]
            _edge_x = min(5.0, comp * 0.03)
            _edge_y = min(5.0, larg * 0.03)
            _raw_v: list[float] = []
            _raw_h: list[float] = []
            for _e in msp:
                if _e.dxftype() != 'LINE' or not _is_paineis_layer(str(getattr(_e.dxf, 'layer', ''))):
                    continue
                _a = _e.dxf.start; _b = _e.dxf.end
                _ddx = abs(_b.x - _a.x); _ddy = abs(_b.y - _a.y)
                if _ddx < 1.0 and _ddy >= larg * 0.75:
                    rel = round(min(_a.x, _b.x) - _x0, 1)
                    if _edge_x < rel < comp - _edge_x:
                        _raw_v.append(rel)
                elif _ddy < 1.0 and _ddx >= comp * 0.75:
                    rel = round(min(_a.y, _b.y) - _y0, 1)
                    if _edge_y < rel < larg - _edge_y:
                        _raw_h.append(rel)
            if _raw_v:
                for _v in _dedupe_positions(_raw_v):
                    linhas_v.append({'value': _v, 'is_union': UNIAO_MIN <= _v <= UNIAO_MAX})
            if _raw_h:
                for _h in _dedupe_positions(_raw_h):
                    linhas_h.append({'value': _h, 'is_union': UNIAO_MIN <= _h <= UNIAO_MAX})

        if hlaz_box and cota_nums and not panel_geom:
            hx0, hy0, hx1, hy1 = hlaz_box
            hw = round(hx1 - hx0, 2)
            hh = round(hy1 - hy0, 2)
            non_union = [v for v in cota_nums if not (UNIAO_MIN <= v <= UNIAO_MAX)]
            union_vals = [v for v in cota_nums if UNIAO_MIN <= v <= UNIAO_MAX]
            x_segments, y_segments = _best_subset_sum(non_union, hw)
            def _ordered_by_position(values, axis):
                remaining = list(values)
                ordered = []
                entries = sorted(
                    [e for e in cota_entries if e['value'] in remaining],
                    key=lambda e: e[axis],
                )
                for entry in entries:
                    value = entry['value']
                    if value in remaining:
                        ordered.append(value)
                        remaining.remove(value)
                ordered.extend(remaining)
                return ordered
            x_segments = _ordered_by_position(x_segments, 'x')
            if union_vals:
                # A tira HLAZ representa a uniao no eixo Y; o restante das cotas
                # numericas pertence ao eixo ortogonal.
                y_segments = _ordered_by_position([v for v in y_segments if v > 0] + [round(hh, 1)], 'y')
            if x_segments:
                comp = round(sum(x_segments), 2)
            if y_segments:
                larg = round(sum(y_segments), 2)
            if x_segments and y_segments:
                y_non_union = [v for v in y_segments if not (UNIAO_MIN <= v <= UNIAO_MAX)]
                below_hlaz = max(y_non_union) if y_non_union else 0.0
                slab_y0 = hy0 - below_hlaz
                slab_box = (hx0, slab_y0, hx0 + comp, slab_y0 + larg)
                result['comprimento'] = comp
                result['largura'] = larg
                result['area_cm2'] = round(comp * larg, 2)
                result['coordenadas'] = _rect_from_bbox(slab_box)
                result['_stog_pose'] = {'x': round(slab_box[0], 2), 'y': round(slab_box[1], 2)}
                linhas_v = _lines_from_segments(x_segments)
                # Ordenacao vertical: paineis abaixo da HLAZ, uniao, paineis acima.
                linhas_h = _lines_from_segments(y_segments)

        result['linhas_verticais'] = _filter_internal_lines(linhas_v, result.get('comprimento', 0))
        result['linhas_horizontais'] = _filter_internal_lines(linhas_h, result.get('largura', 0))
        result['obstaculos'] = _extract_obstacles(polylines, slab_box)
        if hlaz_box:
            hx0, hy0, hx1, hy1 = hlaz_box
            result['_hlaz'] = [{'x': round(hx0 - slab_box[0], 2), 'y': round(hy0 - slab_box[1], 2),
                                'width': round(hx1 - hx0, 2), 'height': round(hy1 - hy0, 2)}]
        result['modo_selecionado'] = 1 if len(linhas_h) > len(linhas_v) else 0
        result['unioes_nos_bordes'] = False
        result['observacoes'] = ''
        result['pontaletes'] = {}
        result['_forma_canonica'] = {
            'cotas_valor': sorted(round(v, 2) for v in cota_nums),
            'textos': sorted(t for t in textos if t and not re.fullmatch(r'P\d+', t.strip(), re.I)),
            'textos_contexto': sorted(t for t in textos if re.fullmatch(r'P\d+', t.strip(), re.I)),
        }

        result['_confianca_extracao'] = 0.85 if slab_box else 0.35

    except Exception as ex:
        result['_extracao_erro'] = str(ex)
        result['_confianca_extracao'] = 0.3
    return result

def extrair_ficha_laje(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
) -> dict:
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name
    fase4 = _lookup_fase4_laj(elemento_id, obra_root_path) if obra_root_path else None
    dxf_data = _extract_laj_from_dxf(recorte_path)
    dxf_conf = dxf_data.pop('_confianca_extracao', 0.4)
    dxf_data.pop('_extracao_erro', None)
    if fase4:
        result = dict(fase4)
        for key in (
            'comprimento', 'largura', 'coordenadas', 'area_cm2',
            'linhas_verticais', 'linhas_horizontais', 'obstaculos',
            'cotas_paineis', 'modo_selecionado', 'unioes_nos_bordes', 'observacoes',
            'pontaletes', '_hlaz', '_stog_pose', '_forma_canonica'
        ):
            if key in dxf_data:
                result[key] = dxf_data[key]
        result['_er_meta'] = {'source': 'fase4+dxf_extract', 'dxf_path': str(recorte_path), 'confianca': max(0.80, dxf_conf)}
        result['_confianca'] = max(0.80, dxf_conf)
        result.pop('_stog_detail_primitives', None)
    else:
        elem_num = re.sub(r'[^\d]', '', elemento_id)
        result = {
            'numero': int(elem_num) if elem_num else 0,
            'nome': elemento_id,
            'pavimento': 'Pavimento',
            **dxf_data,
        }
        result['_er_meta'] = {'source': 'dxf_extract', 'dxf_path': str(recorte_path), 'confianca': dxf_conf}
        result['_confianca'] = dxf_conf
    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "L1"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_laje(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
