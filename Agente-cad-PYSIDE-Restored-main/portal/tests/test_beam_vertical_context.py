import pytest


def test_end_joint_contact_is_bounded_by_measured_corridor_and_preserves_source():
    from src.core.beam_vertical_context import end_joint_footprint, incident_vertical_contract
    pair = dict(start=[70,0], end=[81,0], footprint=[[70,0],[81,0],[81,19],[70,19]])
    joint = end_joint_footprint(pair, [0,0,100,19], 19)
    assert joint == [[70,0],[100,0],[100,19],[70,19]]
    assert pair['end'] == [81,0] and pair['footprint'][1] == [81,0]
    contract = dict(base_level_m=851.64, top_level_m=852.19)
    entry = dict(beam='V1', pairs=[dict(pair, joint_footprint=joint)], section_contract=contract)
    assert incident_vertical_contract([100,9.5], 'V1', [entry]) == contract
    assert end_joint_footprint(pair, [0,0,140,19], 19) is None
    assert end_joint_footprint(pair, [0,100,100,119], 19) is None
    with pytest.raises(ValueError, match='sem seção'):
        incident_vertical_contract([110,9.5], 'V1', [entry])


def test_short_terminal_joint_does_not_collapse_both_end_faces():
    from src.core.beam_vertical_context import end_joint_footprint
    pair = dict(start=[0,80], end=[0,90], footprint=[[0,80],[0,90],[19,90],[19,80]])
    assert end_joint_footprint(pair, [0,0,19,100], 19) == [[0,80],[0,100],[19,100],[19,80]]
from src.core.beam_vertical_context import inverted_cut_evidence, inverted_levels, vertical_overlap


POINTS = [[0,0],[19,0],[39,0],[39,13],[19,13],[19,82],[0,82],[0,10],[-20,10],[-20,0]]
LINES = [dict(start=[-4,49],end=[23,53],aci=1,handle='a'),
         dict(start=[-4,53],end=[23,57],aci=1,handle='b')]


def test_crossing_uses_each_local_wall_instead_of_incident_depth():
    from src.core.beam_vertical_context import lateral_wall_contact
    owner = dict(base_level_m=851.99, top_level_m=852.70, mounting={
        'A': dict(panel_base_cm=15, panel_top_cm=71),
        'B': dict(panel_base_cm=22, panel_top_cm=71)})
    incident = dict(base_level_m=851.64, top_level_m=852.19)
    contact = lateral_wall_contact(owner, incident, 'A')
    assert contact['height_cm'] == 5
    assert contact['bottom_cm'] == 0
    assert contact['top_cm'] == 5
    assert contact['panel_height_cm'] == 56
    assert lateral_wall_contact(owner, incident, 'B') is None


def test_crossing_preserves_interior_contact_offset_and_unknown_levels():
    from src.core.beam_vertical_context import lateral_wall_contact
    owner = dict(base_level_m=850., top_level_m=851.20,
                 mounting={'A': dict(panel_base_cm=15, panel_top_cm=120)})
    contact = lateral_wall_contact(owner, dict(base_level_m=850.40, top_level_m=850.80), 'A')
    assert contact['bottom_cm'] == 25
    assert contact['top_cm'] == 65
    assert contact['height_cm'] == 40
    assert lateral_wall_contact(owner, dict(base_level_m=851.20, top_level_m=851.70), 'A') is None
    with pytest.raises(ValueError, match='confirmados'):
        lateral_wall_contact(owner, dict(top_level_m=850.80), 'A')
    with pytest.raises(ValueError, match='inválido'):
        lateral_wall_contact(owner, dict(base_level_m=850.80, top_level_m=850.40), 'A')


@pytest.mark.parametrize('levels,expected', [
    ([852.12,852.19], True), ([852.70], False), ([853.26], False),
    ([], False), ([float('nan')], False),
])
def test_cap_clearance_requires_all_incident_levels_below_cap(monkeypatch, levels, expected):
    from src.core.beam_vertical_context import clear_top_cap_interferences
    contract=dict(beam_type='inverted',form_role='top_cap',top_level_m=852.70)
    monkeypatch.setattr('src.core.lv_n3_cut_contract.build_cut_contract',lambda cut: contract)
    cut=dict(pairs=[dict(start=[0,0],end=[14,0],
                        beam_interferences=[dict(level_candidates_m=levels)])])
    result=clear_top_cap_interferences([cut])
    assert bool(result)==expected
    assert 'cap_contract' not in cut


