"""Experimental Formascia faces built from approved Nova SA geometry."""
import math,copy
import ezdxf
from shapely.geometry import box,LineString
from shapely.ops import unary_union
from src.core.lv_nova_design import _template,_hatch,_parts,_text,panel_spans,pontalete_count
from src.core.lv_formascia_design import setup_formascia_resources
from ezdxf.enums import TextEntityAlignment

def draw_ab(contract):
    """Draw contiguous local segments. Opening coordinates are local to each segment."""
    requested_assembly=contract['assembly_variant']
    assembly='sarrafeadas'
    doc, ref = _template(assembly, 'ab')
    m = doc.modelspace()
    body, height = float(contract['body_cm']), float(contract['total_cm'])
    from shapely.geometry import box as raw_box
    active_y = 0.
    def box(x1, y1, x2, y2, offset=None):
        dy = active_y if offset is None else offset
        return raw_box(x1, y1+dy, x2, y2+dy)
    segments, start, voids = [], 0., []
    for source in contract['segments']:
        active_y = float(source.get('y_offset_cm', 0))
        body = float(source.get('body_cm', contract['body_cm']))
        height = float(source.get('total_cm', contract['total_cm']))
        length = float(source['length'])
        if length <= 0 or body <= 0 or height < body:
            raise ValueError('Invalid AB local dimensions')
        end = start + length
        beam_openings = source.get('beam_openings', [source['beam_opening']] if source.get('beam_opening') else [])
        columns = source.get('column_openings', [source['column_opening']] if source.get('column_opening') else [])
        beam_openings = [(max(0., a), min(length, b), max(0., min(body, y)))
                         for a, b, y in beam_openings if b > 0 and a < length and b > a]
        columns = [(max(0., a), min(length, b)) for a, b in columns if b > 0 and a < length and b > a]
        segments.append((start, end, source, beam_openings, columns))
        voids.extend(box(start+a, y, start+b, height) for a, b, y in beam_openings)
        if height > body:
            voids.append(box(start, body, end, height))
        start = end
    total = start
    if all(float(s[2].get('y_offset_cm',0)) == active_y and
           float(s[2].get('body_cm',contract['body_cm'])) == body and
           float(s[2].get('total_cm',contract['total_cm'])) == height for s in segments):
        voids = [box(sx+a,y,sx+b,height) for sx,end,source,holes,columns in segments for a,b,y in holes]
        if height > body:
            voids.insert(0,box(0,body,total,height))
    void_geometry = unary_union(voids).simplify(1e-7, preserve_topology=True)
    band = next(e for e in ref.modelspace().query('HATCH') if e.dxf.pattern_name == 'AR-CONC')
    for part in _parts(void_geometry):
        if part.geom_type == 'Polygon' and part.area:
            hatch = _hatch(m, list(part.exterior.coords)[:-1], band, 1)
            hatch.dxf.layer, hatch.dxf.color = 'COTA', 256
    doc.layers.get('SARR_2.2x7').dxf.color = 40
    doc.layers.get('SARR_3.5x7').dxf.color = 81

    def line(a, b, layer, mask=None, world=False):
        if not world:
            a, b = (a[0], a[1]+active_y), (b[0], b[1]+active_y)
        geometry = LineString([a, b])
        if mask is not None:
            geometry = geometry.intersection(mask)
        for part in _parts(geometry):
            if part.geom_type == 'LineString' and part.length > 1e-6:
                m.add_line(part.coords[0], part.coords[-1], dxfattribs={'layer': layer})

    def measure(p1, p2, base, angle=0):
        p1, p2, base = [(p[0],p[1]+active_y) for p in (p1,p2,base)]
        d = m.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle,
                             dimstyle='PAINEL', dxfattribs={'layer': 'COTA'})
        d.render()

    dimension_floor = min(float(s[2].get('y_offset_cm',0)) for s in segments)
    orange, green, materials, jambs, continuations = [], [], [], [], []
    for index, (sx, end, source, openings, columns) in enumerate(segments, 1):
        active_y = float(source.get('y_offset_cm', 0))
        body = float(source.get('body_cm', contract['body_cm']))
        height = float(source.get('total_cm', contract['total_cm']))
        material = box(sx, 0, end, height)
        for a, b, y in openings:
            material = material.difference(box(sx+a, y, sx+b, height+1))
        local = material.intersection(box(sx, 0, end, body))
        materials.append(local)
        mask, greenmask = local, local
        for a, b in columns:
            mask = mask.difference(box(sx+a, -1, sx+b, body-7))
            greenmask = greenmask.difference(box(sx+a, -1, sx+b, body+1))
        spans = [(sx+a, sx+b) for a, b in panel_spans(end-sx)]
        for x, stop in spans:
            panel = box(x, 0, stop, body).intersection(local)
            for part in _parts(panel):
                if part.geom_type != 'Polygon' or not part.area:
                    continue
                coords = list(part.exterior.coords)
                for a, b in zip(coords, coords[1:]):
                    if abs(a[0]-b[0]) < 1e-6 and sx < a[0] < end:
                        line(a, b, 'Painéis', local, world=True)
                    else:
                        line(a, b, 'Painéis', world=True)
            line((x, body), (stop, body), 'Painéis', material)
            measure((x, 0), (stop, 0), (x, dimension_floor-26.54-active_y))
        for a, b, y in openings:
            a, b = sx+a, sx+b
            measure((a, y), (b, y), (a, height+24))
            q = a+25 if abs(a-sx) < 1e-6 else b-25
            measure((q, y), (q, height), (q, y), 90)
        for a, b in columns:
            a, b = sx+a, sx+b
            anchors = [a]+[q for x, q in spans[:-1] if a < q < b]+[b]
            for x, stop in zip(anchors, anchors[1:]):
                measure((x, body/2), (stop, body/2), (x, body/2))
        if index == 1:
            label = (f'Cont. {contract["beam"]}.{contract.get("side", "A")}'
                     if contract.get('continuation') else contract['beam'])
            _text(m, f"{contract['beam']}{contract.get('side','A')}", sx+5, height+15+active_y, 16.5)
        rails = [(body-2.2, body)]
        if assembly == 'sarrafeadas':
            n = max(2, math.ceil((body-7)/30)+1)
            rails = [(0, 7), (body-7, body)] + [((body-7)*i/(n-1), (body-7)*i/(n-1)+7) for i in range(1, n-1)]
        for low, high in rails:
            if min(end, total-7) > max(sx, 7):
                rail=box(max(sx,7),low,min(end,total-7),high).intersection(mask)
                if requested_assembly=='gradeadas':
                    rail=rail.intersection(unary_union([box(7,low,30,high),box(total-30,low,total-7,high)]))
                orange.append(rail)
        for a, b in columns:
            a, b = sx+a, sx+b
            orange.append(box(a, body-7, b, body).intersection(local))
            if assembly == 'gradeadas':
                green.extend([box(a-3.5, 0, a, body-2.2).intersection(local),
                              box(b, 0, b+3.5, body-2.2).intersection(local)])
        if sx == 0:
            orange.append(box(0, 0, min(7, total), body).intersection(local))
        if end == total:
            orange.append(box(max(0, total-7), 0, total, body).intersection(local))
        if assembly == 'gradeadas':
            if sx == 0:
                green.append(box(15, 0, 18.5, body-2.2).intersection(greenmask))
            if end == total:
                green.append(box(total-18.5, 0, total-15, body-2.2).intersection(greenmask))
            for x, stop in spans[:-1]:
                green.extend([box(stop-3.5, 0, stop, body-2.2).intersection(greenmask),
                              box(stop, 0, stop+3.5, body-2.2).intersection(greenmask)])
            if end < total:
                next_body = float(segments[index][2].get('body_cm', contract['body_cm']))
                if not any(abs(b-(end-sx)) < 1e-6 for a,b,y in openings):
                    green.append(box(end-3.5, 0, end, body-2.2).intersection(greenmask))
                next_y = float(segments[index][2].get('y_offset_cm',0))
                next_mask = box(end,0,segments[index][1],next_body,offset=next_y)
                for a,b,y in segments[index][3]:
                    next_mask = next_mask.difference(box(end+a,y,end+b,next_body+1,offset=next_y))
                post = box(end, 0, end+3.5, next_body-2.2,offset=next_y)
                green.append(post.intersection(next_mask) if segments[index][3] else post)
        elif index > 1:
            previous = segments[index-2]
            if any(abs(b-(previous[1]-previous[0])) < 1e-6 for a, b, y in previous[3]):
                continuations.append((sx, active_y, body+active_y))
        for a, b, y in openings:
            a, b = sx+a, sx+b
            left = abs(a-sx) < 1e-6
            if assembly == 'gradeadas':
                j1, j2 = (b, b+3.5) if left else (a-3.5, a)
                green.append(box(j1, 0, j2, body-2.2).intersection(local))
                orange.append(box(a, y-2.2, b, y))
                endpoint = a if left else b
                outer = abs(endpoint) < 1e-6 or abs(endpoint-total) < 1e-6
                width = 7 if outer else 3.5
                e1, e2 = (endpoint, endpoint+width) if left else (endpoint-width, endpoint)
                if outer or left or abs(endpoint-end) > 1e-6:
                    (orange if outer else green).append(box(e1, 0, e2, y-2.2))
            else:
                j1, j2 = (b, b+7) if left else (a-7, a)
                orange.extend([box(j1, y-7, j2, body).intersection(mask), box(a, y-7, b, y)])
                jambs.append((j1, j2, y+active_y, body+active_y))
        if assembly == 'gradeadas':
            intervals = [(sx+a, sx+b) for a, b, y in openings]+[(sx+a, sx+b) for a, b in columns]
            for x, stop in spans:
                free = box(x, 4, stop, body-5)
                for a, b, y in openings:
                    free = free.difference(box(sx+a, y, sx+b, body+1))
                for a, b in columns:
                    free = free.difference(box(sx+a, 0, sx+b, body+1))
                regions = [p for p in _parts(free) if p.geom_type == 'Polygon' and p.area]
                if not regions:
                    continue
                count = pontalete_count(x, stop, intervals)
                # A fully removed panel must not receive a floating annotation.
                if unary_union([box(max(x,a), 0, min(stop,b), 1) for a,b in intervals if b>x and a<stop]).area >= stop-x-1e-6:
                    continue
                label = f'{count} pontalete' if count == 1 else f'{count} pontaletes'
                region = max(regions, key=lambda p: p.bounds[2]-p.bounds[0])
                p = region.representative_point()
                size = min(5, max(1.2, (region.bounds[2]-region.bounds[0]-2)/(len(label)*.75)))
                _text(m, label, p.x, p.y, size, True)

    active_y = 0.
    measure((0,float(segments[0][2].get('y_offset_cm',0))),
            (total,float(segments[-1][2].get('y_offset_cm',0))),
            (0,dimension_floor-70))
    # Formascia void boundaries are grey; panel interfaces remain green.
    if 'FORMASCIA_VAZIOS' not in doc.layers:
        doc.layers.new('FORMASCIA_VAZIOS',dxfattribs={'color':8})
    interface = unary_union(materials).boundary
    for part in ([] if void_geometry.is_empty else _parts(void_geometry.boundary.difference(interface))):
        if part.geom_type == 'LineString':
            coords=list(part.simplify(1e-7).coords)
            for a,b in zip(coords,coords[1:]):
                line(a,b,'FORMASCIA_VAZIOS',world=True)
    body_heights = {float(s[2].get('body_cm',contract['body_cm']))+float(s[2].get('y_offset_cm',0)) for s in segments}
    base_heights = {float(s[2].get('y_offset_cm',0)) for s in segments}
    seen = set()
    def outline(geometry, layer):
        for part in _parts(geometry):
            if part.geom_type != 'Polygon' or not part.area:
                continue
            for ring in [part.exterior]+list(part.interiors):
                coords = list(ring.coords)
                for a, b in zip(coords, coords[1:]):
                    if layer == 'SARR_2.2x7':
                        if any(abs(a[1]-y) < 1e-6 and abs(b[1]-y) < 1e-6 for y in (*base_heights, *body_heights)):
                            continue
                        if any(abs(a[0]-x) < 1e-6 and abs(b[0]-x) < 1e-6 for x in (0, total, 7, total-7)):
                            continue
                    key = layer, tuple(sorted((tuple(round(v,6) for v in a), tuple(round(v,6) for v in b))))
                    if key not in seen:
                        line(a, b, layer)
                        seen.add(key)
    setup_formascia_resources(doc)
    style=doc.mline_styles.get('EEEEEEEE')
    style.elements.elements.clear();style.elements.append(7.,256,'BYLAYER');style.elements.append(0.,256,'BYLAYER')
    for part in _parts(unary_union(orange)):
        if part.geom_type!='Polygon' or not part.area:continue
        hatch=m.add_hatch(color=1,dxfattribs={'layer':'ACABAMENTO'})
        hatch.set_solid_fill(color=1)
        hatch.paths.add_polyline_path(list(part.exterior.coords)[:-1],is_closed=True)
        for ring in part.interiors:hatch.paths.add_polyline_path(list(ring.coords)[:-1],is_closed=True,flags=0)
    outline(unary_union(orange), 'SARR_2.2x7')
    for x, edge_source in ((7,segments[0][2]), (total-7,segments[-1][2])):
        edge_body = float(edge_source.get('body_cm',contract['body_cm']))
        edge_y = float(edge_source.get('y_offset_cm',0))
        line((x, edge_y), (x, edge_body+edge_y), 'SARR_2.2x7', unary_union(materials))
    for j1, j2, y, jamb_body in jambs:
        for e in list(m.query('LINE')):
            if e.dxf.layer != 'SARR_2.2x7':
                continue
            a, b = e.dxf.start, e.dxf.end
            if abs(a.x-b.x) < 1e-6 and any(abs(a.x-x) < 1e-6 for x in (j1,j2)) and min(a.y,b.y) >= y-7-1e-6:
                m.delete_entity(e)
        for x in (j1, j2):
            line((x, y-7), (x, jamb_body), 'SARR_2.2x7')
        if not any(e.dxf.layer=='SARR_2.2x7' and abs(e.dxf.start.y-(y-7))<1e-6 and abs(e.dxf.end.y-(y-7))<1e-6 and abs(min(e.dxf.start.x,e.dxf.end.x)-j1)<1e-6 and abs(max(e.dxf.start.x,e.dxf.end.x)-j2)<1e-6 for e in m.query('LINE')):
            line((j1,y-7),(j2,y-7),'SARR_2.2x7')
    for geometry in green:
        outline(geometry, 'SARR_3.5x7')
    for sx, end, source, openings, columns in segments:
        segment_y = float(source.get('y_offset_cm',0))
        for a, b, y in openings:
            y += segment_y
            for e in m.query('LINE'):
                if e.dxf.layer != 'SARR_3.5x7':
                    continue
                p, q = e.dxf.start, e.dxf.end
                if min(p.x,q.x) < sx+a-1e-6 or max(p.x,q.x) > sx+b+1e-6:
                    continue
                if max(p.y,q.y) > y+1e-6 or max(p.y,q.y) <= y-2.2+1e-6:
                    continue
                e.dxf.start=(p.x,min(p.y,y-2.2),p.z)
                e.dxf.end=(q.x,min(q.y,y-2.2),q.z)
    for start, base_y, body in continuations:
        for e in list(m.query('LINE')):
            if e.dxf.layer != 'SARR_2.2x7' or abs(e.dxf.start.y-e.dxf.end.y)>1e-6:
                continue
            left, right = sorted((e.dxf.start.x,e.dxf.end.x))
            y = e.dxf.start.y
            if right <= start+1e-6 or left >= start+7-1e-6:
                continue
            m.delete_entity(e)
            if left < start-1e-6:
                line((left,y),(start,y),'SARR_2.2x7')
            if right > start+7+1e-6:
                line((start+7,y),(right,y),'SARR_2.2x7')
        for x in (start,start+7):
            line((x,base_y),(x,body),'SARR_2.2x7')
    first=segments[0][2]
    body=float(first.get('body_cm',contract['body_cm']))
    height=float(first.get('total_cm',contract['total_cm']))
    active_y=float(first.get('y_offset_cm',0))
    measure((0,0),(0,body),(-37,0),90)
    if height>body:measure((0,body),(0,height),(-37,body),90)
    measure((0,0),(0,height),(-57,0),90)
    if requested_assembly=='gradeadas' and body>10:
        measure((0,10),(0,body),(-17,10),90)
        measure((0,3),(0,10),(-17,3),90)
        # One panel joint carries the pressure-strip chain, as in the original.
        joints=[b for a,b in panel_spans(segments[0][1]-segments[0][0])][:-1]
        joint=joints[0] if joints else (segments[0][1] if len(segments)>1 else None)
        if joint is not None:
            measure((joint,0),(joint,10),(joint+18,0),90)
            measure((joint,10),(joint,body),(joint+18,10),90)
    # Different segment heights get local right-side chains; uniform runs do not.
    first_profile=(float(first.get('y_offset_cm',0)),body,height)
    for sx,end,source,openings,columns in segments[1:]:
        body=float(source.get('body_cm',contract['body_cm']))
        height=float(source.get('total_cm',contract['total_cm']))
        active_y=float(source.get('y_offset_cm',0))
        if (active_y,body,height)!=first_profile:
            measure((end,0),(end,body),(end+29.35,0),90)
            if height>body:measure((end,body),(end,height),(end+29.35,body),90)
            measure((end,0),(end,height),(end+55.34,0),90)
    active_y=0.
    # Merge adjoining straight panel/void walls without changing any other
    # construction members or dimension graphics.
    groups = {}
    for e in list(m.query('LINE')):
        if e.dxf.layer not in ('Painéis','FORMASCIA_VAZIOS'):
            continue
        a,b=e.dxf.start,e.dxf.end
        if abs(a.y-b.y)<1e-7:
            key=(e.dxf.layer,'h',round(a.y,6)); interval=sorted((a.x,b.x))
        elif abs(a.x-b.x)<1e-7:
            key=(e.dxf.layer,'v',round(a.x,6)); interval=sorted((a.y,b.y))
        else:
            continue
        groups.setdefault(key,[]).append((interval,e))
    for (layer,axis,fixed),items in groups.items():
        intervals=[]
        for (lo,hi),e in sorted(items,key=lambda v:v[0]):
            m.delete_entity(e)
            if intervals and lo<=intervals[-1][1]+1e-6:
                intervals[-1][1]=max(intervals[-1][1],hi)
            else:
                intervals.append([lo,hi])
        for lo,hi in intervals:
            a,b=((lo,fixed),(hi,fixed)) if axis=='h' else ((fixed,lo),(fixed,hi))
            m.add_line(a,b,dxfattribs={'layer':layer})
    # Apply the original Formascia palette while preserving native dimensions.
    for name,color in [('Painéis',3),('SARR_2.2x7',1),('SARR_3.5x7',2),('Texto Seção',7)]:
        doc.layers.get(name).dxf.color=color
    for e in m.query('HATCH'):
        if e.dxf.pattern_name=='AR-CONC':e.dxf.color=8
    cursor=0.;number=1
    for source in contract['segments']:
        length=float(source['length']);body=float(source.get('body_cm',contract['body_cm']));dy=float(source.get('y_offset_cm',0))
        for start,stop in panel_spans(length):
            area=raw_box(cursor+start,dy,cursor+stop,body+dy)
            for a,b,y in source.get('beam_openings',[]):area=area.difference(raw_box(cursor+a,y+dy,cursor+b,body+dy+1))
            if area.is_empty:continue
            point=area.representative_point();cx,cy=point.x,point.y
            # Small panels keep the original numbering immediately below the face.
            if stop-start<70:cy=dy-12
            radius=min(10,max(4,(stop-start)/5));th=min(12,radius*1.2)
            m.add_circle((cx,cy),radius,dxfattribs={'layer':'NUMERAÇÃO DAS CHAPAS','color':1})
            t=m.add_text(str(number),dxfattribs={'layer':'NUMERAÇÃO DAS CHAPAS','color':7,'height':th})
            t.set_placement((cx,cy),align=TextEntityAlignment.MIDDLE_CENTER);number+=1
        cursor+=length
    if requested_assembly=='gradeadas':
        if 'HIDDEN' not in doc.linetypes:doc.linetypes.new('HIDDEN').setup_pattern([6.,3.,-3.])
        if 'Sarrafo de pressão' not in doc.layers:doc.layers.new('Sarrafo de pressão',dxfattribs={'color':2,'linetype':'HIDDEN'})
        doc.layers.get('Sarrafo de pressão').dxf.color=2
        for sx,end,source,openings,columns in segments:
            dy=float(source.get('y_offset_cm',0));material=unary_union(materials)
            for yy in (dy+3,dy+10):
                for piece in _parts(LineString([(sx+7,yy),(end-7,yy)]).intersection(material)):
                    if piece.geom_type=='LineString' and piece.length>1e-6:m.add_line(piece.coords[0],piece.coords[-1],dxfattribs={'layer':'Sarrafo de pressão','color':2,'linetype':'HIDDEN'})
        t=m.add_text('UTILIZAR GRADE SOLTA',dxfattribs={'layer':'BNC_TEXTO','color':1,'height':10})
        t.set_placement((total/2,dimension_floor-90),align=TextEntityAlignment.MIDDLE_CENTER)
    doc.header['$INSUNITS']=5
    return doc
