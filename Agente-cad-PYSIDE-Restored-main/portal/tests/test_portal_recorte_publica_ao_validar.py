"""Ao validar um recorte (Torre 1/Detalhes) na Triagem, o Portal minta na
hora o código de pavimento + o código próprio do recorte em
`public_consulta.db` [2026-07-13] — pedido do dono: "garanta que ao validar
se gere o codigo do pavimento... e os detalhes tambem é bom ter codigo".
Isso NUNCA depende do SA ter rodado (diferente do auto_publish_poller, que
só publica obra inteira em `estado='pronta'`).

Setup 100% sintético (sem depender de fixtures DXF reais no disco) — só
precisa que `torre_crop.set_recorte_validado` grave `validado.json` (não
lê o `.dxf` em si no caminho de validar=True).
"""

from __future__ import annotations

import sqlite3

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo


@pytest.mark.asyncio
async def test_validar_recorte_minta_codigo_de_pavimento_e_recorte(settings, tmp_path):
    obra_dir = tmp_path / "obra_recorte_validar"
    obra_dir.mkdir()

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    ana = repo.obter_membro_por_login(c, "ana")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraRecorteValidar", pasta_drive_id="folder-ana",
        arquivo_hash="hash-recorte-validar", estado="processando", local_path=str(obra_dir),
    )
    c.execute(
        "INSERT INTO portal_documentos (id, obra_id, arquivo_nome, status, pavimento_confirmado) "
        "VALUES ('doc-1', ?, 'BRUTO-TESTE.dxf', 'classificado', 'TERREO')",
        (obra_id,),
    )
    c.commit()
    c.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "ana", "senha": "segredo123"})
            r = await client.post(
                f"/obras/{obra_id}/recortes/brutos/BRUTO-TESTE/torre_1/validar",
                json={"validado": True},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["validado"] is True
            assert body["code_publico_pavimento"]
            assert body["code_publico_recorte"]
            assert body["code_publico_pavimento"] != body["code_publico_recorte"]
            assert body["referencia_pavimento"] == "ObraRecorteValidar › Térreo"
            assert body["referencia_recorte"] == "ObraRecorteValidar › Térreo › Torre 1"

    pub = sqlite3.connect(str(settings.public_consulta_db_path))
    pub.row_factory = sqlite3.Row
    row_pav = pub.execute(
        "SELECT code FROM public_codes WHERE obra_id=? AND pavimento='TERREO' AND kind='pavimento'",
        (obra_id,),
    ).fetchone()
    assert row_pav is not None
    assert row_pav["code"] == body["code_publico_pavimento"]

    row_rec = pub.execute(
        "SELECT * FROM public_codes WHERE obra_id=? AND kind='recorte'", (obra_id,),
    ).fetchone()
    assert row_rec is not None
    assert row_rec["classe"] == "torre_1"
    assert row_rec["item_id"] == "BRUTO-TESTE"
    assert row_rec["titulo_publico"] == "Torre 1"
    pub.close()


@pytest.mark.asyncio
async def test_invalidar_recorte_nao_minta_nada(settings, tmp_path):
    """Invalidar um recorte não deve mintar código nenhum — só validar sim."""
    obra_dir = tmp_path / "obra_recorte_invalidar"
    obra_dir.mkdir()

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="bia", nome="Bia Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-bia",
    )
    bia = repo.obter_membro_por_login(c, "bia")
    obra_id = repo.criar_obra(
        c, membro_id=bia["id"], nome="ObraRecorteInvalidar", pasta_drive_id="folder-bia",
        arquivo_hash="hash-recorte-invalidar", estado="processando", local_path=str(obra_dir),
    )
    c.execute(
        "INSERT INTO portal_documentos (id, obra_id, arquivo_nome, status, pavimento_confirmado) "
        "VALUES ('doc-2', ?, 'BRUTO-TESTE.dxf', 'classificado', 'TERREO')",
        (obra_id,),
    )
    c.commit()
    c.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "bia", "senha": "segredo123"})
            r = await client.post(
                f"/obras/{obra_id}/recortes/brutos/BRUTO-TESTE/torre_1/validar",
                json={"validado": False},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["validado"] is False
            assert "code_publico_pavimento" not in body

    assert not settings.public_consulta_db_path.exists()


@pytest.mark.asyncio
async def test_validar_recorte_sem_pavimento_classificado_nao_quebra(settings, tmp_path):
    """Doc sem pavimento_confirmado/sugerido ainda — validar continua
    funcionando, só não minta nada (sem pavimento não dá pra mintar)."""
    obra_dir = tmp_path / "obra_recorte_sem_pav"
    obra_dir.mkdir()

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="caio", nome="Caio Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-caio",
    )
    caio = repo.obter_membro_por_login(c, "caio")
    obra_id = repo.criar_obra(
        c, membro_id=caio["id"], nome="ObraRecorteSemPav", pasta_drive_id="folder-caio",
        arquivo_hash="hash-recorte-sem-pav", estado="processando", local_path=str(obra_dir),
    )
    c.execute(
        "INSERT INTO portal_documentos (id, obra_id, arquivo_nome, status) "
        "VALUES ('doc-3', ?, 'BRUTO-TESTE.dxf', 'classificado')",
        (obra_id,),
    )
    c.commit()
    c.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "caio", "senha": "segredo123"})
            r = await client.post(
                f"/obras/{obra_id}/recortes/brutos/BRUTO-TESTE/torre_1/validar",
                json={"validado": True},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["validado"] is True
            assert body["code_publico_pavimento"] is None
            assert body["code_publico_recorte"] is None
