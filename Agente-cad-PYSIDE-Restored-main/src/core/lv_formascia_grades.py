"""Experimental loose-grade presentation; no production changes."""
import json,copy
import ezdxf
from shapely.geometry import box
from src.core.lv_nova_design import _parts
from src.core.n5_formascia_frames import transfer
from ezdxf import bbox
from src.core.lv_formascia_design import legacy_draw_ab as draw_ab, panel_spans


def grade_key(contract):
    # Equal physical geometry only; side, station and absolute floor are provenance.
    datum = min(float(s.get('y_offset_cm', 0)) for s in contract['segments'])
    def rounded(value):
        if isinstance(value, (int, float)):
            return round(value, 6)
        if isinstance(value, list):
            return [rounded(v) for v in value]
        return value
    segments = []
    for s in contract['segments']:
        segments.append(rounded([s['length'], s.get('body_cm', contract['body_cm']),
                                 float(s.get('y_offset_cm', 0))-datum,
                                 s.get('beam_openings', []), s.get('column_openings', [])]))
    return json.dumps(segments, sort_keys=True)


def prepare_grades(doc, contract, quantity):
    if len(contract['segments'])>1:
        combined=ezdxf.new('R2018');cursor=0.;number=1
        for source in contract['segments']:
            # Loose pieces sit independently on one baseline; measured SA heights stay intact.
            item=copy.deepcopy(contract);local=copy.deepcopy(source);local['y_offset_cm']=0
            item['segments']=[local];item['body_cm']=source.get('body_cm',contract['body_cm']);item['total_cm']=source.get('total_cm',contract['total_cm'])
            part=prepare_grades(None,item,quantity)
            for e in part.modelspace().query('TEXT'):
                if e.dxf.layer=='NUMERAÇÃO DAS CHAPAS':e.dxf.text=str(number+int(e.dxf.text)-1)
            number+=len(panel_spans(source['length']))
            bb=bbox.extents(part.modelspace())
            transfer(part,combined,dx=cursor-bb.extmin.x,native_mlines=True)
            cursor+=bb.size.x+25
        combined.header['$INSUNITS']=5
        return combined
    doc = draw_ab(contract)
    if 'HIDDEN' not in doc.linetypes:doc.linetypes.new('HIDDEN').setup_pattern([6.,3.,-3.])
    m = doc.modelspace()
    # Each detachable grade starts its own 30 cm pitch and has posts at both ends.
    for e in list(m):
        if e.dxf.layer in ('Sarrafos','Meio_pont.'):m.delete_entity(e)
    source=contract['segments'][0];length=float(source['length']);height=float(source.get('body_cm',contract['body_cm']));dy=float(source.get('y_offset_cm',0))
    material=box(0,dy,length,dy+height)
    for a,b,y in source.get('beam_openings',[]):material=material.difference(box(a,y+dy,b,dy+height+1))
    def rectangle(x1,y1,x2,y2,layer,color):
        for part in _parts(box(x1,y1,x2,y2).intersection(material)):
            if part.geom_type=='Polygon' and part.area:m.add_lwpolyline(list(part.exterior.coords)[:-1],close=True,dxfattribs={'layer':layer,'color':color})
    for start,stop in panel_spans(length):
        rectangle(start,dy,stop,dy+2.2,'Sarrafos',1)
        rectangle(start,dy+height-2.2,stop,dy+height,'Sarrafos',1)
        positions=[start];x=start+30
        while x+3.5<stop-3.5-1e-6:positions.append(x);x+=30
        if stop-start>3.5:positions.append(stop-3.5)
        for x in positions:rectangle(x,dy+2.2,min(stop,x+3.5),dy+height-2.2,'Meio_pont.',43)
    boundaries = []
    for e in list(m):
        layer = e.dxf.layer
        if layer == 'VIGAS' and e.dxftype() == 'LWPOLYLINE':
            points = list(e.get_points('xy'))
            for a, b in zip(points, points[1:]+points[:1]):
                if abs(a[0]-b[0]) < 1e-7:
                    boundaries.append((a, b))
        if layer not in ('Sarrafos', 'Meio_pont.', 'NUMERAÇÃO DAS CHAPAS'):
            m.delete_entity(e)
        elif e.dxftype() == 'TEXT' and 'UTILIZAR GRADE' in e.dxf.text:
            m.delete_entity(e)
        elif layer == 'NUMERAÇÃO DAS CHAPAS':
            e.dxf.color = 7  # white circle and numeral, matching original loose grades
    if 'FORMASCIA_GRADE_DIVISOES' not in doc.layers:
        doc.layers.new('FORMASCIA_GRADE_DIVISOES', dxfattribs={'color': 3})
    seen = set()
    for a, b in boundaries:
        key = tuple(sorted((tuple(round(v, 6) for v in a), tuple(round(v, 6) for v in b))))
        if key in seen:
            continue
        seen.add(key)
        m.add_line(a, b, dxfattribs={'layer': 'FORMASCIA_GRADE_DIVISOES', 'color': 3})
    def dim(p1,p2,base,angle=0,location=None):
        if abs(p1[0]-p2[0])+abs(p1[1]-p2[1])<1e-6:return
        d=m.add_linear_dim(p1=p1,p2=p2,base=base,angle=angle,dimstyle='FORMASCIA-PAINEL',dxfattribs={'layer':'cotas','color':4})
        if location is not None:d.set_location(location,leader=False,relative=False)
        d.render()
    floor=min(float(s.get('y_offset_cm',0)) for s in contract['segments'])
    cursor=0.
    for source in contract['segments']:
        length=float(source['length']);height=float(source.get('body_cm',contract['body_cm']));dy=float(source.get('y_offset_cm',0));end=cursor+length
        # Show the first actual pitch of the posts; never invent a 30 on a short piece.
        posts=sorted({round(min(p[0] for p in e.get_points('xy')),6) for e in m.query('LWPOLYLINE') if e.dxf.layer=='Meio_pont.' and cursor-1e-5<=min(p[0] for p in e.get_points('xy'))<end-1e-5})
        if len(posts)>=2:dim((posts[0],dy),(posts[1],dy),(posts[0],dy-15))
        for a,b in panel_spans(length):dim((cursor+a,dy),(cursor+b,dy),(cursor+a,floor-35))
        # Stack the two 2.2 chords and the useful vertical post on the near lane.
        lane=end+22
        dim((end,dy),(end,dy+2.2),(lane,dy),90,(lane,dy-12))
        dim((end,dy+2.2),(end,dy+height-2.2),(lane,dy+2.2),90)
        dim((end,dy+height-2.2),(end,dy+height),(lane,dy+height-2.2),90,(lane,dy+height+12))
        # Overall height further right, at the group's final edge.
        if source is contract['segments'][-1]:dim((end,dy),(end,dy+height),(end+50,dy),90)
        cursor=end
    if len(contract['segments'])>1 or len(panel_spans(cursor))>1:
        dim((0,floor),(cursor,floor),(0,floor-60))
    ext = bbox.extents(m)
    m.add_mtext(f'GRADE SOLTA\\P({quantity}X)', dxfattribs={
        'layer': 'BNC_TEXTO', 'color': 7, 'char_height': 16.5,
        'insert': (ext.extmin.x, ext.extmax.y+50), 'attachment_point': 1})
    return doc
