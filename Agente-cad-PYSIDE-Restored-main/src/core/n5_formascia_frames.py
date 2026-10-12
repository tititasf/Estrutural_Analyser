"""Formascia sheets from registered templates and the actual published N3.

Calibration is for the uploaded sheets, never for a structural item.
Native dimensions, hatches and multilines remain individually editable.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import ezdxf
from ezdxf import bbox
from ezdxf.math import Matrix44
from src.core.formascia_design import text

TEMPLATES = {
    'PL': ('drawing_frames','PL','INDICE E MOLDURA ABCD CIMA PILARES.dxf','b94ca3000269830dd4842a079c235beae8a8f461a75ea3f5ca2d28afd600904a'),
    'PL_FIRST': ('drawing_legends','PL','INDICE PRIMEIRA FOLHA PILARES ACBD CIMA.dxf','ae67dd3bcea9565e41c3ac09baaa0a8484da71ec8500afc6260bebf31466d516'),
    'GRADES': ('drawing_legends','PL','INDICE GRADES PILARES.dxf','e234a3d756a37cad94e751aaeac524f0120a714a0b12472c2dcdb770227dc01e'),
    'FV': ('drawing_legends','FV','moldura e indice fundos.dxf','15f29ca6a7470bbab4d17d1aabfdd66ebbeb30173546d58ee62267e6aa98f031'),
    'LJ': ('drawing_frames','LJ','LAJES FORMACIA.dxf','18ea08414c8621aaaa8128eb282969d31da5bdeabc20dc8ce6e83666909df926'),
    'LV_FIRST': ('drawing_legends', 'LV', 'INDICE PRIMEIRA FOLHA Laterais e viga.dxf', '4cfa2d01758836c1fcc2b762b8345f58fdb754e007c93a2e26651c32ed89c5b6'),
    'LV': ('drawing_frames', 'LV', 'MOLDURA ABCD LATERIAS DE VIGA OFRSMACIA.dxf', '09c93b6f650d5ed0dbf3ba97b5251a80249ee7966e96012d02f935b9cdebcffb'),
    'LV_GRADES': ('drawing_legends', 'LV', 'MOLDURA GRADES SOLTAS LATERIAS DE VIGA OFRSMACIA.dxf', '33c45fce88c598a1585bb1bfddd8c23fb3cf81723482a38c6955ed98271db108'),
}

def registered(kind,behavior=None):
    from scripts.drawing_mode_config import storage_path
    collection,cls,name,digest=TEMPLATES[kind]
    if kind.startswith('LV'):
        roots=[storage_path().parent/c/'MOLDE_1'/k for k in
               ((f'LV_{behavior.upper()}',cls) if behavior else (cls,'LV_PARA'))
               for c in (collection,'drawing_frames','drawing_legends')]
        for root in roots:
            if not (root/'index.json').is_file():continue
            index=json.loads((root/'index.json').read_text(encoding='utf8'))
            entries=index if isinstance(index,list) else index.get('items',[])
            for entry in entries:
                token=entry.get('id','')
                if len(token)!=32 or any(c not in '0123456789abcdef' for c in token):continue
                p=root/(token+'.dxf')
                if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest:return p
        raise ValueError(f'Moldura/índice Formascia {behavior} ausente ou substituído: {name}')
    root=storage_path().parent/collection/'MOLDE_1'/cls
    if not (root/'index.json').is_file():raise ValueError(f'Moldura/índice Formascia ausente: {name}')
    index=json.loads((root/'index.json').read_text(encoding='utf8'))
    records=index if isinstance(index,list) else index.get('items',index.get('documents',[]))
    for entry in records:
        token=entry.get('id','')
        if len(token)!=32 or any(c not in '0123456789abcdef' for c in token):continue
        p=root/(token+'.dxf')
        if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest:return p
    raise ValueError(f'Moldura/índice Formascia substituído: calibre o arquivo {name}')

def template_doc(kind,behavior=None):
    doc=ezdxf.readfile(registered(kind,behavior));m=doc.modelspace()
    explode_inserts(doc)
    margins=[bbox.extents([e]) for e in m.query('LWPOLYLINE') if e.closed and e.dxf.layer=='margem']
    if not margins:raise ValueError('Moldura Formascia sem margem')
    outer=max(margins,key=lambda b:b.size.x*b.size.y);ox,oy=outer.extmin.x,outer.extmin.y
    W,H=outer.size.x,outer.size.y
    # Uploaded slab example includes an old structural plan; keep only its sheet and legend.
    if kind=='LJ':
        keep={'margem','Folha','NOMENCLATURA','HACHURA','BNC_TEXTO','NUMERAÇÃO DAS CHAPAS','CONTORNO PAINEL'}
        for e in list(m):
            if e.dxf.layer not in keep:m.delete_entity(e)
    elif kind in ('LV', 'LV_FIRST', 'LV_GRADES', 'LV_PAINEIS'):
        remove = {
            'VIGAS', 'Meio_pont.', 'Sarrafos', 'cotas', 'BNC_HACHURA DE CONCRETO', 
            'BNC_HACHURA MADEIRAS', 'BNC_COMPENSADO', 'BNC_AGULHA', 'Sarrafo de pressão', 
            'presilha', 'BNC_MEIO PONTALETE', 'barrote', 'detalhes', 'SCO-___-LAJ',
            'CONTORNO PAINEL', 'HACHURA', 'Texto', 'material do compensado', 'perfil metalico', 'pontalete', '0'
        }
        for e in list(m):
            layer = e.dxf.layer
            if layer in remove:
                if kind == 'LV_FIRST' and layer in ('BNC_HACHURA MADEIRAS', 'BNC_COMPENSADO', 'detalhes', 'SCO-___-LAJ', 'CONTORNO PAINEL', 'HACHURA', 'Texto', 'material do compensado', 'presilha', 'perfil metalico', 'pontalete'):
                    pass # Keep details in index sheet
                else:
                    m.delete_entity(e)
            else:
                if kind != 'LV_FIRST':
                    try: b = bbox.extents([e], fast=True)
                    except: continue
                    if b.has_data and layer not in ('margem', 'Folha', 'Carimbo'):
                        if b.extmin.x < ox + W - 1000 or b.extmin.y > oy + 500:
                            m.delete_entity(e)
    for e in list(m):
        if e.dxftype()=='OLE2FRAME':m.delete_entity(e);continue
        b=bbox.extents([e],fast=True)
        if b.has_data and (b.extmin.x>outer.extmax.x+1 or b.extmax.y<oy-1):m.delete_entity(e);continue
        e.translate(-ox,-oy,0)
    # Original duplicated grid lines are redundant and visually thicken the sheet.
    seen=set()
    for e in list(m.query('LWPOLYLINE')):
        if e.dxf.layer!='Carimbo':continue
        signature=tuple((round(x,0),round(y,0)) for x,y in e.get_points('xy'))
        if signature in seen:m.delete_entity(e)
        else:seen.add(signature)
    audit=doc.audit()
    if audit.errors:raise ValueError('Template Formascia com erros de integridade')
    return doc,W,H

def stamp(doc,W,H,*,obra,cliente,pavimento,cls,number,total):
    """Populate uploaded stamp fields; never carry the example's project data."""
    m=doc.modelspace()
    for e in list(m.query('ATTDEF ATTRIB')):
        tag=e.dxf.get('tag','').strip()
        if tag.casefold() in {'revisão','data','descrição','projetista','legenda:'}:
            m.add_text(tag,dxfattribs={'layer':e.dxf.layer,'color':7,'height':e.dxf.height,'insert':e.dxf.insert})
        m.delete_entity(e)
    labels={}
    for e in m.query('TEXT'):
        name=e.dxf.text.strip().casefold()
        if name in {'cliente','obra','setor/pavimento','elemento','folha'}:
            labels[name]=e
    if cls == 'PL' and set(labels) != {'cliente','obra','setor/pavimento','elemento','folha'}:
        # Continuation template lacks some labels; the registered first sheet
        # supplies the same stamp's canonical field positions.
        first,fw,fh=template_doc('PL_FIRST')
        if abs(fw-W)>1 or abs(fh-H)>1:
            raise ValueError('Carimbos Formascia incompatíveis')
        for e in first.modelspace().query('TEXT'):
            name=e.dxf.text.strip().casefold()
            if name in {'cliente','obra','setor/pavimento','elemento','folha'} and name not in labels:
                copy=e.copy();m.add_entity(copy);labels[name]=copy
    if not labels:raise ValueError('Carimbo Formascia sem campos identificáveis')
    left=min(e.dxf.insert.x for e in labels.values())
    top=max(e.dxf.insert.y for e in labels.values())
    unit=labels['obra'].dxf.height
    for e in list(m.query('TEXT MTEXT')):
        q=e.dxf.insert
        if e in labels.values():continue
        content=e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()
        if 'ARQUIVO PROJETO EXECUTIVO' in content.upper():
            if e.dxftype()=='TEXT':e.dxf.text='GERAÇÃO N3 / N5 — FORMASCIA'
            else:e.text='GERAÇÃO N3 / N5 — FORMASCIA'
            continue
        if q.x>=left-10 and q.y<top+unit*2 or e.dxf.layer=='margem' and e.dxftype()=='MTEXT':
            m.delete_entity(e)
        elif 'PÇS' in content.upper():
            # Example quantities are not a bill of materials for this SA.
            m.delete_entity(e)
        elif 'RELACIONADOS COM OS GASTALHOS' in content.upper():
            e.dxf.text='GASTALHOS: CONFORME DESENHOS DESTE PAVIMENTO'
    values={'cliente':cliente or '—','obra':obra,'setor/pavimento':pavimento,
            'elemento':{'PL':'PILARES','LJ':'LAJES','FV':'FUNDOS DE VIGA','LV':'LATERAIS DE VIGA'}[cls],
            'folha':f'{number:02d}/{total:02d}'}
    for name,e in labels.items():
        q=e.dxf.insert
        m.add_text(values[name],dxfattribs={'layer':e.dxf.layer,'color':7,
            'style':e.dxf.style,'height':unit,'insert':(q.x+unit*2.5,q.y-unit*1.8)})

