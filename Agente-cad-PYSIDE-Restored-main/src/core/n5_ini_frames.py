"""Initial iNi sheets from registered originals; publication is not design approval.

The registered PL/LV indices calibrate the sheet, not any structural item.
FV/LJ use an explicitly adapted iNi shell pending their own reference uploads.
"""
from pathlib import Path
import hashlib,json,io,math
import ezdxf
from ezdxf import bbox
from .n5_formascia_frames import transfer as native_transfer,explode_inserts,text,beam_resources
from .lv_formascia_design import normalize_resources as normalize_base


def normalize_resources(doc):
 # Register XDATA applications from a snapshot before the shared normalizer
 # scans the entity database; creating APPIDs during that scan mutates it.
 for entity in list(doc.entitydb.values()):
  if entity.is_alive and entity.xdata:
   for name in entity.xdata.data:
    if name not in doc.appids:doc.appids.new(name)
 normalize_base(doc)
 for hatch in doc.modelspace().query('HATCH'):
  hatch.dxf.associative=0
  for boundary in hatch.paths:
   boundary.source_boundary_objects.clear()
   # Derived contours copied from the native legend require code 47 in
   # AutoCAD's strict reader. These are explicit closed boundaries now.
   boundary.path_type_flags &= ~4
  hatch.dxf.discard('pixel_size')

TEMPLATES={
 'PL':('PL','364d9a67fb174e1a8dea555ffa5b54ae','1430cb88a5e2c38f552b8209f94c73d4961933e37fae15ca1c2b4b841565bf3c'),
 'LV':('LV_PARA','76107741b1bf442ebdc0d1374abf22e2','2fe2bd6354c6fb5580edc1a59fbf0590562ac2abff0ad3c9c73b51f58ce81d54'),
}
W=4204.99473524184
H=2970.
LEFT=125.
RIGHT=3280.
CW=(RIGHT-LEFT)/3
CH=(H-100)/3

def transfer(src,dst,dx=0.,dy=0.,scale=1.,*,native_mlines=True):
 # A registered legend can use the same layer name with a different color.
 # Namespace only conflicts; the legend must not recolor fabrication units.
 for layer in list(src.layers):
  name=layer.dxf.name
  if name in dst.layers and dst.layers.get(name).dxf.color!=layer.dxf.color and name not in ('0','Defpoints'):
   target=f'INI_N3_{layer.dxf.color}_{name}'
   if target not in src.layers:layer.rename(target)
 return native_transfer(src,dst,dx,dy,scale,native_mlines=True)

def clone(doc):
 stream=io.StringIO();doc.write(stream)
 return ezdxf.read(io.StringIO(stream.getvalue()))

def registered(cls):
 from scripts.drawing_mode_config import storage_path
 group,token,digest=TEMPLATES['LV' if cls=='LV' else 'PL']
 p=storage_path().parent/'drawing_legends'/'INI'/group/(token+'.dxf')
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
  raise ValueError(f'Moldura/índice iNi ausente ou substituído: {group}; recalibre a referência')
 return p

def template_doc(cls,flow=False):
 doc=ezdxf.readfile(registered(cls));ext=bbox.extents(doc.modelspace());ox,oy=ext.extmin.x,ext.extmin.y
 explode_inserts(doc);m=doc.modelspace()
 for e in list(m):
  if e.dxftype() in ('OLE2FRAME','ATTDEF','ATTRIB'):m.delete_entity(e);continue
  e.translate(-ox,-oy,0)
  layer=e.dxf.layer.casefold()
  if layer=='indice':m.delete_entity(e);continue
  if e.dxftype() in ('TEXT','MTEXT'):
   value=e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()
   # Actual project fields in the original are reference metadata, not this SA.
   if e.dxf.insert.x>RIGHT and e.dxf.insert.y<610:
    if any(t in value.upper() for t in ('DIÁLOGO','DIALOGO','MIRAGAIA','TORRE','SUBSOLO','PROJEÇÃO')) or layer=='folha_selo':
     m.delete_entity(e);continue
  if flow:
   b=bbox.extents([e],fast=True)
   if b.has_data and b.extmax.x<=RIGHT+2 and b.extmin.x>=LEFT-2 and b.extmin.y>=49 and b.extmax.y<=H-49:
    m.delete_entity(e)
 # Adapt the right-hand technical legend only where no class-specific iNi reference exists.
 if cls in ('FV','LJ'):
  for e in list(m):
   b=bbox.extents([e],fast=True)
   if b.has_data and b.extmin.x>RIGHT+5 and b.extmin.y>620 and b.extmax.y<H-60:
    m.delete_entity(e)
  text(m,{'FV':'FUNDOS DE VIGA','LJ':'LAJES'}[cls],(3700,H-170),24,7)
  text(m,'iNi — GEOMETRIA N3 APROVADA',(3700,H-230),12,7)
 beam_resources(doc)
 return doc,W,H

