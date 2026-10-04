import hashlib
import json

import pytest

from scripts.arete.qa_cli_fallback import claude_stream_response, TechnicalFailure
from portal.app.qa_review_contract import validate_read_receipts


def stream(path, *, name='Read', error=False, args=None, result_id='read-1'):
    result = 'actual tool response'
    if path.is_file() and path.suffix == '.json':
        start = (args or {}).get('offset',1)
        limit = (args or {}).get('limit',2000)
        result = '\n'.join(f'{n}→{line}' for n,line in enumerate(path.read_text().splitlines(),1)
                           if start <= n < start+limit)
    return '\n'.join(json.dumps(e) for e in [
        {'type':'assistant','message':{'content':[{'type':'tool_use','id':'read-1',
            'name':name,'input':args or {'file_path':str(path)}}]}},
        {'type':'user','message':{'content':[{'type':'tool_result',
            'tool_use_id':result_id,'is_error':error,'content':result}]}},
        {'type':'result','result':'{}','modelUsage':{'claude-sonnet-5-5':{'outputTokens':4}}},
    ])


def test_completed_cli_read_has_hash_and_gate_rejects_changed_file(tmp_path):
    folder = tmp_path/'package'; folder.mkdir()
    path = folder/'source.png'; path.write_bytes(b'file accessed by CLI')
    raw = stream(path)
    wrapper = json.loads(claude_stream_response(raw,tmp_path))
    audit = wrapper['qa_execution_audit']
    assert audit['origin'] == 'claude_stream'
    assert audit['proves_comprehension'] is False
    assert audit['stream_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert audit['reads'][0]['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert validate_read_receipts(audit,folder,tmp_path,'LAJ') is audit
    path.write_bytes(b'changed evidence')
    with pytest.raises(ValueError,match='alterado'):
        validate_read_receipts(audit,folder,tmp_path,'LAJ')


@pytest.mark.parametrize('kwargs',[
    {'error':True}, {'name':'Grep'}, {'result_id':'unrelated'},
    {'args':{'file_path':'source.png','offset':2}},
])
def test_failed_unmatched_search_and_partial_reads_are_not_receipts(tmp_path,kwargs):
    path=tmp_path/'source.png'; path.write_bytes(b'evidence')
    assert not json.loads(claude_stream_response(stream(path,**kwargs),tmp_path))['qa_execution_audit']['reads']


def test_outside_root_read_and_prose_claim_are_not_receipts(tmp_path):
    root=tmp_path/'root'; root.mkdir()
    outside=tmp_path/'outside.png'; outside.write_bytes(b'other')
    assert not json.loads(claude_stream_response(stream(outside),root))['qa_execution_audit']['reads']
    claimed=json.dumps({'result':'I read source.png','qa_execution_audit':{'origin':'claude_stream','reads':[{}]}})
    assert 'qa_execution_audit' not in json.loads(claude_stream_response(claimed,root))
    with pytest.raises(TechnicalFailure):claude_stream_response('{}',root)


def test_read_limit_and_long_line_cannot_attest_complete_text(tmp_path):
    path=tmp_path/'fields.json';path.write_text('\n'.join(['x']*2001))
    assert not json.loads(claude_stream_response(stream(path),tmp_path))['qa_execution_audit']['reads']
    short=stream(path,args={'file_path':str(path),'limit':10})
    assert not json.loads(claude_stream_response(short,tmp_path))['qa_execution_audit']['reads']
    full=stream(path,args={'file_path':str(path),'limit':2001})
    assert json.loads(claude_stream_response(full,tmp_path))['qa_execution_audit']['reads']
    path.write_text('x'*2001)
    assert not json.loads(claude_stream_response(stream(path),tmp_path))['qa_execution_audit']['reads']


def test_invoker_requests_real_stream_and_keeps_model_guard(monkeypatch,tmp_path):
    from scripts.arete import qa_cli_fallback as a
    from subprocess import CompletedProcess
    captured=[]
    def run(cmd,**kwargs):
        captured.extend(cmd)
        return CompletedProcess(cmd,0,stream(tmp_path/'missing.png'),'')
    monkeypatch.setattr(a,'_run',run)
    raw,model=a.ClaudeInvoker(a.ProviderConfig('claude','claude-sonnet-5-5',None,'claude',60)).invoke('p',tmp_path)
    assert model == 'claude-sonnet-5-5'
    assert captured[captured.index('--output-format')+1] == 'stream-json'
    assert '--verbose' in captured
    assert json.loads(raw)['qa_execution_audit']['origin'] == 'claude_stream'


def test_verified_pages_cover_large_file_and_gaps_are_not_receipts(tmp_path):
    path=tmp_path/'fields.json'; path.write_text('\n'.join(str(n) for n in range(4001)))
    pages=[stream(path,args={'file_path':str(path),'offset':offset,'limit':2000})
           for offset in (1,2001,4001)]
    audit=lambda raw:json.loads(claude_stream_response(raw,tmp_path))['qa_execution_audit']['reads']
    assert not audit('\n'.join([pages[0],pages[2]]))
    reads=audit('\n'.join(pages))
    assert reads[0]['covered_lines']==4001 and len(reads[0]['tool_use_ids'])==3
    tampered=pages[1].replace('2001\\u21922000','2001\\u2192wrong')
    assert not audit('\n'.join([pages[0],tampered,pages[2]]))


def test_claimed_limit_does_not_prove_returned_text_and_repeated_page_leaves_gap(tmp_path):
    path=tmp_path/'fields.json'; path.write_text('\n'.join(['x']*2001))
    raw=stream(path,args={'file_path':str(path),'limit':3000})
    events=[json.loads(line) for line in raw.splitlines()]
    events[1]['message']['content'][0]['content']='1→x\n2→x'
    partial='\n'.join(json.dumps(e) for e in events)
    audit=lambda raw:json.loads(claude_stream_response(raw,tmp_path))['qa_execution_audit']['reads']
    assert not audit(partial)
    assert not audit(partial+'\n'+partial)


@pytest.mark.parametrize('separator',['→','\t'])
def test_cli_number_prefix_variants_preserve_exact_indented_content(tmp_path,separator):
    path=tmp_path/'fields.json'
    path.write_text('{\n  "value": 19,\n\t"nested": {}\n}\n')
    events=[json.loads(line) for line in stream(path).splitlines()]
    returned='\n'.join(f'{n}{separator}{line}' for n,line in enumerate(path.read_text().splitlines(),1))
    events[1]['message']['content'][0]['content']=returned
    audit=lambda:json.loads(claude_stream_response('\n'.join(json.dumps(e) for e in events),tmp_path))['qa_execution_audit']['reads']
    assert audit()[0]['covered_lines']==4
    events[1]['message']['content'][0]['content']=returned.replace('19','20')
    assert not audit()


def test_cli_terminal_newline_is_optional_but_extra_content_is_rejected(tmp_path):
    path=tmp_path/'fields.json';path.write_text('{}\n')
    events=[json.loads(line) for line in stream(path).splitlines()]
    audit=lambda:json.loads(claude_stream_response('\n'.join(json.dumps(e) for e in events),tmp_path))['qa_execution_audit']['reads']
    events[1]['message']['content'][0]['content']='1\t{}\n2\t'
    assert audit()[0]['covered_lines']==1
    events[1]['message']['content'][0]['content']='1\t{}\n2\tunexpected'
    assert not audit()
    path.write_text('{}')
    events[1]['message']['content'][0]['content']='1\t{}\n2\t'
    assert not audit()