def cells(doc,kind,W,H):
    if kind in ('PL','PL_FIRST'):
        boxes=[]
        for e in doc.modelspace().query('LWPOLYLINE'):
            b=bbox.extents([e])
            if e.dxf.layer=='Carimbo' and e.closed and 700<b.size.x<2000 and 600<b.size.y<1200:
                v=(b.extmin.x,b.extmin.y,b.extmax.x,b.extmax.y)
                if not any(max(abs(a-c) for a,c in zip(v,old))<1 for old in boxes):boxes.append(v)
        # A closed stamp outline is not a drawing cell.
        stamp_points = [e.dxf.insert for e in doc.modelspace().query('TEXT')
                        if e.dxf.text.strip().casefold() in {'obra', 'folha'}]
        boxes = [b for b in boxes if not any(
            b[0] <= q.x <= b[2] and b[1] <= q.y <= b[3] for q in stamp_points)]
        # Bottom left shares its boundary with the outer frame. Derive its
        # upper edge from the middle row, not from a neighboring bottom cell.
        if kind=='PL':
            xs=min(b[0] for b in boxes);bottom=50.
            middle=min(b[1] for b in boxes if b[1] > H*.2)
            edge=min(b[2] for b in boxes)
            if not any(abs(b[0]-xs)<1 and b[1]<H*.2 for b in boxes):
                boxes.append((xs,bottom,edge,middle))
        return sorted(boxes,key=lambda b:(-round(b[3]/50),b[0]))
    left=125.;bottom=50.;right=W-50.;top=H-50.
    if kind=='GRADES':
        # Right bottom contains the original legend and stamp.
        return [(left+i*(right-left)/3,bottom+j*(top-bottom)/3,
                 left+(i+1)*(right-left)/3,bottom+(j+1)*(top-bottom)/3)
                for j in (2,1,0) for i in range(3) if not (j==0 and i==2)]
    if kind=='FV':
        # All beam rows stay left of the mounting legend, at its full height.
        right=W-1020.
        return [(left+i*(right-left)/2,bottom+j*(top-bottom)/7,
                 left+(i+1)*(right-left)/2,bottom+(j+1)*(top-bottom)/7)
                for j in range(6,-1,-1) for i in range(2)]
    if kind in ('LV', 'LV_GRADES', 'LV_PAINEIS'):
        return [(left, 50., right, top)]
    return [(left,1200.,right,top)]

