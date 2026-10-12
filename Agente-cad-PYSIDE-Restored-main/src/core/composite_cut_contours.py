"""Recover section outlines exported as touching filled rectangles.

Only same-layer, closed orthogonal pieces are combined. No gap bridging,
buffer, or nearest-neighbour matching is permitted here. Slab ownership and
section measurements remain the responsibility of the SA boundary detector.
"""
from collections import defaultdict
import re


def partition_cut_contours(polylines, texts):
    """Partition connected CAD section pieces using dimensioned beam bodies.

    Only exact, closed orthogonal source pieces are used. A beam seed must
    match the width of a nearby dimension annotation; the source depth is
    measured independently and disagreements are retained. Slab transitions are
    collinear thin pieces meeting at an end with a change in thickness/level.
    No missing geometry is synthesized or gap bridged.
    """
    from shapely.geometry import Polygon, Point, box
    from shapely.ops import unary_union
    pieces = defaultdict(list)
    dimensions = []
    for text in texts:
        if 'PIL' in str(text.get('layer') or '').upper():
            continue
        match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*', text.get('text', ''))
        if match:
            dimensions.append((float(match[1].replace(',', '.')), float(match[2].replace(',', '.')), text))
    for item in polylines:
        if 'PIL' in str(item.get('layer') or '').upper():
            continue
        pts = item.get('points') or []
        if len(pts) != 5 or pts[0] != pts[-1]:
            continue
        if any(abs(a[0]-b[0]) > 1e-5 and abs(a[1]-b[1]) > 1e-5 for a,b in zip(pts,pts[1:])):
            continue
        p = Polygon(pts)
        if not p.is_valid or p.area < 10:
            continue
        x,y,X,Y = p.bounds
        if min(X-x,Y-y) < 5 or max(X-x,Y-y) > 300:
            continue
        key = tuple(sorted(set(tuple(q) for q in pts)))
        if not any(v['key'] == key for v in pieces[str(item.get('layer') or '')]):
            pieces[str(item.get('layer') or '')].append(dict(shape=p,key=key,item=item))
    result = []
    for layer, rows in pieces.items():
        seeds = []
        for i,row in enumerate(rows):
            p = row['shape'];x,y,X,Y=p.bounds;w,h=X-x,Y-y
            matching = [(p.distance(Point(t['pos'][:2])), t) for bw,bh,t in dimensions
                        if abs(min(w,h)-bw)<.05 and max(w,h)>=30
                        and p.distance(Point(t['pos'][:2]))<=160]
            if matching:
                seeds.append((i,min(matching,key=lambda v:v[0])[1]))
        # A layer containing annotated seed bodies establishes section provenance;
        # pillar contours from other layers never enter this decomposition.
        if not seeds:
            continue
        established_widths={round(min(rows[i]['shape'].bounds[2]-rows[i]['shape'].bounds[0],
                                      rows[i]['shape'].bounds[3]-rows[i]['shape'].bounds[1]),2)
                            for i,_ in seeds}
        for i,row in enumerate(rows):
            if any(i==j for j,_ in seeds):continue
            a=row['shape'];ax,ay,aX,aY=a.bounds
            if round(min(aX-ax,aY-ay),2) not in established_widths or max(aX-ax,aY-ay)<30:continue
            av=aY-ay>aX-ax
            # Missing text must not discard a complete section. Its body width
            # is established by annotated bodies on this same source layer,
            # and a touching perpendicular slab arm confirms the local glyph.
            for j,other in enumerate(rows):
                if i==j:continue
                b=other['shape'];bx,by,bX,bY=b.bounds
                if av!=(bY-by>bX-bx) and min(bX-bx,bY-by)<=20 and a.intersection(b).length>1:
                    seeds.append((i,{}));break
        merged=unary_union([r['shape'] for r in rows])
        components=list(merged.geoms) if merged.geom_type=='MultiPolygon' else [merged]
        for component in components:
            members=[i for i,r in enumerate(rows) if component.intersection(r['shape']).area>.01]
            local_seeds=[(i,t) for i,t in seeds if i in members]
            seed_ids={i for i,t in local_seeds}
            # Connected thin slab segments are a transition only when their
            # long axes align and their ends touch. Perpendicular beam flanges
            # are not slab steps.
            step_ids=set()
            for i in members:
                if i in seed_ids:continue
                a=rows[i]['shape'];ax,ay,aX,aY=a.bounds;av=(aY-ay)>(aX-ax)
                at=min(aX-ax,aY-ay)
                if at>20 or max(aX-ax,aY-ay)<2*at:continue
                for j in members:
                    if j<=i or j in seed_ids:continue
                    b=rows[j]['shape'];bx,by,bX,bY=b.bounds;bv=(bY-by)>(bX-bx)
                    bt=min(bX-bx,bY-by)
                    if av!=bv or bt>20 or max(bX-bx,bY-by)<2*bt:continue
                    ends=abs(aY-by)<1e-5 or abs(bY-ay)<1e-5 if av else abs(aX-bx)<1e-5 or abs(bX-ax)<1e-5
                    shifted = abs((ax+aX)-(bx+bX))>.05 if av else abs((ay+aY)-(by+bY))>.05
                    if ends and a.intersection(b).length>1 and (abs(at-bt)>.05 or shifted):
                        step_ids.update((i,j))
            step_shape=unary_union([rows[i]['shape'] for i in step_ids]) if step_ids else Polygon()
            if step_ids:
                parts=list(step_shape.geoms) if step_shape.geom_type=='MultiPolygon' else [step_shape]
                for p in parts:
                    result.append(_piece_record(p,layer,rows,members,'slab_step',None))
            for seed,text in local_seeds:
                body=rows[seed]['shape'];region=component.difference(step_shape)
                # Partition a bridge shared by two bodies at its actual midpoint;
                # each body remains whole. This does not invent or move a contour.
                for other,_ in local_seeds:
                    if other==seed:continue
                    b=rows[other]['shape'];c,d=body.centroid,b.centroid
                    dx,dy=d.x-c.x,d.y-c.y
                    if abs(dx)>abs(dy):
                        mid=(body.bounds[2]+b.bounds[0])/2 if dx>0 else (b.bounds[2]+body.bounds[0])/2
                        clip=box(-1e9,-1e9,mid,1e9) if dx>0 else box(mid,-1e9,1e9,1e9)
                    else:
                        mid=(body.bounds[3]+b.bounds[1])/2 if dy>0 else (b.bounds[3]+body.bounds[1])/2
                        clip=box(-1e9,-1e9,1e9,mid) if dy>0 else box(-1e9,mid,1e9,1e9)
                    region=region.intersection(clip)
                parts=list(region.geoms) if hasattr(region,'geoms') else [region]
                shape=next((p for p in parts if p.geom_type=='Polygon' and p.intersection(body).area>.99*body.area),None)
                if shape is not None:
                    result.append(_piece_record(shape,layer,rows,members,'beam',dict(body_points=list(body.exterior.coords),dimension_text=text)))
    return result


