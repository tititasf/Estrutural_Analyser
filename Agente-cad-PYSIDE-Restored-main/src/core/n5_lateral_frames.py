"""Pack verified NOVA N3 units; do not regenerate or simplify their geometry."""
from hashlib import sha256
import json
from pathlib import Path

import ezdxf
from ezdxf import bbox
from .n5_pillar_frames import SheetBuilder, UX, UY, UW, UH

LV_INDEX_SHA = 'cbce4855d9dcdbcdee43589fc84e6d5f55d3d77286058b703c47ecc974748833'
LV_INDEX_TITLES = ['CAPA', 'ÍNDICE']


def cut_design_key(doc, beam):
    """Compare native cut geometry/annotations within the same beam only."""
    from ezdxf.lldxf.tagwriter import TagCollector
    entities=[]
    for e in doc.modelspace():
        tags=[]
        for tag in TagCollector.dxftags(e):
            if tag.code in (5,330,360):
                continue
            value=tag.value
            if tag.code==1 and e.dxftype()=='TEXT' and value==beam:
                value='<BEAM>'
            elif isinstance(value,float):
                value=round(value,6)
            tags.append((tag.code,str(value)))
        entities.append(json.dumps(tags))
    return sha256((str(beam)+'\n'+'\n'.join(sorted(entities))).encode()).hexdigest()


def published_manifests(obra_dir, pavimento, assembly, behavior, *, pending=None):
    """The newest LV contract inventory is authoritative, including failed units."""
    from .n5_assembler import _production_n3_dirs, natural_key
    behavior = behavior.upper()
    for folder in _production_n3_dirs(Path(obra_dir), pavimento, 'NOVA'):
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
                                                          view[-1], mode='NOVA', assembly=assembly)
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
                                      include_svgs=False)['cut_views']
                if not cuts:
                    raise ValueError(f'N3 atual incompleto: {beam}/{behavior}/CORTE sem seções SA')
                for cut in cuts:
                    try:
                        _, preview, _ = cut_identity(obra_dir, pavimento, behavior.lower(), cut,
                                                    mode='NOVA', assembly=assembly)
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
    raise ValueError(f'Inventário N3 NOVA ausente: {behavior}/{assembly}')


def read_units(manifests, assembly, behavior):
    if assembly not in ('gradeadas', 'sarrafeadas') or behavior.upper() not in ('PARA', 'PASSA'):
        raise ValueError('Identidade N5 lateral inválida')
    units, seen = [], set()
    for manifest in manifests:
        manifest = Path(manifest)
        data = json.loads(manifest.read_text(encoding='utf8'))
        if (data.get('mode'), data.get('assembly_variant'), data.get('behavior','').upper()) != (
                'NOVA', assembly, behavior.upper()):
            raise ValueError('Inventário N3 mistura modos ou montagens')
        for unit in data['units']:
            filename = unit['file']
            if Path(filename).name != filename or Path(filename).suffix != '.dxf':
                raise ValueError('Caminho de unidade N3 inválido')
            path = manifest.parent / filename
            if sha256(path.read_bytes()).hexdigest() != unit['sha256']:
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


