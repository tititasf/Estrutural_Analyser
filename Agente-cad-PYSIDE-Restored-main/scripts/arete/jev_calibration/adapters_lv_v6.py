"""v6 read-only LV wall-level set comparison. Does not modify v1–v5 or N1.

Source grouping and ownership run before any N1 sidecar join. Jev packets are
source-only. Comparison fails closed when frozen SHA identities do not match.
"""
from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from typing import Any

from scripts.arete.jev_sa_second_read import MODEL, validate_request

from .adapters_lv_v5 import collision_index, ownership_gate as ownership_gate_v5
from .catalog_v6 import (
    CATALOG_V6_REVISION,
    CONTROL_ID,
    FACTORY_V6_VERSION,
    MAX_API_CALLS,
    MAX_ROUTED_PACKETS,
    PAVEMENT_SPECS_V6,
    V6_REQUEST_SCHEMA,
    catalog_v6_hash,
)
from .hashing import sha256_json
from .leakage import scan_evidence_leakage, scan_semantic_leakage, validate_factory_request
from .runner import api_payload, cache_key

BEHAVIORS = ("PARA", "PASSA")
OWNED = "OWNED"
REJECTED = "REJECTED"
UNCERTAIN = "UNCERTAIN"

V6_FORBIDDEN_EVIDENCE_KEYS = {
    "baseline_sa", "sa_value", "sa_level", "ground_truth", "qa_verdict",
    "expected_choice", "qa_score", "gabarito", "n1_value", "sa_choice",
    "hypotheses", "source_outcomes", "n1_relevance", "n1_field_would_change",
    "n1_locator", "cad_baseline", "n1_outcomes", "n1_cell_matches",
}
V6_LEAK_TOKENS = (
    "n1 says", "qa score", "gabarito", "expected_choice", "baseline_sa",
    "source_outcomes", "cad_redundant", "n1_locator", "golden",
    "n1_field_would_change",
)


class ComparisonInvalid(ValueError):
    """Frozen provenance does not support a valid comparison."""


def _load_json(path) -> dict[str, Any]:
    from pathlib import Path
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _norm_handle(handle: str | None) -> str:
    return str(handle or "").strip().upper()


def _norm_behavior(raw: Any) -> str | None:
    text = str(raw or "").strip().upper()
    if text in BEHAVIORS:
        return text
    return None


def _norm_face(raw: Any) -> str | None:
    text = str(raw or "").strip().upper()
    if text in {"A", "B"}:
        return text
    return None


def wall_key(*, pavimento: str, beam: str, wall_handle: str, face: str | None) -> str:
    face_id = _norm_face(face) or "FACE_UNKNOWN"
    return f"{pavimento}|LV|{beam}|wall|{_norm_handle(wall_handle)}|{face_id}"


def midpoint(segment: list | None) -> list[float] | None:
    if not isinstance(segment, list) or len(segment) < 2:
        return None
    a, b = segment[0], segment[1]
    if not (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple))):
        return None
    return [round((float(a[0]) + float(b[0])) / 2.0, 3), round((float(a[1]) + float(b[1])) / 2.0, 3)]


def endpoint_source_behavior(enc: dict[str, Any]) -> str | None:
    hyp = enc.get("hypotheses") or {}
    para = bool(hyp.get("para"))
    passa = bool(hyp.get("passa"))
    if para and passa:
        return "BOTH"
    if para:
        return "PARA"
    if passa:
        return "PASSA"
    return None


def endpoint_n1_compare_is_valid(*, n1_cells: list[dict[str, Any]]) -> bool:
    """A wall-covering locator cannot score a single endpoint."""
    if not n1_cells:
        return False
    points = []
    for cell in n1_cells:
        pts = cell.get("locator_points") or []
        if len(pts) == 2:
            points.append((tuple(pts[0]), tuple(pts[1])))
    unique_pts = set(points)
    behaviors = {_norm_behavior(c.get("behavior")) for c in n1_cells}
    behaviors.discard(None)
    if len(unique_pts) == 1 and len(behaviors) >= 2:
        return False
    covers = [c for c in n1_cells if c.get("locator_match") == "cover" or c.get("locator_cover")]
    if covers:
        return False
    return len(n1_cells) == 1 and next(iter(behaviors), None) in BEHAVIORS


