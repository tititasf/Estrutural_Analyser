# -*- coding: utf-8 -*-
"""Motor Reverso LAJ — Extrai ficha N2 de recorte DXF STOG laje."""

from pathlib import Path
import json, re, math, sqlite3
import unicodedata

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
PROJECT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
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

def _lookup_sa_outline(fase4: dict | None, elem_id: str, reference: dict | None = None) -> dict | None:
    project_id = ((fase4 or {}).get('_sa_meta') or {}).get('project_id')
    if not PROJECT_DB_PATH.exists():
        return None
    conn = sqlite3.connect(f'file:{PROJECT_DB_PATH}?mode=ro', uri=True)
    try:
        if project_id:
            rows = conn.execute(
                'SELECT points_json, area FROM slabs WHERE project_id=? AND name=? ORDER BY rowid DESC',
                (str(project_id), str(elem_id)),
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT points_json, area FROM slabs WHERE name=? ORDER BY rowid DESC',
                (str(elem_id),),
            ).fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    candidates = []
    ref_w = float((reference or {}).get('comprimento') or 0.0)
    ref_h = float((reference or {}).get('largura') or 0.0)
    for row in rows:
        try:
            points = [(float(x), float(y)) for x, y in json.loads(row[0] or '[]')]
        except Exception:
            continue
        box = _bbox(points)
        if len(points) < 3 or not box:
            continue
        normalized = _simplify_closed_polygon(_normalize_poly(points))
        area = _poly_area(points)
        bbox_area = _area_bbox(box)
        if len(normalized) <= 5 or not area or area >= bbox_area * 0.98:
            continue
        width = box[2] - box[0]
        height = box[3] - box[1]
        score = abs(width - ref_w) / max(ref_w, 1.0) + abs(height - ref_h) / max(ref_h, 1.0)
        candidates.append((score, {
            'coordenadas': normalized,
            'comprimento': round(width, 2),
            'largura': round(height, 2),
            'area_cm2': round(area, 2),
        }))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None

def _entity_points(e) -> list[tuple[float, float]]:
    if e.dxftype() == 'LWPOLYLINE':
        return [(float(x), float(y)) for x, y, *_ in e.get_points()]
    if e.dxftype() == 'POLYLINE':
        return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
    return []

def _hatch_polyline_points(e) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    try:
        paths = list(e.paths)
    except Exception:
        return []
    for path in paths:
        vertices = getattr(path, 'vertices', None)
        if not vertices:
            continue
        try:
            points = [(float(v[0]), float(v[1])) for v in vertices]
        except Exception:
            points = []
        if points:
            return points
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

def _simplify_closed_polygon(points: list[list[float]], tol: float = 0.5) -> list[list[float]]:
    clean = [[float(x), float(y)] for x, y in points]
    if clean and clean[0] == clean[-1]:
        clean.pop()
    changed = True
    while changed and len(clean) > 3:
        changed = False
        simplified = []
        count = len(clean)
        for index, point in enumerate(clean):
            prev = clean[(index - 1) % count]
            nxt = clean[(index + 1) % count]
            dx = nxt[0] - prev[0]
            dy = nxt[1] - prev[1]
            span = math.hypot(dx, dy)
            distance = abs(dx * (prev[1] - point[1]) - (prev[0] - point[0]) * dy) / max(span, 1.0)
            between = (
                min(prev[0], nxt[0]) - tol <= point[0] <= max(prev[0], nxt[0]) + tol
                and min(prev[1], nxt[1]) - tol <= point[1] <= max(prev[1], nxt[1]) + tol
            )
            if distance <= tol and between:
                changed = True
                continue
            simplified.append(point)
        clean = simplified
    if clean:
        clean.append(list(clean[0]))
    return [[round(x, 2), round(y, 2)] for x, y in clean]

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

def _has_diagonal_geometry(msp) -> bool:
    for e in msp:
        layer_key = _layer_key(getattr(e.dxf, 'layer', ''))
        # Marcas X de reaproveitamento (layer 1) e hachuras não definem o
        # contorno da laje. PAINEIS permanece válida porque o N4 canônico
        # grava nela o contorno estrutural; o limite de comprimento elimina
        # setas e hachuras curtas.
        if layer_key in {'1', 'HACHURA', 'REAPROVEITAMENTO'}:
            continue
        if e.dxftype() == 'LINE':
            segments = [_line_points(e)]
        elif e.dxftype() in ('POLYLINE', 'LWPOLYLINE'):
            pts = _entity_points(e)
            segments = list(zip(pts, pts[1:]))
        else:
            continue
        for a, b in segments:
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            if dx > 5.0 and dy > 5.0 and math.hypot(dx, dy) >= 60.0:
                return True
    return False

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

