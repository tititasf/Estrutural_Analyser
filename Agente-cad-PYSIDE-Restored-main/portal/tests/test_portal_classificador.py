"""Classificador de classe/pavimento por nome de arquivo (2026-07-06).

Casos reais retirados de DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/ (não
inventados) — a suíte prova que a sugestão bate com o que sabemos ser
verdade para esses arquivos, e que casos ambíguos honestamente caem em
'revisar' (nunca uma sugestão errada disfarçada de certeza).
"""

from __future__ import annotations

from portal.app.classificador import (
    classificar_arquivo, sugerir_classe, sugerir_pavimento, sugerir_tipo_documento,
)


def test_classe_detecta_as_5_classes_reais():
    assert sugerir_classe("ALIMONTI - PARAISO - 13° PAV.- PL - R00.dxf") == "PIL"
    assert sugerir_classe("ALIMONTI - PARAISO - 13° PAV.- LV - R00.dxf") == "LV"
    assert sugerir_classe("ALIMONTI - PARAISO - 13° PAV.- FV - R00.dxf") == "FV"
    assert sugerir_classe("ALIMONTI - PARAISO - 13° PAV.- LJ - R00.dxf") == "LAJ"
    assert sugerir_classe("ALIMONTI - PARAISO - 13° PAV.- GF - R00.dxf") == "GF"


def test_classe_nao_identificada_devolve_none_nunca_lanca():
    assert sugerir_classe("TMC-EST-PE-6000-13P-R03.dwg") is None
    assert sugerir_classe("arquivo_sem_padrao_nenhum.dxf") is None


def test_pavimento_numerico_com_grau_e_reconhecido():
    """Achado real: "13° PAV" (grau+espaço) quebrava o casamento de _floor_key
    sem normalização — testado com o nome de arquivo real da obra."""
    assert sugerir_pavimento("ALIMONTI - PARAISO - 13° PAV.- FV - R00.dxf") == "13_PAV"
    assert sugerir_pavimento("ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf") == "1_PAV"


def test_pavimento_abreviado_tmc_e_reconhecido():
    """Convenção "Estruturais_dos_Pavimentos_Estado_Bruto" real: dígito+P colado."""
    assert sugerir_pavimento("TMC-EST-PE-6000-13P-R03.dwg") == "13_PAV"


def test_pavimento_especial_abreviado_e_reconhecido():
    assert sugerir_pavimento("TMC-EST-PE-8000-COB-R03.dwg") == "COBERTURA"


def test_pavimento_ambiguo_devolve_none_nao_chuta():
    """Faixa de pavimentos ("3° AO 12° PAV") e palavra cheia não-abreviada
    ("TÉRREO", "COBERTURA E DECK") são ambíguos de verdade — o classificador
    NUNCA deve inventar uma resposta única errada; 'revisar' é o correto."""
    assert sugerir_pavimento("ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- PL - R00.dxf") is None
    assert sugerir_pavimento("ALIMONTI - PARAISO - TÉRREO - FV - R00.dxf") is None


def test_classificar_arquivo_promove_a_classificado_so_quando_os_2_batem():
    r1 = classificar_arquivo("ALIMONTI - PARAISO - 13° PAV.- PL - R00.dxf")
    assert r1 == {
        "classe_sugerida": "PIL", "pavimento_sugerido": "13_PAV",
        "tipo_documento_sugerido": "Bruto", "status": "classificado",
    }

    r2 = classificar_arquivo("ALIMONTI - PARAISO - TÉRREO - FV - R00.dxf")
    assert r2["classe_sugerida"] == "FV"
    assert r2["pavimento_sugerido"] is None
    assert r2["status"] == "revisar"

    r3 = classificar_arquivo("arquivo_qualquer.dxf")
    assert r3 == {
        "classe_sugerida": None, "pavimento_sugerido": None,
        "tipo_documento_sugerido": "Bruto", "status": "revisar",
    }


# --------------------------------------------------------------------------- #
# tipo_documento (2026-07-07) — eixo NOVO: Bruto/Detalhe/PDF, diferente de
# classe estrutural (PIL/LV/FV/LAJ/GF).
# --------------------------------------------------------------------------- #

def test_sugerir_tipo_documento_pdf_pela_extensao():
    assert sugerir_tipo_documento("ALIMONTI - MEMORIAL DESCRITIVO.pdf") == "PDF"


def test_sugerir_tipo_documento_detalhe_por_marcador_no_nome():
    assert sugerir_tipo_documento("ALIMONTI - PARAISO - 13 PAV - DETALHE ESCADA.dxf") == "Detalhe"


def test_sugerir_tipo_documento_default_bruto():
    assert sugerir_tipo_documento("ALIMONTI - PARAISO - 13° PAV.- PL - R00.dxf") == "Bruto"


def test_classificar_arquivo_pdf_nao_exige_classe_estrutural():
    """PDF é material de referência — não passa pelo pipeline DXF, então não
    precisa de classe_sugerida pra ser considerado 'classificado' (só pavimento)."""
    r = classificar_arquivo("ALIMONTI - PARAISO - 13° PAV - MEMORIAL.pdf")
    assert r["tipo_documento_sugerido"] == "PDF"
    assert r["classe_sugerida"] is None
    assert r["pavimento_sugerido"] == "13_PAV"
    assert r["status"] == "classificado"
