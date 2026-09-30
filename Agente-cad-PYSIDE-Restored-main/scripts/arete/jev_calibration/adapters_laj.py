"""LAJ region conflict discovery from DXF markers. Level convention stays undecided."""
from __future__ import annotations

from typing import Any

from .adapters_pil import ConflictCandidate
from .cad_source import CadEntity, CadSource
from .geometry_util import (
    HEIGHT_RE, LEVEL_RE, compact_entity, expand_bbox, point_in_ring, stable_option_id,
)
from .n1_snapshot import N1Item

SEARCH_RADIUS = 460.0
MAX_CANDIDATES = 8


def _covering_solids(point: list[float], solids: list[CadEntity]) -> list[CadEntity]:
    x, y = float(point[0]), float(point[1])
    covering = []
    for solid in solids:
        if point_in_ring(x, y, solid.points):
            covering.append(solid)
    return covering


def discover_laj(item: N1Item, source: CadSource, *, pavimento: str) -> ConflictCandidate | dict[str, str]:
    labels = source.texts_with_value(item.name)
    if len(labels) != 1:
        return {"item": item.name, "classe": "LAJ", "reason": "NO_UNIQUE_LABEL",
                "detail": f"label_count={len(labels)}"}
    label = labels[0]
    lx, ly = label.xy
    near = source.entities_near(lx, ly, SEARCH_RADIUS, types=["TEXT", "MTEXT", "SOLID", "HATCH", "LWPOLYLINE"])
    levels, heights, solids, excluded = [], [], [], []
    for ent in near:
        text = (ent.text or "").strip()
        if ent.etype == "SOLID":
            solids.append(ent)
            continue
        if ent.handle == label.handle:
            continue
        if LEVEL_RE.fullmatch(text):
            levels.append(ent)
        elif HEIGHT_RE.fullmatch(text):
            heights.append(ent)
        elif text:
            excluded.append({"handle": ent.handle, "text": text, "reason": "not_level_or_height_marker"})
    n1_poly = item.points
    inside = []
    for ent in levels:
        in_poly = point_in_ring(ent.xy[0], ent.xy[1], n1_poly) if n1_poly else False
        grey = _covering_solids(ent.xy, solids)
        inside.append((ent, in_poly, grey))
    inside_levels = [row for row in inside if row[1]]
    unique_inside = sorted({(row[0].text or "").strip() for row in inside_levels})
    if not inside_levels and not levels:
        return {"item": item.name, "classe": "LAJ", "reason": "NO_CANDIDATES"}
    if len(unique_inside) <= 1 and len(inside_levels) <= 1:
        return {"item": item.name, "classe": "LAJ", "reason": "NO_CONFLICT",
                "detail": "single_or_empty_inside_level"}

    alternatives = []
    used = inside_levels or [(row[0], False, row[2]) for row in inside[:MAX_CANDIDATES]]
    for ent, in_poly, grey in used[:MAX_CANDIDATES]:
        nearest_h = min(heights, key=lambda h: abs(h.xy[0] - ent.xy[0]) + abs(h.xy[1] - ent.xy[1])) if heights else None
        alternatives.append(compact_entity(ent, {
            "id": stable_option_id(ent.handle, ent.text or ""),
            "inside_raw_grey_solid": bool(grey),
            "grey_solid_handle": grey[0].handle if grey else None,
            "nearby_height": compact_entity(nearest_h) if nearest_h else None,
        }))
    height_rows = [compact_entity(h, {"role": "height_marker"}) for h in heights[:6]]
    evidence = {
        "target": compact_entity(label, {"role": "slab_label", "name": item.name,
                                         "nearby_height": next((compact_entity(h) for h in heights
                                                                if abs(h.xy[0]-lx)+abs(h.xy[1]-ly) < 80), None)}),
        "direct_elevations": alternatives,
        "height_markers": height_rows,
        "search": {"center": [round(lx, 3), round(ly, 3)], "radius": SEARCH_RADIUS, "units": "dxf_drawing"},
    }
    criteria = {
        row["id"]: (
            f"Elevation {row['text']!r} handle {row['handle']} at {row['xy']}"
            + ("; inside grey SOLID" if row.get("inside_raw_grey_solid") else "; outside grey SOLID")
        )
        for row in alternatives
    }
    criteria["INSUFFICIENT"] = (
        "The supplied source evidence does not determine which elevation belongs to the target region."
    )
    question = {
        "instructions": (
            "Which elevation marker belongs to the named slab region? Both markers may sit inside a broad "
            "N1 polygon that covers more than one drawn region. Use local h= annotations and CAD fill "
            "membership. If the target region has no direct marker, choose INSUFFICIENT. This does not "
            "approve the engineering level convention of a desnivel."
        ),
        "criteria": criteria,
    }
    main_handles = [row["handle"] for row in alternatives if not row.get("inside_raw_grey_solid")]
    unit_id = f"region:{label.handle}"
    case_id = f"{pavimento}|LAJ|{item.name}|laje_nivel|{unit_id}"
    included = [evidence["target"], *alternatives, *height_rows]
    return ConflictCandidate(
        case_id=case_id, classe="LAJ", item=item.name, campo="laje_nivel",
        unit_kind="region", unit_id=unit_id,
        trigger="competing_elevations_in_region",
        severity="high" if item.name == "L410" else "medium",
        alternatives=alternatives, evidence=evidence, included=included, excluded=excluded[:40],
        decisive_handles=main_handles or [alternatives[0]["handle"]],
        question=question,
        physical_unit={"kind": "region", "label_handle": label.handle,
                       "bbox": [round(v, 3) for v in expand_bbox([lx, ly, lx, ly], SEARCH_RADIUS)]},
        cad_rules=["elevation texts from DXF", "grey SOLID membership is graphic region, not level convention"],
        convention_status="CONVENCAO_INDETERMINADA",
    )


def withdrawal_control(candidate: ConflictCandidate) -> dict[str, Any]:
    drop = set(candidate.decisive_handles)
    remaining = [row for row in candidate.evidence["direct_elevations"] if row["handle"] not in drop]
    return {
        "id": "target_elevation_removed",
        "expected_choice": "INSUFFICIENT",
        "evidence": {
            "target": candidate.evidence["target"],
            "direct_elevations": remaining,
            "height_markers": candidate.evidence.get("height_markers") or [],
            "search": candidate.evidence["search"],
            "control_note": "elevation marker of the unfilled/main region removed",
        },
    }


def reversed_control(candidate: ConflictCandidate) -> dict[str, Any] | None:
    rows = list(reversed(candidate.evidence["direct_elevations"]))
    if len(rows) < 2:
        return None
    return {
        "id": "candidate_order_reversed",
        "evidence": {
            "target": candidate.evidence["target"],
            "direct_elevations": rows,
            "height_markers": candidate.evidence.get("height_markers") or [],
            "search": candidate.evidence["search"],
        },
    }
