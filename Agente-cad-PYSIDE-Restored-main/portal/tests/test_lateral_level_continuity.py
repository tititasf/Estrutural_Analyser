from copy import deepcopy
from portal.app.preprocessamento.segment_levels import continue_lateral_segment


def row(uid,value=10,status='sa_evidence',funds=None):
    return dict(fact_id=uid,value=value,status=status,confidence_pct=85,
        evidence_ids=['cad:A'],warnings=[],fv_segments=funds or [],method='spatial_fv_reference')


def test_supported_segment_level_continues_over_pillar_and_ends():
    rows=[row('start',9,'estimated'),row('fv',funds=['1']),row('pillar',None,'unknown'),
          row('fv2',funds=['2']),row('end',9,'estimated')]
    continue_lateral_segment(rows,row('native',9,'estimated'))
    assert all(r['value']==10 for r in rows)
    assert rows[2]['status']=='inferred' and rows[2]['confidence_pct']==80.8
    assert rows[2]['source_fact_ids']==['fv','fv2']
    assert rows[0]['fact_id']=='start' and rows[-1]['fact_id']=='end'


def test_different_supported_levels_keep_gap_pending():
    rows=[row('fv1',funds=['1']),row('gap',9,'estimated'),row('fv2',11,funds=['2'])]
    original=deepcopy(rows);continue_lateral_segment(rows,row('native',9,'estimated'))
    assert rows==original


def test_estimates_do_not_bootstrap_and_conflicts_do_not_disappear():
    for rows in ([row('guess',10,'estimated'),row('gap',None,'unknown')],
                 [row('proof',funds=['1']),row('conflict',None,'conflict'),row('gap',9,'estimated')]):
        original=deepcopy(rows);continue_lateral_segment(rows,row('native',9,'estimated'))
        assert rows==original


def test_native_direct_level_and_supported_fv_are_not_overwritten():
    rows=[row('fv',funds=['1']),row('gap',9,'estimated')]
    original=deepcopy(rows);continue_lateral_segment(rows,row('human',11,'human_review'))
    assert rows==original


def test_local_equal_neighbors_confirm_gap_despite_other_altitude_elsewhere():
    rows=[row('left',10,funds=['1']),row('gap',9,'estimated'),
          row('right',10,funds=['2']),row('other',11,funds=['3'])]
    continue_lateral_segment(rows,row('native',9,'estimated'))
    assert rows[1]['value']==10 and rows[1]['status']=='inferred'
    assert rows[1]['source_fact_ids']==['left','right']
    assert rows[3]['value']==11


def test_multiple_altitudes_do_not_confirm_unbounded_gap():
    rows=[row('first',10,funds=['1']),row('other',11,funds=['2']),
          row('end',10,'estimated')]
    original=deepcopy(rows)
    continue_lateral_segment(rows,row('native',9,'estimated'))
    assert rows==original
