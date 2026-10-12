"""Initial iNi native-unit layout; geometry is never regenerated in N5."""
import json,io,math,hashlib
from pathlib import Path
import ezdxf
from ezdxf import bbox
from .n5_formascia_frames import text
from .n5_ini_frames import template_doc,stamp,transfer,beam_resources,normalize_resources
from .n5_lateral_frames import cut_design_key
from .lv_formascia_grades import grade_key,prepare_grades
from .lv_formascia_pagination import paginate_ab
from .lv_ini_pagination import paginate_grade
MARGIN=50.
def clone(doc):
 stream=io.StringIO();doc.write(stream);stream.seek(0);return ezdxf.read(stream)
def published_manifests(obra_dir, pavimento, assembly, behavior, *, pending=None):
    """The newest LV contract inventory is authoritative, including failed units."""
    from .n5_assembler import _production_n3_dirs, natural_key
    behavior = behavior.upper()
    for folder in _production_n3_dirs(Path(obra_dir), pavimento, 'INI'):
        inventory = folder.parent / 'contracts_lv' / f'LV-{behavior}'
        contracts = inventory / assembly
        # Pending SA contracts are written before fabrication. They must not
        # disappear merely because preparing this variant failed.
        paths = sorted(inventory.glob('*_A.json'), key=lambda p: natural_key(p.stem))
        if not paths:
            paths = sorted(contracts.glob('*_A.json'), key=lambda p: natural_key(p.stem))
        if not paths:
            if pending is not None:
                from portal.app.ficha_reader import ler_estado_pavimento, listar_itens_n1
                state = ler_estado_pavimento(obra_dir, pavimento)
                if not state:
                    raise ValueError('Estado SA atual ausente')
                expected = {item['beam_name'] for side in 'ab' for item in listar_itens_n1(state, f'lateral_{side}_{behavior.lower()}')}
                pending.extend(dict(item_id=beam, source='', status='missing', message='inventário N3 atual ausente') for beam in sorted(expected, key=natural_key))
                return [], []
            continue
        from portal.app.ficha_reader import ler_estado_pavimento, listar_itens_n1
        state = ler_estado_pavimento(obra_dir, pavimento)
        if state:
            expected = {item['beam_name'] for side in 'ab' for item in
                        listar_itens_n1(state, f'lateral_{side}_{behavior.lower()}')}
            actual = {p.stem.removesuffix('_A') for p in paths}
            if actual - expected or (pending is None and expected != actual):
                raise ValueError(f'N3 atual incompleto: inventário {behavior}/{assembly}; '
                                 f'ausentes={sorted(expected-actual, key=natural_key)}; '
                                 f'fora do SA={sorted(actual-expected, key=natural_key)}')
        if pending is not None and state:
            pending.extend(dict(item_id=beam, source='', status='missing', message='contrato N3 atual ausente')
                           for beam in sorted(expected-actual, key=natural_key))
        manifests, beams = [], []
        reference_context = {}
        for contract in paths:
            beam = contract.stem.removesuffix('_A')
            beam_manifests = []
            try:
                if not (contracts / f'{beam}_A.json').is_file():
                    raise ValueError(f'N3 atual incompleto: contrato A {beam}/{behavior}/{assembly}')
                if not (contracts / f'{beam}_B.json').is_file():
                    raise ValueError(f'Contrato B ausente: {beam}/{behavior}')
                for view in ('VIEW_A', 'VIEW_B'):
                    # The portal uses this fingerprinted artifact even when
                    # there is no manual override. A production-run preview
                    # can predate the approved renderer or current configuration.
                    from portal.app.lv_n3_panels import artifact_identity
                    try:
                        _, preview, _ = artifact_identity(obra_dir, pavimento, behavior.lower(), beam,
                                                          view[-1], mode='INI', assembly=assembly)
                    except (ValueError, LookupError, FileNotFoundError) as exc:
                        raise ValueError(f'N3 atual incompleto: {beam}/{behavior}/{view}/{assembly}: {exc}') from exc
                    manifest = preview.with_suffix('.units') / 'manifest.json'
                    if not preview.is_file() or not manifest.is_file():
                        raise ValueError(f'N3 atual incompleto: {beam}/{behavior}/{view}/{assembly}')
                    beam_manifests.append(manifest)
                from portal.app.lv_ficha import montar_ficha_lv
                from portal.app.lv_n3_cuts import artifact_identity as cut_identity
                if not state:
                    raise ValueError('Estado SA atual ausente para inventário de cortes N5')
                cuts = montar_ficha_lv(obra_dir, pavimento, beam, behavior.lower(), state,
                                      include_svgs=False, reference_context=reference_context)['cut_views']
                if not cuts:
                    raise ValueError(f'N3 atual incompleto: {beam}/{behavior}/CORTE sem seções SA')
                for cut in cuts:
                    try:
                        _, preview, _ = cut_identity(obra_dir, pavimento, behavior.lower(), cut,
                                                    mode='INI', assembly=assembly)
                    except ValueError as exc:
                        raise ValueError(f'N3 atual incompleto: {beam}/{behavior}/CORTE/{cut["id"]}: {exc}') from exc
                    manifest = preview.with_suffix('.units') / 'manifest.json'
                    if not preview.is_file() or not manifest.is_file():
                        raise ValueError(f'N3 atual incompleto: {beam}/{behavior}/CORTE/{cut["id"]}/{assembly}')
                    beam_manifests.append(manifest)
            except (ValueError, LookupError, FileNotFoundError) as exc:
                if pending is None:
                    raise
                pending.append(dict(item_id=beam, source='', status='missing', message=str(exc)))
                continue
            beams.append(beam)
            manifests.extend(beam_manifests)
        return beams, manifests
    raise ValueError(f'Inventário N3 iNi ausente: {behavior}/{assembly}')


