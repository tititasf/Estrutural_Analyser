"""Partial positive measurements cannot establish an absent pillar contact."""
from src.core.pillar_abcd_tables import prune_beams_far_from_face, measured_arrival_dists


def beam(points, verified):
    return {'name':'VTEST','is_h':False,'geometry':{'classified':{'seg_bottom':[{'points':points}]}},
            '_verified_wall_runs':[(verified,'19/120')]}


def tables():
    return {'D':{'interior':[{'nome':'VTEST','dim':'19/120'}]}}


def test_partial_verified_run_preserves_other_traced_contact_candidate():
    b=beam([[0,-120],[19,-120],[19,0],[0,0]],(0,100,19,300))
    t=tables()
    assert prune_beams_far_from_face(t,(0,0,19,100),[b])==[]
    assert t['D']['interior'][0]['nome']=='VTEST'
    # Keeping an unproved candidate must not supply numerical measurement.
    assert measured_arrival_dists('D',(0,0,19,100),[b],'VTEST',verified_only=True)==(None,None)


def test_all_traced_and_verified_runs_far_still_remove_contact():
    b=beam([[0,100],[19,100],[19,300],[0,300]],(0,100,19,300))
    t=tables()
    assert prune_beams_far_from_face(t,(0,0,19,100),[b])==['D.interior: VTEST longe da face']
    assert not t['D']['interior']


def test_measured_corridor_still_vetoes_foreign_degenerate_cap():
    b=beam([[0,0],[19,0]],(100,100,119,300))
    b['_measured_corridor']=(100,100,119,300)
    t=tables()
    assert prune_beams_far_from_face(t,(0,0,19,100),[b])


def test_original_measured_arm_keeps_candidate_without_certifying_interior():
    b=beam([[0,100],[19,100],[19,300],[0,300]],(0,100,19,300))
    b['_measured_corridor']=(0,-120,14,0)
    t=tables()
    t['D']['interior'][0]['_source']='original_contact_identity'
    assert not prune_beams_far_from_face(t,(0,0,19,100),[b])
    assert measured_arrival_dists('D',(0,0,19,100),[b],'VTEST',verified_only=True)==(None,None)
    assert measured_arrival_dists('D',(0,0,19,100),[b],'VTEST',section_dim='14/55',
                                  original_contact_bound=True)==(5,0)


def test_measured_corridor_does_not_restore_unbound_alias():
    b=beam([[0,100],[19,100],[19,300],[0,300]],(0,100,19,300))
    b['_measured_corridor']=(0,-120,14,0)
    t=tables()
    assert prune_beams_far_from_face(t,(0,0,19,100),[b])
    assert not t['D']['interior']
    assert measured_arrival_dists('D',(0,0,19,100),[b],'VTEST',
                                  section_dim='14/55')==(None,None)


def test_original_measured_and_traced_conflicting_arrivals_remain_ambiguous():
    b={'name':'VTEST','is_h':False,'geometry':{'classified':{'seg_bottom':[
        {'points':[[0,-120],[14,-120],[14,0],[0,0]]}]}},
        '_measured_corridor':(5,-120,19,0)}
    assert measured_arrival_dists('D',(0,0,19,100),[b],'VTEST',section_dim='14/55',
                                  original_contact_bound=True)==(None,None)
