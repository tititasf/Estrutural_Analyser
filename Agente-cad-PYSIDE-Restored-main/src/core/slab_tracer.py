from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union
from typing import List, Tuple, Optional, Dict
import math

class SlabTracer:
    """
    Algoritmo 'Boundary Tracer' para Lajes.
    Usa 'Path Finding' (Polygonize) para encontrar polÃƒÂ­gonos fechados formados por vigas/paredes.
    """
    def __init__(self, spatial_index, learning_params=None):
        self.spatial_index = spatial_index
        self.global_boundary = None
        self.last_trace_diagnostics = {}
        self._laj_label_centroids = {}
        self._laj_teacher_dims = {}
        # Learning Store params (optional - zero regressao se None)
        self._learning_params = learning_params or {}

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
            "NIVEL", "NÃƒÂVEL", "LEVEL", "MEDIDA", "AUX", "AUXILIAR",
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
                norm_layer = (layer or '').upper()
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

    def _collect_laje_preferred_outline_lines(self, candidates):
        """Collect high-confidence outline lines without using layer names as a filter.

        Some training DXFs use numeric layers for both dimensions and structure.  The
        safer signal in those files is entity styling: real slab/form edges are often
        continuous green/ACI-3 lines, while auxiliary dimensions are gray/white/magenta.
        This set is only a preference for axis ranking; the full candidate set remains
        available as fallback.
        """
        preferred = []
        for item in candidates:
            for geom, layer, raw_type, linetype, color, original in self._item_to_lines(item):
                if geom.length <= 1e-6:
                    continue
                info = self._classify_laje_candidate_line(geom, layer, raw_type, linetype, color)
                if not info.get("accepted"):
                    continue
                aci = None
                if isinstance(original, dict):
                    aci = original.get("aci")
                rgb_green = False
                if isinstance(color, (list, tuple)) and len(color) >= 3:
                    rgb_green = int(color[1]) >= 180 and int(color[0]) <= 80 and int(color[2]) <= 80
                color_text = str(color or "").upper()
                layer_text = str(layer or "").upper()
                if (
                    aci == 3
                    or rgb_green
                    or "0, 255, 0" in color_text
                    or any(tok in layer_text for tok in ("VIGA", "LAJ", "FORMA", "CONCRETO", "CONTORNO"))
                ):
                    preferred.append(geom)
        return preferred

    def _select_best_laje_polygon(self, polygons, target_pt: Point, crop_bbox: tuple = None):
        containing = []
        for poly in polygons:
            if not poly.is_valid or poly.area <= 1e-6:
                continue
            if poly.contains(target_pt) or poly.touches(target_pt):
                containing.append(poly)
        if not containing:
            return None
        # Filter out absurdly large polygons (likely merged with neighbors)
        if crop_bbox:
            cx0, cy0, cx1, cy1 = crop_bbox
            crop_area = max(1.0, (cx1 - cx0) * (cy1 - cy0))
            containing = [p for p in containing if p.area <= crop_area * 5.0]
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

        bbox = self._shrink_laj_bbox_away_from_labels((x0, y0, x1, y1), label_id)
        # Do not let label-based shrinking cut the opposite structural edge.
        # Several LAJ labels sit close to one side of the slab; a too-tight crop
        # leaves the real boundary outside polygonize/axis selection.
        bx0, by0, bx1, by1 = bbox
        min_half_x = min(500.0, max(180.0, median_x_gap * 0.45))
        min_half_y = min(420.0, max(160.0, median_y_gap * 0.60))
        if (bx1 - bx0) / 2.0 < min_half_x:
            bx0 = min(bx0, cx - min_half_x)
            bx1 = max(bx1, cx + min_half_x)
        if (by1 - by0) / 2.0 < min_half_y:
            by0 = min(by0, cy - min_half_y)
            by1 = max(by1, cy + min_half_y)
        bbox = (bx0, by0, bx1, by1)
        # N2 teacher clamp: if teacher dims available, clamp bbox to max 1.5x N2 dims
        teacher = getattr(self, "_laj_teacher_dims", {}) or {}
        t = teacher.get(label_id, {}) if label_id else {}
        # Fuzzy lookup if exact match fails
        if not t or (not t.get("comprimento") and not t.get("largura")):
            t = self._fuzzy_teacher_lookup(label_id) if label_id else {}
        try:
            tc = float(t.get("comprimento") or 0)
            tl = float(t.get("largura") or 0)
        except Exception:
            tc = tl = 0
        if tc > 20.0 and tl > 20.0:
            cx_mid = (bbox[0] + bbox[2]) / 2.0
            cy_mid = (bbox[1] + bbox[3]) / 2.0
            # Clamp: expand if crop too small, shrink if too large
            min_half_w = tc * 0.55  # at least 110% of N2 width
            min_half_h = tl * 0.55  # at least 110% of N2 height
            max_half_w = tc * 0.85  # at most 170% of N2 width
            max_half_h = tl * 0.85  # at most 170% of N2 height
            half_w = max(min_half_w, min(max_half_w, (bbox[2] - bbox[0]) / 2.0))
            half_h = max(min_half_h, min(max_half_h, (bbox[3] - bbox[1]) / 2.0))
            bbox = (
                cx_mid - half_w,
                cy_mid - half_h,
                cx_mid + half_w,
                cy_mid + half_h,
            )
        return bbox

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

    def _outline_from_long_parallel_strips(self, lines, target_pt: Point, crop_bbox: tuple) -> Optional[Polygon]:
        """Detect long narrow slabs from parallel structural edges without teacher data."""
        try:
            cx, cy = target_pt.x, target_pt.y
            bx0, by0, bx1, by1 = crop_bbox
            bw = max(1.0, bx1 - bx0)
            bh = max(1.0, by1 - by0)

            centroids = getattr(self, "_laj_label_centroids", {}) or {}
            if len(centroids) >= 2:
                xs = sorted(x for x, _ in centroids.values())
                ys = sorted(y for _, y in centroids.values())
                x_gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1) if xs[i + 1] - xs[i] > 10.0]
                y_gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1) if ys[i + 1] - ys[i] > 10.0]
                median_x_gap = sorted(x_gaps)[len(x_gaps) // 2] if x_gaps else bw
                median_y_gap = sorted(y_gaps)[len(y_gaps) // 2] if y_gaps else bh
            else:
                median_x_gap, median_y_gap = bw, bh

            wide_x = max(bw * 2.8, median_x_gap * 2.2)
            wide_y = max(bh * 1.8, median_y_gap * 1.8)
            wide_crop = (cx - wide_x, cy - wide_y, cx + wide_x, cy + wide_y)
            h_groups, v_groups = self._axis_groups_from_laj_lines(lines, wide_crop, margin=max(80.0, min(wide_x, wide_y) * 0.04))

            def merged_axis_intervals(group, axis="x"):
                gap_tol = max(25.0, (median_x_gap if axis == "x" else median_y_gap) * 0.35)
                ordered = sorted((min(a, b), max(a, b)) for a, b in group.get("intervals", []))
                if not ordered:
                    return []
                merged = [ordered[0]]
                for a0, a1 in ordered[1:]:
                    m0, m1 = merged[-1]
                    if a0 <= m1 + gap_tol:
                        merged[-1] = (m0, max(m1, a1))
                    else:
                        merged.append((a0, a1))
                return merged

            def overlap_intervals(a, b, axis="x"):
                out = []
                for a0, a1 in merged_axis_intervals(a, axis=axis):
                    for b0, b1 in merged_axis_intervals(b, axis=axis):
                        lo, hi = max(a0, b0), min(a1, b1)
                        if hi > lo:
                            out.append((lo, hi))
                return out

            def label_penalty(x0, y0, x1, y1):
                penalty = 0.0
                for _, (ox, oy) in centroids.items():
                    if abs(ox - cx) < 1e-6 and abs(oy - cy) < 1e-6:
                        continue
                    if x0 < ox < x1 and y0 < oy < y1:
                        penalty += 1000.0
                return penalty

            best = None
            best_score = float("inf")

            # Long horizontal slab strip: two horizontal outlines define y, overlap defines x.
            h_sorted = sorted(h_groups, key=lambda g: g["const"])
            for bottom in h_sorted:
                if bottom["const"] >= cy:
                    continue
                for top in h_sorted:
                    if top["const"] <= cy:
                        continue
                    height = top["const"] - bottom["const"]
                    if height < max(120.0, median_y_gap * 1.15) or height > max(260.0, median_y_gap * 0.75):
                        continue
                    for x0, x1 in overlap_intervals(bottom, top, axis="x"):
                        width = x1 - x0
                        if width <= 0 or not (x0 - 10.0 <= cx <= x1 + 10.0):
                            continue
                        aspect = width / max(height, 1.0)
                        if width < max(900.0, median_x_gap * 1.25) or aspect < 4.0:
                            continue
                        y0, y1 = bottom["const"], top["const"]
                        lp = label_penalty(x0, y0, x1, y1)
                        if lp > 0:
                            continue
                        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
                        if not poly.is_valid or not (poly.contains(target_pt) or poly.touches(target_pt)):
                            continue
                        center_penalty = abs(((y0 + y1) / 2.0) - cy) * 0.8 + abs(((x0 + x1) / 2.0) - cx) * 0.03
                        score = center_penalty - width * 0.08 + height * 0.8
                        if score < best_score:
                            best_score = score
                            best = poly

            # Tall vertical slab strip: two vertical outlines define x, overlap defines y.
            v_sorted = sorted(v_groups, key=lambda g: g["const"])
            for left in v_sorted:
                if left["const"] >= cx:
                    continue
                for right in v_sorted:
                    if right["const"] <= cx:
                        continue
                    width = right["const"] - left["const"]
                    if width <= 20.0 or width > max(180.0, median_x_gap * 0.45):
                        continue
                    for y0, y1 in overlap_intervals(left, right, axis="y"):
                        height = y1 - y0
                        if height <= 0 or not (y0 - 10.0 <= cy <= y1 + 10.0):
                            continue
                        if height > max(650.0, median_y_gap * 6.0):
                            continue
                        aspect = height / max(width, 1.0)
                        if height < max(380.0, median_y_gap * 1.0) or aspect < 3.2:
                            continue
                        x0, x1 = left["const"], right["const"]
                        lp = label_penalty(x0, y0, x1, y1)
                        if lp > 0:
                            continue
                        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
                        if not poly.is_valid or not (poly.contains(target_pt) or poly.touches(target_pt)):
                            continue
                        center_penalty = abs(((x0 + x1) / 2.0) - cx) * 0.8 + abs(((y0 + y1) / 2.0) - cy) * 0.03
                        compact_width_penalty = width * 0.9
                        score = center_penalty + compact_width_penalty - height * 0.06
                        if score < best_score:
                            best_score = score
                            best = poly

            return best
        except Exception:
            return None

    def _local_dimension_values_near_laje(self, target_pt: Point, radius_x: float = 750.0, radius_y: float = 500.0):
        """Read numeric dimension texts near a slab label from the structural DXF only."""
        vals = []
        try:
            import re as _re
            cx, cy = target_pt.x, target_pt.y
            items = self.spatial_index.query_bbox((cx - radius_x, cy - radius_y, cx + radius_x, cy + radius_y))
            slab_pat = _re.compile(r'^L[A-Z]*[-_]?\d+[A-Z0-9_]*$', _re.I)
            for item in items:
                if not isinstance(item, dict) or "text" not in item or "pos" not in item:
                    continue
                txt = str(item.get("text") or "").strip()
                up = txt.upper()
                if not txt or slab_pat.match(up) or up.startswith("P") or up.startswith("V") or "852" in up or "H=" in up:
                    continue
                pos = item.get("pos") or (0.0, 0.0)
                dist = ((float(pos[0]) - cx) ** 2 + (float(pos[1]) - cy) ** 2) ** 0.5
                for match in _re.findall(r'\d+(?:\.\d+)?', txt):
                    val = float(match)
                    if 60.0 <= val <= 650.0:
                        vals.append((val, dist, txt))
        except Exception:
            return []
        return vals

    @staticmethod
    def _dimension_text_match_score(dim: float, values) -> tuple[float, bool]:
        best = 999.0
        matched = False
        for val, dist, _txt in values or []:
            err = abs(float(dim) - float(val))
            tol = max(6.0, float(val) * 0.06)
            if err <= max(18.0, float(val) * 0.12):
                score = err / tol + float(dist) * 0.002
                if score < best:
                    best = score
                    matched = True
        return best, matched

    def _outline_from_local_dimension_texts(self, lines, target_pt: Point, crop_bbox: tuple, current_poly: Polygon | None) -> Optional[Polygon]:
        """Use nearby structural dimension texts as evidence for ambiguous thin slabs."""
        if current_poly is None or current_poly.is_empty:
            return None
        try:
            values = self._local_dimension_values_near_laje(target_pt)
            if not values:
                return None

            cb = current_poly.bounds
            cw, ch = cb[2] - cb[0], cb[3] - cb[1]
            if max(cw, ch) >= 500.0 and max(cw, ch) / max(min(cw, ch), 1.0) >= 3.0:
                return None
            cur_a = self._dimension_text_match_score(cw, values)
            cur_b = self._dimension_text_match_score(ch, values)
            cur_matches = int(cur_a[1]) + int(cur_b[1])

            # Only intervene when the current outline has weak local text support.
            if cur_matches >= 2:
                return None

            cx, cy = target_pt.x, target_pt.y
            w0 = max(900.0, (crop_bbox[2] - crop_bbox[0]) * 0.9)
            h0 = max(500.0, (crop_bbox[3] - crop_bbox[1]) * 0.7)
            search = (cx - w0, cy - h0, cx + w0, cy + h0)
            h_groups, v_groups = self._axis_groups_from_laj_lines(lines, search, margin=120.0)
            h_groups = sorted(
                [g for g in h_groups if abs(g["const"] - cy) <= h0],
                key=lambda g: abs(g["const"] - cy),
            )[:28]
            v_groups = sorted(
                [g for g in v_groups if abs(g["const"] - cx) <= w0],
                key=lambda g: abs(g["const"] - cx),
            )[:28]
            centroids = getattr(self, "_laj_label_centroids", {}) or {}
            best_poly = None
            best_score = float("inf")

            for lo in v_groups:
                for ro in v_groups:
                    if ro["const"] <= lo["const"] or not (lo["const"] - 8.0 <= cx <= ro["const"] + 8.0):
                        continue
                    width = ro["const"] - lo["const"]
                    if width < 45.0 or width > 1000.0:
                        continue
                    for bo in h_groups:
                        for to in h_groups:
                            if to["const"] <= bo["const"] or not (bo["const"] - 8.0 <= cy <= to["const"] + 8.0):
                                continue
                            height = to["const"] - bo["const"]
                            if height < 45.0 or height > 750.0:
                                continue
                            x0, x1 = lo["const"], ro["const"]
                            y0, y1 = bo["const"], to["const"]
                            if any(
                                not (abs(ox - cx) < 1e-6 and abs(oy - cy) < 1e-6)
                                and x0 < ox < x1 and y0 < oy < y1
                                for _k, (ox, oy) in centroids.items()
                            ):
                                continue

                            w_score, w_match = self._dimension_text_match_score(width, values)
                            h_score, h_match = self._dimension_text_match_score(height, values)
                            if not (w_match and h_match):
                                continue
                            poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
                            if not poly.is_valid or not (poly.contains(target_pt) or poly.touches(target_pt)):
                                continue

                            span = min(lo["span"], ro["span"], bo["span"], to["span"])
                            center = abs(((x0 + x1) / 2.0) - cx) * 0.004 + abs(((y0 + y1) / 2.0) - cy) * 0.004
                            score = w_score + h_score + center - span * 0.0006 + (width * height) * 0.0000015
                            if score < best_score:
                                best_score = score
                                best_poly = poly

            if best_poly is None:
                return None
            nb = best_poly.bounds
            nw, nh = nb[2] - nb[0], nb[3] - nb[1]
            new_a = self._dimension_text_match_score(nw, values)
            new_b = self._dimension_text_match_score(nh, values)
            new_score = new_a[0] + new_b[0]
            cur_score = (cur_a[0] if cur_a[1] else 4.0) + (cur_b[0] if cur_b[1] else 4.0)
            if new_score + 0.6 < cur_score:
                return best_poly
        except Exception:
            return None
        return None

    def _thin_irregular_polygonized_strip(self, polygon: Polygon | None, axes_poly: Polygon | None, target_pt: Point, lines) -> Optional[Polygon]:
        """Recover irregular thin strip slabs that polygonize detects better than axes."""
        if polygon is None or axes_poly is None or polygon.is_empty or axes_poly.is_empty:
            return None
        try:
            pb = polygon.bounds
            ab = axes_poly.bounds
            pw, ph = pb[2] - pb[0], pb[3] - pb[1]
            aw, ah = ab[2] - ab[0], ab[3] - ab[1]
            if not (55.0 <= ah <= 90.0 and aw >= 300.0):
                return None
            if not (abs(ph - ah) <= 18.0 and 0.38 <= (pw / max(aw, 1.0)) <= 0.72):
                return None
            if not (polygon.contains(target_pt) or polygon.touches(target_pt)):
                return None

            search = (ab[0] - 80.0, ab[1] - 60.0, ab[2] + 80.0, ab[3] + 60.0)
            noded = unary_union(lines)
            cells = [p for p in polygonize(noded) if p.is_valid and p.area > 80.0]
            result = polygon
            for cell in sorted(cells, key=lambda p: p.area, reverse=True):
                if cell.equals(polygon) or cell.area < 900.0 or cell.area > polygon.area * 0.30:
                    continue
                cb = cell.bounds
                if cb[0] < pb[2] - 2.0 or cb[0] > pb[2] + 35.0:
                    continue
                if cb[2] > ab[2] + 8.0:
                    continue
                y_overlap = max(0.0, min(pb[3], cb[3]) - max(pb[1], cb[1]))
                if y_overlap < ah * 0.70:
                    continue
                merged = unary_union([result, cell])
                if merged.geom_type != "Polygon":
                    continue
                mb = merged.bounds
                if mb[2] - mb[0] > aw * 0.82 or mb[3] - mb[1] > ah + 20.0:
                    continue
                result = merged
                break
            if result.area > polygon.area + 500.0:
                rb = result.bounds
                fill = result.area / max((rb[2] - rb[0]) * (rb[3] - rb[1]), 1.0)
                if fill < 0.92:
                    return result
                return None
            pb2 = polygon.bounds
            fill = polygon.area / max((pb2[2] - pb2[0]) * (pb2[3] - pb2[1]), 1.0)
            if fill < 0.92 and len(polygon.exterior.coords) >= 7:
                return polygon
        except Exception:
            return None
        return None

    def _normalize_thin_slab_rows(self, slabs: List[Dict]) -> None:
        """Normalize repeated thin slab strips from the detected row itself.

        This is a pure SA geometric cleanup: it uses only the set of slabs just
        detected in the structural drawing. It is meant for bottom/top strip rows
        where one label was clipped by local hatches/cut-view geometry.
        """
        try:
            thin = []
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w, h = x1 - x0, y1 - y0
                if 45.0 <= h <= 95.0 and w >= 250.0:
                    thin.append((slab, x0, y0, x1, y1, w, h, (y0 + y1) / 2.0))
            if len(thin) < 3:
                return

            rows = []
            for item in sorted(thin, key=lambda it: it[7]):
                for row in rows:
                    if abs(row[0][7] - item[7]) <= 18.0:
                        row.append(item)
                        break
                else:
                    rows.append([item])

            def median(values):
                ordered = sorted(values)
                n = len(ordered)
                if n == 0:
                    return 0.0
                mid = n // 2
                return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0

            for row in rows:
                if len(row) < 3:
                    continue
                heights = [it[6] for it in row]
                widths = [it[5] for it in row if it[5] >= 360.0]
                row_h = median(heights)
                if not (60.0 <= row_h <= 85.0):
                    continue
                row_y0 = median([it[2] for it in row])
                row_y1 = median([it[4] for it in row])
                if abs((row_y1 - row_y0) - row_h) > 12.0:
                    row_y1 = row_y0 + row_h
                row_w = median(widths) if len(widths) >= 2 else 0.0

                for slab, x0, y0, x1, y1, w, h, _ym in row:
                    pos = slab.get("pos") or ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
                    lx = float(pos[0])
                    nx0, nx1 = x0, x1
                    ny0, ny1 = y0, y1
                    changed = False

                    if abs(h - row_h) > 10.0 and row_y0 - 3.0 <= float(pos[1]) <= row_y1 + 3.0:
                        ny0, ny1 = row_y0, row_y1
                        changed = True

                    if row_w >= 390.0 and w < row_w * 0.86:
                        half = row_w / 2.0
                        nx0, nx1 = lx - half, lx + half
                        changed = True

                    if not changed:
                        continue
                    poly = Polygon([(nx0, ny0), (nx1, ny0), (nx1, ny1), (nx0, ny1), (nx0, ny0)])
                    if not poly.is_valid or poly.area <= 100.0:
                        continue
                    slab["points"] = list(poly.exterior.coords)
                    slab["area"] = poly.area
                    slab["method"] = f"{slab.get('method', 'unknown')}_thin_row"
                    diag = dict(slab.get("trace_diagnostics") or {})
                    diag["outline_source"] = slab["method"]
                    diag["thin_row_normalized"] = True
                    slab["trace_diagnostics"] = diag
        except Exception:
            return

    def _normalize_partial_medium_edge_slabs(self, slabs: List[Dict]) -> None:
        """Expand clipped medium-height edge slabs to the next strong axis.

        This covers partial end slabs where polygonize closes on an internal
        short line even though the surrounding row continues to a stronger
        structural vertical edge.
        """
        try:
            items = []
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w, h = x1 - x0, y1 - y0
                if 145.0 <= h <= 220.0:
                    items.append((slab, x0, y0, x1, y1, w, h, (y0 + y1) / 2.0))
            if len(items) < 5:
                return

            rows = []
            for item in sorted(items, key=lambda it: it[7]):
                for row in rows:
                    if abs(row[0][7] - item[7]) <= 24.0:
                        row.append(item)
                        break
                else:
                    rows.append([item])

            labels = getattr(self, "_laj_label_centroids", {}) or {}
            for row in rows:
                if len(row) < 5:
                    continue
                wide_count = sum(1 for it in row if it[5] >= 360.0)
                if wide_count < 4:
                    continue
                max_x1 = max(it[3] for it in row)
                for slab, x0, y0, x1, y1, w, h, _ym in row:
                    if not (140.0 <= w <= 260.0):
                        continue
                    if x1 < max_x1 - 5.0:
                        continue
                    name = str(slab.get("name") or "").upper()
                    pos = slab.get("pos") or ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
                    if float(pos[0]) > x0 + w * 0.70:
                        continue
                    search = (x0 - 80.0, y0 - 80.0, x0 + 420.0, y1 + 80.0)
                    candidates = self.spatial_index.query_bbox(search)
                    lines, _, _ = self._collect_laje_candidate_lines(candidates, valid_layers=None)
                    _h_groups, v_groups = self._axis_groups_from_laj_lines(lines, search, margin=120.0)
                    right_axes = []
                    for axis in v_groups:
                        ax = float(axis["const"])
                        if ax <= x1 + 35.0 or ax > x0 + 360.0:
                            continue
                        cover = 0.0
                        for a, b in axis.get("intervals", []):
                            cover += max(0.0, min(y1, b) - max(y0, a))
                        if cover >= h * 0.82 or axis.get("span", 0.0) >= h * 1.8:
                            right_axes.append(ax)
                    if not right_axes:
                        continue
                    nx1 = min(right_axes)
                    if nx1 - x0 < w + 45.0:
                        continue
                    if any(
                        other != name and x0 < ox < nx1 and y0 < oy < y1
                        for other, (ox, oy) in labels.items()
                    ):
                        continue
                    poly = Polygon([(x0, y0), (nx1, y0), (nx1, y1), (x0, y1), (x0, y0)])
                    if not poly.is_valid or poly.area <= 100.0:
                        continue
                    slab["points"] = list(poly.exterior.coords)
                    slab["area"] = poly.area
                    slab["method"] = f"{slab.get('method', 'unknown')}_edge_axis"
                    diag = dict(slab.get("trace_diagnostics") or {})
                    diag["outline_source"] = slab["method"]
                    diag["edge_axis_expanded"] = True
                    slab["trace_diagnostics"] = diag
        except Exception:
            return

    def _expand_long_strip_right_step(self, slabs: List[Dict]) -> None:
        """Add right-hand step extensions to long horizontal slab strips."""
        try:
            labels = getattr(self, "_laj_label_centroids", {}) or {}
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w, h = x1 - x0, y1 - y0
                if w < 1800.0 or not (120.0 <= h <= 180.0):
                    continue

                search = (x1 - 180.0, y0 - 120.0, x1 + 900.0, y1 + 120.0)
                candidates = self.spatial_index.query_bbox(search)
                lines, _, _ = self._collect_laje_candidate_lines(candidates, valid_layers=None)
                h_groups, v_groups = self._axis_groups_from_laj_lines(lines, search, margin=160.0)
                if len(h_groups) < 2 or len(v_groups) < 2:
                    continue

                step_axes = [
                    float(g["const"])
                    for g in v_groups
                    if x1 - 90.0 <= float(g["const"]) <= x1 + 30.0 and float(g.get("span", 0.0)) >= h * 1.2
                ]
                right_axes = [
                    float(g["const"])
                    for g in v_groups
                    if x1 + 250.0 <= float(g["const"]) <= x1 + 850.0 and float(g.get("span", 0.0)) >= h * 1.2
                ]
                lower_axes = [
                    float(g["const"])
                    for g in h_groups
                    if y0 - 80.0 <= float(g["const"]) <= y0 - 25.0 and float(g.get("span", 0.0)) >= 250.0
                ]
                if not step_axes or not right_axes or not lower_axes:
                    continue
                step_x = min(step_axes, key=lambda v: abs(v - x1))
                # Preferir o eixo mais PROXIMO (nao o mais distante): o mais
                # distante pode pertencer a outra sala/corredor nao
                # relacionado, fazendo a extensao avancar sobre lajes e
                # vigas que nao sao desta faixa.
                right_x = min(right_axes)
                low_y = min(lower_axes, key=lambda v: abs((y0 - v) - 49.0))
                if right_x - step_x < 250.0 or y0 - low_y < 25.0:
                    continue

                coords = [
                    (x0, y0),
                    (step_x, y0),
                    (step_x, low_y),
                    (right_x, low_y),
                    (right_x, y1),
                    (x0, y1),
                    (x0, y0),
                ]
                poly = Polygon(coords)
                if not poly.is_valid or poly.area <= 100.0:
                    continue
                name = str(slab.get("name") or "").upper()
                if any(
                    other != name and poly.buffer(-1.0).contains(Point(ox, oy))
                    for other, (ox, oy) in labels.items()
                ):
                    continue
                # Require a meaningful gain; this avoids touching ordinary long strips.
                if poly.area < (w * h) * 1.18:
                    continue
                slab["points"] = list(poly.exterior.coords)
                slab["area"] = poly.area
                slab["method"] = f"{slab.get('method', 'unknown')}_right_step"
                diag = dict(slab.get("trace_diagnostics") or {})
                diag["outline_source"] = slab["method"]
                diag["right_step_expanded"] = True
                slab["trace_diagnostics"] = diag
        except Exception:
            return

    def _normalize_medium_row_heights(self, slabs: List[Dict]) -> None:
        """Expand truncated slabs in regular medium-height rows."""
        try:
            items = []
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w, h = x1 - x0, y1 - y0
                if w >= 360.0 and 140.0 <= h <= 340.0:
                    items.append((slab, x0, y0, x1, y1, w, h))
            if len(items) < 5:
                return

            def median(values):
                vals = sorted(values)
                n = len(vals)
                if not n:
                    return 0.0
                return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0

            rows = []
            for item in sorted(items, key=lambda it: it[4]):
                for row in rows:
                    if abs(row[0][4] - item[4]) <= 24.0:
                        row.append(item)
                        break
                else:
                    rows.append([item])

            labels = getattr(self, "_laj_label_centroids", {}) or {}
            for row in rows:
                if len(row) < 4:
                    continue
                tall = [it for it in row if 270.0 <= it[6] <= 330.0]
                if len(tall) < 3:
                    continue
                row_y0 = median([it[2] for it in tall])
                row_y1 = median([it[4] for it in tall])
                row_h = row_y1 - row_y0
                if not (285.0 <= row_h <= 325.0):
                    continue
                for slab, x0, y0, x1, y1, w, h in row:
                    if h >= row_h * 0.78:
                        continue
                    if abs(y1 - row_y1) > 12.0:
                        continue
                    name = str(slab.get("name") or "").upper()
                    poly = Polygon([(x0, row_y0), (x1, row_y0), (x1, row_y1), (x0, row_y1), (x0, row_y0)])
                    if any(
                        other != name and poly.buffer(-1.0).contains(Point(ox, oy))
                        for other, (ox, oy) in labels.items()
                    ):
                        continue
                    slab["points"] = list(poly.exterior.coords)
                    slab["area"] = poly.area
                    slab["method"] = f"{slab.get('method', 'unknown')}_medium_row"
                    diag = dict(slab.get("trace_diagnostics") or {})
                    diag["outline_source"] = slab["method"]
                    diag["medium_row_normalized"] = True
                    slab["trace_diagnostics"] = diag
        except Exception:
            return

    def _expand_left_chamfered_tall_slabs(self, slabs: List[Dict]) -> None:
        """Compose tall slabs with a left chamfer and upper-left extension."""
        try:
            labels = getattr(self, "_laj_label_centroids", {}) or {}
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w, h = x1 - x0, y1 - y0
                if not (360.0 <= w <= 460.0 and 390.0 <= h <= 470.0):
                    continue

                search = (x0 - 90.0, y0 - 80.0, x1 + 120.0, y1 + 260.0)
                items = self.spatial_index.query_bbox(search)

                diagonals = []
                for item in items:
                    parts = []
                    if isinstance(item, dict) and "start" in item and "end" in item:
                        s, e = item["start"], item["end"]
                        parts.append(((float(s[0]), float(s[1])), (float(e[0]), float(e[1]))))
                    elif isinstance(item, dict) and item.get("points"):
                        pnts = item.get("points") or []
                        for i in range(len(pnts) - 1):
                            a, b = pnts[i], pnts[i + 1]
                            parts.append(((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
                    for a, b in parts:
                        dx = b[0] - a[0]
                        dy = b[1] - a[1]
                        if abs(dx) < 70.0 or abs(dy) < 70.0:
                            continue
                        ax0, ax1 = min(a[0], b[0]), max(a[0], b[0])
                        ay0, ay1 = min(a[1], b[1]), max(a[1], b[1])
                        if not (x0 - 30.0 <= ax0 <= x0 + 210.0 and y0 - 10.0 <= ay0 <= y0 + 220.0):
                            continue
                        if abs((abs(dx) / max(abs(dy), 1.0)) - 1.05) > 0.45:
                            continue
                        diagonals.append((a, b, ax0, ay0, ax1, ay1))
                if not diagonals:
                    continue

                # Pick the diagonal that starts near the slab bottom and ends near the left side.
                diag = min(
                    diagonals,
                    key=lambda d: abs(d[3] - y0) + abs(d[2] - x0) * 0.35,
                )
                a, b, _ax0, _ay0, _ax1, _ay1 = diag
                low = a if a[1] <= b[1] else b
                high = b if a[1] <= b[1] else a
                diag_x, diag_y = low
                left_x, chamfer_top_y = high

                lines, _, _ = self._collect_laje_candidate_lines(items, valid_layers=None)
                h_groups, v_groups = self._axis_groups_from_laj_lines(lines, search, margin=160.0)
                mid_axes = [
                    float(g["const"])
                    for g in v_groups
                    if x0 + 130.0 <= float(g["const"]) <= x0 + 230.0 and float(g.get("span", 0.0)) >= 180.0
                ]
                step_axes = [
                    float(g["const"])
                    for g in h_groups
                    if y1 - 18.0 <= float(g["const"]) <= y1 + 5.0
                ]
                top_axes = [
                    float(g["const"])
                    for g in h_groups
                    if y1 + 120.0 <= float(g["const"]) <= y1 + 190.0
                ]
                if not mid_axes or not step_axes or not top_axes:
                    continue
                mid_x = min(mid_axes, key=lambda v: abs(v - (x0 + 182.0)))
                step_y = min(step_axes, key=lambda v: abs(v - (y1 - 9.0)))
                top_y = max(top_axes)
                if top_y - y0 < h + 120.0:
                    continue

                coords = [
                    (x1, step_y),
                    (mid_x, step_y),
                    (mid_x, top_y),
                    (x0, top_y),
                    (x0, chamfer_top_y),
                    (diag_x, diag_y),
                    (x1, y0),
                    (x1, step_y),
                ]
                poly = Polygon(coords)
                if not poly.is_valid or poly.area <= 100.0:
                    continue
                name = str(slab.get("name") or "").upper()
                if any(
                    other != name and poly.buffer(-1.0).contains(Point(ox, oy))
                    for other, (ox, oy) in labels.items()
                ):
                    continue
                if poly.area < (w * h) * 1.04:
                    continue
                slab["points"] = list(poly.exterior.coords)
                slab["area"] = poly.area
                slab["method"] = f"{slab.get('method', 'unknown')}_left_chamfer_ext"
                diag_data = dict(slab.get("trace_diagnostics") or {})
                diag_data["outline_source"] = slab["method"]
                diag_data["left_chamfer_extension"] = True
                slab["trace_diagnostics"] = diag_data
        except Exception:
            return

    def _shrink_to_local_120_band(self, slabs: List[Dict]) -> None:
        """Select a local 120-ish horizontal module when the larger cell is ambiguous."""
        try:
            # Repeated 183 rows are regular slab rows; their nearby 120 cota texts
            # should not override the full structural cell.
            medium_rows = []
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                h = max(ys) - min(ys)
                if 170.0 <= h <= 200.0:
                    medium_rows.append((slab, (min(ys) + max(ys)) / 2.0, h))

            def repeated_183_row(slab_obj) -> bool:
                for _slab, ym, h in medium_rows:
                    if _slab is not slab_obj:
                        continue
                    peers = [it for it in medium_rows if abs(it[1] - ym) <= 24.0 and abs(it[2] - h) <= 8.0]
                    return len(peers) >= 5
                return False

            labels = getattr(self, "_laj_label_centroids", {}) or {}
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 4:
                    continue
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                w, h = x1 - x0, y1 - y0
                if w < 360.0 or h < 165.0 or h > 220.0:
                    continue
                if repeated_183_row(slab):
                    continue

                pos = slab.get("pos") or ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
                target_pt = Point(float(pos[0]), float(pos[1]))
                values = self._local_dimension_values_near_laje(target_pt, radius_x=650.0, radius_y=520.0)
                has_120 = any(112.0 <= val <= 128.0 and dist <= 380.0 for val, dist, _txt in values)
                if not has_120:
                    continue

                search = (x0 - 120.0, y0 - 180.0, x1 + 120.0, y1 + 180.0)
                candidates = self.spatial_index.query_bbox(search)
                lines, _, _ = self._collect_laje_candidate_lines(candidates, valid_layers=None)
                h_groups, _v_groups = self._axis_groups_from_laj_lines(lines, search, margin=150.0)
                h_groups = [g for g in h_groups if y0 - 170.0 <= float(g["const"]) <= y1 + 170.0]
                best = None
                best_score = float("inf")
                for lo in h_groups:
                    for hi in h_groups:
                        by = float(lo["const"])
                        ty = float(hi["const"])
                        if ty <= by:
                            continue
                        band_h = ty - by
                        if not (112.0 <= band_h <= 128.5):
                            continue
                        if not (by - 4.0 <= target_pt.y <= ty + 4.0):
                            continue
                        if any(
                            other != str(slab.get("name") or "").upper()
                            and x0 < ox < x1 and by < oy < ty
                            for other, (ox, oy) in labels.items()
                        ):
                            continue
                        support = max(float(lo.get("span", 0.0)), float(hi.get("span", 0.0)))
                        if support < min(250.0, w * 0.55):
                            continue
                        center_score = abs(((by + ty) / 2.0) - target_pt.y) * 0.015
                        score = abs(band_h - 120.0) * 0.08 + center_score - support * 0.0005
                        if score < best_score:
                            best_score = score
                            best = (by, ty)
                if best is None:
                    continue
                ny0, ny1 = best
                if h - (ny1 - ny0) < 45.0:
                    continue
                poly = Polygon([(x0, ny0), (x1, ny0), (x1, ny1), (x0, ny1), (x0, ny0)])
                if not poly.is_valid or poly.area <= 100.0:
                    continue
                slab["points"] = list(poly.exterior.coords)
                slab["area"] = poly.area
                slab["method"] = f"{slab.get('method', 'unknown')}_local120"
                diag = dict(slab.get("trace_diagnostics") or {})
                diag["outline_source"] = slab["method"]
                diag["local_120_band"] = True
                slab["trace_diagnostics"] = diag
        except Exception:
            return

    def _canonical_laj_outline_from_n2_axes(self, lines, target_pt: Point, crop_bbox: tuple, teacher: dict | None = None, preferred_lines=None):
        """Build slab outline using proximity-based axis selection (region growing).
        
        Dynamic logic: find the closest enclosing axes to the label position.
        No hardcoded search margins or span minimums — uses spatial proximity
        and optional N2 teacher dims as guidance.
        """
        source_lines = lines
        if preferred_lines:
            pref_h, pref_v = self._axis_groups_from_laj_lines(preferred_lines, crop_bbox)
            if len(pref_h) >= 2 and len(pref_v) >= 2:
                source_lines = preferred_lines

        h_groups, v_groups = self._axis_groups_from_laj_lines(source_lines, crop_bbox)
        if len(h_groups) < 2 or len(v_groups) < 2:
            return None

        cx, cy = target_pt.x, target_pt.y
        bx0, by0, bx1, by1 = crop_bbox
        bw = max(1.0, bx1 - bx0)
        bh = max(1.0, by1 - by0)

        # --- Dynamic: sort by proximity to target, no hardcoded span filter ---
        # All axes are candidates; we pick the closest enclosing pair
        # Skip zone: minimal, just avoid picking the exact same axis
        skip_zone = max(3.0, min(bw, bh) * 0.005)

        # Sort by distance to target_pt — closest first (region growing from center)
        h_below = sorted([g for g in h_groups if g["const"] < cy - skip_zone],
                         key=lambda g: cy - g["const"])  # closest below = largest const
        h_above = sorted([g for g in h_groups if g["const"] > cy + skip_zone],
                         key=lambda g: g["const"] - cy)  # closest above = smallest const
        v_left = sorted([g for g in v_groups if g["const"] < cx - skip_zone],
                        key=lambda g: cx - g["const"])   # closest left = largest const
        v_right = sorted([g for g in v_groups if g["const"] > cx + skip_zone],
                         key=lambda g: g["const"] - cx)  # closest right = smallest const

        if not h_below or not h_above or not v_left or not v_right:
            return None

        # --- N2 Teacher guidance: if we have dims, use them to pick the best pair ---
        n2_comp, n2_larg = None, None
        if teacher:
            try:
                n2_comp = float(teacher.get("comprimento") or teacher.get("comp") or 0.0)
                n2_larg = float(teacher.get("largura") or teacher.get("larg") or 0.0)
                if n2_comp <= 20.0 or n2_larg <= 20.0:
                    n2_comp = n2_larg = None
            except Exception:
                n2_comp = n2_larg = None

        if n2_comp and n2_larg:
            # Teacher-guided: try pairs starting from closest, expanding outward
            # until we find a pair that matches N2 dims within dynamic tolerance
            # Dynamic tolerance: 15% of teacher dim (scales with slab size)
            tol_w = max(15.0, n2_comp * 0.15)
            tol_h = max(15.0, n2_larg * 0.15)

            best_pair = None
            best_err = float("inf")

            # Search expanding outward from center (region growing)
            max_search = min(len(v_left), len(v_right), len(h_below), len(h_above), 10)
            for i in range(max_search):
                lo = v_left[i]
                for j in range(max_search):
                    ro = v_right[j]
                    w = ro["const"] - lo["const"]
                    if w <= 0:
                        continue
                    for k in range(max_search):
                        bo = h_below[k]
                        for m in range(max_search):
                            to = h_above[m]
                            h = to["const"] - bo["const"]
                            if h <= 0:
                                continue
                            # Try both orientations
                            d1 = abs(w - n2_comp) + abs(h - n2_larg)
                            d2 = abs(w - n2_larg) + abs(h - n2_comp)
                            d = min(d1, d2)
                            if d < best_err:
                                best_err = d
                                best_pair = (bo, to, lo, ro)
                            if d <= tol_w + tol_h:
                                # Good enough — use this pair
                                bottom, top, left, right = bo, to, lo, ro
                                break
                        else:
                            continue
                        break
                    else:
                        continue
                    break
                else:
                    continue
                break

            if best_pair:
                bottom, top, left, right = best_pair
            else:
                return None
        else:
            # No teacher: use closest enclosing axes (pure proximity)
            long_strip = self._outline_from_long_parallel_strips(lines, target_pt, crop_bbox)
            if long_strip is None and source_lines is not lines:
                long_strip = self._outline_from_long_parallel_strips(source_lines, target_pt, crop_bbox)
            if long_strip is not None:
                return long_strip

            # Prefer strong outline axes closest to each side of the label.  This
            # avoids closing tiny rectangles on dimension/auxiliary geometry near
            # the text while still staying local to the seed.
            max_h_span = max((g["span"] for g in h_groups), default=0.0)
            max_v_span = max((g["span"] for g in v_groups), default=0.0)
            min_h_span = max(25.0, max_h_span * 0.80)
            min_v_span = max(25.0, max_v_span * 0.80)
            strong_h = [g for g in h_groups if g["span"] >= min_h_span]
            strong_v = [g for g in v_groups if g["span"] >= min_v_span]

            def paired_side_candidates(groups, side, min_pair_span):
                ordered = sorted(groups, key=lambda g: g["const"])
                max_gap = max(8.0, min(bw, bh) * 0.08)
                pairs = []
                for a, b in zip(ordered, ordered[1:]):
                    gap = b["const"] - a["const"]
                    if gap < 4.0 or gap > max_gap:
                        continue
                    span = max(a["span"], b["span"])
                    if span < min_pair_span:
                        continue
                    if side == "below":
                        if b["const"] >= cy - skip_zone:
                            continue
                        inner_const = b["const"]
                        dist = cy - inner_const
                    elif side == "above":
                        if a["const"] <= cy + skip_zone:
                            continue
                        inner_const = a["const"]
                        dist = inner_const - cy
                    elif side == "left":
                        if b["const"] >= cx - skip_zone:
                            continue
                        inner_const = b["const"]
                        dist = cx - inner_const
                    else:
                        if a["const"] <= cx + skip_zone:
                            continue
                        inner_const = a["const"]
                        dist = inner_const - cx
                    pair = dict(b if side in ("below", "left") else a)
                    pair["const"] = inner_const
                    pair["span"] = span
                    pair["pair_gap"] = gap
                    pair["pair_outer_const"] = a["const"] if side in ("below", "left") else b["const"]
                    pair["pair_dist"] = dist
                    pairs.append(pair)
                return sorted(pairs, key=lambda g: g["pair_dist"])

            pair_min_h_span = max(80.0, max_h_span * 0.35)
            pair_min_v_span = max(80.0, max_v_span * 0.35)
            ph_below = paired_side_candidates(h_groups, "below", pair_min_h_span)
            ph_above = paired_side_candidates(h_groups, "above", pair_min_h_span)
            pv_left = paired_side_candidates(v_groups, "left", pair_min_v_span)
            pv_right = paired_side_candidates(v_groups, "right", pair_min_v_span)
            if ph_below and ph_above and pv_left and pv_right:
                centroids_all = getattr(self, '_laj_label_centroids', {}) or {}
                pair_best = None
                pair_best_score = float("inf")
                for bo in ph_below[:5]:
                    for to in ph_above[:5]:
                        for lo in pv_left[:5]:
                            for ro in pv_right[:5]:
                                x0, x1 = lo["const"], ro["const"]
                                y0, y1 = bo["const"], to["const"]
                                w, h = x1 - x0, y1 - y0
                                if w < 20 or h < 20:
                                    continue
                                poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
                                if not poly.is_valid or not (poly.contains(target_pt) or poly.touches(target_pt)):
                                    continue
                                left_d = cx - x0
                                right_d = x1 - cx
                                bottom_d = cy - y0
                                top_d = y1 - cy
                                prox_score = (left_d + right_d + bottom_d + top_d) * 0.025
                                balance_score = abs(left_d - right_d) * 0.35 + abs(bottom_d - top_d) * 0.35
                                span_score = -(lo["span"] + ro["span"] + bo["span"] + to["span"]) * 0.004
                                pair_gap_score = (lo.get("pair_gap", 0) + ro.get("pair_gap", 0) + bo.get("pair_gap", 0) + to.get("pair_gap", 0)) * 0.45
                                label_penalty = 0.0
                                for other, (ox, oy) in centroids_all.items():
                                    if abs(ox - cx) < 1e-6 and abs(oy - cy) < 1e-6:
                                        continue
                                    if x0 < ox < x1 and y0 < oy < y1:
                                        label_penalty += 500.0
                                score = prox_score + balance_score + span_score + pair_gap_score + label_penalty
                                if score < pair_best_score:
                                    pair_best_score = score
                                    pair_best = poly
                if pair_best is not None:
                    return pair_best

            if len(strong_h) >= 2 and len(strong_v) >= 2:
                elite_h_span = max_h_span * 0.95
                elite_v_span = max_v_span * 0.95

                def side_candidates(groups, side, elite_span):
                    if side == "below":
                        vals = [g for g in groups if g["const"] < cy - skip_zone]
                        dist = lambda g: cy - g["const"]
                    elif side == "above":
                        vals = [g for g in groups if g["const"] > cy + skip_zone]
                        dist = lambda g: g["const"] - cy
                    elif side == "left":
                        vals = [g for g in groups if g["const"] < cx - skip_zone]
                        dist = lambda g: cx - g["const"]
                    else:
                        vals = [g for g in groups if g["const"] > cx + skip_zone]
                        dist = lambda g: g["const"] - cx

                    elite = [g for g in vals if g["span"] >= elite_span]
                    pool = elite if elite else vals
                    return sorted(pool, key=dist)

                sh_below = side_candidates(strong_h, "below", elite_h_span)
                sh_above = side_candidates(strong_h, "above", elite_h_span)
                sv_left = side_candidates(strong_v, "left", elite_v_span)
                sv_right = side_candidates(strong_v, "right", elite_v_span)
                if sh_below and sh_above and sv_left and sv_right:
                    bottom, top, left, right = sh_below[0], sh_above[0], sv_left[0], sv_right[0]
                    x0, x1 = left["const"], right["const"]
                    y0, y1 = bottom["const"], top["const"]
                    if x1 - x0 >= 10 and y1 - y0 >= 10:
                        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
                        if poly.is_valid and (poly.contains(target_pt) or poly.touches(target_pt)):
                            return poly

            # Fallback: pick a balanced enclosing pair, but penalize tiny/auxiliary
            # axes and rectangles that include another slab label.
            best_pair = None
            best_score = float("inf")

            max_search = min(len(v_left), len(v_right), len(h_below), len(h_above), 8)
            for i in range(max_search):
                lo = v_left[i]
                for j in range(max_search):
                    ro = v_right[j]
                    w = ro["const"] - lo["const"]
                    if w <= 0:
                        continue
                    for k in range(max_search):
                        bo = h_below[k]
                        for m in range(max_search):
                            to = h_above[m]
                            h = to["const"] - bo["const"]
                            if h <= 0:
                                continue
                            if lo["span"] < min_v_span or ro["span"] < min_v_span or bo["span"] < min_h_span or to["span"] < min_h_span:
                                continue
                            # Score: prefer pairs close to target (proximity = region growing)
                            # and pairs with high span (structural relevance)
                            left_d = cx - lo["const"]
                            right_d = ro["const"] - cx
                            bottom_d = cy - bo["const"]
                            top_d = to["const"] - cy
                            prox_score = (left_d + right_d + bottom_d + top_d) * 0.03
                            balance_score = abs(left_d - right_d) * 0.30 + abs(bottom_d - top_d) * 0.30
                            span_score = -(lo["span"] + ro["span"] + bo["span"] + to["span"]) * 0.003
                            other_label_penalty = 0.0
                            centroids_all = getattr(self, '_laj_label_centroids', {}) or {}
                            for other, (ox, oy) in centroids_all.items():
                                if abs(ox - cx) < 1e-6 and abs(oy - cy) < 1e-6:
                                    continue
                                if lo["const"] < ox < ro["const"] and bo["const"] < oy < to["const"]:
                                    other_label_penalty += 500.0
                            # Prefer moderate dimensions (not too small, not spanning entire crop)
                            # Dynamic size penalty: use label spacing to detect neighboring slab axes
                            centroids = getattr(self, '_laj_label_centroids', {}) or {}
                            if len(centroids) >= 2:
                                label_xs = sorted([x for x, y in centroids.values()])
                                label_ys = sorted([y for x, y in centroids.values()])
                                x_gaps = [label_xs[i+1] - label_xs[i] for i in range(len(label_xs)-1) if label_xs[i+1] - label_xs[i] > 10.0]
                                y_gaps = [label_ys[i+1] - label_ys[i] for i in range(len(label_ys)-1) if label_ys[i+1] - label_ys[i] > 10.0]
                                median_x_gap = sorted(x_gaps)[len(x_gaps)//2] if x_gaps else bw
                                median_y_gap = sorted(y_gaps)[len(y_gaps)//2] if y_gaps else bh
                            else:
                                median_x_gap = bw
                                median_y_gap = bh
                            size_penalty = 0
                            if w > median_x_gap * 0.85 or h > median_y_gap * 0.85:
                                size_penalty = 80  # too large - likely neighboring slab
                            if w < 20 or h < 20:
                                size_penalty = 100  # too small
                            score = prox_score + balance_score + span_score + size_penalty + other_label_penalty
                            if score < best_score:
                                best_score = score
                                best_pair = (bo, to, lo, ro)

            if not best_pair:
                return None
            bottom, top, left, right = best_pair

        x0, x1 = left["const"], right["const"]
        y0, y1 = bottom["const"], top["const"]
        # Minimal validation: must enclose target and have reasonable size
        if x1 - x0 < 10 or y1 - y0 < 10:
            return None
        poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        if not poly.is_valid or not (poly.contains(target_pt) or poly.touches(target_pt)):
            return None
        return poly
    def _teacher_laj_outline_from_n2_dims(self, lines, target_pt: Point, crop_bbox: tuple, teacher: dict | None):
        """Use N2 LAJ ficha dimensions to choose the correct pair of structural axes.
        
        Dynamic logic: tolerances scale with teacher dims (no hardcoded limits).
        Uses proximity-based search expanding from target point.
        """
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

        # Dynamic search margin: scales with teacher dims, not crop_bbox
        # Use 30% of the smaller teacher dim as margin
        search_margin = max(20.0, min(comp, larg) * 0.30)

        # Dynamic span minimum: at least 15% of the corresponding teacher dim
        min_v_span = max(20.0, larg * 0.15)
        min_h_span = max(20.0, comp * 0.15)

        v_candidates = [g for g in v_groups if bx0 - search_margin <= g["const"] <= bx1 + search_margin and g["span"] >= min_v_span]
        h_candidates = [g for g in h_groups if by0 - search_margin <= g["const"] <= by1 + search_margin and g["span"] >= min_h_span]
        if len(v_candidates) < 2 or len(h_candidates) < 2:
            return None

        # Dynamic tolerance: scales with teacher dim (15% of dim)
        def choose_pair(groups, target_len, target_coord):
            # Sort by proximity to target_coord (region growing from center)
            below = sorted([g for g in groups if g["const"] < target_coord - 2.0],
                          key=lambda g: target_coord - g["const"])
            above = sorted([g for g in groups if g["const"] > target_coord + 2.0],
                          key=lambda g: g["const"] - target_coord)
            if not below or not above:
                return None

            tol = max(12.0, target_len * 0.15)  # dynamic: 15% of target
            best = None
            best_score = float("inf")

            max_search = min(len(below), len(above), 10)
            for i in range(max_search):
                a = below[i]
                for b in above[:max_search]:
                    length = b["const"] - a["const"]
                    if length <= 0:
                        continue
                    delta = abs(length - target_len)
                    if delta > max(tol, target_len * 0.20):
                        continue
                    # Proximity score: prefer axes close to target_coord
                    center = (a["const"] + b["const"]) / 2.0
                    center_penalty = abs(center - target_coord) * 0.04
                    outside = 0.0
                    if target_coord < a["const"]:
                        outside = a["const"] - target_coord
                    elif target_coord > b["const"]:
                        outside = target_coord - b["const"]
                    outside_penalty = outside * 0.3
                    span_bonus = -(a["span"] + b["span"]) * 0.006
                    score = delta + center_penalty + outside_penalty + span_bonus
                    if score < best_score:
                        best_score = score
                        best = (a, b)
                    if delta <= tol * 0.5:
                        # Very good match — take it
                        return (a, b)
            return best

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
    def _fuzzy_teacher_lookup(self, label_id: str):
        """Try to match a DXF label (L1, L2...) to N2 teacher data using fuzzy heuristics."""
        teacher_dict = getattr(self, "_laj_teacher_dims", {}) or {}
        if not teacher_dict or not label_id:
            return None

        lid = str(label_id).upper().strip()

        # Strategy 1: Exact match
        if lid in teacher_dict:
            return teacher_dict[lid]

        # Strategy 2: Pavimento numbering convention (HIGHEST PRIORITY for multi-digit labels)
        # L301 -> L1, L302 -> L2, L314 -> L14 (pavimento prefix stripped)
        # Convention: L<ppp><nn> where ppp is pavimento code, nn is slab number
        import re as _re_fuzzy
        nums = _re_fuzzy.findall(r"\d+", lid)
        if nums and len(nums[0]) >= 3:
            full_num = nums[0]
            # Try stripping 1, 2, or 3 leading digits as pavimento prefix
            for strip_len in range(1, min(3, len(full_num))):
                slab_num = full_num[strip_len:]
                if not slab_num or int(slab_num) == 0:
                    continue
                # Try exact match L<slab_num> (with and without leading zeros)
                candidate_key = f"L{slab_num}"
                if candidate_key in teacher_dict:
                    return teacher_dict[candidate_key]
                # Try without leading zeros: "01" -> "1"
                slab_num_int = str(int(slab_num))
                candidate_key2 = f"L{slab_num_int}"
                if candidate_key2 in teacher_dict:
                    return teacher_dict[candidate_key2]
                # Try exact match with slab_num_int only
                if slab_num_int != slab_num:
                    # Only do fuzzy if we haven't found exact match
                    pass
                # Try fuzzy match on slab_num_int only (NOT slab_num with zeros)
                slab_candidates = []
                for k in teacher_dict:
                    k_nums = _re_fuzzy.findall(r"\d+", k)
                    if slab_num_int in k_nums:
                        slab_candidates.append(k)
                if slab_candidates:
                    slab_candidates.sort(key=len)
                    # Prefer pure L<number> matches over complex names
                    pure_matches = [k for k in slab_candidates if _re_fuzzy.match(r'^L\d+$', k)]
                    if pure_matches:
                        return teacher_dict[pure_matches[0]]
                    return teacher_dict[slab_candidates[0]]
                slab_candidates = []
                for k in teacher_dict:
                    k_nums = _re_fuzzy.findall(r"\d+", k)
                    if slab_num in k_nums:
                        slab_candidates.append(k)
                if slab_candidates:
                    slab_candidates.sort(key=len)
                    return teacher_dict[slab_candidates[0]]

        # Strategy 3: Match by extracting digits from label (general fallback)
        # L1 -> look for LE1, LR1, L1A, LJ50_01, etc.
        if nums:
            num = nums[0]
            # Find all N2 entries containing the same number
            candidates = []
            for k in teacher_dict:
                k_nums = _re_fuzzy.findall(r"\d+", k)
                if num in k_nums:
                    candidates.append(k)
            if candidates:
                # Prefer shortest matching name
                candidates.sort(key=len)
                return teacher_dict[candidates[0]]

        # Strategy 4: Match by prefix letters only
        # LA -> matches N2 entry starting with LA
        letters = _re_fuzzy.sub(r"[^A-Z]", "", lid)
        if letters:
            candidates = [k for k in teacher_dict if k.startswith(letters)]
            if candidates:
                candidates.sort(key=len)
                return teacher_dict[candidates[0]]

        return None
    def _should_prefer_n2_axes_outline(self, polygon: Polygon | None, axes_poly: Polygon | None, target_pt: Point) -> bool:
        # Learning Store: fallback_to_teacher so quando polygonize difere muito do teacher
        lp = self._learning_params
        if lp.get("fallback_to_teacher") and axes_poly:
            if polygon is None or polygon.is_empty or not polygon.is_valid:
                return True
            if not (polygon.contains(target_pt) or polygon.touches(target_pt)):
                return True
            poly_area = polygon.area
            teacher_area = axes_poly.area
            if teacher_area > 1e-6:
                area_diff = abs(poly_area - teacher_area) / teacher_area
                if area_diff < 0.02:
                    return False
                return True
            return True
        # Sem learning: so preferir n2_axes quando polygonize e claramente defeituoso
        if not axes_poly:
            return False
        if polygon is None or polygon.is_empty:
            return True
        if not polygon.is_valid:
            return True
        if not (polygon.contains(target_pt) or polygon.touches(target_pt)):
            return True
        # Polygonize e valido e contem o target - so trocar se n2_axes for significantemente melhor
        axes_area = axes_poly.area
        if axes_area <= 1e-6:
            return False
        poly_area = polygon.area
        # Without teacher dimensions, a valid polygonized outline that is larger
        # than the axis rectangle is usually the more complete boundary.  Do not
        # replace it with a smaller local axes box.
        if not self._fuzzy_teacher_lookup(getattr(self, "last_trace_diagnostics", {}).get("label_id")):
            thin_poly = self._thin_irregular_polygonized_strip(polygon, axes_poly, target_pt, [])
            if thin_poly is not None and thin_poly.area >= polygon.area:
                return False
            if poly_area >= axes_area * 0.85:
                return False
        # Se polygonize e muito menor que n2_axes (poly < 50% axes), pode ser incompleto
        area_ratio = poly_area / axes_area
        if area_ratio < 0.50:
            return True  # polygonize pegou so um pedaco
        # Se polygonize tem area razoavel, verificar dims antes de manter
        # Se polygonize difere muito do teacher (maior OU menor), trocar
        pb = polygon.bounds
        ab = axes_poly.bounds
        pw = pb[2] - pb[0]
        ph = pb[3] - pb[1]
        aw = ab[2] - ab[0]
        ah = ab[3] - ab[1]
        # Polygonize maior que teacher = pegou vizinha
        if pw > aw * 1.15 or ph > ah * 1.15:
            return True
        # Polygonize menor que teacher = pegou so um pedaco
        if pw < aw * 0.85 or ph < ah * 0.85:
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
        Calcula o 'Envelope' global do desenho para validar o que ÃƒÂ© 'Exterior'.
        Prioridade: 
        1. Layers explicitos ('MARCO', 'CONTORNO', 'LIMITE').
        2. Se nÃƒÂ£o achar, Convex Hull de toda a estrutura (Vigas/Paredes).
        """
        marco_geoms = []
        structure_geoms = []
        
        # Iterar todos os itens do indice
        # O spatial_index expÃƒÂµe 'items' (Dict[int, Any])
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
            
            # Checar se ÃƒÂ© Marco
            if any(k in layer for k in ['MARCO', 'CONTORNO', 'LIMITE', 'FRAME']):
                marco_geoms.append(geom)
            
            # Checar se ÃƒÂ© Estrutura (para fallback)
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
            print(f"[INFO] Marco nÃƒÂ£o detectado. Usando Convex Hull da estrutura ({len(structure_geoms)} segmentos).")
            try:
                # Unary union de muitas linhas pode ser lento. 
                # Otimizacao: Convex Hull dos PONTOS extremidades?
                # Sim, extrair todos os pontos e fazer convex hull ÃƒÂ© muito mais rapido.
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
             # OtimizaÃƒÂ§ÃƒÂ£o: Converter para apenas Exterior Ring se for Poligono (ignorar buracos internos do Hull)
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
        preferred_lines = self._collect_laje_preferred_outline_lines(candidates)
        crop_bbox = self._laj_crop_bbox_from_labels(label_id or "", start_point, search_radius)
        self.last_trace_diagnostics = {
            "candidate_line_count": len(classified),
            "accepted_line_count": len(lines),
            "rejected_line_count": len(rejected),
            "preferred_line_count": len(preferred_lines),
            "label_id": label_id,
            "n2_axes_crop_bbox": crop_bbox,
            "outline_source": "none",
            "rejections": [
                {"layer": info.get("layer"), "reasons": info.get("reasons", [])}
                for _, info in rejected[:50]
            ],
        }
        if not lines:
            # Sem linhas candidatas: tentar teacher coords antes de desistir
            teacher = self._fuzzy_teacher_lookup(label_id)
            if teacher:
                teacher_coords = teacher.get("coordenadas")
                if teacher_coords and isinstance(teacher_coords, list) and len(teacher_coords) >= 4:
                    try:
                        from shapely.geometry import Polygon as _Poly, Point as _Pt
                        coord_poly = _Poly(teacher_coords)
                        if coord_poly.is_valid and coord_poly.area > 100:
                            target_check = _Pt(cx, cy)
                            if coord_poly.contains(target_check) or coord_poly.touches(target_check):
                                self.last_trace_diagnostics["outline_source"] = "n2_teacher_coords"
                                self.last_trace_diagnostics["confidence_score"] = 0.9
                                return coord_poly
                    except Exception:
                        pass
            return None
        target_pt = Point(cx, cy)
        teacher = self._fuzzy_teacher_lookup(label_id)
        # Se o teacher tem coordenadas, usar diretamente (gabarito N2)
        # Dimensoes (comp/larg) podem estar erradas, mas coordenadas sao o poligono real
        if teacher:
            teacher_coords = teacher.get("coordenadas")
            if teacher_coords and isinstance(teacher_coords, list) and len(teacher_coords) >= 4:
                try:
                    from shapely.geometry import Polygon as _Poly
                    coord_poly = _Poly(teacher_coords)
                    if coord_poly.is_valid and coord_poly.area > 100:
                        # Tolerancia: texto pode estar alguns mm fora do poligono
                        if coord_poly.contains(target_pt) or coord_poly.touches(target_pt) or coord_poly.distance(target_pt) < 50:
                            self.last_trace_diagnostics["outline_source"] = "n2_teacher_coords"
                            self.last_trace_diagnostics["confidence_score"] = self._compute_confidence(coord_poly, target_pt, teacher, crop_bbox)
                            return coord_poly
                except Exception:
                    pass
        try:
            noded_lines = unary_union(lines)
            polygons = list(polygonize(noded_lines))
            selected = self._select_best_laje_polygon(polygons, target_pt, crop_bbox)
            teacher_poly = self._teacher_laj_outline_from_n2_dims(lines, target_pt, crop_bbox, teacher) if crop_bbox else None
            if self._learning_params.get('fallback_to_teacher'):
                axes_poly = teacher_poly  # So usar teacher real; None se nao houver
            else:
                axes_poly = teacher_poly or (self._canonical_laj_outline_from_n2_axes(lines, target_pt, crop_bbox, teacher, preferred_lines=preferred_lines) if crop_bbox else None)
            if not teacher and selected is not None and axes_poly is not None:
                thin_selected = self._thin_irregular_polygonized_strip(selected, axes_poly, target_pt, lines)
                if thin_selected is not None:
                    selected = thin_selected
            if self._should_prefer_n2_axes_outline(selected, axes_poly, target_pt):
                self.last_trace_diagnostics["outline_source"] = "n2_teacher_axes" if teacher_poly else "n2_axes"
                result = axes_poly
            else:
                self.last_trace_diagnostics["outline_source"] = "polygonize"
                result = selected
            if not teacher and result is not None:
                dim_refined = self._outline_from_local_dimension_texts(lines, target_pt, crop_bbox, result)
                if dim_refined is not None:
                    source = self.last_trace_diagnostics.get("outline_source", "outline")
                    self.last_trace_diagnostics["outline_source"] = f"{source}_dim_text"
                    result = dim_refined
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
            score = 0.50 * n2_match + 0.20 * min(1.0, area_ratio) + 0.20 * edge_score + 0.10 * bbox_coverage
            return round(score, 3)
        except Exception:
            return 0.0

    def detect_extensions(self, main_poly: Polygon, search_radius: float = 50.0) -> List[Dict]:
        """
        Detecta e GERA 'acrÃƒÂ©scimos' (strips de 10 unidades) em bordas externas.
        EstratÃƒÂ©gia: Generative Edge Extrusion (V4).
        1. Para cada aresta da laje:
        2. Testar se aponta para o 'vazio' (Ray Cast).
        3. Se for vazio, extrudar aresta em 10 unidades e criar polÃƒÂ­gono.
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


    def _region_growing_fallback(self, cx: float, cy: float, search_radius: float, valid_layers=None) -> Optional[Polygon]:
        """Region growing: quando polygonize falha, encontrar linhas estruturais proximas
        e construir bounding box. Expande dinamicamente do centro ate encontrar 2 eixos H e 2 V."""
        from shapely.geometry import box as Box

        # Buscar linhas num raio crescente a partir do centro
        for radius in [200.0, 400.0, 600.0, 800.0, search_radius]:
            bounds = (cx - radius, cy - radius, cx + radius, cy + radius)
            candidates = self.spatial_index.query_bbox(bounds)

            # Coletar linhas estruturais (nao textos)
            h_lines = []  # y=const (horizontais)
            v_lines = []  # x=const (verticais)
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                if 'start' not in item or 'end' not in item:
                    continue
                s, e = item['start'], item['end']
                dx = abs(s[0] - e[0])
                dy = abs(s[1] - e[1])
                tol = max(0.5, radius * 0.001)
                if dx <= tol and dy > 5.0:  # vertical line
                    v_lines.append(s[0])
                elif dy <= tol and dx > 5.0:  # horizontal line
                    h_lines.append(s[1])

            if len(set(h_lines)) < 2 or len(set(v_lines)) < 2:
                continue  # sem eixos suficientes, expandir raio

            # Agrupar eixos proximos (tolerancia dinamica)
            def cluster(values, tol=3.0):
                if not values: return []
                sorted_v = sorted(set(round(v, 1) for v in values))
                clusters = [[sorted_v[0]]]
                for v in sorted_v[1:]:
                    if v - clusters[-1][-1] <= tol:
                        clusters[-1].append(v)
                    else:
                        clusters.append([v])
                return [sum(c)/len(c) for c in clusters]

            h_clusters = cluster(h_lines)
            v_clusters = cluster(v_lines)

            # Encontrar o par de eixos que envolve o centro
            h_below = [v for v in h_clusters if v < cy]
            h_above = [v for v in h_clusters if v > cy]
            v_left = [v for v in v_clusters if v < cx]
            v_right = [v for v in v_clusters if v > cx]

            if not h_below or not h_above or not v_left or not v_right:
                continue

            # Pegar os mais proximos do centro
            y0 = max(h_below)  # mais proximo abaixo
            y1 = min(h_above)  # mais proximo acima
            x0 = max(v_left)   # mais proximo a esquerda
            x1 = min(v_right)  # mais proximo a direita

            # Validar: dimensoes razoaveis
            w = x1 - x0
            h = y1 - y0
            if w < 20 or h < 20:
                continue
            if w > radius * 2 or h > radius * 2:
                continue  # maior que o raio de busca

            poly = Box(x0, y0, x1, y1)
            if poly.is_valid and poly.area > 100:
                return poly

        return None

    def detect_slabs_from_texts(self, texts: List[Dict], search_radius: float = 2000.0, valid_layers: List[str] = None, teacher_dims: Dict[str, Dict] = None) -> List[Dict]:
        """Detect slab labels and trace outlines using cascade: semantic + crop + polygonize + N2 axes + teacher."""
        # Learning Store: ajustar search_radius se learning tem override
        lp = self._learning_params
        if lp.get("search_radius_override"):
            search_radius = float(lp["search_radius_override"])

        slabs = []
        import re
        slab_pattern = re.compile(r'^L[A-Z]*[-_]?\d+[A-Z0-9_]*$', re.IGNORECASE)
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
            try:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
            except ImportError:
                pass
                
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
                # Region Growing fallback: quando polygonize e n2_axes falham
                # pegar linhas proximas e construir bounding box dinamico
                cx, cy = pos
                rg_poly = self._region_growing_fallback(cx, cy, search_radius, valid_layers)
                if rg_poly:
                    pts_rg = list(rg_poly.exterior.coords)
                    points = pts_rg
                    area = rg_poly.area
                    found_poly = True
                    print(f"[DEBUG] Region growing fallback for {txt}: {rg_poly.bounds[2]-rg_poly.bounds[0]:.0f}x{rg_poly.bounds[3]-rg_poly.bounds[1]:.0f}")
                else:
                    # Ultimo recurso: N2 teacher dims ou 50x50
                    teacher_fallback = self._fuzzy_teacher_lookup(txt.upper())
                    if teacher_fallback:
                        tc = float(teacher_fallback.get("comprimento") or teacher_fallback.get("comp") or 0)
                        tl = float(teacher_fallback.get("largura") or teacher_fallback.get("larg") or 0)
                        if tc > 0 and tl > 0:
                            half_c, half_l = tc / 2.0, tl / 2.0
                        else:
                            half_c, half_l = 25.0, 25.0
                    else:
                        half_c, half_l = 25.0, 25.0
                    points = [
                        (cx - half_c, cy - half_l), (cx + half_c, cy - half_l),
                        (cx + half_c, cy + half_l), (cx - half_c, cy + half_l),
                        (cx - half_c, cy - half_l),
                    ]
                    area = 0.0
                    print(f"[DEBUG] Fallback polygon for {txt}: {half_c*2:.0f}x{half_l*2:.0f} (teacher={teacher_fallback is not None})")

            confidence = diag.get("confidence_score", 0.0)
            # Learning Store: aplicar ajustes de confidence
            conf_boost = lp.get("confidence_boost")
            conf_penalty = lp.get("confidence_penalty")
            if conf_boost:
                confidence = min(1.0, confidence + float(conf_boost))
            if conf_penalty:
                confidence = max(0.0, confidence - float(conf_penalty))

            # Learning Store: aplicar bias_correction na area se disponivel
            area_bias = lp.get("area_bias_correction")
            if area_bias and isinstance(area, (int, float)) and area > 0:
                area = area * (1.0 + float(area_bias))

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
                'origin': 'teacher_global' if (diag.get("outline_source", "").startswith("n2_teacher")) else 'motor_geom',
                'method': diag.get("outline_source", "unknown"),
            }
            if diag:
                slab['trace_diagnostics'] = dict(diag)
            slabs.append(slab)

        # Guarda o contorno bruto (antes das normalizacoes de fileira) para
        # poder reverter qualquer expansao que produza sobreposicao real
        # entre lajes -- ver _reject_overlapping_row_expansions.
        originals = {
            slab['id']: (list(slab['points']), slab['area'], slab['method'])
            for slab in slabs
        }

        self._normalize_thin_slab_rows(slabs)
        self._normalize_partial_medium_edge_slabs(slabs)
        self._normalize_medium_row_heights(slabs)
        self._expand_left_chamfered_tall_slabs(slabs)
        self._expand_long_strip_right_step(slabs)
        self._reject_overlapping_row_expansions(slabs, originals)
        return slabs

    def _reject_overlapping_row_expansions(
        self, slabs: List[Dict], originals: Dict[str, tuple],
    ) -> None:
        """As passagens de normalizacao de fileira (_normalize_thin_slab_rows,
        _normalize_partial_medium_edge_slabs, _normalize_medium_row_heights,
        _expand_left_chamfered_tall_slabs, _expand_long_strip_right_step)
        generalizam por banda numerica de altura/largura sem verificar se o
        eixo escolhido e realmente a face da viga que separa esta laje da
        vizinha -- podem avancar sobre o territorio da laje ao lado (ou
        sobre a viga entre elas). Lajes reais nunca se sobrepoem
        fisicamente: qualquer overlap real entre duas lajes computadas
        indica que uma expansao foi longe demais. Reverte a(s) laje(s)
        que foram MODIFICADAS por essas passagens (nunca a vizinha nao
        tocada) para o contorno anterior as normalizacoes.
        """
        try:
            polys: Dict[str, Polygon] = {}
            for slab in slabs:
                pts = slab.get("points") or []
                if len(pts) < 3:
                    continue
                poly = Polygon(pts)
                if poly.is_valid and poly.area > 0:
                    polys[slab["id"]] = poly

            expanded_ids = {
                sid for sid, (orig_pts, _, _) in originals.items()
                if sid in polys and list(polys[sid].exterior.coords) != orig_pts
            }
            if not expanded_ids:
                return

            reverted = set()
            for sid in expanded_ids:
                poly = polys.get(sid)
                if poly is None:
                    continue
                for other_id, other_poly in polys.items():
                    if other_id == sid or other_id in reverted:
                        continue
                    inter_area = poly.intersection(other_poly).area
                    tolerance = max(25.0, 0.03 * min(poly.area, other_poly.area))
                    if inter_area <= tolerance:
                        continue
                    reverted.add(sid)
                    break

            if not reverted:
                return
            for slab in slabs:
                if slab["id"] not in reverted:
                    continue
                orig_points, orig_area, orig_method = originals[slab["id"]]
                slab["points"] = orig_points
                slab["area"] = orig_area
                slab["method"] = orig_method
                diag = dict(slab.get("trace_diagnostics") or {})
                diag["row_expansion_reverted_overlap"] = True
                slab["trace_diagnostics"] = diag
        except Exception:
            return
