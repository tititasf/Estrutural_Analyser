"""Preferências do pavimento aplicadas somente a cópias dos contratos N3."""
from copy import deepcopy
from .lv_cut_inventory import number

LV_ASSEMBLIES = ('gradeadas', 'sarrafeadas')


def normalize_lv_assembly(value):
    if value not in LV_ASSEMBLIES:
        raise ValueError('Laterais: escolha gradeadas ou sarrafeadas')
    return value


def lv_variants(contract, config=None):
    """Two independent fabrication contracts, both derived from the same N1."""
    config = normalize_config(config)
    return {kind: apply_lv_config(contract, {**config,
            'comportamento_laterais_vigas': kind}) for kind in LV_ASSEMBLIES}


def prepare_lv_sources(sides, *, mode=None):
    """Recover local fabrication profiles from physically overlapping SA faces.

    Segment indices are local to a face and must never pair A1 with B1 by name.
    Ambiguous profiles remain pending rather than combining unrelated maxima.
    """
    import math
    import json
    from .lv_n3_cut_contract import build_cut_contract
    result = deepcopy(sides)
    partitioned = False
    for side in ('A', 'B'):
        for segment in result.get(side, {}).get('structural_segments', []):
            if segment.get('section_contract'):
                continue
            cell = segment.get('lv_cell') or {}
            points = segment.get('points') or []
            if len(points) != 2 or number(cell.get('depth')) is None:
                continue
            a, end = points
            length = math.dist(a, end)
            if not length:
                continue
            u = [(end[i]-a[i])/length for i in (0, 1)]
            width = number(result[side].get('total_width'))
            candidates = {}
            local_sections = {}
            spans = []
            other = 'B' if side == 'A' else 'A'
            for peer in sides.get(other, {}).get('structural_segments', []):
                pp = peer.get('points') or []
                pc = peer.get('lv_cell') or {}
                if len(pp) != 2 or number(pc.get('depth')) != number(cell.get('depth')):
                    continue
                projections = [sum((p[i]-a[i])*u[i] for i in (0, 1)) for p in pp]
                offsets = [(p[0]-a[0])*(-u[1])+(p[1]-a[1])*u[0] for p in pp]
                if max(abs(o) for o in offsets) > (width or 0)+.5 or min(abs(o) for o in offsets) < .5:
                    continue
                if abs(offsets[0]-offsets[1]) > .5 or min(length,max(projections))-max(0,min(projections)) <= .5:
                    continue
                profiles = {}
                for face, source in ((side, cell), (other, pc)):
                    profiles[face] = {'level':number(source.get('level')), 'level_source':'lv_cell_slabs',
                        'slabs':[{'name':s.get('name'), 'level':number(s.get('level')),
                                  'height_cm':number(s.get('height'))} for s in source.get('slabs',[])]}
                section = {'kind':'calculated','id':str(segment.get('segment_index')),
                    'beam':result[side]['beam_name'],'width_cm':width,
                    'beam_height_cm':number(cell['depth']),'profiles':profiles,'pairs':[]}
                evidence = result[side].get('relative_originals') or []
                if evidence:
                    from .lv_cut_datum import apply_original_datums
                    own = [e for e in evidence if e.get('beam') == section['beam']]
                    section = apply_original_datums([section], own, [],
                        regional_originals=evidence)[0]
                cut = build_cut_contract(section,
                    allow_multiple_slabs=mode in ('NOVA','MOLDE_1','INI'))
                key = json.dumps({'mounting':cut['mounting'][side], 'datum':cut.get('top_level_m')},sort_keys=True)
                candidates[key] = cut
                local_sections[json.dumps(cut, sort_keys=True)] = cut
                spans.append((max(0., min(projections)), min(length, max(projections)), key, cut))
            if len(candidates) > 1:
                if mode not in ('NOVA','MOLDE_1','INI'):
                    raise ValueError('Segmento atravessa perfis de montagem distintos; subdividir no SA')
                segment['section_spans'] = _confirmed_profile_spans(length, spans)
                continue
            if candidates:
                segment['section_contract'] = next(iter(candidates.values()))
                segment['section_contracts'] = list(local_sections.values())
        if any(s.get('section_spans') for s in result.get(side, {}).get('structural_segments', [])):
            _partition_profile_panels(result[side])
            partitioned = True
        sections = {s.get('physical_segment_index', s.get('segment_index')):s.get('section_contract')
                    for s in result.get(side,{}).get('structural_segments',[]) if s.get('segment_index') is not None}
        for panel in result.get(side,{}).get('panels',[]):
            cut = sections.get(panel.get('physical_segment_index',
                                         panel.get('structural_segment_index',panel.get('segment_index'))))
            if cut:
                panel['section_contract'] = cut
                if cut.get('beam_type') != 'inverted':
                    panel['height1'] = panel['height2'] = cut['height_cm']+4.
    # The production headless records a preparation failure on both faces.
    # Clear only that exact historical cause, after measured partition succeeds;
    # missing levels, inverted profiles and all other pending reasons survive.
    if partitioned:
        for contract in result.values():
            if contract.get('vertical_pending') == 'Segmento atravessa perfis de montagem distintos; subdividir no SA':
                contract['vertical_pending'] = ''
    return result


