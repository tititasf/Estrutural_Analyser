from __future__ import annotations

import ezdxf

from portal.app.preprocessamento.adapters.level_convention import extract_level_convention


def _drawing(path, annotations):
    document = ezdxf.new("R2010")
    for value, position in annotations:
        document.modelspace().add_text(value, dxfattribs={"insert": position})
    document.saveas(path)


def test_preserva_zero_negativo_virgula_e_unidade_desconhecida(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [
        ("14 PAV.", (0, 100)),
        ("0,00", (100, 100)),
        ("15 PAV.", (0, 80)),
        ("-3,25", (100, 80)),
    ])
    result = extract_level_convention(path)

    assert result["unit"] is None
    assert {item["text"] for item in result["raw_cotas"]} == {"0,00", "-3,25"}
    assert "cotas_fora_do_dominio_do_extrator_legado" in result["warnings"]
    assert result["status"] == "partial"
    assert all(row["chegada"] == "?" for row in result["rows"])
    assert [row["selected"]["value"] for row in result["direct_floor_levels"]] == [0.0, -3.25]
    assert all(row["selected"]["unit"] is None for row in result["direct_floor_levels"])


def test_unidade_explicitamente_declarada_sem_assumir_datum(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [
        ("NIVEIS EM METROS", (0, 130)),
        ("14 PAV.", (0, 100)),
        ("855,18", (100, 100)),
        ("15 PAV.", (0, 80)),
        ("858,18", (100, 80)),
    ])
    result = extract_level_convention(path)

    assert result["unit"] == "m"
    assert result["datum"] is None
    assert result["rows"][0]["chegada"] == "855,18"
    assert result["rows"][0]["saida"] == "858,18"
    assert result["direct_floor_levels"][0]["selected"]["unit"] == "m"


def test_medidas_em_cm_e_niveis_em_m_na_mesma_prancha(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [
        ("MEDIDAS EM CENTIMETROS - NIVEIS EM METROS", (0, 130)),
        ("14 PAV.", (0, 100)),
        ("855,25", (100, 100)),
    ])
    result = extract_level_convention(path)
    assert result["unit"] == "m"
    assert "unidades_conflitantes" not in result["warnings"]
    assert result["direct_floor_levels"][0]["selected"]["unit"] == "m"


def test_unidades_conflitantes_permanecem_ambiguas(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [("COTAS EM METROS", (0, 50)), ("NIVEIS EM CENTIMETROS", (0, 30))])
    result = extract_level_convention(path)
    assert result["unit"] is None
    assert "unidades_conflitantes" in result["warnings"]


def test_cotas_empatadas_na_mesma_linha_nao_escolhem_primeira(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [
        ("14 PAV.", (0, 100)),
        ("0,00", (100, 100)),
        ("3,00", (200, 100)),
    ])
    result = extract_level_convention(path)
    row = result["direct_floor_levels"][0]
    assert row["status"] == "ambiguous"
    assert row["selected"] is None
    assert {value["value"] for value in row["candidates"]} == {0.0, 3.0}


def test_cota_longe_na_mesma_altura_nao_vira_nivel_do_pavimento(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [("14 PAV.", (0, 100)), ("855,18", (1200, 100))])
    row = extract_level_convention(path)["direct_floor_levels"][0]
    assert row["status"] == "unknown"
    assert row["selected"] is None


def test_mesma_cota_nao_e_prova_direta_de_dois_pavimentos(tmp_path):
    path = tmp_path / "levels.dxf"
    _drawing(path, [
        ("14 PAV.", (0, 100)),
        ("15 PAV.", (0, 80)),
        ("855,18", (100, 90)),
    ])
    readings = extract_level_convention(path)["direct_floor_levels"]
    assert all(row["status"] == "ambiguous" and row["selected"] is None for row in readings)
    assert all(row["warnings"] == ["cota_compartilhada_por_pavimentos"] for row in readings)
