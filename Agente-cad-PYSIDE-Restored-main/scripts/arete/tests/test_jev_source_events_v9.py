import math
import pytest
from scripts.arete.jev_source_events_v9 import boundary_distance
from scripts.arete.jev_event_fragments_v9 import split_record, encoded

def test_bounding_box_interior_is_not_boundary_contact():
    assert boundary_distance([5,5],[[0,0],[10,0],[10,10],[0,10]],True)==5

def test_closed_edge_is_measured():
    assert boundary_distance([0,5],[[0,0],[10,0],[10,10],[0,10]],True)==0
    assert boundary_distance([0,5],[[0,0],[10,0],[10,10],[0,10]],False)==5

def test_projection_clamped_to_endpoint():
    assert boundary_distance([12,3],[[0,0],[10,0]])==pytest.approx(math.sqrt(13))

def test_degenerate_edge():
    assert boundary_distance([3,4],[[0,0],[0,0]])==5

def test_nonfinite_rejected():
    with pytest.raises(ValueError):boundary_distance([float('nan'),0],[[0,0],[10,0]])

def test_empty_entity_is_unknown():
    assert boundary_distance([0,0],[]) is None

def test_fragments_keep_all_entities_in_order():
    record={'encounter_id':'e1','entities':[{'handle':str(i),'text':'a'*60} for i in range(15)]}
    chunks=split_record(record,max_bytes=260)
    assert len(chunks)>1
    assert [e for c in chunks for e in c['entities']]==record['entities']
    assert all(len(encoded(c))<=260 for c in chunks)

def test_oversized_entity_fails_without_truncation():
    with pytest.raises(ValueError):split_record({'entities':[{'text':'a'*1000}]},100)

@pytest.mark.parametrize('endpoint,points',[
    ([4708.59,3188.025],[[4708.59,3193.025],[4708.59,3325.31832]]),
    ([2099.09,2393.025],[[2094.09,2393.025],[1958.514033,2393.025]])])
def test_translation_preserves_separation(endpoint,points):
    translated=[[round(p[0]-endpoint[0],6),round(p[1]-endpoint[1],6)] for p in points]
    assert boundary_distance(endpoint,points)==pytest.approx(5)
    assert boundary_distance([0,0],translated)==pytest.approx(5)
