"""Formascia cut proposal, reusing the approved Nova physical construction."""
from pathlib import Path
import ezdxf
from ezdxf.addons import Importer
from ezdxf.enums import TextEntityAlignment
from src.core.lv_nova_design import draw_cut as nova_cut
from scripts.arete.lv_n3_cut_draw import load_original_fittings,insert_original_fitting

def draw_cut(contract):
 doc=nova_cut(contract)
 m=doc.modelspace();b=float(contract['width_cm']);h=float(contract['height_cm'])
 # Both Formascia assemblies have unfilled panel boards.
 for e in list(m.query('HATCH')):
  if e.dxf.solid_fill:m.delete_entity(e)
 # Sarrafeada: remove the horizontal support joining the long upright rectangles.
 if contract.get('assembly_variant')=='sarrafeadas':
  for e in list(m.query('LWPOLYLINE')):
   if e.dxf.layer!='SARR_3.5x7' or not e.closed:continue
   pts=list(e.get_points('xy'))
   width=max(p[0] for p in pts)-min(p[0] for p in pts)
   height=max(p[1] for p in pts)-min(p[1] for p in pts)
   if width>height:m.delete_entity(e)
 # Gradeada keeps its approved removal of the bottom width dimension.
 if contract.get('assembly_variant')=='gradeadas':
  for e in list(m.query('DIMENSION')):
   a,z=e.dxf.defpoint2,e.dxf.defpoint3
   if abs(a.y-z.y)<1e-6 and abs(abs(a.x-z.x)-b)<1e-6 and e.dxf.defpoint.y<0:
    m.delete_entity(e)
 colors={'Painéis':3,'CONCRETO':8,'Madeira':3,'SARR_3.5x7':2,
         'barrote':7,'Tensor7':1,'presilha':1,'SCO-___-LAJ':1,'Texto Seção':7}
 for name,color in colors.items():
  if name in doc.layers:doc.layers.get(name).dxf.color=color
  else:doc.layers.new(name,dxfattribs={'color':color})
 if 'BNC_HACHURA MADEIRAS' not in doc.layers:doc.layers.new('BNC_HACHURA MADEIRAS',dxfattribs={'color':1})
 for e in m.query('HATCH'):
  if not e.dxf.solid_fill:
   e.dxf.layer='BNC_HACHURA MADEIRAS';e.dxf.color=1
   e.set_pattern_fill('ANSI31',scale=.25)
   e.dxf.color=1
  else:e.dxf.color=8
 # Keep the 7 cm grade outside the 2.2 cm discrete side battens.
 # v03 put battens inside the post, creating an overlap.
 if contract.get('assembly_variant')=='gradeadas':
  import math
  for e in list(m.query('LWPOLYLINE')):
   if e.dxf.layer!='Madeira' or not e.closed:continue
   pts=list(e.get_points('xy'));x1,x2=min(p[0] for p in pts),max(p[0] for p in pts);y1,y2=min(p[1] for p in pts),max(p[1] for p in pts)
   if abs(x2-x1-7)>.001 or y2-y1<=7:continue
   sign=-1 if x2<=0 else 1
   # translate outward; leave a measured 2.2 cm space for the face battens
   e.set_points([(x1+sign*2.2,y1),(x2+sign*2.2,y1),(x2+sign*2.2,y2-2.2),(x1+sign*2.2,y2-2.2)]);e.dxf.color=2
   # Move Nova's cap and foot with the grade; the cap sits above the post.
   for piece in list(m.query('LWPOLYLINE HATCH')):
    if piece is e:continue
    if piece.dxftype()=='HATCH':
     if piece.dxf.solid_fill or not piece.paths:continue
     path=piece.paths[0]
     if not hasattr(path,'vertices'):continue
     pp=[(v[0],v[1]) for v in path.vertices]
    else:
     if piece.dxf.layer!='Madeira':continue
     pp=list(piece.get_points('xy'))
    if not pp:continue
    ax,bx=min(v[0] for v in pp),max(v[0] for v in pp);ay,by=min(v[1] for v in pp),max(v[1] for v in pp)
    cap=abs(ax-x1)<.001 and abs(bx-x2)<.001 and abs(ay-(y2-2.2))<.001 and abs(by-y2)<.001
    foot=abs(ay-y1)<.001 and abs(by-(y1+2.2))<.001 and (abs(bx-x1)<.001 if sign<0 else abs(ax-x2)<.001)
    if cap or foot:piece.translate(sign*2.2,0,0)
   wx1,wx2=(x2-2.2,x2) if sign<0 else (x1,x1+2.2)
   count=max(2,math.ceil((y2-y1-7)/30)+1)
   for i in range(count):
    yy=y1+(y2-y1-7)*i/(count-1);p=[(wx1,yy),(wx2,yy),(wx2,yy+7),(wx1,yy+7)]
    m.add_lwpolyline(p,close=True,dxfattribs={'layer':'Madeira','color':1})
    hh=m.add_hatch(dxfattribs={'layer':'BNC_HACHURA MADEIRAS'});hh.set_pattern_fill('ANSI31',scale=.25);hh.dxf.color=1;hh.paths.add_polyline_path(p,is_closed=True)
 # Native title proportion: 13.2 in the original 2x reference -> 6.6 at N3.
 # Keep one dimension line BELOW the name, never a duplicate above it.
 for e in m.query('TEXT'):
  if e.dxf.text==contract['beam']:e.dxf.height=6.6
  elif e.dxf.text==f'({b:g}x{h:g})':
   e.dxf.height=6.6
   e.dxf.insert=(e.dxf.insert.x,e.dxf.insert.y-4,e.dxf.insert.z)
   if e.dxf.hasattr('align_point'):e.dxf.align_point=(e.dxf.align_point.x,e.dxf.align_point.y-4,e.dxf.align_point.z)
 # The sarrafeada has no bottom screw. Preserve its Nova wood support.
 # The gradeada has one native bottom clamp pair, not a second robot fitting.
 inverted=bool(contract.get('inverted') or (contract.get('beam_type')=='inverted' and contract.get('form_role')=='top_cap'))
 if not inverted and contract.get('assembly_variant')=='gradeadas':
  load_original_fittings(doc)
  if 'BARRA_ANCORAGEM' not in doc.layers:doc.layers.new('BARRA_ANCORAGEM',dxfattribs={'color':1})
  axes=[e.dxf.start.y for e in m.query('LINE') if e.dxf.layer=='Tensor7']
  # Replace the incomplete line-only head/nut housing with native left/right
  # thread, head and inner fastener blocks. Keep a single real continuous rod.
  for yy in axes:
   for e in list(m.query('LINE')):
    a,z=e.dxf.start,e.dxf.end
    if e.dxf.layer=='Tensor7':continue
    if max(a.x,z.x)<=-24+1e-6 or min(a.x,z.x)>=b+24-1e-6:
     if min(a.y,z.y)>=yy-3.1 and max(a.y,z.y)<=yy+3.1:m.delete_entity(e)
   insert_original_fitting(m,'PAR_ESQ',-24,yy)
   head=insert_original_fitting(m,'PAR_ESQ',b+24,yy);head.dxf.xscale=-.5
   insert_original_fitting(m,'par_int_esq',-11.2,yy)
   insert_original_fitting(m,'par_int_dir',b+11.2,yy)
 # Retain the Formascia assembly callouts with the original text proportion.
 if not inverted and contract.get('assembly_variant')=='gradeadas':
  label_height=8.24999587500817/2
  for edge,sign in ((0,-1),(b,1)):
   x=edge+sign*5.5;end=edge+sign*45
   m.add_leader(vertices=[(x,-4),(x,-43),(end,-43)],dxfattribs={'layer':'COTA','color':4})
   t=m.add_text('GRADE SOLTA',dxfattribs={'layer':'Texto Seção','height':label_height,'color':2})
   t.set_placement((end,-46),align=TextEntityAlignment.MIDDLE_CENTER)
  m.add_leader(vertices=[(b/2,-7),(b/2,-60),(b/2+35,-60)],dxfattribs={'layer':'COTA','color':4})
  t=m.add_text('FUNDO ERGUIDO',dxfattribs={'layer':'Texto Seção','height':label_height,'color':2})
  t.set_placement((b/2+35,-63),align=TextEntityAlignment.MIDDLE_CENTER)
 doc.header['$INSUNITS']=5
 return doc
