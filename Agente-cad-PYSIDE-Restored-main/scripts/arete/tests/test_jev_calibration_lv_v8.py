"""v8 encounter-identity matcher. No live Jev API. Frozen v1–v7 files stay read-only."""
from __future__ import annotations

import json

from scripts.arete.jev_calibration.adapters_lv_v8 import (
    ABSTAIN_COVER,
    ABSTAIN_G10,
    ABSTAIN_HANDLE_ONLY,
    ABSTAIN_MISSING_N1,
    ABSTAIN_NEAR_ONLY,
    ABSTAIN_PILLAR,
    ABSTAIN_SET_LEVEL,
    MATCHED,
    build_identity_request,
    extract_four_contracts,
    match_encounter,
    scan_v8_leakage,
)
from scripts.arete.jev_calibration.catalog_v1 import CATALOG
from scripts.arete.jev_calibration.catalog_v3 import CATALOG_V3
from scripts.arete.jev_calibration.catalog_v6 import CATALOG_V6
from scripts.arete.jev_calibration.catalog_v8 import CATALOG_V8, CATALOG_V8_REVISION
from scripts.arete.jev_calibration.runner import api_payload
from scripts.arete.jev_sa_second_read import validate_request

WALL = [[4708.59, 3103.025], [4708.59, 3188.025]]
SOUTH = [4708.59, 3103.025]
NORTH = [4708.59, 3188.025]


def _source(*, at, handle="2F6", face="A", beam="V420", pav="14_PAV",
            gaps=None, conts=None, pillars=None, face_curta=None, set_level=False):
    facts = {
        "gap_handles": list(gaps or []),
        "continuation_handles": list(conts or []),
        "pillar_markers": [
            {"handle": h, "text": "P16", "xy": at} for h in (pillars or [])
        ],
        "label_handle": "L1",
        "label_xy": [8.0, 7.0],
        "wall_etype": "LWPOLYLINE",
    }
    if face_curta is not None:
        facts["face_lateral_curta"] = face_curta
    return {
        "encounter_id": f"{pav}|LV|{beam}|enc|{handle}|{face}|{at[0]:.3f},{at[1]:.3f}",
        "pavimento": pav,
        "beam": beam,
        "face": face,
        "wall_handle": handle,
        "at": at,
        "wall_segment": WALL,
        "partner_handle": "P1",
        "facts": facts,
        "set_level": set_level,
    }


def _seg(points, *, side="A", behavior="PARA", key="viga_a_seg_1_comprimento_total",
         face_curta=None, flags=None):
    cell = {"flags": list(flags or []), "support_start": {}, "support_end": {}, "pillar_openings": []}
    if face_curta is not None:
        cell["face_lateral_curta"] = face_curta
    return {
        "side": side,
        "behavior": behavior,
        "contract_id": f"LV_{side}_{behavior}",
        "source_key": key,
        "points": points,
        "lv_cell": cell,
        "segment_index": 1,
    }


def _n1_from_links(segments_by_cid: dict):
    links = {}
    suffix = {"PARA": "comprimento_total", "PASSA": "comp_total_passa"}
    for cid, segs in segments_by_cid.items():
        side, behavior = cid.split("_", 1)
        for index, seg in enumerate(segs, 1):
            key = f"viga_{side.lower()}_seg_{index}_{suffix[behavior]}"
            entry = dict(seg)
            links[key] = {f"seg_side_{side.lower()}": [entry]}
    return extract_four_contracts({"links": links})


def test_v8_catalog_distinct_from_prior():
    assert CATALOG["revision"] != CATALOG_V8["revision"]
    assert CATALOG_V3["revision"] != CATALOG_V8["revision"]
    assert CATALOG_V6["revision"] != CATALOG_V8["revision"]
    assert CATALOG_V8["revision"] == CATALOG_V8_REVISION


def test_same_handle_two_encounters_do_not_mix():
    south = _source(at=SOUTH, gaps=["356"])
    north = _source(at=NORTH, conts=["770"])
    n1 = _n1_from_links({
        "A_PARA": [_seg([SOUTH, [4708.59, 3140.0]], behavior="PARA",
                        key="viga_a_seg_1_comprimento_total")],
        "A_PASSA": [_seg([[4708.59, 3145.0], NORTH], side="A", behavior="PASSA",
                         key="viga_a_seg_1_comp_total_passa")],
        "B_PARA": [],
        "B_PASSA": [],
    })
    south_match = match_encounter(source=south, n1_contracts=n1,
                                  other_source_encounters=[north])
    north_match = match_encounter(source=north, n1_contracts=n1,
                                  other_source_encounters=[south])
    assert south_match["identity"]["at"] == [round(SOUTH[0], 3), round(SOUTH[1], 3)]
    assert north_match["identity"]["at"] == [round(NORTH[0], 3), round(NORTH[1], 3)]
    assert south_match["encounter_id"] != north_match["encounter_id"]
    assert "A_PARA" in south_match["n1_origin"]["matched_contract_ids"]
    assert "A_PASSA" not in south_match["n1_origin"]["matched_contract_ids"]
    assert "A_PASSA" in north_match["n1_origin"]["matched_contract_ids"]
    assert "A_PARA" not in north_match["n1_origin"]["matched_contract_ids"]
    assert south_match["n1_origin"]["matched_contract_ids"] != north_match["n1_origin"]["matched_contract_ids"]


