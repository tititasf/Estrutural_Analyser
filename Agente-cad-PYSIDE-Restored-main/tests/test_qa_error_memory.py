from __future__ import annotations

from pathlib import Path

from scripts.arete.qa_error_memory import append_errors, field_pattern, recurrence_report


def test_field_pattern_generalizes_segments_and_faces():
    assert field_pattern("viga_fundo_seg_12_dim") == "viga_fundo_seg_N_dim"
    assert "p_sF_" in field_pattern("p_sD_l1_n")


def test_append_and_recurrence(tmp_path: Path):
    ledger = tmp_path / "errors.jsonl"
    findings = [
        {"classe": "FV", "item": "V1", "field_id": "viga_fundo_seg_1_dim", "code": "DIM", "message": "a"},
        {"classe": "FV", "item": "V2", "field_id": "viga_fundo_seg_3_dim", "code": "DIM", "message": "b"},
        {"classe": "LV", "item": "V1", "field_id": "lv_contract_PARA_A", "code": "CTR", "message": "c"},
    ]
    assert append_errors(findings, ledger=ledger, run_id="r1", project_id="p") == 3
    report = recurrence_report(ledger, min_count=2)
    assert report["total_entries"] == 3
    assert any(row["count"] >= 2 and row["familia"] == "fv_segments" for row in report["recurring"])
