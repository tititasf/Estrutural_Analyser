"""§2 fila de jobs com exclusão mútua — testes de integração (threads/subprocess reais).

Dois níveis de serialização no código real:
  1. repository.consumir_job(): SELECT+UPDATE dentro de `with conn` (transação) — dois
     consumidores concorrentes NUNCA pegam o mesmo job (I2.1 adaptado ao código real).
  2. single_instance lock ('headless_sa'): rede de segurança inter-processo reusada por
     portal.app.jobs (I2.2/I2.3/I2.4) — estende tests/test_single_instance.py.

Handoff supôs `JobQueue.run_next()`; a implementação real é `repository.consumir_job` +
`JobWorker` + o lock `single_instance`. Os testes provam o MESMO invariante (1 job por
vez, nunca duplicado, lock liberado em crash) sobre a interface real.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from portal.db import connection, repository as repo

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCK_SRC = _REPO_ROOT / "scripts" / "arete"
sys.path.insert(0, str(_LOCK_SRC))

from single_instance import acquire_lock, release_lock, wait_for_lock  # noqa: E402


# --------------------------------------------------------------------------- #
# I2.1 (adaptado) — dois consumidores concorrentes NUNCA pegam o mesmo job
# --------------------------------------------------------------------------- #

def test_i2_1_consumo_concorrente_nunca_duplica(db_path):
    """N threads reais chamam consumir_job em paralelo; cada job é consumido 1x só.

    Prova o invariante central da fila com concorrência real (não mock): a transação
    SELECT+UPDATE de consumir_job serializa o consumo mesmo sob N escritores.
    """
    # cada thread precisa da PRÓPRIA conexão sqlite (sqlite3 não é thread-safe entre threads)
    setup = connection.init_db(db_path)
    membro = repo.criar_membro(setup, login="ana", nome="Ana", senha_hash="h",
                               drive_folder_id="f")
    obra_id = repo.criar_obra(setup, membro_id=membro, nome="Obra", pasta_drive_id="p")
    n_jobs = 40
    job_ids = {repo.enfileirar_job(setup, obra_id=obra_id) for _ in range(n_jobs)}
    setup.close()

    consumidos: list[str] = []
    consumidos_lock = threading.Lock()
    barreira = threading.Barrier(8)

    def worker():
        conn = connection.get_connection(db_path)
        try:
            barreira.wait()  # largada simultânea maximiza a chance de corrida
            while True:
                job = repo.consumir_job(conn)
                if job is None:
                    return
                with consumidos_lock:
                    consumidos.append(job["id"])
        finally:
            conn.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # cada job consumido exatamente uma vez; nenhum duplicado; nenhum perdido
    assert len(consumidos) == n_jobs
    assert len(set(consumidos)) == n_jobs      # zero duplicatas
    assert set(consumidos) == job_ids          # exatamente os enfileirados


def test_i2_1b_prioridade_e_fifo_sob_concorrencia(db_path):
    """Mesmo consumo concorrente respeita prioridade e desempate FIFO por rowid."""
    setup = connection.init_db(db_path)
    membro = repo.criar_membro(setup, login="ana", nome="Ana", senha_hash="h",
                               drive_folder_id="f")
    obra_id = repo.criar_obra(setup, membro_id=membro, nome="O", pasta_drive_id="p")
    alta = repo.enfileirar_job(setup, obra_id=obra_id, prioridade=9)
    setup.close()

    conn = connection.get_connection(db_path)
    try:
        primeiro = repo.consumir_job(conn)
        assert primeiro["id"] == alta  # prioridade 9 sai antes de qualquer prioridade 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# I2.2 — segundo aguarda com wait (reuso do lock single_instance)
# --------------------------------------------------------------------------- #

def test_i2_2_segundo_aguarda_com_wait(tmp_path):
    """Subprocesso segura 'portal_worker' ~2s; wait_for_lock espera e adquire (sem race)."""
    code = (
        "import sys, time; sys.path.insert(0, r'%s'); "
        "from single_instance import acquire_lock; "
        "h, e = acquire_lock('portal_worker', r'%s'); "
        "assert h is not None; print('LOCKED', flush=True); time.sleep(2)"
        % (str(_LOCK_SRC), str(tmp_path))
    )
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "LOCKED"
        h, err = wait_for_lock("portal_worker", tmp_path, poll_s=0.5, timeout_s=30.0)
        assert h is not None and err is None
        release_lock(h)
    finally:
        proc.kill()
        proc.wait()


# --------------------------------------------------------------------------- #
# I2.3 — crash do detentor libera a fila (anti-órfão, SO libera o lock)
# --------------------------------------------------------------------------- #

def test_i2_3_crash_libera_a_fila(tmp_path):
    """Subprocesso com o lock é morto; o SO libera -> próximo adquire (espelha o base)."""
    code = (
        "import sys, time; sys.path.insert(0, r'%s'); "
        "from single_instance import acquire_lock; "
        "h, e = acquire_lock('portal_worker', r'%s'); "
        "assert h is not None; print('LOCKED', flush=True); time.sleep(10)"
        % (str(_LOCK_SRC), str(tmp_path))
    )
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "LOCKED"
        # enquanto vivo, não conseguimos o lock
        h, err = acquire_lock("portal_worker", tmp_path)
        assert h is None and "pid=" in (err or "")
    finally:
        proc.kill()
        proc.wait()
    # após kill, o SO liberou -> agora adquire
    h2, err2 = acquire_lock("portal_worker", tmp_path)
    assert h2 is not None and err2 is None
    release_lock(h2)


# --------------------------------------------------------------------------- #
# I2.5 — estado da fila é durável: job 'executando' órfão é reconciliado no reinício
# --------------------------------------------------------------------------- #

def test_i2_5_reconciliacao_reenfileira_orfaos(db_path):
    """Job que ficou 'executando' (crash no meio) volta para 'na_fila' na reconciliação."""
    from portal.app import jobs as jobs_mod

    conn = connection.init_db(db_path)
    membro = repo.criar_membro(conn, login="ana", nome="Ana", senha_hash="h",
                               drive_folder_id="f")
    obra_id = repo.criar_obra(conn, membro_id=membro, nome="O", pasta_drive_id="p")
    job_id = repo.enfileirar_job(conn, obra_id=obra_id)
    # simula crash: job foi consumido (executando) mas nunca finalizado
    consumido = repo.consumir_job(conn)
    assert consumido["id"] == job_id and consumido["status"] == "executando"

    # "reinício": reconciliar re-enfileira o órfão
    n = jobs_mod.reconciliar_jobs(conn)
    assert n == 1
    reposto = conn.execute("SELECT status, iniciado_em FROM portal_jobs WHERE id=?",
                           (job_id,)).fetchone()
    assert reposto["status"] == "na_fila"
    assert reposto["iniciado_em"] is None  # limpo para nova execução
    # nada "some": o job continua consumível
    assert repo.consumir_job(conn)["id"] == job_id
    conn.close()


# --------------------------------------------------------------------------- #
# Regressão 2026-07-06 — DEADLOCK real achado rodando SA pela 1a vez contra
# Obra_TREINO_1: o worker segurava 'headless_sa' ANTES de lançar o subprocess
# `headless_sa_analise.py --wait`, que por sua vez tenta adquirir a MESMA trava
# internamente — o filho esperava o próprio pai soltar, o que só aconteceria
# quando o filho terminasse. Travou 30min (timeout default de wait_for_lock)
# até o filho desistir e sair com erro. Fix: 'sa' não trava mais no worker —
# quem serializa é o próprio subprocess via --wait. 'triagem'/'recortes'
# continuam travando no worker (não têm serialização própria).
# --------------------------------------------------------------------------- #

class _AppStateFake:
    def __init__(self, settings, db_conn):
        self.settings = settings
        self.db = db_conn
        self.job_meta = {}


def _job_pronto_para_processar(conn):
    membro = repo.criar_membro(conn, login="ana", nome="Ana", senha_hash="h", drive_folder_id="f")
    obra_id = repo.criar_obra(conn, membro_id=membro, nome="O", pasta_drive_id="p")
    job_id = repo.enfileirar_job(conn, obra_id=obra_id)
    job = repo.consumir_job(conn)
    assert job["id"] == job_id
    return job


def test_sa_nao_chama_wait_for_lock_no_worker(settings, monkeypatch):
    """etapa='sa': processar_um_job NÃO deve chamar wait_for_lock/release_lock —
    é exatamente essa chamada, feita ANTES do subprocess (que já tem seu próprio
    --wait), que causava o deadlock."""
    from portal.app import jobs as jobs_mod
    from portal.db import connection as db_conn_mod

    conn = db_conn_mod.init_db(settings.db_path)
    job = _job_pronto_para_processar(conn)

    chamadas = {"wait_for_lock": 0, "release_lock": 0}
    monkeypatch.setattr(jobs_mod, "wait_for_lock",
                        lambda *a, **k: (chamadas.__setitem__("wait_for_lock", chamadas["wait_for_lock"] + 1), (object(), None))[1])
    monkeypatch.setattr(jobs_mod, "release_lock",
                        lambda *a, **k: chamadas.__setitem__("release_lock", chamadas["release_lock"] + 1))
    monkeypatch.setattr(
        jobs_mod.pipeline_runner, "executar_etapa",
        lambda *a, **k: type("R", (), {"ok": True, "log_tail": "", "artefatos": {}})(),
    )

    app_state = _AppStateFake(settings, conn)
    app_state.job_meta[job["id"]] = {"etapa": "sa"}
    jobs_mod.processar_um_job(app_state, job)

    assert chamadas["wait_for_lock"] == 0, "worker NÃO deve travar para 'sa' (subprocess já tem --wait)"
    assert chamadas["release_lock"] == 0
    row = conn.execute("SELECT status FROM portal_jobs WHERE id=?", (job["id"],)).fetchone()
    assert row["status"] == "concluido"
    conn.close()


def test_triagem_ainda_chama_wait_for_lock_no_worker(settings, monkeypatch):
    """etapa='triagem': accoreconsole NÃO tem serialização própria — o worker
    PRECISA continuar travando aqui (protege contra o dono rodando SA na app
    PySide6 ao mesmo tempo). Regressão: só 'sa' foi isento pelo fix acima."""
    from portal.app import jobs as jobs_mod
    from portal.db import connection as db_conn_mod

    conn = db_conn_mod.init_db(settings.db_path)
    job = _job_pronto_para_processar(conn)

    chamadas = {"wait_for_lock": 0, "release_lock": 0}
    monkeypatch.setattr(jobs_mod, "wait_for_lock",
                        lambda *a, **k: (chamadas.__setitem__("wait_for_lock", chamadas["wait_for_lock"] + 1), (object(), None))[1])
    monkeypatch.setattr(jobs_mod, "release_lock",
                        lambda *a, **k: chamadas.__setitem__("release_lock", chamadas["release_lock"] + 1))
    monkeypatch.setattr(
        jobs_mod.pipeline_runner, "executar_etapa",
        lambda *a, **k: type("R", (), {"ok": True, "log_tail": "", "artefatos": {}})(),
    )

    app_state = _AppStateFake(settings, conn)
    app_state.job_meta[job["id"]] = {"etapa": "triagem"}
    jobs_mod.processar_um_job(app_state, job)

    assert chamadas["wait_for_lock"] == 1, "worker DEVE travar para 'triagem' (accoreconsole sem --wait próprio)"
    assert chamadas["release_lock"] == 1
    row = conn.execute("SELECT status FROM portal_jobs WHERE id=?", (job["id"],)).fetchone()
    assert row["status"] == "concluido"
    conn.close()


def test_sa_item_dispara_microciclo_e_nao_toca_estado_da_obra(settings, monkeypatch):
    """etapa='sa_item' (P4 do escape hatch web): dispara APENAS o microciclo do
    item — nunca a etapa cheia — e não mexe em etapa_concluida/estado() da
    obra. É um item avulso criado pelo laço, não uma etapa formal do pipeline;
    tratá-lo como 'sa' completo corromperia o painel de progresso da obra."""
    from portal.app import jobs as jobs_mod
    from portal.db import connection as db_conn_mod

    conn = db_conn_mod.init_db(settings.db_path)
    job = _job_pronto_para_processar(conn)
    obra_antes = repo.obter_obra(conn, job["obra_id"])

    chamadas = {"wait_for_lock": 0, "microciclo": []}
    monkeypatch.setattr(jobs_mod, "wait_for_lock",
                        lambda *a, **k: (chamadas.__setitem__("wait_for_lock", chamadas["wait_for_lock"] + 1), (object(), None))[1])
    monkeypatch.setattr(jobs_mod, "release_lock", lambda *a, **k: None)

    def _fake_microciclo(settings, obra, *, secao, item, pav, dry_run, log_path=None):
        chamadas["microciclo"].append({"secao": secao, "item": item, "pav": pav, "dry_run": dry_run})
        return type("R", (), {"ok": True, "log_tail": ""})()

    monkeypatch.setattr(jobs_mod.pipeline_runner, "executar_microciclo_item", _fake_microciclo)

    app_state = _AppStateFake(settings, conn)
    app_state.job_meta[job["id"]] = {
        "etapa": "sa_item", "secao": "pilares", "item": "P900", "pav": "13_PAV",
    }
    jobs_mod.processar_um_job(app_state, job)

    assert chamadas["wait_for_lock"] == 0, "sa_item nao deve travar (subprocess ja tem --wait)"
    assert chamadas["microciclo"] == [
        {"secao": "pilares", "item": "P900", "pav": "13_PAV", "dry_run": False}
    ]

    row = conn.execute("SELECT status FROM portal_jobs WHERE id=?", (job["id"],)).fetchone()
    assert row["status"] == "concluido"

    obra_depois = repo.obter_obra(conn, job["obra_id"])
    assert obra_depois["estado"] == obra_antes["estado"]
    assert obra_depois["etapa_concluida"] == obra_antes["etapa_concluida"]
    conn.close()


def test_sa_item_com_falha_finaliza_job_sem_mexer_na_obra(settings, monkeypatch):
    from portal.app import jobs as jobs_mod
    from portal.db import connection as db_conn_mod

    conn = db_conn_mod.init_db(settings.db_path)
    job = _job_pronto_para_processar(conn)
    obra_antes = repo.obter_obra(conn, job["obra_id"])

    monkeypatch.setattr(
        jobs_mod.pipeline_runner, "executar_microciclo_item",
        lambda *a, **k: type("R", (), {"ok": False, "log_tail": "erro simulado do motor"})(),
    )

    app_state = _AppStateFake(settings, conn)
    app_state.job_meta[job["id"]] = {
        "etapa": "sa_item", "secao": "lajes", "item": "L1", "pav": "13_PAV",
    }
    jobs_mod.processar_um_job(app_state, job)

    row = conn.execute("SELECT status, erro_msg FROM portal_jobs WHERE id=?", (job["id"],)).fetchone()
    assert row["status"] == "falhou"
    assert "erro simulado" in row["erro_msg"]

    obra_depois = repo.obter_obra(conn, job["obra_id"])
    assert obra_depois["estado"] == obra_antes["estado"], (
        "falha de UM item nao pode marcar a obra inteira como 'erro'"
    )
    conn.close()
