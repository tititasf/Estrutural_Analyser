"""Na cadeia, o gate CAD roda em fundo e a cadeia espera por ele [2026-10-12]."""

import threading
from pathlib import Path

from portal.app import pipeline_runner, qa_cad_gate_run


def test_gate_fora_da_cadeia_roda_na_hora(monkeypatch, tmp_path):
    monkeypatch.setattr(qa_cad_gate_run, "best_effort", lambda *a, **k: tmp_path / "13_PAV.json")
    assert pipeline_runner._gate_cad(None, "obra", "13_PAV") == tmp_path / "13_PAV.json"


def test_gate_na_cadeia_roda_em_fundo_e_registra_no_log(monkeypatch, tmp_path):
    liberar = threading.Event()
    chamadas = []

    def gate(obra_dir, pav, secao=None, item_names=None):
        liberar.wait(5)
        chamadas.append((obra_dir, pav, secao))
        return Path(tmp_path / "13_PAV.json")

    monkeypatch.setattr(qa_cad_gate_run, "best_effort", gate)
    log = tmp_path / "pav.log"
    log.write_text("SA\n", encoding="utf-8")
    with pipeline_runner.gate_cad_em_fundo():
        assert pipeline_runner._gate_cad(log, "obra", "13_PAV", secao=None) is None
        assert chamadas == []  # a cadeia segue para o N5 sem esperar
        liberar.set()
    assert chamadas == [("obra", "13_PAV", None)]
    texto = log.read_text(encoding="utf-8")
    assert "GATE CAD pós-SA: 13_PAV.json" in texto
    assert "gate_cad (em paralelo ao N5)" in texto
