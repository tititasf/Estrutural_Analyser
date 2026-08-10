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
    AGENT_PENDING_KEY,
    ORIGEM_HUMANO_APP,
    ORIGEM_HUMANO_PORTAL,
    ORIGEM_NA_AGENTE_MARCADOR,
    ORIGEM_QA_AGENTE,
    adicionar_validacao_campo,
    calcular_selos_item,
    campo_esta_validado,
    campo_pendente_do_agente,
    migrar_validated_fields_legado,
    na_motivo_exibicao,
    na_tem_origem_agente,
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


# [2026-07-17] N/A com origem — decisão do dono: N/A decidido pelo agente
# QA fica laranja no app, distinguível de N/A marcado manualmente por um
# humano. Sem coluna nova no banco: o marcador vive dentro do texto livre
# de `na_reasons[field_id]` (já existia, era string solta).

def test_na_tem_origem_agente_detecta_marcador():
    motivo = ORIGEM_NA_AGENTE_MARCADOR + "face sem laje explicitamente marcada"
    assert na_tem_origem_agente(motivo) is True


def test_na_tem_origem_agente_falso_pra_motivo_humano():
    assert na_tem_origem_agente("marcado manualmente pelo usuário") is False
    assert na_tem_origem_agente(None) is False
    assert na_tem_origem_agente("") is False


def test_na_motivo_exibicao_remove_marcador_tecnico():
    motivo = ORIGEM_NA_AGENTE_MARCADOR + "face sem laje explicitamente marcada"
    assert na_motivo_exibicao(motivo) == "face sem laje explicitamente marcada"


def test_na_motivo_exibicao_preserva_motivo_humano_intacto():
    assert na_motivo_exibicao("marcado manualmente pelo usuário") == "marcado manualmente pelo usuário"


def test_na_motivo_exibicao_none_vira_string_vazia():
    assert na_motivo_exibicao(None) == ""


# [2026-07-17] Campo "pendente do agente" — o agente tentou resolver e
# concluiu que precisa de humano; guardado em
# extra_data_json['agent_pending'], mesclado direto no item_data (ver
# database.py::load_pillars/load_slabs). A UI pinta de roxo.

def test_campo_pendente_do_agente_retorna_motivo():
    item = {AGENT_PENDING_KEY: {"dim": "vínculo contaminado"}}
    assert campo_pendente_do_agente(item, "dim") == "vínculo contaminado"


def test_campo_pendente_do_agente_none_quando_ausente():
    item = {AGENT_PENDING_KEY: {"dim": "vínculo contaminado"}}
    assert campo_pendente_do_agente(item, "name") is None


def test_campo_pendente_do_agente_none_quando_sem_chave():
    assert campo_pendente_do_agente({}, "dim") is None


def test_campo_pendente_do_agente_ignora_estrutura_invalida():
    assert campo_pendente_do_agente({AGENT_PENDING_KEY: "nao-e-dict"}, "dim") is None
