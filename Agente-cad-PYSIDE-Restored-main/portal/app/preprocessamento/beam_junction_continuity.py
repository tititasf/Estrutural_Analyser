"""Derived continuity through a traced transverse beam; never redraw N1."""
from copy import deepcopy
from pathlib import Path
from shapely.geometry import LineString, Point, box

EPS = .1


def corner_junction(target, anchor, crossing, walls):
    """Prove four original own ends and four transverse corner wall ends."""
    a, b = target.bounds, anchor.bounds
    axis = 0 if b[2]-b[0] > b[3]-b[1] else 1
    other = 1-axis
    if any(abs(a[n]-b[n]) > EPS for n in (other, other+2)):
        return None
    low, high = a[other], a[other+2]
    if a[axis+2] <= b[axis]:
        start, end = a[axis+2], b[axis]
    elif b[axis+2] <= a[axis]:
        start, end = b[axis+2], a[axis]
    else:
        return None
    if end-start <= EPS:
        return None
    gap = box(start,low,end,high) if axis == 0 else box(low,start,high,end)
    if not crossing.buffer(EPS).covers(gap):
        return None
    cb = crossing.bounds
    if abs(cb[axis]-start)>EPS or abs(cb[axis+2]-end)>EPS:
        return None
    def world(along, across):
        return (along,across) if axis == 0 else (across,along)
    handles=set()
    for across in (low,high):
        for along, fund in ((start, target if a[axis+2]<=b[axis] else anchor),
                            (end, anchor if a[axis+2]<=b[axis] else target)):
            corner=Point(world(along,across))
            own=[]; transverse=[]
            fb=fund.bounds; length=fb[axis+2]-fb[axis]
            for wall in walls:
                line=LineString([wall['a'],wall['b']])
                dx=abs(wall['a'][0]-wall['b'][0]);dy=abs(wall['a'][1]-wall['b'][1])
                direction=0 if dx>dy else 1
                if (min(corner.distance(Point(wall['a'])),corner.distance(Point(wall['b'])))>EPS
                        or min(dx,dy)>EPS):
                    continue
                if direction==axis and line.intersection(fund.boundary.buffer(EPS)).length>=length-2*EPS:
                    own.append(wall['handle'])
                if direction==other and line.length>=max(10,high-low):
                    # The transverse source edge must leave the intersection,
                    # not a short annotation line drawn inside it.
                    outward = wall['b'][other] if Point(wall['a']).distance(corner)<=EPS else wall['a'][other]
                    if (across==low and outward<low-EPS) or (across==high and outward>high+EPS):
                        transverse.append(wall['handle'])
            if not own or not transverse:
                return None
            handles.update(own+transverse)
    return dict(axis=axis,gap_cm=end-start,source_entity_handles=sorted(handles))


def measured_readings(fund, geom, cuts):
    from .cut_level_scope import for_fund
    from .segment_levels import cut_matches_fund
    candidates=[for_fund(f,geom,fund.get('height_cm')) for g,f in cuts if g.distance(geom)<=1.]
    if any(f and f.get('status')=='conflict' for f in candidates):
        return []
    candidates=[f for f in candidates if f and f.get('value') is not None]
    if not candidates or max(f['value'] for f in candidates)-min(f['value'] for f in candidates)>.0025:
        return []
    return [f for f in candidates if f.get('status') not in ('estimated','unknown','conflict','candidate')
        and (f.get('cut_height_evidence') or {}).get('beam_name')==fund.get('beam_name')
        and (f.get('cut_height_evidence') or {}).get('height_cm')==fund.get('height_cm')
        and cut_matches_fund(f.get('cut_profile_geometry'),geom,fund.get('height_cm'),f.get('cut_height_evidence'))]


def propagate_junctions(funds, all_funds, records, shapes, cuts, source, paints, inherit, sync):
    if not source or paints is None:
        return
    from .oriented_beam_section import _source_evidence
    from .segment_levels import geometry
    try:
        path=Path(source);stat=path.stat()
        _,walls=_source_evidence(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
    except (OSError,ValueError,TypeError):
        return
    frozen=deepcopy(records)
    for target in funds:
        uid=target['segment_id'];current=frozen[uid];tg=shapes.get(uid)
        if (tg is None or tg.geom_type!='Polygon' or current.get('status') in ('human_review','conflict')
                or current.get('method')=='cut_geometry_on_fv' or target.get('height_cm') is None):
            continue
        proofs=[]
        for anchor in funds:
            if anchor is target or anchor.get('beam_name')!=target.get('beam_name'):
                continue
            ag=shapes.get(anchor['segment_id'])
            if ag is None or anchor.get('height_cm')!=target['height_cm']:
                continue
            anchors=measured_readings(anchor,ag,cuts)
            if not anchors:
                continue
            for cross in all_funds:
                if cross.get('beam_name') in (None,target.get('beam_name')) or cross.get('height_cm')!=target['height_cm']:
                    continue
                cg=geometry(cross.get('points'))
                if cg is None or cg.geom_type!='Polygon':
                    continue
                proof=corner_junction(tg,ag,cg,walls)
                if not proof or any(p.intersection(g.buffer(-.25)).area>2 for p in paints for g in (tg,ag,cg)):
                    continue
                crossings=measured_readings(cross,cg,cuts)
                for own in anchors:
                    for other in crossings:
                        if (not own.get('datum_id') or own.get('datum_id')!=other.get('datum_id')
                                or not own.get('unit') or own.get('unit')!=other.get('unit')
                                or current.get('datum_id')!=own['datum_id'] or current.get('unit')!=own['unit']
                                or abs(own['value']-other['value'])>.0025):
                            continue
                        proofs.append((own,other,{**proof,'crossing_beam':cross['beam_name'],
                            'anchor_segment_id':anchor['segment_id']}))
        if not proofs or max(a['value'] for a,_,_ in proofs)-min(a['value'] for a,_,_ in proofs)>.0025:
            continue
        own,other,proof=max(proofs,key=lambda row:min(row[0]['confidence_pct'],row[1]['confidence_pct']))
        result=inherit(current,[own,other],'measured_four_corner_beam_junction',.9,value=own['value'],
            junction_proof=proof,previous_level_evidence=deepcopy(current),
            section_height_authority=deepcopy(own['cut_height_evidence']))
        records[uid].update(result);sync(target,records[uid])
