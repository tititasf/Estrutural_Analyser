"""Bind the approved Nova U assembly to physical SA walls, without changing N1."""
import math
from src.core.pillar_special_faces import physical_ring, special_u_face_segments


def u_nova_payload(pj):
    """Return an eight-face CCW contour with semantic, pose-independent caps.

    C/D are the two free ends. Numeric vertex indices belong only to the
    returned normalized ring; they are never inferred from the incoming order.
    """
    if not isinstance(pj, dict):
        return None
    nested = pj.get('n1_base')
    if not isinstance(nested, dict):
        contract = pj.get('_sa_mode_contract')
        nested = contract.get('n1_base', {}) if isinstance(contract, dict) else {}
    if not isinstance(nested, dict):
        nested = {}
    points = pj.get('geometry_points') or nested.get('geometry_points')
    ring = physical_ring(points)
    faces = special_u_face_segments(ring)
    if set(faces) != set('ABCDEFGH'):
        return None
    # The special drawing normalizes to CCW before consuming index metadata.
    area2 = sum(p[0]*ring[(i+1)%len(ring)][1] - ring[(i+1)%len(ring)][0]*p[1]
                for i, p in enumerate(ring))
    if area2 < 0:
        ring.reverse()
    names = {}
    for i, p in enumerate(ring):
        q = ring[(i+1)%len(ring)]
        matches = [name for name, face in faces.items()
                   if {tuple(face['p0']), tuple(face['p1'])} == {tuple(p), tuple(q)}]
        if len(matches) != 1:
            raise ValueError('U: ambiguous physical face binding')
        names[str(i)] = matches[0]
    caps = [i for i in range(len(ring)) if names[str(i)] in 'CD']
    return {
        'geometry_points': ring, 'face_names': names,
        'panel_end_cap_faces': caps, 'extended_grade_caps': caps,
        'metal_profile_faces': [i for i in range(len(ring)) if i not in caps],
        'inner_bolt_clearance_cm': 35,
        # The approved U uses the timber INSERT with its -90 degree rotation
        # baked in before sizing; raw block coordinates swap the half-piece axes.
        'wood_template_rotation_deg': -90,
    }


def n3_u_faces(pj, *, grades_only=False):
    """Consume each declared face panel independently; retain its physical size.

    Explicit panel widths are the conversion/ficha contract, not the contour's
    bounding box. A missing panel width uses the named physical edge. Assembly
    clearances are not inferred by copying the rectangular A/B formula to U.
    """
    payload = u_nova_payload(pj)
    if not payload:
        return []
    faces = special_u_face_segments(payload['geometry_points'])
    result = []
    for name in 'ABCDEFGH':
        face = faces[name]
        inner = math.dist(face['p0'], face['p1'])
        if grades_only and name in 'CD' and inner <= 40:
            continue
        widths = []
        for column in range(1, 4):
            try:
                width = float(pj.get(f'larg{column}_{name}') or 0)
            except (TypeError, ValueError):
                raise ValueError(f'U face {name}: invalid declared panel width')
            if not math.isfinite(width) or width < 0:
                raise ValueError(f'U face {name}: invalid declared panel width')
            widths.append(width)
        result.append({'id': name, 'panel': sum(widths) or inner, 'inner': inner})
    return result
