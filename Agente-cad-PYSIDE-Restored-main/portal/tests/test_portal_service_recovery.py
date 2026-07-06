"""§6 smoke P3/P5 — sobe e derruba a app (lifespan) sem erro; retomada durável.

Escopo testável headless (sem reiniciar a máquina real):
- SM leve: create_app + lifespan sobem e descem limpos com poll_enabled=False (task 6).
- SM6.2/I2.5: job PENDING no store durável é retomado após "reinício" (novo lifespan).
- SM6.3/U1.5: o "visto" do poller (dedup por hash) sobrevive a reinício.

O reinício real da máquina (P3 literal) e o subprocesso uvicorn de longa duração
NÃO são exercidos aqui — ficam como TODO documentado no relatório de QA (o handoff
os marca @pytest.mark.slow; sem um supervisor de verdade no CI, viram teste manual).
"""

from __future__ import annotations

import pytest

from portal.app import auth, drive_poller
from portal.app.main import create_app
from portal.db import connection, repository as repo


# --------------------------------------------------------------------------- #
# Task 6 — smoke: lifespan sobe e desce sem erro (poll_enabled=False)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_lifespan_sobe_e_desce_sem_erro(settings):
    """create_app + lifespan: startup migra db + worker; shutdown para tudo, sem exceção."""
    assert settings.poll_enabled is False
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        # dentro do lifespan: estado montado
        assert app.state.settings is settings
        assert app.state.worker is not None
        assert app.state.poller_task is None       # poll_enabled=False -> sem task de poller
        assert app.state.estado_global["drive"] == "ok"
        # db foi migrado (as 6 tabelas existem)
        c = connection.get_connection(settings.db_path)
        nomes = {r["name"] for r in
                 c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        c.close()
        assert "portal_jobs" in nomes and "portal_membros" in nomes
    # saiu do contexto sem levantar -> shutdown limpo


@pytest.mark.asyncio
async def test_lifespan_com_poller_habilitado_cria_task(tmp_path):
    """poll_enabled=True cria a task do poller; shutdown a cancela sem vazar exceção.

    Usa FakeDriveClient (montar_drive_client cai nele sem credencial) -> nenhuma rede.
    """
    from portal.app.config import load_settings

    settings = load_settings(
        db_path=tmp_path / "portal_data.db", poll_enabled=True,
        poll_interval_s=1, dados_obras_dir=tmp_path / "DADOS-OBRAS",
        logs_dir=tmp_path / "logs", status_md_path=tmp_path / "STATUS.md",
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert app.state.poller_task is not None
        assert isinstance(app.state.drive_client, drive_poller.FakeDriveClient)
    # shutdown cancelou a task; nenhum erro propagado


# --------------------------------------------------------------------------- #
# SM6.2 / I2.5 — job PENDING sobrevive ao "reinício" e é reconciliado/consumível
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_sm6_2_job_pendente_sobrevive_reinicio(settings):
    """Job 'na_fila' persistido antes do reinício continua consumível depois."""
    # "antes do reinício": cria membro/obra/job direto no db durável
    c = connection.init_db(settings.db_path)
    membro = repo.criar_membro(c, login="ana", nome="Ana",
                               senha_hash=auth.hash_senha("x"), drive_folder_id="f")
    obra_id = repo.criar_obra(c, membro_id=membro, nome="O", pasta_drive_id="p")
    job_id = repo.enfileirar_job(c, obra_id=obra_id)
    c.close()

    # "reinício": novo lifespan (novo processo lógico) abre o MESMO db
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        c2 = connection.get_connection(settings.db_path)
        try:
            row = c2.execute("SELECT status FROM portal_jobs WHERE id=?", (job_id,)).fetchone()
            assert row["status"] in ("na_fila", "executando", "concluido", "falhou")
            # o job não sumiu: ainda existe atrelado à obra
            jobs = repo.listar_jobs_por_obra(c2, obra_id)
            assert any(j["id"] == job_id for j in jobs)
        finally:
            c2.close()


# --------------------------------------------------------------------------- #
# SM6.3 / U1.5 — "visto" do poller (dedup por hash) sobrevive ao reinício
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_sm6_3_dedup_sobrevive_reinicio(settings, tmp_path):
    """Obra já ingerida (hash no db durável) não é reprocessada após reinício."""
    import ezdxf

    fake_raiz = tmp_path / "drive"
    pasta = fake_raiz / "folder-ana"
    pasta.mkdir(parents=True)
    doc = ezdxf.new(); doc.modelspace().add_line((0, 0), (1, 1))
    doc.saveas(pasta / "obra_x.dxf")

    # ingestão inicial
    c = connection.init_db(settings.db_path)
    repo.criar_membro(c, login="ana", nome="Ana", senha_hash="h", drive_folder_id="folder-ana")
    membro = repo.obter_membro_por_login(c, "ana")
    client = drive_poller.FakeDriveClient(fake_raiz)
    n1 = drive_poller.varrer_uma_vez(c, client, settings, membros=[membro])
    assert len(n1) == 1
    c.close()

    # "reinício": novo lifespan + nova varredura -> hash já visto, nada novo
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        c2 = connection.get_connection(settings.db_path)
        try:
            membro2 = repo.obter_membro_por_login(c2, "ana")
            n2 = drive_poller.varrer_uma_vez(c2, client, settings, membros=[membro2])
            assert n2 == []  # dedup durável
        finally:
            c2.close()
