"""QA/Jev join must fail closed on source and N1 snapshot changes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.arete.jev_qa_bridge import summarize_result, validate_packets, write_advice


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "jev_sa_second_read_l410.json"


def _fixtures(tmp_path: Path):
    source = tmp_path / "source.dxf"
    source.write_bytes(b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
    request = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    request["use_context"] = "QA_B3"
    request["identity"]["source_dxf_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["qa_snapshot_sha256"] = "snapshot-1"
    path = tmp_path / "question.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    manifest = {"project_id": request["identity"]["project_id"],
                "snapshots": {"L410": {"classe": "LAJ", "hash": "snapshot-1"}}}
    decisions = [SimpleNamespace(classe="LAJ", item="L410", field_id="laje_nivel")]
    return source, path, manifest, decisions


def test_validated_advice_is_separate_from_qa_score(tmp_path: Path) -> None:
    source, path, manifest, decisions = _fixtures(tmp_path)
    prepared = validate_packets([path], source, manifest, decisions)
    rows = write_advice(tmp_path, prepared, execute=False)
    assert rows[0]["status"] == "VALIDATED_ONLY"
    assert rows[0]["changes_qa_score"] is False
    assert (tmp_path / "jev_consultas.jsonl").exists()


def test_changed_dxf_or_snapshot_rejected(tmp_path: Path) -> None:
    source, path, manifest, decisions = _fixtures(tmp_path)
    source.write_bytes(source.read_bytes() + b"change")
    with pytest.raises(ValueError, match="source DXF hash"):
        validate_packets([path], source, manifest, decisions)
    source, path, manifest, decisions = _fixtures(tmp_path)
    manifest["snapshots"]["L410"]["hash"] = "snapshot-2"
    with pytest.raises(ValueError, match="qa_snapshot_sha256"):
        validate_packets([path], source, manifest, decisions)


def test_field_outside_review_rejected(tmp_path: Path) -> None:
    source, path, manifest, decisions = _fixtures(tmp_path)
    decisions[0].field_id = "other_field"
    with pytest.raises(ValueError, match="outside this QA"):
        validate_packets([path], source, manifest, decisions)


def test_choice_presence_contradiction_routes_to_review() -> None:
    request = {"presence_question_id": "marker_present"}
    result = {"results": [
        {"variant": "full", "choice": "candidate_a",
         "companion_answers": {"marker_present": {"noul": 0.36}}},
        {"variant": "removed", "control_matches_expectation": True},
    ]}
    assert summarize_result(request, result)["status"] == "CONTRADICTORY_SIGNALS"


def test_class_keyed_snapshot_wins_when_item_names_overlap(tmp_path: Path) -> None:
    source, path, manifest, decisions = _fixtures(tmp_path)
    manifest["snapshots"]["L410"] = {"classe": "FV", "hash": "other-class"}
    manifest["snapshots_by_class"] = {"LAJ:L410": {"hash": "snapshot-1"}}
    assert len(validate_packets([path], source, manifest, decisions)) == 1