def transfer(src,dst,dx=0.,dy=0.,scale=1.,*,native_mlines=False):
    from src.core.n5_assembler import _import_doc_entities
    if native_mlines:
        # New MLINESTYLE records start with two default elements; copying
        # without clearing them creates a style incompatible with its vertices.
        for entity in src.modelspace().query('MLINE'):
            name=entity.dxf.style_name
            if name not in dst.mline_styles:
                original=src.mline_styles.get(name);style=dst.mline_styles.new(name)
                for attr in ('flags','fill_color','start_angle','end_angle'):
                    setattr(style.dxf,attr,original.dxf.get(attr))
                style.elements.elements.clear()
                for element in original.elements:
                    style.elements.append(element.offset,element.color,element.linetype)
    transform=Matrix44.chain(Matrix44.scale(scale,scale,scale),Matrix44.translate(dx,dy,0))
    for e in src.modelspace():
        e.transform(transform)
        if e.dxftype()=='DIMENSION' and scale!=1:
            d=e.override();d.update({'dimlfac':d.get('dimlfac',1)/scale});d.render()
    count=_import_doc_entities(src,dst)
    return count

def explode_inserts(doc):
    m=doc.modelspace()
    for _ in range(12):
        inserts=list(m.query('INSERT'))
        if not inserts:return
        for e in inserts:e.explode()
    raise ValueError('Hierarquia de blocos excedeu o limite da folha')

