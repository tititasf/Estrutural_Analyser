import json
import sqlite3
from pathlib import Path

import ezdxf
import pytest

from scripts.arete.diagnostico_fv_n1_n2 import (
    _compare_segment_measures,
    classify_delta,
    diagnose_item,
    load_n1_beams,
    load_n2_beams,
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


def test_segment_measures_compare_physical_multiset_with_five_hundredths_cm_tolerance():
    comparison = _compare_segment_measures(
        [291.04, 252.96],
        [253.0, 291.0],
    )

    assert comparison["match"] is True
    assert comparison["metodo"] == "multiconjunto_ordenado"
    assert comparison["pares"][0]["delta_abs_cm"] == pytest.approx(0.04)


def test_segment_measures_reject_same_total_with_wrong_partition():
    comparison = _compare_segment_measures([50.0, 150.0], [100.0, 100.0])

    assert comparison["match"] is False
    assert [pair["passa"] for pair in comparison["pares"]] == [False, False]


def test_segment_measures_reject_tenth_cm_delta():
    comparison = _compare_segment_measures([100.1], [100.0])

    assert comparison["match"] is False
    assert comparison["pares"][0]["delta_abs_cm"] == pytest.approx(0.1)


def test_diagnose_never_calls_equal_total_with_wrong_segmentation_excellent():
    item = diagnose_item(
        "V322",
        {
            "largura": 19.0,
            "comprimento_total": 380.0,
            "comprimentos": [118.0, 112.0, 150.0],
            "segmentos": 3,
        },
        {
            "largura": 19.0,
            "comprimento_total": 380.0,
            "comprimentos": [118.0, 262.0],
            "segmentos": 2,
        },
        obra="Obra_TESTE",
        pavimento="13_PAV",
        generated_at="2026-07-16T00:00:00+00:00",
    )

    assert item["causa_raiz"] == "schema_gap"
    assert item["evidencia"]["classificacao"] == "DIVERGENTE_SEGMENTOS"
    assert item["evidencia"]["deltas"] == {"largura": 0.0, "comprimento_total": 0.0}


def test_load_n1_beams_uses_special_diagonal_measure_instead_of_global_bbox(tmp_path: Path):
    state = {
        "segmentos": {
            "fundo": [
                {
                    "beam_name": "V307",
                    "segment_label": "1",
                    "length": 255.7,
                    "width": 35.4,
                    "status": "valid",
                    "measure_source": "special_diagonal_longest_edge",
                    "measure_length": 255.7,
                    "measure_width": 35.4,
                    "points": [
                        (1178.8825, 2240.038),
                        (1197.8825, 2240.038),
                        (1197.8825, 2217.506423),
                        (1356.845108, 2067.038),
                        (1603.3825, 2067.038),
                        (1603.3825, 2048.038),
                        (1349.278794, 2048.038),
                        (1178.8825, 2209.329149),
                        (1178.8825, 2240.038),
                    ],
                }
            ]
        }
    }
    state_path = tmp_path / "estado.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    _, beams = load_n1_beams(state_path)

    assert beams["V307"]["comprimentos"] == [255.7]
    assert beams["V307"]["comprimento_geometrico_total"] == 255.7
    assert beams["V307"]["largura"] == 35.4


def test_load_n1_beams_uses_declared_length_for_complex_local_axis_polygon(tmp_path: Path):
    state = {
        "segmentos": {
            "fundo": [
                {
                    "beam_name": "V307",
                    "segment_label": "1",
                    "length": 254.1,
                    "width": 19,
                    "status": "valid",
                    "points": [
                        (1178.8825, 2240.038),
                        (1197.8825, 2240.038),
                        (1197.8825, 2217.506423),
                        (1356.845108, 2067.038),
                        (1603.3825, 2067.038),
                        (1603.3825, 2048.038),
                        (1349.278794, 2048.038),
                        (1178.8825, 2209.329149),
                        (1178.8825, 2240.038),
                    ],
                }
            ]
        }
    }
    state_path = tmp_path / "estado.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    _, beams = load_n1_beams(state_path)

    assert beams["V307"]["comprimentos"] == [254.1]
    assert beams["V307"]["comprimento_geometrico_total"] == 254.1


def _create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "id INTEGER PRIMARY KEY, obra_name TEXT, pavimento TEXT, classe TEXT, "
        "elemento_id TEXT, campos_json TEXT, status TEXT, confianca REAL)"
    )
    rows = [
        (
            1,
            "Obra_TESTE",
            "13_PAV",
            "FV",
            "V101",
            json.dumps({
                "total_width": 20,
                "total_height": 200,
                "segments_rich": [{"total_width": 100}, {"total_width": 100}],
                "holes": [{"active": True}],
            }),
            "draft",
            0.9,
        ),
        (
            2,
            "Obra_TESTE",
            "13_PAV",
            "FV",
            "V102",
            json.dumps({
                "total_width": 20,
                "total_height": 100,
                "segments_rich": [{"total_width": 100}],
                "holes": [],
            }),
            "draft",
            0.8,
        ),
        (
            3,
            "Obra_TESTE",
            "12_PAV",
            "FV",
            "V999",
            json.dumps({"total_width": 20, "total_height": 100}),
            "draft",
            0.8,
        ),
    ]
    connection.executemany(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?,?,?)", rows
    )
    connection.commit()
    connection.close()


