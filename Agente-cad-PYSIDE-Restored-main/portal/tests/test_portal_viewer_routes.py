"""Viewer do estrutural limpo por pavimento (P2).

Usa a obra REAL em disco (TMC-EST-PE-6000-13P-R03), não fixture sintética: o que
importa aqui é que a transform e a geometria do SA vivam no MESMO espaço de
coordenadas. Um teste com DXF inventado não pegaria desalinhamento.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from portal.app.routers import viewer_routes

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"
_PAVIMENTO = "13_PAV"
_OBRA = {"arquivo_nome": "TMC-EST-PE-6000-13P-R03.dxf", "nome": "TMC-EST-PE-6000-13P-R03"}

pytestmark = pytest.mark.skipif(
    not (_OBRA_DIR / f"estado_{_PAVIMENTO}.json").is_file(),
    reason="obra real TMC-EST-PE-6000-13P-R03 ausente nesta maquina",
)


def _transform():
    from portal.app import dxf_preview
    fonte = viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, _OBRA)
    assert fonte is not None
    return dxf_preview.transform_preview_completo(Path(fonte["path"]))


def _estado():
    from portal.app import ficha_reader
    return ficha_reader.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)


def test_fonte_e_a_torre_limpa_nao_o_bruto():
    """O fundo de desenho tem de ser o estrutural LIMPO.

    O bruto ainda traz a faixa de detalhes/convencoes ao lado da planta — usá-lo
    poria essa faixa sob o traço do operador.
    """
    fonte = viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, _OBRA)
    assert fonte is not None
    assert fonte["item_id"].startswith("torre")
    assert Path(fonte["path"]).name == "torre_1.dxf"
    assert "entrada" not in Path(fonte["path"]).parts


def test_detalhes_nunca_e_escolhido_como_fundo():
    """'detalhes' é a faixa de convencoes: nao tem planta, nao serve de fundo."""
    fonte = viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, _OBRA)
    assert fonte["item_id"] != "detalhes"


def test_sao_os_botoes_de_destaque_pedidos():
    grupos = [g for g, _rotulo, _classes in viewer_routes.GRUPOS_VIEWER]
    assert grupos == [
        "pilares",
        "lat_a_para", "lat_a_passa", "lat_b_para", "lat_b_passa",
        "fundos", "lajes",
    ]


def test_pilares_somam_retangulares_e_especiais():
    """46 = 44 retangulares + 2 em L. Agrupar impede que os especiais sumam."""
    itens = []
    for classe in ("pilares", "pilares_especiais"):
        itens += viewer_routes._geometria_dos_itens(_estado(), classe, _transform())
    ids = {i["item_id"] for i in itens}
    assert len(itens) == 46
    assert {"P1", "P26", "P27"} <= ids


def test_laterais_sao_quatro_grupos_isolados():
    """Pedido 2026-07-31: A/B × Para/Passa em botões separados para isolar
    o destaque — mesmo que a geometria coincida no DXF."""
    laterais = [g for g in viewer_routes.GRUPOS_VIEWER if g[0].startswith("lat_")]
    assert [g[0] for g in laterais] == [
        "lat_a_para", "lat_a_passa", "lat_b_para", "lat_b_passa",
    ]
    for _id, _rotulo, classes in laterais:
        assert len(classes) == 1


def test_segmento_de_viga_e_rotulado_SEG_n():
    """O dono pediu a contagem explicita: SEG 1, SEG 2, SEG 3."""
    fundos = viewer_routes._geometria_dos_itens(_estado(), "fundo", _transform())
    v2 = sorted(i["rotulo"] for i in fundos if i["beam_name"] == "V2")
    assert v2 == ["V2 SEG 1", "V2 SEG 2"]


def test_pilar_e_laje_usam_o_proprio_nome():
    t = _transform()
    pilares = viewer_routes._geometria_dos_itens(_estado(), "pilares", t)
    lajes = viewer_routes._geometria_dos_itens(_estado(), "lajes", t)
    assert any(i["rotulo"] == "P1" for i in pilares)
    assert any(i["rotulo"] == "L301" for i in lajes)


def test_geometria_do_SA_cai_dentro_do_frame_renderizado():
    """Alinhamento: o grosso dos itens tem de cair sobre a imagem servida.

    Se a transform e a geometria do SA vivessem em espacos diferentes, quase
    tudo cairia fora — e o destaque apareceria deslocado da planta.
    """
    t = _transform()
    total = dentro = 0
    for _g, _r, classes in viewer_routes.GRUPOS_VIEWER:
        for classe in classes:
            for item in viewer_routes._geometria_dos_itens(_estado(), classe, t):
                total += 1
                dentro += 0 if item["fora_do_frame"] else 1
    assert total > 300
    assert dentro / total > 0.95


def test_item_fora_da_prancha_e_sinalizado_nao_escondido():
    """8 segmentos do 13_PAV tem Y ~4175-5320 num desenho que acaba em Y=3796.

    Geometria do SA fora do papel. O viewer marca `fora_do_frame` em vez de
    recortar: item invisivel parece item inexistente, e e' assim que erro de
    interpretacao passa despercebido.
    """
    t = _transform()
    fora = [
        i for _g, _r, classes in viewer_routes.GRUPOS_VIEWER
        for classe in classes
        for i in viewer_routes._geometria_dos_itens(_estado(), classe, t)
        if i["fora_do_frame"]
    ]
    assert fora, "esperava sinalizar os itens fora da prancha"
    # continuam na resposta, com geometria — nao foram descartados
    assert all(i["pontos_dxf"] for i in fora)
    assert any(i["bbox_dxf"][3] > t.bbox_dxf[3] for i in fora)


def test_descobre_bruto_no_disco_e_nao_pelo_nome_da_obra():
    """`portal_obras.arquivo_nome` é NULL nas obras reais.

    Derivar o bruto_id do nome da obra só acerta quando obra e arquivo se chamam
    igual — em Obra-Teste-Inicial2 os brutos são TMC-EST-EX-*, nada a ver com o
    nome. A descoberta em disco tem de achar a torre mesmo assim.
    """
    obra_sem_arquivo = {"arquivo_nome": None, "nome": "nome-que-nao-existe-em-disco"}
    fonte = viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, obra_sem_arquivo)
    assert fonte is not None, "devia achar a torre pela varredura, sem depender do nome"
    assert fonte["item_id"].startswith("torre")


def test_obra_sem_recortes_devolve_none_em_vez_de_cair_no_bruto(tmp_path):
    """Sem torre gerada o viewer responde 409. Cair no bruto pareceria funcionar
    e poria a faixa de detalhes/convenções sob o traço do operador."""
    vazia = tmp_path / "obra_vazia"
    (vazia / "entrada").mkdir(parents=True)
    assert viewer_routes.encontrar_estrutural_limpo(vazia, {"nome": "x"}) is None


# ── HTTP real (rota JSON + página), com sessão autenticada ───────────────────

import contextlib  # noqa: E402

import httpx  # noqa: E402

from portal.app import auth  # noqa: E402
from portal.app.main import create_app  # noqa: E402
from portal.db import connection, repository as repo  # noqa: E402


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


def _obra_real(settings) -> str:
    c = connection.init_db(settings.db_path)
    ana = repo.obter_membro_por_login(c, "ana")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraViewer", pasta_drive_id="folder-ana",
        arquivo_hash="hash-viewer", estado="pronta", local_path=str(_OBRA_DIR),
    )
    c.close()
    return obra_id


@pytest.mark.asyncio
async def test_rota_json_do_viewer_responde_completa(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/obras/{obra_id}/viewer/{_PAVIMENTO}")
        assert r.status_code == 200
        body = r.json()

        assert body["fonte"]["arquivo"] == "torre_1.dxf"
        assert body["sa_rodado"] is True
        # a imagem servida e' a da torre, nao a do bruto
        assert f"/{body['fonte']['item_id']}/foto" in body["svg_url"]

        t = body["transform"]
        assert t["largura_px"] > 0 and t["altura_px"] > 0
        assert len(t["bbox_dxf"]) == 4

        grupos = {g["grupo"]: g for g in body["grupos"]}
        assert "pilares" in grupos and "fundos" in grupos and "lajes" in grupos
        assert grupos["pilares"]["total"] == 46
        assert grupos["lajes"]["total"] == 31
        # 4 laterais isoladas (A/B × Para/Passa). Cada lado costuma ter ~107.
        lats = [k for k in grupos if k.startswith("lat_")]
        assert set(lats) >= {"lat_a_para", "lat_b_para"}
        total_lat = sum(grupos[k]["total"] for k in lats)
        assert total_lat >= 200
        assert any(i["rotulo"] == "P1" for i in grupos["pilares"]["itens"])
        assert any(i["rotulo"] == "V2 SEG 1" for i in grupos["fundos"]["itens"])


@pytest.mark.asyncio
async def test_pagina_do_viewer_renderiza(settings):
    """A tela em si — o que o dono abre no navegador."""
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/app/obras/{obra_id}/viewer/{_PAVIMENTO}")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Estrutural limpo" in r.text
        assert _PAVIMENTO in r.text
        # o palco e a camada de destaque existem
        assert 'id="v-palco"' in r.text
        assert 'id="v-camada"' in r.text
        # e a pagina busca os dados da rota JSON certa
        assert f"/obras/{obra_id}/viewer/{_PAVIMENTO}" in r.text


@pytest.mark.asyncio
async def test_viewer_sem_sessao_nao_vaza_dados(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        r = await client.get(f"/obras/{obra_id}/viewer/{_PAVIMENTO}")
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_pagina_do_viewer_sem_sessao_manda_para_login(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_real(settings)
        r = await client.get(f"/app/obras/{obra_id}/viewer/{_PAVIMENTO}",
                             follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"


# ── Cada pavimento abre o SEU estrutural ─────────────────────────────────────
# Bug que o dono viu: "só funciona no link que você passou, não em todos os
# pavimentos que seleciono". encontrar_estrutural_limpo ignorava o pavimento e
# devolvia sempre a primeira torre da obra.

_OBRA_MULTI = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "Obra-Teste-Inicial"

multi = pytest.mark.skipif(
    not (_OBRA_MULTI / "Fase-2_Triagem" / "recortes").is_dir(),
    reason="obra com varios brutos ausente nesta maquina",
)


@multi
def test_cada_pavimento_resolve_seu_proprio_bruto():
    obra = {"arquivo_nome": None, "nome": "Obra-Teste-Inicial2"}
    esperado = {
        "13_PAV": "6000-13P",
        "14_PAV": "7000-14P",
        "TERREO": "2000-TER",
        "COBERTURA": "8000-COB",
        "1_PAV": "3000-1PV",
    }
    for pavimento, marca in esperado.items():
        fonte = viewer_routes.encontrar_estrutural_limpo(_OBRA_MULTI, obra, pavimento)
        assert fonte is not None, f"{pavimento} devia ter torre"
        assert marca in fonte["bruto_id"], (
            f"{pavimento} abriu {fonte['bruto_id']}, esperava conter {marca}"
        )


@multi
def test_pavimentos_diferentes_nao_abrem_o_mesmo_desenho():
    """O sintoma exato do bug: tudo caía na mesma torre."""
    obra = {"arquivo_nome": None, "nome": "Obra-Teste-Inicial2"}
    vistos = {
        pav: viewer_routes.encontrar_estrutural_limpo(_OBRA_MULTI, obra, pav)["bruto_id"]
        for pav in ("13_PAV", "14_PAV", "TERREO", "COBERTURA")
    }
    assert len(set(vistos.values())) == 4, f"brutos repetidos: {vistos}"


def test_pavimento_sem_torre_nao_cai_em_outro():
    """Mostrar o pavimento ERRADO com cara de certo é pior que não mostrar."""
    obra = {"arquivo_nome": None, "nome": "TMC-EST-PE-6000-13P-R03"}
    # a obra TMC só tem a prancha do 13_PAV
    assert viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, obra, "13_PAV") is not None
    assert viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, obra, "COBERTURA") is None
    assert viewer_routes.encontrar_estrutural_limpo(_OBRA_DIR, obra, "14_PAV") is None


@multi
def test_listagem_de_pavimentos_sobe_na_ordem_do_predio():
    from portal.app import viewer_pavimentos

    obra = {"arquivo_nome": None, "nome": "Obra-Teste-Inicial2"}
    ordem = [p["pavimento"] for p in viewer_pavimentos.listar_pavimentos_com_torre(_OBRA_MULTI, obra)]
    # alfabetico poria COBERTURA antes de 1_PAV e 13_PAV antes de 2_PAV
    assert ordem.index("TERREO") < ordem.index("1_PAV") < ordem.index("2_PAV")
    assert ordem.index("2_PAV") < ordem.index("13_PAV") < ordem.index("COBERTURA")
    assert ordem.index("FUNDACAO") < ordem.index("TERREO")
