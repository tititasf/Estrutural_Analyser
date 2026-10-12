"""Approved Formascia geometry. Runs only for MOLDE_1; SA stays immutable."""
from __future__ import annotations

import functools
import inspect
import copy
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Vec3
from shapely.geometry import Polygon, box, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polygonize

ASSET = Path(__file__).resolve().parents[2] / 'config/formascia/details.dxf'
EPS = 1e-5


@functools.lru_cache(maxsize=1)
def template():
    return ezdxf.readfile(ASSET)


def layer(doc, name, color):
    if name not in doc.layers:
        doc.layers.new(name, dxfattribs={'color': color})
    doc.layers.get(name).dxf.color = color


def paint(e, color):
    if e.dxf.is_supported('color'):
        e.dxf.color = color
        e.dxf.discard('true_color')


def copy_native(m, original):
    """Keep native symbol metadata valid for AutoCAD's strict DXF reader."""
    clone = original.copy()
    if clone.xdata:
        for appid in clone.xdata.data:
            if appid not in m.doc.appids:
                m.doc.appids.new(appid)
    m.add_entity(clone)
    return clone


def resources(doc):
    if 'FORMASCIA-PAINEL' in doc.dimstyles:
        return
    src = template()
    imp = Importer(src, doc)
    imp.import_table('styles')
    imp.import_table('dimstyles', entries=['FORMASCIA-PAINEL'])
    imp.import_block('_Oblique')
    imp.finalize()
    for name in ['EEEEEEEE', 'SAR15']:
        st = doc.mline_styles.get(name) if name in doc.mline_styles else doc.mline_styles.new(name)
        original = src.mline_styles.get(name)
        for key in ['flags', 'fill_color', 'start_angle', 'end_angle']:
            setattr(st.dxf, key, original.dxf.get(key))
        st.elements.elements.clear()
        for el in original.elements:
            st.elements.append(el.offset, el.color, el.linetype)
    layer(doc, 'FORMASCIA-SARRAFOS', 1)
    layer(doc, 'FORMASCIA-REFORCOS', 8)
    layer(doc, 'FORMASCIA-FOLGA', 8)
    layer(doc, 'S1', 191)
    layer(doc, 'Texto Nível', 2)


def text(m, value, p, height=6, color=7, rotation=0, name='NOMENCLATURA'):
    e = m.add_text(str(value), dxfattribs={'layer': name, 'height': height,
        'color': color, 'rotation': rotation})
    e.set_placement(p, align=TextEntityAlignment.MIDDLE_CENTER)
    return e


def dimensions(m, entities, zone):
    resources(m.doc)
    tiers = {}
    used = set()
    verticals = [e for e in entities if e.is_alive and e.dxftype() == 'DIMENSION'
                 and abs(e.dxf.get('angle', 0)-90)<EPS]
    for e in list(entities):
        if not e.is_alive or e.dxftype() != 'DIMENSION':
            continue
        a, b, base = e.dxf.defpoint2, e.dxf.defpoint3, e.dxf.defpoint
        angle = e.dxf.get('angle', 0)
        value, label = e.get_measurement(), e.dxf.get('text', '<>')
        if zone == 'grades' and abs(angle-90)<EPS and value>150:
            key = (round(a.y, 4), round(value, 4),
                   sum(1 for n in entities if n.is_alive and n.dxftype()=='TEXT'
                       and n.dxf.layer=='NOMENCLATURA' and n.dxf.insert.x<a.x))
            if key in used:
                m.delete_entity(e)
                continue
            used.add(key)
        if zone == 'abcd' and abs(angle-90)<EPS and value<20:
            key = round(a.x, 3)
            tier = tiers.get(key, 0); tiers[key] = tier+1
            base = base.replace(x=a.x+35+tier*24)
        m.delete_entity(e)
        d = m.add_linear_dim(base=base, p1=a, p2=b, angle=angle, text=label,
            dimstyle='FORMASCIA-PAINEL', override={'dimdec':1,'dimzin':8,'dimdsep':44},
            dxfattribs={'layer':'COTA','color':4})
        if abs(angle-90)<EPS and value<20:
            d.set_location((base.x-8, (a.y+b.y)/2 if zone=='grades' else min(a.y,b.y)-12),
                           leader=False, relative=False)
        d.render()
        if zone=='abcd' and abs(value-2)<EPS:
            # Symbols are normalized to the original folga dimension base.
            for original in template().modelspace():
                if original.dxf.layer=='FORMASCIA-FOLGA':
                    clone=copy_native(m, original)
                    clone.translate(base.x, min(a.y,b.y), 0)


def mline(m, points, style='EEEEEEEE', color=8, scale=1, justification=0):
    if style == 'EEEEEEEE' and color == 8:
        # AutoCAD resolves BYLAYER fill through the imported sheet layer,
        # which can be red. Keep PL gray independent of template resources.
        name = 'FORMASCIA-PL-SARRAFO-CINZA'
        if name not in m.doc.mline_styles:
            original = m.doc.mline_styles.get(style)
            native = m.doc.mline_styles.new(name)
            for attr in ('flags', 'start_angle', 'end_angle'):
                setattr(native.dxf, attr, original.dxf.get(attr))
            native.dxf.fill_color = 8
            native.elements.elements.clear()
            for element in original.elements:
                native.elements.append(element.offset, 8, element.linetype)
        style = name
    layer(m.doc, 'FORMASCIA-SARRAFOS', 8)
    e=m.add_mline(points,dxfattribs={'layer':'FORMASCIA-SARRAFOS',
        'style_name':style,'color':color,'scale_factor':scale,'justification':justification})
    return e


