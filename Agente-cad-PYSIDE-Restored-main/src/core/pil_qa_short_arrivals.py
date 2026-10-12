"""Positive geometry evidence for short original arrivals, never section approval.

The normal name/section reader needs a useful longitudinal span. A short pair
can still prove face distances. It cannot prove a beam identity or its height.
"""


def short_original_arrival(walls, *, axis, face_coordinates, anchor,
                           direction, closed_handles, tolerance_cm,
                           minimum_span_cm=10.0):
    """Return one independent short exterior pair, or abstain on ambiguity.

Inputs are original structural walls after annotation exclusion. Closed
contours, arbitrary gaps, and projections behind the face cannot supply walls.
The caller must keep the contact uncertain until identity and B/H are proved.
"""
    if axis not in ('x', 'y') or direction not in (-1, 1):
        return None
    eps = tolerance_cm
    left, right = face_coordinates
    low, high = sorted((left, right))
    if eps <= 0 or high-low <= eps or minimum_span_cm <= eps:
        return None
    candidates = []
    for wall in walls:
        handles = set(wall['handles'])
        if wall['axis'] != axis or not handles or handles & set(closed_handles):
            continue
        if not low-eps <= wall['pos'] <= high+eps:
            continue
        if not wall['lo']-eps <= anchor <= wall['hi']+eps:
            continue
        lo, hi = ((max(anchor, wall['lo']), wall['hi']) if direction > 0
                  else (wall['lo'], min(anchor, wall['hi'])))
        if hi-lo > eps:
            candidates.append(dict(wall, lo=lo, hi=hi))
    pairs = []
    for i, a in enumerate(candidates):
        for b in candidates[i+1:]:
            bottom, top = sorted((a['pos'], b['pos']))
            span = (max(a['lo'], b['lo']), min(a['hi'], b['hi']))
            if top-bottom <= eps or span[1]-span[0] <= eps:
                continue
            pairs.append((a, b, bottom, top, span))
    # A long or competing pair must go through the normal independent reader.
    if len(pairs) != 1:
        return None
    a, b, bottom, top, span = pairs[0]
    if span[1]-span[0] >= minimum_span_cm:
        return None
    return dict(
        status='geometry_only', kind='original_short_arrival',
        wall_handles=sorted(set(a['handles']) | set(b['handles'])),
        wall_pair_positions=[bottom, top], original_span=list(span),
        width_cm=top-bottom,
        dist_esq_cm=bottom-low if left < right else high-top,
        dist_dir_cm=high-top if left < right else bottom-low,
        identity_proved=False, section_proved=False,
    )