def _piece_record(shape, layer, rows, members, kind, body):
    pts=[list(p) for p in shape.simplify(1e-6,preserve_topology=True).exterior.coords]
    record=dict(points=pts,layer=layer,source='partitioned_closed_contours',
                section_kind=kind,source_piece_count=len(members),
                source_piece_keys=[list(rows[i]['key']) for i in members],
                source_entity_handles=sorted({h for i in members
                    for h in rows[i]['item'].get('source_entity_handles') or []}))
    record['measured_pieces']=[dict(points=[list(q) for q in rows[i]['shape'].exterior.coords],
                                  assigned_points=[list(q) for q in part.exterior.coords],
                                  shared_for_display=part.area<rows[i]['shape'].area-.01)
        for i in members for part in [rows[i]['shape'].intersection(shape)]
        if part.geom_type=='Polygon' and part.area>.01]
    if body:record.update(body)
    return record


def source_section_drawing(record, title=''):
    """Dimension the unmodified source polygon; never redraw a CAD original."""
    from shapely.geometry import Polygon
    shape=Polygon(record['points']);x,y,X,Y=shape.bounds
    color='#ffe033' if record.get('section_kind')=='slab_step' else '#a8fff0'
    primitives=[dict(kind='polygon',points=record['points'],color=color)]
    def dimension(a,b,value,offset,role='dimension'):
        a=[a[0]+offset[0],a[1]+offset[1]];b=[b[0]+offset[0],b[1]+offset[1]]
        primitives.append(dict(kind='line',points=[a,b],color='#fff38c'))
        for p in (a,b):
            primitives.append(dict(kind='line',points=[[p[0]-1.5,p[1]-1.5],[p[0]+1.5,p[1]+1.5]],color='#fff38c'))
        p=[(a[0]+b[0])/2,(a[1]+b[1])/2]
        horizontal=abs(b[0]-a[0])>abs(b[1]-a[1]);p[1 if horizontal else 0]+=5
        primitives.append(dict(kind='text',points=[p,[p[0]+1,p[1]]],text=f'{value:g}',size=5,color='#fff',role=role))
    body=record.get('body_points')
    if body:
        bx,by,bX,bY=Polygon(body).bounds
        # The total depth sits 4 cm beyond the slab/granular dimension lane.
        horizontal_depth=bX-bx>bY-by
        dimension([bx,by],[bX,by],bX-bx,[0,y-by-(12 if horizontal_depth else 8)])
        dimension([bX,by],[bX,bY],bY-by,[X-bX+12,0])
        # Slab contacts divide each physical face into exposed wall intervals.
        # Use assigned source pieces so a shared bridge cannot borrow a wall
        # from the neighbouring body. Neither contours nor levels are changed.
        vertical=bY-by>bX-bx
        lo,hi=(by,bY) if vertical else (bx,bX)
        for face,sign in ((bx,-1),(bX,1)) if vertical else ((by,-1),(bY,1)):
            contacts=[]
            for piece in record.get('measured_pieces') or []:
                part=Polygon(piece.get('assigned_points') or piece['points'])
                if part.equals(Polygon(body)):continue
                px,py,pX,pY=part.bounds
                near,far=(px,pX) if vertical else (py,pY)
                start,end=(py,pY) if vertical else (px,pX)
                touches=abs((far if sign<0 else near)-face)<1e-5
                extends=near<face-1e-5 if sign<0 else far>face+1e-5
                if touches and extends and min(hi,end)>max(lo,start)+1e-5:
                    contacts.append((max(lo,start),min(hi,end)))
            if not contacts:continue
            cursor=lo;free=[]
            for start,end in sorted(contacts):
                if start>cursor+1e-5:free.append((cursor,start))
                cursor=max(cursor,end)
            if cursor<hi-1e-5:free.append((cursor,hi))
            for start,end in free:
                a,b=([face,start],[face,end]) if vertical else ([start,face],[end,face])
                # Position beside the measured wall, independent of slab-arm extent.
                offset=[sign*8,0] if vertical else [0,sign*8]
                dimension(a,b,end-start,offset,role='wall_dimension')
    seen=set()
    thicknesses=[]
    for piece in record.get('measured_pieces') or []:
        p=Polygon(piece['points']);px,py,pX,pY=p.bounds
        if body and p.equals(Polygon(body)):continue
        horizontal=pX-px>pY-py
        a,b=([px,py],[px,pY]) if horizontal else ([px,py],[pX,py])
        value=min(pX-px,pY-py)
        key=(tuple(a),tuple(b))
        if key in seen:continue
        seen.add(key);thicknesses.append(value)
        # Slab arm lengths describe the drawn symbol, not a formwork measure.
        # Keep source geometry intact and dimension only the slab thickness.
        dimension(a,b,value,[-8,0] if horizontal else [0,-8],role='slab_thickness')
    if not body and thicknesses:
        title=(title+' · ' if title else '')+f'Degrau de laje ({" / ".join(f"{v:g}" for v in sorted(set(thicknesses)))} cm)'
    if body:
        width,depth=sorted((bX-bx,bY-by))
        title += f' · {width:g}/{depth:g} cm (geometria)'
        annotation=(record.get('dimension_text') or {}).get('text','')
        match=re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*',annotation)
        if match and abs(float(match[2].replace(',','.'))-depth)>.05:
            title += f' · anotação {annotation}: conferir'
    # Text follows the section width axis and sits outside the entire glyph,
    # including slab arms that project past the beam body.
    horizontal_body=bool(body) and bX-bx>bY-by
    anchor=[x-32,(y+Y)/2] if horizontal_body else [(x+X)/2,Y+32]
    direction=[0,1] if horizontal_body else [1,0]
    primitives.append(dict(kind='text',points=[anchor,[anchor[0]+direction[0],anchor[1]+direction[1]]],text=title or 'Corte original',size=8,color='#fff',role='section_title'))
    return dict(anchor=[shape.centroid.x,shape.centroid.y],primitives=primitives,
                measurement_source='source_closed_pieces',source_points=record['points'])


