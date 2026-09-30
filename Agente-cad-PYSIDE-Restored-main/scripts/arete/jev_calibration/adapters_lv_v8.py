"""v8 fail-closed LV encounter identity. Does not modify v1–v7 or N1.

Input: one local source encounter plus the four N1 contracts/links.
Output: identified encounter with provenance, or ABSTAIN with a reason.
Handle, near, cover and whole-wall sets never authorize a verdict.
Missing N1 semantics are not inferred. SA/contract origin stays out of
the Jev evidence payload.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any

from scripts.arete.jev_sa_second_read import MODEL, validate_request

from .catalog_v8 import (
    CATALOG_V8_REVISION,
    CONTROL_ID,
    FACTORY_V8_VERSION,
    N1_CONTRACT_IDS,
    V8_MATCH_SCHEMA,
    V8_REQUEST_SCHEMA,
    catalog_v8_hash,
    lv_v8_question,
)
from .hashing import sha256_json
from .leakage import scan_evidence_leakage, scan_semantic_leakage
from .runner import api_payload, cache_key

COORD_NDIGITS = 3
NEAR_TOL = 6.0
ON_SEG_TOL = 0.5
LINK_RE = re.compile(
    r"^viga_([ab])_seg_(\d+)_(comprimento_total|comp_total_passa)$",
    re.IGNORECASE,
)

ABSTAIN_HANDLE_ONLY = "ABSTAIN_HANDLE_ONLY"
ABSTAIN_NEAR_ONLY = "ABSTAIN_NEAR_ONLY"
ABSTAIN_COVER = "ABSTAIN_COVER"
ABSTAIN_SET_LEVEL = "ABSTAIN_SET_LEVEL"
ABSTAIN_IDENTITY = "ABSTAIN_IDENTITY_INCOMPLETE"
ABSTAIN_MISSING_N1 = "ABSTAIN_MISSING_N1"
ABSTAIN_MISSING_CONTRACT = "ABSTAIN_MISSING_N1_CONTRACT"
ABSTAIN_AMBIGUOUS = "ABSTAIN_AMBIGUOUS_ENCOUNTER"
ABSTAIN_G10 = "ABSTAIN_FACE_CURTA_UNRESOLVED"
ABSTAIN_PILLAR = "ABSTAIN_PILLAR_CONTACT_NOT_AUTO_PARA"
ABSTAIN_FOREIGN = "ABSTAIN_FOREIGN_SEGMENT"
ABSTAIN_FACE = "ABSTAIN_FACE_MISMATCH"
MATCHED = "MATCHED_ENCOUNTER"

V8_FORBIDDEN_EVIDENCE_KEYS = {
    "baseline_sa", "sa_value", "sa_level", "ground_truth", "qa_verdict",
    "expected_choice", "qa_score", "gabarito", "n1_value", "sa_choice",
    "hypotheses", "n1_origin", "n1_contracts", "n1_outcomes", "n1_set",
    "n1_cell_matches", "source_outcomes", "n1_field_would_change",
}
V8_LEAK_TOKENS = (
    "n1 says", "qa score", "gabarito", "expected_choice", "baseline_sa",
    "n1_origin", "n1_contracts", "source_outcomes", "n1_locator",
)


class EncounterIdentityInvalid(ValueError):
    """Caller mixed set-level or incomplete identity into the matcher."""


def _norm_handle(handle: str | None) -> str:
    return str(handle or "").strip().upper()


def _norm_face(raw: Any) -> str | None:
    text = str(raw or "").strip().upper()
    return text if text in {"A", "B"} else None


def _norm_behavior(raw: Any) -> str | None:
    text = str(raw or "").strip().upper()
    if text in {"PARA", "PASSA"}:
        return text
    if text == "COMPRIMENTO_TOTAL":
        return "PARA"
    if text == "COMP_TOTAL_PASSA":
        return "PASSA"
    return None


def round_xy(pt: Any) -> list[float] | None:
    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
        return None
    try:
        values = [float(pt[0]), float(pt[1])]
        if not all(math.isfinite(value) for value in values):
            return None
        return [round(value, COORD_NDIGITS) for value in values]
    except (TypeError, ValueError):
        return None


def pts_equal(a: Any, b: Any) -> bool:
    ra, rb = round_xy(a), round_xy(b)
    return ra is not None and rb is not None and ra == rb


def dist(a: Any, b: Any) -> float:
    ra, rb = round_xy(a), round_xy(b)
    if ra is None or rb is None:
        return float("inf")
    return math.hypot(ra[0] - rb[0], ra[1] - rb[1])


def point_on_segment(pt: Any, segment: list | None, *, tol: float = ON_SEG_TOL) -> bool:
    if not isinstance(segment, list) or len(segment) < 2:
        return False
    p = round_xy(pt)
    a = round_xy(segment[0])
    b = round_xy(segment[-1])
    if p is None or a is None or b is None:
        return False
    if pts_equal(p, a) or pts_equal(p, b):
        return True
    vx, vy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(vx, vy)
    if length < 1e-6:
        return dist(p, a) <= tol
    t = ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (length * length)
    if t < -1e-6 or t > 1 + 1e-6:
        return False
    proj = [a[0] + t * vx, a[1] + t * vy]
    return dist(p, proj) <= tol


def encounter_key(*, pavimento: str, beam: str, face: str, wall_handle: str,
                  at: list[float]) -> str:
    xy = round_xy(at) or [0.0, 0.0]
    return (
        f"{pavimento}|LV|{beam}|enc|{_norm_handle(wall_handle)}|{face}|"
        f"{xy[0]:.3f},{xy[1]:.3f}"
    )


def source_encounter_identity(source: dict[str, Any]) -> dict[str, Any] | None:
    if source.get("unit") == "source_wall_face" or source.get("set_level"):
        return None
    face = _norm_face(source.get("face") or source.get("side"))
    handle = _norm_handle(source.get("wall_handle") or source.get("handle"))
    at = round_xy(source.get("at") or source.get("endpoint"))
    beam = str(source.get("beam") or source.get("item") or "").strip()
    pavimento = str(source.get("pavimento") or "").strip()
    wall = source.get("wall_segment") or source.get("segment") or []
    if not pavimento or not beam or face is None or not handle or at is None:
        return None
    if not isinstance(wall, (list, tuple)) or len(wall) < 2:
        return None
    first, last = round_xy(wall[0]), round_xy(wall[-1])
    if first is None or last is None or first == last or at not in (first, last):
        return None
    return {
        "pavimento": pavimento,
        "beam": beam,
        "face": face,
        "wall_handle": handle,
        "at": at,
        "encounter_id": str(source.get("encounter_id") or encounter_key(
            pavimento=pavimento, beam=beam, face=face, wall_handle=handle, at=at,
        )),
        "wall_segment": wall,
    }


def _contract_id(side: str, behavior: str) -> str:
    return f"{side}_{behavior}"


def _segment_row(entry: dict[str, Any], *, side: str, behavior: str,
                 source_key: str | None, origin: str) -> dict[str, Any]:
    cell = entry.get("lv_cell") if isinstance(entry.get("lv_cell"), dict) else {}
    points = entry.get("points") or []
    return {
        "side": side,
        "behavior": behavior,
        "contract_id": entry.get("contract_id") or f"LV_{side}_{behavior}",
        "source_key": source_key or entry.get("source_key"),
        "source_slot": entry.get("source_slot") or f"seg_side_{side.lower()}",
        "index": entry.get("segment_index") or entry.get("index"),
        "points": points,
        "origin": origin,
        "support_start": cell.get("support_start") or entry.get("support_start") or {},
        "support_end": cell.get("support_end") or entry.get("support_end") or {},
        "flags": list(cell.get("flags") or entry.get("flags") or []),
        "pillar_openings": list(cell.get("pillar_openings") or []),
        "face_curta": _face_curta_from_entry(entry, cell),
    }


def _face_curta_from_entry(entry: dict[str, Any], cell: dict[str, Any]) -> bool | None:
    for blob in (cell, entry, cell.get("support_start") or {}, cell.get("support_end") or {}):
        if not isinstance(blob, dict):
            continue
        if "face_lateral_curta" in blob:
            val = blob.get("face_lateral_curta")
            return None if val is None else bool(val)
        por_lado = blob.get("face_curta_por_lado")
        if isinstance(por_lado, dict):
            side = str(entry.get("side") or "").upper()
            if side in por_lado:
                val = por_lado.get(side)
                return None if val is None else bool(val)
        flags = blob.get("flags") or []
        if any("G10_face_curta" in str(flag) for flag in flags):
            return True
        rule = str(blob.get("rule") or "")
        if "G10_face_curta" in rule:
            return True
        for opening in blob.get("pillar_openings") or []:
            if isinstance(opening, dict) and "G10_face_curta" in str(opening.get("rule") or ""):
                return True
    return None


def extract_four_contracts(n1: dict[str, Any] | None) -> dict[str, Any]:
    """Read A/B × PARA/PASSA from published contracts or SA links. No inference."""
    empty = {
        cid: {"present": False, "origin": None, "segments": [], "endpoint_events": [],
              "endpoint_labels": {}, "generation_ready": None}
        for cid in N1_CONTRACT_IDS
    }
    if not isinstance(n1, dict):
        return {"schema": "jev_lv_n1_four_contracts/v8", "contracts": empty,
                "present_ids": [], "missing_ids": list(N1_CONTRACT_IDS),
                "origin": "absent"}
    payload = n1.get("data") or n1.get("payload") or n1
    links = payload.get("links") if isinstance(payload.get("links"), dict) else n1.get("links") or {}
    published = payload.get("lv_generation_contracts")
    contracts = copy.deepcopy(empty)
    origin = "absent"
    if isinstance(published, dict):
        origin = "lv_generation_contracts"
        for behavior_raw, sides in published.items():
            behavior = _norm_behavior(behavior_raw)
            if not behavior or not isinstance(sides, dict):
                continue
            for side_raw, cell in sides.items():
                side = _norm_face(side_raw)
                if side is None or not isinstance(cell, dict):
                    continue
                cid = _contract_id(side, behavior)
                segs = []
                for entry in cell.get("structural_segments") or []:
                    if isinstance(entry, dict):
                        segs.append(_segment_row(
                            entry, side=side, behavior=behavior,
                            source_key=entry.get("source_key"), origin=origin,
                        ))
                contracts[cid] = {
                    "present": bool(segs) or bool(cell.get("contract_id")),
                    "origin": origin,
                    "contract_id": cell.get("contract_id") or f"LV_{side}_{behavior}",
                    "side": side,
                    "behavior": behavior,
                    "segments": segs,
                    "endpoint_events": list(cell.get("endpoint_events") or []),
                    "endpoint_labels": dict(cell.get("endpoint_labels") or {}),
                    "generation_ready": cell.get("generation_ready"),
                    "sa_meta": cell.get("_sa_meta") or {},
                }
    if isinstance(links, dict):
        link_origin = "links"
        grouped: dict[str, list] = {cid: [] for cid in N1_CONTRACT_IDS}
        for key, slots in links.items():
            match = LINK_RE.match(str(key))
            if not match or not isinstance(slots, dict):
                continue
            side = _norm_face(match.group(1))
            behavior = _norm_behavior(match.group(3))
            if side is None or behavior is None:
                continue
            cid = _contract_id(side, behavior)
            slot = f"seg_side_{side.lower()}"
            entries = slots.get(slot) or []
            for entry in entries if isinstance(entries, list) else []:
                if isinstance(entry, dict):
                    grouped[cid].append(_segment_row(
                        entry, side=side, behavior=behavior, source_key=str(key),
                        origin=link_origin,
                    ))
        for cid, segs in grouped.items():
            if segs and not contracts[cid]["segments"]:
                origin = "links" if origin == "absent" else origin
                side, behavior = cid.split("_", 1)
                contracts[cid] = {
                    "present": True,
                    "origin": "links",
                    "contract_id": f"LV_{side}_{behavior}",
                    "side": side,
                    "behavior": behavior,
                    "segments": segs,
                    "endpoint_events": [],
                    "endpoint_labels": {},
                    "generation_ready": None,
                    "sa_meta": {},
                }
            elif segs and contracts[cid]["present"]:
                existing_keys = {s.get("source_key") for s in contracts[cid]["segments"]}
                for row in segs:
                    if row.get("source_key") not in existing_keys:
                        contracts[cid]["segments"].append(row)
    present = [cid for cid, row in contracts.items() if row.get("present")]
    return {
        "schema": "jev_lv_n1_four_contracts/v8",
        "contracts": contracts,
        "present_ids": present,
        "missing_ids": [cid for cid in N1_CONTRACT_IDS if cid not in present],
        "origin": origin,
        "lv_interpreter_contract_version": payload.get("lv_interpreter_contract_version"),
        "lv_cells_version": payload.get("lv_cells_version"),
        "beam_name": payload.get("name") or payload.get("beam_name"),
        "project_id": payload.get("project_id"),
    }


def classify_segment_vs_encounter(points: list, identity: dict[str, Any]) -> str:
    if not isinstance(points, list) or len(points) < 2:
        return "MISS"
    a, b = points[0], points[-1]
    at = identity["at"]
    wall = identity.get("wall_segment") or []
    covers_endpoints = False
    if isinstance(wall, list) and len(wall) >= 2:
        w0, w1 = wall[0], wall[-1]
        covers_endpoints = (
            (pts_equal(a, w0) and pts_equal(b, w1))
            or (pts_equal(a, w1) and pts_equal(b, w0))
        )
        wall_ends_on_seg = point_on_segment(w0, [a, b]) and point_on_segment(w1, [a, b])
        if covers_endpoints or (wall_ends_on_seg and dist(a, b) >= dist(w0, w1) - ON_SEG_TOL):
            return "COVER"
    exact_a, exact_b = pts_equal(a, at), pts_equal(b, at)
    if exact_a or exact_b:
        other = b if exact_a else a
        if wall and not point_on_segment(other, wall):
            return "FOREIGN"
        return "EXACT"
    if dist(a, at) <= NEAR_TOL or dist(b, at) <= NEAR_TOL:
        return "NEAR"
    return "MISS"


def _pillar_listed(source: dict[str, Any]) -> bool:
    facts = source.get("facts") or {}
    markers = facts.get("pillar_markers") or source.get("pillar_markers") or []
    return bool(markers)


def _source_face_curta(source: dict[str, Any]) -> bool | None:
    facts = source.get("facts") or {}
    for blob in (source, facts):
        if "face_lateral_curta" in blob:
            val = blob.get("face_lateral_curta")
            return None if val is None else bool(val)
        por_lado = blob.get("face_curta_por_lado")
        if isinstance(por_lado, dict):
            face = _norm_face(source.get("face"))
            if face and face in por_lado:
                val = por_lado.get(face)
                return None if val is None else bool(val)
    return None


def g10_gate(*, source: dict[str, Any], matched_rows: list[dict[str, Any]]) -> tuple[str | None, str]:
    """Pillar contact never auto-PARA. Short-face (C/D) requires an explicit flag."""
    if not _pillar_listed(source):
        return None, "no_listed_pillar"
    source_flag = _source_face_curta(source)
    n1_flags = [row.get("face_curta") for row in matched_rows if row.get("face_curta") is not None]
    if source_flag is True or True in n1_flags:
        return ABSTAIN_PILLAR, "g10_short_face_CD_para_does_not_stop"
    if source_flag is False or False in n1_flags:
        return ABSTAIN_PILLAR, "pillar_contact_not_automatic_para"
    return ABSTAIN_G10, "pillar_listed_face_curta_flag_absent"


def match_encounter(*, source: dict[str, Any], n1_contracts: dict[str, Any],
                    other_source_encounters: list[dict[str, Any]] | None = None
                    ) -> dict[str, Any]:
    """Identify this encounter or ABSTAIN. Does not emit a PARA/PASSA verdict."""
    if source.get("set_level") or source.get("unit") == "source_wall_face":
        return _abstain(source, None, ABSTAIN_SET_LEVEL, "wall_or_set_handle_not_an_encounter")
    if source.get("wall_handle") and not (source.get("at") or source.get("endpoint")):
        return _abstain(source, None, ABSTAIN_HANDLE_ONLY, "handle_without_endpoint")
    identity = source_encounter_identity(source)
    if identity is None:
        return _abstain(source, None, ABSTAIN_IDENTITY, "beam_face_handle_or_at_missing")

    others = other_source_encounters or []
    same_handle = []
    for other in others:
        oid = source_encounter_identity(other)
        if oid is None:
            continue
        if (oid["wall_handle"] == identity["wall_handle"]
                and oid["beam"] == identity["beam"]
                and oid["face"] == identity["face"]):
            if oid["at"] != identity["at"]:
                same_handle.append(oid["encounter_id"])
            elif oid["encounter_id"] != identity["encounter_id"]:
                return _abstain(source, identity, ABSTAIN_AMBIGUOUS,
                                "duplicate_identity_same_handle_and_endpoint")

    extracted = n1_contracts if n1_contracts.get("contracts") else extract_four_contracts(n1_contracts)
    baseline_name = str(extracted.get("beam_name") or "").strip().upper()
    if baseline_name and baseline_name != identity["beam"].upper():
        return _abstain(source, identity, ABSTAIN_IDENTITY, "baseline_beam_name_mismatch")
    if (source.get("project_id") and extracted.get("project_id")
            and source["project_id"] != extracted["project_id"]):
        return _abstain(source, identity, ABSTAIN_IDENTITY, "baseline_project_id_mismatch")
    contracts = extracted.get("contracts") or {}
    exact_rows: list[dict[str, Any]] = []
    near_rows: list[dict[str, Any]] = []
    cover_rows: list[dict[str, Any]] = []
    foreign_rows: list[dict[str, Any]] = []
    face_mismatch: list[dict[str, Any]] = []
    for cid, cell in contracts.items():
        for seg in cell.get("segments") or []:
            side = _norm_face(seg.get("side") or cell.get("side"))
            kind = classify_segment_vs_encounter(seg.get("points") or [], identity)
            row = {
                "contract_id": cid,
                "kind": kind,
                "side": side,
                "behavior": cell.get("behavior") or seg.get("behavior"),
                "source_key": seg.get("source_key"),
                "origin": seg.get("origin") or cell.get("origin"),
                "face_curta": seg.get("face_curta"),
                "support_start": seg.get("support_start") or {},
                "support_end": seg.get("support_end") or {},
                "index": seg.get("index"),
            }
            if side is not None and side != identity["face"] and kind in {"EXACT", "NEAR", "COVER"}:
                face_mismatch.append(row)
                continue
            if kind == "EXACT":
                exact_rows.append(row)
            elif kind == "NEAR":
                near_rows.append(row)
            elif kind == "COVER":
                cover_rows.append(row)
            elif kind == "FOREIGN":
                foreign_rows.append(row)

    if cover_rows and not exact_rows:
        return _abstain(source, identity, ABSTAIN_COVER, "locator_or_segment_covers_whole_wall",
                        extras={"cover_contracts": [r["contract_id"] for r in cover_rows],
                                "same_handle_other_encounters": same_handle})
    if near_rows and not exact_rows:
        return _abstain(source, identity, ABSTAIN_NEAR_ONLY, "near_endpoint_is_not_identity",
                        extras={"near_contracts": [r["contract_id"] for r in near_rows],
                                "same_handle_other_encounters": same_handle})
    if foreign_rows and not exact_rows:
        return _abstain(source, identity, ABSTAIN_FOREIGN, "endpoint_matches_at_segment_not_on_wall",
                        extras={"same_handle_other_encounters": same_handle})
    if face_mismatch and not exact_rows:
        return _abstain(source, identity, ABSTAIN_FACE, "n1_side_differs_from_source_face",
                        extras={"same_handle_other_encounters": same_handle})
    if not exact_rows:
        missing = extracted.get("missing_ids") or []
        if len(extracted.get("present_ids") or []) == 0:
            return _abstain(source, identity, ABSTAIN_MISSING_N1, "four_contracts_absent",
                            extras={"missing_ids": missing, "same_handle_other_encounters": same_handle})
        return _abstain(source, identity, ABSTAIN_MISSING_N1, "no_exact_n1_endpoint_on_this_encounter",
                        extras={"present_ids": extracted.get("present_ids"),
                                "missing_ids": missing,
                                "same_handle_other_encounters": same_handle})

    g10_status, g10_why = g10_gate(source=source, matched_rows=exact_rows)
    n1_origin = {
        "layer": "N1_ORIGIN",
        "visible_to_jev": False,
        "contracts_present": extracted.get("present_ids"),
        "contracts_missing": extracted.get("missing_ids"),
        "contracts_origin": extracted.get("origin"),
        "matched_contract_ids": sorted({r["contract_id"] for r in exact_rows}),
        "matched_rows": exact_rows,
        "lv_interpreter_contract_version": extracted.get("lv_interpreter_contract_version"),
        "lv_cells_version": extracted.get("lv_cells_version"),
        "g10": {"status": g10_status, "why": g10_why},
    }
    result = {
        "schema": V8_MATCH_SCHEMA,
        "status": MATCHED,
        "why": "exact_endpoint_and_face_on_listed_wall",
        "encounter_id": identity["encounter_id"],
        "identity": identity,
        "same_handle_other_encounters": same_handle,
        "n1_origin": n1_origin,
        "source_facts_only": True,
        "semantic_verdict": None,
        "pack_ready": False,
        "pack_blockers": [],
    }
    blockers = []
    if extracted.get("missing_ids"):
        blockers.append(ABSTAIN_MISSING_CONTRACT + ":" + ",".join(extracted["missing_ids"]))
    if g10_status:
        blockers.append(f"{g10_status}:{g10_why}")
        result["status"] = g10_status
        result["why"] = g10_why
    if cover_rows:
        blockers.append("cover_rows_also_present")
    result["pack_blockers"] = blockers
    result["pack_ready"] = not blockers and result["status"] == MATCHED
    return result


def _abstain(source: dict, identity: dict | None, status: str, why: str,
             extras: dict | None = None) -> dict[str, Any]:
    payload = {
        "schema": V8_MATCH_SCHEMA,
        "status": status,
        "why": why,
        "encounter_id": (identity or {}).get("encounter_id") or source.get("encounter_id"),
        "identity": identity,
        "n1_origin": {
            "layer": "N1_ORIGIN",
            "visible_to_jev": False,
            "matched_contract_ids": [],
        },
        "source_facts_only": True,
        "semantic_verdict": None,
        "pack_ready": False,
        "pack_blockers": [f"{status}:{why}"],
    }
    if extras:
        payload.update(extras)
    return payload


def source_evidence(source: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    facts = source.get("facts") or {}
    segment = identity.get("wall_segment") or source.get("wall_segment") or []
    return {
        "definitions_apply_to_listed_objects_only": True,
        "encounter": {
            "wall_handle": identity["wall_handle"],
            "face": identity["face"],
            "at": identity["at"],
            "segment": segment,
        },
        "wall": {
            "handle": identity["wall_handle"],
            "etype": facts.get("wall_etype") or "LWPOLYLINE",
            "points": segment,
            "xy": identity["at"],
            "role": "listed_wall",
        },
        "partner": {"handle": source.get("partner_handle") or facts.get("partner_handle"),
                    "role": "listed_partner"}
        if (source.get("partner_handle") or facts.get("partner_handle")) else None,
        "beam_label": {
            "handle": facts.get("label_handle") or source.get("label_handle"),
            "text": identity["beam"],
            "xy": facts.get("label_xy"),
            "role": "listed_label",
        },
        "listed_gaps": [{"handle": h, "role": "listed_gap"}
                        for h in (facts.get("gap_handles") or source.get("gap_handles") or []) if h],
        "listed_pillar_markers": [
            {"handle": p.get("handle"), "text": p.get("text"), "xy": p.get("xy"),
             "role": "listed_pillar"}
            for p in (facts.get("pillar_markers") or []) if isinstance(p, dict) and p.get("handle")
        ],
        "listed_colinear_continuations": [
            {"handle": h, "role": "listed_continuation"}
            for h in (facts.get("continuation_handles") or []) if h
        ],
        "face_curta_flag_listed": _source_face_curta(source),
        "g10_note": "listed_pillar_does_not_prove_para",
        "search": {"center": identity["at"], "units": "dxf_drawing"},
    }


def withdrawal_control(evidence: dict[str, Any]) -> dict[str, Any]:
    ctrl = copy.deepcopy(evidence)
    ctrl["listed_gaps"] = []
    ctrl["listed_pillar_markers"] = []
    ctrl["listed_colinear_continuations"] = []
    ctrl["face_curta_flag_listed"] = None
    return {"id": CONTROL_ID, "evidence": ctrl}


def scan_v8_leakage(node: Any) -> list[str]:
    problems = list(scan_evidence_leakage(node) if isinstance(node, dict) else [])
    problems.extend(scan_semantic_leakage(node))
    keys = set()

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            keys.update(current)
            for value in current.values():
                walk(value)
        elif isinstance(current, (list, tuple)):
            for item in current:
                walk(item)

    walk(node)
    for key in sorted(keys & V8_FORBIDDEN_EVIDENCE_KEYS):
        problems.append(f"forbidden_key:{key}")
    blob = str(node).lower()
    for token in V8_LEAK_TOKENS:
        if token in blob:
            problems.append(f"leak_token:{token}")
    return sorted(set(problems))


def build_identity_request(*, match: dict[str, Any], source: dict[str, Any],
                           identity_base: dict[str, Any],
                           baseline_sa: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = match.get("identity")
    if not identity:
        raise EncounterIdentityInvalid("cannot pack without encounter identity")
    evidence = source_evidence(source, identity)
    request = {
        "schema": "jev_sa_second_read_request/1",
        "identity": {
            **identity_base,
            "classe": "LV",
            "item": identity["beam"],
            "campo": "lv_encounter",
            "source_dxf_sha256": identity_base.get("source_dxf_sha256"),
            "project_id": identity_base.get("project_id"),
            "pavimento": identity.get("pavimento") or identity_base.get("pavimento"),
        },
        "use_context": "QA_B3",
        "baseline_sa": baseline_sa or {
            "value": None,
            "field": "lv_encounter",
            "source": "calibration_baseline_v8_outside_payload",
        },
        "question": lv_v8_question(),
        "evidence": evidence,
        "controls": [withdrawal_control(evidence)],
    }
    validate_request(request)
    payload = api_payload(request)
    leaks = scan_v8_leakage(payload)
    if leaks:
        raise EncounterIdentityInvalid("Jev payload leakage: " + "; ".join(leaks))
    if "baseline_sa" in payload:
        raise EncounterIdentityInvalid("baseline_sa leaked into Jev payload")
    wrapper = {
        "schema": V8_REQUEST_SCHEMA,
        "catalog_revision": CATALOG_V8_REVISION,
        "factory_version": FACTORY_V8_VERSION,
        "catalog_sha256": catalog_v8_hash(),
        "model": MODEL,
        "encounter_id": match["encounter_id"],
        "pack_ready": bool(match.get("pack_ready")),
        "pack_blockers": list(match.get("pack_blockers") or []),
        "n1_in_payload": False,
        "n1_origin": match.get("n1_origin"),
        "v1_request": request,
        "request_sha256": sha256_json(request),
        "payload_sha256": sha256_json(payload),
        "cache_key": cache_key(
            source_dxf_sha256=str(identity_base.get("source_dxf_sha256") or ""),
            request=request, model=MODEL, catalog_sha256=catalog_v8_hash(),
        ),
    }
    return wrapper