def _confirmed_profile_spans(length, spans):
    """Partition only fully measured coverage; never extrapolate a local profile."""
    bounds = sorted({0., length, *[v for a,b,_,_ in spans for v in (a,b)]})
    pieces = []
    for a,b in zip(bounds,bounds[1:]):
        if b-a < .001:
            continue
        hits = {key:cut for lo,hi,key,cut in spans if lo <= (a+b)/2 <= hi}
        if len(hits) != 1:
            raise ValueError('Partição de montagem sem cobertura física única do SA')
        key,cut = next(iter(hits.items()))
        if pieces and pieces[-1]['key'] == key:
            pieces[-1]['end_cm'] = b
        else:
            pieces.append(dict(start_cm=a,end_cm=b,key=key,section_contract=cut))
    return pieces


def _partition_profile_panels(contract):
    """Split derived physical pieces and clip existing holes in their own frame."""
    import math
    structural = contract['structural_segments']
    panels = contract.get('panels', [])
    new_structural, new_panels = [], []
    for position, segment in enumerate(structural):
        identity = segment.get('physical_segment_index', segment['segment_index'])
        owned = [p for p in panels if p.get('physical_segment_index',
                    p.get('structural_segment_index',p.get('segment_index'))) == identity]
        spans = segment.get('section_spans')
        if not spans:
            physical = len(new_structural)+1
            new_structural.append(dict(segment, physical_segment_index=physical))
            new_panels.extend(dict(p, physical_segment_index=physical) for p in owned)
            continue
        if not owned:
            raise ValueError('Partição de montagem sem painéis executivos do SA')
        points = segment['points']; length = math.dist(*points)
        axis = [(points[1][i]-points[0][i])/length for i in (0,1)]
        start = float(contract.get('start_adjustment') or 0) if position == 0 else 0.
        end = float(contract.get('end_adjustment') or 0) if position == len(structural)-1 else 0.
        expected = length+start+end
        if abs(sum(p['width'] for p in owned)-expected) > .01:
            raise ValueError('Partição de montagem diverge do comprimento executivo do SA')
        for index, span in enumerate(spans):
            lo,hi = span['start_cm'],span['end_cm']
            executable_lo = 0. if index == 0 else lo+start
            executable_hi = expected if index == len(spans)-1 else hi+start
            physical = len(new_structural)+1
            piece = deepcopy(segment)
            piece.pop('section_spans',None)
            piece.update(physical_segment_index=physical, width=hi-lo,
                         points=[[points[0][i]+axis[i]*t for i in (0,1)] for t in (lo,hi)],
                         opening_source_points=segment.get('opening_source_points') or points,
                         section_contract=span['section_contract'])
            new_structural.append(piece)
            offset = 0.
            for panel in owned:
                a,b = max(offset,executable_lo),min(offset+panel['width'],executable_hi)
                if b-a > .001:
                    sliced = deepcopy(panel)
                    sliced.update(width=b-a,physical_segment_index=physical,points=piece['points'],
                                  section_contract=span['section_contract'])
                    holes = []
                    for hole in panel.get('holes') or []:
                        corner = str(hole.get('corner') or 'TL').upper()
                        hole_width = float(hole.get('width') or 0)
                        left = offset+(0. if corner.endswith('L') else panel['width']-hole_width)
                        h0,h1 = max(a,left),min(b,left+hole_width)
                        if h1-h0 <= .001:
                            continue
                        # Original holes touch a panel edge. Clipping preserves
                        # that corner convention and the measured vertical offset.
                        if h0 > a+.001 and h1 < b-.001:
                            raise ValueError('Partição criou abertura sem esquina executiva')
                        holes.append(dict(hole,width=h1-h0,
                                          corner=corner[0]+('L' if h0 <= a+.001 else 'R')))
                    sliced['holes'] = holes
                    new_panels.append(sliced)
                offset += panel['width']
    contract.update(structural_segments=new_structural,panels=new_panels,
                    structural_segment_count=len(new_structural),segment_count=len(new_panels),
                    total_length=sum(p['width'] for p in new_panels))


