#!/usr/bin/env python3
"""Roteador serial de QA entre CLIs autenticadas por assinatura/OAuth.

Contrato operacional:

* uma rodada pode conter varios itens, mas processa um item por vez;
* ordem fixa: Gemini (Antigravity) -> Claude -> Codex;
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
    env: dict[str, str] | None = None,
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
    if env is not None:
        run_kwargs["env"] = env
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
                # Texto antes do JSON ou chave sobrando depois dele (visto no Grok):
                # decodifica cada objeto completo a partir de cada "{", sem alterá-lo.
                decoder = json.JSONDecoder()
                for match in re.finditer(r"\{", value):
                    try:
                        obj, _ = decoder.raw_decode(value, match.start())
                    except json.JSONDecodeError:
                        continue
                    if isinstance(obj, dict) and "verdict" in obj:
                        yield obj
                        break

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
    try:
        confidence = float(payload.get("confidence_percent"))
    except (TypeError, ValueError) as exc:
        raise TechnicalFailure("invalid_output", "confidence_percent deve ser numerico") from exc
    if not 0 <= confidence <= 100:
        raise TechnicalFailure("invalid_output", "confidence_percent deve estar entre 0 e 100")
    suggestion = dict(suggestion)
    suggestion["confidence_percent"] = round(confidence, 1)
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
    if provider in ("claude", "grok") and wrapper.get("is_error") is True:
        status = wrapper.get("api_error_status")
        text = str(wrapper.get("result") or f"{provider} is_error=true")
        limited = status == 429 or any(k in text.lower() for k in ("429", "rate limit", "quota", "usage limit"))
        raise TechnicalFailure("quota_or_rate_limit" if limited else "process_error", text)


def claude_stream_response(raw: str, cwd: Path) -> str:
    """Record successful Read calls, joined to their CLI tool results by ID.

    Text receipts require complete coverage from actual numbered Read results;
    several pages may cover a large file, but gaps and truncated lines fail.
    Access never proves comprehension.
    """
    pending, reads, coverage, final = {}, {}, {}, None
    root = cwd.resolve()
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'result':
            final = event
        content = (event.get('message') or {}).get('content', [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if event.get('type') == 'assistant' and block.get('type') == 'tool_use' and block.get('name') == 'Read':
                args = block.get('input') or {}
                if isinstance(args, dict) and args.get('file_path'):
                    pending[block.get('id')] = args
            if event.get('type') != 'user' or block.get('type') != 'tool_result':
                continue
            args = pending.pop(block.get('tool_use_id'), None)
            result = block.get('content')
            if not args or block.get('is_error') or not result or '<tool_use_error>' in str(result):
                continue
            try:
                p = Path(args['file_path'])
                p = (p if p.is_absolute() else root / p).resolve()
                rel = str(p.relative_to(root)).replace('\\', '/')
                if p.is_file():
                    if args.get('pages'):
                        continue
                    offset, limit = args.get('offset', 1), args.get('limit', 2000)
                    if (not isinstance(offset, int) or isinstance(offset, bool) or offset < 1
                            or not isinstance(limit, int) or isinstance(limit, bool) or limit < 1):
                        continue
                    digest = hashlib.sha256(p.read_bytes()).hexdigest()
                    if p.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
                        file_text = p.read_text(encoding='utf-8')
                        lines = file_text.splitlines()
                        if not lines or any(len(line) > 2000 for line in lines):
                            continue
                        text = result if isinstance(result, str) else '\n'.join(
                            part.get('text', '') for part in result if isinstance(part, dict)
                            and part.get('type') == 'text') if isinstance(result, list) else ''
                        returned = []
                        invalid = False
                        # CLI releases use either an arrow or a tab after the line number.
                        # Only that prefix varies; the returned file content must match exactly.
                        for number, actual in re.findall(r'^[ \t]*(\d+)(?:→|\t)([^\n]*)$', text, re.MULTILINE):
                            number = int(number)
                            # Read can expose the terminal newline as one extra empty line.
                            if (number == len(lines)+1 and actual == '' and file_text.endswith('\n')
                                    and offset <= number < offset+limit):
                                continue
                            if (number < offset or number >= offset+limit or number > len(lines)
                                    or actual.rstrip('\r') != lines[number-1]):
                                invalid = True
                                break
                            returned.append(number)
                        if invalid or not returned or returned != list(range(returned[0],returned[-1]+1)):
                            continue
                        entry = coverage.setdefault((rel,digest), {'lines':set(), 'ids':[]})
                        entry['lines'].update(returned)
                        entry['ids'].append(block.get('tool_use_id'))
                        if entry['lines'] != set(range(1,len(lines)+1)):
                            continue
                        reads[rel] = {'path':rel, 'sha256':digest, 'tool':'Read',
                                      'tool_use_ids':entry['ids'], 'covered_lines':len(lines)}
                    elif offset == 1:
                        reads[rel] = {'path':rel, 'sha256':digest,
                                      'tool':'Read', 'tool_use_id':block.get('tool_use_id')}
            except (OSError, ValueError, TypeError, UnicodeError):
                continue
    if final is None:
        # Legacy envelopes remain parseable, but contain no accepted access audit.
        try:
            legacy = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TechnicalFailure('invalid_output', 'Claude sem evento final auditável') from exc
        if not isinstance(legacy, dict) or 'result' not in legacy:
            raise TechnicalFailure('invalid_output', 'Claude sem evento final auditável')
        legacy.pop('qa_execution_audit', None)
        return json.dumps(legacy, ensure_ascii=False)
    final = dict(final)
    final['qa_execution_audit'] = {'schema':'cad.cli_read_receipts/v1',
        'origin':'claude_stream', 'stream_sha256':_sha256_text(raw),
        'reads':list(reads.values()), 'proves_comprehension':False}
    return json.dumps(final, ensure_ascii=False)


class ClaudeInvoker:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def _env_sem_modelo_auxiliar(self) -> dict[str, str]:
        # O CLI usa Haiku nas tarefas auxiliares; aqui todo papel vai para o modelo pedido.
        env = dict(os.environ)
        for var in ("ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
                    "CLAUDE_CODE_SUBAGENT_MODEL"):
            env[var] = self.config.model
        return env

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]:
        proc = _run(
            [
                self.config.executable,
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--verbose",
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
            env=self._env_sem_modelo_auxiliar(),
        )
        raw = claude_stream_response(proc.stdout, cwd)
        wrapper = json.loads(raw)
        model = None
        usage = wrapper.get("modelUsage") if isinstance(wrapper, dict) else None
        if isinstance(usage, dict) and usage:
            # Haiku proibido no QA (dono 2026-10-03): resposta com ele não vale.
            proibidos = [m for m in usage if "haiku" in m.lower()]
            if proibidos:
                raise TechnicalFailure("model_mismatch", f"modelo proibido no QA: {', '.join(proibidos)}")
            if self.config.model in usage:
                model = self.config.model
            else:
                model = max(usage, key=lambda m: (usage[m] or {}).get("outputTokens", 0)
                            if isinstance(usage[m], dict) else 0)
        return raw, model


IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


def grok_stream_response(raw: str, cwd: Path) -> str:
    """Record read_file results of the Grok CLI, joined to their tool calls by ID.

    Text receipts require the returned raw_output pages to equal the real file
    lines and to cover all of them; images require ImageContent from the tool.
    Access never proves comprehension.
    """
    pending, reads, coverage, final = {}, {}, {}, None
    root = cwd.resolve()
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'result':
            final = event
        content = (event.get('message') or {}).get('content', [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if event.get('type') == 'assistant' and block.get('type') == 'tool_use' and block.get('name') == 'read_file':
                args = block.get('input') or {}
                if isinstance(args, dict) and args.get('target_file'):
                    pending[block.get('id')] = args
            if event.get('type') != 'user' or block.get('type') != 'tool_result':
                continue
            args = pending.pop(block.get('tool_use_id'), None)
            if not args or block.get('is_error'):
                continue
            try:
                result = json.loads(block.get('content'))
                p = Path(args['target_file'])
                p = (p if p.is_absolute() else root / p).resolve()
                rel = str(p.relative_to(root)).replace('\\', '/')
                if not p.is_file():
                    continue
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
                if p.suffix.lower() in IMAGE_SUFFIXES:
                    if (result.get('ImageContent') or {}).get('data'):
                        reads[rel] = {'path':rel, 'sha256':digest, 'tool':'read_file',
                                      'tool_use_id':block.get('tool_use_id')}
                    continue
                page = result.get('FileContent') or {}
                returned = str(page.get('raw_output') or '').splitlines()
                offset = page.get('offset') or 1
                lines = p.read_text(encoding='utf-8').splitlines()
                if (not returned or not isinstance(offset, int) or isinstance(offset, bool) or offset < 1
                        or lines[offset-1:offset-1+len(returned)] != returned):
                    continue
                entry = coverage.setdefault((rel, digest), {'lines':set(), 'ids':[]})
                entry['lines'].update(range(offset, offset+len(returned)))
                entry['ids'].append(block.get('tool_use_id'))
                # Página exata e parcial = acesso ao trecho (pode ser citado);
                # só a cobertura total vale como leitura obrigatória (complete).
                reads[rel] = {'path':rel, 'sha256':digest, 'tool':'read_file',
                              'tool_use_ids':list(entry['ids']), 'covered_lines':len(entry['lines']),
                              'total_lines':len(lines),
                              'complete':entry['lines'] >= set(range(1, len(lines)+1))}
            except (OSError, ValueError, TypeError, UnicodeError, AttributeError):
                continue
    if final is None:
        raise TechnicalFailure('invalid_output', 'Grok sem evento final auditável')
    final = dict(final)
    final['qa_execution_audit'] = {'schema':'cad.cli_read_receipts/v1',
        'origin':'grok_stream', 'stream_sha256':_sha256_text(raw),
        'reads':list(reads.values()), 'proves_comprehension':False}
    return json.dumps(final, ensure_ascii=False)


class GrokInvoker:
    """Grok Build CLI (OAuth do dono na VPS), somente leitura e sem subagentes."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    def invoke(self, prompt: str, cwd: Path) -> tuple[str, str | None]:
        cmd = [
            self.config.executable,
            "-p",
            prompt,
            "-m",
            self.config.model,
            "--output-format",
            "streaming-messages-json",
            "--permission-mode",
            "plan",
            "--tools",
            "read_file,list_dir,grep",
            "--no-subagents",
            "--disable-web-search",
        ]
        if self.config.effort:
            cmd.extend(("--reasoning-effort", self.config.effort))
        proc = _run(cmd, cwd=cwd, timeout_s=self.config.timeout_s)
        raw = grok_stream_response(proc.stdout, cwd)
        usage = json.loads(raw).get("modelUsage")
        model = None
        if isinstance(usage, dict) and usage:
            model = max(usage, key=lambda m: (usage[m] or {}).get("outputTokens", 0)
                        if isinstance(usage[m], dict) else 0)
            # A CLI reporta a variante "-build" do modelo pedido; outro modelo
            # (inclusive o "-build-fast" do mesmo número) não vale.
            if model not in (self.config.model, self.config.model + "-build"):
                raise TechnicalFailure("model_mismatch", f"Grok respondeu com {model}, pedido {self.config.model}")
        return raw, model


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


