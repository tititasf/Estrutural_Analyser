import pytest
from src.core.pil_qa_identity_paths import supported_anchor_start


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('failure', [None, 'unnamed', 'unnumbered', 'two_supports',
    'gap', 'wrong_pair', 'two_exits', 'outside', 'boundary'])
def test_only_unique_original_owned_support_can_locate_start(side, failure):
    support = dict(lo=40, hi=60, handle='original-pillar', bounds=(40,60,0,19),
                   name_handles=['P-name'], dimension_handles=['20/19'])
    wall = dict(lo=0 if side=='left' else 50, hi=50 if side=='left' else 100)
    node = dict(lo=0 if side=='left' else 60, hi=40 if side=='left' else 100,
                walls=[dict(wall),dict(wall)], wall_handles=['a','b'])
    nodes=[node]; supports=[support]; handles=['a','b']; anchor=50
    if failure=='unnamed':support['name_handles']=[]
    if failure=='unnumbered':support['dimension_handles']=[]
    if failure=='two_supports':supports.append(dict(support, handle='other'))
    if failure=='gap':node['walls'][1]['hi' if side=='left' else 'lo']=45 if side=='left' else 55
    if failure=='wrong_pair':handles=['unrelated']
    if failure=='two_exits':
        nodes=[dict(lo=0,hi=40,walls=[dict(lo=0,hi=100)]*2,wall_handles=handles),
               dict(lo=60,hi=100,walls=[dict(lo=0,hi=100)]*2,wall_handles=handles)]
    if failure=='outside':anchor=70
    if failure=='boundary':anchor=40
    proof=supported_anchor_start(nodes,supports,handles,anchor,.05)
    if failure is None:
        assert proof[0]==0 and proof[1]['pillar_handle']=='original-pillar'
        assert proof[1]['exit_at']==(40 if side=='left' else 60)
        assert 'section' not in proof[1]
    else:assert proof is None