def read_units(manifests, assembly, behavior):
    if assembly not in ('gradeadas', 'sarrafeadas') or behavior.upper() not in ('PARA', 'PASSA'):
        raise ValueError('Identidade N5 lateral inválida')
    units, seen = [], set()
    for manifest in manifests:
        manifest = Path(manifest)
        data = json.loads(manifest.read_text(encoding='utf8'))
        if (data.get('mode'), data.get('assembly_variant'), data.get('behavior','').upper()) != (
                'INI', assembly, behavior.upper()):
            raise ValueError('Inventário N3 mistura modos ou montagens')
        for unit in data['units']:
            filename = unit['file']
            if Path(filename).name != filename or Path(filename).suffix != '.dxf':
                raise ValueError('Caminho de unidade N3 inválido')
            path = manifest.parent / filename
            if hashlib.sha256(path.read_bytes()).hexdigest() != unit['sha256']:
                raise ValueError(f'Unidade N3 alterada: {path.name}')
            # A structural segment can have several consecutive mounting
            # profiles. Its segment number is not a fabrication-unit identity.
            # Preserve each occurrence within the source inventory, while
            # rejecting repeated imports of the same native unit file.
            key = (manifest.resolve(), filename)
            if key in seen:
                raise ValueError('Unidade N3 duplicada no inventário')
            seen.add(key)
            units.append((unit, path))
    if not units:
        raise ValueError('N5 lateral sem unidades N3')
    return units


def sheet(kind,behavior=None):
 doc,w,h=template_doc('LV',flow=True)
 left,right,bottom,top=175.,3280.-50.,100.,h-100.
 if 'DASHED' not in doc.linetypes:doc.linetypes.new('DASHED').setup_pattern([10.,6.,-4.])
 if 'N5_SEPARACAO_VIGAS' not in doc.layers:doc.layers.new('N5_SEPARACAO_VIGAS',dxfattribs={'color':4,'linetype':'DASHED'})
 return dict(doc=doc,width=w,height=h,left=left,right=right,bottom=bottom,top=top,kind=kind,entries=[])

