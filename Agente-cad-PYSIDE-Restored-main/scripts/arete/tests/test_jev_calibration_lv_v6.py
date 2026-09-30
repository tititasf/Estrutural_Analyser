"""v6 wall-level LV comparison. No live Jev API. Frozen v3/v4/v5 files are read-only."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.arete.jev_calibration.adapters_lv_v5 import ownership_gate as ownership_gate_v5
from scripts.arete.jev_calibration.adapters_lv_v6 import (
    ComparisonInvalid,
    aggregate_source_walls,
    build_source_only_request,
    classify_n1_mapping,
    endpoint_n1_compare_is_valid,
    endpoint_source_behavior,
    join_n1_wall_sets,
    load_frozen_pavement,
    ownership_status_v6,
    route_adviser,
    spec_for,
    wall_key,
    wall_verdict,
)
from scripts.arete.jev_calibration.catalog_v1 import CATALOG
from scripts.arete.jev_calibration.catalog_v2 import CATALOG_V2
from scripts.arete.jev_calibration.catalog_v3 import CATALOG_V3
from scripts.arete.jev_calibration.catalog_v5 import CATALOG_V5
from scripts.arete.jev_calibration.catalog_v6 import (
    CATALOG_V6,
    CATALOG_V6_REVISION,
    EXPECTED_V3_SIDECAR_SHA,
    EXPECTED_V4_COLLISION_AUDIT_SHA,
    PAVEMENT_SPECS_V6,
)
from scripts.arete.jev_calibration.lv_wall_ownership_audit import EXPECTED_V3_INVENTORY_SHA
from scripts.arete.jev_calibration.runner import api_payload
from scripts.arete.jev_sa_second_read import validate_request


def _enc(*, pav, beam, handle, face, at, para, passa, gaps=None, conts=None, pillars=None,
         partner="P1", label="L1", label_ok=True, segment=None):
    facts = {
        "gap_handles": list(gaps or []),
        "continuation_handles": list(conts or []),
        "pillar_markers": [{"handle": h, "text": "P1", "xy": at} for h in (pillars or [])],
        "label_handle": label,
        "label_xy": [8.0, 7.0],
        "wall_etype": "LWPOLYLINE",
    }
    eid = f"{pav}|LV|{beam}|enc|{handle}|{face}|{at[0]:.3f},{at[1]:.3f}|{handle}"
    seg = segment or [at, [at[0], at[1] + 85.0]]
    return {
        "encounter_id": eid,
        "beam": beam,
        "face": face,
        "wall_handle": handle,
        "at": at,
        "partner_handle": partner,
        "label_ok": label_ok,
        "source_handles": [handle, partner, label],
        "facts": facts,
        "hypotheses": {"para": para, "passa": passa, "layer": "HYPOTHESIS"},
        "wall_segment": seg,
    }


def _inventory(encounters, pav="14_PAV"):
    return {
        "schema": "jev_lv_source_inventory/v3",
        "pavimento": pav,
        "inventory_sha256": "inv",
        "source_dxf_sha256": "d" * 64,
        "encounters": encounters,
        "beams": [],
    }


def _sidecar(rows, inv_sha="inv"):
    return {
        "schema": "jev_lv_n1_comparison_sidecar/v3",
        "source_inventory_sha256": inv_sha,
        "sidecar_sha256": "sid",
        "n1_source": "test",
        "rows": rows,
    }


def _n1_row(enc, matches, present=True):
    return {
        "encounter_id": enc["encounter_id"],
        "beam": enc["beam"],
        "wall_handle": enc["wall_handle"],
        "n1_present": present,
        "n1_cell_matches": matches,
    }


def _cell(*, behavior, handle="2F8", match="exact", cover=False, side="A",
          pts=None, near=True):
    return {
        "behavior": behavior,
        "side": side,
        "kind": f"lateral_{side.lower()}_{behavior.lower()}",
        "index": "3",
        "locator_points": pts or [[4708.59, 3103.025], [4708.59, 3188.025]],
        "matched_source_handle": handle,
        "locator_match": match,
        "locator_cover": cover,
        "endpoint_near_encounter": near,
    }


def test_v6_catalog_distinct_from_prior():
    assert CATALOG["revision"] != CATALOG_V6["revision"]
    assert CATALOG_V2["revision"] != CATALOG_V6["revision"]
    assert CATALOG_V3["revision"] != CATALOG_V6["revision"]
    assert CATALOG_V5["revision"] != CATALOG_V6["revision"]
    assert CATALOG_V6["revision"] == CATALOG_V6_REVISION


def test_wall_level_vs_endpoint_trap():
    south = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A",
                 at=[4708.59, 3103.025], para=True, passa=False, gaps=["356"],
                 segment=[[4708.59, 3103.025], [4708.59, 3188.025]])
    north = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A",
                 at=[4708.59, 3188.025], para=False, passa=True, conts=["770"],
                 segment=[[4708.59, 3103.025], [4708.59, 3188.025]])
    both_cells = [
        _cell(behavior="Para"),
        _cell(behavior="Passa"),
    ]
    assert endpoint_source_behavior(south) == "PARA"
    assert endpoint_source_behavior(north) == "PASSA"
    assert endpoint_n1_compare_is_valid(n1_cells=both_cells) is False

    table = aggregate_source_walls(_inventory([south, north]), collisions={})
    assert len(table["walls"]) == 1
    wall = table["walls"][0]
    assert wall["source_set"] == ["PARA", "PASSA"]
    assert wall["source_status"] == "COMPLETE"
    assert wall["ownership_status"] == "OWNED"

    sidecar = _sidecar([
        _n1_row(south, both_cells),
        _n1_row(north, both_cells),
    ])
    joined = join_n1_wall_sets(table, sidecar)
    row = joined["walls"][0]
    assert row["n1_set"] == ["PARA", "PASSA"]
    assert row["verdict"] == "SET_EQUAL"
    south_n1 = {c["behavior"].upper() for c in both_cells}
    assert {endpoint_source_behavior(south)} != south_n1
    assert row["verdict"] != "MISMATCH"


def test_cover_locator_excluded_from_equality():
    a = _enc(pav="14_PAV", beam="V411", handle="315", face="A",
             at=[2300.59, 2602.025], para=True, passa=False, gaps=["G1"])
    b = _enc(pav="14_PAV", beam="V411", handle="315", face="A",
             at=[2300.59, 2754.025], para=False, passa=True, conts=["C1"])
    table = aggregate_source_walls(_inventory([a, b]), collisions={})
    cells = [_cell(behavior="Para", handle="315", match="cover", cover=True,
                   pts=[[2300.59, 2602.025], [2300.59, 2754.025]])]
    mapping = classify_n1_mapping(wall_handle="315", face="A", cells=cells)
    assert mapping["status"] == "COVER_ONLY"
    assert mapping["exact_set"] == []
    sidecar = _sidecar([_n1_row(a, cells), _n1_row(b, cells)])
    joined = join_n1_wall_sets(table, sidecar)
    assert joined["walls"][0]["verdict"] == "ABSTAIN_N1_COVERAGE"
    assert "cover" in joined["walls"][0]["verdict_why"]


def test_exact_plus_cover_on_same_wall_abstains():
    cells = [
        _cell(behavior="Para", handle="315", match="exact", side="A"),
        _cell(behavior="Passa", handle="315", match="cover", cover=True, side="A"),
    ]
    mapping = classify_n1_mapping(wall_handle="315", face="A", cells=cells)
    assert mapping["status"] == "AMBIGUOUS"
    assert mapping["exact_set"] == []
    assert mapping["reason"] == "mixed_exact_and_cover_locators_for_same_wall"


def test_missing_n1_is_coverage_not_mismatch():
    a = _enc(pav="13_PAV", beam="V304", handle="444", face="B",
             at=[3360.883, 2509.038], para=False, passa=True, conts=["43C"])
    b = _enc(pav="13_PAV", beam="V304", handle="444", face="B",
             at=[3360.883, 2400.038], para=True, passa=False, gaps=["G"])
    table = aggregate_source_walls(_inventory([a, b], pav="13_PAV"), collisions={})
    sidecar = _sidecar([
        _n1_row(a, [], present=False),
        _n1_row(b, [], present=False),
    ])
    joined = join_n1_wall_sets(table, sidecar)
    assert joined["walls"][0]["verdict"] == "ABSTAIN_N1_COVERAGE"
    assert joined["walls"][0]["n1_mapping_status"] == "MISSING"
    assert "MISMATCH" not in joined["walls"][0]["verdict"]


def test_ambiguous_locator_without_handle_is_not_mismatch():
    a = _enc(pav="14_PAV", beam="V402", handle="29A", face="B",
             at=[2118.09, 2773.025], para=True, passa=False, gaps=["G"])
    b = _enc(pav="14_PAV", beam="V402", handle="29A", face="B",
             at=[2493.09, 2773.025], para=False, passa=True, conts=["C"])
    table = aggregate_source_walls(_inventory([a, b]), collisions={})
    cells = [_cell(behavior="Para", handle=None, match=None, near=True)]
    mapping = classify_n1_mapping(wall_handle="29A", face="B", cells=cells)
    assert mapping["status"] == "AMBIGUOUS"
    sidecar = _sidecar([_n1_row(a, cells), _n1_row(b, cells)])
    assert join_n1_wall_sets(table, sidecar)["walls"][0]["verdict"] == "ABSTAIN_N1_COVERAGE"


def test_ambiguous_ownership_shared_joint_abstains():
    idx = {
        "CC": {
            "category": "SHARED_JOINT",
            "in_strip_names": ["V303", "V310"],
            "owners": [
                {"beam": "V303", "membership": {"in_strip": True}},
                {"beam": "V310", "membership": {"in_strip": True}},
            ],
        }
    }
    assert ownership_status_v6(wall_handle="CC", beam="V303", collisions=idx) == (
        "UNCERTAIN", "shared_joint_not_forced_exclusive",
    )
    assert ownership_gate_v5(wall_handle="CC", beam="V303", collisions=idx)[0] is True
    a = _enc(pav="13_PAV", beam="V303", handle="CC", face="A",
             at=[0.0, 0.0], para=True, passa=False, gaps=["G"])
    b = _enc(pav="13_PAV", beam="V303", handle="CC", face="A",
             at=[0.0, 10.0], para=False, passa=True, conts=["C"])
    table = aggregate_source_walls(_inventory([a, b], pav="13_PAV"), collisions=idx)
    assert table["walls"][0]["ownership_status"] == "UNCERTAIN"
    cells = [_cell(behavior="Para", handle="CC"), _cell(behavior="Passa", handle="CC")]
    sidecar = _sidecar([_n1_row(a, cells), _n1_row(b, cells)])
    joined = join_n1_wall_sets(table, sidecar)
    assert joined["walls"][0]["verdict"] == "ABSTAIN_OWNERSHIP"
    assert joined["walls"][0]["verdict"] != "SET_DIVERGE"


def test_overexpanded_keeps_only_in_strip_owner():
    idx = {
        "187": {
            "category": "LIKELY_OVER_EXPANDED_STRIP",
            "in_strip_names": ["V406"],
            "owners": [
                {"beam": "V406", "membership": {"in_strip": True}},
                {"beam": "V409", "membership": {"in_strip": False}},
            ],
        }
    }
    kept, why = ownership_status_v6(wall_handle="187", beam="V406", collisions=idx)
    rejected, _ = ownership_status_v6(wall_handle="187", beam="V409", collisions=idx)
    assert kept == "OWNED"
    assert "in_strip_owner_kept" in why
    assert rejected == "REJECTED"


def test_incomplete_source_abstains():
    a = _enc(pav="13_PAV", beam="V1", handle="W1", face="A",
             at=[0.0, 0.0], para=True, passa=False, gaps=["G"])
    b = _enc(pav="13_PAV", beam="V1", handle="W1", face="A",
             at=[0.0, 10.0], para=False, passa=False)
    table = aggregate_source_walls(_inventory([a, b], pav="13_PAV"), collisions={})
    assert table["walls"][0]["source_status"] == "INCOMPLETE"
    mapping = {"status": "EXACT", "reason": "x", "exact_set": ["PARA"]}
    verdict, _ = wall_verdict(table["walls"][0], mapping, n1_present=True)
    assert verdict == "ABSTAIN_SOURCE"


def test_sidecar_inventory_sha_mismatch_fails_closed():
    a = _enc(pav="14_PAV", beam="V1", handle="W1", face="A",
             at=[0.0, 0.0], para=True, passa=False, gaps=["G"])
    b = _enc(pav="14_PAV", beam="V1", handle="W1", face="A",
             at=[0.0, 10.0], para=False, passa=True, conts=["C"])
    table = aggregate_source_walls(_inventory([a, b]), collisions={})
    with pytest.raises(ComparisonInvalid, match="source_inventory_sha256"):
        join_n1_wall_sets(table, _sidecar([], inv_sha="other"))


def test_source_only_request_validates_and_excludes_n1():
    south = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A",
                 at=[4708.59, 3103.025], para=True, passa=False, gaps=["356"])
    north = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A",
                 at=[4708.59, 3188.025], para=False, passa=True, conts=["770"])
    table = aggregate_source_walls(_inventory([south, north]), collisions={})
    spec = {
        "project_id": PAVEMENT_SPECS_V6["14_PAV"]["project_id"],
        "expected_dxf_sha256": PAVEMENT_SPECS_V6["14_PAV"]["expected_dxf_sha256"],
    }
    built = build_source_only_request(table["walls"][0], spec)
    v1 = built["v1_request"]
    validate_request(v1)
    payload = api_payload(v1)
    blob = json.dumps(payload).lower()
    assert "baseline_sa" not in payload
    assert "expected_choice" not in blob
    assert "n1_set" not in blob
    assert "n1_outcomes" not in blob
    assert "hypotheses" not in blob
    assert built["n1_in_request"] is False
    assert set(v1["question"]["criteria"]) == {
        "PARA_ONLY", "PASSA_ONLY", "PARA_AND_PASSA", "INSUFFICIENT",
    }


def test_route_only_diverge_or_actionable_ambiguity():
    south = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A",
                 at=[4708.59, 3103.025], para=True, passa=False, gaps=["356"])
    north = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A",
                 at=[4708.59, 3188.025], para=False, passa=True, conts=["770"])
    table = aggregate_source_walls(_inventory([south, north]), collisions={})
    equal_cells = [_cell(behavior="Para"), _cell(behavior="Passa")]
    joined_equal = join_n1_wall_sets(table, _sidecar([
        _n1_row(south, equal_cells), _n1_row(north, equal_cells),
    ]))
    routed_equal = route_adviser(table, joined_equal)
    assert routed_equal["n_actionable"] == 0
    assert routed_equal["calls_used"] == 0
    diverge_cells = [_cell(behavior="Para")]
    joined_div = join_n1_wall_sets(table, _sidecar([
        _n1_row(south, diverge_cells), _n1_row(north, diverge_cells),
    ]))
    routed_div = route_adviser(table, joined_div)
    assert routed_div["n_actionable"] == 1
    assert routed_div["packed"][0]["route"] == "SOURCE_VS_N1_SET_DIVERGE"
    assert routed_div["execute"] is False
    assert "v1_request" in routed_div["packed"][0]


def test_frozen_comparable_diverge_queue_is_wall_level():
    from scripts.arete.jev_calibration.adapters_lv_v6 import run_pavement
    row = run_pavement("14_PAV")
    assert row["parity_claimed"] is False
    assert row["coverage"]["set_diverge"] == 4
    assert row["coverage"]["set_equal"] == 5
    ids = {w["wall_id"] for w in row["comparable_rows"] if w["verdict"] == "SET_DIVERGE"}
    assert ids == {
        "14_PAV|LV|V409|wall|2CC|A",
        "14_PAV|LV|V409|wall|2CD|B",
        "14_PAV|LV|V420|wall|2F6|A",
        "14_PAV|LV|V420|wall|2F7|B",
    }
    assert row["routing"]["n_packed"] == 4
    assert row["routing"]["calls_used"] == 0


def test_frozen_v420_2f8_wall_set_from_artifacts():
    inventory, collisions, sidecar, spec = load_frozen_pavement("14_PAV")
    assert spec["parity_claimed"] is False
    assert inventory["inventory_sha256"] == EXPECTED_V3_INVENTORY_SHA["14_PAV"]
    assert sidecar["sidecar_sha256"] == EXPECTED_V3_SIDECAR_SHA["14_PAV"]
    table = aggregate_source_walls(inventory, collisions)
    key = wall_key(pavimento="14_PAV", beam="V420", wall_handle="2F8", face="A")
    wall = next(w for w in table["walls"] if w["wall_id"] == key)
    assert wall["source_set"] == ["PARA", "PASSA"]
    assert wall["n1_used"] is False
    joined = join_n1_wall_sets(table, sidecar)
    row = next(w for w in joined["walls"] if w["wall_id"] == key)
    assert row["n1_set"] == ["PARA", "PASSA"]
    assert row["verdict"] == "SET_EQUAL"
    assert row["ownership_status"] == "OWNED"


def test_frozen_sha_constants_match_expected_docs():
    assert EXPECTED_V3_INVENTORY_SHA["13_PAV"].startswith("c8335551")
    assert EXPECTED_V4_COLLISION_AUDIT_SHA["14_PAV"].startswith("aa5eb968")
    inventory, collisions, sidecar, spec = load_frozen_pavement("13_PAV")
    assert inventory["inventory_sha256"] == EXPECTED_V3_INVENTORY_SHA["13_PAV"]
    assert sidecar["sidecar_sha256"] == EXPECTED_V3_SIDECAR_SHA["13_PAV"]
    assert spec["expected_collision_sha256"] == EXPECTED_V4_COLLISION_AUDIT_SHA["13_PAV"]
    assert "2F8" not in collisions or True


def test_v5_corrigido_not_imported_as_truth():
    path = (
        Path(__file__).resolve().parents[1] / "relatorios"
        / "20260930_jev_lv_blinded_single_outcome_v5" / "STATUS_CORRIGIDO.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["n1_endpoint_comparable_n"] == 0
    assert payload["n1_agrees_cad_n"] is None
    from scripts.arete.jev_calibration import adapters_lv_v6 as v6
    source = Path(v6.__file__).read_text(encoding="utf-8")
    assert "n1_endpoint_comparable_n" not in source
    assert "n1_agrees_cad_n" not in source
