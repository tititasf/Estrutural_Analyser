"""v5 blinded single-outcome gates. No live Jev API."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.arete.jev_calibration.adapters_lv_v5 import (
    CONTROL_ID,
    QUESTION,
    cad_baseline,
    cache_key_v5,
    collision_index,
    eligible_encounters,
    ownership_gate,
    select_sample,
    source_behavior,
    to_v1_request,
    validate_v5_request,
    withdrawal_evidence,
)
from scripts.arete.jev_calibration.catalog_v1 import CATALOG
from scripts.arete.jev_calibration.catalog_v2 import CATALOG_V2
from scripts.arete.jev_calibration.catalog_v3 import CATALOG_V3
from scripts.arete.jev_calibration.catalog_v5 import CATALOG_V5, CATALOG_V5_REVISION, V5_REQUEST_SCHEMA
from scripts.arete.jev_calibration.runner import api_payload
from scripts.arete.jev_sa_second_read import validate_request


def _enc(*, pav, beam, handle, face, at, para, passa, gaps=None, conts=None, pillars=None,
         partner="P1", label="L1", ownership_handle=None):
    facts = {
        "gap_handles": list(gaps or []),
        "continuation_handles": list(conts or []),
        "pillar_markers": [{"handle": h, "text": "P1", "xy": at} for h in (pillars or [])],
        "label_handle": label,
        "nearby_polygon_handles": [],
        "wall_etype": "LWPOLYLINE",
        "closed": False,
        "vertex_count": 2,
    }
    eid = f"{pav}|LV|{beam}|enc|{handle}|{face}|{at[0]:.3f},{at[1]:.3f}|{handle}"
    return {
        "encounter_id": eid,
        "beam": beam,
        "face": face,
        "wall_handle": handle,
        "at": at,
        "partner_handle": partner,
        "label_ok": True,
        "source_handles": [handle, partner, label],
        "facts": facts,
        "hypotheses": {"para": para, "passa": passa, "layer": "HYPOTHESIS"},
        "wall_segment": [at, [at[0], at[1] + 10]],
    }


def _v5_request(behavior="PARA"):
    evidence = {
        "endpoint": {"xy": [1.0, 2.0], "units": "dxf_drawing"},
        "wall": {"handle": "W1", "etype": "LINE", "points": [[1.0, 2.0], [1.0, 12.0]], "xy": [1.0, 7.0]},
        "partner": {"handle": "P1", "etype": "LINE", "points": [[15.0, 2.0], [15.0, 12.0]], "xy": [15.0, 7.0]},
        "beam_label": {"handle": "L1", "text": "V420", "xy": [8.0, 7.0]},
        "encounter_gaps": [{"handle": "G1", "etype": "LWPOLYLINE", "points": [[0.0, 2.0], [16.0, 2.0]], "xy": [8.0, 2.0]}],
        "pillar_markers": [],
        "colinear_continuations": [],
        "local_same_layer_polygons": [],
        "definitions_apply_to_listed_objects_only": True,
    }
    if behavior == "PASSA":
        evidence["encounter_gaps"] = []
        evidence["colinear_continuations"] = [
            {"handle": "C1", "etype": "LINE", "points": [[1.0, 12.0], [1.0, 40.0]], "xy": [1.0, 26.0]},
        ]
    control = withdrawal_evidence(evidence, behavior)
    return {
        "schema": V5_REQUEST_SCHEMA,
        "identity": {
            "project_id": "p",
            "pavimento": "14_PAV",
            "classe": "LV",
            "item": "V420",
            "campo": "endpoint_behavior",
            "source_dxf_sha256": "a" * 64,
        },
        "question": copy.deepcopy(QUESTION),
        "evidence": evidence,
        "controls": [{"id": CONTROL_ID, "evidence": control}],
        "withdrawal_kind": behavior,
    }


def test_v5_catalog_distinct_from_v1_v2_v3():
    assert CATALOG["revision"] != CATALOG_V5["revision"]
    assert CATALOG_V2["revision"] != CATALOG_V5["revision"]
    assert CATALOG_V3["revision"] != CATALOG_V5["revision"]
    assert CATALOG_V5["revision"] == CATALOG_V5_REVISION


def test_v1_validator_rejects_v5_schema():
    with pytest.raises(ValueError, match="jev_sa_second_read_request/1"):
        validate_request(_v5_request())


def test_v5_validate_and_v1_adapter_string_criteria():
    v5 = _v5_request("PARA")
    summary = validate_v5_request(v5)
    assert summary["criteria"] == ["PARA", "PASSA", "INSUFFICIENT"]
    v1 = to_v1_request(v5)
    assert v1["schema"] == "jev_sa_second_read_request/1"
    assert all(isinstance(v, str) for v in v1["question"]["criteria"].values())
    assert v1["baseline_sa"]["n1_withheld_until_unblind"] is True
    payload = api_payload(v1)
    blob = json.dumps(payload)
    assert "baseline_sa" not in payload
    assert "expected_choice" not in blob
    assert "n1_withheld" not in blob
    validate_request(v1)


def test_hypothesis_and_n1_rejected_in_evidence():
    v5 = _v5_request()
    v5["evidence"]["hypotheses"] = {"para": True}
    with pytest.raises(ValueError, match="v5_forbidden"):
        validate_v5_request(v5)
    v5 = _v5_request()
    v5["evidence"]["source_outcomes"] = ["A_PARA"]
    with pytest.raises(ValueError, match="v5_forbidden"):
        validate_v5_request(v5)


def test_withdrawal_removes_decisive_handles_without_fabricating():
    v5 = _v5_request("PARA")
    ctrl = v5["controls"][0]["evidence"]
    assert ctrl["encounter_gaps"] == []
    assert ctrl["pillar_markers"] == []
    assert ctrl["wall"]["handle"] == "W1"
    assert ctrl["partner"]["handle"] == "P1"
    assert ctrl["colinear_continuations"] == []
    v5p = _v5_request("PASSA")
    ctrlp = v5p["controls"][0]["evidence"]
    assert ctrlp["colinear_continuations"] == []
    assert v5p["evidence"]["colinear_continuations"][0]["handle"] == "C1"
    validate_v5_request(v5)
    validate_v5_request(v5p)


def test_withdrawal_leak_fails_gate():
    v5 = _v5_request("PARA")
    v5["controls"][0]["evidence"]["encounter_gaps"] = copy.deepcopy(v5["evidence"]["encounter_gaps"])
    with pytest.raises(ValueError, match="withdrawal_leaked"):
        validate_v5_request(v5)


def test_ownership_excludes_overexpanded_and_unresolved():
    over = {"category": "LIKELY_OVER_EXPANDED_STRIP", "owners": []}
    unresolved = {"category": "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP", "owners": []}
    joint = {
        "category": "SHARED_JOINT",
        "owners": [
            {"beam": "V303", "membership": {"in_strip": True}},
            {"beam": "V310", "membership": {"in_strip": True}},
        ],
    }
    idx = {"AA": over, "BB": unresolved, "CC": joint}
    assert ownership_gate(wall_handle="aa", beam="V1", collisions=idx)[0] is False
    assert ownership_gate(wall_handle="BB", beam="V1", collisions=idx)[0] is False
    assert ownership_gate(wall_handle="CC", beam="V303", collisions=idx) == (True, "shared_joint_in_strip_member")
    assert ownership_gate(wall_handle="CC", beam="V999", collisions=idx)[0] is False
    assert ownership_gate(wall_handle="ZZ", beam="V1", collisions=idx) == (True, "exclusive_unique_label")


def test_select_prefers_v420_2f8_and_both_pavements():
    e14_s = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A", at=[4708.59, 3103.025],
                 para=True, passa=False, gaps=["G14"])
    e14_n = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A", at=[4708.59, 3188.025],
                 para=False, passa=True, conts=["C14"])
    e13_p = _enc(pav="13_PAV", beam="V303", handle="W13P", face="A", at=[100.0, 200.0],
                 para=True, passa=False, pillars=["P13"])
    e13_s = _enc(pav="13_PAV", beam="V305", handle="W13S", face="B", at=[300.0, 400.0],
                 para=False, passa=True, conts=["C13"])
    over = _enc(pav="13_PAV", beam="V310", handle="OX", face="A", at=[1.0, 1.0],
                para=True, passa=False, gaps=["GOX"])
    inventory_13 = {"encounters": [e13_p, e13_s, over]}
    inventory_14 = {"encounters": [e14_s, e14_n]}
    collisions = collision_index({
        "cases": [
            {"wall_handle": "OX", "category": "LIKELY_OVER_EXPANDED_STRIP", "owners": []},
        ]
    })
    pool13 = eligible_encounters(inventory_13, collisions)
    pool14 = eligible_encounters(inventory_14, collisions)
    assert all(r["wall_handle"] != "OX" for r in pool13)
    sample = select_sample({"13_PAV": pool13, "14_PAV": pool14})
    ids = [r["encounter_id"] for r in sample["selected"]]
    assert len(ids) == 4
    assert any("2F8" in i and "3103.025" in i for i in ids)
    assert any("2F8" in i and "3188.025" in i for i in ids)
    assert any(i.startswith("13_PAV|") for i in ids)
    assert {r["source_behavior"] for r in sample["selected"]} == {"PARA", "PASSA"}
    assert "OX" not in "".join(ids)


def test_cad_baseline_stays_outside_jev_state():
    enc = _enc(pav="14_PAV", beam="V420", handle="2F8", face="A", at=[4708.59, 3103.025],
               para=True, passa=False, gaps=["G14"])
    base = cad_baseline(enc)
    assert base["visible_to_jev"] is False
    assert base["choice"] == "PARA"
    assert source_behavior(enc) == "PARA"
    v5 = _v5_request()
    blob = json.dumps(v5["evidence"])
    assert "PARA" not in blob
    assert "hypotheses" not in blob


def test_freeze_hash_is_byte_stable():
    v5 = _v5_request()
    a = validate_v5_request(v5)["request_sha256"]
    b = validate_v5_request(copy.deepcopy(v5))["request_sha256"]
    assert a == b
    k1 = cache_key_v5(dxf_sha256="d" * 64, api_payload_sha256="e" * 64)
    k2 = cache_key_v5(dxf_sha256="d" * 64, api_payload_sha256="e" * 64)
    assert k1 == k2


def test_state_size_gate():
    v5 = _v5_request()
    v5["evidence"]["wall"]["blob"] = "x" * 20000
    with pytest.raises(ValueError, match="16kb"):
        validate_v5_request(v5)
