"""v5 blinded single-outcome LV packets. Does not modify v1–v4 catalogs.

Source-first selection from frozen v3 inventory + collision audit. N1 sidecar
is read only after requests and Jev responses are frozen. Max 8 API calls.
"""
from __future__ import annotations

import copy
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.arete.jev_sa_second_read import (
    MAX_STATE_BYTES,
    MODEL,
    _canonical,
    _sha,
    run as jev_run,
    validate_request,
    verify_source_dxf,
)

from .cad_source import CadSource, DxfParserCadSource
from .catalog_v5 import (
    CATALOG_V5,
    CATALOG_V5_REVISION,
    FACTORY_V5_VERSION,
    V5_AUDIT_SCHEMA,
    V5_REQUEST_SCHEMA,
    V5_RESULT_SCHEMA,
    catalog_v5_hash,
)
from .geometry_util import compact_entity, dist, rounded_points
from .hashing import sha256_file, sha256_json
from .leakage import evidence_handles, scan_evidence_leakage, scan_semantic_leakage
from .lv_wall_ownership_audit import EXPECTED_V3_INVENTORY_SHA
from .runner import api_payload, sanitize_error

REPO = Path(__file__).resolve().parents[3]
V3_ROOT = REPO / "scripts" / "arete" / "relatorios" / "20260929_jev_catalog_v3_lv_source_encounter"
OWN_ROOT = REPO / "scripts" / "arete" / "relatorios" / "20260929_jev_lv_source_wall_ownership"

EXCLUDED_OWNERSHIP = {
    "LIKELY_OVER_EXPANDED_STRIP",
    "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP",
}
MAX_ENCOUNTERS = 4
MAX_API_CALLS = 8
CONTROL_ID = "decisive_facts_removed"

PAVEMENT_SPECS = {
    "13_PAV": {
        "project_id": "dd238e47-1dc6-4f63-a760-4e7ce19a7386",
        "inventory": V3_ROOT / "dryrun_13pav_lv" / "source_inventory.json",
        "collision": OWN_ROOT / "collision_audit_13_PAV.json",
        "n1_sidecar": V3_ROOT / "dryrun_13pav_lv" / "n1_comparison_sidecar.json",
        "dxf": Path(
            r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1"
            r"\Fase-1_Ingestao\Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
            r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf"
        ),
        "expected_dxf_sha256": "d23381e30eb358cc07e8c140d92db4c06b7be97859e7f9fb3eea2c0bd33151a4",
    },
    "14_PAV": {
        "project_id": "f28c3897-c8df-4bb9-a187-cb090f2c7ec7",
        "inventory": V3_ROOT / "dryrun_14pav_lv" / "source_inventory.json",
        "collision": OWN_ROOT / "collision_audit_14_PAV.json",
        "n1_sidecar": V3_ROOT / "dryrun_14pav_lv" / "n1_comparison_sidecar.json",
        "dxf": REPO / "scripts" / "arete" / "relatorios" / "20260924_jev_14pav" / "vps_parity" / "torre_1.dxf",
        "expected_dxf_sha256": "7ec8a5edd4e5aecc78d60002a7198906c83b0699a4a87084fb9fdc7ac5f36a3b",
    },
}

PREFERRED_CONTROLS = (
    {"pavimento": "14_PAV", "beam": "V420", "wall_handle": "2F8", "which": "min_y", "tag": "south"},
    {"pavimento": "14_PAV", "beam": "V420", "wall_handle": "2F8", "which": "max_y", "tag": "north"},
)

