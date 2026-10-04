import pytest

from src.core.lv_generation_contract import build_lv_generation_contracts


@pytest.mark.parametrize('vertical,reverse', [(False,False),(True,False),(False,True),(True,True)])
def test_opening_projects_across_touching_segments_without_merging_them(vertical, reverse):
    def point(x):
        x = -x if reverse else x
        return [5,x] if vertical else [x,5]
    rows = []
    for start,end in [(0,100),(100,200)]:
        rows.append({'points':[point(start),point(end)],'len':100,'lv_dimensao':'19/120','lv_cell':{}})
    rows[0]['lv_cell']['beam_openings'] = [{'name':'incident','largura':19,'abertura_largura':27,
                                           'abertura_altura':59,'pos_inicio':81}]
    beam = {'name':'beam','links':{f'viga_b_seg_{i}_comp_total_passa':{'seg_side_b':[r]} for i,r in enumerate(rows,1)}}
    c = build_lv_generation_contracts(beam)['Passa']['B']
    assert c['structural_segment_count'] == 2
    assert c['total_length'] == 200
    assert [p['width'] for p in c['panels']] == [100,100]
    assert [(p['holes'][0]['width'],p['holes'][0]['corner']) for p in c['panels']] == [(23,'TR'),(4,'TL')]
    assert [(p['segment_index'],p['holes'][0]['height']) for p in c['panels'] if p.get('holes')] == [(1,59),(2,59)]
    assert not build_lv_generation_contracts(beam)['Para']['B']['panels']


def test_interior_opening_has_exact_corner_coordinates_after_panel_split():
    entry = {'points':[[0,0],[200,0]],'len':200,'lv_dimensao':'19/60','lv_cell':{'beam_openings':[
        {'name':'incident','largura':19,'abertura_largura':27,'abertura_altura':59,'pos_inicio':80}]}}
    c = build_lv_generation_contracts({'links':{'viga_a_seg_1_comprimento_total':{'seg_side_a':[entry]}}})['Para']['A']
    assert c['structural_segment_count'] == 1
    assert [p['width'] for p in c['panels']] == [76,124]
    assert c['panels'][1]['holes'][0]['width'] == 27
    assert c['panels'][1]['holes'][0]['corner'] == 'TL'
    assert c['total_length'] == 200


def test_opening_does_not_bridge_physical_gap_or_invent_unknown_height():
    first = {'points':[[0,0],[100,0]],'len':100,'lv_dimensao':'19/120','lv_cell':{'beam_openings':[
        {'name':'incident','largura':19,'abertura_largura':27,'abertura_altura':59,'pos_inicio':81},
        {'name':'unknown','largura':19,'abertura_largura':27,'abertura_altura':None,'pos_inicio':10}]}}
    second = {'points':[[130,0],[230,0]],'len':100,'lv_dimensao':'19/120'}
    beam = {'links':{'viga_b_seg_1_comprimento_total':{'seg_side_b':[first]},
                    'viga_b_seg_2_comprimento_total':{'seg_side_b':[second]}}}
    c = build_lv_generation_contracts(beam)['Para']['B']
    assert [p['width'] for p in c['panels']] == [100,100]
    assert not c['panels'][-1].get('holes')
    assert c['total_length'] == 200