def test_cap_continuity_requires_adjacent_same_faces_height_and_original(monkeypatch):
    from copy import deepcopy
    from src.core.beam_vertical_context import clear_top_cap_interferences
    contract=dict(beam_type='inverted',form_role='top_cap',base_level_m=851.99,top_level_m=852.70)
    def build(cut):
        if cut.get('verified'): return contract
        raise ValueError('sem laje no cruzamento')
    monkeypatch.setattr('src.core.lv_n3_cut_contract.build_cut_contract',build)
    ref=dict(verified=True,width_cm=19,beam_height_cm=71,
             section_semantics=dict(source_section_id='original'),
             pairs=[dict(a_id='a',b_id='b',start=[0,0],end=[100,0])])
    gap=dict(width_cm=19,beam_height_cm=71,section_semantics=dict(source_section_id='original'),
             pairs=[dict(a_id='a',b_id='b',start=[100,0],end=[114,0],
                         beam_interferences=[dict(level=852.19)])])
    result=clear_top_cap_interferences([gap],[ref])
    assert result[0]['cap_contract']['level_continuity_source']=='adjacent_same_ab_faces_and_height'
    for change in ('height','face','distance','original'):
        wrong=deepcopy(ref)
        if change=='height': wrong['beam_height_cm']=120
        if change=='face': wrong['pairs'][0]['b_id']='other'
        if change=='distance': wrong['pairs'][0]['end']=[98,0]
        if change=='original': wrong['section_semantics']['source_section_id']='undecoded-original'
        assert not clear_top_cap_interferences([gap],[wrong])


@pytest.mark.parametrize('reference_side', ['A', 'B'])
def test_changed_inverted_height_uses_local_dimension_slab_not_lowest_level(reference_side):
    from src.core.beam_vertical_context import attach_local_inverted_references, inverted_profile_levels
    profiles = {'A': dict(level_source='lv_cell_slabs',level=852.12,
                         slabs=[dict(name='LA',level=852.12,height_cm=13)]),
                'B': dict(level_source='lv_cell_slabs',level=852.19,
                         slabs=[dict(name='LB',level=852.19,height_cm=13)])}
    cut = dict(beam_height_cm=71,width_cm=19,profiles=profiles,
               section_semantics=dict(confirmed=True,reference_height_cm=120),
               pairs=[dict(start=[0,0],end=[0,100])])
    slabs = [dict(name='LA',points=[[-30,0],[-1,0],[-1,100],[-30,100]]),
             dict(name='LB',points=[[20,0],[40,0],[40,100],[20,100]])]
    pos = [-3,50] if reference_side == 'A' else [21,50]
    labels = [dict(text='19/71',pos=pos),dict(text='19/120',pos=[-3,60]),
              dict(text='19/71',pos=[-3,130])]
    attach_local_inverted_references([cut],labels,slabs)
    result = inverted_profile_levels(71,profiles,cut['section_semantics'])
    base = 851.99 if reference_side == 'A' else 852.06
    assert result['base_level_m'] == pytest.approx(base)
    assert result['top_level_m'] == pytest.approx(base+.71)
    assert result['level_references'][0]['side'] == reference_side
    # Two matching annotations indicating conflicting owners remain pending.
    cut['section_semantics'].pop('local_slab_reference')
    attach_local_inverted_references([cut],labels+[dict(text='19/71',pos=[21,50] if reference_side=='A' else [-3,50])],slabs)
    with pytest.raises(ValueError,match='incompatíveis'):
        inverted_profile_levels(71,profiles,cut['section_semantics'])