def filled(e):
    polys=[]
    for v in e.virtual_entities():
        if v.dxftype()=='HATCH':
            polys.extend(Polygon([(p[0],p[1]) for p in path.vertices])
                         for path in v.paths if hasattr(path,'vertices'))
    return unary_union(polys)


def boundaries(entities, names=('Painéis',)):
    lines=[]
    for e in entities:
        if not e.is_alive or e.dxf.layer not in names:
            continue
        if e.dxftype()=='LINE':
            lines.append(LineString([(e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)]))
        elif e.dxftype()=='LWPOLYLINE':
            pts=list(e.get_points('xy'))
            if e.closed and pts: pts.append(pts[0])
            if len(pts)>=2: lines.append(LineString(pts))
    return unary_union(list(polygonize(unary_union(lines))))


def abcd(m, pj, entities):
    resources(m.doc)
    layer(m.doc, 'FORMASCIA-VAZIOS', 8)
    layer(m.doc, 'NUMERACAO_PAINEIS', 7)
    panels=boundaries(entities)
    obstacles=[]
    for e in entities:
        if e.is_alive and e.dxftype()=='HATCH':
            e.dxf.layer='FORMASCIA-VAZIOS'
            e.set_pattern_fill('AR-CONC',scale=.1,angle=0,color=8)
            for path in e.paths:
                if hasattr(path,'vertices'):
                    poly=Polygon([(v[0],v[1]) for v in path.vertices])
                    if poly.is_valid: obstacles.append(poly)
    names=sorted([e for e in entities if e.is_alive and e.dxftype()=='TEXT'
                  and e.dxf.layer=='NOMENCLATURA' and '.' in e.dxf.text],key=lambda e:e.dxf.insert.x)
    for e in list(entities):
        if e.is_alive and (e.dxf.layer == 'SARR_2.2x7'
            and not (e.dxf.layer=='SARR_2.2x7' and e.dxf.get('linetype','').upper() in ('DASHED','HIDDEN'))
            or e.dxf.layer=='NOMENCLATURA' and e.dxftype()=='TEXT' and e not in names):
            m.delete_entity(e)
    panel_labels=[]
    for index, name in enumerate(names):
        face=name.dxf.text.split('.')[-1]
        # Face envelope comes from generated panel contours, never item coordinates.
        nx=name.dxf.insert.x
        next_x=names[index+1].dxf.insert.x if index+1<len(names) else float('inf')
        face_edges=[]
        for edge in entities:
            if edge.is_alive and edge.dxf.layer=='Painéis':
                bounds=bbox.extents([edge])
                if bounds.has_data and bounds.extmin.x>=nx-EPS and bounds.extmax.x<next_x:
                    face_edges.append(edge)
        envelope=bbox.extents(face_edges)
        if not envelope.has_data:continue
        xl,xr=envelope.extmin.x,envelope.extmax.x
        levels=bbox.extents([e for e in entities if e.is_alive and e.dxf.layer=='Nível'])
        yb=levels.extmin.y if levels.has_data else envelope.extmin.y
        yt=envelope.extmax.y
        region=box(xl,yb,xr,yt)
        candidates=[]
        level=yb+float(pj.get(f'h1_{face}',2) or 0)
        for height in pj.get(f'paineis_intervals_{face}') or []:
            upper=min(level+float(height),yt)
            if upper>level+EPS:candidates.append(box(xl,level,xr,upper))
            level+=float(height)
        if not candidates:candidates=[region]
        available=region.difference(unary_union(obstacles))
        # Numbers belong to logical manufacturing panels, including panels
        # with corner cuts. Place labels in the remaining solid region.
        numbered=[]
        cap_height=float(pj.get(f'rebaixo_laje_{face}',0) or 0)
        slab_height=float(pj.get(f'vazio_laje_{face}',0) or 0)
        cap_bottom=yt-cap_height
        for candidate in candidates:
            lo,hi=candidate.bounds[1],candidate.bounds[3]
            # A slab separates the narrow cap from the manufacturing panel
            # below it. Opening cuts alone do not create extra panel numbers.
            if cap_height>EPS and slab_height>EPS and lo+EPS<cap_bottom<hi-EPS:
                numbered.extend([box(xl,lo,xr,cap_bottom),box(xl,cap_bottom,xr,hi)])
            else:
                numbered.append(candidate)
        number=0
        for candidate in numbered:
            solid=available.intersection(candidate)
            if not solid.is_empty and solid.area>EPS:
                pieces=list(solid.geoms) if hasattr(solid,'geoms') else [solid]
                solid=max(pieces,key=lambda piece:piece.area)
                center=solid.centroid
                if not solid.contains(center):center=solid.representative_point()
                number+=1
                radius=min(6.,(xr-xl)/4.,(solid.bounds[3]-solid.bounds[1])/4.)
                panel_labels.append(((center.x,center.y),radius,number))
        if face in 'ABEFGH':
            pieces=list(available.geoms) if hasattr(available,'geoms') else [available]
            retained=[]
            for piece in pieces:
                for a,b in zip(list(orient(piece,sign=-1).exterior.coords),list(orient(piece,sign=-1).exterior.coords)[1:]):
                    ax,ay=a; bx,by=b
                    if abs(ay-by)<EPS and ay>yb+2+EPS:
                        if ay<yt-EPS:
                            direction=1 if bx>ax else -1
                            ax+=direction*7 if abs(ax-xl)<.01 or abs(ax-xr)<.01 else -direction*7
                            bx-=direction*7 if abs(bx-xl)<.01 or abs(bx-xr)<.01 else -direction*7
                        if abs(bx-ax)<EPS: continue
                    elif abs(ax-bx)<EPS and xl+EPS<ax<xr-EPS:
                        if ay>by: ay-=7
                        else: by-=7
                        if abs(by-ay)<EPS: continue
                    else: continue
                    e=mline(m,[(ax,ay),(bx,by)])
                    strip=filled(e); clipped=strip.intersection(available)
                    if clipped.is_empty:
                        m.delete_entity(e); continue
                    if strip.difference(available).area>EPS and abs(ay-by)<EPS:
                        lo,_,hi,_=clipped.bounds
                        e.generate_geometry(Vec3.list([(lo,ay),(hi,by)] if bx>ax else [(hi,ay),(lo,by)]))
                        strip=filled(e)
                    if any(strip.symmetric_difference(old).area<EPS for old in retained):
                        m.delete_entity(e)
                    else: retained.append(strip)
        else:
            # Physical panel pieces retain independent end assemblies.
            for piece in candidates:
                for reg in (list(piece.difference(unary_union(obstacles)).geoms)
                            if hasattr(piece.difference(unary_union(obstacles)),'geoms')
                            else [piece.difference(unary_union(obstacles))]):
                    if reg.is_empty: continue
                    l,b,r,t=reg.bounds
                    if t-b<14 or r-l<7: continue
                    leg=min(30.,(t-b-18)/2)
                    top=[(l,t-leg),(l,t),(r,t),(r,t-leg)]
                    bottom=[(l,b+leg),(l,b),(r,b),(r,b+leg)]
                    if xr-xl>=30-EPS: top=top[1:3]; bottom=bottom[1:3]
                    mline(m,top,'SAR15',7)
                    mline(m,bottom,'SAR15',7,-1)
    # Create labels after filled MLINEs so thin cap numbers remain visible
    # in AutoCAD as well as in previews.
    for center,radius,number in panel_labels:
        m.add_circle(center,radius,dxfattribs={'layer':'NUMERACAO_PAINEIS','color':1})
        text(m,number,center,radius*1.25,7,name='NUMERACAO_PAINEIS')
    dimensions(m,entities,'abcd')
    if not panels.is_empty:
        xl,yb,xr,yt=panels.bounds
        levels=bbox.extents([e for e in entities if e.is_alive and e.dxf.layer=='Nível'])
        if levels.has_data:yb,yt=levels.extmin.y,levels.extmax.y
        dims=[e for e in m if e.dxftype()=='DIMENSION' and abs(e.dxf.get('angle',0)-90)<EPS]
        mx=min([xl]+[e.dxf.defpoint.x for e in dims])-115
        level_markers(m,pj,yb,yt,mx)
        trim_level_spans(m,entities)


