from copy import deepcopy

from portal.app.preprocessamento.sa_levels import merge_sa_levels, item_level_input, consume_item_levels
from portal.app.preprocessamento.crosscheck import check_facts


def fixture():
    items = [{'item_id': n, 'display_name': n, 'item_class': c, 'levels': [], 'segments': []}
             for n,c in [('L1','slab'), ('V1','beam'), ('P1','pillar')]]
    polygon = [[0,0],[10,0],[10,10],[0,10],[0,0]]
    context = {'evidence_id': 'scoped-source', 'marks': [{'value': 852.19, 'pos':[5,5], 'handle':'A'}],
        'state': {'slabs':[{'name':'L1', 'nivel':None, 'points':polygon}],
                  'pilares':[{'name':'P1','classification':'NASCE'}],
                  'segmentos': {'fundo':[{'uid':'V1|1', 'beam_name':'V1','segment_label':1,
                    'level':852.19, 'level_source':'highest_touching_slab', 'level_slabs':['L1'],
                    'points':[[100,0],[200,0],[200,19],[100,19],[100,0]]},
                    {'uid':'V1|2', 'beam_name':'V1','segment_label':2,'level':852.12,
                     'level_source':'estimated_beam_level','level_slabs':[],
                     'points':[[220,0],[320,0],[320,19],[220,19],[220,0]]}] }},
        'tables': {'beams':[{'name':'V1','data_json':'{"fields":{"viga_fundo_seg_1_dim":"19/55","viga_fundo_seg_2_dim":"19/48"}}'}]}}
    return {'reference':{'base':848.98,'top':852.19,'unit':'m'},'items':items}, context


def test_all_segments_distinct_bottom_and_nasce_not_false_missing():
    tower, context = fixture()
    result = merge_sa_levels(tower, context)
    slab, beam, pillar = result['items']
    assert slab['levels'][0]['value'] == 852.19
    assert [s['bottom_level'] for s in beam['segments']] == [851.64,851.71]
    assert beam['segments'][1]['status'] == 'estimated'
    assert all(f['status'] == 'not_applicable' for f in pillar['levels'])
    assert not check_facts(beam['levels'])
    assert result['sa_evidence']['segments'] == 2


def test_contained_level_consumed_preserving_human_and_changed_geometry():
    tower, context = fixture()
    result = merge_sa_levels(tower, context)
    package = {'levels':result['items'][0]['levels'], 'level_inventory':{'items':tower['items']}}
    levels = item_level_input(package)
    slab = {'name':'L1','points':context['state']['slabs'][0]['points'],'fields':{'laje_nivel':'402.5'}}
    protected = deepcopy(slab); protected['validated_link_classes']={'laje_nivel':['label']}
    changed = deepcopy(slab); changed['points']=[[20,20],[30,20],[30,30],[20,30]]
    assert consume_item_levels([protected,changed],levels) == []
    assert len(consume_item_levels([slab],levels)) == 1
    assert slab['fields']['laje_nivel']=='852.19'


def test_multiple_parts_retained_never_flattened_into_sa_scalar():
    tower,context=fixture()
    context['marks'].append({'value':852.12,'pos':[6,6],'handle':'B'})
    result=merge_sa_levels(tower,context)
    assert len(result['items'][0]['levels'])==2
    assert item_level_input({'levels':result['items'][0]['levels'],
        'level_inventory':{'items':tower['items']}})=={}


def test_multi_part_slab_does_not_certify_consuming_segment_scalar():
    tower, context = fixture()
    context['marks'].append({'value': 852.12, 'pos': [6,6], 'handle': 'B'})
    beam = merge_sa_levels(tower, context)['items'][1]
    assert beam['segments'][0]['status'] == 'inferred'
    assert 'source_slab_level_not_uniquely_observed' in beam['segments'][0]['warnings']


def test_automatic_beam_value_without_source_is_not_measured():
    tower, context = fixture()
    context['state']['segmentos']['fundo'][0].update(
        level_source='explicit_beam_or_side', level_slabs=[])
    beam = merge_sa_levels(tower, context)['items'][1]
    assert beam['segments'][0]['status'] == 'inferred'
    assert 'automatic_beam_field_without_cad_level_provenance' in beam['segments'][0]['warnings']


def test_contradictory_cut_candidate_visible_but_never_consumed():
    import json
    tower, context = fixture()
    context['marks'] = []
    context['state']['slabs'][0]['nivel'] = 852.19
    context['tables']['slabs'] = [{'name': 'L1', 'extra_data_json': json.dumps({
        'level_inference': {'status': 'needs_review', 'candidates': [
            {'value': 852.12, 'source_slab': 'L2', 'method': 'cut_delta'}]}})}]
    result = merge_sa_levels(tower, context)
    facts = result['items'][0]['levels']
    assert [(f['field'], f['value']) for f in facts] == [
        ('slab_level', 852.19), ('slab_level_candidate', 852.12)]
    assert 'unresolved_cut_level_alternative' in facts[0]['warnings']
    assert item_level_input({'levels': facts, 'level_inventory': {'items': tower['items']}}) == {}
