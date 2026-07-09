"""§3/§5 fluxo HTTP básico + gate N5 (R9) via httpx.ASGITransport.

Por que ASGITransport e NÃO fastapi.testclient.TestClient: nesta máquina a combinação
starlette 0.27.0 + httpx 0.28.1 quebra o TestClient (`TypeError: Client.__init__()
got an unexpected keyword argument 'app'`) — confirmado rodando de verdade. httpx
0.28.1 tem ASGITransport, e pytest-asyncio 1.3.0 está instalado; então batemos na app
ASGI diretamente, o equivalente automatizado do que foi validado manualmente com
uvicorn+urllib.

Cobre: login -> sessão via cookie -> listar obras -> enfileirar job (etapa) ->
consultar job (GET /jobs/{id}); 401 sem sessão; e o gate 409 do N5 (S9.5: liberar N5
sem validação prévia é recusado).
"""

from __future__ import annotations

import contextlib

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo


@contextlib.asynccontextmanager
async def _app_cliente(settings):
    """Sobe a app (lifespan real: migra db, worker, poller off) e um AsyncClient ASGI.

    Semeia um membro 'ana' com senha conhecida ANTES do lifespan para o login funcionar.
    """
    # semeia membro no mesmo db que a app vai usar
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


def _obra_da_ana(settings, arquivo_hash: str = "hash-obra-1") -> str:
    """Cria uma obra para a ana direto no db (como se o poller a tivesse ingerido).

    Usa init_db (migração idempotente). Deve ser chamado DEPOIS de a ana existir
    (i.e. dentro do contexto _app_cliente, que semeia a ana no startup).
    """
    c = connection.init_db(settings.db_path)
    try:
        ana = repo.obter_membro_por_login(c, "ana")
        assert ana is not None, "ana precisa existir antes de criar a obra"
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="EdificioTeste", pasta_drive_id="folder-ana",
            arquivo_hash=arquivo_hash, estado="aguardando_ingestao",
        )
        return obra_id
    finally:
        c.close()


# --------------------------------------------------------------------------- #
# Fluxo feliz: login -> sessão -> listar obras -> enfileirar -> consultar job
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_fluxo_login_listar_enfileirar_consultar(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)  # ana já semeada pelo _app_cliente
        # 1) login errado -> 401
        r = await client.post("/login", json={"login": "ana", "senha": "errada"})
        assert r.status_code == 401

        # 2) login certo -> cookie de sessão setado
        r = await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert settings.session_cookie_name in client.cookies

        # 3) /me confirma a sessão
        r = await client.get("/me")
        assert r.status_code == 200 and r.json()["login"] == "ana"

        # 4) listar obras -> a obra ingerida aparece
        r = await client.get("/obras")
        assert r.status_code == 200
        body = r.json()
        assert body["membro"] == "ana"
        assert any(o["id"] == obra_id for o in body["obras"])

        # 5) enfileirar um job de etapa (triagem enfileira e retorna job_id)
        r = await client.post(f"/obras/{obra_id}/triagem")
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        assert r.json()["estado"] == "queued"

        # 6) consultar o job (pode já ter sido pego pelo worker; ambos são válidos)
        r = await client.get(f"/jobs/{job_id}")
        assert r.status_code == 200
        job = r.json()
        assert job["job_id"] == job_id
        assert job["obra_id"] == obra_id
        assert job["estado"] in ("queued", "running", "done", "error")


# --------------------------------------------------------------------------- #
# Sem sessão -> 401 nas rotas protegidas
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_sem_sessao_401(settings):
    async with _app_cliente(settings) as (_app, client):
        r = await client.get("/obras")
        assert r.status_code == 401
        r = await client.get("/me")
        assert r.status_code == 401


# --------------------------------------------------------------------------- #
# health -> 200 e reflete poll_enabled=False
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_health_ok(settings):
    async with _app_cliente(settings) as (_app, client):
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["poll_enabled"] is False


