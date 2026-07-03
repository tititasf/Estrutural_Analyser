import json
import sqlite3
from pathlib import Path

import pytest

from scripts.arete.diagnostico_pil_n1_n2 import (
    _pilar_formato,
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


def test_pilar_formato_detects_retangular_and_l():
    rect = [(0, 0), (20, 0), (20, 60), (0, 60), (0, 0)]
    assert _pilar_formato(rect) == "Retangular"

    em_l = [(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40), (0, 0)]
    assert _pilar_formato(em_l) == "em L"


def _create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "id INTEGER PRIMARY KEY, obra_name TEXT, pavimento TEXT, classe TEXT, "
        "elemento_id TEXT, campos_json TEXT, status TEXT, confianca REAL)"
    )
    rows = [
        (1, "Obra_TESTE", "13_PAV", "PIL", "P1",
         json.dumps({"comprimento": 60, "largura": 20}), "draft", 0.9),
        (2, "Obra_TESTE", "13_PAV", "PIL", "P2",
         json.dumps({"comprimento": 60, "largura": 10}), "draft", 0.9),
        (3, "Obra_TESTE", "13_PAV", "PIL", "P3",
         json.dumps({"comprimento": 200, "largura": 5}), "draft", 0.8),
        (4, "Obra_TESTE", "13_PAV", "PIL", "P5",
         json.dumps({"comprimento": 20, "largura": 20}), "draft", 0.8),
        (5, "Obra_TESTE", "12_PAV", "PIL", "P999",
         json.dumps({"comprimento": 20, "largura": 20}), "draft", 0.8),
    ]
    connection.executemany(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?,?,?)", rows
    )
    connection.commit()
    connection.close()


def _pillar_entry(name: str, points: list, lado_b: str = "nulo") -> dict:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return {
        "key": name,
        "name": name,
        "classification": "MORRE",
        "points": points,
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "lado_A": "nulo",
        "lado_B": lado_b,
        "lado_C": "nulo",
        "lado_D": "nulo",
    }


def test_run_diagnostic_is_headless_versioned_and_emits_schema_v2(tmp_path: Path):
    rect = [(0, 0), (20, 0), (20, 60), (0, 60), (0, 0)]
    em_l = [(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40), (0, 0)]

    state = {
        "gerado_em": "2026-07-02T23:46:09",
        "obra": "Obra_TESTE",
        "pavimento": "TMC-EST-13P",
        "pilares": [
            _pillar_entry("P1", rect, lado_b="Laje: L301"),
            _pillar_entry("P2", rect),
            _pillar_entry("P3", em_l),
            _pillar_entry("P4", rect),  # sem ficha N2 correspondente
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
    assert report["run_id"] == "20260702_234609"
    assert report["resumo"] == {
        "itens": 5,
        "n1_itens": 4,
        "n2_itens": 4,
        "alertas": 3,
        "fora_de_escopo_nao_retangular": 1,
        "classificacoes": {
            "EXCELENTE": 1,
            "INDETERMINADO": 2,
            "RUIM": 2,
        },
    }

    items = {item["item"]: item for item in report["itens"]}

    # P1: bbox 20x60 == comprimento/largura 60/20 (eixo trocado) -> EXCELENTE
    assert items["P1"]["causa_raiz"] is None
    assert items["P1"]["status"] == "nao_reproduzido"
    assert items["P1"]["evidencia"]["classificacao"] == "EXCELENTE"
    assert items["P1"]["evidencia"]["formato"] == "Retangular"
    assert items["P1"]["evidencia"]["faces_preenchidas_n1"] == 1

    # P2: mesma bbox, N2 diverge (largura 10 vs 20) -> RUIM -> extractor_bug
    assert items["P2"]["causa_raiz"] == "extractor_bug"
    assert items["P2"]["evidencia"]["classificacao"] == "RUIM"
    assert items["P2"]["marcado_por"] == "auto"
    assert items["P2"]["concordancia"] == "pendente"

    # P3: formato "em L" com bbox propositalmente muito diferente do N2
    # (delta cairia em RUIM) -> mesmo assim NUNCA extractor_bug, porque a
    # comparação bbox vs comprimento/largura não é válida para não-retangular
    assert items["P3"]["evidencia"]["classificacao"] == "RUIM"
    assert items["P3"]["causa_raiz"] is None
    assert items["P3"]["evidencia"]["formato"] == "em L"
    assert "não-retangular" in items["P3"]["causa_descricao"]
    assert items["P3"]["confianca"] == 0.3

    # P4: só existe no N1 (sem ficha N2) -> schema_gap
    assert items["P4"]["causa_raiz"] == "schema_gap"
    assert "apenas no N1" in items["P4"]["causa_descricao"]

    # P5: só existe no N2 (sem estado N1) -> schema_gap
    assert items["P5"]["causa_raiz"] == "schema_gap"
    assert "apenas no N2" in items["P5"]["causa_descricao"]

    expected_dir = (
        tmp_path / "relatorios" / "Obra_TESTE" / "13_PAV" / "20260702_234609"
    )
    assert json_path == expected_dir / "diagnostico_pil_n1_n2.json"
    assert jsonl_path == expected_dir / "triagem_auto_pil.jsonl"
    assert json.loads(json_path.read_text(encoding="utf-8"))["resumo"]["alertas"] == 3

    jsonl_items = {
        json.loads(line)["item"]
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    }
    assert jsonl_items == {"P2", "P4", "P5"}
