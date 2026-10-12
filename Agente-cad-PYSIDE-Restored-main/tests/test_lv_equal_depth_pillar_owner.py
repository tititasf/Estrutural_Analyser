from copy import deepcopy

import pytest

from src.core.lv_beam_scene import LvScene, _cede_shared_end_pillars
from src.core.beam_interpreters.lateral_viga_cells import segment_cell, apply_cells_to_beam
from src.core.lv_generation_contract import build_lv_generation_contracts
from src.core.preficha_segments import collect_preficha_segments


def runs(horizontal=True, same_name=True, right_width=19, right_depth=55):
    left = LvScene('V1', horizontal, 0, 14, 0, 100)
    right = LvScene('V1' if same_name else 'V2', horizontal, 0, right_width, 120, 300)
    for run, end, depth in [(left, 'end', 55), (right, 'start', right_depth)]:
        run.sections = [dict(start=run.start, end=run.end, width=run.width,
                             depth=depth, dim=f'{run.width:g}/{depth:g}')]
        run.end_supports[end] = [dict(type='pilar', name='P1', start=100, end=120,
            miolo_por_lado={'A':False,'B':False}, face_curta_por_lado={'A':False,'B':False})]
        run.face_coverage = {'A':[[0,300]], 'B':[[0,300]]}
    return left, right


@pytest.mark.parametrize('horizontal',[True,False])
@pytest.mark.parametrize('same_name',[True,False])
@pytest.mark.parametrize('reverse',[True,False])
def test_equal_depth_common_wall_has_one_owner_and_balanced_adjustments(horizontal,same_name,reverse):
    left,right = runs(horizontal,same_name)
    _cede_shared_end_pillars([right,left] if reverse else [left,right])
    assert left.end_supports['end'][0]['passa_ownership']['A']['chosen'] is False
    assert right.end_supports['start'][0]['passa_ownership']['A']['chosen'] is True
    # The different upper walls do not share ownership or endpoint offsets.
    assert 'B' not in left.end_supports['end'][0]['passa_ownership']
    a,b = segment_cell(left,'A','passa')[0],segment_cell(right,'A','passa')[0]
    assert sorted((a.start,a.end)) == [0,100]
    assert sorted((b.start,b.end)) == [100,300]
    left_adjustment = a.adjustment_end if horizontal else a.adjustment_start
    right_adjustment = b.adjustment_start if horizontal else b.adjustment_end
    assert left_adjustment == -11
    assert right_adjustment == 11
    assert 100+left_adjustment == 100-right_adjustment  # Same executable seam.
    assert a.pillar_openings == []
    assert b.pillar_openings[0]['comprimento'] == 20
    # PARA remains an independent interpretation.
    assert sorted((segment_cell(left,'A','para')[0].start,
                   segment_cell(left,'A','para')[0].end)) == [0,100]
    assert sorted((segment_cell(right,'A','para')[0].start,
                   segment_cell(right,'A','para')[0].end)) == [120,300]


def test_equal_width_tie_uses_stable_geometry_and_not_input_order():
    for reverse in (False,True):
        left,right=runs(right_width=14)
        _cede_shared_end_pillars([right,left] if reverse else [left,right])
        assert left.end_supports['end'][0]['passa_ownership']['A']['chosen'] is True
        assert right.end_supports['start'][0]['passa_ownership']['A']['chosen'] is False


@pytest.mark.parametrize('horizontal', [True, False])
@pytest.mark.parametrize('ceded_end', ['start', 'end'])
def test_ceded_pillar_entry_face_overrides_measured_wall_extension(horizontal, ceded_end):
    left, right = runs(horizontal=horizontal, right_width=14 if ceded_end == 'start' else 19)
    _cede_shared_end_pillars([left, right])
    loser = right if ceded_end == 'start' else left
    # A side wall can be traced inside the pillar toward an incident beam.
    # This proves line continuity, not permission to occupy a ceded pillar.
    loser.face_extent['A'] = (107, 300) if ceded_end == 'start' else (0, 113)
    cell = segment_cell(loser, 'A', 'passa')[0]
    assert sorted((cell.start, cell.end)) == ([120, 300] if ceded_end == 'start' else [0, 100])
    at_start = (ceded_end == 'start') == horizontal
    assert (cell.adjustment_start if at_start else cell.adjustment_end) == -11
    assert cell.pillar_openings == []


