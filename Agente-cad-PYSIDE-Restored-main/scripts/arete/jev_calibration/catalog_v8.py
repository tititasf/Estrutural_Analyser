"""Catalog v8: encounter-identity matching for LV. Does not modify v1–v7."""
from __future__ import annotations

from typing import Any

from .hashing import sha256_json
from .schemas import CATALOG_SCHEMA, JEV_MODEL

CATALOG_V8_REVISION = "v8-2026-09-30-lv-encounter-identity"
FACTORY_V8_VERSION = "0.9.0-lv-encounter-identity"
V8_REQUEST_SCHEMA = "jev_lv_encounter_identity_request/v8"
V8_AUDIT_SCHEMA = "jev_lv_encounter_identity_audit/v8"
V8_STATUS_SCHEMA = "jev_lv_encounter_identity_status/v8"
V8_MATCH_SCHEMA = "jev_lv_encounter_match/v8"

CONTROL_ID = "endpoint_facts_removed"
MAX_PAIRED_PACKETS = 4

N1_CONTRACT_IDS = ("A_PARA", "B_PARA", "A_PASSA", "B_PASSA")

CATALOG_V8: dict[str, Any] = {
    "schema": CATALOG_SCHEMA,
    "revision": CATALOG_V8_REVISION,
    "model_recorded": JEV_MODEL,
    "note": (
        "LV v8 matches one source encounter (beam, face, wall handle, "
        "endpoint) to N1 four-contract provenance. Wall handle, near "
        "endpoint, locator cover and whole-wall sets do not authorize a "
        "verdict. Pillar contact is not automatic PARA (G10/D-48: PARA "
        "never stops on short C/D faces). Jev remains an optional adviser; "
        "this revision is dry-run identity only."
    ),
    "classes": {
        "LV": {
            "unit": "source_encounter",
            "catalog_id": "lv_encounter_identity_four_contracts",
            "campo": "lv_encounter",
            "primitive": "Choice",
            "criteria_ids": [
                "LISTED_GAP_AT_ENDPOINT",
                "LISTED_COLINEAR_CONTINUATION",
                "PILLAR_PRESENT_BEHAVIOR_UNDECIDED",
                "INSUFFICIENT",
            ],
            "pack_gate": (
                "Pack only when encounter identity is unique, N1 endpoint "
                "correspondence is exact (not near/cover/handle/set), four "
                "contracts are extracted with provenance, G10 short-face is "
                "resolved whenever a pillar is listed, and N1/SA origin stays "
                "outside the Jev payload. Missing N1 is ABSTAIN, never inferred."
            ),
            "n1_contracts": list(N1_CONTRACT_IDS),
            "face_rule": "contract_side_equals_source_face",
            "g10_rule": "para_never_stops_on_pillar_short_faces_CD",
            "discovery": "source_encounter_plus_four_n1_contracts",
        },
    },
}


def catalog_v8_hash() -> str:
    return sha256_json(CATALOG_V8)


def lv_v8_question() -> dict[str, Any]:
    return {
        "instructions": (
            "For this one listed wall handle and this one listed endpoint of "
            "this labeled beam, which listed FACT pattern is present? Use only "
            "listed handles, coordinates and points. A listed pillar marker at "
            "the endpoint does not by itself prove PARA: PARA stops on long "
            "pillar faces A/B/E/F/G/H and continues along short C/D faces "
            "(G10). The opposite endpoint is a different encounter. If the "
            "listed facts are empty, mixed, or the short-face flag is absent "
            "while a pillar is listed, choose INSUFFICIENT."
        ),
        "criteria": {
            "LISTED_GAP_AT_ENDPOINT": (
                "A listed strip-width gap polyline is present at this same "
                "endpoint and listed colinear continuations are empty here."
            ),
            "LISTED_COLINEAR_CONTINUATION": (
                "A listed colinear open wall continues through this same "
                "endpoint and listed gaps are empty here."
            ),
            "PILLAR_PRESENT_BEHAVIOR_UNDECIDED": (
                "A listed pillar marker is present at this endpoint and the "
                "listed facts do not include a resolved short-face/G10 flag, "
                "so PARA versus PASSA stays undecided."
            ),
            "INSUFFICIENT": (
                "The listed FACT objects do not uniquely support one of the "
                "other choices at this single encounter."
            ),
        },
    }
