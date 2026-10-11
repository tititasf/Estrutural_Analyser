"""DXF evidence for internal slab thickness regions and their own sections.

Contours remain immutable. D-52 compares bottom elevations in metres, with
thickness in centimetres. Missing altitude is never replaced by the slab's
aggregate altitude (which may itself belong to the inset region).
"""
from functools import lru_cache, wraps
from threading import Lock
from pathlib import Path
import re
import json
import hashlib

from shapely.geometry import LineString, Point, Polygon, box

_HEIGHT = re.compile(r"^h\s*=\s*(\d+(?:[.,]\d+)?)$", re.I)
_LEVEL = re.compile(r"^[+-]?\d{2,4}[.,]\d{2,3}$")


@lru_cache(maxsize=16)
def _drawing(path, mtime_ns, size):
    import ezdxf
    doc = ezdxf.readfile(path)
    polygons, texts = [], []
    for e in doc.modelspace():
        kind = e.dxftype()
        if kind in ('TEXT', 'MTEXT'):
            raw = e.dxf.text if kind == 'TEXT' else e.plain_text()
            raw = raw.strip()
            h = _HEIGHT.fullmatch(raw)
            if h or _LEVEL.fullmatch(raw):
                texts.append(dict(handle=e.dxf.handle, position=list(e.dxf.insert)[:2],
                                  kind='height' if h else 'level',
                                  value=float((h.group(1) if h else raw).replace(',', '.'))))
        elif kind in ('LWPOLYLINE', 'POLYLINE'):
            if kind == 'LWPOLYLINE':
                # Curved boundaries require the contour tracer, not a chord.
                if any(abs(p[4]) > 1e-8 for p in e.get_points()):
                    continue
                pts = list(e.get_points('xy'))
                closed = e.closed
            else:
                pts = [list(v.dxf.location)[:2] for v in e.vertices]
                closed = e.is_closed
            if len(pts) < 4 or not (closed or pts[0] == pts[-1]):
                continue
            p = Polygon(pts)
            if not p.is_valid or p.area <= 0:
                continue
            color = e.dxf.color
            if color == 256:
                color = doc.layers.get(e.dxf.layer).dxf.color
            polygons.append(dict(handle=e.dxf.handle, points=pts, color=color))
    from src.core.dxf_loader import DXFLoader
    from src.core.cad_object_recognition import thickness_references
    data = DXFLoader.load_dxf(path)
    refs = thickness_references(data.get('texts', []),
                                data.get('lines', [])+data.get('polylines', []))
    original_heights = {tuple(round(v, 6) for v in t['position']): t
                        for t in texts if t['kind'] == 'height'}
    resolved = []
    for reference, value in refs:
        if reference.get('target_class') == 'foundation_block':
            continue
        source = reference.get('source_position', reference['pos'])
        original = original_heights.get(tuple(round(v, 6) for v in source))
        if original:
            resolved.append(dict(original, position=reference['pos']))
    return polygons, [t for t in texts if t['kind'] != 'height']+resolved


_STEP_NUMBER = re.compile(r"^\d{1,2}(?:[.,]\d+)?$")


@lru_cache(maxsize=16)
def _step_numbers(path, mtime_ns, size):
    """Plain small numbers (degrau escrito, ex. "3" junto ao corte B1D)."""
    import ezdxf
    rows = []
    for e in ezdxf.readfile(path).modelspace().query('TEXT MTEXT'):
        raw = (e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()).strip()
        if _STEP_NUMBER.fullmatch(raw):
            rows.append(dict(handle=e.dxf.handle, position=list(e.dxf.insert)[:2],
                             value=float(raw.replace(',', '.'))))
    return rows


