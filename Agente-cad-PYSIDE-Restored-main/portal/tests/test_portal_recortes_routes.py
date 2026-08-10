"""Testes HTTP reais das rotas de Recortes (viewer bruto×limpo) — 2026-07-06.

Mesma fixture da obra real usada em test_portal_n1_routes.py.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo


def _dimensoes_svg_px(conteudo: bytes) -> tuple[float, float]:
    """(largura, altura) em px a partir do cabeçalho do SVG do matplotlib.

    O matplotlib emite width/height em POINTS (figsize_in * 72) enquanto o
    renderer trabalha em px com dpi=100 — logo px = pt * 100 / 72. Conferido:
    largura_px=2400 sai como width="1728pt".
    """
    cabecalho = conteudo[:1000].decode("utf-8", errors="replace")
    largura = re.search(r'width="([\d.]+)pt"', cabecalho)
    altura = re.search(r'height="([\d.]+)pt"', cabecalho)
    if not (largura and altura):
        raise AssertionError(f"SVG sem width/height em pt: {cabecalho[:200]!r}")
    return (float(largura.group(1)) * 100 / 72, float(altura.group(1)) * 100 / 72)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR_REAL = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"

pytestmark = pytest.mark.skipif(
    not (_OBRA_DIR_REAL / "Fase-2_Triagem" / "recortes_reversos").exists(),
    reason="recortes reais da obra TMC-EST-PE-6000-13P-R03 ausentes nesta máquina",
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


def _obra_com_recortes_reais(settings) -> str:
    c = connection.init_db(settings.db_path)
    ana = repo.obter_membro_por_login(c, "ana")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraComRecortesReais", pasta_drive_id="folder-ana",
        arquivo_hash="hash-recortes-reais", estado="pronta",
        arquivo_nome="TMC-EST-PE-6000-13P-R03.dwg",
        local_path=str(_OBRA_DIR_REAL),
    )
    c.close()
    return obra_id


@pytest.mark.asyncio
async def test_listar_classes_recorte_real(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/classes")
        assert r.status_code == 200
        classes = r.json()["classes"]
        por_classe = {c["classe"]: c["total"] for c in classes}
        assert por_classe["LAJ"] == 31
        # [2026-07-06] as 4 "pastas" (PIL/LV/FV/LAJ) sempre aparecem, mesmo
        # as vazias nesta obra — mostra a estrutura real do RecorteMotor.
        assert set(por_classe.keys()) == {"PIL", "LV", "FV", "LAJ"}
        assert por_classe["PIL"] == 0


@pytest.mark.asyncio
async def test_listar_brutos_recorte_real(settings):
    """[2026-07-07] navegação trocada pra por-bruto (espelha diagnostic_hub.py
    real) — a obra real tem 1 bruto (dwg+dxf do mesmo nome, dedup por stem)."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/brutos")
        assert r.status_code == 200
        brutos = r.json()["brutos"]
        assert len(brutos) == 1
        assert brutos[0]["nome"] == "TMC-EST-PE-6000-13P-R03.dxf"


@pytest.mark.asyncio
async def test_listar_brutos_recorte_enriquecido_com_pavimento_e_tipo(settings):
    """[2026-07-07 v2] Achado com o dono: a lista de brutos tinha que
    organizar igual a Triagem (Pavimento→Tipo via portal_documentos), não um
    glob cru do disco em ordem alfabética."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        c = connection.init_db(settings.db_path)
        repo.criar_documento(
            c, obra_id=obra_id, arquivo_nome="TMC-EST-PE-6000-13P-R03.dxf",
            pavimento_sugerido="13_PAV", tipo_documento_sugerido="Bruto",
        )
        c.close()
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/brutos")
        assert r.status_code == 200
        bruto = r.json()["brutos"][0]
        assert bruto["pavimento"] == "13_PAV"
        assert bruto["tipo_documento"] == "Bruto"


@pytest.mark.asyncio
async def test_listar_brutos_recorte_sem_documento_correspondente_fica_indeterminado(settings):
    """Bruto encontrado só no disco (sem portal_documentos casando pelo nome)
    — pavimento/tipo vêm None, a UI trata como "Indeterminado", honesto."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/brutos")
        bruto = r.json()["brutos"][0]
        assert bruto["pavimento"] is None
        assert bruto["tipo_documento"] is None


