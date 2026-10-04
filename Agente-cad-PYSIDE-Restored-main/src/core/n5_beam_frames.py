"""Pack the actual FV N3 segments in Nova sheets, without redrawing geometry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.enums import TextEntityAlignment

from src.core.n5_pillar_frames import SheetBuilder, UX, UY, UW, UH, uploaded_template


def segment_entities(doc, contract):
    """Use N3 dimension anchors, not assumptions about the generator's gaps."""
    panels = contract.get('panels', [])
    dims = []
    for e in doc.modelspace().query('DIMENSION'):
        a, z = e.dxf.get('defpoint2'), e.dxf.get('defpoint3')
        if a is not None and z is not None and abs(a.y-z.y) < .01 and abs(a.x-z.x) > .01:
            dims.append((min(a.x,z.x),max(a.x,z.x)))
    spans = []
    previous = float('-inf')
    expanded = []
    for panel in panels:
        for _ in range(max(1,int(panel.get('_multiplier',1)))):
            expanded.append(panel)
            width = float(panel.get('total_width',panel.get('comprimento_total_fundo',0)))
            candidates = [(a,z) for a,z in dims if a >= previous-.01 and abs(z-a-width)<.06]
            if not candidates:
                raise ValueError(f"Segmento sem cota N3 correspondente: {contract.get('name')} / {width}")
            span = min(candidates)
            spans.append(span)
            previous = span[1]+.02
    if not spans:
        raise ValueError('N3 de fundos sem segmentos')
    cuts = [(spans[i][1]+spans[i+1][0])/2 for i in range(len(spans)-1)]
    groups = [[] for _ in spans]
    removed = []
    for e in doc.modelspace():
        b = bbox.extents([e],fast=True)
        if b.has_data and b.extmax.x < -5000:
            removed.append(('helper',e.dxf.handle)); continue
        if e.dxftype() in ('TEXT','MTEXT') and e.dxf.layer == 'NOMENCLATURA':
            removed.append(('annotation',e.dxf.handle)); continue
        if not b.has_data:
            raise ValueError(f'Entidade N3 sem extensão: {e.dxftype()}')
        x = b.center.x
        if e.dxftype() == 'TEXT' and e.dxf.layer == '5':
            # Long support names must not migrate to the next segment merely
            # because their text bounding box crosses the partition.
            x = e.get_placement()[1].x
        if e.dxftype() == 'DIMENSION':
            a,z = e.dxf.get('defpoint2'),e.dxf.get('defpoint3')
            if a is not None and z is not None:
                x = (a.x+z.x)/2
                if sum(a.x>c for c in cuts) != sum(z.x>c for c in cuts):
                    raise ValueError('Cota N3 atravessa segmentos; montagem interrompida')
        groups[sum(x>c for c in cuts)].append(e)
    if sum(map(len,groups))+len(removed) != len(doc.modelspace()):
        raise ValueError('Partição N3 incompleta')
    return [(panel,span,entities) for panel,span,entities in zip(expanded,spans,groups)], removed


def _label(doc, value, at, align=TextEntityAlignment.LEFT, layer='5', source=None):
    if value:
        if layer not in doc.layers:
            color = source.layers.get(layer).dxf.color if source is not None and layer in source.layers else (5 if layer=='5' else 7)
            doc.layers.new(layer,dxfattribs={'color':color})
        template = next(iter(source.modelspace().query('TEXT').filter(lambda e: e.dxf.layer==layer)),None) if source is not None else None
        attrs = {'height':12,'color':256,'layer':layer}
        if template is not None:
            attrs.update({k:getattr(template.dxf,k) for k in ('height','color','style','rotation','width')})
            style=attrs['style']
            if style not in doc.styles:
                doc.styles.new(style,dxfattribs={'font':source.styles.get(style).dxf.font})
        doc.modelspace().add_text(str(value),dxfattribs=attrs).set_placement(at,align=align)