def test_current_round_slab_levels_replace_stale_scalars_without_changing_contours():
    from src.core.beam_vertical_context import current_section_slabs
    old = [dict(name='L',nivel=852.15,points=[[0,0],[1,0],[1,1]])]
    fresh = [dict(name='L',fields=dict(laje_nivel='852.19',laje_dim='13'),points=[[0,0],[2,0],[2,2]])]
    merged = current_section_slabs(old,fresh)
    assert merged[0]['nivel'] == 852.19
    assert merged[0]['height'] == 13
    assert merged[0]['points'] == old[0]['points']
    assert old[0]['nivel'] == 852.15
    assert current_section_slabs(old,[dict(name='L',fields={})])[0]['nivel'] is None


@pytest.mark.parametrize('rotated', [False, True])
def test_measured_inverted_symbol_requires_distinct_strokes_and_base_flange(rotated):
    transform = lambda p: [-p[1],p[0]] if rotated else p
    points = [transform(p) for p in POINTS]
    lines = [{**r,'start':transform(r['start']),'end':transform(r['end'])} for r in LINES]
    evidence = inverted_cut_evidence(points,lines,'Norte' if rotated else 'Leste',19,120)
    assert evidence['confirmed'] and evidence['height_cm']==120
    assert evidence['flanges']['left']==dict(height_cm=10,bottom_cm=0)
    assert evidence['flanges']['right']==dict(height_cm=13,bottom_cm=0)
    assert inverted_cut_evidence(points,[lines[0],lines[0]],'Norte' if rotated else 'Leste',19,120) is None
    assert inverted_cut_evidence(points,[{**r,'aci':2} for r in lines],'Norte' if rotated else 'Leste',19,120) is None


def test_regional_slabs_share_base_without_global_scaling():
    slabs=[dict(level=852.16,height_cm=10),dict(level=852.19,height_cm=13)]
    assert inverted_levels(120,slabs)==dict(base_level_m=852.06,top_level_m=853.26)
    assert inverted_levels(71,slabs)==dict(base_level_m=852.06,top_level_m=852.77)
    with pytest.raises(ValueError,match='incompatíveis'):
        inverted_levels(120,[dict(level=852.12,height_cm=13),slabs[1]])
    from src.core.lv_cut_equivalence import group_equivalent_cuts
    from src.core.lv_n3_cut_contract import CutContractError, build_cut_contract
    conflicting=dict(id='pending',kind='calculated',beam='V',width_cm=19,beam_height_cm=120,
        section_semantics=dict(confirmed=True,beam_type='inverted'),pairs=[],
        profiles={'A':dict(level=852.12,slabs=[dict(name='L1',level=852.12,height_cm=13)]),
                  'B':dict(level=852.19,slabs=[dict(name='L2',level=852.19,height_cm=13)])})
    with pytest.raises(CutContractError,match='incompatíveis'):
        build_cut_contract(conflicting)
    assert group_equivalent_cuts([conflicting])==[conflicting]


def test_vertical_contact_does_not_turn_unknown_into_clearance():
    a=dict(base_level_m=852.06,top_level_m=853.26)
    assert vertical_overlap(a,dict(base_level_m=851,top_level_m=852))==0
    assert vertical_overlap(a,dict(base_level_m=852,top_level_m=852.19))==pytest.approx(13)
    assert vertical_overlap(a,{}) is None
    for invalid in (dict(base_level_m=float('nan'),top_level_m=853),
                    dict(base_level_m=853,top_level_m=852)):
        with pytest.raises(ValueError,match='inválido'):
            vertical_overlap(a,invalid)


