"""Nova presentation adapter, shared by real N3 generation and previews.

No item geometry is copied from a reference: the asset contains only approved
wood textures and bolt end symbols. Sections and dimensions use the SA payload.
"""
from pathlib import Path
import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.math import Matrix44, Vec3

ASSET = Path(__file__).parent/'assets/nova_pillar_details.dxf'


def texture(ms, entities):
    assets=ezdxf.readfile(ASSET)
    for layer,color in [('Madeira_textura',126),('Parafuso_detalhe',8)]:
        if layer not in ms.doc.layers:
            ms.doc.layers.new(layer,dxfattribs={'color':color})
    for cell in entities:
        if cell.dxftype()!='LWPOLYLINE' or cell.dxf.layer!='Madeira': continue
        b=bbox.extents([cell]);w,h=b.size.x,b.size.y
        if w>h*1.1 or min(w,h)<=0: continue
        parts=list(assets.blocks.get('PONTALETE' if w>h*.8 else 'MEIO PONTALETE'))
        pb=bbox.extents(parts);scale=min(w/pb.size.x,h/pb.size.y)
        matrix=Matrix44.chain(Matrix44.scale(scale),Matrix44.translate(b.center.x-pb.center.x*scale,b.center.y-pb.center.y*scale,0))
        for e in parts:
            e=e.copy();e.transform(matrix);e.dxf.layer='Madeira_textura';e.dxf.color=126;ms.add_entity(e)
    profiles=[e for e in entities if 'Perfil' in e.dxf.layer]
    if not profiles: return
    bounds=bbox.extents(profiles)
    centers=set()
    for e in entities:
        if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='Hachura':
            b=bbox.extents([e])
            if b.size.x<=2.01 and b.size.y>20: centers.add(round(b.center.x,6))
    for x in centers:
        for key,y in [('HEAD_TOP',bounds.extmax.y),('HEAD_BOTTOM',bounds.extmin.y)]:
            for e in assets.blocks.get(key):
                e=e.copy();e.translate(x,y,0);e.dxf.layer='Parafuso_detalhe';e.dxf.color=8;ms.add_entity(e)


def common_top(ms, entities):
    panels=[e for e in entities if e.dxftype()=='LWPOLYLINE' and e.dxf.layer.lower().startswith('pain')]
    if not panels: return
    panel=max(panels,key=lambda e:bbox.extents([e]).size.x)
    b=bbox.extents([panel]);cx,cy=b.center.x,b.center.y
    hw,hh=b.size.x/2,b.size.y/2
    if 'NOVA_ARIAL' not in ms.doc.styles: ms.doc.styles.new('NOVA_ARIAL',dxfattribs={'font':'arial.ttf'})
    positions={'A':(cx-23,cy-hh+12),'B':(cx+18,cy+hh-12),'C':(cx-hw+20,cy-2.5),'D':(cx+hw-20,cy-2.5)}
    for e in entities:
        if e.dxftype()=='TEXT' and e.dxf.layer=='TEXTO_GERAL' and e.dxf.text in positions:
            e.dxf.insert=positions[e.dxf.text];e.dxf.height=5;e.dxf.style='NOVA_ARIAL';e.dxf.color=7
        if e.dxftype()=='HATCH' and e.dxf.pattern_name=='ANSI31': e.dxf.color=8
    before_texture={e.dxf.handle for e in ms}
    texture(ms,entities)
    local_entities=entities+[e for e in ms if e.dxf.handle not in before_texture]
    chapas=[e for e in entities if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='CHAPA' and bbox.extents([e]).size.x>bbox.extents([e]).size.y]
    upper=[bbox.extents([e]).extmin.y for e in chapas if bbox.extents([e]).extmin.y>cy]
    gap=max(0,min(upper)-b.extmax.y) if upper else 0
    for e in list(entities):
        if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='Madeira':
            eb=bbox.extents([e])
            if eb.size.x>eb.size.y*1.1: ms.delete_entity(e)
    def shift(y): return -gap if y>cy else gap
    for e in local_entities:
        if not e.is_alive: continue
        layer=e.dxf.layer
        if layer=='CHAPA' or layer.lower().startswith('pain'): e.dxf.color=1
        movable=(e in chapas or layer in ('Madeira','Madeira_textura','Parafuso_detalhe','SARRAFO','Hachura') or 'Perfil' in layer)
        if not movable or not gap: continue
        eb=bbox.extents([e])
        if e.dxftype()=='LWPOLYLINE' and eb.extmin.y<cy<eb.extmax.y:
            e.set_points([(p[0],p[1]+shift(p[1]),*p[2:]) for p in e.get_points()])
        else: e.translate(0,shift(eb.center.y),0)
    for e in entities:
        if not e.is_alive or e.dxftype()!='DIMENSION': continue
        p1,p2=e.dxf.defpoint2,e.dxf.defpoint3
        if abs(p2.x-p1.x-b.size.x)<.01: continue
        if min(p1.y,p2.y)<cy<max(p1.y,p2.y):
            for key in ('defpoint','defpoint2','defpoint3'):
                v=e.dxf.get(key);e.dxf.set(key,Vec3(v.x,v.y+shift(v.y),v.z))
            o=e.override();o.update({'dimlfac':.5,'dimtxt':5,'dimasz':3,'dimclrt':240});o.render()
        else: e.translate(0,shift((p1.y+p2.y)/2),0)


