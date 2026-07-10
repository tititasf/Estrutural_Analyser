"""Testes HTTP reais das rotas N1 (viewer nativo) — 2026-07-06.

Usa a obra real TMC-EST-PE-6000-13P-R03 (rodada real de SA feita nesta sessão)
como fixture: cria uma obra de teste com `local_path` apontando pro diretório
real em disco (leitura, nunca escreve nele). Se os artefatos reais não
existirem nesta máquina, os testes são pulados.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR_REAL = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"

pytestmark = pytest.mark.skipif(
    not (_OBRA_DIR_REAL / "estado_13_PAV.json").is_file(),
    reason="obra real TMC-EST-PE-6000-13P-R03 sem estado_13_PAV.json nesta máquina",
)


@contextlib.asynccontextmanager
async def _app_cliente(settings):
    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    c.close()
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


def _obra_com_sa_real(settings) -> str:
    c = connection.init_db(settings.db_path)
    ana = repo.obter_membro_por_login(c, "ana")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraComSAReal", pasta_drive_id="folder-ana",
        arquivo_hash="hash-sa-real", estado="pronta",
        local_path=str(_OBRA_DIR_REAL),
    )
    c.close()
    return obra_id


@pytest.mark.asyncio
async def test_listar_classes_n1_conta_itens_reais(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_sa_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n1/classes")
        assert r.status_code == 200
        body = r.json()
        assert "13_PAV" in body["pavimentos"]
        por_classe = {c["classe"]: c["total"] for c in body["classes"]}
        assert por_classe["pilares"] == 46
        assert por_classe["lajes"] == 31
        assert por_classe["fundo"] == 106


@pytest.mark.asyncio
async def test_listar_itens_de_uma_classe(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_sa_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n1/pilares")
        assert r.status_code == 200
        body = r.json()
        assert body["pavimento"] == "13_PAV"
        assert len(body["itens"]) == 46
        assert any(i["item_id"] == "P1" for i in body["itens"])


@pytest.mark.asyncio
async def test_obter_item_n1_pilar_com_foto_real(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_sa_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n1/pilares/P1")
        assert r.status_code == 200
        body = r.json()
        assert body["campos"]["Nome"] == "P1"
        assert body["foto_n1"] is not None and "<svg" in body["foto_n1"]
        assert body["foto_n3"] is None  # honesto: N3 nao existe pra pilares nesta obra


@pytest.mark.asyncio
async def test_obter_item_n1_fundo_com_n1_e_n3_reais(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_sa_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n1/pilares")  # so' pra achar 1 item de fundo, ver abaixo
        r2 = await client.get(f"/obras/{obra_id}/n1/fundo")
        assert r2.status_code == 200
        item_id = next(i["item_id"] for i in r2.json()["itens"] if i["titulo"].startswith("V1 "))
        r3 = await client.get(f"/obras/{obra_id}/n1/fundo/{item_id}")
        assert r3.status_code == 200
        body = r3.json()
        assert body["foto_n1"] is not None
        assert body["foto_n3"] is not None


@pytest.mark.asyncio
async def test_obter_item_n1_nao_encontrado_404(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_sa_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n1/pilares/P999_NAO_EXISTE")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_obra_sem_sa_rodado_devolve_vazio_sem_erro(settings):
    """Obra criada sem nenhum estado_<pav>.json (SA nunca rodou) -> listas
    vazias, nunca 500 — comportamento honesto de 'ainda não processado'."""
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="ObraSemSA", pasta_drive_id="folder-ana",
            arquivo_hash="hash-sem-sa", estado="aguardando_ingestao",
        )
        c.close()
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n1/classes")
        assert r.status_code == 200
        assert r.json()["pavimentos"] == []
        r2 = await client.get(f"/obras/{obra_id}/n1/pilares")
        assert r2.status_code == 200
        assert r2.json()["itens"] == []


@pytest.mark.asyncio
async def test_n1_de_obra_de_outro_membro_e_recusado_403(settings):
    c = connection.init_db(settings.db_path)
    bruno = repo.criar_membro(c, login="bruno", nome="Bruno",
                              senha_hash=auth.hash_senha("x"), drive_folder_id="folder-bruno")
    obra_bruno = repo.criar_obra(c, membro_id=bruno, nome="ObraBruno",
                                 pasta_drive_id="folder-bruno", arquivo_hash="h-bruno")
    c.close()
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_bruno}/n1/classes")
        assert r.status_code == 403