def antigravity_stream_response(raw: str, cwd: Path) -> tuple[str, str | None]:
    """Retain CLI-origin read receipts, never the model's claim that it read PNG.

    Receipts prove tool access, not comprehension or correctness. Only completed
    view_file reads within the repository are recorded; arbitrary command output
    is deliberately excluded from the response persisted by the portal.
    """
    final = None
    model = None
    reads = {}
    root = cwd.resolve()
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get('event') == 'init':
            model = event.get('init', {}).get('model')
        if event.get('event') == 'result':
            final = event.get('result')
        step = event.get('step_update', {})
        if step.get('state') != 'DONE' or step.get('tool_name') != 'view_file':
            continue
        info = step.get('tool_info', {})
        path = info.get('parameters', {}).get('AbsolutePath')
        if not path or info.get('error'):
            continue
        try:
            p = Path(path).resolve()
            rel = str(p.relative_to(root)).replace('\\', '/')
            if not p.is_file():
                continue
            reads[rel] = {'path':rel, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                          'tool':'view_file', 'step_index':step.get('step_index')}
        except (OSError, ValueError):
            continue
    if not isinstance(final, dict):
        raise TechnicalFailure('invalid_output', 'CLI sem evento final auditável')
    wrapper = dict(final)
    wrapper['qa_execution_audit'] = {'schema':'cad.cli_read_receipts/v1',
        'origin':'antigravity_stream', 'stream_sha256':_sha256_text(raw),
        'reads':list(reads.values()), 'proves_comprehension':False}
    return json.dumps(wrapper, ensure_ascii=False), model