def in_strip_owner_names(case: dict[str, Any]) -> list[str]:
    names = list(case.get("in_strip_names") or [])
    if names:
        return sorted(set(names))
    found = []
    for owner in case.get("owners") or []:
        mem = owner.get("membership") or {}
        if mem.get("in_strip") is True and owner.get("beam"):
            found.append(owner["beam"])
    return sorted(set(found))


def ownership_status_v6(*, wall_handle: str, beam: str, collisions: dict[str, dict]
                        ) -> tuple[str, str]:
    """Conservative gate. Shared joints and unknown stay UNCERTAIN, never exclusive."""
    case = collisions.get(_norm_handle(wall_handle))
    if case is None:
        return OWNED, "exclusive_unique_label"
    category = str(case.get("category") or "")
    in_strip = set(in_strip_owner_names(case))
    if category == "LIKELY_OVER_EXPANDED_STRIP":
        if beam in in_strip and len(in_strip) == 1:
            return OWNED, "over_expanded_others_rejected_in_strip_owner_kept"
        return REJECTED, "likely_over_expanded_owner_not_unique_in_strip"
    if category == "SHARED_JOINT":
        return UNCERTAIN, "shared_joint_not_forced_exclusive"
    if category == "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP":
        return UNCERTAIN, "unresolved_multiple_ownership"
    if not category:
        return UNCERTAIN, "unknown_collision_category"
    v5_ok, v5_why = ownership_gate_v5(wall_handle=wall_handle, beam=beam, collisions=collisions)
    if not v5_ok:
        return REJECTED, v5_why
    return UNCERTAIN, f"unlisted_category:{category}"


def _source_set_from_endpoints(endpoints: list[dict[str, Any]]) -> tuple[set[str], str, str]:
    if len(endpoints) != 2:
        return set(), "INCOMPLETE", "expected_two_endpoints"
    behaviors = []
    for row in endpoints:
        beh = row.get("source_behavior")
        if beh == "BOTH":
            return set(), "AMBIGUOUS", "para_and_passa_at_same_endpoint"
        if beh is None:
            return set(), "INCOMPLETE", "endpoint_without_xor_hypothesis"
        behaviors.append(beh)
    return set(behaviors), "COMPLETE", "both_endpoints_xor"


def _dedupe_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple, dict[str, Any]] = {}
    for cell in cells:
        key = (
            str(cell.get("side") or "").upper(),
            str(cell.get("behavior") or "").upper(),
            json.dumps(cell.get("locator_points") or [], sort_keys=True),
            _norm_handle(cell.get("matched_source_handle")),
            str(cell.get("locator_match") or ""),
            str(cell.get("index") or ""),
        )
        seen[key] = {
            "side": _norm_face(cell.get("side")),
            "behavior": _norm_behavior(cell.get("behavior")),
            "kind": cell.get("kind"),
            "index": cell.get("index"),
            "locator_points": cell.get("locator_points") or [],
            "matched_source_handle": cell.get("matched_source_handle"),
            "locator_match": cell.get("locator_match"),
            "locator_cover": bool(cell.get("locator_cover")),
            "endpoint_near_encounter": bool(cell.get("endpoint_near_encounter")),
        }
    return list(seen.values())


def classify_n1_mapping(*, wall_handle: str, face: str | None, cells: list[dict[str, Any]]
                        ) -> dict[str, Any]:
    handle = _norm_handle(wall_handle)
    face_id = _norm_face(face)
    exact: list[dict[str, Any]] = []
    cover: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    trap: list[dict[str, Any]] = []
    face_mismatch: list[dict[str, Any]] = []
    for cell in cells:
        match = str(cell.get("locator_match") or "")
        cell_handle = _norm_handle(cell.get("matched_source_handle"))
        cell_face = cell.get("side")
        if cell_face and face_id and cell_face != face_id:
            face_mismatch.append(cell)
            continue
        if not cell_handle or match in {"", "None", "null"}:
            ambiguous.append(cell)
            continue
        if cell_handle != handle:
            trap.append(cell)
            continue
        if match == "cover" or cell.get("locator_cover"):
            cover.append(cell)
            continue
        if match == "exact":
            exact.append(cell)
            continue
        ambiguous.append(cell)
    exact_set = {c["behavior"] for c in exact if c.get("behavior") in BEHAVIORS}
    if exact and cover:
        status = "AMBIGUOUS"
        reason = "mixed_exact_and_cover_locators_for_same_wall"
        exact_set = set()
    elif exact:
        status = "EXACT"
        reason = "unique_source_wall_exact_segment"
    elif cover:
        status = "COVER_ONLY"
        reason = "locator_cover_excluded_from_set_equality"
        exact_set = set()
    elif ambiguous or trap or face_mismatch:
        status = "AMBIGUOUS"
        reason = "locator_mapping_ambiguous_or_endpoint_near_trap"
        exact_set = set()
    else:
        status = "MISSING"
        reason = "no_n1_cell_mapped_to_this_source_wall"
        exact_set = set()
    return {
        "status": status,
        "reason": reason,
        "exact_set": sorted(exact_set),
        "n_exact": len(exact),
        "n_cover": len(cover),
        "n_ambiguous": len(ambiguous),
        "n_endpoint_near_trap": len(trap),
        "n_face_mismatch": len(face_mismatch),
    }


