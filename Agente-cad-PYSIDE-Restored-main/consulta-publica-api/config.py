"""Configuração da API pública de Consulta (STORY-02).

Processo FISICAMENTE separado do portal interno (`portal/app/config.py`) —
nenhum import cruzado. Tudo via variável de ambiente com default sensato.
Nunca hardcoda path absoluto de máquina de desenvolvedor em produção — os
defaults abaixo existem só para rodar localmente sem configurar nada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Configuração imutável do processo público (montada uma vez em create_app)."""

    # --- Rede — bind SEMPRE 127.0.0.1, nunca 0.0.0.0 (AC 1). Exposição pública
    # real acontece via Cloudflare Tunnel/reverse-proxy, nunca bind direto. ---
    host: str = field(
        default_factory=lambda: os.environ.get("CONSULTA_PUBLICA_HOST", "127.0.0.1")
    )
    port: int = field(
        default_factory=lambda: _env_int("CONSULTA_PUBLICA_PORT", 21390)
    )

    # --- Banco read-only (STORY-01) ---
    public_consulta_db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "PUBLIC_CONSULTA_DB_PATH",
                str(_REPO_ROOT.parent / "public_consulta.db"),
            )
        )
    )

    # --- Dados por obra (SVGs/fichas já materializados — read-only) ---
    # Mesmo diretório usado pelo portal interno (`portal/app/config.py`,
    # `REPO_ROOT / "DADOS-OBRAS"`) — nunca `_REPO_ROOT.parent` (esse é o
    # sibling do repo, usado só pelo `public_consulta_db_path`, que fica
    # FORA do repo de propósito; `DADOS-OBRAS` fica DENTRO).
    dados_obras_root: Path = field(
        default_factory=lambda: Path(
            os.environ.get("DADOS_OBRAS_ROOT", str(_REPO_ROOT / "DADOS-OBRAS"))
        )
    )

    # --- CORS (usado pela STORY-04) — domínio do frontend. Em produção,
    # sempre setar via env (domínio Vercel real). Default local aponta para
    # `consulta-publica-web` (STORY-08), que roda em :21391 — dentro da
    # faixa de portas Diana 21300-21399 (CLAUDE.md), não a porta padrão
    # 3000 do `create-next-app` (nunca usada aqui de propósito). ---
    allowed_origin: str = field(
        default_factory=lambda: os.environ.get(
            "CONSULTA_PUBLICA_ALLOWED_ORIGIN", "http://127.0.0.1:21391"
        )
    )

    # --- Log de auditoria (STORY-04, AC 5) — JSONL append-only, arquivo
    # FISICAMENTE distinto de public_consulta.db (que fica mode=ro sempre). ---
    audit_log_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "CONSULTA_PUBLICA_AUDIT_LOG",
                str(_REPO_ROOT.parent / "public_audit.log"),
            )
        )
    )


_PATH_FIELDS = {"public_consulta_db_path", "dados_obras_root", "audit_log_path"}


def load_settings(**overrides) -> Settings:
    """Monta Settings do ambiente; `overrides` (testes) têm precedência."""
    s = Settings()
    for key, value in overrides.items():
        if not hasattr(s, key):
            continue
        if key in _PATH_FIELDS and value is not None:
            value = Path(value)
        setattr(s, key, value)
    return s