def grades(ms, entities):
    vertical=[e for e in entities if e.dxftype()=='DIMENSION' and abs(e.dxf.defpoint2.x-e.dxf.defpoint3.x)<1e-6 and abs(e.dxf.defpoint2.y-e.dxf.defpoint3.y)>1e-6]
    if vertical:
        height=max(e.get_measurement() for e in vertical)
        # Each face has its own total at the right. Redundant member heights
        # occur at the member's own X, whereas the total is outside its anchor.
        totals=[e for e in vertical if abs(e.get_measurement()-height)<.01 and e.dxf.defpoint.x>e.dxf.defpoint2.x+20]
        for e in vertical:
            if abs(e.get_measurement()-height)<.01 and e not in totals and totals:
                ms.delete_entity(e)
    bands=[]
    for e in entities:
        if e.is_alive and e.dxftype()=='LWPOLYLINE' and 'SARR' in e.dxf.layer.upper():
            b=bbox.extents([e])
            if b.size.x>b.size.y: bands.append(b)
    for e in entities:
        if not e.is_alive or e.dxftype()!='DIMENSION': continue
        a,z=e.dxf.defpoint2,e.dxf.defpoint3;o=e.override()
        o.update({'dimclrd':4,'dimclre':4,'dimclrt':1})
        if abs(a.y-z.y)<1e-6 and e.dxf.defpoint.y<min(a.y,z.y):
            e.dxf.defpoint2=Vec3(a.x,0,0);e.dxf.defpoint3=Vec3(z.x,0,0)
            o.update({'dimexo':0,'dimse1':0,'dimse2':0})
        elif e in vertical and e.get_measurement()<height-.01 and abs(e.dxf.defpoint.x-a.x)<=10:
            x=a.x-abs(e.dxf.defpoint.x-a.x)-2;e.dxf.defpoint=Vec3(x,a.y,0)
            relevant=[b for b in bands if b.extmin.x-10<=a.x<=b.extmax.x+10]
            desired=(a.y+z.y)/2;lo,hi=sorted((a.y,z.y));margin=6
            candidates=[desired]+[y for b in relevant for y in (b.extmin.y-margin,b.extmax.y+margin)]
            free=[y for y in candidates if lo+margin<=y<=hi-margin and all(y+margin<=b.extmin.y or y-margin>=b.extmax.y for b in relevant)]
            if free:o.set_location((x,min(free,key=lambda y:abs(y-desired)),0),leader=False,relative=False)
        o.render()
    for name,width,right in [('GRA-E',15,False),('GRA-D',12,True)]:
        if name not in ms.doc.blocks: continue
        block=ms.doc.blocks.get(name)
        for e in list(block):block.delete_entity(e)
        points=[(7-width,0),(7,0),(7,15)] if right else [(0,0),(15,0),(0,15)]
        h=block.add_hatch(color=252,dxfattribs={'layer':'SARR_2.2x7'});h.paths.add_polyline_path(points,is_closed=True)
        block.add_lwpolyline(points,close=True,dxfattribs={'layer':'SARR_2.2x7','color':7})


def special_payload(pj):
    from src.core.cima_l_contract import secao_l_do_payload
    sec=secao_l_do_payload(pj)
    if not sec: return None
    ex,ey,ix,iy=(sec[k] for k in ('externa_x','externa_y','interna_x','interna_y'))
    return {'geometry_points':[(0,0),(ex,0),(ex,ey-iy),(ix,ey-iy),(ix,ey),(0,ey)],
        'face_names':{'0':'A','1':'C','2':'B','3':'F','4':'D','5':'E'},
        'panel_end_cap_faces':[1,4],'metal_profile_faces':[0,2,3,5],
        'extended_grade_caps':[1,4],'inner_bolt_clearance_cm':20,
        'grade_end_offsets':{'A':[0,11],'B':[-11,-21],'E':[-11,11],'F':[4,11]}}


def apply_zone(ms,pj,zone,entities):
    if zone=='grades': grades(ms,entities)
    elif zone=='cima':
        payload=special_payload(pj)
        if payload:
            from src.core.pillar_nova_special import Drawing
            doc=Drawing(payload).generate()
            from ezdxf.enums import TextEntityAlignment
            bounds=bbox.extents(doc.modelspace())
            doc.modelspace().add_text(str(pj.get('nome') or pj.get('name') or '?'),
                dxfattribs={'layer':'NOMENCLATURA','height':5,'color':7}).set_placement(
                    (bounds.center.x,bounds.extmax.y+20),align=TextEntityAlignment.MIDDLE_CENTER)
            for e in doc.modelspace():
                if e.dxf.is_supported('color') and e.dxf.get('color',256)==256:
                    e.dxf.color=doc.layers.get(e.dxf.layer).dxf.color
            for e in entities:ms.delete_entity(e)
            imp=Importer(doc,ms.doc);imp.import_entities(doc.modelspace(),ms);imp.finalize()
        else: common_top(ms,entities)
    ms.doc._nova_design_revision='approved_dynamic_v1'
    ms.doc.ezdxf_metadata()['NOVA_DESIGN_REVISION']='approved_dynamic_v1'