def _written_step_section(points, region, numbers, tol=.2, reach=30.):
    """Flat-bottom section whose drawn top step equals a written number.

    The region has no h= of its own (14_PAV L406/96B, corte B1D): the section
    gives a continuous underside, a drawn step on the region boundary and the
    number written beside that step. Same convention as _flat_bottom_section:
    the continuous edge is the underside. Returns (top_drop_cm, number), the
    drop positive when the region top is lower, or None.
    """
    shape = Polygon(points)
    x0, y0, x1, y1 = shape.bounds
    if y1-y0 > x1-x0 or (x1-x0) < 3*(y1-y0):
        return None  # vertical: sem convenção de qual lado é o fundo
    stations = []
    for ratio in (.2, .35, .65, .8):
        v = x0+(x1-x0)*ratio
        hit = shape.intersection(LineString([(v, y0-1), (v, y1+1)]))
        if hit.geom_type != 'LineString' or hit.length <= 0:
            continue
        stations.append((region.buffer(.2).covers(hit.centroid), hit.bounds[1], hit.bounds[3]))
    inner = {(round(a, 3), round(b, 3)) for flag, a, b in stations if flag}
    outer = {(round(a, 3), round(b, 3)) for flag, a, b in stations if not flag}
    if len(inner) != 1 or len(outer) != 1:
        return None
    (a, b), (c, d) = inner.pop(), outer.pop()
    # Underside = the lower drawn edge, continuous across the step.
    if not (abs(a-c) < tol and abs(b-d) >= tol):
        return None
    drop = d-b
    step = shape.boundary.intersection(region.boundary)
    if step.is_empty:
        return None
    hits = [n for n in numbers if abs(n['value']-abs(drop)) <= tol and
            step.distance(Point(n['position'])) <= reach]
    return (round(drop, 3), hits[0]) if len(hits) == 1 else None


def _unique(rows, kind):
    values = {r['value'] for r in rows if r['kind'] == kind}
    return next(iter(values)) if len(values) == 1 else None


def _flat_bottom_section(points, region, height, owner_height):
    """Check both widths against h= and a continuous edge across the step.

    No T section is accepted: the transverse size must represent the slab
    thickness, and the two stations must lie on opposite sides of its region.
    """
    shape = Polygon(points)
    x0, y0, x1, y1 = shape.bounds
    vertical = y1-y0 > x1-x0
    narrow, long = (x1-x0, y1-y0) if vertical else (y1-y0, x1-x0)
    if narrow <= 0 or long < narrow * 3 or narrow > max(height, owner_height) * 2.1:
        return False
    # Use stations away from break symbols at the ends of the section.
    stations = []
    for ratio in (.2, .35, .65, .8):
        v = (y0+(y1-y0)*ratio) if vertical else (x0+(x1-x0)*ratio)
        line = LineString([(x0-1, v), (x1+1, v)] if vertical else [(v, y0-1), (v, y1+1)])
        hit = shape.intersection(line)
        if hit.geom_type != 'LineString' or hit.length <= 0:
            continue
        a, b = (hit.bounds[0], hit.bounds[2]) if vertical else (hit.bounds[1], hit.bounds[3])
        stations.append((region.buffer(.2).covers(hit.centroid), a, b))
    inner = [s for s in stations if s[0]]
    outer = [s for s in stations if not s[0]]
    for _, a, b in inner:
        for _, c, d in outer:
            scale = (b-a) / height
            if .25 <= scale <= 4 and abs((d-c)/owner_height-scale) < .03:
                if min(abs(a-c), abs(b-d)) < .2:
                    return True
    return False


