"""Catalog v2 LV face×behavior packets. v1 regression stays in test_jev_calibration_lv_fv.py."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.catalog_v1 import CATALOG, catalog_hash
from scripts.arete.jev_calibration.adapters_lv_v2 import classify_relevance
from scripts.arete.jev_calibration.catalog_v2 import CATALOG_V2, CATALOG_V2_REVISION, lv_v2_question
from scripts.arete.jev_calibration.factory import run_factory
from scripts.arete.jev_calibration.hashing import sha256_file
from scripts.arete.jev_calibration.leakage import scan_semantic_leakage, validate_factory_request
from scripts.arete.jev_calibration.n1_snapshot import N1Item, N1Snapshot, attach_scope_audits, load_snapshot_from_estado
from scripts.arete.jev_calibration.schemas import FROZEN_VPS_14PAV, VPS_PARITY_DIR
from scripts.arete.jev_sa_second_read import validate_request
from scripts.arete.tests.test_jev_calibration_lv_fv import _beam_dxf, _lv_item

DXF_14 = VPS_PARITY_DIR / "torre_1.dxf"
ESTADO_14 = VPS_PARITY_DIR / "estado_14_PAV.json"
LV_AUDIT = VPS_PARITY_DIR / "lv_cell_geometry_audit_vps.json"


def _conflict_dxf(tmp_path: Path) -> Path:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("V500", dxfattribs={"insert": (88, 50), "layer": "4"})
    msp.add_text("V499", dxfattribs={"insert": (200, 50), "layer": "4"})
    msp.add_lwpolyline([(90, 40), (90, 80)], dxfattribs={"layer": "3"})
    msp.add_lwpolyline([(110, 40), (110, 80)], dxfattribs={"layer": "3"})
    msp.add_lwpolyline(
        [(90, 80), (110, 80), (110, 96), (90, 96), (90, 80)],
        close=True, dxfattribs={"layer": "7"},
    )
    msp.add_line((90, 8), (90, 34), dxfattribs={"layer": "9"})
    path = tmp_path / "fase1_lv_v2.dxf"
    doc.saveas(path)
    return path


def _conflict_item() -> N1Item:
    return N1Item(
        classe="LV", name="V500", points=[[90, 40], [90, 80]],
        sa_value="lateral_a_para", sa_field="lv_cell", snapshot_hash="v500hash",
        extras={
            "cells": [
                {"kind": "lateral_b_passa", "side": "B", "behavior": "Passa", "index": 1,
                 "points": [[90, 40], [90, 80]]},
            ],
            "fundo": [{"index": 1, "points": [[90, 40], [110, 40], [110, 80], [90, 80], [90, 40]]}],
        },
    )


def test_catalog_v2_is_distinct_from_v1() -> None:
    assert CATALOG["revision"] != CATALOG_V2["revision"]
    assert CATALOG_V2["revision"] == CATALOG_V2_REVISION
    q = lv_v2_question({"A_PARA": "FACE_A PARA", "A_PASSA": "FACE_A PASSA"})
    assert "INSUFFICIENT" in q["criteria"]
    assert "A_PARA" in q["criteria"] and "A_PASSA" in q["criteria"]
    assert "LINE_" not in json.dumps(q)
    assert not scan_semantic_leakage(q)
    assert catalog_hash()


def test_v1_factory_default_still_packs_parallel_line(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _lv_item()
    item.extras["cells"] = [item.extras["cells"][0]]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"})
    assert audit["catalog"] == "v1"
    assert audit["packed"] == 1
    assert audit["cases"][0]["catalog_id"] == "lv_cell_nearby_parallel_line"
    assert "LINE_" in json.dumps(audit["cases"][0]["packet"]["question"]["criteria"])


def test_v2_mixed_endpoint_para_passa_is_not_n1_decision(tmp_path: Path) -> None:
    """Gap at one end + colinear continuation at the other are two encounters."""
    source = DxfParserCadSource(_conflict_dxf(tmp_path))
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V500"): _conflict_item()})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V500"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"}, catalog="v2")
    assert audit["packed"] == 0
    assert audit["cases"] == []
    rows = [row for row in audit["cell_audits"] if row.get("handle")]
    assert rows
    assert all(row["n1_relevance"] != "N1_DECISION_RELEVANT" for row in rows)
    mixed = [row for row in rows if row.get("why") == "para_and_passa_on_distinct_encounters"]
    assert mixed
    assert mixed[0]["source_outcomes"] == ["A_PARA", "A_PASSA"]
    blob = json.dumps(audit["cell_audits"])
    assert "lateral_b_passa" not in blob
    assert "own_stretch" not in blob.lower()


def test_classify_relevance_split_encounters_fail_closed() -> None:
    wall = {"match": "exact", "unique": True}
    flags = [
        {"at": [90.0, 80.0], "para": True, "passa": False},
        {"at": [90.0, 40.0], "para": False, "passa": True},
    ]
    relevance, why = classify_relevance(
        wall=wall, face="A", para=True, passa=True, label_ok=True,
        endpoint_flags=flags,
    )
    assert relevance == "SOURCE_INSUFFICIENT"
    assert why == "para_and_passa_on_distinct_encounters"


def test_classify_relevance_same_encounter_gap_and_continuation_fail_closed() -> None:
    wall = {"match": "exact", "unique": True}
    flags = [
        {"at": [90.0, 80.0], "para": True, "passa": True},
        {"at": [90.0, 40.0], "para": False, "passa": False},
    ]
    relevance, why = classify_relevance(
        wall=wall, face="B", para=True, passa=True, label_ok=True,
        endpoint_flags=flags,
    )
    assert relevance == "SOURCE_INSUFFICIENT"
    assert why == "para_and_passa_not_exclusive_at_one_encounter"


def test_v2_missing_source_wall_is_source_insufficient(tmp_path: Path) -> None:
    source = DxfParserCadSource(_beam_dxf(tmp_path))
    item = _lv_item()
    item.extras["cells"] = [{"kind": "lateral_a_para", "index": 9, "points": [[1, 1], [2, 9]]}]
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"}, catalog="v2")
    assert audit["packed"] == 0
    assert audit["unpackable_reasons"].get("NEEDS_SOURCE")
    rel = {row.get("n1_relevance") for row in audit["unpackable_rows"]}
    assert "SOURCE_INSUFFICIENT" in rel


def test_v2_does_not_use_n1_kind_to_prune(tmp_path: Path) -> None:
    source = DxfParserCadSource(_conflict_dxf(tmp_path))
    item = _conflict_item()
    item.extras["cells"][0]["kind"] = "lateral_b_para"
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V500"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V500"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"}, catalog="v2")
    assert audit["packed"] == 0
    outcomes = []
    for row in audit["cell_audits"]:
        outcomes.extend(row.get("source_outcomes") or [])
    assert "A_PARA" in outcomes and "A_PASSA" in outcomes
    assert "B_PARA" not in outcomes
    assert "lateral_b_para" not in json.dumps(audit["cell_audits"])


def test_frozen_14pav_v419_v420_v411_v2(tmp_path: Path) -> None:
    if not (DXF_14.is_file() and ESTADO_14.is_file()):
        return
    if sha256_file(DXF_14) != FROZEN_VPS_14PAV["source_dxf_sha256"]:
        return
    source = DxfParserCadSource(DXF_14)
    snap = load_snapshot_from_estado(ESTADO_14, FROZEN_VPS_14PAV["project_id"], "14_PAV")
    attach_scope_audits(snap, lv_audit=LV_AUDIT if LV_AUDIT.is_file() else None)
    audit = run_factory(
        snapshot=snap, source=source, classes=["LV"], items=["V419", "V420", "V411"],
        identity_base={"project_id": FROZEN_VPS_14PAV["project_id"], "pavimento": "14_PAV"},
        catalog="v2",
    )
    by_item = {}
    for row in audit["cell_audits"]:
        by_item.setdefault(row["item"], []).append(row)
    v419 = by_item.get("V419") or []
    assert v419
    assert all(row["n1_relevance"] == "SOURCE_INSUFFICIENT" for row in v419)
    assert all(row.get("why") == "no_dxf_line_matches_n1_cell" for row in v419)
    packed_items = {row["packet"]["identity"]["item"] for row in audit["cases"]}
    assert "V419" not in packed_items
    assert "V420" not in packed_items
    assert "V411" not in packed_items
    v420 = by_item.get("V420") or []
    mixed = {row["handle"]: row for row in v420
             if row.get("why") == "para_and_passa_on_distinct_encounters"}
    assert set(mixed) >= {"2F8", "2F5", "2F9"}
    assert mixed["2F8"]["source_outcomes"] == ["A_PARA", "A_PASSA"]
    assert mixed["2F5"]["source_outcomes"] == ["B_PARA", "B_PASSA"]
    assert mixed["2F9"]["source_outcomes"] == ["B_PARA", "B_PASSA"]
    assert all(row["n1_relevance"] == "SOURCE_INSUFFICIENT" for row in mixed.values())
    v411 = by_item.get("V411") or []
    assert any(row.get("handle") == "315" and row["n1_relevance"] == "CAD_REDUNDANT"
               for row in v411)
    for row in audit["cases"]:
        validate_request(row["jev_request"])
        assert row["n1_relevance"] == "N1_DECISION_RELEVANT"
        blob = json.dumps(row["packet"]["evidence"])
        assert "lateral_a_para" not in blob
        assert row["packet"]["question"]["criteria"]["INSUFFICIENT"]