def clean_source(path,cls):
    from src.core.n5_assembler import _is_fv_helper_entity
    doc=ezdxf.readfile(path)
    for e in list(doc.modelspace()):
        if (cls=='FV' and _is_fv_helper_entity(e)) or e.dxftype()=='INSERT' and e.dxf.name=='MULDURA':
            doc.modelspace().delete_entity(e)
        elif cls=='LV_PAINEIS' and e.dxf.layer in ('Sarrafos', 'Meio_pont.'):
            doc.modelspace().delete_entity(e)
        elif cls=='LV_GRADES' and 'CORTE' not in str(path).upper() and e.dxf.layer not in ('Sarrafos', 'Meio_pont.'):
            doc.modelspace().delete_entity(e)
    return doc

def bundle(paths,cls):
    """Cima above elevation; grades and beam segments keep their own N3 views."""
    d=ezdxf.new('R2018');cursor_x=0
    for path in paths:
        src=clean_source(path,cls);b=bbox.extents(src.modelspace())
        if not b.has_data:raise ValueError(f'N3 vazio: {path}')
        scale = 2.0 if 'CORTE' in str(path).upper() and cls in ('LV', 'LV_GRADES', 'LV_PAINEIS') else 1.0
        transfer(src,d,cursor_x-b.extmin.x*scale,-b.extmax.y*scale,scale=scale,native_mlines=cls=='FV')
        cursor_x+=b.size.x*scale+150
    return d


def pillar_transfer(src,dst,dx=0.,dy=0.):
    """Keep native two-element MLINE styles during PL sheet imports."""
    for entity in src.modelspace().query('MLINE'):
        name=entity.dxf.style_name
        if name not in dst.mline_styles:
            original=src.mline_styles.get(name);style=dst.mline_styles.new(name)
            for attr in ('flags','fill_color','start_angle','end_angle'):
                setattr(style.dxf,attr,original.dxf.get(attr))
            style.elements.elements.clear()
            for element in original.elements:
                style.elements.append(element.offset,element.color,element.linetype)
    return transfer(src,dst,dx,dy,1.)


def pillar_resources(doc):
    """Resolve copied CAD metadata in Formascia PL only."""
    seen=set()
    for line in list(doc.modelspace().query('LWPOLYLINE[layer=="Nível"]')):
        signature=tuple((round(x,6),round(y,6)) for x,y in line.get_points('xy'))
        if signature in seen:doc.modelspace().delete_entity(line)
        else:seen.add(signature)
    for entity in list(doc.entitydb.values()):
        if entity.is_alive and entity.xdata:
            for appid in entity.xdata.data:
                if appid not in doc.appids:doc.appids.new(appid)
    if 'DASHED' in doc.linetypes:doc.linetypes.get('DASHED').setup_pattern([5.,3.,-2.])
    for layer in doc.layers:
        for attr,kind in [('material_handle','MATERIAL'),('plotstyle_handle','ACDBPLACEHOLDER')]:
            handle=layer.dxf.get(attr);target=doc.entitydb.get(handle) if handle else None
            if handle and (target is None or target.dxftype()!=kind):layer.dxf.discard(attr)
        layer.set_required_attributes()
    for hatch in doc.modelspace().query('HATCH'):
        if hatch.dxf.layer=='FORMASCIA-VAZIOS' and hatch.has_pattern_fill:
            # ezdxf's transform scales already-scaled pattern lines again,
            # even for a translation. Rebuild PL void definitions once from
            # their declared scale after page and consolidated-sheet imports.
            hatch.set_pattern_fill('AR-CONC',scale=hatch.dxf.pattern_scale,
                                   angle=hatch.dxf.pattern_angle,color=8)
            hatch.dxf.discard('pixel_size')
        hatch.dxf.associative=0
        for boundary in hatch.paths:boundary.source_boundary_objects.clear()