def level_markers(m,pj,yb,yt,mx):
    """Native arrows and real floor labels, shared by elevations and grades."""
    for y,key,floor_key in [(yb,'nivel_saida_abs','pavimento'),(yt,'nivel_chegada_abs','pavimento_chegada')]:
        if key not in pj: continue
        for original in template().modelspace():
            if original.dxf.layer=='S1':
                clone=copy_native(m, original); clone.translate(mx,y,0)
        live_base=(pj.get('_sa_mode_contract') or {}).get('n1_base') or {}
        floor=pj.get(floor_key)
        if not floor or str(floor).strip().casefold()=='pavimento':
            floor=live_base.get(floor_key) or (pj.get('pavimento_nome') if floor_key=='pavimento' else None)
        if floor: text(m,floor,(mx+46,y+38.85),10,2,name='Texto Nível')
        text(m,f"{float(pj[key]):.2f}".replace('.',','),(mx+46,y+23.56),10,2,name='Texto Nível')


def trim_level_spans(m,entities):
    levels=[e for e in entities if e.is_alive and e.dxf.layer=='Nível' and e.dxftype()=='LWPOLYLINE']
    content=bbox.extents([e for e in m if e.dxf.layer!='Nível'])
    if not content.has_data:return
    for line in levels:
        y=line.get_points()[0][1]
        line.set_points([(content.extmin.x,y),(content.extmax.x+15,y)])



