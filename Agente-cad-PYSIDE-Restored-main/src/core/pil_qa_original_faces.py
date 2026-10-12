"""Physical QA planes derived from the original closed CAD contour."""
import math
from src.core.qa_original_polyline import original_polyline_xyb

from src.core.pillar_special_faces import physical_ring, special_l_face_segments, special_u_face_segments


def original_special_face_planes(entity, *, tolerance_cm):
    vertices, closed = original_polyline_xyb(entity)
    if not vertices or any(p[2] for p in vertices):
        return {}
    points = [p[:2] for p in vertices]
    if not closed and (len(points) < 4 or math.dist(points[0], points[-1]) > tolerance_cm):
        return {}
    ring = physical_ring(points, collinear_tol_cm=tolerance_cm)
    # Resolve only established L/U topology from the original contour. Other
    # polygons and oblique edges stay unmeasured; no enclosing rectangle.
    if len(ring) not in (6, 8) or any(min(abs(a[0]-b[0]), abs(a[1]-b[1])) > tolerance_cm
                             for a,b in zip(ring, ring[1:]+ring[:1])):
        return {}
    segments = special_l_face_segments(ring) if len(ring) == 6 else special_u_face_segments(ring)
    return {fid: dict(edge) for fid, edge in segments.items()}