def _discover_structural_layers(msp) -> set[str]:
    stats: dict[str, dict[str, float]] = {}
    for e in msp:
        layer = str(getattr(e.dxf, 'layer', ''))
        if e.dxftype() in ('TEXT', 'MTEXT'):
            text = _plain_text(e).replace(',', '.')
            if re.fullmatch(r'\d+(?:\.\d+)?', text):
                stats.setdefault(layer, {'h': 0.0, 'v': 0.0, 'count': 0.0, 'numeric': 0.0})['numeric'] += 1
            continue
        if e.dxftype() not in ('LINE', 'POLYLINE', 'LWPOLYLINE'):
            continue
        row = stats.setdefault(layer, {'h': 0.0, 'v': 0.0, 'count': 0.0, 'numeric': 0.0})
        if e.dxftype() == 'LINE':
            segments = [_line_points(e)]
        else:
            pts = _entity_points(e)
            segments = list(zip(pts, pts[1:]))
            if _is_closed_poly(e, pts) and pts:
                segments.append((pts[-1], pts[0]))
        for a, b in segments:
            dx = abs(float(a[0]) - float(b[0]))
            dy = abs(float(a[1]) - float(b[1]))
            length = math.hypot(dx, dy)
            if length < 2.0 or length > 3300.0:
                continue
            if dy <= TOL:
                row['h'] += length
                row['count'] += 1
            elif dx <= TOL:
                row['v'] += length
                row['count'] += 1

    ranked = []
    for layer, row in stats.items():
        total = row['h'] + row['v']
        if total <= 0 or row['h'] <= 0 or row['v'] <= 0:
            continue
        balance = min(row['h'], row['v']) / max(row['h'], row['v'])
        ranked.append((row['numeric'], total * (1.0 + balance * 0.25), layer))
    if not ranked:
        return set()
    ranked.sort(reverse=True)
    return {ranked[0][2]}

def _discover_contour_layers(msp, primary_layers: set[str]) -> set[str]:
    lengths: dict[str, float] = {}
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        a, b = _line_points(e)
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        if dx > TOL and dy > TOL:
            continue
        length = math.hypot(dx, dy)
        if 2.0 <= length <= 3300.0:
            layer = str(getattr(e.dxf, 'layer', ''))
            lengths[layer] = lengths.get(layer, 0.0) + length
    if not lengths:
        return set(primary_layers)
    peak = max(lengths.values())
    return set(primary_layers) | {
        layer for layer, length in lengths.items()
        if length >= max(20.0, peak * 0.10)
    }

def _extract_outline_polygon(msp, fallback_box=None):
    """Extrai o poligono real da area interna LAJ quando ha contorno fechado."""
    candidates = []
    for e in msp:
        if e.dxftype() not in ('POLYLINE', 'LWPOLYLINE'):
            continue
        layer_key = _layer_key(getattr(e.dxf, 'layer', ''))
        if layer_key in {'7', 'HACHURA', 'REAPROVEITAMENTO'}:
            continue
        pts = _entity_points(e)
        if not _is_closed_poly(e, pts):
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
        if fallback_box:
            fw = fallback_box[2] - fallback_box[0]
            fh = fallback_box[3] - fallback_box[1]
            if w < fw * 0.25 or h < fh * 0.25:
                continue
        score = area
        if fallback_box:
            overlap = _bbox_overlap(box, fallback_box)
            score *= 1.0 + overlap / max(_area_bbox(box), 1.0)
        candidates.append((score, box, pts))

    if not candidates:
        return None
    _, box, pts = max(candidates, key=lambda item: item[0])
    return box, _normalize_poly(pts)

def _extract_panel_union_outline(msp, fallback_box=None):
    """Reconstrói o contorno pela união dos painéis fechados do próprio N2.

    O STOG pode representar uma laje em degrau por vários retângulos de
    REAPROVEITAMENTO, ligados por uma faixa HLAZ. Usar somente o bbox desses
    retângulos preenche vazios que não pertencem à laje. A união só é aceita
    quando cobre o envelope inteiro e uma fração forte desse envelope.
    """
    if not fallback_box:
        return None
    try:
        from shapely.geometry import box as shapely_box
        from shapely.ops import unary_union
    except ImportError:
        return None

    fx0, fy0, fx1, fy1 = fallback_box
    fw = fx1 - fx0
    fh = fy1 - fy0
    if fw <= 0 or fh <= 0:
        return None

    rectangles = []
    for entity in msp:
        if entity.dxftype() not in ('POLYLINE', 'LWPOLYLINE'):
            continue
        layer_key = _layer_key(getattr(entity.dxf, 'layer', ''))
        if layer_key not in {'REAPROVEITAMENTO', 'HACHURA'}:
            continue
        points = _entity_points(entity)
        rect_box = _bbox(points)
        if (
            not rect_box
            or not _is_closed_poly(entity, points)
            or not _axis_aligned_points(points + [points[0]])
        ):
            continue
        x0, y0, x1, y1 = rect_box
        if x1 - x0 < 30.0 or y1 - y0 < 5.0:
            continue
        clipped = (
            max(fx0, x0), max(fy0, y0),
            min(fx1, x1), min(fy1, y1),
        )
        if clipped[2] - clipped[0] < 1.0 or clipped[3] - clipped[1] < 1.0:
            continue
        rectangles.append(shapely_box(*clipped))

    if len(rectangles) < 2:
        return None
    merged = unary_union(rectangles)
    if merged.geom_type != 'Polygon' or merged.is_empty:
        return None
    mx0, my0, mx1, my1 = merged.bounds
    edge_tol = max(2.0, min(8.0, min(fw, fh) * 0.04))
    covers_envelope = (
        abs(mx0 - fx0) <= edge_tol
        and abs(my0 - fy0) <= edge_tol
        and abs(mx1 - fx1) <= edge_tol
        and abs(my1 - fy1) <= edge_tol
    )
    coverage = float(merged.area) / max(fw * fh, 1.0)
    if not covers_envelope or coverage < 0.55:
        return None

    absolute = _simplify_closed_polygon(
        [[float(x), float(y)] for x, y in merged.exterior.coords],
        tol=0.5,
    )
    box = _bbox([(x, y) for x, y in absolute])
    return (box, _normalize_poly([(x, y) for x, y in absolute])) if box else None

