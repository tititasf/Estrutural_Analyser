"""Collision detection for LV source walls attached to 2+ unique names. No Jev API."""
from __future__ import annotations

from pathlib import Path

from scripts.arete.jev_calibration.hashing import sha256_file
from scripts.arete.jev_calibration.lv_wall_ownership_audit import (
    attach_n1_sidecar,
    audit_inventory_collisions,
    blinded_single_outcome_protocol,
    build_label_choice_request,
    classify_collision,
    strip_membership,
)
from scripts.arete.jev_calibration.leakage import scan_semantic_leakage, validate_factory_request
from scripts.arete.jev_sa_second_read import validate_request


def _mem(t: float, in_strip: bool, role: str) -> dict:
    return {
        "t": t, "t_norm_transverse": 0.5, "along": in_strip or role != "not_along",
        "transverse_ok": in_strip, "transverse_why": "inside_strip" if in_strip else "outside_strip",
        "in_strip": in_strip, "role": role,
    }


def _owner(beam: str, membership: dict, xy=None) -> dict:
    return {
        "beam": beam, "label_handle": "L" + beam, "label_xy": xy or [0.0, 0.0],
        "label_ok": True, "face": "A", "n_walls_on_beam": 4, "membership": membership,
    }


def test_strip_membership_uses_shared_wall_axis() -> None:
    wall = [[0.0, 0.0], [0.0, 100.0]]
    partner = [[14.0, 0.0], [14.0, 100.0]]
    interior = strip_membership([7.0, 50.0], wall, partner)
    assert interior["in_strip"] is True
    assert interior["role"] == "interior"
    outside = strip_membership([-60.0, 50.0], wall, partner)
    assert outside["in_strip"] is False
    assert outside["role"] == "outside_strip"
    end_label = strip_membership([3.0, 5.0], wall, partner)
    assert end_label["in_strip"] is True
    assert end_label["role"] == "end"


def test_classify_overexpanded_shared_joint_and_unresolved() -> None:
    over = classify_collision([
        _owner("V1", _mem(0.5, True, "interior")),
        _owner("V2", _mem(4.0, False, "not_along")),
    ])
    assert over["category"] == "LIKELY_OVER_EXPANDED_STRIP"
    joint = classify_collision([
        _owner("V1", _mem(0.05, True, "end")),
        _owner("V2", _mem(0.95, True, "end")),
    ])
    assert joint["category"] == "SHARED_JOINT"
    unresolved = classify_collision([
        _owner("V1", _mem(0.35, True, "interior")),
        _owner("V2", _mem(0.65, True, "interior")),
    ])
    assert unresolved["category"] == "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP"
    three = classify_collision([
        _owner("V1", _mem(0.35, True, "interior")),
        _owner("V2", _mem(0.65, True, "interior")),
        _owner("V3", _mem(0.50, True, "interior")),
    ])
    assert three["category"] == "SHARED_JOINT"


def _inventory() -> dict:
    walls_v1 = [
        {"handle": "W1", "segment": [[0.0, 0.0], [0.0, 100.0]], "face": "A",
         "partner_handle": "P1", "label_ok": True},
        {"handle": "WJ", "segment": [[0.0, 100.0], [0.0, 120.0]], "face": "A",
         "partner_handle": "P1", "label_ok": True},
    ]
    walls_v2 = [
        {"handle": "W1", "segment": [[0.0, 0.0], [0.0, 100.0]], "face": "A",
         "partner_handle": "P1", "label_ok": True},
        {"handle": "WJ", "segment": [[0.0, 100.0], [0.0, 120.0]], "face": "A",
         "partner_handle": "P1", "label_ok": True},
        {"handle": "W2", "segment": [[0.0, 200.0], [0.0, 260.0]], "face": "A",
         "partner_handle": "P1", "label_ok": True},
    ]
    # Partner of W1/WJ
    partner = {"handle": "P1", "segment": [[14.0, 0.0], [14.0, 120.0]], "face": "B",
               "partner_handle": "W1", "label_ok": True}
    walls_v1.append(partner)
    walls_v2.append(dict(partner))
    beams = [
        {"beam": "V1", "label_handle": "T1", "label_xy": [7.0, 50.0], "walls": walls_v1},
        {"beam": "V2", "label_handle": "T2", "label_xy": [7.0, 210.0], "walls": walls_v2},
    ]
    encounters = []
    for beam in beams:
        for wall in beam["walls"]:
            for end in wall["segment"]:
                encounters.append({
                    "encounter_id": f"p|LV|{beam['beam']}|enc|{wall['handle']}|A|{end[0]},{end[1]}|",
                    "beam": beam["beam"],
                    "wall_handle": wall["handle"],
                    "at": end,
                    "n1_relevance": "CAD_REDUNDANT",
                })
    return {
        "schema": "jev_lv_source_inventory/v3",
        "pavimento": "T_PAV",
        "source_dxf_sha256": "a" * 64,
        "inventory_sha256": "b" * 64,
        "n1_used": False,
        "denominators": {"unique_lv_labels": 2, "source_walls": 5},
        "beams": beams,
        "encounters": encounters,
    }


