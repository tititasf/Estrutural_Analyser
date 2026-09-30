from __future__ import annotations

import json
from pathlib import Path

from scripts.arete.qa_cli_fallback import (
    ProviderConfig,
    TechnicalFailure,
    run_round,
)


class FakeProvider:
    def __init__(self, name, outcome, model=None):
        self.config = ProviderConfig(name, model or f"{name}-model", "high", name, 1)
        self.outcome = outcome
        self.calls = []

    def invoke(self, prompt: str, cwd: Path):
        self.calls.append((prompt, cwd))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return json.dumps(self.outcome), self.config.model


def payload(item: str, verdict: str = "validou"):
    return {
        "item": item,
        "layer": "L1",
        "verdict": verdict,
        "note": "evidencia suficiente",
        "suggestion": {
            "action": "manter" if verdict == "validou" else "corrigir",
            "target_layer": "L1",
            "summary": "proposta L1",
            "proposed": [] if verdict == "validou" else [{"role": "face_A_chega"}],
        },
    }


def test_validou_nao_aciona_fallback(tmp_path):
    claude = FakeProvider("claude", payload("P9", "validou"))
    codex = FakeProvider("codex", payload("P9", "invalidou"))
    result = run_round(
        round_id="r1", items=["P9"], layer="L1", cwd=tmp_path,
        context_for_item=lambda _: "contexto", providers=[claude, codex],
    )
    assert result.items[0].verdict == "validou"
    assert result.items[0].provider == "claude"
    assert len(claude.calls) == 1
    assert codex.calls == []


def test_invalidou_e_resultado_valido_sem_fallback(tmp_path):
    claude = FakeProvider("claude", payload("P9", "invalidou"))
    codex = FakeProvider("codex", payload("P9"))
    result = run_round(
        round_id="r2", items=["P9"], layer="L1", cwd=tmp_path,
        context_for_item=lambda _: "contexto", providers=[claude, codex],
    )
    assert result.items[0].verdict == "invalidou"
    assert result.items[0].suggestion["action"] == "corrigir"
    assert codex.calls == []


def test_falha_tecnica_pula_para_codex(tmp_path):
    claude = FakeProvider("claude", TechnicalFailure("quota_or_rate_limit", "limit"))
    codex = FakeProvider("codex", payload("P9"), "gpt-5.6-terra")
    result = run_round(
        round_id="r3", items=["P9"], layer="L1", cwd=tmp_path,
        context_for_item=lambda _: "contexto", providers=[claude, codex],
    )
    item = result.items[0]
    assert item.provider == "codex"
    assert [a.status for a in item.attempts] == ["technical_failure", "completed"]
    assert item.attempts[0].failure_category == "quota_or_rate_limit"


def test_duas_falhas_pulam_para_antigravity(tmp_path):
    providers = [
        FakeProvider("claude", TechnicalFailure("authentication", "login")),
        FakeProvider("codex", TechnicalFailure("timeout", "timeout")),
        FakeProvider("antigravity", payload("P9"), "gemini-3.6-flash"),
    ]
    result = run_round(
        round_id="r4", items=["P9"], layer="L1", cwd=tmp_path,
        context_for_item=lambda _: "contexto", providers=providers,
    )
    assert result.items[0].provider == "antigravity"
    assert len(result.items[0].attempts) == 3


def test_falha_de_capacidade_declarada_pelo_modelo_aciona_fallback(tmp_path):
    claude = FakeProvider(
        "claude",
        {
            "status": "technical_failure",
            "failure_category": "capability",
            "error": "imagem indisponivel",
        },
    )
    codex = FakeProvider("codex", payload("P9"))
    result = run_round(
        round_id="r-cap",
        items=["P9"],
        layer="L1",
        cwd=tmp_path,
        context_for_item=lambda _: "contexto",
        providers=[claude, codex],
    )
    assert result.items[0].provider == "codex"
    assert result.items[0].attempts[0].failure_category == "capability"


def test_envelope_error_da_cli_nao_vira_resultado_treinavel(tmp_path):
    antigravity = FakeProvider(
        "antigravity",
        {
            "status": "ERROR",
            "error": "sandbox reset",
            "response": json.dumps(payload("P9")),
        },
    )
    result = run_round(
        round_id="r-wrapper", items=["P9"], layer="L1", cwd=tmp_path,
        context_for_item=lambda _: "contexto", providers=[antigravity],
    )
    assert result.items[0].status == "failed"
    assert result.items[0].training_eligible is False
    assert result.items[0].attempts[0].failure_category == "process_error"


def test_rodada_multi_item_continua_serialmente(tmp_path):
    provider = FakeProvider("claude", payload("P9"))

    class PerItem:
        config = provider.config

        def invoke(self, prompt, cwd):
            item = "P9" if "Item: P9." in prompt else "P10"
            return json.dumps(payload(item)), "claude-sonnet"

    result = run_round(
        round_id="r5", items=["P9", "P10"], layer="L1", cwd=tmp_path,
        context_for_item=lambda item: f"evidencia {item}", providers=[PerItem()],
    )
    assert [item.item for item in result.items] == ["P9", "P10"]
    assert all(item.status == "completed" for item in result.items)


def test_todos_falham_fecha_item_com_auditoria(tmp_path):
    providers = [
        FakeProvider("claude", TechnicalFailure("quota_or_rate_limit", "limit")),
        FakeProvider("codex", TechnicalFailure("authentication", "login")),
        FakeProvider("antigravity", TechnicalFailure("transport", "network")),
    ]
    result = run_round(
        round_id="r6", items=["P9"], layer="L1", cwd=tmp_path,
        context_for_item=lambda _: "contexto", providers=providers,
    )
    item = result.items[0]
    assert item.status == "failed"
    assert item.verdict is None
    assert [a.provider for a in item.attempts] == ["claude", "codex", "antigravity"]
