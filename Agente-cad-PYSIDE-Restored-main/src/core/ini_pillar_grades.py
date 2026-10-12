"""Native iNi grades with Nova fabrication geometry and face dimension chains."""
import math, copy
import ezdxf
from ezdxf import bbox
from ezdxf.math import BoundingBox
from scripts.visual_modes import apply_visual_mode
from . import n5_ini_frames as frames
from .n5_pillar_frames import grade_groups
from .ini_pillar_top import cd_post_centres

def cd_unit(pj, namespace):
    """C/D metal sections share the side-grade stations emitted in CIMA."""
    width=float(pj['largura'])-10; height=float(pj['altura'])
    d=namespace['setup_doc'](); m=d.modelspace()
    for tag,fill,edge in [('INI_TRAVA',17,24),('INI_PONT1',23,18),('INI_MEIOPONT',33,12)]:
        st=d.mline_styles.new(tag);st.dxf.flags=st.FILL|st.START_SQUARE|st.END_SQUARE;st.dxf.fill_color=fill
        st.elements.elements.clear();st.elements.append(.5,edge,'BYLAYER');st.elements.append(-.5,edge,'BYLAYER')
    d.dimstyles.new('INI-GRADE-REVIEW',dxfattribs={'dimclrd':4,'dimclre':4,'dimclrt':1,'dimtxt':5,'dimasz':3})
    def ml(a,z,th,tag):
        st=d.mline_styles.get(tag)
        return m.add_mline([a,z],dxfattribs={'style_name':tag,'style_handle':st.dxf.handle,'scale_factor':th,'justification':1,'layer':'Sarrafos'})
    centres=cd_post_centres(width)
    for i,x in enumerate(centres):ml((x,2.2),(x,height),7 if i in (0,len(centres)-1) else 3.5,'INI_PONT1' if i in (0,len(centres)-1) else 'INI_MEIOPONT')
    ml((0,1.1),(width,1.1),2.2,'INI_TRAVA')
    levels={2.2+v+5 for v in namespace['grade_horizontal_positions_for_mode']('NOVA') if 2.2+v+10<height}
    for y in sorted(levels|{height-5}):ml((0,y),(width,y),10,'INI_TRAVA')
    for pts in [[(0,0),(15,0),(0,15)],[(width,0),(width-15,0),(width,15)]]:
        h=m.add_hatch(color=5);h.paths.add_polyline_path(pts,is_closed=True)
        m.add_lwpolyline(pts,close=True,dxfattribs={'color':7})
    chain=[0]+centres[1:-1]+[width]
    for a,z in ([] if len(chain)==2 else zip(chain,chain[1:])):m.add_linear_dim(base=(0,-15),p1=(a,0),p2=(z,0),dimstyle='INI-GRADE-REVIEW').render()
    m.add_linear_dim(base=(0,-30),p1=(0,0),p2=(width,0),dimstyle='INI-GRADE-REVIEW').render()
    return d

