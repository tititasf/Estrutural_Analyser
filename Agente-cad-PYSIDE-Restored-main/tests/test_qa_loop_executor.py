from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.arete.qa_loop_executor import (
    advance,
    ask_question,
    compatible_state,
    create_state,
    list_states,
    load_state,
    record,
    record_cycle_phase,
    teach,
)


def _state(tmp_path: Path):
    return create_state(
        project_id="project",
        classe="PIL",
        items=["P35"],
        level="N1",
        pav="13_PAV",
        part=None,
        variant=None,
        max_cycles=4,
        root=tmp_path,
    )


def test_loop_state_is_persistent_and_fix_invalidates_automatic_checks(tmp_path: Path):
    state = _state(tmp_path)
    assert state["authority"] == "validation_ready"
    assert (tmp_path / state["run_id"] / "session_metrics.json").is_file()
    state["tasks"]["evidence_review"] = {"status": "COMPLETE"}
    state["tasks"]["class_coverage"] = {"status": "COMPLETE"}
    fixed = record(
        tmp_path,
        state,
        kind="fix",
        result="PASS",
        message="resolver por topologia, sem hardcode",
        evidence=["tests/test_rule.py"],
    )
    restored = load_state(tmp_path, fixed["run_id"])
    assert restored["status"] == "ACTIVE"
    assert restored["tasks"]["evidence_review"]["status"] == "PENDING"
    assert restored["tasks"]["class_coverage"]["status"] == "PENDING"
    assert restored.get("pending_regen_after_fix") is True
    assert restored["cycle_phases"]["fix"] >= 1
    assert (tmp_path / fixed["run_id"] / "events.jsonl").is_file()
    assert (tmp_path / fixed["run_id"] / "RESUME.md").is_file()
    metrics = json.loads((tmp_path / fixed["run_id"] / "session_metrics.json").read_text(encoding="utf-8"))
    assert metrics["schema"] == "arete.qa_session_metrics/v1"
    assert metrics["authority"] == "validation_ready"
    assert metrics.get("cycle_efficiency", {}).get("schema") == "arete.qa_cycle_efficiency/v1"
    assert metrics["cycle_efficiency"]["phases"]["fix"] >= 1


def test_record_visual_and_teach_auto_note_cycle_phases(tmp_path: Path):
    state = _state(tmp_path)
    visual = record(
        tmp_path,
        state,
        kind="visual",
        result="FAIL",
        message="cota desalinhada",
        evidence=["n2.png", "n4.png"],
    )
    assert visual["cycle_phases"]["visual"] >= 1
    assert visual["status"] == "NEEDS_IMPLEMENTATION"
    taught = teach(
        tmp_path,
        load_state(tmp_path, visual["run_id"]),
        family="faces",
        field="dim",
        rule="aresta do contorno prova dim em L/U",
        examples=["P99 20/40"],
        exceptions=[],
        evidence=["dossie.md"],
    )
    assert taught["cycle_phases"]["train"] >= 1
    resume = (tmp_path / taught["run_id"] / "RESUME.md").read_text(encoding="utf-8")
    assert "Eficiência do ciclo" in resume
    metrics = json.loads((tmp_path / taught["run_id"] / "session_metrics.json").read_text(encoding="utf-8"))
    assert metrics["cycle_efficiency"]["phases"]["visual"] >= 1
    assert metrics["cycle_efficiency"]["phases"]["train"] >= 1


def test_manual_record_cycle_still_works(tmp_path: Path):
    state = _state(tmp_path)
    updated = record_cycle_phase(
        tmp_path, state, phase="validate", result="PASS", message="probe ok",
    )
    assert updated["cycle_phases"]["validate"] == 1
    events = (tmp_path / updated["run_id"] / "events.jsonl").read_text(encoding="utf-8")
    assert "cycle_phase" in events


def test_teaching_requires_reusable_rule_and_becomes_unpromoted_t1_candidate(tmp_path: Path):
    state = _state(tmp_path)
    taught = teach(
        tmp_path,
        state,
        family="faces",
        field="viga_passante",
        rule="usar o segmento que toca a face, não o texto mais próximo",
        examples=["P35 face D: V328 passa; V327 não toca"],
        exceptions=["nome ausente exige contexto N1 distante"],
        evidence=["P35.html"],
    )
    artifact = Path(taught["teachings"][0])
    assert artifact.is_file()
    assert taught["status"] == "NEEDS_IMPLEMENTATION"
    assert "Não promover" in artifact.read_text(encoding="utf-8") or "requires_human_approval" in artifact.read_text(encoding="utf-8")


def test_promotion_fails_closed_without_explicit_evidence(tmp_path: Path):
    state = _state(tmp_path)
    with pytest.raises(ValueError):
        record(tmp_path, state, kind="promotion", result="PASS", message="", evidence=[])


def test_structured_question_tells_owner_how_to_teach_without_asking_for_diagnosis(tmp_path: Path):
    state = _state(tmp_path)
    waiting = ask_question(
        tmp_path,
        state,
        gate="PIL/N1/face_D",
        observation="duas identidades competem pelo mesmo segmento",
        attempts=["rastreio pelo bbox", "rastreio pelo fundo FV"],
        rejected=["texto mais próximo"],
        alternatives=["priorizar contato", "priorizar continuidade"],
        needed="qual regra universal desempata contato e continuidade?",
        evidence=["probe.json"],
    )
    assert waiting["status"] == "WAITING_HUMAN_RULE"
    question_path = next((tmp_path / waiting["run_id"] / "questions").glob("*.json"))
    content = question_path.read_text(encoding="utf-8")
    assert "positive_example" in content
    assert "counterexample_or_exception" in content


def test_resume_while_waiting_does_not_spend_cycle_or_repeat_probe(tmp_path: Path):
    state = _state(tmp_path)
    state["status"] = "WAITING_HUMAN_VISUAL"
    state["cycle"] = 2
    resumed = advance(tmp_path, state, db=tmp_path / "missing.vision")
    assert resumed["cycle"] == 2
    assert resumed["status"] == "WAITING_HUMAN_VISUAL"


def test_active_run_can_be_discovered_and_reused_by_exact_scope(tmp_path: Path):
    state = _state(tmp_path)
    assert list_states(tmp_path, classe="PIL", item="P35")[0]["run_id"] == state["run_id"]
    reused = compatible_state(
        tmp_path,
        project_id="project",
        classe="PIL",
        items=["P35"],
        level="N1",
    )
    assert reused and reused["run_id"] == state["run_id"]
    assert compatible_state(
        tmp_path,
        project_id="project",
        classe="PIL",
        items=["P1"],
        level="N1",
    ) is None
