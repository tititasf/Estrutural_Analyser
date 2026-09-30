#!/usr/bin/env python3
"""Roteador serial de QA entre CLIs autenticadas por assinatura/OAuth.

Contrato operacional:

* uma rodada pode conter varios itens, mas processa um item por vez;
* ordem fixa: Claude -> Codex -> Antigravity;
* apenas falha tecnica aciona fallback;
* ``validou`` e ``invalidou`` sao resultados validos e encerram o item;
* a sugestao de camada e somente proposta read-only, nunca apply/persistencia.

O modulo nao conhece FastAPI nem SQLite. Isso permite testar a politica de fallback
sem iniciar o portal e reutiliza-la depois no worker persistente.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol


VALID_VERDICTS = {"validou", "invalidou"}
VALID_ACTIONS = {"manter", "corrigir", "revisar_humano"}


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    effort: str | None
    executable: str
    timeout_s: int = 600


@dataclass
class Attempt:
    provider: str
    model_requested: str
    effort_requested: str | None
    started_at: float
    duration_s: float
    status: str
    failure_category: str | None = None
    error: str | None = None
    model_reported: str | None = None
    provider_version: str | None = None
    raw_response: str | None = None
    raw_response_sha256: str | None = None


@dataclass
class ItemResult:
    item: str
    layer: str
    status: str
    provider: str | None
    model: str | None
    verdict: str | None
    note: str | None
    suggestion: dict[str, Any] | None
    attempts: list[Attempt] = field(default_factory=list)
    prompt: str | None = None
    prompt_sha256: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    adapter_version: str = "qa_cli_fallback/v2"
    decision_authority: str = "PENDENTE"
    training_eligible: bool = False


@dataclass
class RoundResult:
    round_id: str
    items: list[ItemResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id,
            "items": [
                {**asdict(item), "attempts": [asdict(a) for a in item.attempts]}
                for item in self.items
            ],
        }


class TechnicalFailure(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


class ProviderInvoker(Protocol):
    config: ProviderConfig

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]: ...


def _compact_error(text: str, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(
        r'("(?:session_id|conversation_id|uuid)"\s*:\s*")[^"]+',
        r"\1<redacted>",
        text,
        flags=re.IGNORECASE,
    )
    return text[:limit]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@lru_cache(maxsize=16)
def _provider_version(executable: str) -> str | None:
    try:
        proc = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = _compact_error(proc.stdout or proc.stderr, limit=300)
    return value or None


def collect_evidence(cwd: Path, context: str) -> list[dict[str, Any]]:
    """Extrai caminhos declarados no contexto e registra proveniencia por hash."""
    evidence: list[dict[str, Any]] = []
    for line in context.splitlines():
        if not line.startswith("- "):
            continue
        label_path = line[2:].strip()
        role, sep, raw_path = label_path.partition(": ")
        if not sep:
            raw_path, role = label_path, "operational_rule"
        path = Path(raw_path)
        resolved = path if path.is_absolute() else cwd / path
        if not resolved.is_file():
            continue
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        suffix = resolved.suffix.lower()
        authority = "presentation"
        if suffix == ".png":
            authority = "visual_evidence"
        elif suffix in {".md", ".json"} and role == "operational_rule":
            authority = "governance"
        evidence.append({
            "role": role,
            "path": str(path).replace("\\", "/"),
            "sha256": digest,
            "size_bytes": resolved.stat().st_size,
            "authority": authority,
        })
    return evidence


def classify_process_failure(returncode: int, stderr: str, stdout: str) -> str:
    text = f"{stderr}\n{stdout}".lower()
    if any(x in text for x in ("not logged in", "login required", "authentication", "unauthorized", "invalid_grant")):
        return "authentication"
    if any(
        x in text
        for x in ("quota", "usage limit", "session limit", "rate limit", "capacity", "credit", "429")
    ):
        return "quota_or_rate_limit"
    if any(x in text for x in ("timed out", "timeout")):
        return "timeout"
    if any(x in text for x in ("connection", "network", "econn", "dns", "tls")):
        return "transport"
    return "process_error" if returncode else "invalid_output"


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout_s: int,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    run_kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout_s,
        "check": False,
    }
    if input_text is None:
        run_kwargs["stdin"] = subprocess.DEVNULL
    else:
        run_kwargs["input"] = input_text
    try:
        proc = subprocess.run(cmd, **run_kwargs)
    except subprocess.TimeoutExpired as exc:
        raise TechnicalFailure("timeout", f"timeout apos {timeout_s}s") from exc
    except OSError as exc:
        raise TechnicalFailure("executable", str(exc)) from exc
    if proc.returncode != 0:
        category = classify_process_failure(proc.returncode, proc.stderr, proc.stdout)
        detail = _compact_error(proc.stderr or proc.stdout or f"exit {proc.returncode}")
        raise TechnicalFailure(category, detail)
    if not proc.stdout.strip():
        raise TechnicalFailure("invalid_output", "CLI retornou stdout vazio")
    return proc


def _find_json_object(text: str) -> dict[str, Any]:
    """Extrai objeto JSON inclusive de wrappers JSON/JSONL das CLIs."""
    candidates: list[Any] = []
    stripped = text.strip()
    try:
        candidates.append(json.loads(stripped))
    except json.JSONDecodeError:
        for line in stripped.splitlines():
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def walk(value: Any) -> Iterable[Any]:
        yield value
        if isinstance(value, dict):
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
        elif isinstance(value, str) and "{" in value:
            try:
                yield json.loads(value)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", value, flags=re.DOTALL)
                if match:
                    try:
                        yield json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass

    for candidate in candidates:
        for value in walk(candidate):
            if isinstance(value, dict) and (
                str(value.get("verdict", "")).lower() in VALID_VERDICTS
                or str(value.get("status", "")).lower() == "technical_failure"
            ):
                return value

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        try:
            value = json.loads(match.group(0))
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise TechnicalFailure("invalid_output", "resposta nao contem o JSON de QA esperado")


def validate_qa_payload(payload: dict[str, Any], *, item: str, layer: str) -> dict[str, Any]:
    if str(payload.get("status", "completed")).lower() == "technical_failure":
        category = str(payload.get("failure_category") or "capability").strip().lower()
        error = str(payload.get("error") or "provedor nao conseguiu inspecionar a evidencia")
        raise TechnicalFailure(category, error)
    verdict = str(payload.get("verdict", "")).lower()
    if verdict not in VALID_VERDICTS:
        raise TechnicalFailure("invalid_output", f"verdict invalido: {verdict!r}")
    if str(payload.get("item", "")).upper() != item.upper():
        raise TechnicalFailure("invalid_output", "item da resposta difere do item solicitado")
    if str(payload.get("layer", "")).upper() != layer.upper():
        raise TechnicalFailure("invalid_output", "camada da resposta difere da camada solicitada")
    note = str(payload.get("note") or payload.get("nota") or "").strip()
    if not note:
        raise TechnicalFailure("invalid_output", "nota/justificativa ausente")
    suggestion = payload.get("suggestion") or payload.get("sugestao")
    if not isinstance(suggestion, dict):
        raise TechnicalFailure("invalid_output", "sugestao estruturada ausente")
    action = str(suggestion.get("action") or suggestion.get("acao") or "").lower()
    if action not in VALID_ACTIONS:
        raise TechnicalFailure("invalid_output", f"acao de sugestao invalida: {action!r}")
    proposed = suggestion.get("proposed", [])
    if verdict == "invalidou" and action == "corrigir" and not isinstance(proposed, list):
        raise TechnicalFailure("invalid_output", "proposed deve ser uma lista")
    return {
        "item": item,
        "layer": layer.upper(),
        "verdict": verdict,
        "note": note,
        "suggestion": suggestion,
    }


def validate_cli_wrapper(raw: str, provider: str) -> None:
    """Falha fechado quando a própria CLI declara erro no envelope."""
    try:
        wrapper = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(wrapper, dict):
        return
    if provider == "antigravity" and str(wrapper.get("status", "")).upper() == "ERROR":
        raise TechnicalFailure("process_error", str(wrapper.get("error") or "Antigravity status ERROR"))
    if provider == "claude" and wrapper.get("is_error") is True:
        status = wrapper.get("api_error_status")
        category = "quota_or_rate_limit" if status == 429 else "process_error"
        raise TechnicalFailure(category, str(wrapper.get("result") or "Claude is_error=true"))


class ClaudeInvoker:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]:
        proc = _run(
            [
                self.config.executable,
                "-p",
                prompt,
                "--output-format",
                "json",
                "--model",
                self.config.model,
                "--tools",
                "Read,Grep,Glob",
                "--permission-mode",
                "plan",
                "--no-session-persistence",
            ],
            cwd=cwd,
            timeout_s=self.config.timeout_s,
        )
        wrapper = json.loads(proc.stdout)
        model = None
        usage = wrapper.get("modelUsage") if isinstance(wrapper, dict) else None
        if isinstance(usage, dict) and usage:
            model = next(iter(usage))
        return proc.stdout, model


class CodexInvoker:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]:
        with tempfile.TemporaryDirectory(prefix="cad-qa-codex-") as tmp:
            final_path = Path(tmp) / "final.json"
            _run(
                [
                    self.config.executable,
                    "exec",
                    "-",
                    "--model",
                    self.config.model,
                    "-c",
                    f'model_reasoning_effort="{self.config.effort or "high"}"',
                    "--sandbox",
                    "read-only",
                    "--ephemeral",
                    "--color",
                    "never",
                    "--output-last-message",
                    str(final_path),
                ],
                cwd=cwd,
                timeout_s=self.config.timeout_s,
                input_text=prompt,
            )
            if not final_path.is_file():
                raise TechnicalFailure("invalid_output", "Codex nao gravou a mensagem final")
            return final_path.read_text(encoding="utf-8", errors="replace"), self.config.model


class AntigravityInvoker:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]:
        cmd = [
            self.config.executable,
            "--print",
            prompt,
            "--output-format",
            "json",
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
        proc = _run(
            cmd,
            cwd=cwd,
            timeout_s=self.config.timeout_s,
        )
        return proc.stdout, self.config.model


def default_providers(timeout_s: int = 600) -> list[ProviderInvoker]:
    return [
        ClaudeInvoker(
            ProviderConfig(
                "claude",
                os.environ.get("CAD_QA_CLAUDE_MODEL", "sonnet"),
                None,
                os.environ.get("CAD_QA_CLAUDE_BIN", shutil.which("claude") or "claude"),
                timeout_s,
            )
        ),
        CodexInvoker(
            ProviderConfig(
                "codex",
                os.environ.get("CAD_QA_CODEX_MODEL", "gpt-5.6-terra"),
                os.environ.get("CAD_QA_CODEX_EFFORT", "high"),
                os.environ.get("CAD_QA_CODEX_BIN", shutil.which("codex") or "codex"),
                timeout_s,
            )
        ),
        AntigravityInvoker(
            ProviderConfig(
                "antigravity",
                os.environ.get("CAD_QA_ANTIGRAVITY_MODEL", "gemini-3.6-flash"),
                os.environ.get("CAD_QA_ANTIGRAVITY_EFFORT", "medium"),
                os.environ.get("CAD_QA_ANTIGRAVITY_BIN", shutil.which("agy") or "agy"),
                timeout_s,
            )
        ),
    ]


def build_item_prompt(*, item: str, layer: str, context: str) -> str:
    schema = {
        "status": "completed",
        "item": item,
        "layer": layer.upper(),
        "verdict": "validou|invalidou",
        "note": "justificativa curta baseada em evidencia",
        "suggestion": {
            "action": "manter|corrigir|revisar_humano",
            "target_layer": layer.upper(),
            "summary": "o que a camada deve representar",
            "proposed": [
                {
                    "label": "1",
                    "role": "face_A_chega",
                    "points": [[0, 0], [1, 1]],
                    "note": "somente quando houver evidencia geometrica",
                }
            ],
        },
    }
    return f"""Voce e o revisor agentico de PIL/SA-N1 do CAD-ANALYZER.
