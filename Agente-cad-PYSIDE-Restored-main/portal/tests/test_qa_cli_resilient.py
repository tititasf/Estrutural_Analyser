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