@pytest.mark.asyncio
async def test_listar_todos_recortes_achatado_real(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes")
        assert r.status_code == 200
        itens = r.json()["itens"]
        assert len(itens) == 31
        assert all(i["classe"] == "LAJ" for i in itens)
        assert any(i["item_id"] == "L301" for i in itens)


@pytest.mark.asyncio
async def test_listar_itens_recorte_de_uma_classe(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/LAJ")
        assert r.status_code == 200
        assert any(i["item_id"] == "L301" for i in r.json()["itens"])


@pytest.mark.asyncio
async def test_foto_recorte_limpo_e_bruto_reais(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})

        r_limpo = await client.get(f"/obras/{obra_id}/recortes/LAJ/L301/foto", params={"tipo": "limpo"})
        assert r_limpo.status_code == 200
        assert r_limpo.headers["content-type"] == "image/svg+xml"
        assert b"<svg" in r_limpo.content[:2000]

        r_bruto = await client.get(f"/obras/{obra_id}/recortes/LAJ/L301/foto", params={"tipo": "bruto"})
        assert r_bruto.status_code == 200
        assert b"<svg" in r_bruto.content[:2000]
        assert r_bruto.content != r_limpo.content  # imagens DIFERENTES (bruto tem mais contexto)


@pytest.mark.asyncio
async def test_foto_recorte_detalhes_real(settings):
    """[2026-07-06] 3o painel 'Detalhes e Convenções' — zoom fechado no
    próprio recorte (sem folga de contexto), imagem DIFERENTE do 'limpo'
    (que tem folga) — nao e' o mesmo enquadramento."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})

        r_detalhes = await client.get(f"/obras/{obra_id}/recortes/LAJ/L301/foto", params={"tipo": "detalhes"})
        assert r_detalhes.status_code == 200
        assert b"<svg" in r_detalhes.content[:2000]

        r_limpo = await client.get(f"/obras/{obra_id}/recortes/LAJ/L301/foto", params={"tipo": "limpo"})
        assert r_detalhes.content != r_limpo.content


@pytest.mark.asyncio
async def test_detalhes_recorte_metadados_reais(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/LAJ/L301/detalhes")
        assert r.status_code == 200
        body = r.json()
        assert body["entidades"] > 0
        assert body["largura"] > 0
        assert isinstance(body["camadas"], list)


@pytest.mark.asyncio
async def test_detalhes_recorte_item_inexistente_404(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/LAJ/L999_NAO_EXISTE/detalhes")
        assert r.status_code == 404


@pytest.mark.asyncio
def _garantir_torre_gerada(settings):
    """Gera torre_1/detalhes de verdade (idempotente) pra estes testes não
    dependerem de estado deixado por uma sessão manual anterior."""
    from portal.app import torre_crop
    dxf_bruto = _OBRA_DIR_REAL / "entrada" / "TMC-EST-PE-6000-13P-R03.dxf"
    torre_crop.gerar_recortes_bruto(_OBRA_DIR_REAL, dxf_bruto, "TMC-EST-PE-6000-13P-R03", force=False)


@pytest.mark.asyncio
async def test_listar_itens_torre_endpoint_real(settings):
    """[2026-07-07] Recortes REAIS pra revisão: torre_1 + detalhes (motor
    obra_crop_engine), não os 31 por-laje do RecorteMotor."""
    _garantir_torre_gerada(settings)
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r_brutos = await client.get(f"/obras/{obra_id}/recortes/brutos")
        bruto_id = r_brutos.json()["brutos"][0]["bruto_id"]
        r = await client.get(f"/obras/{obra_id}/recortes/brutos/{bruto_id}/itens")
        assert r.status_code == 200
        ids = {i["item_id"] for i in r.json()["itens"]}
        assert ids == {"torre_1", "detalhes"}


@pytest.mark.asyncio
async def test_foto_bruto_completo_alta_resolucao(settings):
    _garantir_torre_gerada(settings)
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r_brutos = await client.get(f"/obras/{obra_id}/recortes/brutos")
        bruto_id = r_brutos.json()["brutos"][0]["bruto_id"]
        r = await client.get(f"/obras/{obra_id}/recortes/brutos/{bruto_id}/foto")
        assert r.status_code == 200
        assert b"<svg" in r.content[:2000]
        # [2026-07-30] Era Image.open (PIL) sobre PNG; a rota migrou para SVG e o
        # PIL não abre SVG. A intenção do teste continua a mesma — alta resolução,
        # não o 640x480 antigo — medida agora no cabeçalho do próprio SVG.
        # [2026-07-31] Alvo caiu de 2400 para PREVIEW_ALVO_PX=1200
        # (dxf_preview.py): SVG do matplotlib em 2400px chegava a ~28MB por causa
        # da quantidade de paths, e o pan/zoom no navegador morria. 1200 continua
        # muito acima do 640x480 antigo — o que este teste protege.
        from portal.app.dxf_preview import PREVIEW_ALVO_PX
        assert max(_dimensoes_svg_px(r.content)) >= PREVIEW_ALVO_PX


@pytest.mark.asyncio
async def test_foto_torre_1_alta_resolucao_diferente_do_bruto(settings):
    _garantir_torre_gerada(settings)
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r_brutos = await client.get(f"/obras/{obra_id}/recortes/brutos")
        bruto_id = r_brutos.json()["brutos"][0]["bruto_id"]
        r_bruto = await client.get(f"/obras/{obra_id}/recortes/brutos/{bruto_id}/foto")
        r_torre = await client.get(f"/obras/{obra_id}/recortes/brutos/{bruto_id}/torre_1/foto")
        assert r_torre.status_code == 200
        assert b"<svg" in r_torre.content[:2000]
        assert r_torre.content != r_bruto.content


@pytest.mark.asyncio
async def test_foto_torre_item_inexistente_404(settings):
    _garantir_torre_gerada(settings)
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r_brutos = await client.get(f"/obras/{obra_id}/recortes/brutos")
        bruto_id = r_brutos.json()["brutos"][0]["bruto_id"]
        r = await client.get(f"/obras/{obra_id}/recortes/brutos/{bruto_id}/torre_99/foto")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_foto_recorte_tipo_invalido_422(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/LAJ/L301/foto", params={"tipo": "invalido"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_foto_recorte_item_inexistente_404(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_com_recortes_reais(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/recortes/LAJ/L999_NAO_EXISTE/foto", params={"tipo": "limpo"})
        assert r.status_code == 404
