"""Local anti-leakage and packet-size gates. No API calls."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from scripts.arete.jev_sa_second_read import (
    MAX_STATE_BYTES,
    _canonical,
    validate_request,
    verify_source_dxf,
)
from scripts.arete.qa_session_index import _check_dxf_path_allowed

from .schemas import FORBIDDEN_EVIDENCE_KEYS

SEMANTIC_LEAK_TOKENS = (
    "own_stretch",
    "own-stretch",
    "own stretch",
    "associated_to_cell",
    "belongs to this stretch",
    "beam's own",
    "ownership",
)
LINE_ETYPES = {"LINE", "LWPOLYLINE", "POLYLINE"}


def iter_strings(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from iter_strings(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from iter_strings(item)


def collect_keys(node: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        keys.update(node)
        for value in node.values():
            keys.update(collect_keys(value))
    elif isinstance(node, (list, tuple)):
        for item in node:
            keys.update(collect_keys(item))
    return keys


def assert_source_path_allowed(path: Path) -> None:
    _check_dxf_path_allowed(path)


def scan_semantic_leakage(node: Any) -> list[str]:
    joined = " ".join(iter_strings(node)).lower()
    problems: list[str] = []
    for token in SEMANTIC_LEAK_TOKENS:
        if token in joined:
            problems.append(f"semantic_leak:{token}")
    return problems


def scan_missing_endpoints(evidence: dict) -> list[str]:
    problems: list[str] = []
    for node in _walk_dicts(evidence):
        etype = str(node.get("etype") or "")
        if etype not in LINE_ETYPES or not node.get("handle"):
            continue
        if "withdrawn" in str(node.get("role") or ""):
            continue
        points = node.get("points")
        if not isinstance(points, list) or len(points) < 2:
            problems.append(f"missing_endpoints:{node.get('handle')}")
            continue
        if any(not isinstance(pt, (list, tuple)) or len(pt) < 2 for pt in points[:2]):
            problems.append(f"invalid_endpoints:{node.get('handle')}")
    return problems


def scan_polygon_wall_separation(evidence: dict) -> list[str]:
    problems: list[str] = []
    for node in _walk_dicts(evidence):
        role = str(node.get("role") or "")
        handle = node.get("handle")
        if role == "nearby_parallel_line" and node.get("closed") is True:
            problems.append(f"closed_polygon_presented_as_wall:{handle}")
        if role != "closed_polygon_edge":
            continue
        if node.get("closed") is not True:
            problems.append(f"polygon_missing_closed:{handle}")
        try:
            if int(node.get("vertex_count") or 0) < 3:
                problems.append(f"polygon_vertex_count:{handle}")
        except (TypeError, ValueError):
            problems.append(f"polygon_vertex_count:{handle}")
        if not isinstance(node.get("bbox"), list) or len(node.get("bbox") or []) != 4:
            problems.append(f"polygon_bbox:{handle}")
        edge = node.get("selected_edge")
        if not isinstance(edge, list) or len(edge) != 2:
            problems.append(f"polygon_selected_edge:{handle}")
        points = node.get("points")
        if not node.get("points_truncated") and (not isinstance(points, list) or len(points) < 3):
            problems.append(f"polygon_incomplete_contour:{handle}")
    return problems


def scan_evidence_leakage(evidence: dict, *, leak_values: Iterable[str] = ()) -> list[str]:
    problems: list[str] = []
    keys = collect_keys(evidence)
    leaked = FORBIDDEN_EVIDENCE_KEYS.intersection(keys)
    if leaked:
        problems.append("forbidden_keys:" + ",".join(sorted(leaked)))
    joined = " ".join(iter_strings(evidence)).lower()
    for token in ("baseline_sa", "ground_truth", "expected_choice", "qa_verdict", "gabarito"):
        if token in joined:
            problems.append(f"forbidden_token:{token}")
    problems.extend(scan_semantic_leakage(evidence))
    problems.extend(scan_missing_endpoints(evidence))
    problems.extend(scan_polygon_wall_separation(evidence))
    for raw in leak_values:
        value = str(raw).strip()
        if len(value) < 4:
            continue
        # CAD texts may equal an SA number; only flag explicit SA attribution.
        for prefix in ("sa chose", "sa_value", "n1 says", "qa score"):
            if prefix in joined and value.lower() in joined:
                problems.append(f"attributed_sa_value:{value}")
    return problems


def evidence_handles(evidence: dict) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            handle = node.get("handle")
            if isinstance(handle, str) and handle:
                found.add(handle)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(evidence)
    return found


LV_WITHDRAWAL_IDS = {"nearby_lines_removed", "neighbor_label_only", "topology_removed"}


def _lv_withdrawn_handles(evidence: dict) -> set[str]:
    found: set[str] = set()
    for key in ("nearby_lines", "nearby_polygon_edges", "encounter_gaps",
                "colinear_continuations"):
        for row in evidence.get(key) or []:
            if isinstance(row, dict) and row.get("handle"):
                found.add(row["handle"])
            if isinstance(row, dict):
                found.update(h for h in (row.get("duplicate_handles") or []) if h)
    return found


def scan_withdrawal_leaks(request: dict) -> list[str]:
    problems: list[str] = []
    withdrawn = _lv_withdrawn_handles(request.get("evidence") or {})
    keep = set()
    target = (request.get("evidence") or {}).get("target") or {}
    if target.get("handle"):
        keep.add(target["handle"])
    label = (request.get("evidence") or {}).get("beam_label") or {}
    if label.get("handle"):
        keep.add(label["handle"])
    for nb in (request.get("evidence") or {}).get("neighbor_beam_labels") or []:
        if isinstance(nb, dict) and nb.get("handle"):
            keep.add(nb["handle"])
    for control in request.get("controls") or []:
        cid = control.get("id")
        if cid not in LV_WITHDRAWAL_IDS:
            continue
        ev = control.get("evidence") or {}
        leaked = sorted(h for h in evidence_handles(ev) if h in withdrawn and h not in keep)
        if leaked:
            problems.append(f"withdrawal_leaked_handles:{cid}:" + ",".join(leaked))
        if ev.get("nearby_lines"):
            problems.append(f"withdrawal_left_nearby_lines:{cid}")
        if ev.get("nearby_polygon_edges"):
            problems.append(f"withdrawal_left_polygon_edges:{cid}")
        if cid == "topology_removed" and ev.get("encounter_gaps"):
            problems.append(f"withdrawal_left_encounter_gaps:{cid}")
        if cid == "topology_removed" and ev.get("colinear_continuations"):
            problems.append(f"withdrawal_left_continuations:{cid}")
    return problems


def validate_factory_request(request: dict, *, source_dxf: Path | None = None,
                             known_handles: set[str] | None = None,
                             leak_values: Iterable[str] = ()) -> dict:
    summary = validate_request(request)
    problems: list[str] = []
    problems.extend(scan_semantic_leakage(request.get("question") or {}))
    problems.extend(scan_withdrawal_leaks(request))
    states = [request["evidence"], *(control["evidence"] for control in request["controls"])]
    for state in states:
        problems.extend(scan_evidence_leakage(state, leak_values=leak_values))
        if len(_canonical(state)) > MAX_STATE_BYTES:
            problems.append("state_exceeds_16kb")
        if "INSUFFICIENT" not in request["question"]["criteria"]:
            problems.append("missing_insufficient")
        handles = evidence_handles(state)
        if not handles:
            problems.append("no_handles")
        if known_handles is not None:
            missing = sorted(handle for handle in handles if handle not in known_handles and handle != "INSUFFICIENT")
            if missing:
                problems.append("unknown_handles:" + ",".join(missing))
        has_xy = any(
            isinstance(node, dict) and ("xy" in node or {"x", "y"} <= set(node))
            for node in _walk_dicts(state)
        )
        if not has_xy:
            problems.append("geometry_without_referential")
    ids = [row["id"] for row in request["controls"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate_control_ids")
    criteria_ids = list(request["question"]["criteria"])
    if len(criteria_ids) != len(set(criteria_ids)):
        problems.append("duplicate_choice_ids")
    if source_dxf is not None:
        assert_source_path_allowed(source_dxf)
        verify_source_dxf(source_dxf, request["identity"]["source_dxf_sha256"])
    if problems:
        raise ValueError("anti-leakage: " + "; ".join(problems))
    return summary


def _walk_dicts(node: Any) -> Iterable[dict]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_dicts(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_dicts(item)
