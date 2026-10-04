"""Separate JSONL writers for source_packet, baseline and adjudication."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from scripts.arete.jev_sa_second_read import _canonical

from .hashing import sha256_json
from .leakage import scan_evidence_leakage
from .schemas import (
    ADJUDICATION_SCHEMA,
    BASELINE_SCHEMA,
    JEV_REQUEST_SCHEMA,
    SOURCE_PACKET_SCHEMA,
)


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def source_packet_record(case_id: str, identity: dict, physical_unit: dict,
                         question: dict, evidence: dict, controls: list[dict],
                         included: list[dict], excluded: list[dict],
                         *, use_context: str = "QA_B3",
                         qa_snapshot_sha256: str | None = None,
                         catalog_revision: str | None = None) -> dict[str, Any]:
    leaks = scan_evidence_leakage(evidence)
    for control in controls:
        leaks.extend(scan_evidence_leakage(control.get("evidence") or {}))
    if leaks:
        raise ValueError(f"{case_id}: leakage in source_packet: {leaks}")
    record = {
        "schema": SOURCE_PACKET_SCHEMA,
        "case_id": case_id,
        "identity": identity,
        "physical_unit": physical_unit,
        "use_context": use_context,
        "question": question,
        "evidence": evidence,
        "controls": controls,
        "included_entities": included,
        "excluded_entities": excluded,
        "evidence_bytes": len(_canonical(evidence)),
        "catalog_revision": catalog_revision,
        "qa_snapshot_sha256": qa_snapshot_sha256,
    }
    record["record_sha256"] = sha256_json(record)
    return record


def baseline_record(case_id: str, identity: dict, *, sa_value: Any, sa_field: str,
                    qa_decision: Any = None, qa_score: Any = None,
                    router_trigger: str | None = None, cad_rules: list[str] | None = None,
                    cost_without_jev: dict | None = None) -> dict[str, Any]:
    record = {
        "schema": BASELINE_SCHEMA,
        "case_id": case_id,
        "identity": identity,
        "sa_field": sa_field,
        "sa_value": sa_value,
        "qa_decision": qa_decision,
        "qa_score": qa_score,
        "router_trigger": router_trigger,
        "cad_rules": cad_rules or [],
        "cost_without_jev": cost_without_jev or {"calls": 0, "note": "deterministic CAD/QA only"},
        "visible_to_jev": False,
    }
    record["record_sha256"] = sha256_json(record)
    return record


def adjudication_record(case_id: str, identity: dict, *, status: str,
                        handles: list[str] | None = None, png_relpath: str | None = None,
                        convention: str | None = None, gravity: str | None = None,
                        notes: str | None = None, agents: list[str] | None = None,
                        consensus: bool = False) -> dict[str, Any]:
    record = {
        "schema": ADJUDICATION_SCHEMA,
        "case_id": case_id,
        "identity": identity,
        "status": status,
        "supporting_handles": handles or [],
        "png_relpath": png_relpath,
        "convention": convention,
        "gravity": gravity,
        "notes": notes,
        "agents": agents or [],
        "consensus": consensus,
        "visible_to_jev": False,
    }
    record["record_sha256"] = sha256_json(record)
    return record


def to_jev_request(packet: dict, baseline: dict) -> dict[str, Any]:
    """Join packet + baseline into the existing helper contract. Evidence stays clean."""
    request = {
        "schema": JEV_REQUEST_SCHEMA,
        "identity": packet["identity"],
        "use_context": packet.get("use_context") or "QA_B3",
        "baseline_sa": {
            "value": baseline.get("sa_value"),
            "field": baseline.get("sa_field"),
            "source": "calibration_baseline",
        },
        "question": packet["question"],
        "evidence": packet["evidence"],
        "controls": packet["controls"],
    }
    if packet.get("qa_snapshot_sha256"):
        request["qa_snapshot_sha256"] = packet["qa_snapshot_sha256"]
    return request
