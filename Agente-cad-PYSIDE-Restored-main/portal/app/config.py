"""Configuracao do portal — paths, credenciais Drive, intervalos, segredo de sessao.

Tudo vem de variaveis de ambiente com defaults sensatos (HANDOFF §1.1). Nenhum
segredo hardcoded: SESSION_SECRET default e' um valor DEV explicito e avisado; em
producao o dono seta PORTAL_SESSION_SECRET.

[ASSUMPTION] O handoff cita `portal/.secrets/drive-sa.json`. Mantido esse default,
mas configuravel por PORTAL_DRIVE_SA_JSON para o dono apontar a chave real depois.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# raiz do repo = pai de portal/app/ -> portal/ -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]

# Segredo DEV explicito — trocar em producao via env. Nunca commitar segredo real.
_DEV_SECRET = "portal-dev-secret-troque-em-producao"


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "sim")


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Configuracao imutavel do processo (montada uma vez em create_app)."""

    repo_root: Path = REPO_ROOT

    # --- Banco ---
    # None => portal.db.connection.DEFAULT_DB_PATH (raiz do repo). Testes injetam tmp.
    db_path: Path | None = None

    # --- Sessao / auth ---
    session_secret: str = field(
        default_factory=lambda: os.environ.get("PORTAL_SESSION_SECRET", _DEV_SECRET)
    )
    session_cookie_name: str = "portal_sessao"
    session_ttl_horas: int = field(default_factory=lambda: _env_int("PORTAL_SESSION_TTL_H", 12))
    cookie_secure: bool = field(default_factory=lambda: _env_bool("PORTAL_COOKIE_SECURE", False))

    # --- Rede (P3: so 127.0.0.1 / Tailscale, nunca porta publica) ---
    host: str = field(default_factory=lambda: os.environ.get("PORTAL_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("PORTAL_PORT", 21380))

    # --- Poller do Drive (DP-10/DP-11) ---
    drive_sa_json: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "PORTAL_DRIVE_SA_JSON",
                str(REPO_ROOT / "portal" / ".secrets" / "drive-sa.json"),
            )
        )
    )
    poll_interval_s: int = field(default_factory=lambda: _env_int("PORTAL_POLL_INTERVAL_S", 120))
    poll_enabled: bool = field(default_factory=lambda: _env_bool("PORTAL_POLL_ENABLED", False))
    max_obra_mb: int = field(default_factory=lambda: _env_int("PORTAL_MAX_OBRA_MB", 200))
    auto_triagem: bool = field(default_factory=lambda: _env_bool("PORTAL_AUTO_TRIAGEM", False))

    # --- Pipeline / subprocess ---
    # Diretorio onde o poller baixa obras e onde o headless procura --obra.
    dados_obras_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("PORTAL_DADOS_OBRAS", str(REPO_ROOT / "DADOS-OBRAS"))
        )
    )
    # Diretorio de logs de job (stdout/stderr do subprocess).
    logs_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("PORTAL_LOGS_DIR", str(REPO_ROOT / "portal" / "logs"))
        )
    )
    # Timeout do subprocess do headless (segundos). SA completo ~315s -> folga.
    subprocess_timeout_s: int = field(
        default_factory=lambda: _env_int("PORTAL_SUBPROCESS_TIMEOUT_S", 3600)
    )
    # Pavimento default passado ao headless quando o cliente nao informa.
    pav_default: str = field(default_factory=lambda: os.environ.get("PORTAL_PAV_DEFAULT", "13_PAV"))

    # STATUS.md — fonte read-only do rotulo certificado/beta por classe (R9).
    status_md_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("PORTAL_STATUS_MD", str(REPO_ROOT / "docs" / "STATUS.md"))
        )
    )

    def usa_secret_dev(self) -> bool:
        return self.session_secret == _DEV_SECRET


# campos que sao Path (coeragem de overrides str -> Path)
_PATH_FIELDS = {
    "db_path", "repo_root", "drive_sa_json", "dados_obras_dir",
    "logs_dir", "status_md_path",
}


def load_settings(**overrides) -> Settings:
    """Monta Settings do ambiente; `overrides` (testes) tem precedencia.

    Overrides de campos Path aceitam str e sao convertidos (exceto db_path, que
    pode ser None => usa o default do portal.db.connection).
    """
    s = Settings()
    for k, v in overrides.items():
        if not hasattr(s, k):
            continue
        if k in _PATH_FIELDS and v is not None and not isinstance(v, Path):
            v = Path(v)
        setattr(s, k, v)
    # garante diretorios de trabalho
    s.logs_dir.mkdir(parents=True, exist_ok=True)
    s.dados_obras_dir.mkdir(parents=True, exist_ok=True)
    return s