def grades(m, pj, entities):
    resources(m.doc)
    from scripts.visual_modes import _line_rectangles
    rectangles=list(_line_rectangles([e for e in entities if e.dxftype()=='LINE' and e.dxf.layer.startswith('SARR_')]))
    bases=[(g,b) for g,b in rectangles if abs(b[3]-b[1]-2.2)<EPS and b[2]-b[0]>15]
    drawn_bands=[]
    for group,base in bases:
        l,y,r,by=base
        posts=sorted([(b[0],b[2],b[3]-by) for g,b in rectangles
                      if b[0]>=l-EPS and b[2]<=r+EPS and abs(b[1]-by)<EPS
                      and b[3]-b[1]>14 and b[2]-b[0]<=7+EPS])
        if not posts: continue
        for g,b in rectangles:
            if g[0].is_alive and g[0].dxf.layer=='SARR_2.2x10' and b[0]>=l-EPS and b[2]<=r+EPS:
                for e in g:
                    if e.is_alive: m.delete_entity(e)
        bands=[]
        from scripts.drawing_mode_config import grade_positions
        positions=grade_positions('MOLDE_1') or [50.,120.,180.]
        for height in positions:
            run=[]
            for post in posts+[None]:
                if post is not None and post[2]>=height+10-EPS: run.append(post)
                else:
                    if len(run)>=2: bands.append(box(run[0][0],by+height,run[-1][1],by+height+10))
                    run=[]
        run=[]; maximum=max(p[2] for p in posts)
        for post in posts+[None]:
            if post is not None and (not run or abs(post[2]-run[-1][2])<EPS): run.append(post);continue
            if len(run)>=2 and abs(run[0][2]-maximum)<EPS:
                bands.append(box(run[0][0],by+maximum-10,run[-1][1],by+maximum))
            run=[] if post is None else [post]
        union=unary_union(bands)
        drawn_bands.extend(bands)
        for region in list(union.geoms) if hasattr(union,'geoms') else [union]:
            if not region.is_empty: m.add_lwpolyline(list(region.exterior.coords)[:-1],close=True,
                dxfattribs={'layer':'SARR_2.2x10','color':1})
    for e in entities:
        if not e.is_alive: continue
        if e.dxftype()=='INSERT' and e.dxf.name in ('GRA-E','GRA-D'):
            bounds=bbox.extents([e]); anchor=bounds.extmin.x if e.dxf.name=='GRA-E' else bounds.extmax.x
            bottom=bounds.extmin.y; direction=1 if e.dxf.name=='GRA-E' else -1
            m.delete_entity(e)
            for original in template().modelspace():
                if original.dxf.layer=='FORMASCIA-REFORCOS':
                    clone=copy_native(m, original)
                    if direction<0: clone.scale(-1,1,1)
                    clone.translate(anchor,bottom,0)
        elif e.dxf.layer.startswith('SARR_'): paint(e,1)
        elif e.dxftype()=='TEXT': paint(e,7)
    # Only the rightmost grade carries the total, outside its current chain.
    # Measure above the bottom timber, matching the post dimension convention.
    if bases:
        _, base = max(bases, key=lambda item:item[1][2])
        l, _, r, by = base
        tops = [b[3] for _,b in rectangles
                if b[0]>=l-EPS and b[2]<=r+EPS and abs(b[1]-by)<EPS
                and b[3]-b[1]>14 and b[2]-b[0]<=7+EPS]
        if tops:
            top = max(tops); total = top-by
            verticals = [e for e in entities if e.is_alive and e.dxftype()=='DIMENSION'
                         and abs(e.dxf.get('angle',0)-90)<EPS]
            outer = max([r]+[e.dxf.defpoint.x for e in verticals])+24
            for e in verticals:
                # Legacy chains describe the pre-Formascia timber positions.
                # Replace them with intervals of the bands actually drawn.
                old_chain=(abs(e.dxf.defpoint2.x-r)<EPS
                           and abs(e.dxf.defpoint3.x-r)<EPS)
                # Equal-length post dimensions add no information to the total.
                if old_chain or abs(e.get_measurement()-total)<EPS:
                    m.delete_entity(e)
            intervals=sorted((b.bounds[1],b.bounds[3]) for b in drawn_bands
                if b.bounds[0]>=l-EPS and b.bounds[2]<=r+EPS)
            merged=[]
            for low,high in intervals:
                if merged and low<=merged[-1][1]+EPS:
                    merged[-1]=(merged[-1][0],max(high,merged[-1][1]))
                else: merged.append((low,high))
            points=sorted({round(y,6) for y in [by,top]
                +[y for interval in merged for y in interval] if by-EPS<=y<=top+EPS})
            for low,high in zip(points,points[1:]):
                if high-low<EPS or abs(high-low-total)<EPS: continue
                dim=m.add_linear_dim(base=(r+30,(low+high)/2),
                    p1=(r,low),p2=(r,high),angle=90,
                    dimstyle='FORMASCIA-PAINEL',dxfattribs={'layer':'COTA','color':4})
                entities.append(dim.dimension)
                dim.render()
            dim=m.add_linear_dim(base=(outer,(by+top)/2),p1=(r,by),p2=(r,top),
                angle=90,dimstyle='FORMASCIA-PAINEL',
                override={'dimdec':1,'dimzin':8,'dimdsep':44},
                dxfattribs={'layer':'COTA','color':4})
            dim.render()
    dimensions(m,entities,'grades')
    # The level datum follows SA height; a shortened grade post is not a floor.
    wood=bbox.extents([e for e in m if e.dxf.layer.startswith('SARR_')])
    if wood.has_data:
        yb=wood.extmin.y;yt=yb+float(pj['altura'])
        dims=[e for e in m if e.dxftype()=='DIMENSION' and abs(e.dxf.get('angle',0)-90)<EPS]
        mx=min([wood.extmin.x]+[e.dxf.defpoint.x for e in dims])-115
        level_markers(m,pj,yb,yt,mx)
        layer(m.doc,'Nível',8)
        for y in (yb,yt):
            m.add_lwpolyline([(wood.extmin.x,y),(wood.extmax.x,y)],dxfattribs={'layer':'Nível','color':8,'linetype':'DASHED'})
        trim_level_spans(m,list(m))