def test_inverted_drawings_compress_upper_tail_keep_slabs_and_true_dimensions():
    from portal.app.lv_cut_map import section_drawings
    from src.core.lv_n3_cut_contract import build_cut_contract
    from math import dist
    pair=dict(start=[0,0],end=[300,0],length_cm=300,b_id='B',a_index=1,b_index=1)
    cut=dict(id='inverted',beam='V330',kind='calculated',width_cm=19,beam_height_cm=120,
             section_semantics=dict(confirmed=True,beam_type='inverted'),pairs=[pair],
             profiles={'A':dict(level=852.16,slabs=[dict(name='L316',level=852.16,height_cm=10)]),
                       'B':dict(level=852.19,slabs=[dict(name='L317',level=852.19,height_cm=13)])})
    contract=build_cut_contract(cut)
    assert contract['form_role']=='top_cap'
    assert contract['top_level_m']==853.26
    assert contract['slabs']['A'][0]['drop_cm']==110
    assert contract['slabs']['B'][0]['drop_cm']==107
    drawings,blocked=section_drawings([cut],dict(B=dict(segments=[dict(id='B',points=[[0,19],[300,19]])])))
    assert not blocked
    shapes=[p for p in drawings[0]['primitives'] if p['kind']=='polygon']
    assert dist(shapes[0]['points'][1],shapes[0]['points'][2])==pytest.approx(50)
    assert [dist(p['points'][1],p['points'][2]) for p in shapes[1:]]==pytest.approx([10,13])
    assert any(p.get('text')=='INVERTIDA' for p in drawings[0]['primitives'])
    title=next(p for p in drawings[0]['primitives'] if p.get('role')=='section_title')
    tag=next(p for p in drawings[0]['primitives'] if p.get('role')=='beam_type_label')
    assert dist(title['points'][0],tag['points'][0])==pytest.approx(10)


def test_next_unknown_original_stops_propagation_and_local_height_survives():
    from src.core.beam_vertical_context import apply_inverted_sections
    originals=[dict(beam='V',source_cut=dict(pts=[[0,0],[19,0],[19,2],[0,2]],
                  section_semantics=dict(confirmed=True,beam_type='inverted',height_cm=120))),
               dict(beam='V',source_cut=dict(pts=[[0,100],[19,100],[19,102],[0,102]]))]
    cuts=[dict(id='x',beam='V',beam_height_cm=71,pairs=[dict(start=[0,20],end=[0,40])]),
          dict(id='y',beam='V',beam_height_cm=120,pairs=[dict(start=[0,120],end=[0,140])])]
    result=apply_inverted_sections(cuts,originals)
    assert result[0]['section_semantics']['height_cm']==71
    assert not result[1].get('section_semantics')


@pytest.mark.parametrize('reverse', [False, True])
def test_original_boundary_splits_interval_without_losing_physical_length(reverse):
    from src.core.beam_vertical_context import apply_inverted_sections
    originals=[dict(id='inverted',beam='V',source_cut=dict(pts=[[0,0],[19,0],[19,2],[0,2]],
                  section_semantics=dict(confirmed=True,beam_type='inverted',height_cm=120))),
               dict(id='unknown',beam='V',source_cut=dict(pts=[[0,100],[19,100],[19,102],[0,102]]))]
    endpoints=[[0,20],[0,140]]
    if reverse:
        endpoints.reverse()
    pair=dict(start=endpoints[0],end=endpoints[1],length_cm=120,a_id='A',b_id='B')
    cuts=[dict(id='x',beam='V',beam_height_cm=71,pairs=[pair])]
    result=apply_inverted_sections(cuts,originals)
    assert len(result)==2
    assert [r['pairs'][0]['length_cm'] for r in result]==[81,39]
    assert result[0]['section_semantics']['height_cm']==71
    assert not result[1].get('section_semantics')
    assert all(r['pairs'][0]['a_id']=='A' for r in result)
    assert cuts[0]['pairs'][0]==pair  # No modification of N1 input.


def test_conversion_enriches_ephemeral_context_without_changing_n1_fields():
    from src.core.beam_vertical_context import enrich_originals
    evidence=inverted_cut_evidence(POINTS,LINES,'Leste',19,120)
    raw=dict(pts=POINTS,section_semantics=evidence,
             ficha=dict(direction='Leste',beam_height=120,beam_bottom_dim=19,own_slab_height=13))
    converted=enrich_originals([raw],[])[0]
    assert converted['ficha']['own_slab_height']==10
    assert converted['ficha']['own_dist_top']==110
    assert raw['ficha']['own_slab_height']==13