QUESTION = {
    "instructions": (
        "At this one listed wall endpoint, which listed FACT class is present? "
        "Use only the listed objects (handles, coordinates, layers, points). "
        "Do not invent unlisted walls, gaps, markers, or continuations. "
        "Facts at the other end of the same wall are a different encounter and "
        "are not listed. If listed encounter_gaps, pillar_markers, and "
        "colinear_continuations are all empty, or they do not uniquely fit "
        "one definition below, choose INSUFFICIENT."
    ),
    "criteria": {
        "PARA": (
            "A listed gap polyline in encounter_gaps or a listed pillar marker "
            "in pillar_markers occupies this same listed endpoint, so the listed "
            "wall terminates there."
        ),
        "PASSA": (
            "A listed colinear open wall in colinear_continuations shares this "
            "same listed endpoint, and encounter_gaps is empty at this endpoint."
        ),
        "INSUFFICIENT": (
            "The listed FACT objects do not uniquely support PARA or PASSA as "
            "defined. Choose this when the decisive gap/pillar or continuation "
            "objects are absent, mixed, or incomplete."
        ),
    },
}

V5_FORBIDDEN_EVIDENCE_KEYS = {
    "baseline_sa", "sa_value", "sa_level", "ground_truth", "qa_verdict",
    "expected_choice", "qa_score", "gabarito", "n1_value", "sa_choice",
    "hypotheses", "source_outcomes", "n1_relevance", "n1_field_would_change",
    "n1_locator", "cad_baseline", "why",
}
V5_LEAK_TOKENS = (
    "n1 says", "qa score", "gabarito", "expected_choice", "baseline_sa",
    "source_outcomes", "cad_redundant", "a_para", "a_passa", "b_para", "b_passa",
    "n1_locator", "golden",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _norm_handle(handle: str | None) -> str:
    return str(handle or "").strip().upper()


def collision_index(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for case in audit.get("cases") or []:
        handle = case.get("handle") or case.get("wall_handle")
        if handle:
            out[_norm_handle(handle)] = case
    return out


def ownership_gate(*, wall_handle: str, beam: str, collisions: dict[str, dict]
                   ) -> tuple[bool, str]:
    case = collisions.get(_norm_handle(wall_handle))
    if case is None:
        return True, "exclusive_unique_label"
    category = str(case.get("category") or "")
    if category in EXCLUDED_OWNERSHIP:
        return False, category
    if category == "SHARED_JOINT":
        for owner in case.get("owners") or []:
            mem = owner.get("membership") or {}
            if owner.get("beam") == beam and mem.get("in_strip") is True:
                return True, "shared_joint_in_strip_member"
        return False, "shared_joint_label_not_in_strip"
    return True, category or "unlisted_category"


def source_behavior(enc: dict[str, Any]) -> str | None:
    hyp = enc.get("hypotheses") or {}
    para = bool(hyp.get("para"))
    passa = bool(hyp.get("passa"))
    if para and not passa:
        return "PARA"
    if passa and not para:
        return "PASSA"
    return None


def decisive_handles(enc: dict[str, Any], behavior: str) -> list[str]:
    facts = enc.get("facts") or {}
    if behavior == "PARA":
        handles = list(facts.get("gap_handles") or [])
        handles.extend(p.get("handle") for p in facts.get("pillar_markers") or [] if p.get("handle"))
        return [h for h in handles if h]
    if behavior == "PASSA":
        return [h for h in (facts.get("continuation_handles") or []) if h]
    return []


def is_xor_source_supported(enc: dict[str, Any]) -> bool:
    if source_behavior(enc) is None:
        return False
    if enc.get("face") not in {"A", "B"}:
        return False
    if not enc.get("label_ok"):
        return False
    behavior = source_behavior(enc)
    return bool(behavior and decisive_handles(enc, behavior))


def eligible_encounters(inventory: dict[str, Any], collisions: dict[str, dict]
                        ) -> list[dict[str, Any]]:
    rows = []
    for enc in inventory.get("encounters") or []:
        if not is_xor_source_supported(enc):
            continue
        ok, why = ownership_gate(
            wall_handle=enc["wall_handle"], beam=enc["beam"], collisions=collisions,
        )
        if not ok:
            continue
        rows.append({**enc, "ownership_why": why, "source_behavior": source_behavior(enc)})
    rows.sort(key=lambda e: e["encounter_id"])
    return rows


def _match_preferred(pool: list[dict[str, Any]], spec: dict[str, str]) -> dict[str, Any] | None:
    hits = [
        enc for enc in pool
        if enc.get("beam") == spec["beam"]
        and _norm_handle(enc.get("wall_handle")) == _norm_handle(spec["wall_handle"])
        and str(enc.get("encounter_id") or "").startswith(spec["pavimento"] + "|")
    ]
    if not hits:
        return None
    if spec["which"] == "min_y":
        return min(hits, key=lambda e: (float(e["at"][1]), float(e["at"][0]), e["encounter_id"]))
    return max(hits, key=lambda e: (float(e["at"][1]), float(e["at"][0]), e["encounter_id"]))


def select_sample(pools: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Source-only. Does not read N1 sidecars."""
    selected: list[dict[str, Any]] = []
    notes: list[str] = []
    used_ids: set[str] = set()

    def take(enc: dict[str, Any] | None, reason: str) -> None:
        if enc is None or enc["encounter_id"] in used_ids or len(selected) >= MAX_ENCOUNTERS:
            return
        row = dict(enc)
        row["selection_reason"] = reason
        selected.append(row)
        used_ids.add(enc["encounter_id"])

    for spec in PREFERRED_CONTROLS:
        pool = pools.get(spec["pavimento"]) or []
        hit = _match_preferred(pool, spec)
        take(hit, f"preferred_control_V420_2F8_{spec['tag']}")
        if hit is None:
            notes.append(f"preferred_missing:{spec['tag']}")

    have_13 = any(str(r["encounter_id"]).startswith("13_PAV|") for r in selected)
    have_14 = any(str(r["encounter_id"]).startswith("14_PAV|") for r in selected)
    have_para = any(r["source_behavior"] == "PARA" for r in selected)
    have_passa = any(r["source_behavior"] == "PASSA" for r in selected)

    def pick_from(pav: str, behavior: str | None, exclusive_first: bool) -> dict[str, Any] | None:
        for enc in pools.get(pav) or []:
            if enc["encounter_id"] in used_ids:
                continue
            if behavior and enc["source_behavior"] != behavior:
                continue
            if exclusive_first and enc.get("ownership_why") != "exclusive_unique_label":
                continue
            return enc
        if exclusive_first:
            return pick_from(pav, behavior, exclusive_first=False)
        return None

    if not have_13:
        need = []
        if not have_para:
            need.append("PARA")
        if not have_passa:
            need.append("PASSA")
        if not need:
            need = ["PARA", "PASSA"]
        for beh in need:
            take(pick_from("13_PAV", beh, True), f"13_PAV_{beh}_fill")
    if not have_14:
        take(pick_from("14_PAV", None, True), "14_PAV_fill")
    for pav in ("13_PAV", "14_PAV"):
        for beh in ("PARA", "PASSA"):
            if any(r["source_behavior"] == beh for r in selected):
                continue
            take(pick_from(pav, beh, True), f"behavior_fill_{pav}_{beh}")
    for pav in ("13_PAV", "14_PAV"):
        take(pick_from(pav, None, True), f"slot_fill_{pav}")

    pool_counts = {
        pav: {
            "eligible": len(rows),
            "para": sum(1 for r in rows if r["source_behavior"] == "PARA"),
            "passa": sum(1 for r in rows if r["source_behavior"] == "PASSA"),
            "exclusive": sum(1 for r in rows if r.get("ownership_why") == "exclusive_unique_label"),
        }
        for pav, rows in pools.items()
    }
    return {
        "schema": "jev_lv_blinded_single_outcome_selection/v5",
        "n1_used": False,
        "catalog_revision": CATALOG_V5_REVISION,
        "factory_version": FACTORY_V5_VERSION,
        "max_encounters": MAX_ENCOUNTERS,
        "selected": [
            {
                "encounter_id": r["encounter_id"],
                "pavimento": r["encounter_id"].split("|", 1)[0],
                "beam": r["beam"],
                "wall_handle": r["wall_handle"],
                "endpoint": r["at"],
                "face": r.get("face"),
                "source_behavior": r["source_behavior"],
                "ownership_why": r.get("ownership_why"),
                "selection_reason": r.get("selection_reason"),
                "source_handles": list(r.get("source_handles") or []),
                "gap_handles": list((r.get("facts") or {}).get("gap_handles") or []),
                "continuation_handles": list((r.get("facts") or {}).get("continuation_handles") or []),
                "pillar_handles": [
                    p.get("handle") for p in (r.get("facts") or {}).get("pillar_markers") or []
                    if p.get("handle")
                ],
                "partner_handle": r.get("partner_handle"),
                "label_handle": (r.get("facts") or {}).get("label_handle"),
                "inventory_record": r,
            }
            for r in selected[:MAX_ENCOUNTERS]
        ],
        "pool_counts": pool_counts,
        "notes": notes,
    }


def _entity_row(source: CadSource, handle: str, extra: dict[str, Any] | None = None
                ) -> dict[str, Any]:
    ent = source.by_handle(handle) or source.by_handle(handle.lower()) or source.by_handle(handle.upper())
    if ent is None:
        raise ValueError(f"source handle missing on DXF: {handle}")
    row = compact_entity(ent, extra)
    pts = rounded_points(ent.points, limit=8)
    if pts and "points" not in row:
        row["points"] = pts
    return row


def build_evidence(enc: dict[str, Any], source: CadSource) -> dict[str, Any]:
    facts = enc.get("facts") or {}
    wall_h = enc["wall_handle"]
    partner_h = enc.get("partner_handle")
    label_h = facts.get("label_handle")
    evidence: dict[str, Any] = {
        "definitions_apply_to_listed_objects_only": True,
        "endpoint": {"xy": list(enc["at"]), "units": "dxf_drawing"},
        "wall": _entity_row(source, wall_h, {
            "role": "listed_wall",
            "points": enc.get("wall_segment"),
        }),
        "partner": _entity_row(source, partner_h, {"role": "listed_partner"}) if partner_h else None,
        "beam_label": _entity_row(source, label_h, {"role": "listed_label", "include_points": False})
        if label_h else None,
        "encounter_gaps": [
            _entity_row(source, h, {"role": "listed_gap"})
            for h in facts.get("gap_handles") or []
        ],
        "pillar_markers": [
            {
                "handle": p["handle"],
                "text": p.get("text"),
                "xy": p.get("xy"),
                "role": "listed_pillar_marker",
            }
            for p in facts.get("pillar_markers") or [] if p.get("handle")
        ],
        "colinear_continuations": [
            _entity_row(source, h, {"role": "listed_continuation"})
            for h in facts.get("continuation_handles") or []
        ],
        "local_same_layer_polygons": [
            _entity_row(source, h, {"role": "listed_same_layer_polygon"})
            for h in (facts.get("nearby_polygon_handles") or [])[:6]
        ],
    }
    return evidence


def withdrawal_evidence(evidence: dict[str, Any], behavior: str) -> dict[str, Any]:
    out = copy.deepcopy(evidence)
    if behavior == "PARA":
        out["encounter_gaps"] = []
        out["pillar_markers"] = []
    elif behavior == "PASSA":
        out["colinear_continuations"] = []
    else:
        raise ValueError("withdrawal requires PARA or PASSA")
    return out


def cad_baseline(enc: dict[str, Any]) -> dict[str, Any]:
    behavior = source_behavior(enc)
    return {
        "layer": "HYPOTHESIS",
        "visible_to_jev": False,
        "rule": (
            "PARA if gap or pillar at this endpoint; PASSA if colinear open wall "
            "at this endpoint without a strip-width gap. Locator-cover length is "
            "never PASSA."
        ),
        "choice": behavior,
        "para": bool((enc.get("hypotheses") or {}).get("para")),
        "passa": bool((enc.get("hypotheses") or {}).get("passa")),
        "decisive_handles": decisive_handles(enc, behavior or ""),
        "encounter_id": enc["encounter_id"],
    }


def scan_v5_leakage(node: Any) -> list[str]:
    problems = scan_semantic_leakage(node)
    problems.extend(scan_evidence_leakage(node if isinstance(node, dict) else {}))
    keys = set()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            keys.update(item)
            for value in item.values():
                walk(value)
        elif isinstance(item, (list, tuple)):
            for value in item:
                walk(value)

    walk(node)
    leaked = V5_FORBIDDEN_EVIDENCE_KEYS.intersection(keys)
    if leaked:
        problems.append("v5_forbidden_keys:" + ",".join(sorted(leaked)))
    blob = json.dumps(node, ensure_ascii=False).lower()
    for token in V5_LEAK_TOKENS:
        if token in blob:
            problems.append(f"v5_leak_token:{token}")
    return problems


def validate_v5_request(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema") != V5_REQUEST_SCHEMA:
        raise ValueError(f"schema must be {V5_REQUEST_SCHEMA}")
    identity = request.get("identity")
    if not isinstance(identity, dict) or not all(identity.get(k) for k in
            ("project_id", "pavimento", "classe", "item", "campo", "source_dxf_sha256")):
        raise ValueError("identity incomplete")
    question = request.get("question") or {}
    criteria = question.get("criteria") or {}
    if set(criteria) != {"PARA", "PASSA", "INSUFFICIENT"}:
        raise ValueError("criteria must be PARA, PASSA, INSUFFICIENT")
    evidence = request.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("evidence required")
    controls = request.get("controls") or []
    if len(controls) != 1 or controls[0].get("id") != CONTROL_ID:
        raise ValueError("exactly one decisive_facts_removed control is required")
    if "cad_baseline" in request.get("evidence", {}):
        raise ValueError("cad baseline must stay outside evidence")
    problems: list[str] = []
    problems.extend(scan_v5_leakage(question))
    for state in [evidence, controls[0]["evidence"]]:
        problems.extend(scan_v5_leakage(state))
        if len(_canonical(state)) > MAX_STATE_BYTES:
            problems.append("state_exceeds_16kb")
        if state.get("wall", {}).get("handle") and "points" not in state["wall"] and "xy" not in state["wall"]:
            problems.append("wall_missing_geometry")
    if evidence == controls[0]["evidence"]:
        problems.append("control_evidence_identical")
    withdrawn = set()
    behavior = request.get("withdrawal_kind")
    if behavior == "PARA":
        withdrawn.update(h["handle"] for h in evidence.get("encounter_gaps") or [] if h.get("handle"))
        withdrawn.update(h["handle"] for h in evidence.get("pillar_markers") or [] if h.get("handle"))
    elif behavior == "PASSA":
        withdrawn.update(h["handle"] for h in evidence.get("colinear_continuations") or [] if h.get("handle"))
    keep = {evidence.get("wall", {}).get("handle"), (evidence.get("partner") or {}).get("handle"),
            (evidence.get("beam_label") or {}).get("handle")}
    leaked_h = sorted(h for h in evidence_handles(controls[0]["evidence"]) if h in withdrawn and h not in keep)
    if leaked_h:
        problems.append("withdrawal_leaked_handles:" + ",".join(leaked_h))
    if problems:
        raise ValueError("v5 gates: " + "; ".join(problems))
    return {
        "request_sha256": _sha(request),
        "max_state_bytes": max(len(_canonical(s)) for s in [evidence, controls[0]["evidence"]]),
        "criteria": list(criteria),
    }


def to_v1_request(v5: dict[str, Any]) -> dict[str, Any]:
    """Adapt to the existing helper: string criteria, withheld baseline_sa."""
    request = {
        "schema": "jev_sa_second_read_request/1",
        "identity": dict(v5["identity"]),
        "baseline_sa": {
            "n1_withheld_until_unblind": True,
            "source": "sidecar_not_read_at_freeze",
        },
        "question": {
            "instructions": v5["question"]["instructions"],
            "criteria": {k: str(v) for k, v in v5["question"]["criteria"].items()},
        },
        "evidence": copy.deepcopy(v5["evidence"]),
        "controls": [
            {
                "id": CONTROL_ID,
                "expected_choice": "INSUFFICIENT",
                "evidence": copy.deepcopy(v5["controls"][0]["evidence"]),
            }
        ],
        "use_context": "SA_POST_EXTRACT",
    }
    validate_request(request)
    payload = api_payload(request)
    blob = json.dumps(payload, ensure_ascii=False)
    if "baseline_sa" in payload or "expected_choice" in blob:
        raise ValueError("v1 adapter leaked baseline or expected_choice into API payload")
    return request


def freeze_case(*, row: dict[str, Any], source: CadSource, dxf_path: Path,
                project_id: str) -> dict[str, Any]:
    enc = row["inventory_record"]
    pav = row["pavimento"]
    verify_source_dxf(dxf_path, PAVEMENT_SPECS[pav]["expected_dxf_sha256"])
    if source.dxf_sha256.lower() != PAVEMENT_SPECS[pav]["expected_dxf_sha256"]:
        raise ValueError("loaded CadSource SHA mismatch")
    evidence = build_evidence(enc, source)
    known = source.known_handles()
    handles = evidence_handles(evidence)
    missing = sorted(h for h in handles if h not in known)
    if missing:
        raise ValueError("unknown_handles:" + ",".join(missing))
    behavior = row["source_behavior"]
    control_ev = withdrawal_evidence(evidence, behavior)
    v5 = {
        "schema": V5_REQUEST_SCHEMA,
        "catalog_revision": CATALOG_V5_REVISION,
        "factory_version": FACTORY_V5_VERSION,
        "identity": {
            "project_id": project_id,
            "pavimento": pav,
            "classe": "LV",
            "item": row["beam"],
            "campo": "endpoint_behavior",
            "source_dxf_sha256": PAVEMENT_SPECS[pav]["expected_dxf_sha256"],
            "encounter_id": row["encounter_id"],
        },
        "question": copy.deepcopy(QUESTION),
        "evidence": evidence,
        "controls": [{"id": CONTROL_ID, "evidence": control_ev}],
        "withdrawal_kind": behavior,
        "source_path": str(dxf_path),
    }
    summary = validate_v5_request(v5)
    v1 = to_v1_request(v5)
    payload = api_payload(v1)
    baseline = cad_baseline(enc)
    return {
        "v5_request": v5,
        "v1_request": v1,
        "cad_baseline": baseline,
        "gates": summary,
        "api_payload_sha256": sha256_json(payload),
        "v5_request_sha256": summary["request_sha256"],
        "v1_request_sha256": _sha(v1),
        "dxf_sha256": PAVEMENT_SPECS[pav]["expected_dxf_sha256"],
        "source_handles": sorted(handles),
        "request_bytes": {
            "full": len(_canonical(evidence)),
            "control": len(_canonical(control_ev)),
        },
    }


def cache_key_v5(*, dxf_sha256: str, api_payload_sha256: str) -> str:
    return sha256_json({
        "source_dxf_sha256": dxf_sha256,
        "api_payload_sha256": api_payload_sha256,
        "model": MODEL,
        "catalog_sha256": catalog_v5_hash(),
    })


def execute_frozen(*, v1_request: dict[str, Any], cache_dir: Path, cache_key: str,
                   execute: bool) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key}.json"
    if path.is_file():
        cached = json.loads(path.read_text(encoding="utf-8"))
        cached["cache_hit"] = True
        return cached
    if not execute:
        return {
            "schema": V5_RESULT_SCHEMA,
            "status": "FROZEN_NOT_EXECUTED",
            "cache_hit": False,
            "model": MODEL,
            "calls": 0,
        }
    started = time.perf_counter()
    try:
        result = jev_run(v1_request)
        elapsed = round(time.perf_counter() - started, 3)
        record = {
            "schema": V5_RESULT_SCHEMA,
            "status": "RECORDED",
            "cache_hit": False,
            "model": result.get("model") or MODEL,
            "created_at_utc": result.get("created_at_utc"),
            "request_sha256": result.get("request_sha256"),
            "elapsed_s_wall": elapsed,
            "results": result.get("results"),
            "calls": 1 + len(v1_request.get("controls") or []),
            "error": None,
        }
    except Exception as exc:
        record = {
            "schema": V5_RESULT_SCHEMA,
            "status": "TECHNICAL_ERROR",
            "cache_hit": False,
            "model": MODEL,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_s_wall": round(time.perf_counter() - started, 3),
            "results": [],
            "calls": 0,
            "error": sanitize_error(exc),
        }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return record


def load_pavement_source_only(pavimento: str) -> tuple[dict[str, Any], dict[str, dict], dict[str, Any]]:
    spec = PAVEMENT_SPECS[pavimento]
    inventory = _load_json(spec["inventory"])
    got = inventory.get("inventory_sha256")
    expected = EXPECTED_V3_INVENTORY_SHA[pavimento]
    if got != expected:
        raise ValueError(f"{pavimento} inventory SHA {got} != {expected}")
    if inventory.get("source_dxf_sha256") != spec["expected_dxf_sha256"]:
        raise ValueError(f"{pavimento} inventory DXF SHA mismatch")
    audit = _load_json(spec["collision"])
    return inventory, collision_index(audit), spec


def build_selection() -> dict[str, Any]:
    pools = {}
    inventory_shas = {}
    collision_shas = {}
    for pav in ("13_PAV", "14_PAV"):
        inventory, collisions, spec = load_pavement_source_only(pav)
        pools[pav] = eligible_encounters(inventory, collisions)
        inventory_shas[pav] = inventory["inventory_sha256"]
        collision_shas[pav] = sha256_file(spec["collision"])
    selection = select_sample(pools)
    selection["inventory_sha256"] = inventory_shas
    selection["collision_sha256"] = collision_shas
    selection["dxf_sha256"] = {p: PAVEMENT_SPECS[p]["expected_dxf_sha256"] for p in PAVEMENT_SPECS}
    selection["n1_sidecars_read"] = False
    selection["selection_sha256"] = sha256_json(
        {k: v for k, v in selection.items() if k not in {"selection_sha256", "selected"}}
        | {"selected_ids": [r["encounter_id"] for r in selection["selected"]]}
    )
    return selection


def unblind_n1(selection: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in selection["selected"]:
        pav = item["pavimento"]
        sidecar = _load_json(PAVEMENT_SPECS[pav]["n1_sidecar"])
        by_id = {r["encounter_id"]: r for r in sidecar.get("rows") or []}
        n1 = by_id.get(item["encounter_id"]) or {}
        rows.append({
            "encounter_id": item["encounter_id"],
            "source_behavior": item["source_behavior"],
            "n1_present": n1.get("n1_present"),
            "n1_outcomes": n1.get("n1_outcomes"),
            "n1_kinds": n1.get("n1_kinds"),
            "n1_field_would_change": n1.get("n1_field_would_change"),
            "n1_relevance": n1.get("n1_relevance"),
            "locator_cover_seen": n1.get("locator_cover_seen"),
            "sidecar_sha256": sidecar.get("sidecar_sha256"),
        })
    return rows
