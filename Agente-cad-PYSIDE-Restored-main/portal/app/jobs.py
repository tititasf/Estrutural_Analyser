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
    memory = app_state.job_meta.get(job_id)
    if memory:
        return memory
    persisted = repo.obter_job_meta(app_state.db, job_id)
    return persisted or {"etapa": "sa"}


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
        if etapa == "qa_agentico":
            from . import qa_jobs

            round_id = meta.get("round_id")
            if not round_id:
                repo.finalizar_job(conn, job["id"], "falhou", erro_msg="round_id QA ausente")
                return
            status = qa_jobs.executar_qa_round(
                settings=settings,
                conn=conn,
                round_id=round_id,
                log_path=log_path,
            )
            if status == "completed":
                repo.finalizar_job(conn, job["id"], "concluido", log_path=str(log_path))
            else:
                repo.finalizar_job(
                    conn, job["id"], "falhou",
                    erro_msg=f"rodada QA terminou como {status}", log_path=str(log_path),
                )
            return

        if etapa == "sa_item":
            # P4 do escape hatch web (item criado pelo laço do viewer):
            # microciclo de UM item (--secao --item --persist-db --wait),
            # enfileirado em vez de rodado dentro do handler HTTP que criou o
            # item — subprocess_timeout_s default é 3600s, e bloquear a
            # requisição de criar item por até 1h travaria a aba do operador
            # sem feedback nenhum. Ramo isolado, ANTES do "etapa_efetiva"
            # abaixo: "sa_item" não é uma etapa formal do pipeline (não está em
            # ETAPAS_SUBPROCESS) e NÃO pode tocar etapa_concluida/estado da
            # obra — é um item avulso, não uma etapa inteira. Mesma razão do
            # branch "sa": o subprocess já tem --wait, o worker não precisa de
            # wait_for_lock aqui.
            resultado = pipeline_runner.executar_microciclo_item(
                settings, obra, secao=meta.get("secao"), item=meta.get("item"),
                pav=meta.get("pav"), dry_run=False, log_path=log_path,
            )
            if resultado.ok:
                repo.finalizar_job(conn, job["id"], "concluido", log_path=str(log_path))
            else:
                erro_tail = resultado.log_tail[-500:] or "microciclo do item falhou"
                repo.finalizar_job(conn, job["id"], "falhou",
                                   erro_msg=erro_tail, log_path=str(log_path))
            return

        etapa_efetiva = etapa if etapa in pipeline_runner.ETAPAS_SUBPROCESS else "sa"

        if etapa == "n5":
            resultado = pipeline_runner.executar_n5(
                settings, obra, classe=meta.get("classe", "PL"),
                pavimento=meta.get("pavimento", "GERAL"), dry_run=False,
            )
        elif etapa == "converter_dwg":
            # [novo, a pedido do dono] conversao avulsa DWG->DXF, fora do fluxo
            # normal triagem/recortes/sa — mesma trava de maquina inteira
            # (accoreconsole nao paraleliza), mas NAO e' uma etapa formal do
            # pipeline (nao mexe em etapa_concluida la' embaixo).
            lock, holder = wait_for_lock(_LOCK_NAME, timeout_s=settings.subprocess_timeout_s)
            if lock is None:
                repo.finalizar_job(conn, job["id"], "falhou",
                                   erro_msg=f"lock ocupado (timeout): {holder}")
                return
            try:
                documentos = repo.listar_documentos_por_obra(conn, obra["id"])
                resultado = pipeline_runner.executar_conversao_dwg(
                    settings, obra, documentos, dry_run=False, log_path=log_path,
                )
            finally:
                release_lock(lock)
        elif etapa_efetiva == "sa":
            # [FIX 2026-07-06] achado real rodando SA pela 1a vez de verdade contra
            # uma obra nova: DEADLOCK. Este branch ANTES tambem chamava
            # wait_for_lock(_LOCK_NAME) aqui, no processo do WORKER, e so' depois
            # rodava o subprocess `headless_sa_analise.py --wait` — mas esse
            # subprocesso TAMBEM chama wait_for_lock(_LOCK_NAME) internamente (e' o
            # que --wait faz). Como o worker ja' segurava a trava, o filho esperava
            # o PROPRIO PAI liberar — o que so' aconteceria quando o filho
            # terminasse. Travou por 30min (o timeout default de wait_for_lock)
            # ate o filho desistir e sair com erro, so' ai' o pai destravava.
            # Reproduzido de verdade com Obra_TREINO_1 antes deste fix.
            # Correcao: SA nao trava aqui — o subprocess `--wait` JA' e' a
            # serializacao (contra o dono na app PySide6 e contra outros jobs).
            resultado = pipeline_runner.executar_etapa(
                settings, "sa", obra, secao=meta.get("secao"), pav=meta.get("pav"),
                dry_run=False, log_path=log_path,
            )
        else:
            # triagem/recortes: nao tem `--wait` interno proprio (accoreconsole e'
            # chamado direto, RecorteMotor e' Python puro) — o worker precisa
            # segurar a trava aqui mesmo, senao dono+portal podem rodar accoreconsole
            # ou o motor ao mesmo tempo (protecao anti-OOM real).
            lock, holder = wait_for_lock(_LOCK_NAME, timeout_s=settings.subprocess_timeout_s)
            if lock is None:
                repo.finalizar_job(conn, job["id"], "falhou",
                                   erro_msg=f"lock ocupado (timeout): {holder}")
                return
            try:
                # [2026-07-06] obra-como-container: se ha' portal_documentos para
                # esta obra, a triagem roda em LOTE (1 job classifica/valida todos
                # os docs pendentes) — modelo novo. Obras legadas (1 arquivo, sem
                # linhas em portal_documentos) seguem no fluxo antigo, inalterado.
                documentos = repo.listar_documentos_por_obra(conn, obra["id"])
                if etapa_efetiva == "triagem" and documentos:
                    pendentes = [d for d in documentos if d["status"] == "pendente"]
                    por_id = {d["id"]: d for d in pendentes}
                    resultado = pipeline_runner.executar_triagem_documentos(
                        settings, obra, pendentes, dry_run=False, log_path=log_path,
                    )
                    for item in resultado.artefatos.get("documentos", []):
                        if not item["ok"]:
                            repo.atualizar_classificacao_documento(
                                conn, item["doc_id"], status="erro",
                                erro_msg=item.get("erro_msg"),
                            )
                            continue
                        # arquivo valido (converteu/abriu ok) — promove pra
                        # 'classificado' (auto-confirma sugestao do upload) SO' se
                        # classe+pavimento ja' eram inequivocos; senao 'revisar'
                        # (humano decide na tela da obra, arquivo em si esta' ok).
                        doc = por_id[item["doc_id"]]
                        inequivoco = bool(doc["classe_sugerida"] and doc["pavimento_sugerido"])
                        repo.atualizar_classificacao_documento(
                            conn, item["doc_id"],
                            status="classificado" if inequivoco else "revisar",
                            classe_confirmada=doc["classe_sugerida"] if inequivoco else None,
                            pavimento_confirmado=doc["pavimento_sugerido"] if inequivoco else None,
                        )
                else:
                    resultado = pipeline_runner.executar_etapa(
                        settings, etapa_efetiva, obra, secao=meta.get("secao"), pav=meta.get("pav"),
                        dry_run=False, log_path=log_path,
                    )
            finally:
                release_lock(lock)

        if resultado.ok:
            repo.finalizar_job(conn, job["id"], "concluido", log_path=str(log_path))
            if etapa == "converter_dwg":
                # [novo] conversao avulsa NAO e' etapa formal do pipeline —
                # so' devolve a obra pro estado "processando" (nao mexe em
                # etapa_concluida, que fica preservado via COALESCE) pra nao
                # regredir etapa_atual (_PROXIMA_ETAPA nao conhece essa chave).
                repo.atualizar_estado_obra(conn, obra["id"], "processando")
            elif etapa == "n5" or etapa_efetiva == "sa":
                repo.atualizar_estado_obra(conn, obra["id"], "pronta", processada_em=_agora(),
                                           etapa_concluida=None if etapa == "n5" else "sa")
            else:
                # [FIX 2026-07-06] achado real testando o modo rapido: ANTES,
                # QUALQUER job bem-sucedido (inclusive triagem sozinha) marcava
                # a obra "pronta" (etapa 4, Validacao) — a UI mostrava "Recortes
                # (concluida)" e "SA (concluida)" mesmo sem nenhum dos dois ter
                # rodado. triagem/recortes NAO terminam o pipeline (falta SA);
                # continua "processando" (pipeline em andamento, so' registra
                # qual etapa concluiu) em vez de "pronta".
                repo.atualizar_estado_obra(conn, obra["id"], "processando",
                                           etapa_concluida=etapa_efetiva)
                # [novo, a pedido do dono] Triagem + Recortes: nao quer 2
                # botoes separados — apos a triagem terminar com sucesso,
                # encadeia AUTOMATICAMENTE um job de recortes (classifica os
                # brutos), sem o usuario precisar clicar de novo. O worker
                # (thread unica) so' pega esse job na proxima volta do loop,
                # entao nao ha' concorrencia com o job de triagem que acabou
                # de liberar a trava.
                if etapa_efetiva == "triagem":
                    ev = pipeline_runner.engine_version(settings.repo_root)
                    proximo_job_id = repo.enfileirar_job(conn, obra_id=obra["id"], engine_version=ev)
                    app_state.job_meta[proximo_job_id] = {"etapa": "recortes"}
        else:
            # [FIX] `log_tail` já é só as últimas linhas do processo (ver
            # `_tail()` em pipeline_runner.py); fatiar com `[:500]` (primeiros
            # 500 caracteres) cortava exatamente a linha final da exceção
            # quando o traceback tinha mais que isso — o erro mostrado na tela
            # sempre terminava no meio de um `File "..."`, nunca mostrando o
            # `XxxError: ...` de verdade. `[-500:]` preserva o final real.
            erro_tail = resultado.log_tail[-500:] or "etapa falhou"
            repo.finalizar_job(conn, job["id"], "falhou",
                               erro_msg=erro_tail, log_path=str(log_path))
            repo.atualizar_estado_obra(conn, obra["id"], "erro", erro_msg=erro_tail)
    except Exception as exc:  # noqa: BLE001 - quarentena (R6): job com erro nao para a fila
        log.exception("job %s falhou", job["id"])
        repo.finalizar_job(conn, job["id"], "falhou", erro_msg=str(exc)[:500])
        if etapa != "qa_agentico":
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