def test_fv_cap_requires_full_coverage_and_splits_mixed_profiles(monkeypatch):
    from copy import deepcopy
    from src.core.fv_generation_contract import build_fv_generation_contract
    contract=dict(beam_type='inverted',form_role='top_cap',width_cm=19,height_cm=120,
                  base_level_m=852.06,top_level_m=853.26,section_semantics=dict(confirmed=True))
    entries=[dict(beam='V330',section_contract=contract,pairs=[dict(start=[0,0],end=[160,0])]),
             dict(beam='V330',section_contract=contract,pairs=[dict(start=[160,0],end=[311,0])])]
    source=dict(dim_text='19/120',segmentos_fundo=[dict(length=311,dim_width=19,dim_height=120,
                                                    geometry=[[0,0],[311,0],[311,19],[0,19]])])
    converted=build_fv_generation_contract('V330',source,section_context=dict(entries=entries))
    assert build_fv_generation_contract('V330',source,
        section_context=dict(entries=[],physical_entries=entries))['segments_rich'][0]['form_role']=='top_cap'
    with pytest.raises(ValueError,match='sem intervalo'):
        build_fv_generation_contract('V330',source,section_context=dict(entries=[],
            physical_entries=[dict(beam='V330',section_semantics=dict(beam_type='inverted'),
                                   pending='níveis incompatíveis')]))
    segment=converted['segments_rich'][0]
    assert segment['form_role']=='top_cap' and segment['nivel']==853.26
    assert sum(p['width'] for p in segment['panels'])==311
    assert all(p['is_liso'] for p in segment['panels'])
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'scripts'))
    from scripts.gerar_fv_dxf_stog import setup_doc, draw_viga
    document=setup_doc()
    modelspace=document.modelspace()
    draw_viga(modelspace,0,0,converted['segments_rich'],19,'V330.C')
    liso=[e for e in modelspace.query('TEXT') if e.dxf.text=='LISO']
    assert len(liso)==len(segment['panels'])
    assert not [e for e in modelspace if e.dxf.layer.startswith('SARR')]
    assert 'panels' not in source['segmentos_fundo'][0]
    with pytest.raises(ValueError,match='sem intervalo|cobre todo'):
        build_fv_generation_contract('V330',source,section_context=dict(entries=entries[:1]))
    changed=deepcopy(entries)
    changed[1]['section_contract']=deepcopy(changed[1]['section_contract'])
    changed[1]['section_contract'].update(height_cm=71,top_level_m=852.77)
    split=build_fv_generation_contract('V330',source,section_context=dict(entries=changed))['segments_rich']
    assert [s['comprimento_total_fundo'] for s in split]==[160,151]
    assert [s['altura_total'] for s in split]==[120,71]
    assert [s['nivel'] for s in split]==[853.26,852.77]
    assert all(p['is_liso'] for s in split for p in s['panels'])
    assert source['segmentos_fundo'][0]['length']==311
    distant=deepcopy(entries)
    for entry in distant:
        for pair in entry['pairs']:
            pair['start'][1]+=200
            pair['end'][1]+=200
    with pytest.raises(ValueError,match='sem intervalo'):
        build_fv_generation_contract('V330',source,section_context=dict(entries=distant))


def test_matching_pending_inversion_preserves_reason_instead_of_normal_fallback():
    from src.core.beam_vertical_context import covering_vertical_contract
    entry=dict(section_semantics=dict(beam_type='inverted',confirmed=True),
               pending='bases das lajes incompatíveis com o corte invertido',
               pairs=[dict(start=[0,0],end=[311,0])])
    with pytest.raises(ValueError,match='pendente: bases das lajes incompatíveis'):
        covering_vertical_contract([[0,0],[311,0],[311,19],[0,19]],[entry])


