"""Catalog v6: wall-level LV source-set vs N1-set. Does not modify v1–v5."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .hashing import sha256_json
from .lv_wall_ownership_audit import EXPECTED_V3_INVENTORY_SHA
from .schemas import CATALOG_SCHEMA, JEV_MODEL

REPO = Path(__file__).resolve().parents[3]
V3_ROOT = REPO / "scripts" / "arete" / "relatorios" / "20260929_jev_catalog_v3_lv_source_encounter"
OWN_ROOT = REPO / "scripts" / "arete" / "relatorios" / "20260929_jev_lv_source_wall_ownership"

CATALOG_V6_REVISION = "v6-2026-09-30-lv-wall-level-set"
FACTORY_V6_VERSION = "0.8.0-lv-wall-level-set"
V6_REQUEST_SCHEMA = "jev_lv_wall_level_set_request/v6"
V6_AUDIT_SCHEMA = "jev_lv_wall_level_calibration_audit/v6"
V6_STATUS_SCHEMA = "jev_lv_wall_level_calibration_status/v6"

MAX_ROUTED_PACKETS = 4
MAX_API_CALLS = 8
CONTROL_ID = "endpoint_facts_removed"

EXPECTED_V3_SIDECAR_SHA = {
    "13_PAV": "01d007dfd057579ee2e156df34dcfa20ed1ecc4776c6edf2db5a7221912a540d",
    "14_PAV": "7da42e5c421a4ebc63bd3b95847c486bc568f47657c8edae748854b5e01da5e4",
}
EXPECTED_V4_COLLISION_AUDIT_SHA = {
    "13_PAV": "f472d5ffdbef796c241ff2798052b3795ec6788ae591f54b5cabedaa4c4e601b",
    "14_PAV": "aa5eb968aa1d867c81a6aa217d662ea6f5ccdc94f60552c9400265a768a9fa5d",
}

PAVEMENT_SPECS_V6 = {
    "13_PAV": {
        "project_id": "dd238e47-1dc6-4f63-a760-4e7ce19a7386",
        "inventory": V3_ROOT / "dryrun_13pav_lv" / "source_inventory.json",
        "collision": OWN_ROOT / "collision_audit_13_PAV.json",
        "n1_sidecar": V3_ROOT / "dryrun_13pav_lv" / "n1_comparison_sidecar.json",
        "expected_dxf_sha256": "d23381e30eb358cc07e8c140d92db4c06b7be97859e7f9fb3eea2c0bd33151a4",
        "expected_inventory_sha256": EXPECTED_V3_INVENTORY_SHA["13_PAV"],
        "expected_sidecar_sha256": EXPECTED_V3_SIDECAR_SHA["13_PAV"],
        "expected_collision_sha256": EXPECTED_V4_COLLISION_AUDIT_SHA["13_PAV"],
        "parity_claimed": False,
        "role": "development",
    },
    "14_PAV": {
        "project_id": "f28c3897-c8df-4bb9-a187-cb090f2c7ec7",
        "inventory": V3_ROOT / "dryrun_14pav_lv" / "source_inventory.json",
        "collision": OWN_ROOT / "collision_audit_14_PAV.json",
        "n1_sidecar": V3_ROOT / "dryrun_14pav_lv" / "n1_comparison_sidecar.json",
        "expected_dxf_sha256": "7ec8a5edd4e5aecc78d60002a7198906c83b0699a4a87084fb9fdc7ac5f36a3b",
        "expected_inventory_sha256": EXPECTED_V3_INVENTORY_SHA["14_PAV"],
        "expected_sidecar_sha256": EXPECTED_V3_SIDECAR_SHA["14_PAV"],
        "expected_collision_sha256": EXPECTED_V4_COLLISION_AUDIT_SHA["14_PAV"],
        "parity_claimed": False,
        "role": "frozen_regression",
    },
}

CATALOG_V6: dict[str, Any] = {
    "schema": CATALOG_SCHEMA,
    "revision": CATALOG_V6_REVISION,
    "model_recorded": JEV_MODEL,
    "note": (
        "Wall-level set comparison for one unique beam label, source wall "
        "handle and face. Both endpoint hypotheses form a source set; N1 LV "
        "cells mapped to that unique source wall form an N1 set. Endpoint-"
        "to-cell handle matching is invalid. Jev is an optional adviser; "
        "N1 stays out of prompts and source selection. Dry-run routing only."
    ),
    "classes": {
        "LV": {
            "unit": "source_wall_face",
            "catalog_id": "lv_wall_level_behavior_set",
            "campo": "wall_endpoint_set",
            "primitive": "Choice",
            "criteria_ids": ["PARA_ONLY", "PASSA_ONLY", "PARA_AND_PASSA", "INSUFFICIENT"],
            "pack_gate": (
                "Route only when ownership is exclusive/in-strip, source "
                "endpoints are complete XOR, N1 mapping is exact (not cover "
                "or ambiguous), and the source set diverges from the N1 set; "
                "or when source endpoint facts are ambiguous and listed "
                "handles can resolve them. Shared joints and unknown owners "
                "abstain. A routing queue is not an accuracy claim."
            ),
            "max_routed_packets": MAX_ROUTED_PACKETS,
            "max_api_calls": MAX_API_CALLS,
            "control_id": CONTROL_ID,
            "execute_default": False,
        },
    },
}


def catalog_v6_hash() -> str:
    return sha256_json(CATALOG_V6)