def cima(m,pj,entities):
    resources(m.doc)
    layer(m.doc,'FORMASCIA-VEIOS',1)
    layer(m.doc,'FORMASCIA-PARAFUSOS',8)
    for e in entities:
        k=e.dxf.layer.casefold()
        c=7 if e.dxftype() in ('TEXT','MTEXT') else 8
        if k in ('painéis','chapa'):
            c=1 if e.dxftype()=='HATCH' and not e.dxf.solid_fill else 3
        elif k in ('madeira','sarrafo') or k.startswith('sarr'): c=1
        elif k=='hachura': c=1 if e.dxftype()=='HATCH' else 8
        paint(e,c)
        if e.dxftype()=='DIMENSION':
            d=e.override(); d.update({'dimclrd':8,'dimclre':8,'dimclrt':8,'dimdsep':44,'dimdec':1,'dimzin':8});d.render()
    cima_details(m,entities)


@functools.lru_cache(maxsize=1)
def cima_template():
    return ezdxf.readfile(ASSET.with_name('cima_details.dxf'))


def cima_details(m,entities):
    """Original wood grain and bolt ends, positioned by generated geometry."""
    src=cima_template()
    names=('C','A$C521F0DC7','A$C07E1659E')
    importer=Importer(src,m.doc)
    for name in names:
        if name not in m.doc.blocks: importer.import_block(name)
    importer.finalize()
    def primitives(name,point,sx,sy,rotation,layer_name,color):
        ref=m.add_blockref(name,point,dxfattribs={'xscale':sx,'yscale':sy,'rotation':rotation})
        for child in ref.virtual_entities():
            child.dxf.layer=layer_name;paint(child,color);m.add_entity(child)
        m.delete_entity(ref)
    for e in entities:
        if not e.is_alive:continue
        k=e.dxf.layer.casefold()
        if e.dxftype()=='HATCH' and k=='hachura':
            # Cross-section squares use wood grain curves, not diagonal fill.
            m.delete_entity(e)
        elif e.dxftype()=='LWPOLYLINE' and k=='madeira' and e.closed:
            b=bbox.extents([e]);w=b.size.x;h=b.size.y
            if w<=14.01 and h<=14.01 and w>0 and h>0:
                name='A$C07E1659E' if abs(w-h)<EPS else 'A$C521F0DC7'
                original=bbox.extents([q for q in src.blocks[name] if q.dxftype()=='LWPOLYLINE'])
                ref=m.add_blockref(name,(0,0),dxfattribs={'xscale':w/original.size.x,'yscale':h/original.size.y})
                for child in ref.virtual_entities():
                    if child.dxftype()=='LWPOLYLINE':continue
                    child.translate(b.extmin.x,b.extmin.y,0);child.dxf.layer='FORMASCIA-VEIOS';paint(child,1);m.add_entity(child)
                m.delete_entity(ref)
    bolts={}
    shafts={}
    for e in entities:
        if e.is_alive and e.dxftype()=='LWPOLYLINE' and e.dxf.layer.casefold()=='hachura':
            b=bbox.extents([e])
            if min(b.size.x,b.size.y)<3 and max(b.size.x,b.size.y)>3:
                axis=1 if b.size.y>b.size.x else 0
                key=(axis,round(b.center[1-axis],5))
                shafts.setdefault(key,[]).append(e)
                low,high=bolts.get(key,(b.extmin[axis],b.extmax[axis]))
                bolts[key]=(min(low,b.extmin[axis]),max(high,b.extmax[axis]))
    for (axis,station),(low,high) in bolts.items():
        profiles=[]
        for e in entities:
            if not e.is_alive or e.dxf.layer!='Perfil Metálico':continue
            b=bbox.extents([e])
            if b.has_data and b.size[1-axis]>b.size[axis]:profiles.append(e)
        metal=boundaries(profiles,('Perfil Metálico',))
        if metal.is_empty:continue
        bounds=metal.bounds
        endpoints=[(station,bounds[1]-1),(station,bounds[3]+1)] if axis else [(bounds[0]-1,station),(bounds[2]+1,station)]
        contacts=metal.intersection(LineString(endpoints))
        pieces=list(contacts.geoms) if hasattr(contacts,'geoms') else [contacts]
        if len([p for p in pieces if p.length>EPS])<2:continue
        if not contacts.is_empty:
            old_low,old_high=low,high
            low=contacts.bounds[axis]
            high=contacts.bounds[axis+2]
            for shaft in shafts[(axis,station)]:
                points=[]
                for px,py,sw,ew,bulge in shaft.get_points():
                    point=[px,py];v=point[axis]
                    point[axis]=low if v<=old_low+EPS else high if v>=old_high-EPS else max(low,min(high,v))
                    points.append((*point,sw,ew,bulge))
                shaft.set_points(points)
        for contact,sx,edge in ((low,2,'extmax'),(high,-2,'extmin')):
            rotation=270 if axis else 180
            probe=m.add_blockref('C',(0,0),dxfattribs={'xscale':sx,'yscale':2,'rotation':rotation})
            bounds=bbox.extents(list(probe.virtual_entities()))
            offset=getattr(bounds,edge)[axis]
            m.delete_entity(probe)
            point=(station,contact-offset) if axis else (contact-offset,station)
            primitives('C',point,sx,2,rotation,'FORMASCIA-PARAFUSOS',8)


