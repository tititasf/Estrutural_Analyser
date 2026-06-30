"""Geometric recognition helpers for folded FV panels."""

from __future__ import annotations


def derive_quadrilateral_chanfros(vertices, tolerance=0.15):
    """Derive TE/FE/TD/FD setbacks from a four-corner panel outline."""
    if vertices is None:
        return {}
    try:
        raw_points = list(vertices)
    except TypeError:
        return {}

    points = []
    for point in raw_points:
        try:
            if isinstance(point, dict):
                candidate = (
                    float(point.get("x", 0.0)),
                    float(point.get("y", 0.0)),
                )
            else:
                candidate = (float(point[0]), float(point[1]))
        except (IndexError, TypeError, ValueError):
            return {}
        if not any(
            abs(candidate[0] - existing[0]) <= tolerance
            and abs(candidate[1] - existing[1]) <= tolerance
            for existing in points
        ):
            points.append(candidate)

    if len(points) != 4:
        return {}
    x_min = min(x for x, _ in points)
    x_max = max(x for x, _ in points)
    y_min = min(y for _, y in points)
    y_max = max(y for _, y in points)
    bottom = [x for x, y in points if abs(y - y_min) <= tolerance]
    top = [x for x, y in points if abs(y - y_max) <= tolerance]
    if len(bottom) != 2 or len(top) != 2 or y_max - y_min <= tolerance:
        return {}

    chanfros = {
        "te": max(0.0, min(top) - x_min),
        "fe": max(0.0, min(bottom) - x_min),
        "td": max(0.0, x_max - max(top)),
        "fd": max(0.0, x_max - max(bottom)),
    }
    rounded = {key: round(value, 1) for key, value in chanfros.items()}
    return rounded if any(value > tolerance for value in rounded.values()) else {}


def detect_left_angled_l_panel(vertices, tolerance=0.25):
    """Recognize one-piece panels formed by a horizontal body and angled left fold."""
    if vertices is None:
        return None
    try:
        raw_points = list(vertices)
    except TypeError:
        return None

    points = []
    for point in raw_points:
        try:
            if isinstance(point, dict):
                candidate = (
                    float(point.get("x", 0.0)),
                    float(point.get("y", 0.0)),
                )
            else:
                candidate = (float(point[0]), float(point[1]))
        except (IndexError, TypeError, ValueError):
            return None
        if not any(
            abs(candidate[0] - existing[0]) <= tolerance
            and abs(candidate[1] - existing[1]) <= tolerance
            for existing in points
        ):
            points.append(candidate)
    if len(points) != 6:
        return None

    y_min = min(y for _, y in points)
    y_max = max(y for _, y in points)
    bottom = sorted(
        (point for point in points if abs(point[1] - y_min) <= tolerance),
        key=lambda point: point[0],
    )
    tip = [point for point in points if abs(point[1] - y_max) <= tolerance]
    if len(bottom) != 2 or len(tip) != 1:
        return None

    intermediate_levels = []
    for _, y in points:
        if abs(y - y_min) <= tolerance or abs(y - y_max) <= tolerance:
            continue
        level = [point for point in points if abs(point[1] - y) <= tolerance]
        if len(level) == 2 and not any(
            abs(y - known_y) <= tolerance for known_y, _ in intermediate_levels
        ):
            intermediate_levels.append((y, level))
    if len(intermediate_levels) != 1:
        return None

    main_top_y, main_top = intermediate_levels[0]
    main_top = sorted(main_top, key=lambda point: point[0])
    used = set(bottom + main_top + tip)
    outer = [point for point in points if point not in used]
    if len(outer) != 1:
        return None

    outer_mid = outer[0]
    bottom_left, bottom_right = bottom
    top_left, top_right = main_top
    tip_top = tip[0]
    main_height = main_top_y - y_min
    if (
        main_height <= tolerance
        or outer_mid[0] >= bottom_left[0] - tolerance
        or tip_top[0] >= top_left[0] - tolerance
        or bottom_right[0] <= top_right[0] + tolerance
    ):
        return None

    dx = bottom_left[0] - outer_mid[0]
    dy = bottom_left[1] - outer_mid[1]
    edge_length = (dx * dx + dy * dy) ** 0.5
    if edge_length <= tolerance:
        return None
    fold_width = abs(
        dx * (tip_top[1] - outer_mid[1])
        - dy * (tip_top[0] - outer_mid[0])
    ) / edge_length
    if abs(fold_width - main_height) > max(1.5, main_height * 0.12):
        return None

    def as_point(point):
        return {"x": round(point[0], 1), "y": round(point[1], 1)}

    return {
        "type": "left_angled",
        "main_height": round(main_height, 1),
        "total_height": round(y_max - y_min, 1),
        "outer_mid": as_point(outer_mid),
        "bottom_left": as_point(bottom_left),
        "bottom_right": as_point(bottom_right),
        "top_left": as_point(top_left),
        "top_right": as_point(top_right),
        "tip_top": as_point(tip_top),
    }


def detect_right_l_panel(vertices, main_height, tolerance=1.5):
    """Recognize a right-side, downward L panel from its orthogonal outline.

    The STOG outline is the union of a horizontal panel and a rotated panel.
    Returned dimensions keep those two physical panels independent while
    preserving the original longitudinal footprint.
    """
    if vertices is None:
        return None
    try:
        raw_points = list(vertices)
    except TypeError:
        return None
    if len(raw_points) < 6:
        return None

    points = []
    for point in raw_points:
        try:
            if isinstance(point, dict):
                x = float(point.get("x", 0.0))
                y = float(point.get("y", 0.0))
            else:
                x = float(point[0])
                y = float(point[1])
        except (IndexError, TypeError, ValueError):
            return None
        points.append((x, y))

    height = float(main_height or 0.0)
    if height <= 0:
        return None

    x_min = min(x for x, _ in points)
    x_max = max(x for x, _ in points)
    y_bottom = min(y for _, y in points)
    y_top = max(y for _, y in points)
    y_base = y_top - height
    if y_base - y_bottom <= tolerance:
        return None

    def has_point(target_x, target_y):
        return any(
            abs(x - target_x) <= tolerance and abs(y - target_y) <= tolerance
            for x, y in points
        )

    inner_candidates = sorted({
        x for x, y in points
        if x_min + tolerance < x < x_max - tolerance
        and abs(y - y_base) <= tolerance
    })
    if not inner_candidates:
        return None
    inner_x = inner_candidates[-1]

    required = (
        (x_min, y_top),
        (x_max, y_top),
        (x_max, y_bottom),
        (inner_x, y_bottom),
        (inner_x, y_base),
        (x_min, y_base),
    )
    if not all(has_point(x, y) for x, y in required):
        return None

    main_width = inner_x - x_min
    leaf_width = x_max - inner_x
    leaf_height = y_top - y_bottom
    if main_width <= tolerance or leaf_width <= tolerance:
        return None
    # A folha rotacionada deve ter a mesma largura transversal do fundo.
    if abs(leaf_width - height) > max(tolerance, height * 0.12):
        return None

    return {
        "main_width": round(main_width, 1),
        "leaf_width": round(leaf_width, 1),
        "leaf_height": round(leaf_height, 1),
        "drop_depth": round(y_base - y_bottom, 1),
        "side": "right",
    }