def test_inverted_cap_assembly_stops_at_junctions_without_changing_lateral_contacts():
    from copy import deepcopy
    from src.core.fv_generation_contract import build_fv_generation_contract
    contract = dict(beam_type='inverted', form_role='top_cap', width_cm=19, height_cm=120,
                    base_level_m=852.06, top_level_m=853.26,
                    section_semantics=dict(confirmed=True, beam_type='inverted'))
    full = dict(beam='VX', section_contract=contract,
                pairs=[dict(start=[0,0], end=[527,0])])
    junctions = [dict(beam='VX', section_contract=contract,
        pairs=[dict(start=[a,0], end=[b,0], footprint=[[a,0],[b,0],[b,19],[a,19]],
                    beam_interferences=[dict(name=name, level=852.19)])])
        for a,b,name in [(311,330,'VY'), (513,527,'VZ')]]
    entries = [full, *junctions, deepcopy(junctions[0])]
    source = dict(segmentos_fundo=[dict(length=527, dim_width=19, dim_height=120,
        geometry=[[0,0],[527,0],[527,19],[0,19]], apoio_inicial='PX', apoio_final='VZ')])
    before = deepcopy((source, entries))
    result = build_fv_generation_contract('VX', source, section_context=dict(physical_entries=entries))
    # VX has no numeric suffix, but keeps its explicit identity.
    segments = result['segments_rich']
    assert [s['comprimento_total_fundo'] for s in segments] == [311,183]
    assert [(s['texto_esq'], s['texto_dir']) for s in segments] == [('PX','VY'),('VY','VZ')]
    assert all(s['nivel'] == 853.26 and s['form_role'] == 'top_cap' for s in segments)
    assert all(p['is_liso'] for s in segments for p in s['panels'])
    assert sum(p['width'] for s in segments for p in s['panels']) == 494
    assert (source, entries) == before
    assert all(s['cap_assembly_rule'] == 'between_incident_beam_faces' for s in segments)
    assert len(result['beam_section_runs']) == 1
    assert [s['beam_section_run_index'] for s in segments] == [0,0]


def test_cap_assembly_gap_does_not_split_the_continuous_120_section():
    from copy import deepcopy
    from src.core.fv_generation_contract import build_fv_generation_contract
    c = dict(beam_type='inverted',form_role='top_cap',width_cm=19,height_cm=120,
             base_level_m=852.06,top_level_m=853.26,
             section_semantics=dict(confirmed=True))
    small = dict(c,height_cm=71,top_level_m=852.77)
    entries = [dict(beam='VX',section_contract=c,pairs=[dict(start=[0,0],end=[415,0])]),
               dict(beam='VX',section_contract=small,pairs=[dict(start=[415,0],end=[527,0])]),
               dict(beam='VX',section_contract=c,pairs=[dict(start=[311,0],end=[330,0],
                    footprint=[[311,0],[330,0],[330,19],[311,19]],
                    beam_interferences=[dict(name='VY')])])]
    source = dict(segmentos_fundo=[dict(geometry=[[0,0],[527,0],[527,19],[0,19]],
                                       dim_width=19,dim_height=120,length=527)])
    result = build_fv_generation_contract('VX',source,section_context=dict(physical_entries=entries))
    runs = result['beam_section_runs']
    assert [(r['length_cm'],r['section_contract']['height_cm']) for r in runs] == [(415,120),(112,71)]
    assert [s['beam_section_run_index'] for s in result['segments_rich']] == [0,0,1]
    assert [s['width'] for s in result['segments_rich']] == [311,85,112]


def test_inverted_cap_rejects_partial_width_junction_instead_of_rectangularizing():
    from src.core.beam_vertical_context import exclude_inverted_cap_junctions
    source = dict(geometry=[[0,0],[100,0],[100,19],[0,19]])
    entries = [dict(pairs=[dict(footprint=[[40,0],[59,0],[59,8],[40,8]],
                               beam_interferences=[dict(name='V2')])])]
    with pytest.raises(ValueError, match='parcial'):
        exclude_inverted_cap_junctions(source, entries)
    entries[0]['pairs'][0]['footprint'] = [[40,200],[59,200],[59,219],[40,219]]
    assert exclude_inverted_cap_junctions(source, entries) == [source]


def test_inverted_cap_terminal_contact_preserves_declared_junction_width():
    from src.core.beam_vertical_context import exclude_inverted_cap_junctions
    source = dict(geometry=[[0,0],[527,0],[527,19],[0,19]], apoio_final='V2')
    entries = [dict(pairs=[dict(footprint=[[513.037,.0175],[527,.0175],[527,19.0175],[513.037,19.0175]],
        beam_interferences=[dict(name='V2', width_cm=14)])])]
    spans = exclude_inverted_cap_junctions(source, entries)
    assert len(spans) == 1 and spans[0]['length'] == 513
    assert spans[0]['apoio_final'] == 'V2'
    assert source['geometry'][1][0] == 527


