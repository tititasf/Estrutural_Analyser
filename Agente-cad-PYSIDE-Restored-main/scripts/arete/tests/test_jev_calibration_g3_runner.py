"""G3 runner: caps, cache, technical errors, API payload isolation. No live Jev."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.catalog_v1 import catalog_hash
from scripts.arete.jev_calibration.factory import run_factory, write_dry_run
from scripts.arete.jev_calibration.hashing import sha256_file
from scripts.arete.jev_calibration.manifest import build_run_manifest
from scripts.arete.jev_calibration.n1_snapshot import N1Item, N1Snapshot
from scripts.arete.jev_calibration.runner import (
    api_payload, cache_key, run_batch, sanitize_error,
)
from scripts.arete.jev_calibration.schemas import JEV_MODEL
from scripts.arete.tests.test_jev_calibration_lv_fv import _beam_dxf, _fv_item, _lv_item


def _packed_dir(tmp_path: Path) -> tuple[Path, Path]:
    dxf = _beam_dxf(tmp_path)
    source = DxfParserCadSource(dxf)
    item = _lv_item()
    item.extras["cells"] = [item.extras["cells"][0]]
    snap = N1Snapshot(
        project_id="p", pavimento="14_PAV", source="fixture", fingerprint_sha256="fp",
        items={("LV", "V419"): item, ("FV", "V414"): _fv_item()},
    )
    audit = run_factory(
        snapshot=snap, source=source, classes=["LV"], items=["V419"],
        identity_base={"project_id": "p", "pavimento": "14_PAV"},
    )
    assert audit["packed"] >= 1
    manifest = build_run_manifest(
        project_id="p", obra=None, pavimento="14_PAV", dxf_path=dxf,
        n1_source="fixture", n1_fingerprint_sha256="fp",
        command=["pytest"], config={"mode": "g3-test"},
    )
    out = tmp_path / "dry"
    write_dry_run(out, audit, manifest)
    return out, dxf


def test_api_payload_omits_baseline_and_expected_choice(tmp_path: Path) -> None:
    out, _dxf = _packed_dir(tmp_path)
    request = json.loads(next((out / "jev_requests").glob("*.json")).read_text(encoding="utf-8"))
    payload = api_payload(request)
    blob = json.dumps(payload)
    assert "baseline_sa" not in payload
    assert "expected_choice" not in blob
    assert request["baseline_sa"]["value"]


def test_batch_dry_run_does_not_call_jev(tmp_path: Path) -> None:
    out, dxf = _packed_dir(tmp_path)
    called = []

    def boom(request):
        called.append(request)
        raise AssertionError("Jev must not run in dry-run")

    summary = run_batch(
        requests_dir=out / "jev_requests", source_dxf=dxf,
        out_dir=tmp_path / "batch_dry", execute=False, max_cases=2, max_calls=4,
        cache_dir=tmp_path / "cache", jev_run_fn=boom,
    )
    assert called == []
    assert summary["jev_api_called"] is False
    assert summary["calls_made"] == 0
    assert summary["eligible"] >= 1
    assert summary["results"][0]["status"] == "DRY_RUN_ELIGIBLE"
    assert summary["affects_qa_or_n1"] is False


def test_batch_execute_uses_cache_and_caps(tmp_path: Path) -> None:
    out, dxf = _packed_dir(tmp_path)
    fake_result = {
        "schema": "jev_sa_second_read_result/1",
        "results": [{"variant": "full", "choice": "INSUFFICIENT"}],
        "decision": "QA_REVIEW_ONLY",
    }
    calls = []

    def fake_run(request):
        calls.append(request)
        return fake_result

    first = run_batch(
        requests_dir=out / "jev_requests", source_dxf=dxf,
        out_dir=tmp_path / "batch1", execute=True, max_cases=2, max_calls=4,
        cache_dir=tmp_path / "cache", jev_run_fn=fake_run,
    )
    assert first["calls_made"] >= 1
    assert first["results"][0]["status"] == "RECORDED"
    assert len(calls) == 1
    second = run_batch(
        requests_dir=out / "jev_requests", source_dxf=dxf,
        out_dir=tmp_path / "batch2", execute=True, max_cases=2, max_calls=4,
        cache_dir=tmp_path / "cache", jev_run_fn=fake_run,
    )
    assert second["cache_hits"] == 1
    assert second["results"][0]["status"] == "CACHE_HIT"
    assert second["jev_api_called"] is False
    assert len(calls) == 1
    capped = run_batch(
        requests_dir=out / "jev_requests", source_dxf=dxf,
        out_dir=tmp_path / "batch_cap", execute=True, max_cases=1, max_calls=1,
        cache_dir=tmp_path / "cache_empty", jev_run_fn=fake_run,
    )
    assert capped["calls_made"] == 0
    assert any(r.get("status") == "SKIPPED_CAP" or r.get("reason") == "cap_max_cases_or_calls"
               for r in capped["results"] + capped["skipped_cap"])


def test_technical_error_does_not_affect_qa(tmp_path: Path) -> None:
    out, dxf = _packed_dir(tmp_path)

    def fail(request):
        raise RuntimeError("TYPESAFE_API_KEY absent from environment/.env")

    summary = run_batch(
        requests_dir=out / "jev_requests", source_dxf=dxf,
        out_dir=tmp_path / "batch_err", execute=True, max_cases=2, max_calls=4,
        cache_dir=tmp_path / "cache_err", jev_run_fn=fail,
    )
    assert summary["technical_errors"] == 1
    assert summary["results"][0]["status"] == "TECHNICAL_ERROR"
    assert summary["results"][0]["affects_qa_or_n1"] is False
    assert summary["calls_reserved"] >= 1
    assert summary["calls_completed"] == 0
    assert summary["calls_actual_unknown"] == summary["calls_reserved"]
    assert summary["jev_api_attempted"] is True
    sidecar = Path(summary["results"][0]["sidecar"])
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["affects_qa_or_n1"] is False
    assert payload["calls_actual_unknown"] is True
    assert "TYPESAFE_API_KEY" in payload["error"]


def test_throwing_runner_reserves_calls_and_blocks_next_case(tmp_path: Path) -> None:
    out, dxf = _packed_dir(tmp_path)
    src = next((out / "jev_requests").glob("*.json"))
    two = tmp_path / "two_requests"
    two.mkdir()
    (two / "01.json").write_bytes(src.read_bytes())
    (two / "02.json").write_bytes(src.read_bytes())
    calls = []

    def fail(request):
        calls.append(request)
        raise RuntimeError("remote failed after some calls")

    summary = run_batch(
        requests_dir=two, source_dxf=dxf,
        out_dir=tmp_path / "batch_throw_cap", execute=True, max_cases=2, max_calls=2,
        cache_dir=tmp_path / "cache_throw", jev_run_fn=fail,
    )
    assert len(calls) == 1
    assert summary["results"][0]["status"] == "TECHNICAL_ERROR"
    assert summary["results"][0]["calls_actual_unknown"] is True
    assert any(r.get("status") == "SKIPPED_CAP" for r in summary["results"][1:])
    assert summary["calls_reserved"] == summary["results"][0]["calls_planned"]
    assert summary["calls_completed"] == 0
    assert summary["calls_actual_unknown"] == summary["calls_reserved"]
    assert summary["calls_reserved"] <= 2
    assert summary["affects_qa_or_n1"] is False


def test_sanitize_error_redacts_key_material() -> None:
    err = sanitize_error(RuntimeError("api_key=sk-secret-value remaining"))
    assert "sk-secret-value" not in err
    assert "<redacted>" in err


def test_cache_key_changes_with_catalog_or_source(tmp_path: Path) -> None:
    out, dxf = _packed_dir(tmp_path)
    request = json.loads(next((out / "jev_requests").glob("*.json")).read_text(encoding="utf-8"))
    sha = sha256_file(dxf)
    a = cache_key(source_dxf_sha256=sha, request=request, model=JEV_MODEL,
                  catalog_sha256=catalog_hash())
    b = cache_key(source_dxf_sha256="0" * 64, request=request, model=JEV_MODEL,
                  catalog_sha256=catalog_hash())
    c = cache_key(source_dxf_sha256=sha, request=request, model=JEV_MODEL,
                  catalog_sha256="abc")
    assert a != b and a != c


def test_adjudicate_bbox_from_endpoints(tmp_path: Path) -> None:
    from scripts.arete.jev_calibration.adjudicate import cad_geometry_notes, evidence_bbox

    out, _dxf = _packed_dir(tmp_path)
    request = json.loads(next((out / "jev_requests").glob("*.json")).read_text(encoding="utf-8"))
    box = evidence_bbox(request["evidence"])
    assert box is not None
    assert box[2] > box[0] and box[3] > box[1]
    notes = cad_geometry_notes(request)
    assert notes["target_handle"]
    assert notes["target_points"]


def test_g1_consensus_rejected_without_two_independent_judgments() -> None:
    from scripts.arete.jev_calibration.adjudicate import assert_g1_consensus_allowed

    assert_g1_consensus_allowed({"consensus": False, "agents": ["only"]})
    with pytest.raises(ValueError, match="independent_reviews"):
        assert_g1_consensus_allowed({"consensus": True, "agents": ["a", "b"]})
    with pytest.raises(ValueError, match="distinct reviewing agents"):
        assert_g1_consensus_allowed({
            "consensus": True,
            "independent_reviews": [
                {"agent": "same", "judgment": "CORRETO"},
                {"agent": "same", "judgment": "CORRETO"},
            ],
        })
    with pytest.raises(ValueError, match="missing judgment"):
        assert_g1_consensus_allowed({
            "consensus": True,
            "independent_reviews": [
                {"agent": "a"},
                {"agent": "b", "judgment": "CORRETO"},
            ],
        })
    assert_g1_consensus_allowed({
        "consensus": True,
        "independent_reviews": [
            {"agent": "rev_a", "judgment": "CORRETO"},
            {"agent": "rev_b", "status": "CORRETO"},
        ],
    })


def test_write_g1_scaffold_rejects_names_only_consensus(tmp_path: Path, monkeypatch) -> None:
    from scripts.arete.jev_calibration import adjudicate as adj

    monkeypatch.setattr(adj, "render_pngs", lambda **kwargs: {"full_dxf_png": str(tmp_path / "x.png")})
    monkeypatch.setattr(adj, "sha256_file", lambda path: "a" * 64)
    request = {
        "case_id": "t|LV|V1|lv_cell|cell:1",
        "identity": {"classe": "LV", "item": "V1"},
        "evidence": {"target": {"handle": "AA", "points": [[0, 0], [1, 1]]}},
    }
    with pytest.raises(ValueError, match="independent_reviews"):
        adj.write_g1_scaffold(
            requests=[(tmp_path / "r.json", request)],
            dxf=tmp_path / "fase1.dxf",
            out_dir=tmp_path / "g1_bad",
            notes_by_case={request["case_id"]: {
                "consensus": True,
                "agents": ["g1_cad_png_agent", "imaginary_second"],
            }},
        )
    summary = adj.write_g1_scaffold(
        requests=[(tmp_path / "r.json", request)],
        dxf=tmp_path / "fase1.dxf",
        out_dir=tmp_path / "g1_ok",
        notes_by_case={request["case_id"]: {
            "status": "INDETERMINADO_POR_FONTE",
            "consensus": False,
            "agents": ["g1_cad_png_agent"],
            "independent_reviews": [
                {"agent": "g1_cad_png_agent", "judgment": "INDETERMINADO_POR_FONTE"},
            ],
        }},
    )
    assert summary["rows"][0]["consensus"] is False
    assert summary["rows"][0]["review_kind"] == "single_review"
