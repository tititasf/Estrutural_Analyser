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

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from ..db import connection as db_conn
from ..db import repository as repo
from . import n5_release, pipeline_runner
from .config import Settings

log = logging.getLogger("portal.jobs")

# reuso REAL do lock anti-OOM (HANDOFF §0/§3.1) — nunca reimplementar.
try:
    from scripts.arete.single_instance import wait_for_lock, release_lock
except ImportError:  # pragma: no cover - fallback de path
    from single_instance import wait_for_lock, release_lock  # type: ignore

_LOCK_NAME = "headless_sa"


def _registrar_dxf_convertido(
    conn,
    *,
    obra_id: str,
    documento_origem: dict,
    dxf_path: Optional[str],
    status: str,
    classe_confirmada: Optional[str] = None,
    pavimento_confirmado: Optional[str] = None,
) -> Optional[str]:
    """Materializa no catalogo o DXF que o conversor ja gravou em disco."""
    if not dxf_path or not str(documento_origem.get("arquivo_nome") or "").lower().endswith(".dwg"):
        return None
    caminho = Path(dxf_path)
    if caminho.suffix.lower() != ".dxf" or not caminho.is_file():
        return None
    digest = hashlib.md5()  # noqa: S324 - hash de deduplicacao, nao de seguranca
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloco)
    return repo.sincronizar_documento_dxf_convertido(
        conn,
        obra_id=obra_id,
        documento_origem=documento_origem,
        arquivo_nome=caminho.name,
        local_path=str(caminho),
        arquivo_hash=digest.hexdigest(),
        status=status,
        classe_confirmada=classe_confirmada,
        pavimento_confirmado=pavimento_confirmado,
    )


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
        if etapa == "preprocessamento":
            from .preprocessamento.preprocess_runner import execute_inventory_job

            obra_dir = Path(obra["local_path"]) if obra.get("local_path") else settings.dados_obras_dir / obra["nome"]
            def preprocess_progress(value):
                current = conn.execute("SELECT status FROM portal_jobs WHERE id=?", (job['id'],)).fetchone()
                if current and current['status'] == 'cancelado':
                    raise InterruptedError('pré-processamento cancelado pelo operador')
                meta['progress'] = value
                repo.salvar_job_meta(conn, job['id'], meta)
            floors = {d.get('pavimento_confirmado') or d.get('pavimento_sugerido')
                      for d in repo.listar_documentos_por_obra(conn, obra['id'])}
            result = execute_inventory_job(
                obra_dir=obra_dir, obra_id=obra["id"], pavimento=meta["pav"],
                job_id=job["id"], frozen_sources=meta["frozen_sources"],
                declarations=meta["sources"],
                progress=preprocess_progress, known_floors=sorted(f for f in floors if f),
            )
            meta["result"] = result
            repo.salvar_job_meta(conn, job["id"], meta)
            current = conn.execute("SELECT status FROM portal_jobs WHERE id=?", (job['id'],)).fetchone()
            if current and current['status'] != 'cancelado':
                repo.finalizar_job(conn, job["id"], "falhou" if result['status'] == 'failed' else "concluido")
            return
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
            elif status in {"paused", "cancelled"}:
                # O endpoint já persistiu a decisão. Não sobrescreve a pausa ou
                # o cancelamento ao alcançar a fronteira entre itens QA.
                log.info("job QA %s interrompido pelo operador: %s", job["id"], status)
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
                visual_mode=meta.get("visual_mode", "NOVA"),
            )
            if resultado.ok:
                repo.finalizar_job(conn, job["id"], "concluido", log_path=str(log_path))
            else:
                erro_tail = resultado.log_tail[-500:] or "microciclo do item falhou"
                repo.finalizar_job(conn, job["id"], "falhou",
                                   erro_msg=erro_tail, log_path=str(log_path))
            return

        if etapa in {"n3_cima_item", "n3_pilar_vista_item"}:
            resultado = pipeline_runner.regenerar_n3_cima_item(
                settings, obra, item=meta.get("item"), pav=meta.get("pav"),
                dry_run=False, log_path=log_path,
                visual_mode=meta.get("visual_mode", "NOVA"),
                vista=meta.get("requested_view", "cima"),
            )
            if resultado.ok:
                repo.finalizar_job(conn, job["id"], "concluido", log_path=str(log_path))
            else:
                repo.finalizar_job(
                    conn, job["id"], "falhou",
                    erro_msg=resultado.log_tail[-500:] or "regeneracao N3 Cima falhou",
                    log_path=str(log_path),
                )
            return

        if etapa == "n3_lv_view_item":
            resultado = pipeline_runner.regenerar_n3_lv_vista_item(
                settings, obra, beam=meta.get("item"), pav=meta.get("pav"),
                behavior=meta.get("behavior"), view=meta.get("requested_view"),
                visual_mode=meta.get("visual_mode", "NOVA"),
                dry_run=False, log_path=log_path,
            )
            repo.finalizar_job(
                conn, job["id"], "concluido" if resultado.ok else "falhou",
                erro_msg=None if resultado.ok else resultado.log_tail[-500:],
                log_path=str(log_path),
            )
            return

        etapa_efetiva = etapa if etapa in pipeline_runner.ETAPAS_SUBPROCESS else "sa"

        if etapa == "n5":
            resultado = pipeline_runner.executar_n5(
                settings, obra, classe=meta.get("classe", "PL"),
                pavimento=meta.get("pavimento", "GERAL"), dry_run=False,
                visual_mode=meta.get("visual_mode", "NOVA"),
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
                documentos_por_id = {d["id"]: d for d in documentos}
                for item in resultado.artefatos.get("documentos", []):
                    doc_id = item.get("doc_id")
                    if not doc_id:
                        continue
                    if item["ok"]:
                        doc_origem = documentos_por_id.get(doc_id)
                        if doc_origem:
                            _registrar_dxf_convertido(
                                conn,
                                obra_id=obra["id"],
                                documento_origem=doc_origem,
                                dxf_path=item.get("dxf_path"),
                                status=(
                                    "classificado"
                                    if doc_origem.get("status") == "classificado"
                                    else "revisar"
                                ),
                            )
                        repo.atualizar_classificacao_documento(
                            conn, doc_id, status="pendente",
                        )
                        repo.limpar_erro_documento(conn, doc_id)
                    else:
                        repo.atualizar_classificacao_documento(
                            conn, doc_id, status="erro",
                            erro_msg=item.get("erro_msg"),
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
                visual_mode=meta.get("visual_mode", "NOVA"),
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
                    # Pré-verificação obrigatória: documentos que falharam por
                    # falta de conversor precisam poder ser tentados novamente
                    # depois que o runtime for corrigido. A triagem chama
                    # `_converter_e_validar_um`, portanto todo DWG sem par DXF
                    # é convertido ANTES da sanidade/classificação.
                    pendentes = [
                        d for d in documentos if d["status"] in ("pendente", "erro")
                    ]
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
                        status_final = "classificado" if inequivoco else "revisar"
                        classe_final = doc["classe_sugerida"] if inequivoco else None
                        pavimento_final = doc["pavimento_sugerido"] if inequivoco else None
                        repo.atualizar_classificacao_documento(
                            conn, item["doc_id"],
                            status=status_final,
                            classe_confirmada=classe_final,
                            pavimento_confirmado=pavimento_final,
                        )
                        repo.limpar_erro_documento(conn, item["doc_id"])
                        _registrar_dxf_convertido(
                            conn,
                            obra_id=obra["id"],
                            documento_origem=doc,
                            dxf_path=item.get("dxf_path"),
                            status=status_final,
                            classe_confirmada=classe_final,
                            pavimento_confirmado=pavimento_final,
                        )
                else:
                    if etapa_efetiva == "recortes" and "target_dxf_paths" in meta:
                        resultado = pipeline_runner.executar_recortes(
                            settings, obra, dry_run=False, log_path=log_path,
                            target_dxf_paths=meta.get("target_dxf_paths") or [],
                        )
                    else:
                        resultado = pipeline_runner.executar_etapa(
                            settings, etapa_efetiva, obra, secao=meta.get("secao"), pav=meta.get("pav"),
                            dry_run=False, log_path=log_path,
                        )
            finally:
                release_lock(lock)

        if resultado.ok:
            if meta.get("cascade_n5"):
                # O headless SA materializa o N3 da mesma rodada. Depois disso,
                # unifica apenas classes que já passaram pelo gate humano.
                for class_code in ("PL", "LV", "FV", "LAJ"):
                    validation = repo.obter_validacao_classe(conn, obra["id"], class_code)
                    if not validation.get("validado"):
                        continue
                    n5_release.liberar_n5(
                        conn, settings, obra=obra, classe=class_code,
                        pavimento=meta.get("pav") or "GERAL",
                        membro_id=meta.get("membro_id") or obra.get("membro_id") or "system",
                        job_id=job["id"],
                        engine_version=job.get("engine_version"), dry_run=False,
                        visual_mode=("NOVA" if class_code == "LV" else meta.get("visual_mode", "NOVA")),
                    )
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
                    dxf_processados = [
                        item["dxf_path"]
                        for item in resultado.artefatos.get("documentos", [])
                        if item.get("ok") and item.get("dxf_path")
                    ]
                    # Granularidade rígida: o recorte automático recebe apenas
                    # os DXFs aprovados por ESTA triagem. Documentos antigos já
                    # classificados/aprovados não entram novamente no motor.
                    if dxf_processados:
                        ev = pipeline_runner.engine_version(settings.repo_root)
                        proximo_job_id = repo.enfileirar_job(conn, obra_id=obra["id"], engine_version=ev)
                        proxima_meta = {
                            "etapa": "recortes",
                            "target_dxf_paths": dxf_processados,
                            "origin_triage_job_id": job["id"],
                        }
                        app_state.job_meta[proximo_job_id] = proxima_meta
                        # Não depender apenas do mapa em memória: se o portal
                        # reiniciar entre triagem e recortes, o worker recupera
                        # também o escopo granular correto.
                        repo.salvar_job_meta(conn, proximo_job_id, proxima_meta)
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
        if etapa == 'preprocessamento' and isinstance(exc, InterruptedError):
            return  # Mantém o cancelamento persistido pelo operador.
        log.exception("job %s falhou", job["id"])
        if etapa == "qa_agentico" and meta.get("round_id"):
            itens = repo.listar_qa_items(conn, meta["round_id"])
            concluidos = sum(item["status"] == "completed" for item in itens)
            repo.finalizar_qa_round(
                conn, meta["round_id"], "partial_failed" if concluidos else "failed"
            )
        repo.finalizar_job(conn, job["id"], "falhou", erro_msg=str(exc)[:500])
        if etapa not in {"qa_agentico", "preprocessamento"}:
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
