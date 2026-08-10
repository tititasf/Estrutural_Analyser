"""Normalização de pavimento — ponto único de vínculo recorte <-> ficha.

Todos os casos abaixo são grafias REAIS extraídas de `reverse_eng_recortes`
(806 linhas) e de `reverse_eng_fichas` do project_data.vision em 2026-07-30.
Errar aqui não dá erro: dá vínculo silenciosamente errado, gate lendo zeros e
relatório acusando "campo obrigatório ausente" como se fosse falha do motor.
"""
from __future__ import annotations

import pytest

from src.core.obra_identity import (
    mesmo_pavimento,
    normalizar_pavimento,
    pavimento_de_caminho,
)


@pytest.mark.parametrize("bruto,esperado", [
    # Pastas reais da Obra_TREINO_1
    ("ALIMONTI - PARAISO - 13° PAV.- FV - R00", "13_PAV"),
    ("ALIMONTI - PARAISO - 1° PAV.- PL - R00", "1_PAV"),
    ("ALIMONTI - PARAISO - 2° PAV.- LJ - R00", "2_PAV"),
    ("ALIMONTI - PARAISO - 14° PAV.- LV - R00", "14_PAV"),
    ("ALIMONTI - PARAISO - TÉRREO - PL - R00", "TERREO"),
    ("NOVA - ALIMONTI - PARAISO - COBERTURA - DECK - LJ - R00", "COBERTURA"),
    ("NOVA - ALIMONTI - PARAISO - COBERTURA E DECK - PL - R00", "COBERTURA"),
    # Já canônico entra e sai igual (idempotência)
    ("13_PAV", "13_PAV"),
    ("COBERTURA", "COBERTURA"),
    ("TERREO", "TERREO"),
    # Portal / código de prancha (viewer destaques)
    ("FUNDACAO", "FUNDACAO"),
    ("LOCACAO", "LOCACAO"),
    ("ATICO", "ATICO"),
    ("TIPO", "TIPO"),
])
def test_grafias_reais(bruto, esperado):
    assert normalizar_pavimento(bruto) == esperado


def test_intervalo_usa_o_topo_nao_o_inicio():
    """'TIPO - 3° AO 12° PAV' é o pavimento-tipo gravado como 12_PAV.

    Regex ingênua pegaria o primeiro número e devolveria 3_PAV — que não existe
    no banco (só 12_PAV). Vincularia a nada, em silêncio.
    """
    assert normalizar_pavimento("ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- PL - R00") == "12_PAV"


def test_mojibake_de_paths_gravados():
    """recorte_path tem encoding corrompido gravado ('13� PAV'). Tem de funcionar."""
    assert normalizar_pavimento("ALIMONTI - 13\ufffd PAV.- FV - R00") == "13_PAV"
    assert normalizar_pavimento("ALIMONTI - 1\ufffd PAV.- PL") == "1_PAV"


def test_variacoes_de_ordinal():
    for grafia in ("13° PAV", "13º PAV", "13 PAV", "13PAV", "13 PAVIMENTO"):
        assert normalizar_pavimento(grafia) == "13_PAV", grafia


def test_subsolo_com_erro_de_digitacao_real():
    """'1° SUBOLO' (sic) está gravado na obra S.DIAMOND."""
    assert normalizar_pavimento("S.DIAMOND - 1° SUBOLO - PL - PROJEÇÃO - R00") == "1_SUBSOLO"
    assert normalizar_pavimento("1° SUBSOLO") == "1_SUBSOLO"


@pytest.mark.parametrize("bruto", ["", None, "planta generica", "R00_R2018_ASCII_ODA", "PIL_P35_motor.dxf"])
def test_nao_reconhecido_devolve_none_em_vez_de_chutar(bruto):
    """Chutar cria vínculo errado, que é pior do que não vincular."""
    assert normalizar_pavimento(bruto) is None


def test_zero_a_esquerda_normaliza():
    assert normalizar_pavimento("03° PAV") == "3_PAV"


# ── pavimento_de_caminho ─────────────────────────────────────────────────────

def test_caminho_windows_real():
    caminho = (
        r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem"
        r"\recortes_reversos\ALIMONTI - PARAISO - 13° PAV.- FV - R00"
        r"\FV_V301_motor_178111331094.dxf"
    )
    assert pavimento_de_caminho(caminho) == "13_PAV"


def test_caminho_prefere_o_segmento_mais_especifico():
    """Pasta do recorte vence a raiz da obra: percorre da folha para a raiz."""
    caminho = "/obras/EDIFICIO 2 PAV/recortes/ALIMONTI - 13° PAV.- PL - R00/PIL_P1.dxf"
    assert pavimento_de_caminho(caminho) == "13_PAV"


def test_caminho_sem_pavimento():
    assert pavimento_de_caminho("/obras/qualquer/arquivo.dxf") is None
    assert pavimento_de_caminho(None) is None


# ── mesmo_pavimento ──────────────────────────────────────────────────────────

def test_mesmo_pavimento_entre_origens_diferentes():
    """O caso que o vínculo recorte->ficha precisa acertar."""
    assert mesmo_pavimento("ALIMONTI - PARAISO - 13° PAV.- FV - R00", "13_PAV")
    assert mesmo_pavimento("ALIMONTI - PARAISO - TÉRREO - PL - R00", "TERREO")


def test_mesmo_pavimento_recusa_diferentes():
    assert not mesmo_pavimento("13_PAV", "14_PAV")
    assert not mesmo_pavimento("COBERTURA", "TERREO")


def test_dois_desconhecidos_nao_sao_iguais():
    """None == None casaria qualquer coisa com qualquer coisa."""
    assert not mesmo_pavimento(None, None)
    assert not mesmo_pavimento("lixo", "outro lixo")