def cima_rectangular(m,pj,entities):
    """Approved Cima layout, calculated from the current panel contract."""
    if str(pj.get('subtipo_pil','RETANGULAR')).upper() not in ('','RETANGULAR'):
        return
    from scripts.gerar_pl_dxf_stog import cima_layout_contract
    dims=[e for e in entities if e.is_alive and e.dxftype()=='DIMENSION']
    metal=[e for e in entities if e.is_alive and e.dxf.layer=='Perfil Metálico']
    mb=bbox.extents(metal)
    if not mb.has_data:return
    c=float(pj['comprimento']);w=float(pj['largura'])
    panel=bbox.extents([e for e in entities if e.is_alive and e.dxf.layer in ('CHAPA','Painéis')])
    if not panel.has_data:return
    ox=panel.center.x;oy=panel.center.y
    left=ox-c-22;right=ox+c+22;bottom=oy-w;top=oy+w
    bolts=[(e.dxf.defpoint2.x,e.dxf.defpoint3.x) for e in dims
           if abs(e.dxf.defpoint2.y-e.dxf.defpoint3.y)<.01 and e.dxf.defpoint.y>top+40]
    for e in list(entities):
        if e.is_alive and e.dxftype() in ('TEXT','MTEXT','DIMENSION'):m.delete_entity(e)
    ds='FORMASCIA-CIMA'
    if ds not in m.doc.dimstyles:
        m.doc.dimstyles.new(ds,dxfattribs={'dimtxt':7,'dimasz':2,'dimclrd':8,'dimclre':8,
            'dimclrt':8,'dimlfac':.5,'dimdec':1,'dimdsep':44,'dimzin':8,'dimgap':2})
    def dim(a,b,base,angle=0,label='<>'):
        m.add_linear_dim(base=base,p1=a,p2=b,angle=angle,text=label,dimstyle=ds,
                         dxfattribs={'layer':'COTA','color':8}).render()
    layout=cima_layout_contract(pj,c)
    for start,segments in zip(layout['starts'],layout['divisions_a']):
        x=left+2*start
        for value in segments:
            nx=x+2*float(value);dim((x,bottom-18),(nx,bottom-18),(x,bottom-62));x=nx
    dim((left,bottom-18),(right,bottom-18),(left,bottom-85),label='<>-PAINEL/GRADE')
    dim((ox-c,bottom),(ox+c,bottom),(ox-c,oy-2))
    dim((ox+c,bottom),(ox+c,top),(right+24,bottom),90)
    dim((left,bottom+4),(ox-c-8,bottom+4),(left,bottom+12))
    dim((ox+c+8,bottom+4),(right,bottom+4),(ox+c+8,bottom+12))
    for a,b in bolts:dim((a,top+55),(b,top+55),(a,top+88))
    dim((mb.extmin.x,top+38),(mb.extmax.x,top+38),(mb.extmin.x,top+114),label='Perfil Metálico L=<>')
    for v,x,y in [('A',ox-c*.32,bottom+8),('B',ox-c*.32,top-8),('C',ox-c+5,oy),('D',ox+c-5,oy)]:
        text(m,v,(x,y),9.6)
    text(m,pj['nome'],(mb.extmin.x-58,oy+12),16)
    text(m,f'({w:g}X{c:g})',(mb.extmin.x-58,oy-12),12)


def apply_zone(m,pj,zone,entities):
    # The generator's legacy DASHED record contains only a gap. Normalize
    # the Formascia PL resource locally, without changing other modes/classes.
    if 'DASHED' in m.doc.linetypes:
        m.doc.linetypes.get('DASHED').setup_pattern([5.0, 3.0, -2.0])
    if zone in ('abcd','efgh'):
        for e in entities:
            paint(e,3 if e.dxf.layer=='Painéis' else 1 if e.dxf.layer.startswith('SARR_') else 8 if e.dxftype()=='HATCH' else 7)
        abcd(m,pj,entities)
    elif zone=='grades': grades(m,pj,entities)
    elif zone=='cima':
        cima(m,pj,entities);cima_rectangular(m,pj,entities)
    # Imported arrow-block layers may retain handles from the source drawing.
    # PL Formascia uses the target document's default material and plot style.
    for entry in m.doc.layers:
        for attr, kind in (('material_handle', 'MATERIAL'), ('plotstyle_handle', 'ACDBPLACEHOLDER')):
            handle = entry.dxf.get(attr)
            target = m.doc.entitydb.get(handle) if handle else None
            if handle and (target is None or target.dxftype() != kind):
                entry.dxf.discard(attr)
        entry.set_required_attributes()


def wrap_draw(function,zone):
    signature=inspect.signature(function)
    @functools.wraps(function)
    def wrapped(*args,**kwargs):
        bound=signature.bind(*args,**kwargs);m=bound.arguments['msp']
        if zone in ('abcd','efgh'):
            from scripts.pl_abcd_visual_nova import distribute_paineis_nova
            pj=copy.deepcopy(bound.arguments['pj'])
            for face in 'ABEFGH':
                intervals=pj.get(f'paineis_intervals_{face}') or []
                # Preserve explicit unions and their manufacturing boundaries.
                if intervals and not pj.get(f'paineis_unidos_{face}'):
                    pj[f'paineis_intervals_{face}']=distribute_paineis_nova(sum(map(float,intervals)))
            bound.arguments['pj']=pj
        before={e.dxf.handle for e in m}
        result=function(*bound.args,**bound.kwargs)
        apply_zone(m,bound.arguments['pj'],zone,[e for e in m if e.dxf.handle not in before])
        return result
    wrapped._formascia_wrapped=True
    return wrapped


