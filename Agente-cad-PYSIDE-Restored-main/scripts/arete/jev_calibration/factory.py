"""Discover PIL/LAJ/LV/FV CAD conflicts and emit separate corpus records. Dry-run only."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Callable

from scripts.arete.jev_sa_second_read import MAX_STATE_BYTES, _canonical, validate_request

from .adapters_fv import discover_fv, reversed_control as fv_reversed, withdrawal_control as fv_withdraw
from .adapters_laj import discover_laj, reversed_control as laj_reversed, withdrawal_control as laj_withdraw
from .adapters_lv import discover_lv, reversed_control as lv_reversed, withdrawal_control as lv_withdraw
from .adapters_lv_v2 import (
    discover_lv_v2,
    reversed_control_v2 as lv_v2_reversed,
    withdrawal_control_v2 as lv_v2_withdraw,
)
from .adapters_pil import ConflictCandidate, discover_pil, reversed_control as pil_reversed, withdrawal_control as pil_withdraw
from .cad_source import CadSource
from .catalog_v1 import catalog_hash
from .catalog_v2 import CATALOG_V2, CATALOG_V2_REVISION, FACTORY_V2_VERSION, catalog_v2_hash
from .catalog_v3 import CATALOG_V3, CATALOG_V3_REVISION, FACTORY_V3_VERSION, catalog_v3_hash
from .corpus import adjudication_record, baseline_record, source_packet_record, to_jev_request, write_json
from .filenames import assert_visible_request_files, request_filename
from .hashing import sha256_json
from .leakage import validate_factory_request
from .n1_snapshot import N1Snapshot
from .schemas import AUDIT_SCHEMA, CATALOG_REVISION, FACTORY_VERSION

UNPACKABLE_REASONS = {"NEEDS_SOURCE", "UNPACKABLE_NEEDS_SOURCE", "STATE_EXCEEDS_16KB"}

DISCOVERERS: dict[str, Callable[..., Any]] = {
    "PIL": discover_pil,
    "LAJ": discover_laj,
    "LV": discover_lv,
    "FV": discover_fv,
}
WITHDRAWALS = {"PIL": pil_withdraw, "LAJ": laj_withdraw, "LV": lv_withdraw, "FV": fv_withdraw}
REVERSALS = {"PIL": pil_reversed, "LAJ": laj_reversed, "LV": lv_reversed, "FV": fv_reversed}


def _as_discoveries(found: Any) -> list[ConflictCandidate] | dict[str, str]:
    if isinstance(found, dict):
        return found
    if isinstance(found, ConflictCandidate):
        return [found]
    return list(found)


def _controls_for(candidate: ConflictCandidate) -> list[dict[str, Any]]:
    if candidate.catalog_id == "lv_source_encounter_face_behavior":
        from .adapters_lv_v3 import reversed_control_v3 as lv_v3_reversed
        from .adapters_lv_v3 import withdrawal_control_v3 as lv_v3_withdraw
        controls = [lv_v3_withdraw(candidate)]
        reversed_ctrl = lv_v3_reversed(candidate)
    elif candidate.catalog_id == "lv_cell_face_behavior_choice":
        controls = [lv_v2_withdraw(candidate)]
        reversed_ctrl = lv_v2_reversed(candidate)
    else:
        controls = [WITHDRAWALS[candidate.classe](candidate)]
        reversed_ctrl = REVERSALS[candidate.classe](candidate)
    for extra in candidate.extra_controls or []:
        if extra.get("id") not in {c.get("id") for c in controls}:
            controls.append(extra)
    if reversed_ctrl and reversed_ctrl.get("id") not in {c.get("id") for c in controls}:
        controls.append(reversed_ctrl)
    full = candidate.evidence
    distinct = []
    for control in controls:
        if control.get("evidence") == full:
            continue
        distinct.append(control)
    return distinct[:4]


def emit_case(candidate: ConflictCandidate, *, identity_base: dict, snapshot: N1Snapshot,
              source: CadSource, n1_item) -> dict[str, Any]:
    identity = {
        **identity_base,
        "classe": candidate.classe,
        "item": candidate.item,
        "campo": candidate.campo,
        "source_dxf_sha256": source.dxf_sha256,
    }
    controls = _controls_for(candidate)
    packet = source_packet_record(
        candidate.case_id, identity, candidate.physical_unit, candidate.question,
        candidate.evidence, controls, candidate.included, candidate.excluded,
        qa_snapshot_sha256=n1_item.snapshot_hash,
        catalog_revision=candidate.catalog_revision or CATALOG_REVISION,
    )
    packet["catalog_id"] = candidate.catalog_id
    sizes = [len(_canonical(packet["evidence"]))] + [len(_canonical(c["evidence"])) for c in controls]
    if max(sizes) > MAX_STATE_BYTES:
        return {
            "status": "UNPACKABLE",
            "reason": "STATE_EXCEEDS_16KB",
            "case_id": candidate.case_id,
            "bytes": max(sizes),
            "item": candidate.item,
            "classe": candidate.classe,
        }
    sa_value = candidate.baseline_value if candidate.baseline_value is not None else n1_item.sa_value
    if candidate.classe == "FV" and (sa_value is None or sa_value == ""):
        return {
            "status": "UNPACKABLE", "reason": "NEEDS_SOURCE",
            "detail": "baseline_claim_missing",
            "case_id": candidate.case_id, "item": candidate.item, "classe": candidate.classe,
        }
    if "NONE" in candidate.question.get("criteria", {}) and not (
            candidate.evidence.get("inventory") or {}
    ).get("exhaustive"):
        return {
            "status": "UNPACKABLE", "reason": "NEEDS_SOURCE",
            "detail": "none_without_exhaustive_inventory",
            "case_id": candidate.case_id, "item": candidate.item, "classe": candidate.classe,
        }
    if len(candidate.question.get("criteria") or {}) < 2:
        return {
            "status": "UNPACKABLE", "reason": "NEEDS_SOURCE",
            "detail": "fewer_than_two_choice_options",
            "case_id": candidate.case_id, "item": candidate.item, "classe": candidate.classe,
        }
    baseline = baseline_record(
        candidate.case_id, identity, sa_value=sa_value, sa_field=n1_item.sa_field,
        router_trigger=candidate.trigger, cad_rules=candidate.cad_rules,
    )
    adj_status = candidate.convention_status or "PENDENTE_G1"
    adjudication = adjudication_record(
        candidate.case_id, identity, status=adj_status,
        handles=[row.get("handle") for row in candidate.alternatives if row.get("handle")],
        convention="desnivel_laje" if candidate.classe == "LAJ" else None,
        notes=("Level convention is not proven by competing DXF markers; case stays out of accuracy."
               if adj_status == "CONVENCAO_INDETERMINADA"
               else "G1 independent adjudication has not run; this is a packet, not a sealed label."),
    )
    request = to_jev_request(packet, baseline)
    validate_factory_request(
        request, source_dxf=source.dxf_path, known_handles=source.known_handles(),
        leak_values=[str(n1_item.sa_value)] if n1_item.sa_value else [],
    )
    packed = {
        "status": "PACKED",
        "case_id": candidate.case_id,
        "packet": packet,
        "baseline": baseline,
        "adjudication": adjudication,
        "jev_request": request,
        "trigger": candidate.trigger,
        "severity": candidate.severity,
        "n1_relevance": candidate.n1_relevance or "N1_DECISION_RELEVANT",
        "n1_relevance_why": candidate.n1_relevance_why,
        "catalog_id": candidate.catalog_id,
    }
    return packed


def _record_audits(audits: list[dict[str, Any]], *, discards: list, unpackable: list) -> None:
    for row in audits:
        relevance = str(row.get("n1_relevance") or "")
        if relevance == "N1_DECISION_RELEVANT":
            continue
        reason = str(row.get("reason") or "unknown")
        payload = dict(row)
        if relevance == "SOURCE_INSUFFICIENT" or reason in UNPACKABLE_REASONS:
            unpackable.append({
                "status": "UNPACKABLE",
                "reason": "NEEDS_SOURCE" if reason not in UNPACKABLE_REASONS else reason,
                "item": payload.get("item"),
                "classe": payload.get("classe") or "LV",
                "detail": payload.get("why") or payload.get("detail"),
                "n1_relevance": relevance or "SOURCE_INSUFFICIENT",
                "handle": payload.get("handle"),
                "source_outcomes": payload.get("source_outcomes") or [],
            })
        else:
            discards.append({
                "item": payload.get("item"),
                "classe": payload.get("classe") or "LV",
                "reason": reason,
                "detail": payload.get("why") or payload.get("detail"),
                "n1_relevance": relevance or reason,
                "handle": payload.get("handle"),
                "source_outcomes": payload.get("source_outcomes") or [],
            })


def run_factory(*, snapshot: N1Snapshot, source: CadSource, classes: list[str],
                items: list[str] | None, identity_base: dict, limit: int | None = None,
                catalog: str = "v1") -> dict[str, Any]:
    catalog_key = str(catalog or "v1").lower()
    if catalog_key == "v3":
        from .adapters_lv_v3 import run_lv_v3
        lv_audit = None
        other = [c for c in classes if c != "LV"]
        if "LV" in classes:
            lv_audit = run_lv_v3(
                snapshot=snapshot, source=source, identity_base=identity_base,
                items=items, limit=limit,
            )
        if not other:
            return lv_audit or {
                "schema": AUDIT_SCHEMA, "factory_version": FACTORY_V3_VERSION,
                "scanned": 0, "packed": 0, "unpackable": 0, "discarded": 0,
                "discard_reasons": {}, "unpackable_reasons": {}, "cases": [],
                "unpackable_rows": [], "discards": [], "cell_audits": [],
                "n1_relevance_counts": {}, "catalog_revision": CATALOG_V3_REVISION,
                "catalog_sha256": catalog_v3_hash(), "catalog": "v3",
                "audit_sha256": None,
            }
        rest = run_factory(
            snapshot=snapshot, source=source, classes=other, items=items,
            identity_base=identity_base, limit=limit, catalog="v1",
        )
        if lv_audit is None:
            return rest
        merged_cases = list(lv_audit["cases"]) + list(rest["cases"])
        return {
            **lv_audit,
            "scanned": lv_audit["scanned"] + rest["scanned"],
            "packed": len(merged_cases),
            "unpackable": lv_audit["unpackable"] + rest["unpackable"],
            "discarded": lv_audit["discarded"] + rest["discarded"],
            "cases": merged_cases,
            "unpackable_rows": list(lv_audit["unpackable_rows"]) + list(rest["unpackable_rows"]),
            "discards": list(lv_audit["discards"]) + list(rest["discards"]),
            "cell_audits": list(lv_audit.get("cell_audits") or []) + list(rest.get("cell_audits") or []),
            "other_classes_catalog": rest.get("catalog"),
        }
    discoverers = dict(DISCOVERERS)
    if catalog_key == "v2":
        discoverers["LV"] = discover_lv_v2
    discards: list[dict[str, Any]] = []
    packed: list[dict[str, Any]] = []
    unpackable: list[dict[str, Any]] = []
    cell_audits: list[dict[str, Any]] = []
    scanned = 0
    seen_names: set[str] = set()
    for classe in classes:
        if classe not in discoverers:
            discards.append({"classe": classe, "reason": "CLASS_NOT_IN_PHASE1"})
            continue
        class_names = snapshot.names(classe)
        if items:
            names = [name for name in items if name in class_names]
            seen_names.update(names)
        else:
            names = class_names
        for name in names:
            if limit is not None and scanned >= limit:
                break
            n1_item = snapshot.get(classe, name)
            if n1_item is None:
                discards.append({"classe": classe, "item": name, "reason": "ITEM_ABSENT_IN_SNAPSHOT"})
                continue
            scanned += 1
            found = _as_discoveries(
                discoverers[classe](n1_item, source, pavimento=identity_base["pavimento"])
            )
            if isinstance(found, dict) and "packets" in found:
                audits = list(found.get("audits") or [])
                cell_audits.extend(audits)
                _record_audits(audits, discards=discards, unpackable=unpackable)
                for cand in found.get("packets") or []:
                    emitted = emit_case(cand, identity_base=identity_base, snapshot=snapshot,
                                        source=source, n1_item=n1_item)
                    if emitted["status"] == "UNPACKABLE":
                        unpackable.append(emitted)
                    else:
                        packed.append(emitted)
                if not found.get("packets") and found.get("reason") and not audits:
                    reason = str(found.get("reason") or "unknown")
                    row = {
                        "item": found.get("item"), "classe": found.get("classe"),
                        "reason": reason, "detail": found.get("detail"),
                        "n1_relevance": found.get("n1_relevance"),
                    }
                    if reason in UNPACKABLE_REASONS:
                        unpackable.append({"status": "UNPACKABLE", **row})
                    else:
                        discards.append(row)
                continue
            if isinstance(found, dict):
                reason = str(found.get("reason") or "unknown")
                if found.get("audits"):
                    cell_audits.extend(found["audits"])
                    _record_audits(found["audits"], discards=discards, unpackable=unpackable)
                    continue
                if reason in UNPACKABLE_REASONS:
                    unpackable.append({
                        "status": "UNPACKABLE",
                        "reason": reason,
                        "item": found.get("item"),
                        "classe": found.get("classe"),
                        "detail": found.get("detail"),
                        "n1_relevance": found.get("n1_relevance"),
                    })
                else:
                    discards.append(found)
                continue
            for cand in found:
                emitted = emit_case(cand, identity_base=identity_base, snapshot=snapshot,
                                    source=source, n1_item=n1_item)
                if emitted["status"] == "UNPACKABLE":
                    unpackable.append(emitted)
                else:
                    packed.append(emitted)
        if limit is not None and scanned >= limit:
            break
    if items:
        known = {name for (_classe, name) in snapshot.items}
        for name in items:
            if name not in known and name not in seen_names:
                discards.append({"item": name, "reason": "ITEM_ABSENT_IN_SNAPSHOT"})
    reasons = Counter(row.get("reason") or "unknown" for row in discards)
    unpack_reasons = Counter(row.get("reason") or "unknown" for row in unpackable)
    relevance_counts = Counter(
        row.get("n1_relevance") or "UNSET" for row in cell_audits
    )
    if not cell_audits:
        relevance_counts = Counter(
            row.get("n1_relevance") or "UNSET" for row in packed
        )
    v2 = catalog_key == "v2"
    return {
        "schema": AUDIT_SCHEMA,
        "factory_version": FACTORY_V2_VERSION if v2 else FACTORY_VERSION,
        "scanned": scanned,
        "packed": len(packed),
        "unpackable": len(unpackable),
        "discarded": len(discards),
        "discard_reasons": dict(reasons),
        "unpackable_reasons": dict(unpack_reasons),
        "cases": packed,
        "unpackable_rows": unpackable,
        "discards": discards,
        "cell_audits": cell_audits,
        "n1_relevance_counts": dict(relevance_counts),
        "catalog_revision": CATALOG_V2_REVISION if v2 else CATALOG_REVISION,
        "catalog_sha256": catalog_v2_hash() if v2 else catalog_hash(),
        "catalog": catalog_key,
        "audit_sha256": None,
    }


def write_dry_run(out_dir: Path, audit: dict[str, Any], manifest: dict[str, Any]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    from .corpus import append_jsonl

    packets = [row["packet"] for row in audit["cases"]]
    baselines = [row["baseline"] for row in audit["cases"]]
    adjs = [row["adjudication"] for row in audit["cases"]]
    for path in (out_dir / "source_packet.jsonl", out_dir / "baseline.jsonl", out_dir / "adjudication.jsonl"):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite {path}")
    append_jsonl(out_dir / "source_packet.jsonl", packets)
    append_jsonl(out_dir / "baseline.jsonl", baselines)
    append_jsonl(out_dir / "adjudication.jsonl", adjs)
    requests_dir = out_dir / "jev_requests"
    requests_dir.mkdir(parents=True, exist_ok=True)
    written_names: list[str] = []
    for index, row in enumerate(audit["cases"], 1):
        payload = dict(row["jev_request"])
        payload["case_id"] = row["case_id"]
        path = requests_dir / request_filename(index, row["case_id"])
        if path.exists():
            raise FileExistsError(f"refusing to overwrite {path}")
        write_json(path, payload)
        validate_request(payload)
        written_names.append(path.name)
    visible = assert_visible_request_files(out_dir, len(audit["cases"]))
    slim = {k: v for k, v in audit.items() if k != "cases"}
    slim["case_ids"] = [row["case_id"] for row in audit["cases"]]
    slim["request_files"] = written_names
    slim["visible_request_json"] = [path.name for path in visible]
    slim["audit_sha256"] = sha256_json(slim)
    from .catalog_v1 import CATALOG
    write_json(out_dir / "catalog_v1.json", CATALOG)
    paths = {
        "manifest": str(out_dir / "run_manifest.json"),
        "source_packet": str(out_dir / "source_packet.jsonl"),
        "baseline": str(out_dir / "baseline.jsonl"),
        "adjudication": str(out_dir / "adjudication.jsonl"),
        "audit": str(out_dir / "dry_run_audit.json"),
        "catalog": str(out_dir / "catalog_v1.json"),
        "jev_requests": str(requests_dir),
    }
    if audit.get("catalog") == "v2":
        write_json(out_dir / "catalog_v2.json", CATALOG_V2)
        paths["catalog_v2"] = str(out_dir / "catalog_v2.json")
        slim["case_relevance"] = [
            {
                "case_id": row["case_id"],
                "n1_relevance": row.get("n1_relevance"),
                "why": row.get("n1_relevance_why"),
                "catalog_id": row.get("catalog_id"),
            }
            for row in audit["cases"]
        ]
    if audit.get("catalog") == "v3":
        write_json(out_dir / "catalog_v3.json", CATALOG_V3)
        paths["catalog_v3"] = str(out_dir / "catalog_v3.json")
        inventory = audit.get("source_inventory")
        sidecar = audit.get("n1_sidecar")
        if inventory is not None:
            write_json(out_dir / "source_inventory.json", inventory)
            paths["source_inventory"] = str(out_dir / "source_inventory.json")
            slim["source_inventory_sha256"] = inventory.get("inventory_sha256")
            slim["denominators"] = audit.get("denominators") or inventory.get("denominators")
        if sidecar is not None:
            write_json(out_dir / "n1_comparison_sidecar.json", sidecar)
            paths["n1_comparison_sidecar"] = str(out_dir / "n1_comparison_sidecar.json")
            slim["n1_sidecar_sha256"] = sidecar.get("sidecar_sha256")
        slim.pop("source_inventory", None)
        slim.pop("n1_sidecar", None)
        slim.pop("catalog_doc", None)
        slim["case_relevance"] = [
            {
                "case_id": row["case_id"],
                "n1_relevance": row.get("n1_relevance"),
                "why": row.get("n1_relevance_why"),
                "catalog_id": row.get("catalog_id"),
            }
            for row in audit["cases"]
        ]
        control_handles = {"2F8", "2F5", "2F9", "315", "312", "313"}
        control_items = {"V419", "V420", "V411"}
        slim["control_audits"] = [
            {
                "item": row.get("item"),
                "handle": row.get("handle"),
                "at": row.get("at"),
                "face": row.get("face"),
                "n1_relevance": row.get("n1_relevance"),
                "why": row.get("why"),
                "source_outcomes": row.get("source_outcomes") or [],
            }
            for row in audit.get("cell_audits") or []
            if row.get("item") in control_items or row.get("handle") in control_handles
        ]
    slim["audit_sha256"] = sha256_json({k: v for k, v in slim.items() if k != "audit_sha256"})
    write_json(out_dir / "dry_run_audit.json", slim)
    write_json(out_dir / "run_manifest.json", manifest)
    return paths