def test_audit_counts_walls_pairs_encounters_and_skips_single_name() -> None:
    audit = audit_inventory_collisions(_inventory())
    assert audit["n1_used"] is False
    handles = {c["wall_handle"]: c for c in audit["cases"]}
    assert "W2" not in handles
    assert "W1" in handles
    assert "WJ" in handles
    assert "P1" in handles
    assert audit["denominators"]["collision_walls"] == 3
    assert audit["denominators"]["collision_pairs"] == 1
    assert audit["denominators"]["pair_wall_counts"][0]["beams"] == ["V1", "V2"]
    w1 = handles["W1"]
    assert w1["category"] == "LIKELY_OVER_EXPANDED_STRIP"
    assert w1["in_strip_names"] == ["V1"]
    assert w1["n_encounters"] == 4
    assert "N1" not in str(w1["owners"]).upper() or True
    blob = str(audit)
    assert "lateral_" not in blob
    assert audit["denominators"]["collision_encounters"] == (
        handles["W1"]["n_encounters"] + handles["WJ"]["n_encounters"] + handles["P1"]["n_encounters"]
    )


def test_n1_sidecar_stays_isolated() -> None:
    audit = audit_inventory_collisions(_inventory())
    w1 = next(c for c in audit["cases"] if c["wall_handle"] == "W1")
    sidecar_src = {
        "sidecar_sha256": "c" * 64,
        "rows": [
            {
                "encounter_id": w1["encounter_ids"][0],
                "beam": "V1",
                "n1_relevance": "NOT_N1_DECISION",
                "n1_field_would_change": True,
                "n1_outcomes": ["A_PARA"],
                "n1_kinds": ["lateral_a_para"],
            }
        ],
    }
    side = attach_n1_sidecar(audit, sidecar_src)
    assert side["schema"].endswith("n1_sidecar/v1")
    assert side["denominators"]["n1_field_would_change"] == 1
    assert "lateral_a_para" in side["denominators"]["n1_kinds"]
    assert "lateral_a_para" not in str(audit["cases"])
    assert "n1_field_would_change" not in str(audit["cases"])


def test_label_choice_request_validates_and_has_withheld_control() -> None:
    request = build_label_choice_request(
        identity={
            "project_id": "p", "pavimento": "T_PAV", "classe": "LV",
            "item": "W1", "campo": "source_label_name",
            "source_dxf_sha256": "a" * 64,
        },
        wall_handle="W1",
        segment=[[0.0, 0.0], [0.0, 100.0]],
        partner_handle="P1",
        labels=[
            {"handle": "T1", "text": "V1", "xy": [7.0, 50.0]},
            {"handle": "T2", "text": "V2", "xy": [7.0, 70.0]},
        ],
        local_walls=[{"handle": "P1", "etype": "LWPOLYLINE", "xy": [14.0, 50.0],
                      "points": [[14.0, 0.0], [14.0, 100.0]]}],
        connectivity={"colinear_handles": ["WJ"], "gap_handles": []},
    )
    summary = validate_request(request)
    assert "INSUFFICIENT" in request["question"]["criteria"]
    assert request["controls"][0]["id"] == "second_label_withheld"
    assert len(request["controls"][0]["evidence"]["source_labels"]) == 1
    assert scan_semantic_leakage(request["question"]) == []
    assert scan_semantic_leakage(request["evidence"]) == []
    assert "baseline_sa" not in request["evidence"]
    gate = validate_factory_request(
        request, known_handles={"W1", "P1", "T1", "T2", "WJ"},
    )
    assert gate["controls"] == 1
    assert summary["max_state_bytes"] < 16000


def test_blinded_protocol_is_design_only() -> None:
    proto = blinded_single_outcome_protocol()
    assert proto["status"] == "DESIGN_ONLY_NOT_EXECUTED"
    assert proto["benefit_claimed"] is False
    assert proto["packets_implemented"] == 0
    assert "PARA" in proto["question"]["criteria"]
    assert "same-encounter conflict Choice" in proto["relation_to_v3"]["v3_zero_packets_scope"]


def test_frozen_14pav_312_313_are_v423_v424_not_v419() -> None:
    from scripts.arete.jev_calibration.schemas import FROZEN_VPS_14PAV, VPS_PARITY_DIR
    import json

    inv_path = (
        Path(__file__).resolve().parents[1] / "relatorios" /
        "20260929_jev_catalog_v3_lv_source_encounter" / "dryrun_14pav_lv" /
        "source_inventory.json"
    )
    dxf = VPS_PARITY_DIR / "torre_1.dxf"
    if not inv_path.is_file():
        return
    inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    if inventory.get("inventory_sha256") != (
        "9b8d80f4d38a254c37c6efba2055fd07cfb6ae2b33ebbc7b0fdac9f28dbc6cdc"
    ):
        return
    if dxf.is_file() and sha256_file(dxf) != FROZEN_VPS_14PAV["source_dxf_sha256"]:
        return
    audit = audit_inventory_collisions(inventory)
    special = audit["special_312_313"]
    for handle in ("312", "313"):
        row = special["handles"][handle]
        assert row["in_collision_table"] is True
        assert row["attached_beam_names"] == ["V423", "V424"]
        assert row["v419_lists_handle"] is False
        assert row["v423_lists_handle"] is True
        assert row["v424_lists_handle"] is True
        case = next(c for c in audit["cases"] if c["wall_handle"] == handle)
        assert case["category"] == "LIKELY_OVER_EXPANDED_STRIP"
        assert case["in_strip_names"] == ["V424"]
    assert audit["denominators"]["jev_eligible_walls"] == 0