def slab_resources(doc):
    """Resolve layer handles copied from the uploaded LJ sheet in AutoCAD."""
    for layer in doc.layers:
        for attr,kind in [('material_handle','MATERIAL'),('plotstyle_handle','ACDBPLACEHOLDER')]:
            handle=layer.dxf.get(attr);target=doc.entitydb.get(handle) if handle else None
            if handle and (target is None or target.dxftype()!=kind):layer.dxf.discard(attr)
        layer.set_required_attributes()


def beam_resources(doc):
    """Keep FV imported MLINE metadata valid for native CAD readers."""
    slab_resources(doc)
    for entity in list(doc.entitydb.values()):
        if entity.is_alive and entity.xdata:
            for appid in entity.xdata.data:
                if appid not in doc.appids:doc.appids.new(appid)
    for entity in doc.modelspace().query('MLINE'):
        entity.dxf.extrusion=entity.dxf.extrusion.normalize()


def pillar_cell(paths,page,cell,label,*,grades=False,level_span=None,baseline_offset=None):
    """Approved 2x/1x/1x geometry, top/down and bottom/up cell anchors."""
    l,b,r,t=cell
    elevation=clean_source(paths[1],'PL')
    levels=[e for e in elevation.modelspace() if e.dxf.layer=='Nível' and e.dxftype()=='LWPOLYLINE']
    if not levels:raise ValueError(f'N3 {label}: níveis da elevação ausentes')
    level_ys=sorted({e.get_points()[0][1] for e in levels})
    ext=bbox.extents([e for e in elevation.modelspace() if e.dxf.layer!='Nível'])
    baseline=b+(baseline_offset if baseline_offset is not None else 55+min(level_ys)-ext.extmin.y)
    views=[(clean_source(paths[0],'PL'),'GRADES')] if grades else [(clean_source(paths[0],'PL'),'CIMA'),(elevation,'ABCD')]
    records=[]
    for source,zone in views:
        if zone=='GRADES' and not list(source.modelspace().query('LWPOLYLINE[layer=="Nível"]')):
            # Existing N3 grades predate native level markers. Derive their
            # datum and symbols from the same item's actual elevation.
            for original in elevation.modelspace():
                if original.dxf.layer not in ('S1','Texto Nível','Nível'):continue
                name=original.dxf.layer
                if name not in source.layers:
                    source.layers.new(name,dxfattribs={'color':elevation.layers.get(name).dxf.color})
                clone=original.copy();clone.translate(0,-min(level_ys),0)
                if clone.xdata:
                    for appid in clone.xdata.data:
                        if appid not in source.appids:source.appids.new(appid)
                source.modelspace().add_entity(clone)
        ext=bbox.extents([e for e in source.modelspace() if e.dxf.layer!='Nível'])
        dx=(l+r)/2-ext.center.x
        if zone=='CIMA':dy=t-85-ext.extmax.y
        else:
            native_levels=[e for e in source.modelspace() if e.dxf.layer=='Nível' and e.dxftype()=='LWPOLYLINE']
            if not native_levels:raise ValueError(f'N3 {label}: níveis de {zone} ausentes; regenere o item')
            dy=baseline-min(e.get_points()[0][1] for e in native_levels)
            for line in native_levels:
                y=line.get_points()[0][1]
                left,right=level_span or (l,r)
                line.set_points([(left-dx,y),(right-dx,y)])
        bounds=[ext.extmin.x+dx,ext.extmin.y+dy,ext.extmax.x+dx,ext.extmax.y+dy]
        if bounds[0]<l+45 or bounds[2]>r-45 or bounds[1]<b+35 or bounds[3]>t-55:
            raise ValueError(f'N3 {label}: {zone} excede a célula nas escalas aprovadas 2x/1x/1x')
        records.append({'view':zone,'bounds':bounds,'levels':sorted({e.get_points()[0][1]+dy for e in source.modelspace() if e.dxf.layer=='Nível' and e.dxftype()=='LWPOLYLINE'})})
        pillar_transfer(source,page,dx,dy)
    if len(records)==2 and records[0]['bounds'][1]<records[1]['bounds'][3]+45:
        raise ValueError(f'N3 {label}: CIMA e ABCD sobrepostos nas escalas aprovadas')
    return {'label':label,'scale':1.,'native_scales':{'CIMA':2.,'ABCD':1.,'GRADES':1.},'cell':list(cell),'views':records}