def aggregate_source_walls(inventory: dict[str, Any], collisions: dict[str, dict]
                           ) -> dict[str, Any]:
    """Source-only. Does not read N1."""
    pavimento = inventory["pavimento"]
    grouped: dict[str, dict[str, Any]] = {}
    for enc in inventory.get("encounters") or []:
        face = _norm_face(enc.get("face"))
        key = wall_key(
            pavimento=pavimento, beam=enc["beam"],
            wall_handle=enc["wall_handle"], face=face,
        )
        row = grouped.setdefault(key, {
            "wall_id": key,
            "pavimento": pavimento,
            "beam": enc["beam"],
            "wall_handle": enc["wall_handle"],
            "face": face,
            "label_ok": True,
            "partner_handle": enc.get("partner_handle"),
            "wall_segment": enc.get("wall_segment"),
            "endpoints": [],
            "source_handles": set(),
        })
        row["label_ok"] = bool(row["label_ok"] and enc.get("label_ok"))
        if enc.get("partner_handle"):
            row["partner_handle"] = enc.get("partner_handle")
        if enc.get("wall_segment"):
            row["wall_segment"] = enc.get("wall_segment")
        facts = enc.get("facts") or {}
        row["label_handle"] = facts.get("label_handle")
        row["label_xy"] = facts.get("label_xy")
        row["wall_etype"] = facts.get("wall_etype")
        row["source_handles"].update(enc.get("source_handles") or [])
        row["endpoints"].append({
            "encounter_id": enc["encounter_id"],
            "at": enc.get("at"),
            "source_behavior": endpoint_source_behavior(enc),
            "para": bool((enc.get("hypotheses") or {}).get("para")),
            "passa": bool((enc.get("hypotheses") or {}).get("passa")),
            "gap_handles": list(facts.get("gap_handles") or []),
            "continuation_handles": list(facts.get("continuation_handles") or []),
            "pillar_markers": list(facts.get("pillar_markers") or []),
            "label_handle": facts.get("label_handle"),
            "label_xy": facts.get("label_xy"),
        })
    walls = []
    for key, row in sorted(grouped.items()):
        row["endpoints"].sort(key=lambda e: json.dumps(e.get("at") or [], sort_keys=True))
        source_set, source_status, source_why = _source_set_from_endpoints(row["endpoints"])
        own_status, own_why = ownership_status_v6(
            wall_handle=row["wall_handle"], beam=row["beam"], collisions=collisions,
        )
        if row["face"] is None:
            own_status, own_why = UNCERTAIN, "face_unknown"
        elif not row["label_ok"] and own_status == OWNED:
            own_status, own_why = UNCERTAIN, "label_not_connected_to_strip"
        row["source_set"] = sorted(source_set)
        row["source_status"] = source_status
        row["source_why"] = source_why
        row["ownership_status"] = own_status
        row["ownership_why"] = own_why
        row["source_handles"] = sorted(h for h in row["source_handles"] if h)
        row["n1_used"] = False
        walls.append(row)
    den = Counter()
    for wall in walls:
        den["source_walls"] += 1
        den[f"ownership_{wall['ownership_status'].lower()}"] += 1
        den[f"source_{wall['source_status'].lower()}"] += 1
        if wall["face"] is None:
            den["face_unknown"] += 1
    return {
        "schema": "jev_lv_source_wall_table/v6",
        "catalog_revision": CATALOG_V6_REVISION,
        "pavimento": pavimento,
        "n1_used": False,
        "source_inventory_sha256": inventory.get("inventory_sha256"),
        "source_dxf_sha256": inventory.get("source_dxf_sha256"),
        "denominators": dict(den),
        "walls": walls,
    }


def _sidecar_rows_by_encounter(sidecar: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["encounter_id"]: row for row in sidecar.get("rows") or []}


