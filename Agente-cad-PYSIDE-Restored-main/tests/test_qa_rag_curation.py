"""Contrato: QA só cria candidatos T1, nunca promove memória sozinho."""
from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE = Path(__file__).parents[1] / "scripts" / "arete" / "qa_rag_curation.py"
SPEC = importlib.util.spec_from_file_location("qa_rag_curation", MODULE)
assert SPEC and SPEC.loader
curation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(curation)


def test_build_candidates_groups_only_high_nonhuman_decisions() -> None:
    manifest = {"run_id": "qa_laj_test", "project_id": "project-1"}
    decisions = [
        {"classe": "LAJ", "field_id": "laje_visao_corte", "item": "L318", "decision": "CORRIGIR", "confidence": "high", "decision_id": "d1", "evidence": [{"kind": "db"}]},
        {"classe": "LAJ", "field_id": "laje_visao_corte", "item": "L319", "decision": "CONFIRMAR", "confidence": "high", "decision_id": "d2", "evidence": []},
        {"classe": "LAJ", "field_id": "laje_visao_corte", "item": "L320", "decision": "CONFIRMAR", "confidence": "high", "decision_id": "d4", "operations": [{"op": "remove_link"}], "evidence": []},
        {"classe": "LAJ", "field_id": "laje_dim", "item": "L318", "decision": "PERGUNTAR", "confidence": "medium", "decision_id": "d3", "evidence": []},
    ]

    candidates = curation.build_candidates(manifest, decisions)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["status"] == "T1_CANDIDATE_REQUIRES_HUMAN_APPROVAL"
    assert candidate["tier_candidate"] == "T1"
    assert candidate["items"] == ["L319"]
    assert candidate["decision_ids"] == ["d2"]
