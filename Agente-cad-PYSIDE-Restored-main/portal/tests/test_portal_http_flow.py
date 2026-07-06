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
