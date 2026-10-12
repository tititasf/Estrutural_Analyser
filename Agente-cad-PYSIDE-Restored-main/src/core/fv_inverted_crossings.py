"""Effective FV continuations below confirmed inverted crossings.

Source N1 remains immutable. A continuation needs both actual structural walls,
local absolute levels, and complete inverted coverage of the added footprint.
It stops at the far face, never beyond the measured crossing.
"""
from copy import deepcopy
from functools import lru_cache
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union


@lru_cache(maxsize=4)
def structural_lines_from_dxf(path, revision):
    import ezdxf
    from .lv_beam_scene import split_dimension_geometry
    document=ezdxf.readfile(path)
    lines=[dict(start=list(e.dxf.start)[:2],end=list(e.dxf.end)[:2],layer=e.dxf.layer)
           for e in document.modelspace().query('LINE')]
    texts=[dict(text=e.dxf.text if e.dxftype()=='TEXT' else e.plain_text(),
                pos=list(e.dxf.insert)[:2]) for e in document.modelspace().query('TEXT MTEXT')]
    structural,_=split_dimension_geometry(lines,texts)
    return tuple(structural)


def _buffered_footprint(footprint, distance=.1):
    # Same footprints are tested for every row and end; buffering dominates.
    return _buffered_footprint_cached(tuple(tuple(map(float, p[:2])) for p in footprint), distance)


@lru_cache(maxsize=8192)
def _buffered_footprint_cached(footprint, distance):
    return Polygon(footprint).buffer(distance)


def extend_normal_soffit(row, entries, structural_lines, pillars=()):
    points = row.get('points') or []
    if len(points) < 4 or row.get('geometry_validated') or row.get('validated'):
        return deepcopy(row)
    polygon = Polygon(points)
    if not polygon.is_valid:
        return deepcopy(row)
    x0,y0,x1,y1 = polygon.bounds
    horizontal = x1-x0 >= y1-y0
    axis = 0 if horizontal else 1
    low,high = (x0,x1) if horizontal else (y0,y1)
    across_low,across_high = (y0,y1) if horizontal else (x0,x1)
    if abs(polygon.area-(high-low)*(across_high-across_low)) > .05:
        return deepcopy(row)
    name = str(row.get('beam_name') or '').upper()
    result = deepcopy(row)
    changed = False
    for end,sign in ((low,-1),(high,1)):
        inside = [end-sign*.2,(across_low+across_high)/2]
        if not horizontal:
            inside.reverse()
        owners = [e for e in entries if str(e.get('beam') or '').upper()==name
                  and any(len(p.get('footprint') or [])>=3 and
                          _buffered_footprint(p['footprint']).covers(Point(inside))
                          for p in e.get('pairs') or [])]
        if not owners or any(e.get('pending') for e in owners):
            continue
        contracts = [e.get('section_contract') or {} for e in owners]
        if any(c.get('beam_type')=='inverted' or c.get('base_level_m') is None
               or c.get('top_level_m') is None for c in contracts):
            continue
        signatures = {(c['base_level_m'],c['top_level_m']) for c in contracts}
        if len(signatures)!=1:
            continue
        own_base = contracts[0]['base_level_m']
        candidates = {}
        for entry in entries:
            c = entry.get('section_contract') or {}
            if (entry.get('pending') or c.get('beam_type')!='inverted'
                or not (c.get('section_semantics') or {}).get('confirmed')
                or c.get('base_level_m') is None or own_base >= c['base_level_m']-.005):
                continue
            for pair in entry.get('pairs') or []:
                footprint = pair.get('footprint') or []
                if len(footprint)<3:
                    continue
                shape = Polygon(footprint)
                bounds = shape.bounds
                a,b = (bounds[0],bounds[2]) if horizontal else (bounds[1],bounds[3])
                near,far = (a,b) if sign>0 else (b,a)
                if abs(near-end)>.15 or sign*(far-end)<=.01:
                    continue
                # Reject a parallel beam, not just a coincident end coordinate.
                direction = [pair['end'][i]-pair['start'][i] for i in (0,1)]
                if abs(direction[axis])>.1:
                    continue
                key = (str(entry.get('beam')),round(far,4))
                candidates.setdefault(key,[]).append(shape)
        valid = []
        for (incident,far),shapes in candidates.items():
            lo,hi = sorted((end,far))
            added = box(lo,across_low,hi,across_high) if horizontal else box(across_low,lo,across_high,hi)
            if added.difference(unary_union(shapes).buffer(.05)).area>.05:
                continue
            uncertain=False
            for entry in entries:
                if str(entry.get('beam'))!=incident:
                    continue
                c=entry.get('section_contract') or {}
                if not any(len(p.get('footprint') or [])>=3 and
                           Polygon(p['footprint']).intersection(added).area>.05
                           for p in entry.get('pairs') or []):
                    continue
                if (entry.get('pending') or c.get('beam_type')!='inverted'
                    or not (c.get('section_semantics') or {}).get('confirmed')
                    or c.get('base_level_m') is None or own_base>=c['base_level_m']-.005):
                    uncertain=True
            if uncertain:
                continue
            # A support whose far face is exactly this measured endpoint is
            # an arrival, not permission to shorten the bottom to the near
            # face. Never pass beyond a support extending past the endpoint.
            blocked=False
            for pillar in pillars:
                if len(pillar.get('points') or [])<3:
                    continue
                support=Polygon(pillar['points'])
                if support.intersection(added).area<=.05:
                    continue
                bound=support.bounds[axis+2] if sign>0 else support.bounds[axis]
                if sign*(bound-far)>.15:
                    blocked=True
            if blocked:
                continue
            # Structural lines, already stripped of loose CAD dimensions.
            def wall_proves(across):
                spans = []
                for xa,ya,xb,yb in structural_lines:
                    a,b = ([xa,ya],[xb,yb])
                    if abs(a[1-axis]-across)>.15 or abs(b[1-axis]-across)>.15:
                        continue
                    spans.append(sorted((a[axis],b[axis])))
                cursor=lo
                for a,b in sorted(spans):
                    if b<cursor:
                        continue
                    if a>cursor+.15:
                        break
                    cursor=max(cursor,b)
                return cursor>=hi-.15
            if all(wall_proves(a) for a in (across_low,across_high)):
                valid.append((incident,far))
        if len(valid)!=1:
            continue
        incident,far=valid[0]
        changed = True
        # Do not conceal an overlapping panel of the same beam; callers check
        # other source rows before accepting this proposed continuation.
        result['points'] = [[far if i==axis and abs(float(p[i])-end)<.15 else float(p[i])
                             for i in (0,1)] for p in result['points']]
        result.setdefault('normal_inverted_continuations',[]).append(dict(
            incident_beam=incident, from_station_cm=end, to_station_cm=far,
            source='confirmed_inverted_levels_and_two_structural_walls'))
    if changed:
        bounds=Polygon(result['points']).bounds
        result['length']=bounds[axis+2]-bounds[axis]
        result.setdefault('ficha',{})['comprimento_total_fundo']=result['length']
        result['measure_source']='normal_soffit_below_inverted_crossing'
    return result


