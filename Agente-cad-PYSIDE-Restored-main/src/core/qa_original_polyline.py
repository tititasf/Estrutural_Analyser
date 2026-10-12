"""Read original planar DXF polyline vertices without tessellating curves."""


def original_polyline_xyb(entity):
    """Return (vertices, closed flag); unsupported 3D/mesh entities stay absent.

    OCS vertices are safe as XY only for the standard extrusion. Bulges remain
    attached to their original starting vertex so callers can reject curves.
    """
    kind = entity.dxftype()
    if tuple(entity.dxf.get('extrusion', (0, 0, 1))) != (0, 0, 1):
        return [], False
    if kind == 'LWPOLYLINE':
        return list(entity.get_points('xyb')), bool(entity.closed)
    if kind == 'POLYLINE' and entity.is_2d_polyline:
        return [(float(v.dxf.location.x), float(v.dxf.location.y),
                 float(v.dxf.get('bulge', 0))) for v in entity.vertices], bool(entity.is_closed)
    return [], False
