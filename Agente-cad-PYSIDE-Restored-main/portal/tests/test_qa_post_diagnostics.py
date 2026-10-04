from scripts.arete.qa_cli_fallback import Attempt, ItemResult
from portal.app.qa_jobs import _post_review_record


def test_failed_post_keeps_provider_reason_and_stays_failed():
    attempt = Attempt('antigravity','gemini',None,0,20,'technical_failure',
                      'invalid_output','missing final JSON',raw_response='private response',
                      raw_response_sha256='response-hash')
    post = ItemResult('P1','L1','failed',None,None,None,None,None,[attempt],
                      prompt_sha256='prompt-hash')
    record = _post_review_record(post)
    assert record['status'] == 'failed' and record['verdict'] is None
    assert 'missing final JSON' in record['note']
    assert record['attempts'][0]['failure_category'] == 'invalid_output'
    assert record['attempts'][0]['raw_response_sha256'] == 'response-hash'
    assert 'raw_response' not in record['attempts'][0]
    assert record['prompt_sha256'] == 'prompt-hash'


def test_post_opinion_is_preserved_without_inventing_diagnostic():
    post = ItemResult('L301','L1','completed','antigravity','gemini','validou',
                      'supported opinion',{'assessment':'pass','confidence_percent':90})
    record = _post_review_record(post)
    assert record['note'] == 'supported opinion'
    assert record['assessment'] == 'pass'
    assert record['confidence_percent'] == 90
    assert record['attempts'] == []
