"""Geometric guard for LV endpoint supports.

The FV interpretation may describe the *global* limits of a beam.  LV consumes
those labels only as context: a global label is not automatically an endpoint
of either lateral.  This module keeps that boundary explicit and contains no
FV/N2 dimension fallback.
"""

from __future__ import annotations

from typing import Any, Iterable


Point = tuple[float, float]


def _as_points(value: Any) -> list[Point]:
    """Return valid XY points from a polyline-like value."""
    if not isinstance(value, (list, tuple)):
        return []
    points: list[Point] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            points.append((float(item[0]), float(item[1])))
        except (TypeError, ValueError):
            continue
    return points


def _bbox(points: Iterable[Point]) -> tuple[float, float, float, float] | None:
    values = list(points)
    if not values:
        return None
    xs = [p[0] for p in values]
    ys = [p[1] for p in values]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_touches(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
    *,
    tolerance: float,
) -> bool:
    return not (
        left[2] + tolerance < right[0]
        or right[2] + tolerance < left[0]
        or left[3] + tolerance < right[1]
        or right[3] + tolerance < left[1]
    )


def entity_geometry_candidates(entity: Any) -> list[list[Point]]:
    """Extract local CAD contours from an SA entity without guessing geometry."""
    if not isinstance(entity, dict):
        return []
    candidates: list[list[Point]] = []

    def add(raw: Any) -> None:
        points = _as_points(raw)
        if len(points) >= 2:
            candidates.append(points)

    add(entity.get("points"))
    geometry = entity.get("geometry")
    if isinstance(geometry, dict):
        add(geometry.get("points"))
        classified = geometry.get("classified")
        if isinstance(classified, dict):
            for groups in classified.values():
                if isinstance(groups, list):
                    for group in groups:
                        add(group)
    links = entity.get("links")
    if isinstance(links, dict):
        for value in links.values():
            if not isinstance(value, dict):
                continue
            for contour in value.get("contour") or []:
                if isinstance(contour, dict):
                    add(contour.get("points"))
    return candidates


def support_contacts_lv_segment(
    segment_points: Any,
    support_name: str,
    *,
    beams: Iterable[dict[str, Any]] = (),
    pillars: Iterable[dict[str, Any]] = (),
    tolerance: float = 2.0,
) -> bool:
    """True only when the named support physically touches this LV segment.

    A false result is intentionally *not* a request to choose a nearer support.
    It means that the inherited label is not local proof and must not populate a
    lateral endpoint automatically.
    """
    segment_bbox = _bbox(_as_points(segment_points))
    wanted = str(support_name or "").strip().upper()
    if segment_bbox is None or not wanted:
        return False
    for entity in (*list(beams), *list(pillars)):
        if str(entity.get("name") or "").strip().upper() != wanted:
            continue
        for candidate in entity_geometry_candidates(entity):
            candidate_bbox = _bbox(candidate)
            if candidate_bbox and _bbox_touches(
                segment_bbox, candidate_bbox, tolerance=tolerance
            ):
                return True
        return False
    return False