def _extract_stepped_outline_from_segments(msp, fallback_box=None, structural_layers=None):
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
        if structural_layers and str(getattr(e.dxf, 'layer', '')) not in structural_layers:
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
    if fallback_box:
        fw = fallback_box[2] - fallback_box[0]
        fh = fallback_box[3] - fallback_box[1]
        if (box[2] - box[0]) < fw * 0.85 or (box[3] - box[1]) < fh * 0.85:
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

def _panel_axis_groups(msp, min_len: float = 10.0, structural_layers=None) -> tuple[list[dict], list[dict]]:
    """Agrupa linhas da layer Paineis por eixo para inferir grade interna."""
    h_raw: dict[float, list[tuple[float, float]]] = {}
    v_raw: dict[float, list[tuple[float, float]]] = {}
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        if structural_layers and str(getattr(e.dxf, 'layer', '')) not in structural_layers:
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

def _snap_nominal_panel_segments(values: list[float]) -> list[float]:
    snapped = []
    previous = 0.0
    for value in sorted(values):
        segment = value - previous
        nominal = min((60.0, 122.0, 244.0), key=lambda item: abs(item - segment))
        if abs(nominal - segment) <= 0.6:
            value = previous + nominal
        value = round(value, 1)
        snapped.append(value)
        previous = value
    return snapped

def _fill_oversized_panel_spans(lines: list[dict], total: float) -> list[dict]:
    ordered = sorted((dict(item) for item in lines or []), key=lambda item: float(item['value']))
    out = []
    previous = 0.0
    for item in ordered + [{'value': total, '_edge': True}]:
        value = float(item['value'])
        while value - previous > 244.6:
            previous = round(previous + 244.0, 1)
            out.append({'value': previous, 'is_union': False})
        if not item.get('_edge'):
            out.append(item)
            previous = value
    return out

def _axis_panel_lengths(positions: list[float], total: float) -> list[float]:
    edges = [0.0] + sorted(float(p) for p in positions) + [float(total)]
    return [round(b - a, 2) for a, b in zip(edges, edges[1:]) if b - a > 0.5]

def _is_preferred_panel_length(length: float) -> bool:
    return any(abs(length - target) <= 1.0 for target in (244.0, 122.0, 60.0))

def _looks_like_canonical_panel_distribution(lines: list[dict], total: float) -> bool:
    lengths = _axis_panel_lengths([float(item.get('value') or 0.0) for item in lines or []], total)
    if not lengths:
        return True
    residuals = []
    for length in lengths:
        if _is_preferred_panel_length(length):
            continue
        if UNIAO_MIN <= length <= UNIAO_MAX:
            continue
        if length >= 60.0:
            residuals.append(length)
            continue
        return False
    return len(residuals) <= 1

def _smart_canonical_lines(comprimento: float, largura: float) -> list[dict]:
    try:
        try:
            from smart_panner import distribute_panels
        except ImportError:
            from scripts.smart_panner import distribute_panels
        return distribute_panels(comprimento, largura).get('linhas_verticais') or []
    except Exception:
        lines = []
        pos = 244.0
        while pos < comprimento - 60.0:
            lines.append({'value': round(pos, 1), 'is_union': False})
            pos += 244.0
        return lines

def _smart_canonical_axis_lines(total: float, other: float, axis: str) -> list[dict]:
    try:
        try:
            from smart_panner import distribute_panels
        except ImportError:
            from scripts.smart_panner import distribute_panels
        if axis == 'x':
            return distribute_panels(total, other).get('linhas_verticais') or []
        return distribute_panels(other, total).get('linhas_horizontais') or []
    except Exception:
        lines = []
        pos = 244.0
        while pos < total - 60.0:
            lines.append({'value': round(pos, 1), 'is_union': False})
            pos += 244.0
        return lines

def _polygon_break_anchors_local(coords, comp: float, larg: float, axis: str) -> list[float]:
    if not coords or len(coords) <= 4:
        return []
    pts = [(float(x), float(y)) for x, y in coords]
    x0 = min(x for x, _ in pts)
    y0 = min(y for _, y in pts)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    anchors = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if axis == 'x':
            if abs(x1 - x2) > 0.5:
                continue
            local = round(x1 - x0, 1)
            length = abs(y2 - y1)
            total = larg
            axis_total = comp
        else:
            if abs(y1 - y2) > 0.5:
                continue
            local = round(y1 - y0, 1)
            length = abs(x2 - x1)
            total = comp
            axis_total = larg
        if local <= 30.0 or local >= axis_total - 30.0:
            continue
        if 5.0 <= length < total - 0.5:
            anchors.append(local)
    return _dedupe_positions(anchors)

