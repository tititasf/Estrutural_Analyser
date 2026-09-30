"""FV segment local-proof discovery. Pack only with a concrete N1 claim and a closed DXF contour."""
from __future__ import annotations

import re
from typing import Any

from .adapters_pil import ConflictCandidate
from .cad_source import CadSource
from .catalog_v1 import CATALOG, fv_question
from .geometry_util import (
    PILLAR_NAME_RE, compact_entity, is_closed_loop, match_dxf_polygon, midpoint,
    point_in_ring, rounded_points, stable_option_id,
)
from .n1_snapshot import N1Item

MAX_UNITS = 3
NEAR_CM = 8.0
OPENING_CLAIM = re.compile(r"(\d+)\s*interferencia", re.IGNORECASE)


def opening_claim(seg: dict) -> dict[str, Any] | None:
    statement = str(seg.get("statement") or "")
    count = seg.get("claimed_count")
    match = OPENING_CLAIM.search(statement)
    if match:
        count = int(match.group(1))
    if count is None:
        return None
    try:
        count_i = int(count)
    except (TypeError, ValueError):
        return None
    return {"kind": "opening_pillar", "count": count_i, "text": statement or f"{count_i} interferencia(s) por pilar"}


def discover_fv(item: N1Item, source: CadSource, *, pavimento: str
                ) -> list[ConflictCandidate] | dict[str, str]:
    labels = source.texts_with_value(item.name)
    if len(labels) != 1:
        return {"item": item.name, "classe": "FV", "reason": "NO_UNIQUE_LABEL",
                "detail": f"label_count={len(labels)}"}
    label = labels[0]
    segments = list(item.extras.get("segments") or [])
    audit = item.extras.get("scope_audit") or {}
    if audit.get("segments"):
        by_index = {int(s["index"]): s for s in audit["segments"] if s.get("index") is not None}
        for seg in segments:
            try:
                idx = int(seg.get("index"))
            except (TypeError, ValueError):
                continue
            if idx in by_index:
                overlay = by_index[idx]
                if overlay.get("claimed_count") is not None:
                    seg["claimed_count"] = overlay["claimed_count"]
                if overlay.get("statement"):
                    seg["statement"] = overlay["statement"]
    claimed_rows = []
    for seg in segments:
        claim = opening_claim(seg)
        if claim is None:
            continue
        pts = seg.get("points") or []
        contour = match_dxf_polygon(source, pts)
        verts = rounded_points(contour.points) if contour is not None else None
        if contour is None or not is_closed_loop(contour) or verts is None:
            claimed_rows.append(("needs", seg, claim, None, None))
            continue
        claimed_rows.append(("ok", seg, claim, contour, verts))
    if not claimed_rows:
        return {"item": item.name, "classe": "FV", "reason": "NO_CONFLICT",
                "detail": "no_concrete_per_segment_opening_claim"}
    ok = [row for row in claimed_rows if row[0] == "ok"]
    if not ok:
        return {"item": item.name, "classe": "FV", "reason": "NEEDS_SOURCE",
                "detail": "opening_claim_without_closed_dxf_contour"}
    leftover = [{"index": row[1].get("index"), "reason": "no_closed_dxf_contour"}
                for row in claimed_rows if row[0] != "ok"]
    chosen = ok[:MAX_UNITS]
    leftover.extend({"index": row[1].get("index"), "reason": "unit_cap"} for row in ok[MAX_UNITS:])
    continuity = [str(row[1].get("index")) for row in ok]
    packets = []
    for _status, seg, claim, contour, verts in chosen:
        packet = _packet(item, pavimento, label, seg, claim, contour, verts, source, continuity, leftover)
        if packet is None:
            leftover.append({"index": seg.get("index"), "reason": "cannot_form_two_choices"})
            continue
        packets.append(packet)
    if not packets:
        return {"item": item.name, "classe": "FV", "reason": "NEEDS_SOURCE",
                "detail": "claim_present_but_no_packable_choice_set"}
    return packets


def _inventory(source: CadSource, contour, verts: list, label_handle: str) -> dict[str, Any]:
    spec = CATALOG["classes"]["FV"]
    cx, cy = contour.xy
    span = max(contour.maxx - contour.minx, contour.maxy - contour.miny) / 2.0 + NEAR_CM
    texts = source.entities_near(cx, cy, span, types=["TEXT", "MTEXT"])
    local, excluded = [], []
    for ent in texts:
        if ent.handle == label_handle:
            continue
        text = (ent.text or "").strip()
        if not text:
            continue
        inside = point_in_ring(ent.xy[0], ent.xy[1], contour.points)
        if inside and PILLAR_NAME_RE.fullmatch(text):
            local.append(ent)
        elif inside:
            excluded.append({"handle": ent.handle, "text": text, "reason": "inside_not_pillar_opening_marker"})
        elif PILLAR_NAME_RE.fullmatch(text):
            excluded.append({"handle": ent.handle, "text": text, "reason": "pillar_outside_segment"})
    exhaustive = bool(is_closed_loop(contour) and verts and len(verts) >= 3)
    return {
        "marker_class": spec["marker_class"],
        "spatial_scope": "point_in_closed_dxf_contour",
        "layer_policy": spec["layer_policy"],
        "texts_tested_in_bbox": len(texts),
        "closed_contour": True,
        "vertex_count": len(verts),
        "exhaustive": exhaustive,
        "local": local,
        "excluded": excluded,
    }


