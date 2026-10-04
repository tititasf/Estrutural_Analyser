"""Haiku é proibido no QA (dono 2026-10-03): papel auxiliar vai para o modelo pedido; uso com Haiku falha."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.arete import qa_cli_fallback as a


def _invoker():
    return a.ClaudeInvoker(a.ProviderConfig("claude", "claude-sonnet-5-5", None, "claude", 60))


def _fake_run(usage, capturado):
    def run(cmd, *, cwd, timeout_s, input_text=None, env=None):
        capturado["env"] = env
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": "{}", "modelUsage": usage}), "")
    return run


def test_tarefas_auxiliares_usam_o_modelo_pedido(monkeypatch):
    capturado = {}
    monkeypatch.setattr(a, "_run", _fake_run({"claude-sonnet-5-5": {"outputTokens": 4}}, capturado))
    _, model = _invoker().invoke("p", Path("."))
    assert model == "claude-sonnet-5-5"
    for var in ("ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
        assert capturado["env"][var] == "claude-sonnet-5-5"


def test_resposta_com_haiku_e_falha_tecnica(monkeypatch):
    usage = {"claude-haiku-4-5-20251001": {"outputTokens": 15}, "claude-sonnet-5-5": {"outputTokens": 4}}
    monkeypatch.setattr(a, "_run", _fake_run(usage, {}))
    with pytest.raises(a.TechnicalFailure) as exc:
        _invoker().invoke("p", Path("."))
    assert exc.value.category == "model_mismatch"
