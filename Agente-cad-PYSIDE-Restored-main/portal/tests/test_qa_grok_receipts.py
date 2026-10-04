import json

import pytest

from scripts.arete import qa_cli_fallback as base


def _use(call, path, offset=None):
    args = {'target_file': str(path)}
    if offset:
        args['offset'] = offset
    return {'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'id': call, 'name': 'read_file', 'input': args}]}}


def _result(call, payload):
    return {'type': 'user', 'message': {'content': [
        {'type': 'tool_result', 'tool_use_id': call, 'content': json.dumps(payload), 'is_error': False}]}}


def _page(text, offset=None):
    return {'type': 'ReadFile', 'FileContent': {'raw_output': text, 'offset': offset}}


FINAL = {'type': 'result', 'is_error': False, 'result': '{"verdict":"validou"}',
         'modelUsage': {'grok-4.6-build': {'outputTokens': 10}}}


def _stream(*events):
    return '\n'.join(json.dumps(e) for e in [*events, FINAL])


def test_paged_text_read_is_receipted_only_when_complete_and_exact(tmp_path):
    lines = [f'linha {i}' for i in range(1, 1501)]
    (tmp_path / 'f.json').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    first = '\n'.join(lines[:1000]) + '\n'
    rest = '\n'.join(lines[1000:]) + '\n'
    only_first = json.loads(base.grok_stream_response(_stream(_use('a', tmp_path / 'f.json'), _result('a', _page(first))), tmp_path))
    [partial] = only_first['qa_execution_audit']['reads']
    assert partial['complete'] is False and partial['covered_lines'] == 1000
    full = json.loads(base.grok_stream_response(_stream(
        _use('a', tmp_path / 'f.json'), _result('a', _page(first)),
        _use('b', tmp_path / 'f.json', 1001), _result('b', _page(rest, 1001))), tmp_path))
    audit = full['qa_execution_audit']
    assert audit['origin'] == 'grok_stream' and audit['reads'][0]['covered_lines'] == 1500
    assert audit['reads'][0]['complete'] is True
    forged = json.loads(base.grok_stream_response(_stream(
        _use('a', tmp_path / 'f.json'), _result('a', _page(first.replace('linha 7', 'linha X'))),
        _use('b', tmp_path / 'f.json', 1001), _result('b', _page(rest, 1001))), tmp_path))
    assert [r['complete'] for r in forged['qa_execution_audit']['reads']] == [False]


def test_partial_read_never_satisfies_mandatory_manual_but_full_bundle_does(tmp_path):
    from portal.app import qa_review_contract as contract
    import hashlib
    folder = tmp_path / 'round'
    folder.mkdir()
    manual = 'docs/M.md'
    (tmp_path / 'docs').mkdir()
    (tmp_path / manual).write_text('regra 1\nregra 2\n', encoding='utf-8')
    (folder / 'rules.json').write_text(json.dumps({'available': [manual]}), encoding='utf-8')
    (folder / contract.NORMAS).write_text(contract.rules_bundle(tmp_path, [manual]), encoding='utf-8')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    bundle_rel = 'round/' + contract.NORMAS
    full = {bundle_rel: {'complete': True, 'sha256': sha(folder / contract.NORMAS)}}
    assert contract._bundled_rules(full, folder, tmp_path) == {manual}
    half = {bundle_rel: {'complete': False, 'sha256': sha(folder / contract.NORMAS)}}
    assert contract._bundled_rules(half, folder, tmp_path) == set()
    (tmp_path / manual).write_text('regra 1\nregra 2 mudou\n', encoding='utf-8')
    assert contract._bundled_rules(full, folder, tmp_path) == set()


def test_verdict_found_despite_prose_or_trailing_brace():
    wrapper = {'type': 'result', 'result': 'Vou emitir.\n{"verdict":"invalidou","item":"P1"}\n}'}
    assert base._find_json_object(json.dumps(wrapper))['verdict'] == 'invalidou'


def test_image_needs_tool_image_content(tmp_path):
    (tmp_path / 's.png').write_bytes(b'\x89PNG fake')
    ok = json.loads(base.grok_stream_response(_stream(
        _use('a', tmp_path / 's.png'), _result('a', {'type': 'ReadFile', 'ImageContent': {'data': 'abc'}})), tmp_path))
    assert [r['path'] for r in ok['qa_execution_audit']['reads']] == ['s.png']
    claimed = json.loads(base.grok_stream_response(_stream(_use('a', tmp_path / 's.png')), tmp_path))
    assert claimed['qa_execution_audit']['reads'] == []


def test_error_wrapper_is_quota_or_process_failure(tmp_path):
    with pytest.raises(base.TechnicalFailure) as exc:
        base.validate_cli_wrapper(json.dumps({'is_error': True, 'result': 'Rate limit reached (429)'}), 'grok')
    assert exc.value.category == 'quota_or_rate_limit'
    with pytest.raises(base.TechnicalFailure) as exc:
        base.grok_stream_response('{"type":"assistant","message":{"content":[]}}', tmp_path)
    assert exc.value.category == 'invalid_output'