def fv_sarrafo(m,x0,y0,height,widths,verts=None,panel_items=None,left=True,right=True):
    """End assemblies from the union of the actual manufacturing outlines."""
    resources(m.doc)
    name='FORMASCIA-FV-7'
    if name not in m.doc.mline_styles:
        st=m.doc.mline_styles.new(name);st.dxf.flags=1;st.dxf.fill_color=256
        st.elements.elements.clear()
        for off in (0,-7):st.elements.append(off,256,'BYLAYER')
    polygons=[];cursor=x0
    for i,width in enumerate(widths):
        item=panel_items[i] if panel_items and i<len(panel_items) else {}
        points=verts[i] if verts and i<len(verts) else None
        if points:
            p=Polygon([(cursor+float(v['x']),y0+float(v['y'])) for v in points])
        else:
            ph=float(item.get('height',height) or height)
            bottom=y0+height-ph if item.get('is_L_drop') else y0
            p=box(cursor,bottom,cursor+width,bottom+ph)
        for op in item.get('aberturas',[]):
            p=p.difference(box(cursor+float(op['x1']),y0+float(op['y1']),
                               cursor+float(op['x2']),y0+float(op['y2'])))
        polygons.append(p);cursor+=width
    outline=unary_union(polygons)
    # A central void must be represented by two corner segments.
    pieces=split_fv_openings(outline)
    if any(p.interiors for p in (list(outline.geoms) if hasattr(outline,'geoms') else [outline])):
        # Manufacturing segments have corner cuts, never an interior ring.
        # Redraw only this run's panel edges, preserving physical panel unions.
        l,b,r,t=outline.bounds
        for e in list(m):
            if e.dxftype()!='LINE' or e.dxf.layer.casefold() not in {'painéis','paineis'}:continue
            if all(l-EPS<=q.x<=r+EPS and b-EPS<=q.y<=t+EPS for q in (e.dxf.start,e.dxf.end)):
                m.delete_entity(e)
        seen=set()
        for original in polygons:
            for piece in pieces:
                cut=original.intersection(piece)
                for part in list(cut.geoms) if hasattr(cut,'geoms') else [cut]:
                    if part.geom_type!='Polygon' or part.is_empty:continue
                    coords=list(part.exterior.coords)
                    for a,c in zip(coords,coords[1:]):
                        key=tuple(sorted(tuple(round(v,6) for v in q) for q in (a,c)))
                        if key in seen:continue
                        seen.add(key);m.add_line(a,c,dxfattribs={'layer':'Painéis','color':3})
    for poly in pieces:
        coords=list(orient(poly,sign=-1).exterior.coords)[:-1]
        l,b,r,t=poly.bounds
        branch=t-b>height+EPS and len(coords)>4
        def ml(a,c): return mline(m,[a,c],name,1,justification=1)
        for i,a in enumerate(coords):
            c=coords[(i+1)%len(coords)];dx,dy=c[0]-a[0],c[1]-a[1]
            if abs(dy)<EPS: continue
            if branch and min(a[0],c[0])>l+EPS: continue
            if branch and min(a[1],c[1])>b+EPS: continue
            if branch and abs(a[0]-c[0])<EPS and l+EPS<a[0]<r-EPS: continue
            is_left=dy>0
            if is_left and not left or not is_left and not right: continue
            sign=1 if is_left else -1
            pa=(a[0]+sign*2,a[1]);pc=(c[0]+sign*2,c[1])
            prev=coords[(i-1)%len(coords)];nxt=coords[(i+2)%len(coords)]
            # Concave endpoint extends by the native 7 cm section for the extra rail.
            def concave(p,q,s):
                return (q[0]-p[0])*(s[1]-q[1])-(q[1]-p[1])*(s[0]-q[0])>EPS
            start_inner=concave(prev,a,c);end_inner=concave(a,c,nxt)
            start_y=pa[1]-7 if start_inner and dy>0 else pa[1]+7 if start_inner else pa[1]
            end_y=pc[1]+7 if end_inner and dy>0 else pc[1]-7 if end_inner else pc[1]
            spine=ml((pa[0],start_y),(pc[0],end_y))
            if abs(dx)>EPS:
                # Bevel end plane follows the true diagonal, with horizontal cuts.
                for v in spine.vertices:v.miter_direction=Vec3(-sign,0,0)
                spine._update_parametrization()
            length=min(30.,max(0,(r-l-4)/2))
            # Each horizontal uses the same free length; two opposing rails cannot overlap.
            for p,inner in ((pa,start_inner),(pc,end_inner)):
                if not branch and b+EPS<p[1]<t-EPS and not inner: continue
                below=p[1]<=b+EPS or inner and not is_left
                end=(p[0]+sign*length,p[1])
                # Orientation selects whether the native fill is above or below the axis.
                pair=(end,p) if below and sign>0 or not below and sign<0 else (p,end)
                rail=ml(*pair)
                if abs(dx)>EPS:
                    idx=0 if pair[0]==p else 1
                    rail.vertices[idx].miter_direction=Vec3(dx/abs(dy),sign,0).normalize() * (1 if idx==0 else -1)
                    rail._update_parametrization()
        if branch:
            topedges=[(a,coords[(i+1)%len(coords)]) for i,a in enumerate(coords)
                      if abs(a[1]-t)<EPS and abs(coords[(i+1)%len(coords)][1]-t)<EPS]
            for a,c in topedges:
                lo,hi=sorted((a[0],c[0]));yy=t-2
                ml((lo,yy),(hi,yy));length=min(30.,max(7,t-b))
                ml((lo,yy-length),(lo,yy));ml((hi,yy),(hi,yy-length))
        text(m,'A-----A',(l+3,b+(min(t,b+height)-b)/2),6)
        text(m,'B-----B',(r-9,t-15 if branch else b+(t-b)/2),6,rotation=90 if branch else 0)
        # Number only in the available area between end assemblies.
        cursor=x0
        for i,width in enumerate(widths,1):
            fl=max(cursor,l+32);fr=min(cursor+width,r-32)
            free=poly.intersection(box(fl,b,fr,t)) if fr-fl>=20 else Polygon()
            if not free.is_empty:
                p=free.representative_point()
                m.add_circle((p.x,p.y),10,dxfattribs={'layer':'NOMENCLATURA','color':1})
                text(m,i,(p.x,p.y),12)
            cursor+=width