# --------------------------------------------------------------------------- #
# S9.5 (R9) — gate do N5: liberar sem validação prévia é RECUSADO (409)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_s9_5_n5_sem_validacao_recusa_409(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)  # ana já semeada pelo _app_cliente
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})

        # sem etapa 5 (validação) registrada -> POST /n5 deve segurar
        r = await client.post(f"/obras/{obra_id}/n5", json={"classe": "PL", "pavimento": "13"})
        assert r.status_code == 409
        assert "valida" in r.json()["detail"].lower()

        # registra a validação (n1_ok+n3_ok) -> agora libera (dry gating passa;
        # a montagem real do DXF pode falhar por falta de obra em disco, mas o GATE
        # de validação já não é mais o bloqueio — provamos que o gate soltou).
        r = await client.post(
            f"/obras/{obra_id}/validacao",
            json={"classe": "PL", "n1_ok": True, "n3_ok": True},
        )
        assert r.status_code == 200 and r.json()["libera_n5"] is True

        r = await client.post(f"/obras/{obra_id}/n5", json={"classe": "PL", "pavimento": "13"})
        # não pode mais ser 409 (o gate de validação liberou). O resultado da montagem
        # em si depende de artefatos em disco — 200 (montou/dry) ou erro de montagem,
        # NUNCA 409 de "validação não registrada".
        assert r.status_code != 409


# --------------------------------------------------------------------------- #
# Isolamento entre membros: obra de outro membro -> 403
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_obra_de_outro_membro_403(settings):
    # cria bruno + obra do bruno; ana logada tenta acessar -> 403
    c = connection.init_db(settings.db_path)  # migração idempotente (roda antes do lifespan)
    bruno = repo.criar_membro(c, login="bruno", nome="Bruno",
                              senha_hash=auth.hash_senha("x"), drive_folder_id="folder-bruno")
    obra_bruno = repo.criar_obra(c, membro_id=bruno, nome="ObraBruno",
                                 pasta_drive_id="folder-bruno", arquivo_hash="h-bruno")
    c.close()

    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_bruno}")
        assert r.status_code == 403


# --------------------------------------------------------------------------- #
# /app/status — publica STATUS.md no portal (achado do DevOps handoff: rota
# não existia — 2026-07-06).
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_status_sem_arquivo_mostra_mensagem_clara(settings):
    """settings de teste aponta status_md_path pra um arquivo que não existe."""
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/status")
        assert r.status_code == 200
        assert "ainda não foi gerado" in r.text


@pytest.mark.asyncio
async def test_status_renderiza_tabela_do_status_md(settings, tmp_path):
    """Com STATUS.md real presente, a tabela markdown vira <table> HTML de verdade."""
    settings.status_md_path.write_text(
        "## Última rodada Arete por classe\n\n"
        "| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| PIL | 13_PAV | x | 35 | 0 | 0 | 100.0% | sim | |\n",
        encoding="utf-8",
    )
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/status")
        assert r.status_code == 200
        assert "<table>" in r.text
        assert "PIL" in r.text and "100.0%" in r.text


@pytest.mark.asyncio
async def test_status_exige_sessao(settings):
    async with _app_cliente(settings) as (_app, client):
        r = await client.get("/app/status", follow_redirects=False)
        assert r.status_code == 303  # redireciona pro /login, não 401 (página HTML)


# --------------------------------------------------------------------------- #
# POST /obras/upload — upload direto pelo portal (2026-07-06, usuário não abre o Drive)
# --------------------------------------------------------------------------- #

