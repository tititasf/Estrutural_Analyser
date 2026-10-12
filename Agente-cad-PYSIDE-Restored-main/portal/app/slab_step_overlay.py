"""Local slab transition sections derived from measured region levels."""
from math import hypot, isfinite


def step_drawing(slab, step):
    from shapely.geometry import Point, Polygon

    def number(key):
        value = step.get(key)
        if value is None or not isfinite(float(value)):
            raise ValueError(f'degrau de laje: {key} ausente')
        return float(value)

    height, owner_height = number('height_cm'), number('owner_height_cm')
    level, owner_level = number('level_m'), number('owner_level_m')
    if min(height, owner_height) <= 0:
        raise ValueError('degrau de laje: espessura inválida')
    owner, region = Polygon(slab.get('points') or []), Polygon(step.get('points') or [])
    if not owner.is_valid or not region.is_valid:
        raise ValueError('degrau de laje: contorno inválido')
    principal = owner
    for neighbor in slab.get('slab_steps') or []:
        if neighbor.get('points'):
            principal = principal.difference(Polygon(neighbor['points']))
    candidates = []
    points = list(region.exterior.coords)
    for a, b in zip(points, points[1:]):
        length = hypot(b[0]-a[0], b[1]-a[1])
        if length <= .1:
            continue
        anchor = [(a[i]+b[i])/2 for i in (0, 1)]
        tangent = [(b[i]-a[i])/length for i in (0, 1)]
        normal = [-tangent[1], tangent[0]]
        if not region.covers(Point([anchor[i]+normal[i]*.5 for i in (0, 1)])):
            normal = [-v for v in normal]
        # Select an actual internal edge, with region and principal slab on
        # opposite sides. Never use the external slab perimeter as a step.
        available = 25.
        for distance in (.5, 1., 2., 5., 10., 15., 20., 25.):
            inside = Point([anchor[i]+normal[i]*distance for i in (0, 1)])
            outside = Point([anchor[i]-normal[i]*distance for i in (0, 1)])
            if (not owner.buffer(.15).covers(inside) or not owner.buffer(.15).covers(outside)
                    or not region.covers(inside) or not principal.covers(outside)):
                available = distance/2
                break
        if available >= 1:
            candidates.append((available, length, anchor, tangent, normal))
    if not candidates:
        raise ValueError('degrau de laje: transição interna sem espaço confirmado')
    half, _, anchor, tangent, normal = max(candidates, key=lambda row: row[:2])
    # Elevation must point upwards in CAD coordinates, independently of the
    # winding of the region boundary. Otherwise a correct datum is displayed
    # upside down (a top step appears as a soffit step).
    if tangent[1] < -.001 or (abs(tangent[1]) <= .001 and tangent[0] > 0):
        tangent = [-v for v in tangent]
    bottom = (level-owner_level)*100 + owner_height-height
    top = bottom+height
    center = (min(0., bottom)+max(owner_height, top))/2

    def world(t, z):
        return [anchor[i]+normal[i]*t+tangent[i]*(z-center) for i in (0, 1)]

    outline = [world(-half, 0), world(0, 0), world(0, bottom),
               world(half, bottom), world(half, top), world(0, top),
               world(0, owner_height), world(-half, owner_height)]
    primitives = [dict(kind='polygon', points=outline, color='#ffe033')]

    def readable(vector):
        return [-v for v in vector] if vector[0] < -.001 or (abs(vector[0]) <= .001 and vector[1] < 0) else vector

    def text_at(point, vector, text, size, **extra):
        direction = readable(vector)
        primitives.append(dict(kind='text', points=[point, [point[i]+direction[i] for i in (0, 1)]],
                               text=text, size=size, color='#ffffff', **extra))

    def dimension(t, lo, hi, value):
        primitives.append(dict(kind='line', points=[world(t, lo), world(t, hi)], color='#fff38c'))
        for z in (lo, hi):
            primitives.append(dict(kind='line', points=[world(t-1, z-1), world(t+1, z+1)], color='#fff38c'))
        text_at(world(t+2, (lo+hi)/2), tangent, f'{value:.1f}'.rstrip('0').rstrip('.'), 5)

    dimension(-half/2, 0, owner_height, owner_height)
    dimension(half/2, bottom, top, height)
    title = world(0, max(owner_height, top)+10)
    text_at(title, normal, f"{slab['name']} · Degrau de laje", 8, role='section_title')
    return dict(anchor=anchor, points=outline, primitives=primitives,
                confidence='high', section_kind='slab_step',
                levels_m=dict(region=level, principal=owner_level),
                heights_cm=dict(region=height, principal=owner_height),
                source='slab_region_levels_and_internal_boundary')


def missing_drawings(state):
    sections, blocked = [], []
    for slab in state.get('slabs') or []:
        for step in slab.get('slab_steps') or []:
            if step.get('sections') or not step.get('uid'):
                continue
            try:
                drawing = step_drawing(slab, step)
                sections.append(dict(slab=slab['name'], step_uid=step['uid'], drawing=drawing))
            except (ValueError, TypeError) as exc:
                blocked.append(dict(slab=slab.get('name'), step_uid=step['uid'], reason=str(exc)))
    return sections, blocked