def _anchored_axis_lines(lines: list[dict], total: float, other: float, anchors: list[float], axis: str) -> list[dict]:
    anchors = [float(a) for a in anchors if 1.0 < float(a) < total - 1.0]
    if not anchors:
        return lines
    current = [float(item.get('value') or 0.0) for item in lines or []]
    if current and not any(
        min(abs(anchor - pos) for pos in current) <= 35.0
        for anchor in anchors
    ):
        return lines
    out = []
    edges = [0.0] + anchors + [float(total)]
    edges = _dedupe_positions(edges)
    previous = 0.0
    for edge in edges[1:]:
        span = edge - previous
        for item in _smart_canonical_axis_lines(span, other, axis):
            value = previous + float(item.get('value') or 0.0)
            if previous + 1.0 < value < edge - 1.0:
                out.append({'value': round(value, 1), 'is_union': bool(item.get('is_union', False))})
        if edge < total - 1.0:
            out.append({'value': round(edge, 1), 'is_union': False})
        previous = edge
    if not out:
        return lines
    if len(out) > max(len(lines or []) + len(anchors) + 2, 3):
        return lines
    return out

def _canonicalize_long_panel_axis(lines: list[dict], comprimento, largura) -> list[dict]:
    try:
        comp = float(comprimento or 0.0)
        larg = float(largura or 0.0)
    except (TypeError, ValueError):
        return lines
    if comp < max(larg, 2 * 244.0) or not lines:
        return lines
    if _looks_like_canonical_panel_distribution(lines, comp):
        return lines
    canonical = _smart_canonical_lines(comp, larg)
    return canonical or lines

def _canonicalize_noisy_panel_axis(lines: list[dict], total, other, axis: str) -> list[dict]:
    try:
        total_f = float(total or 0.0)
        other_f = float(other or 0.0)
    except (TypeError, ValueError):
        return lines
    if not lines or total_f <= 0:
        return lines
    if min(total_f, other_f) <= 75.0:
        return lines
    if _looks_like_canonical_panel_distribution(lines, total_f):
        return lines
    canonical = _smart_canonical_axis_lines(total_f, other_f, axis)
    return canonical or lines

def _canonicalize_panel_axes_for_outline(
    linhas_v: list[dict],
    linhas_h: list[dict],
    coords,
    comprimento,
    largura,
) -> tuple[list[dict], list[dict]]:
    try:
        comp = float(comprimento or 0.0)
        larg = float(largura or 0.0)
    except (TypeError, ValueError):
        return linhas_v, linhas_h
    if not coords or len(coords) <= 4:
        return linhas_v, linhas_h
    x_anchors = _polygon_break_anchors_local(coords, comp, larg, 'x')
    if x_anchors:
        linhas_v = _anchored_axis_lines(linhas_v, comp, larg, x_anchors, 'x')
    # Eixo Y fica desativado por enquanto: Fase-4 é fonte oficial/intocável e
    # alguns itens (ex.: L319) ainda têm paginação antiga armazenada ali.
    return linhas_v, linhas_h

def _extract_panel_geometry(msp, structural_layers=None):
    """Inferencia universal da area interna e linhas a partir da layer Paineis."""
    h_groups, v_groups = _panel_axis_groups(msp, structural_layers=structural_layers)
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

    xs = _snap_nominal_panel_segments(_dedupe_positions(list(x_cuts)))
    ys = _snap_nominal_panel_segments(_dedupe_positions(list(y_cuts)))
    linhas_v = [{'value': x, 'is_union': _is_union_position(x, xs)} for x in xs]
    linhas_h = [{'value': y, 'is_union': _is_union_position(y, ys)} for y in ys]
    return (x0, y0, x1, y1), linhas_v, linhas_h

def _extract_complex_outline_cuts(msp, outline_box, structural_layers):
    x0, y0, x1, y1 = outline_box
    width = x1 - x0
    height = y1 - y0
    edge_x = max(15.0, min(25.0, width * 0.02))
    edge_y = max(15.0, min(25.0, height * 0.02))
    xs = []
    ys = []
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        if structural_layers and str(getattr(e.dxf, 'layer', '')) not in structural_layers:
            continue
        axis = _line_axis(e)
        if not axis:
            continue
        a, b = _line_points(e)
        if axis == 'v':
            length = abs(b[1] - a[1])
            rel = round(((a[0] + b[0]) / 2.0) - x0, 1)
            overlap = max(0.0, min(y1, max(a[1], b[1])) - max(y0, min(a[1], b[1])))
            if length >= max(20.0, height * 0.20) and overlap >= length * 0.70:
                if edge_x < rel < width - edge_x:
                    xs.append(rel)
        else:
            length = abs(b[0] - a[0])
            rel = round(((a[1] + b[1]) / 2.0) - y0, 1)
            overlap = max(0.0, min(x1, max(a[0], b[0])) - max(x0, min(a[0], b[0])))
            if length >= max(20.0, width * 0.10) and overlap >= length * 0.70:
                if edge_y < rel < height - edge_y:
                    ys.append(rel)
    xs = _dedupe_positions(xs)
    ys = _dedupe_positions(ys)
    return (
        [{'value': x, 'is_union': _is_union_position(x, xs)} for x in xs],
        [{'value': y, 'is_union': _is_union_position(y, ys)} for y in ys],
    )