def _dxf_bytes() -> bytes:
    import io

    import ezdxf

    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (1, 1))
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_upload_registra_obra_na_hora(settings):
    """Upload de verdade (multipart) -> vai pro FakeDriveClient -> aparece em GET /obras
    sem esperar o poller (o endpoint já dispara varrer_uma_vez)."""
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})

        r = await client.post(
            "/obras/upload",
            files={"arquivo": ("obra_upload.dxf", _dxf_bytes(), "application/octet-stream")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["novas_obras"] == 1

        r = await client.get("/obras")
        nomes = [o["arquivo_nome"] for o in r.json()["obras"]]
        assert "obra_upload.dxf" in nomes


@pytest.mark.asyncio
async def test_upload_extensao_invalida_e_recusado(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post(
            "/obras/upload",
            files={"arquivo": ("obra.txt", b"nao e' cad", "text/plain")},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_upload_sem_pasta_drive_e_recusado(settings):
    """Membro sem drive_folder_id configurado não pode enviar (peça ao dono)."""
    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="sem-pasta", nome="Sem Pasta",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id=None,
    )
    c.close()

    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "sem-pasta", "senha": "segredo123"})
        r = await client.post(
            "/obras/upload",
            files={"arquivo": ("obra.dxf", _dxf_bytes(), "application/octet-stream")},
        )
        assert r.status_code == 422
        assert "pasta" in r.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# Obra-como-container (2026-07-06): POST /obras/criar + POST /{id}/documentos +
# POST /{id}/documentos/{doc_id}/classificar — "criar Obra, poder descrevê-la
# e eleger nome, separar os docs recebidos nas classes, ver a triagem".
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_criar_obra_com_nome_e_descricao(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post(
            "/obras/criar", json={"nome": "Edificio Paraiso", "descricao": "13 pavimentos"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["nome"] == "Edificio Paraiso"
        assert body["obra_id"]
        assert body["pasta_drive_id"]

        r = await client.get(f"/obras/{body['obra_id']}")
        assert r.status_code == 200
        assert r.json()["obra"]["descricao"] == "13 pavimentos"
        assert r.json()["obra"]["nome"] == "Edificio Paraiso"
        assert r.json()["documentos"] == []


@pytest.mark.asyncio
async def test_criar_obra_nome_vazio_e_recusado(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "   "})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_upload_documentos_multiplos_classifica_cada_um(settings):
    """Upload de 2 documentos de classes diferentes na MESMA obra — cada um vira
    1 linha em portal_documentos com sua PROPRIA sugestão de classe/pavimento
    (nunca "1 upload = 1 obra")."""
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraMultiDoc"})
        obra_id = r.json()["obra_id"]

        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[
                ("arquivos", ("ALIMONTI - PARAISO - 13° PAV.- PL - R00.dxf", _dxf_bytes(), "application/octet-stream")),
                ("arquivos", ("ALIMONTI - PARAISO - 13° PAV.- FV - R00.dxf", _dxf_bytes(), "application/octet-stream")),
            ],
        )
        assert r.status_code == 200, r.text
        docs = r.json()["documentos"]
        assert len(docs) == 2
        assert all(d["ok"] for d in docs)
        classes = {d["classe_sugerida"] for d in docs}
        assert classes == {"PIL", "FV"}
        assert all(d["pavimento_sugerido"] == "13_PAV" for d in docs)

        r = await client.get(f"/obras/{obra_id}")
        body = r.json()
        assert len(body["documentos"]) == 2
        # status workflow ('pendente'->'classificado'/'revisar'/'erro') só muda
        # quando o job de triagem em lote roda (jobs.py); no upload em si os
        # docs ficam 'pendente' — classe_sugerida/pavimento_sugerido já vêm
        # preenchidos (conferido acima), mas a CONFIRMAÇÃO é outra etapa.
        assert body["resumo_documentos"].get("pendente") == 2


@pytest.mark.asyncio
async def test_upload_documentos_extensao_invalida_reportada_por_arquivo(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraExtInvalida"})
        obra_id = r.json()["obra_id"]

        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("nao_e_cad.txt", b"texto qualquer", "text/plain"))],
        )
        assert r.status_code == 200
        docs = r.json()["documentos"]
        assert docs[0]["ok"] is False
        assert "suportada" in docs[0]["erro"].lower()


