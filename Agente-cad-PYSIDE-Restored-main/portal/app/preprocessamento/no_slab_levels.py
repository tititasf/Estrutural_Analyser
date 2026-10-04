"""Floor exit reference in CAD areas positively recognized as lacking a slab.

An unlabelled or unlevelled slab is never evidence of absence. Red crosses
and repeated stair treads are recorded with CAD handles, independently of levels.
"""
from collections import Counter
from shapely.geometry import LineString, box
from shapely.ops import unary_union

DECISION = 'NIV-SEM-LAJE-20261002'


def regions(context):
    if not context.get('tower_path'):
        return []
    import ezdxf
    doc = ezdxf.readfile(context['tower_path'])
    diagonals, treads, walls = [], {}, []
    for e in doc.modelspace():
        if e.dxftype() == 'LWPOLYLINE':
            color=e.dxf.get('color',256)
            if color==256:
                color=doc.layers.get(e.dxf.layer).dxf.color
            if color==3:
                pts=[tuple(p)[:2] for p in e.get_points()]
                if e.closed and pts:
                    pts.append(pts[0])
                for a,b in zip(pts,pts[1:]):
                    dx,dy=abs(a[0]-b[0]),abs(a[1]-b[1])
                    if (dx<.05 or dy<.05) and max(dx,dy)>80:
                        walls.append((LineString([a,b]),str(e.dxf.handle)))
        if e.dxftype() != 'LINE':
            continue
        a, b = tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]
        dx, dy = abs(a[0]-b[0]), abs(a[1]-b[1])
        color = e.dxf.get('color', 256)
        if color == 256:
            color = doc.layers.get(e.dxf.layer).dxf.color
        handle = str(e.dxf.handle)
        if color == 3 and (dx < .05 or dy < .05) and max(dx,dy)>80:
            walls.append((LineString([a,b]),handle))
        if color == 1 and dx > 30 and dy > 30:
            diagonals.append((LineString([a,b]), handle))
        # Only neutral stair strokes, not green walls or yellow dimension ticks.
        if color not in (7,8,9,250,251,252,253,254,255):
            continue
        if dy < .05 and 80 < dx < 250:
            key = ('h', round(min(a[0],b[0]),1), round(max(a[0],b[0]),1))
            treads.setdefault(key, []).append((a[1],handle))
        elif dx < .05 and 80 < dy < 250:
            key = ('v', round(min(a[1],b[1]),1), round(max(a[1],b[1]),1))
            treads.setdefault(key, []).append((a[0],handle))
    found = []
    for i,(a,ha) in enumerate(diagonals):
        for b,hb in diagonals[i+1:]:
            if not a.crosses(b) or max(abs(x-y) for x,y in zip(a.bounds,b.bounds)) > 1:
                continue
            found.append((box(*a.bounds), 'red_cross_no_slab', [ha,hb]))
    for (axis,lo,hi), rows in treads.items():
        rows = sorted(set(rows))
        runs, run = [], []
        for row in rows:
            if run and not 15 <= row[0]-run[-1][0] <= 40:
                runs.append(run); run=[]
            run.append(row)
        runs.append(run)
        for run in runs:
            if len(run) < 6:
                continue
            gaps = [b[0]-a[0] for a,b in zip(run,run[1:])]
            if max(gaps)-min(gaps) > 1:
                continue
            bounds = (lo,run[0][0],hi,run[-1][0]) if axis=='h' else (run[0][0],lo,run[-1][0],hi)
            area=box(*bounds)
            # Treads prove the stair; four enclosing structural walls prove its
            # cell, including the unhatched landing. Never expand by distance alone.
            cx,cy=area.centroid.coords[0]
            x1,y1,x2,y2=bounds
            left=[w for w in walls if abs(w[0].bounds[0]-w[0].bounds[2])<.05 and w[0].bounds[0]<=x1+1 and w[0].bounds[1]<=cy<=w[0].bounds[3]]
            right=[w for w in walls if abs(w[0].bounds[0]-w[0].bounds[2])<.05 and w[0].bounds[0]>=x2-1 and w[0].bounds[1]<=cy<=w[0].bounds[3]]
            down=[w for w in walls if abs(w[0].bounds[1]-w[0].bounds[3])<.05 and w[0].bounds[1]<=y1+1 and w[0].bounds[0]<=x2 and w[0].bounds[2]>=x1]
            up=[w for w in walls if abs(w[0].bounds[1]-w[0].bounds[3])<.05 and w[0].bounds[1]>=y2-1 and w[0].bounds[0]<=x2 and w[0].bounds[2]>=x1]
            handles=[h for _,h in run]
            if all((left,right,down,up)):
                selected=[max(left,key=lambda w:w[0].bounds[0]),min(right,key=lambda w:w[0].bounds[0]),
                          max(down,key=lambda w:w[0].bounds[1]),min(up,key=lambda w:w[0].bounds[1])]
                l,r,d,u=[w[0] for w in selected]
                candidate=box(l.bounds[0],d.bounds[1],r.bounds[0],u.bounds[1])
                edges=list(candidate.exterior.coords)
                perimeter=[LineString([a,b]) for a,b in zip(edges,edges[1:])]
                barriers=[w for w,_ in walls]
                for pillar in context.get('state',{}).get('pilares',[]):
                    pts=pillar.get('points') or []
                    if len(pts)>2:
                        barriers.append(LineString(pts+[pts[0]]))
                for fund in context.get('state',{}).get('segmentos',{}).get('fundo',[]):
                    pts=fund.get('points') or []
                    if len(pts)>2:
                        barriers.append(LineString(pts+[pts[0]]))
                boundary=unary_union(barriers).buffer(1)
                if candidate.area<=10*area.area and all(edge.difference(boundary).length<1 for edge in perimeter):
                    area=candidate
                    handles.extend(h for w,h in walls if w.intersects(candidate.boundary.buffer(1)))
            found.append((area, 'stair_tread_array', handles))
    return found


