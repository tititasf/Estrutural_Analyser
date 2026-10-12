"""Reject a named contour only when its original label owns another pillar."""


def foreign_named_contour(contour_handle, labels, bindings):
    """Unknown or competing ownership remains a barrier, never an exclusion.

    Bindings must come from the original numeric pillar-section reader.
    A text merely contained in a rectangle does not bind that rectangle.
    """
    if not labels:
        return False
    for label in labels:
        owners={b['contour_handle'] for b in bindings
            if label['handle'] in b.get('name_handles',[]) and
            b.get('dimension_handles')}
        if len(owners)!=1 or contour_handle in owners:
            return False
    return True
