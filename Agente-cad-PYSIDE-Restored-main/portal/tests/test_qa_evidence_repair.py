from types import SimpleNamespace

import pytest

from portal.app.qa_jobs import _invoke_with_evidence_repair
from scripts.arete.qa_cli_fallback import TechnicalFailure


def test_repair_returns_validated_response_and_preserves_rejection():
    calls, rejected = [], []
    def invoke(prompt, cwd):
        calls.append(prompt)
        return ('unsupported' if len(calls) == 1 else 'uncertain'), 'gemini'
    def validate(raw):
        if raw == 'unsupported':
            raise ValueError('identidade_contorno: aprovaÃ§Ã£o apoiada apenas no payload SA')
        return 'validated ' + raw
    result = _invoke_with_evidence_repair(SimpleNamespace(invoke=invoke), 'original contract', '.',
                                        validate, lambda *args: rejected.append(args))
    assert result == ('validated uncertain', 'gemini')
    assert len(rejected) == 1 and rejected[0][0] == 'unsupported'
    assert calls[1].startswith('original contract')
    assert 'identidade_contorno' in calls[1] and 'inventadas' in calls[1]


def test_repair_is_bounded_and_never_suppresses_invalid_output():
    calls = []
    def invoke(prompt, cwd):
        calls.append(prompt)
        return 'bad', 'gemini'
    def validate(raw):
        raise ValueError('missing proof')
    with pytest.raises(TechnicalFailure, match='missing proof'):
        _invoke_with_evidence_repair(SimpleNamespace(invoke=invoke), 'contract', '.', validate, lambda *args: None)
    assert len(calls) == 2


def test_authentication_failure_is_not_retried():
    calls = []
    def invoke(prompt, cwd):
        calls.append(prompt)
        raise TechnicalFailure('authentication', 'login needed')
    with pytest.raises(TechnicalFailure, match='login needed'):
        _invoke_with_evidence_repair(SimpleNamespace(invoke=invoke), 'contract', '.', lambda raw: raw, lambda *args: None)
    assert len(calls) == 1