def stamp(doc,width,height,*,obra,cliente,pavimento,cls,number,total):
 m=doc.modelspace()
 if cls=='PL':
  labels=sorted([e for e in m.query('TEXT') if e.dxf.layer=='DIVISAO_FOLHA' and e.dxf.text.isdigit()],key=lambda e:(-round(e.dxf.insert.y,1),e.dxf.insert.x))
  for slot,label in enumerate(labels,1):label.dxf.text=str((number-1)*9+slot)
 # A designated new metadata strip replaces the removed project values.
 for label,y in [(obra,470),(cliente or '—',420),(pavimento+' / '+cls,370),(f'{number:02d}/{total:02d}',310)]:
  text(m,label,(3700,y),18,7)
 text(m,'N3 / N5 — iNi',(3700,650),20,7)

def cells():
 return [(LEFT+i*CW,50+j*CH,LEFT+(i+1)*CW,50+(j+1)*CH)
         for j in (2,1,0) for i in range(3)]

def source(path,cls):
 from .n5_assembler import _is_fv_helper_entity
 doc=ezdxf.readfile(path)
 for e in list(doc.modelspace()):
  if e.dxftype()=='INSERT' and e.dxf.name=='MULDURA' or cls=='FV' and _is_fv_helper_entity(e):doc.modelspace().delete_entity(e)
 return doc

