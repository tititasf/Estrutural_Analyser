"""Criação de item pelo laço do viewer (P3) — HTTP real, autenticado.

Usa o DXF real da torre do 13_PAV (mesmo arquivo dos demais testes do viewer) e
o `sa_db_path` ISOLADO da fixture `settings` (`project_data_teste.vision` em
tmp) — nunca toca o `project_data.vision` de produção (1,44 GB).
"""
from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"
_PAVIMENTO = "13_PAV"

pytestmark = pytest.mark.skipif(
    not (_OBRA_DIR / "Fase-2_Triagem" / "recortes" / "TMC-EST-PE-6000-13P-R03" / "torre_1.dxf").is_file(),
    reason="torre real do 13_PAV ausente nesta maquina",
)


def _bootstrap_sa_schema(sa_db_path: Path) -> None:
    """Cria reverse_eng_fichas/recortes no sa_db de teste — mesmo bootstrap que
    o próprio app usa em produção (`_garantir_project_registrado`)."""
    from src.core.database import DatabaseManager

    DatabaseManager(db_path=str(sa_db_path))


@contextlib.asynccontextmanager
async def _app_cliente(settings):
    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    c.close()
    _bootstrap_sa_schema(settings.sa_db_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


def _obra_real(settings) -> str:
    c = connection.init_db(settings.db_path)
    ana = repo.obter_membro_por_login(c, "ana")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraViewer", pasta_drive_id="folder-ana",
        arquivo_hash="hash-viewer", estado="pronta", local_path=str(_OBRA_DIR),
    )
    c.close()
    return obra_id


async def _login(client: httpx.AsyncClient) -> None:
    r = await client.post("/login", json={"login": "ana", "senha": "segredo123"})
    assert r.status_code == 200


async def _poligono_tela_inteira(client: httpx.AsyncClient, obra_id: str) -> list[dict]:
    """Retângulo cobrindo TODO o frame — garante entidades dentro sem precisar
    calcular coordenada real do desenho no teste."""
    r = await client.get(f"/obras/{obra_id}/viewer/{_PAVIMENTO}/transform")
    assert r.status_code == 200
    t = r.json()
    L, A = t["largura_px"], t["altura_px"]
    return [{"x": 0, "y": 0}, {"x": L, "y": 0}, {"x": L, "y": A}, {"x": 0, "y": A}]


def _linhas_sa(sa_db_path: Path, tabela: str) -> list[sqlite3.Row]:
    con = sqlite3.connect(str(sa_db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(f"SELECT * FROM {tabela}").fetchall()
    finally:
        con.close()


# ── criação bem-sucedida ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_criar_item_grava_ficha_e_recorte_reais(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)

        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "pilares", "poligono_px": poligono, "elemento_id": "P900"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["classe"] == "PIL"
        assert body["elemento_id"] == "P900"
        assert body["entities_copied"] > 0
        assert body["pavimento"] == "13_PAV"
        # P4 — comando do microciclo MONTADO para exibir/depurar, mas a
        # EXECUCAO agora e' via job enfileirado (headless_enabled=False nos
        # testes por padrao, ver conftest.py -> job_id fica None).
        assert body["job_id"] is None
        assert "--secao" in body["comando_sa"] and "pilares" in body["comando_sa"]
        assert "--item" in body["comando_sa"] and "P900" in body["comando_sa"]
        assert "--wait" in body["comando_sa"]
        assert "--persist-db" in body["comando_sa"]

        # o DXF recortado existe de verdade em disco
        recorte = Path(body["recorte_path"])
        assert recorte.is_file()
        assert recorte.suffix == ".dxf"

        # P5 — preview N3 no path canônico que assemble_n5 varre
        n3 = Path(body["n3_preview_path"])
        assert n3.is_file()
        assert n3.name == "PL_preview_P900.dxf"
        assert "Fase-6_Execucao_CAD" in str(n3)

        # e a identidade gravada é a decidida: web:<obra>:<pavimento>
        fichas = _linhas_sa(settings.sa_db_path, "reverse_eng_fichas")
        assert len(fichas) == 1
        assert fichas[0]["projeto_id"] == "web:TMC-EST-PE-6000-13P-R03:13_PAV"
        assert fichas[0]["obra_name"] == "TMC-EST-PE-6000-13P-R03"  # pasta em disco
        assert fichas[0]["status"] == "manual"
        assert fichas[0]["campos_json"] == "{}"  # nada de campo inventado

        recortes = _linhas_sa(settings.sa_db_path, "reverse_eng_recortes")
        assert len(recortes) == 1
        assert recortes[0]["entity_count"] == body["entities_copied"]


@pytest.mark.asyncio
async def test_criar_item_sem_nome_usa_sugestao_automatica(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)

        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "lajes", "poligono_px": poligono},
        )
        assert r.status_code == 201, r.text
        assert r.json()["elemento_id"] == "L1"  # primeiro nome livre da classe