def split_fv_openings(poly):
    """Partition interior openings into two complementary, hole-free corner pieces."""
    pieces=list(poly.geoms) if hasattr(poly,'geoms') else [poly]
    result=[]
    while pieces:
        current=pieces.pop()
        if not current.interiors: result.append(current);continue
        hole=Polygon(current.interiors[0]);x0,y0,x1,y1=hole.bounds
        l,b,r,t=current.bounds
        first=current.intersection(unary_union([box(l,b,x1,y0),box(l,y0,x0,t)]))
        second=current.difference(first)
        for part in (first,second):
            pieces.extend(list(part.geoms) if hasattr(part,'geoms') else [part])
    return result


def apply_palette(doc,cls):
    """Semantic colors after generic config; never recolor entire shared Cima layers."""
    if cls=='FV':
        # Native MLINE fill/elements are BYLAYER: the FV layer must be red,
        # independently of the gray PL sarrafo settings.
        layer(doc,'FORMASCIA-SARRAFOS',1)
        # Imported native dimension blocks can retain source layer handles.
        for entry in doc.layers:
            for attr,kind in [('material_handle','MATERIAL'),('plotstyle_handle','ACDBPLACEHOLDER')]:
                handle=entry.dxf.get(attr);target=doc.entitydb.get(handle) if handle else None
                if handle and (target is None or target.dxftype()!=kind):entry.dxf.discard(attr)
            entry.set_required_attributes()
    for e in list(doc.modelspace()):
        if cls=='PL' and e.dxftype()=='TEXT' and e.dxf.text.startswith(('CENARIOS','NIVEL DE')):
            doc.modelspace().delete_entity(e);continue
        k=e.dxf.layer.casefold()
        if cls=='PL':
            if k=='formascia-sarrafos':paint(e,7 if e.dxf.style_name=='SAR15' else 8)
            elif k=='formascia-vazios':
                e.set_pattern_fill('AR-CONC',scale=.1,angle=0,color=8)
            elif k=='nível':paint(e,8)
            elif k=='hachura' and e.dxftype()=='LWPOLYLINE':paint(e,8)
            elif k=='numeracao_paineis':paint(e,1 if e.dxftype()=='CIRCLE' else 7)
            elif k=='formascia-veios':paint(e,1)
            elif k=='formascia-parafusos':paint(e,8)
            elif k.startswith('sarr_') and e.dxf.get('linetype','').upper() in ('DASHED','HIDDEN'):paint(e,1)
            elif k=='sarrafo de pressão':paint(e,1)
            elif e.dxftype()=='TEXT' and e.dxf.text=='SP':paint(e,4)
        if cls=='LJ' and k in ('painéis','paineis'):paint(e,3)
        elif cls=='FV':
            if e.dxftype()=='INSERT' and e.dxf.name.lower().startswith('nf') and e.dxf.name[2:].isdigit():
                doc.modelspace().delete_entity(e);continue
            if k in ('painéis','paineis','sarr_contorno_10cm'):paint(e,3)
            elif k=='5' or e.dxftype()=='TEXT' and k=='nomenclatura':paint(e,7)
            elif e.dxftype()=='MLINE':paint(e,1)
            elif e.dxftype()=='CIRCLE' and k=='nomenclatura':paint(e,1)
        elif cls in ('LV', 'LV_PARA', 'LV_PASSA'):
            if k in ('painéis', 'paineis', 'vigas'): paint(e, 3)
            elif k in ('acabamento', 'sarrafos') or k.startswith('sarr_'): paint(e, 1)
            elif k in ('cotas', 'cota'): paint(e, 4)
            elif k in ('bnc_texto', 'nomenclatura'): paint(e, 7)
            elif 'numer' in k:
                paint(e, 1 if e.dxftype() == 'CIRCLE' else 7)
            elif 'concreto' in k:
                paint(e, 8)
                if e.dxftype() == 'HATCH':
                    e.set_pattern_fill('AR-CONC', scale=1.0, angle=0, color=8)
            elif k == 'meio_pont.': paint(e, 43)
            elif k == 'sarrafo de pressão': paint(e, 1)
