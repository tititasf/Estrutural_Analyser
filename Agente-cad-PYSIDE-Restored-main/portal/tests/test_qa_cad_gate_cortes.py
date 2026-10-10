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