def normalize_config(config=None):
    config = config or {}
    result = {
        'comportamento_laterais_vigas': config.get('comportamento_laterais_vigas', 'sarrafeadas'),
        'fundos_vigas_possui_garfos': config.get('fundos_vigas_possui_garfos', 'nao'),
    }
    if result['comportamento_laterais_vigas'] not in {'gradeadas', 'sarrafeadas'}:
        raise ValueError('Laterais: escolha gradeadas ou sarrafeadas')
    if result['fundos_vigas_possui_garfos'] not in {'sim', 'nao'}:
        raise ValueError('Garfos: escolha sim ou nao')
    return result


def apply_lv_config(contract, config=None):
    result = deepcopy(contract)
    config = normalize_config(config)
    result['vigas_config'] = config
    result['assembly_variant'] = config['comportamento_laterais_vigas']
    grade = config['comportamento_laterais_vigas'] == 'gradeadas'
    segments={s.get('segment_index'):s for s in result.get('structural_segments',[])}
    for panel in result.get('panels', []):
        segment=segments.get(panel.get('structural_segment_index',panel.get('segment_index'))) or {}
        cell=segment.get('lv_cell') or {}
        # Older contracts copied the first section height to every segment.
        # Recover the interpreted local depth, without consulting N4 dimensions.
        if not panel.get('section_contract') and cell.get('depth'):
            height=float(cell['depth'])+4.
            if panel.get('height1')==panel.get('height2')==contract.get('total_height'):
                panel['height1']=panel['height2']=height
        height=float(panel.get('height1') or 0)
        profile=(panel.get('section_contract') or {}).get('mounting',{}).get(result.get('side'),{})
        body=height
        if profile:
            body=float(profile['h1_cm'])
        elif cell.get('slabs'):
            bodies=[]
            for slab in cell['slabs']:
                if slab.get('height') is None or slab.get('level') is None or cell.get('level') is None:
                    continue
                level, slab_level, thick = number(cell['level']), number(slab['level']), number(slab['height'])
                if None in (level, slab_level, thick):
                    raise ValueError('Medida da laje ausente no SA')
                drop=max(0.,(level-slab_level)*100.)
                bodies.append(height-drop-thick-2.)
            if bodies and max(bodies)-min(bodies)<.1:
                body=min(bodies)
            elif bodies:
                raise ValueError('Perfis de lajes distintos no mesmo segmento: revisar o SA antes do N3')
        body=max(0.,min(body,height))
        panel['body_height_cm']=body
        panel['top_band_cm']=height-body
        panel['panel_type'] = 'Grade' if grade else 'Sarrafeado'
        for index in (1, 2):
            panel[f'grade_h{index}'] = body if grade else 0.0
    return result


def apply_fv_config(contract, config=None):
    result = deepcopy(contract)
    config = normalize_config(config)
    result['vigas_config'] = config
    result['possui_garfos'] = config['fundos_vigas_possui_garfos'] == 'sim'
    # A distribuição geométrica depende da regra do dono; não inventar garfos.
    return result


def require_supported_generation(config, sections=None):
    config = normalize_config(config)
    if config['fundos_vigas_possui_garfos'] == 'sim' and (not sections or 'fundos_viga' in sections):
        raise ValueError('A regra de desenho dos garfos ainda precisa ser definida. A opção Sim está salva; o N3 de fundos com garfos ainda não pode ser gerado.')
