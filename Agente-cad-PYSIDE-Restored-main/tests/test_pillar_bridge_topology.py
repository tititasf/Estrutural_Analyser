"""A bridge preserves beam identity; occupation alone cannot establish it."""
from src.core.pillar_face_beams import _bridgeable_gap
def row(name,run,is_h=False):return dict(name=name,runs=[run],is_h=is_h)
def test_parallel_competitor_cannot_extend_requested_beam():
    assert _bridgeable_gap([row('V426',[10,0,29,100])],'V425','H',0,1,10,29,19,100)==0
def test_duplicate_crossings_do_not_cover_a_hole():
    info=[row('V1',[0,0,100,45],True),row('V2',[0,0,100,45],True)]
    assert _bridgeable_gap(info,'V425','H',0,1,10,29,19,100)==64
def test_partially_overlapping_crossings_count_union():
    info=[row('V1',[0,0,100,45],True),row('V2',[0,25,100,60],True)]
    assert _bridgeable_gap(info,'V425','H',0,1,10,29,19,100)==79
def test_transverse_bridge_preserves_owner_r1():
    info=[row('V306',[1357,2048,3788,2067],True)]
    assert _bridgeable_gap(info,'V313','H',2029,1,2040.4,2059.4,19,38)==38
def test_competing_corridor_outside_candidate_band_does_not_veto():
    info=[row('VX',[50,0,69,100]),row('VH',[0,0,100,81],True)]
    assert _bridgeable_gap(info,'V425','H',0,1,10,29,19,100)==100
def test_vertical_face_uses_same_orientation_rule():
    assert _bridgeable_gap([row('VX',[0,10,100,29],True)],'V1','V',0,1,10,29,19,100)==0
