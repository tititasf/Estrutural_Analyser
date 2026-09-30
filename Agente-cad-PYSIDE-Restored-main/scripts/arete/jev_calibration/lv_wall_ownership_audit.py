"""Read-only audit of LV source walls attached to 2+ distinct unique beam names.

N1 stays in a separate sidecar and never enters Jev evidence. Does not write
N1, DXF, production DB, or call the Jev API by itself.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .cad_source import CadSource
from .geometry_util import (
    BEAM_NAME_RE,
    along_segment_t,
    dist,
    midpoint,
    signed_line_distance,
)
from .hashing import sha256_json
from .leakage import scan_semantic_leakage, validate_factory_request
from scripts.arete.jev_sa_second_read import MODEL, validate_request, verify_source_dxf

AUDIT_SCHEMA = "jev_lv_source_wall_collision_audit/v1"
N1_COLLISION_SIDECAR_SCHEMA = "jev_lv_wall_collision_n1_sidecar/v1"
CAD_PROBE_SCHEMA = "jev_lv_bounded_cad_probe/v1"
PROTOCOL_SCHEMA = "jev_lv_blinded_single_outcome_protocol/v1"

T_MARGIN = 0.15
T_INTERIOR_LO = 0.20
T_INTERIOR_HI = 0.80
MAX_OUTSIDE = 40.0
PROBE_RADIUS = 70.0
MAX_PROBE_ROWS = 8

EXPECTED_V3_INVENTORY_SHA = {
    "13_PAV": "c83355515d2c2f76deb6754a9f68b3ad07dca72959452cb2e7a1a254e3359827",
    "14_PAV": "9b8d80f4d38a254c37c6efba2055fd07cfb6ae2b33ebbc7b0fdac9f28dbc6cdc",
}

SPECIAL_14PAV_HANDLES = ("312", "313")
SPECIAL_14PAV_NAMES = ("V419", "V423", "V424")


def _seg_len(seg: list) -> float:
    return dist(seg[0], seg[1])


def strip_membership(label_xy, wall_seg, partner_seg) -> dict[str, Any]:
    """Label vs one wall+partner using a shared wall-direction transverse axis."""
    t = along_segment_t(wall_seg[0], wall_seg[1], label_xy)
    along = -T_MARGIN <= t <= 1.0 + T_MARGIN
    s_lab = signed_line_distance(wall_seg[0], wall_seg[1], label_xy)
    s_par = signed_line_distance(wall_seg[0], wall_seg[1], midpoint(partner_seg))
    gap = abs(s_par)
    if gap < 1e-6:
        trans_ok = abs(s_lab) <= MAX_OUTSIDE
        trans_why = "degenerate_partner"
        t_norm = None
    else:
        t_norm = s_lab / s_par
        lo = -MAX_OUTSIDE / gap
        hi = 1.0 + MAX_OUTSIDE / gap
        trans_ok = lo <= t_norm <= hi
        if 0.0 <= t_norm <= 1.0:
            trans_why = "inside_strip"
        elif trans_ok:
            trans_why = "offset_from_strip"
        else:
            trans_why = "outside_strip"
    if not along:
        role = "not_along"
        in_strip = False
    elif not trans_ok:
        role = "outside_strip"
        in_strip = False
    elif T_INTERIOR_LO < t < T_INTERIOR_HI:
        role = "interior"
        in_strip = True
    else:
        role = "end"
        in_strip = True
    return {
        "t": round(float(t), 6),
        "t_norm_transverse": None if t_norm is None else round(float(t_norm), 6),
        "along": along,
        "transverse_ok": trans_ok,
        "transverse_why": trans_why,
        "in_strip": in_strip,
        "role": role,
    }


def classify_collision(owner_facts: list[dict[str, Any]]) -> dict[str, str]:
    """Inventory-only category. Does not read N1."""
    names = sorted({row["beam"] for row in owner_facts})
    in_rows = [row for row in owner_facts if row["membership"]["in_strip"]]
    in_names = sorted({row["beam"] for row in in_rows})
    n_in = len(in_names)
    n_interior = sum(1 for row in in_rows if row["membership"]["role"] == "interior")
    n_end = sum(1 for row in in_rows if row["membership"]["role"] == "end")
    if n_in <= 1:
        category = "LIKELY_OVER_EXPANDED_STRIP"
        uncertainty = "ONE_OR_ZERO_UNIQUE_LABELS_IN_THIS_STRIP"
    elif n_interior >= 2 and n_in == 2:
        category = "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP"
        uncertainty = "TWO_DISTINCT_UNIQUE_LABELS_INTERIOR_TO_SAME_STRIP"
    else:
        category = "SHARED_JOINT"
        if n_in >= 3:
            uncertainty = "THREE_OR_MORE_UNIQUE_LABELS_TOUCH_THIS_STRIP"
        elif n_end >= 2 and n_interior == 0:
            ts = [row["membership"]["t"] for row in in_rows]
            if min(ts) < 0.25 and max(ts) > 0.75:
                uncertainty = "LABELS_AT_OPPOSITE_ENDS"
            else:
                uncertainty = "TWO_UNIQUE_LABELS_AT_STRIP_ENDS"
        else:
            uncertainty = "TWO_UNIQUE_LABELS_MIXED_END_AND_INTERIOR"
    return {
        "category": category,
        "uncertainty": uncertainty,
        "in_strip_names": in_names,
        "n_in_strip": n_in,
        "n_interior": n_interior,
        "inventory_names": names,
    }


def _index_walls(inventory: dict[str, Any]) -> tuple[dict[str, list], dict[str, list]]:
    by_handle: dict[str, list] = defaultdict(list)
    segs: dict[str, list] = {}
    for beam in inventory.get("beams") or []:
        for wall in beam.get("walls") or []:
            handle = wall["handle"]
            segs[handle] = wall["segment"]
            by_handle[handle].append({"beam_row": beam, "wall": wall})
    return by_handle, segs


def audit_inventory_collisions(inventory: dict[str, Any]) -> dict[str, Any]:
    """Every wall handle attached to 2+ distinct unique beam names."""
    pavimento = inventory["pavimento"]
    by_handle, segs = _index_walls(inventory)
    encounters_by_handle: dict[str, list] = defaultdict(list)
    for enc in inventory.get("encounters") or []:
        encounters_by_handle[enc["wall_handle"]].append(enc)

    cases: list[dict[str, Any]] = []
    pair_counter: Counter = Counter()
    category_counter: Counter = Counter()
    encounter_total = 0
    n1_relevance_from_inventory = Counter()

    for handle, rows in sorted(by_handle.items()):
        names = sorted({row["beam_row"]["beam"] for row in rows})
        if len(names) < 2:
            continue
        wall0 = rows[0]["wall"]
        partner = wall0.get("partner_handle")
        partner_seg = segs.get(partner) if partner else None
        owner_facts = []
        for row in rows:
            beam = row["beam_row"]
            wall = row["wall"]
            if partner_seg is None:
                membership = {
                    "t": None, "t_norm_transverse": None, "along": False,
                    "transverse_ok": False, "transverse_why": "no_partner",
                    "in_strip": False, "role": "no_partner",
                }
            else:
                membership = strip_membership(beam["label_xy"], wall0["segment"], partner_seg)
            owner_facts.append({
                "beam": beam["beam"],
                "label_handle": beam.get("label_handle"),
                "label_xy": list(beam.get("label_xy") or []),
                "label_ok": wall.get("label_ok"),
                "face": wall.get("face"),
                "n_walls_on_beam": len(beam.get("walls") or []),
                "membership": membership,
            })
        tagged = classify_collision(owner_facts)
        pair = tuple(names)
        pair_counter[pair] += 1
        category_counter[tagged["category"]] += 1
        encs = encounters_by_handle.get(handle) or []
        encounter_total += len(encs)
        for enc in encs:
            n1_relevance_from_inventory[enc.get("n1_relevance") or "UNKNOWN"] += 1
        cases.append({
            "layer": "FACT",
            "pavimento": pavimento,
            "wall_handle": handle,
            "attached_beam_names": names,
            "n_attached_names": len(names),
            "pair_key": "|".join(names),
            "segment": wall0["segment"],
            "segment_length": round(_seg_len(wall0["segment"]), 3),
            "partner_handle": partner,
            "face": wall0.get("face"),
            "owners": owner_facts,
            "category": tagged["category"],
            "uncertainty": tagged["uncertainty"],
            "in_strip_names": tagged["in_strip_names"],
            "n_in_strip": tagged["n_in_strip"],
            "n_interior": tagged["n_interior"],
            "n_encounters": len(encs),
            "encounter_ids": [enc["encounter_id"] for enc in encs],
            "source_inventory_n1_relevance": dict(Counter(
                enc.get("n1_relevance") or "UNKNOWN" for enc in encs
            )),
            "jev_eligible": tagged["category"] == "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP",
            "n1_used": False,
        })

    special = _special_312_313(cases, inventory) if pavimento == "14_PAV" else None
    denominators = {
        "unique_lv_labels": (inventory.get("denominators") or {}).get("unique_lv_labels"),
        "source_walls_listed": (inventory.get("denominators") or {}).get("source_walls"),
        "unique_wall_handles": len(by_handle),
        "collision_walls": len(cases),
        "collision_pairs": len(pair_counter),
        "collision_encounters": encounter_total,
        "category_walls": dict(category_counter),
        "pair_wall_counts": [
            {"beams": list(k), "n_walls": v} for k, v in pair_counter.most_common()
        ],
        "inventory_n1_relevance_on_collision_encounters": dict(n1_relevance_from_inventory),
        "jev_eligible_walls": sum(1 for c in cases if c["jev_eligible"]),
    }
    payload = {
        "schema": AUDIT_SCHEMA,
        "note": (
            "FACT inventory of unique-label strip attachments. A collision is a "
            "wall handle listed under 2+ distinct unique V-names. Categories use "
            "label-vs-strip geometry from the same inventory. N1 is absent."
        ),
        "pavimento": pavimento,
        "source_dxf_sha256": inventory.get("source_dxf_sha256"),
        "source_inventory_sha256": inventory.get("inventory_sha256"),
        "n1_used": False,
        "denominators": denominators,
        "special_312_313": special,
        "cases": cases,
    }
    payload["audit_sha256"] = sha256_json(
        {k: v for k, v in payload.items() if k != "audit_sha256"}
    )
    return payload


def _special_312_313(cases: list[dict[str, Any]], inventory: dict[str, Any]) -> dict[str, Any]:
    by_beam = {b["beam"]: b for b in inventory.get("beams") or []}
    rows = {}
    for handle in SPECIAL_14PAV_HANDLES:
        match = next((c for c in cases if c["wall_handle"] == handle), None)
        v419_walls = [w["handle"] for w in (by_beam.get("V419") or {}).get("walls") or []]
        rows[handle] = {
            "in_collision_table": match is not None,
            "attached_beam_names": None if match is None else match["attached_beam_names"],
            "category": None if match is None else match["category"],
            "uncertainty": None if match is None else match["uncertainty"],
            "v419_lists_handle": handle in v419_walls,
            "v423_lists_handle": handle in [
                w["handle"] for w in (by_beam.get("V423") or {}).get("walls") or []
            ],
            "v424_lists_handle": handle in [
                w["handle"] for w in (by_beam.get("V424") or {}).get("walls") or []
            ],
        }
    return {
        "question": (
            "Are handles 312/313 collisions of two unique labels, or a surprising "
            "attachment relative to the v2 V419 note?"
        ),
        "handles": rows,
        "v419_n_walls": len((by_beam.get("V419") or {}).get("walls") or []),
        "v423_n_walls": len((by_beam.get("V423") or {}).get("walls") or []),
        "v424_n_walls": len((by_beam.get("V424") or {}).get("walls") or []),
        "inventory_only_verdict": (
            "Handles 312 and 313 are listed under unique labels V423 and V424. "
            "V419 does not list them. That is a V423/V424 inventory collision and "
            "a surprising non-attachment to V419, not a V419 collision."
        ),
    }


def attach_n1_sidecar(collision_audit: dict[str, Any], n1_sidecar: dict[str, Any]
                     ) -> dict[str, Any]:
    """Join N1 comparison AFTER freezing collisions. Never copy into Jev evidence."""
    by_enc = {row["encounter_id"]: row for row in n1_sidecar.get("rows") or []}
    joined = []
    field_counter: Counter = Counter()
    would_change = 0
    relevance: Counter = Counter()
    kinds: Counter = Counter()
    for case in collision_audit.get("cases") or []:
        enc_rows = []
        for eid in case.get("encounter_ids") or []:
            row = by_enc.get(eid)
            if row is None:
                continue
            enc_rows.append({
                "encounter_id": eid,
                "beam": row.get("beam"),
                "n1_relevance": row.get("n1_relevance"),
                "n1_field_would_change": row.get("n1_field_would_change"),
                "n1_outcomes": row.get("n1_outcomes"),
                "n1_kinds": row.get("n1_kinds"),
            })
            relevance[row.get("n1_relevance") or "UNKNOWN"] += 1
            if row.get("n1_field_would_change"):
                would_change += 1
            for kind in row.get("n1_kinds") or []:
                kinds[str(kind)] += 1
                field_counter["lv_cell:" + str(kind)] += 1
        joined.append({
            "wall_handle": case["wall_handle"],
            "attached_beam_names": case["attached_beam_names"],
            "category": case["category"],
            "n_n1_rows": len(enc_rows),
            "n1_field_would_change_rows": sum(
                1 for r in enc_rows if r["n1_field_would_change"]
            ),
            "n1_relevance_counts": dict(Counter(r["n1_relevance"] for r in enc_rows)),
        })
    payload = {
        "schema": N1_COLLISION_SIDECAR_SCHEMA,
        "layer": "N1_COMPARISON",
        "note": (
            "Isolated sidecar. Do not copy into Jev evidence. Collision "
            "categories were frozen from source inventory only."
        ),
        "pavimento": collision_audit.get("pavimento"),
        "source_inventory_sha256": collision_audit.get("source_inventory_sha256"),
        "collision_audit_sha256": collision_audit.get("audit_sha256"),
        "n1_sidecar_sha256": n1_sidecar.get("sidecar_sha256"),
        "denominators": {
            "collision_walls": len(collision_audit.get("cases") or []),
            "n1_rows_on_collision_encounters": sum(j["n_n1_rows"] for j in joined),
            "n1_field_would_change": would_change,
            "n1_relevance": dict(relevance),
            "n1_kinds": dict(kinds),
            "n1_fields": dict(field_counter),
        },
        "walls": joined,
    }
    payload["sidecar_sha256"] = sha256_json(
        {k: v for k, v in payload.items() if k != "sidecar_sha256"}
    )
    return payload


def bounded_cad_probe(source: CadSource, handle: str,
                      extra_xy: list[list[float]] | None = None) -> dict[str, Any]:
    """Neighborhood slice around one handle. Does not load the DXF into a prompt."""
    ent = source.by_handle(handle)
    if ent is None:
        return {"handle": handle, "found": False}
    points = list(ent.points or [])
    if len(points) < 2:
        points = [[ent.minx, ent.miny], [ent.maxx, ent.maxy]]
    centers = [list(points[0]), list(points[-1]), list(ent.xy)]
    for xy in extra_xy or []:
        centers.append(list(xy))
    texts: list[dict[str, Any]] = []
    walls: list[dict[str, Any]] = []
    seen_t: set[str] = set()
    seen_w: set[str] = set()
    for cx, cy in centers:
        for near in source.entities_near(float(cx), float(cy), PROBE_RADIUS,
                                         types=["TEXT", "MTEXT", "LINE", "LWPOLYLINE"]):
            if near.etype in {"TEXT", "MTEXT"}:
                text = (near.text or "").strip()
                if not BEAM_NAME_RE.fullmatch(text):
                    continue
                if near.handle in seen_t:
                    continue
                seen_t.add(near.handle)
                texts.append({
                    "handle": near.handle, "text": text, "xy": list(near.xy),
                    "layer": near.layer,
                })
            elif near.handle != handle and near.layer == ent.layer and not near.closed:
                if near.handle in seen_w:
                    continue
                seen_w.add(near.handle)
                pts = list(near.points or [])
                walls.append({
                    "handle": near.handle, "etype": near.etype, "layer": near.layer,
                    "xy": list(near.xy),
                    "points": pts[:2],
                })
    texts.sort(key=lambda row: row["handle"])
    walls.sort(key=lambda row: row["handle"])
    name_counts = Counter(row["text"] for row in texts)
    return {
        "schema": CAD_PROBE_SCHEMA,
        "handle": handle,
        "found": True,
        "etype": ent.etype,
        "layer": ent.layer,
        "closed": bool(ent.closed),
        "points": points[:4],
        "xy": list(ent.xy),
        "beam_texts": texts[:MAX_PROBE_ROWS],
        "same_layer_open_walls": walls[:MAX_PROBE_ROWS],
        "duplicate_name_texts_in_probe": {
            name: n for name, n in name_counts.items() if n >= 2
        },
        "source_dxf_sha256": source.dxf_sha256,
    }


def duplicate_name_labels(source: CadSource) -> dict[str, Any]:
    buckets: dict[str, list] = defaultdict(list)
    for etype in ("TEXT", "MTEXT"):
        for ent in source.entities_of_type(etype):
            text = (ent.text or "").strip()
            if not BEAM_NAME_RE.fullmatch(text) or text.upper().startswith("VF"):
                continue
            buckets[text].append({"handle": ent.handle, "xy": list(ent.xy), "layer": ent.layer})
    multi = {name: rows for name, rows in buckets.items() if len(rows) >= 2}
    return {
        "unique_lv_text_names": len(buckets),
        "names_with_duplicate_text": len(multi),
        "duplicate_names": [
            {"name": name, "n": len(rows), "handles": [r["handle"] for r in rows]}
            for name, rows in sorted(multi.items())
        ],
    }


def apply_cad_validation(case: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    """CAD may confirm or demote eligibility; it does not invent N1 truth."""
    texts = probe.get("beam_texts") or []
    names_in_probe = sorted({row["text"] for row in texts})
    attached = set(case["attached_beam_names"])
    in_strip = set(case["in_strip_names"])
    confirmed = sorted(n for n in names_in_probe if n in attached)
    dups = probe.get("duplicate_name_texts_in_probe") or {}
    cad_category = case["category"]
    cad_uncertainty = case["uncertainty"]
    if dups:
        cad_category = "SAME_NAME_DUPLICATE_LABEL"
        cad_uncertainty = "PROBE_HAS_TWO_TEXT_ENTITIES_WITH_SAME_V_NAME"
    elif case["category"] == "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP":
        if len(in_strip) == 2 and len([n for n in confirmed if n in in_strip]) == 2:
            cad_uncertainty = "CAD_CONFIRMS_TWO_DISTINCT_UNIQUE_LABELS"
        else:
            cad_category = "LIKELY_OVER_EXPANDED_STRIP"
            cad_uncertainty = "CAD_DID_NOT_CONFIRM_BOTH_INTERIOR_LABELS"
    return {
        "cad_category": cad_category,
        "cad_uncertainty": cad_uncertainty,
        "cad_names_in_probe": names_in_probe,
        "cad_attached_names_seen": confirmed,
        "jev_eligible_after_cad": (
            cad_category == "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP"
            and len(in_strip) == 2
            and len([n for n in confirmed if n in in_strip]) == 2
        ),
    }


def build_label_choice_request(*, identity: dict[str, Any], wall_handle: str,
                               segment: list, partner_handle: str | None,
                               labels: list[dict[str, Any]],
                               local_walls: list[dict[str, Any]],
                               connectivity: dict[str, Any]) -> dict[str, Any]:
    """Closed Choice between two source label names + INSUFFICIENT. No N1."""
    if len(labels) != 2:
        raise ValueError("label Choice requires exactly two source names")
    a, b = labels[0], labels[1]
    id_a = f"LABEL_{a['text']}"
    id_b = f"LABEL_{b['text']}"
    evidence = {
        "wall": {
            "handle": wall_handle,
            "etype": "LWPOLYLINE",
            "points": segment,
            "xy": [
                round((segment[0][0] + segment[1][0]) / 2.0, 3),
                round((segment[0][1] + segment[1][1]) / 2.0, 3),
            ],
            "partner_handle": partner_handle,
        },
        "source_labels": [
            {"handle": a["handle"], "text": a["text"], "xy": a["xy"]},
            {"handle": b["handle"], "text": b["text"], "xy": b["xy"]},
        ],
        "strip_connectivity": connectivity,
        "local_same_layer_walls": local_walls,
    }
    withheld = {
        "wall": evidence["wall"],
        "source_labels": [evidence["source_labels"][0]],
        "strip_connectivity": connectivity,
        "local_same_layer_walls": local_walls,
        "note": "second listed source label withheld",
    }
    request = {
        "schema": "jev_sa_second_read_request/1",
        "identity": identity,
        "baseline_sa": {
            "value": None,
            "source": "withheld_from_jev",
            "note": "N1 comparison stays outside Jev state",
        },
        "question": {
            "instructions": (
                "Which listed source label name is connected to this one wall "
                "handle by the listed DXF facts (label handles, wall handle, xy, "
                "strip connectivity, local same-layer elements)? Choose a listed "
                "name only when the facts pick that name uniquely. If both names "
                "remain compatible, or the facts are incomplete, choose INSUFFICIENT."
            ),
            "criteria": {
                id_a: f"Source label {a['text']} handle {a['handle']} is the unique name connected to wall {wall_handle}.",
                id_b: f"Source label {b['text']} handle {b['handle']} is the unique name connected to wall {wall_handle}.",
                "INSUFFICIENT": (
                    "The listed DXF facts do not pick a unique source label name "
                    "for this wall handle."
                ),
            },
        },
        "evidence": evidence,
        "controls": [
            {
                "id": "second_label_withheld",
                "expected_choice": "INSUFFICIENT",
                "evidence": withheld,
            }
        ],
        "use_context": "SA_POST_EXTRACT",
    }
    leaks = scan_semantic_leakage(request["question"]) + scan_semantic_leakage(evidence)
    if leaks:
        raise ValueError("semantic leak in Jev request: " + ",".join(leaks))
    validate_request(request)
    return request


def genuine_unresolved_after_cad(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        case for case in cases
        if case.get("cad_validation", {}).get("jev_eligible_after_cad")
        or (case.get("jev_eligible") and not case.get("cad_validation"))
    ]


def blinded_single_outcome_protocol() -> dict[str, Any]:
    """Design only. Do not emit speculative packets or claim benefit."""
    return {
        "schema": PROTOCOL_SCHEMA,
        "status": "DESIGN_ONLY_NOT_EXECUTED",
        "benefit_claimed": False,
        "packets_implemented": 0,
        "unit": "one_source_encounter_with_exactly_one_source_supported_outcome",
        "question": {
            "primitive": "Choice",
            "criteria": ["PARA", "PASSA", "INSUFFICIENT"],
            "about": (
                "Geometry/behavior at one wall handle + one endpoint: terminating "
                "gap or pillar (PARA), colinear open continuation without a "
                "strip-width gap (PASSA), or insufficient listed facts."
            ),
        },
        "blinding": {
            "evidence_contains": [
                "wall handle", "endpoints xy", "partner handle",
                "gap handles", "pillar text handles", "continuation handles",
                "local same-layer elements",
            ],
            "evidence_excludes": [
                "N1 values", "N1 locators", "QA verdict", "gabarito",
                "SA hypothesis labels PARA/PASSA as conclusions",
                "expected_choice in the full state",
            ],
            "compare_n1": "only after Jev and CAD baseline are frozen",
        },
        "controls": [
            "remove gap and pillar facts",
            "remove continuation facts",
            "perturb endpoint xy beyond the listed wall",
        ],
        "cad_deterministic_baseline": {
            "separate_from_jev_state": True,
            "rule": (
                "Same FACT rules as LV v3 hypotheses: PARA if gap or pillar at "
                "this endpoint; PASSA if colinear open wall at this endpoint "
                "without a strip-width gap. Locator-cover length is never PASSA."
            ),
        },
        "metrics": [
            "agreement Jev vs CAD baseline",
            "abstention (INSUFFICIENT)",
            "control INSUFFICIENT rate",
            "API outcome, model, latency, tokens",
            "N1 sidecar disagreement counted after unblinding",
        ],
        "not_accuracy_without_independent_truth": True,
        "relation_to_v3": {
            "v3_pack_gate": (
                "Choice only when two mutually exclusive source-supported N1 "
                "outcomes compete at the same encounter. Dry-runs packed 0."
            ),
            "v3_zero_packets_scope": (
                "The count of 0 Jev packets in catalog v3 applies only to that "
                "same-encounter conflict Choice. It is not evidence that Jev "
                "lacks value as a blinded check of a single source-supported "
                "outcome versus SA/N1."
            ),
            "this_protocol": (
                "Independent corroboration of ONE source-supported outcome, "
                "compared to N1 afterwards."
            ),
        },
        "gates_before_any_call": [
            "frozen inventory SHA",
            "anti-leakage and size validation",
            "source handles exist on the DXF",
            "CAD baseline computed and stored outside evidence",
            "max 8 API calls in a bounded experiment",
        ],
    }


def select_representative_handles(audit: dict[str, Any]) -> list[str]:
    chosen: list[str] = []
    if audit.get("pavimento") == "14_PAV":
        chosen.extend(SPECIAL_14PAV_HANDLES)
    by_cat: dict[str, list[str]] = defaultdict(list)
    for case in audit.get("cases") or []:
        by_cat[case["category"]].append(case["wall_handle"])
    for cat in (
        "UNRESOLVED_TRUE_MULTIPLE_OWNERSHIP",
        "SHARED_JOINT",
        "LIKELY_OVER_EXPANDED_STRIP",
    ):
        for handle in by_cat.get(cat) or []:
            if handle not in chosen:
                chosen.append(handle)
                break
    return chosen[:6]


def run_api_if_eligible(requests: list[dict[str, Any]], *, execute: bool,
                        source_dxf: Path, known_handles: set[str],
                        output_dir: Path, max_calls: int = 8) -> dict[str, Any]:
    """Validate all requests. Call Jev only when execute=True and still under cap."""
    from scripts.arete.jev_sa_second_read import run as run_jev

    outcomes = []
    calls = 0
    for i, request in enumerate(requests):
        identity = request["identity"]
        verify_source_dxf(source_dxf, identity["source_dxf_sha256"])
        try:
            gate = validate_factory_request(
                request, source_dxf=source_dxf, known_handles=known_handles,
            )
            problems: list[str] = []
        except ValueError as exc:
            gate = {"error": str(exc)}
            problems = [str(exc)]
        row = {
            "index": i,
            "item": identity.get("item"),
            "campo": identity.get("campo"),
            "validation": gate,
            "executed": False,
        }
        if problems:
            row["api_outcome"] = "NOT_CALLED_VALIDATION_FAILED"
            outcomes.append(row)
            continue
        n_states = 1 + len(request["controls"])
        if not execute:
            row["api_outcome"] = "NOT_CALLED_EXECUTE_FALSE"
            outcomes.append(row)
            continue
        if calls + n_states > max_calls:
            row["api_outcome"] = "NOT_CALLED_MAX_CALLS"
            outcomes.append(row)
            continue
        out_path = output_dir / f"jev_result_{i:02d}.json"
        result = run_jev(request)
        out_path.write_text(
            __import__("json").dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        calls += n_states
        row["executed"] = True
        row["api_outcome"] = "RECORDED"
        row["model"] = result.get("model") or MODEL
        row["output"] = str(out_path)
        row["choices"] = [
            {
                "variant": r.get("variant"),
                "choice": r.get("choice"),
                "confidence": r.get("confidence"),
                "latency_s": r.get("latency_s"),
                "input_tokens": r.get("input_tokens"),
                "expected_choice": r.get("expected_choice"),
                "control_matches_expectation": r.get("control_matches_expectation"),
            }
            for r in result.get("results") or []
        ]
        outcomes.append(row)
    return {
        "model_recorded": MODEL,
        "execute": execute,
        "calls_used": calls,
        "max_calls": max_calls,
        "n_requests": len(requests),
        "outcomes": outcomes,
    }
