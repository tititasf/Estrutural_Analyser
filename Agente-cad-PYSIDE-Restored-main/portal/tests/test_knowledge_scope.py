import json
from pathlib import Path
from portal.app.knowledge_scope import _source, _archive_towers, safe
import pytest

def test_complete_evidence_and_compact_search_are_separate(tmp_path):
    geometry={'points':[[1,2],[3,4]], 'level':537.86}
    _source(tmp_path,'obra-a','TIPO',Path('sa/item'),'Item',geometry,{'source_revision':'sha-a'})
    path=tmp_path/'knowledge/sources/pavimentos/TIPO/sa/item'
    evidence=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    assert evidence['data']==geometry
    text=path.with_suffix('.md').read_text(encoding='utf-8')
    assert '537.86' in text and 'source_revision' in text
    assert 'data.points' not in text
    assert evidence['scope']=={'obra_id':'obra-a','pavimento_id':'TIPO'}

def test_removed_tower_is_archived_outside_index(tmp_path):
    base=tmp_path/'knowledge/sources/pavimentos/TIPO/niveis'
    for tower in ('current','removed'):
        folder=base/tower;folder.mkdir(parents=True)
        (folder/'fact.md').write_text('measured level')
    _archive_towers(base,{'current'})
    assert (base/'current/fact.md').exists()
    assert not (base/'removed/fact.md').exists()
    assert len(list((tmp_path/'knowledge/history').rglob('fact.md')))==1

@pytest.mark.parametrize('value',['../obra','a/b','a\\b','..','obra:other'])
def test_scope_cannot_escape_work(value):
    with pytest.raises(ValueError): safe(value)
