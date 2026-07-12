"""App factory da API pública de Consulta (STORY-02).

Processo FastAPI fisicamente separado do portal interno (`portal/app/main.py`,
porta 21380) — bind 127.0.0.1:21390, sem nenhuma dependência de
auth/access/repository/connection do portal. Read-only por design: todos os
endpoints (a partir da STORY-03) só fazem GET contra `public_consulta.db`
aberto em mode=ro.

Executar (raiz do repo):
    uvicorn consulta-publica-api.main:app --host 127.0.0.1 --port 21390

(o nome do diretório tem hífen — não é importável como pacote Python; rode a
partir de dentro de `consulta-publica-api/`, ou use o script
`run_consulta_publica.sh`/`run_consulta_publica.bat`, que ajusta o cwd.)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from audit.logger import AuditLogger
from config import Settings, load_settings
from middleware.rate_limit import RateLimitMiddleware
from routers import (
    ficha_routes,
    health_routes,
    obra_routes,
    paineis_lv_routes,
    pavimento_routes,
    resolve_routes,
    svg_routes,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("consulta_publica.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(
        title="API Pública de Consulta — CAD-ANALYZER",
        version="0.1.0",
        # Nenhuma UI docs pública por padrão em produção seria o ideal, mas
        # para o MVP mantemos /docs (read-only, sem dado sensível exposto).
    )
    app.state.settings = settings

    audit_logger = AuditLogger(settings.audit_log_path)
    app.state.audit_logger = audit_logger

    # Ordem importa: Starlette aplica middlewares na ordem INVERSA de adição
    # (o último adicionado roda primeiro). Rate limit precisa rodar antes do
    # CORS resolver headers, então adicionamos CORS por último.
    app.add_middleware(RateLimitMiddleware, audit_logger=audit_logger)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origin],  # NUNCA "*" (AC 3)
        allow_credentials=False,
        allow_methods=["GET"],  # API é 100% read-only (STORY-02, AC 5)
        allow_headers=["*"],
    )

    app.include_router(health_routes.router)
    app.include_router(resolve_routes.router)
    app.include_router(ficha_routes.router)
    app.include_router(svg_routes.router)
    app.include_router(obra_routes.router)
    app.include_router(paineis_lv_routes.router)
    app.include_router(pavimento_routes.router)

    log.info(
        "consulta-publica-api iniciada — host=%s port=%s db=%s allowed_origin=%s",
        settings.host, settings.port, settings.public_consulta_db_path,
        settings.allowed_origin,
    )

    return app


# instância default para `uvicorn main:app`
app = create_app()