@pytest.mark.asyncio
async def test_rota_sugerir_nome(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        r = await client.get(f"/obras/{obra_id}/viewer/{_PAVIMENTO}/sugerir-nome",
                              params={"grupo": "fundos"})
        assert r.status_code == 200
        assert r.json() == {"grupo": "fundos", "classe": "FV", "sugestao": "VF1"}


# ── erros e proteções ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grupo_desconhecido_e_422(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)
        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "escadas", "poligono_px": poligono},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_poligono_com_menos_de_3_pontos_e_422(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "pilares", "poligono_px": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_traco_sem_nenhuma_entidade_dentro_e_422_e_nao_deixa_arquivo_orfao(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        # 1x1 px no canto: quase certamente sem entidade nenhuma dentro.
        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "pilares", "poligono_px": [
                {"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1},
            ]},
        )
        assert r.status_code == 422
        assert "nenhuma entidade" in r.json()["detail"]
        assert _linhas_sa(settings.sa_db_path, "reverse_eng_fichas") == []


@pytest.mark.asyncio
async def test_nome_duplicado_e_409_e_nao_duplica_no_banco(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)
        payload = {"grupo": "pilares", "poligono_px": poligono, "elemento_id": "P901"}

        primeiro = await client.post(f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens", json=payload)
        assert primeiro.status_code == 201

        segundo = await client.post(f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens", json=payload)
        assert segundo.status_code == 409
        assert len(_linhas_sa(settings.sa_db_path, "reverse_eng_fichas")) == 1
        assert len(_linhas_sa(settings.sa_db_path, "reverse_eng_recortes")) == 1


@pytest.mark.asyncio
async def test_nome_duplicado_e_case_insensitive(settings):
    """'p1' e 'P1' são o mesmo item — normalizar_nome_item já garante isso em
    unidade; aqui confirmamos que a ROTA aplica a normalização antes de checar."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)

        a = await client.post(f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
                              json={"grupo": "pilares", "poligono_px": poligono, "elemento_id": "p902"})
        assert a.status_code == 201
        b = await client.post(f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
                              json={"grupo": "pilares", "poligono_px": poligono, "elemento_id": "P902"})
        assert b.status_code == 409


@pytest.mark.asyncio
async def test_sem_sessao_nao_cria_item(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "pilares", "poligono_px": [
                {"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10},
            ]},
        )
        assert r.status_code in (401, 403)
        assert _linhas_sa(settings.sa_db_path, "reverse_eng_fichas") == []


@pytest.mark.asyncio
async def test_grupos_de_lateral_criam_item_de_classe_LV(settings):
    """Trava a correspondência _GRUPO_PARA_CLASSE <-> GRUPOS_VIEWER.

    GRUPOS_VIEWER mudou de 1 grupo "laterais" para 4 ("lat_a_para",
    "lat_a_passa", "lat_b_para", "lat_b_passa") sem atualizar o dicionário de
    criação — a rota de criar item quebrava (422 "grupo desconhecido") para
    QUALQUER lateral. _GRUPO_PARA_CLASSE agora é derivado de GRUPOS_VIEWER
    para os dois nunca divergirem de novo; este teste prova que continuam
    default_para o mesmo destino.
    """
    from portal.app.routers import viewer_routes

    grupos_lateral = [g for g, _r, _c in viewer_routes.GRUPOS_VIEWER if g.startswith("lat_")]
    assert grupos_lateral, "GRUPOS_VIEWER precisa ter pelo menos um grupo de lateral"

    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)

        for grupo in grupos_lateral:
            r = await client.post(
                f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
                json={"grupo": grupo, "poligono_px": poligono, "elemento_id": f"V_{grupo}"},
            )
            assert r.status_code == 201, f"{grupo}: {r.text}"
            assert r.json()["classe"] == "LV"


# ── P4 assíncrono: enfileira job em vez de rodar dentro do handler HTTP ──────

@pytest.mark.asyncio
async def test_com_headless_habilitado_enfileira_job_em_vez_de_bloquear(settings):
    """headless_enabled=True (produção): a criação do item enfileira um job
    real na fila do portal (mesma usada por triagem/SA/N5) em vez de rodar o
    subprocess síncrono dentro do POST /itens.

    subprocess_timeout_s default é 3600s — bloquear a requisição por até 1h
    sem feedback é o problema que este desenho evita. NÃO inicia o JobWorker
    aqui (o teste fica rápido); só confirma que o job foi enfileirado com os
    metadados certos para o worker processar depois.
    """
    import dataclasses

    settings_prod = dataclasses.replace(settings, headless_enabled=True)
    async with _app_cliente(settings_prod) as (_app, client):
        obra_id = _obra_real(settings_prod)
        await _login(client)
        poligono = await _poligono_tela_inteira(client, obra_id)

        r = await client.post(
            f"/obras/{obra_id}/viewer/{_PAVIMENTO}/itens",
            json={"grupo": "pilares", "poligono_px": poligono, "elemento_id": "P901"},
        )
        assert r.status_code == 201, r.text
        job_id = r.json()["job_id"]
        assert job_id, "esperava job_id quando headless_enabled=True"

        # está na fila do portal (mesma tabela que triagem/SA/N5 usam)
        conn = connection.init_db(settings_prod.db_path)
        try:
            jobs = repo.listar_jobs_por_obra(conn, obra_id)
            assert len(jobs) == 1
            assert jobs[0]["id"] == job_id
            assert jobs[0]["status"] == "na_fila"
        finally:
            conn.close()

        # e o polling uniforme (GET /jobs/{id}, mesmo contrato das etapas 2-6)
        # já enxerga o job com o tipo certo
        rj = await client.get(f"/jobs/{job_id}")
        assert rj.status_code == 200
        corpo_job = rj.json()
        assert corpo_job["tipo"] == "sa_item"
        assert corpo_job["estado"] == "queued"