def refine_grades(doc,pj,namespace):
    from .pillar_nova_design import special_payload
    from .pillar_u_nova_contract import u_nova_payload, n3_u_faces
    is_u = u_nova_payload(pj) is not None
    required_u = {f['id'] for f in n3_u_faces(pj, grades_only=True)} if is_u else set()
    groups=grade_groups(doc,pj['nome'])
    faces={}
    for g in groups:
        face=g['names'][0].removeprefix(pj['nome']+'.').split('-')[0]
        if face in 'CD' and (not is_u or face not in required_u):continue
        faces.setdefault(face,[]).append((convert_unit(doc,g),g['names'][0]))
    if not special_payload(pj) and float(pj['largura'])>=40:
        for face in 'CD':faces[face]=[(cd_unit(pj,namespace),pj['nome']+'.'+face)]
    cima_gaps={}
    if special_payload(pj):
        from .pillar_nova_special import Drawing
        drawing=Drawing(special_payload(pj));drawing.generate()
        indices = ([(i, f['name']) for i, f in enumerate(drawing.faces)] if is_u
                   else ((5,'A'),(3,'B'),(0,'E'),(2,'F')))
        for index,face in indices:
            records=[r for r in drawing.report if r['face']==drawing.faces[index]['name']]
            if records:cima_gaps[face]=records[0]['gap_cm']
    else:
        contract=namespace['cima_layout_contract'](pj,float(pj['comprimento']))
        for face in 'AB':cima_gaps[face]=contract['gaps']
    for e in list(doc.modelspace()):doc.modelspace().delete_entity(e)
    cursor=0
    def span(d):
        bars=[e for e in d.modelspace().query('MLINE') if e.dxf.style_name=='INI_TRAVA']
        base=min(bars,key=lambda e:min(v.location.y for v in e.vertices))
        return min(v.location.x for v in base.vertices),max(v.location.x for v in base.vertices)
    for face,units in sorted(faces.items()):
        assembly=frames.clone(units[0][0]);frames.normalize_resources(assembly);left,right=span(assembly);spans=[(left,right)]
        for i,(unit,name) in enumerate(units[1:]):
            l,r=span(unit);gaps=cima_gaps.get(face,0)
            gap=float(gaps[i] if isinstance(gaps,list) and i<len(gaps) else gaps if not isinstance(gaps,list) else 0)
            shift=right+gap-l
            frames.normalize_resources(unit)
            frames.transfer(frames.clone(unit),assembly,shift,0)
            # All width totals use y=-25 in the Nova source units.
            baseline=min((e.dxf.defpoint.y for e in assembly.modelspace().query('DIMENSION') if abs(e.dxf.defpoint2.y-e.dxf.defpoint3.y)<.001),default=-25)
            assembly.modelspace().add_linear_dim(base=(right,baseline),p1=(right,0),p2=(right+gap,0),dimstyle='INI-GRADE-REVIEW',override={'dimclrd':4,'dimclre':4,'dimclrt':1,'dimtxt':5,'dimasz':3},dxfattribs={'layer':'INI_COTA_VAO_GRADES'}).render()
            spans.append((l+shift,r+shift));right=r+shift
        complete_shared_rails(assembly,spans)
        vertical_dimensions(assembly)
        for i,((unit,name),(l,r)) in enumerate(zip(units,spans),1):
            x=(l+r)/2;y=float(pj['altura'])/2
            assembly.modelspace().add_circle((x,y),8,dxfattribs={'color':5,'layer':'NUMERACAO'})
            assembly.modelspace().add_text(str(i),dxfattribs={'color':5,'height':8,'insert':(x-3,y-4),'layer':'NUMERACAO'})
        assembly.modelspace().add_text(pj['nome']+'.'+face,dxfattribs={'layer':'NOMENCLATURA','height':14,'rotation':90,'insert':(left-10,0)})
        frames.normalize_resources(assembly)
        bb=bounds(assembly.modelspace());frames.transfer(assembly,doc,cursor-bb.extmin.x,0);cursor+=bb.size.x+40
    for y in (0,float(pj['altura'])):doc.modelspace().add_line((0,y),(cursor,y),dxfattribs={'layer':'PEDIREITO','color':2})
    frames.normalize_resources(doc)
def bounds(entities):
    b = BoundingBox()
    for e in entities:
        if e.dxftype() == 'MLINE':
            a = BoundingBox([v.location for v in e.vertices])
            s = abs(e.dxf.scale_factor)
            if a.has_data:
                b.extend([(a.extmin.x - s, a.extmin.y - s, 0), (a.extmax.x + s, a.extmax.y + s, 0)])
        else:
            a = bbox.extents([e], fast=True)
            if a.has_data:
                b.extend([a.extmin, a.extmax])
    return b

def subset(doc, entities):
    d = frames.clone(doc)
    keep = {e.dxf.handle for e in entities}
    for e in list(d.modelspace()):
        if e.dxf.handle not in keep:
            d.modelspace().delete_entity(e)
    return d

def wood_info(d):
    wood = list(d.modelspace().query('MLINE'))
    posts = [e for e in wood if e.dxf.style_name in ('INI_PONT1', 'INI_MEIOPONT') and abs(e.vertices[-1].location.y - e.vertices[0].location.y) > 15]
    bars = [e for e in wood if abs(e.vertices[-1].location.x - e.vertices[0].location.x) > abs(e.vertices[-1].location.y - e.vertices[0].location.y)]
    low = min((v.location.y for e in posts for v in e.vertices))
    high = max((v.location.y for e in posts for v in e.vertices))
    xr = max((v.location.x + abs(e.dxf.scale_factor) / 2 for e in posts for v in e.vertices))
    return (posts, bars, low, high, xr)

