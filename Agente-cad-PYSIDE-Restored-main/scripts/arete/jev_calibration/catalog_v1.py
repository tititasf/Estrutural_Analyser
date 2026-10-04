"""Catalog v1 of Choice questions and controls. Hypotheses to calibrate, not sealed prompts."""
from __future__ import annotations

from typing import Any

from .hashing import sha256_json
from .schemas import CATALOG_REVISION, CATALOG_SCHEMA, JEV_MODEL

CATALOG: dict[str, Any] = {
    "schema": CATALOG_SCHEMA,
    "revision": CATALOG_REVISION,
    "model_recorded": JEV_MODEL,
    "note": (
        "Choice is the calibrated primitive. Optional Noul/Score companions are "
        "diagnostics only and never vote with Choice or change QA/N1. Item names "
        "are not answer hints."
    ),
    "classes": {
        "PIL": {
            "unit": "contour_or_face",
            "catalog_id": "pil_contour_dimension_choice",
            "campo": "dim",
            "controls": ["decisive_dimension_removed", "candidate_order_reversed"],
        },
        "LAJ": {
            "unit": "region_or_edge",
            "catalog_id": "laj_region_elevation_choice",
            "campo": "laje_nivel",
            "controls": ["target_elevation_removed", "candidate_order_reversed"],
            "convention": "desnivel stays CONVENCAO_INDETERMINADA without a documented rule",
        },
        "LV": {
            "unit": "cell_nearby_line",
            "catalog_id": "lv_cell_nearby_parallel_line",
            "campo": "lv_cell",
            "instructions": (
                "Which listed nearby DXF line, if any, is parallel and adjacent to the "
                "target cell line according to the supplied handles and endpoints? "
                "nearby_lines are open wall segments (closed flag and vertex_count included). "
                "nearby_polygon_edges, if present, are closed source contours whose one "
                "selected edge is parallel; they are source context, not equivalent wall "
                "lines. The beam label is location context. If the source geometry does "
                "not determine a unique relation, choose INSUFFICIENT."
            ),
            "insufficient": "The supplied source evidence does not determine a unique geometric relation.",
            "controls": ["nearby_lines_removed", "candidate_order_reversed", "neighbor_label_only"],
            "pack_gate": (
                "Emit only when a unique source-DXF label lies in or within 40 drawing "
                "units of the strip formed by the target cell and a parallel source-DXF "
                "line. The gate is a source-sufficiency check, not a beam-ownership label."
            ),
            "diagnostics": {
                "noul": {
                    "id": "unique_parallel_pair",
                    "instructions": "Is exactly one listed nearby line parallel and adjacent to the target cell line given the supplied endpoints?",
                    "criteria": {
                        "true": "Exactly one listed nearby line is parallel and adjacent to the target.",
                        "false": "Zero or several listed nearby lines fit the supplied endpoints.",
                    },
                },
                "score": {
                    "id": "endpoint_support",
                    "instructions": "Grade how completely the listed endpoints support a unique parallel pair.",
                    "criteria": [
                        "Endpoints missing or contradictory",
                        "One parallel pair is possible among the listed lines",
                        "Unique parallel pair with both endpoints present",
                    ],
                },
            },
        },
        "FV": {
            "unit": "segment",
            "catalog_id": "fv_segment_local_opening_marker",
            "campo": "fv_segment_local_proof",
            "marker_class": "pillar_name_P_digits",
            "layer_policy": "all_layers_no_filter",
            "instructions": (
                "Which DXF pillar-name marker is local proof of a pillar opening on this "
                "segment contour? The question is only about opening-by-pillar markers. "
                "A beam-wide count is not local proof. Choose a marker whose insert lies "
                "inside the closed contour, or INSUFFICIENT if the source does not decide."
            ),
            "controls": ["local_markers_removed", "candidate_order_reversed"],
        },
    },
}


def catalog_hash() -> str:
    return sha256_json(CATALOG)


def lv_question(line_options: dict[str, str]) -> dict[str, Any]:
    spec = CATALOG["classes"]["LV"]
    criteria = dict(line_options)
    criteria["INSUFFICIENT"] = spec["insufficient"]
    return {"instructions": spec["instructions"], "criteria": criteria}


def lv_diagnostics() -> dict[str, Any]:
    return dict(CATALOG["classes"]["LV"].get("diagnostics") or {})


def fv_question(marker_options: dict[str, str], *, allow_none: bool) -> dict[str, Any]:
    spec = CATALOG["classes"]["FV"]
    criteria = dict(marker_options)
    if allow_none:
        criteria["NONE"] = (
            "Exhaustive inventory of pillar-name texts inside the closed DXF contour "
            "found no opening marker of class pillar_name_P_digits."
        )
    criteria["INSUFFICIENT"] = (
        "The supplied source evidence does not determine a local opening marker on this segment."
    )
    return {"instructions": spec["instructions"], "criteria": criteria}
