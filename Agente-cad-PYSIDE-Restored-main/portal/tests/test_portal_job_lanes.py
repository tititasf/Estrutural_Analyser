"""Duas raias de jobs (pesada × QA) com conflito por obra+pavimento (dono 2026-10-02)."""

from __future__ import annotations

from portal.db import connection, repository as repo


def _setup(db_path):
    conn = connection.init_db(db_path)
    membro = repo.criar_membro(conn, login="ana", nome="Ana", senha_hash="h", drive_folder_id="f")
    obra_a = repo.criar_obra(conn, membro_id=membro, nome="A", pasta_drive_id="pa")
    obra_b = repo.criar_obra(conn, membro_id=membro, nome="B", pasta_drive_id="pb")
    return conn, obra_a, obra_b


def _job(conn, obra_id, **meta):
    job_id = repo.enfileirar_job(conn, obra_id=obra_id)
    repo.salvar_job_meta(conn, job_id, meta)
    return job_id


def test_raias_rodam_em_paralelo_em_obras_diferentes(db_path):
    conn, obra_a, obra_b = _setup(db_path)
    pesado = _job(conn, obra_a, etapa="sa", pav="13_PAV")
    qa = _job(conn, obra_b, etapa="qa_agentico")
    assert repo.consumir_job(conn, raia=repo.RAIA_PESADA)["id"] == pesado
    assert repo.consumir_job(conn, raia=repo.RAIA_QA)["id"] == qa


def test_qa_espera_job_pesado_do_mesmo_escopo(db_path):
    conn, obra_a, obra_b = _setup(db_path)
    _job(conn, obra_a, etapa="sa", pav="13_PAV")
    _job(conn, obra_a, etapa="qa_agentico")
    qa_b = _job(conn, obra_b, etapa="qa_agentico")
    # o pesado da obra A ainda está na fila: o QA da A não pode passar à frente dele
    assert repo.consumir_job(conn, raia=repo.RAIA_QA)["id"] == qa_b
    assert repo.consumir_job(conn, raia=repo.RAIA_QA) is None
    repo.consumir_job(conn, raia=repo.RAIA_PESADA)
    assert repo.consumir_job(conn, raia=repo.RAIA_QA) is None  # agora rodando


def test_pesado_espera_so_qa_rodando_do_mesmo_pavimento(db_path):
    conn, obra_a, _ = _setup(db_path)
    _job(conn, obra_a, etapa="qa_agentico")  # sem pavimento = obra inteira
    assert repo.consumir_job(conn, raia=repo.RAIA_QA) is not None
    _job(conn, obra_a, etapa="sa", pav="13_PAV")
    assert repo.consumir_job(conn, raia=repo.RAIA_PESADA) is None


def test_pesado_de_outro_pavimento_nao_conflita(db_path):
    conn, obra_a, _ = _setup(db_path)
    a = _job(conn, obra_a, etapa="sa", pav="13_PAV")
    _job(conn, obra_a, etapa="sa", pav="14_PAV")
    assert repo._mesmo_escopo(("pesada", obra_a, "13_PAV"), ("qa", obra_a, "14_PAV")) is False
    assert repo._mesmo_escopo(("pesada", obra_a, None), ("qa", obra_a, "14_PAV")) is True
    # dentro da raia pesada continua 1 por vez, em FIFO
    assert repo.consumir_job(conn, raia=repo.RAIA_PESADA)["id"] == a


def test_consumo_sem_raia_mantem_fifo_unica(db_path):
    conn, obra_a, _ = _setup(db_path)
    qa = _job(conn, obra_a, etapa="qa_agentico")
    _job(conn, obra_a, etapa="sa", pav="13_PAV")
    assert repo.consumir_job(conn)["id"] == qa
