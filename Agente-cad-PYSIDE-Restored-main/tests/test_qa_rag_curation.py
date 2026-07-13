"""Contrato: QA só cria candidatos T1, nunca promove memória sozinho."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
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


def test_promote_candidates_is_idempotent_and_records_t1(tmp_path: Path) -> None:
    db = tmp_path / "rag.vision"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE semantic_rag_kb (id INTEGER PRIMARY KEY, classe TEXT, regra_semantica TEXT, obra_contexto TEXT, confianca REAL);
        CREATE TABLE human_event_logs (
            log_id TEXT PRIMARY KEY, timestamp TEXT, obra_id TEXT, classe TEXT, item_id TEXT, fase_editada TEXT,
            ui_context TEXT, estado_anterior_json TEXT, estado_novo_json TEXT, campos_alterados TEXT,
            processado_por_rag INTEGER, event_kind TEXT, status TEXT, tier TEXT, validation_origin TEXT,
            user_reason TEXT, source_agent TEXT, actor_id TEXT, session_id TEXT, idempotency_key TEXT,
            approved_at TEXT, approved_by TEXT, updated_at TEXT
        );
    """)
    conn.close()
    candidates = [{
        "candidate_id": "qa-rag-1", "project_id": "p1", "classe": "LAJ", "field_id": "laje_dim",
        "items": ["L318"], "source_run": "run", "decision_ids": ["d1"], "evidence": [],
    }]
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(candidates), encoding="utf-8")

    first = curation.promote_candidates(db, path, approved_by="dono")
    second = curation.promote_candidates(db, path, approved_by="dono")

    assert first == {"selected": 1, "inserted": 1, "already_promoted": 0}
    assert second == {"selected": 1, "inserted": 0, "already_promoted": 1}
    conn = sqlite3.connect(db)
    rule = json.loads(conn.execute("SELECT regra_semantica FROM semantic_rag_kb").fetchone()[0])
    assert rule["tier"] == "T1"
    assert conn.execute("SELECT tier FROM human_event_logs").fetchone()[0] == "T1"
