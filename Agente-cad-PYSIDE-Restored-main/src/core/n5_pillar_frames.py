"""N5 Nova sheets from published N3, with immutable uploaded templates.

The template coordinates below describe the owner's approved sheet, not a
pillar or a job. Unknown templates fail explicitly instead of silently clipping.
"""
from __future__ import annotations

import hashlib
import json
import math
import textwrap
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.disassemble import recursive_decompose, make_primitive
from ezdxf.math import Matrix44

W, H, DX, DY = 1485.0, 1050.0, 1585.0, 1150.0
UX, UY, UW, UH = 73.5, 240.243513411, 1373.0, 771.256486589
BASE_Y = UY + 100
FRAME_SHA = 'ecbe21091b1c8ac13634d1530915c2e12376bd6ac405499619f1fec6295c30ac'
INDEX_SHA = 'd08aaa486b2e0fb83b1926dfe4053eb070c25f11648c24b609b95d6a435d92fc'
INDEX_ORIGINS = [(3241.333912680476,2334.388199800193),
 (4826.333912680478,2334.388199800193),(6411.333912680482,2334.388199800195),
 (7996.333912680483,2334.388199800195),(3241.333912680482,1184.388199800195),
 (4826.333912680482,1184.388199800195)]
INDEX_TITLES = ['CAPA','ÍNDICE','LEGENDA DO PROJETO',
 'GUIA DE MONTAGEM E INTERPRETAÇÃO','PLANTA DO PILAR / DETALHE GASTALHO',
 'DETALHE GENÉRICO DA FURAÇÃO']


def flatten_editable(doc):
    """Publish native entities, never one INSERT per drawing or sheet.

    Resolve inherited block attributes before dropping the block hierarchy;
    otherwise layer 0 and BYBLOCK objects would change their appearance.
    """
    ms = doc.modelspace()
    def expand(entity, parent=None):
        e = entity.copy()
        if parent is not None:
            if e.dxf.layer == '0':
                e.dxf.layer = parent.dxf.layer
            if e.dxf.get('color',256) == 0:
                color = parent.dxf.get('color',256)
                e.dxf.color = color
                if parent.dxf.hasattr('true_color'):
                    e.dxf.true_color = parent.dxf.true_color
        if e.dxftype() == 'INSERT':
            for child in e.virtual_entities():
                yield from expand(child,e)
            for attr in e.attribs:
                from ezdxf.explode import attrib_to_text
                yield attrib_to_text(attr)
        elif e.dxftype() in ('LWPOLYLINE','POLYLINE'):
            for part in e.virtual_entities():
                yield part
        elif e.dxftype() == 'DIMENSION':
            for child in e.virtual_entities():
                yield from expand(child,e)
        else:
            yield e
    for entity in list(ms):
        if entity.dxftype() in ('INSERT','LWPOLYLINE','POLYLINE','DIMENSION'):
            parts = list(expand(entity))
            ms.delete_entity(entity)
            for part in parts:
                ms.add_entity(part)


def uploaded_template(collection: str, classe: str = 'PL') -> Path | None:
    from scripts.drawing_mode_config import storage_path
    root = storage_path().parent / collection / 'NOVA' / classe
    current = root / 'current.json'
    if not current.exists():
        return None
    value = json.loads(current.read_text(encoding='utf8'))
    token = value['id']
    if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Identificador de documento inválido')
    path = root / (token + '.dxf')
    expected = FRAME_SHA if collection == 'drawing_frames' else INDEX_SHA
    if collection == 'drawing_legends' and classe in ('LV_PARA', 'LV_PASSA'):
        from .n5_lateral_frames import LV_INDEX_SHA
        expected = LV_INDEX_SHA
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('A moldura/índice foi substituída; calibre a área útil antes de unificar')
    return path