def join_n1_wall_sets(source_table: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    """N1 join after source freeze. Never copy N1 into Jev evidence."""
    if sidecar.get("source_inventory_sha256") != source_table.get("source_inventory_sha256"):
        raise ComparisonInvalid(
            "N1 sidecar source_inventory_sha256 does not match frozen source table"
        )
    by_enc = _sidecar_rows_by_encounter(sidecar)
    joined = []
    counts = Counter()
    for wall in source_table.get("walls") or []:
        raw_cells = []
        for end in wall.get("endpoints") or []:
            row = by_enc.get(end["encounter_id"]) or {}
            raw_cells.extend(row.get("n1_cell_matches") or [])
        cells = _dedupe_cells(raw_cells)
        mapping = classify_n1_mapping(
            wall_handle=wall["wall_handle"], face=wall.get("face"), cells=cells,
        )
        n1_present = any(
            (by_enc.get(end["encounter_id"]) or {}).get("n1_present")
            for end in wall.get("endpoints") or []
        )
        verdict, verdict_why = wall_verdict(wall, mapping, n1_present=n1_present)
        item = {
            "wall_id": wall["wall_id"],
            "pavimento": wall["pavimento"],
            "beam": wall["beam"],
            "wall_handle": wall["wall_handle"],
            "face": wall.get("face"),
            "ownership_status": wall["ownership_status"],
            "ownership_why": wall["ownership_why"],
            "source_status": wall["source_status"],
            "source_why": wall["source_why"],
            "source_set": list(wall["source_set"]),
            "n1_mapping_status": mapping["status"],
            "n1_mapping_why": mapping["reason"],
            "n1_set": list(mapping["exact_set"]),
            "n1_present": bool(n1_present),
            "n1_n_exact": mapping["n_exact"],
            "n1_n_cover": mapping["n_cover"],
            "n1_n_ambiguous": mapping["n_ambiguous"],
            "n1_n_endpoint_near_trap": mapping["n_endpoint_near_trap"],
            "verdict": verdict,
            "verdict_why": verdict_why,
        }
        counts[verdict] += 1
        counts[f"n1_{mapping['status'].lower()}"] += 1
        joined.append(item)
    return {
        "schema": "jev_lv_wall_n1_join/v6",
        "layer": "N1_COMPARISON",
        "note": (
            "Isolated join. Do not copy into Jev evidence. Set equality is not "
            "correctness or SA gain."
        ),
        "pavimento": source_table.get("pavimento"),
        "source_inventory_sha256": source_table.get("source_inventory_sha256"),
        "n1_sidecar_sha256": sidecar.get("sidecar_sha256"),
        "n1_source": sidecar.get("n1_source"),
        "n1_fingerprint_sha256": sidecar.get("n1_fingerprint_sha256"),
        "denominators": dict(counts),
        "walls": joined,
    }


def wall_verdict(wall: dict[str, Any], mapping: dict[str, Any], *, n1_present: bool
                 ) -> tuple[str, str]:
    if wall["ownership_status"] == REJECTED:
        return "ABSTAIN_OWNERSHIP", wall["ownership_why"]
    if wall["ownership_status"] == UNCERTAIN:
        return "ABSTAIN_OWNERSHIP", wall["ownership_why"]
    if wall["source_status"] == "AMBIGUOUS":
        return "ABSTAIN_SOURCE", wall["source_why"]
    if wall["source_status"] != "COMPLETE":
        return "ABSTAIN_SOURCE", wall["source_why"]
    if mapping["status"] == "MISSING":
        return "ABSTAIN_N1_COVERAGE", mapping["reason"]
    if mapping["status"] == "COVER_ONLY":
        return "ABSTAIN_N1_COVERAGE", mapping["reason"]
    if mapping["status"] != "EXACT":
        return "ABSTAIN_N1_COVERAGE", mapping["reason"]
    src = set(wall["source_set"])
    n1 = set(mapping["exact_set"])
    if src == n1:
        return "SET_EQUAL", "source_set_equals_n1_exact_set"
    return "SET_DIVERGE", "source_set_differs_from_n1_exact_set"


def source_ambiguity_is_actionable(wall: dict[str, Any]) -> bool:
    if wall.get("source_status") != "AMBIGUOUS":
        return False
    if wall.get("ownership_status") != OWNED:
        return False
    for end in wall.get("endpoints") or []:
        if end.get("source_behavior") == "BOTH":
            handles = list(end.get("gap_handles") or []) + list(end.get("continuation_handles") or [])
            handles.extend(p.get("handle") for p in end.get("pillar_markers") or [] if p.get("handle"))
            if len([h for h in handles if h]) >= 2:
                return True
    return False


def route_adviser(source_table: dict[str, Any], joined: dict[str, Any]) -> dict[str, Any]:
    """Queue source-only packets. Routing is not an accuracy claim. Dry-run."""
    by_id = {w["wall_id"]: w for w in source_table.get("walls") or []}
    queue = []
    for row in joined.get("walls") or []:
        src = by_id.get(row["wall_id"])
        if src is None:
            continue
        if row["verdict"] == "SET_DIVERGE":
            queue.append({
                "wall_id": row["wall_id"],
                "route": "SOURCE_VS_N1_SET_DIVERGE",
                "reason": row["verdict_why"],
                "source_set": row["source_set"],
                "n1_set": row["n1_set"],
                "ownership_why": row["ownership_why"],
                "escalation": "QA_REVIEW_AFTER_JEV_OPTIONAL",
            })
        elif source_ambiguity_is_actionable(src):
            queue.append({
                "wall_id": row["wall_id"],
                "route": "SOURCE_AMBIGUITY_EVIDENCE_MAY_RESOLVE",
                "reason": src["source_why"],
                "source_set": src["source_set"],
                "n1_set": row["n1_set"],
                "ownership_why": row["ownership_why"],
                "escalation": "QA_REVIEW_IF_INSUFFICIENT",
            })
    queue.sort(key=lambda r: r["wall_id"])
    packed = []
    skipped = []
    for i, item in enumerate(queue):
        if i >= MAX_ROUTED_PACKETS:
            skipped.append({**item, "packed": False, "why": "max_routed_packets"})
            continue
        src = by_id[item["wall_id"]]
        request = build_source_only_request(src, spec_for(src["pavimento"]))
        packed.append({
            **item,
            "packed": True,
            "request_sha256": request["request_sha256"],
            "cache_key": request["cache_key"],
            "v1_request": request["v1_request"],
            "calls_if_executed": 1 + len(request["v1_request"].get("controls") or []),
        })
    return {
        "schema": "jev_lv_v6_routing_queue/v6",
        "note": "A routing queue is not an accuracy claim. Dry-run: zero API calls.",
        "n1_in_prompts": False,
        "execute": False,
        "max_routed_packets": MAX_ROUTED_PACKETS,
        "max_api_calls": MAX_API_CALLS,
        "n_actionable": len(queue),
        "n_packed": len(packed),
        "n_not_packed": len(skipped),
        "calls_used": 0,
        "packed": packed,
        "not_packed": skipped,
        "abstain_escalation": "QA_OR_MORE_SOURCE_EVIDENCE",
    }


def spec_for(pavimento: str) -> dict[str, Any]:
    spec = PAVEMENT_SPECS_V6.get(pavimento)
    if spec is None:
        raise ComparisonInvalid(f"unknown pavement {pavimento}")
    return spec


QUESTION = {
    "instructions": (
        "For this one listed wall handle, which listed FACT pattern is present "
        "at its two listed endpoints? Use only the listed objects (handles, "
        "coordinates, layers, points). Do not invent unlisted walls, gaps, "
        "markers, or continuations. The two endpoints belong to the same wall. "
        "If listed gaps, pillar markers, and colinear continuations are empty, "
        "mixed at one endpoint, or do not uniquely fit one definition below, "
        "choose INSUFFICIENT."
    ),
    "criteria": {
        "PARA_ONLY": (
            "Each listed endpoint has a listed gap polyline or pillar marker, "
            "and listed colinear_continuations is empty at both endpoints."
        ),
        "PASSA_ONLY": (
            "Each listed endpoint has a listed colinear open wall continuation, "
            "and listed encounter gaps and pillar markers are empty at both "
            "endpoints."
        ),
        "PARA_AND_PASSA": (
            "One listed endpoint has a listed gap or pillar marker and no listed "
            "continuation, and the other listed endpoint has a listed colinear "
            "continuation and no listed gap or pillar marker."
        ),
        "INSUFFICIENT": (
            "The listed FACT objects do not uniquely support PARA_ONLY, "
            "PASSA_ONLY, or PARA_AND_PASSA as defined."
        ),
    },
}


def _endpoint_evidence(end: dict[str, Any]) -> dict[str, Any]:
    return {
        "xy": list(end.get("at") or []),
        "listed_gaps": [{"handle": h} for h in end.get("gap_handles") or [] if h],
        "listed_pillar_markers": [
            {"handle": p.get("handle"), "text": p.get("text"), "xy": p.get("xy")}
            for p in end.get("pillar_markers") or [] if p.get("handle")
        ],
        "listed_colinear_continuations": [
            {"handle": h} for h in end.get("continuation_handles") or [] if h
        ],
    }


def build_evidence(wall: dict[str, Any]) -> dict[str, Any]:
    segment = wall.get("wall_segment") or []
    xy = midpoint(segment) or [0.0, 0.0]
    evidence = {
        "definitions_apply_to_listed_objects_only": True,
        "wall": {
            "handle": wall["wall_handle"],
            "etype": wall.get("wall_etype") or "LWPOLYLINE",
            "points": segment,
            "xy": xy,
            "role": "listed_wall",
        },
        "partner": {"handle": wall.get("partner_handle"), "role": "listed_partner"}
        if wall.get("partner_handle") else None,
        "beam_label": {
            "handle": wall.get("label_handle"),
            "text": wall.get("beam"),
            "xy": wall.get("label_xy"),
            "role": "listed_label",
        } if wall.get("label_handle") else None,
        "endpoints": [_endpoint_evidence(end) for end in wall.get("endpoints") or []],
    }
    return evidence


def withdrawal_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(evidence)
    for end in out.get("endpoints") or []:
        end["listed_gaps"] = []
        end["listed_pillar_markers"] = []
        end["listed_colinear_continuations"] = []
    return out


def scan_v6_leakage(node: Any) -> list[str]:
    problems = scan_semantic_leakage(node)
    if isinstance(node, dict):
        problems.extend(scan_evidence_leakage(node))
    keys: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            keys.update(item)
            for value in item.values():
                walk(value)
        elif isinstance(item, (list, tuple)):
            for value in item:
                walk(value)

    walk(node)
    leaked = V6_FORBIDDEN_EVIDENCE_KEYS.intersection(keys)
    if leaked:
        problems.append("v6_forbidden_keys:" + ",".join(sorted(leaked)))
    blob = json.dumps(node, ensure_ascii=False).lower()
    for token in V6_LEAK_TOKENS:
        if token in blob:
            problems.append(f"v6_leak_token:{token}")
    if "n1" in keys or any(str(k).startswith("n1_") for k in keys):
        problems.append("v6_n1_key_in_jev_state")
    return problems


def to_v1_request(v6: dict[str, Any]) -> dict[str, Any]:
    request = {
        "schema": "jev_sa_second_read_request/1",
        "identity": dict(v6["identity"]),
        "case_id": v6["identity"].get("wall_id") or v6["identity"]["item"],
        "baseline_sa": {
            "n1_withheld": True,
            "source": "sidecar_not_in_jev_state",
        },
        "question": {
            "instructions": v6["question"]["instructions"],
            "criteria": {k: str(v) for k, v in v6["question"]["criteria"].items()},
        },
        "evidence": copy.deepcopy(v6["evidence"]),
        "controls": [
            {
                "id": CONTROL_ID,
                "expected_choice": "INSUFFICIENT",
                "evidence": copy.deepcopy(v6["controls"][0]["evidence"]),
            }
        ],
        "use_context": "SA_POST_EXTRACT",
    }
    validate_request(request)
    validate_factory_request(request)
    payload = api_payload(request)
    blob = json.dumps(payload, ensure_ascii=False)
    if "baseline_sa" in payload or "expected_choice" in blob:
        raise ValueError("v1 adapter leaked baseline or expected_choice into API payload")
    if "n1" in blob.lower() and "n1_withheld" in blob:
        raise ValueError("v1 adapter leaked withheld N1 note into API payload")
    problems = scan_v6_leakage(payload)
    if problems:
        raise ValueError("v6 leakage in API payload: " + "; ".join(problems))
    return request


def build_source_only_request(wall: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    evidence = build_evidence(wall)
    control_ev = withdrawal_evidence(evidence)
    v6 = {
        "schema": V6_REQUEST_SCHEMA,
        "catalog_revision": CATALOG_V6_REVISION,
        "factory_version": FACTORY_V6_VERSION,
        "identity": {
            "project_id": spec["project_id"],
            "pavimento": wall["pavimento"],
            "classe": "LV",
            "item": wall["beam"],
            "campo": "wall_endpoint_set",
            "source_dxf_sha256": spec["expected_dxf_sha256"],
            "wall_id": wall["wall_id"],
        },
        "question": copy.deepcopy(QUESTION),
        "evidence": evidence,
        "controls": [{"id": CONTROL_ID, "evidence": control_ev}],
    }
    problems = scan_v6_leakage(v6["question"]) + scan_v6_leakage(evidence) + scan_v6_leakage(control_ev)
    if problems:
        raise ValueError("v6 request leakage: " + "; ".join(problems))
    v1 = to_v1_request(v6)
    payload = api_payload(v1)
    key = cache_key(
        source_dxf_sha256=spec["expected_dxf_sha256"],
        request=v1,
        model=MODEL,
        catalog_sha256=catalog_v6_hash(),
    )
    return {
        "v6_request": v6,
        "v1_request": v1,
        "request_sha256": sha256_json(v1),
        "api_payload_sha256": sha256_json(payload),
        "cache_key": key,
        "n1_in_request": False,
    }


def load_frozen_pavement(pavimento: str) -> tuple[dict[str, Any], dict[str, dict], dict[str, Any], dict[str, Any]]:
    spec = spec_for(pavimento)
    inventory = _load_json(spec["inventory"])
    if inventory.get("inventory_sha256") != spec["expected_inventory_sha256"]:
        raise ComparisonInvalid(
            f"{pavimento} inventory SHA {inventory.get('inventory_sha256')} "
            f"!= {spec['expected_inventory_sha256']}"
        )
    if inventory.get("source_dxf_sha256") != spec["expected_dxf_sha256"]:
        raise ComparisonInvalid(f"{pavimento} inventory DXF SHA mismatch")
    if inventory.get("schema") != "jev_lv_source_inventory/v3":
        raise ComparisonInvalid(f"{pavimento} inventory schema is not frozen v3")
    audit = _load_json(spec["collision"])
    if audit.get("audit_sha256") != spec["expected_collision_sha256"]:
        raise ComparisonInvalid(
            f"{pavimento} collision audit SHA {audit.get('audit_sha256')} "
            f"!= {spec['expected_collision_sha256']}"
        )
    if audit.get("source_inventory_sha256") != spec["expected_inventory_sha256"]:
        raise ComparisonInvalid(f"{pavimento} collision audit inventory SHA mismatch")
    sidecar = _load_json(spec["n1_sidecar"])
    if sidecar.get("sidecar_sha256") != spec["expected_sidecar_sha256"]:
        raise ComparisonInvalid(
            f"{pavimento} N1 sidecar SHA {sidecar.get('sidecar_sha256')} "
            f"!= {spec['expected_sidecar_sha256']}"
        )
    if sidecar.get("source_inventory_sha256") != spec["expected_inventory_sha256"]:
        raise ComparisonInvalid(f"{pavimento} N1 sidecar inventory SHA mismatch")
    return inventory, collision_index(audit), sidecar, spec


def compact_wall(wall: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "wall_id", "pavimento", "beam", "wall_handle", "face",
        "ownership_status", "ownership_why", "source_status", "source_why",
        "source_set", "n1_mapping_status", "n1_mapping_why", "n1_set",
        "n1_present", "verdict", "verdict_why",
    )
    return {k: wall[k] for k in keep if k in wall}


def run_pavement(pavimento: str) -> dict[str, Any]:
    inventory, collisions, sidecar, spec = load_frozen_pavement(pavimento)
    source_table = aggregate_source_walls(inventory, collisions)
    source_sha = sha256_json({
        "walls": [
            {
                "wall_id": w["wall_id"],
                "source_set": w["source_set"],
                "source_status": w["source_status"],
                "ownership_status": w["ownership_status"],
                "ownership_why": w["ownership_why"],
            }
            for w in source_table["walls"]
        ],
        "denominators": source_table["denominators"],
    })
    source_table["source_table_sha256"] = source_sha
    joined = join_n1_wall_sets(source_table, sidecar)
    routing = route_adviser(source_table, joined)
    coverage = {
        "source_walls": source_table["denominators"].get("source_walls", 0),
        "source_complete": source_table["denominators"].get("source_complete", 0),
        "source_incomplete": source_table["denominators"].get("source_incomplete", 0),
        "source_ambiguous": source_table["denominators"].get("source_ambiguous", 0),
        "ownership_owned": source_table["denominators"].get("ownership_owned", 0),
        "ownership_rejected": source_table["denominators"].get("ownership_rejected", 0),
        "ownership_uncertain": source_table["denominators"].get("ownership_uncertain", 0),
        "n1_exact": joined["denominators"].get("n1_exact", 0),
        "n1_cover_only": joined["denominators"].get("n1_cover_only", 0),
        "n1_missing": joined["denominators"].get("n1_missing", 0),
        "n1_ambiguous": joined["denominators"].get("n1_ambiguous", 0),
        "set_equal": joined["denominators"].get("SET_EQUAL", 0),
        "set_diverge": joined["denominators"].get("SET_DIVERGE", 0),
        "abstain_ownership": joined["denominators"].get("ABSTAIN_OWNERSHIP", 0),
        "abstain_source": joined["denominators"].get("ABSTAIN_SOURCE", 0),
        "abstain_n1_coverage": joined["denominators"].get("ABSTAIN_N1_COVERAGE", 0),
    }
    return {
        "pavimento": pavimento,
        "role": spec["role"],
        "parity_claimed": False,
        "project_id": spec["project_id"],
        "source_dxf_sha256": spec["expected_dxf_sha256"],
        "inventory_sha256": spec["expected_inventory_sha256"],
        "collision_audit_sha256": spec["expected_collision_sha256"],
        "n1_sidecar_sha256": spec["expected_sidecar_sha256"],
        "n1_source": sidecar.get("n1_source"),
        "n1_fingerprint_sha256": sidecar.get("n1_fingerprint_sha256"),
        "source_table_sha256": source_sha,
        "source_denominators": source_table["denominators"],
        "join_denominators": joined["denominators"],
        "coverage": coverage,
        "routing": {
            "n_actionable": routing["n_actionable"],
            "n_packed": routing["n_packed"],
            "n_not_packed": routing["n_not_packed"],
            "calls_used": 0,
            "packed_wall_ids": [p["wall_id"] for p in routing["packed"]],
        },
        "actionable": [
            {k: v for k, v in item.items() if k != "v1_request"}
            for item in routing["packed"]
        ] + routing["not_packed"],
        "packed_requests": [
            {
                "wall_id": p["wall_id"],
                "route": p["route"],
                "request_sha256": p["request_sha256"],
                "cache_key": p["cache_key"],
                "v1_request": p["v1_request"],
            }
            for p in routing["packed"]
        ],
        "comparable_rows": [
            compact_wall(w) for w in joined["walls"]
            if w["verdict"] in {"SET_EQUAL", "SET_DIVERGE"}
        ],
        "missing_evidence": missing_evidence_summary(joined["walls"]),
    }


def missing_evidence_summary(walls: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = Counter()
    for wall in walls:
        if str(wall.get("verdict") or "").startswith("ABSTAIN"):
            reasons[wall.get("verdict_why") or wall.get("verdict")] += 1
    return {
        "abstain_n": sum(reasons.values()),
        "reasons": dict(reasons.most_common()),
    }


def run_v6() -> dict[str, Any]:
    pavements = {}
    for pav in ("13_PAV", "14_PAV"):
        pavements[pav] = run_pavement(pav)
    totals = Counter()
    for pav, row in pavements.items():
        for key, value in row["coverage"].items():
            totals[key] += int(value or 0)
        totals["actionable"] += int(row["routing"]["n_actionable"])
        totals["packed"] += int(row["routing"]["n_packed"])
    return {
        "schema": "jev_lv_wall_level_calibration_run/v6",
        "catalog_revision": CATALOG_V6_REVISION,
        "factory_version": FACTORY_V6_VERSION,
        "catalog_sha256": catalog_v6_hash(),
        "n1_in_jev_prompts": False,
        "n1_in_source_selection": False,
        "api_calls": 0,
        "execute": False,
        "benefit_claimed": False,
        "parity_claimed": False,
        "accuracy_claimed": False,
        "cad_bfs_rewritten": False,
        "v3_v4_v5_reports_unmodified": True,
        "jev_role": "optional_adviser",
        "v5_endpoint_n1_metrics": "withdrawn_not_reused",
        "totals": dict(totals),
        "pavements": pavements,
        "next_controlled_experiment": (
            "If packed>0, execute at most 8 cached Jev calls on the frozen "
            "source-only packets, then compare Jev vs source set only. PNG G1 "
            "and independent truth remain required before any SA-gain claim. "
            "Do not rewrite CAD BFS until this wall-level measurement is used."
        ),
    }
