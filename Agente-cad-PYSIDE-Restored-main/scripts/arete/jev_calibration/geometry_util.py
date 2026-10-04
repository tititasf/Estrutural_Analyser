"""Small CAD geometry helpers for packet bounding. No DXF ingest into prompts."""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

from .cad_source import CadEntity

DIM_RE = re.compile(r"^\s*(\d{1,3}(?:[.,]\d+)?)\s*[/xX×]\s*(\d{1,3}(?:[.,]\d+)?)\s*$")
HEIGHT_RE = re.compile(r"^h\s*=\s*\d+(?:[.,]\d+)?$", re.IGNORECASE)
LEVEL_RE = re.compile(r"^85\d(?:[.,]\d{1,2})?$")
PILLAR_NAME_RE = re.compile(r"^P\d+[A-Z]?$", re.IGNORECASE)
SLAB_NAME_RE = re.compile(r"^L\d+[A-Z]?$", re.IGNORECASE)
BEAM_NAME_RE = re.compile(r"^V[F]?\d+[A-Z]?$", re.IGNORECASE)


def parse_dimension(text: str | None) -> tuple[float, float] | None:
    match = DIM_RE.fullmatch(str(text or "").strip())
    if not match:
        return None
    return tuple(sorted(float(part.replace(",", ".")) for part in match.groups()))  # type: ignore[return-value]


def rectangular_sides(points: list) -> tuple[float, float] | None:
    xy = [(float(p[0]), float(p[1])) for p in points or []]
    if len(xy) >= 2 and math.dist(xy[0], xy[-1]) < 0.05:
        xy = xy[:-1]
    if len(xy) != 4:
        return None
    xs, ys = sorted({round(x, 3) for x, _ in xy}), sorted({round(y, 3) for _, y in xy})
    if len(xs) != 2 or len(ys) != 2:
        return None
    if {(round(x, 3), round(y, 3)) for x, y in xy} != {(x, y) for x in xs for y in ys}:
        return None
    return tuple(sorted((xs[1] - xs[0], ys[1] - ys[0])))  # type: ignore[return-value]


def pair_matches(a: tuple[float, float] | None, b: tuple[float, float], tol: float = 0.15) -> bool:
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def polygon_area(points: list) -> float:
    ring = [(float(p[0]), float(p[1])) for p in points or []]
    if len(ring) < 3:
        return 0.0
    if math.dist(ring[0], ring[-1]) < 0.05:
        ring = ring[:-1]
    if len(ring) < 3:
        return 0.0
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]))) / 2.0


def is_closed_loop(entity: CadEntity) -> bool:
    if entity.closed is True:
        return True
    pts = entity.points or []
    if len(pts) >= 4 and math.dist((pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])) < 0.05:
        return True
    return False


def verified_closed_contour_containing(label_xy: list[float], entities: Iterable[CadEntity],
                                       *, min_area: float = 80.0, max_area: float = 20000.0
                                       ) -> CadEntity | None:
    """Smallest closed DXF loop that actually contains the label. Nearby lines do not qualify."""
    x, y = float(label_xy[0]), float(label_xy[1])
    containing: list[tuple[float, CadEntity]] = []
    for ent in entities:
        if ent.etype not in {"LWPOLYLINE", "POLYLINE"}:
            continue
        if not is_closed_loop(ent):
            continue
        if not point_in_ring(x, y, ent.points):
            continue
        area = polygon_area(ent.points)
        if area < min_area or area > max_area:
            continue
        containing.append((area, ent))
    if not containing:
        return None
    containing.sort(key=lambda row: (row[0], row[1].handle))
    return containing[0][1]


def point_in_ring(x: float, y: float, points: list) -> bool:
    ring = [(float(p[0]), float(p[1])) for p in points or []]
    if len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def expand_bbox(box: list[float], margin: float) -> list[float]:
    return [box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin]