def recognize_slabs(slabs, dxf_path):
    """Return derived metadata keyed by name; never change source geometry."""
    path = Path(dxf_path)
    stat = path.stat()
    outlines, texts = _drawing(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    striped = _striped_drawing(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    review_path = path.with_suffix('.slab-region-review.json')
    reviews = {}
    if review_path.is_file():
        review = json.loads(review_path.read_text(encoding='utf-8'))
        if review.get('source_sha256') == hashlib.sha256(path.read_bytes()).hexdigest():
            reviews = review.get('regions') or {}
    result = {}
    for slab in slabs:
        pts = slab.get('points') or []
        if len(pts) < 3:
            continue
        owner = Polygon(pts)
        if not owner.is_valid or owner.area <= 0:
            continue
        candidates = []
        for row in outlines:
            if row['color'] != 3:
                continue
            region = Polygon(row['points'])
            if not (0 < region.area < owner.area*.85 and owner.buffer(.5).covers(region)):
                continue
            inner = [t for t in texts if region.covers(Point(t['position']))]
            height = _unique(inner, 'height')
            if height is not None:
                candidates.append((row, region, inner, height))
        # Nested unrelated polygons cannot vote for the owner level.
        outside = [t for t in texts if owner.covers(Point(t['position'])) and
                   not any(p.covers(Point(t['position'])) for _, p, _, _ in candidates)]
        owner_height, owner_level = _unique(outside, 'height'), _unique(outside, 'level')
        steps = []
        for row, region, inner, height in candidates:
            if owner_height is None or abs(height-owner_height) < .01:
                continue
            level = _unique(inner, 'level')
            cuts = []
            for section in outlines:
                if section['color'] != 8:
                    continue
                shape = Polygon(section['points'])
                if (owner.buffer(.5).covers(shape) and
                        shape.intersects(region.boundary) and
                        _flat_bottom_section(section['points'], region, height, owner_height)):
                    cuts.append(section)
            method = 'direct_scoped_cad'
            inferred = False
            local_owner_level = owner_level
            evidence_checks = dict(contained_region=True, closed_cad_boundary=True, internal_height=True,
                principal_height=True, direct_internal_level=level is not None,
                direct_principal_level=local_owner_level is not None)
            if cuts and (level is None) != (local_owner_level is None):
                # Continuous underside plus two measured widths/h= establishes
                # the altitude delta; the section is not a contour source.
                if level is None:
                    level = round(local_owner_level+(height-owner_height)/100, 6)
                else:
                    local_owner_level = round(level+(owner_height-height)/100, 6)
                method, inferred = 'scoped_level_and_flat_bottom_section', True
            bottom = None if level is None else round(level-height/100, 6)
            owner_bottom = None if local_owner_level is None else round(local_owner_level-owner_height/100, 6)
            delta = None if bottom is None or owner_bottom is None else round(bottom-owner_bottom, 6)
            status = 'unknown' if delta is None else 'same_bottom' if abs(delta) <= .001 else 'different_bottom'
            ids = [row['handle'], *[t['handle'] for t in inner+outside], *[c['handle'] for c in cuts]]
            steps.append(dict(uid=f"slab-step:{slab['name']}:{row['handle']}",
                owner=slab['name'], points=row['points'], height_cm=height,
                owner_height_cm=owner_height, level_m=level, owner_level_m=local_owner_level,
                bottom_m=bottom, owner_bottom_m=owner_bottom, bottom_delta_m=delta,
                status=status, method=method,
                evidence_coverage_pct=100*sum(evidence_checks.values())/len(evidence_checks),
                evidence_checks=evidence_checks,
                evidence_handles=list(dict.fromkeys(ids)), sections=cuts,
                color='#ff4545' if status == 'different_bottom' else '#ffe033'))
        # Região sem h= próprio: só um corte com fundo contínuo e degrau
        # escrito junto ao degrau desenhado dá altura e desnível (B1D/96B).
        if owner_height is not None:
            numbers = _step_numbers(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
            for row in outlines:
                if row['color'] != 3 or any(row['handle'] == c[0]['handle'] for c in candidates):
                    continue
                region = Polygon(row['points'])
                if not (0 < region.area < owner.area*.85 and owner.buffer(.5).covers(region)):
                    continue
                if any(region.covers(Point(t['position'])) for t in texts):
                    continue
                if any(region.symmetric_difference(Polygon(s['points'])).area < .5 for s in steps):
                    continue
                found = []
                for section in outlines:
                    shape = Polygon(section['points'])
                    if (section['color'] == 8 and owner.buffer(.5).covers(shape)
                            and shape.intersects(region.boundary)):
                        hit = _written_step_section(section['points'], region, numbers)
                        if hit:
                            found.append((section, *hit))
                if len({round(f[1], 3) for f in found}) != 1:
                    continue
                drop = found[0][1]
                height = round(owner_height-drop, 6)
                level = None if owner_level is None else round(owner_level-drop/100, 6)
                bottom = None if level is None else round(level-height/100, 6)
                owner_bottom = None if owner_level is None else round(owner_level-owner_height/100, 6)
                ids = [row['handle'], *[t['handle'] for t in outside],
                       *[f[0]['handle'] for f in found], *[f[2]['handle'] for f in found]]
                steps.append(dict(uid=f"slab-step:{slab['name']}:{row['handle']}",
                    owner=slab['name'], points=row['points'], height_cm=height,
                    owner_height_cm=owner_height, level_m=level, owner_level_m=owner_level,
                    bottom_m=bottom, owner_bottom_m=owner_bottom,
                    bottom_delta_m=None if bottom is None else 0.,
                    status='unknown' if bottom is None else 'same_bottom',
                    method='flat_bottom_section_written_step', top_drop_cm=drop,
                    evidence_coverage_pct=100.,
                    evidence_checks=dict(contained_region=True, closed_cad_boundary=True,
                        internal_height=False, principal_height=True, direct_internal_level=False,
                        direct_principal_level=owner_level is not None, written_step=True,
                        flat_bottom_section=True),
                    evidence_handles=list(dict.fromkeys(ids)), sections=[f[0] for f in found],
                    color='#ffe033'))
        # Stripes signal attention even when altitude/cut evidence is absent.
        # A measured region already recognized above has precedence.
        from src.core.slab_regions import scoped_thickness
        seeds=[({'pos':t['position']},t['value']) for t in texts if t['kind']=='height']
        scope=scoped_thickness(owner,seeds,striped)
        if scope:
            for region in scope[1]:
                shape=Polygon(region['points'])
                if any(shape.symmetric_difference(Polygon(s['points'])).area < .5 for s in steps):
                    continue
                steps.append(dict(region, owner=slab['name']))
        if steps:
            apply_region_reviews(steps, reviews)
            result[slab['name']] = steps
    return result


@lru_cache(maxsize=16)
def _striped_drawing(path, mtime_ns, size):
    from src.core.dxf_loader import DXFLoader
    from src.core.slab_tracer import SlabTracer
    from src.core.slab_regions import striped_regions
    from src.core.spatial_index import SpatialIndex
    from shapely import set_precision
    data=DXFLoader.load_dxf(path)
    items=data.get('lines',[])+data.get('polylines',[])
    tracer=SlabTracer(SpatialIndex())
    _,_,rows=tracer._collect_laje_candidate_lines(items)
    structural=[set_precision(g,.001) for g,i in rows if i['support']=='structural'
                and (i['accepted'] or i['reasons']==['too_short'])]
    return striped_regions(items,structural)


def apply_region_reviews(steps, reviews):
    """Owner decisions are scoped by immutable contour UID and DXF revision."""
    for step in steps:
        review = reviews.get(step['uid']) or {}
        if review.get('same_bottom') is not True or not review.get('decision_id'):
            continue
        if step.get('height_cm') is None or step.get('owner_height_cm') is None:
            continue
        principal = review.get('principal_level_m', step.get('owner_level_m'))
        if principal is None and step.get('level_m') is not None:
            principal = step['level_m']+(step['owner_height_cm']-step['height_cm'])/100
        if principal is None:
            continue
        inner = round(principal+(step['height_cm']-step['owner_height_cm'])/100,6)
        # A decision cannot silently contradict a direct CAD altitude.
        checks=step['evidence_checks']
        if ((checks.get('direct_internal_level') and abs(step['level_m']-inner)>.0025) or
            (checks.get('direct_principal_level') and abs(step['owner_level_m']-principal)>.0025)):
            step['review_conflict']=review
            continue
        step.update(level_m=inner,owner_level_m=principal,
            bottom_m=round(inner-step['height_cm']/100,6),
            owner_bottom_m=round(principal-step['owner_height_cm']/100,6),
            bottom_delta_m=0.,status='same_bottom',method='owner_confirmed_scoped_same_bottom',
            owner_review=review)
        step['evidence_handles']=list(dict.fromkeys(step['evidence_handles']+['owner-review:'+review['decision_id']]))


def fill_region_levels(steps, regions):
    """Empty step/principal altitudes take the pre-SA region levels.

    Only a region the DXF reading left empty is filled; a direct CAD altitude
    or an owner decision always stays. Filled fields are listed so that the
    pre-processing never reads its own vote back as a measured step level.
    """
    principal = (regions.get('principal') or {}).get('value')
    for step in steps:
        filled = []
        inner = (regions.get(step.get('uid')) or {}).get('value')
        if step.get('level_m') is None and inner is not None:
            step['level_m'] = inner
            filled.append('level_m')
        if step.get('owner_level_m') is None and principal is not None:
            step['owner_level_m'] = principal
            filled.append('owner_level_m')
        if (step.get('level_m') is None and step.get('top_drop_cm') is not None
                and step.get('owner_level_m') is not None):
            # Degrau escrito no corte (B1D): o nível da região é derivado,
            # nunca a cópia do nível da laje.
            step['level_m'] = round(step['owner_level_m']-step['top_drop_cm']/100, 6)
            filled.append('level_m')
        if not filled:
            continue
        level, owner = step['level_m'], step['owner_level_m']
        # An h-only region has no level mark and no cut view indicating a level.
        # Copying the slab level onto it is not a different-level step, and the
        # thickness difference alone does not prove a different bottom.
        height_only = (not step.get('sections')
                       and not (step.get('evidence_checks') or {}).get('direct_internal_level')
                       and level is not None and owner is not None
                       and abs(level-owner) <= .0025)
        evidence = {k: regions[k] for k in (step.get('uid'), 'principal') if k in regions}
        if height_only:
            step.update(bottom_m=None, bottom_delta_m=None, status='unknown',
                        method='preprocess_layered_region_level', preprocess_filled=filled,
                        preprocess_region_evidence=evidence)
            step['color'] = '#ffe033'
            continue
        bottom = None if level is None or step.get('height_cm') is None else round(level-step['height_cm']/100, 6)
        owner_bottom = None if owner is None or step.get('owner_height_cm') is None else round(owner-step['owner_height_cm']/100, 6)
        delta = None if bottom is None or owner_bottom is None else round(bottom-owner_bottom, 6)
        step.update(bottom_m=bottom, owner_bottom_m=owner_bottom, bottom_delta_m=delta,
                    status='unknown' if delta is None else 'same_bottom' if abs(delta) <= .001 else 'different_bottom',
                    method='preprocess_layered_region_level', preprocess_filled=filled,
                    preprocess_region_evidence=evidence)
        step['color'] = '#ff4545' if step['status'] == 'different_bottom' else '#ffe033'


def _singleflight_regions(cached):
    locks = [Lock() for _ in range(32)]
    @wraps(cached)
    def shared(*args):
        # lru_cache allows duplicate concurrent misses. Serialize lookup for
        # each revision so publisher and viewer share one cold recognition.
        with locks[hash(args) % len(locks)]:
            return cached(*args)
    shared.cache_clear = cached.cache_clear
    shared.cache_info = cached.cache_info
    return shared


@_singleflight_regions
@lru_cache(maxsize=4)
def _cached_regions(serialized_slabs, path, source_revision, review_revision):
    return recognize_slabs(json.loads(serialized_slabs), path)


def enrich_state(state, dxf_path):
    """Re-detect contours, then refill only altitudes the DXF left empty.

    The portal snapshot keeps preprocess_region_levels and not the step
    geometry. A fresh recognition must not drop the region vote: the LV cut
    reads these steps and fails closed when a touched region has no level.
    """
    from copy import deepcopy
    path = Path(dxf_path).resolve()
    stat = path.stat() if path.is_file() else None
    review = path.with_suffix('.slab-region-review.json')
    review_stat = review.stat() if review.is_file() else None
    detected = deepcopy(_cached_regions(json.dumps(state.get('slabs', []), sort_keys=True),
        str(path), (stat.st_mtime_ns, stat.st_size),
        (review_stat.st_mtime_ns, review_stat.st_size) if review_stat else None)
        if stat else recognize_slabs(state.get('slabs', []), dxf_path))
    for slab in state.get('slabs', []):
        steps = detected.get(slab.get('name'), [])
        fill_region_levels(steps, slab.get('preprocess_region_levels') or {})
        slab['slab_steps'] = steps
    return state


def collect_sa_steps(slabs, dxf_path):
    """Supply scoped region evidence to SA before its level report is built.

    Only a uniquely evidenced principal altitude replaces an automatic value.
    Human level links/fields always win. Unknown regions remain explicit.
    """
    detected = recognize_slabs(slabs, dxf_path)
    for slab in slabs:
        steps = detected.get(slab.get('name'), [])
        fill_region_levels(steps, slab.get('preprocess_region_levels') or {})
        slab['slab_steps'] = steps
        links = slab.setdefault('links', {}).setdefault('laje_nivel', {})
        validated = slab.get('validated_fields') or []
        slots = (slab.get('validated_link_classes') or {}).get('laje_nivel') or []
        if ('laje_nivel' in validated or 'level' in validated or 'label' in slots or
                any(l.get('human') or l.get('validated') or l.get('source') == 'human'
                    for l in links.get('label', []) if isinstance(l, dict))):
            continue
        values = {s['owner_level_m'] for s in steps if s['owner_level_m'] is not None}
        if len(values) != 1:
            continue
        value = next(iter(values))
        ids = list(dict.fromkeys(h for s in steps for h in s['evidence_handles']))
        inferred = any(s['method'] != 'direct_scoped_cad' for s in steps)
        slab['level_before_region_scoping'] = slab.get('fields', {}).get('laje_nivel')
        slab.setdefault('fields', {})['laje_nivel'] = str(value)
        slab['laje_nivel'] = str(value)
        links['label'] = [dict(text=str(value), type='text', source='scoped_slab_principal_region',
            is_inferred=inferred, evidence_ids=['cad:'+h for h in ids])]
        slab['level_inference'] = dict(status='inferred' if inferred else 'observed',
            reason='scoped_slab_principal_region', value=value, evidence_ids=['cad:'+h for h in ids])
    return detected
