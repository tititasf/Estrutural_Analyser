import json
import sqlite3
from pathlib import Path

import pytest

from scripts.arete.diagnostico_lv_n1_n2 import (
    _numbers_from_text,
    classify_delta,
    run_diagnostic,
)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (0.02, "EXCELENTE"),
        (0.05, "BOM"),
        (0.10, "REGULAR"),
        (0.1001, "RUIM"),
        (None, "INDETERMINADO"),
    ],
)
def test_classify_delta_uses_arete_thresholds(delta, expected):
    assert classify_delta(delta) == expected


def test_numbers_from_text_extracts_both_numbers_regardless_of_order():
    assert _numbers_from_text("19/55") == {19.0, 55.0}
    assert _numbers_from_text("100/19") == {100.0, 19.0}
    assert _numbers_from_text("") == set()
    assert _numbers_from_text(None) == set()


def _create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "id INTEGER PRIMARY KEY, obra_name TEXT, pavimento TEXT, classe TEXT, "
        "elemento_id TEXT, campos_json TEXT, status TEXT, confianca REAL)"
    )
    rows = [
        (1, "Obra_TESTE", "13_PAV", "LV", "V301",
         json.dumps({
             "total_width": 19.0, "h_section": 55.0, "h_section_all": [],
             "panels_A": [{"height1": 125.0, "height2": 0.0}],
             "panels_B": [{"height1": 125.0, "height2": 0.0}],
         }), "draft", 0.9),
        (2, "Obra_TESTE", "13_PAV", "LV", "V302",
         json.dumps({
             "total_width": 19.0, "h_section": 55.0, "h_section_all": [],
             "panels_A": [], "panels_B": [],
         }), "draft", 0.9),
        (3, "Obra_TESTE", "13_PAV", "LV", "V999",
         json.dumps({"total_width": 19.0, "h_section": 55.0}), "draft", 0.8),
        (4, "Obra_TESTE", "12_PAV", "LV", "V888",
         json.dumps({"total_width": 19.0, "h_section": 55.0}), "draft", 0.8),
    ]
    connection.executemany(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?,?,?)", rows
    )
    connection.commit()
    connection.close()


def test_run_diagnostic_is_headless_versioned_and_emits_schema_v2(tmp_path: Path):
    state = {
        "gerado_em": "2026-07-03T00:44:24",
        "obra": "Obra_TESTE",
        "pavimento": "TMC-EST-13P",
        "segmentos": {
            "lateral_a_para": [
                {"beam_name": "V301", "side": "A", "width": "19/55"},
                {"beam_name": "V302", "side": "A", "width": "19/120"},
                {"beam_name": "V303", "side": "A", "width": "19/55"},
            ],
            "lateral_b_para": [
                {"beam_name": "V301", "side": "B", "width": "19/55"},
                {"beam_name": "V302", "side": "B", "width": "19/120"},
            ],
            "lateral_a_passa": [],
            "lateral_b_passa": [],
        },
    }
    state_path = tmp_path / "estado_13_PAV.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    db_path = tmp_path / "project_data.vision"
    _create_db(db_path)

    report, json_path, jsonl_path = run_diagnostic(
        obra="Obra_TESTE",
        pavimento="13_PAV",
        state_path=state_path,
        db_path=db_path,
        output_root=tmp_path / "relatorios",
    )

    assert report["schema_version"] == 2
    assert report["run_id"] == "20260703_004424"
    assert report["resumo"]["itens"] == 4  # V301, V302, V303 (só N1), V999 (só N2)
    assert report["resumo"]["n1_itens"] == 3
    assert report["resumo"]["n2_itens"] == 3  # V301, V302, V999 — V888 é 12_PAV (excluído)

    items = {item["item"]: item for item in report["itens"]}

    # V301: números {19,55} do N1 batem com total_width/h_section do N2 -> sem alerta
    assert items["V301"]["causa_raiz"] is None
    assert items["V301"]["status"] == "nao_reproduzido"
    assert items["V301"]["marcado_por"] == "auto"
    assert items["V301"]["concordancia"] == "pendente"

    # V302: 120 não aparece em nenhum campo do N2 -> schema_gap (não extractor_bug,
    # ver docstring do módulo — correspondência de campo ainda não confirmada)
    assert items["V302"]["causa_raiz"] == "schema_gap"
    assert 120.0 in items["V302"]["evidencia"]["numeros_ausentes_no_n2"]
    assert items["V302"]["confianca"] == 0.6

    # V303: só existe no N1 (sem ficha N2) -> schema_gap, confiança alta (fato, não hipótese)
    assert items["V303"]["causa_raiz"] == "schema_gap"
    assert "apenas no N1" in items["V303"]["causa_descricao"]
    assert items["V303"]["confianca"] == 0.99

    # V999: só existe no N2 (sem segmento N1) -> schema_gap
    assert items["V999"]["causa_raiz"] == "schema_gap"
    assert "apenas no N2" in items["V999"]["causa_descricao"]

    expected_dir = (
        tmp_path / "relatorios" / "Obra_TESTE" / "13_PAV" / "20260703_004424"
    )
    assert json_path == expected_dir / "diagnostico_lv_n1_n2.json"
    assert jsonl_path == expected_dir / "triagem_auto_lv.jsonl"

    jsonl_items = {
        json.loads(line)["item"]
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    }
    assert jsonl_items == {"V302", "V303", "V999"}