def entity_bbox(entities: Iterable[CadEntity], fallback: list[float] | None = None) -> list[float]:
    items = list(entities)
    if not items:
        return list(fallback or [0, 0, 0, 0])
    return [
        min(e.minx for e in items), min(e.miny for e in items),
        max(e.maxx for e in items), max(e.maxy for e in items),
    ]


def compact_entity(entity: CadEntity, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row = entity.as_candidate()
    extra = dict(extra or {})
    include_points = extra.pop("include_points", None)
    if include_points is None:
        include_points = entity.etype in {"LINE", "LWPOLYLINE", "POLYLINE"}
    if include_points and "points" not in extra:
        pts = rounded_points(entity.points)
        if pts:
            extra["points"] = pts
    row.update(extra)
    return row


def stable_option_id(handle: str, text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{handle}_{text}").strip("_")
    return safe[:48] or handle


def dist(a: list[float] | tuple, b: list[float] | tuple) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def same_segment(p0, p1, q0, q1, tol: float = 2.0) -> bool:
    return (
        (dist(p0, q0) <= tol and dist(p1, q1) <= tol)
        or (dist(p0, q1) <= tol and dist(p1, q0) <= tol)
    )


def unique_vertices(points: list, *, ndigits: int = 3) -> list[tuple[float, float]]:
    verts: list[tuple[float, float]] = []
    for point in points or []:
        xy = (round(float(point[0]), ndigits), round(float(point[1]), ndigits))
        if not verts or xy != verts[-1]:
            verts.append(xy)
    if len(verts) >= 2 and verts[0] == verts[-1]:
        verts = verts[:-1]
    return verts


def entity_vertex_count(entity: CadEntity) -> int:
    return len(entity.points or [])


def entity_bbox_row(entity: CadEntity) -> list[float]:
    return [
        round(float(entity.minx), 3), round(float(entity.miny), 3),
        round(float(entity.maxx), 3), round(float(entity.maxy), 3),
    ]


def classify_source_curve(entity: CadEntity) -> str:
    """Open 2-vertex walls vs closed contours whose one edge happens to be parallel."""
    if is_closed_loop(entity) and len(unique_vertices(entity.points)) >= 3:
        return "closed_polygon_edge"
    return "wall_line"


def entity_as_segments(entity: CadEntity) -> list[tuple[list[float], list[float]]]:
    pts = entity.points or []
    if entity.etype == "LINE" and len(pts) >= 2:
        return [([float(pts[0][0]), float(pts[0][1])], [float(pts[-1][0]), float(pts[-1][1])])]
    segs = []
    for a, b in zip(pts, pts[1:]):
        segs.append(([float(a[0]), float(a[1])], [float(b[0]), float(b[1])]))
    if is_closed_loop(entity) and len(pts) >= 3:
        first = [float(pts[0][0]), float(pts[0][1])]
        last = [float(pts[-1][0]), float(pts[-1][1])]
        if dist(first, last) >= 0.05:
            segs.append((last, first))
    return segs


def match_dxf_line(source, p0, p1, *, types: tuple[str, ...] = ("LINE", "LWPOLYLINE"),
                   tol: float = 2.0) -> CadEntity | None:
    mid = [(float(p0[0]) + float(p1[0])) / 2.0, (float(p0[1]) + float(p1[1])) / 2.0]
    radius = max(dist(p0, p1) / 2.0 + 8.0, 20.0)
    hits = []
    for ent in source.entities_near(mid[0], mid[1], radius, types=list(types)):
        for a, b in entity_as_segments(ent):
            if same_segment(p0, p1, a, b, tol=tol):
                hits.append(ent)
                break
    if not hits:
        return None

    def _rank(ent: CadEntity) -> tuple:
        wall = classify_source_curve(ent) == "wall_line"
        return (0 if wall else 1, dist(ent.xy, mid), ent.handle)

    hits.sort(key=_rank)
    return hits[0]


def match_dxf_polygon(source, points: list, *, tol: float = 3.0) -> CadEntity | None:
    """Closed DXF loop whose vertices and area match this polygon, not a nearby outline."""
    if not points or len(points) < 3:
        return None
    n1_area = polygon_area(points)
    if n1_area < 20.0:
        return None
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    n1_needed = [p for i, p in enumerate(points)
                 if i == 0 or dist(p, points[i - 1]) > 0.05]
    if dist(n1_needed[0], n1_needed[-1]) < 0.05 and len(n1_needed) > 1:
        n1_needed = n1_needed[:-1]
    radius = max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 + 20.0
    best = None
    best_score = -1.0
    for ent in source.entities_near(cx, cy, radius, types=["LWPOLYLINE", "POLYLINE"]):
        if not is_closed_loop(ent) or len(ent.points) < 3:
            continue
        dxf_area = polygon_area(ent.points)
        if dxf_area < 20.0:
            continue
        ratio = dxf_area / n1_area if n1_area else 0.0
        if ratio < 0.7 or ratio > 1.3:
            continue
        hits = sum(1 for vx, vy in n1_needed
                   if any(dist([vx, vy], p) <= tol for p in ent.points))
        if hits < max(3, int(0.75 * len(n1_needed))):
            continue
        centroid_ok = point_in_ring(cx, cy, ent.points)
        score = hits + (2.0 if centroid_ok else 0.0) - abs(1.0 - ratio)
        if score > best_score:
            best_score = score
            best = ent
    return best


def rounded_points(points: list, limit: int = 24) -> list[list[float]] | None:
    pts = [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in points or []]
    if len(pts) > limit:
        return None
    return pts


def direction(p0, p1) -> tuple[float, float] | None:
    dx, dy = float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1])
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return None
    return (dx / length, dy / length)