def composite_cut_contours(polylines, texts=None):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    layers = defaultdict(list)
    for item in polylines:
        pts = item.get('points') or []
        if len(pts) != 5 or pts[0] != pts[-1]:
            continue
        try:
            if any(abs(a[0]-b[0]) > 1e-6 and abs(a[1]-b[1]) > 1e-6
                   for a, b in zip(pts, pts[1:])):
                continue
            shape = Polygon(pts)
            x0, y0, x1, y1 = shape.bounds
            if not shape.is_valid or min(x1-x0, y1-y0) < 5 or max(x1-x0, y1-y0) > 180:
                continue
            layers[str(item.get('layer') or '')].append((shape, item))
        except (TypeError, ValueError):
            continue

    result = []
    for layer, pieces in layers.items():
        merged = unary_union([p for p, _ in pieces])
        parts = list(merged.geoms) if merged.geom_type == 'MultiPolygon' else [merged]
        for shape in parts:
            if shape.geom_type != 'Polygon' or shape.interiors:
                continue
            # Shared points alone do not merge polygons; shared edges do.
            contributors = [(p, item) for p, item in pieces if shape.intersection(p).area > .01]
            if len(contributors) < 2:
                continue
            contour = shape.simplify(1e-6, preserve_topology=True)
            pts = list(contour.exterior.coords)
            x0, y0, x1, y1 = contour.bounds
            w, h = x1-x0, y1-y0
            if not 7 <= len(pts) <= 24 or max(w, h) > 180:
                continue
            if contour.area / (w*h) >= .70:
                continue
            result.append(dict(points=[list(p) for p in pts], layer=layer,
                               source='connected_closed_contours',
                               source_piece_count=len(contributors),
                               source_piece_keys=[sorted(set(tuple(p) for p in g.exterior.coords))
                                                  for g, _ in contributors],
                               source_entity_handles=sorted({h for _, item in contributors
                                   for h in item.get('source_entity_handles') or []})))
    if texts:
        # Touching glyphs can belong to different beams. A union cannot be
        # measured as one section when independent annotated bodies exist.
        partitions = partition_cut_contours(polylines, texts)
        separated = []
        for record in result:
            keys = {tuple(tuple(p) for p in key) for key in record['source_piece_keys']}
            rows = [p for p in partitions if
                    {tuple(tuple(q) for q in key) for key in p['source_piece_keys']} == keys]
            if sum(p['section_kind'] == 'beam' for p in rows) < 2:
                separated.append(record)
                continue
            original = Polygon(record['points'])
            coverage = unary_union([Polygon(p['points']) for p in rows])
            if original.symmetric_difference(coverage).area > 1e-4:
                separated.append(record)
                continue
            for row in rows:
                separated.append({**row, 'source': 'connected_closed_contours',
                                  'replaces_contour': record['points']})
        result = separated
    return result