Item: {item}. Camada atual: {layer.upper()}.

Regras obrigatorias:
- Leia e respeite CLAUDE.md e os documentos citados no contexto.
- Julgue a camada pedida; nao use um FAIL legitimo como falha tecnica.
- N2/N4 sao apenas comparadores e nunca podem alimentar N1/N3.
- Nao grave ou edite arquivos. A sugestao e somente uma proposta read-only.
- Se uma ferramenta, arquivo ou imagem obrigatoria estiver inacessivel, isso NAO e
  invalidacao de engenharia. Responda somente com
  {{"status":"technical_failure","failure_category":"capability","error":"motivo"}}
  para permitir fallback ao proximo provedor.
- Se invalidar, proponha apenas mudancas sustentadas por evidencia; se a prova faltar,
  use revisar_humano. Se validar, use manter e proposed vazio.
- Responda exclusivamente com um objeto JSON no schema abaixo.

Contexto e caminhos de evidencia:
{context}

Schema esperado:
{json.dumps(schema, ensure_ascii=False)}
"""


def run_round(
    *,
    round_id: str,
    items: Iterable[str],
    layer: str,
    cwd: Path,
    context_for_item: Callable[[str], str],
    providers: Iterable[ProviderInvoker] | None = None,
) -> RoundResult:
    provider_list = list(providers or default_providers())
    results: list[ItemResult] = []
    for raw_item in items:
        item = raw_item.strip().upper()
        attempts: list[Attempt] = []
        final: ItemResult | None = None
        context = context_for_item(item)
        prompt = build_item_prompt(item=item, layer=layer, context=context)
        evidence = collect_evidence(cwd, context)
        for provider in provider_list:
            started = time.time()
            raw: str | None = None
            provider_version = _provider_version(provider.config.executable)
            try:
                raw, model_reported = provider.invoke(prompt, cwd)
                validate_cli_wrapper(raw, provider.config.name)
                payload = validate_qa_payload(_find_json_object(raw), item=item, layer=layer)
            except TechnicalFailure as exc:
                detail = str(exc)
                if exc.category == "invalid_output" and raw:
                    detail = f"{detail}; raw={_compact_error(raw)}"
                attempts.append(
                    Attempt(
                        provider.config.name,
                        provider.config.model,
                        provider.config.effort,
                        started,
                        round(time.time() - started, 3),
                        "technical_failure",
                        exc.category,
                        _compact_error(detail),
                        provider_version=provider_version,
                        raw_response=_compact_error(raw, 50_000) if raw else None,
                        raw_response_sha256=_sha256_text(raw) if raw else None,
                    )
                )
                continue
            except (ValueError, json.JSONDecodeError) as exc:
                attempts.append(
                    Attempt(
                        provider.config.name,
                        provider.config.model,
                        provider.config.effort,
                        started,
                        round(time.time() - started, 3),
                        "technical_failure",
                        "invalid_output",
                        _compact_error(str(exc)),
                        provider_version=provider_version,
                        raw_response=_compact_error(raw, 50_000) if raw else None,
                        raw_response_sha256=_sha256_text(raw) if raw else None,
                    )
                )
                continue
            attempts.append(
                Attempt(
                    provider.config.name,
                    provider.config.model,
                    provider.config.effort,
                    started,
                    round(time.time() - started, 3),
                    "completed",
                    model_reported=model_reported,
                    provider_version=provider_version,
                    raw_response=_compact_error(raw, 50_000),
                    raw_response_sha256=_sha256_text(raw),
                )
            )
            final = ItemResult(
                item,
                layer.upper(),
                "completed",
                provider.config.name,
                model_reported or provider.config.model,
                payload["verdict"],
                payload["note"],
                payload["suggestion"],
                attempts,
            )
            break
        if final is None:
            final = ItemResult(
                item,
                layer.upper(),
                "failed",
                None,
                None,
                None,
                None,
                None,
                attempts,
            )
        final.prompt = prompt
        final.prompt_sha256 = _sha256_text(prompt)
        final.evidence = evidence
        results.append(final)
    return RoundResult(round_id, results)
