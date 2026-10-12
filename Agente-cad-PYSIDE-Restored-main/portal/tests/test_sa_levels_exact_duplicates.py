from copy import deepcopy
from portal.app.preprocessamento.sa_levels import deduplicate_identical_source_records


def test_same_identity_and_all_original_provenance_deduplicates_without_mutation():
    record=dict(item_id='source',source_entity_handles=['original'],geometry={'points':[[0,0],[1,1]]},levels=[dict(fact_id='f',status='unknown',value=None)])
    rows=[record,deepcopy(record)];before=deepcopy(rows)
    assert deduplicate_identical_source_records(rows)==[record]
    assert rows==before


def test_same_identity_keeps_disagreeing_geometry_handle_facts_and_metadata():
    original=dict(item_id='source',source_entity_handles=['original'],geometry={'points':[[0,0],[1,1]]},levels=[dict(fact_id='f',status='unknown',value=None)])
    for key,value in [('source_entity_handles',['other']),('geometry',{'points':[[0,0],[2,2]]}),('levels',[dict(fact_id='f',status='inferred',value=855.25)]),('review','needs_review')]:
        other=deepcopy(original);other[key]=value
        assert len(deduplicate_identical_source_records([original,other]))==2
    assert len(deduplicate_identical_source_records([dict(original,item_id=None),dict(original,item_id=None)]))==2


def test_collided_identity_with_lost_original_geometry_and_handles_is_not_deduplicated():
    record=dict(item_id='collision',geometry=None,source_entity_handles=[],levels=[])
    assert len(deduplicate_identical_source_records([record,deepcopy(record)]))==2


def test_normalized_union_of_distinct_original_handles_is_not_duplicate_proof():
    record=dict(item_id='union',geometry={'points':[[0,0],[1,1]]},source_entity_handles=['one','two'],levels=[])
    assert len(deduplicate_identical_source_records([record,deepcopy(record)], {'union'}))==2
