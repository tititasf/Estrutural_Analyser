from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union
from typing import List, Tuple, Optional, Dict
import math

class SlabTracer:
    """
    Algoritmo 'Boundary Tracer' para Lajes.
    Usa 'Path Finding' (Polygonize) para encontrar polÃ­gonos fechados formados por vigas/paredes.
    """
    def __init__(self, spatial_index):
        self.spatial_index = spatial_index
        self.global_boundary = None
        self.last_trace_diagnostics = {}
        self._laj_label_centroids = {}
        self._laj_teacher_dims = {}

    def _item_to_lines(self, item):
        layer = ""
        raw_type = ""
        linetype = ""
        color = ""
        geoms = []
        if isinstance(item, dict):
            layer = str(item.get('layer') or '').upper()
            raw_type = str(item.get('type') or item.get('dxftype') or '').upper()
            linetype = str(item.get('linetype') or '').upper()
            color = str(item.get('color') or item.get('true_color') or '').upper()
            if 'points' in item:
                pts = item.get('points') or []
                if len(pts) > 1:
                    geoms.append(LineString(pts))
            elif 'start' in item and 'end' in item:
                geoms.append(LineString([item['start'], item['end']]))
        elif isinstance(item, tuple) and len(item) == 2:
            geoms.append(LineString(item))
        elif isinstance(item, list) and len(item) > 1:
            geoms.append(LineString(item))
        return [(g, layer, raw_type, linetype, color, item) for g in geoms if g and g.length > 1e-6]

    def _classify_laje_candidate_line(self, geom: LineString, layer: str = "", raw_type: str = "", linetype: str = "", color: str = "") -> Dict:
        norm = (layer or "").upper()
        entity = (raw_type or "").upper()
        line_style = (linetype or "").upper()
        color_name = (color or "").upper()
        reject_tokens = (
            "COTA", "DIM", "DEFPOINT", "TEXT", "TEXTO", "EIXO", "AXIS",
            "HATCH", "HACH", "SIMBO", "SYMB", "LEADER", "ANNO", "OBS",
            "CORTE", "CUT", "SECTION", "DETALHE", "DETAIL", "CARIMBO",
            "NIVEL", "NÃVEL", "LEVEL", "MEDIDA", "AUX", "AUXILIAR",
        )
        structural_tokens = (
            "VIGA", "BEAM", "PILAR", "PIL", "PAREDE", "WALL", "LAJ",
            "SCO", "CONTORNO", "LIMITE", "CONCRETO", "FORMA", "PAIN",
        )
        reasons = []
        if any(tok in norm for tok in reject_tokens):
            reasons.append("layer_noise")
        if any(tok in line_style for tok in ("DASH", "DOT", "HIDDEN", "CENTER", "EIXO")):
            reasons.append("linetype_noise")
        if entity in {"TEXT", "MTEXT", "HATCH", "DIMENSION", "LEADER"}:
            reasons.append("entity_noise")
        # Hachura heuristic: short line on fill/hach layer
        if geom.length < 15.0 and any(tok in norm for tok in ("HATCH", "HACH", "FILL", "PREENCH", "HA", "ZONE", "MASSA")):
            reasons.append("hatch_pattern")
        elif geom.length < 5.0:
            reasons.append("too_short")
        accepted = not reasons
        support = "unknown"
        if any(tok in norm for tok in structural_tokens):
            support = "structural"
            if reasons == ["too_short"] and geom.length >= 2.0:
                accepted = True
                reasons = []
        elif not norm:
            support = "legacy"
        elif accepted:
            support = "unclassified"
        return {
            "accepted": accepted,
            "reasons": reasons,
            "support": support,
            "layer": layer,
            "raw_type": raw_type,
            "linetype": linetype,
            "color": color,
            "length": geom.length,
            "bbox": geom.bounds,
        }

    def _collect_laje_candidate_lines(self, candidates, valid_layers=None):
        accepted = []
        rejected = []
        classified = []
        for item in candidates:
            for geom, layer, raw_type, linetype, color, original in self._item_to_lines(item):
                if valid_layers and layer and layer not in valid_layers:
                    rejected.append((geom, {"layer": layer, "reasons": ["not_in_valid_layers"]}))
                    continue
                info = self._classify_laje_candidate_line(geom, layer, raw_type, linetype, color)
                info["original"] = original
                classified.append((geom, info))
                if not info["accepted"]:
                    rejected.append((geom, info))
                else:
                    accepted.append(geom)
        return accepted, rejected, classified

    def _select_best_laje_polygon(self, polygons, target_pt: Point):
        containing = []
        for poly in polygons:
            if not poly.is_valid or poly.area <= 1e-6:
                continue
            if poly.contains(target_pt) or poly.touches(target_pt):
                containing.append(poly)
        if not containing:
            return None
        containing.sort(key=lambda p: (p.area, len(p.exterior.coords)))
        best = containing[0]
        return self._clean_small_orthogonal_notches(best, target_pt)

    def _laj_crop_bbox_from_labels(self, label_id: str, start_point: Tuple[float, float], search_radius: float) -> tuple:
        """N2/RecorteMotor-style local crop: Voronoi adaptive margins based on label distribution."""
        cx, cy = start_point
        centroids = getattr(self, "_laj_label_centroids", {}) or {}
        if not label_id or label_id not in centroids:
            # Fallback: use search_radius with reasonable caps
            half_x = min(500.0, max(150.0, search_radius * 0.22))
            half_y = min(300.0, max(100.0, search_radius * 0.14))
            return (cx - half_x, cy - half_y, cx + half_x, cy + half_y)

        # --- Adaptive: compute tolerances from label distribution ---
        if len(centroids) >= 2:
            xs = [x for x, y in centroids.values()]
            ys = [y for x, y in centroids.values()]
            x_gaps = sorted([abs(xs[i] - xs[j]) for i in range(len(xs)) for j in range(i+1, len(xs)) if abs(xs[i] - xs[j]) > 10.0])
            y_gaps = sorted([abs(ys[i] - ys[j]) for i in range(len(ys)) for j in range(i+1, len(ys)) if abs(ys[i] - ys[j]) > 10.0])
            median_x_gap = x_gaps[len(x_gaps)//2] if x_gaps else 400.0
            median_y_gap = y_gaps[len(y_gaps)//2] if y_gaps else 300.0
        else:
            median_x_gap = 400.0
            median_y_gap = 300.0

        # Tolerances scale with median label spacing
        ROW_TOL = min(200.0, median_y_gap * 0.45)
        COL_TOL = min(500.0, median_x_gap * 0.50)
        MARGIN_X = max(30.0, median_x_gap * 0.10)
        MARGIN_Y = max(20.0, median_y_gap * 0.08)
        MAX_HALF_X = min(500.0, median_x_gap * 0.55)
        MAX_HALF_Y = min(350.0, median_y_gap * 0.60)

        cx, cy = centroids[label_id]
        same_row = [(x, y) for other, (x, y) in centroids.items() if other != label_id and abs(y - cy) < ROW_TOL]
        same_col = [(x, y) for other, (x, y) in centroids.items() if other != label_id and abs(x - cx) < COL_TOL]

        left_xs = [x for x, _ in same_row if x < cx - 10.0]
        right_xs = [x for x, _ in same_row if x > cx + 10.0]
        below_ys = [y for _, y in same_col if y < cy - 10.0]
        above_ys = [y for _, y in same_col if y > cy + 10.0]

        x0 = (max(left_xs) + cx) / 2.0 - MARGIN_X if left_xs else cx - MAX_HALF_X
        x1 = (min(right_xs) + cx) / 2.0 + MARGIN_X if right_xs else cx + MAX_HALF_X
        y0 = (max(below_ys) + cy) / 2.0 - MARGIN_Y if below_ys else cy - MAX_HALF_Y
        y1 = (min(above_ys) + cy) / 2.0 + MARGIN_Y if above_ys else cy + MAX_HALF_Y

        return self._shrink_laj_bbox_away_from_labels((x0, y0, x1, y1), label_id)

    def _shrink_laj_bbox_away_from_labels(self, bbox: tuple, label_id: str, clearance: float = 5.0) -> tuple:
        centroids = getattr(self, "_laj_label_centroids", {}) or {}
        if label_id not in centroids:
            return bbox
        cx, cy = centroids[label_id]
        x0, y0, x1, y1 = bbox
        for other_id, (ox, oy) in centroids.items():
            if other_id == label_id:
                continue
            if not (x0 <= ox <= x1 and y0 <= oy <= y1):
                continue
            options = []
            if ox < cx and ox + clearance < cx:
                value = ox + clearance
                options.append(("x0", value, abs(value - x0)))
            if ox > cx and ox - clearance > cx:
                value = ox - clearance
                options.append(("x1", value, abs(x1 - value)))
            if oy < cy and oy + clearance < cy:
                value = oy + clearance
                options.append(("y0", value, abs(value - y0)))
            if oy > cy and oy - clearance > cy:
                value = oy - clearance
                options.append(("y1", value, abs(y1 - value)))
            if not options:
                continue
            side, value, _ = min(options, key=lambda item: item[2])
            if side == "x0":
                x0 = max(x0, value)
            elif side == "x1":
                x1 = min(x1, value)
            elif side == "y0":
                y0 = max(y0, value)
            elif side == "y1":
                y1 = min(y1, value)
        return (x0, y0, x1, y1)

    def _line_segments_from_geom(self, geom: LineString):
        coords = list(geom.coords)
        for a, b in zip(coords, coords[1:]):
            if a != b:
                yield (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))

    def _axis_groups_from_laj_lines(self, lines, crop_bbox: tuple, margin: float = 0):
        x0, y0, x1, y1 = crop_bbox
        bw = max(1.0, x1 - x0)
        bh = max(1.0, y1 - y0)
        if margin <= 1.0:
            margin = max(50.0, min(bw, bh) * 0.12)
        env = (x0 - margin, y0 - margin, x1 + margin, y1 + margin)
        h_raw = {}
        v_raw = {}
        # Adaptive tolerances from bbox size
        tol = max(0.5, min(bw, bh) * 0.001)
        min_axis_len = max(5.0, min(bw, bh) * 0.015)
        for geom in lines:
            for a, b in self._line_segments_from_geom(geom):
                sx0, sy0 = min(a[0], b[0]), min(a[1], b[1])
                sx1, sy1 = max(a[0], b[0]), max(a[1], b[1])
                if sx1 < env[0] or sx0 > env[2] or sy1 < env[1] or sy0 > env[3]:
                    continue
                dx = abs(a[0] - b[0])
                dy = abs(a[1] - b[1])
                if dx <= tol and dy > min_axis_len:
                    key = round(((a[0] + b[0]) / 2.0) * 2.0) / 2.0
                    v_raw.setdefault(key, []).append((max(sy0, env[1]), min(sy1, env[3])))
                elif dy <= tol and dx > min_axis_len:
                    key = round(((a[1] + b[1]) / 2.0) * 2.0) / 2.0
                    h_raw.setdefault(key, []).append((max(sx0, env[0]), min(sx1, env[2])))

        def merge_intervals(intervals):
            merge_gap = max(1.0, min(bw, bh) * 0.003)
            ordered = sorted((min(a, b), max(a, b)) for a, b in intervals if max(a, b) - min(a, b) > tol)
            if not ordered:
                return []
            merged = [ordered[0]]
            for a, b in ordered[1:]:
                la, lb = merged[-1]
                if a <= lb + merge_gap:
                    merged[-1] = (la, max(lb, b))
                else:
                    merged.append((a, b))
            return merged

        def groups(raw):
            out = []
            for const, intervals in raw.items():
                merged = merge_intervals(intervals)
                if not merged:
                    continue
                mn = min(a for a, _ in merged)
                mx = max(b for _, b in merged)
                out.append({"const": const, "intervals": merged, "min": mn, "max": mx, "span": mx - mn})
            return out

        return groups(h_raw), groups(v_raw)

    def _canonical_laj_outline_from_n2_axes(self, lines, target_pt: Point, crop_bbox: tuple):
        """Build the slab outline from major panel/form axes with adaptive tolerances."""
        h_groups, v_groups = self._axis_groups_from_laj_lines(lines, crop_bbox)
        if len(h_groups) < 2 or len(v_groups) < 2:
            return None

        cx, cy = target_pt.x, target_pt.y
        bx0, by0, bx1, by1 = crop_bbox
        bw = max(1.0, bx1 - bx0)
        bh = max(1.0, by1 - by0)
        adaptive_margin = max(50.0, min(bw, bh) * 0.08)
        skip_zone = max(5.0, min(bw, bh) * 0.012)

        max_h_span = max((g["span"] for g in h_groups), default=0.0)
        max_v_span = max((g["span"] for g in v_groups), default=0.0)
        min_h_span = min(max(bw * 0.25, 50.0), max_h_span * 0.65)
        min_v_span = min(max(bh * 0.25, 35.0), max_v_span * 0.65)

        h_candidates = [g for g in h_groups if g["span"] >= min_h_span and by0 - adaptive_margin <= g["const"] <= by1 + adaptive_margin]
        v_candidates = [g for g in v_groups if g["span"] >= min_v_span and bx0 - adaptive_margin <= g["const"] <= bx1 + adaptive_margin]
        if len(h_candidates) < 2 or len(v_candidates) < 2:
            return None

        bottom_options = [g for g in h_candidates if g["const"] < cy - skip_zone]
        top_options = [g for g in h_candidates if g["const"] > cy + skip_zone]
        left_options = [g for g in v_candidates if g["const"] < cx - skip_zone]
        right_options = [g for g in v_candidates if g["const"] > cx + skip_zone]
        if not bottom_options or not top_options or not left_options or not right_options:
            return None

        bottom = min(bottom_options, key=lambda g: (abs(g["const"] - by0), -g["span"]))
        top = min(top_options, key=lambda g: (abs(g["const"] - by1), -g["span"]))
        left = min(left_options, key=lambda g: (abs(g["const"] - bx0), -g["span"]))
        right = min(right_options, key=lambda g: (abs(g["const"] - bx1), -g["span"]))

        x0, x1 = left["const"], right["const"]
        y0, y1 = bottom["const"], top["const"]
        min_dim = max(25.0, min(bw, bh) * 0.06)
        if x1 - x0 < min_dim or y1 - y0 < min_dim:
            return None
        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        if not poly.is_valid or not (poly.contains(target_pt) or poly.touches(target_pt)):
            return None
        return poly

    def _teacher_laj_outline_from_n2_dims(self, lines, target_pt: Point, crop_bbox: tuple, teacher: dict | None):
        """Use N2 LAJ ficha dimensions to choose the correct pair of structural axes (adaptive)."""
        if not teacher:
            return None
        try:
            comp = float(teacher.get("comprimento") or teacher.get("comp") or 0.0)
            larg = float(teacher.get("largura") or teacher.get("larg") or 0.0)
        except Exception:
            return None
        if comp <= 20.0 or larg <= 20.0:
            return None

        h_groups, v_groups = self._axis_groups_from_laj_lines(lines, crop_bbox)
        if len(h_groups) < 2 or len(v_groups) < 2:
            return None

        cx, cy = target_pt.x, target_pt.y
        bx0, by0, bx1, by1 = crop_bbox
        bw = max(1.0, bx1 - bx0)
        bh = max(1.0, by1 - by0)
        search_margin = max(80.0, min(bw, bh) * 0.18)
        v_candidates = [g for g in v_groups if bx0 - search_margin <= g["const"] <= bx1 + search_margin and g["span"] >= max(30.0, larg * 0.15)]
        h_candidates = [g for g in h_groups if by0 - search_margin <= g["const"] <= by1 + search_margin and g["span"] >= max(40.0, comp * 0.12)]
        if len(v_candidates) < 2 or len(h_candidates) < 2:
            return None

        def choose_pair(groups, target_len, target_coord):
            best = None
            tol = max(12.0, target_len * 0.08)
            ordered = sorted(groups, key=lambda g: g["const"])
            for i, a in enumerate(ordered):
                for b in ordered[i + 1:]:
                    length = b["const"] - a["const"]
                    if length <= 0:
                        continue
                    delta = abs(length - target_len)
                    if delta > max(tol, target_len * 0.18):
                        continue
                    outside = 0.0
                    if target_coord < a["const"]:
                        outside = a["const"] - target_coord
                    elif target_coord > b["const"]:
                        outside = target_coord - b["const"]
                    if outside > max(60.0, target_len * 0.25):
                        continue
                    center = (a["const"] + b["const"]) / 2.0
                    center_penalty = abs(center - target_coord) * 0.06
                    outside_penalty = outside * 0.5
                    support_bonus = (a["span"] + b["span"]) * -0.008
                    score = delta + center_penalty + outside_penalty + support_bonus
                    if best is None or score < best[0]:
                        best = (score, a, b)
            if not best:
                return None
            return best[1], best[2]

        x_pair = choose_pair(v_candidates, comp, cx)
        y_pair = choose_pair(h_candidates, larg, cy)
        if not x_pair or not y_pair:
            return None

        left, right = x_pair
        bottom, top = y_pair
        x0, x1 = left["const"], right["const"]
        y0, y1 = bottom["const"], top["const"]
        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        if not poly.is_valid or poly.area <= 1e-6:
            return None
        return poly

    def _should_prefer_n2_axes_outline(self, polygon: Polygon | None, axes_poly: Polygon | None, target_pt: Point) -> bool:
        if not axes_poly:
            return False
        if polygon is None or polygon.is_empty:
            return True
        if not polygon.is_valid:
            return True
        if not (polygon.contains(target_pt) or polygon.touches(target_pt)):
            return True
        axes_area = axes_poly.area
        if axes_area <= 1e-6:
            return False
        area_ratio = polygon.area / axes_area
        if area_ratio < 0.93:
            return True
        pb = polygon.bounds
        ab = axes_poly.bounds
        inset = max(abs(pb[0] - ab[0]), abs(pb[1] - ab[1]), abs(pb[2] - ab[2]), abs(pb[3] - ab[3]))
        if inset > 18.0 and area_ratio < 0.98:
            return True
        return False

    def _clean_small_orthogonal_notches(self, poly: Polygon, target_pt: Point) -> Polygon:
        """Remove small CAD detail notches from a slab outline without forcing a rectangle."""
        if not poly or poly.is_empty:
            return poly
        try:
            coords = list(poly.exterior.coords)
            if len(coords) < 8:
                return poly
            if coords[0] == coords[-1]:
                coords = coords[:-1]

            xs = [p[0] for p in coords]
            ys = [p[1] for p in coords]
            span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
            max_notch = max(80.0, min(180.0, span * 0.30))
            tol = max(1e-6, span * 0.001)

            def same_x(a, b):
                return abs(a[0] - b[0]) <= tol

            def same_y(a, b):
                return abs(a[1] - b[1]) <= tol

            def dist(a, b):
                return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

            def remove_collinear(points):
                if len(points) < 4:
                    return points
                result = []
                m = len(points)
                for idx, point in enumerate(points):
                    prev_pt = points[(idx - 1) % m]
                    next_pt = points[(idx + 1) % m]
                    if (same_x(prev_pt, point) and same_x(point, next_pt)) or (
                        same_y(prev_pt, point) and same_y(point, next_pt)
                    ):
                        continue
                    result.append(point)
                return result if len(result) >= 3 else points

            changed = True
            cleaned = coords[:]
            passes = 0
            while changed and passes < 4 and len(cleaned) >= 7:
                passes += 1
                changed = False
                n = len(cleaned)
                for i in range(n):
                    p0 = cleaned[i]
                    p1 = cleaned[(i + 1) % n]
                    p2 = cleaned[(i + 2) % n]
                    p3 = cleaned[(i + 3) % n]

                    bridge_is_horizontal = same_y(p0, p3)
                    bridge_is_vertical = same_x(p0, p3)
                    if not bridge_is_horizontal and not bridge_is_vertical:
                        continue

                    d01 = dist(p0, p1)
                    d12 = dist(p1, p2)
                    d23 = dist(p2, p3)
                    bridge = dist(p0, p3)
                    if min(d01, d12, d23) <= 1e-6:
                        continue
                    if max(d01, d12, d23, bridge) > max_notch:
                        continue

                    candidate = cleaned[:]
                    idxs = sorted({(i + 1) % n, (i + 2) % n}, reverse=True)
                    for idx in idxs:
                        del candidate[idx]
                    candidate_ring = candidate + [candidate[0]]
                    candidate_poly = Polygon(candidate_ring)
                    if not candidate_poly.is_valid:
                        candidate_poly = candidate_poly.buffer(0)
                    if (
                        candidate_poly
                        and candidate_poly.geom_type == "Polygon"
                        and candidate_poly.area > 1e-6
                        and (candidate_poly.contains(target_pt) or candidate_poly.touches(target_pt))
                    ):
                        cleaned = candidate
                        changed = True
                        break

            if cleaned != coords and len(cleaned) >= 3:
                cleaned = remove_collinear(cleaned)
                cleaned_poly = Polygon(cleaned + [cleaned[0]])
                if not cleaned_poly.is_valid:
                    cleaned_poly = cleaned_poly.buffer(0)
                if cleaned_poly and cleaned_poly.geom_type == "Polygon":
                    return cleaned_poly
        except Exception:
            return poly
        return poly
        
    def _init_global_boundary(self):
        """
        Calcula o 'Envelope' global do desenho para validar o que Ã© 'Exterior'.
        Prioridade: 
        1. Layers explicitos ('MARCO', 'CONTORNO', 'LIMITE').
        2. Se nÃ£o achar, Convex Hull de toda a estrutura (Vigas/Paredes).
        """
        marco_geoms = []
        structure_geoms = []
        
        # Iterar todos os itens do indice
        # O spatial_index expÃµe 'items' (Dict[int, Any])
        all_items = list(self.spatial_index.items.values()) if hasattr(self.spatial_index, 'items') else []
        
        invalid_layers = ['COTA', 'DIM', 'TEXT', 'EIXO', 'HATCH', 'MP_', 'OBS', 'TITULO']
        
        for item in all_items:
            geom = None
            layer = ""
            
            if isinstance(item, dict):
                layer = item.get('layer', '').upper()
                if 'points' in item: geom = LineString(item['points'])
                elif 'start' in item: geom = LineString([item['start'], item['end']])
            elif isinstance(item, list) and len(item) > 1:
                geom = LineString(item) # Tupla antiga/lista
                
            if not geom: continue
            
            # Checar se Ã© Marco
            if any(k in layer for k in ['MARCO', 'CONTORNO', 'LIMITE', 'FRAME']):
                marco_geoms.append(geom)
            
            # Checar se Ã© Estrutura (para fallback)
            is_invalid = any(k in layer for k in invalid_layers)
            if not is_invalid:
                structure_geoms.append(geom)
                
        if marco_geoms:
            # Temos um Marco explicito!
            print(f"[INFO] Detectado Marco Global com {len(marco_geoms)} segmentos.")
            try:
                self.global_boundary = unary_union(marco_geoms)
            except:
                self.global_boundary = unary_union(marco_geoms).convex_hull
        elif structure_geoms:
            # Fallback: Convex Hull de tudo
            print(f"[INFO] Marco nÃ£o detectado. Usando Convex Hull da estrutura ({len(structure_geoms)} segmentos).")
            try:
                # Unary union de muitas linhas pode ser lento. 
                # Otimizacao: Convex Hull dos PONTOS extremidades?
                # Sim, extrair todos os pontos e fazer convex hull Ã© muito mais rapido.
                all_points = []
                for g in structure_geoms:
                    all_points.extend(g.coords)
                
                if all_points:
                    from shapely.geometry import MultiPoint
                    self.global_boundary = MultiPoint(all_points).convex_hull
            except Exception as e:
                print(f"[ERROR] Falha ao calcular Convex Hull: {e}")
                self.global_boundary = None
        
        if self.global_boundary:
             # OtimizaÃ§Ã£o: Converter para apenas Exterior Ring se for Poligono (ignorar buracos internos do Hull)
             if isinstance(self.global_boundary, Polygon):
                 self.global_boundary = self.global_boundary.exterior
             elif isinstance(self.global_boundary, MultiLineString):
                 self.global_boundary = self.global_boundary

    def trace_boundary(self, start_point: Tuple[float, float], search_radius: float = 1000.0, valid_layers: List[str] = None, label_id: str = None) -> Optional[Polygon]:
        """Find slab polygon via cascade: semantic filter -> local crop -> polygonize -> N2 axes -> professor N2."""
        cx, cy = start_point
        bounds = (cx - search_radius, cy - search_radius, cx + search_radius, cy + search_radius)
        candidates = self.spatial_index.query_bbox(bounds)
        lines, rejected, classified = self._collect_laje_candidate_lines(candidates, valid_layers=valid_layers)
        crop_bbox = self._laj_crop_bbox_from_labels(label_id or "", start_point, search_radius)
        self.last_trace_diagnostics = {
            "candidate_line_count": len(classified),
            "accepted_line_count": len(lines),
            "rejected_line_count": len(rejected),
            "label_id": label_id,
            "n2_axes_crop_bbox": crop_bbox,
            "outline_source": "none",
            "rejections": [
                {"layer": info.get("layer"), "reasons": info.get("reasons", [])}
                for _, info in rejected[:50]
            ],
        }
        if not lines:
            return None
        target_pt = Point(cx, cy)
        try:
            noded_lines = unary_union(lines)
            polygons = list(polygonize(noded_lines))
            selected = self._select_best_laje_polygon(polygons, target_pt)
            teacher = (getattr(self, "_laj_teacher_dims", {}) or {}).get((label_id or "").upper())
            teacher_poly = self._teacher_laj_outline_from_n2_dims(lines, target_pt, crop_bbox, teacher) if crop_bbox else None
            axes_poly = teacher_poly or (self._canonical_laj_outline_from_n2_axes(lines, target_pt, crop_bbox) if crop_bbox else None)
            if self._should_prefer_n2_axes_outline(selected, axes_poly, target_pt):
                self.last_trace_diagnostics["outline_source"] = "n2_teacher_axes" if teacher_poly else "n2_axes"
                result = axes_poly
            else:
                self.last_trace_diagnostics["outline_source"] = "polygonize"
                result = selected
            self.last_trace_diagnostics["confidence_score"] = self._compute_confidence(result, target_pt, teacher, crop_bbox)
            return result
        except Exception as e:
            print(f"[DEBUG] Trace Error: {e}")
            return None

    def _compute_confidence(self, poly: Polygon, target_pt: Point, teacher: dict | None, crop_bbox: tuple | None) -> float:
        """Compute confidence score 0-1 for the detected slab outline."""
        if poly is None or poly.is_empty:
            return 0.0
        try:
            area_ratio = 1.0
            n2_match = 0.0
            edge_score = 1.0
            bbox_coverage = 1.0

            poly_area = poly.area
            poly_bbox = poly.bounds
            pw, ph = poly_bbox[2] - poly_bbox[0], poly_bbox[3] - poly_bbox[1]

            # N2 teacher match
            if teacher:
                t_comp = float(teacher.get("comprimento") or teacher.get("comp") or 0.0)
                t_larg = float(teacher.get("largura") or teacher.get("larg") or 0.0)
                if t_comp > 0 and t_larg > 0:
                    d1 = min(abs(pw - t_comp), abs(ph - t_comp))
                    d2 = min(abs(pw - t_larg), abs(ph - t_larg))
                    dim_delta = (d1 + d2) / max(t_comp + t_larg, 1.0)
                    if dim_delta <= 0.02:
                        n2_match = 1.0
                    elif dim_delta <= 0.05:
                        n2_match = 0.7
                    elif dim_delta <= 0.10:
                        n2_match = 0.4

            # Edge count (rectangular = 4 edges ideal)
            n_edges = len(poly.exterior.coords) - 1
            if n_edges <= 4:
                edge_score = 1.0
            elif n_edges <= 6:
                edge_score = 0.8
            elif n_edges <= 8:
                edge_score = 0.5
            else:
                edge_score = 0.3

            # Area ratio (not too tiny, not absurdly large)
            if teacher and t_comp > 0 and t_larg > 0:
                n2_area = t_comp * t_larg
                area_ratio = min(poly_area, n2_area) / max(poly_area, n2_area, 1.0) if n2_area > 0 else 1.0

            # Bbox coverage within crop
            if crop_bbox:
                cx0, cy0, cx1, cy1 = crop_bbox
                crop_area = max(0.0, cx1 - cx0) * max(0.0, cy1 - cy0)
                if crop_area > 0:
                    ix0 = max(poly_bbox[0], cx0)
                    iy0 = max(poly_bbox[1], cy0)
                    ix1 = min(poly_bbox[2], cx1)
                    iy1 = min(poly_bbox[3], cy1)
                    overlap = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
                    bbox_coverage = min(overlap / max(poly_area, 1.0), 1.0)

            # Weighted score with tightened edge weight (structural quality matters more)
            score = 0.45 * n2_match + 0.20 * min(1.0, area_ratio) + 0.20 * edge_score + 0.15 * bbox_coverage
            return round(score, 3)
        except Exception:
            return 0.0

    def detect_extensions(self, main_poly: Polygon, search_radius: float = 50.0) -> List[Dict]:
        """
        Detecta e GERA 'acrÃ©scimos' (strips de 10 unidades) em bordas externas.
        EstratÃ©gia: Generative Edge Extrusion (V4).
        1. Para cada aresta da laje:
        2. Testar se aponta para o 'vazio' (Ray Cast).
        3. Se for vazio, extrudar aresta em 10 unidades e criar polÃ­gono.
        """
        if not main_poly or not self.spatial_index:
            return []

        generated_extensions = []
        
        coords = list(main_poly.exterior.coords)
        if len(coords) < 2: return []
        
        # Remove duplicate last point for indexing ease (LinearRing logic)
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        
        num_pts = len(coords)
        if num_pts < 3: return []

        # Parameters
        BLOCK_DIST_THRESHOLD = 1000.0 # 10m
        EXTENSION_WIDTH = 10.0
        
        # 1. Classification Phase
        # ---------------------
        edge_status = [] # True=Free, False=Blocked
        
        for i in range(num_pts):
            p1 = coords[i]
            p2 = coords[(i+1)%num_pts] # Wrap around
            
            # Geometry Check
            edge = LineString([p1, p2])
            if edge.length < 1.0: 
                edge_status.append(False) # Too short, ignore/block
                continue
                
            # --- Ray Cast Logic (Reuse V4) ---
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = (dx*dx + dy*dy)**0.5
            nx, ny = -dy/length, dx/length
            
            # Ensure Normal is Outward
            mid = edge.interpolate(0.5, normalized=True)
            check_pt = (mid.x + nx*0.1, mid.y + ny*0.1)
            if main_poly.contains(Point(check_pt)):
                nx, ny = -nx, -ny
            
            # Fan Scan
            angles = [0, -10, 10]
            is_blocked = False
            
            for ang in angles:
                rad = math.radians(ang)
                rnx = nx * math.cos(rad) - ny * math.sin(rad)
                rny = nx * math.sin(rad) + ny * math.cos(rad)
                
                r_start = (mid.x + rnx*1.0, mid.y + rny*1.0)
                r_end = (r_start[0] + rnx*5000.0, r_start[1] + rny*5000.0)
                ray_geom = LineString([r_start, r_end])
                
                hits = self.spatial_index.query_bbox(ray_geom.bounds)
                
                for h in hits:
                    h_geom = None
                    if isinstance(h, dict):
                        if 'points' in h: h_geom = LineString(h['points'])
                        elif 'start' in h: h_geom = LineString([h['start'], h['end']])
                    elif isinstance(h, list) and len(h) > 1: h_geom = LineString(h)
                    
                    if not h_geom: continue
                    if not ray_geom.intersects(h_geom): continue
                    
                    if Point(r_start).distance(h_geom) < BLOCK_DIST_THRESHOLD:
                        is_blocked = True
                        break
                if is_blocked: break
            
            edge_status.append(not is_blocked)
            
        # 2. Chaining Phase
        # -----------------
        # Find continuous sequences of True
        chains = []
        if not edge_status: return []
        
        # Rotate logic to handle wrap-around easily
        # Ensure we don't start in the middle of a True chain
        start_idx = 0
        if all(edge_status):
            # Special Case: All Free (Island)
            chains.append(list(range(num_pts)) + [0]) # Full Loop
        else:
            # Shift start_idx to a False (Blocked) to ensure Chain starts cleanly
            if edge_status[0]:
                for k in range(num_pts):
                    if not edge_status[k]:
                        start_idx = (k + 1) % num_pts
                        break
            
            current_chain = []
            for k in range(num_pts):
                idx = (start_idx + k) % num_pts
                if edge_status[idx]:
                    if not current_chain:
                        current_chain.append(idx)
                    current_chain.append((idx + 1) % num_pts)
                else:
                    if current_chain:
                        chains.append(current_chain)
                        current_chain = []
            
            # Append last chain if exists
            if current_chain:
                chains.append(current_chain)

        # 3. Generation Phase (Offset)
        # ----------------------------
        for chain_indices in chains:
            # Extract geometry points
            pts = [coords[i] for i in chain_indices]
            if len(pts) < 2: continue
            
            line = LineString(pts)
            
            # Determining Side for Offset
            # Shapely's offset_curve:
            # Positive distance = Left side
            # Negative distance = Right side
            # If Polygon is CCW, Outwards is RIGHT (-distance)
            # We need to verify basic winding or just try.
            # Usually LinearRing is CCW. So we try -EXTENSION_WIDTH.
            
            try:
                # Try Negative Offset (Right/Outwards for CCW)
                offset_dist = -EXTENSION_WIDTH
                offset_line = line.offset_curve(offset_dist, join_style=2) # 2=Mitre
                
                # Validation: Check if offset is actually outside
                # Take midpoint of offset line
                test_pt = offset_line.interpolate(0.5, normalized=True)
                if main_poly.contains(test_pt) or main_poly.distance(test_pt) < 1.0:
                    # Oops, it went inside. Flip sign.
                    # This handles CW polygons too.
                    offset_dist = EXTENSION_WIDTH
                    offset_line = line.offset_curve(offset_dist, join_style=2)
                
                # Construct Polygon
                # Pts -> ... -> OffsetPts(Reversed) -> Pts[0]
                
                # Careful with OffsetCurve output, it might be MultiLineString if complex, 
                # but for simple chains it should be LineString.
                if hasattr(offset_line, 'geoms'): # MultiLineString
                     # Fallback to simple segment processing? 
                     # Or pick longest? Usually happens if self-intersecting.
                     # Simplified approach: skip complex stuff or take largest
                     continue
                
                off_coords = list(offset_line.coords)
                
                # Ring Construction:
                # Original Line (A->B->C) + Offset Line Reversed (C'->B'->A') + Close
                if offset_dist > 0:
                   # If Positive (Left), offset runs A->B direction? No, offset direction usually matches index.
                   # Let's trust coords order and reverse one of them to form loop.
                   pass
                
                # Standard Loop: Pts + Reversed(Offset)
                # Note: offset_curve usually returns points usually in same direction as input
                final_loop = pts + off_coords[::-1] + [pts[0]]
                
                ext_poly = Polygon(final_loop)
                
                # Fix self-intersections if any (buffer 0)
                if not ext_poly.is_valid:
                    ext_poly = ext_poly.buffer(0)

                generated_extensions.append({
                    'type': 'poly',
                    'points': list(ext_poly.exterior.coords),
                    'role': 'Acrescimo_borda',
                    'width_est': EXTENSION_WIDTH,
                    'side': 'Composite' # Generic side
                })
                
            except Exception as e:
                print(f"[ERROR] Failed to generate offset for chain: {e}")
                continue

        return generated_extensions


    def detect_slabs_from_texts(self, texts: List[Dict], search_radius: float = 2000.0, valid_layers: List[str] = None, teacher_dims: Dict[str, Dict] = None) -> List[Dict]:
        """Detect slab labels and trace outlines using cascade: semantic + crop + polygonize + N2 axes + teacher."""
        slabs = []
        import re
        slab_pattern = re.compile(r'^(L|LAJE)\s*[-_]?\s*\d+[a-zA-Z]*$', re.IGNORECASE)
        label_centroids = {}
        label_points = {}
        for t in texts:
            txt = t.get('text', '').strip().upper()
            if not slab_pattern.match(txt):
                continue
            pos = t.get('pos')
            if not pos:
                continue
            label_points.setdefault(txt, []).append((float(pos[0]), float(pos[1])))
        for txt, pts in label_points.items():
            label_centroids[txt] = (
                sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts),
            )
        self._laj_label_centroids = label_centroids
        self._laj_teacher_dims = {str(k).upper(): v for k, v in (teacher_dims or {}).items() if isinstance(v, dict)}

        teacher_count = len(self._laj_teacher_dims)
        print(f"[DEBUG] SlabTracer cascade on {len(texts)} texts. N2 teacher={teacher_count}")
        for t in texts:
            txt = t.get('text', '').strip()
            if not slab_pattern.match(txt):
                continue
            pos = t.get('pos')
            if not pos:
                continue

            poly = self.trace_boundary(
                pos,
                search_radius,
                valid_layers=valid_layers,
                label_id=txt.upper(),
            )
            found_poly = bool(poly)
            extensions = []
            diag = self.last_trace_diagnostics or {}
            if poly:
                points = list(poly.exterior.coords)
                area = poly.area
                try:
                    extensions = self.detect_extensions(poly)
                except Exception as e:
                    print(f"Erro detectando extensoes Laje {txt}: {e}")
            else:
                cx, cy = pos
                points = [
                    (cx - 25, cy - 25), (cx + 25, cy - 25),
                    (cx + 25, cy + 25), (cx - 25, cy + 25),
                    (cx - 25, cy - 25),
                ]
                area = 0.0

            confidence = diag.get("confidence_score", 0.0)
            slab = {
                'id': f"temp_{len(slabs)}",
                'name': txt.upper(),
                'pos': pos,
                'points': points,
                'area': area,
                'neighbors': [],
                'is_detected': found_poly,
                'is_validated': False,
                'type': 'Laje',
                'extensions': extensions,
                'analysis_mode': 'cascade',
                'confidence_score': confidence,
                'confidence_level': 'HIGH' if confidence >= 0.85 else ('MEDIUM' if confidence >= 0.60 else 'LOW'),
            }
            if diag:
                slab['trace_diagnostics'] = dict(diag)
            slabs.append(slab)

        return slabs