def _extract_local_vertical_segments(msp, slab_box, structural_layers, lines):
    x0, y0, _, y1 = slab_box
    positions = [float(item['value']) for item in lines]
    grouped = {round(value, 1): [] for value in positions}
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        if structural_layers and str(getattr(e.dxf, 'layer', '')) not in structural_layers:
            continue
        if _line_axis(e) != 'v':
            continue
        a, b = _line_points(e)
        rel_x = round(((a[0] + b[0]) / 2) - x0, 1)
        match = min(positions, key=lambda value: abs(value - rel_x), default=None)
        if match is None or abs(match - rel_x) > 0.6:
            continue
        lo = max(y0, min(a[1], b[1]))
        hi = min(y1, max(a[1], b[1]))
        if hi - lo >= 10.0:
            grouped[round(match, 1)].append((lo - y0, hi - y0))
    result = []
    for value, intervals in grouped.items():
        for lo, hi in _merge_intervals(intervals, gap_tol=1.0):
            result.append({'value': value, 'y0': round(lo, 1), 'y1': round(hi, 1)})
    return result

def _extract_local_horizontal_segments(msp, slab_box, structural_layers, lines):
    x0, y0, x1, _ = slab_box
    positions = [float(item['value']) for item in lines]
    grouped = {round(value, 1): [] for value in positions}
    for entity in msp:
        if entity.dxftype() != 'LINE':
            continue
        if structural_layers and str(getattr(entity.dxf, 'layer', '')) not in structural_layers:
            continue
        if _line_axis(entity) != 'h':
            continue
        a, b = _line_points(entity)
        rel_y = round(((a[1] + b[1]) / 2) - y0, 1)
        match = min(positions, key=lambda value: abs(value - rel_y), default=None)
        if match is None or abs(match - rel_y) > 0.6:
            continue
        lo = max(x0, min(a[0], b[0]))
        hi = min(x1, max(a[0], b[0]))
        if hi - lo >= 10.0:
            grouped[round(match, 1)].append((lo - x0, hi - x0))
    result = []
    for value, intervals in grouped.items():
        for lo, hi in _merge_intervals(intervals, gap_tol=1.0):
            result.append({'value': value, 'x0': round(lo, 1), 'x1': round(hi, 1)})
    return result

def _extract_panel_dimension_texts(msp, slab_box):
    x0, y0, _, _ = slab_box
    result = []
    for entity in msp:
        if entity.dxftype() != 'TEXT' or not _is_paineis_layer(getattr(entity.dxf, 'layer', '')):
            continue
        text = str(getattr(entity.dxf, 'text', '')).strip()
        if not re.fullmatch(r'\d+(?:[.,]\d+)?', text):
            continue
        insert = entity.dxf.insert
        result.append({
            'text': text,
            'value': float(text.replace(',', '.')),
            'x': round(float(insert.x) - x0, 2),
            'y': round(float(insert.y) - y0, 2),
            'rotation': round(float(getattr(entity.dxf, 'rotation', 0) or 0), 2),
            'height': round(float(getattr(entity.dxf, 'height', 8) or 8), 2),
        })
    return result

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

def _best_dimension_total(values: list[float], target: float) -> float | None:
    clean = [round(float(v), 1) for v in values if 2.0 <= float(v) <= target * 1.05]
    if not clean or target <= 0:
        return None
    candidates = clean + [round(sum(clean), 1)]
    best = min(candidates, key=lambda total: abs(total - target))
    return best if abs(best - target) <= max(4.0, target * 0.015) else None

def _lines_from_segments(segments: list[float]) -> list[dict]:
    acc = 0.0
    lines = []
    for seg in segments[:-1]:
        acc = round(acc + seg, 1)
        lines.append({'value': acc, 'is_union': UNIAO_MIN <= seg <= UNIAO_MAX})
    return lines

def _extract_form_bbox(msp, structural_layers=None):
    """BBox do conteudo LAJ, evitando contexto de pilar/cota distante."""
    closed_strips = []
    painel_segments = []
    all_form_pts = []

    for e in msp:
        etype = e.dxftype()
        layer = str(getattr(e.dxf, 'layer', ''))
        if etype == 'HATCH' and _layer_key(layer) == 'HACHURA' and int(getattr(e.dxf, 'color', 0) or 0) == 251:
            pts = _hatch_polyline_points(e)
            box = _bbox(pts)
            if not box:
                continue
            w = box[2] - box[0]
            h = box[3] - box[1]
            if (
                _axis_aligned_points(pts + [pts[0]])
                and w >= 30.0
                and 5.0 <= h <= 100.0
                and w >= h * 2.0
            ):
                closed_strips.append((box, pts))
        if etype in ('POLYLINE', 'LWPOLYLINE'):
            pts = _entity_points(e)
            box = _bbox(pts)
            if not box:
                continue
            w = box[2] - box[0]
            h = box[3] - box[1]
            if (
                _layer_key(layer) == 'HACHURA'
                and
                _is_closed_poly(e, pts)
                and _axis_aligned_points(pts + [pts[0]])
                and w >= 30.0
                and 5.0 <= h <= 100.0
                and w >= h * 2.0
            ):
                closed_strips.append((box, pts))
            if not structural_layers or layer in structural_layers:
                all_form_pts.extend(pts)
        elif etype == 'LINE' and (not structural_layers or layer in structural_layers):
            length = _line_len(e)
            if length >= 40:
                a = e.dxf.start
                b = e.dxf.end
                painel_segments.append((length, _line_axis(e), (float(a.x), float(a.y)), (float(b.x), float(b.y)), layer))
                all_form_pts.extend([(float(a.x), float(a.y)), (float(b.x), float(b.y))])

    form_box = _bbox(all_form_pts)
    if form_box:
        form_w = form_box[2] - form_box[0]
        form_h = form_box[3] - form_box[1]
        closed_strips = [
            item for item in closed_strips
            if abs((item[0][2] - item[0][0]) - form_w) > max(10.0, form_w * 0.03)
            or abs((item[0][3] - item[0][1]) - form_h) > max(5.0, form_h * 0.05)
        ]

    if closed_strips:
        # HLAZ e a regua mais confiavel para o vao da laje no recorte.
        best_hatch = max(closed_strips, key=lambda item: _area_bbox(item[0]))
        hx0, hy0, hx1, hy1 = best_hatch[0]
        near_pts = [(x, y) for _, _, a, b, _ in painel_segments for x, y in (a, b)
                    if hx0 - 5 <= x <= hx1 + 5 and hy0 - 150 <= y <= hy1 + 150]
        if near_pts:
            return _bbox(near_pts), best_hatch[0]
        return best_hatch[0], best_hatch[0]

    if form_box:
        return form_box, None
    return None, None