@pytest.mark.asyncio
async def test_upload_documentos_duplicado_por_hash_nao_duplica(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraDedup"})
        obra_id = r.json()["obra_id"]

        conteudo = _dxf_bytes()
        r1 = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("a.dxf", conteudo, "application/octet-stream"))],
        )
        r2 = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("a.dxf", conteudo, "application/octet-stream"))],
        )
        assert r2.json()["documentos"][0]["duplicado"] is True
        assert r2.json()["documentos"][0]["doc_id"] == r1.json()["documentos"][0]["doc_id"]

        r = await client.get(f"/obras/{obra_id}")
        assert len(r.json()["documentos"]) == 1  # nao duplicou


@pytest.mark.asyncio
async def test_classificar_documento_manual_sobrescreve_sugestao(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraRevisao"})
        obra_id = r.json()["obra_id"]

        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("ambiguo_sem_padrao.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        doc = r.json()["documentos"][0]
        assert doc["classe_sugerida"] is None  # nome ambiguo -> sem sugestao

        r = await client.post(
            f"/obras/{obra_id}/documentos/{doc['doc_id']}/classificar",
            json={"classe_confirmada": "LV", "pavimento_confirmado": "13_PAV"},
        )
        assert r.status_code == 200
        atualizado = r.json()
        assert atualizado["classe_confirmada"] == "LV"
        assert atualizado["pavimento_confirmado"] == "13_PAV"
        assert atualizado["status"] == "classificado"


# --------------------------------------------------------------------------- #
# GET /obras/{id}/fichas — achado real rodando o SA de verdade contra uma obra
# nova: as fichas ficam em <obra_dir>/<pavimento>_<run_id>/, nao em
# "Fase-6_Execucao_CAD" (path fixo que nunca existiu de verdade — 2026-07-06).
# --------------------------------------------------------------------------- #

def _criar_ficha_real(obra_dir, run_id: str = "13_PAV_20260706_181817") -> None:
    run_dir = obra_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "arete_manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "index.html").write_text("<html>ficha real</html>", encoding="utf-8")
    (run_dir / "pilares").mkdir(exist_ok=True)
    (run_dir / "pilares" / "P1.html").write_text("<html>P1</html>", encoding="utf-8")


@pytest.mark.asyncio
async def test_listar_fichas_acha_dir_com_run_id_nao_fase6(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        obra_dir = tmp_path / "obra_com_ficha_real"
        c = connection.init_db(settings.db_path)
        c.execute("UPDATE portal_obras SET local_path=? WHERE id=?", (str(obra_dir), obra_id))
        c.commit()
        c.close()
        _criar_ficha_real(obra_dir)

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/fichas")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        nomes = {f["nome"] for f in body["fichas"]}
        assert nomes == {"index.html", "P1.html"}


@pytest.mark.asyncio
async def test_servir_ficha_real_retorna_html(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        obra_dir = tmp_path / "obra_ficha_servida"
        c = connection.init_db(settings.db_path)
        c.execute("UPDATE portal_obras SET local_path=? WHERE id=?", (str(obra_dir), obra_id))
        c.commit()
        c.close()
        _criar_ficha_real(obra_dir)

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/fichas/pilares/P1.html")
        assert r.status_code == 200
        assert "P1" in r.text


@pytest.mark.asyncio
async def test_listar_fichas_sem_sa_rodado_ainda_devolve_vazio(settings):
    """Obra que nunca rodou o SA (sem nenhum dir com arete_manifest.json) ->
    lista vazia, sem erro — nao confunde 'entrada'/outras pastas com fichas."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/fichas")
        assert r.status_code == 200
        assert r.json()["total"] == 0


# --------------------------------------------------------------------------- #
# GET /obras/{id}/n5/{classe}/foto — 2026-07-06: N5 so' tinha download de DXF,
# sem preview visual. Achado real testando: DXF de N5 pode vir vazio (0
# entidades) quando o robo N3 de origem nunca rodou — nao e' bug, e' honesto.
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_n5_foto_renderiza_dxf_real(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})

        dxf_path = tmp_path / "N5_FV_13_PAV.dxf"
        import ezdxf
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0), (10, 10))
        doc.saveas(dxf_path)

        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        repo.registrar_n5_release(
            c, obra_id=obra_id, classe="FV", liberado_por=ana["id"],
            status_certificacao="certificado", pavimento="13_PAV", dxf_path=str(dxf_path),
        )
        c.close()

        r = await client.get(f"/obras/{obra_id}/n5/FV/foto")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_n5_foto_sem_release_404(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/n5/PL/foto")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_n5_foto_dxf_apagado_depois_do_release_410(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})

        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        repo.registrar_n5_release(
            c, obra_id=obra_id, classe="LV", liberado_por=ana["id"],
            status_certificacao="beta", pavimento="13_PAV",
            dxf_path=str(tmp_path / "nao_existe_mais.dxf"),
        )
        c.close()

        r = await client.get(f"/obras/{obra_id}/n5/LV/foto")
        assert r.status_code == 410


@pytest.mark.asyncio
async def test_documentos_de_obra_de_outro_membro_e_recusado_403(settings):
    # carla precisa existir ANTES do lifespan subir (mesmo padrão de
    # test_obra_de_outro_membro_403) — _app_cliente só semeia a ana.
    c = connection.init_db(settings.db_path)
    repo.criar_membro(c, login="carla", nome="Carla",
                       senha_hash=auth.hash_senha("x"), drive_folder_id="folder-carla")
    c.close()

    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraSoDaAna"})
        obra_id = r.json()["obra_id"]
        await client.post("/logout")

        await client.post("/login", json={"login": "carla", "senha": "x"})
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("x.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Cabeçalho da obra + nome de exibição do doc (2026-07-07) — a obra nunca fica
# só com o nome do arquivo bruto: cliente, prazos, critérios, observações.
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_atualizar_cabecalho_obra_via_http(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraCabecalho"})
        obra_id = r.json()["obra_id"]

        r = await client.post(f"/obras/{obra_id}/cabecalho", json={
            "nome": "Processamento Torre Sul",
            "cliente": "Construtora Aurora",
            "data_solicitacao": "2026-07-01",
            "data_entrega": "2026-07-20",
            "criterios_cliente": "Tolerância 2cm",
            "observacoes": "Prioridade alta",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["nome"] == "Processamento Torre Sul"
        assert body["cliente"] == "Construtora Aurora"
        assert body["data_entrega"] == "2026-07-20"

        r = await client.get(f"/obras/{obra_id}")
        assert r.json()["obra"]["cliente"] == "Construtora Aurora"


@pytest.mark.asyncio
async def test_atualizar_cabecalho_obra_nome_vazio_e_recusado(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraCabecalho2"})
        obra_id = r.json()["obra_id"]
        r = await client.post(f"/obras/{obra_id}/cabecalho", json={"nome": "   "})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_cabecalho_obra_de_outro_membro_e_recusado_403(settings):
    c = connection.init_db(settings.db_path)
    repo.criar_membro(c, login="beto", nome="Beto",
                       senha_hash=auth.hash_senha("x"), drive_folder_id="folder-beto")
    c.close()
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraSoDaAna2"})
        obra_id = r.json()["obra_id"]
        await client.post("/logout")

        await client.post("/login", json={"login": "beto", "senha": "x"})
        r = await client.post(f"/obras/{obra_id}/cabecalho", json={"cliente": "X"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_renomear_documento_via_http(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraRenomeiaDoc"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("13_PAV_PL_v3_final2.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        doc_id = r.json()["documentos"][0]["doc_id"]

        r = await client.post(
            f"/obras/{obra_id}/documentos/{doc_id}/renomear",
            json={"nome_exibicao": "Pilares - 13o pavimento"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["nome_exibicao"] == "Pilares - 13o pavimento"
        assert r.json()["arquivo_nome"] == "13_PAV_PL_v3_final2.dxf"


@pytest.mark.asyncio
async def test_renomear_documento_nome_vazio_e_recusado(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraRenomeiaDoc2"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("a.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        doc_id = r.json()["documentos"][0]["doc_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos/{doc_id}/renomear", json={"nome_exibicao": "   "},
        )
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# tipo_documento + PDF (2026-07-07) — eixo novo Bruto/Detalhe/PDF, PDF é
# material de referência aceito no upload (mas não entra no pipeline DXF).
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_upload_com_tipo_e_pavimento_padrao_do_lote(settings):
    """[2026-07-07] Ao enviar um lote inteiro do mesmo tipo/pavimento, o
    usuário pode informar isso 1 vez no upload em vez de corrigir doc por
    doc depois — grava direto como *_confirmado."""
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraLotePadrao"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            data={"tipo_documento_padrao": "Detalhe", "pavimento_padrao": "13_PAV"},
            files=[("arquivos", ("arquivo_sem_padrao_nenhum.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        assert r.status_code == 200, r.text
        doc_id = r.json()["documentos"][0]["doc_id"]

        r = await client.get(f"/obras/{obra_id}")
        doc = next(d for d in r.json()["documentos"] if d["id"] == doc_id)
        assert doc["tipo_documento_confirmado"] == "Detalhe"
        assert doc["pavimento_confirmado"] == "13_PAV"


@pytest.mark.asyncio
async def test_upload_sem_tipo_padrao_usa_so_a_sugestao_automatica(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraSemPadrao"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("arquivo_qualquer.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        doc_id = r.json()["documentos"][0]["doc_id"]
        r = await client.get(f"/obras/{obra_id}")
        doc = next(d for d in r.json()["documentos"] if d["id"] == doc_id)
        assert doc["tipo_documento_confirmado"] is None
        assert doc["pavimento_confirmado"] is None


@pytest.mark.asyncio
async def test_upload_pdf_e_aceito_e_classificado_como_pdf(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraComPdf"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("memorial - 13 PAV.pdf", b"%PDF-1.4 conteudo fake", "application/pdf"))],
        )
        assert r.status_code == 200, r.text
        doc = r.json()["documentos"][0]
        assert doc["ok"] is True
        assert doc["tipo_documento_sugerido"] == "PDF"
        assert doc["classe_sugerida"] is None


@pytest.mark.asyncio
async def test_upload_extensao_nao_suportada_ainda_e_recusada(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraExtInvalida"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("planilha.xlsx", b"conteudo", "application/octet-stream"))],
        )
        assert r.status_code == 200
        assert r.json()["documentos"][0]["ok"] is False


@pytest.mark.asyncio
async def test_mover_documento_para_pavimento_e_tipo(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraMoverDoc"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("arquivo_qualquer.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        doc_id = r.json()["documentos"][0]["doc_id"]

        r = await client.post(
            f"/obras/{obra_id}/documentos/{doc_id}/mover",
            json={"pavimento": "13_PAV", "tipo_documento": "Bruto"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["pavimento_confirmado"] == "13_PAV"
        assert r.json()["tipo_documento_confirmado"] == "Bruto"


@pytest.mark.asyncio
async def test_mover_documento_para_indeterminado_limpa_classificacao(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraMoverIndet"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos",
            files=[("arquivos", ("arquivo_qualquer.dxf", _dxf_bytes(), "application/octet-stream"))],
        )
        doc_id = r.json()["documentos"][0]["doc_id"]
        await client.post(
            f"/obras/{obra_id}/documentos/{doc_id}/mover",
            json={"pavimento": "13_PAV", "tipo_documento": "Bruto"},
        )

        r = await client.post(f"/obras/{obra_id}/documentos/{doc_id}/mover", json={})
        assert r.status_code == 200, r.text
        assert r.json()["pavimento_confirmado"] is None
        assert r.json()["tipo_documento_confirmado"] is None


@pytest.mark.asyncio
async def test_mover_documento_inexistente_404(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraMoverInexistente"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos/doc-nao-existe/mover",
            json={"pavimento": "13_PAV"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_renomear_documento_inexistente_404(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.post("/obras/criar", json={"nome": "ObraRenomeiaDoc3"})
        obra_id = r.json()["obra_id"]
        r = await client.post(
            f"/obras/{obra_id}/documentos/doc-nao-existe/renomear", json={"nome_exibicao": "X"},
        )
        assert r.status_code == 404
