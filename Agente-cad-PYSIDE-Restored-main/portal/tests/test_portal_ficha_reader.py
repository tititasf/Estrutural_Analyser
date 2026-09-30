"""Testes reais de ficha_reader.py (2026-07-06) — usa os artefatos REAIS já em
disco da obra TMC-EST-PE-6000-13P-R03 (rodada real de SA feita nesta sessão),
não dados sintéticos: `estado_13_PAV.json` e as fichas HTML de
`13_PAV_20260706_181817/`. Se algum dia esses artefatos não existirem mais
(obra removida/limpa), os testes são pulados (skip), não falham — não é
responsabilidade do portal gerar esses fixtures, só ler o que já existe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.app import ficha_reader as fr
from portal.app import pipeline_runner

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"
_PAVIMENTO = "13_PAV"

pytestmark = pytest.mark.skipif(
    not (_OBRA_DIR / f"estado_{_PAVIMENTO}.json").is_file(),
    reason="obra real TMC-EST-PE-6000-13P-R03 sem estado_13_PAV.json nesta máquina",
)


def test_descobrir_pavimentos_acha_o_real():
    assert _PAVIMENTO in fr.descobrir_pavimentos(_OBRA_DIR)


def test_ler_estado_pavimento_real():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    assert estado is not None
    assert set(estado.keys()) >= {"pilares", "slabs", "cortes", "segmentos"}


def test_ler_estado_pavimento_inexistente_devolve_none():
    assert fr.ler_estado_pavimento(_OBRA_DIR, "99_PAV_NAO_EXISTE") is None


def test_listar_itens_n1_pilares_tem_campos_reais():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    itens = fr.listar_itens_n1(estado, "pilares")
    assert len(itens) == 46  # confirmado real: 46 pilares nesta obra
    p1 = next(i for i in itens if i["item_id"] == "P1")
    assert p1["campos"]["Nome"] == "P1"
    assert p1["campos"]["Nível"] == "852.12"
    assert len(p1["points"]) >= 4  # geometria real (retângulo)


def test_listar_itens_n1_pilares_expoe_campos_field_id():
    """[2026-07-13, Fase 3.1] campos_field_id mapeia só os campos com field_id
    real conhecido do SA (Nome/Classificação) — Orientação/Nível Relativo
    ficam de fora (gap documentado). Lado A-D/Lajes contíguas viram campos
    GRANULARES por lado×índice na Fase 3.3 (ver teste dedicado abaixo)."""
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    p1 = fr.obter_item_n1(estado, "pilares", "P1")
    assert p1["campos_field_id"]["Nome"] == "name"
    assert p1["campos_field_id"]["Classificação"] == "classification"
    assert "Orientação" not in p1["campos_field_id"]
    assert "Nível Relativo" not in p1["campos_field_id"]


def test_listar_itens_n1_pilares_expoe_lajes_contiguas_granular():
    """[2026-07-13, Fase 3.3] "Lajes contíguas" (texto agregado) continua
    existindo, mas cada laje que toca um lado do pilar também vira campo
    GRANULAR (Nome/Altura/Nível), field_id IDÊNTICO ao do app desktop
    (`p_s{lado}_l{i}_n/h/v`) — P1 nesta obra toca 1 laje (L301) no lado B."""
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    p1 = fr.obter_item_n1(estado, "pilares", "P1")
    assert p1["campos"]["Laje B #1 — Nome"] == "L301"
    assert p1["campos_field_id"]["Laje B #1 — Nome"] == "p_sB_l1_n"
    assert p1["campos_field_id"]["Laje B #1 — Nível"] == "p_sB_l1_v"
    # "Lajes contíguas" (agregado) continua presente, não foi removido
    assert p1["campos"]["Lajes contíguas"] == "L301"


def test_listar_itens_n1_lajes_expoe_campos_field_id():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    itens = fr.listar_itens_n1(estado, "lajes")
    laje = itens[0]
    assert laje["campos_field_id"] == {"Nome": "name", "Nível": "laje_nivel"}
    assert "Altura" not in laje["campos_field_id"]  # sem field_id conhecido no SA


def test_listar_itens_n1_segmentos_fundo_reais():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    itens = fr.listar_itens_n1(estado, "fundo")
    assert len(itens) == 106
    v1 = next(i for i in itens if i["beam_name"] == "V1")
    assert v1["campos"]["Comportamento"] == "Fundo"
    assert v1["campos"]["Comprimento"] > 0


def test_listar_itens_n1_segmentos_expoe_campos_field_id_por_classe():
    """[2026-07-13, Fase 3.4] field_id de segmento é um SUFIXO (prefixo "_")
    resolvido só no app desktop via seg_uid — fundo usa _dim (largura E
    comprimento aproximam pro mesmo campo), lateral usa
    _comprimento_total/_comp_total_passa conforme a classe (para/passa)."""
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    fundo = next(i for i in fr.listar_itens_n1(estado, "fundo") if i["beam_name"] == "V1")
    assert fundo["campos_field_id"] == {"Nome": "name", "Comprimento": "_dim", "Largura": "_dim"}

    lateral_para = fr.listar_itens_n1(estado, "lateral_a_para")
    if lateral_para:
        assert lateral_para[0]["campos_field_id"]["Comprimento"] == "_comprimento_total"

    lateral_passa = fr.listar_itens_n1(estado, "lateral_a_passa")
    if lateral_passa:
        assert lateral_passa[0]["campos_field_id"]["Comprimento"] == "_comp_total_passa"


def test_listar_itens_n1_classe_desconhecida_devolve_vazio():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    assert fr.listar_itens_n1(estado, "classe_que_nao_existe") == []


def test_obter_item_n1_encontra_e_none_quando_nao_existe():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    assert fr.obter_item_n1(estado, "pilares", "P1") is not None
    assert fr.obter_item_n1(estado, "pilares", "P999_NAO_EXISTE") is None


def test_extrair_fotos_fundo_tem_n1_e_n3_reais():
    """Achado real: fundos_viga é a ÚNICA classe com N3 (robô) já gerado nesta
    obra — as demais mostram 'ausente' honestamente (não inventamos foto)."""
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    dir_fichas = pipeline_runner.encontrar_dir_fichas(_OBRA_DIR)
    assert dir_fichas is not None
    item = fr.obter_item_n1(estado, "fundo", next(
        i["item_id"] for i in fr.listar_itens_n1(estado, "fundo") if i["beam_name"] == "V1"
    ))
    fotos = fr.extrair_fotos_ficha(dir_fichas, "fundo", item)
    assert fotos["n1"] is not None and "<svg" in fotos["n1"]
    assert fotos["n3"] is not None and "<svg" in fotos["n3"]


def test_extrair_fotos_pilares_tem_n1_mas_nao_n3():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    dir_fichas = pipeline_runner.encontrar_dir_fichas(_OBRA_DIR)
    item = fr.obter_item_n1(estado, "pilares", "P1")
    fotos = fr.extrair_fotos_ficha(dir_fichas, "pilares", item)
    assert fotos["n1"] is not None and "<svg" in fotos["n1"]
    assert fotos["n3"] is None  # honesto: N3 nao foi gerado pra pilares nesta obra


def test_extrair_fotos_laterais_discrimina_lado_a_de_lado_b():
    """Achado real: 1 HTML por viga (ex.: V1-Para.html) contem N1 do lado A E
    do lado B juntos — extrair_fotos_ficha tem que devolver a foto CERTA pro
    lado pedido, nao misturar."""
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    dir_fichas = pipeline_runner.encontrar_dir_fichas(_OBRA_DIR)

    item_a = next(i for i in fr.listar_itens_n1(estado, "lateral_a_para") if i["beam_name"] == "V1")
    item_b = next(i for i in fr.listar_itens_n1(estado, "lateral_b_para") if i["beam_name"] == "V1")
    foto_a = fr.extrair_fotos_ficha(dir_fichas, "lateral_a_para", item_a)
    foto_b = fr.extrair_fotos_ficha(dir_fichas, "lateral_b_para", item_b)
    assert foto_a["n1"] is not None and foto_b["n1"] is not None
    assert foto_a["n1"] != foto_b["n1"]  # sao fotos DIFERENTES (lado A != lado B)


def test_extrair_fotos_cortes_sem_ficha_dedicada_devolve_ausente():
    """'Visão de Cortes' não tem pasta própria de fichas nesta versão do motor
    — honesto: devolve ausente, nunca inventa imagem."""
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    dir_fichas = pipeline_runner.encontrar_dir_fichas(_OBRA_DIR)
    itens = fr.listar_itens_n1(estado, "cortes")
    fotos = fr.extrair_fotos_ficha(dir_fichas, "cortes", itens[0])
    assert fotos == {"n1": None, "n3": None}


def test_extrair_fotos_sem_dir_fichas_devolve_ausente_sem_lancar():
    estado = fr.ler_estado_pavimento(_OBRA_DIR, _PAVIMENTO)
    item = fr.obter_item_n1(estado, "pilares", "P1")
    assert fr.extrair_fotos_ficha(None, "pilares", item) == {"n1": None, "n3": None}
