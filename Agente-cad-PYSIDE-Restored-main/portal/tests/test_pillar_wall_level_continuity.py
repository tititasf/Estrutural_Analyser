from copy import deepcopy
from shapely.geometry import LineString
from portal.app.preprocessamento.segment_levels import continue_pillar_wall_segments


def fixture():
    sides = [dict(segment_id='pillar', family='lateral_b_passa',
        details={'lv_cell':dict(depth=60,pillar_openings=[dict(comprimento=100)],
            support_end=dict(type='viga',rule='G7_incidente_menos_profunda_passa_por_baixo'))},
        level_ranges=[dict(fact_id='pillar:range',value=9,status='estimated',fv_segments=[],
            confidence_pct=30,evidence_ids=[],warnings=[])]),
        dict(segment_id='wall',family='lateral_b_passa',details={'lv_cell':dict(depth=60)})]
    records = {uid:dict(fact_id=uid,value=value,status=status,
        confidence_pct=confidence,evidence_ids=['cad'] if uid=='wall' else [],warnings=[])
        for uid,value,status,confidence in [('pillar',9,'estimated',30),('wall',10,'sa_evidence',85)]}
    shapes = dict(pillar=LineString([(0,0),(0,100)]),wall=LineString([(0,100),(0,200)]))
    return sides,records,shapes


def test_full_pillar_wall_uses_touching_same_face_supported_level():
    sides,records,shapes=fixture()
    continue_pillar_wall_segments(sides,records,shapes)
    assert records['pillar']['value']==10
    assert records['pillar']['status']=='sa_evidence'
    assert records['pillar']['confidence_pct']==80.8
    assert sides[0]['level_ranges'][0]['source_fact_ids']==['wall']


def test_step_opposite_face_depth_change_and_estimate_do_not_confirm():
    for mode in ['step','opposite','depth','estimate']:
        sides,records,shapes=fixture()
        if mode=='step': sides[1]['details']['lv_cell']['support_start']={'type':'degrau_laje'}
        if mode=='opposite': sides[1]['family']='lateral_a_passa'
        if mode=='depth': sides[1]['details']['lv_cell']['depth']=55
        if mode=='estimate': records['wall']['status']='estimated'
        before=deepcopy(records)
        continue_pillar_wall_segments(sides,records,shapes)
        assert records==before


def test_step_at_far_endpoint_does_not_block_pillar_junction():
    sides,records,shapes=fixture()
    sides[1]['details']['lv_cell']['support_end']={'type':'degrau_laje'}
    continue_pillar_wall_segments(sides,records,shapes)
    assert records['pillar']['value']==10
    assert records['pillar']['confidence_pct']==80.8