def _packet(item, pavimento, label, seg, claim, contour, verts, source, continuity, leftover
            ) -> ConflictCandidate | None:
    inv = _inventory(source, contour, verts, label.handle)
    local, excluded = inv.pop("local"), inv.pop("excluded")
    excluded.extend(leftover)
    markers = [compact_entity(e, {
        "id": stable_option_id(e.handle, e.text or ""),
        "role": "local_opening_marker",
    }) for e in local[:8]]
    allow_none = bool(inv["exhaustive"] and not markers)
    option_rows = {row["id"]: f"Opening marker {row['text']!r} handle {row['handle']} at {row['xy']}"
                   for row in markers}
    question = fv_question(option_rows, allow_none=allow_none)
    if len(question["criteria"]) < 2:
        return None
    if "NONE" in question["criteria"] and not inv["exhaustive"]:
        return None
    unit_id = f"segment:{seg.get('index')}"
    case_id = f"{pavimento}|FV|{item.name}|fv_segment|{unit_id}"
    target = compact_entity(contour, {
        "role": "segment_contour", "index": seg.get("index"),
        "point_count": len(verts), "closed": True, "points": verts,
    })
    evidence = {
        "target": target,
        "beam_label": compact_entity(label, {"role": "beam_label"}),
        "local_markers": markers,
        "inventory": inv,
        "search": {"center": midpoint(seg.get("points") or verts), "units": "dxf_drawing"},
        "continuity_index": continuity,
    }
    extra = []
    if markers:
        extra.append({
            "id": "local_markers_removed",
            "expected_choice": "INSUFFICIENT",
            "evidence": {
                "target": target,
                "beam_label": evidence["beam_label"],
                "local_markers": [],
                "inventory": inv,
                "search": evidence["search"],
                "continuity_index": continuity,
                "control_note": "local pillar-opening markers removed",
            },
        })
    return ConflictCandidate(
        case_id=case_id, classe="FV", item=item.name, campo="fv_segment_local_proof",
        unit_kind="segment", unit_id=unit_id,
        trigger="per_segment_opening_claim",
        severity="high",
        alternatives=markers, evidence=evidence,
        included=[target, evidence["beam_label"], *markers],
        excluded=excluded[:40],
        decisive_handles=[e.handle for e in local] if local else [contour.handle],
        question=question,
        physical_unit={"kind": "segment", "index": seg.get("index"), "continuity_index": continuity,
                       "claim_kind": "opening_pillar"},
        cad_rules=["closed DXF contour associated to this N1 segment",
                   "local proof is a pillar-name marker inside that contour"],
        extra_controls=extra,
        catalog_id="fv_segment_local_opening_marker",
        baseline_value=claim["text"],
    )


def withdrawal_control(candidate: ConflictCandidate) -> dict[str, Any]:
    if candidate.evidence.get("local_markers"):
        return {
            "id": "local_markers_removed",
            "expected_choice": "INSUFFICIENT",
            "evidence": {
                "target": candidate.evidence["target"],
                "beam_label": candidate.evidence["beam_label"],
                "local_markers": [],
                "inventory": candidate.evidence.get("inventory"),
                "search": candidate.evidence["search"],
                "continuity_index": candidate.evidence.get("continuity_index") or [],
                "control_note": "local pillar-opening markers removed",
            },
        }
    target = dict(candidate.evidence["target"])
    withdrawn = {**target, "role": "contour_withdrawn", "points": []}
    return {
        "id": "contour_removed",
        "expected_choice": "INSUFFICIENT",
        "evidence": {
            "target": withdrawn,
            "beam_label": candidate.evidence["beam_label"],
            "local_markers": [],
            "inventory": {**(candidate.evidence.get("inventory") or {}), "exhaustive": False,
                          "closed_contour": False},
            "search": candidate.evidence["search"],
            "continuity_index": candidate.evidence.get("continuity_index") or [],
            "control_note": "closed contour vertices removed; NONE is no longer licensed",
        },
    }


def reversed_control(candidate: ConflictCandidate) -> dict[str, Any] | None:
    rows = list(reversed(candidate.evidence.get("local_markers") or []))
    if len(rows) < 2:
        return None
    return {
        "id": "candidate_order_reversed",
        "evidence": {
            "target": candidate.evidence["target"],
            "beam_label": candidate.evidence["beam_label"],
            "local_markers": rows,
            "inventory": candidate.evidence.get("inventory"),
            "search": candidate.evidence["search"],
            "continuity_index": candidate.evidence.get("continuity_index") or [],
        },
    }
