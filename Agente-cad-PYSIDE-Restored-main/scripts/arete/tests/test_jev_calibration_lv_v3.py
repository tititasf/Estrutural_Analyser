"""Catalog v3 source-first LV encounters. v1/v2 regression stays in sibling tests."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.catalog_v1 import CATALOG
from scripts.arete.jev_calibration.catalog_v2 import CATALOG_V2
from scripts.arete.jev_calibration.catalog_v3 import CATALOG_V3, CATALOG_V3_REVISION, lv_v3_question
from scripts.arete.jev_calibration.adapters_lv_v3 import (
    classify_encounter,
    compare_n1_sidecar,
    extract_source_inventory,
    pack_gate,
)
from scripts.arete.jev_calibration.factory import run_factory
from scripts.arete.jev_calibration.hashing import sha256_file
from scripts.arete.jev_calibration.leakage import scan_semantic_leakage
from scripts.arete.jev_calibration.n1_snapshot import N1Item, N1Snapshot, load_snapshot_from_estado
from scripts.arete.jev_calibration.schemas import FROZEN_VPS_14PAV, VPS_PARITY_DIR
from scripts.arete.tests.test_jev_calibration_lv_fv import _beam_dxf, _lv_item
from scripts.arete.tests.test_jev_calibration_lv_v2 import _conflict_dxf, _conflict_item

DXF_14 = VPS_PARITY_DIR / "torre_1.dxf"
ESTADO_14 = VPS_PARITY_DIR / "estado_14_PAV.json"


def _v419_miss_dxf(tmp_path: Path) -> Path:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("V419", dxfattribs={"insert": (2160, 2200), "layer": "4"})
    msp.add_lwpolyline([(2150, 2075), (2150, 2335)], dxfattribs={"layer": "3"})
    msp.add_lwpolyline([(2170, 2075), (2170, 2335)], dxfattribs={"layer": "3"})
    msp.add_lwpolyline(
        [(2150, 2075), (2170, 2075), (2170, 2055), (2150, 2055), (2150, 2075)],
        close=True, dxfattribs={"layer": "7"},
    )
    path = tmp_path / "fase1_lv_v3_v419.dxf"
    doc.saveas(path)
    return path


def _v419_miss_item() -> N1Item:
    return N1Item(
        classe="LV", name="V419", points=[[2157.75, 2473], [2157.75, 2600]],
        sa_value="lateral_a_para", sa_field="lv_cell", snapshot_hash="v419miss",
        extras={
            "cells": [
                {"kind": "lateral_a_para", "side": "A", "behavior": "Para", "index": 1,
                 "points": [[2157.75, 2473], [2157.75, 2600]]},
            ],
            "fundo": [],
        },
    )


def test_catalog_v3_is_distinct_from_v1_v2() -> None:
    assert CATALOG["revision"] != CATALOG_V3["revision"]
    assert CATALOG_V2["revision"] != CATALOG_V3["revision"]
    assert CATALOG_V3["revision"] == CATALOG_V3_REVISION
    q = lv_v3_question({"A_PARA": "FACE_A PARA", "A_PASSA": "FACE_A PASSA"})
    assert "INSUFFICIENT" in q["criteria"]
    assert "one encounter" in CATALOG_V3["classes"]["LV"]["instructions"]
    assert not scan_semantic_leakage(q)


def test_v1_default_unchanged_with_v3_present(tmp_path: Path) -> None:
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


def test_classify_same_encounter_para_passa_fail_closed() -> None:
    relevance, why = classify_encounter(face="A", para=True, passa=True, label_ok=True)
    assert relevance == "SOURCE_INSUFFICIENT"
    assert why == "para_and_passa_not_exclusive_at_one_encounter"
    packed, packed_why = pack_gate(
        relevance="N1_DECISION_RELEVANT", why="should_not_stick",
        para=True, passa=True, para_handles=["G1"], passa_handles=["C1"],
        n1_field_would_change=True,
    )
    assert packed == "SOURCE_INSUFFICIENT"
    assert packed_why == "para_and_passa_not_exclusive_at_one_encounter"


def test_v3_mixed_endpoints_are_two_encounters_not_choice(tmp_path: Path) -> None:
    source = DxfParserCadSource(_conflict_dxf(tmp_path))
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V500"): _conflict_item()})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V500"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"}, catalog="v3")
    assert audit["catalog"] == "v3"
    assert audit["packed"] == 0
    assert audit["cases"] == []
    assert "N1_DECISION_RELEVANT" not in (audit.get("n1_relevance_counts") or {})
    rows = [row for row in audit["cell_audits"] if row.get("handle")]
    assert rows
    ats = {tuple(row.get("at") or []) for row in rows}
    assert len(ats) >= 2
    blob = json.dumps(audit["source_inventory"])
    assert "lateral_b_passa" not in blob
    assert "own_stretch" not in blob.lower()
    assert audit["source_inventory"]["n1_used"] is False
    sidecar_blob = json.dumps(audit["n1_sidecar"])
    assert "lateral_b_passa" in sidecar_blob


def test_v3_finds_source_walls_when_n1_locators_miss(tmp_path: Path) -> None:
    source = DxfParserCadSource(_v419_miss_dxf(tmp_path))
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V419"): _v419_miss_item()})
    inventory = extract_source_inventory(source, pavimento="14_PAV", beam_names=["V419"])
    assert inventory["denominators"]["source_walls"] >= 2
    handles = {w["handle"] for b in inventory["beams"] for w in b.get("walls") or []}
    assert handles
    sidecar = compare_n1_sidecar(inventory, snap, source)
    assert sidecar["schema"] == "jev_lv_n1_comparison_sidecar/v3"
    assert sidecar["denominators"]["n1_decision_relevant"] == 0
    miss = sidecar["denominators"]["n1_field_would_change"]
    assert miss >= 0
    locators_unmatched = any(
        row.get("n1_locator_miss_cells_on_beam", 0) > 0 for row in sidecar["rows"]
    )
    assert locators_unmatched
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V419"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"}, catalog="v3")
    assert audit["packed"] == 0
    assert audit["source_inventory"]["denominators"]["source_walls"] >= 2


def test_v3_does_not_use_n1_kind_or_locator_cover_as_passa(tmp_path: Path) -> None:
    source = DxfParserCadSource(_conflict_dxf(tmp_path))
    item = _conflict_item()
    item.extras["cells"][0]["kind"] = "lateral_b_para"
    snap = N1Snapshot(project_id="p", pavimento="14_PAV", source="fixture",
                      fingerprint_sha256="fp", items={("LV", "V500"): item})
    audit = run_factory(snapshot=snap, source=source, classes=["LV"], items=["V500"],
                        identity_base={"project_id": "p", "pavimento": "14_PAV"}, catalog="v3")
    for enc in audit["source_inventory"]["encounters"]:
        assert enc["hypotheses"]["n1_locator_cover_unused"] is True
        assert "lateral_b_para" not in json.dumps(enc)
    for row in audit["n1_sidecar"]["rows"]:
        assert row["locator_cover_not_used_as_passa"] is True


def test_frozen_14pav_v419_v420_v411_v3() -> None:
    if not (DXF_14.is_file() and ESTADO_14.is_file()):
        return
    if sha256_file(DXF_14) != FROZEN_VPS_14PAV["source_dxf_sha256"]:
        return
    source = DxfParserCadSource(DXF_14)
    snap = load_snapshot_from_estado(ESTADO_14, FROZEN_VPS_14PAV["project_id"], "14_PAV")
    audit = run_factory(
        snapshot=snap, source=source, classes=["LV"], items=["V419", "V420", "V411"],
        identity_base={"project_id": FROZEN_VPS_14PAV["project_id"], "pavimento": "14_PAV"},
        catalog="v3",
    )
    assert audit["packed"] == 0
    assert audit["cases"] == []
    by_item: dict[str, list] = {}
    for row in audit["cell_audits"]:
        by_item.setdefault(row["item"], []).append(row)
    v419 = by_item.get("V419") or []
    assert v419
    assert all(row["n1_relevance"] != "N1_DECISION_RELEVANT" for row in v419)
    v419_handles = {row.get("handle") for row in v419}
    assert v419_handles - {None}
    v420 = by_item.get("V420") or []
    mixed = {row["handle"] for row in v420
             if row.get("why") == "para_and_passa_not_exclusive_at_one_encounter"
             or "PARA" in ",".join(row.get("source_outcomes") or [])}
    # Controls: each of 2F8/2F5/2F9 is present as a source wall with >=2 encounters.
    for handle in ("2F8", "2F5", "2F9"):
        rows = [row for row in v420 if row.get("handle") == handle]
        assert rows, handle
        ats = {tuple(row.get("at") or []) for row in rows}
        assert len(ats) >= 2, handle
        assert all(row["n1_relevance"] != "N1_DECISION_RELEVANT" for row in rows)
    v411 = by_item.get("V411") or []
    assert any(row.get("handle") == "315" for row in v411)
    inv_blob = json.dumps(audit["source_inventory"])
    assert "lateral_a_para" not in inv_blob
    assert audit["source_inventory"]["n1_used"] is False
    assert mixed or v420