def grade_row_span(doc,cell,W,H):
    """Use physical frame walls; bottom rows stop at the actual stamp wall."""
    left=cell[0];right=W-50.
    outlines=[bbox.extents([e]) for e in doc.modelspace().query('LWPOLYLINE')
              if e.closed and e.dxf.layer=='Carimbo']
    outer=max(outlines,key=lambda ext:ext.size.x*ext.size.y)
    left,right=outer.extmin.x,outer.extmax.x
    for ext in outlines:
        if ext.extmin.x>W*.6 and ext.extmin.y<cell[3] and ext.extmax.y>cell[1]:
            right=min(right,ext.extmin.x)
    return left,right

def fit(source,page,cell,label,*,pillar_views=False,native_mlines=False):
    l,b,r,t=cell;pad=45.;heading=55.
    text(page.modelspace(),label,((l+r)/2,t-28),22,7)
    ext=bbox.extents(source.modelspace());cw=r-l-2*pad;ch=t-b-2*pad-heading
    limit=min(cw/max(ext.size.x,1),ch/max(ext.size.y,1))
    allowed=[.1,.2,.25,.5,1.,2.,2.5,5.]
    scale=max((v for v in allowed if v<=limit),default=0)
    if not scale:raise ValueError(f'Desenho {label} não cabe na moldura Formascia')
    dx=(l+r)/2-ext.center.x*scale;dy=(b+t-heading)/2-ext.center.y*scale
    transfer(source,page,dx,dy,scale,native_mlines=native_mlines)
    scale_text=(f'CIMA 1:{5/scale:g} · FACES 1:{10/scale:g}' if pillar_views
                else f'ESCALA 1:{10/scale:g}')
    text(page.modelspace(),scale_text,((l+r)/2,b+18),12,7)
    return {'label':label,'scale':scale,'cell':list(cell),
            'bounds':[ext.extmin.x*scale+dx,ext.extmin.y*scale+dy,ext.extmax.x*scale+dx,ext.extmax.y*scale+dy]}

def beam_area(doc):
    """Derive drawing bounds and the mounting-legend obstacle from the frame."""
    outlines=[bbox.extents([e]) for e in doc.modelspace().query('LWPOLYLINE')
              if e.closed and e.dxf.layer=='Folha']
    if not outlines:raise ValueError('Limites internos da moldura FV ausentes')
    frame=max(outlines,key=lambda w:w.size.x*w.size.y);pad=30.
    area=(frame.extmin.x+pad,frame.extmin.y+pad,frame.extmax.x-pad,frame.extmax.y-pad)
    walls=[bbox.extents([e]) for e in doc.modelspace().query('LINE') if e.dxf.layer=='CONTORNO PAINEL']
    walls=[w for w in walls if frame.extmin.x+frame.size.x*.6<w.extmin.x<frame.extmax.x-100
           and w.size.x<1 and w.size.y>frame.size.y*.3]
    if not walls:raise ValueError('Parede da legenda FV nao identificada')
    return area,(min(w.extmin.x for w in walls),max(w.extmax.y for w in walls))


def beam_position(width,height,area,legend,cursor,*,gap=35.):
    """Left-to-right shelves; None requests a fresh sheet, never overlaps legend."""
    l,b,r,t=area;legend_left,legend_top=legend;x,top,row_height=cursor
    if width>r-l or height>t-b:raise ValueError('Envelope FV excede a folha na escala calculada')
    available_right=legend_left-gap if top-height<legend_top+gap else r
    if x+width>available_right:
        x=l;top-=row_height+gap;row_height=0.
        available_right=legend_left-gap if top-height<legend_top+gap else r
    if top-height<b or x+width>available_right:return None
    bounds=[x,top-height,x+width,top]
    return bounds,(x+width+gap,top,max(row_height,height))