def _point_in_polygon(point: tuple[float, float], polygon) -> bool:
    x, y = point
    points = [(float(px), float(py)) for px, py in (polygon or [])]
    if len(points) < 3:
        return False
    inside = False
    previous = points[-1]
    for current in points:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            x_cross = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
            if x < x_cross:
                inside = not inside
        previous = current
    return inside

def _extract_obstacles(
    polys: list[tuple[str, list[tuple[float, float]]]],
    slab_box,
    slab_outline=None,
) -> list[dict]:
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
            center_local = (
                (x0 + x1) / 2 - sx0,
                (y0 + y1) / 2 - sy0,
            )
            if slab_outline and not _point_in_polygon(center_local, slab_outline):
                continue
            obstacles.append({
                'x': round(x0 - sx0, 2), 'y': round(y0 - sy0, 2),
                'width': round(w, 2), 'height': round(h, 2),
                'coords': [[round(x - sx0, 2), round(y - sy0, 2)] for x, y in (pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts)],
            })
    return obstacles

def _extract_support_hatch_lines(msp, slab_box) -> list[dict]:
    """Extrai hachura diagonal de apoio STOG como primitivas locais.

    No produto de referência esses traços são LINEs a 45 graus na layer 3,
    tangentes ou próximos ao contorno da laje. O campo explícito evita que o
    gerador invente apoios por heurística.
    """
    if not slab_box:
        return []
    sx0, sy0, sx1, sy1 = slab_box
    margin = 100.0
    lines = []
    for entity in msp:
        if entity.dxftype() != 'LINE' or _layer_key(getattr(entity.dxf, 'layer', '')) != '3':
            continue
        a, b = _line_points(entity)
        vx = float(b[0]) - float(a[0])
        vy = float(b[1]) - float(a[1])
        dx = abs(vx)
        dy = abs(vy)
        if not (0.5 <= dx <= 40.0 and 0.5 <= dy <= 40.0):
            continue
        if vx * vy <= 0 or not (0.75 <= dx / dy <= 1.25):
            continue
        mx = (float(a[0]) + float(b[0])) / 2
        my = (float(a[1]) + float(b[1])) / 2
        if not (sx0 - margin <= mx <= sx1 + margin and sy0 - margin <= my <= sy1 + margin):
            continue
        lines.append({
            'x1': round(float(a[0]) - sx0, 2),
            'y1': round(float(a[1]) - sy0, 2),
            'x2': round(float(b[0]) - sx0, 2),
            'y2': round(float(b[1]) - sy0, 2),
        })
    # Uma hachura real é uma sequência; traços isolados são setas/ruído.
    return lines if len(lines) >= 3 else []


def _filter_support_hatch_lines(lines: list[dict], comprimento, largura) -> list[dict]:
    """Remove hachuras de vizinhos fora da janela local da laje."""
    try:
        comp = float(comprimento or 0)
        larg = float(largura or 0)
    except (TypeError, ValueError):
        return []
    if comp <= 0 or larg <= 0:
        return []
    margin = 100.0
    filtered = []
    for line in lines or []:
        try:
            mx = (float(line['x1']) + float(line['x2'])) / 2
            my = (float(line['y1']) + float(line['y2'])) / 2
        except (KeyError, TypeError, ValueError):
            continue
        if -margin <= mx <= comp + margin and -margin <= my <= larg + margin:
            filtered.append(line)
    return filtered if len(filtered) >= 3 else []


def _filter_obstacles_by_outline(obstacles: list[dict], outline) -> list[dict]:
    if not outline:
        return list(obstacles or [])
    valid = []
    for obstacle in obstacles or []:
        try:
            center = (
                float(obstacle.get('x', 0)) + float(obstacle.get('width', 0)) / 2,
                float(obstacle.get('y', 0)) + float(obstacle.get('height', 0)) / 2,
            )
        except (TypeError, ValueError):
            continue
        if _point_in_polygon(center, outline):
            valid.append(obstacle)
    return valid

