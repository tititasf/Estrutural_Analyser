"""Adaptação resiliente do provedor Antigravity para o QA do portal.

Algumas versões do ``agy`` devolvem uma resposta final válida no envelope JSON e,
em seguida, encerram com erro de transporte do sandbox. O veredito só é recuperado
quando o objeto interno passa pelo mesmo parser e validação falha-fechada do adapter
canônico; saídas parciais continuam sendo falha técnica.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

from scripts.arete import qa_cli_fallback as base


ProviderInvoker = base.ProviderInvoker


def _recover_valid_response(stdout: str) -> str | None:
    try:
        payload = base._find_json_object(stdout)
    except base.TechnicalFailure:
        return None
    if str(payload.get("verdict", "")).lower() not in base.VALID_VERDICTS:
        return None
    return json.dumps(payload, ensure_ascii=False)


class ResilientAntigravityInvoker:
    def __init__(self, config: base.ProviderConfig):
        self.config = config

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]:
        cmd = [
            self.config.executable,
            "--print",
            prompt,
            "--output-format",
            "stream-json",
            "--model",
            self.config.model,
            "--mode",
            "plan",
            "--sandbox",
            "--dangerously-skip-permissions",
            "--disable-slash-commands",
        ]
        if self.config.effort:
            cmd.extend(("--effort", self.config.effort))
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout_s,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            raise base.TechnicalFailure("timeout", f"timeout apos {self.config.timeout_s}s") from exc
        except OSError as exc:
            raise base.TechnicalFailure("executable", str(exc)) from exc

        # Preserve tool receipts even when sandbox shutdown returns nonzero.
        # A legacy final JSON alone cannot prove the required evidence reads.
        if proc.stdout.strip():
            try:
                recovered, model = base.antigravity_stream_response(proc.stdout, cwd)
                payload = base._find_json_object(recovered)
                if str(payload.get("verdict", "")).lower() in base.VALID_VERDICTS:
                    return recovered, model or self.config.model
            except base.TechnicalFailure:
                pass
        if proc.returncode != 0:
            category = base.classify_process_failure(proc.returncode, proc.stderr, proc.stdout)
            detail = base._compact_error(proc.stderr or proc.stdout or f"exit {proc.returncode}")
            raise base.TechnicalFailure(category, detail)
        if not proc.stdout.strip():
            raise base.TechnicalFailure("invalid_output", "CLI retornou stdout vazio")
        raise base.TechnicalFailure("invalid_output", "CLI sem resposta final auditável")


# Ordem viva da fila de CLIs. Claude fica fora por decisão do dono (03/10/2026):
# a cota dele é do trabalho interativo. Reativar via CAD_QA_PROVIDERS no env do serviço.
DEFAULT_ORDER = "antigravity,grok,codex"


def default_providers(timeout_s: int = 600) -> list[ProviderInvoker]:
    available = {provider.config.name: provider for provider in base.default_providers(timeout_s)}
    order = [name.strip() for name in os.environ.get("CAD_QA_PROVIDERS", DEFAULT_ORDER).split(",") if name.strip()]
    providers = [available[name] for name in order if name in available]
    if not providers:
        raise ValueError(f"CAD_QA_PROVIDERS sem CLI conhecida: {order}; disponíveis: {sorted(available)}")
    return [
        ResilientAntigravityInvoker(provider.config)
        if provider.config.name == "antigravity" else provider
        for provider in providers
    ]


def run_round(*, providers: Iterable[ProviderInvoker] | None = None, **kwargs):
    return base.run_round(
        providers=providers if providers is not None else default_providers(),
        **kwargs,
    )

