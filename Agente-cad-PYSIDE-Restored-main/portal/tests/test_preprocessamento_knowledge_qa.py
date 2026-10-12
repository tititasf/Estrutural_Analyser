import json
import sqlite3
import pytest
from portal.app.preprocessamento import knowledge_qa
from portal.app.preprocessamento.service import digest


@pytest.mark.parametrize('case', ['current_relative', 'wrong_work', 'stale_package', 'outside_root'])
def test_retrieval_reopens_exact_scope_and_revision(tmp_path, monkeypatch, case):
    app=tmp_path/'app'
    monkeypatch.setattr(knowledge_qa,'__file__',str(app/'portal/app/preprocessamento/knowledge_qa.py'))
    root=app/'DADOS-OBRAS/Work'
    package={'scope':{'obra_id':'work-1','pavimento_id':'TIPO_TESTE'},'run_id':'run-1'}
    source={'scope':package['scope'], 'provenance':{'package_hash':digest(package),
             'run_id':'run-1','source_revision':'sha'}}
    path=root/'knowledge/sources/pavimentos/TIPO_TESTE/preprocessamento/tower/levels.json'
    if case=='wrong_work':source['scope']={'obra_id':'work-2','pavimento_id':'TIPO_TESTE'}
    if case=='stale_package':source['provenance']['package_hash']='old'
    if case=='outside_root':path=app/'DADOS-OBRAS/Other/levels.json'
    path.parent.mkdir(parents=True);path.write_text(json.dumps(source))
    db=app/'KB-GLOBAL/obras/work-1.sqlite';db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute('create table chunks (id text, path text)')
        conn.execute('insert into chunks values (?,?)',('row',path.with_suffix('.md').relative_to(tmp_path).as_posix()))
    import scripts.kb.kb_query
    monkeypatch.setattr(scripts.kb.kb_query,'busca_texto',lambda *args:['row', 'row'])
    original_read = type(path).read_text
    reads = []
    def observed_read(self, *args, **kwargs):
        if self == path.resolve(): reads.append(self)
        return original_read(self, *args, **kwargs)
    monkeypatch.setattr(type(path), 'read_text', observed_read)
    result=knowledge_qa.retrieve_context_qa(root,package)
    assert result['numeric_authority'] is False
    assert bool(result['hits'])==(case=='current_relative')
    assert len(reads) == (0 if case == 'outside_root' else 1)
    if case!='current_relative':assert result['rejected']==1


@pytest.mark.parametrize('change', ['run', 'revision', 'aux_revision', 'recorte', 'missing_sources', 'floor'])
def test_history_requires_complete_identical_cad_lineage(tmp_path, monkeypatch, change):
    app = tmp_path/'app'
    monkeypatch.setattr(knowledge_qa, '__file__', str(app/'portal/app/preprocessamento/knowledge_qa.py'))
    root = app/'DADOS-OBRAS/Work'
    package = {'scope': {'obra_id': 'work-1', 'pavimento_id': 'Floor',
                        'recorte_id': 'tower-1', 'source_revision': 'cad-sha'},
               'run_id': 'new-run', 'sources': [{'source_id': 'aux', 'revision': 'aux-sha'}]}
    provenance = {'package_hash': 'old-package', 'run_id': 'old-run',
                  'source_revision': 'cad-sha', 'recorte_id': 'tower-1',
                  'sources': [{'source_id': 'aux', 'revision': 'aux-sha'}]}
    source_scope = {'obra_id': 'work-1', 'pavimento_id': 'Floor'}
    if change == 'revision': provenance['source_revision'] = 'other-cad'
    if change == 'aux_revision': provenance['sources'][0]['revision'] = 'other-aux'
    if change == 'recorte': provenance['recorte_id'] = 'tower-2'
    if change == 'missing_sources': provenance.pop('sources')
    if change == 'floor': source_scope['pavimento_id'] = 'Other'
    path = root/'knowledge/sources/pavimentos/Floor/preprocessamento/tower/levels.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'scope': source_scope, 'provenance': provenance}))
    db = app/'KB-GLOBAL/obras/work-1.sqlite'
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute('create table chunks (id text, path text)')
        conn.execute('insert into chunks values (?,?)', ('row', str(path.with_suffix('.md'))))
    import scripts.kb.kb_query
    monkeypatch.setattr(scripts.kb.kb_query, 'busca_texto', lambda *args: ['row'])
    result = knowledge_qa.retrieve_context_qa(root, package)
    assert result['numeric_authority'] is False
    assert result['independent_confirmation'] is False
    if change == 'run':
        assert result['status'] == 'historical_reference_available'
        assert result['hits'][0]['status'] == 'historical_same_sources_consultation'
        assert result['hits'][0]['independent_confirmation'] is False
    else:
        assert result['hits'] == []
        assert sum(result['rejection_reasons'].values()) == result['rejected'] == 1


@pytest.mark.parametrize('broken', ['malformed', 'missing', 'non_object', 'provenance'])
def test_bad_source_does_not_discard_later_valid_evidence(tmp_path, monkeypatch, broken):
    app = tmp_path/'app'
    monkeypatch.setattr(knowledge_qa, '__file__', str(app/'portal/app/preprocessamento/knowledge_qa.py'))
    root = app/'DADOS-OBRAS/Work'
    package = {'scope': {'obra_id': 'work-1', 'pavimento_id': 'Floor'}, 'run_id': 'run-1'}
    folder = root/'knowledge/sources/pavimentos/Floor/preprocessamento/tower'
    folder.mkdir(parents=True)
    bad, good = folder/'bad.json', folder/'good.json'
    if broken != 'missing':
        bad.write_text({'malformed': '{', 'non_object': '[]',
                        'provenance': json.dumps({'scope': package['scope'], 'provenance': []})}[broken])
    good.write_text(json.dumps({'scope': package['scope'], 'provenance': {
        'package_hash': digest(package), 'run_id': 'run-1', 'source_revision': 'sha'}}))
    db = app/'KB-GLOBAL/obras/work-1.sqlite'
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute('create table chunks (id text, path text)')
        for name, path in [('bad', bad), ('good', good)]:
            conn.execute('insert into chunks values (?,?)', (name, str(path.with_suffix('.md'))))
    import scripts.kb.kb_query
    monkeypatch.setattr(scripts.kb.kb_query, 'busca_texto', lambda *args: ['bad', 'good'])
    result = knowledge_qa.retrieve_context_qa(root, package)
    assert result['status'] == 'verified'
    assert result['rejected'] == 1
    assert [hit['path'] for hit in result['hits']] == [str(good.resolve())]
    assert result['numeric_authority'] is False
