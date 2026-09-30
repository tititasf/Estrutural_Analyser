"""Contract checks for the optional Jev request boundary; no API calls."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts" / "arete" / "jev_sa_second_read.py"
EXAMPLE = ROOT / "scripts" / "arete" / "examples" / "jev_sa_second_read_l410.json"
SPEC = importlib.util.spec_from_file_location("jev_sa_second_read", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _request() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_keeps_baseline_outside_evidence_and_has_control() -> None:
    summary = MODULE.validate_request(_request())
    assert summary["identity"]["item"] == "L410"
    assert summary["controls"] == 1
    assert summary["max_state_bytes"] < 1000


def test_rejects_baseline_leakage_into_jev_state() -> None:
    request = copy.deepcopy(_request())
    request["evidence"]["baseline_sa"] = request["baseline_sa"]
    with pytest.raises(ValueError, match="outside Jev evidence"):
        MODULE.validate_request(request)


def test_rejects_uncontrolled_or_oversize_request() -> None:
    request = _request()
    request["controls"] = []
    with pytest.raises(ValueError, match="controls"):
        MODULE.validate_request(request)
    request = _request()
    request["evidence"]["full_dxf"] = "x" * 16000
    with pytest.raises(ValueError, match="split by item"):
        MODULE.validate_request(request)


def test_companion_noul_and_score_contract() -> None:
    request = _request()
    request["companion_questions"] = {
        "local_marker_present": {
            "type": "noul", "instructions": "Is there a direct marker in the target region?",
            "criteria": {"true": "Direct source marker in target region.",
                         "false": "No direct marker in target region."},
        },
        "evidence_grade": {
            "type": "score", "instructions": "Rate support for the selected region.",
            "criteria": ["No direct source marker", "A marker exists but region is ambiguous",
                         "Direct marker and region agree"],
        },
    }
    assert MODULE.validate_request(request)["companions"] == ["local_marker_present", "evidence_grade"]
    request["companion_questions"]["evidence_grade"]["criteria"] = ["one level"]
    with pytest.raises(ValueError, match="ordered"):
        MODULE.validate_request(request)


def test_source_dxf_hash_is_verified(tmp_path: Path) -> None:
    path = tmp_path / "source.dxf"
    path.write_bytes(b"0\nEOF\n")
    MODULE.verify_source_dxf(path, hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="hash does not match"):
        MODULE.verify_source_dxf(path, "0" * 64)