def position(page: int):
    return ((page-1) % 4 * DX, -((page-1)//4) * DY)


def index_sheet_order(continuations, titles=None):
    """Keep overflow beside the index and shift every subsequent sheet."""
    titles = INDEX_TITLES if titles is None else titles
    if len(titles) not in (2, len(INDEX_ORIGINS)):
        raise ValueError('O índice calibrado requer duas ou seis folhas iniciais')
    return ([(0, titles[0]), (1, titles[1])]
            + [(1, 'ÍNDICE — CONTINUAÇÃO')] * continuations
            + list(enumerate(titles[2:], start=2)))


def primitives(entities):
    result = []
    for entity in recursive_decompose(entities):
        result.extend(recursive_decompose([entity]) if entity.dxftype() == 'DIMENSION' else [entity])
    return result


def projection_entities(doc):
    return [e for e in doc.modelspace() if e.dxf.layer != 'Nível'
            and not (e.dxftype() == 'INSERT' and e.dxf.name == 'MULDURA')
            and not (e.dxftype() == 'TEXT' and e.dxf.text.startswith(('CENARIOS', 'NIVEL DE')))]


def projection_parts(doc):
    """Split at real E-face anchor; preserves all geometry and dimension entities."""
    entities = projection_entities(doc)
    anchors = {}
    for e in doc.modelspace().query('TEXT'):
        text = e.dxf.text.strip().rsplit('.',1)[-1]
        if text in 'ABCDEFGH' and len(text) == 1:
            anchors[text] = e.dxf.insert.x
    if 'E' not in anchors:
        return [entities]
    left = max(x for key, x in anchors.items() if key in 'ABCD')
    cut = (left + anchors['E']) / 2
    parts = [[], []]
    for e in entities:
        b = bbox.extents([e], fast=True)
        if b.has_data:
            parts[int(b.center.x >= cut)].append(e)
    return [part for part in parts if part]


def grade_groups(doc, item_id):
    labels = sorted([e for e in doc.modelspace().query('TEXT')
                     if e.dxf.text.startswith(item_id + '.')], key=lambda e:e.dxf.insert.x)
    if not labels:
        raise ValueError('Grades sem identificação de face')
    cuts = [e.dxf.insert.x-10 for e in labels[1:]]
    faces = [[] for _ in labels]
    for e in doc.modelspace():
        b = bbox.extents([e], fast=True)
        if b.has_data:
            faces[sum(b.center.x > x for x in cuts)].append(e)
    result = []
    for i, face in enumerate(faces):
        spans = sorted(set((round(min(e.dxf.start.x,e.dxf.end.x),4),
                            round(max(e.dxf.start.x,e.dxf.end.x),4)) for e in face
            if e.dxftype() == 'LINE' and e.dxf.layer == 'SARR_2.2x7'
            and abs(e.dxf.start.y) < .001 and abs(e.dxf.end.y) < .001
            and abs(e.dxf.end.x-e.dxf.start.x) > 10))
        if not spans:
            raise ValueError('Grades sem limites geométricos')
        for n, (lo, hi) in enumerate(spans):
            entities = []
            for e in face:
                if e.dxftype() in ('TEXT','MTEXT') and e.dxf.layer.upper() != 'COTA':
                    continue
                b = bbox.extents([e], fast=True)
                if not b.has_data:
                    continue
                x = b.center.x
                if e.dxftype() == 'DIMENSION':
                    a,z = e.dxf.get('defpoint2'), e.dxf.get('defpoint3')
                    if a is None or z is None or not (lo-.01 <= a.x <= hi+.01 and lo-.01 <= z.x <= hi+.01):
                        continue
                    x = (a.x+z.x)/2
                if lo-.01 <= x <= hi+.01:
                    entities.append(e)
            geom = [e for e in entities if e.dxftype() != 'DIMENSION' and e.dxf.layer.upper() != 'COTA']
            b = bbox.extents(geom, fast=True)
            signature = []
            for e in recursive_decompose(geom):
                points = sorted((round(v.x-b.extmin.x,4),round(v.y-b.extmin.y,4)) for v in make_primitive(e).vertices())
                signature.append((e.dxftype(),e.dxf.layer,e.dxf.get('color',256),
                    (e.dxf.get('pattern_name'),e.dxf.get('pattern_scale'),e.dxf.get('pattern_angle'),e.dxf.get('solid_fill')) if e.dxftype()=='HATCH' else None,points))
            digest = hashlib.sha256(json.dumps(sorted(signature,key=str)).encode()).hexdigest()
            name = labels[i].dxf.text + (f'-{n+1}' if len(spans)>1 else '')
            result.append({'doc':doc,'entities':entities,'signature':digest,'names':[name]})
    return result


def grade_requirements(payload):
    """Physical faces from N3's SA contract; narrow end faces need no grade."""
    from src.core.cima_l_contract import n3_faces_l
    special = n3_faces_l(payload)
    base = payload.get('_sa_mode_contract', {}).get('n1_base', {}) or payload.get('n1_base', {})
    shape = str(payload.get('subtipo_pil') or base.get('subtipo_pil') or
                (payload.get('pilar_especial') or {}).get('tipo_pilar_especial') or '').upper()
    widths = {face['id']: float(face['panel']) for face in special} if special else {
        face: sum(float(payload.get(f'larg{i}_{face}') or 0) for i in range(1, 4))
        for face in 'ABCDEFGH'}
    return {face: {'width': width, 'required': width > (40 if face in 'CD' or
            (face == 'H' and shape == 'T') else 0)} for face, width in widths.items() if width > 0}


def eligible_grade_groups(groups, payload, item_id, variant=''):
    requirements = grade_requirements(payload)
    by_face = {}
    for group in groups:
        face = group['names'][0].removeprefix(item_id + '.').split('-')[0]
        if face not in requirements:
            raise ValueError(f'{item_id}: grade em face sem largura SA: {face}')
        by_face.setdefault(face, []).append(group)
    missing = [face for face, rule in requirements.items() if rule['required'] and not by_face.get(face)]
    if missing:
        raise ValueError(f'{item_id}: faltam grades necessárias nas faces {", ".join(missing)}')
    kept = [group for face, face_groups in by_face.items() if requirements[face]['required'] for group in face_groups]
    audit = {'item': item_id, 'variant': variant, 'faces': [dict(face=face, **rule,
        source_parts=len(by_face.get(face, [])), unified_parts=len(by_face.get(face, [])) if rule['required'] else 0)
        for face, rule in requirements.items()], 'names': [name for group in kept for name in group['names']]}
    return kept, audit


class SheetBuilder:
    def __init__(self, dst, frame, obra='', pavimento='', classe_title='PILARES', cliente=None):
        self.dst = dst
        self.frame = frame
        self.sheets = []
        self.blocks = 0
        self.placements = []
        # Carimbo values can live inside INSERTs. Expand copies before replacing
        # them; changing only modelspace TEXT leaves the uploaded example names.
        self.frame_entities = [e.copy() for e in primitives(frame.modelspace())
            if not (e.dxftype() == 'TEXT' and e.dxf.layer == 'CARIMBO' and e.dxf.text == '06')]
        self.stamp_values = {'ALIMONTI': (cliente or '').strip() or 'NÃO INFORMADO',
            'CAPREM': (cliente or '').strip() or 'NÃO INFORMADO',
            'PARAISO': obra, 'RESIDENCIAL DIAMOND': obra,
            '1° PAVIMENTO': pavimento, '1º PAVIMENTO': pavimento,
            '1° SUB - PERIFERIA - TORRE 1 - S01A': pavimento,
            'LATERAL DE VIGAS': classe_title, 'PILAR': classe_title, 'PILARES': classe_title}
        self.fill_stamp(self.frame_entities)
        self.page_label = next(e for e in frame.modelspace().query('TEXT') if e.dxf.text == '06')
        if 'NOVA_LEVEL_DASH' not in dst.linetypes:
            dst.linetypes.new('NOVA_LEVEL_DASH',dxfattribs={'pattern':[12,6,-6]})
        if 'REFERENCIA_NIVEL' not in dst.layers:
            dst.layers.new('REFERENCIA_NIVEL',dxfattribs={'color':5,'linetype':'NOVA_LEVEL_DASH'})

    def fill_stamp(self, entities):
        for entity in entities:
            if entity.dxftype() in ('TEXT', 'MTEXT'):
                text = entity.dxf.text.strip()
                if text in self.stamp_values:
                    entity.dxf.text = self.stamp_values[text]
        return entities

    def block(self, doc, entities):
        self.blocks += 1
        name = 'N5_FRAME_PART_' + str(self.blocks)
        while name in doc.blocks:
            self.blocks += 1
            name = 'N5_FRAME_PART_' + str(self.blocks)
        block = doc.blocks.new(name)
        for e in primitives(entities):
            block.add_entity(e.copy())
        imp = Importer(doc,self.dst)
        key = imp.import_block(name,rename=True)
        imp.finalize()
        return key

    def sheet(self, title, counted=True):
        doc = ezdxf.new('R2018')
        self.sheets.append({'title':title,'counted':counted,'doc':doc,'names':[]})
        return doc

    def place(self, target, source, entities, x, y, scale=1):
        # All N3 inputs are loaded copies; imported primitives never mutate source files.
        key = self.block(source, entities)
        imp = Importer(self.dst,target)
        imported = imp.import_block(key,rename=True)
        imp.finalize()
        target.modelspace().add_blockref(imported,(x,y),dxfattribs={'xscale':scale,'yscale':scale})
        b = bbox.extents(entities,fast=True)
        self.placements.append({'bounds':[x+b.extmin.x*scale,y+b.extmin.y*scale,
            x+b.extmax.x*scale,y+b.extmax.y*scale],'scale':scale})

    def centered(self, target, source, entities, region, scale=1, fit=False):
        b = bbox.extents(entities,fast=True)
        x,y,w,h = region
        if fit:
            scale=min(scale,w/b.size.x,h/b.size.y)
        if b.size.x*scale>w+.01 or b.size.y*scale>h+.01:
            raise ValueError('Vista N3 excede área útil da moldura na escala original')
        self.place(target,source,entities,x+(w-b.size.x*scale)/2-b.extmin.x*scale,
                   y+(h-b.size.y*scale)/2-b.extmin.y*scale,scale)

    def top_aligned(self, target, source, entities, region, scale=1, fit=False):
        """Anchor the complete Cima (including its name) to the upper frame.

        Different section sizes grow downwards; the ABCD level datum stays fixed.
        """
        b = bbox.extents(entities,fast=True)
        x,y,w,h = region
        if fit:
            scale=min(scale,w/b.size.x,h/b.size.y)
        if b.size.x*scale>w+.01 or b.size.y*scale>h+.01:
            raise ValueError('Vista N3 excede área útil da moldura na escala original')
        self.place(target,source,entities,x+(w-b.size.x*scale)/2-b.extmin.x*scale,
                   y+h-b.extmax.y*scale,scale)

    def level_headers(self, target, height, payload):
        from src.core.number_presentation import display_level, display_number
        values=[('NÍVEL DE CHEGADA',display_level(payload.get('nivel_chegada_abs',payload.get('nivel_chegada')))),
                ('NÍVEL DE SAÍDA',display_level(payload.get('nivel_saida_abs',payload.get('nivel_saida')))),
                ('PÉ-DIREITO',f'{display_number(height)} cm')]
        for i,(label,value) in enumerate(values):
            target.modelspace().add_text(f'{label}: {value}',dxfattribs={
                'height':10,'color':7,'insert':(UX+16,UY+UH-24-i*16)})
        next(s for s in self.sheets if s['doc'] is target)['level_headers']=True

    def anchored(self, target, source, entities, source_y, left=None):
        b = bbox.extents(entities,fast=True)
        x = UX+(UW-b.size.x)/2 if left is None else left
        dy = BASE_Y-source_y
        if b.size.x > UW-60 or b.extmin.y+dy < UY or b.extmax.y+dy > UY+UH-30:
            raise ValueError('Projeção/grade excede a moldura na escala original')
        self.place(target,source,entities,x-b.extmin.x,dy)

    def levels(self, target, height, payload, headers=True):
        if 'NOVA_LEVEL_DASH' not in target.linetypes:
            target.linetypes.new('NOVA_LEVEL_DASH',dxfattribs={'pattern':[12,6,-6]})
        if 'REFERENCIA_NIVEL' not in target.layers:
            target.layers.new('REFERENCIA_NIVEL',dxfattribs={'color':5,'linetype':'NOVA_LEVEL_DASH'})
        ms = target.modelspace()
        for y in (BASE_Y,BASE_Y+height):
            ms.add_line((UX,y),(UX+UW,y),dxfattribs={'layer':'REFERENCIA_NIVEL','color':5,'linetype':'NOVA_LEVEL_DASH'})
        if headers:
            self.level_headers(target,height,payload)
        dim = ms.add_linear_dim(base=(UX+28,BASE_Y),p1=(UX+45,BASE_Y),
            p2=(UX+45,BASE_Y+height),angle=90,override={'dimtxt':8,'dimasz':3,
            'dimclrd':5,'dimclre':5,'dimclrt':7})
        dim.render()

    def finish(self, index, pages_dir=None, *, index_titles=None, index_sha256=INDEX_SHA):
        counted=[s for s in self.sheets if s['counted']]
        # Overflow follows the index itself, before the remaining template sheets.
        continuations = 0
        base_count = len(INDEX_TITLES if index_titles is None else index_titles)
        while True:
            rows=[(i+1,t) for i,(_,t) in enumerate(index_sheet_order(continuations, index_titles))]
            rows += [(base_count+1+continuations+i,s['title']) for i,s in enumerate(counted)]
            lines=[]
            for number,title in rows:
                for j,line in enumerate(textwrap.wrap(title,width=72,break_long_words=False)):
                    lines.append((f'{number:02d}' if j==0 else '',line))
            needed=max(0,math.ceil(len(lines)/22)-1)
            if needed==continuations:
                break
            continuations=needed
        index_entities=primitives(index.modelspace())
        layout=[]
        def emit(doc, entities, old, new):
            key=self.block(doc,entities)
            self.dst.modelspace().add_blockref(key,(new[0]-old[0],new[1]-old[1]))
            if pages_dir is not None:
                pages_dir.mkdir(parents=True,exist_ok=True)
                page_doc=ezdxf.new('R2018')
                imp=Importer(self.dst,page_doc)
                imported=imp.import_block(key,rename=True);imp.finalize()
                page_doc.modelspace().add_blockref(imported,(-old[0],-old[1]))
                flatten_editable(page_doc)
                page_doc.saveas(pages_dir/f'page_{len(layout):03d}.dxf')
        index_part=0
        for page,(i,title) in enumerate(index_sheet_order(continuations, index_titles),start=1):
            old=INDEX_ORIGINS[i]
            selected=[e for e in index_entities if (lambda b:b.has_data and
                old[0]-.01<=b.center.x<=old[0]+W+.01 and old[1]-.01<=b.center.y<=old[1]+H+.01)(bbox.extents([e],fast=True))]
            selected=self.fill_stamp([e.copy() for e in selected])
            for e in selected:
                if e.dxftype()=='TEXT' and e.dxf.text==f'{i+1:02d}':
                    e.dxf.text=f'{page:02d}'
            if i==0:
                selected.append(index.modelspace().add_text('01',dxfattribs={'height':40,'color':7,
                    'insert':(old[0]+1349.553261834,old[1]+76)}))
            if i==1:
                selected=self.index_body(index,selected,lines[index_part*22:(index_part+1)*22])
                index_part+=1
            if not any(e.dxftype()=='TEXT' and e.dxf.text=='CLIENTE:' for e in selected):
                # The uploaded index page has no footer: reuse the current stamp,
                # reserving the bottom 240 cm by limiting index rows above it.
                for e in self.frame_entities:
                    if e.dxftype()=='TEXT' and (e.dxf.text in self.stamp_values.values() or
                            e.dxf.text in ('CLIENTE:','OBRA:','PAVIMENTO:','PROJETO:')):
                        label=e.copy()
                        label.translate(old[0]-2017.803539105,old[1]-1429.188948938,0)
                        selected.append(label)
            emit(index,selected,old,position(page))
            layout.append({'page':page,'title':title,'origin':position(page),'counted':True})
        number=base_count+1+continuations
        individual=0
        for sheet in self.sheets:
            target=sheet['doc'];ms=target.modelspace()
            key=self.block(self.frame,self.frame_entities)
            imp=Importer(self.dst,target);name=imp.import_block(key,rename=True);imp.finalize()
            ms.add_blockref(name,(-2017.803539105,-1429.188948938))
            if sheet['counted']:
                new=position(number)
                if self.page_label.dxf.layer not in target.layers:
                    target.layers.new(self.page_label.dxf.layer,dxfattribs={'color':self.frame.layers.get(self.page_label.dxf.layer).dxf.color})
                label=self.page_label.copy();label.dxf.text=f'{number:02d}'
                label.translate(-2017.803539105,-1429.188948938,0);ms.add_entity(label)
                page=number;number+=1
            else:
                new=(4*DX+400,-individual*DY);individual+=1;page=None
            display_title=sheet['title'] if not sheet['title'].startswith('Grades: ') else 'Grades unificadas'
            if not sheet.get('level_headers') and sheet.get('show_header', True):
                ms.add_text(display_title,dxfattribs={'height':14,'color':7,'insert':(UX+30,UY+UH-24)})
            emit(target,list(ms),(0,0),new)
            layout.append({'page':page,'title':sheet['title'],'origin':new,'counted':sheet['counted']})
        flatten_editable(self.dst)
        return {'kind':'nova_frames_v1','columns':4,'pages':layout,'index_rows':rows,
                'minimum_grade_gap_cm':60,'placements':self.placements,
                'template_sha256':FRAME_SHA,'index_sha256':index_sha256}

    @staticmethod
    def index_body(doc, entities, lines):
        result=[e for e in entities if not (e.dxftype()=='TEXT' and e.dxf.layer=='TEXTO'
            and 5240<e.dxf.insert.x<5870 and 2380<e.dxf.insert.y<3245)]
        # Stop the original empty table at the footer boundary, so its grid
        # never runs through the client/work labels copied onto index sheets.
        table_bottom = INDEX_ORIGINS[1][1] + 256.4021360859192
        clipped = []
        for entity in result:
            if entity.dxftype() == 'LINE':
                a, b = entity.dxf.start, entity.dxf.end
                if 5239 <= a.x <= 5860 and 5239 <= b.x <= 5860:
                    if max(a.y, b.y) < table_bottom - .01:
                        continue
                    if min(a.y, b.y) < table_bottom:
                        if a.y < table_bottom:
                            entity.dxf.start = (a.x, table_bottom, a.z)
                        if b.y < table_bottom:
                            entity.dxf.end = (b.x, table_bottom, b.z)
            clipped.append(entity)
        result = clipped
        for i,(number,text) in enumerate(lines):
            for value,x in ((text,5249.430492813659),(number,5816.318990441315)):
                result.append(doc.modelspace().add_text(value,dxfattribs={'insert':(x,3230.790335886109-i*30),'height':10,'color':7,'layer':'TEXTO'}))
        return result


def assemble_frames(dst, sources, *, obra='', pavimento='', pages_dir=None, cliente=None):
    frame_path=uploaded_template('drawing_frames')
    index_path=uploaded_template('drawing_legends')
    if frame_path is None or index_path is None:
        raise ValueError('Envie moldura e índice do Modo Nova antes de gerar N5')
    builder=SheetBuilder(dst,ezdxf.readfile(frame_path),obra,pavimento,cliente=cliente)
    unique={}
    coverage=[]
    for entry in sources:
        item_id,paths=entry[:2]
        suffix=(' — '+entry[2]) if len(entry)>2 else ''
        top,projection,grades=[ezdxf.readfile(p) for p in paths]
        payload_path=Path(paths[1]).parent/(item_id+'.json')
        if not payload_path.exists():
            raise ValueError(f'Ficha N3 ausente para {item_id}')
        payload=json.loads(payload_path.read_text(encoding='utf8'))
        height=float(payload.get('altura',280))
        parts=projection_parts(projection)
        source_y=min(e.get_points()[0][1] for e in projection.modelspace().query('LWPOLYLINE') if e.dxf.layer=='Nível')
        if len(parts)==1:
            sheet=builder.sheet(item_id+suffix+' — Cima + ABCD')
            builder.anchored(sheet,projection,parts[0],source_y)
            builder.top_aligned(sheet,top,list(top.modelspace()),(UX+30,BASE_Y+height+40,UW-60,UY+UH-(BASE_Y+height+40)-24))
            builder.levels(sheet,height,payload)
        else:
            sheet=builder.sheet(item_id+suffix+' — Cima')
            builder.top_aligned(sheet,top,list(top.modelspace()),(UX+30,UY+30,UW-60,UH-54),fit=True)
            builder.level_headers(sheet,height,payload)
            for n,part in enumerate(parts):
                sheet=builder.sheet(item_id+suffix+(' — ABCD' if n==0 else ' — EFGH'))
                builder.anchored(sheet,projection,part,source_y)
                builder.levels(sheet,height,payload)
        original_groups=grade_groups(grades,item_id)
        groups,audit=eligible_grade_groups(original_groups,payload,item_id,entry[2] if len(entry)>2 else '')
        coverage.append(audit)
        grade_box=bbox.extents(grades.modelspace(),fast=True)
        if grade_box.size.x<=UW-60 and len(groups)==len(original_groups):
            sheet=builder.sheet(item_id+suffix+' — Grades',False)
            builder.anchored(sheet,grades,list(grades.modelspace()),0)
            builder.levels(sheet,height,payload)
        else:
            cursor=0; sheet=None
            for group in groups:
                width=bbox.extents(group['entities'],fast=True).size.x
                if sheet is None or cursor+width>UW-60:
                    sheet=builder.sheet(item_id+suffix+' — Grades',False);cursor=0
                    builder.levels(sheet,height,payload)
                builder.anchored(sheet,grades,group['entities'],0,UX+30+cursor)
                sheet.modelspace().add_text(group['names'][0],dxfattribs={'height':10,'color':7,
                    'insert':(UX+30+cursor,BASE_Y+height+95)})
                cursor+=width+60
        for group in groups:
            group['occurrences']=[{'item':item_id,'variant':audit['variant'],'name':group['names'][0]}]
            if group['signature'] in unique:
                unique[group['signature']]['names']+=group['names']
                unique[group['signature']]['occurrences']+=group['occurrences']
            else:
                group.update(height=height,payload=payload)
                unique[group['signature']]=group
    cursor=0;sheet=None;names=[]
    sheet_height=None
    for group in sorted(unique.values(),key=lambda g:(g['height'],-bbox.extents(g['entities'],fast=True).size.x)):
        b=bbox.extents(group['entities'],fast=True)
        if sheet is None or cursor+b.size.x>UW-60 or group['height'] != sheet_height:
            sheet=builder.sheet('Grades: ')
            sheet_height=group['height']
            sheet_record=builder.sheets[-1];names=[];cursor=0
            builder.levels(sheet,group['height'],group['payload'],False)
        builder.anchored(sheet,group['doc'],group['entities'],0,UX+30+cursor)
        group['names']=list(dict.fromkeys(group['names']))
        label=', '.join(group['names'])
        # Keep repeated face names above the grade, within the available header.
        font=8.0
        while True:
            lines=textwrap.wrap(label,width=max(8,int(b.size.x/(font*.65))))
            if len(lines)*font*1.5<=90 or font<=1.5: break
            font-=.5
        for i,line in enumerate(lines):
            sheet.modelspace().add_text(line,dxfattribs={'height':font,'color':7,'insert':(UX+30+cursor,BASE_Y+group['height']+110-i*font*1.5)})
        if cursor:
            sheet.modelspace().add_line((UX+cursor,BASE_Y-65),(UX+cursor,UY+UH-45),dxfattribs={'color':8})
        names.extend(group['names']);sheet_record['title']='Grades: '+', '.join(names)
        cursor+=b.size.x+60
    result=builder.finish(ezdxf.readfile(index_path),pages_dir)
    result['grade_coverage']=coverage
    result['unified_grades']=[{'signature':g['signature'],'names':g['names'],
        'quantity':len(g['occurrences']),'occurrences':g['occurrences']} for g in unique.values()]
    return result
