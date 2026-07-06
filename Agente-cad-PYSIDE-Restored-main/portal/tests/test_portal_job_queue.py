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
