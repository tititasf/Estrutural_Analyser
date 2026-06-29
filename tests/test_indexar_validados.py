import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from indexar_validados import format_reverse_eng_text, row_to_meta, tipo_from_classe  # noqa: E402


def test_tipo_from_classe():
    assert tipo_from_classe("PIL") == "pilar"
    assert tipo_from_classe("LAJ") == "laje"
    assert tipo_from_classe("LV") == "viga"
    assert tipo_from_classe("FV") == "viga"


def test_format_reverse_eng_text_includes_core_fields():
    row = {
        "id": 1,
        "obra_name": "Obra_TREINO_1",
        "pavimento": "1_PAV",
        "classe": "PIL",
        "elemento_id": "P101",
        "status": "aprovado",
        "confianca": 0.95,
        "campos_json": '{"comprimento": 60, "largura": 24, "altura": 280, "grade_1": 82}',
    }
    text = format_reverse_eng_text(row)
    assert "Pilar P101" in text
    assert "classe=PIL" in text
    assert "comprimento=60" in text
    assert "grade_1=82" in text


def test_row_to_meta_marks_tier_and_source():
    row = {
        "id": 7,
        "obra_name": "Obra_TREINO_1",
        "pavimento": "13_PAV",
        "classe": "LAJ",
        "elemento_id": "L308",
        "status": "aprovado",
        "confianca": 0.9,
        "campos_json": '{"comprimento": 289, "largura": 183}',
    }
    meta = row_to_meta(row)
    assert meta["tipo"] == "laje"
    assert meta["id"] == "L308"
    assert meta["tier"] == "T1"
    assert meta["source_table"] == "reverse_eng_fichas"
    assert meta["source_id"].startswith("reverse_eng_fichas:7:")
    assert meta["legacy_source_id"] == "reverse_eng_fichas:7"