def parallel(p0, p1, q0, q1, *, min_dot: float = 0.92) -> bool:
    a, b = direction(p0, p1), direction(q0, q1)
    if a is None or b is None:
        return False
    return abs(a[0] * b[0] + a[1] * b[1]) >= min_dot


def line_point_distance(p0, p1, q) -> float:
    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(p1[0]) - ax, float(p1[1]) - ay
    length2 = bx * bx + by * by
    if length2 < 1e-9:
        return dist(p0, q)
    t = max(0.0, min(1.0, ((float(q[0]) - ax) * bx + (float(q[1]) - ay) * by) / length2))
    return dist([ax + t * bx, ay + t * by], q)


def midpoint(points: list) -> list[float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return [round((min(xs) + max(xs)) / 2.0, 3), round((min(ys) + max(ys)) / 2.0, 3)]


def signed_line_distance(p0, p1, q) -> float:
    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(p1[0]) - ax, float(p1[1]) - ay
    length = math.hypot(bx, by)
    if length < 1e-9:
        return dist(p0, q)
    return ((float(q[0]) - ax) * by - (float(q[1]) - ay) * bx) / length


def along_segment_t(p0, p1, q) -> float:
    ax, ay = float(p0[0]), float(p0[1])
    bx, by = float(p1[0]) - ax, float(p1[1]) - ay
    length2 = bx * bx + by * by
    if length2 < 1e-9:
        return 0.0
    return ((float(q[0]) - ax) * bx + (float(q[1]) - ay) * by) / length2


def label_near_strip(label_xy, cell_pts, other_pts, *, max_outside: float = 40.0,
                     t_margin: float = 0.35) -> tuple[bool, str]:
    if len(cell_pts) != 2 or len(other_pts) != 2:
        return False, "missing_endpoints"
    t = along_segment_t(cell_pts[0], cell_pts[1], label_xy)
    if t < -t_margin or t > 1.0 + t_margin:
        return False, "label_not_along_cell"
    s0 = signed_line_distance(cell_pts[0], cell_pts[1], label_xy)
    s1 = signed_line_distance(other_pts[0], other_pts[1], label_xy)
    if s0 * s1 <= 0:
        return True, "inside_strip"
    outside = min(abs(s0), abs(s1))
    if outside <= max_outside:
        return True, "offset_from_strip"
    return False, "outside_strip"


def longitudinal_overlap_ratio(p0, p1, q0, q1) -> float:
    t0 = along_segment_t(p0, p1, q0)
    t1 = along_segment_t(p0, p1, q1)
    lo, hi = min(t0, t1), max(t0, t1)
    return max(0.0, min(hi, 1.0) - max(lo, 0.0))


def _segment_payload(p0, p1, a, b, radius: float) -> dict[str, Any] | None:
    if dist(a, b) < 1.0 or not parallel(p0, p1, a, b):
        return None
    if same_segment(p0, p1, a, b, tol=2.0):
        return None
    overlap = longitudinal_overlap_ratio(p0, p1, a, b)
    gap = min(
        line_point_distance(a, b, p0), line_point_distance(a, b, p1),
        line_point_distance(p0, p1, a), line_point_distance(p0, p1, b),
    )
    return {
        "segment": ([round(float(a[0]), 3), round(float(a[1]), 3)],
                    [round(float(b[0]), 3), round(float(b[1]), 3)]),
        "gap": round(float(gap), 3),
        "overlap": round(float(overlap), 3),
        "radius": round(float(radius), 3),
    }


def _hit_from_entity(ent: CadEntity, best: dict[str, Any]) -> dict[str, Any]:
    classification = classify_source_curve(ent)
    return {
        "entity": ent,
        "segment": best["segment"],
        "selected_edge": [list(best["segment"][0]), list(best["segment"][1])],
        "gap": best["gap"],
        "overlap": best["overlap"],
        "classification": classification,
        "closed": bool(is_closed_loop(ent)),
        "vertex_count": entity_vertex_count(ent),
        "unique_vertex_count": len(unique_vertices(ent.points)),
        "bbox": entity_bbox_row(ent),
        "duplicate_handles": [],
        "duplicate_layers": [],
        "provenance": {
            "source": "fase1_dxf",
            "method": "entities_near_parallel_gap_overlap",
            "radius": best["radius"],
            "gap": best["gap"],
            "overlap": best["overlap"],
            "n1_fundo_used": False,
            "classification": classification,
        },
    }


def _contour_dedupe_key(ent: CadEntity) -> tuple | None:
    verts = unique_vertices(ent.points)
    if not is_closed_loop(ent) or len(verts) < 3:
        return None
    bbox = tuple(entity_bbox_row(ent))
    return ("closed", bbox, frozenset(verts))


def _open_edge_dedupe_key(hit: dict[str, Any]) -> tuple:
    a, b = hit["segment"]
    pair = tuple(sorted((tuple(a), tuple(b))))
    return ("open", pair)


def dedupe_parallel_hits(found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse identical closed contours (and identical open edges) across layers."""
    groups: dict[tuple, list[dict[str, Any]]] = {}
    order: list[tuple] = []
    for hit in found:
        ent = hit["entity"]
        key = _contour_dedupe_key(ent)
        if key is None:
            key = _open_edge_dedupe_key(hit)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(hit)
    out: list[dict[str, Any]] = []
    for key in order:
        members = groups[key]
        members.sort(key=lambda row: (row["entity"].handle, row["entity"].layer or ""))
        keep = dict(members[0])
        extras = members[1:]
        if extras:
            keep["duplicate_handles"] = [row["entity"].handle for row in extras]
            keep["duplicate_layers"] = [row["entity"].layer for row in extras]
            keep["provenance"] = dict(keep["provenance"])
            keep["provenance"]["duplicate_handles"] = list(keep["duplicate_handles"])
            keep["provenance"]["duplicate_layers"] = list(keep["duplicate_layers"])
        out.append(keep)
    return out


def nearby_parallel_segments(source, cell_pts: list, cell_handle: str, *,
                             gap_max: float = 40.0, min_overlap: float = 0.5
                             ) -> list[dict[str, Any]]:
    if len(cell_pts) != 2:
        return []
    p0, p1 = cell_pts[0], cell_pts[1]
    mid = midpoint([p0, p1])
    radius = max(dist(p0, p1) / 2.0 + gap_max + 8.0, 50.0)
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ent in source.entities_near(mid[0], mid[1], radius, types=["LINE", "LWPOLYLINE"]):
        if ent.handle == cell_handle or ent.handle in seen:
            continue
        best = None
        for a, b in entity_as_segments(ent):
            payload = _segment_payload(p0, p1, a, b, radius)
            if payload is None or payload["overlap"] < min_overlap or payload["gap"] > gap_max:
                continue
            if best is None or (payload["overlap"], -payload["gap"]) > (best["overlap"], -best["gap"]):
                best = payload
        if best is None:
            continue
        seen.add(ent.handle)
        found.append(_hit_from_entity(ent, best))
    found = dedupe_parallel_hits(found)
    found.sort(key=lambda row: (-row["overlap"], row["gap"], row["entity"].handle))
    return found


def point_on_segment(p0, p1, q, *, tol: float = 2.0) -> bool:
    t = along_segment_t(p0, p1, q)
    return line_point_distance(p0, p1, q) <= tol and -0.02 <= t <= 1.02


def wall_contains_endpoints(ent: CadEntity, p0, p1, *, tol: float = 2.0) -> dict[str, Any] | None:
    """Return the open wall segment that carries both locator endpoints, if any."""
    if classify_source_curve(ent) != "wall_line":
        return None
    best = None
    for a, b in entity_as_segments(ent):
        if dist(a, b) < 1.0:
            continue
        exact = same_segment(p0, p1, a, b, tol=tol)
        covering = (
            parallel(p0, p1, a, b)
            and point_on_segment(a, b, p0, tol=tol)
            and point_on_segment(a, b, p1, tol=tol)
        )
        if not exact and not covering:
            continue
        wall_len = dist(a, b)
        cell_len = dist(p0, p1)
        payload = {
            "segment": ([round(float(a[0]), 3), round(float(a[1]), 3)],
                        [round(float(b[0]), 3), round(float(b[1]), 3)]),
            "match": "exact" if exact else "cover",
            "wall_length": round(float(wall_len), 3),
            "locator_length": round(float(cell_len), 3),
            "extends_beyond_locator": (not exact) or wall_len > cell_len + tol,
        }
        rank = (0 if exact else 1, -wall_len)
        if best is None or rank < best[0]:
            best = (rank, payload)
    return None if best is None else best[1]


def unique_source_wall(source, p0, p1, *, types: tuple[str, ...] = ("LINE", "LWPOLYLINE"),
                       tol: float = 2.0) -> dict[str, Any] | None:
    """Unique open source wall whose geometry carries both locator endpoints.

    Closed contours that happen to share an edge are ignored. Several distinct
    walls is insufficient. Exact same-segment match wins over a longer cover.
    """
    mid = [(float(p0[0]) + float(p1[0])) / 2.0, (float(p0[1]) + float(p1[1])) / 2.0]
    radius = max(dist(p0, p1) / 2.0 + 12.0, 30.0)
    hits: list[tuple[CadEntity, dict[str, Any]]] = []
    seen: set[str] = set()
    for ent in source.entities_near(mid[0], mid[1], radius, types=list(types)):
        if ent.handle in seen:
            continue
        payload = wall_contains_endpoints(ent, p0, p1, tol=tol)
        if payload is None:
            continue
        seen.add(ent.handle)
        hits.append((ent, payload))
    exact = [(ent, payload) for ent, payload in hits if payload["match"] == "exact"]
    pool = exact or hits
    handles = {ent.handle for ent, _payload in pool}
    if len(handles) != 1:
        return None
    ent, payload = sorted(pool, key=lambda row: (row[0].handle,))[0]
    return {"entity": ent, **payload, "unique": True, "exact_count": len(exact),
            "cover_count": len(hits) - len(exact)}


def colinear_continuations(source, p0, p1, cell_handle: str, *, gap: float = 8.0,
                           types: tuple[str, ...] = ("LINE", "LWPOLYLINE")
                           ) -> list[dict[str, Any]]:
    """Open walls that share an endpoint with the target and stay parallel."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for end in (p0, p1):
        for ent in source.entities_near(float(end[0]), float(end[1]), max(gap + 12.0, 20.0),
                                        types=list(types)):
            if ent.handle == cell_handle or ent.handle in seen:
                continue
            if classify_source_curve(ent) != "wall_line":
                continue
            best = None
            for a, b in entity_as_segments(ent):
                if dist(a, b) < 1.0 or not parallel(p0, p1, a, b):
                    continue
                if same_segment(p0, p1, a, b, tol=2.0):
                    continue
                near = min(dist(a, end), dist(b, end))
                if near > gap:
                    continue
                if best is None or near < best["gap"]:
                    best = {
                        "entity": ent,
                        "segment": ([round(float(a[0]), 3), round(float(a[1]), 3)],
                                    [round(float(b[0]), 3), round(float(b[1]), 3)]),
                        "gap": round(float(near), 3),
                        "at": [round(float(end[0]), 3), round(float(end[1]), 3)],
                    }
            if best is None:
                continue
            seen.add(ent.handle)
            found.append(best)
    found.sort(key=lambda row: (row["gap"], row["entity"].handle))
    return found


def transverse_axis(p0, p1) -> str:
    dx = abs(float(p1[0]) - float(p0[0]))
    dy = abs(float(p1[1]) - float(p0[1]))
    return "x" if dy >= dx else "y"


def face_from_transverse(target_pts: list, partner_pts: list) -> str | None:
    """FACE_A is the strip wall with the smaller transverse coordinate."""
    if len(target_pts) != 2 or len(partner_pts) != 2:
        return None
    axis = transverse_axis(target_pts[0], target_pts[1])
    idx = 0 if axis == "x" else 1
    tmid = (float(target_pts[0][idx]) + float(target_pts[1][idx])) / 2.0
    pmid = (float(partner_pts[0][idx]) + float(partner_pts[1][idx])) / 2.0
    if abs(tmid - pmid) < 0.5:
        return None
    return "A" if tmid < pmid else "B"


def rectangle_width_height(points: list) -> tuple[float, float] | None:
    verts = unique_vertices(points)
    if len(verts) != 4:
        return None
    xs = sorted({round(x, 3) for x, _y in verts})
    ys = sorted({round(y, 3) for _x, y in verts})
    if len(xs) != 2 or len(ys) != 2:
        return None
    return (abs(xs[1] - xs[0]), abs(ys[1] - ys[0]))


def is_strip_encounter_gap(ent: CadEntity, cell_pts: list, partner_pts: list,
                           endpoint, *, width_tol: float = 3.0, touch_tol: float = 6.0
                           ) -> bool:
    """Closed rectangle whose width matches the beam strip and that touches an endpoint."""
    if not is_closed_loop(ent):
        return False
    box = rectangle_width_height(ent.points)
    if box is None:
        return False
    strip = abs(signed_line_distance(cell_pts[0], cell_pts[1], midpoint(partner_pts)))
    if strip < 8.0 or strip > 40.0:
        return False
    width, height = box
    axis = transverse_axis(cell_pts[0], cell_pts[1])
    span = width if axis == "x" else height
    if abs(span - strip) > width_tol:
        return False
    if min(dist(endpoint, p) for p in ent.points) > touch_tol:
        return False
    return True