def assemble(dst,sources,cls,*,obra,cliente,pavimento,pages_dir,pillar_group=None,slab_plan=None):
    """sources: (item id, five PL files or FV segment files)."""
    pages_dir=Path(pages_dir);pages_dir.mkdir(parents=True,exist_ok=True)
    groups=[]
    if cls=='PL':
        for item,paths in sources:
            families=[('Para',3,4),('Passa',1,2)] if pillar_group is None else [('Para',3,4)] if pillar_group=='PARA' else [('Passa',1,2)]
            for family,elev,grade in families:
                groups.append(('PL_FIRST' if not groups else 'PL',f'{item} — {family}',[paths[0],paths[elev]]))
        for item,paths in sources:
            for family,elev,grade in ([('Para',3,4),('Passa',1,2)] if pillar_group is None else [('Para',3,4)] if pillar_group=='PARA' else [('Passa',1,2)]):
                groups.append(('GRADES',f'{item} — Grades {family}',[paths[grade],paths[elev]]))
    elif cls=='FV':
        for item,paths in sources:
            for i,path in enumerate(paths,1):
                label=item if len(paths)==1 else f'{item} — Segmento {i}'
                groups.append(('FV',label,[path]))
    elif cls=='LV':
        from src.core.lv_formascia_packer import assemble_lv_formascia
        return assemble_lv_formascia(dst, sources, cls, obra=obra, cliente=cliente, pavimento=pavimento, pages_dir=pages_dir)
    else:groups=[('LJ',f'LAJES — {pavimento}',slab_plan)]
    baseline_offset=55.
    if cls=='PL':
        for kind,label,paths in groups:
            elevation=clean_source(paths[1],'PL')
            levels=[e.get_points()[0][1] for e in elevation.modelspace() if e.dxf.layer=='Nível' and e.dxftype()=='LWPOLYLINE']
            ext=bbox.extents([e for e in elevation.modelspace() if e.dxf.layer!='Nível'])
            if levels:baseline_offset=max(baseline_offset,55+min(levels)-ext.extmin.y)
    pages=[];index=[]
    # A dedicated index preserves every row and gives explicit sheet mappings.
    index_doc,W,H=template_doc('GRADES' if cls=='PL' else 'LV_FIRST' if cls=='LV' else cls)
    m=index_doc.modelspace();available_width=W-1200.;rows=math.ceil(len(groups)/3) or 1
    if rows>90:raise ValueError('Índice Formascia excede a folha; subdivida o pavimento')
    text(m,f'{obra} · {pavimento} · {cls}',(available_width/2+125,H-150),35,7)
    text(m,'ÍNDICE DAS FOLHAS — FORMASCIA',(available_width/2+125,H-220),26,7)
    pages.append({'doc':index_doc,'kind':'INDEX','entries':[],'width':W,'height':H})
    if cls=='FV':
        prepared=[]
        for kind,label,paths in groups:
            source=bundle(paths,cls);ext=bbox.extents(source.modelspace())
            if not ext.has_data:raise ValueError(f'N3 vazio: {label}')
            prepared.append((label,source,ext))
        calibration,_,_=template_doc('FV');area,legend=beam_area(calibration)
        limit=min([2.]+[min((area[2]-area[0])/max(ext.size.x,1),
                            (area[3]-area[1])/max(ext.size.y,1)) for _,_,ext in prepared])
        scale=max((v for v in [.1,.2,.25,.5,1.,2.] if v<=limit),default=0)
        if not scale:raise ValueError('Fundos nao cabem na moldura Formascia')
        current=None
        for label,source,ext in prepared:
            if current is None:
                doc,W,H=template_doc('FV');area,legend=beam_area(doc);cursor=(area[0],area[3],0.)
                current={'doc':doc,'kind':'FV','family':'FV','entries':[],'width':W,'height':H}
                pages.append(current)
            placed=beam_position(ext.size.x*scale,ext.size.y*scale,area,legend,cursor)
            if placed is None:
                doc,W,H=template_doc('FV');area,legend=beam_area(doc);cursor=(area[0],area[3],0.)
                current={'doc':doc,'kind':'FV','family':'FV','entries':[],'width':W,'height':H}
                pages.append(current)
                placed=beam_position(ext.size.x*scale,ext.size.y*scale,area,legend,cursor)
                if placed is None:raise ValueError(f'{label}: nao cabe na area livre da moldura')
            bounds,cursor=placed;x,_,_,top=bounds
            transfer(source,current['doc'],x-ext.extmin.x*scale,top-ext.extmax.y*scale,scale,native_mlines=True)
            entry={'label':label,'scale':scale,'bounds':bounds,'page':len(pages)}
            current['entries'].append(entry);index.append(entry)
    else:
        current=None;slot=0
        for kind,label,paths in groups:
            family='GRADES' if kind=='GRADES' else 'LV' if kind in ('LV_GRADES', 'LV_PAINEIS') else cls
            if current is None or current['family']!=family or slot>=len(current['cells']):
                actual='PL_FIRST' if cls=='PL' and len(pages)==1 else 'PL' if cls=='PL' and kind!='GRADES' else 'LV' if kind=='LV_PAINEIS' else kind
                doc,W,H=template_doc(actual)
                current={'doc':doc,'kind':actual,'family':family,'entries':[],'width':W,'height':H,'cells':cells(doc,actual,W,H)}
                pages.append(current);slot=0
            if cls=='PL':
                entry=pillar_cell(paths,current['doc'],current['cells'][slot],label,grades=family=='GRADES',
                    level_span=grade_row_span(current['doc'],current['cells'][slot],current['width'],current['height']) if family=='GRADES' else None,
                    baseline_offset=baseline_offset)
            else:
                source=paths if cls=='LJ' else bundle(paths,kind)
                entry=fit(source,current['doc'],current['cells'][slot],label,native_mlines=cls=='FV')
            slot+=1
            entry['page']=len(pages);current['entries'].append(entry);index.append(entry)
    # Index layout is calculated from the complete output inventory.
    for i,entry in enumerate(index):
        col=i//rows;row=i%rows
        x=150+col*available_width/3;y=H-320-row*27
        index_doc.modelspace().add_text(f"{entry['label']}  —  FOLHA {entry['page']:02d}",
            dxfattribs={'layer':'NOMENCLATURA','color':7,'height':16,'insert':(x,y)})
    records=[]
    for number,page in enumerate(pages,1):
        doc=page['doc'];m=doc.modelspace();W,H=page['width'],page['height']
        stamp(doc,W,H,obra=obra,cliente=cliente,pavimento=pavimento,cls=cls,number=number,total=len(pages))
        explode_inserts(doc)
        if cls in {'LJ','FV'}:
            # Export only the sheet's native entities and used resources. The
            # uploaded template retains obsolete invalid anonymous blocks.
            clean=ezdxf.new('R2018');transfer(doc,clean,native_mlines=cls=='FV');doc=clean
        if cls=='PL':pillar_resources(doc)
        elif cls=='LJ':slab_resources(doc)
        elif cls=='FV':beam_resources(doc)
        if 'HIDDEN' not in doc.linetypes:
            doc.linetypes.new('HIDDEN', dxfattribs={'description': 'Hidden __ __', 'pattern': [0.25, 0.125, -0.125]})
        audit=doc.audit()
        # Removed example texts may own obsolete AutoCAD FIELD objects. Audit
        # removes these orphan references; geometry repairs are never accepted.
        if any(x.code!=202 or 'FIELD' not in x.message for x in audit.fixes):
            raise ValueError(f'Folha Formascia {number}: reparo de geometria inesperado: {[(x.code,x.message) for x in audit.fixes]}')
        audit=doc.audit()
        if audit.errors or audit.fixes:raise ValueError(f'Folha Formascia {number}: DXF inválido: {[(x.code,x.message) for x in audit.errors+audit.fixes]}')
        path=pages_dir/f'folha_{number:03d}.dxf';doc.saveas(path)
        origin=[((number-1)%3)*(W+250),-((number-1)//3)*(H+250)]
        records.append({'page':number,'kind':page['kind'],'output':str(path),'origin':origin,'width':W,'height':H,'entries':page['entries'],'template_sha256':TEMPLATES['GRADES' if page['kind']=='INDEX' and cls=='PL' else cls if page['kind']=='INDEX' else page['kind']][3]})
        # The consolidated model keeps every native CAD entity, sheet by sheet.
        if cls=='PL':pillar_transfer(ezdxf.readfile(path),dst,*origin)
        else:transfer(ezdxf.readfile(path),dst,*origin,native_mlines=cls=='FV')
    if cls=='PL':pillar_resources(dst)
    elif cls=='LJ':slab_resources(dst)
    elif cls=='FV':beam_resources(dst)
    return {'kind':'formascia_frames_v1','mode':'MOLDE_1','pages':records,'editable':True,'index':index}