def test_inverted_cap_support_requires_full_solid_face_and_preserves_assembly_span():
    from copy import deepcopy
    from src.core.beam_vertical_context import exclude_inverted_cap_junctions
    source = dict(geometry=[[0,0],[527,0],[527,19],[0,19]], apoio_inicial='WRONG')
    entries = [dict(pairs=[dict(footprint=[[311,0],[330,0],[330,19],[311,19]],
                               beam_interferences=[dict(name='VY')])])]
    pillars = [dict(name='PX', classification='SEGUE',
                    points=[[-79,-.0175],[.038,-.0175],[.038,18.9825],[-79,18.9825]]),
               dict(name='NEAR', classification='SEGUE',
                    points=[[-79,30],[0,30],[0,49],[-79,49]])]
    original = deepcopy((source, entries, pillars))
    spans = exclude_inverted_cap_junctions(source, entries, pillars=pillars)
    assert spans[0]['apoio_inicial'] == 'PX'
    assert spans[0]['apoio_final'] == 'VY'
    assert spans[0]['cap_assembly_span']['length_cm'] == 311
    assert spans[1]['cap_assembly_span']['length_cm'] == 197
    assert (source, entries, pillars) == original
    pillars[0]['points'] = [[-79,0],[0,0],[0,8],[-79,8]]
    assert exclude_inverted_cap_junctions(source, entries, pillars=pillars)[0]['apoio_inicial'] == 'WRONG'


def test_short_vertical_partition_keeps_beam_axis_instead_of_width():
    from src.core.beam_vertical_context import split_inverted_soffit
    contract=dict(beam_type='inverted',form_role='top_cap',width_cm=19,height_cm=71,
                  base_level_m=851.99,top_level_m=852.70,section_semantics=dict(confirmed=True))
    entries=[dict(section_contract=contract,pairs=[dict(start=[0,0],end=[0,90])]),
             dict(section_contract=contract,pairs=[dict(start=[0,90],end=[0,104])])]
    source=dict(geometry=[[0,0],[19,0],[19,104],[0,104]],uid='short-crossing')
    parts=split_inverted_soffit(source,entries)
    assert len(parts)==1 and parts[0]['length']==104
    assert parts[0]['_vertical_contract']['top_level_m']==852.70


def test_inverted_local_slab_reference_keeps_opposite_slab_elevation():
    from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
    profiles=dict(A=dict(level=852.12,level_source='lv_cell_slabs',
                        slabs=[dict(name='L308',level=852.12,height_cm=13)]),
                  B=dict(level=852.12,level_source='lv_cell_estimado',
                        slabs=[dict(name='L317',level=852.19,height_cm=13)]))
    cut=dict(id='local',beam='V',kind='calculated',width_cm=19,beam_height_cm=71,
             profiles=profiles,section_semantics=dict(confirmed=True,beam_type='inverted'))
    c=build_cut_contract(cut)
    assert c['base_level_m']==851.99
    assert c['top_level_m']==852.70
    assert c['slabs']['A'][0]['drop_cm']==58
    assert c['slabs']['B'][0]['drop_cm']==51
    assert c['mounting']['B']['below_slab_concrete_cm']==7
    assert c['mounting']['B']['h1_cm']==49
    # Geometric contact does not turn a previously borrowed face datum into
    # a second independent reference for the beam's base.
    profiles['B'].update(level=852.19,level_source='paired_touching_slabs')
    c=build_cut_contract(cut)
    assert c['base_level_m']==851.99
    assert c['slabs']['B'][0]['drop_cm']==51
    assert [r['side'] for r in c['level_references']]==['A']
    profiles['B'].update(level=852.19,level_source='lv_cell_slabs')
    with pytest.raises(CutContractError,match='bases das lajes incompatíveis'):
        build_cut_contract(cut)
