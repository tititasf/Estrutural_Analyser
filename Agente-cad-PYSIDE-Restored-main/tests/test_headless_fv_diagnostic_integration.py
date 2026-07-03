from pathlib import Path

from scripts.arete import diagnostico_fv_n1_n2
from scripts.arete.headless_sa_analise import _run_fv_diagnostic_postprocess


def test_fv_diagnostic_postprocess_returns_paths(monkeypatch, tmp_path: Path):
    expected_json = tmp_path / "diagnostico.json"
    expected_jsonl = tmp_path / "triagem.jsonl"
    calls = []

    def fake_run_diagnostic(**kwargs):
        calls.append(kwargs)
        return ({"resumo": {"alertas": 2}}, expected_json, expected_jsonl)

    monkeypatch.setattr(
        diagnostico_fv_n1_n2, "run_diagnostic", fake_run_diagnostic
    )
    result = _run_fv_diagnostic_postprocess(
        obra="Obra_TESTE",
        pavimento="13_PAV",
        state_path="estado.json",
        db_path="project_data.vision",
    )

    assert result == {
        "status": "ok",
        "json_path": str(expected_json),
        "jsonl_path": str(expected_jsonl),
        "resumo": {"alertas": 2},
    }
    assert calls == [{
        "obra": "Obra_TESTE",
        "pavimento": "13_PAV",
        "state_path": "estado.json",
        "db_path": "project_data.vision",
    }]


def test_fv_diagnostic_postprocess_is_non_blocking(monkeypatch):
    def fail_diagnostic(**kwargs):
        raise RuntimeError("falha controlada")

    monkeypatch.setattr(
        diagnostico_fv_n1_n2, "run_diagnostic", fail_diagnostic
    )
    result = _run_fv_diagnostic_postprocess(
        obra="Obra_TESTE",
        pavimento="13_PAV",
        state_path="estado.json",
        db_path="project_data.vision",
    )

    assert result == {"status": "erro", "erro": "falha controlada"}