def assemble_manifests(dst,manifests,*,assembly,behavior,obra,cliente,pavimento,pages_dir):
 units=read_units(manifests,assembly,behavior)
 sources=dict.fromkeys(unit['beam'] for unit,path in units)
 pages=[];coverage=[]
 families=('LV_PAINEIS','LV_GRADES') if assembly=='gradeadas' else ('LV',)
 for family in families:
  prototype=sheet(family,behavior);left,right,bottom,top=[prototype[k] for k in ('left','right','bottom','top')]
  prepared=[];cut_keys=set()
  grade_counts={};grade_seen=set()
  if family=='LV_GRADES':
   for mf in manifests:
    for u in json.loads(mf.read_text(encoding='utf8'))['units']:
     if u['kind']=='GRADE':
      k=(u['beam'],grade_key(u['contract']));grade_counts[k]=grade_counts.get(k,0)+1
  for manifest in manifests:
   data=json.loads(manifest.read_text(encoding='utf8'))
   for unit in data['units']:
    if family=='LV_GRADES' and unit['kind']=='AB':continue
    if family!='LV_GRADES' and unit['kind']=='GRADE':continue
    path=manifest.parent/unit['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==unit['sha256']
    doc=ezdxf.readfile(path)
    if unit['kind']=='CORTE':
     key=cut_design_key(doc,unit['beam'])
     # Preserve each of the 12 approved section contracts, even if the current renderer hides a difference.
     cut_keys.add(key)
     b=bbox.extents(doc.modelspace())
     text(doc.modelspace(),'CORTE — ESC. 1:25',((b.extmin.x+b.extmax.x)/2,b.extmin.y-12),5,7)
    elif assembly=='gradeadas':
     for e in list(doc.modelspace()):
      if family=='LV_PAINEIS' and e.dxf.layer.casefold() in ('sarrafos','meio_pont.','madeira','sarrafo_2_2x7','sarr_3.5x7','meiopontalete'):doc.modelspace().delete_entity(e)
      # Loose grades receive their own explicit boundary and number layers below.
    if unit['kind']=='GRADE':
     k=(unit['beam'],grade_key(unit['contract']))
     if k in grade_seen:continue
     grade_seen.add(k)
     for e in doc.modelspace().query('MTEXT'):
      if e.text.startswith('GRADE SOLTA'):e.text=f'GRADE SOLTA\\P({grade_counts[k]}X)'
    if unit['kind']=='GRADE':pieces=paginate_grade(doc,unit['contract'],right-left)
    elif unit['kind']=='AB' and family!='LV_GRADES':pieces=paginate_ab(doc,unit['contract'],right-left)
    else:pieces=[(doc,None)]
    for doc,window in pieces:
     b=bbox.extents(doc.modelspace());scale=2 if unit['kind']=='CORTE' else 1
     prepared.append(dict(doc=doc,b=b,scale=scale,w=b.size.x*scale,h=b.size.y*scale,anchor=b.extmax.y,unit=unit,source=str(path),window=window))
  for beam in sources:
   panels=[p for p in prepared if p['unit']['beam']==beam and p['unit']['kind']=='AB']
   above=max((p['b'].extmax.y-p['unit']['contract'].get('datum_y_cm',p['b'].extmax.y) for p in panels),default=0)
   for p in panels:
    p['anchor']=p['unit']['contract'].get('datum_y_cm',p['b'].extmax.y)+above;p['h']=p['anchor']-p['b'].extmin.y
  page=None;next_zone=None
  def place(p,x,y):
   b=p['b'];s=p['scale']
   # Each prepared doc is placed once and discarded; transfer may move it in place.
   transfer(p['doc'],page['doc'],x-b.extmin.x*s,y-p['anchor']*s,scale=s,native_mlines=True)
   coverage.append(dict(family=family,beam=p['unit']['beam'],kind=p['unit']['kind'],unit=p['unit'],source=p['source'],window=p['window'],scale=s,page=len(pages),bounds=[x,y-p['h'],x+p['w'],y]))
  for beam in sources:
   cuts=[p for p in prepared if p['unit']['beam']==beam and p['unit']['kind']=='CORTE']
   panels=[p for p in prepared if p['unit']['beam']==beam and p['unit']['kind'] in ('AB','GRADE')]
   first=cuts[0] if cuts else panels[0]
   if next_zone and first['w']<=right-next_zone[0] and first['h']<=next_zone[1]-bottom:
    zl,zt=next_zone
    page['doc'].modelspace().add_line((zl-30,bottom),(zl-30,zt),dxfattribs={'layer':'N5_SEPARACAO_VIGAS'})
   else:page=None;zl,zt=left,top
   next_zone=None
   while cuts or panels:
    if page is None:page=sheet(family,behavior);pages.append(page);zl,zt=left,top
    x=zl;ch=0.;placed=[]
    for p in cuts:
     if x+p['w']<=right and p['h']<=zt-bottom:
      place(p,x,zt);placed.append(p);x+=p['w']+25;ch=max(ch,p['h'])
    cuts=[p for p in cuts if p not in placed]
    cx=x;x=zl;y=zt-ch-(45 if placed else 0);rh=0.;count=0
    while panels:
     p=panels[0]
     if x+p['w']>right:
      if family!='LV_GRADES' and p['window'] is None and right-x>120:
       try:pieces=paginate_ab(p['doc'],p['unit']['contract'],right-zl,first_width=right-x)
       except ValueError:pieces=[]
       if len(pieces)>1:
        children=[]
        for d,w in pieces:
         b=bbox.extents(d.modelspace());children.append(dict(p,doc=d,b=b,window=w,w=b.size.x,h=p['anchor']-b.extmin.y))
        panels[:1]=children;continue
      if x==zl:break
      x=zl;y-=rh+45;rh=0
      if x+p['w']>right:break
     if y-max(rh,p['h'])<bottom:break
     place(p,x,y);panels.pop(0);x+=p['w']+25;rh=max(rh,p['h']);count+=1
    if cuts or panels:
     if not placed and not count and zl==left:raise ValueError('Unidade não cabe: '+beam)
     page=None
    else:next_zone=(x+35,y) if count else (cx+35,zt)
 index,iw,ih=template_doc('LV',flow=True)
 for e in list(index.modelspace()):
  if e.dxf.layer in ('margem','Folha','Carimbo'):continue
  b=bbox.extents([e],fast=True)
  if b.has_data and (b.extmin.x<iw-1150 or b.extmin.y>1300):index.modelspace().delete_entity(e)
 text(index.modelspace(),f'{obra} / {pavimento} — {behavior.upper()} — {assembly.upper()}',(1100,ih-200),24,7)
 index_entries=[]
 for i,p in enumerate(pages,2):
  beams=list(dict.fromkeys(e['beam'] for e in coverage if e['page']==i-1))
  index_entries.append(dict(page=i,kind=p['kind'],beams=beams))
 rows=max(1,int((ih-600)//35))
 for j,e in enumerate(index_entries):
  col,row=divmod(j,rows)
  label=text(index.modelspace(),f'{e["page"]:02d} — {e["kind"]} — '+', '.join(e['beams']),(150+col*(iw-300)/3,ih-280-row*35),16,7)
  from ezdxf.enums import TextEntityAlignment
  label.set_placement((150+col*(iw-300)/3,ih-280-row*35),align=TextEntityAlignment.LEFT)
 pages.insert(0,dict(doc=index,width=iw,height=ih,kind='INDEX'))
 pages_dir=Path(pages_dir);pages_dir.mkdir(parents=True,exist_ok=True)
 records=[];cursor=0.
 for i,p in enumerate(pages,1):
  stamp(p['doc'],p['width'],p['height'],obra=obra,cliente=cliente,pavimento=pavimento,cls='LV',number=i,total=len(pages))
  # Keep used native resources while dropping invalid anonymous template blocks.
  clean=ezdxf.new('R2018');transfer(p['doc'],clean,native_mlines=True)
  normalize_resources(clean);beam_resources(clean);clean.header['$INSUNITS']=5
  audit=clean.audit()
  if audit.errors or any(x.code!=202 or 'FIELD' not in x.message for x in audit.fixes):
   raise ValueError(f'Folha {i}: reparo CAD inesperado: {[(x.code,x.message) for x in audit.errors+audit.fixes]}')
  audit=clean.audit()
  if audit.errors or audit.fixes:raise ValueError(f'Folha {i}: DXF inválido')
  path=pages_dir/f'folha_{i:03d}.dxf';clean.saveas(path)
  origin=[cursor,0.]
  transfer(clean,dst,dx=cursor,native_mlines=True);cursor+=p['width']+300
  entries=[dict(e,page=i) for e in coverage if i>1 and e['page']==i-1]
  records.append(dict(page=i,kind=p['kind'],output=str(path),origin=origin,width=p['width'],height=p['height'],entries=entries))
 for e in coverage:e['page']+=1
 normalize_resources(dst);beam_resources(dst);dst.header['$INSUNITS']=5
 return dict(kind='ini_frames_v1',design='ini_approved_n3_v02',approval='n3_design_approved',mode='INI',assembly=assembly,behavior=behavior,pages=records,index=index_entries,lateral_units=coverage,editable=True)
