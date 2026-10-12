"""Conservative proof that a nearby dimension labels only part of a section."""


def partial_height_dimension(points, direction, label, lines):
    """Return traced 1:1 partial dimension evidence; unknown drawings stay unknown.

    Require a dimension baseline and both perpendicular extension lines. A
    numeric text merely near a section is insufficient to identify its role.
    Whole-span dimensions (including scaled ones) are never rejected here.
    """
    if not points or not label or direction not in ('Norte', 'Sul', 'Leste', 'Oeste'):
        return None
    axis = 0 if direction in ('Norte', 'Sul') else 1
    cross = 1 - axis
    try:
        value = float(str(label['text']).replace(',', '.'))
        position = tuple(map(float, label['pos'][:2]))
        lo = min(float(p[axis]) for p in points)
        hi = max(float(p[axis]) for p in points)
        dimension_lines = [line for line in lines if str(line.get('layer')) == '9']
        for baseline in dimension_lines:
            start, end = baseline['start'], baseline['end']
            if abs(start[cross] - end[cross]) > 0.1:
                continue
            a, b = sorted((float(start[axis]), float(end[axis])))
            ordinate = float(start[cross])
            if not (a <= position[axis] <= b and abs(position[cross] - ordinate) <= 12):
                continue
            if not (lo - .1 <= a < b <= hi + .1 and hi - lo - (b - a) > .25):
                continue
            if abs(value - (b - a)) > .25:
                continue
            extensions = []
            for endpoint in (a, b):
                match = next((line for line in dimension_lines
                    if abs(line['start'][axis] - endpoint) <= .1
                    and abs(line['end'][axis] - endpoint) <= .1
                    and abs(line['start'][cross] - line['end'][cross]) > 2
                    and min(line['start'][cross], line['end'][cross]) - .1 <= ordinate
                    <= max(line['start'][cross], line['end'][cross]) + .1), None)
                if match is None:
                    break
                extensions.append(match.get('handle'))
            if len(extensions) == 2:
                return dict(value=value, span=b-a, section_span=hi-lo, axis=axis,
                            baseline_handle=baseline.get('handle'),
                            extension_handles=extensions, text_handle=label.get('handle'))
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return None