def _extract_laj_from_dxf(dxf_path: str) -> dict:
    """Extrai campos LAJ do DXF recorte."""
    result = {'_confianca_extracao': 0.4}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        result['_has_diagonal_geometry'] = _has_diagonal_geometry(msp)

        polylines = []
        for e in msp:
            if e.dxftype() in ('POLYLINE', 'LWPOLYLINE'):
                pts = _entity_points(e)
                if len(pts) >= 2:
                    polylines.append((str(e.dxf.layer), pts))

        structural_layers = _discover_structural_layers(msp)
        contour_layers = _discover_contour_layers(msp, structural_layers)
        slab_box, hlaz_box = _extract_form_bbox(msp, structural_layers)
        source_form_box = slab_box
        panel_geom = _extract_panel_geometry(msp, structural_layers)
        panel_linhas_v = []
        panel_linhas_h = []
        panel_box = None
        if panel_geom:
            panel_box, panel_linhas_v, panel_linhas_h = panel_geom
            # A layer Paineis representa a area interna da laje. O bbox amplo
            # de layer 3 pode conter vigas/pilares de contexto ao redor.
            slab_box = panel_box
            source_w = source_form_box[2] - source_form_box[0] if source_form_box else 0.0
            source_h = source_form_box[3] - source_form_box[1] if source_form_box else 0.0
            panel_w = panel_box[2] - panel_box[0]
            panel_h = panel_box[3] - panel_box[1]
            source_extends_panel = source_w > panel_w + 5.0 or source_h > panel_h + 5.0
            if result['_has_diagonal_geometry'] and not hlaz_box and source_form_box and source_extends_panel:
                dx = panel_box[0] - source_form_box[0]
                dy = panel_box[1] - source_form_box[1]
                for item in panel_linhas_v:
                    item['value'] = round(float(item.get('value', 0.0)) + dx, 1)
                for item in panel_linhas_h:
                    item['value'] = round(float(item.get('value', 0.0)) + dy, 1)
                _, complex_h = _extract_complex_outline_cuts(
                    msp, source_form_box, structural_layers
                )
                if complex_h:
                    panel_linhas_h = complex_h
                    result['_stog_clip_unions'] = True
                slab_box = source_form_box
        panel_union_outline = _extract_panel_union_outline(msp, slab_box)
        outline = panel_union_outline or _extract_outline_polygon(msp, slab_box)
        if not outline:
            outline = _extract_stepped_outline_from_segments(msp, slab_box, contour_layers)
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
            if len(outline_coords or []) > 5:
                complex_v, complex_h = _extract_complex_outline_cuts(
                    msp, slab_box, structural_layers
                )
                if complex_v:
                    panel_linhas_v = complex_v
                if complex_h:
                    panel_linhas_h = complex_h
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
        declared_dimensions = []
        textos = []
        for e in msp:
            if e.dxftype() in ('TEXT', 'MTEXT'):
                txt = _plain_text(e)
                if txt:
                    textos.append(txt)
                for match in re.finditer(r'(\d+(?:[.,]\d+)?)\s*[Xx]\s*(\d+(?:[.,]\d+)?)', txt):
                    declared_dimensions.extend(
                        [float(match.group(1).replace(',', '.')), float(match.group(2).replace(',', '.'))]
                    )
                if re.fullmatch(r'\d+(?:[.,]\d+)?', txt):
                    try:
                        val = float(txt.replace(',', '.'))
                        cota_nums.append(val)
                        ins = e.dxf.insert
                        cota_entries.append({
                            'value': val,
                            'x': float(ins.x),
                            'y': float(ins.y),
                            'rotation': float(getattr(e.dxf, 'rotation', 0.0)) % 180.0,
                        })
                    except Exception:
                        pass

        if slab_box and not outline:
            x0, y0, x1, y1 = slab_box
            comp = x1 - x0
            larg = y1 - y0
            horizontal_values = [
                entry['value'] for entry in cota_entries
                if min(entry['rotation'], 180.0 - entry['rotation']) <= 15.0
            ]
            vertical_values = [
                entry['value'] for entry in cota_entries
                if abs(entry['rotation'] - 90.0) <= 15.0
            ]
            declared_width = min(declared_dimensions, key=lambda v: abs(v - comp), default=None)
            declared_height = min(declared_dimensions, key=lambda v: abs(v - larg), default=None)
            exact_comp = _best_dimension_total(horizontal_values, comp)
            exact_larg = _best_dimension_total(vertical_values, larg)
            if declared_width is not None and abs(declared_width - comp) <= max(5.0, comp * 0.03):
                exact_comp = declared_width
            if declared_height is not None and abs(declared_height - larg) <= max(5.0, larg * 0.03):
                exact_larg = declared_height
            if exact_comp is not None or exact_larg is not None:
                comp = round(exact_comp if exact_comp is not None else comp, 2)
                larg = round(exact_larg if exact_larg is not None else larg, 2)
                slab_box = (x0, y0, x0 + comp, y0 + larg)
                result['comprimento'] = comp
                result['largura'] = larg
                result['coordenadas'] = _rect_from_bbox(slab_box)
                result['area_cm2'] = round(comp * larg, 2)

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
                if _e.dxftype() != 'LINE':
                    continue
                if structural_layers and str(getattr(_e.dxf, 'layer', '')) not in structural_layers:
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
        result['linhas_verticais'] = _canonicalize_long_panel_axis(
            result['linhas_verticais'],
            result.get('comprimento', 0),
            result.get('largura', 0),
        )
        complex_outline = bool(
            panel_union_outline
            or (outline_coords and len(outline_coords) > 5)
        )
        if not complex_outline and not hlaz_box:
            # Em retângulos simples, linhas extraídas que geram peça <60 cm são
            # ruído de paginação antiga, não geometria. Canonicalizar ambos os
            # eixos pela regra 244/122/60 + uma sobra ampla.
            result['linhas_verticais'] = _canonicalize_noisy_panel_axis(
                result['linhas_verticais'],
                result.get('comprimento', 0),
                result.get('largura', 0),
                'x',
            )
            result['linhas_horizontais'] = _canonicalize_noisy_panel_axis(
                result['linhas_horizontais'],
                result.get('largura', 0),
                result.get('comprimento', 0),
                'y',
            )
        result['linhas_verticais'], result['linhas_horizontais'] = _canonicalize_panel_axes_for_outline(
            result['linhas_verticais'],
            result['linhas_horizontais'],
            result.get('coordenadas') or [],
            result.get('comprimento', 0),
            result.get('largura', 0),
        )
        if complex_outline and result['linhas_horizontais']:
            local_horizontal = _extract_local_horizontal_segments(
                msp, slab_box, structural_layers, result['linhas_horizontais']
            )
            kept_horizontal = []
            for item in result['linhas_horizontais']:
                value = float(item.get('value') or 0)
                segments = [
                    {'x0': segment['x0'], 'x1': segment['x1']}
                    for segment in local_horizontal
                    if abs(float(segment['value']) - value) <= 0.1
                ]
                # Cortes derivados apenas de endpoints são bordas do degrau,
                # não uma divisão que deva atravessar o bbox inteiro.
                if not segments:
                    continue
                clean = dict(item)
                comp = float(result.get('comprimento') or 0)
                is_full_width = all(
                    float(segment['x0']) <= 0.5
                    and float(segment['x1']) >= comp - 0.5
                    for segment in segments
                )
                if not is_full_width:
                    clean['segments'] = segments
                else:
                    clean.pop('segments', None)
                kept_horizontal.append(clean)
            result['linhas_horizontais'] = kept_horizontal
        result['cotas_paineis'] = _extract_panel_dimension_texts(msp, slab_box)
        if min(float(result.get('comprimento') or 0), float(result.get('largura') or 0)) <= 75.0:
            larg = float(result.get('largura') or 0)
            local_segments = _extract_local_vertical_segments(
                msp, slab_box, structural_layers, result['linhas_verticais']
            )
            local_segments = [
                segment for segment in local_segments
                if float(segment['y0']) <= 1.0 and float(segment['y1']) >= larg - 1.0
            ]
            full_values = {round(float(segment['value']), 1) for segment in local_segments}
            result['linhas_verticais'] = [
                item for item in result['linhas_verticais']
                if round(float(item.get('value') or 0), 1) in full_values
            ]
            result['linhas_horizontais'] = [
                item for item in result['linhas_horizontais']
                if min(float(item.get('value') or 0), larg - float(item.get('value') or 0)) >= 30.0
            ]
            if larg <= 75.0:
                canonical_h = _smart_canonical_axis_lines(larg, float(result.get('comprimento') or 0), 'y')
                if canonical_h:
                    result['linhas_horizontais'] = canonical_h
            if float(result.get('comprimento') or 0) <= 75.0:
                canonical_v = _smart_canonical_axis_lines(
                    float(result.get('comprimento') or 0),
                    larg,
                    'x',
                )
                if canonical_v:
                    result['linhas_verticais'] = canonical_v
            for item in result['linhas_verticais'] + result['linhas_horizontais']:
                item['is_union'] = False
                item['exact'] = True
            result['_panel_vertical_segments'] = local_segments
            for item in result['linhas_verticais']:
                value = float(item.get('value') or 0)
                segments = [
                    {'y0': segment['y0'], 'y1': segment['y1']}
                    for segment in local_segments
                    if abs(float(segment['value']) - value) <= 0.1
                ]
                if segments:
                    item['segments'] = segments
        result['obstaculos'] = _extract_obstacles(
            polylines, slab_box, result.get('coordenadas')
        )
        result['apoios_hachurados'] = _extract_support_hatch_lines(msp, slab_box)
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
    has_diagonal_geometry = bool(dxf_data.pop('_has_diagonal_geometry', False))
    sa_outline = _lookup_sa_outline(fase4, elemento_id, dxf_data)
    if has_diagonal_geometry and sa_outline:
        dxf_data.update(sa_outline)
        dxf_data['linhas_verticais'] = _fill_oversized_panel_spans(
            dxf_data.get('linhas_verticais') or [], float(dxf_data.get('comprimento') or 0)
        )
        dxf_data['linhas_horizontais'] = _fill_oversized_panel_spans(
            dxf_data.get('linhas_horizontais') or [], float(dxf_data.get('largura') or 0)
        )
    if fase4:
        result = dict(fase4)
        for key in (
            'comprimento', 'largura', 'coordenadas', 'area_cm2',
            'linhas_verticais', 'linhas_horizontais', 'obstaculos',
            'apoios_hachurados',
            'cotas_paineis', 'modo_selecionado', 'unioes_nos_bordes', 'observacoes',
            'pontaletes', '_hlaz', '_stog_pose', '_forma_canonica', '_stog_clip_unions',
            '_panel_vertical_segments'
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
    result['obstaculos'] = _filter_obstacles_by_outline(
        result.get('obstaculos') or [], result.get('coordenadas')
    )
    result['apoios_hachurados'] = _filter_support_hatch_lines(
        result.get('apoios_hachurados') or [],
        result.get('comprimento'), result.get('largura'),
    )
    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "L1"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_laje(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
