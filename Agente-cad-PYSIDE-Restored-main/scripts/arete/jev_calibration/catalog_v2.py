"""Catalog v2: LV cell face×behavior Choice. v1 stays the default regression catalog."""
from __future__ import annotations

from typing import Any

from .hashing import sha256_json
from .schemas import CATALOG_SCHEMA, JEV_MODEL

CATALOG_V2_REVISION = "v2-2026-09-29-lv-cell-encounter-failclosed"
FACTORY_V2_VERSION = "0.5.1-lv-cell-encounter-failclosed"

N1_OUTCOMES = ("A_PARA", "A_PASSA", "B_PARA", "B_PASSA")

CATALOG_V2: dict[str, Any] = {
    "schema": CATALOG_SCHEMA,
    "revision": CATALOG_V2_REVISION,
    "model_recorded": JEV_MODEL,
    "note": (
        "LV v2 asks which N1 cell assignment (face A/B × PARA/PASSA) the source "
        "DXF supports for one wall segment. Candidates come from handles, "
        "endpoints and topology. The N1 baseline field is a discord locator "
        "only and stays outside evidence. Parallel-line adjacency is catalog v1."
    ),
    "classes": {
        "LV": {
            "unit": "cell_face_behavior",
            "catalog_id": "lv_cell_face_behavior_choice",
            "campo": "lv_cell",
            "instructions": (
                "Which listed N1 cell assignment does the source DXF support for "
                "one encounter of the target wall segment of this labeled beam? "
                "FACE_A is the strip wall with the smaller transverse coordinate "
                "(smaller X when the wall is vertical, smaller Y when horizontal). "
                "FACE_B is the other strip wall. PARA and PASSA are per encounter: "
                "PARA means this wall terminates at the listed gap or pillar of "
                "that endpoint; PASSA means a listed colinear source wall continues "
                "through that same encounter. Evidence at opposite endpoints is two "
                "encounters, not two exclusive answers. If the source does not "
                "decide a unique assignment at one encounter, choose INSUFFICIENT."
            ),
            "insufficient": (
                "The supplied source geometry does not decide a unique N1 cell "
                "assignment among the listed face and behavior options."
            ),
            "controls": ["topology_removed", "candidate_order_reversed", "neighbor_label_only"],
            "pack_gate": (
                "Emit a Jev packet only when a unique source LINE/LWPOLYLINE "
                "carries both locator endpoints and two mutually exclusive "
                "source-supported N1 outcomes compete at the same face and the "
                "same encounter. PARA at one endpoint and PASSA at the other are "
                "simultaneously true of separate encounters and must not pack as "
                "N1_DECISION_RELEVANT. Locator-cover length is not encounter-local "
                "PASSA. Otherwise audit CAD_REDUNDANT, SOURCE_INSUFFICIENT or "
                "CONVENTION_INDETERMINATE."
            ),
            "n1_outcomes": list(N1_OUTCOMES),
            "face_rule": "transverse_min_is_face_a",
        },
    },
}


def catalog_v2_hash() -> str:
    return sha256_json(CATALOG_V2)


def lv_v2_question(outcome_options: dict[str, str]) -> dict[str, Any]:
    spec = CATALOG_V2["classes"]["LV"]
    criteria = dict(outcome_options)
    criteria["INSUFFICIENT"] = spec["insufficient"]
    return {"instructions": spec["instructions"], "criteria": criteria}


def outcome_id(face: str, behavior: str) -> str:
    return f"{face}_{behavior}"
