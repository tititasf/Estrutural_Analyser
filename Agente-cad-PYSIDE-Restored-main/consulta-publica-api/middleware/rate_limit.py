"""Rate limiting + detecção de enumeração (STORY-04, AC 1, 2, 6, 7).

Decisão de kickoff: middleware PRÓPRIO em memória, em vez da lib `slowapi`
sugerida na story — evita adicionar dependência nova ao ambiente Python
compartilhado com o portal (`slowapi` não está instalada; a story permite
explicitamente "slowapi ou middleware equivalente"). Trade-off documentado:
estado em memória de processo único — não sobrevive a restart nem escala
entre múltiplos workers/processos. Aceitável para o MVP (1 processo); se o
deploy real usar múltiplos workers, mover para um backend compartilhado
(Redis) fica registrado como próximo passo (ver Dev Agent Record).

Defesa em profundidade: Cloudflare é a 1ª linha (fora do escopo desta
story); este middleware é a 2ª linha, no próprio processo.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from audit.logger import AuditLogger

LIMIT_PER_MINUTE = 60
WINDOW_SECONDS = 60.0
NOT_FOUND_BURST_THRESHOLD = 20
NOT_FOUND_BLOCK_SECONDS = 30.0

# /health é isento do limite agressivo (AC 6) — health check de infra não
# deve ser bloqueado.
_EXEMPT_PATHS = {"/api/v1/health"}


def _trim(window: deque, now: float, seconds: float) -> None:
    while window and now - window[0] > seconds:
        window.popleft()


def _client_ip(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, audit_logger: Optional[AuditLogger] = None):
        super().__init__(app)
        self._requests: dict[str, deque] = defaultdict(deque)
        self._not_found: dict[str, deque] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._audit_logger = audit_logger

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        ip = _client_ip(request)
        now = time.monotonic()

        # Bloqueio temporário ativo por rajada de 404 detectada antes (AC 2)?
        bloqueado_ate = self._blocked_until.get(ip)
        if bloqueado_ate and now < bloqueado_ate:
            return self._too_many_requests(int(bloqueado_ate - now) + 1)

        janela = self._requests[ip]
        _trim(janela, now, WINDOW_SECONDS)
        if len(janela) >= LIMIT_PER_MINUTE:
            retry_after = int(WINDOW_SECONDS - (now - janela[0])) + 1
            return self._too_many_requests(retry_after)
        janela.append(now)

        response = await call_next(request)

        if response.status_code == 404:
            nf_janela = self._not_found[ip]
            _trim(nf_janela, now, WINDOW_SECONDS)
            nf_janela.append(now)
            if len(nf_janela) > NOT_FOUND_BURST_THRESHOLD:
                self._blocked_until[ip] = now + NOT_FOUND_BLOCK_SECONDS
                if self._audit_logger:
                    self._audit_logger.log_evento(
                        "enumeracao_detectada", ip=ip,
                        path=_redact_code_from_path(path),
                        contagem_404=len(nf_janela),
                    )

        if self._audit_logger:
            code = _extrair_code_do_path(path)
            self._audit_logger.log_acesso(
                ip=ip, path=_redact_code_from_path(path),
                status=response.status_code, code=code,
            )

        return response

    @staticmethod
    def _too_many_requests(retry_after_seconds: int) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "erro": "muitas_tentativas",
                "retry_after_seconds": retry_after_seconds,
            },
            headers={"Retry-After": str(retry_after_seconds)},
        )


def _extrair_code_do_path(path: str) -> Optional[str]:
    """Extrai o `{code}` de rotas conhecidas (`/resolve/{code}`,
    `/ficha/{code}`, `/ficha/{code}/paineis-lv`, `/obra/{code}`) só pra
    fins de log hasheado — não faz parsing de rota real (isso é
    responsabilidade do router), é só uma extração best-effort pro audit."""
    partes = [p for p in path.split("/") if p]
    conhecidas = {"resolve", "ficha", "obra"}
    for i, parte in enumerate(partes):
        if parte in conhecidas and i + 1 < len(partes):
            return partes[i + 1]
    return None


def _redact_code_from_path(path: str) -> str:
    """Substitui o segmento `{code}` (achado por `_extrair_code_do_path`) por
    um placeholder antes de logar — o `path` sozinho NUNCA deve carregar o
    código em texto puro, mesmo quando `code_hash` também é gravado (achado
    real em teste: logar `path` cru ao lado de `code_hash` derrotava o hash,
    já que o código aparecia de novo, sem redação, dentro do próprio path)."""
    code = _extrair_code_do_path(path)
    if not code:
        return path
    return path.replace(code, "{code}", 1)
