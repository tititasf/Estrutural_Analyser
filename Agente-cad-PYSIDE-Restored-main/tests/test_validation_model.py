"""Modelo de validação de campo/item [2026-07-13] — 3 origens de campo que
empilham (humano_app/humano_portal/qa_agente) + 4 selos de item
(verde é independente, calculado por fora; azul/rosa/laranja calculados
aqui a partir da cobertura campo-a-campo)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.validation_model import (  # noqa: E402
    ORIGEM_HUMANO_APP,
    ORIGEM_HUMANO_PORTAL,
    ORIGEM_QA_AGENTE,
    adicionar_validacao_campo,
    calcular_selos_item,
    campo_esta_validado,
    migrar_validated_fields_legado,
    origens_do_campo,
    remover_validacao_campo,
)


def test_migrar_lista_legada_vira_humano_app():
    migrado = migrar_validated_fields_legado(["nivel", "classificacao"])
    assert migrado == {
        "nivel": [{"origem": ORIGEM_HUMANO_APP, "quando": None}],
        "classificacao": [{"origem": ORIGEM_HUMANO_APP, "quando": None}],
    }


def test_migrar_none_vira_dict_vazio():
    assert migrar_validated_fields_legado(None) == {}


def test_migrar_dict_novo_passa_direto():
    novo = {"nivel": [{"origem": "qa_agente", "quando": "2026-07-13T00:00:00+00:00"}]}
    assert migrar_validated_fields_legado(novo) is novo


def test_adicionar_validacao_campo_registra_origem():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    assert origens_do_campo(dados, "nivel") == {ORIGEM_HUMANO_APP}


def test_adicionar_validacao_campo_acumula_origens_diferentes():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    dados = adicionar_validacao_campo(dados, "nivel", ORIGEM_QA_AGENTE)
    dados = adicionar_validacao_campo(dados, "nivel", ORIGEM_HUMANO_PORTAL)
    assert origens_do_campo(dados, "nivel") == {ORIGEM_HUMANO_APP, ORIGEM_QA_AGENTE, ORIGEM_HUMANO_PORTAL}


def test_adicionar_validacao_campo_e_idempotente_pra_mesma_origem():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    dados = adicionar_validacao_campo(dados, "nivel", ORIGEM_HUMANO_APP)
    assert len(dados["nivel"]) == 1


def test_adicionar_validacao_campo_origem_invalida_levanta_erro():
    import pytest
    with pytest.raises(ValueError):
        adicionar_validacao_campo({}, "nivel", "origem_inventada")


def test_remover_validacao_campo_origem_especifica():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    dados = adicionar_validacao_campo(dados, "nivel", ORIGEM_QA_AGENTE)
    dados = remover_validacao_campo(dados, "nivel", origem=ORIGEM_HUMANO_APP)
    assert origens_do_campo(dados, "nivel") == {ORIGEM_QA_AGENTE}


def test_remover_validacao_campo_todas_origens():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    dados = remover_validacao_campo(dados, "nivel")
    assert campo_esta_validado(dados, "nivel") is False


def test_campo_esta_validado_qualquer_origem_conta():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_QA_AGENTE)
    assert campo_esta_validado(dados, "nivel") is True
    assert campo_esta_validado(dados, "outro_campo") is False


def test_calcular_selos_azul_quando_100_por_cento_humano_app():
    dados = {}
    for campo in ("nivel", "classificacao"):
        dados = adicionar_validacao_campo(dados, campo, ORIGEM_HUMANO_APP)
    selos = calcular_selos_item(dados, na_fields=[], campos_obrigatorios=["nivel", "classificacao"])
    assert selos == {"azul": True, "rosa": False, "laranja": False}


def test_calcular_selos_azul_falso_se_falta_1_campo():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    selos = calcular_selos_item(dados, na_fields=[], campos_obrigatorios=["nivel", "classificacao"])
    assert selos["azul"] is False


def test_calcular_selos_na_fields_conta_como_resolvido():
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_HUMANO_APP)
    selos = calcular_selos_item(dados, na_fields=["classificacao"], campos_obrigatorios=["nivel", "classificacao"])
    assert selos["azul"] is True


def test_calcular_selos_laranja_puro():
    dados = {}
    for campo in ("nivel", "classificacao"):
        dados = adicionar_validacao_campo(dados, campo, ORIGEM_QA_AGENTE)
    selos = calcular_selos_item(dados, na_fields=[], campos_obrigatorios=["nivel", "classificacao"])
    assert selos == {"azul": False, "rosa": False, "laranja": True}


def test_calcular_selos_laranja_e_isolado_mix_com_azul_nao_conta():
    """Correção do dono: laranja fica ISOLADO (só qa_agente) — mix com
    azul NÃO conta mais pro selo laranja (era a regra anterior, revogada)."""
    dados = adicionar_validacao_campo({}, "nivel", ORIGEM_QA_AGENTE)
    dados = adicionar_validacao_campo(dados, "classificacao", ORIGEM_HUMANO_APP)
    selos = calcular_selos_item(dados, na_fields=[], campos_obrigatorios=["nivel", "classificacao"])
    assert selos["laranja"] is False  # só 1 dos 2 campos é qa_agente
    assert selos["azul"] is False  # só 1 dos 2 campos é humano_app


def test_calcular_selos_rosa_puro():
    dados = {}
    for campo in ("nivel", "classificacao"):
        dados = adicionar_validacao_campo(dados, campo, ORIGEM_HUMANO_PORTAL)
    selos = calcular_selos_item(dados, na_fields=[], campos_obrigatorios=["nivel", "classificacao"])
    assert selos == {"azul": False, "rosa": True, "laranja": False}


def test_calcular_selos_item_pode_ter_azul_rosa_e_laranja_juntos():
    """Um item pode ter os 3 selos calculados aqui ao mesmo tempo — cada
    campo tendo as 3 origens simultaneamente cobre os 3 critérios."""
    dados = {}
    for campo in ("nivel", "classificacao"):
        dados = adicionar_validacao_campo(dados, campo, ORIGEM_HUMANO_APP)
        dados = adicionar_validacao_campo(dados, campo, ORIGEM_HUMANO_PORTAL)
        dados = adicionar_validacao_campo(dados, campo, ORIGEM_QA_AGENTE)
    selos = calcular_selos_item(dados, na_fields=[], campos_obrigatorios=["nivel", "classificacao"])
    assert selos == {"azul": True, "rosa": True, "laranja": True}


def test_calcular_selos_sem_campos_obrigatorios_nunca_valida():
    selos = calcular_selos_item({}, na_fields=[], campos_obrigatorios=[])
    assert selos == {"azul": False, "rosa": False, "laranja": False}
