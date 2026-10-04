"""Catalog v3: source-first LV encounters. v1/v2 stay regression catalogs."""
from __future__ import annotations

from typing import Any

from .hashing import sha256_json
from .schemas import CATALOG_SCHEMA, JEV_MODEL

CATALOG_V3_REVISION = "v3-2026-09-29-lv-source-encounter"
FACTORY_V3_VERSION = "0.6.0-lv-source-encounter"

N1_OUTCOMES = ("A_PARA", "A_PASSA", "B_PARA", "B_PASSA")

CATALOG_V3: dict[str, Any] = {
    "schema": CATALOG_SCHEMA,
    "revision": CATALOG_V3_REVISION,
    "model_recorded": JEV_MODEL,
    "note": (
        "LV v3 enumerates beam-strip encounters from Fase-1 DXF handles, "
        "endpoints and topology before any N1 comparison. N1 locators never "
        "seed walls, never supply PASSA, and never appear in evidence. "
        "PARA and PASSA are hypotheses at one encounter. v1 = nearby parallel "
        "line; v2 = locator-seeded wall (fail-closed)."
    ),
    "classes": {
        "LV": {
            "unit": "source_encounter",
            "catalog_id": "lv_source_encounter_face_behavior",
            "campo": "lv_cell",
            "instructions": (
                "Which listed N1 cell assignment does the source DXF support "
                "for this one encounter (one wall handle + one endpoint) of "
                "this labeled beam? FACE_A is the strip wall with the smaller "
                "transverse coordinate. PARA means this wall terminates at the "
                "listed gap or pillar of this same endpoint. PASSA means a "
                "listed colinear source wall continues through this same "
                "endpoint without a strip-width gap between them. Evidence at "
                "the opposite endpoint is a different encounter. If the source "
                "does not decide a unique assignment, choose INSUFFICIENT."
            ),
            "insufficient": (
                "The supplied source geometry does not decide a unique N1 cell "
                "assignment among the listed face and behavior options at this "
                "encounter."
            ),
            "controls": ["topology_removed", "candidate_order_reversed", "neighbor_label_only"],
            "pack_gate": (
                "Emit a Jev packet only when two mutually exclusive "
                "source-supported N1 outcomes compete at the same encounter "
                "(same beam, face, wall handle and endpoint), both are backed "
                "by listed source handles, and choosing would change a specific "
                "N1 field. Otherwise audit CAD_REDUNDANT, SOURCE_INSUFFICIENT, "
                "CONVENTION_INDETERMINATE or NOT_N1_DECISION. Locator-cover "
                "length is never encounter-local PASSA. A far-side wall across "
                "a gap is the next encounter, not PASSA of this one."
            ),
            "n1_outcomes": list(N1_OUTCOMES),
            "face_rule": "transverse_min_is_face_a",
            "discovery": "source_first_dxf_label_strip_endpoints",
        },
    },
}


def catalog_v3_hash() -> str:
    return sha256_json(CATALOG_V3)


def lv_v3_question(outcome_options: dict[str, str]) -> dict[str, Any]:
    spec = CATALOG_V3["classes"]["LV"]
    criteria = dict(outcome_options)
    criteria["INSUFFICIENT"] = spec["insufficient"]
    return {"instructions": spec["instructions"], "criteria": criteria}