class AntigravityInvoker:
    def __init__(self, config: ProviderConfig):
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
        proc = _run(
            cmd,
            cwd=cwd,
            timeout_s=self.config.timeout_s,
        )
        raw, model = antigravity_stream_response(proc.stdout, cwd)
        return raw, model or self.config.model


def default_providers(timeout_s: int = 600) -> list[ProviderInvoker]:
    return [
        AntigravityInvoker(
            ProviderConfig(
                "antigravity",
                os.environ.get("CAD_QA_ANTIGRAVITY_MODEL", "gemini-3.8-flash-high"),
                os.environ.get("CAD_QA_ANTIGRAVITY_EFFORT", ""),
                os.environ.get("CAD_QA_ANTIGRAVITY_BIN", shutil.which("agy") or "agy"),
                timeout_s,
            )
        ),
        GrokInvoker(
            ProviderConfig(
                "grok",
                # Dono 2026-10-04: grok-4.7 com esforço medium.
                os.environ.get("CAD_QA_GROK_MODEL", "grok-4.7"),
                os.environ.get("CAD_QA_GROK_EFFORT", "medium"),
                os.environ.get("CAD_QA_GROK_BIN", shutil.which("grok") or "grok"),
                timeout_s,
            )
        ),
        ClaudeInvoker(
            ProviderConfig(
                "claude",
                os.environ.get("CAD_QA_CLAUDE_MODEL", "claude-sonnet-5-5"),
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
    ]


def build_item_prompt(*, item: str, layer: str, context: str, qa_class: str = "PIL") -> str:
    schema = {
        "status": "completed",
        "item": item,
        "layer": layer.upper(),
        "verdict": "validou|invalidou",
        "confidence_percent": 0,
        "note": "justificativa curta baseada em evidencia",
        "suggestion": {
            "action": "manter|corrigir|revisar_humano",
            "target_layer": layer.upper(),
            "summary": "o que a camada deve representar",
            "proposed": [
                {
                    "label": "1",
                    "role": "face_A_chega",
                    "points": [[0, 0], [1, 0], [1, 1]],
                    "note": "somente quando houver evidencia geometrica",
                }
            ],
        },
    }
    if 'CONTRATO PORTAL QA-EVIDÊNCIAS v3' in context:
        schema['suggestion'].update({
            'contract_version': 3, 'assessment': 'pass|fail|inconclusive',
            'confidence_basis': 'evidência que sustenta o veredito e limites',
            'checks': [{'id': 'id obrigatório do checklist da classe', 'criterion': 'critério',
                        'status': 'pass|fail|uncertain', 'observation': 'observação localizada',
                        'expected': 'regra e valor esperado', 'actual': 'valor observado ou não legível',
                        'evidence': [{'source': 'source.png', 'location': 'região/coordenadas',
                                      'finding': 'o que foi observado'}],
                        'rule_refs': ['docs/manual.md#seção']}],
            'candidate_interpretation': None,
            'candidate_evidence': [], 'candidate_rule_refs': [],
            'unit_reviews': [],
            'evidence_catalog': {},
            'field_corrections': [], 'limitations': [], 'questions': [], 'next_probes': []})
        schema['suggestion']['proposed'] = []
    return f"""Voce e o revisor agentico de {qa_class}/SA-N1 do CAD-ANALYZER.
Item: {item}. Camada atual: {layer.upper()}.

Regras obrigatorias:
- Leia e respeite CLAUDE.md e os documentos citados no contexto.
- Julgue a versao-fonte definida no contexto; a camada pedida e o destino da proposta.
- Nao use um FAIL legitimo como falha tecnica.
- N2/N4 sao apenas comparadores e nunca podem alimentar N1/N3.
- Nao grave ou edite arquivos. A sugestao e somente uma proposta read-only.
- Se uma ferramenta, arquivo ou imagem obrigatoria estiver inacessivel, isso NAO e
  invalidacao de engenharia. Responda somente com
  {{"status":"technical_failure","failure_category":"capability","error":"motivo"}}
  para permitir fallback ao proximo provedor.
- Se invalidar, proponha apenas mudancas sustentadas por evidencia; se a prova faltar,
  use revisar_humano. Se validar, use manter e proposed vazio.
- confidence_percent e obrigatorio, numerico entre 0 e 100, e mede sua confianca no veredito.
- Responda exclusivamente com um objeto JSON no schema abaixo.

Contexto e caminhos de evidencia:
{context}

Schema esperado:
{json.dumps(schema, ensure_ascii=False)}

No contrato v3, escolha EXATAMENTE UMA forma de correção SA:
1. Patches: candidate_interpretation=null; field_corrections contém objetos com
   field_path (JSON Pointer relativo ao sa_snapshot, começando /collections/;
   NUNCA /sa_snapshot/collections/), before (valor exato), after,
   evidence=[{{"source":"reference.svg","location":"entidade/coordenadas",
   "finding":"medição independente"}}], rule_refs=["documento#seção"].
   Use esta forma para mudanças localizadas. Não copie o snapshot completo também.
2. Reconstrução completa: candidate_interpretation é o objeto sa_snapshot inteiro
   corrigido, field_corrections=[]; candidate_evidence e candidate_rule_refs são
   OBRIGATÓRIOS e não vazios, cobrindo TODAS as mudanças. Evidências apenas em checks
   ou em field_corrections não substituem essas duas propriedades da suggestion.
Em manter/revisar_humano: candidate_interpretation=null e listas de correção vazias.
Não escreva placeholders/exemplos como valores reais. proposed permanece vazio no v3;
o servidor desenha o candidato a partir da interpretação CAD, não de overlays SVG.
"""


def run_round(
    *,
    round_id: str,
    items: Iterable[str],
    layer: str,
    cwd: Path,
    context_for_item: Callable[[str], str],
    providers: Iterable[ProviderInvoker] | None = None,
    qa_class: str = "PIL",
) -> RoundResult:
    provider_list = list(providers or default_providers())
    results: list[ItemResult] = []
    for raw_item in items:
        item = raw_item.strip().upper()
        attempts: list[Attempt] = []
        final: ItemResult | None = None
        context = context_for_item(item)
        prompt = build_item_prompt(item=item, layer=layer, context=context, qa_class=qa_class)
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
