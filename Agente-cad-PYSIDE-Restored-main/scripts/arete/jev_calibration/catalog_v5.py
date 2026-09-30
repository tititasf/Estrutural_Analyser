"""Catalog v5: blinded single-outcome LV PARA/PASSA/INSUFFICIENT.

Preserves v1–v4 catalogs and pack-gates. This catalog does not emit
same-encounter exclusive Choice packets (v3) or two-name wall Choice.
"""
from __future__ import annotations

from typing import Any

from .hashing import sha256_json
from .schemas import CATALOG_SCHEMA, JEV_MODEL

CATALOG_V5_REVISION = "v5-2026-09-30-lv-blinded-single-outcome"
FACTORY_V5_VERSION = "0.7.0-lv-blinded-single-outcome"
V5_REQUEST_SCHEMA = "jev_lv_blinded_single_outcome_request/v5"
V5_RESULT_SCHEMA = "jev_lv_blinded_single_outcome_result/v5"
V5_AUDIT_SCHEMA = "jev_lv_blinded_single_outcome_audit/v5"

CATALOG_V5: dict[str, Any] = {
    "schema": CATALOG_SCHEMA,
    "revision": CATALOG_V5_REVISION,
    "model_recorded": JEV_MODEL,
    "note": (
        "Blinded corroboration of ONE source-supported endpoint behavior. "
        "Jev sees FACT geometry/topology plus explicit PARA/PASSA definitions. "
        "Deterministic CAD hypothesis and N1 sidecar stay outside Jev state. "
        "v3 packed-0 remains a same-encounter conflict pack-gate result."
    ),
    "classes": {
        "LV": {
            "unit": "source_encounter",
            "catalog_id": "lv_blinded_single_outcome_para_passa",
            "campo": "endpoint_behavior",
            "primitive": "Choice",
            "criteria_ids": ["PARA", "PASSA", "INSUFFICIENT"],
            "pack_gate": (
                "At most four encounters with exactly one source-supported "
                "PARA xor PASSA. Exclude LIKELY_OVER_EXPANDED_STRIP and "
                "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP. SHARED_JOINT only with "
                "this beam label in-strip. Freeze source selection before N1."
            ),
            "max_encounters": 4,
            "max_api_calls": 8,
            "control_id": "decisive_facts_removed",
        },
    },
}


def catalog_v5_hash() -> str:
    return sha256_json(CATALOG_V5)
