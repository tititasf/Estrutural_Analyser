"""Derivação auditável do nível de cada segmento de fundo de viga.

A regra acompanha a interpretação já usada pelas laterais: a viga assume a
maior cota das lajes em contato. Uma cota explícita do próprio segmento/lateral
tem prioridade. Para vigas de borda sem contato, usa a laje cotada geometricamente
mais próxima e registra a distância usada na associação.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable


_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _number(value: Any, *, zero_is_missing: bool = False) -> float | None:
    if value in (None, "", "—", "-"):
        return None
    match = _NUMBER_RE.search(str(value))
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", "."))
    except ValueError:
        return None
    if not math.isfinite(number) or (zero_is_missing and number == 0):
        return None
    return number


def _points(values: Iterable[Any] | None) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in values or []:
        try:
            current = (float(point[0]), float(point[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if not result or current != result[-1]:
            result.append(current)
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    denominator = dx * dx + dy * dy
    if denominator <= 1e-18:
        return math.hypot(px - sx, py - sy)
    ratio = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / denominator))
    return math.hypot(px - (sx + ratio * dx), py - (sy + ratio * dy))


def _polygon_distance(
    first: list[tuple[float, float]], second: list[tuple[float, float]]
) -> float:
    """Distância mínima entre contornos; zero quando um invade o outro."""
    if not first or not second:
        return math.inf
    if _point_in_polygon(first[0], second) or _point_in_polygon(second[0], first):
        return 0.0
    first_edges = list(zip(first, first[1:] + first[:1]))
    second_edges = list(zip(second, second[1:] + second[:1]))
    if any(_segments_intersect(a, b, c, d) for a, b in first_edges for c, d in second_edges):
        return 0.0
    from_first = min(
        min(_point_segment_distance(point, start, end) for start, end in second_edges)
        for point in first
    )
    from_second = min(
        min(_point_segment_distance(point, start, end) for start, end in first_edges)
        for point in second
    )
    return min(from_first, from_second)


def _segments_intersect(a, b, c, d) -> bool:
    def orientation(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p, q, r):
        return (
            min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
            and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
        )

    ab_c, ab_d = orientation(a, b, c), orientation(a, b, d)
    cd_a, cd_b = orientation(c, d, a), orientation(c, d, b)
    if (ab_c < 0) != (ab_d < 0) and (cd_a < 0) != (cd_b < 0):
        return True
    return (
        (abs(ab_c) <= 1e-9 and on_segment(a, c, b))
        or (abs(ab_d) <= 1e-9 and on_segment(a, d, b))
        or (abs(cd_a) <= 1e-9 and on_segment(c, a, d))
        or (abs(cd_b) <= 1e-9 and on_segment(c, b, d))
    )


def _axis(points: list[tuple[float, float]]) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None:
    if len(points) < 2:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    if dx >= dy:
        center = (min(ys) + max(ys)) / 2.0
        return (min(xs), center), (max(xs), center), (0.0, 1.0)
    center = (min(xs) + max(xs)) / 2.0
    return (center, min(ys)), (center, max(ys)), (1.0, 0.0)


def derive_fundo_segment_level(
    segment_points: Iterable[Any] | None,
    slabs: Iterable[dict[str, Any]] | None,
    *,
    explicit_levels: Iterable[Any] = (),
) -> dict[str, Any]:
    """Retorna ``value``, ``source`` e as lajes que comprovam a cota.

    A associação testa três amostras no eixo longitudinal, dos dois lados do
    fundo, com tolerâncias pequenas em coordenadas CAD. Isso funciona tanto
    para polígonos fechados quanto para linhas e evita usar apenas bbox.
    """
    explicit = [
        number
        for number in (_number(value, zero_is_missing=True) for value in explicit_levels)
        if number is not None
    ]
    if explicit:
        return {
            "value": max(explicit),
            "source": "explicit_beam_or_side",
            "slabs": [],
            "distance_cm": 0.0,
        }

    clean = _points(segment_points)
    axis = _axis(clean)
    if axis is None:
        return {"value": None, "source": "unresolved", "slabs": [], "distance_cm": None}
    start, end, normal = axis
    touching: list[tuple[float, str]] = []
    levelled_slabs: list[tuple[float, str, list[tuple[float, float]]]] = []
    for slab in slabs or []:
        if not isinstance(slab, dict):
            continue
        raw_level = (slab.get("fields") or {}).get("laje_nivel")
        if raw_level in (None, ""):
            raw_level = slab.get("nivel")
        level = _number(raw_level)
        polygon = _points(slab.get("points") or [])
        if level is None or len(polygon) < 3:
            continue
        levelled_slabs.append((level, str(slab.get("name") or ""), polygon))
        hits = 0
        for ratio in (0.15, 0.5, 0.85):
            base = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
            if any(
                _point_in_polygon(
                    (base[0] + normal[0] * sign * offset,
                     base[1] + normal[1] * sign * offset),
                    polygon,
                )
                for sign in (-1.0, 1.0)
                for offset in (1.0, 3.0, 8.0, 16.0)
            ):
                hits += 1
        if hits:
            touching.append((level, str(slab.get("name") or "")))

    if not touching:
        nearest = [
            (_polygon_distance(clean, polygon), level, name)
            for level, name, polygon in levelled_slabs
        ]
        if not nearest:
            return {"value": None, "source": "unresolved", "slabs": [], "distance_cm": None}
        minimum = min(distance for distance, _, _ in nearest)
        equally_near = [entry for entry in nearest if abs(entry[0] - minimum) <= 0.01]
        highest = max(level for _, level, _ in equally_near)
        names = sorted({name for _, level, name in equally_near if level == highest and name})
        return {
            "value": highest,
            "source": "nearest_levelled_slab",
            "slabs": names,
            "distance_cm": round(minimum, 3),
        }
    highest = max(level for level, _ in touching)
    names = sorted({name for level, name in touching if level == highest and name})
    return {
        "value": highest,
        "source": "highest_touching_slab",
        "slabs": names,
        "distance_cm": 0.0,
    }
