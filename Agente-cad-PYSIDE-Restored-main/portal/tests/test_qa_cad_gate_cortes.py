from shapely.geometry import box
from shapely.ops import unary_union

from portal.app import qa_cad_gate_cortes as vc
from portal.app import qa_cad_gate_run as run


def _tee(bw=19, h=55, left=(0, 12), right=(0, 12), arm=30):
    """Viga em pé (topo em y=h), braços de laje (desnível, espessura) por lado."""
    parts = [box(0, 0, bw, h)]
    if left:
        parts.append(box(-arm, h-left[0]-left[1], 0, h-left[0]))
    if right:
        parts.append(box(bw, h-right[0]-right[1], bw+arm, h-right[0]))
    return unary_union(parts)


def _best(shape, declared):
    scored = []
    for c in vc.orientations(shape):
        errs, mapping, notes = vc._arm_errors(c, declared)
        bad = abs(c['bw']-declared['bw']) > vc.TOL_CM or (not c['broken'] and abs(c['h']-declared['h']) > vc.TOL_CM)
        scored.append((len(errs)+bad, errs, c))
    return min(scored, key=lambda s: s[0])


def _declared(a, b, bw=19, h=55):
    return dict(bw=bw, h=h, own_side='A', slabs={
        'A': [dict(name='L1', thick=a[1], drop=a[0])] if a else [],
        'B': [dict(name='L2', thick=b[1], drop=b[0])] if b else []})


def test_tee_reads_width_height_and_both_slabs():
    p = vc.profile(_tee(), 'y', -1)
    assert (p['bw'], p['h'], p['broken']) == (19, 55, False)
    assert p['arms'] == {'-': [dict(drop=0, thick=12)], '+': [dict(drop=0, thick=12)]}


def test_rotated_L_with_step_matches_declared_levels():
    from shapely import affinity
    shape = affinity.rotate(_tee(left=(7, 12), right=None), 90, origin=(0, 0))
    n, errs, c = _best(shape, _declared((7, 12), None))
    assert n == 0 and errs == [] and c['bw'] == 19


def test_slab_drawn_but_declared_absent_is_divergence():
    n, errs, _ = _best(_tee(), _declared((0, 12), None))
    assert n == 1 and '0 laje(s) declarada(s), 1 braço(s)' in errs[0]


def test_wrong_level_is_divergence():
    n, errs, _ = _best(_tee(left=(0, 12), right=(3, 10)), _declared((0, 12), (0, 10)))
    assert n == 1 and 'desnível declarado 0, desenho 3' in errs[0]


def test_schematic_thickness_is_note_when_plan_agrees():
    c = vc.profile(_tee(left=(0, 12), right=(0, 12)), 'y', -1)
    errs, _, notes = vc._arm_errors(c, _declared((0, 13), (0, 12)), plan_h=lambda n: 13 if n == 'L1' else None)
    assert errs == [] and 'vale a planta' in notes[0]
    errs, _, _ = vc._arm_errors(c, _declared((0, 13), (0, 12)), plan_h=lambda n: 14)
    assert errs and 'planta h=14' in errs[0]


def test_broken_stem_measures_bottom_slab_from_beam_bottom():
    # Viga invertida 19/120 desenhada com quebra: só 40 cm de alma, lajes no fundo.
    stem = unary_union([box(0, 0, 19, 15), box(0, 25, 19, 40)])
    shape = unary_union([stem, box(-30, 0, 0, 10), box(19, 0, 49, 13)])
    c = vc.profile(shape, 'y', -1)
    assert c['broken']
    errs, _, _ = vc._arm_errors(c, _declared((110, 10), (107, 13), h=120))
    assert errs == []


def test_vc_status_reaches_beam_and_slab_fichas(tmp_path):
    run._write(run.sidecar_path(tmp_path, '13_PAV'), {'classes': {
        'FV': {'V1': {'status': 'confere'}},
        'VC': {'V1': {'status': 'diverge', 'divergencias': ['x']}, 'L1': {'status': 'confere'}}}})
    fv = run.item_status(tmp_path, '13_PAV', 'fundo', 'V1_S1', beam_name='V1')
    assert fv['status'] == 'confere' and fv['visao_corte']['status'] == 'diverge'
    lv = run.item_status(tmp_path, '13_PAV', 'lateral_a_para', 'V1', beam_name='V1')
    assert lv == {'status': None, 'visao_corte': {'status': 'diverge', 'divergencias': ['x']}}
    assert run.item_status(tmp_path, '13_PAV', 'lajes', 'L1')['visao_corte']['status'] == 'confere'