def assemble_beam_frames(dst, sources, *, obra='', pavimento='', pages_dir=None, cliente=None,
                         frame_path=None, index_path=None):
    frame_path = frame_path or uploaded_template('drawing_frames','FV')
    index_path = index_path or uploaded_template('drawing_legends','FV')
    if frame_path is None or index_path is None:
        raise ValueError('Envie moldura e índice dos fundos do Modo Nova antes de gerar N5')
    builder = SheetBuilder(dst,ezdxf.readfile(frame_path),obra,pavimento,'FUNDOS DE VIGA',cliente=cliente)
    # Bounds include the real dimension/text extents, not only panel widths.
    left,right,top,bottom = UX+20,UX+UW-20,UY+UH-60,UY+20
    x,y,row_height = left,top,0.0
    sheet = None
    row = 0
    coverage = []
    placements = []
    for item,path in sources:
        path = Path(path)
        contract_path = path.parent.parent/'contracts'/(item+'_fundo.json')
        if not contract_path.exists():
            raise ValueError(f'Contrato N3 ausente para {item}')
        contract = json.loads(contract_path.read_text(encoding='utf8'))
        source = ezdxf.readfile(path)
        parts,removed = segment_entities(source,contract)
        coverage.append({'item':item,'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'segments':len(parts),'source_entities':len(source.modelspace()),
            'preserved_entities':sum(len(p[2]) for p in parts),'replaced_annotations':sum(t=='annotation' for t,_ in removed),
            'excluded_helpers':sum(t=='helper' for t,_ in removed)})
        last_row = None
        for number,(panel,(a,z),entities) in enumerate(parts,1):
            b = bbox.extents(entities,fast=True)
            if not b.has_data:
                raise ValueError(f'Segmento N3 vazio: {item}/{number}')
            annotation = ezdxf.new('R2018')
            # Native N3 endpoint annotations stay untouched. Only a continuation
            # needs its initial support repeated at the new row's left edge.
            endpoint = next((e for e in source.modelspace().query('TEXT') if e.dxf.layer=='5'),None)
            label_y = endpoint.get_placement()[1].y if endpoint is not None else b.extmax.y+35
            header=next((e for e in source.modelspace().query('TEXT') if e.dxf.layer=='NOMENCLATURA'),None)
            header_y=header.get_placement()[1].y if header is not None else b.extmax.y+9
            possible_name=('Cont. ' if number>1 else '')+item+'.'+str(contract.get('side') or 'C')
            _label(annotation,possible_name,(a+3,header_y),layer='NOMENCLATURA',source=source)
            if number>1:
                _label(annotation,panel.get('texto_esq',''),(a-10,label_y),TextEntityAlignment.RIGHT,source=source)
            ab = bbox.extents(annotation.modelspace(),fast=True)
            min_x = min(b.extmin.x,ab.extmin.x) if ab.has_data else b.extmin.x
            max_x = max(b.extmax.x,ab.extmax.x) if ab.has_data else b.extmax.x
            min_y = min(b.extmin.y,ab.extmin.y) if ab.has_data else b.extmin.y
            max_y = max(b.extmax.y,ab.extmax.y) if ab.has_data else b.extmax.y
            width,height = max_x-min_x,max_y-min_y
            if width > right-left+.01 or height > top-bottom+.01:
                raise ValueError(f'Segmento {item}/{number} excede a área útil; não será reduzido ou cortado')
            if sheet is not None and x+width > right+.01:
                y -= row_height+45; x=left; row_height=0; row+=1
            if sheet is None or y-height < bottom-.01:
                sheet = builder.sheet('Fundos: ')
                sheet_record = builder.sheets[-1]
                sheet_record['names'] = []
                x,y,row_height,row = left,top,0,0
            key = (len(builder.sheets),row)
            name = ''
            if number==1 or key!=last_row:
                name = possible_name
            else:
                annotation.modelspace().delete_all_entities()
            dx,dy = x-min_x,y-max_y
            builder.place(sheet,source,entities,dx,dy)
            if len(annotation.modelspace()):
                builder.place(sheet,annotation,list(annotation.modelspace()),dx,dy)
            if item not in sheet_record['names']:
                sheet_record['names'].append(item)
            sheet_record['title']='Fundos: '+', '.join(sheet_record['names'])
            placements.append({'item':item,'segment':number,'sheet':len(builder.sheets),'row':row,
                'name':name,'initial':panel.get('texto_esq',''),'final':panel.get('texto_dir',''),
                'length_cm':z-a,'bounds':[x,y-height,x+width,y],'scale':1})
            last_row=(len(builder.sheets),row)
            x+=width+25;row_height=max(row_height,height)
    result = builder.finish(ezdxf.readfile(index_path),pages_dir)
    result.pop('minimum_grade_gap_cm',None)
    result.update(beam_coverage=coverage,segments=placements,segment_gap_cm=25,row_gap_cm=45)
    return result