def test_connected_meeting_cannot_elect_multiple_owners_pair_by_pair():
    left,right=runs()
    third=deepcopy(right)
    third.beam_name='V3'
    third.t_hi=24
    for order in ([left,right,third],[third,right,left]):
        _cede_shared_end_pillars(order)
        choices=[(r.end_supports['end' if r is left else 'start'][0]
                  ['passa_ownership']['A']['chosen']) for r in (left,right,third)]
        assert choices == [False,False,True]


@pytest.mark.parametrize('guard',['depth','core','detached','wall','short'])
def test_equal_depth_choice_requires_opposite_connected_exterior_walls(guard):
    left,right=runs(right_depth=60 if guard=='depth' else 55)
    if guard=='core':right.end_supports['start'][0]['miolo_por_lado']['A']=True
    if guard=='detached':right.start=130
    if guard=='wall':right.t_lo=2
    if guard=='short':right.end_supports['start'][0]['face_curta_por_lado']['A']=True
    _cede_shared_end_pillars([left,right])
    assert not (left.end_supports['end'][0].get('passa_ownership') or {}).get('A')


def test_adjustment_tags_and_executable_contract_use_offsets_once():
    left,right=runs()
    _cede_shared_end_pillars([left,right])
    beam=dict(name='V1',id='one',links={})
    apply_cells_to_beam(beam,[left,right])
    rows=collect_preficha_segments([beam])['lateral_a_passa']
    assert [r['details']['adjustment']['final'] for r in rows] == ['-11','0']
    assert [r['details']['adjustment']['initial'] for r in rows] == ['0','+11']
    before=deepcopy(beam)
    contract=build_lv_generation_contracts(beam)['Passa']['A']
    assert contract['geometry_length'] == 300
    assert contract['total_length'] == 300
    panels=contract['panels']
    assert sum(p['width'] for p in panels if p['physical_segment_index']==1) == 89
    assert sum(p['width'] for p in panels if p['physical_segment_index']==2) == 211
    assert beam == before


def test_portal_endpoint_highlights_expose_the_same_signed_owner_adjustments():
    from pathlib import Path
    from portal.app.ficha_reader import listar_itens_n1
    from portal.app.routers.viewer_routes import _ajustes_pontas_lateral
    from portal.app.lv_ficha import _segment
    left,right=runs()
    _cede_shared_end_pillars([left,right])
    beam=dict(name='V1',id='one',links={})
    apply_cells_to_beam(beam,[left,right])
    rows=collect_preficha_segments([beam])['lateral_a_passa']
    # Same metadata promotion performed by PreValidationDialog._build_state.
    state={'segmentos':{'lateral_a_passa':[
        {**row,'lv_cell':row['details']['lv_cell']} for row in rows]}}
    items=listar_itens_n1(state,'lateral_a_passa')
    for row, item, expected in zip(rows,items,[(0,-11),(11,0)]):
        tags=_ajustes_pontas_lateral(item,'lateral_a_passa')
        assert (tags['esquerda'],tags['direita']) == expected
        assert tags['direita_ponto' if expected[1] else 'esquerda_ponto'] == 'P1'
        payload=_segment(Path('unused'),'PAV','lateral_a_passa',item,
                         include_svgs=False,beam_record=beam)
        assert payload['adjustment'] == row['details']['adjustment']


@pytest.mark.parametrize('horizontal', [True, False])
@pytest.mark.parametrize('section_change', [False, True])
def test_short_face_between_two_trechos_is_one_lateral(horizontal, section_change):
    # LV-FACE-CURTA-SEGMENTO-UNICO-20261012 (V517 x P16, TIPO_TESTE): a face A
    # corre pela face curta do pilar; os dois trechos englobavam o pilar e se
    # sobrepunham. Para e Passa viram um segmento só; a face B para no pilar.
    left, right = runs(horizontal, right_width=14, right_depth=60 if section_change else 55)
    for run, end in ((left, 'end'), (right, 'start')):
        run.end_supports[end][0]['face_curta_por_lado'] = {'A': True, 'B': False}
    beam = dict(name='V1', id='one', links={})
    apply_cells_to_beam(beam, [left, right])
    rows = collect_preficha_segments([beam])
    for kind in ('lateral_a_para', 'lateral_a_passa'):
        lengths = [r['length'] for r in rows[kind]]
        if section_change:
            assert len(lengths) == 2
            continue
        assert lengths == [300]
        opening, = rows[kind][0]['details']['lv_cell']['pillar_openings']
        assert (opening['dist_face_inicio'], opening['dist_face_fim']) == ((100, 180) if horizontal else (180, 100))
    assert [r['length'] for r in rows['lateral_b_para']] == [100, 180]