def reconcile_state(state, inventory, structural_lines, protected_uids=()):
    result=deepcopy(state)
    originals=(state.get('segmentos') or {}).get('fundo') or []
    rows=[]
    for row in originals:
        if row.get('uid') in protected_uids:
            rows.append(deepcopy(row))
            continue
        proposed=extend_normal_soffit(row,inventory.get('physical_entries') or [],structural_lines,state.get('pilares') or [])
        if proposed.get('normal_inverted_continuations'):
            added=Polygon(proposed['points']).difference(Polygon(row['points']))
            if any(other.get('uid')!=row.get('uid') and other.get('beam_name')==row.get('beam_name')
                   and len(other.get('points') or [])>=3
                   and Polygon(other['points']).intersection(added).area>.05 for other in originals):
                proposed=deepcopy(row)
        rows.append(proposed)
    # Two opposite ends can independently claim the same crossing gap.
    # Source rows alone cannot reveal that conflict; evaluate all proposals
    # together and retain the source geometry for both ambiguous arrivals.
    conflicts=set()
    for index,row in enumerate(rows):
        if not row.get('normal_inverted_continuations'):
            continue
        for other_index,other in enumerate(rows):
            if other_index<=index or other.get('beam_name')!=row.get('beam_name'):
                continue
            if len(other.get('points') or [])>=3 and Polygon(row['points']).intersection(Polygon(other['points'])).area>.05:
                conflicts.update((index,other_index))
    for index in conflicts:
        rows[index]=deepcopy(originals[index])
    # Opposite arrivals are one continuous bottom when BOTH ends independently
    # prove the same non-blocking crossing. Merge their owners instead of
    # publishing two overlapping continuations or dropping the crossing gap.
    rows = merge_opposite_arrivals(rows, inventory.get('physical_entries') or [],
                                   structural_lines, state.get('pilares') or [], protected_uids)
    result.setdefault('segmentos',{})['fundo']=rows
    return result


