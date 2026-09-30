"""Troca de senha no primeiro acesso + isolamento entre perfis (2026-09-28).

Membro criado com a senha padrão (trocar_senha=1) só enxerga a página de troca
até trocar; depois, cada membro vê só as próprias obras e apontamentos, e o dono
vê tudo, com todo membro listado na lista de obras mesmo sem obra.
"""

from __future__ import annotations

import contextlib

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo


@contextlib.asynccontextmanager
async def _app(settings):
    c = connection.init_db(settings.db_path)
    for login, nome in (("stephanie", "Stephanie"), ("felipe", "Felipe")):
        repo.criar_membro(c, login=login, nome=nome,
                          senha_hash=auth.hash_senha("123456"), trocar_senha=True)
    repo.criar_membro(c, login="chefe", nome="Chefe", papel="dono",
                      senha_hash=auth.hash_senha("segredosuper"))
    c.close()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as client:
            yield client


def _obra(settings, login: str, nome: str) -> str:
    c = connection.init_db(settings.db_path)
    try:
        m = repo.obter_membro_por_login(c, login)
        return repo.criar_obra(c, membro_id=m["id"], nome=nome, pasta_drive_id=f"p-{nome}", arquivo_hash=f"h-{nome}",
                               estado="aguardando_ingestao")
    finally:
        c.close()


async def _entrar(client, login, senha):
    r = await client.post("/login", json={"login": login, "senha": senha})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_primeiro_acesso_so_libera_a_troca_de_senha(settings):
    async with _app(settings) as client:
        assert (await _entrar(client, "stephanie", "123456"))["trocar_senha"] is True
        r = await client.get("/app/obras", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/app/trocar-senha"
        assert (await client.get("/obras")).status_code == 403
        pagina = await client.get("/app/trocar-senha")
        assert pagina.status_code == 200 and "primeiro acesso" in pagina.text

        curta = await client.post("/trocar-senha", json={"nova_senha": "12345", "confirmacao": "12345"})
        assert curta.status_code == 400
        igual = await client.post("/trocar-senha", json={"nova_senha": "123456", "confirmacao": "123456"})
        assert igual.status_code == 400
        ok = await client.post("/trocar-senha", json={"nova_senha": "111111", "confirmacao": "111111"})
        assert ok.status_code == 200, ok.text

        assert (await client.get("/app/obras", follow_redirects=False)).status_code == 200
        await client.post("/logout")
        client.cookies.clear()
        assert (await client.post("/login", json={"login": "stephanie", "senha": "123456"})).status_code == 401
        assert (await _entrar(client, "stephanie", "111111"))["trocar_senha"] is False


@pytest.mark.asyncio
async def test_troca_voluntaria_exige_senha_atual(settings):
    async with _app(settings) as client:
        await _entrar(client, "chefe", "segredosuper")
        r = await client.post("/trocar-senha", json={"senha_atual": "errada", "nova_senha": "abcdef", "confirmacao": "abcdef"})
        assert r.status_code == 400
        r = await client.post("/trocar-senha", json={"senha_atual": "segredosuper", "nova_senha": "abcdef", "confirmacao": "abcdef"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_isolamento_entre_membros_e_dono_ve_todos(settings):
    async with _app(settings) as client:
        obra_s = _obra(settings, "stephanie", "ObraDaStephanie")
        obra_f = _obra(settings, "felipe", "ObraDoFelipe")

        await _entrar(client, "stephanie", "123456")
        await client.post("/trocar-senha", json={"nova_senha": "222222", "confirmacao": "222222"})
        ids = {o["id"] for o in (await client.get("/obras")).json()["obras"]}
        assert ids == {obra_s}
        assert (await client.get(f"/obras/{obra_f}")).status_code in (403, 404)
        lista = (await client.get("/app/obras")).text
        assert "ObraDoFelipe" not in lista
        status_pag = await client.get("/app/status", follow_redirects=False)
        assert status_pag.status_code == 303
        assert "/app/base-global" not in lista and "/app/status" not in lista
        await client.post("/logout")
        client.cookies.clear()

        await _entrar(client, "chefe", "segredosuper")
        lista = (await client.get("/app/obras")).text
        assert "ObraDaStephanie" in lista and "ObraDoFelipe" in lista
        assert "Lista de Obras — Felipe" in lista and "Lista de Obras — Stephanie" in lista
        assert "/app/base-global" in lista and "/app/status" in lista


@pytest.mark.asyncio
async def test_apontamento_de_um_membro_nao_aparece_para_outro(settings):
    c = connection.init_db(settings.db_path)
    c.close()
    async with _app(settings) as client:
        c = connection.init_db(settings.db_path)
        felipe = repo.obter_membro_por_login(c, "felipe")
        c.execute(
            "INSERT INTO portal_apontamentos_ui (id, membro_id, texto, pagina_url, clique_x, clique_y,"
            " pagina_x, pagina_y, viewport_largura, viewport_altura) VALUES (?,?,?,?,0,0,0,0,800,600)",
            ("ap-felipe", felipe["id"], "tela de obras do Felipe", "/app/obras"),
        )
        c.commit()
        stephanie = repo.obter_membro_por_login(c, "stephanie")
        dono = repo.obter_membro_por_login(c, "chefe")
        assert repo.listar_apontamentos_ui(c, membro=stephanie) == []
        assert [a["id"] for a in repo.listar_apontamentos_ui(c, membro=dono)] == ["ap-felipe"]
        c.close()
