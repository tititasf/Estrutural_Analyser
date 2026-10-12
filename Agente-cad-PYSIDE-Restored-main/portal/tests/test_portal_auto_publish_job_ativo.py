"""Obra com job ativo não é republicada até o job terminar [2026-10-12]."""

from __future__ import annotations

from portal.app import auto_publish_poller
from portal.db import connection, repository as repo
from portal.tests.test_portal_auto_publish import _criar_obra, _montar_obra_dir_real


def test_obra_com_job_ativo_espera_o_fim_do_job(settings, tmp_path, monkeypatch):
    obra_dir = _montar_obra_dir_real(tmp_path, "ObraEmCadeia")
    obra_id = _criar_obra(settings, nome="ObraEmCadeia", estado_obra="pronta", local_path=obra_dir)
    publicadas = []
    monkeypatch.setattr(auto_publish_poller, "publicar",
                        lambda obra, *a, **k: publicadas.append(obra["id"]))
    c = connection.init_db(settings.db_path)
    try:
        job_id = repo.enfileirar_job(c, obra_id=obra_id)
        assert auto_publish_poller._ciclo(settings)["ignoradas"] == 1
        assert publicadas == []
        repo.finalizar_job(c, job_id, "concluido")
    finally:
        c.close()
    assert auto_publish_poller._ciclo(settings)["publicadas"] == 1
    assert publicadas == [obra_id]
