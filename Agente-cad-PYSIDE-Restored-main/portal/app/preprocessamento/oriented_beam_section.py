"""Numeric section authority bound to two original walls in a local frame."""
import math
import re
from pathlib import Path
from functools import lru_cache
from shapely.geometry import LineString, Point, Polygon

EPS_CM = .05


def measured_section(points, name, texts, walls):
    """Return proof only for an own aligned name and unique section/wall pair.

    ``walls`` contain original straight a/b points and handles; text records
    contain text/position/rotation/handle. Neither a bbox nor nearest text
    supplies width, depth, or beam identity.
    """
    try:
        polygon = Polygon(points)
    except (TypeError, ValueError):
        return None
    if not polygon.is_valid or polygon.area <= 0:
        return None
    found=[]
    for label in texts:
        if str(label.get('text','')).strip().upper() != str(name).strip().upper():continue
        angle=float(label.get('rotation',0))%180
        rad=math.radians(angle);u=(math.cos(rad),math.sin(rad));v=(-u[1],u[0])
        def local(p):return p[0]*u[0]+p[1]*u[1],p[0]*v[0]+p[1]*v[1]
        own=local(label['position']);candidates=[]
        for w in walls:
            a,b=local(w['a']),local(w['b'])
            if abs(a[1]-b[1])>EPS_CM or abs(a[0]-b[0])<40:continue
            # Both original wall pieces must lie on this fund's real boundary.
            line=LineString([w['a'],w['b']])
            covered=line.intersection(polygon.boundary.buffer(EPS_CM)).length
            if covered < 40:continue
            candidates.append((min(a[0],b[0]),max(a[0],b[0]),(a[1]+b[1])/2,w['handle']))
        for i,left in enumerate(candidates):
            for right in candidates[i+1:]:
                lo,hi=max(left[0],right[0]),min(left[1],right[1])
                low,high=sorted([left[2],right[2]]);width=high-low
                if width<=.05 or hi-lo<max(40,3*width):continue
                # Source walls may continue beyond this fund. Certify their
                # shared physical span only, with no unobserved middle gap.
                def world(x,y):return (x*u[0]+y*v[0],x*u[1]+y*v[1])
                observed=[]
                for wall in (left,right):
                    span=LineString([world(lo,wall[2]),world(hi,wall[2])])
                    observed.append(span.intersection(polygon.boundary.buffer(EPS_CM)).length)
                if min(observed)<hi-lo-2*EPS_CM:continue
                if not (lo-30<=own[0]<=hi+30 and low-30<=own[1]<=high+30):continue
                sections=[]
                for t in texts:
                    m=re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*',str(t.get('text','')))
                    if not m:continue
                    ta=float(t.get('rotation',0))%180
                    if min(abs(ta-angle),180-abs(ta-angle))>.1:continue
                    x,y=local(t['position']);bw,depth=[float(z.replace(',','.')) for z in m.groups()]
                    if lo-EPS_CM<=x<=hi+EPS_CM and low-20<=y<=high+20 and abs(bw-width)<=EPS_CM and depth>0:
                        sections.append((depth,t['handle'],t['text']))
                depths={x[0] for x in sections}
                if len(depths)!=1:continue
                found.append(dict(height_cm=depths.pop(),width_cm=width,axis_deg=angle,
                    source_name_handle=label['handle'],
                    section_source='original_aligned_name_section_wall_pair',
                    coverage_contract='shared_original_wall_span_on_real_fund_boundary_except_two_endpoint_eps',
                    proves='numeric_section_only_not_end_supports_or_full_contour',
                    source_entity_handles=sorted({label['handle'],left[3],right[3],*[x[1] for x in sections]}),
                    local_overlap_cm=[lo,hi],source_texts=[x[2] for x in sections]))
    if len({x['height_cm'] for x in found})!=1:return None
    if not found:return None
    best=max(found,key=lambda x:x['local_overlap_cm'][1]-x['local_overlap_cm'][0])
    best['source_name_candidates']=sorted({x['source_name_handle'] for x in found})
    return best


@lru_cache(maxsize=8)
def _source_evidence(source, modified_ns, size):
    import ezdxf
    doc=ezdxf.readfile(source);texts=[];walls=[]
    for e in doc.modelspace():
        kind=e.dxftype()
        if kind in ('TEXT','MTEXT'):
            texts.append(dict(text=e.dxf.text if kind=='TEXT' else e.plain_text(),
                position=(e.dxf.insert.x,e.dxf.insert.y),rotation=float(e.dxf.get('rotation',0)),handle=e.dxf.handle))
        elif kind=='LINE':
            walls.append(dict(a=tuple(e.dxf.start)[:2],b=tuple(e.dxf.end)[:2],handle=e.dxf.handle))
        elif kind=='LWPOLYLINE':
            pts=list(e.get_points('xyb'))
            for a,b in zip(pts,pts[1:]+(pts[:1] if e.closed else [])):
                if not a[2]:walls.append(dict(a=a[:2],b=b[:2],handle=e.dxf.handle))
    return texts,walls


def source_section(points,name,source):
    path=Path(source);stat=path.stat()
    texts,walls=_source_evidence(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
    return measured_section(points,name,texts,walls)
