"""Controles persistentes de pausa, retomada e cancelamento da fila."""

from portal.db import repository as repo


def _job(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra controles", pasta_drive_id="p-controle"
    )
    return obra_id, repo.enfileirar_job(conn, obra_id=obra_id)


def test_pausar_e_continuar_job_preserva_identidade(conn, membro_id):
    _obra_id, job_id = _job(conn, membro_id)

    pausado = repo.pausar_job(conn, job_id)
    assert pausado["status"] == "cancelado"
    assert pausado["erro_msg"] == repo.PAUSA_OPERADOR
    assert repo.consumir_job(conn) is None

    retomado = repo.continuar_job(conn, job_id)
    assert retomado["id"] == job_id
    assert retomado["status"] == "na_fila"
    assert retomado["erro_msg"] is None
    assert repo.consumir_job(conn)["id"] == job_id


def test_cancelar_pausa_impede_retomada(conn, membro_id):
    _obra_id, job_id = _job(conn, membro_id)
    assert repo.pausar_job(conn, job_id)

    cancelado = repo.cancelar_job_operador(conn, job_id)
    assert cancelado["status"] == "cancelado"
    assert cancelado["erro_msg"] == repo.CANCELAMENTO_OPERADOR
    assert repo.continuar_job(conn, job_id) is None
    assert repo.consumir_job(conn) is None


def test_retomar_qa_mantem_itens_concluidos(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra QA controles", pasta_drive_id="p-qa-controle"
    )
    round_id, job_id = repo.enfileirar_qa_round(
        conn, obra_id=obra_id, membro_id=membro_id, classe="FV",
        pavimento="13_PAV", layer="L1", items=["V301", "V302"],
    )
    primeiro = conn.execute(
        "SELECT id FROM portal_qa_items WHERE round_id=? ORDER BY ordinal LIMIT 1", (round_id,)
    ).fetchone()
    conn.execute("UPDATE portal_qa_items SET status='completed' WHERE id=?", (primeiro["id"],))
    conn.execute("UPDATE portal_qa_rounds SET status='running' WHERE id=?", (round_id,))
    conn.commit()

    assert repo.pausar_job(conn, job_id)
    assert repo.continuar_job(conn, job_id)
    qa_round = repo.obter_qa_round(conn, round_id)
    items = repo.listar_qa_items(conn, round_id)
    assert qa_round["status"] == "queued"
    assert [item["status"] for item in items] == ["completed", "queued"]
