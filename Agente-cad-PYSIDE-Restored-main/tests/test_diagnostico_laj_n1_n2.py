import json
import sqlite3
from pathlib import Path

import pytest

from scripts.arete.diagnostico_laj_n1_n2 import (
    classify_delta,
    compare_polygon_footprint,
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


def _create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "id INTEGER PRIMARY KEY, obra_name TEXT, pavimento TEXT, classe TEXT, "
        "elemento_id TEXT, campos_json TEXT, status TEXT, confianca REAL)"
    )
    rows = [
        (1, "Obra_TESTE", "13_PAV", "LAJ", "L301",
         json.dumps({
             "comprimento": 100.0,
             "largura": 50.0,
             "area_cm2": 5000.0,
             "coordenadas": [(0, 0), (100, 0), (100, 50), (0, 50), (0, 0)],
         }), "draft", 0.9),
        (2, "Obra_TESTE", "13_PAV", "LAJ", "L318",
         json.dumps({
             "comprimento": 2413.0,
             "largura": 152.0,
             "area_cm2": 366776.0,
             "coordenadas": [(0, 0), (2413, 0), (2413, 152), (0, 152), (0, 0)],
         }), "draft", 0.9),
        (3, "Obra_TESTE", "13_PAV", "LAJ", "L999",
         json.dumps({
             "comprimento": 80.0,
             "largura": 40.0,
             "area_cm2": 3200.0,
             "coordenadas": [(0, 0), (80, 0), (80, 40), (0, 40), (0, 0)],
         }), "draft", 0.8),
        (4, "Obra_TESTE", "12_PAV", "LAJ", "L888",
         json.dumps({"comprimento": 80.0, "largura": 40.0}), "draft", 0.8),
    ]
    connection.executemany(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?,?,?)", rows
    )
    connection.commit()
    connection.close()


def _rect(width: float, height: float) -> list:
    return [(0, 0), (width, 0), (width, height), (0, height), (0, 0)]


def test_compare_polygon_footprint_rejects_same_bbox_with_different_contour():
    n1 = _rect(100, 100)
    n2 = [(0, 0), (100, 0), (100, 100), (50, 100), (50, 50), (0, 50), (0, 0)]

    result = compare_polygon_footprint(n1, n2, n2_area_cm2=7500.0)

    assert result is not None
    assert result["classificacao"] == "RUIM"
    assert result["iou"] < 0.90
    assert result["symmetric_diff_pct"] > 0.10


def test_run_diagnostic_is_headless_versioned_and_emits_schema_v2(tmp_path: Path):
    state = {
        "gerado_em": "2026-07-03T12:00:00",
        "obra": "Obra_TESTE",
        "pavimento": "TMC-EST-13P",
        "slabs": [
            {"name": "L301", "nivel": "852.12", "height": "12", "points": _rect(50, 100)},
            # L318: reproduz o bug real documentado no §7 do procedimento —
            # bbox N1 "engolindo" a fileira (2831x201) vs N2 real (2413x152)
            {"name": "L318", "nivel": "852.19", "height": "12", "points": _rect(2831.12, 201.0)},
            {"name": "L320", "nivel": "852.10", "height": "12", "points": _rect(60, 30)},
        ],
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
    assert report["run_id"] == "20260703_120000"
    assert report["resumo"]["itens"] == 4  # L301, L318, L320 (N1) + L999 (só N2)
    assert report["resumo"]["n1_itens"] == 3
    assert report["resumo"]["n2_itens"] == 3

    items = {item["item"]: item for item in report["itens"]}

    # L301: bbox 50x100 == comprimento/largura 100/50 (eixo trocado) -> EXCELENTE
    assert items["L301"]["causa_raiz"] is None
    assert items["L301"]["status"] == "nao_reproduzido"
    assert items["L301"]["marcado_por"] == "auto"
    assert items["L301"]["concordancia"] == "pendente"

    # L318: bug real documentado — RUIM, contorno divergente, confiança REDUZIDA (0.7,
    # não 0.85/0.95 como PIL/FV) por causa da ambiguidade overlap-viga vs overlap-laje
    assert items["L318"]["causa_raiz"] == "n1_contorno_divergente"
    assert items["L318"]["evidencia"]["classificacao"] == "RUIM"
    assert items["L318"]["evidencia"]["geometria"]["iou"] < 0.90
    assert items["L318"]["confianca"] == 0.7
    assert "Contorno" in items["L318"]["causa_descricao"]

    # L320: sem ficha N2 -> schema_gap, confiança alta (fato, não hipótese)
    assert items["L320"]["causa_raiz"] == "schema_gap"
    assert "apenas no N1" in items["L320"]["causa_descricao"]

    # L999: só existe no N2 -> schema_gap
    assert items["L999"]["causa_raiz"] == "schema_gap"
    assert "apenas no N2" in items["L999"]["causa_descricao"]

    expected_dir = (
        tmp_path / "relatorios" / "Obra_TESTE" / "13_PAV" / "20260703_120000"
    )
    assert json_path == expected_dir / "diagnostico_laj_n1_n2.json"
    assert jsonl_path == expected_dir / "triagem_auto_laj.jsonl"

    jsonl_items = {
        json.loads(line)["item"]
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    }
    assert jsonl_items == {"L318", "L320", "L999"}
