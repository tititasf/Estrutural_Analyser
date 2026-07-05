from pathlib import Path

import pytest

from src.core.item_attention_store import (
    ensure_table,
    is_human_validated,
    load_attention,
    load_para_passa,
    save_attention,
    save_human_validation,
    save_para_passa,
)


def test_attention_notes_keep_origin_metadata(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"

    save_attention(
        "Obra_TREINO_3",
        "TERREO",
        "PIL",
        "P101",
        "N3",
        True,
        "Verificar face A/B.",
        db_path=db_path,
        note_origin="human_ui",
        updated_by="thierry",
        metadata={"source": "comparison_engine"},
    )

    data = load_attention("Obra_TREINO_3", "TERREO", "PIL", "P101", "N3", db_path)
    assert data["attention"] is True
    assert data["note"] == "Verificar face A/B."
    assert data["note_origin"] == "human_ui"
    assert data["updated_by"] == "thierry"
    assert "comparison_engine" in data["metadata_json"]


def test_human_validation_requires_human_origin(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    ensure_table(db_path)

    with pytest.raises(ValueError):
        save_human_validation(
            "Obra_TREINO_3",
            "TERREO",
            "PIL",
            "P101",
            "N3",
            True,
            db_path=db_path,
            validation_origin="cli",
        )

    assert is_human_validated("Obra_TREINO_3", "TERREO", "PIL", "P101", "N3", db_path) is False


def test_human_ui_validation_is_recorded(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"

    save_human_validation(
        "Obra_TREINO_3",
        "TERREO",
        "PIL",
        "P101",
        "N3",
        True,
        db_path=db_path,
        validation_origin="human_ui",
        updated_by="thierry",
    )

    data = load_attention("Obra_TREINO_3", "TERREO", "PIL", "P101", "N3", db_path)
    assert data["human_validated"] is True
    assert data["validation_origin"] == "human_ui"
    assert data["updated_by"] == "thierry"


def test_para_passa_loads_canonical_pavimento_from_project_name(tmp_path: Path):
    db_path = tmp_path / "project_data.vision"
    save_para_passa(
        "Obra_TREINO_1",
        "13_PAV",
        "LV",
        "V301",
        "passa",
        db_path=db_path,
    )

    assert load_para_passa(
        "Obra_TREINO_1",
        "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA",
        "LV",
        "V301",
        db_path=db_path,
    ) == "passa"
