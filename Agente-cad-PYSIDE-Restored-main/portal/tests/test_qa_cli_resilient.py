from __future__ import annotations

import json

from scripts.arete.qa_cli_resilient import _recover_valid_response


def test_recupera_resposta_qa_valida_de_envelope_de_erro():
    qa = {
        "status": "completed",
        "item": "V301",
        "layer": "L1",
        "verdict": "validou",
        "confidence_percent": 95,
        "note": "evidencia suficiente",
        "suggestion": {"action": "manter", "target_layer": "L1", "proposed": []},
    }
    wrapper = {"status": "ERROR", "response": f"```json\n{json.dumps(qa)}\n```", "error": "reset"}
    recovered = json.loads(_recover_valid_response(json.dumps(wrapper)))
    assert recovered == qa


def test_nao_recupera_resposta_incompleta():
    wrapper = {"status": "ERROR", "response": "analise interrompida", "error": "reset"}
    assert _recover_valid_response(json.dumps(wrapper)) is None


def test_fila_preserva_leitura_real_mesmo_com_erro_de_transporte(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts.arete import qa_cli_resilient as module
    evidence = tmp_path / 'source.png'
    evidence.write_bytes(b'fixture')
    qa = {'verdict': 'validou', 'item': 'L301', 'layer': 'L1'}
    events = [
        {'event': 'init', 'init': {'model': 'gemini-test'}},
        {'event': 'step_update', 'step_update': {'state': 'DONE', 'tool_name': 'view_file',
         'tool_info': {'parameters': {'AbsolutePath': str(evidence)}}}},
        {'event': 'result', 'result': {'status': 'ERROR', 'response': json.dumps(qa)}},
    ]
    def run(cmd, **kwargs):
        assert cmd[cmd.index('--output-format') + 1] == 'stream-json'
        return SimpleNamespace(returncode=1, stdout='\n'.join(map(json.dumps, events)), stderr='reset')
    monkeypatch.setattr(module.subprocess, 'run', run)
    config = module.base.ProviderConfig('antigravity', 'gemini-test', None, 'agy', 10)
    raw, model = module.ResilientAntigravityInvoker(config).invoke('review', tmp_path)
    audit = json.loads(raw)['qa_execution_audit']
    assert model == 'gemini-test'
    assert audit['reads'][0]['path'] == 'source.png'
    assert not audit['proves_comprehension']


def test_fila_recusa_json_sem_eventos_auditaveis(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from scripts.arete import qa_cli_resilient as module
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout='{"verdict":"validou"}', stderr=''))
    config = module.base.ProviderConfig('antigravity', 'gemini-test', None, 'agy', 10)
    with pytest.raises(module.base.TechnicalFailure):
        module.ResilientAntigravityInvoker(config).invoke('review', tmp_path)

