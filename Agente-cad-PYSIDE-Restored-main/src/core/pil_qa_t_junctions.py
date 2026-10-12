"""Original wall proof for a lateral T ending outside a continuous corridor."""
from __future__ import annotations


def capped_exterior_t(pa, pb, longitudinal, original_walls, *, axis,
                      positions, closed_handles, tolerance_cm):
    """The main wall may itself close the lateral; no redundant cap is needed.

    Caller must independently prove the lateral's name and numeric width.
    A crossing, partial endpoint or closed contour cannot supply this proof.
    """
    eps = tolerance_cm
    bottom, top = sorted(positions)
    tlo, thi = sorted((pa['pos'], pb['pos']))
    if thi-tlo <= eps or len(longitudinal) != 2:
        return False
    if any(w['axis'] == axis for w in (pa, pb)):
        return False
    if any(w['axis'] != axis for w in longitudinal):
        return False
    if not all(w['lo'] <= tlo+eps and w['hi'] >= thi-eps
               for w in longitudinal):
        return False
    for edge in (bottom, top):
        exterior = (
            abs(pa['lo']-edge) <= eps and abs(pb['lo']-edge) <= eps
            and edge >= top-eps and min(pa['hi'], pb['hi']) > edge+eps
        ) or (
            abs(pa['hi']-edge) <= eps and abs(pb['hi']-edge) <= eps
            and edge <= bottom+eps and max(pa['lo'], pb['lo']) < edge-eps
        )
        if exterior and any(
            w['axis'] == axis and w['handle'] not in closed_handles
            and abs(w['pos']-edge) <= eps
            and w['lo'] <= tlo+eps and w['hi'] >= thi-eps
            for w in original_walls
        ):
            return True
    return False
