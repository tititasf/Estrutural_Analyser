"""LV/FV factory units, catalog v1 and controls. No Jev API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.catalog_v1 import CATALOG, catalog_hash, fv_question, lv_question
from scripts.arete.jev_calibration.leakage import scan_semantic_leakage
from scripts.arete.jev_calibration.factory import run_factory, write_dry_run
from scripts.arete.jev_calibration.filenames import assert_visible_request_files
from scripts.arete.jev_calibration.hashing import sha256_file
from scripts.arete.jev_calibration.manifest import build_run_manifest
from scripts.arete.jev_calibration.n1_snapshot import N1Item, N1Snapshot, attach_scope_audits, load_snapshot_from_estado
from scripts.arete.jev_calibration.schemas import FROZEN_VPS_14PAV, VPS_PARITY_DIR
from scripts.arete.jev_sa_second_read import validate_request

DXF_14 = VPS_PARITY_DIR / "torre_1.dxf"
ESTADO_14 = VPS_PARITY_DIR / "estado_14_PAV.json"
LV_AUDIT = VPS_PARITY_DIR / "lv_cell_geometry_audit_vps.json"
FV_AUDIT = VPS_PARITY_DIR / "fv_scope_audit_vps.json"


def _beam_dxf(tmp_path: Path) -> Path:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("V419", dxfattribs={"insert": (100, 50)})
    msp.add_text("V418", dxfattribs={"insert": (400, 50)})
    msp.add_lwpolyline([(90, 40), (110, 40), (110, 80), (90, 80), (90, 40)], close=True)
    msp.add_line((90, 40), (90, 80))
    msp.add_line((110, 40), (110, 80))
    msp.add_line((350, 200), (500, 200))
    msp.add_text("V414", dxfattribs={"insert": (20, 220)})
    msp.add_lwpolyline([(0, 200), (40, 200), (40, 240), (0, 240), (0, 200)], close=True)
    msp.add_lwpolyline([(50, 200), (90, 200), (90, 240), (50, 240), (50, 200)], close=True)
    msp.add_text("P10", dxfattribs={"insert": (20, 210)})
    msp.add_text("P99", dxfattribs={"insert": (800, 800)})
    path = tmp_path / "fase1_beams.dxf"
    doc.saveas(path)
    return path


def _lv_item() -> N1Item:
    fundo = [{"index": 1, "points": [[90, 40], [110, 40], [110, 80], [90, 80], [90, 40]]}]
    cells = [
        {"kind": "lateral_a_para", "side": "A", "behavior": "Para", "index": 1,
         "points": [[90, 40], [90, 80]], "width": 40},
        {"kind": "lateral_a_para", "side": "A", "behavior": "Para", "index": 2,
         "points": [[350, 200], [500, 200]], "width": 150},
    ]
    return N1Item(
        classe="LV", name="V419", points=[[90, 40], [90, 80]], sa_value=True, sa_field="lv_cell",
        snapshot_hash="lvhash",
        extras={"cells": cells, "fundo": fundo, "bbox": [90, 40, 110, 80], "center": [100, 60]},
    )


def _fv_item() -> N1Item:
    segs = [
        {"index": 1, "points": [[0, 200], [40, 200], [40, 240], [0, 240], [0, 200]], "statement": "8 interferencia(s) por pilar"},
        {"index": 2, "points": [[50, 200], [90, 200], [90, 240], [50, 240], [50, 200]], "statement": "8 interferencia(s) por pilar"},
    ]
    return N1Item(
        classe="FV", name="V414", points=segs[0]["points"], sa_value="8 interferencia(s) por pilar",
        sa_field="fv_segment_local_proof", snapshot_hash="fvhash",
        extras={"segments": segs, "repeated_claim": "8 interferencia(s) por pilar",
                "scope_audit": {"repeated_same_claim_across_segments": True,
                                "segments": [{"index": 1, "claimed_count": 8, "statement": segs[0]["statement"]},
                                             {"index": 2, "claimed_count": 8, "statement": segs[1]["statement"]}]},
                "bbox": [0, 200, 90, 240], "center": [45, 220]},
    )


def test_catalog_v1_has_all_classes_and_insufficient() -> None:
    assert set(CATALOG["classes"]) == {"PIL", "LAJ", "LV", "FV"}
    q = lv_question({"LINE_AB": "Source DXF LINE handle AB from [0, 0] to [0, 10]"})
    assert "INSUFFICIENT" in q["criteria"]
    assert "OWN_STRETCH" not in q["criteria"]
    assert not scan_semantic_leakage(q)
    fv = fv_question({"H1": "marker"}, allow_none=False)
    assert "INSUFFICIENT" in fv["criteria"] and "NONE" not in fv["criteria"]
    fv_none = fv_question({}, allow_none=True)
    assert "NONE" in fv_none["criteria"] and "INSUFFICIENT" in fv_none["criteria"]
    assert catalog_hash()


def test_lv_nearby_line_uses_source_endpoints_and_withdrawal_removes_it(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _lv_item()
    item.extras["cells"] = [item.extras["cells"][0]]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["packed"] == 1
    row = audit["cases"][0]
    ev = row["packet"]["evidence"]
    blob = json.dumps({"evidence": ev, "question": row["packet"]["question"]})
    assert "own_stretch" not in blob.lower()
    assert "associated_to_cell" not in blob
    assert not scan_semantic_leakage(row["jev_request"]["question"])
    assert not scan_semantic_leakage(ev)
    nearby_handles = {line["handle"] for line in ev["nearby_lines"]}
    assert nearby_handles
    assert ev["target"]["handle"] not in nearby_handles
    assert all(h in source.known_handles() for h in nearby_handles | {ev["target"]["handle"]})
    assert len(ev["target"]["points"]) >= 2
    for line in ev["nearby_lines"]:
        assert line["role"] == "nearby_parallel_line"
        assert line.get("closed") is not True
        assert len(line["points"]) >= 2
        assert line["provenance"]["n1_fundo_used"] is False
        assert line["provenance"]["source"] == "fase1_dxf"
        assert line["provenance"]["overlap"] >= 0.5
    for poly in ev.get("nearby_polygon_edges") or []:
        assert poly["role"] == "closed_polygon_edge"
        assert poly["closed"] is True
        assert poly["vertex_count"] >= 4
        assert len(poly["points"]) >= 3
        assert len(poly["bbox"]) == 4
        assert len(poly["selected_edge"]) == 2
        assert poly["handle"] not in nearby_handles
        assert f"LINE_{poly['handle']}" not in row["packet"]["question"]["criteria"]
    assert ev["relation_provenance"]["n1_fundo_used_for_relation"] is False
    line_ids = [k for k in row["packet"]["question"]["criteria"] if k.startswith("LINE_")]
    assert line_ids
    assert "OWN_STRETCH" not in row["packet"]["question"]["criteria"]
    alt = next(a for a in row["packet"]["included_entities"] if a.get("role") == "nearby_parallel_line")
    assert alt["handle"] in nearby_handles
    control = next(c for c in row["packet"]["controls"] if c["id"] == "nearby_lines_removed")
    assert control["evidence"]["nearby_lines"] == []
    assert nearby_handles.isdisjoint({row.get("handle") for row in control["evidence"].get("nearby_lines") or []})
    validate_request(row["jev_request"])


def test_lv_semantic_leak_tokens_are_rejected(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _lv_item()
    item.extras["cells"] = [item.extras["cells"][0]]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    request = audit["cases"][0]["jev_request"]
    leaked = dict(request)
    leaked["question"] = dict(request["question"])
    leaked["question"]["instructions"] = "Does this cell belong to this stretch of the beam's own stretch?"
    from scripts.arete.jev_calibration.leakage import validate_factory_request
    with pytest.raises(ValueError, match="semantic_leak"):
        validate_factory_request(leaked, source_dxf=source.dxf_path, known_handles=source.known_handles())


def test_lv_fundo_claim_without_source_parallel_is_needs_source(tmp_path: Path) -> None:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("V419", dxfattribs={"insert": (100, 50)})
    msp.add_line((90, 40), (90, 80))
    path = tmp_path / "fase1_cell_only.dxf"
    doc.saveas(path)
    source = DxfParserCadSource(path)
    item = _lv_item()
    item.extras["cells"] = [item.extras["cells"][0]]
    item.extras["fundo"] = [{"index": 1, "points": [[90, 40], [110, 40], [110, 80], [90, 80], [90, 40]]}]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["packed"] == 0
    assert audit["unpackable_reasons"].get("NEEDS_SOURCE") == 1


def test_lv_remote_cell_without_associated_stretch_is_needs_source(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _lv_item()
    item.extras["cells"] = [item.extras["cells"][1]]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["packed"] == 0
    assert audit["unpackable_reasons"].get("NEEDS_SOURCE") == 1


def test_lv_needs_source_without_dxf_cell_line(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _lv_item()
    item.extras["cells"] = [{"kind": "lateral_a_para", "index": 9, "points": [[1, 1], [2, 9]]}]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["unpackable_reasons"].get("NEEDS_SOURCE") == 1


def test_fv_segment_does_not_put_global_count_in_evidence(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("FV", "V414"): _fv_item()})
    audit = run_factory(snapshot=snap, source=source, classes=["FV"], items=["V414"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["packed"] >= 1
    for row in audit["cases"]:
        blob = json.dumps(row["packet"]["evidence"])
        assert "interferencia" not in blob
        target = row["packet"]["evidence"]["target"]
        assert target["role"] == "segment_contour"
        assert target.get("closed") is True
        assert len(target.get("points") or []) >= 4
        assert row["baseline"]["sa_value"]
        assert row["baseline"]["visible_to_jev"] is False
        validate_request(row["jev_request"])


def test_fv_without_per_segment_claim_is_not_packed(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _fv_item()
    item.extras["segments"] = [{"index": 1, "points": item.extras["segments"][0]["points"], "statement": ""}]
    item.extras["repeated_claim"] = None
    item.extras["scope_audit"] = {}
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("FV", "V414"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["FV"], items=["V414"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["packed"] == 0
    assert "no_concrete_per_segment_opening_claim" in json.dumps(audit["discards"])


def test_fv_none_requires_exhaustive_inventory_and_never_null_baseline(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("FV", "V414"): _fv_item()})
    audit = run_factory(snapshot=snap, source=source, classes=["FV"], items=["V414"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    for row in audit["cases"]:
        assert row["baseline"]["sa_value"] not in (None, "")
        ev = row["packet"]["evidence"]
        criteria = row["packet"]["question"]["criteria"]
        if "NONE" in criteria:
            assert ev.get("inventory", {}).get("exhaustive") is True
            assert ev.get("target", {}).get("points")
            assert ev.get("target", {}).get("closed") is True
            assert not ev.get("local_markers")
        else:
            assert ev.get("local_markers")
        assert "opening, support or special measure" not in row["packet"]["question"]["instructions"]


def test_write_dry_run_lv_filenames_are_windows_safe(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp",
                      items={("LV", "V419"): _lv_item(), ("FV", "V414"): _fv_item()})
    audit = run_factory(snapshot=snap, source=source, classes=["LV", "FV"], items=["V419", "V414"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    manifest = build_run_manifest(
        project_id="p", obra=None, pavimento="14_PAV", dxf_path=source.dxf_path,
        n1_source="fixture", n1_fingerprint_sha256="fp", command=["test"], config={},
    )
    write_dry_run(tmp_path / "out", audit, manifest)
    files = assert_visible_request_files(tmp_path / "out", audit["packed"])
    assert all(":" not in p.name and p.stat().st_size > 0 for p in files)
    assert (tmp_path / "out" / "catalog_v1.json").is_file()


@pytest.mark.skipif(not (DXF_14.is_file() and ESTADO_14.is_file()), reason="frozen 14_PAV source absent")
def test_smoke_14pav_lv_fv_frozen(tmp_path: Path) -> None:
    digest = sha256_file(DXF_14)
    source = DxfParserCadSource(DXF_14)
    snap = load_snapshot_from_estado(ESTADO_14, FROZEN_VPS_14PAV["project_id"], "14_PAV")
    attach_scope_audits(snap, lv_audit=LV_AUDIT if LV_AUDIT.is_file() else None,
                        fv_audit=FV_AUDIT if FV_AUDIT.is_file() else None)
    items = ["V419", "V420", "V411", "V414", "VF402"]
    audit = run_factory(
        snapshot=snap, source=source, classes=["LV", "FV"], items=items,
        identity_base={"project_id": FROZEN_VPS_14PAV["project_id"], "pavimento": "14_PAV"},
    )
    assert audit["scanned"] >= 1
    if digest != FROZEN_VPS_14PAV["source_dxf_sha256"]:
        pytest.skip("frozen DXF hash differs from recorded VPS identity")
    manifest = build_run_manifest(
        project_id=FROZEN_VPS_14PAV["project_id"], obra=None, pavimento="14_PAV",
        dxf_path=DXF_14, n1_source=snap.source, n1_fingerprint_sha256=snap.fingerprint_sha256,
        command=["pytest"], config={"mode": "smoke-lv-fv"}, estado_path=ESTADO_14,
    )
    write_dry_run(tmp_path / "smoke", audit, manifest)
    assert_visible_request_files(tmp_path / "smoke", audit["packed"])
    for row in audit["cases"]:
        validate_request(row["jev_request"])
        assert "interferencia" not in json.dumps(row["packet"]["evidence"])
        assert row["baseline"]["sa_value"] not in (None, "")
        if row["packet"]["identity"]["classe"] == "FV":
            if "NONE" in row["packet"]["question"]["criteria"]:
                assert row["packet"]["evidence"]["inventory"]["exhaustive"] is True
        blob = json.dumps(row["packet"]["evidence"]) + json.dumps(row["packet"]["question"])
        assert "own_stretch" not in blob.lower()
        if row["packet"]["identity"]["classe"] == "LV":
            for line in row["packet"]["evidence"]["nearby_lines"]:
                assert len(line.get("points") or []) >= 2
                assert line["provenance"]["n1_fundo_used"] is False
                assert line.get("closed") is not True
                assert line["role"] == "nearby_parallel_line"
            for poly in row["packet"]["evidence"].get("nearby_polygon_edges") or []:
                assert poly["role"] == "closed_polygon_edge"
                assert poly["closed"] is True
                assert len(poly.get("points") or []) >= 3
                assert len(poly.get("bbox") or []) == 4
                assert f"LINE_{poly['handle']}" not in row["packet"]["question"]["criteria"]
            if row["packet"]["identity"]["item"] == "V411":
                nearby = {line["handle"] for line in row["packet"]["evidence"]["nearby_lines"]}
                assert "315" in nearby
                criteria = row["packet"]["question"]["criteria"]
                assert "LINE_315" in criteria
                assert "LINE_9C0" not in criteria
                assert "LINE_C59" not in criteria
                polys = row["packet"]["evidence"].get("nearby_polygon_edges") or []
                assert any(p["handle"] in {"9C0", "C59"} for p in polys)
                for poly in polys:
                    if poly["handle"] in {"9C0", "C59"}:
                        assert poly["closed"] is True
                        assert poly["vertex_count"] >= 4
                        xs = {round(pt[0], 3) for pt in poly["points"]}
                        ys = {round(pt[1], 3) for pt in poly["points"]}
                        assert 2300.59 in xs and 2118.09 in xs
                        assert 2484.025 in ys and 2696.025 in ys
                        dups = set(poly.get("duplicate_handles") or [])
                        assert ({"9C0", "C59"} - {poly["handle"]}) <= dups or dups
                control = next(c for c in row["packet"]["controls"] if c["id"] == "nearby_lines_removed")
                blob = json.dumps(control["evidence"])
                assert '"handle": "315"' not in blob
                assert "9C0" not in blob and "C59" not in blob
                assert control["evidence"]["nearby_lines"] == []
                assert control["evidence"]["nearby_polygon_edges"] == []


def _v411_shape_dxf(tmp_path: Path) -> Path:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("V411", dxfattribs={"insert": (2296.84, 2598.025), "layer": "4"})
    msp.add_text("V403", dxfattribs={"insert": (2319.079, 2605.775), "layer": "4"})
    msp.add_lwpolyline([(2314.59, 2602.025), (2314.59, 2754.025)], dxfattribs={"layer": "3"})
    msp.add_lwpolyline([(2300.59, 2754.025), (2300.59, 2583.025)], dxfattribs={"layer": "3"})
    slab = [(2300.59, 2484.025), (2118.09, 2484.025), (2118.09, 2696.025), (2300.59, 2696.025)]
    msp.add_lwpolyline(slab, close=True, dxfattribs={"layer": "3"})
    msp.add_lwpolyline(list(reversed(slab)), close=True, dxfattribs={"layer": "9"})
    path = tmp_path / "fase1_v411_shape.dxf"
    doc.saveas(path)
    return path


def test_v411_shape_closed_slab_is_not_a_wall_option(tmp_path: Path) -> None:
    source = DxfParserCadSource(_v411_shape_dxf(tmp_path))
    item = N1Item(
        classe="LV", name="V411", points=[[2314.59, 2602.025], [2314.59, 2754.025]],
        sa_value=True, sa_field="lv_cell", snapshot_hash="v411hash",
        extras={
            "cells": [{
                "kind": "lateral_b_para", "side": "B", "behavior": "Para", "index": 1,
                "points": [[2314.59, 2602.025], [2314.59, 2754.025]], "width": 14,
            }],
            "fundo": [{"index": 1, "points": [
                [2300.59, 2583.025], [2314.59, 2583.025],
                [2314.59, 2754.025], [2300.59, 2754.025], [2300.59, 2583.025],
            ]}],
        },
    )
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V411"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V411"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["packed"] == 1
    row = audit["cases"][0]
    ev = row["packet"]["evidence"]
    walls = ev["nearby_lines"]
    polys = ev["nearby_polygon_edges"]
    assert len(walls) == 1
    wall = walls[0]
    assert wall["closed"] is False
    assert wall["vertex_count"] == 2
    assert wall["role"] == "nearby_parallel_line"
    assert wall["points"] == [[2300.59, 2754.025], [2300.59, 2583.025]] or \
        wall["selected_edge"][0][0] == 2300.59
    assert len(polys) == 1
    poly = polys[0]
    assert poly["role"] == "closed_polygon_edge"
    assert poly["closed"] is True
    assert poly["vertex_count"] >= 4
    assert len(poly["points"]) >= 4
    assert poly["bbox"] == [2118.09, 2484.025, 2300.59, 2696.025]
    assert poly["selected_edge"][0][0] == 2300.59
    assert poly["selected_edge"][1][0] == 2300.59
    assert poly["duplicate_handles"]
    assert poly["duplicate_layers"]
    criteria = row["packet"]["question"]["criteria"]
    assert f"LINE_{wall['handle']}" in criteria
    assert f"LINE_{poly['handle']}" not in criteria
    for dup in poly["duplicate_handles"]:
        assert f"LINE_{dup}" not in criteria
    control = next(c for c in row["packet"]["controls"] if c["id"] == "nearby_lines_removed")
    assert control["evidence"]["nearby_lines"] == []
    assert control["evidence"]["nearby_polygon_edges"] == []
    blob = json.dumps(control["evidence"])
    assert f'"handle": "{wall["handle"]}"' not in blob
    assert f'"handle": "{poly["handle"]}"' not in blob
    for dup in poly["duplicate_handles"]:
        assert f'"handle": "{dup}"' not in blob
    validate_request(row["jev_request"])
