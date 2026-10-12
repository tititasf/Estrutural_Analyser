"""Adaptador N1 de Visão Corte; reutiliza estilos, cotas e anatomia SCR do motor LV.

O gerador STOG certificado não é alterado. Nenhuma entrada N2/N4 é consultada.
"""
from __future__ import annotations
import importlib.util
from functools import lru_cache
from pathlib import Path
import sys


@lru_cache(maxsize=1)
def motor():
    path=Path(__file__).resolve().parents[1]/'gerar_lv_dxf_stog.py'
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('lv_n3_cut_shared_motor',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FITTING_NAMES=('PAR_ESQ','PAR_FUNDO_ESQ','PAR_FUNDO_DIR','par_int_esq','par_int_dir')
FITTING_SCALE=.5  # original COTAX2 has DIMLFAC=0.5; N3 geometry is 1:1 cm


def load_original_fittings(doc):
    """Load LV section hardware from the robot mold, including nested blocks.

    Geometry is an independent style asset, never a source of N1 dimensions.
    Do not use the shared motor's two-line cross placeholders for these blocks.
    """
    import ezdxf
    from ezdxf.addons import Importer
    source=ezdxf.readfile(Path(__file__).parent/'assets'/'lv_cut_fittings.dxf')
    for name in FITTING_NAMES:
        if name not in source.blocks:
            raise ValueError(f'Bloco original LV ausente: {name}')
        if name in doc.blocks:
            doc.blocks.delete_block(name,safe=False)
    importer=Importer(source,doc)
    importer.import_blocks(FITTING_NAMES)
    importer.finalize()


def insert_original_fitting(space,name,x,y):
    """Insert original LV hardware at a physical-centimeter anchor point."""
    if name not in FITTING_NAMES:
        raise ValueError(f'Ferragem fora do escopo Visão Corte LV: {name}')
    return space.add_blockref(name,(x,y),dxfattribs={
        'layer':'BARRA_ANCORAGEM','xscale':FITTING_SCALE,
        'yscale':FITTING_SCALE,'zscale':FITTING_SCALE})


def generate(contract, path, mode='NOVA', behavior='PARA'):
    """Concreto em escala 1:1, lajes com seu desnível e montagem SCR paramétrica."""
    if str(mode).upper() == 'INI':
        from src.core.ini_design import draw_cut
        doc=draw_cut(contract,behavior)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        doc.saveas(path)
        return doc
    if str(mode).upper() == 'MOLDE_1':
        from src.core.lv_formascia_design import draw_cut
        from scripts.drawing_mode_config import apply_config
        from src.core.lv_formascia_design import normalize_resources
        doc = draw_cut(contract)
        apply_config(doc, mode, 'LV', behavior)
        normalize_resources(doc)
        doc.saveas(path)
        return doc
    if str(mode).upper() == 'NOVA':
        from src.core.lv_nova_design import draw_cut
        from scripts.drawing_mode_config import apply_config
        doc = draw_cut(contract)
        apply_config(doc, mode, 'LV', behavior)
        doc.saveas(path)
        return doc
    from shapely.geometry import box
    from shapely.ops import unary_union
    from src.core.vigas_drawing_config import normalize_lv_assembly
    assembly=normalize_lv_assembly(contract.get('assembly_variant','sarrafeadas'))
    m=motor()
    from scripts.drawing_semantics import LayoutProxy
    doc=m.setup_doc(); space=LayoutProxy(doc.modelspace(),'LV')
    load_original_fittings(doc)
    # Acabamento da rodada N4 AQ: linhas ciano, números vermelhos,
    # sarrafos em verde claro, compensado violeta e concreto cinza.
    for name,color in [('SARR_3.5x7',81),('Madeira',126),('Painéis',200),('CONCRETO',251)]:
        if name not in doc.layers: doc.layers.add(name,color=color)
        else: doc.layers.get(name).dxf.color=color
    b,h=contract['width_cm'],contract['height_cm']
    inverted = contract.get('beam_type') == 'inverted' and contract.get('form_role') == 'top_cap'
    left,right=-b/2,b/2
    rules=contract['rules']; allowance=rules['face_allowance_cm']
    panel,wood,cap=rules['panel_cm'],rules['wood_cm'],rules['cap_cm']
    # Corte representativo: comprimento da mesa não é cota nem dimensão executiva.
    reach=max(35.,b)
    concrete=[box(left,0,right,h)]

    def rect(x1,y1,x2,y2,layer,hatch=False):
        if x2<=x1 or y2<=y1: return
        points=[(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
        space.add_lwpolyline(points,close=True,dxfattribs={'layer':layer})
        if hatch and mode!='INI':
            entity=space.add_hatch(dxfattribs={'layer':'Hachura'})
            entity.set_pattern_fill('ANSI31',scale=.5)
            entity.paths.add_polyline_path(points,is_closed=True)

    def dim_h(x1,x2,y,label,extension):
        before=set(e.dxf.handle for e in space)
        m.add_plain_dim_h(space,x1,x2,y,label,extension_to_y=extension)
        for entity in space:
            if entity.dxf.handle not in before:
                entity.dxf.color=1 if entity.dxftype()=='TEXT' else 4
                if entity.dxftype()=='LINE' and abs(entity.dxf.end.x-entity.dxf.start.x)>0 and abs(entity.dxf.end.y-entity.dxf.start.y)>0:
                    entity.dxf.color=241
                if entity.dxftype()=='TEXT': entity.dxf.height=3.5

    def dim_v(x,y1,y2,label,extension):
        before=set(e.dxf.handle for e in space)
        m.add_plain_dim_v(space,x,y1,y2,label,extension_from_x=extension)
        for entity in space:
            if entity.dxf.handle not in before:
                entity.dxf.color=1 if entity.dxftype()=='TEXT' else 4
                if entity.dxftype()=='LINE' and abs(entity.dxf.end.x-entity.dxf.start.x)>0 and abs(entity.dxf.end.y-entity.dxf.start.y)>0:
                    entity.dxf.color=241
                if entity.dxftype()=='TEXT': entity.dxf.height=3.5

    body_tops=[]
    for side,x,direction in [('A',left,-1),('B',right,1)]:
        slabs=contract['slabs'][side]
        slab=slabs[0] if slabs else None
        profile=contract['mounting'][side]
        top=profile['panel_top_cm']; base=profile['panel_base_cm']
        body_tops.append(top)
        px1,px2=(x-panel,x) if direction<0 else (x,x+panel)
        # Perfil lateral: sarrafo 2.2×7 visto de lado, seguido do montante
        # 3.5×7; não uma placa maciça de madeira preenchida com hachura.
        depth,post_width=2.2,7.
        wx1,wx2=(px1-depth,px1) if direction<0 else (px2,px2+depth)
        rect(px1,base,px2,top,'Painéis')
        post1,post2=(wx1-post_width,wx1) if direction<0 else (wx2,wx2+post_width)
        rect(post1,base if inverted else -allowance-2*wood,post2,top-3,'SARR_3.5x7')
        # Use the lateral N3's sarrafo rule, without the two extra edge
        # pieces formerly synthesized only in this perspective.
        _,batt_height,positions=m._get_sarrafo_positions(profile['h1_cm'])
        for position in positions if assembly=='sarrafeadas' else ():
            yc=position+base
            if yc-batt_height/2>=base and yc+batt_height/2<=top:
                rect(wx1,yc-batt_height/2,wx2,yc+batt_height/2,'Madeira')
        if assembly=='gradeadas':
            # The section of a grade has two upright chords and a top chord;
            # it is not the horizontal batten stack of the other assembly.
            gx1,gx2=(wx1-3.5,wx1) if direction<0 else (wx2,wx2+3.5)
            rect(gx1,base,gx2,top-2.2,'SARR_3.5x7')
            rect(wx1,top-2.2,wx2,top,'SARR_2.2x7',hatch=True)
        dim_v(x+direction*(reach+22),base,top,f'{top-base:g}',wx1 if direction<0 else wx2)
        m.add_text(space,(wx1+wx2)/2, max(0,top*.28),'a' if side=='A' else 'b',4.8,'detalhes',halign=1,color=4)
        m.add_text(space,x+direction*reach/2,h+17,'Lado '+side,3.5,'Texto Seção',halign=1)
        if slab:
            slab_top=h-slab['drop_cm']; slab_bottom=slab_top-slab['height_cm']
            sx1,sx2=(x-reach,x) if direction<0 else (x,x+reach)
            concrete.append(box(sx1,slab_bottom,sx2,slab_top))
            # Fundo da laje acompanha a posição real, sem flange genérico h-16.
            deck1,deck2=(sx1,x) if direction<0 else (x,sx2)
            rect(deck1,slab_bottom-panel,deck2,slab_bottom,'Painéis')
            dim_v(x+direction*(reach+8),slab_bottom,slab_top,f'{slab["height_cm"]:g}',x+direction*reach)
            if slab['drop_cm']>.5 and not profile['lower_slab'] and not inverted:
                rect(px1,slab_top,px2,h+2,'Painéis')
                dim_v(x+direction*(reach+8),slab_top,h,f'{slab["drop_cm"]:g}',x)
            names=', '.join(str(s['name']) for s in slabs)
            m.add_text(space,x+direction*reach/2,slab_top+8,names,3.5,'Texto Seção',halign=1)
    geometry=unary_union(concrete)
    space.add_lwpolyline(list(geometry.exterior.coords)[:-1],close=True,dxfattribs={'layer':'CONCRETO','lineweight':35})
    if inverted:
        rect(left,h,right,h+panel,'Painéis')
        m.add_text(space,0,h+panel+5,'LISO',3.5,'Texto Seção',halign=1)
        m.add_text(space,0,h+22,'VIGA INVERTIDA',3.5,'Texto Seção',halign=1)
    else:
        rect(left,-allowance-panel,right,-allowance,'Painéis')
        support_extent=panel+2.2+7.
        rect(left-support_extent,-allowance-15,right+support_extent,-allowance,'SARR_3.5x7')
    # Original LV generator ef43f8e01, _gerar_secao_corte: either lower slab
    # suppresses the whole fixing assembly. H1 on BOTH sides must exceed
    # 40/90 cm (strictly) for the axes 25/75 cm above the H1 base.
    bottom_y=-allowance-panel-3.7
    if not inverted and not any(p['lower_slab'] for p in contract['mounting'].values()):
        center_a=left-9.; center_b=right+9.
        bolt_left=center_a+.9; bolt_right=center_b-.9
        rect(bolt_left,bottom_y-.5,bolt_right,bottom_y+.5,'BARRA_ANCORAGEM')
        rect(center_b+9.15,bottom_y-.5,center_b+21.15,bottom_y+.5,'BARRA_ANCORAGEM')
        insert_original_fitting(space,'PAR_FUNDO_ESQ',bolt_left,bottom_y)
        insert_original_fitting(space,'PAR_FUNDO_DIR',bolt_right,bottom_y)
        for threshold,offset in ((40.,25.),(90.,75.)):
            if not all(p['h1_cm']>threshold for p in contract['mounting'].values()):
                continue
            y=-allowance+offset
            # Legacy's inner plate is beam width minus 4 cm, shifted 1 cm left.
            rect(left+1,y-.5,right-3,y+1.5,'BARRA_ANCORAGEM')
            insert_original_fitting(space,'par_int_esq',left+1,y)
            insert_original_fitting(space,'par_int_dir',right-3,y)
            x1=center_a-18.; x2=center_b+5.
            rect(x1,y-.5,x2,y+.5,'BARRA_ANCORAGEM')
            rect(x2,y-3,x2+1.2,y+3,'BARRA_ANCORAGEM')
            insert_original_fitting(space,'PAR_ESQ',x1+13,y)
            # Two supporting battens around each central anchor, as in SCR.
            for x1,x2 in ((left-14,left-4),(right+4,right+14)):
                for delta in (-3.1,.9):
                    rect(x1,y+delta,x2,y+delta+2.2,'SARR_3.5x7')
            dim_v(right+reach+28,-allowance if offset==25 else -allowance+25,
                  y,'25' if offset==25 else '50',center_b+5)
    cap_y = h+panel/2 if inverted else -allowance-2
    m.add_text(space,0,cap_y,'c',4.8,'detalhes',halign=1,color=4)
    dim_h(left,right,-allowance-9,f'{b:g}',0 if inverted else -allowance)
    # Altura estrutural junto ao núcleo e alturas executivas fora das mesas.
    dim_v(right+reach+38,0,h,f'{h:g}',right)
    dim_v(left-reach-38,0 if inverted else -allowance,h,
          f'{h if inverted else h+allowance:g}',left-panel)
    m.add_text(space,0,h+34,f'{contract["beam"]} ({h:g}x{b:g})',6,'Texto Seção',halign=1)
    m.restack_lv_draw_order(space)
    doc.header['$INSUNITS']=5  # centímetros; não escala o desenho
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    from scripts.drawing_mode_config import apply_config
    apply_config(doc,mode,'LV',behavior)
    doc.saveas(path)
    return doc


def generate_local_sections(sides, path, mode='NOVA', behavior='PARA'):
    """Render each local N1 section without combining unrelated A/B maxima.

    This is the section adapter used by the isolated headless LV preview.
    Lateral panel geometry remains the responsibility of the STOG generator.
    """
    import json
    import tempfile
    from ezdxf import bbox
    from ezdxf.addons import Importer
    from ezdxf.math import Matrix44

    contracts = {}
    for side in ('A', 'B'):
        for segment in (sides.get(side) or {}).get('structural_segments') or []:
            sections = segment.get('section_contracts') or [segment.get('section_contract')]
            for contract in sections:
                if not contract:
                    raise ValueError('Seção local ausente no segmento lateral')
                contract=dict(contract,assembly_variant=(sides.get(side) or {}).get('assembly_variant','sarrafeadas'))
                # Equal shapes at different levels retain their own absolute datum.
                fields = ('beam', 'beam_type', 'form_role', 'width_cm', 'height_cm',
                          'slabs', 'mounting', 'rules', 'base_level_m', 'top_level_m','assembly_variant')
                key = json.dumps({k: contract.get(k) for k in fields}, sort_keys=True)
                contracts.setdefault(key, contract)
    if not contracts:
        raise ValueError('Nenhuma seção local confirmada para o corte N3')
    doc = motor().setup_doc()
    units = []
    unit_dir = Path(path).with_suffix('.units')
    if mode in ('NOVA', 'MOLDE_1'):
        unit_dir.mkdir(parents=True, exist_ok=True)
    y = 0.
    with tempfile.TemporaryDirectory(prefix='lv-local-sections-') as directory:
        for index, contract in enumerate(contracts.values(), 1):
            source = generate(contract, Path(directory)/f'{index}.dxf', mode, behavior)
            if mode in ('NOVA', 'MOLDE_1'):
                from hashlib import sha256
                unit_path = unit_dir / f'CORTE_{index:03d}.dxf'
                source.saveas(unit_path)
                units.append(dict(file=unit_path.name, kind='CORTE', beam=contract['beam'],
                                  contract=contract, sha256=sha256(unit_path.read_bytes()).hexdigest()))
            bounds = bbox.extents(source.modelspace())
            if not bounds.has_data:
                raise ValueError('Seção N3 sem geometria')
            transform = Matrix44.translate(-bounds.extmin.x, y-bounds.extmax.y, 0)
            if mode in ('NOVA', 'MOLDE_1'):
                from ezdxf.xref import load_modelspace
                existing = {e.dxf.handle for e in doc.modelspace()}
                load_modelspace(source, doc)
                for entity in doc.modelspace():
                    if entity.dxf.handle not in existing:
                        entity.transform(transform)
            else:
                importer = Importer(source, doc)
                entities = list(source.modelspace())
                for entity in entities:
                    entity.transform(transform)
                importer.import_entities(entities)
                importer.finalize()
            y -= bounds.size.y + 45.
    doc.header['$INSUNITS'] = 5
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)
    if mode in ('NOVA', 'MOLDE_1'):
        (unit_dir / 'manifest.json').write_text(json.dumps(dict(mode=mode, behavior=behavior,
            assembly_variant=next(iter(contracts.values()))['assembly_variant'], units=units),
            ensure_ascii=False, indent=2), encoding='utf8')
    return list(contracts.values())


def generate_local_panels(sides, path, side, mode='NOVA', behavior='PARA'):
    """Pass explicit local heights to the certified panel drawing primitive.

    The legacy whole-face route interprets short sections as slab frames and
    substitutes the largest height. N1 confirmed local mounting is authoritative;
    Each confirmed station retains its own drawing unit without deleting stations.
    """
    if str(mode).upper() == 'MOLDE_1':
        from src.core.lv_formascia_sa_adapter import generate_ab
        source = dict(sides[side], side=side)
        return generate_ab(source, path, behavior, mode='MOLDE_1')
    if str(mode).upper() == 'INI':
        from src.core.lv_ini_sa_adapter import generate_ab
        source = dict(sides[side], side=side)
        return generate_ab(source,path,behavior)
    if str(mode).upper() == 'NOVA':
        from src.core.lv_nova_sa_adapter import generate_ab
        source = dict(sides[side], side=side)
        return generate_ab(source, path, behavior)
    from copy import deepcopy
    from scripts.drawing_semantics import LayoutProxy
    from scripts.drawing_mode_config import apply_config
    contract = sides[side]
    if contract.get('vertical_pending') or not contract.get('panels'):
        raise ValueError('Lateral N3 sem montagem local confirmada')
    groups = []
    for panel in contract['panels']:
        height = float(panel['height1'])
        if height <= 0 or float(panel['height2']) != height:
            raise ValueError('Painel local sem altura única confirmada')
        # Each confirmed station is a body panel. Joining narrow stations to
        # wide bays activates legacy N2 slab-frame heuristics in draw_lv_face.
        drawing_panel = deepcopy(panel)
        # Robot height2 is an additional band, whereas the SA contract stores
        # equal end heights. A uniform wall has one band in the robot schema.
        drawing_panel['height2'] = 0.
        drawing_panel['grade_h2']=0.
        body=float(panel.get('body_height_cm',height))
        drawing_panel['height1']=body
        segment=panel.get('structural_segment_index',panel.get('segment_index'))
        if segment is not None and groups and groups[-1]['segment']==segment and groups[-1]['height']==height and groups[-1]['body']==body:
            groups[-1]['panels'].append(drawing_panel)
        else:
            groups.append({'height': height, 'body':body,'segment':segment,'panels': [drawing_panel]})
    m = motor()
    doc = m.setup_doc()
    space = LayoutProxy(doc.modelspace(), 'LV')
    x = 0.
    for index, group in enumerate(groups, 1):
        previous_handles={e.dxf.handle for e in doc.modelspace()}
        holes = []
        offset = 0.
        for panel in group['panels']:
            for raw in panel.get('holes') or []:
                hole = dict(raw)
                hole.setdefault('active', True)
                hole.update(panel_offset=offset, panel_width=float(panel['width']))
                holes.append(hole)
            offset += float(panel['width'])
        label = (f'{contract["beam_name"]}.{side} S{group["segment"]}' if group['segment'] is not None
                 else f'{contract["beam_name"]}.{side}#{index}')
        m.plano_cotas_abrir(label)
        m.draw_lv_face(space, x, -group['height'], group['panels'],
                            group['body'], label,
                            holes=holes, pillar_left={'active': False},
                            pillar_right={'active': False}, laje_sup=0., laje_inf=0.,
                            fallback_panel_ids=False, nom_height=8.,
                            sarrafo_vertical_esquerdo=True,
                            sarrafo_vertical_direito=True)
        band=group['height']-group['body']
        if band>.01:
            offset=x
            for panel in group['panels']:
                width=panel['width']
                points=[(offset,-band),(offset+width,-band),(offset+width,0),(offset,0)]
                space.add_lwpolyline(points,close=True,dxfattribs={'layer':'Painéis'})
                if mode!='INI':
                    hatch=space.add_hatch(dxfattribs={'layer':'Hachura','color':214})
                    hatch.set_pattern_fill('AR-CONC',scale=.015)
                    hatch.paths.add_polyline_path(points,is_closed=True)
                offset+=width
            m.add_plain_dim_v(space,offset+40,-group['height'],0,f"{group['height']:g}",extension_from_x=offset)
            m.add_plain_dim_v(space,offset+25,-band,0,f'{band:g}',extension_from_x=offset)
        if mode == 'NOVA':
            for entity in doc.modelspace().query('TEXT'):
                if entity.dxf.handle in previous_handles:
                    continue
                if entity.dxf.text == label:
                    entity.set_placement((x+3,9))
                    entity.dxf.height=6.5
                elif entity.dxf.layer in ('5','Cota Seção (2x)'):
                    entity.dxf.height=3.5
                    if entity.dxf.layer=='5':
                        entity.dxf.color=7
            for dim in doc.modelspace().query('DIMENSION'):
                if dim.dxf.handle in previous_handles:
                    continue
                # Robot styles use a 2x presentation. The adapter draws in cm
                # at 1:1 and must halve typography without changing geometry.
                if dim.dxf.dimstyle != 'PAINEL':
                    continue
                if abs(dim.dxf.defpoint2.y-dim.dxf.defpoint3.y)<.001:
                    dim.dxf.defpoint=(dim.dxf.defpoint.x,-group['height']-15,0)
                overrides=dim.override()
                overrides.update({'dimtxt':3.5,'dimasz':1.5,'dimgap':1.,
                                  'dimclrd':4,'dimclre':4,'dimclrt':1})
                overrides.render()
        m.plano_cotas_despejar(m.plano_cotas_fechar(), label)
        x += sum(p['width'] for p in group['panels']) + 100.
    seen_dimensions = set()
    for entity in list(doc.modelspace().query('DIMENSION')):
        key = (entity.dxf.dimtype, tuple(entity.dxf.defpoint),
               tuple(entity.dxf.get('defpoint2', (0., 0., 0.))),
               tuple(entity.dxf.get('defpoint3', (0., 0., 0.))),
               round(float(entity.get_measurement()), 6))
        if key in seen_dimensions:
            doc.modelspace().delete_entity(entity)
        else:
            seen_dimensions.add(key)
    m.restack_lv_draw_order(space)
    apply_config(doc, mode, 'LV', behavior)
    doc.header['$INSUNITS'] = 5
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)
    return groups
