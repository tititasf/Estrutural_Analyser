from pathlib import Path

from src.core.sa_project_source import select_sa_project


def _project(tmp_path: Path, project_id: str, pavement: str, filename: str):
    source = tmp_path / filename
    source.write_text("0\nEOF\n", encoding="ascii")
    return {
        "id": project_id,
        "work_name": "Obra_TREINO_1",
        "pavement_name": pavement,
        "dxf_path": str(source),
    }


def test_selects_first_project_in_same_order_as_sa_combo(tmp_path):
    current = _project(
        tmp_path, "current", "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA", "torre_1.dxf"
    )
    stale = _project(
        tmp_path, "stale", "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA", "old.dxf"
    )

    selected = select_sa_project(
        [current, stale], obra="Obra_TREINO_1", pavimento="13_PAV"
    )

    assert selected["id"] == "current"
    assert Path(selected["dxf_path"]).name == "torre_1.dxf"


def test_explicit_project_id_is_authoritative(tmp_path):
    first = _project(tmp_path, "first", "13_PAV", "first.dxf")
    chosen = _project(tmp_path, "chosen", "13_PAV", "chosen.dxf")

    selected = select_sa_project(
        [first, chosen],
        obra="Obra_TREINO_1",
        pavimento="13_PAV",
        project_id="chosen",
    )

    assert selected["id"] == "chosen"


def test_does_not_fallback_to_arbitrary_dxf(tmp_path):
    project = _project(tmp_path, "other", "12_PAV", "other.dxf")

    try:
        select_sa_project(
            [project], obra="Obra_TREINO_1", pavimento="13_PAV"
        )
    except LookupError as error:
        assert "13_PAV" in str(error)
    else:
        raise AssertionError("deveria rejeitar pavimento sem projeto SA")
