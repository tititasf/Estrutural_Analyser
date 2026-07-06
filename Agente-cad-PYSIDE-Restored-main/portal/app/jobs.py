"""Fila de jobs: worker de thread unica + exclusao mutua real via single_instance (HANDOFF §3).

Dois niveis de serializacao (§3.1):
  1. Thread unica: o worker processa 1 job por vez -> nunca dispara 2 subprocess por conta propria.
  2. single_instance lock ('headless_sa'): rede de seguranca contra o dono (app PySide6)
     + portal ao mesmo tempo. O subprocess do headless ja pega o lock com --wait; o
     worker tambem tenta wait_for_lock antes de rodar a etapa pesada, para nunca dois
     na maquina inteira. Lock liberado pelo SO mesmo em crash (§3.4).

Crash recovery (§3.4): na inicializacao, reconciliar_jobs re-enfileira todo job que
ficou 'executando' (so acontece se o servidor caiu no meio). Idempotente: as etapas
regeneram artefatos determinísticos.

A trava e' REUSADA de scripts.arete.single_instance — nao reimplementada.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from ..db import connection as db_conn
from ..db import repository as repo
from . import pipeline_runner
from .config import Settings

log = logging.getLogger("portal.jobs")

# reuso REAL do lock anti-OOM (HANDOFF §0/§3.1) — nunca reimplementar.
try:
    from scripts.arete.single_instance import wait_for_lock, release_lock
except ImportError:  # pragma: no cover - fallback de path
    from single_instance import wait_for_lock, release_lock  # type: ignore

_LOCK_NAME = "headless_sa"


def _metadados_job(app_state, job_id: str) -> dict:
    """Metadados da etapa (tipo/secao/classe/pav) que o router guardou por job_id.

    O schema real de portal_jobs nao tem coluna 'tipo' — o portal guarda os detalhes
    da etapa num mapa em memoria (app_state.job_meta). Se ausente (ex.: reconciliacao
    pos-crash sem meta), assume etapa 'sa' completa (regenera tudo, idempotente).
    """
    return app_state.job_meta.get(job_id, {"etapa": "sa"})


def reconciliar_jobs(conn) -> int:
    """Re-enfileira jobs 'executando' orfaos de um crash (§3.4). Retorna quantos."""
    linhas = conn.execute(
        "SELECT id FROM portal_jobs WHERE status = 'executando'"
    ).fetchall()
    n = 0
    for row in linhas:
        conn.execute(
            "UPDATE portal_jobs SET status='na_fila', iniciado_em=NULL, "
            "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
            (row["id"],),
        )
        n += 1
    conn.commit()
    if n:
        log.info("reconciliacao: %d job(s) re-enfileirado(s) apos reinicio", n)
    return n


def processar_um_job(app_state, job: dict) -> None:
    """Executa um job ja consumido (status='executando'). Fecha em concluido/falhou.

    Pega o lock de maquina inteira (wait) para etapas pesadas; N5/validacao dispensam.
    """
    settings: Settings = app_state.settings
    conn = app_state.db
    meta = _metadados_job(app_state, job["id"])
    etapa = meta.get("etapa", "sa")
    obra = repo.obter_obra(conn, job["obra_id"])
    if obra is None:
        repo.finalizar_job(conn, job["id"], "falhou", erro_msg="obra inexistente")
        return

    log_path = Path(settings.logs_dir) / f"job_{job['id']}.log"
    try:
        if etapa == "n5":
            resultado = pipeline_runner.executar_n5(
                settings, obra, classe=meta.get("classe", "PL"),
                pavimento=meta.get("pavimento", "GERAL"), dry_run=False,
            )
        else:
            # etapa pesada: garante 1 headless por maquina inteira (dono + portal).
            lock, holder = wait_for_lock(_LOCK_NAME, timeout_s=settings.subprocess_timeout_s)
            if lock is None:
                repo.finalizar_job(conn, job["id"], "falhou",
                                   erro_msg=f"lock ocupado (timeout): {holder}")
                return
            try:
                resultado = pipeline_runner.executar_etapa(
                    settings, etapa if etapa in pipeline_runner.ETAPAS_SUBPROCESS else "sa",
                    obra, secao=meta.get("secao"), pav=meta.get("pav"),
                    dry_run=False, log_path=log_path,
                )
            finally:
                release_lock(lock)

        if resultado.ok:
            repo.finalizar_job(conn, job["id"], "concluido", log_path=str(log_path))
            repo.atualizar_estado_obra(conn, obra["id"], "pronta",
                                       processada_em=_agora())
        else:
            repo.finalizar_job(conn, job["id"], "falhou",
                               erro_msg=resultado.log_tail[:500] or "etapa falhou",
                               log_path=str(log_path))
            repo.atualizar_estado_obra(conn, obra["id"], "erro",
                                       erro_msg=(resultado.log_tail[:500] or "etapa falhou"))
    except Exception as exc:  # noqa: BLE001 - quarentena (R6): job com erro nao para a fila
        log.exception("job %s falhou", job["id"])
        repo.finalizar_job(conn, job["id"], "falhou", erro_msg=str(exc)[:500])
        repo.atualizar_estado_obra(conn, obra["id"], "erro", erro_msg=str(exc)[:500])
    finally:
        app_state.job_meta.pop(job["id"], None)


def _agora() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class JobWorker:
    """Worker de thread unica que consome a fila FIFO do portal_data.db (§3.2/§3.3).

    Abre a PROPRIA conexao SQLite (sqlite3 nao e' thread-safe entre conexoes) — os
    routers web usam a deles (Depends(get_db_conn), uma por request; ver dbdep.py).
    """

    def __init__(self, app_state):
        self.app_state = app_state
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, name="portal-job-worker", daemon=True)
        self._thread.start()
        log.info("JobWorker iniciado")

    def stop(self, timeout: float = 5.0) -> None:
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        log.info("JobWorker parado")

    def _loop(self) -> None:
        settings: Settings = self.app_state.settings
        conn = db_conn.get_connection(settings.db_path)
        # o worker usa a SUA conexao para escrever no estado do job
        worker_state = _WorkerState(self.app_state, conn)
        try:
            reconciliar_jobs(conn)
            while not self._parar.is_set():
                job = repo.consumir_job(
                    conn, engine_version=pipeline_runner.engine_version(settings.repo_root)
                )
                if job is None:
                    time.sleep(2.0)
                    continue
                processar_um_job(worker_state, job)
        finally:
            conn.close()


class _WorkerState:
    """Adapta app_state para usar a conexao propria do worker (thread-safe)."""

    def __init__(self, app_state, conn):
        self._app_state = app_state
        self.db = conn

    def __getattr__(self, item):
        return getattr(self._app_state, item)
