"""App factory FastAPI do portal (HANDOFF §1.1). NUNCA importa PySide6.

Monta routers, abre portal_data.db (migrado), e no lifespan sobe o worker de jobs
(thread unica) e, se habilitado, o poller do Drive (asyncio background task). Bind
default 127.0.0.1 (P3: nenhuma porta publica).

Executar de verdade (raiz do repo):
    uvicorn portal.app.main:app --host 127.0.0.1 --port 21380
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from types import SimpleNamespace

from fastapi import FastAPI

from ..db import connection as db_conn
from . import drive_poller, jobs
from .config import Settings, load_settings
from .routers import (
    auth_routes,
    comentarios_routes,
    fichas_routes,
    jobs_routes,
    obras_routes,
    paginas_routes,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("portal.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a app FastAPI. `settings` injetavel para testes (db em tmp, poller off)."""
    settings = settings or load_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- startup ---
        app.state.settings = settings
        # [FIX 2026-07-05] app.state.db costumava guardar UMA conexao sqlite3
        # reusada por routers (threadpool) + poller (asyncio.to_thread) + JobWorker
        # (thread propria) — 3 contextos de thread diferentes tocando o MESMO
        # objeto sqlite3.Connection, que o modulo proibe por padrao
        # (`sqlite3.ProgrammingError: SQLite objects created in a thread can only
        # be used in that same thread`), confirmado rodando o servidor de verdade.
        # Migracao roda 1x aqui com uma conexao efemera, fechada em seguida;
        # routers usam `Depends(get_db_conn)` (conexao por request) e o
        # JobWorker/poller ja abrem a propria conexao na sua propria thread.
        _conn_migracao = db_conn.init_db(settings.db_path)
        _conn_migracao.close()
        app.state.job_meta = {}          # job_id -> {etapa, secao, classe, pavimento}
        app.state.validacoes = {}        # obra_id -> {classe -> {validado,...}}  (etapa 5, MVP)
        app.state.estado_global = {"drive": "ok"}
        app.state.drive_client = drive_poller.montar_drive_client(settings)

        worker = jobs.JobWorker(app.state)
        worker.start()
        app.state.worker = worker

        poller_task = None
        if settings.poll_enabled:
            poller_task = asyncio.create_task(drive_poller.poller_loop(app.state))
        app.state.poller_task = poller_task
        log.info("portal iniciado (poll_enabled=%s, db=%s)",
                 settings.poll_enabled, settings.db_path or db_conn.DEFAULT_DB_PATH)
        if settings.usa_secret_dev():
            log.warning("PORTAL_SESSION_SECRET nao definido — usando segredo DEV. "
                        "Defina-o em producao.")
        try:
            yield
        finally:
            # --- shutdown ---
            worker.stop()
            if poller_task is not None:
                poller_task.cancel()
                # [FIX 2026-07-05] `asyncio.CancelledError` NAO herda de `Exception`
                # (herda de `BaseException` desde o Python 3.8), entao
                # `suppress(Exception)` NAO a capturava: todo shutdown limpo com o
                # poller ligado (PORTAL_POLL_ENABLED=true) propagava CancelledError
                # para fora do lifespan — quebrando o restart limpo exigido por P3/P5.
                # Achado real pelo teste test_lifespan_com_poller_habilitado_cria_task.
                # Suprimir CancelledError aqui e' o padrao correto de shutdown: nos
                # mesmos cancelamos a task de proposito.
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await poller_task
            log.info("portal encerrado")

    app = FastAPI(title="Portal Soberano — CAD Estrutural", version="1.0.0", lifespan=lifespan)

    # attach settings tambem fora do lifespan (testes que usam TestClient ja passam por ele)
    app.state.settings = settings

    # Front-end server-rendered (Jinja2) + estáticos.
    # setup_templates monta o Jinja2Templates em app.state.templates.
    from pathlib import Path as _Path

    from fastapi.staticfiles import StaticFiles

    paginas_routes.setup_templates(app)
    _static_dir = _Path(__file__).resolve().parent / "static"
    _static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    app.include_router(auth_routes.router)
    app.include_router(obras_routes.router)
    app.include_router(jobs_routes.router)
    app.include_router(fichas_routes.router)
    app.include_router(comentarios_routes.router)
    app.include_router(paginas_routes.router)

    @app.get("/health", tags=["infra"])
    def health():
        estado = getattr(app.state, "estado_global", {"drive": "desconhecido"})
        return {"status": "ok", "drive": estado.get("drive", "desconhecido"),
                "poll_enabled": settings.poll_enabled}

    return app


# instancia default para `uvicorn portal.app.main:app`
app = create_app()