def vertical_dimensions(d):
    m = d.modelspace()
    for e in list(m.query('DIMENSION')):
        if abs(e.dxf.defpoint2.x - e.dxf.defpoint3.x) < 0.001:
            m.delete_entity(e)
    posts, bars, low, high, xr = wood_info(d)
    points = sorted({round(y, 5) for y in [low, high] + [e.vertices[0].location.y + s * abs(e.dxf.scale_factor) / 2 for e in bars for s in (-1, 1)] if low - 0.001 <= y <= high + 0.001})

    def vd(y1, y2, x, anchor, kind):
        dim = m.add_linear_dim(base=(x, (y1 + y2) / 2), p1=(anchor, y1), p2=(anchor, y2), angle=90, dimstyle='INI-GRADE-REVIEW', override={'dimclrd': 4, 'dimclre': 4, 'dimclrt': 1, 'dimtxt': 5, 'dimasz': 3, 'dimdec': 1, 'dimzin': 8, 'dimdsep': 44}, dxfattribs={'layer': 'INI_COTA_' + kind, 'color': 4})
        dim.render()
    for y1, y2 in zip(points, points[1:]):
        if 0.01 < y2 - y1 < high - low - 0.01:
            vd(y1, y2, xr + 25, xr, 'GRANULAR')
    vd(low, high, xr + 50, xr, 'TOTAL')
    seen = set()
    for post in posts:
        a, z = (post.vertices[0].location, post.vertices[-1].location)
        length = abs(z.y - a.y)
        if abs(length - (high - low)) < 0.01 or round(length, 3) in seen:
            continue
        seen.add(round(length, 3))
        vd(min(a.y, z.y), max(a.y, z.y), a.x - 7, a.x, 'SARRAFO')
    for e in m.query('DIMENSION'):
        for child in d.blocks.get(e.dxf.geometry):
            child.dxf.discard('true_color')
            child.dxf.color = 1 if child.dxftype() in ('TEXT', 'MTEXT') else 4
    return dict(total=high - low, granular=len(points) - 1, shorter_members=sorted(seen), chain_anchor=xr)

def complete_shared_rails(d, spans):
    posts, bars, low, high, xr = wood_info(d)
    levels = sorted({round(e.vertices[0].location.y, 6) for e in bars if abs(e.dxf.scale_factor - 10) < 0.001 and e.vertices[0].location.y + 5 < high - 0.001})
    added = []
    for left, right in spans:
        own = sorted([e for e in posts if left - 0.001 <= e.vertices[0].location.x <= right + 0.001], key=lambda e: e.vertices[0].location.x)
        for y in levels:
            run = []
            runs = []
            for post in own + [None]:
                if post is not None and max((v.location.y for v in post.vertices)) >= y + 5 - 0.001:
                    run.append(post)
                    continue
                if len(run) >= 2:
                    runs.append(run)
                run = []
            for run in runs:
                a = run[0].vertices[0].location.x - abs(run[0].dxf.scale_factor) / 2
                z = run[-1].vertices[0].location.x + abs(run[-1].dxf.scale_factor) / 2
                exists = any((abs(e.vertices[0].location.y - y) < 0.001 and abs(e.dxf.scale_factor - 10) < 0.001 and (min((v.location.x for v in e.vertices)) <= a + 0.001) and (max((v.location.x for v in e.vertices)) >= z - 0.001) for e in bars))
                if exists:
                    continue
                st = d.mline_styles.get('INI_TRAVA')
                e = d.modelspace().add_mline([(a, y), (z, y)], dxfattribs={'style_name': st.dxf.name, 'style_handle': st.dxf.handle, 'scale_factor': 10, 'justification': 1, 'layer': 'SARR_2.2x10'})
                bars.append(e)
                added.append({'left': a, 'right': z, 'height': y, 'posts': len(run)})
    return added