def test_near_or_cover_not_enough():
    south = _source(at=SOUTH, gaps=["356"])
    near_n1 = _n1_from_links({
        "A_PARA": [_seg([[4708.59, 3106.0], [4708.59, 3140.0]], behavior="PARA")],
    })
    near_match = match_encounter(source=south, n1_contracts=near_n1)
    assert near_match["status"] == ABSTAIN_NEAR_ONLY
    assert near_match["pack_ready"] is False

    cover_n1 = _n1_from_links({
        "A_PARA": [_seg(WALL, behavior="PARA")],
        "A_PASSA": [_seg(WALL, behavior="PASSA", key="viga_a_seg_1_comp_total_passa")],
    })
    cover_match = match_encounter(source=south, n1_contracts=cover_n1)
    assert cover_match["status"] == ABSTAIN_COVER
    assert cover_match["semantic_verdict"] is None


def test_short_face_requires_g10_rule():
    south = _source(at=SOUTH, pillars=["P16"])
    n1 = _n1_from_links({
        "A_PARA": [_seg([SOUTH, [4708.59, 3140.0]], behavior="PARA")],
        "A_PASSA": [_seg([[4708.59, 3145.0], NORTH], behavior="PASSA",
                         key="viga_a_seg_1_comp_total_passa")],
        "B_PARA": [_seg([SOUTH, [4708.59, 3140.0]], side="B", behavior="PARA",
                        key="viga_b_seg_1_comprimento_total")],
        "B_PASSA": [_seg([[4708.59, 3145.0], NORTH], side="B", behavior="PASSA",
                         key="viga_b_seg_1_comp_total_passa")],
    })
    unresolved = match_encounter(source=south, n1_contracts=n1)
    assert unresolved["status"] == ABSTAIN_G10
    assert unresolved["pack_ready"] is False
    assert unresolved["semantic_verdict"] is None

    short = _source(at=SOUTH, pillars=["P16"], face_curta=True)
    short_match = match_encounter(source=short, n1_contracts=n1)
    assert short_match["status"] == ABSTAIN_PILLAR
    assert "g10_short_face" in short_match["why"]
    assert short_match["semantic_verdict"] is None

    long_face = _source(at=SOUTH, pillars=["P16"], face_curta=False)
    long_match = match_encounter(source=long_face, n1_contracts=n1)
    assert long_match["status"] == ABSTAIN_PILLAR
    assert "not_automatic_para" in long_match["why"]


def test_missing_data_abstains():
    south = _source(at=SOUTH, gaps=["356"])
    empty = match_encounter(source=south, n1_contracts=extract_four_contracts({}))
    assert empty["status"] == ABSTAIN_MISSING_N1
    handle_only = match_encounter(
        source={"beam": "V420", "face": "A", "wall_handle": "2F6", "pavimento": "14_PAV"},
        n1_contracts=extract_four_contracts({}),
    )
    assert handle_only["status"] == ABSTAIN_HANDLE_ONLY
    wall_set = match_encounter(
        source=_source(at=SOUTH, set_level=True),
        n1_contracts=extract_four_contracts({}),
    )
    assert wall_set["status"] == ABSTAIN_SET_LEVEL


def test_baseline_not_in_payload():
    south = _source(at=SOUTH, gaps=["356"])
    north = _source(at=NORTH, conts=["770"])
    n1 = _n1_from_links({
        "A_PARA": [_seg([SOUTH, [4708.59, 3140.0]], behavior="PARA")],
        "A_PASSA": [_seg([[4708.59, 3145.0], NORTH], behavior="PASSA",
                         key="viga_a_seg_1_comp_total_passa")],
        "B_PARA": [_seg([SOUTH, [4708.59, 3140.0]], side="B", behavior="PARA",
                        key="viga_b_seg_1_comprimento_total")],
        "B_PASSA": [_seg([[4708.59, 3145.0], NORTH], side="B", behavior="PASSA",
                         key="viga_b_seg_1_comp_total_passa")],
    })
    match = match_encounter(source=south, n1_contracts=n1, other_source_encounters=[north])
    assert match["status"] == MATCHED
    packed = build_identity_request(
        match=match,
        source=south,
        identity_base={
            "project_id": "f28c3897-c8df-4bb9-a187-cb090f2c7ec7",
            "pavimento": "14_PAV",
            "source_dxf_sha256": "7ec8a5edd4e5aecc78d60002a7198906c83b0699a4a87084fb9fdc7ac5f36a3b",
        },
        baseline_sa={"value": "A_PARA", "field": "lv_encounter", "source": "test"},
    )
    validate_request(packed["v1_request"])
    payload = api_payload(packed["v1_request"])
    blob = json.dumps(payload).lower()
    assert "baseline_sa" not in payload
    assert "n1_origin" not in payload
    assert "n1_contracts" not in blob
    assert "expected_choice" not in blob
    assert packed["n1_in_payload"] is False
    assert packed["n1_origin"]["visible_to_jev"] is False
    assert packed["n1_origin"]["layer"] == "N1_ORIGIN"
    assert scan_v8_leakage(payload) == []
    assert match["n1_origin"]["matched_contract_ids"] == ["A_PARA"]
