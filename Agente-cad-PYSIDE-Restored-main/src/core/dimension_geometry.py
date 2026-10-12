"""Internal dimension provenance. No CAD entities are removed or simplified."""
import math
from collections import defaultdict


def mark_exploded_circle_dimensions(entities):
    """Require concentric markers, two witness lines and a matching measurement.

    Layers, colors, drawing names and absolute marker sizes are not evidence.
    Independent polylines remain structural even when a dimension overlaps them.
    """
    centers = defaultdict(list)
    for circle in entities.get('circles', ()):
        x, y = circle['center'][:2]
        centers[(float(x), float(y))].append(float(circle['radius']))
    markers = [(x, y, max(rs)) for (x, y), rs in centers.items()
               if len(set(r for r in rs if r > 0)) >= 2]
    numbers = []
    for t in entities.get('texts', ()):
        try:
            value = float(str(t.get('text', '')).strip().replace(',', '.'))
            if value > 0:
                numbers.append((value, t))
        except (TypeError, ValueError):
            continue
    lines = entities.get('lines', ())
    geometry = []
    for i, line in enumerate(lines):
        pts = line.get('points') or [line.get('start'), line.get('end')]
        if len(pts) != 2 or not all(pts):
            continue
        x, y = pts[0][:2]
        dx, dy = pts[1][0] - x, pts[1][1] - y
        length = math.hypot(dx, dy)
        if length > 0:
            geometry.append((i, x, y, dx / length, dy / length, length))
    excluded = set()
    for i, x, y, ux, uy, length in geometry:
        anchors = []
        for mx, my, radius in markers:
            a = (mx - x) * ux + (my - y) * uy
            transverse = abs((mx - x) * uy - (my - y) * ux)
            if transverse <= radius * .1 and -radius * .1 <= a <= length + radius * .1:
                witnesses = []
                for j, wx, wy, vx, vy, wl in geometry:
                    if i == j or abs(ux * vx + uy * vy) > .01:
                        continue
                    wa = (mx - wx) * vx + (my - wy) * vy
                    wt = abs((mx - wx) * vy - (my - wy) * vx)
                    if (wt <= radius * .1 and wl > radius * 8
                            and radius * .5 <= min(wa, wl - wa) <= radius * 6):
                        witnesses.append(j)
                if witnesses:
                    anchors.append((a, mx, my, radius, witnesses))
        anchors.sort()
        for left, right in zip(anchors, anchors[1:]):
            distance = right[0] - left[0]
            radius = max(left[3], right[3])
            if distance <= radius * 2:
                continue
            for value, t in numbers:
                # Numeric units must match the CAD measurement; ambiguous units
                # are deliberately left unresolved rather than deleting walls.
                if abs(value - distance) > max(distance * .002, radius * .15):
                    continue
                tx, ty = t['pos'][:2]
                height = float(t.get('height') or radius * 4)
                angle = math.radians(float(t.get('rotation') or 0))
                if abs(math.cos(angle) * ux + math.sin(angle) * uy) < .99:
                    continue
                ta = (tx - x) * ux + (ty - y) * uy
                tt = abs((tx - x) * uy - (ty - y) * ux)
                if left[0] - height * 3 <= ta <= right[0] + height * 3 and tt <= height * 2:
                    t['annotation_role'] = 'dimension'
                    t['dimension_evidence'] = 'concentric_markers_witnesses_measurement'
                    excluded.add(i)
                    excluded.update(left[4])
                    excluded.update(right[4])
                    break
    for i in excluded:
        lines[i]['annotation_role'] = 'dimension'
        lines[i]['dimension_evidence'] = 'concentric_markers_witnesses_measurement'
    return len(excluded)