def test_grouped_cut_takes_slab_region_from_any_pair():
    # D-87: um corte agrupa pares; a L2 rebaixada (BD1) está no segundo par.
    prof = lambda name, rid: {'B': {'slabs': [{'name': name, 'region_id': rid}]}}
    entry = {'beam': 'V1', 'section_contract': {'top_level_m': 852.19, 'slabs': {
        'A': [], 'B': [{'name': 'L2', 'height_cm': 10.0, 'drop_cm': 3.0}]}},
        'pairs': [{'profiles': prof('L9', 'slab-step:L9:BD9')}, {'profiles': prof('L2', 'slab-step:L2:BD1')}]}
    written = {('L2', 'principal'): {'h': 13.0, 'nivel': 852.19}, ('L2', 'BD1'): {'h': 10.0, 'nivel': 852.16}}
    contacts = vc.measure_calculated(entry, written, '/u', 'corte')
    assert [c['errors'] for c in contacts] == [{}]
    assert 'degrau BD1' in contacts[0]['aspect']


def test_plan_link_uses_fundo_segment_nearest_to_cut_symbol():
    # V408 14_PAV: seg 2 escreve 14/55, seg 6 escreve 19/55; o corte sobre o seg 2 vincula 14/55.
    plan = [((2982, 3395, 2056, 2070), {(14.0, 55.0)}), ((4809, 5062, 2056, 2075), {(19.0, 55.0)})]
    symbol = [(3124, 2041), (3184, 2041), (3184, 2120), (3124, 2120)]
    assert vc._plan_at(plan, symbol) == {(14.0, 55.0)}
    assert vc._plan_at([], symbol) is None


def test_original_cut_owner_follows_lv_association(monkeypatch):
    # 14_PAV: L419_3154_2078 vem rotulado V413 pelo SA, mas a ficha LV o associa à V408.
    from portal.app import corte_references
    monkeypatch.setattr(corte_references, 'preparar_segmentos', lambda state: [])
    monkeypatch.setattr(corte_references, 'associar_referencias',
                        lambda raw, refs: {'nome_sugerido': 'V408'})
    seen = []
    monkeypatch.setattr(vc, 'measure_original', lambda source, sc, beam, *a, **k: seen.append(beam) or [])
    monkeypatch.setattr(vc, 'slab_values', lambda source, slabs: {})
    monkeypatch.setattr(vc, 'plan_sections', lambda source, state: {})
    inventory = {'relative_originals': [dict(id='L419_3154_2078', beam='V413',
                                             source_cut={'uid': 'L419_3154_2078'})]}
    vc.measure_pavimento('x.dxf', {}, inventory, [])
    assert seen == ['V408']


def test_written_step_cut_uses_plan_principal_and_drawn_step(monkeypatch):
    from shapely.geometry import Polygon
    b1d = [(3659.6, 2845.7), (3595.6, 2845.7), (3595.6, 2858.7), (3629.6, 2858.7),
           (3629.6, 2855.7), (3659.6, 2855.7)]
    monkeypatch.setattr(vc, '_source_shape', lambda source, pts: (Polygon(b1d), ['B1D']))
    step = dict(uid='slab-step:L406:96B', method='flat_bottom_section_written_step', height_cm=12.,
                owner_height_cm=15., level_m=855.22, owner_level_m=855.25, bottom_m=855.10, owner_bottom_m=855.10)
    written = {('L406', 'principal'): {'h': 15.}}
    got = vc.measure_slab_step('x.dxf', {'name': 'L406'}, step, {'points': b1d}, '/u', written)
    assert got['errors'] == {} and 'vale o número' in got['notes'][0]
    step['method'] = 'direct_scoped_cad'
    assert vc.measure_slab_step('x.dxf', {'name': 'L406'}, step, {'points': b1d}, '/u', written)['errors']
