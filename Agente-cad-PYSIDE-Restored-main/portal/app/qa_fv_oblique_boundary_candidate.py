"""Candidate physical-boundary proof; no sections, caps or ownership approval.

Call with the real polygon and original strokes in the same local coordinate
system. The slice clips only the polygon's existing boundary, so its artificial
subdivision faces are never treated as original walls. Every real sliver stays.
"""
import math

from shapely.geometry import LineString, Polygon, box
from shapely.errors import GEOSException
from shapely.ops import unary_union


def prove_oblique_boundary(local_polygon, span, originals, epsilon=.05):
    """Measure original coverage of every physical boundary piece in a slice.

    `originals` consists of (point_a, point_b, original_handle) tuples. The
    returned status concerns identity_contorno alone. A measured result never
    establishes support limits, numeric section, ownership or encounter inventory.
    Missing evidence, including an unsupported tiny edge, fails closed.
    """
    result = {'status':'uncertain', 'guards':['identidade_contorno'],
              'kind':'original_physical_boundary_slice', 'pieces':[],
              'caps_approved':False, 'section_approved':False,
              'ownership_approved':False, 'inventory_approved':False}
    try:
        lo,hi=span
        if (not isinstance(local_polygon,Polygon) or not local_polygon.is_valid
                or local_polygon.area<=0 or not all(math.isfinite(v) for v in (lo,hi,epsilon))
                or hi<=lo or epsilon<=0):
            result['reason']='invalid real polygon or slice';return result
        ymin,ymax=local_polygon.bounds[1],local_polygon.bounds[3]
        clipped=local_polygon.boundary.intersection(box(lo,ymin-1,hi,ymax+1))
        def lines(geometry):
            if geometry.geom_type in {'LineString','LinearRing'}:
                coords=list(geometry.coords)
                # Split at every actual vertex; a bent polyline is not a chord.
                return [LineString([a,b]) for a,b in zip(coords,coords[1:]) if a!=b]
            return [line for g in getattr(geometry,'geoms',[]) for line in lines(g)]
        pieces=lines(clipped)
        if not pieces:
            result['reason']='no physical polygon boundary in slice';return result
        for edge in pieces:
            a,b=list(edge.coords);length=edge.length
            ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
            intervals=[];handles=[]
            for c,d,handle in originals:
                if not isinstance(handle,str) or not handle:continue
                if len(c)!=2 or len(d)!=2 or not all(math.isfinite(v) for v in (*c,*d)):
                    result['reason']='invalid original stroke coordinates';return result
                other=math.dist(c,d)
                if other<=0:continue
                if abs(ux*(d[1]-c[1])-uy*(d[0]-c[0]))/other>math.sin(math.radians(.1)):continue
                if max(abs((p[0]-a[0])*uy-(p[1]-a[1])*ux) for p in (c,d))>epsilon:continue
                start,end=sorted(( (p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (c,d)))
                start,end=max(0,start),min(length,end)
                if end>start:
                    intervals.append(LineString([(start,0),(end,0)]));handles.append(handle)
            covered=unary_union(intervals).length if intervals else 0
            missing=max(0.,length-covered)
            result['pieces'].append({'points':[a,b], 'length_cm':length,
                'covered_cm':covered, 'uncovered_cm':missing,
                'wall_handles':sorted(set(handles)),
                'proved':covered>0 and missing<=epsilon})
        if all(piece['proved'] for piece in result['pieces']):
            result['status']='measured'
        else:
            result['reason']='real boundary contains unsupported physical or ownership edge'
        return result
    except (TypeError,ValueError,AttributeError,ZeroDivisionError,GEOSException) as exc:
        result['reason']='invalid boundary input: '+str(exc)
        return result
