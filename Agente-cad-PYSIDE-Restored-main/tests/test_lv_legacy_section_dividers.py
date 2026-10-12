from copy import deepcopy
import pytest
from src.core.lv_section_dividers import reconcile_section_dividers


def scene(horizontal=True, side='A'):
    point = lambda u,v: [u,v] if horizontal else [v,u]
    wall = 10 if side == 'A' else 29
    rows=[]
    for index,(lo,hi,depth,endpoint) in enumerate([(0,200,120,1),(200,400,71,0)]):
        cell=dict(depth=depth,dim=f'19/{depth}',sections=[dict(start=lo,end=hi,
            depth=depth,source='midpoint_between_labels')],beam_openings=[],pillar_openings=[])
        cell['support_start' if endpoint == 0 else 'support_end']={'type':'secao'}
        rows.append(dict(uid=str(index),beam_name='VX',side=side,points=[point(lo,wall),point(hi,wall)],
                         length=hi-lo,lv_cell=cell))
    return {'segmentos':{'lateral_a_para':rows}},point


@pytest.mark.parametrize('horizontal',[True,False])
@pytest.mark.parametrize('side',['A','B'])
def test_legacy_midpoint_replaced_by_unique_measured_divider(horizontal,side):
    state,point=scene(horizontal,side); before=deepcopy(state)
    lines=[(*point(290,10),*point(290,29)),(*point(240,-10),*point(240,49))]
    corrected=reconcile_section_dividers(state,lines)
    rows=corrected['segmentos']['lateral_a_para']
    assert [r['length'] for r in rows]==[290,110]
    assert rows[0]['points'][1]==rows[1]['points'][0]==point(290,10 if side=='A' else 29)
    assert state==before
    assert reconcile_section_dividers(corrected,lines)==corrected


@pytest.mark.parametrize('reason',['ambiguous','manual','pillar','explicit','partial'])
def test_do_not_move_unproved_or_protected_boundary(reason):
    state,point=scene();rows=state['segmentos']['lateral_a_para']
    lines=[(*point(290,10),*point(290,29))]
    if reason=='ambiguous': lines.append((*point(280,10),*point(280,29)))
    if reason=='manual': rows[0]['geometry_validated']=True
    if reason=='pillar': rows[0]['lv_cell']['pillar_openings']=[{'name':'P1'}]
    if reason=='explicit':
        for r in rows:r['lv_cell']['sections'][0]['source']='structural_transverse_divider'
    if reason=='partial':lines=[(*point(290,10),*point(290,19))]
    assert reconcile_section_dividers(state,lines)==state