def test_load_n2_beams_expands_dxf_multiplier_text_into_physical_segments(
    tmp_path: Path,
):
    dxf_path = tmp_path / "FV_V306.dxf"
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("254", dxfattribs={"insert": (0, 0)})
    msp.add_text("418", dxfattribs={"insert": (100, 0)})
    msp.add_text("5x", dxfattribs={"insert": (100, 24)})
    doc.saveas(dxf_path)

    db_path = tmp_path / "project_data.vision"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "id INTEGER PRIMARY KEY, obra_name TEXT, pavimento TEXT, classe TEXT, "
        "elemento_id TEXT, campos_json TEXT, status TEXT, confianca REAL)"
    )
    connection.execute(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?,?,?)",
        (
            1,
            "Obra_TESTE",
            "13_PAV",
            "FV",
            "V306",
            json.dumps({
                "total_width": 19,
                "total_height": 672,
                "segments_rich": [
                    {"total_width": 254},
                    {"total_width": 418},
                ],
                "_er_meta": {"dxf_path": str(dxf_path)},
                "holes": [],
            }),
            "draft",
            0.9,
        ),
    )
    connection.commit()
    connection.close()

    beams = load_n2_beams(db_path, "Obra_TESTE", "13_PAV")

    assert beams["V306"]["segmentos"] == 6
    assert beams["V306"]["segmentos_logicos"] == 2
    assert beams["V306"]["comprimentos"] == [254.0, 418.0, 418.0, 418.0, 418.0, 418.0]
    assert beams["V306"]["comprimento_total"] == 2344.0
    assert beams["V306"]["detalhe_segmentos_n2"][1] == {
        "index": 2,
        "comprimento_cm": 418.0,
        "multiplicador": 5,
        "origem_multiplicador": "dxf_text",
    }


def test_run_diagnostic_is_headless_versioned_and_emits_schema_v2(tmp_path: Path):
    state = {
        "gerado_em": "2026-07-02T19:46:11",
        "obra": "Obra_TESTE",
        "pavimento": "TMC-EST-PE-6000-13P-R03",
        "segmentos": {
            "fundo": [
                {
                    "beam_name": "V101",
                    "segment_label": "1",
                    "length": 100,
                    "width": 20,
                    "status": "valid",
                    "points": [(0, 0), (100, 0), (100, 20), (0, 20)],
                },
                {
                    "beam_name": "V101",
                    "segment_label": "2",
                    "length": 100,
                    "width": 20,
                    "status": "valid",
                    "points": [(100, 0), (200, 0), (200, 20), (100, 20)],
                },
                {
                    "beam_name": "V102",
                    "segment_label": "1",
                    "length": 140,
                    "width": 20,
                    "status": "valid",
                    "points": [(0, 0), (140, 0), (140, 20), (0, 20)],
                },
                {
                    "beam_name": "VIGNORADA",
                    "segment_label": "1",
                    "length": 100,
                    "width": 20,
                    "status": "Ignorar — remover vínculo",
                    "points": [],
                },
            ]
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
    assert report["run_id"] == "20260702_194611"
    assert report["resumo"] == {
        "itens": 2,
        "n1_itens": 2,
        "n2_itens": 2,
        "alertas": 1,
        "classificacoes": {"DIVERGENTE_SEGMENTOS": 1, "EXCELENTE": 1},
        "segmentacao": {
            "comparaveis": 2,
            "quantidade_pass": 2,
            "quantidade_fail": 0,
            "medidas_pass": 1,
            "medidas_fail": 1,
            "tolerancia_medida_cm": 0.05,
        },
    }
    items = {item["item"]: item for item in report["itens"]}
    assert items["V101"]["causa_raiz"] is None
    assert items["V101"]["status"] == "nao_reproduzido"
    assert items["V101"]["evidencia"]["segmentos_match"] is True
    assert items["V101"]["evidencia"]["medidas_segmentos_match"] is True
    assert items["V102"]["causa_raiz"] == "extractor_bug"
    assert items["V102"]["evidencia"]["medidas_segmentos_match"] is False
    assert items["V102"]["evidencia"]["classificacao"] == "DIVERGENTE_SEGMENTOS"
    assert items["V102"]["evidencia"]["deltas"]["comprimento_total"] == pytest.approx(0.4)
    assert items["V102"]["marcado_por"] == "auto"
    assert items["V102"]["concordancia"] == "pendente"

    expected_dir = (
        tmp_path
        / "relatorios"
        / "Obra_TESTE"
        / "13_PAV"
        / "20260702_194611"
    )
    assert json_path == expected_dir / "diagnostico_fv_n1_n2.json"
    assert jsonl_path == expected_dir / "triagem_auto_fv.jsonl"
    assert json.loads(json_path.read_text(encoding="utf-8"))["resumo"]["alertas"] == 1
    jsonl_rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["item"] for row in jsonl_rows] == ["V102"]