def finish(dst,pages,index,cls,obra,cliente,pavimento,pages_dir):
 pages_dir=Path(pages_dir);pages_dir.mkdir(parents=True,exist_ok=True);records=[];cursor=0.
 for i,p in enumerate(pages,1):
  stamp(p['doc'],W,H,obra=obra,cliente=cliente,pavimento=pavimento,cls=cls,number=i,total=len(pages))
  rows=[row for row in index if row['page']==i]
  if cls=='FV':
   counts={}
   for row in rows:counts[row['label']]=counts.get(row['label'],0)+1
   rows=[dict(label=f'{label} ({count} seg.)') for label,count in counts.items()]
  # Two columns keep the complete page inventory above the title block.
  per_column=max(1,(len(rows)+1)//2) if cls=='FV' else 26
  for j,row in enumerate(rows):
   label=str(row.get('label',''))
   if 'module' in row:label=f"{row['module']:03d} — {label}"
   x=3450+(j//per_column)*360 if cls=='FV' else 3710
   text(p['doc'].modelspace(),label,(x,1150-(j%per_column)*18),12,7)
  # The page and clean docs are discarded after their transfer; a write/read
  # clone only to protect them from layer renames cost ~40% of N5 PL.
  clean=ezdxf.new('R2018');transfer(p['doc'],clean,native_mlines=True)
  normalize_resources(clean);beam_resources(clean);clean.header['$INSUNITS']=5
  for hatch in clean.modelspace().query('HATCH'):
   if hatch.has_pattern_fill:
    hatch.set_pattern_fill(hatch.dxf.pattern_name,scale=hatch.dxf.pattern_scale,angle=hatch.dxf.pattern_angle,color=hatch.dxf.color)
    hatch.dxf.discard('pixel_size')
  first=clean.audit()
  if first.errors:raise ValueError(f'Folha iNi {i}: DXF inválido')
  second=clean.audit()
  if second.errors or second.fixes:raise ValueError(f'Folha iNi {i}: reparos persistentes')
  path=pages_dir/f'folha_{i:03d}.dxf';clean.saveas(path)
  cursor=(i-1)%3*(W+300) if cls=='PL' else (i-1)*(W+300)
  origin_y=-((i-1)//3)*(H+300) if cls=='PL' else 0.
  transfer(clean,dst,dx=cursor,dy=origin_y,native_mlines=True)
  records.append(dict(page=i,kind=p['kind'],output=str(path),origin=[cursor,origin_y],width=W,height=H,entries=p['entries']))
  cursor+=W+300
 normalize_resources(dst);beam_resources(dst);dst.header['$INSUNITS']=5
 return dict(kind='ini_frames_v1',mode='INI',design='ini_approved_n3_v02',approval='n3_design_approved',pagination='nine_cells_three_columns' if cls=='PL' else 'native_units',pages=records,index=index,editable=True)

def assemble(dst,sources,cls,*,obra,cliente,pavimento,pages_dir,pillar_group=None,slab_plan=None,pending=None):
 pages=[];index=[]
 def page(flow=False,kind=None):
  doc,_,_=template_doc(cls,flow);p=dict(doc=doc,kind=kind or cls,entries=[]);pages.append(p);return p
 if cls=='PL':
  from .ini_pillar_pagination import assemble as paginate_pillars
  pillar_manifest=paginate_pillars(pages,index,sources,pillar_group)
 elif cls=='LJ':
  # Preserve the complete SA arrangement at an explicit, declared paper scale.
  from .ini_plan_windows import windows
  for doc,window in windows(slab_plan,RIGHT-LEFT-100,H-200):
   p=page(True);box=bbox.extents(doc.modelspace());scale=window['scale'];dx=175-box.extmin.x*scale;dy=H-100-box.extmax.y*scale
   transfer(doc,p['doc'],dx,dy,scale,native_mlines=True)
   text(p['doc'].modelspace(),'PLANTA COERENTE — ESC. '+window['paper_scale'],(3700,H-310),18,7)
   e=dict(label='LAJES / '+pavimento,page=len(pages),scale=scale,window=window)
   p['entries'].append(e);index.append(e)
 else:
  p=None;x=175.;top=H-100;rh=0.;right=RIGHT-50.;bottom=100.
  for item,paths in sources:
   units=[]
   try:
    # Validate every segment before placing any part of this item. Compare
    # against a fresh sheet, not the remaining height of the current row.
    for path in paths:
     doc=source(path,cls);box=bbox.extents(doc.modelspace());w,h=box.size.x,box.size.y
     if w>right-175 or h>H-200:raise ValueError(f'{item}: unidade excede folha iNi 1x')
     units.append((path,doc,box,w,h))
   except (ValueError,OSError) as exc:
    if pending is None:raise
    pending.append(dict(item_id=item,status='missing',source=';'.join(map(str,paths)),message=str(exc)))
    continue
   for path,doc,box,w,h in units:
    if x+w>right:x=175.;top-=rh+35;rh=0.
    if p is None or top-h<bottom:p=page(True);x=175.;top=H-100;rh=0.
    transfer(doc,p['doc'],x-box.extmin.x,top-box.extmax.y,native_mlines=True)
    e=dict(label=item,page=len(pages),scale=1.,source=str(path),bounds=[x,top-h,x+w,top]);p['entries'].append(e);index.append(e)
    x+=w+35;rh=max(rh,h)
 if not pages:
  if pending is not None:return dict(kind='ini_frames_v1',mode='INI',pages=[],index=[])
  raise ValueError('N5 iNi sem conteúdo')
 result=finish(dst,pages,index,cls,obra,cliente,pavimento,pages_dir)
 if cls=='PL':result.update(pillar_manifest)
 return result
