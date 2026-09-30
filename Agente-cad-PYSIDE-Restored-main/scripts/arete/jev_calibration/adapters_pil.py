"""PIL contour/face conflict discovery from DXF handles. N1 is only a discord detector."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .cad_source import CadSource
from .geometry_util import (
    BEAM_NAME_RE, compact_entity, expand_bbox, pair_matches, parse_dimension,
    polygon_area, rectangular_sides, stable_option_id, verified_closed_contour_containing,
)
from .n1_snapshot import N1Item

SEARCH_RADIUS = 190.0
MAX_CANDIDATES = 8


@dataclass
class ConflictCandidate:
    case_id: str
    classe: str
    item: str
    campo: str
    unit_kind: str
    unit_id: str
    trigger: str
    severity: str
    alternatives: list[dict[str, Any]]
    evidence: dict[str, Any]
    included: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    decisive_handles: list[str]
    question: dict[str, Any]
    physical_unit: dict[str, Any]
    cad_rules: list[str] = field(default_factory=list)
    discard_reason: str | None = None
    unpackable_reason: str | None = None
    convention_status: str | None = None
    extra_controls: list[dict[str, Any]] = field(default_factory=list)
    catalog_id: str | None = None
    baseline_value: Any = None
    n1_relevance: str | None = None
    n1_relevance_why: str | None = None
    catalog_revision: str | None = None


def _search_box(item: N1Item, source: CadSource) -> tuple[float, float, list[float]]:
    center = item.extras.get("center")
    bbox = item.extras.get("bbox")
    if not center:
        labels = source.texts_with_value(item.name)
        if len(labels) != 1:
            raise ValueError("NO_UNIQUE_LABEL")
        center = labels[0].xy
    if not bbox:
        bbox = [center[0] - SEARCH_RADIUS, center[1] - SEARCH_RADIUS,
                center[0] + SEARCH_RADIUS, center[1] + SEARCH_RADIUS]
    return float(center[0]), float(center[1]), [float(v) for v in bbox]


def discover_pil(item: N1Item, source: CadSource, *, pavimento: str) -> ConflictCandidate | dict[str, str]:
    try:
        cx, cy, bbox = _search_box(item, source)
    except ValueError as exc:
        return {"item": item.name, "classe": "PIL", "reason": str(exc)}
    margin = expand_bbox(bbox, 40.0)
    labels = [e for e in source.texts_in_bbox(*margin) if (e.text or "").strip() == item.name]
    if len(labels) != 1:
        return {"item": item.name, "classe": "PIL", "reason": "NO_UNIQUE_LABEL",
                "detail": f"label_count={len(labels)}"}
    label = labels[0]
    near = source.entities_near(cx, cy, SEARCH_RADIUS, types=["TEXT", "MTEXT", "LWPOLYLINE", "POLYLINE"])
    dim_texts, beam_texts, other_texts, polylines, excluded = [], [], [], [], []
    for ent in near:
        text = (ent.text or "").strip()
        if ent.handle == label.handle:
            continue
        if ent.etype in {"LWPOLYLINE", "POLYLINE"}:
            polylines.append(ent)
            continue
        if parse_dimension(text):
            dim_texts.append(ent)
        elif BEAM_NAME_RE.fullmatch(text):
            beam_texts.append(ent)
        elif text and text != item.name:
            if len(other_texts) < 6:
                other_texts.append(ent)
            else:
                excluded.append({"handle": ent.handle, "text": text, "reason": "neighborhood_cap"})
    contour = verified_closed_contour_containing(label.xy, polylines)
    if contour is None:
        return {
            "item": item.name, "classe": "PIL", "reason": "NEEDS_SOURCE",
            "detail": "no_closed_dxf_loop_contains_label",
        }
    for ent in polylines:
        if ent.handle != contour.handle:
            excluded.append({"handle": ent.handle, "etype": ent.etype,
                             "reason": "unverified_nearby_polyline"})
    sides = rectangular_sides(contour.points)
    matching = [e for e in dim_texts if sides and pair_matches(parse_dimension(e.text), sides)]
    competing = dim_texts
    trigger = None
    severity = "low"
    if len(matching) == 0 and dim_texts:
        trigger = "dimension_texts_incompatible_with_contour"
        severity = "high"
    elif len(matching) > 1:
        trigger = "multiple_contour_compatible_dimensions"
        severity = "medium"
    elif beam_texts and dim_texts:
        trigger = "nearby_beam_text_with_dimension_candidates"
        severity = "medium"
    elif len(dim_texts) > 1:
        trigger = "multiple_dimension_syntax_texts"
        severity = "medium"
    elif not dim_texts:
        return {"item": item.name, "classe": "PIL", "reason": "NO_CANDIDATES"}
    else:
        return {"item": item.name, "classe": "PIL", "reason": "NO_CONFLICT",
                "detail": "single_dimension_candidate"}

    alternatives = []
    for ent in competing[:MAX_CANDIDATES]:
        alternatives.append(compact_entity(ent, {
            "id": stable_option_id(ent.handle, ent.text or ""),
            "is_dimension_syntax": True,
        }))
    for ent in competing[MAX_CANDIDATES:]:
        excluded.append({"handle": ent.handle, "text": ent.text, "reason": "candidate_cap"})
    included = [compact_entity(label, {"role": "pillar_label"})]
    included.append(compact_entity(contour, {
        "role": "verified_closed_polyline_containing_label",
        "point_count": len(contour.points),
        "closed": True,
        "area": round(polygon_area(contour.points), 2),
    }))
    included.extend(alternatives)
    for ent in beam_texts[:4]:
        included.append(compact_entity(ent, {"role": "nearby_beam_label"}))
    evidence = {
        "target": compact_entity(label, {"role": "pillar_label", "name": item.name}),
        "contour_ref": compact_entity(contour, {
            "role": "verified_closed_polyline_containing_label",
            "point_count": len(contour.points),
            "closed": True,
            "area": round(polygon_area(contour.points), 2),
        }),
        "dimension_candidates": alternatives,
        "nearby_beam_labels": [compact_entity(e, {"role": "beam_label"}) for e in beam_texts[:4]],
        "search": {"center": label.xy, "radius": SEARCH_RADIUS, "units": "dxf_drawing"},
    }
    criteria = {row["id"]: f"DXF text {row['text']!r} handle {row['handle']} at {row['xy']}" for row in alternatives}
    criteria["INSUFFICIENT"] = "The supplied source evidence does not determine which text belongs to this contour."
    question = {
        "instructions": (
            "Which dimension text belongs to this pillar contour? The contour is the closed DXF polyline "
            "that contains the unique pillar label. Neighbor beam labels and nearby unverified lines are "
            "not the contour. If the evidence is insufficient, choose INSUFFICIENT. This is a second "
            "reading of source candidates, not approval of N1."
        ),
        "criteria": criteria,
    }
    unit_id = f"contour:{label.handle}"
    case_id = f"{pavimento}|PIL|{item.name}|dim|{unit_id}"
    return ConflictCandidate(
        case_id=case_id, classe="PIL", item=item.name, campo="dim",
        unit_kind="contour", unit_id=unit_id, trigger=trigger, severity=severity,
        alternatives=alternatives, evidence=evidence, included=included, excluded=excluded,
        decisive_handles=[e.handle for e in matching] or [alternatives[0]["handle"]],
        question=question,
        physical_unit={"kind": "contour", "label_handle": label.handle, "bbox": [round(v, 3) for v in margin]},
        cad_rules=["closed DXF loop containing the label", "rectangular sides of that loop vs dimension syntax"],
    )


def withdrawal_control(candidate: ConflictCandidate) -> dict[str, Any]:
    drop = set(candidate.decisive_handles)
    remaining = [row for row in candidate.evidence["dimension_candidates"] if row["handle"] not in drop]
    evidence = {
        "target": candidate.evidence["target"],
        "contour_ref": candidate.evidence["contour_ref"],
        "dimension_candidates": remaining,
        "nearby_beam_labels": candidate.evidence.get("nearby_beam_labels") or [],
        "search": candidate.evidence["search"],
        "control_note": "decisive contour-compatible dimension texts removed",
    }
    return {
        "id": "decisive_dimension_removed",
        "expected_choice": "INSUFFICIENT",
        "evidence": evidence,
    }


def reversed_control(candidate: ConflictCandidate) -> dict[str, Any] | None:
    rows = list(reversed(candidate.evidence["dimension_candidates"]))
    if len(rows) < 2:
        return None
    evidence = dict(candidate.evidence)
    evidence = {
        "target": candidate.evidence["target"],
        "contour_ref": candidate.evidence["contour_ref"],
        "dimension_candidates": rows,
        "nearby_beam_labels": candidate.evidence.get("nearby_beam_labels") or [],
        "search": candidate.evidence["search"],
    }
    return {"id": "candidate_order_reversed", "evidence": evidence}