def merge_opposite_arrivals(rows, entries, structural_lines, pillars=(), protected_uids=()):
    def identity(row):
        uid = str(row.get('uid') or '').split('|')
        return row.get('beam_identity') or (uid[1] if len(uid)>1 else None)
    result = deepcopy(rows)
    # Rows are never mutated in place here; a merge replaces them with new
    # objects. Keep the row with its extension so a reused id cannot alias.
    extended = {}
    def extension(row):
        cached = extended.get(id(row))
        if cached is None or cached[0] is not row:
            cached = extended[id(row)] = (row, extend_normal_soffit(row,entries,structural_lines,pillars))
        return cached[1]
    while True:
        candidates = []
        for i, first in enumerate(result):
            if first.get('uid') in protected_uids or first.get('validated') or first.get('geometry_validated'):
                continue
            a = Polygon(first.get('points') or [])
            if not a.is_valid or a.area <= 0:
                continue
            axis = 0 if a.bounds[2]-a.bounds[0] >= a.bounds[3]-a.bounds[1] else 1
            for j in range(i+1, len(result)):
                second = result[j]
                if (second.get('uid') in protected_uids or second.get('validated') or second.get('geometry_validated')
                    or second.get('beam_name') != first.get('beam_name')
                    or identity(second) != identity(first)
                    or str(second.get('width')) != str(first.get('width'))):
                    continue
                b = Polygon(second.get('points') or [])
                if not b.is_valid or b.area <= 0 or a.intersection(b).area > .05:
                    continue
                left,right = (first,second) if a.bounds[axis] < b.bounds[axis] else (second,first)
                lp,rp = Polygon(left['points']),Polygon(right['points'])
                if any(abs(lp.bounds[k]-rp.bounds[k]) > .05 for k in (1-axis,3-axis)):
                    continue
                near,far = lp.bounds[axis+2],rp.bounds[axis]
                if far-near <= .15:
                    continue
                le = extension(left)
                re = extension(right)
                lc = [c for c in le.get('normal_inverted_continuations',[]) if abs(c['from_station_cm']-near)<.15 and abs(c['to_station_cm']-far)<.15]
                rc = [c for c in re.get('normal_inverted_continuations',[]) if abs(c['from_station_cm']-far)<.15 and abs(c['to_station_cm']-near)<.15]
                if len(lc)!=1 or len(rc)!=1 or lc[0]['incident_beam']!=rc[0]['incident_beam']:
                    continue
                gap = Polygon(le['points']).difference(lp)
                if any(len(p.get('points') or [])>=3 and Polygon(p['points']).intersection(gap).area>.05 for p in pillars):
                    continue
                union = unary_union([lp,rp,gap])
                if union.geom_type!='Polygon' or any(k not in (i,j) and
                    other.get('beam_name')==first.get('beam_name') and len(other.get('points') or [])>=3
                    and Polygon(other['points']).intersection(union).area>.05 for k,other in enumerate(result)):
                    continue
                # Width/depth transitions remain distinct even if their bottoms
                # happen to pass below the same inverted beam.
                contracts=[]
                for original,shape in ((left,lp),(right,rp)):
                    local=[e for e in entries if e.get('beam')==original.get('beam_name') and
                           any(len(p.get('footprint') or [])>=3 and Polygon(p['footprint']).intersection(shape).area>.05 for p in e.get('pairs') or [])]
                    contracts.extend(e.get('section_contract') or {} for e in local)
                if not contracts or len({(c.get('width_cm'),c.get('height_cm')) for c in contracts})!=1:
                    continue
                if any(c.get('width_cm') is None or c.get('height_cm') is None for c in contracts):
                    continue
                levels = {str(r.get('level') or '') for r in (left,right)}
                if len(levels)>1 and any(r.get('level_source')=='explicit_beam_or_side' or r.get('level_evidence_fields') for r in (left,right)):
                    continue
                merged=deepcopy(left)
                merged.update(points=[list(p) for p in union.exterior.coords],
                              length=union.bounds[axis+2]-union.bounds[axis],
                              measure_source='continuous_normal_soffit_below_inverted_crossing')
                merged.setdefault('ficha',{})['comprimento_total_fundo']=merged['length']
                sources=[s for r in (left,right) for s in r.get('merged_source_uids',[r.get('uid')])]
                merged['merged_source_uids']=sources
                merged['normal_inverted_continuations']=lc
                merged['merged_source_segments']=[s for r in (left,right) for s in r.get('merged_source_segments',[dict(uid=r.get('uid'),segment_index=r.get('segment_index') or r.get('segment_label'),level=r.get('level'),level_source=r.get('level_source'),points=deepcopy(r['points']))])]
                if len(levels)>1:
                    merged.update(level='',level_source='unresolved_local_slab_references',
                                  level_slabs=sorted({s for r in (left,right) for s in r.get('level_slabs',[])}))
                    merged['attention']='Fundo contínuo: referências de nível das lajes diferem; nível da viga a confirmar.'
                    merged['atencao']=merged['attention']
                candidates.append((i,j,merged))
        # Reject branching claims rather than choosing by iteration order.
        unique=[c for c in candidates if not any(c is not d and set(c[:2]) & set(d[:2]) for d in candidates)]
        if not unique:
            return result
        removed={j for i,j,row in unique}
        replacements={i:row for i,j,row in unique}
        result=[replacements.get(i,row) for i,row in enumerate(result) if i not in removed]