def assemble_lateral_frames(dst, manifests, *, assembly, behavior, frame_path,
                            index_path, obra='', pavimento='', cliente=None, pages_dir=None,
                            index_titles=None):
    units = read_units(manifests, assembly, behavior)
    from .n5_assembler import natural_key
    units.sort(key=lambda pair: (natural_key(pair[0]['beam']), pair[0]['kind'] == 'CORTE',
                               pair[0].get('side', ''), pair[0].get('segments', [0])[0]))
    builder = SheetBuilder(dst, ezdxf.readfile(frame_path), obra=obra, pavimento=pavimento,
                           cliente=cliente, classe_title=f'LATERAIS {behavior.upper()} — {assembly.upper()}')
    left, right = UX+20, UX+UW-20
    bottom, top = UY+20, UY+UH-60
    coverage = []
    prepared = []
    from .lv_n5_pagination import paginate_ab
    for unit, path in units:
        source = ezdxf.readfile(path)
        pieces = (paginate_ab(source, unit['contract'], right-left)
                  if unit['kind'] == 'AB' else [(source, None)])
        for doc, window in pieces:
            entities = list(doc.modelspace())
            b = bbox.extents(entities)
            if not b.has_data or doc.audit().has_errors:
                raise ValueError(f'N3 inválido: {path}')
            scale = 2 if unit['kind'] == 'CORTE' else 1
            width, height = b.size.x*scale, b.size.y*scale
            if width > right-left+.01 or height > top-bottom+.01:
                raise ValueError(f"{unit['beam']}/{unit['kind']} excede a moldura na escala {scale}x")
            prepared.append(dict(unit=unit, path=path, doc=doc, window=window,
                                 entities=entities, bbox=b, width=width, height=height, scale=scale,
                                 anchor_top=b.extmax.y))

    # One section per actual design per beam; different beams stay independent.
    cut_groups={}
    unique=[]
    for item in prepared:
        if item['unit']['kind']!='CORTE':
            unique.append(item)
            continue
        key=cut_design_key(item['doc'],item['unit']['beam'])
        alias=dict(unit=item['unit'],source=str(item['path']))
        if key in cut_groups:
            cut_groups[key]['represented_cuts'].append(alias)
        else:
            item.update(cut_key=key,represented_cuts=[alias])
            cut_groups[key]=item
            unique.append(item)
    prepared=unique
    for item in cut_groups.values():
        beams=sorted({a['unit']['beam'] for a in item['represented_cuts']},key=natural_key)
        item['cut_beams']=beams
        for e in item['doc'].modelspace().query('TEXT'):
            if e.dxf.text==item['unit']['beam']:
                e.dxf.text=' / '.join(beams)
        b=bbox.extents(item['entities'])
        item.update(bbox=b,width=b.size.x*2,height=b.size.y*2,anchor_top=b.extmax.y)

    for beam in {p['unit']['beam'] for p in prepared}:
        panels = [p for p in prepared if p['unit']['beam']==beam and p['unit']['kind']=='AB'
                  and 'datum_y_cm' in p['unit'].get('contract', {})]
        above = max((p['bbox'].extmax.y-p['unit']['contract']['datum_y_cm'] for p in panels), default=0.)
        for p in panels:
            p['anchor_top'] = p['unit']['contract']['datum_y_cm']+above
            p['height'] = p['anchor_top']-p['bbox'].extmin.y

    def place(item, sheet, x, y, repeated=False):
        b, scale = item['bbox'], item['scale']
        builder.place(sheet, item['doc'], item['entities'],
                      x-b.extmin.x*scale, y-item['anchor_top']*scale, scale=scale)
        u = item['unit']
        name = u['beam']+('.'+u['side'] if u.get('side') else ' — Corte')
        if u['kind']=='CORTE':
            name=' / '.join(item['cut_beams'])+' — Corte'
        if name not in builder.sheets[-1]['names']:
            builder.sheets[-1]['names'].append(name)
        coverage.append(dict(unit=u, source=str(item['path']), sheet=len(builder.sheets),
                             bounds=[x,y-item['height'],x+item['width'],y], scale=scale,
                             repeated_context=repeated, source_entities=len(item['entities']),
                             translation_cm=[x-b.extmin.x*scale,y-item['anchor_top']*scale],
                             source_window_cm=item['window'],
                             represented_cuts=item.get('represented_cuts',[]),
                             cut_design_key=item.get('cut_key')))

    # Fill cut rows independently of AB associations. A shared sheet keeps
    # separate beam columns; no cut is merged across beams.
    sheet = None
    next_zone = None
    if 'N5_SEPARACAO_VIGAS' not in dst.layers:
        dst.layers.new('N5_SEPARACAO_VIGAS', dxfattribs={'color':4})
    for beam in sorted({p['unit']['beam'] for p in prepared}, key=natural_key):
        cuts = [p for p in prepared if p['unit']['kind']=='CORTE' and beam in p['cut_beams']]
        panels = [p for p in prepared if p['unit']['beam']==beam and p['unit']['kind']=='AB']
        zone = next_zone
        next_zone = None
        first = cuts[0] if cuts else (panels[0] if panels else None)
        if zone and first and first['width'] <= right-zone[0]+.01 and first['height'] <= zone[1]-bottom+.01:
            zl, zt = zone
            if 'N5_SEPARACAO_VIGAS' not in sheet.layers:
                sheet.layers.new('N5_SEPARACAO_VIGAS', dxfattribs={'color':4})
            sheet.modelspace().add_line((zl-12.5,bottom),(zl-12.5,zt),
                           dxfattribs={'layer':'N5_SEPARACAO_VIGAS','color':4})
        else:
            sheet = None
            zl, zt = left, top
        while cuts or panels:
            if sheet is None:
                sheet = builder.sheet(beam)
                builder.sheets[-1]['show_header'] = False
                zl, zt = left, top
            cx, ch = zl, 0.
            row_cuts=[]
            # Scan all pending sections to fill the first row as much as possible.
            for c in cuts:
                if cx+c['width'] <= right+.01 and c['height'] <= zt-bottom+.01:
                    place(c,sheet,cx,zt)
                    row_cuts.append(c)
                    cx += c['width']+25
                    ch=max(ch,c['height'])
            cuts=[c for c in cuts if c not in row_cuts]
            panel_top=zt-ch-(45 if row_cuts else 0)
            x, y, rh = zl, panel_top, 0.
            placed_panels=0
            while panels:
                item=panels[0]
                if x+item['width'] > right+.01:
                    # Split only at real panel boundaries, preserving native CAD.
                    if item['window'] is None and right-x>120:
                        try:
                            pieces=paginate_ab(item['doc'],item['unit']['contract'],
                                               right-zl,first_width=right-x)
                        except ValueError:
                            pieces=[]
                        if len(pieces)>1:
                            children=[]
                            for doc,window in pieces:
                                entities=list(doc.modelspace());b=bbox.extents(entities)
                                children.append(dict(item,doc=doc,entities=entities,bbox=b,
                                    window=window,width=b.size.x,
                                    height=item['anchor_top']-b.extmin.y))
                            panels[:1]=children
                            continue
                    if x==zl:
                        break
                    x, y, rh = zl, y-rh-45, 0.
                if y-max(rh,item['height']) < bottom-.01:
                    break
                place(item,sheet,x,y)
                placed_panels+=1
                panels.pop(0)
                x+=item['width']+25
                rh=max(rh,item['height'])
            builder.sheets[-1]['title']=', '.join(builder.sheets[-1]['names'])
            if cuts or panels:
                if not row_cuts and not placed_panels and zl==left and zt==top:
                    raise ValueError(f'{beam}: unidade não cabe na moldura')
                sheet=None
            else:
                # The next beam may begin to the right of this last row only
                # when its first cut fits; otherwise it starts a new sheet.
                next_zone=(x,y) if placed_panels else (cx,zt)
    result = builder.finish(ezdxf.readfile(index_path), pages_dir,
                            index_titles=LV_INDEX_TITLES if index_titles is None else index_titles,
                            index_sha256=sha256(Path(index_path).read_bytes()).hexdigest())
    result.pop('minimum_grade_gap_cm', None)
    result.update(lateral_units=coverage, assembly_variant=assembly,
                  behavior=behavior.upper(), unit_gap_cm=25, row_gap_cm=45)
    return result
