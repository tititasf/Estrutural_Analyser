"""Remove redundant closed edges from independently evidenced open walls."""


def independent_open_wall_candidates(walls, tolerance_cm):
    """A closed edge cannot create another pair where one open wall covers it.

    This does not join gaps, extend a wall, infer object ownership, or remove a
    closed edge with only partial coverage. The original open handle stays the
    evidence; the closed handle is never used to certify the open corridor.
    """
    eps = tolerance_cm
    return [wall for wall in walls if not (
        wall.get('closed_contour') and any(
            not other.get('closed_contour') and other['axis'] == wall['axis'] and
            abs(other['pos']-wall['pos']) <= eps and
            other['lo'] <= wall['lo']+eps and other['hi'] >= wall['hi']-eps
            for other in walls))]
