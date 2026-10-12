import json
from src.core.n5_assembler import _state_slab_ids


def test_slab_ids_use_current_floor_and_deduplicate(tmp_path):
    (tmp_path/'estado_ANDAR.json').write_text(json.dumps({'slabs':[
        {'name':'LAUTO_2'}, {'name':'LAUTO_1'}, {'name':'LAUTO_2'},
    ]}), encoding='utf-8')
    (tmp_path/'estado_OUTRO.json').write_text(json.dumps({'slabs':[{'name':'L401'}]}), encoding='utf-8')
    assert _state_slab_ids(tmp_path, 'ANDAR') == ['LAUTO_1','LAUTO_2']


def test_empty_current_slabs_is_authoritative_and_missing_state_allows_legacy(tmp_path):
    (tmp_path/'estado_ANDAR.json').write_text('{"slabs":[]}', encoding='utf-8')
    assert _state_slab_ids(tmp_path, 'ANDAR') == []
    assert _state_slab_ids(tmp_path, 'AUSENTE') is None