def floor_source(tower, slab_sources):
    ref = tower.get('reference') or {}
    if ref.get('status') == 'direct_local_reference' and ref.get('unit') == 'm' and ref.get('top') is not None:
        return dict(fact_id='floor-exit:'+str(ref.get('datum_id')), field='floor_exit_reference',
            value=ref['top'], status='sa_evidence', method='floor_exit_convention',
            datum_id=ref.get('datum_id'), confidence_pct=95,
            confidence_method='level_evidence_completeness_v1',
            confidence_components={'direct_floor_convention_support':95},
            evidence_ids=['cad:'+h for h in ref.get('evidence_handles',[])], warnings=[],
            owner_decision=DECISION)
    # One vote per slab, never per segment/region. Require an unambiguous majority.
    candidates = [s for s in slab_sources.values() if s.get('value') is not None
                  and s['status'] not in ('unknown','conflict','candidate','estimated')]
    counts = Counter(round(s['value'],4) for s in candidates)
    if not counts:
        return None
    ranked = counts.most_common()
    value,count = ranked[0]
    if count < 2 or count <= len(candidates)/2:
        return None
    chosen = [s for s in candidates if round(s['value'],4)==value]
    return dict(fact_id='floor-exit:slab-mode', field='floor_exit_reference', value=value,
        status='inferred', method='floor_exit_slab_majority',
        confidence_pct=round(min(s['confidence_pct'] for s in chosen)*count/len(candidates),1),
        confidence_method='level_evidence_completeness_v1',
        confidence_components={'weakest_source':min(s['confidence_pct'] for s in chosen),
                               'majority_fraction':count/len(candidates)},
        source_fact_ids=[s['fact_id'] for s in chosen],
        evidence_ids=sorted({e for s in chosen for e in s.get('evidence_ids',[])}),
        warnings=['floor_exit_from_slab_majority'], owner_decision=DECISION)


def level(shape, native, areas, source, slab_regions, inherited, projected_coverage):
    if source is None or native['status'] not in ('estimated','unknown'):
        return None
    # Unknown inner regions and ordinary slab contours block the absence rule.
    if any(shape.intersection(region.buffer(1)).area > 1 for region in slab_regions):
        return None
    x1,y1,x2,y2 = shape.bounds
    reach = min(x2-x1,y2-y1)+1  # width of this beam, not a fixed project distance
    contacts = [(shape.intersection(region.buffer(reach)),kind,handles)
                for region,kind,handles in areas if shape.distance(region) <= reach]
    coverage = projected_coverage(shape,[hit for hit,_,_ in contacts])
    if coverage < .8:
        return None
    result = inherited(native,[source],'no_slab_floor_exit_reference',.9*coverage,
        value=source['value'], spatial_coverage=coverage,
        no_slab_kinds=sorted({kind for _,kind,_ in contacts}), owner_decision=DECISION)
    result['status']='inferred'
    result['evidence_ids']=sorted(set(result['evidence_ids']+['cad:'+h for _,_,hs in contacts for h in hs]))
    result['warnings']=sorted(set(result['warnings']+['design_floor_reference_not_cut_measurement']))
    return result