def convert_unit(gd,g):
  unit=subset(gd,g['entities']);unit._ini_building=True;apply_visual_mode(unit,'INI','PL')
  dim_source=next(iter(unit.modelspace().query('DIMENSION'))).dxf.dimstyle
  dst=unit.dimstyles.duplicate_entry(dim_source,'INI-GRADE-REVIEW');dst.dxf.dimclrd=4;dst.dxf.dimclre=4;dst.dxf.dimclrt=1
  for tag,fill,edge in [('INI_TRAVA',17,24),('INI_PONT1',23,18),('INI_MEIOPONT',33,12)]:
   st=unit.mline_styles.new(tag);st.dxf.flags=st.FILL|st.START_SQUARE|st.END_SQUARE;st.dxf.fill_color=fill
   st.elements.elements.clear();st.elements.append(.5,edge,'BYLAYER');st.elements.append(-.5,edge,'BYLAYER')
  for e in unit.modelspace():
   if e.dxftype()=='MLINE':
    verts=[v.location for v in e.vertices];horizontal=abs(verts[-1].x-verts[0].x)>abs(verts[-1].y-verts[0].y)
    st=unit.mline_styles.get('INI_TRAVA' if horizontal else 'INI_PONT1' if abs(e.dxf.scale_factor)>5 else 'INI_MEIOPONT')
    e.dxf.style_name=st.dxf.name;e.dxf.style_handle=st.dxf.handle;e.dxf.color=256
    e.update_geometry()
   elif e.dxftype()=='DIMENSION':
    e.dxf.dimstyle='INI-GRADE-REVIEW'
    o=e.override();o.update({'dimclrd':4,'dimclre':4,'dimclrt':1,'dimtxt':5,'dimasz':3});o.render()
   elif e.dxftype()=='HATCH':e.dxf.color=5
   elif e.dxftype() in ('LINE','LWPOLYLINE') and 'SARR' in e.dxf.layer.upper():e.dxf.color=12;e.dxf.discard('true_color')
  for bn in ('GRA-E','GRA-D'):
   if bn in unit.blocks:
    for ent in unit.blocks[bn]:ent.dxf.color=5 if ent.dxftype()=='HATCH' else 7
  # Strip clipped perimeter fragments. Real posts fit entirely inside the
  # physical base rail span; boundary fragments protrude beyond it.
  bars=[e for e in unit.modelspace().query('MLINE') if abs(e.vertices[-1].location.x-e.vertices[0].location.x)>abs(e.vertices[-1].location.y-e.vertices[0].location.y)]
  base=min(bars,key=lambda e:min(v.location.y for v in e.vertices))
  xl=min(v.location.x for v in base.vertices);xr=max(v.location.x for v in base.vertices)
  removed=[]
  for e in list(unit.modelspace().query('MLINE')):
   if e.dxf.style_name not in ('INI_PONT1','INI_MEIOPONT'):continue
   x=e.vertices[0].location.x;half=abs(e.dxf.scale_factor)/2
   if x-half<xl-.001 or x+half>xr+.001:
    removed.append({'x':x,'height':abs(e.vertices[-1].location.y-e.vertices[0].location.y)})
    unit.modelspace().delete_entity(e)
  posts=sorted([e for e in unit.modelspace().query('MLINE') if e.dxf.style_name in ('INI_PONT1','INI_MEIOPONT')],key=lambda e:e.vertices[0].location.x)
  runs=[];run=[]
  for post in posts+[None]:
   if post is not None and (not run or abs(max(v.location.y for v in post.vertices)-max(v.location.y for v in run[-1].vertices))<.001):
    run.append(post);continue
   if len(run)>=2:runs.append(run)
   run=[post] if post is not None else []
  caps=[]
  true_top=max(max(v.location.y for v in post.vertices) for post in posts)
  for run in runs:
   highest=max(v.location.y for v in run[0].vertices)
   if abs(highest-true_top)>.001:continue
   left=run[0].vertices[0].location.x-abs(run[0].dxf.scale_factor)/2
   right=run[-1].vertices[0].location.x+abs(run[-1].dxf.scale_factor)/2
   exists=any(abs(e.vertices[0].location.y-(highest-5))<.001 and abs(e.dxf.scale_factor-10)<.001 and min(v.location.x for v in e.vertices)<=left+.001 and max(v.location.x for v in e.vertices)>=right-.001 for e in bars)
   if not exists:
    st=unit.mline_styles.get('INI_TRAVA')
    unit.modelspace().add_mline([(left,highest-5),(right,highest-5)],dxfattribs={'style_name':st.dxf.name,'style_handle':st.dxf.handle,'scale_factor':10,'justification':1,'layer':'SARR_2.2x10'})
   caps.append({'posts':len(run),'height':highest,'left':left,'right':right,'already_present':exists})

  # Restore explicit triangle fills/white edges after generic iNi conversion.
  wood=list(unit.modelspace().query('MLINE'))
  bb=bounds(wood)
  if wood:
   xlo=xl
   xhi=xr
   for e in list(unit.modelspace()):
    eb=bounds([e])
    if e.dxftype() in ('HATCH','LWPOLYLINE') and eb.has_data and eb.size.x<20 and eb.size.y<20 and eb.extmax.y<20:unit.modelspace().delete_entity(e)
    elif e.dxftype()=='INSERT' and e.dxf.name.startswith('GRA-'):unit.modelspace().delete_entity(e)
   for pts in [[(xlo,0),(xlo+15,0),(xlo,15)],[(xhi,0),(xhi-15,0),(xhi,15)]]:
    h=unit.modelspace().add_hatch(color=5,dxfattribs={'layer':'INI_TRIANGULOS'});h.paths.add_polyline_path(pts,is_closed=True)
    unit.modelspace().add_lwpolyline(pts,close=True,dxfattribs={'layer':'INI_TRIANGULOS','color':7})
  frames.normalize_resources(unit)

  return unit

