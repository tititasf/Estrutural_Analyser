"""Positive source evidence for dimensioned slab-step section glyphs.

This identifies an annotation role, never a slab owner, thickness or altitude.
The section's geometric thicknesses can disagree with h= annotations; that
disagreement remains for the level consumer. Source colour alone proves nothing.
"""
import hashlib
import math
from pathlib import Path
import re

from shapely.geometry import LineString, Point, Polygon, box

TOL = 1e-5


def step_profile(points):
    """Two rectangular thin bands, one continuous bottom, one actual step."""
    try:
        shape = Polygon(points)
        if not shape.is_valid or shape.area <= 0 or shape.interiors:
            return None
        coords = list(shape.exterior.coords)
        if len(coords) != 7 or any(abs(a[0]-b[0]) > TOL and abs(a[1]-b[1]) > TOL
                                  for a,b in zip(coords,coords[1:])):
            return None
        vertical = shape.bounds[3]-shape.bounds[1] > shape.bounds[2]-shape.bounds[0]
        ps = [(y,x) if vertical else (x,y) for x,y in coords]
        xs = sorted(set(p[0] for p in ps[:-1]))
        ys = sorted(set(p[1] for p in ps[:-1]))
        if len(xs) != 3 or len(ys) != 3:
            return None
        normalized = Polygon(ps)
        options=[]
        for bottom in (ys[0],ys[-1]):
            bands=[]
            for lo,hi in zip(xs,xs[1:]):
                hit=normalized.intersection(LineString([((lo+hi)/2,ys[0]-1),((lo+hi)/2,ys[-1]+1)]))
                if hit.geom_type!='LineString':
                    break
                a,b=hit.bounds[1],hit.bounds[3]
                if min(abs(a-bottom),abs(b-bottom))>TOL:
                    break
                bands.append((lo,hi,a,b))
            if len(bands)!=2:
                continue
            expected=box(*[bands[0][0],bands[0][2],bands[0][1],bands[0][3]]).union(
                     box(bands[1][0],bands[1][2],bands[1][1],bands[1][3]))
            if normalized.symmetric_difference(expected).area>TOL:
                continue
            thicknesses=[b-a for _,_,a,b in bands]
            if xs[-1]-xs[0] < 3*max(thicknesses) or min(thicknesses)<=0:
                continue
            opposite=[b if abs(a-bottom)<TOL else a for _,_,a,b in bands]
            if abs(opposite[0]-opposite[1])<=TOL:
                continue
            options.append(dict(vertical=vertical,span=xs,step_limits=sorted(opposite),
                                measured_thicknesses=thicknesses))
        return options[0] if len(options)==1 else None
    except (TypeError,ValueError):
        return None


def inventory_dimensioned_section_profiles(path):
    import ezdxf
    path=Path(path)
    doc=ezdxf.readfile(path)
    lines=[]; texts=[]; candidates=[]
    for entity in doc.modelspace():
        kind=entity.dxftype()
        if kind=='LINE':
            lines.append(dict(handle=entity.dxf.handle,layer=entity.dxf.layer,
                              points=[tuple(entity.dxf.start)[:2],tuple(entity.dxf.end)[:2]]))
        elif kind in ('TEXT','MTEXT'):
            text=entity.dxf.text if kind=='TEXT' else entity.plain_text()
            texts.append(dict(handle=entity.dxf.handle,layer=entity.dxf.layer,text=text.strip(),
                              position=tuple(entity.dxf.insert)[:2],height=float(entity.dxf.height if kind=='TEXT' else entity.dxf.char_height)))
        elif kind=='LWPOLYLINE':
            raw=list(entity.get_points())
            if any(abs(p[4])>TOL for p in raw):
                continue
            points=[tuple(p[:2]) for p in raw]
            if entity.closed and points and points[0]!=points[-1]:
                points.append(points[0])
            color=entity.dxf.color
            if color==256:
                color=doc.layers.get(entity.dxf.layer).dxf.color
            if color==8:
                profile=step_profile(points)
                if profile:
                    candidates.append((entity,points,profile))
    records=[]
    for entity,points,profile in candidates:
        shape=Polygon(points)
        # An original plan pillar label inside the contour is competing evidence.
        if any(re.fullmatch(r'P\d+[A-Z]*',t['text'],re.I) and shape.covers(Point(t['position'])) for t in texts):
            continue
        swap=lambda p:(p[1],p[0]) if profile['vertical'] else p
        lower,upper=profile['step_limits'];delta=upper-lower
        shafts=[]
        for line in lines:
            a,b=map(swap,line['points'])
            if (abs(a[0]-b[0])>TOL or not profile['span'][0]<a[0]<profile['span'][-1]
                    or abs(min(a[1],b[1])-lower)>TOL or abs(max(a[1],b[1])-upper)>TOL):
                continue
            shaft=LineString(line['points'])
            local=[t for t in texts if re.fullmatch(r'\d+(?:[.,]\d+)?',t['text'])
                   and abs(float(t['text'].replace(',','.'))-delta)<=TOL
                   and shaft.distance(Point(t['position']))<=max(1,2.5*t['height'])]
            if len(local)!=1:
                continue
            text=local[0];ticks=[]
            for endpoint in line['points']:
                hits=[v for v in lines if v['handle']!=line['handle'] and v['layer']==text['layer']
                      and abs(v['points'][0][0]-v['points'][1][0])>TOL
                      and abs(v['points'][0][1]-v['points'][1][1])>TOL
                      and LineString(v['points']).distance(Point(endpoint))<=TOL
                      and abs(Point(v['points'][0]).distance(Point(endpoint))-Point(v['points'][1]).distance(Point(endpoint)))<=TOL]
                if len(hits)!=1:
                    break
                ticks.append(hits[0]['handle'])
            if len(ticks)==2 and ticks[0]!=ticks[1]:
                shafts.append((line,text,ticks))
        if len(shafts)!=1:
            continue
        line,text,ticks=shafts[0]
        records.append(dict(status='proved',role='slab_section_glyph',owner='unassigned_section',
                            source_entity_handles=[entity.dxf.handle],original_points=points,
                            dimension_evidence_handles=[line['handle'],text['handle']]+ticks,
                            step_delta_cm=delta,measured_thicknesses_cm=profile['measured_thicknesses'],
                            level_transfer_authorized=False,consumer_authorized='source_role_only'))
    return dict(schema='cad.dimensioned_section_profiles/v1',source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),records=records)
