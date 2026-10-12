"""Original witnesses for shortened section drawings and broken dimension shafts."""
from __future__ import annotations
import math
from shapely.geometry import Polygon


def traced_section_outline(points, lines, tolerance_cm):
    """Close one diagonal break only with two original stems and their cap."""
    eps=tolerance_cm
    ring=points[:-1] if points[0]==points[-1] else points
    diagonal=[(i,a,b) for i,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1]))
              if abs(a[0]-b[0])>eps and abs(a[1]-b[1])>eps]
    if len(diagonal)!=1:return None
    index,a,b=diagonal[0]
    candidates=[]
    for ai,ti in [(0,1),(1,0)]:
        low,high=sorted((a[ti],b[ti]))
        if high-low<5:continue
        stems=[]
        for line in lines:
            p,q=line['a'],line['b']
            if abs(p[ti]-q[ti])>eps:continue
            edge=a if abs(p[ti]-a[ti])<=eps else b if abs(p[ti]-b[ti])<=eps else None
            if edge is None:continue
            if min(p[ai],q[ai])-eps<=edge[ai]<=max(p[ai],q[ai])+eps:
                stems.append(line)
        for left in stems:
            for right in stems:
                if left is right or abs(left['a'][ti]-right['a'][ti])<eps:continue
                for start,end in [(left['a'],left['b']),(left['b'],left['a'])]:
                    ends=[(p,q) for p,q in [(right['a'],right['b']),(right['b'],right['a'])]
                          if abs(p[ai]-start[ai])<=eps and abs(q[ai]-end[ai])<=eps]
                    if len(ends)!=1:continue
                    coord=start[ai]
                    longitudinal=[p[ai] for p in ring]
                    if min(longitudinal)-eps<=coord<=max(longitudinal)+eps:continue
                    if not min(longitudinal)-eps<=end[ai]<=max(longitudinal)+eps:continue
                    caps=[line for line in lines if abs(line['a'][ai]-coord)<=eps and abs(line['b'][ai]-coord)<=eps
                          and all(abs(v-w)<=eps for v,w in zip(sorted((line['a'][ti],line['b'][ti])),(low,high)))]
                    if not caps:continue
                    pa=list(a);pb=list(b);pa[ai]=pb[ai]=coord
                    expanded=ring[:index+1]+[tuple(pa),tuple(pb)]+ring[index+1:]
                    shape=Polygon(expanded)
                    if not shape.is_valid or shape.interiors or shape.area<=eps:continue
                    edges=list(shape.exterior.coords)
                    if any(abs(p[0]-q[0])>eps and abs(p[1]-q[1])>eps for p,q in zip(edges,edges[1:])):continue
                    handles=sorted({left['handle'],right['handle'],*[line['handle'] for line in caps]})
                    candidates.append((shape,handles))
    unique={shape.wkb:(shape,handles) for shape,handles in candidates}
    return next(iter(unique.values())) if len(unique)==1 else None


def broken_dimension_shafts(lines, markers, tolerance_cm):
    """Two original shaft parts joined by one explicit centred zigzag marker."""
    eps=tolerance_cm;result=[]
    for handle,points in markers:
        if len(points)<6 or math.dist(points[0],points[-1])<=eps:continue
        for ai,ti in [(0,1),(1,0)]:
            points = list(points)
            if points[-1][ai] < points[0][ai]:
                points.reverse()
            first,last=points[0],points[-1]
            if abs(first[ti]-last[ti])>eps or last[ai]-first[ai]<=eps:continue
            if any(p[ai]>q[ai]+eps for p,q in zip(points,points[1:])):continue
            deviations=[p[ti]-first[ti] for p in points[1:-1]]
            if not deviations or min(deviations)>=-eps or max(deviations)<=eps:continue
            if abs(min(deviations)+max(deviations))>eps or max(abs(v) for v in deviations)>15:continue
            crossings=[(p,q) for p,q in zip(points,points[1:]) if abs(p[ai]-q[ai])<=eps
                       and (p[ti]-first[ti])*(q[ti]-first[ti])<0]
            if len(crossings)!=1:continue
            pairs=[]
            for endpoint,direction in [(first,-1),(last,1)]:
                options=[]
                for line in lines:
                    a,b=line['a'],line['b']
                    if abs(a[ti]-b[ti])>eps or abs(a[ti]-first[ti])>eps:continue
                    for p,q in [(a,b),(b,a)]:
                        if math.dist(p,endpoint)<=eps and direction*(q[ai]-p[ai])>eps:
                            options.append((q,line['handle']))
                pairs.append(options)
            if any(len({p for p,h in options})!=1 for options in pairs):continue
            a,b=pairs[0][0][0],pairs[1][0][0]
            result.append(dict(handle=handle,a=a,b=b,
                evidence_handles=sorted({handle,*[h for options in pairs for p,h in options]})))
    return result
